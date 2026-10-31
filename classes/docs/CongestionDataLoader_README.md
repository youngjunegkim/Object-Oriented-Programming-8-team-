# CongestionDataLoader

`Data/`에 있는 가공 완료 CSV 4종을 읽어 파이썬 딕셔너리·리스트로 돌려주는 클래스.
코드: [`data_loader.py`](../data_loader.py)

| 메서드 | 읽는 파일 | 돌려주는 것 |
|---|---|---|
| `load_distance()` | `Data/Edge/edges.csv` | 호선별로 (역명, 소요시간, 거리) |
| `load_congestion()` | `Data/Congestion/congestion.csv` | 호선, 역 코드, 방향에 따른 시간별 혼잡도 |
| `load_transfers()` | `Data/Transfer/transfers.csv` | 환승역별 호선 간 환승 소요시간 (방향별) |
| `load_stations()` | `Data/Station/stations.csv` | 역 목록 |

---

## 하는 일 / 하지 않는 일

**하는 일**: CSV 읽기 → 필수 열·중복 검사 → 자료형 변환(숫자, 빈칸 → `None`)

**하지 않는 일**
- 원본 xlsx 가공, 혼잡도 생성 → `collect/` 코드가 이미 해서 CSV로 만들어 두었다
- `Station`, `Vertex`, `Edge` 객체 생성 → `SubwayGraph.build()`가 로더 결과를 받아 만든다
- 혼잡도 조회·시간대 계산 → `RideEdge`가 한다

로더는 "파일 → 파이썬 자료"까지만 책임진다. 그래서 CSV 형식이 바뀌어도 로더만 고치면 된다.

---

## 사용법

```python
from classes import CongestionDataLoader

loader = CongestionDataLoader()

distance   = loader.load_distance()
congestion = loader.load_congestion()
transfers  = loader.load_transfers()
stations   = loader.load_stations()
```

### 혼잡도 파일 고르기

기본판과 실험판(`Congestion_II`, 역별 승하차 인원 차이를 더 반영한 생성값)은 둘 중 하나만 쓴다.

```python
from classes.data_loader import CONGESTION_II_CSV

loader = CongestionDataLoader(congestion_path=CONGESTION_II_CSV)  # 실험판
```

실측값은 두 파일이 같고 생성값만 다르다. 다른 데이터 폴더를 쓰려면 `CongestionDataLoader(data_dir="경로")`.

---

## 공통 규칙

- **역 코드는 문자열이다.** `"0222"`의 앞자리 0을 지키려고 숫자로 바꾸지 않는다.
  역 코드는 노선마다 다르다. 서울역 1호선 `"0150"`, 4호선은 다른 코드.
- **역 코드(`station_code`)와 노선도 역번호(`station_no`)는 다르다.** 다른 CSV는 모두 역 코드로 역을 가리킨다.
- **같은 이름 ≠ 같은 역.** 양평(5호선, 서울 영등포구)과 양평(경의중앙선, 경기도 양평군)은 다른 역이다. 역은 이름이 아니라 코드로 찾는다.
- **시간은 초, 거리는 미터, 혼잡도는 %.** 혼잡도는 100을 넘을 수 있다(최대 169.9).
- **빈칸은 `None`.** 거리를 모르는 구간, 운행이 없는 시간대가 해당한다. 계산 전에 `None`인지 확인해야 한다.
- 반환값은 매번 파일을 새로 읽어 만든 것이라 받은 쪽에서 고쳐도 된다.

---

## load_distance()

호선별 탑승 구간을 돌려준다. 23개 호선, 구간 1,516개.

```python
distance = loader.load_distance()   # {호선: [구간, ...]}

distance["2호선"][0]
# {'line': '2호선', 'branch': '순환선',
#  'from_code': '0201', 'from_name': '시청',
#  'to_code': '0243', 'to_name': '충정로',
#  'seconds': 90, 'meters': 1100, 'note': None}
```

