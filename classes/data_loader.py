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
from pathlib import Path #pathlib내 Path 모듈 불러움 -> pathlib쓰지 않고 Path모듈 사용 가능
#__file__: 현재 파이썬 파일인 data_loader.py 경로, Path(__file__): 파일 경로를 다루기 위한 Path 객체로 변환
#resolve(): 절대 경로로 변환하고 경로를 정리 .parent: 상위 폴더 접근 .parent: 파일 들어있는 classes 폴더, classes의 상위인 프로젝트 폴더(OOP)
ROOT = Path(__file__).resolve().parent.parent # -> ROOT == OOP 폴더
DATA = ROOT / "Data" # /는 경로를 연결하는 연산자., OOP폴더 내의 Data 폴더
CONGESTION_CSV = DATA / "Congestion" / "congestion.csv"
CONGESTION_II_CSV = DATA / "Congestion_II" / "congestion.csv"

# ["05:30", ... ,"00:30"] 39개, [1:] 슬라이싱 05:00 제외를 위해 사용 , :02d -> 정수 두자리로 표시, 빈 자리 0
DAYS = ["평일", "토요일", "일요일"]
SLOTS = [f"{h % 24:02d}:{m:02d}" for h in range(5, 25) for m in (0, 30)][1:]
SOURCES = {"measured", "measured-9", "generated"} #집합

