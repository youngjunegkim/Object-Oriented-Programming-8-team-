"""역·간선을 따라 경로를 찾는다. 먼저 _dijkstra()의 1~5단계를 읽으면 된다."""
"""route_finder.py: 만들어진 지하철 그래프에서 조건에 맞는 이동 경로를 찾는 파일"""
import heapq
from itertools import count

from ..models.edge import RideEdge
from ..models.route import Route

#time_first(): 시간 우선으로 비교
#transfers_first(): 환승 횟수 우선으로 비교
#_restore_route(): 이동 기록으로 Route 객체 생성
#_cycle_rides(): 경로에서 같은 역으로 돌아오는 구간 확인

def time_first(edge):
    """	시간 우선으로 비교하고, 시간이 같으면 환승이 적은 경로 선택"""
    return edge.cost(), int(edge.is_transfer)


def transfers_first(edge):
    """환승 횟수 우선으로 비교하고, 횟수가 같으면 시간이 짧은 경로 선택"""
    return int(edge.is_transfer), edge.cost()


def _restore_route(previous_steps, end_state):
    """도착역부터 이동 기록을 거꾸로 따라간 뒤, 출발 → 도착 순서로 정렬해 Route 생성"""
    edges = []
    state = end_state
    while state in previous_steps:
        previous_state, edge = previous_steps[state]
        edges.append(edge)
        state = previous_state

    edges.reverse()
    return Route(edges)


def _cycle_rides(route):
    """	경로에서 같은 역을 재방문하는 부분의 탑승 간선 찾기"""
    rides = []
    for edge in route.edges:
        if isinstance(edge, RideEdge):
            rides.append(edge)
    if not rides:
        return []

    station_positions = {rides[0].from_v.station: 0}
    for index, ride in enumerate(rides, start=1): #enumerate 각 항목에 순서번호(인덱스)를 매겨줌-> 튜플이 됨
        station = ride.to_v.station
        if station in station_positions:
            cycle_start = station_positions[station]
            return rides[cycle_start:index]
        station_positions[station] = index
    return []

#만들어진 지하철 연결을 따라 경로를 찾는 클래스
#self.vertices: SubwayGraph에서 전달받은 역코드별 정점들
#_dijkstra(): 다익스트라로 비용이 가장 작은 경로 탐색
#best_route(): 탐색 결과에서 같은 역을 다시 방문하는 경로를 제외
#on_line(): 환승 없이 같은 호선 안에서 경로 탐색
#route_options(): 최단시간·최소 환승·두 번째 경로 반환

