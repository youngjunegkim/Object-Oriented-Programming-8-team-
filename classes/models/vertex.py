# 한 역의 한 호선 정점과 여기서 출발하는 간선을 관리한다.
# 역코드는 문자열("0150")로 보관하고, 탑승·환승 간선을 같은 목록에 담는다.
# 값 검사는 data_loader.py에서 끝났으므로 여기서는 하지 않는다.


class Vertex:
    def __init__(self, station_code, station, line):
        self.station_code = station_code
        self.station = station
        self.line = line
        self.edges = []

    # 이 정점에서 출발하는 간선을 등록한다. 같은 간선의 재등록은 무시한다.
    # 도착 정점이 같아도 방향 조건이 다른 환승 간선은 각각 보관한다.
    def add_edge(self, edge):
        if edge not in self.edges:
            self.edges.append(edge)
