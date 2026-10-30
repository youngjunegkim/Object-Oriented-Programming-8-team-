"""Data/의 가공 완료 CSV를 읽어 파이썬 자료형(딕셔너리·리스트)으로 돌려준다.

- 하는 일: CSV 읽기 → 필수 열·중복 검증 → 자료형 변환. 원본 xlsx 가공이나 혼잡도 생성은 하지 않는다(collect/ 담당).
- Station·Edge 객체는 만들지 않는다. 객체 조립은 SubwayGraph.build()가 한다.
- 역코드는 문자열 그대로 둔다("0222"의 앞자리 0 보존). 빈칸 거리·혼잡도는 None.
- 혼잡도 파일은 기본(Data/Congestion)과 실험(Data/Congestion_II) 중 하나를 생성자에서 고른다.

사용 예:
    loader = CongestionDataLoader()                      # 실험판: CongestionDataLoader(congestion_path=CONGESTION_II_CSV)
    loader.load_distance()["2호선"][0]                    # {"from_name": "시청", "to_name": "충정로", "seconds": 90, ...}
    loader.load_congestion()[("2호선", "0222", "0221")]["평일"]["values"]["08:00"]  # 46.1 (강남→역삼)
    loader.load_transfers()[("0340", "2818")]            # 가락시장 3호선→8호선 방향별 환승 4가지
"""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "Data"
CONGESTION_CSV = DATA / "Congestion" / "congestion.csv"
CONGESTION_II_CSV = DATA / "Congestion_II" / "congestion.csv"

DAYS = ["평일", "토요일", "일요일"]
SLOTS = [f"{h % 24:02d}:{m:02d}" for h in range(5, 25) for m in (0, 30)][1:]  # 05:30 ~ 00:30, 39칸
SOURCES = {"measured", "measured-9", "generated"}

STATION_COLUMNS = ["station_code", "station_no", "name", "line", "api_line", "branch"]
EDGE_COLUMNS = ["line", "branch", "from_code", "from_name", "to_code", "to_name", "seconds", "meters", "note"]
TRANSFER_COLUMNS = [
    "from_code", "from_name", "from_line", "from_prev_code", "from_prev_name", "from_dir",
    "to_code", "to_name", "to_line", "to_next_code", "to_next_name", "to_dir",
    "seconds", "meters", "note",
]
CONGESTION_COLUMNS = ["line", "branch", "from_code", "from_name", "to_code", "to_name", "day", "source", *SLOTS]


