"""수도권 지하철 그래프 구성과 최소 소요시간 경로 탐색."""

from .data_loader import DAYS, CongestionDataLoader
from .edge import RideEdge, TransferEdge
from .route import Route as Route  # 기존 import 경로 유지
from .route_finder import RouteFinder, time_first
from .station import Station
from .vertex import Vertex


def _station_groups(station_rows, transfers):
    """환승으로 연결된 코드끼리 묶는다. 이름만 같은 두 신촌역은 따로 남는다."""
    parent = {row["station_code"]: row["station_code"] for row in station_rows}

    def representative(code):
        while code != parent[code]:
            parent[code] = parent[parent[code]]
            code = parent[code]
        return code

    for from_code, to_code in transfers:
        parent[representative(from_code)] = representative(to_code)
    return {code: representative(code) for code in parent}


def _branch_order(rows, vertices):
    """지선별 선형·순환 구간을 복원한다. CSV의 보정 행은 순서가 뒤에 올 수 있다."""
    branches = {}
    for row in rows:
        neighbors = branches.setdefault(row["branch"], {})
        start, end = row["from_code"], row["to_code"]
        neighbors.setdefault(start, {})[end] = None
        neighbors.setdefault(end, {})[start] = None

    order = {}
    for branch, neighbors in branches.items():
        # 선형 노선은 끝점에서, 순환선은 CSV의 첫 정점에서 출발한다.
        code = next((v for v in neighbors if len(neighbors[v]) == 1), next(iter(neighbors)))
        seen = set()
        ordered = []
        while code is not None:
            seen.add(code)
            ordered.append(vertices[code])
            code = next((v for v in neighbors[code] if v not in seen), None)
        if len(seen) != len(neighbors) or any(len(adj) > 2 for adj in neighbors.values()):
            raise ValueError(f"지선의 역 순서를 정할 수 없습니다: {branch}")
        order[branch] = ordered
    return order


class SubwayGraph:
    def __init__(self, loader=None):
        self.loader = CongestionDataLoader() if loader is None else loader
        self.vertices = {}  # 역코드 → 호선별 Vertex
        self.edges = []
        self.line_order = {}  # 호선 → 지선 → 순서대로 정렬한 Vertex 목록
        self.stations = {}  # 역 이름 → 후보 Station 목록 (동명이역 구분)

    def build(self):
        """CSV를 읽어 정점을 만들고, 각 정점에 출발 간선을 등록한다."""
        station_rows = self.loader.load_stations()
        transfers = self.loader.load_transfers()
        groups = _station_groups(station_rows, transfers)
        congestion = self.loader.load_congestion()

        stations_by_group = {}
        stations = {}
        vertices = {}
        for row in station_rows:
            code, name = row["station_code"], row["name"]
            group = groups[code]
            if group not in stations_by_group:
                stations_by_group[group] = Station(name)
            station = stations_by_group[group]
            candidates = stations.setdefault(name, [])
            if station not in candidates:
                candidates.append(station)

            vertex = Vertex(code, station, row["line"])
            station.add_vertex(vertex)
            vertices[code] = vertex

        line_order = {}
        for line, rows in self.loader.load_distance().items():
            line_order[line] = _branch_order(rows, vertices)
            for row in rows:
                start = vertices[row["from_code"]]
                end = vertices[row["to_code"]]
                key = (line, start.station_code, end.station_code)
                ride = RideEdge(start, end, row["seconds"], row["meters"], congestion[key])
                start.add_edge(ride)

        for (from_code, to_code), rows in transfers.items():
            start, end = vertices[from_code], vertices[to_code]
            for row in rows:
                transfer = TransferEdge(
                    start, end, row["seconds"], row["meters"],
                    from_prev_code=row["from_prev_code"],
                    to_next_code=row["to_next_code"],
                )
                start.add_edge(transfer)

        edges = [edge for vertex in vertices.values() for edge in vertex.edges]
        self.stations, self.vertices = stations, vertices
        self.edges, self.line_order = edges, line_order

    def _station(self, name_or_code, line=None):
        """역코드 입력도 해당 물리적 역을 선택한다. 출발 호선은 자유롭게 고른다."""
        if not self.vertices:
            raise RuntimeError("먼저 build()로 그래프를 구성하세요.")
        if name_or_code in self.vertices:
            candidates = [self.vertices[name_or_code].station]
        else:
            candidates = self.stations.get(name_or_code, [])
        if line is not None:
            candidates = [s for s in candidates if any(v.line == line for v in s.vertices)]
        if not candidates:
            raise ValueError(f"찾을 수 없는 역입니다: {name_or_code}")
        if len(candidates) > 1:
            options = [f"{v.line} {v.station_code}" for s in candidates for v in s.vertices]
            raise ValueError(f"동명이역입니다. 역코드를 입력하세요: {', '.join(options)}")
        return candidates[0]

    def station_congestion(self, station, next_station, line, day):
        """선택한 역에서 같은 호선의 이웃 역 방향으로 출발하는 30분별 혼잡도."""
        if day not in DAYS:
            raise ValueError(f"요일은 {DAYS} 중 하나여야 합니다.")
        origin = self._station(station, line)
        neighbor = self._station(next_station, line)
        for vertex in origin.vertices:
            if vertex.line == line:
                for edge in vertex.edges:
                    if isinstance(edge, RideEdge) and edge.to_v.station is neighbor:
                        return dict(edge.congestion_get(day))
        raise ValueError(f"{line}에서 {station} → {next_station} 방향의 탑승 구간이 없습니다.")

    def stations_between(self, start, end, line):
        """같은 호선에서 가장 빠른 탑승 경로의 Vertex 목록(양 끝 포함)."""
        origin = self._station(start, line)
        destination = self._station(end, line)
        route = RouteFinder(self.vertices).on_line(origin, destination, line)
        if route is None:
            return []
        if not route.edges:
            return [next(v for v in origin.vertices if v.line == line)]
        return [route.edges[0].from_v] + [edge.to_v for edge in route.edges]

    def shortest(self, start, end, *, priority=time_first):
        """기본은 최소 소요시간. priority(edge)로 다른 비용 기준을 선택할 수 있다."""
        origin, destination = self._station(start), self._station(end)
        return RouteFinder(self.vertices).best_route(origin, destination, priority=priority)

    def route_options(self, start, end):
        """최단시간, 최소 환승, 두 번째 최단시간 Route를 각각 반환한다."""
        origin, destination = self._station(start), self._station(end)
        return RouteFinder(self.vertices).route_options(origin, destination)
