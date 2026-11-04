"""수도권 지하철 그래프 구성과 최소 소요시간 경로 탐색."""

import heapq
from itertools import count

from .data_loader import DAYS, CongestionDataLoader
from .edge import RideEdge, TransferEdge
from .station import Station
from .vertex import Vertex


class Route:
    """출발부터 도착까지 실제로 거친 탑승·환승 간선을 순서대로 보관한다."""

    def __init__(self, edges):
        self.edges = edges

    def total_time(self):
        """탑승 시간과 환승 시간을 더한 값(초)."""
        return sum(edge.cost() for edge in self.edges)

    def transfer_count(self):
        return sum(isinstance(edge, TransferEdge) for edge in self.edges)

    def stops(self):
        """(이동한 정거장 수, 총 이동거리 m). 거리 누락이 있으면 거리는 None."""
        count_rides = sum(isinstance(edge, RideEdge) for edge in self.edges)
        if any(edge.meters is None for edge in self.edges):
            return count_rides, None
        return count_rides, sum(edge.meters for edge in self.edges)

    def avg_congestion(self, day, departure_time):
        """각 탑승 구간 진입 시각의 혼잡도 산술평균(%). 계산할 수 없으면 None."""
        if day not in DAYS:
            raise ValueError(f"요일은 {DAYS} 중 하나여야 합니다.")
        hour, minute = map(int, departure_time.split(":"))
        if not (0 <= hour < 24 and 0 <= minute < 60):
            raise ValueError("출발 시각은 00:00~23:59 범위여야 합니다.")
        # 새벽 0시대는 선택한 운행일의 마지막 시간대다.
        clock = ((hour + 24 if hour < 5 else hour) * 60 + minute) * 60
        values = []
        for edge in self.edges:
            if isinstance(edge, RideEdge):
                if clock < (5 * 60 + 30) * 60 or clock >= 25 * 3600:
                    return None
                slot = f"{clock // 3600 % 24:02d}:{clock % 3600 // 1800 * 30:02d}"
                value = edge.congestion_get(day, slot)
                if value is None:
                    return None
                values.append(value)
            clock += edge.cost()  # 환승 보행 시간도 다음 탑승 시각에 반영
        return sum(values) / len(values) if values else None


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


def _cycle_rides(route):
    """이미 지난 물리적 역으로 돌아온 경우 그 순환에 포함된 탑승 간선을 반환한다."""
    rides = [edge for edge in route.edges if isinstance(edge, RideEdge)]
    if not rides:
        return []
    positions = {rides[0].from_v.station: 0}
    for index, ride in enumerate(rides, start=1):
        station = ride.to_v.station
        if station in positions:
            return rides[positions[station]:index]
        positions[station] = index
    return []


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
        route = self._dijkstra(origin, destination, line=line)
        if route is None:
            return []
        if not route.edges:
            return [next(v for v in origin.vertices if v.line == line)]
        return [route.edges[0].from_v] + [edge.to_v for edge in route.edges]

    def shortest(self, start, end):
        """최단시간 Route. 동률이면 환승이 적은 경로, 연결되지 않았으면 None."""
        return self._best_route(self._station(start), self._station(end))

    def route_options(self, start, end):
        """최단시간, 최소 환승, 두 번째 최단시간 Route를 각각 반환한다."""
        origin, destination = self._station(start), self._station(end)
        fastest = self._best_route(origin, destination)
        fewest = fastest
        second = None
        if fastest is not None and fastest.edges:
            if fastest.transfer_count():
                fewest = self._best_route(origin, destination, fewest_first=True)
            # 서로 다른 단순 경로라면 첫 경로의 탑승 간선이 적어도 하나 빠진다.
            exclusions = (frozenset([e]) for e in fastest.edges if isinstance(e, RideEdge))
            second = self._best_route(origin, destination, exclusions=exclusions)
        return {"fastest": fastest, "fewest_transfers": fewest, "second_fastest": second}

    def _best_route(self, origin, destination, *, fewest_first=False, exclusions=(frozenset(),)):
        """간선 제외 조건별 최선 후보를 비교해 물리적 역 재방문이 없는 경로를 고른다."""
        candidates = []
        seen = set()
        sequence = count()

        def add_candidate(excluded):
            if excluded in seen:
                return
            seen.add(excluded)
            route = self._dijkstra(origin, destination, fewest_first, excluded)
            if route is not None:
                rank = (route.total_time(), route.transfer_count())
                if fewest_first:
                    rank = rank[::-1]
                heapq.heappush(candidates, (rank, next(sequence), excluded, route))

        for excluded in exclusions:
            add_candidate(excluded)
        while candidates:
            _, _, excluded, route = heapq.heappop(candidates)
            cycle = _cycle_rides(route)
            if not cycle:
                return route
            # 이 순환을 피하는 모든 경로는 순환 간선 중 하나 이상을 사용하지 않는다.
            for ride in cycle:
                add_candidate(excluded | {ride})
        return None

    def _dijkstra(self, origin, destination, fewest_first=False, excluded=frozenset(), line=None):
        # 상태 = (현재 역코드, 직전 탑승역 코드, 환승 후 타야 할 다음 역코드).
        best = {}
        came_from = {}
        queue = []
        for vertex in origin.vertices:
            if line is not None and vertex.line != line:
                continue
            state = (vertex.station_code, "", "")
            best[state] = (0, 0)
            heapq.heappush(queue, ((0, 0), state))

        while queue:
            score, state = heapq.heappop(queue)
            if score != best[state]:
                continue
            code, previous_code, required_next = state
            current = self.vertices[code]
            if current.station is destination:
                edges = []
                while state in came_from:
                    state, edge = came_from[state]
                    edges.append(edge)
                return Route(list(reversed(edges)))

            for edge in current.edges:
                if edge in excluded:
                    continue
                next_code = edge.to_v.station_code
                transfer = isinstance(edge, TransferEdge)
                if transfer:
                    if line is not None or previous_code != edge.from_prev_code:
                        continue
                    next_state = (next_code, "", edge.to_next_code)
                else:
                    if required_next and next_code != required_next:
                        continue
                    next_state = (next_code, code, "")

                # 두 기준 모두 작은 순서로 비교한다. 최소 환승 모드에서는 순서만 바뀐다.
                primary, secondary = (int(transfer), edge.cost()) if fewest_first else (edge.cost(), int(transfer))
                candidate = (score[0] + primary, score[1] + secondary)
                if next_state not in best or candidate < best[next_state]:
                    best[next_state] = candidate
                    came_from[next_state] = (state, edge)
                    heapq.heappush(queue, (candidate, next_state))
        return None
