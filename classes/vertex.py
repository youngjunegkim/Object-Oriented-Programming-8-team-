"""한 역의 한 호선 정점과 여기서 출발하는 간선을 관리한다."""


class Vertex:
    """역코드는 문자열로 보관하고, 탑승·환승 간선을 같은 목록에 담는다."""

    def __init__(self, station_code: str, station, line: str):
        if not isinstance(station_code, str) or not station_code.strip():
            raise ValueError("역코드는 비어 있지 않은 문자열이어야 합니다.")
        if station is None:
            raise ValueError("소속 Station이 필요합니다.")
        if not isinstance(line, str) or not line.strip():
            raise ValueError("호선은 비어 있지 않은 문자열이어야 합니다.")

        self.station_code = station_code.strip()
        self.station = station
        self.line = line.strip()
        self.edges = []

    def add_edge(self, edge):
        """이 정점에서 출발하는 간선을 등록한다. 같은 간선의 재등록은 무시한다."""
        if edge.from_v is not self:
            raise ValueError("이 정점에서 출발하는 간선만 등록할 수 있습니다.")
        if edge in self.edges:
            return

        # 도착 정점이 같아도 방향 조건이 다른 환승 간선은 각각 보관한다.
        self.edges.append(edge)