| 키 | 자료형 | 뜻 |
|---|---|---|
| `line`, `branch` | str | 노선, 지선 (본선, 경부선, 성수지선 등) |
| `from_code`, `from_name` | str | 출발역 코드, 이름 |
| `to_code`, `to_name` | str | 도착역 코드, 이름 |
| `seconds` | int | 열차 소요시간 (초) |
| `meters` | int 또는 None | 거리 (미터). 16개 구간은 None |
| `note` | str 또는 None | 보정한 값이면 `"fix:..."` |

**방향이 있다.** A→B와 B→A가 각각 한 구간이다. 6호선 응암순환만 한 방향으로 운행한다.

**순서**: 호선 안의 구간 순서는 CSV에 적힌 순서 그대로다. 대체로 노선을 따라가지만,
나중에 보정해 추가한 구간 9개(1호선 1개, 5호선 5개, 경의중앙선 3개)는 그 호선 목록의 끝에 붙어 있다.
그래프를 만들거나 경로를 찾을 때는 순서가 상관없으므로 따로 정렬하지 않는다.

전체 구간만 필요하면 이렇게 쓴다.

```python
for line, edges in distance.items():
    for e in edges:
        ...
```

---

## load_congestion()

구간·요일별 30분 단위 혼잡도. 구간 1,516개 × 요일 3개.

```python
congestion = loader.load_congestion()   # {(호선, 출발역 코드, 도착역 코드): {요일: {...}}}

day = congestion[("2호선", "0222", "0221")]["평일"]   # 강남 → 역삼, 평일
day["source"]            # 'measured'
day["values"]["08:00"]   # 46.1
day["values"]["08:30"]   # 42.9
```

```python
{
    ("2호선", "0222", "0221"): {
        "평일":   {"source": "measured", "values": {"05:30": 22.2, ..., "08:00": 46.1, ..., "00:30": ...}},
        "토요일": {"source": ..., "values": {...}},
        "일요일": {"source": ..., "values": {...}},
    },
    ...
}
```

- **키**: `(호선, 출발역 코드, 도착역 코드)`. 도착역 코드가 방향이다.
  `load_distance()` 구간의 `line`, `from_code`, `to_code`와 같아서 바로 연결된다.
  ```python
  congestion[(e["line"], e["from_code"], e["to_code"])]
  ```
- **요일**: `"평일"`, `"토요일"`, `"일요일"` (상수 `DAYS`)
- **시간대**: `"05:30"` ~ `"00:30"` 39칸 (상수 `SLOTS`)
  - `"08:00"`은 08:00~08:30 칸
  - `"00:00"`, `"00:30"`은 그날 영업일의 자정 이후
- **값**: float(%) 또는 None(운행 없음)
- **source**
  - `"measured"`: 1~8호선 서울교통공사 실측
  - `"measured-9"`: 9호선 실측
  - `"generated"`: 실측 평균으로 만든 생성값

실측 617개 구간, 생성 899개 구간. 화면에서 실측/추정을 구분해 보여줄 때 `source`를 쓴다.

```python
from classes.data_loader import DAYS, SLOTS   # 시간대 계산에서 칸 목록이 필요하면 가져다 쓴다
```

---

## load_transfers()

같은 역에서 노선을 갈아타는 데 걸리는 시간. 역 코드 쌍 310개, 방향별 환승 1,110개.

```python
transfers = loader.load_transfers()   # {(내리는 역 코드, 타는 역 코드): [방향별 환승, ...]}

transfers[("0340", "2818")]   # 가락시장 3호선 → 8호선
# [{'from_prev_code': '0339', 'from_prev_name': '수서',     'to_next_code': '2817', 'to_next_name': '송파', 'seconds': 122, ...},
#  {'from_prev_code': '0339', 'from_prev_name': '수서',     'to_next_code': '2819', 'to_next_name': '문정', 'seconds': 112, ...},
#  {'from_prev_code': '0341', 'from_prev_name': '경찰병원', 'to_next_code': '2817', 'to_next_name': '송파', 'seconds': 122, ...},
#  {'from_prev_code': '0341', 'from_prev_name': '경찰병원', 'to_next_code': '2819', 'to_next_name': '문정', 'seconds': 112, ...}]
```

