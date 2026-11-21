# 역·탑승 구간·환승·혼잡도 CSV를 읽고 검사해 리스트와 딕셔너리로 반환한다.
# 역코드는 문자열로 보존하고, 시간·거리·혼잡도는 숫자로 변환한다.
# 반환된 데이터는 SubwayGraph에서 역·정점·간선 객체를 만드는 데 사용한다.

import csv
from pathlib import Path

from ..service_time import DAYS, SLOTS  # 기존 import 경로에서도 계속 사용 가능

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "Data"
CONGESTION_CSV = DATA / "Congestion" / "congestion.csv"
CONGESTION_II_CSV = DATA / "Congestion_II" / "congestion.csv"

SOURCES = ["measured", "measured-9", "generated"]


# 아래 6개 함수는 CSV 값의 자료형 변환, 빈칸 처리, 허용값 검사를 담당한다.
# 필수 문자열은 빈칸을 거부하고, 선택 항목의 빈칸은 None으로 바꾼다.
# 시간·거리는 0 이상의 정수, 요일·출처는 허용된 값만 받는다.
def text(value):
    if not value.strip():
        raise ValueError("필수 값이 비어 있다")
    return value


def text_or_none(value):
    return value or None


def integer(value):
    try:
        number = int(value)
    except ValueError:
        raise ValueError("0 이상의 정수여야 한다") from None
    if number < 0:
        raise ValueError("0 이상의 정수여야 한다")
    return number


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
    def convert(value):
        if value not in allowed:
            raise ValueError(f"{allowed} 중 하나여야 한다")
        return value
    return convert


STATION_COLUMNS = {
    "station_code": text,
    "station_no": text_or_none,
    "name": text,
    "line": text,
    "api_line": text,
    "branch": text,
}

EDGE_COLUMNS = {
    "line": text,
    "branch": text,
    "from_code": text,
    "from_name": text,
    "to_code": text,
    "to_name": text,
    "seconds": integer,
    "meters": integer_or_none,
    "note": text_or_none,
}

TRANSFER_COLUMNS = {
    "from_code": text,
    "from_name": text,
    "from_line": text,
    "from_prev_code": text,
    "from_prev_name": text,
    "from_dir": text_or_none,
    "to_code": text,
    "to_name": text,
    "to_line": text,
    "to_next_code": text,
    "to_next_name": text,
    "to_dir": text_or_none,
    "seconds": integer,
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
    **{slot: number_or_none for slot in SLOTS},
}


class CongestionDataLoader:
    # 역·구간·환승 CSV의 경로와 사용할 혼잡도 CSV의 경로를 저장한다.
    def __init__(self, data_dir=DATA, congestion_path=CONGESTION_II_CSV):
        data_dir = Path(data_dir)
        self.stations_path = data_dir / "Station" / "stations.csv"
        self.edges_path = data_dir / "Edge" / "edges.csv"
        self.transfers_path = data_dir / "Transfer" / "transfers.csv"
        self.congestion_path = Path(congestion_path)

    # 호선별 역 정보를 읽어 역 정보 딕셔너리들의 리스트로 반환한다.
    def load_stations(self):
        return _read_table(
            self.stations_path,
            STATION_COLUMNS,
            unique_by=["station_code"],
        )

    # 방향별 탑승 구간의 시간·거리를 호선별로 묶어 딕셔너리로 반환한다.
    def load_distance(self):
        edges = _read_table(
            self.edges_path,
            EDGE_COLUMNS,
            unique_by=["line", "branch", "from_code", "to_code"],
        )

        distance = {}
        for edge in edges:
            line = edge["line"]
            if line not in distance:
                distance[line] = []
            distance[line].append(edge)
        return distance

    # 진입·진출 방향을 보존한 환승 목록을 역코드 쌍별 딕셔너리로 반환한다.
    def load_transfers(self):
        transfers = _read_table(
            self.transfers_path,
            TRANSFER_COLUMNS,
            unique_by=["from_code", "from_prev_code", "to_code", "to_next_code"],
        )

        by_pair = {}
        for transfer in transfers:
            pair = (transfer["from_code"], transfer["to_code"])
            if pair not in by_pair:
                by_pair[pair] = []
            by_pair[pair].append(transfer)
        return by_pair

    # 구간별 혼잡도와 출처를 요일·시간대별로 정리한 딕셔너리로 반환한다.
    def load_congestion(self):
        rows = _read_table(
            self.congestion_path,
            CONGESTION_COLUMNS,
            unique_by=["line", "from_code", "to_code", "day"],
        )

        congestion = {}
        for row in rows:
            section = (row["line"], row["from_code"], row["to_code"])
            if section not in congestion:
                congestion[section] = {}
            congestion[section][row["day"]] = {
                "source": row["source"],
                "values": {slot: row[slot] for slot in SLOTS},
            }

        for section, days in congestion.items():
            missing = [day for day in DAYS if day not in days]
            if missing:
                raise ValueError(f"{self.congestion_path.name}: {section} 구간에 {missing} 줄이 없다")
        return congestion


# CSV 문법 처리는 표준 csv 모듈에 맡긴다. 따옴표 안의 쉼표·줄바꿈도 보존한다.
def _read_table(path, columns, unique_by):
    path = Path(path)
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, strict=True)
        result = []
        seen = {}
        try:
            header = reader.fieldnames or []
            missing = [name for name in columns if name not in header]
            if missing:
                raise ValueError(f"{path.name}: 필요한 열이 없다 {missing}")
            if len(header) != len(set(header)):
                raise ValueError(f"{path.name}: 중복된 열 이름이 있다")

            for raw in reader:
                # 여러 줄에 걸친 CSV 값은 해당 레코드가 끝난 실제 파일 줄 번호를 표시한다.
                line_no = reader.line_num
                if None in raw or any(value is None for value in raw.values()):
                    raise ValueError(f"{path.name}:{line_no}: 데이터 칸 수가 헤더의 {len(header)}개와 다르다")

                row = {}
                for name, convert in columns.items():
                    try:
                        row[name] = convert(raw[name])
                    except ValueError as e:
                        raise ValueError(f"{path.name}:{line_no}: '{name}' 칸의 값 {raw[name]!r}을 읽을 수 없다 ({e})") from None

                key = tuple(row[name] for name in unique_by)
                if key in seen:
                    raise ValueError(f"{path.name}:{line_no}: {seen[key]}번째 줄과 겹친다 {dict(zip(unique_by, key))}")
                seen[key] = line_no
                result.append(row)
        except csv.Error as e:
            raise ValueError(f"{path.name}:{reader.line_num}: CSV 형식 오류 ({e})") from None
    return result
