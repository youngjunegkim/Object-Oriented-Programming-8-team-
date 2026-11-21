"""② 호선 히트맵 화면: 호선·지선 선택 목록, 역 × 시간대 혼잡도 행렬."""

from ..service_time import SLOTS, check_day


class LineHeatmapView:
    def __init__(self, query):
        self.query = query  # GraphQuery와 같은 메서드를 가진 객체면 된다.

    def line_options(self):
        """호선 → 지선(첫 역, 마지막 역, 역 수) 목록."""
        return [
            {
                "line": line,
                "branches": [
                    {"branch": branch, "first": order[0].station.name, "last": order[-1].station.name,
                     "count": len(order)}
                    for branch, order in branches.items()
                ],
            }
            for line, branches in self.query.line_branches().items()
        ]

    def render(self, line, branch, day, reverse=False):
        """역(행) × 시간대(열) 혼잡도. 순환선은 마지막 역 → 첫 역 구간도 포함한다."""
        check_day(day)
        order = self.query.branch(line, branch)
        if reverse:
            order.reverse()
        pairs = list(zip(order, order[1:]))
        circular = len(order) > 2 and self.query.ride_between(order[-1], order[0]) is not None
        if circular:
            pairs.append((order[-1], order[0]))

        rows = []
        for start, end in pairs:
            edge = self.query.ride_between(start, end)
            values = edge.day_congestion(day) if edge else {}
            rows.append({
                "station": start.station.name,
                "next": end.station.name,
                "source": edge.source(day) if edge else None,
                "values": [values.get(slot) for slot in SLOTS],
            })
        toward = order[1] if circular else order[-1]
        return {
            "line": line,
            "branch": branch,
            "day": day,
            "direction": f"{order[0].station.name} → {toward.station.name} 방면",
            "circular": circular,
            "slots": SLOTS,
            "rows": rows,
        }
