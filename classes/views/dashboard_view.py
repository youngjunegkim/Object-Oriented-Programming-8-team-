"""대시보드 퍼사드: 화면별 클래스를 묶어 API가 부르는 메서드 이름을 하나로 제공한다.

| 클래스                  | 화면                                  |
|-------------------------|---------------------------------------|
| StationCongestionView   | ① 역별 혼잡도 (station_view.py)        |
| LineHeatmapView         | ② 호선 히트맵 (heatmap_view.py)        |
| RouteView               | ③~⑤ 경로 분석 (route_view.py)          |
| GraphQuery              | 그래프 조회 창구 (graph_query.py)      |

각 화면 클래스는 생성자로 받은 query 객체만 사용하므로, 테스트에서는 가짜 객체를 넣을 수 있다.
"""

from ..routing.subway_graph import SubwayGraph
from ..service_time import DAYS, SLOTS
from .graph_query import GraphQuery
from .heatmap_view import LineHeatmapView
from .route_view import RouteView
from .station_view import StationCongestionView


class DashboardView:
    """사용자 입력(역·호선·방향·요일·시간대)을 받아 화면별 클래스에 넘기고 결과를 돌려준다."""

    def __init__(self, graph=None, *, station_view=None, heatmap_view=None, route_view=None):
        if graph is None:
            graph = SubwayGraph()
            graph.build()
        self.graph = graph
        query = GraphQuery(graph)
        self.stations = station_view or StationCongestionView(query)
        self.heatmap = heatmap_view or LineHeatmapView(query)
        self.routes = route_view or RouteView(query)

    def meta(self):
        """역 선택 목록, 호선·지선, 요일, 시간대."""
        return {
            "stations": self.stations.station_options(),
            "lines": self.heatmap.line_options(),
            "days": DAYS,
            "slots": SLOTS,
        }

    # ① 역별 혼잡도
    def station_directions(self, code):
        return self.stations.directions(code)

    def render_station_congestion(self, code, next_code, line):
        return self.stations.compare_days(code, next_code, line)

    # ② 호선 히트맵
    def render_heatmap(self, line, branch, day, reverse=False):
        return self.heatmap.render(line, branch, day, reverse)

    # ③~⑤ 경로 분석
    def render_route(self, start, end, day, departure_time):
        return self.routes.options(start, end, day, departure_time)

    def render_segment_congestion(self, start, end, day, departure_time):
        return self.routes.segments(start, end, day, departure_time)

    def render_departure_congestion(self, start, end, day):
        return self.routes.departure(start, end, day)
