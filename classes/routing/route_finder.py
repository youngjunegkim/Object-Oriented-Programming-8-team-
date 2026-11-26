"""지하철 그래프에서 조건에 맞는 경로를 찾는다. _dijkstra()의 1~5단계부터 읽으면 된다."""

import heapq
from itertools import count

from ..models.edge import RideEdge
from ..models.route import Route


def time_first(edge):
    """시간이 짧은 경로 우선, 같으면 환승이 적은 경로."""
    return edge.cost(), int(edge.is_transfer)


def transfers_first(edge):
    """환승이 적은 경로 우선, 같으면 시간이 짧은 경로."""
    return int(edge.is_transfer), edge.cost()


def _restore_route(previous_steps, end_state):
    """도착 상태부터 이동 기록을 거꾸로 따라가 출발 → 도착 순서의 Route를 만든다."""
    edges = []
    state = end_state
    while state in previous_steps:
        previous_state, edge = previous_steps[state]
        edges.append(edge)
        state = previous_state

    edges.reverse()
    return Route(edges)


def _cycle_rides(route):
    """경로가 같은 물리적 역을 다시 지나면 그 사이의 탑승 간선을, 아니면 빈 목록을 반환한다."""
    rides = []
    for edge in route.edges:
        if isinstance(edge, RideEdge):
            rides.append(edge)
    if not rides:
        return []

    station_positions = {rides[0].from_v.station: 0}
    for index, ride in enumerate(rides, start=1):
        station = ride.to_v.station
        if station in station_positions:
            cycle_start = station_positions[station]
            return rides[cycle_start:index]
        station_positions[station] = index
    return []


class RouteFinder:
    """역코드 → Vertex 사전을 받아 다익스트라로 경로를 찾는다."""

    def __init__(self, vertices):
        self.vertices = vertices

    def route_options(self, origin, destination):
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

    def best_route(self, origin, destination, *, priority=time_first, exclusions=(frozenset(),)):
        """간선 제외 조건별로 탐색하고, 같은 물리적 역을 재방문하지 않는 가장 싼 경로를 고른다."""
        candidates = []             # (비용, 순번, 제외 간선, 경로) 힙
        checked_exclusions = set()  # 이미 탐색한 제외 조건
        sequence = count()          # 비용이 같은 후보끼리 비교되지 않게 붙이는 순번

        def add_candidate(excluded):
            if excluded in checked_exclusions:
                return
            checked_exclusions.add(excluded)

            result = self._dijkstra(origin, destination, priority=priority, excluded=excluded)
            if result is None:
                return
            cost, route = result
            heapq.heappush(candidates, (cost, next(sequence), excluded, route))

        for excluded in exclusions:
            add_candidate(excluded)

        while candidates:
            _, _, excluded, route = heapq.heappop(candidates)
            cycle_edges = _cycle_rides(route)
            if not cycle_edges:
                return route

            # 순환을 없애려면 그 순환의 간선 중 적어도 하나를 쓰지 않아야 한다.
            for edge in cycle_edges:
                add_candidate(excluded | {edge})
        return None

    def _dijkstra(self, origin, destination, priority=time_first, excluded=frozenset()):
        """주어진 간선 제외 조건에서 (최소 비용, Route)를 반환한다. 못 찾으면 None.

        priority(edge)는 음수가 아닌 두 비용을 반환해야 한다.
        기본 비용은 (시간, 환승 횟수)이며 앞의 값부터 비교한다.
        예: (100, 2)는 (120, 0)보다 좋고, (100, 1)은 (100, 2)보다 좋다.
        상태는 (현재 역코드, 직전 탑승역 코드, 환승 후 가야 할 역코드)다.
        같은 정점도 진입 방향에 따라 가능한 환승이 달라 상태를 구분한다.
        """
        best_costs = {}      # 상태 → 지금까지 찾은 최소 비용
        previous_steps = {}  # 상태 → (직전 상태, 타고 온 간선)
        queue = []           # (누적 비용, 상태) 힙

        # 1. 출발역의 호선별 정점을 비용 0인 출발 후보로 등록한다.
        for vertex in origin.vertices:
            start_state = (vertex.station_code, "", "")
            start_cost = (0, 0)
            best_costs[start_state] = start_cost
            heapq.heappush(queue, (start_cost, start_state))

        while queue:
            # 2. 누적 비용이 가장 작은 후보를 꺼낸다. 더 싼 기록이 이미 있으면 건너뛴다.
            current_cost, current_state = heapq.heappop(queue)
            if current_cost > best_costs[current_state]:
                continue

            current_code, previous_code, required_next = current_state
            current_vertex = self.vertices[current_code]

            # 3. 도착역이면 지나온 간선들을 복원해 반환한다.
            if current_vertex.station is destination:
                return current_cost, _restore_route(previous_steps, current_state)

            # 4. 현재 정점에서 조건에 맞게 이동할 수 있는 간선을 살펴본다.
            for edge in current_vertex.edges:
                if edge in excluded:
                    continue
                next_state = edge.next_state(previous_code, required_next)
                if next_state is None:
                    continue  # 진입 방향이나 환승 후 이동 방향이 맞지 않는다.

                # 5. 지금까지의 비용 + 이번 구간의 비용으로 더 싸면 기록을 갱신한다.
                current_first, current_second = current_cost
                edge_first, edge_second = priority(edge)
                new_cost = (current_first + edge_first, current_second + edge_second)

                old_cost = best_costs.get(next_state)
                if old_cost is None or new_cost < old_cost:
                    best_costs[next_state] = new_cost
                    previous_steps[next_state] = (current_state, edge)
                    heapq.heappush(queue, (new_cost, next_state))

        return None
