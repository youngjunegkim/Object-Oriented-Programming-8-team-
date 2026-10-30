"""Data/ 폴더의 CSV를 읽어 파이썬 기본 자료형(dict, list)으로 돌려주는 로더다.

이 파일이 하는 일은 딱 세 가지다.
  1. CSV 읽기
  2. 검사하기  - 필요한 열이 다 있는지, 같은 행이 두 번 나오지 않는지
  3. 자료형 바꾸기 - "450" → 450, 빈칸 → None

이런 일은 하지 않는다.
  - 원본 엑셀 가공, 혼잡도 생성 → collect/ 코드가 이미 해 두었다.
  - Station·Edge 객체 만들기 → SubwayGraph.build()가 한다.

사용 예:
    loader = CongestionDataLoader()
    loader.load_distance()["2호선"][0]                                         # 시청 → 충정로, 90초
    loader.load_congestion()[("2호선", "0222", "0221")]["평일"]["values"]["08:00"]  # 강남 → 역삼, 46.1
    loader.load_transfers()[("0340", "2818")]                                  # 가락시장 3호선 → 8호선

    실험판 혼잡도를 쓰려면:
    CongestionDataLoader(congestion_path=CONGESTION_II_CSV)
"""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "Data"
CONGESTION_CSV = DATA / "Congestion" / "congestion.csv"        # 기본판
CONGESTION_II_CSV = DATA / "Congestion_II" / "congestion.csv"  # 실험판 (역별 승하차 차이를 더 반영)

DAYS = ["평일", "토요일", "일요일"]
SLOTS = [f"{h % 24:02d}:{m:02d}" for h in range(5, 25) for m in (0, 30)][1:]  # "05:30" ~ "00:30", 30분씩 39칸
SOURCES = ["measured", "measured-9", "generated"]  # 1~8호선 실측 / 9호선 실측 / 생성값


# ── 값 변환 규칙 ─────────────────────────────────────────────
# CSV 칸은 모두 글자로 읽힌다. 아래 함수가 칸 하나를 원하는 자료형으로 바꾼다.
# 바꿀 수 없는 값이면 ValueError를 내고, 어느 파일 몇째 줄인지는 _read_table()이 덧붙인다.

def text(value):
    return value


def text_or_none(value):
    return value or None


def integer(value):
    try:
        return int(value)
    except ValueError:
        raise ValueError("정수여야 한다") from None


def integer_or_none(value):
    return integer(value) if value else None


def number_or_none(value):
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        raise ValueError("숫자여야 한다") from None


def one_of(allowed):
    """정해진 값만 받는 규칙을 만든다. 예) one_of(DAYS)는 "평일"·"토요일"·"일요일"만 통과시킨다."""
    def convert(value):
        if value not in allowed:
            raise ValueError(f"{allowed} 중 하나여야 한다")
        return value
    return convert


# ── 파일별 열 구성 ───────────────────────────────────────────
# "열 이름: 변환 규칙" 표다. CSV에 열이 추가되거나 바뀌면 메서드는 그대로 두고 이 표만 고치면 된다.

STATION_COLUMNS = {
    "station_code": text,           # 역 코드. 다른 CSV는 모두 이 코드로 역을 가리킨다
    "station_no": text_or_none,     # 노선도 역번호. "P170" 같은 값도 있어 글자로 둔다
    "name": text,
    "line": text,
    "api_line": text,
    "branch": text,                 # 지선이 여러 개면 "경부선/경인선"처럼 '/'로 이어져 있다
}

EDGE_COLUMNS = {
    "line": text,
    "branch": text,
    "from_code": text,
    "from_name": text,
    "to_code": text,
    "to_name": text,
    "seconds": integer,             # 열차 소요시간(초)
    "meters": integer_or_none,      # 거리(m). API가 알려주지 않은 구간은 None
    "note": text_or_none,           # 보정한 값이면 "fix:..."
}

TRANSFER_COLUMNS = {
    "from_code": text,              # 내리는 역
    "from_name": text,
    "from_line": text,
    "from_prev_code": text,         # 내리기 직전에 지나온 역 = 타고 온 방향
    "from_prev_name": text,
    "from_dir": text_or_none,       # 상행/하행 같은 방향 표기 (참고용)
    "to_code": text,                # 타는 역
    "to_name": text,
    "to_line": text,
    "to_next_code": text,           # 갈아탄 뒤 다음에 갈 역 = 탈 방향
    "to_next_name": text,
    "to_dir": text_or_none,
    "seconds": integer,             # 걸어서 갈아타는 시간(초). 열차 기다리는 시간은 빠져 있다
    "meters": integer_or_none,
    "note": text_or_none,
}

CONGESTION_COLUMNS = {
    "line": text,
    "branch": text,
    "from_code": text,
    "from_name": text,
    "to_code": text,
    "to_name": text,
    "day": one_of(DAYS),
    "source": one_of(SOURCES),
    **{slot: number_or_none for slot in SLOTS},  # 혼잡도(%). 운행이 없는 시간대는 None
}


