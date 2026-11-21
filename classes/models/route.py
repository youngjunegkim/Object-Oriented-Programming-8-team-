"""찾아낸 경로를 저장하고, 그 경로의 시간·환승·거리·혼잡도를 계산한다."""

from ..service_time import DAYS, departure_seconds, congestion_slot
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

    def ride_congestions(self, day, departure_time):
        """탑승 구간마다 (간선, 진입 시간대, 혼잡도) 목록. 관측 범위 밖이면 시간대·혼잡도는 None."""
        if day not in DAYS:
            raise ValueError(f"요일은 {DAYS} 중 하나여야 합니다.")
        clock = departure_seconds(departure_time)
        result = []
        for edge in self.edges:
            if isinstance(edge, RideEdge):
                slot = congestion_slot(clock)
                value = edge.congestion_get(day, slot) if slot is not None else None
                result.append((edge, slot, value))
            clock += edge.cost()  # 환승 보행 시간도 다음 탑승 시각에 반영한다.
        return result

    def avg_congestion(self, day, departure_time):
        """각 탑승 구간 진입 시각의 혼잡도 산술평균(%). 계산할 수 없으면 None."""
        values = [value for edge, slot, value in self.ride_congestions(day, departure_time)]
        if not values or None in values:
            return None
        return sum(values) / len(values)
