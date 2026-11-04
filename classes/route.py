"""탐색된 경로의 시간, 환승, 거리, 혼잡도를 계산한다."""

from .data_loader import DAYS
from .edge import RideEdge



class Route:
    """출발부터 도착까지 실제로 거친 탑승·환승 간선을 순서대로 보관한다."""

    def __init__(self, edges): #self.edges는 경로를 순서대로 담은 목록(rideedge, transferedge 포함해서 나열한 것)
        self.edges = edges

    def total_time(self):             #경로에 있는 시간을 전부 더 한것
        """탑승 시간과 환승 시간을 더한 값(초)."""
        return sum(edge.cost() for edge in self.edges) #edge.cost()는 edge의 시간임

    def transfer_count(self):      #환승 횟수
        return sum(edge.is_transfer for edge in self.edges)   #edge에서 transferedge가 있으면 True여서 1이 됨-> 1번 환승

    def stops(self):
        """(이동한 정거장 수, 총 이동거리 m). 거리 누락이 있으면 거리는 None."""
        count_rides = sum(isinstance(edge, RideEdge) for edge in self.edges) #rideedge로 열차를 탑승하는 edge인가
        if any(edge.meters is None for edge in self.edges):
            return count_rides, None
        return count_rides, sum(edge.meters for edge in self.edges)         #거리가 전부 있으면 거리를 전부 더해서 반환(rideedge와 transferedge 전부 더함, m임)

    def avg_congestion(self, day, departure_time):      #route.avg_congestion("평일", "08:28") 이 시간 출발하면 평균적으로 얼마나 붐빌까를 답함
        """각 탑승 구간 진입 시각의 혼잡도 산술평균(%). 계산할 수 없으면 None.""" #rideedge에서 30분 단위로 출발시간의 혼잡도를 구하고 transfer은 이동 중이므로 계산 안함.
        if day not in DAYS:
            raise ValueError(f"요일은 {DAYS} 중 하나여야 합니다.")
        hour, minute = map(int, departure_time.split(":"))
        if not (0 <= hour < 24 and 0 <= minute < 60):
            raise ValueError("출발 시각은 00:00~23:59 범위여야 합니다.")
        # 새벽 0시대는 선택한 운행일의 마지막 시간대다.
        clock = ((hour + 24 if hour < 5 else hour) * 60 + minute) * 60 #시간대 구하는 줄: 볼필요 없음
        values = []
        for edge in self.edges:  #edges중에서 rideedge면 slot에 현재 시간의 30분 시간대를 구해 넣음.
            if isinstance(edge, RideEdge):
                if clock < (5 * 60 + 30) * 60 or clock >= 25 * 3600:
                    return None
                slot = f"{clock // 3600 % 24:02d}:{clock % 3600 // 1800 * 30:02d}"
                value = edge.congestion_get(day, slot)
                if value is None:
                    return None
                values.append(value)             # 들여쓰기 주의: 열차에 타 있는 rideedge상태일 때만 append
            clock += edge.cost()  # 환승 보행 시간도 다음 탑승 시각에 반영
        return sum(values) / len(values) if values else None
