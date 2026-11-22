"""경로 패널: 경로 카드(구간별 혼잡도 rides 포함), 출발 시간대 비교.

혼잡도 계산 규칙은 Route.ride_congestions()·avg_congestion()에만 있고, 여기서는 결과를 화면 형식으로 옮긴다.
"""

from classes.service_time import SLOTS, check_day, departure_seconds

ROUTE_LABELS = {
    "fastest": "최단시간",
    "fewest_transfers": "최소환승",
    "second_fastest": "대안 경로",
}


class RouteView:
    def __init__(self, query):
        self.query = query  # GraphQuery와 같은 메서드를 가진 객체면 된다.

    @staticmethod
    def legs(route):
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
                last["codes"].append(edge.to_v.station_code)
                last["seconds"] += edge.seconds
            else:
                legs.append({
                    "type": "ride",
                    "line": edge.from_v.line,
                    "stations": [edge.from_v.station.name, edge.to_v.station.name],
                    "codes": [edge.from_v.station_code, edge.to_v.station_code],  # 지도에 경로를 그릴 때 쓴다.
                    "seconds": edge.seconds,
                })
        return legs

    @staticmethod
    def rides(route, day, departure_time):
        """탑승 구간별 혼잡도(각 구간 진입 시각 기준)."""
        return [
            {
                "from": edge.from_v.station.name,
                "to": edge.to_v.station.name,
                "from_code": edge.from_v.station_code,
                "to_code": edge.to_v.station_code,
                "line": edge.from_v.line,
                "slot": slot,
                "value": value,
                "source": edge.source(day),
            }
            for edge, slot, value in route.ride_congestions(day, departure_time)
        ]

    def summary(self, route, day, departure_time):
        """경로 카드 한 장에 들어갈 값."""
        stops, meters = route.stops()
        return {
            "total_seconds": route.total_time(),
            "transfers": route.transfer_count(),
            "stops": stops,
            "meters": meters,
            "avg_congestion": route.avg_congestion(day, departure_time),
            "legs": self.legs(route),
            "rides": self.rides(route, day, departure_time),  # 지도·구간 그래프에 쓴다.
        }

    def options(self, start, end, day, departure_time):
        """최단시간·최소환승·대안 경로의 요약 카드. 앞 경로와 같은 경로면 same_as로 알린다."""
        check_day(day)
        departure_seconds(departure_time)  # 출발 시각 형식 검사
        routes = []
        seen = []
        for key, route in self.query.route_options(start, end).items():
            if route is None:
                continue
            same_as = next((k for k, r in seen if r.edges == route.edges), None)
            seen.append((key, route))
            item = {"key": key, "label": ROUTE_LABELS[key], "same_as": ROUTE_LABELS.get(same_as)}
            item.update(self.summary(route, day, departure_time))
            routes.append(item)
        return {"routes": routes}

    def departure(self, start, end, day):
        """같은 최단시간 경로를 시간대별로 출발했을 때의 평균 혼잡도."""
        check_day(day)
        route = self.query.shortest(start, end)
        if route is None:
            return {"slots": SLOTS, "values": [None] * len(SLOTS)}
        return {
            "slots": SLOTS,
            "values": [route.avg_congestion(day, slot) for slot in SLOTS],
            "total_seconds": route.total_time(),
        }
