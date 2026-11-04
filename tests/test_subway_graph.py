"""프로젝트 루트에서 python -m unittest discover -s tests -v 로 실행한다."""

import unittest
from types import SimpleNamespace

from classes.edge import RideEdge, TransferEdge
from classes.station import Station
from classes.subway_graph import Route, SubwayGraph
from classes.vertex import Vertex


class SubwayGraphTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.graph = SubwayGraph()
        cls.graph.build()

    def test_directions_and_route_summary(self):
        for end, walk, total in [("송파", 122, 312), ("문정", 112, 302)]:
            with self.subTest(end=end):
                route = self.graph.shortest("수서", end)
                ride, transfer, next_ride = route.edges
                self.assertIsInstance(transfer, TransferEdge)
                self.assertEqual(ride.from_v.station_code, transfer.from_prev_code)
                self.assertEqual(next_ride.to_v.station_code, transfer.to_next_code)
                self.assertEqual(transfer.cost(), walk)
                self.assertEqual(route.total_time(), total)
                self.assertEqual(route.transfer_count(), 1)
        route = self.graph.shortest("수서", "송파")
        self.assertEqual(route.stops(), (2, 2235))
        # 08:28 출발 후 두 번째 탑승은 08:32이므로 다음 시간칸을 사용한다.
        first, _, last = route.edges
        expected = (first.congestion_get("평일", "08:00") + last.congestion_get("평일", "08:30")) / 2
        self.assertAlmostEqual(route.avg_congestion("평일", "08:28"), expected)

    def test_three_route_options(self):
        routes = self.graph.route_options("서울역", "강남")
        expected = {"fastest": (1341, 2), "second_fastest": (1369, 2), "fewest_transfers": (1402, 1)}
        for key, route in routes.items():
            with self.subTest(key=key):
                self.assertEqual((route.total_time(), route.transfer_count()), expected[key])
                stations = [route.edges[0].from_v.station]
                for index, edge in enumerate(route.edges):
                    if index:
                        self.assertIs(route.edges[index - 1].to_v, edge.from_v)
                    if isinstance(edge, RideEdge):
                        stations.append(edge.to_v.station)
                    else:
                        self.assertEqual(route.edges[index - 1].from_v.station_code, edge.from_prev_code)
                        self.assertEqual(route.edges[index + 1].to_v.station_code, edge.to_next_code)
                self.assertEqual(len(stations), len(set(stations)))

    def test_no_alternative_or_travel(self):
        self.assertIsNone(self.graph.route_options("연천", "전곡")["second_fastest"])
        options = self.graph.route_options("총신대입구", "이수")
        self.assertEqual(options["fastest"].stops(), (0, 0))
        self.assertEqual(options["fewest_transfers"].total_time(), 0)
        self.assertIsNone(options["fastest"].avg_congestion("평일", "08:00"))
        self.assertIsNone(options["second_fastest"])

    def test_station_lookup_and_one_way_loop(self):
        with self.assertRaisesRegex(ValueError, "동명이역"):
            self.graph.shortest("신촌", "서울역")
        self.assertGreater(self.graph.shortest("0240", "1252").total_time(), 0)
        series = self.graph.station_congestion("수서", "가락시장", "3호선", "평일")
        self.assertEqual(len(series), 39)
        self.assertEqual(series["08:00"], 18.5)
        with self.assertRaises(ValueError):
            self.graph.station_congestion("수서", "오금", "3호선", "평일")
        self.assertEqual([v.station.name for v in self.graph.stations_between("응암", "구산", "6호선")],
                         ["응암", "역촌", "불광", "독바위", "연신내", "구산"])
        self.assertEqual([v.station.name for v in self.graph.stations_between("구산", "응암", "6호선")],
                         ["구산", "응암"])

    def test_line_order_follows_real_track(self):
        self.assertEqual(len(self.graph.vertices), 782)
        self.assertEqual(len(self.graph.edges), 2626)
        adjacent = set()
        for edge in self.graph.edges:
            if isinstance(edge, RideEdge):
                adjacent.add(frozenset((edge.from_v, edge.to_v)))
        for branches in self.graph.line_order.values():
            for vertices in branches.values():
                for a, b in zip(vertices, vertices[1:]):
                    self.assertIn(frozenset((a, b)), adjacent)

    def test_midnight_and_missing_data(self):
        vertex = Vertex("A", Station("A"), "가상선")
        data = {"토요일": {"values": {"23:30": 20, "00:00": 60, "00:30": None}}}
        ride = RideEdge(vertex, vertex, 120, None, data)
        route = Route([ride, ride])
        self.assertEqual(route.avg_congestion("토요일", "23:59"), 40)
        self.assertIsNone(route.avg_congestion("토요일", "00:29"))
        self.assertIsNone(route.avg_congestion("토요일", "02:00"))
        self.assertEqual(route.stops(), (2, None))

    def test_tied_alternative_and_disconnected_goal(self):
        graph = SubwayGraph()
        for name in "ABCDE":
            station = Station(name)
            vertex = Vertex(name, station, "가상선")
            station.add_vertex(vertex)
            graph.vertices[name] = vertex
            graph.stations[name] = [station]
        for start, end in ["AB", "BD", "AC", "CD"]:
            a, b = graph.vertices[start], graph.vertices[end]
            a.add_edge(RideEdge(a, b, 1, 10, {}))
        routes = graph.route_options("A", "D")
        self.assertEqual(routes["second_fastest"].total_time(), 2)
        self.assertNotEqual(routes["fastest"].edges, routes["second_fastest"].edges)
        self.assertTrue(all(r is None for r in graph.route_options("A", "E").values()))

    def test_faster_platform_detour_does_not_count_as_an_alternative(self):
        # B에 도착한 뒤 C까지 왕복하면 환승이 싸지는 가상 데이터.
        graph = SubwayGraph()
        for name in "ABCD":
            graph.stations[name] = [Station(name)]
        for code, name, line in [("a","A","1"), ("b1","B","1"), ("b2","B","2"),
                                 ("c","C","1"), ("d","D","2")]:
            station = graph.stations[name][0]
            vertex = Vertex(code, station, line)
            station.add_vertex(vertex)
            graph.vertices[code] = vertex
        a, b1, b2, c, d = graph.vertices.values()
        for start, end in [(a,b1), (b1,c), (c,b1), (b2,d)]:
            start.add_edge(RideEdge(start, end, 1, 10, {}))
        for prev, seconds in [(a, 20), (c, 1)]:
            b1.add_edge(TransferEdge(b1, b2, seconds, from_prev_code=prev.station_code, to_next_code="d"))
        routes = graph.route_options("A", "D")
        self.assertEqual(routes["fastest"].total_time(), 22)
        self.assertIsNone(routes["second_fastest"])


    def test_injected_loader_and_new_priority(self):
        # 직행은 10초, 중간 역을 거치면 4초. 두 기준이 실제로 다른 길을 선택한다.
        line = "테스트선"
        rows = [dict(station_code=name, name=name, line=line) for name in "ABC"]

        def ride(start, end, branch, seconds):
            return dict(from_code=start, to_code=end, branch=branch, seconds=seconds, meters=100)

        rides = [ride("A", "B", "본선", 2), ride("B", "C", "본선", 2), ride("A", "C", "직행", 10)]
        loader = SimpleNamespace(
            load_stations=lambda: rows,
            load_transfers=lambda: {},
            load_distance=lambda: {line: rides},
            load_congestion=lambda: {(line, r["from_code"], r["to_code"]): {} for r in rides},
        )
        graph = SubwayGraph(loader=loader)
        graph.build()

        def stops_first(edge):
            return int(isinstance(edge, RideEdge)), edge.cost()

        fastest = graph.shortest("A", "C")
        fewest_stops = graph.shortest("A", "C", priority=stops_first)
        self.assertIsInstance(fastest, Route)
        self.assertEqual((fastest.total_time(), fastest.stops()[0]), (4, 2))
        self.assertEqual((fewest_stops.total_time(), fewest_stops.stops()[0]), (10, 1))

    def test_search_respects_edge_transition_contract(self):
        class ClosedRide(RideEdge):
            def next_state(self, previous_code, required_next):
                return None

        graph = SubwayGraph()
        for code in "AB":
            station = Station(code)
            vertex = Vertex(code, station, "가상선")
            station.add_vertex(vertex)
            graph.stations[code] = [station]
            graph.vertices[code] = vertex
        a, b = graph.vertices.values()
        a.add_edge(ClosedRide(a, b, 1, 1, {}))
        self.assertIsNone(graph.shortest("A", "B"))
        a.add_edge(RideEdge(a, b, 3, 1, {}))
        self.assertEqual(graph.shortest("A", "B").total_time(), 3)
