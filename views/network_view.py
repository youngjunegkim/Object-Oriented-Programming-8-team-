"""노선도 지도 화면: 호선 목록(호선 선택 버튼), 전체 탑승 구간의 시간대별 혼잡도."""

from classes.service_time import SLOTS, check_day


class NetworkView:
    def __init__(self, query):
        self.query = query  # GraphQuery와 같은 메서드를 가진 객체면 된다.

    def line_names(self):
        """호선 선택 버튼에 쓰는 호선 이름 목록."""
        return self.query.line_names()

    def render(self, day):
        """모든 탑승 구간(방향별)의 30분 시간대별 혼잡도. 화면은 slots 순서의 values에서 시각을 고른다."""
        check_day(day)
        edges = []
        for edge in self.query.all_rides():
            values = edge.day_congestion(day)
            edges.append({
                "from": edge.from_v.station_code,
                "to": edge.to_v.station_code,
                "line": edge.from_v.line,
                "source": edge.source(day),
                "values": [values.get(slot) for slot in SLOTS],
            })
        return {"day": day, "slots": SLOTS, "edges": edges}
