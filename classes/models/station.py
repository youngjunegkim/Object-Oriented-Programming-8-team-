# 물리적 역 하나와 그 역에 속한 호선별 정점을 관리한다.
# 예: 교대역 하나에 2호선·3호선 Vertex가 속한다.
# 값 검사는 data_loader.py에서 끝났으므로 여기서는 하지 않는다.


class Station:
    def __init__(self, name):
        self.name = name
        self.vertices = []

    # 이 역에 정점을 등록한다. 같은 정점의 재등록은 무시한다.
    def add_vertex(self, vertex):
        if vertex not in self.vertices:
            self.vertices.append(vertex)
