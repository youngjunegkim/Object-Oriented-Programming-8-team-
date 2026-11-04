# 역·탑승 구간·환승·혼잡도 CSV를 한 줄씩 읽어 리스트와 딕셔너리로 반환한다.
# 데이터 오류(누락·잘못된 값·중복)는 이 파일에서만 검사한다.
# Station·Vertex·Edge 클래스는 여기서 검사를 통과한 값만 받는다고 가정한다.

import os

CODE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = CODE_DIR + "/Data"

DAYS = ["평일", "토요일", "일요일"]
SOURCES = ["measured", "measured-9", "generated"]

# 혼잡도 시간대: 05:30부터 30분 간격으로 다음 날 00:30까지 39칸
SLOTS = ["05:30", "06:00", "06:30", "07:00", "07:30", "08:00", "08:30", "09:00",
         "09:30", "10:00", "10:30", "11:00", "11:30", "12:00", "12:30", "13:00",
         "13:30", "14:00", "14:30", "15:00", "15:30", "16:00", "16:30", "17:00",
         "17:30", "18:00", "18:30", "19:00", "19:30", "20:00", "20:30", "21:00",
         "21:30", "22:00", "22:30", "23:00", "23:30", "00:00", "00:30"]

STATION_COLUMNS = ["station_code", "station_no", "name", "line", "api_line", "branch"]
EDGE_COLUMNS = ["line", "branch", "from_code", "from_name", "to_code", "to_name",
                "seconds", "meters", "note"]
TRANSFER_COLUMNS = ["from_code", "from_name", "from_line", "from_prev_code", "from_prev_name", "from_dir",
                    "to_code", "to_name", "to_line", "to_next_code", "to_next_name", "to_dir",
                    "seconds", "meters", "note"]
CONGESTION_COLUMNS = ["line", "branch", "from_code", "from_name", "to_code", "to_name",
                      "day", "source"] + SLOTS


class DataLoader:
    # 데이터 폴더 아래 역·구간·환승·혼잡도 CSV의 경로를 저장한다.
    def __init__(self, data_dir=DATA_DIR):
        self.stations_path = data_dir + "/Station/stations.csv"
        self.edges_path = data_dir + "/Edge/edges.csv"
        self.transfers_path = data_dir + "/Transfer/transfers.csv"
        self.congestion_path = data_dir + "/Congestion/congestion.csv"

    # 호선별 역 정보를 딕셔너리들의 리스트로 반환한다.
    def load_stations(self):
        stations = []
        seen = {}
        for where, row in read_csv(self.stations_path, STATION_COLUMNS):
            check_filled(row, ["station_code", "name", "line", "api_line", "branch"], where)
            check_unique(seen, row["station_code"], where)

            row["station_no"] = empty_to_none(row["station_no"])
            stations.append(row)
        return stations

    # 방향별 탑승 구간을 {호선: [구간, ...]} 딕셔너리로 반환한다.
    def load_distance(self):
        distance = {}
        seen = {}
        for where, row in read_csv(self.edges_path, EDGE_COLUMNS):
            check_filled(row, ["line", "branch", "from_code", "from_name", "to_code", "to_name", "seconds"], where)
            check_unique(seen, (row["line"], row["branch"], row["from_code"], row["to_code"]), where)

            row["seconds"] = to_int(row, "seconds", where)
            row["meters"] = to_int(row, "meters", where)
            row["note"] = empty_to_none(row["note"])

            if row["line"] not in distance:
                distance[row["line"]] = []
            distance[row["line"]].append(row)
        return distance

    # 환승 목록을 {(출발 역코드, 도착 역코드): [환승, ...]} 딕셔너리로 반환한다.
    def load_transfers(self):
        transfers = {}
        seen = {}
        for where, row in read_csv(self.transfers_path, TRANSFER_COLUMNS):
            check_filled(row, ["from_code", "from_name", "from_line", "from_prev_code", "from_prev_name",
                               "to_code", "to_name", "to_line", "to_next_code", "to_next_name", "seconds"], where)
            check_unique(seen, (row["from_code"], row["from_prev_code"], row["to_code"], row["to_next_code"]), where)

            row["from_dir"] = empty_to_none(row["from_dir"])
            row["to_dir"] = empty_to_none(row["to_dir"])
            row["seconds"] = to_int(row, "seconds", where)
            row["meters"] = to_int(row, "meters", where)
            row["note"] = empty_to_none(row["note"])

            pair = (row["from_code"], row["to_code"])
            if pair not in transfers:
                transfers[pair] = []
            transfers[pair].append(row)
        return transfers

    # 혼잡도를 {(호선, 출발 역코드, 도착 역코드): {요일: {"source", "values"}}} 딕셔너리로 반환한다.
    def load_congestion(self):
        congestion = {}
        seen = {}
        for where, row in read_csv(self.congestion_path, CONGESTION_COLUMNS):
            check_filled(row, ["line", "branch", "from_code", "from_name", "to_code", "to_name", "day", "source"], where)
            check_unique(seen, (row["line"], row["from_code"], row["to_code"], row["day"]), where)
            if row["day"] not in DAYS:
                raise ValueError(f"{where}: day 값은 {DAYS} 중 하나여야 한다 ({row['day']!r})")
            if row["source"] not in SOURCES:
                raise ValueError(f"{where}: source 값은 {SOURCES} 중 하나여야 한다 ({row['source']!r})")

            values = {}
            for slot in SLOTS:
                values[slot] = to_float(row, slot, where)

            section = (row["line"], row["from_code"], row["to_code"])
            if section not in congestion:
                congestion[section] = {}
            congestion[section][row["day"]] = {"source": row["source"], "values": values}

        # 모든 구간에 평일·토요일·일요일 줄이 다 있는지 확인한다.
        for section in congestion:
            for day in DAYS:
                if day not in congestion[section]:
                    raise ValueError(f"{os.path.basename(self.congestion_path)}: {section} 구간에 {day} 줄이 없다")
        return congestion


