"""대시보드 화면에 필요한 값을 SubwayGraph에 요청해 JSON으로 보낼 수 있는 dict로 만든다.

기존 classes의 공개 메서드(station_congestion, stations_between, shortest, route_options,
Route의 계산 메서드)를 그대로 사용하고, 화면 표시용 가공만 이 파일에서 담당한다.
"""

from ..models.edge import RideEdge
from ..routing.subway_graph import SubwayGraph
from ..service_time import DAYS, SLOTS, congestion_slot, departure_seconds

ROUTE_LABELS = {
    "fastest": "최단시간",
    "fewest_transfers": "최소환승",
    "second_fastest": "대안 경로",
}


class DashboardView:
    """사용자 입력(역·호선·방향·요일·시간대)을 받아 SubwayGraph에 요청하고 결과를 정리한다."""

    def __init__(self, graph=None):
        if graph is None:
            graph = SubwayGraph()
            graph.build()
        self.graph = graph

    # ---------- 공통 ----------
    def _vertex(self, code):
        vertex = self.graph.vertices.get(code)
        if vertex is None:
            raise ValueError(f"찾을 수 없는 역코드입니다: {code}")
        return vertex

    @staticmethod
    def _check_day(day):
        if day not in DAYS:
            raise ValueError(f"요일은 {DAYS} 중 하나여야 합니다.")

    @staticmethod
    def _ride_between(start, end):
        for edge in start.edges:
            if isinstance(edge, RideEdge) and edge.to_v is end:
                return edge
        return None

    def meta(self):
        """역 선택 목록, 호선·지선, 요일, 시간대."""
        stations = []
        seen = set()
        for name, candidates in self.graph.stations.items():
            for station in candidates:
                if id(station) in seen:
                    continue
                seen.add(id(station))
                lines = [v.line for v in station.vertices]
                label = name if len(candidates) == 1 else f"{name} ({', '.join(lines)})"
                stations.append({
                    "code": station.vertices[0].station_code,  # 코드로 물리적 역을 선택한다.
                    "name": name,
                    "label": label,
                    "lines": lines,
                })
        stations.sort(key=lambda s: s["label"])

        lines = []
        for line, branches in self.graph.line_order.items():
            lines.append({
                "line": line,
                "branches": [
                    {"branch": branch, "first": order[0].station.name, "last": order[-1].station.name,
                     "count": len(order)}
                    for branch, order in branches.items()
                ],
            })
        return {"stations": stations, "lines": lines, "days": DAYS, "slots": SLOTS}

    # ---------- 1. 역별 혼잡도 조회 ----------
    def station_directions(self, code):
        """선택한 역에서 출발할 수 있는 (호선, 다음 역) 방향 목록."""
        station = self._vertex(code).station
        directions = []
        for vertex in station.vertices:
            for edge in vertex.edges:
                if isinstance(edge, RideEdge):
                    directions.append({
                        "line": vertex.line,
                        "next_code": edge.to_v.station_code,
                        "next_name": edge.to_v.station.name,
                    })
        return {"station": station.name, "directions": directions}

    def render_station_congestion(self, code, next_code, line):
        """평일·토요일·일요일의 30분별 혼잡도를 한 번에 비교한다."""
        start = self._vertex(code).station
        edge = None
        for vertex in start.vertices:
            if vertex.line == line and edge is None:
                edge = self._ride_between(vertex, self._vertex(next_code))
        days = {}
        for day in DAYS:
            values = self.graph.station_congestion(code, next_code, line, day)
            days[day] = {
                "source": edge.congestion[day]["source"] if edge else None,
                "values": [values.get(slot) for slot in SLOTS],
            }
        return {
            "station": start.name,
            "next": self._vertex(next_code).station.name,
            "line": line,
            "slots": SLOTS,
            "days": days,
        }

    # ---------- 2. 호선 전체 혼잡도 히트맵 ----------
    def render_heatmap(self, line, branch, day, reverse=False):
        """역(행) × 시간대(열) 혼잡도. 순환선은 마지막 역 → 첫 역 구간도 포함한다."""
        self._check_day(day)
        branches = self.graph.line_order.get(line)
        if not branches or branch not in branches:
            raise ValueError(f"찾을 수 없는 호선·지선입니다: {line} {branch}")
        order = list(branches[branch])
        if reverse:
            order.reverse()
        pairs = list(zip(order, order[1:]))
        circular = self._ride_between(order[-1], order[0]) is not None and len(order) > 2
        if circular:
            pairs.append((order[-1], order[0]))

        rows = []
        for start, end in pairs:
            edge = self._ride_between(start, end)
            values = edge.congestion_get(day) if edge else {}
            rows.append({
                "station": start.station.name,
                "next": end.station.name,
                "source": edge.congestion[day]["source"] if edge else None,
                "values": [values.get(slot) for slot in SLOTS],
            })
        return {
            "line": line,
            "branch": branch,
            "day": day,
            "direction": f"{order[0].station.name} → {order[1].station.name if circular else order[-1].station.name} 방면",
            "circular": circular,
            "slots": SLOTS,
            "rows": rows,
        }

    # ---------- 3~5. 경로 ----------
    @staticmethod
    def _legs(route):
        """연속된 같은 호선 탑승 간선을 하나의 구간(leg)으로 묶는다."""
        legs = []
        for edge in route.edges:
            if edge.is_transfer:
                legs.append({
                    "type": "transfer",
                    "station": edge.from_v.station.name,
                    "from_line": edge.from_v.line,
                    "to_line": edge.to_v.line,
                    "seconds": edge.seconds,
                    "meters": edge.meters,
                })
                continue
            last = legs[-1] if legs else None
            if last and last["type"] == "ride" and last["line"] == edge.from_v.line:
                last["stations"].append(edge.to_v.station.name)
                last["seconds"] += edge.seconds
            else:
                legs.append({
                    "type": "ride",
                    "line": edge.from_v.line,
                    "stations": [edge.from_v.station.name, edge.to_v.station.name],
                    "seconds": edge.seconds,
                })
        return legs

    @staticmethod
    def _summary(route, day, departure_time):
        stops, meters = route.stops()
        return {
            "total_seconds": route.total_time(),
            "transfers": route.transfer_count(),
            "stops": stops,
            "meters": meters,
            "avg_congestion": route.avg_congestion(day, departure_time),
            "legs": DashboardView._legs(route),
        }

    def render_route(self, start, end, day, departure_time):
        """최단시간·최소환승·대안 경로의 요약 카드."""
        self._check_day(day)
        departure_seconds(departure_time)  # 형식 검사
        options = self.graph.route_options(start, end)
        routes = []
        seen = []
        for key, route in options.items():
            if route is None:
                continue
            same_as = next((k for k, r in seen if r.edges == route.edges), None)
            seen.append((key, route))
            item = {"key": key, "label": ROUTE_LABELS[key], "same_as": ROUTE_LABELS.get(same_as)}
            item.update(self._summary(route, day, departure_time))
            routes.append(item)
        return {"routes": routes}

    def render_segment_congestion(self, start, end, day, departure_time):
        """최단시간 경로의 탑승 구간별 혼잡도. 각 구간에 진입하는 시각의 30분 시간대 값을 쓴다."""
        self._check_day(day)
        route = self.graph.shortest(start, end)
        if route is None:
            return {"segments": []}
        clock = departure_seconds(departure_time)
        segments = []
        for edge in route.edges:
            if isinstance(edge, RideEdge):
                slot = congestion_slot(clock)
                segments.append({
                    "from": edge.from_v.station.name,
                    "to": edge.to_v.station.name,
                    "line": edge.from_v.line,
                    "slot": slot,
                    "value": edge.congestion_get(day, slot) if slot else None,
                    "source": edge.congestion[day]["source"],
                })
            clock += edge.cost()  # Route.avg_congestion과 같은 규칙: 환승 시간도 다음 진입 시각에 반영
        return {"segments": segments}

    def render_departure_congestion(self, start, end, day):
        """같은 최단시간 경로를 시간대별로 출발했을 때의 평균 혼잡도."""
        self._check_day(day)
        route = self.graph.shortest(start, end)
        if route is None:
            return {"slots": SLOTS, "values": [None] * len(SLOTS)}
        return {
            "slots": SLOTS,
            "values": [route.avg_congestion(day, slot) for slot in SLOTS],
            "total_seconds": route.total_time(),
        }
