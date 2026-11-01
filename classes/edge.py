#Station과 Vertex가 관련 객체를 모아 관리한다면, Edge는 정점 사이를 실제로 연결하는 구간
#
class Edge: #두 Vertex 사이의 이동 구간을 표현하기 위해 존재하는 클래스
    def __init__(self, from_v, to_v, seconds: int, meters=None):
        self._validate(from_v, to_v, seconds, meters)

        self.from_v = from_v
        self.to_v = to_v
        self.seconds = seconds
        self.meters = meters

    @staticmethod #데이터 유효성 검사
    def _validate(from_v, to_v, seconds, meters):
        if from_v is None or to_v is None:
            raise ValueError("출발 정점과 도착 정점이 필요합니다.")

        if type(seconds) is not int or seconds < 0:
            raise ValueError("소요시간은 0 이상의 정수여야 합니다.")

        if meters is not None:
            if type(meters) is not int or meters < 0:
                raise ValueError("거리는 0 이상의 정수 또는 None이어야 합니다.")

    def cost(self):
        return self.seconds

class RideEdge(Edge):
    def __init__(self, from_v, to_v, seconds: int, meters, congestion):
        super().__init__(from_v, to_v, seconds, meters)
        self.congestion = congestion

    def congestion_get(self, day=None, slot=None):
        if day is None: #요일 데이터 없이 시간 데이터만 들어올 경우 오류 발생해야함
            if slot is not None:
                raise ValueError("시간대를 지정하려면 요일도 필요합니다.")
            return self.congestion

        if slot is None:
            return self.congestion[day]["values"] # 선택한 요일의 모든 시간대 혼잡도 반환

        return self.congestion[day]["values"][slot] #특정 시간대 혼잡도 반환

class TransferEdge(Edge):
    def __init__(self, from_v, to_v, seconds, meters=None, *, from_prev_code, to_next_code):
        super().__init__(from_v, to_v, seconds, meters)

        self.from_prev_code = from_prev_code
        self.to_next_code = to_next_code




