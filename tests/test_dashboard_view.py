"""대시보드 화면 클래스와 Route·RideEdge에 추가한 메서드의 테스트.

실행: 프로젝트 루트에서  python3 -m unittest discover -s tests -v
"""

import unittest

from api.index import dispatch
from classes.models.edge import RideEdge, TransferEdge
from classes.models.route import Route
from classes.models.station import Station
from classes.models.vertex import Vertex
from classes.routing.subway_graph import SubwayGraph
from classes.service_time import DAYS, SLOTS
from classes.views.dashboard_view import DashboardView
from classes.views.graph_query import GraphQuery
from classes.views.route_view import RouteView

GRAPH = None


def setUpModule():
    global GRAPH
    GRAPH = SubwayGraph()
    GRAPH.build()


def congestion(value, source="measured"):
    """모든 요일·시간대가 value인 혼잡도 데이터 (로더가 만드는 형식)."""
    return {day: {"source": source, "values": {slot: value for slot in SLOTS}} for day in DAYS}


def tiny_route():
    """CSV 없이 만든 경로: A -(X선 10분)-> B -(환승 5분)-> B' -(Y선 20분)-> C"""
    a, b, c = Station("A"), Station("B"), Station("C")
    a_x, b_x, b_y, c_y = Vertex("1", a, "X선"), Vertex("2", b, "X선"), Vertex("3", b, "Y선"), Vertex("4", c, "Y선")
    ride1 = RideEdge(a_x, b_x, 600, 1000, congestion(40.0))
    walk = TransferEdge(b_x, b_y, 300, 50, from_prev_code="1", to_next_code="4")
    ride2 = RideEdge(b_y, c_y, 1200, 3000, congestion(80.0, "generated"))
    return Route([ride1, walk, ride2])


class FakeQuery:
    """GraphQuery 대신 넣는 가짜 객체. RouteView가 그래프 구현에 묶이지 않았음을 확인한다(DIP)."""

    check_day = staticmethod(GraphQuery.check_day)

    def __init__(self, route):
        self.route = route

    def shortest(self, start, end):
        return self.route

    def route_options(self, start, end):
        return {"fastest": self.route, "fewest_transfers": self.route, "second_fastest": None}


class RideEdgeSourceTest(unittest.TestCase):
    def test_source_returns_day_source(self):
        edge = tiny_route().edges[2]
        self.assertEqual(edge.source("평일"), "generated")


class RideCongestionsTest(unittest.TestCase):
    def test_entry_time_moves_with_ride_and_transfer(self):
        # 08:20 출발 → 첫 탑승 08:00 시간대, 10분 탑승 + 5분 환승 후 08:35 → 08:30 시간대
        result = tiny_route().ride_congestions("평일", "08:20")
        self.assertEqual([(slot, value) for _, slot, value in result], [("08:00", 40.0), ("08:30", 80.0)])

    def test_out_of_range_gives_none(self):
        result = tiny_route().ride_congestions("평일", "04:00")
        self.assertEqual([slot for _, slot, _ in result], [None, None])

    def test_invalid_day(self):
        with self.assertRaises(ValueError):
            tiny_route().ride_congestions("월요일", "08:00")


class AvgCongestionTest(unittest.TestCase):
    def test_average_of_rides(self):
        self.assertAlmostEqual(tiny_route().avg_congestion("평일", "08:20"), 60.0)

    def test_none_when_any_ride_out_of_range(self):
        # 00:50 출발 → 두 번째 탑승이 01:05로 관측 범위(01:00 미만)를 벗어난다.
        self.assertIsNone(tiny_route().avg_congestion("평일", "00:50"))

    def test_none_for_empty_route(self):
        self.assertIsNone(Route([]).avg_congestion("평일", "08:00"))

    def test_matches_ride_congestions_on_real_routes(self):
        for start, end in [("서울역", "강남"), ("가락시장", "잠실"), ("0150", "0425")]:
            route = GRAPH.shortest(start, end)
            for slot in ["06:00", "08:00", "18:30", "00:30"]:
                values = [v for _, _, v in route.ride_congestions("평일", slot)]
                expected = None if None in values else sum(values) / len(values)
                self.assertEqual(route.avg_congestion("평일", slot), expected)


class RouteViewTest(unittest.TestCase):
    def setUp(self):
        self.view = RouteView(FakeQuery(tiny_route()))

    def test_legs_group_rides_and_transfers(self):
        legs = self.view.legs(tiny_route())
        self.assertEqual([leg["type"] for leg in legs], ["ride", "transfer", "ride"])
        self.assertEqual(legs[1]["from_line"], "X선")

    def test_same_route_is_marked(self):
        routes = self.view.options("A", "C", "평일", "08:20")["routes"]
        self.assertEqual([r["label"] for r in routes], ["최단시간", "최소환승"])
        self.assertEqual(routes[1]["same_as"], "최단시간")

    def test_segments_use_ride_congestions(self):
        segments = self.view.segments("A", "C", "평일", "08:20")["segments"]
        self.assertEqual([(s["slot"], s["value"], s["source"]) for s in segments],
                         [("08:00", 40.0, "measured"), ("08:30", 80.0, "generated")])


class DashboardViewTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.view = DashboardView(GRAPH)

    def test_meta_separates_same_name_stations(self):
        labels = {s["label"] for s in self.view.meta()["stations"]}
        self.assertIn("신촌 (2호선)", labels)
        self.assertNotIn("신촌", labels)

    def test_circular_line_closes_loop(self):
        heatmap = self.view.render_heatmap("2호선", "순환선", "평일")
        self.assertTrue(heatmap["circular"])
        self.assertEqual(heatmap["rows"][-1]["next"], heatmap["rows"][0]["station"])

    def test_station_compares_three_days(self):
        data = self.view.render_station_congestion("0150", "0151", "1호선")
        self.assertEqual(list(data["days"]), DAYS)
        self.assertEqual(len(data["days"]["평일"]["values"]), len(SLOTS))

    def test_injected_views_are_used(self):
        fake_route_view = RouteView(FakeQuery(tiny_route()))
        view = DashboardView(GRAPH, route_view=fake_route_view)
        self.assertEqual(len(view.render_segment_congestion("A", "C", "평일", "08:20")["segments"]), 2)


class ApiTest(unittest.TestCase):
    def test_ok_bad_request_and_not_found(self):
        self.assertEqual(dispatch("/api/meta", "")[0], 200)
        self.assertEqual(dispatch("/api/route", "start=0150&end=0222&day=월&time=08:00")[0], 400)
        self.assertEqual(dispatch("/api/nothing", "")[0], 404)

    def test_vercel_endpoint_parameter(self):
        status, body = dispatch("/api/index", "endpoint=directions&station=0150")
        self.assertEqual(status, 200)
        self.assertEqual(body["station"], "서울역")


if __name__ == "__main__":
    unittest.main()