class CongestionDataLoader:
    """역·구간·환승·혼잡도 CSV를 읽어 돌려주는 로더다.

    모든 메서드에 공통인 규칙
      - 역 코드는 문자열이다. "0222"의 앞자리 0이 살아 있다.
      - 시간은 초(int), 거리는 미터(int), 혼잡도는 %(float)다.
      - 값이 없으면 None이다. (거리를 모르는 구간, 운행이 없는 시간대 등)
      - 메서드를 부를 때마다 파일을 새로 읽으므로, 받은 결과는 마음대로 고쳐 써도 된다.
    """

    def __init__(self, data_dir=DATA, congestion_path=CONGESTION_CSV):
        # 경로를 밖에서 받아 두면, 코드를 고치지 않고도 다른 데이터나 실험판 혼잡도로 바꿔 쓸 수 있다.
        data_dir = Path(data_dir)
        self.stations_path = data_dir / "Station" / "stations.csv"
        self.edges_path = data_dir / "Edge" / "edges.csv"
        self.transfers_path = data_dir / "Transfer" / "transfers.csv"
        self.congestion_path = Path(congestion_path)

    def load_stations(self):
        """역 목록을 돌려준다.

        [{"station_code", "station_no", "name", "line", "api_line", "branch"}, ...]
        한 항목은 "한 노선의 역" 하나다. 서울역은 노선이 4개라 4개 항목이다.
        """
        return _read_table(self.stations_path, STATION_COLUMNS, unique_by=["station_code"])

    def load_distance(self):
        """호선별 탑승 구간을 돌려준다.

        {"2호선": [{"line", "branch", "from_code", "from_name", "to_code", "to_name",
                    "seconds", "meters", "note"}, ...], ...}
        구간에는 방향이 있다. A→B와 B→A는 서로 다른 구간이다.
        호선 안의 순서는 CSV에 적힌 순서 그대로다. 그래프를 만들거나 경로를 찾을 때는 순서가 상관없다.
        """
        edges = _read_table(self.edges_path, EDGE_COLUMNS, unique_by=["line", "branch", "from_code", "to_code"])

        distance = {}
        for edge in edges:
            distance.setdefault(edge["line"], []).append(edge)
        return distance

    def load_transfers(self):
        """환승역별 호선 간 환승 소요시간을 방향별로 돌려준다.

        {(내리는 역 코드, 타는 역 코드): [{"from_prev_code", "to_next_code", "seconds", ...}, ...]}
        같은 역에서 같은 노선끼리 갈아타도, 어느 쪽에서 와서 어느 쪽으로 가느냐에 따라 시간이 다르다.
        그래서 지나온 역(from_prev_code)과 다음 역(to_next_code)을 함께 담는다.
        """
        transfers =_read_table(self.transfers_path, TRANSFER_COLUMNS,
                                unique_by=["from_code", "from_prev_code", "to_code", "to_next_code"])

        # 역 이름이 아니라 역 코드 쌍으로 묶는다. 이름으로 묶으면 두 방향으로 틀릴 수 있기 때문이다.
        #
        # 이름은 같은데 다른 역 — 양평
        #    5호선 양평(2523)은 서울 영등포구, 경의중앙선 양평(1217)은 경기도 양평군에 있다.
        #    이름으로 묶으면 수십km 떨어진 두 역 사이에 있지도 않은 환승이 생긴다.

        by_pair = {}
        for t in transfers:
            by_pair.setdefault((t["from_code"], t["to_code"]), []).append(t)
        return by_pair

    def load_congestion(self):
        """구간·요일·시간대별 혼잡도를 돌려준다.

        {(호선, 출발역 코드, 도착역 코드): {"평일": {"source": "measured", "values": {"08:00": 46.1, ...}}, ...}}
        키의 세 값은 load_distance() 구간의 line, from_code, to_code와 같아서 바로 이어 붙일 수 있다.
        """
        rows =_read_table(self.congestion_path, CONGESTION_COLUMNS,
                           unique_by=["line", "from_code", "to_code", "day"])

        # CSV 한 줄 = 한 구간의 하루치다. 같은 구간의 세 요일을 하나로 모은다.
        congestion = {}
        for row in rows:
            section = (row["line"], row["from_code"], row["to_code"])
            congestion.setdefault(section, {})[row["day"]] = {
                "source": row["source"],
                "values": {slot: row[slot] for slot in SLOTS},
            }

        for section, days in congestion.items():
            missing = [day for day in DAYS if day not in days]
            if missing:
                raise ValueError(f"{self.congestion_path.name}: {section} 구간에 {missing} 줄이 없다")
        return congestion


# ── CSV 공통 처리 ────────────────────────────────────────────

def _read_table(path, columns, unique_by):
    """CSV를 읽어 columns 표대로 바꾼 딕셔너리 목록을 돌려준다.

    문제가 있으면 바로 ValueError를 낸다. 메시지에 파일 이름과 줄 번호가 들어가 어디를 고칠지 알 수 있다.
      - 필요한 열이 없을 때
      - unique_by 값이 같은 줄이 두 번 나올 때
      - 칸 값을 바꿀 수 없을 때 (숫자 자리에 글자 등)
    """
    path = Path(path)
    with open(path, encoding="utf-8-sig", newline="") as f:  # utf-8-sig: 엑셀이 붙이는 BOM을 떼어 낸다
        reader = csv.DictReader(f)
        missing = [name for name in columns if name not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"{path.name}: 필요한 열이 없다 {missing}")

        result, seen = [], {}
        for line_no, raw in enumerate(reader, start=2):  # 1번째 줄은 열 이름이라 2부터 센다
            key = tuple(raw[name] for name in unique_by)
            if key in seen:
                raise ValueError(f"{path.name}:{line_no}: {seen[key]}번째 줄과 겹친다 {dict(zip(unique_by, key))}")
            seen[key] = line_no

            row = {}
            for name, convert in columns.items():
                try:
                    row[name] = convert(raw[name])
                except ValueError as e:
                    raise ValueError(f"{path.name}:{line_no}: '{name}' 칸의 값 {raw[name]!r}을 읽을 수 없다 ({e})") from None
            result.append(row)
    return result