# CSV를 한 줄씩 읽어 (위치, 행 딕셔너리) 목록으로 반환한다.
# 위치는 "edges.csv 15번째 줄"처럼 오류 메시지에 쓸 문자열이다.
def read_csv(path, columns):
    name = os.path.basename(path)
    f = open(path, encoding="utf-8-sig")  # utf-8-sig: 파일 맨 앞의 BOM 문자를 제거한다.
    header = f.readline().strip().split(",")

    for column in columns:
        if column not in header:
            f.close()
            raise ValueError(f"{name}: 필요한 열 {column!r}이 없다")

    rows = []
    line_no = 1
    for line in f:
        line_no += 1
        if line.strip() == "":
            continue

        values = line.strip().split(",")
        where = f"{name} {line_no}번째 줄"
        if len(values) != len(header):
            f.close()
            raise ValueError(f"{where}: 칸이 {len(header)}개여야 하는데 {len(values)}개다")

        row = {}
        for column in columns:
            row[column] = values[header.index(column)]
        rows.append((where, row))

    f.close()
    return rows


# 아래 함수들은 누락·중복·값 오류를 검사하고, 문제가 있으면 위치를 담아 오류를 발생시킨다.
def check_filled(row, columns, where):
    for column in columns:
        if row[column] == "":
            raise ValueError(f"{where}: {column} 칸이 비어 있다")


def check_unique(seen, key, where):
    if key in seen:
        raise ValueError(f"{where}: {seen[key]}과 겹친다 {key}")
    seen[key] = where


def empty_to_none(value):
    if value == "":
        return None
    return value


def to_int(row, column, where):
    value = row[column]
    if value == "":
        return None
    if not value.isdigit():
        raise ValueError(f"{where}: {column} 값이 0 이상의 정수가 아니다 ({value!r})")
    return int(value)


def to_float(row, column, where):
    value = row[column]
    if value == "":
        return None
    try:
        return float(value)
    except ValueError:
        raise ValueError(f"{where}: {column} 값이 숫자가 아니다 ({value!r})")
