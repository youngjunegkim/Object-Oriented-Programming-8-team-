"""CSV 입출력과 독립적인 운행일·시간대 규칙."""
#service_time.py: 출발 시각을 계산하고, 해당 시각의 혼잡도 데이터를 찾도록 도와주는 파일

DAYS = ["평일", "토요일", "일요일"]
SLOTS = [f"{h % 24:02d}:{m:02d}" for h in range(5, 25) for m in (0, 30)][1:] #혼잡도 데이터의 시간대를 05:30부터 다음 날 00:30까지 30분 간격으로 만듦.



def departure_seconds(departure_time): #"08:30" 같은 문자열을 초 단위 숫자로 바꿈 -> 30600초(새벽 5시 이전은 24시간을 더해 다음 날로 계산하므로 "00:30"은 88200초)
    """HH:MM을 초로 바꾼다. 새벽 0시대는 선택한 운행일의 마지막 시간대다."""
    hour, minute = map(int, departure_time.split(":")) #map: 지정한 함수를 여러 개의 데이터에 일괄적용하는 함수 (리스트로 split된 것에 int()함수를 각각 적용)
    if not (0 <= hour < 24 and 0 <= minute < 60):
        raise ValueError("출발 시각은 00:00~23:59 범위여야 합니다.")
    if hour < 5:
        hour += 24
    return (hour * 60 + minute) * 60


def congestion_slot(clock): #초 단위 시각이 속하는 30분 시간대를 반환
    """08:28은 "08:00", 08:45는 "08:30" → 관측 범위인 05:30 이상, 다음 날 01:00 미만을 벗어나면 None을 반환"""
    if clock < (5 * 60 + 30) * 60 or clock >= 25 * 3600:
        return None
    hour = clock // 3600 % 24
    minute = clock % 3600 // 1800 * 30
    return f"{hour:02d}:{minute:02d}"


"""08:28에 출발하면 → 초로 변환 → "08:00" 시간대의 혼잡도 구할 수 있음"""