# *SLOTS: 여러개의 혼잡도 수치 데이터 하나의 튜플로 받음, 파일별 열 제목들
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

    def __init__(self, data_dir=DATA, congestion_path=CONGESTION_CSV): #디폴트값 지정
        data_dir = Path(data_dir) #경로를 객체로 반환, 경로를 나타내는 Path객체
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
        self._check_unique(self.stations_path, rows, ("station_code",)) #key_columns는 튜플, station_code 값만 기준으로 중복을 검사
        return [
            {
                "station_code": r["station_code"],
                "station_no": r["station_no"] or None, #역 번호 없으면 None 대입 (csv에선 <null>)
                "name": r["name"],
                "line": r["line"],
                "api_line": r["api_line"],
                "branch": r["branch"],
            }
            for _, r in rows
        ] #리스트 반환, 리스트 컴프리헨션(리스트 안에 for 문)

    #edges
    #지선(branch)은 같은 호선(line) 안에서 갈라지는 경로를 구분하는 것
    def load_distance(self):
        """호선별 탑승 구간을 역 순서대로. {호선: [구간, ...]}

        구간 = {line, branch, from_code, from_name, to_code, to_name, seconds, meters, note}
        - seconds: int(열차 소요시간, 초). meters: int 또는 None(API가 거리를 주지 않은 구간).
        - note: 보정한 값이면 "fix:..." 아니면 None.
        - 방향이 있다. A→B와 B→A가 각각 한 구간이다(6호선 응암순환만 한 방향).
        순서: 지선별로 한쪽 끝에서 반대쪽 끝까지 가는 방향을 먼저, 이어서 되돌아오는 방향.
              순환선은 한 바퀴씩. 예) 1호선 = 본선 연천→…→구로, 구로→…→연천, 경부선 …
        """
        rows = self._read(self.edges_path, EDGE_COLUMNS) #edges.csv파일 경로와 파일 내 열 이름 전달
        self._check_unique(self.edges_path, rows, ("line", "branch", "from_code", "to_code"))
        by_branch = {}  # (호선, 지선) → 구간들. 파일에 처음 나온 순서 유지, 딕셔너리
        for n, r in rows:
            # by_branch딕셔너리에 (r["line"], r["branch"])에 해당하는 키가 없으면 키 넣고 값으로 [](리스트 넣는다), 그리고 그 키에 대한 값(리스트)을 아래 내용 삽입
            # setdefault는 key에 해당하는 value반환, line과 branch 같으면 데이터 여러개 가능
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
        return transfers #딕셔너리 반환

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
    def _in_station_order(edges): #line과 branch가 일치하는 데이터(리스트 안에 여러 딕셔너리) 들어옴
        """한 지선의 구간들을 역을 따라 이어지는 순서로 정렬한다.

        끝역(이웃이 하나뿐인 역)에서 출발해 왔던 역으로 되돌아가지 않고 갈 수 있는 데까지 따라간다.
        남은 구간(반대 방향)이 있으면 멈춘 역에서 다시 따라간다. 끝역이 없는 순환선은 첫 구간의 출발역에서 시작.
        """
        #out에는 특정역의 이웃한 역들의 데이터가 들어가고 neighbors는 특정 역과 직접 연결된 이웃 역의 코드의 집합
        out = {}  # 역 코드 → 그 역에서 갈 수 있는 구간들
        neighbors = {}
        for e in edges: #e: line과 branch가 같은 구간 하나를 나타내는 딕셔너리
            out.setdefault(e["from_code"], []).append(e)
            # neighbors는 직접 연결된 이웃하는 역이 갈 수 있는 경로를 키에 대한 값으로 나타냄
            # ex) neighbors = { "A": {"B"}, "B": {"A", "C"}, "C": {"B"} }
            neighbors.setdefault(e["from_code"], set()).add(e["to_code"]) # 출발역 코드 키에 도착역 코드 value(집합)에 넣음, 출발역 코드에서 이어진 여러 도착역 코드
            neighbors.setdefault(e["to_code"], set()).add(e["from_code"]) # 도착역 코드 키에 출발역 코드 value(집합)에 넣음, 도착역에서 출발역으로 가는 경로
        ends = [e["from_code"] for e in edges if len(neighbors[e["from_code"]]) == 1] #직접 연결된 이웃 역이 하나뿐인 역의 코드가 ends에 들어감
        # current에는 ends에 원소가 있으면 첫 번째 원소 값이 들어가고 없으면 edges의 첫번 째 원소의 from_code에 대한 값 들어감
        # 끝역이 있으면 끝역부터, 순환선처럼 끝역이 없으면 첫 구간의 출발역부터 탐색을 시작
        current = ends[0] if ends else edges[0]["from_code"]

        #현재 역에서 출발하는 구간을 하나씩 따라가면서 edges를 연결 순서대로 정리하는 코드
        ordered, used = [], set()
        while len(ordered) < len(edges): # edges에 있는 모든 구간을 넣을 때 까지 반복
            # 현재 역에서 갈 수 있는 구간 중 미사용 구간이 있는지 확인
            # e에는 current값에 해당하는 역의 직접 이웃한 역 데이터(딕셔너리) 들어감. id(e)는 딕셔너리 객체를 구별하는 식별값, 구간 하나를 사용했는지 확인
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

    #_read는 csv데이터 읽어서 번호와 데이터를 리스트 내 튜플 형태로 전달.
    #csv파일 경로와 파일 내 열 이름 전달받음
    #edges.csv를 읽으면 첫 줄의 열 이름이 키, 각 행에서 해당 열에 들어 있는 내용이 값
    #csv.DictReader: CSV의 각 행을 딕셔너리로 읽어 주는 기능
    #reader.fieldnames: 실제 CSV 첫 줄에 있는 열 이름들
    #missing: columns에 저장되어 있는 열 이름이 csv파일 내 열 이름 목록에 없으면 missing 리스트에 저장
    #enumerate(): 반복해서 꺼내는 값에 번호를 붙여 주는 함수, 튜플(번호, 데이터), start=2 -> 번호 2부터 시작, list() -> 리스트내 튜플 형태
    @staticmethod
    def _read(path, columns):
        """[(줄번호, 행 딕셔너리), ...]. 필수 열이 없으면 ValueError. 줄번호는 오류 메시지용(헤더 = 1줄)."""
        with open(path, encoding="utf-8-sig", newline="") as f: #줄바꿈 그래로 사용
            reader = csv.DictReader(f)
            missing = [c for c in columns if c not in (reader.fieldnames or [])]
            if missing:
                raise ValueError(f"{path}: 필수 열 없음 {missing}")
            return list(enumerate(reader, start=2))

    #_check_unique: 중복 검사하는 메소드
    #경로, 검수한(_read) 데이터 리스트 ,
    #key_columns는 어떤 열을 기준으로 중복을 검사할지 지정하기 위해 받는 매개변수
    @staticmethod
    def _check_unique(path, rows, key_columns):
        seen = {} # 딕셔너리
        for n, r in rows:
            key = tuple(r[c] for c in key_columns) #
            if key in seen: #4가지 기준으로 중복을 검사한다고 했을 때 지정한 4개 열의 값이 모두 일치해야 중복으로 판단
                raise ValueError(f"{path}:{n}: {key_columns} = {key} 중복 ({seen[key]}줄과 같음)")
            seen[key] = n
    # 정수 형태의 문자열 데이터 정수값으로 바꾸는 문장
    @staticmethod
    def _to_int(path, line_no, column, text, optional=False): # 경로, 데이터 번호, 열 이름, 정수로 바꿀 데이터
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
