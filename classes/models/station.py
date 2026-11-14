"""물리적 역 하나와 그 역에 속한 호선별 정점을 관리한다."""


class Station:
    """예: 교대역 하나에 2호선·3호선 Vertex가 속한다."""

    def __init__(self, name: str):
        if not isinstance(name, str) or not name.strip():
            raise ValueError("역 이름은 비어 있지 않은 문자열이어야 합니다.")

        self.name = name.strip()
        self.vertices = []

    def add_vertex(self, vertex):
        """이 역에 소속된 정점을 등록한다. 같은 정점의 재등록은 무시한다."""
        if vertex.station is not self:
            raise ValueError("이 역에 소속된 정점만 등록할 수 있습니다.")
        if vertex in self.vertices:
            return
        for existing in self.vertices:
            if existing.station_code == vertex.station_code:
                raise ValueError("같은 역코드의 다른 정점이 이미 등록되어 있습니다.")

        self.vertices.append(vertex)
