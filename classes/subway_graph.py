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


class SubwayGraph:  #데이터를 담을 공간을 준비
    def __init__(self, loader=None):
        self.loader = CongestionDataLoader() if loader is None else loader  #self.loader는 CSV를 읽어줄 객체임.
        self.vertices = {}  # 역코드 → 호선별 Vertex(역코드로 호선별 vertex찾기)
        self.edges = []     # 전체 탑승, 환승 edge: 만들어진 모든 이동 구간 보관
        self.line_order = {}  # 호선 → 지선 → 순서대로 정렬한 Vertex 목록(지선은 길이 갈라지는 역임, 노선을 순서대로 표시할 떄 사용)
        self.stations = {}  # 역 이름 → 후보 Station 목록 (목록이 이유는 이름은 같지만 위치가 다른 역을 구분: 동명이역 구분) (역 이름별 station 후보 목록: "가락시장으로 물리적인 역 찾기")
                               #역 이름: Station객체
 
        # 저장 공간만 준비했으므로 아직 역과 연결 정보가 들어 있지 않음. 그 작업은 build()가 함                     
    def build(self):
        """CSV를 읽어 정점을 만들고, 각 정점에 출발 간선을 등록한다."""
        station_rows = self.loader.load_stations() # 역정보를 담은 리스트(역코드, 역 이름, 호선 정보)  (list안에 dict형을 받아옴)
        transfers = self.loader.load_transfers() # 환승 구간별 상세 정보를 담은 dict, 어느 호선에서 어느 호선으로 환승할 수 있는지 들어있음 (전역과 다음역의 역코드를 튜플로 묶어 키로 환승 목록을 기록)
        groups = _station_groups(station_rows, transfers) #각 역코드의 물리적인 역, 어떤 역코드들이 같은 물리적 역에 속하는지 들어있음. 같은 역에 여러 호선이 있을 수 있어서(dict 형태로 value값이 같으면 같은 물리적 역으로 묶인다는 뜻)
        congestion = self.loader.load_congestion() # 구간별, 요일별, 시간대별 혼잡도가 들어있음(계산이 되어 (평일, 토요일, 일요일)가 각각 key로 되어 혼잡도가 들어있음)

        stations_by_group = {}
        stations = {}
        vertices = {}
        #데이터를 Station, Vertex, Edge 객체로 바꿔서 연결
        for row in station_rows:            #역정보를 담은 리스트(역코드, 역 이름, 호선 정보) -> 역정보를 한 행씩 꺼내서 역코드, 역이름, 그룹(물리적 역코드)을 확인함
            code, name = row["station_code"], row["name"] #역코드, 역이름
            group = groups[code]                          #각 역코드의 물리적인 역 (두 역코드는 다르지만 같은 그룹일 수 있음.)
            if group not in stations_by_group:      #group코드가 없을때
                stations_by_group[group] = Station(name)  #station_by_group에 없을 때임 (해당 그룹의 Station이 없을 때만 새로 만든다.)
            
            station = stations_by_group[group]

            candidates = stations.setdefault(name, []) #name이라는 key가 없으면 빈 리스트를 넣고 그 key에 연결된 리스트를 반환한다는 뜻
            if station not in candidates:
                candidates.append(station)
#Ex) 3호선 가락시장을 처리할 떄 Station("가락시장")이 만들어졌다면, 8호선 가락시장을 처리할 떄는 그 객체를 그대로 사용함.
            vertex = Vertex(code, station, row["line"]) #역코드, 소속역, 호선으로 Vertex 객체 생성
            station.add_vertex(vertex) #해당 vertex객체를 station에 Vertex등록
            vertices[code] = vertex    #역코드로 접근 가능하게 vertices에 등록



        #열차를 타고 이동하는 연결 만들기
        line_order = {}

        for line, rows in self.loader.load_distance().items():
            line_order[line] = _branch_order(rows, vertices)
            #Ex) 8호선 가락시장 -> 송파 구간 처리: start =start = vertices["2818"]  # 가락시장 8호선 Vertex,  end = vertices["2817"]    # 송파 8호선 Vertex
            for row in rows:
                start = vertices[row["from_code"]]
                end = vertices[row["to_code"]]
                key = (line, start.station_code, end.station_code) #key = ("8호선", "2818", "2817") vertex에 있는 station_code임 
              
                ride = RideEdge(start, end, row["seconds"], row["meters"], congestion[key]) #***************Rideedge객체를 만들어냄.********************
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