class RouteFinder:
    def __init__(self, vertices): #	탐색에 사용할 역코드별 정점 정보를 저장
        self.vertices = vertices  # 역코드 → Vertex 객체

    def on_line(self, origin, destination, line): #	같은 호선에서 환승 없이 이동하는 가장 빠른 경로 찾기
        """환승 없이 같은 호선의 탑승 간선만 따라간다."""
        result = self._dijkstra(origin, destination, line=line)
        if result is None:
            return None
        cost, route = result
        return route

    def route_options(self, origin, destination): #	최단시간·최소환승·두 번째 최단시간 경로를 묶어 반환
        """최단시간, 최소 환승, 두 번째 최단시간 경로를 반환한다."""
        fastest = self.best_route(origin, destination)
        fewest_transfers = fastest
        second_fastest = None

        if fastest is not None and fastest.edges:
            # 이미 환승이 0번이면 최소 환승 경로를 다시 찾을 필요가 없다.
            if fastest.transfer_count() > 0:
                fewest_transfers = self.best_route(
                    origin, destination, priority=transfers_first
                )

            # 최단 경로의 탑승 간선을 하나씩 막아서 다른 경로를 찾는다.
            exclusions = []
            for edge in fastest.edges:
                if isinstance(edge, RideEdge):
                    exclusions.append(frozenset([edge]))
            second_fastest = self.best_route(
                origin, destination, exclusions=exclusions
            )

        return {
            "fastest": fastest,
            "fewest_transfers": fewest_transfers,
            "second_fastest": second_fastest,
        }


    #best_route()가 _dijkstra()를 호출해서 사용하는 관계
    #_dijkstra(): 주어진 조건에서 비용이 가장 작은 경로를 찾음.
    #best_route(): 그 경로가 같은 역을 다시 방문하는지 확인하고, 필요하면 조건을 바꿔 _dijkstra()를 다시 호출.
    def best_route(self, origin, destination, *, priority=time_first, exclusions=(frozenset(),)): #	다익스트라 결과에 역 재방문이 있으면 해당 구간의 간선을 제외하며 다시 탐색
        """간선 제외 조건별로 탐색하고, 같은 물리적 역을 재방문하지 않는 경로를 고른다."""
        #candidates: 찾은 경로 후보들
        #checked_exclusions: 이미 탐색한 간선 제외 조건들
        #sequence: 비용이 같은 후보를 구분할 순번

        candidates = []           #찾아낸 경로 후보들을 비용순으로 보관
        checked_exclusions = set() # 이미 시도한 ‘간선 제외 조합’을 기록
        sequence = count()  # 비용이 같은 후보를 구분하기 위한 번호

        def add_candidate(excluded):   #경로를 하나 찾아 후보에 넣는다.
            # frozenset은 변경할 수 없는 집합이므로, 확인한 조건의 집합에 넣을 수 있다.
            if excluded in checked_exclusions: #같은 제외 조건으로 이미 탐색했다면 건너뛰고, 처음이면 기록
                return
            checked_exclusions.add(excluded)

            result = self._dijkstra(origin, destination, priority=priority, excluded=excluded) #이미 시도한 제외조건이면 중복 탐색하지 않음.
            #result=( , )
            if result is None:
                return
            #경로가 있으면 비용·순번·제외 조건·경로를 묶어서 후보에 넣음.
            cost, route = result
            candidate = (cost, next(sequence), excluded, route) #sequence 1증가
            heapq.heappush(candidates, candidate)   #경로가 있으면 비용, 번호, 제외 조건, 경로를 후보 큐에 넣는다.
            #candidate 하나를 candidates에 넣는 코드,  나중에 비용이 가장 작은 후보부터 꺼낼 수 있게 넣어줌.

        #exclusions에 들어 있는 제외 조건을 하나씩 꺼내서, 그 조건으로 경로를 찾음.
      
        for excluded in exclusions:
            add_candidate(excluded)

        while candidates:  #가장 저렴한 경로를 꺼내 재방문을 확인
            cost, order, excluded, route = heapq.heappop(candidates)
            cycle_edges = _cycle_rides(route)
            if not cycle_edges:
                return route    # *******같은 역을 재방문하지 않았다면 이 경로를 최종 반환********

            # 순환을 없애려면 그 순환의 간선 중 적어도 하나를 쓰지 않아야 한다.
            for edge in cycle_edges:
                new_excluded = excluded | {edge}  # 기존 제외 간선에 하나를 추가
                add_candidate(new_excluded)
        return None

    def _dijkstra(self, origin, destination, priority=time_first, excluded=frozenset(), line=None):
        """주어진 제외·호선 조건에서 (최소 비용, Route)를 반환한다. 못 찾으면 None.

        priority(edge)는 음수가 아닌 두 비용을 반환해야 한다.
        기본 비용은 (시간, 환승 횟수)이며 앞의 값부터 비교한다.
        예: (100, 2)는 (120, 0)보다 좋고, (100, 1)은 (100, 2)보다 좋다.
        상태는 (현재 역코드, 직전 탑승역 코드, 환승 후 가야 할 역코드)다.
        같은 정점도 진입 방향에 따라 가능한 환승이 달라 상태를 구분한다.
        """
        best_costs = {}       # 각 상태까지 도달한 가장 작은 비용, 딕셔너리 형태로 (vertex.station_code, "", ""):(0, 0) 같은 것으로 
        previous_steps = {}  # 상태 → (직전 상태, 타고 온 간선)      어떤 상태에서 어떤 간선을 타고 왔는지 기록
        queue = []           # 앞으로 살펴볼 후보(누적 비용, 상태)를 저장하는 우선순위 큐

        # 1. 출발역의 호선별 정점을 비용 0인 출발 후보로 등록한다.
        for vertex in origin.vertices: #출발역에 속한 호선별 Vertex를 하나씩 살펴본다는 뜻(ex 출발역이 가락시장이면 3호선과 8호선 모두에서 출발하는 경우를 고려)
            if line is not None and vertex.line != line:
                continue
         
            start_state = (vertex.station_code, "", "")           #상태 ******(현재 역코드, 직전 탑승역 코드, 환승 후 가야 할 역코드)***** #출발역에 여러 호선이 있으면 각 호선의 정점을 출발 후보로 넣는다. line을 지정했다면 해당 호선만 넣는다.
            start_cost = (0, 0)  #기본비용 (소요시간, 환승 횟수) -> 튜플은 앞쪽 값부터 비교하므로 시간이 같으면 환승횟수를 비교   
            best_costs[start_state] = start_cost  #dict형태에 key와 value로 넣는 거임 (vertex.station_code, "", ""):(0, 0)
            heapq.heappush(queue, (start_cost, start_state))  #queue: 탐색 후보를 저장하는 우선순위 큐,  ((0, 0), (역코드, "", ""))를 queue에 집어 넣음 (출발상태를 비용이 0인 탐색 후보로 등록)
            #heapq는 push한 순서와 상관없이 pop

        while queue:     #탐색할 후보가 남아있는 동안 반복
            # 2. 누적 비용이 가장 작은 후보를 꺼낸다.
            current_cost, current_state = heapq.heappop(queue)  #비용이 가장 작은 후보를 꺼내 비용과 상태로 나눔
            # 예: 120초 후보를 넣은 뒤 100초 경로를 발견했다면, 120초 후보는 무시한다.
            recorded_cost = best_costs[current_state] #같은 상태에 도달하는 더 좋은 경로를 이미 찾았다면 지금 꺼낸 후보는 건너뜀.
            if current_cost > recorded_cost:
                continue

            current_code, previous_code, required_next = current_state #상태 튜플을 (현재 역코드,직전 역코드, 환승 후 지정된 다음 역코드)로 풀고 현재 역코드에 해당하는 Vertex 객체를 가져옴.
            current_vertex = self.vertices[current_code]

            # 3. 도착역이면 지나온 간선들을 복원해 반환한다.
            if current_vertex.station is destination:       #목적지라면 이동 기록으로 경로를 복원하고 최종 비용과 경로를 반환하며 탐색을 끝냄.
                route = _restore_route(previous_steps, current_state)
                return current_cost, route  #route는 간선 목록을 담은 Route 객체임

            # 4. 현재 정점에서 조건에 맞게 이동할 수 있는 간선을 살펴본다.
            for edge in current_vertex.edges:  #현재 정점에서 출발하는 구간을 하나씩 확인 예: 현재 역에서 다음역으로 가는 탑승 구간이나 다른 호선으로 갈아타는 환승 구간을 살펴봄.
                if edge in excluded:           #탐색에서 제외하도록 지정된 구간이면 건너뜀
                    continue
                if line is not None and edge.is_transfer:  #특정 호선 안에서만 찾는 중이면 환승구간은 건너뜀
                    continue
                next_state = edge.next_state(previous_code, required_next) #******들어온 방향과 환승후 이동 방향을 확인, 이동 가능하면 다음 상태 튜플을 받고 불가능하면 건너뜀.*************
                if next_state is None:                                     #next_state는 이동가능한지 확인하고 다음상태를 만드는 메서드 -> 이동가능하면 다음 튜플이 담긴다.
                    continue  # 진입 방향이나 환승 후 이동 방향이 맞지 않는다.

                # 5. 지금까지의 비용 + 이번 구간의 비용을 계산한다.
                # 기본 기준에서는 first가 시간, second가 환승 횟수다.
                # 최소 환승 기준을 선택하면 두 값의 역할이 서로 바뀐다.
                current_first, current_second = current_cost  #이번 구간의 비용을 기존 비용에 더함.
                edge_first, edge_second = priority(edge)      #시간과 환승횟수를 반환
                new_first = current_first + edge_first        #지금까지 걸린 시간에 이번 구간의 시간을 더함.
                new_second = current_second + edge_second     #지금까지 환승횟수에 이번 환승횟수를 더함.
                new_cost = (new_first, new_second)            #새 비용

                # 아직 기록이 없으면 None, 있으면 이전에 찾은 최소 비용을 가져온다.
                old_cost = best_costs.get(next_state)         #다음 상태까지 가는 경로 중 지금까지 기록한 가장 작은 비용을 꺼내는 코드

                
                if old_cost is None or new_cost < old_cost:    #처음 찾았거나 기존보다 비용이 낮으면 갱신
                    best_costs[next_state] = new_cost          #비용기록
                    previous_steps[next_state] = (current_state, edge)   #오는 방법 기록
                    heapq.heappush(queue, (new_cost, next_state))        #탐색 후보 추가

        return None  # 모든 후보를 확인했지만 도착하지 못했다.
