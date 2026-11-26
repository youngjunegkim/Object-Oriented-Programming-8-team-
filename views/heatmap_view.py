"""호선 히트맵 패널: 한 호선·지선의 역(행) × 30분 시간대(열) 혼잡도 행렬.

지도는 한 시각의 전체 노선을, 히트맵은 한 호선의 하루 흐름을 보여 준다.
"""

from classes.service_time import SLOTS, check_day


class LineHeatmapView:
    def __init__(self, query):
        self.query = query  # GraphQuery와 같은 메서드를 가진 객체면 된다.

    def branch_options(self, line):
        """지선 선택 목록: 지선 이름, 첫 역, 마지막 역, 역 수."""
        return [
            {"branch": branch, "first": order[0].station.name, "last": order[-1].station.name, "count": len(order)}
            for branch, order in self.query.branches(line).items()
        ]

    def render(self, line, day, branch=None, reverse=False):
        """지선의 역 순서대로 탑승 간선을 따라가며 혼잡도를 모은다. 순환선은 마지막 역 → 첫 역 구간도 넣는다.

        branch를 주지 않으면 그 호선의 첫 지선(본선)을 쓴다.
        """
        check_day(day)
        options = self.branch_options(line)
        branch = branch or options[0]["branch"]
        order = self.query.branch(line, branch)
        if reverse:
            order.reverse()
        pairs = list(zip(order, order[1:]))
        circular = len(order) > 2 and self.query.ride_between(order[-1], order[0]) is not None
        if circular:
            pairs.append((order[-1], order[0]))

        rows = []
        for start, end in pairs:
            edge = self.query.ride_between(start, end)  # 한 방향만 운행하는 구간은 None
            values = edge.day_congestion(day) if edge else {}
            rows.append({
                "station": start.station.name,
                "next": end.station.name,
                "from_code": start.station_code,  # 행을 누르면 지도의 역을 고를 때 쓴다.
                "source": edge.source(day) if edge else None,
                "values": [values.get(slot) for slot in SLOTS],
            })
        toward = order[1] if circular else order[-1]
        return {
            "line": line,
            "branch": branch,
            "branches": options,
            "day": day,
            "reverse": reverse,
            "direction": f"{order[0].station.name} → {toward.station.name} 방면",
            "circular": circular,
            "slots": SLOTS,
            "rows": rows,
        }