한 항목 = "**from_prev**에서 오는 A호선을 타고 **from**에서 내려, B호선 **to_next** 방향 열차를 **to**에서 탄다".

| 키 | 자료형 | 뜻 |
|---|---|---|
| `from_code`, `from_name`, `from_line` | str | 내리는 역 (A호선) |
| `from_prev_code`, `from_prev_name` | str | A호선에서 직전에 지나온 역 = 타고 온 방향 |
| `from_dir` | str 또는 None | A호선 방향 표기 (상행/하행/내선/외선, 참고용) |
| `to_code`, `to_name`, `to_line` | str | 타는 역 (B호선) |
| `to_next_code`, `to_next_name` | str | B호선에서 다음에 갈 역 = 탈 방향 |
| `to_dir` | str 또는 None | B호선 방향 표기 (참고용) |
| `seconds` | int | 환승 걷는 시간 (초). 열차 대기시간은 포함하지 않음 |
| `meters` | int 또는 None | 환승 거리 (미터) |
| `note` | str 또는 None | 보정한 값이면 `"fix:..."` |

**같은 역·같은 노선 쌍이라도 방향에 따라 시간이 다르다** (예: 교대 2→3호선 57~158초).
그래서 목록으로 두었고, 경로 탐색에서는 실제로 지나온 역과 다음 역으로 맞는 항목을 골라야 한다.

```python
def transfer_seconds(transfers, prev_code, from_code, to_code, next_code):
    for t in transfers.get((from_code, to_code), []):
        if t["from_prev_code"] == prev_code and t["to_next_code"] == next_code:
            return t["seconds"]
    return None   # 그런 환승 없음
```

키를 역 이름이 아니라 역 코드 쌍으로 둔 이유: 이름으로 묶으면 두 방향으로 틀릴 수 있다.

| 경우 | 예 | 이름으로 묶으면 |
|---|---|---|
| 이름은 같은데 다른 역 | 양평 5호선(`2523`, 서울 영등포구) / 양평 경의중앙선(`1217`, 경기도 양평군) | 수십 km 떨어진 두 역 사이에 없는 환승이 생긴다 |
| 이름은 다른데 같은 역 | 총신대입구 4호선(`0432`) / 이수 7호선(`2738`) | 다른 역으로 보여서 실제로 되는 환승이 빠진다 |

```python
transfers[("2738", "0432")]       # 이수 → 총신대입구 환승 목록
transfers.get(("2523", "1217"))   # None (환승 아님)
```

환승 가능 여부는 이름으로 추측하지 않고 이 CSV에 적힌 코드 쌍을 기준으로 한다.

---

## load_stations()

역 목록. 한 행 = 한 노선의 역. 782개.

```python
stations = loader.load_stations()   # [역, ...]

stations[0]
# {'station_code': '0150', 'station_no': '133', 'name': '서울역',
#  'line': '1호선', 'api_line': '1호선', 'branch': '본선'}
```

| 키 | 자료형 | 뜻 |
|---|---|---|
| `station_code` | str | 역 코드. 다른 CSV가 모두 이 코드로 역을 가리킨다 |
| `station_no` | str 또는 None | 노선도 역번호. `"P170"` 같은 값도 있어 문자열. 3개 역은 None |
| `name` | str | 역 이름 |
| `line` | str | 노선명 (예: 경의중앙선) |
| `api_line` | str | API의 노선명 (예: 경의선) |
| `branch` | str | 지선. 여러 개면 `"경부선/경인선/본선"`처럼 `/`로 이어짐 |

서울역은 1호선·4호선·경의중앙선·공항철도에 하나씩 4행이다.
보고서 표에는 없는 메서드지만 역 목록을 만들려면 필요해서 넣었다.

---

## 오류

