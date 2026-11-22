"""대시보드 조립: 그래프를 만들고 화면별 클래스에 GraphQuery를 넣어 묶는다.

| 속성      | 클래스                | 화면                                  |
|-----------|-----------------------|---------------------------------------|
| stations  | StationCongestionView | 역 패널: 역별 혼잡도 (station_view.py) |
| routes    | RouteView             | 경로 패널: 경로 분석 (route_view.py)   |
| network   | NetworkView           | 노선도 지도 (network_view.py)          |

API(api/index.py)는 이 속성들의 메서드를 직접 부른다.
각 화면 클래스는 생성자로 받은 query 객체만 사용하므로, 테스트에서는 가짜 객체를 넣을 수 있다.
"""

from classes.routing.subway_graph import SubwayGraph
from classes.service_time import DAYS, SLOTS

from .graph_query import GraphQuery
from .network_view import NetworkView
from .route_view import RouteView
from .station_view import StationCongestionView


class Dashboard:
    def __init__(self, graph=None, *, station_view=None, route_view=None, network_view=None):
        if graph is None:
            graph = SubwayGraph()
            graph.build()
        self.graph = graph
        query = GraphQuery(graph)
        self.stations = station_view or StationCongestionView(query)
        self.routes = route_view or RouteView(query)
        self.network = network_view or NetworkView(query)

    def meta(self):
        """역 선택 목록, 호선 이름, 요일, 시간대."""
        return {
            "stations": self.stations.station_options(),
            "lines": self.network.line_names(),
            "days": DAYS,
            "slots": SLOTS,
        }
