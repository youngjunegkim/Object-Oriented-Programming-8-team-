"""수도권 지하철 그래프 구성과 최소 소요시간 경로 탐색."""

from ..loaders.data_loader import CongestionDataLoader
from ..service_time import DAYS
from ..models.edge import RideEdge, TransferEdge
from ..models.route import Route as Route  # 기존 import 경로 유지
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


class SubwayGraph:  #데이터를 담을 공간을 준비
    def __init__(self, loader=None, finder_factory=RouteFinder):
        self.loader = CongestionDataLoader() if loader is None else loader  #self.loader는 CSV를 읽어줄 객체임.
        self.finder_factory = finder_factory  # 경로를 찾을 탐색기를 만드는 도구. 기본은 RouteFinder
        self.vertices = {}  # 역코드 → 호선별 Vertex(역코드로 호선별 vertex찾기)
        self.edges = []     # 전체 탑승, 환승 edge: 만들어진 모든 이동 구간 보관
        self.line_order = {}  # 호선 → 지선 → 순서대로 정렬한 Vertex 목록(지선은 길이 갈라지는 역임, 노선을 순서대로 표시할 떄 사용)
        self.stations = {}  # 역 이름 → 후보 Station 목록 (목록이 이유는 이름은 같지만 위치가 다른 역을 구분: 동명이역 구분) (역 이름별 station 후보 목록: "가락시장으로 물리적인 역 찾기")
                               #역 이름: Station객체
 
        # 저장 공간만 준비했으므로 아직 역과 연결 정보가 들어 있지 않음. 그 작업은 build()가 함                     
    def build(self): #지하철 그래프 구성(데이터를 읽어 Station과 호선별 Vertex를 만듦)
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



        #열차를 타고 이동하는 연결 만들기(이미 만들어 놓은 Vertex들을 이동가능한 길인 Edge로 연결)
        line_order = {}

        for line, rows in self.loader.load_distance().items(): #호선을 key, 그 호선의 구간 정보 리스트를 value로 가지는 딕셔너리
            line_order[line] = _branch_order(rows, vertices) #해당 호선의 역들을 지선별로 순서대로 정리
            #Ex) 8호선 가락시장 -> 송파 구간 처리: start =start = vertices["2818"]  # 가락시장 8호선 Vertex,  end = vertices["2817"]    # 송파 8호선 Vertex
            for row in rows:
                start = vertices[row["from_code"]]  #start와 end를 앞에서 만들어진 Vertex객체로 저장
                end = vertices[row["to_code"]]

                #해당 구간의 혼잡도를 찾을 key를 만든 것
                key = (line, start.station_code, end.station_code) #key = ("8호선", "2818", "2817") vertex에 있는 station_code임 
                #해당 구간의 RideEdge객체를 생성함
                ride = RideEdge(start, end, row["seconds"], row["meters"], congestion[key]) #***************Rideedge객체를 만들어냄.********************
                start.add_edge(ride)   #start인 가락시장 정점의 edges 리스트에 방금 만든 간선을 넣음

        #환승 구간 만들기 (transfer의 dict형태의 key를 꺼내 start, end로 정점 객체 만듦)
        for (from_code, to_code), rows in transfers.items(): #transfers의 key값으로 (from_code, to_code)가 있음,  rows 이 두정점 사이의 방향별 환승 정보들

            start, end = vertices[from_code], vertices[to_code] #환승 출발, 도착 정점 객체
            #방향별 환승 정보마다 객체를 만듦(rows에 있는 정점 객체를 꺼내어 start에 transfer 객체를 추가)
            for row in rows:
                transfer = TransferEdge(
                    start, end, row["seconds"], row["meters"],
                    from_prev_code=row["from_prev_code"],
                    to_next_code=row["to_next_code"],
                )
                start.add_edge(transfer)      #이로써 RideEdge와 transferedge가 start에 쌓임
                        #start.add_edge(...)는 이 정점에서 출발할 수 있는 이동 방법을 등록하는 것임.
                        #이후 다익스트라는 현재 정점의 edges를 하나씩 확인하면서 조건에 맞는 이동 중 더 빠른 경로를 찾아가는 것임
        edges = []  #기존객체를 이용해서 간선을 하나의 리스트로 만듦
        for vertex in vertices.values():
            for edge in vertex.edges:
                edges.append(edge)
                #vertices.values(): 딕셔너리에 들어 있는 모든 Vertex 객체
                #vertex.edges: 해당 정점에서 출발하는 간선 목록
                #edges.append(edge): 전체 간선 리스트에 간선을 추가
        self.stations, self.vertices = stations, vertices
        self.edges, self.line_order = edges, line_order

        #build에서 만든 데이터 객체를 보관해야, build()가 끝난 뒤에도 다른 메서드를 사용할 수 있음

    def _station(self, name_or_code, line=None): #역 이름이나 역코드로 Station을 찾는다. 이름이 같은 역이 여러 개면 역코드로 구분하도록 오류를 발생
        """역코드 입력도 해당 물리적 역을 선택한다. 출발 호선은 자유롭게 고른다."""
        if not self.vertices:
            raise RuntimeError("먼저 build()로 그래프를 구성하세요.")
        #candidates는 후보 Station 객체를 담은 리스트
        if name_or_code in self.vertices: #역코드로 찾기
            candidates = [self.vertices[name_or_code].station]  #self.vertices는 역코드로 Vertex객체를 얻을 수 있는 것임
        else: #역이름으로 찾기 
            candidates = self.stations.get(name_or_code, [])

        if line is not None:
            filtered_candidates = []
            for station in candidates:
                for vertex in station.vertices:
                    if vertex.line == line:
                        filtered_candidates.append(station)
                        break  # 하나만 발견해도 이 역은 조건을 만족함
                    
            candidates = filtered_candidates
            #Station 내부의 다른 호선 정점을 삭제하거나, 이후 경로 탐색의 출발호선을 강제로 고정하지는 않음
        if not candidates:
            raise ValueError(f"찾을 수 없는 역입니다: {name_or_code}")
        #후보가 둘 이상이면 어느 역인지 구분할 수 없는 오류를 냄
        if len(candidates) > 1:
            options = [f"{v.line} {v.station_code}" for s in candidates for v in s.vertices]
            raise ValueError(f"동명이역입니다. 역코드를 입력하세요: {', '.join(options)}")
        return candidates[0] #후보는 정확히 하나이고 그 Station 객체를 반환한다. 

    def station_congestion(self, station, next_station, line, day): #특정 역에서 바로 다음 역으로 출발하는 방향의 시간대별 혼잡도를 반환
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

    def stations_between(self, start, end, line): #환승 없이 두 역 사이를 가장 빠르게 이동하는 경로의 정점 목록을 반환
        """같은 호선에서 가장 빠른 탑승 경로의 Vertex 목록(양 끝 포함)."""
        origin = self._station(start, line)
        destination = self._station(end, line)
        route = self.finder_factory(self.vertices).on_line(origin, destination, line)
        if route is None:
            return []
        if not route.edges:
            return [next(v for v in origin.vertices if v.line == line)]
        return [route.edges[0].from_v] + [edge.to_v for edge in route.edges]

    def shortest(self, start, end, *, priority=time_first):  #route = graph.shortest("수서", "송파")
        #1. "수서", "송파"라는 문자열로 실제 Station 객체를 찾는다.
        #2. 만들어 둔 정점 정보를 RouteFinder에 전달해서 경로를 찾게 한다.
        """기본은 최소 소요시간. priority(edge)로 다른 비용 기준을 선택할 수 있다."""
        origin, destination = self._station(start), self._station(end) #Station객체를 받아옴
        return self.finder_factory(self.vertices).best_route(origin, destination, priority=priority) #priority는 경로 비교 기준이며, 기본은 시간 우선·동률이면 환승 횟수 우선이다.
    
    def route_options(self, start, end):
        """최단시간, 최소 환승, 두 번째 최단시간 Route를 각각 반환한다."""
        origin, destination = self._station(start), self._station(end)
        return self.finder_factory(self.vertices).route_options(origin, destination)
