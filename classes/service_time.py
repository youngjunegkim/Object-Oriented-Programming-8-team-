"""운행일·시간대 규칙: 출발 시각을 초로 바꾸고, 그 시각의 혼잡도 시간대를 찾는다."""

DAYS = ["평일", "토요일", "일요일"]
# 혼잡도 시간대: 05:30부터 다음 날 00:30까지 30분 간격
SLOTS = [f"{h % 24:02d}:{m:02d}" for h in range(5, 25) for m in (0, 30)][1:]


def check_day(day):
    if day not in DAYS:
        raise ValueError(f"요일은 {DAYS} 중 하나여야 합니다.")


def departure_seconds(departure_time):
    """HH:MM을 초로 바꾼다. 새벽 0~4시는 선택한 운행일의 마지막 시간대라 24시간을 더한다.

    예: "08:30" → 30600, "00:30" → 88200
    """
    hour, minute = map(int, departure_time.split(":"))
    if not (0 <= hour < 24 and 0 <= minute < 60):
        raise ValueError("출발 시각은 00:00~23:59 범위여야 합니다.")
    if hour < 5:
        hour += 24
    return (hour * 60 + minute) * 60


def congestion_slot(clock):
    """초 단위 시각이 속한 30분 시간대. 08:28 → "08:00", 08:45 → "08:30".

    관측 범위(05:30 이상, 다음 날 01:00 미만)를 벗어나면 None.
    """
    if clock < (5 * 60 + 30) * 60 or clock >= 25 * 3600:
        return None
    hour = clock // 3600 % 24
    minute = clock % 3600 // 1800 * 30
    return f"{hour:02d}:{minute:02d}"
