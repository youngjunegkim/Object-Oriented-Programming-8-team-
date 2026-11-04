# 두 Vertex 사이의 이동 구간(간선)을 표현한다.
# RideEdge는 같은 호선의 탑승 구간, TransferEdge는 다른 호선으로 갈아타는 구간이다.
# 값 검사는 data_loader.py에서 끝났으므로 여기서는 하지 않는다.


class Edge:
    def __init__(self, from_v, to_v, seconds, meters=None):
        self.from_v = from_v
        self.to_v = to_v
        self.seconds = seconds
        self.meters = meters

    # 경로 탐색에 쓰는 비용: 소요시간(초)
    def cost(self):
        return self.seconds


class RideEdge(Edge):
    def __init__(self, from_v, to_v, seconds, meters, congestion):
        super().__init__(from_v, to_v, seconds, meters)
        self.congestion = congestion

    # 요일·시간대를 지정한 만큼 혼잡도를 좁혀서 반환한다.
    # congestion_get()            → 모든 요일
    # congestion_get("평일")       → 평일의 모든 시간대
    # congestion_get("평일", "08:00") → 평일 08:00 값 하나
    def congestion_get(self, day=None, slot=None):
        if day is None:
            return self.congestion
        if slot is None:
            return self.congestion[day]["values"]
        return self.congestion[day]["values"][slot]


class TransferEdge(Edge):
    # from_prev_code: 환승 전 타고 온 열차의 직전 역, to_next_code: 환승 후 탈 열차의 다음 역
    def __init__(self, from_v, to_v, seconds, meters, from_prev_code, to_next_code):
        super().__init__(from_v, to_v, seconds, meters)
        self.from_prev_code = from_prev_code
        self.to_next_code = to_next_code
