"""① 역별 혼잡도 화면: 역 선택 목록, 출발 방향, 평일·토·일 비교."""

from ..service_time import DAYS, SLOTS


class StationCongestionView:
    def __init__(self, query):
        self.query = query  # GraphQuery와 같은 메서드를 가진 객체면 된다.

    def station_options(self):
        """역 선택 목록. 동명이역은 호선을 붙여 구분하고, 서버에는 역코드를 보낸다."""
        options = []
        for name, station, same_name_count in self.query.physical_stations():
            lines = [vertex.line for vertex in station.vertices]
            options.append({
                "code": station.vertices[0].station_code,  # 역코드 하나로 물리적 역 전체를 선택한다.
                "name": name,
                "label": name if same_name_count == 1 else f"{name} ({', '.join(lines)})",
                "lines": lines,
            })
        options.sort(key=lambda option: option["label"])
        return options

    def directions(self, code):
        """선택한 역에서 출발할 수 있는 (호선, 다음 역) 방향 목록."""
        station = self.query.vertex(code).station
        directions = []
        for vertex in station.vertices:
            for edge in self.query.rides_from(vertex):
                directions.append({
                    "line": vertex.line,
                    "next_code": edge.to_v.station_code,
                    "next_name": edge.to_v.station.name,
                })
        return {"station": station.name, "directions": directions}

    def compare_days(self, code, next_code, line):
        """평일·토요일·일요일의 30분별 혼잡도를 한 번에 비교한다."""
        start = self.query.vertex(code).station
        edge = self.query.ride_on_line(code, next_code, line)
        if edge is None:
            raise ValueError(f"{line}에서 {code} → {next_code} 방향의 탑승 구간이 없습니다.")
        days = {}
        for day in DAYS:
            values = edge.day_congestion(day)
            days[day] = {
                "source": edge.source(day),
                "values": [values.get(slot) for slot in SLOTS],
            }
        return {
            "station": start.name,
            "next": self.query.vertex(next_code).station.name,
            "line": line,
            "slots": SLOTS,
            "days": days,
        }
