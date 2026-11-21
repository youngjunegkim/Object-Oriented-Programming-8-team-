"""화면 클래스들이 SubwayGraph를 조회할 때 거치는 어댑터.

graph.vertices, graph.stations, graph.line_order 같은 그래프 내부 구조는 이 파일에서만 다룬다.
그래프의 저장 방식이 바뀌어도 화면 클래스는 그대로 두고 이 파일만 고치면 된다(DIP).
"""

from ..models.edge import RideEdge
from ..service_time import DAYS


class GraphQuery:
    """화면에 필요한 조회만 모아 둔 읽기 전용 창구. 계산은 SubwayGraph·Route에 맡긴다."""

    def __init__(self, graph):
        self.graph = graph

    # ---------- 입력 검사 ----------
    @staticmethod
    def check_day(day):
        if day not in DAYS:
            raise ValueError(f"요일은 {DAYS} 중 하나여야 합니다.")

    # ---------- 역·정점 ----------
    def vertex(self, code):
        """역코드 → Vertex. 없으면 ValueError."""
        vertex = self.graph.vertices.get(code)
        if vertex is None:
            raise ValueError(f"찾을 수 없는 역코드입니다: {code}")
        return vertex

    def physical_stations(self):
        """(역 이름, Station, 같은 이름의 역 수) 목록. 환승역은 Station 하나로 한 번만 나온다."""
        result = []
        seen = set()
        for name, candidates in self.graph.stations.items():
            for station in candidates:
                if id(station) not in seen:
                    seen.add(id(station))
                    result.append((name, station, len(candidates)))
        return result

    # ---------- 탑승 간선 ----------
    @staticmethod
    def rides_from(vertex):
        """정점에서 출발하는 탑승 간선들."""
        return [edge for edge in vertex.edges if isinstance(edge, RideEdge)]

    @classmethod
    def ride_between(cls, start, end):
        """start 정점에서 end 정점으로 바로 가는 탑승 간선. 없으면 None."""
        return next((edge for edge in cls.rides_from(start) if edge.to_v is end), None)

    def ride_on_line(self, code, next_code, line):
        """역코드의 물리적 역에서 line 호선으로 next_code 역에 가는 탑승 간선. 없으면 None."""
        for vertex in self.vertex(code).station.vertices:
            if vertex.line == line:
                return self.ride_between(vertex, self.vertex(next_code))
        return None

    # ---------- 호선·지선 ----------
    def line_branches(self):
        """호선 → 지선 → 순서대로 정렬된 Vertex 목록."""
        return self.graph.line_order

    def branch(self, line, branch):
        """한 지선의 Vertex 목록(복사본). 없으면 ValueError."""
        branches = self.graph.line_order.get(line)
        if not branches or branch not in branches:
            raise ValueError(f"찾을 수 없는 호선·지선입니다: {line} {branch}")
        return list(branches[branch])

    # ---------- SubwayGraph 공개 메서드 전달 ----------
    def station_congestion(self, code, next_code, line, day):
        return self.graph.station_congestion(code, next_code, line, day)

    def shortest(self, start, end):
        return self.graph.shortest(start, end)

    def route_options(self, start, end):
        return self.graph.route_options(start, end)