class CongestionDataLoader:
    """CSV 4종을 읽는 로더. 메서드마다 파일을 새로 읽으며, 반환값은 호출한 쪽이 자유롭게 써도 된다."""

    def __init__(self, data_dir=DATA, congestion_path=CONGESTION_CSV):
        data_dir = Path(data_dir)
        self.stations_path = data_dir / "Station" / "stations.csv"
        self.edges_path = data_dir / "Edge" / "edges.csv"
        self.transfers_path = data_dir / "Transfer" / "transfers.csv"
        self.congestion_path = Path(congestion_path)

    def load_stations(self):
        """역 목록. [{station_code, station_no, name, line, api_line, branch}, ...]

        한 행 = 한 노선의 역. 서울역은 1호선·4호선·경의중앙선·공항철도에 하나씩 4행이다.
        station_no(노선도 역번호)는 "P170" 같은 값도 있어 문자열이며, 빈칸이면 None.
        branch는 여러 지선이면 "경부선/경인선"처럼 '/'로 이어진 원문 그대로.
        """
        rows = self._read(self.stations_path, STATION_COLUMNS)
        self._check_unique(self.stations_path, rows, ("station_code",))
        return [
            {
                "station_code": r["station_code"],
                "station_no": r["station_no"] or None,
                "name": r["name"],
                "line": r["line"],
                "api_line": r["api_line"],
                "branch": r["branch"],
            }
            for _, r in rows
        ]

    def load_distance(self):
        """호선별 탑승 구간을 역 순서대로. {호선: [구간, ...]}

        구간 = {line, branch, from_code, from_name, to_code, to_name, seconds, meters, note}
        - seconds: int(열차 소요시간, 초). meters: int 또는 None(API가 거리를 주지 않은 구간).
        - note: 보정한 값이면 "fix:..." 아니면 None.
        - 방향이 있다. A→B와 B→A가 각각 한 구간이다(6호선 응암순환만 한 방향).
        순서: 지선별로 한쪽 끝에서 반대쪽 끝까지 가는 방향을 먼저, 이어서 되돌아오는 방향.
              순환선은 한 바퀴씩. 예) 1호선 = 본선 연천→…→구로, 구로→…→연천, 경부선 …
        """
        rows = self._read(self.edges_path, EDGE_COLUMNS)
        self._check_unique(self.edges_path, rows, ("line", "branch", "from_code", "to_code"))
        by_branch = {}  # (호선, 지선) → 구간들. 파일에 처음 나온 순서 유지
        for n, r in rows:
            by_branch.setdefault((r["line"], r["branch"]), []).append({
                "line": r["line"],
                "branch": r["branch"],
                "from_code": r["from_code"],
                "from_name": r["from_name"],
                "to_code": r["to_code"],
                "to_name": r["to_name"],
                "seconds": self._to_int(self.edges_path, n, "seconds", r["seconds"]),
                "meters": self._to_int(self.edges_path, n, "meters", r["meters"], optional=True),
                "note": r["note"] or None,
            })
        distance = {}
        for (line, _), edges in by_branch.items():
            distance.setdefault(line, []).extend(self._in_station_order(edges))
        return distance

    def load_transfers(self):
        """환승역별 호선 간 환승 소요시간. {(내리는 역 코드, 타는 역 코드): [방향별 환승, ...]}

        키의 두 코드는 같은 역의 서로 다른 노선 정점이다. 예) ("0340", "2818") = 가락시장 3호선 → 8호선.
        같은 역·노선 쌍이라도 어느 방향에서 와서 어느 방향으로 타느냐에 따라 시간이 달라 목록으로 둔다.
        방향별 환승 = {from_code, from_name, from_line, from_prev_code, from_prev_name, from_dir,
                       to_code, to_name, to_line, to_next_code, to_next_name, to_dir, seconds, meters, note}
        - from_prev_code: 내리기 직전에 지나온 역(= 타고 온 방향). to_next_code: 갈아탄 뒤 다음 역(= 탈 방향).
        - seconds: int(걷는 시간, 초, 열차 대기 제외). meters: int 또는 None. from_dir·to_dir·note: 문자열 또는 None.
        """
        rows = self._read(self.transfers_path, TRANSFER_COLUMNS)
        self._check_unique(self.transfers_path, rows, ("from_code", "from_prev_code", "to_code", "to_next_code"))
        transfers = {}
        for n, r in rows:
            transfers.setdefault((r["from_code"], r["to_code"]), []).append({
                "from_code": r["from_code"],
                "from_name": r["from_name"],
                "from_line": r["from_line"],
                "from_prev_code": r["from_prev_code"],
                "from_prev_name": r["from_prev_name"],
                "from_dir": r["from_dir"] or None,
                "to_code": r["to_code"],
                "to_name": r["to_name"],
                "to_line": r["to_line"],
                "to_next_code": r["to_next_code"],
                "to_next_name": r["to_next_name"],
                "to_dir": r["to_dir"] or None,
                "seconds": self._to_int(self.transfers_path, n, "seconds", r["seconds"]),
                "meters": self._to_int(self.transfers_path, n, "meters", r["meters"], optional=True),
                "note": r["note"] or None,
            })
        return transfers

    def load_congestion(self):
        """호선, 역 코드, 방향에 따른 시간별 혼잡도. {(호선, 출발역 코드, 도착역 코드): {요일: {...}}}

        도착역 코드가 방향이다. 키의 세 값은 load_distance() 구간의 line, from_code, to_code와 같다.
        {
            ("2호선", "0222", "0221"): {        # 강남 → 역삼
                "평일": {"source": "measured", "values": {"05:30": 22.2, ...,"08:00": 46.1, ..., "00:30": None}},
                "토요일": {...},
                "일요일": {...},
            },
        }
        - source: "measured"(1~8호선 실측), "measured-9"(9호선 실측), "generated"(생성값)
        - values: 30분 칸 39개(SLOTS). "08:00"은 08:00~08:30, "00:00"·"00:30"은 그 영업일의 자정 이후.
          float(%) 또는 None(운행 없음). 100%를 넘을 수 있다.
        """
        rows = self._read(self.congestion_path, CONGESTION_COLUMNS)
        self._check_unique(self.congestion_path, rows, ("line", "from_code", "to_code", "day"))
        congestion = {}
        for n, r in rows:
            if r["day"] not in DAYS:
                raise ValueError(f"{self.congestion_path}:{n}: 알 수 없는 요일 {r['day']!r}")
            if r["source"] not in SOURCES:
                raise ValueError(f"{self.congestion_path}:{n}: 알 수 없는 source {r['source']!r}")
            congestion.setdefault((r["line"], r["from_code"], r["to_code"]), {})[r["day"]] = {
                "source": r["source"],
                "values": {slot: self._to_float(self.congestion_path, n, slot, r[slot]) for slot in SLOTS},
            }
        for key, days in congestion.items():
            missing = [day for day in DAYS if day not in days]
            if missing:
                raise ValueError(f"{self.congestion_path}: 구간 {key}에 요일 {missing} 행이 없음")
        return congestion

    @staticmethod
    def _in_station_order(edges):
        """한 지선의 구간들을 역을 따라 이어지는 순서로 정렬한다.

        끝역(이웃이 하나뿐인 역)에서 출발해 왔던 역으로 되돌아가지 않고 갈 수 있는 데까지 따라간다.
        남은 구간(반대 방향)이 있으면 멈춘 역에서 다시 따라간다. 끝역이 없는 순환선은 첫 구간의 출발역에서 시작.
        """
        out = {}  # 역 코드 → 그 역에서 출발하는 구간들
        neighbors = {}
        for e in edges:
            out.setdefault(e["from_code"], []).append(e)
            neighbors.setdefault(e["from_code"], set()).add(e["to_code"])
            neighbors.setdefault(e["to_code"], set()).add(e["from_code"])
        ends = [e["from_code"] for e in edges if len(neighbors[e["from_code"]]) == 1]
        current = ends[0] if ends else edges[0]["from_code"]

        ordered, used = [], set()
        while len(ordered) < len(edges):
            if not any(id(e) not in used for e in out.get(current, [])):
                current = next(e["from_code"] for e in edges if id(e) not in used)
            previous = None
            while True:
                nxt = next((e for e in out.get(current, [])
                            if id(e) not in used and e["to_code"] != previous), None)
                if nxt is None:
                    break
                ordered.append(nxt)
                used.add(id(nxt))
                previous, current = current, nxt["to_code"]
        return ordered

    @staticmethod
    def _read(path, columns):
        """[(줄번호, 행 딕셔너리), ...]. 필수 열이 없으면 ValueError. 줄번호는 오류 메시지용(헤더 = 1줄)."""
        with open(path, encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            missing = [c for c in columns if c not in (reader.fieldnames or [])]
            if missing:
                raise ValueError(f"{path}: 필수 열 없음 {missing}")
            return list(enumerate(reader, start=2))

    @staticmethod
    def _check_unique(path, rows, key_columns):
        seen = {}
        for n, r in rows:
            key = tuple(r[c] for c in key_columns)
            if key in seen:
                raise ValueError(f"{path}:{n}: {key_columns} = {key} 중복 ({seen[key]}줄과 같음)")
            seen[key] = n

    @staticmethod
    def _to_int(path, line_no, column, text, optional=False):
        if text == "" and optional:
            return None
        try:
            return int(text)
        except ValueError:
            raise ValueError(f"{path}:{line_no}: {column} 값 {text!r}은 정수가 아님") from None

    @staticmethod
    def _to_float(path, line_no, column, text):
        if text == "":
            return None
        try:
            return float(text)
        except ValueError:
            raise ValueError(f"{path}:{line_no}: {column} 값 {text!r}은 숫자가 아님") from None
