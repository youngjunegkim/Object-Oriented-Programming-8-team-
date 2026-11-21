"""대시보드 조립: 그래프를 만들고 화면별 클래스에 GraphQuery를 넣어 묶는다.

| 속성      | 클래스                | 화면                             |
|-----------|-----------------------|----------------------------------|
| stations  | StationCongestionView | ① 역별 혼잡도 (station_view.py)  |
| heatmap   | LineHeatmapView       | ② 호선 히트맵 (heatmap_view.py)  |
| routes    | RouteView             | ③~⑤ 경로 분석 (route_view.py)    |

API(api/index.py)는 이 속성들의 메서드를 직접 부른다.
각 화면 클래스는 생성자로 받은 query 객체만 사용하므로, 테스트에서는 가짜 객체를 넣을 수 있다.
"""

from ..routing.subway_graph import SubwayGraph
from ..service_time import DAYS, SLOTS
from .graph_query import GraphQuery
from .heatmap_view import LineHeatmapView
from .route_view import RouteView
from .station_view import StationCongestionView


class Dashboard:
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
