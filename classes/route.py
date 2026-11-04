"""탐색된 경로의 시간, 환승, 거리, 혼잡도를 계산한다."""

from .data_loader import DAYS
from .edge import RideEdge


class Route:
    """출발부터 도착까지 실제로 거친 탑승·환승 간선을 순서대로 보관한다."""

    def __init__(self, edges):
        self.edges = edges

    def total_time(self):
        """탑승 시간과 환승 시간을 더한 값(초)."""
        return sum(edge.cost() for edge in self.edges)

    def transfer_count(self):
        return sum(edge.is_transfer for edge in self.edges)

    def stops(self):
        """(이동한 정거장 수, 총 이동거리 m). 거리 누락이 있으면 거리는 None."""
        count_rides = sum(isinstance(edge, RideEdge) for edge in self.edges)
        if any(edge.meters is None for edge in self.edges):
            return count_rides, None
        return count_rides, sum(edge.meters for edge in self.edges)

    def avg_congestion(self, day, departure_time):
        """각 탑승 구간 진입 시각의 혼잡도 산술평균(%). 계산할 수 없으면 None."""
        if day not in DAYS:
            raise ValueError(f"요일은 {DAYS} 중 하나여야 합니다.")
        hour, minute = map(int, departure_time.split(":"))
        if not (0 <= hour < 24 and 0 <= minute < 60):
            raise ValueError("출발 시각은 00:00~23:59 범위여야 합니다.")
        # 새벽 0시대는 선택한 운행일의 마지막 시간대다.
        clock = ((hour + 24 if hour < 5 else hour) * 60 + minute) * 60
        values = []
        for edge in self.edges:
            if isinstance(edge, RideEdge):
                if clock < (5 * 60 + 30) * 60 or clock >= 25 * 3600:
                    return None
                slot = f"{clock // 3600 % 24:02d}:{clock % 3600 // 1800 * 30:02d}"
                value = edge.congestion_get(day, slot)
                if value is None:
                    return None
                values.append(value)
            clock += edge.cost()  # 환승 보행 시간도 다음 탑승 시각에 반영
        return sum(values) / len(values) if values else None
