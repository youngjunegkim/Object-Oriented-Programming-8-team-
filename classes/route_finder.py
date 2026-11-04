"""역·간선 객체를 따라 경로를 탐색한다. 비용 기준은 함수로 전달받는다."""

import heapq
from itertools import count

from .edge import RideEdge
from .route import Route


def time_first(edge):
    """소요시간을 먼저, 환승 횟수를 두 번째로 비교한다."""
    return edge.cost(), int(edge.is_transfer)


def transfers_first(edge):
    """환승 횟수를 먼저, 소요시간을 두 번째로 비교한다."""
    return int(edge.is_transfer), edge.cost()


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


class RouteFinder:
    def __init__(self, vertices):
        self.vertices = vertices

    def on_line(self, origin, destination, line):
        """같은 호선의 탑승 간선만 따라간다."""
        result = self._dijkstra(origin, destination, line=line)
        return result[1] if result is not None else None

    def route_options(self, origin, destination):
        """최단시간, 최소 환승, 두 번째 최단시간 Route를 각각 반환한다."""
        fastest = self.best_route(origin, destination)
        fewest = fastest
        second = None
        if fastest is not None and fastest.edges:
            if fastest.transfer_count():
                fewest = self.best_route(origin, destination, priority=transfers_first)
            # 서로 다른 단순 경로라면 첫 경로의 탑승 간선이 적어도 하나 빠진다.
            exclusions = (frozenset([e]) for e in fastest.edges if isinstance(e, RideEdge))
            second = self.best_route(origin, destination, exclusions=exclusions)
        return {"fastest": fastest, "fewest_transfers": fewest, "second_fastest": second}

    def best_route(self, origin, destination, *, priority=time_first, exclusions=(frozenset(),)):
        """간선 제외 조건별 최선 후보를 비교해 물리적 역 재방문이 없는 경로를 고른다."""
        candidates = []
        seen = set()
        sequence = count()

        def add_candidate(excluded):
            if excluded in seen:
                return
            seen.add(excluded)
            result = self._dijkstra(origin, destination, priority, excluded)
            if result is not None:
                rank, route = result
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

    def _dijkstra(self, origin, destination, priority=time_first, excluded=frozenset(), line=None):
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
                return score, Route(list(reversed(edges)))

            for edge in current.edges:
                if edge in excluded:
                    continue
                if line is not None and edge.is_transfer:
                    continue
                next_state = edge.next_state(previous_code, required_next)
                if next_state is None:
                    continue

                primary, secondary = priority(edge)
                candidate = (score[0] + primary, score[1] + secondary)
                if next_state not in best or candidate < best[next_state]:
                    best[next_state] = candidate
                    came_from[next_state] = (state, edge)
                    heapq.heappush(queue, (candidate, next_state))
        return None
