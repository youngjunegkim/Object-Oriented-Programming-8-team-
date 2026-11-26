"""CSV를 읽어 수도권 지하철 그래프(Station · Vertex · Edge)를 구성하고 경로 탐색을 요청한다."""

from ..loaders.data_loader import CongestionDataLoader
from ..models.edge import RideEdge, TransferEdge
from .route_finder import RouteFinder, time_first
from ..models.station import Station
from ..models.vertex import Vertex


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
    def __init__(self, loader=None, finder_factory=RouteFinder):
        self.loader = CongestionDataLoader() if loader is None else loader
        self.finder_factory = finder_factory
        self.vertices = {}    # 역코드 → 호선별 Vertex
        self.line_order = {}  # 호선 → 지선 → 순서대로 정렬한 Vertex 목록
        self.stations = {}    # 역 이름 → Station 목록 (동명이역이 있어 목록)
        self.finder = None    # build()가 만드는 경로 탐색기

    def build(self):
        """CSV를 읽어 정점을 만들고, 각 정점에 출발 간선을 등록한다."""
        station_rows = self.loader.load_stations()
        transfers = self.loader.load_transfers()
        groups = _station_groups(station_rows, transfers)
        congestion = self.loader.load_congestion()

        # 환승으로 묶인 역코드들은 Station 하나를 함께 쓴다. 예: 3호선·8호선 가락시장
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

        # 탑승 간선: 같은 호선의 이웃 정점을 방향별로 잇고 구간 혼잡도를 붙인다.
        line_order = {}
        for line, rows in self.loader.load_distance().items():
            line_order[line] = _branch_order(rows, vertices)
            for row in rows:
                start = vertices[row["from_code"]]
                end = vertices[row["to_code"]]
                key = (line, start.station_code, end.station_code)
                ride = RideEdge(start, end, row["seconds"], row["meters"], congestion[key])
                start.add_edge(ride)

        # 환승 간선: 같은 정점 쌍이라도 진입·진출 방향별로 따로 만든다.
        for (from_code, to_code), rows in transfers.items():
            start, end = vertices[from_code], vertices[to_code]
            for row in rows:
                transfer = TransferEdge(
                    start, end, row["seconds"], row["meters"],
                    from_prev_code=row["from_prev_code"],
                    to_next_code=row["to_next_code"],
                )
                start.add_edge(transfer)

        self.stations, self.vertices, self.line_order = stations, vertices, line_order
        self.finder = self.finder_factory(vertices)

    def _station(self, name_or_code, line=None):
        """역 이름이나 역코드로 Station을 찾는다. line을 주면 그 호선이 지나는 역만 후보로 본다."""
        if not self.vertices:
            raise RuntimeError("먼저 build()로 그래프를 구성하세요.")
        if name_or_code in self.vertices:
            candidates = [self.vertices[name_or_code].station]
        else:
            candidates = self.stations.get(name_or_code, [])

        if line is not None:
            filtered_candidates = []
            for station in candidates:
                for vertex in station.vertices:
                    if vertex.line == line:
                        filtered_candidates.append(station)
                        break
            candidates = filtered_candidates

        if not candidates:
            raise ValueError(f"찾을 수 없는 역입니다: {name_or_code}")
        if len(candidates) > 1:
            options = [f"{v.line} {v.station_code}" for s in candidates for v in s.vertices]
            raise ValueError(f"동명이역입니다. 역코드를 입력하세요: {', '.join(options)}")
        return candidates[0]

    def shortest(self, start, end, *, priority=time_first):
        """기본은 최소 소요시간. priority(edge)로 다른 비용 기준을 선택할 수 있다."""
        origin, destination = self._station(start), self._station(end)
        return self.finder.best_route(origin, destination, priority=priority)

    def route_options(self, start, end):
        """최단시간, 최소 환승, 두 번째 최단시간 Route를 각각 반환한다."""
        origin, destination = self._station(start), self._station(end)
        return self.finder.route_options(origin, destination)