데이터에 문제가 있으면 읽는 순간 `ValueError`를 낸다. 메시지에 파일과 줄 번호가 나온다.

| 검사 | 메시지 예 |
|---|---|
| 필수 열이 없음 | `edges.csv: 필요한 열이 없다 ['seconds']` |
| 같은 키가 두 번 | `edges.csv:4: 2번째 줄과 겹친다 {'line': '1호선', 'branch': '본선', 'from_code': '1919', 'to_code': '1918'}` |
| 숫자가 아닌 값 | `edges.csv:3: 'seconds' 칸의 값 'abc'을 읽을 수 없다 (정수여야 한다)` |
| 알 수 없는 요일·source | `congestion.csv:2: 'day' 칸의 값 '공휴일'을 읽을 수 없다 (['평일', '토요일', '일요일'] 중 하나여야 한다)` |
| 구간에 요일 행이 빠짐 | `congestion.csv: ('2호선', '0222', '0221') 구간에 ['일요일'] 줄이 없다` |

중복 검사 키:
- 역: `station_code`
- 구간: `(line, branch, from_code, to_code)`
- 환승: `(from_code, from_prev_code, to_code, to_next_code)`
- 혼잡도: `(line, from_code, to_code, day)`

---

## 다른 클래스와의 관계

```
CSV ──▶ CongestionDataLoader ──▶ SubwayGraph.build(loader)
                                   ├─ Station / Vertex   ← load_stations()
                                   ├─ RideEdge           ← load_distance() + load_congestion()
                                   └─ TransferEdge       ← load_transfers()
```

로더는 객체를 모르고, 객체는 CSV를 모른다. 둘 사이는 위의 딕셔너리 형식으로만 주고받는다.
`SubwayGraph`는 로더를 안에서 만들지 말고 밖에서 받도록 만들면 된다.

```python
class SubwayGraph:
    def build(self, loader):
        stations = loader.load_stations()
        ...

graph.build(CongestionDataLoader())                                   # 기본 혼잡도
graph.build(CongestionDataLoader(congestion_path=CONGESTION_II_CSV))  # 실험판
```

---

## SOLID 적용

| 원칙 | 적용한 곳 |
|---|---|
| **S** 단일 책임 | 로더는 "CSV → 파이썬 자료"만 한다. 엑셀 가공(`collect/`), 객체 생성(`SubwayGraph`), 혼잡도 조회(`RideEdge`)는 다른 클래스 몫이다. 로더 안에서도 CSV 공통 처리(`_read_table`)를 클래스 밖 함수로 떼어 메서드는 "어떤 파일을 어떤 모양으로"만 담는다. |
| **O** 개방-폐쇄 | 파일마다 "열 이름: 변환 규칙" 표(`EDGE_COLUMNS` 등)를 두었다. 열이 바뀌면 표만 고치고 메서드는 그대로 둔다. 혼잡도 파일·데이터 폴더는 생성자 인자라 코드 수정 없이 바꾼다. |
| **L** 리스코프 치환 | 로더는 상속을 쓰지 않아 해당하지 않는다. 이 원칙은 `Edge` → `RideEdge`·`TransferEdge`에서 지킨다. |
| **I** 인터페이스 분리 | 메서드를 데이터 종류별로 나눠 필요한 것만 부른다. 혼잡도만 필요한 쪽은 `load_congestion()`만 쓰면 된다. `RideEdge`·`TransferEdge`는 로더를 아예 몰라도 된다. |
| **D** 의존 역전 | 로더는 객체가 아닌 기본 자료형(dict, list)을 돌려주므로, 그래프·간선 클래스가 CSV 파일 경로나 열 이름에 묶이지 않는다. `SubwayGraph`가 로더를 밖에서 받으면 기본판·실험판을 코드 수정 없이 바꿔 끼울 수 있다. |

클래스를 억지로 늘리지 않았다. 클래스는 `CongestionDataLoader` 하나이고, 나머지 도우미는 함수로 두었다.
