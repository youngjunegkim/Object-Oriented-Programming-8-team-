# 클래스 구현 및 인수인계

데이터 읽기, 도메인 객체, 그래프·탐색, 화면의 책임별로 코드를 배치했다. 폴더 분리 자체가 SOLID를 보장하는 것은 아니며, 아래 책임과 교체 가능한 호출 계약을 유지한다.

## 폴더 구조

```text
classes/
├─ loaders/data_loader.py       # CSV 읽기·검증
├─ models/                     # 역·정점·구간·경로 결과
│  ├─ station.py
│  ├─ vertex.py
│  ├─ edge.py
│  └─ route.py
├─ routing/                    # 그래프 구성과 경로 탐색
│  ├─ subway_graph.py
│  └─ route_finder.py
├─ views/                      # 프론트 담당 영역 (.gitkeep으로 빈 폴더 유지)
└─ service_time.py             # 로더와 Route가 공유하는 시간 규칙

```

화면 구현은 프론트 담당자가 맡는다. 화면은 입력·표시를 담당하고 그래프·경로 객체에 계산을 요청한다. 별도 웹 프론트라면 Python views 파일 대신 API 연결이 필요할 수 있다.

## 빠른 시작과 import 변경

프로젝트 루트에서 Python으로 실행한다. 경로 탐색에는 표준 라이브러리를 사용한다.

```python
from classes.routing.subway_graph import SubwayGraph
from classes.routing.route_finder import transfers_first

graph = SubwayGraph()
graph.build()  # 화면 시작 시 한 번 구성 후 재사용
route = graph.shortest("서울역", "강남", priority=transfers_first)
if route is not None:
    print(route.total_time(), route.transfer_count())
```

Python 3의 네임스페이스 패키지를 사용하므로 `__init__.py` 파일은 두지 않는다. 프로젝트 루트에서 실행하고 아래의 구체적인 모듈 경로로 import한다. `from classes import SubwayGraph` 같은 최상위 클래스 import는 지원하지 않는다. 클래스의 생성자 메서드 `__init__()`는 그대로 유지한다.

| 이전 모듈 | 새 모듈 |
|---|---|
| `classes.data_loader` | `classes.loaders.data_loader` |
| `classes.station`, `classes.vertex`, `classes.edge`, `classes.route` | `classes.models.station`, `classes.models.vertex`, `classes.models.edge`, `classes.models.route` |
| `classes.subway_graph`, `classes.route_finder` | `classes.routing.subway_graph`, `classes.routing.route_finder` |
| `classes.service_time` | 변경 없음 |

CSV 위치는 기존 `Data/`를 유지한다. 이동한 로더는 프로젝트 루트를 `Path(__file__).resolve().parents[2]`로 찾는다. 원본 JSON과 수집 코드는 변경하지 않았다.

## SOLID 적용과 책임

| 원칙 | 코드에서의 적용 |
|---|---|
| S: 단일 책임 | 로더는 읽기·검증, 모델은 데이터·결과 계산, 탐색기는 경로 탐색 담당. 화면 표시를 이 코드에 섞지 않는다. |
| O: 개방·폐쇄 | `priority(edge)` 함수를 전달해 다익스트라 본문 변경 없이 시간·환승 우선 기준을 선택한다. 비용 두 값은 음수가 아니어야 한다. |
| L: 리스코프 치환 | 탑승·환승 간선이 공통 `cost()`와 `next_state()` 계약을 제공한다. 후자는 다음 상태 또는 이동 불가인 `None`을 반환한다. |
| I: 인터페이스 분리 | 혼잡도 조회는 필요한 `RideEdge`에만 있으며, 환승 간선에 구현을 요구하지 않는다. |
| D: 의존성 역전 | `SubwayGraph(loader=..., finder_factory=...)`로 구현을 교체할 수 있다. 추상 클래스 대신 필요한 메서드 계약을 따르는 덕 타이핑을 사용하며, 기본 구현 의존은 남아 있다. |

`models`는 `routing`이나 화면을 import하지 않는다. `service_time`은 CSV와 화면에 의존하지 않는다. 향후 화면은 준비된 그래프를 전달받아 사용한다.

## 상세 문서 목차

- [데이터 로더](#data-loader)
- [Station](#station)
- [Vertex](#vertex)
- [Edge](#edge)
- [경로 탐색·결과·시간 처리](#routing)


<a id="data-loader"></a>
## CongestionDataLoader

**역할: 준비된 CSV를 읽어, 다른 클래스에서 사용할 리스트와 딕셔너리로 바꾼다.**
코드: [data_loader.py](loaders/data_loader.py)

| 메서드 | 읽는 데이터 | 반환 자료형 |
|---|---|---|
| `load_stations()` | 호선별 역 정보 | **리스트** |
| `load_distance()` | 방향별 탑승 구간의 시간·거리 | **딕셔너리** |
| `load_transfers()` | 방향별 환승 시간·거리 | **딕셔너리** |
| `load_congestion()` | 구간·요일·시간대별 혼잡도 | **딕셔너리** |

로딩 메서드는 전체 데이터를 반환한다. 아래 사용 예시는 그 결과에서 **필요한 값 하나만 골라 출력**한다. 반환 자료형과 선택한 값의 자료형은 다를 수 있다.

### 사용 준비

프로젝트 최상위의 실행 파일에서 아래 코드를 작성한다. 이어지는 예시들도 이 코드 다음에 실행한다.

```python
from classes.loaders.data_loader import CongestionDataLoader

loader = CongestionDataLoader()
```

`CongestionDataLoader(...)`가 실행되면 생성자 `__init__()`가 파일 경로를 저장한다. CSV는 각 로딩 메서드를 호출할 때 읽는다.

| 생성자 입력 인자 | 의미 | 생략하면 |
|---|---|---|
| `data_dir` | 역·구간·환승 CSV가 들어 있는 기준 폴더 | 프로젝트의 Data 폴더 사용 |
| `congestion_path` | 사용할 혼잡도 CSV 경로 | Congestion/congestion.csv 사용 |

실험판 Congestion_II를 선택하려면:

```python
from classes.loaders.data_loader import CONGESTION_II_CSV

loader = CongestionDataLoader(congestion_path=CONGESTION_II_CSV)
```

생성 결과는 **로더 객체**다. 두 경로 인자는 독립적이므로 다른 데이터 폴더를 쓸 때는 혼잡도 경로도 지정한다.

### 1. load_stations() — 역 정보 읽기

호선별 역 정보를 리스트로 반환한다. Station·Vertex 객체를 직접 만들지는 않는다.

- **입력 인자:** 없음. Station/stations.csv를 읽는다.
- **반환값: 리스트.** 각 항목은 역코드·역 이름·호선 등을 담은 **딕셔너리**다.

| 접근 방법 | 자료형 | 의미 |
|---|---|---|
| `stations` | 리스트 | 전체 호선별 역 정보 |
| `stations[0]` | 딕셔너리 | 첫 번째 역 정보 |
| `stations[0]["name"]` | 문자열 | 첫 번째 역의 이름 |

**사용 예시: 첫 번째 역의 이름 하나를 조회한다.**

```python
stations = loader.load_stations()
print(stations[0]["name"])
```

**실행 결과: 문자열 하나가 출력된다.**

```text
서울역
```

역 정보의 항목: `station_code`, `station_no`, `name`, `line`, `api_line`, `branch`.
같은 물리적 역이라도 호선이 다르면 별도 항목이다. 실제 역 묶음은 SubwayGraph에서 결정한다.

### 2. load_distance() — 탑승 구간 읽기

출발역→도착역별 소요시간·거리를 호선별로 묶는다. 반대 방향은 별도 구간이다.

- **입력 인자:** 없음. Edge/edges.csv를 읽는다.
- **반환값: 딕셔너리.** 호선 이름이 키이고, 값은 구간 정보 **리스트**다. 각 구간은 **딕셔너리**다.

| 접근 방법 | 자료형 | 의미 |
|---|---|---|
| `distance` | 딕셔너리 | 호선별 탑승 구간 |
| `distance["2호선"]` | 리스트 | 2호선의 구간들 |
| `distance["2호선"][0]` | 딕셔너리 | 2호선의 첫 번째 구간 |

**사용 예시: 2호선 첫 번째 구간의 소요시간 하나를 조회한다.** 현재 데이터의 첫 구간은 시청→충정로다.

```python
distance = loader.load_distance()
section = distance["2호선"][0]
print(section["seconds"])
```

**실행 결과: 정수 하나가 출력되며, 단위는 초다.**

```text
90
```

구간 정보의 항목: `line`, `branch`, `from_code`, `from_name`, `to_code`, `to_name`, `seconds`, `meters`, `note`.
목록은 CSV 순서이며, 화면에 표시할 노선 순서 정렬은 별도로 해야 한다.

### 3. load_transfers() — 환승 구간 읽기

같은 역에서 호선을 바꾸는 정보를 역코드 쌍으로 묶는다. 들어온 방향과 나갈 방향에 따라 다른 환승시간을 보존한다.

- **입력 인자:** 없음. Transfer/transfers.csv를 읽는다.
- **반환값: 딕셔너리.** `(내리는 역코드, 타는 역코드)`가 키이고, 값은 방향별 환승 정보 **리스트**다. 각 환승 정보는 **딕셔너리**다.

| 접근 방법 | 자료형 | 의미 |
|---|---|---|
| `transfers` | 딕셔너리 | 전체 환승 정보 |
| `transfers[("0340", "2818")]` | 리스트 | 가락시장 3호선→8호선의 방향별 환승들 |
| `transfers[("0340", "2818")][0]` | 딕셔너리 | 첫 번째 방향 조합의 환승 정보 |

**사용 예시: 가락시장 3호선→8호선 환승 중, 수서에서 들어와 송파 방향으로 나가는 조건의 시간 하나만 조회한다.**

```python
transfers = loader.load_transfers()
for transfer in transfers[("0340", "2818")]:
    if transfer["from_prev_code"] == "0339" and transfer["to_next_code"] == "2817":
        print(transfer["seconds"])
        break
```

**실행 결과: 정수 하나가 출력되며, 단위는 초다.**

```text
122
```

이 값은 **수서에서 가락시장 3호선에 도착해, 8호선 송파 방향으로 환승할 때 122초**라는 뜻이다.
탐색 코드가 `from_prev_code`와 `to_next_code`를 비교해 실제 방향에 맞는 환승을 선택해야 한다.
그 밖에 출발·도착 역코드·역명·호선, 방향 표기, 시간·거리·보정 메모도 보존한다.

### 4. load_congestion() — 혼잡도 읽기

혼잡도를 방향이 있는 구간→요일→시간대 순서로 찾을 수 있게 정리한다. 추정 공식이나 경로 평균을 계산하는 메서드는 아니다.

- **입력 인자:** 없음. 생성자에서 선택한 혼잡도 CSV를 읽는다.
- **반환값: 딕셔너리.** `(호선, 출발역코드, 도착역코드)`가 키이고, 값은 요일별 **딕셔너리**다.

| 접근 방법 | 자료형 | 의미 |
|---|---|---|
| `congestion` | 딕셔너리 | 전체 구간 혼잡도 |
| `congestion[("2호선", "0222", "0221")]` | 딕셔너리 | 강남→역삼의 요일별 정보 |
| `section["평일"]` | 딕셔너리 | 평일의 출처와 시간대별 혼잡도 |
| `weekday["values"]` | 딕셔너리 | 시간대별 혼잡도 |
| `weekday["values"]["08:00"]` | 실수 또는 None | 해당 시간대 혼잡도, 없으면 None |
| `weekday["source"]` | 문자열 | 실측·생성 출처 |

**사용 예시: 강남→역삼, 평일, 08:00 시간대의 혼잡도 하나만 조회한다.**

```python
congestion = loader.load_congestion()
section = congestion[("2호선", "0222", "0221")]
weekday = section["평일"]
print(weekday["values"]["08:00"])
```

**실행 결과: 실수 하나가 출력되며 단위는 퍼센트이다.**

```text
46.1
```

08:00을 선택했으므로 08:30의 값이나 출처 문자열은 출력하지 않는다. 다른 시간대의 데이터는 반환된 딕셔너리에 그대로 보관된다.

`08:00` 열은 원본의 **08:00~08:30 시간대**를 뜻한다. 평일·토요일·일요일이 각각 있으며, 시간대는 영업일 기준 05:30부터 자정 이후 00:30까지 39개다.
`source`는 measured(1~8호선 실측), measured-9(9호선 실측), generated(생성값) 중 하나다.

### 공통 보조 함수: _read_table(path, columns, unique_by)

**CSV를 읽고, 내용을 검사하고, 값을 문자열에서 알맞은 형태로 변환해 딕셔너리들의 리스트로 반환하는 함수다.**
CongestionDataLoader 클래스 밖에 정의되어 있으며, 네 로딩 메서드가 내부에서 사용한다.

#### 입력 인자

| 입력 인자 | 자료형 | 이 인자로 결정하는 것 |
|---|---|---|
| `path` | 파일 경로 문자열 또는 Path 객체 | 어떤 CSV를 읽을지 |
| `columns` | 딕셔너리 | 어떤 열이 필요하고, 각 값을 어떻게 변환할지 |
| `unique_by` | 열 이름들의 리스트 | 어떤 열의 조합이 같으면 중복으로 볼지 |

예를 들어 `STATION_COLUMNS`는 역 정보의 열 이름과 변환 함수를 연결한 딕셔너리다.
`station_code`에는 문자열을 유지하는 함수를, `station_no`에는 빈칸을 None으로 바꾸는 함수를 지정한다.

#### 처리 순서

1. `path`에 있는 CSV를 연다.
2. `columns`에 지정한 열이 모두 있는지 확인한다.
3. CSV를 한 행씩 읽으며 `unique_by`로 지정한 값의 조합이 중복됐는지 확인한다.
4. 각 열에 지정된 함수를 호출해 값을 변환한다.
5. 변환한 한 행을 딕셔너리로 만들고, 리스트에 차례로 추가한다.
6. 모든 행을 읽으면 완성된 리스트를 반환한다.

변환 예시: 역코드 `"0222"`는 문자열로 유지하고, 시간 `"60"`은 정수 60으로 바꾼다.
혼잡도 `"46.1"`은 실수 46.1로, 빈칸을 허용하는 항목의 빈 문자열은 None으로 바꾼다.

#### 반환값

**바깥 자료형은 리스트이고, 각 항목은 CSV 한 행에 해당하는 딕셔너리다.**
아래는 역 CSV를 읽었을 때 함수가 반환하는 데이터의 첫 번째 항목만 표시한 것이다. 화면에 출력한 결과를 뜻하지는 않는다.

```python
[
    {
        "station_code": "0150",
        "station_no": "133",
        "name": "서울역",
        "line": "1호선",
        "api_line": "1호선",
        "branch": "본선",
    },
]
```

#### 사용 예시

역 CSV를 읽고 변환 규칙을 적용한 뒤, 역코드 중복을 검사한다. 마지막 줄은 반환된 자료에서 첫 번째 역코드 하나만 선택해 출력한다.

```python
from classes.loaders.data_loader import DATA, STATION_COLUMNS, _read_table

rows = _read_table(
    DATA / "Station" / "stations.csv",
    STATION_COLUMNS,
    unique_by=["station_code"],
)
print(rows[0]["station_code"])
```

**실행 결과: 문자열 하나가 출력된다.**

```text
0150
```

#### 각 로딩 메서드와의 차이

`_read_table()`은 데이터를 호선별·구간별로 묶지 않는다. 그 작업은 각 로딩 메서드가 맡는다.

| 함수·메서드 | 담당하는 일 |
|---|---|
| `_read_table()` | 파일 읽기 → 검사 → 값 변환 → 행별 딕셔너리들의 리스트 반환 |
| `load_stations()` | 역 CSV를 읽은 리스트를 그대로 반환 |
| `load_distance()` | 구간 리스트를 호선별 딕셔너리로 묶어 반환 |
| `load_transfers()` | 환승 리스트를 역코드 쌍별 딕셔너리로 묶어 반환 |
| `load_congestion()` | 혼잡도 리스트를 구간·요일별 딕셔너리로 묶고 세 요일이 있는지 검사 |

공통 읽기·검사 코드를 네 번 작성하지 않기 위해 분리한 함수다. 일반 사용 코드는 네 로딩 메서드를 호출하면 된다.
필수 열 누락·중복·값 변환 실패 시 ValueError를 발생시키며, 행 처리 오류에는 파일명과 줄 번호를 표시한다.

### 값 변환 함수

| 함수 | 역할 | 입력 → 반환값 |
|---|---|---|
| `text(value)` | 문자열 유지 | `"0222"` → 문자열 `"0222"` |
| `text_or_none(value)` | 문자열 유지, 빈칸은 None | `""` → None |
| `integer(value)` | 정수로 변환 | `"60"` → 정수 60 |
| `integer_or_none(value)` | 정수로 변환, 빈칸은 None | `"800"` → 정수 800 |
| `number_or_none(value)` | 실수로 변환, 빈칸은 None | `"46.1"` → 실수 46.1 |
| `one_of(allowed)` | 허용된 값인지 확인하는 함수 생성 | 허용 값 목록 → 검사 함수. 그 함수에 `"평일"`을 전달하면 문자열 `"평일"` 반환 |

### 연결할 때 지킬 규칙

- 역코드는 **문자열**, 시간은 **초**, 거리는 **미터**, 혼잡도는 **퍼센트**다.
- 값이 없는 선택 항목은 **None**이다. 혼잡도 0%로 바꾸지 않으며, 100% 초과도 허용한다.
- 각 메서드는 호출할 때마다 CSV를 새로 읽는다. 그래프 생성 시 읽은 결과를 보관해 사용한다.
- 로더는 객체 생성·경로 탐색·화면 출력을 하지 않는다. 이것이 **S — 단일 책임 원칙**을 적용한 부분이다.


<a id="station"></a>
## Station — 물리적 역 하나

교대역처럼 같은 장소에 있는 역의 호선별 정점을 묶는다.
코드: [station.py](models/station.py)

```text
교대 Station
 ├─ 교대 2호선 Vertex
 └─ 교대 3호선 Vertex
```

### 속성

| 속성 | 의미 |
|---|---|
| `name` | 역 이름 문자열 |
| `vertices` | 소속 Vertex들의 리스트 |

### 1. 생성자: Station(name)

**역할:** 역 이름과 빈 정점 목록을 가진 Station 객체를 만든다.

- **입력 인자:** 비어 있지 않은 역 이름 문자열. 앞뒤 공백은 제거한다.
- **생성 결과의 자료형: Station 객체.** `name`은 역 이름 **문자열**, `vertices`는 Vertex 객체들을 담는 **리스트**다. 처음에는 빈 리스트다.

사용 예시: 교대역 객체를 생성한다. 생성자는 이름과 빈 정점 목록을 준비하며, 마지막 print()는 저장된 이름을 확인하기 위한 코드다.

```python
from classes.models.station import Station
from classes.models.vertex import Vertex

station = Station("교대")
print(station.name)
```

실행 결과: 문자열 하나가 화면에 출력된다. 생성자가 이름을 출력하는 것은 아니다.

```text
교대
```

### 2. add_vertex(vertex)

**역할:** 이 역에 속한 호선별 정점을 등록한다. 생성한 Vertex는 이 메서드를 호출해야 목록에 들어간다.

- **입력 인자:** `vertex.station`이 현재 Station 객체인 Vertex 하나.
- **반환값: `None`(돌려주는 데이터 없음).** 리스트를 반환하는 메서드가 아니다. 대신 `vertices`라는 **리스트**에 전달한 Vertex 객체가 추가된다.

사용 예시: 위에서 만든 교대역에 2호선·3호선 정점을 등록한다. 마지막 두 줄은 등록 후 정점 개수와 첫 번째 정점의 호선을 확인한다.

```python
v2 = Vertex("0223", station, "2호선")
v3 = Vertex("0330", station, "3호선")
station.add_vertex(v2)
station.add_vertex(v3)

print(len(station.vertices))
print(station.vertices[0].line)
```

실행 결과: 첫 줄은 등록된 정점 개수(정수), 둘째 줄은 첫 번째 정점의 호선(문자열)이다. add_vertex()의 반환값을 출력한 것이 아니다.

```text
2
2호선
```


### 등록할 때 알아둘 점

- `Vertex(..., station, ...)`은 정점에 소속 역을 알려준다. 역의 `vertices` 리스트에 넣으려면 `station.add_vertex(vertex)`를 별도로 호출한다.
- `add_vertex()`의 None 반환은 실패라는 뜻이 아니다. 등록 결과는 `station.vertices`에 저장되므로, 별도 데이터를 돌려주지 않는 것이다.
- 이미 등록한 같은 정점 객체를 다시 전달하면 추가하지 않는다. 다른 역 소속이거나, 같은 역코드의 다른 객체를 등록하면 오류가 난다.
- 같은 이름의 역을 자동으로 합치지 않는다. 경의중앙선 신촌과 2호선 신촌은 서로 다른 Station으로 만들어야 한다.

### 발표할 SOLID 원칙

**S — 단일 책임:** Station은 물리적 역과 소속 정점 관리만 담당한다. CSV 읽기·환승 판단·경로 탐색은 다른 코드가 맡는다.


<a id="vertex"></a>
## Vertex — 한 역의 한 호선 정점

강남역 2호선처럼 경로 탐색에 사용하는 정점 하나를 나타낸다. 여기서 출발하는 탑승·환승 간선을 보관한다.

- **Station:** 물리적 역 하나. 예: 교대역.
- **Vertex(정점):** 그 역의 특정 호선. 예: 교대역 2호선, 교대역 3호선.
- **Edge(간선):** 정점과 정점 사이의 이동 구간. 예: 강남→역삼 탑승, 교대 2호선→3호선 환승.

같은 교대 Station에 2호선·3호선 Vertex를 따로 만든다. 반면 이름만 같은 두 신촌역은 물리적으로 다른 역이므로 Station부터 따로 만든다.
코드: [vertex.py](models/vertex.py)

### 속성

| 속성 | 의미 |
|---|---|
| `station_code` | CSV에서 쓰는 문자열 역코드. 예: `"0222"` |
| `station` | 소속 Station 객체 |
| `line` | 호선 이름 문자열 |
| `edges` | 이 정점에서 출발하는 간선들의 리스트 |

### 1. 생성자: Vertex(station_code, station, line)

**역할:** 호선별 정점 정보와 빈 출발 간선 목록을 가진 Vertex 객체를 만든다.

| 입력 인자 | 의미 | 예시 |
|---|---|---|
| `station_code` | 비어 있지 않은 문자열 역코드 | `"0222"` |
| `station` | 소속 Station 객체 | 강남 Station |
| `line` | 비어 있지 않은 문자열 호선 이름 | `"2호선"` |

**생성 결과의 자료형: Vertex 객체.** `station_code`와 `line`은 **문자열**, `station`은 **Station 객체**, `edges`는 간선 객체들을 담는 **리스트**다. 처음에는 빈 리스트이며, Station에 자동 등록하지는 않는다.

사용 예시: 강남역 2호선 정점을 생성하고 Station에 등록한다. 마지막 print()는 역코드가 저장됐는지 확인하는 코드다.

```python
from classes.models.station import Station
from classes.models.vertex import Vertex

station = Station("강남")
vertex = Vertex("0222", station, "2호선")
station.add_vertex(vertex)

print(vertex.station_code)
```

실행 결과: 문자열 하나.

```text
0222
```

### 2. add_edge(edge)

**역할:** 전달받은 간선을 이 정점의 출발 간선 목록에 등록한다. 간선을 직접 생성하거나 이동 경로를 선택하지는 않는다.

- **입력 인자:** `edge.from_v`가 현재 Vertex 객체인 간선 하나.
- **반환값: `None`(돌려주는 데이터 없음).** 리스트를 반환하는 메서드가 아니다. 대신 `edges`라는 **리스트**에 전달한 간선 객체가 추가된다.

사용 예시: **통합 Edge 클래스 구현 후** 위 코드에 이어서 실행한다.

```python
from classes.models.edge import Edge

destination = Vertex("0221", Station("역삼"), "2호선")
edge = Edge(
    vertex, destination, 60,
    kind="ride", distance=800, branch="순환선",
)
vertex.add_edge(edge)

print(len(vertex.edges))
```

합의한 생성자로 Edge를 구현했을 때의 예상 실행 결과: 정수 하나. add_edge()의 반환값이 아니라, 등록 후 간선 개수를 확인한 값이다.

```text
1
```


### 도착점이 같은 환승 간선을 왜 여러 개 저장하는가?

가락시장에서 **3호선→8호선**으로 환승하는 두 경우를 비교하면 다음과 같다. 시간은 현재 환승 CSV의 값이다.

| 환승 직전에 지나온 역 | 갈아탄 뒤 다음 역 | 환승시간 |
|---|---|---|
| 수서 | 송파 | 122초 |
| 수서 | 문정 | 112초 |

두 경우의 간선 출발점과 도착점은 똑같다.

```text
출발 정점(from_v): 가락시장 3호선 Vertex
도착 정점(to_v):   가락시장 8호선 Vertex
```

여기서 **도착 정점은 송파나 문정이 아니라 가락시장 8호선**이다. 송파·문정은 환승을 마친 뒤 열차로 이동할 다음 역이다.
8호선에서 탈 방향이 달라 환승시간도 다르므로 두 간선을 따로 저장한다.

```text
가락시장 3호선 Vertex.edges (리스트)
 ├─ 환승 간선 A: 수서에서 들어와 송파 방향, 122초
 └─ 환승 간선 B: 수서에서 들어와 문정 방향, 112초
             두 간선 모두 가락시장 8호선 Vertex로 연결
```

- `add_edge()`는 두 간선을 목록에 보관한다. 도착점이 같다는 이유로 하나를 지우지 않는다.
- Edge는 환승 직전 역(`from_prev_code`)과 환승 후 다음 역(`to_next_code`)을 보관해야 한다.
- SubwayGraph의 탐색 코드가 실제 이동 방향에 맞는 간선을 선택한다. 무조건 더 짧은 112초를 선택하면 안 된다.

### 헷갈리기 쉬운 동작

| 질문 | 실제 동작 |
|---|---|
| Vertex를 만들면 Station에 자동 등록되는가? | 아니다. `station.add_vertex(vertex)`를 따로 호출한다. |
| `add_edge()`가 간선을 만드는가? | 아니다. 이미 생성한 간선을 받아 `edges` 리스트에 추가한다. |
| `add_edge()`가 개수만 세는가? | 아니다. 등록이 본래 기능이다. 예시의 `len(vertex.edges)`는 등록 후 개수를 확인할 뿐이다. |
| 반환값 None이면 등록에 실패한 것인가? | 아니다. 별도 데이터를 돌려주지 않는다는 뜻이다. 오류가 없다면 정상 등록하거나 이미 등록된 간선을 유지한다. |
| A→B를 등록하면 B→A도 생기는가? | 아니다. 반대 방향 간선은 별도로 생성·등록한다. |
| 역코드가 같으면 같은 출발 정점인가? | 등록 검사에서는 정확히 같은 Vertex 객체여야 한다. 같은 코드로 객체를 여러 번 만들지 말고 기존 객체를 재사용한다. |

역코드는 문자열로 전달한다. `"0222"`를 숫자로 바꾸면 앞자리 0이 사라진다.
빈 역코드·빈 호선·소속 역 None·다른 정점에서 출발하는 간선은 ValueError로 알린다.
이미 등록한 같은 간선 객체는 다시 추가하지 않는다. 3번 담당자가 Edge의 동등성 비교를 구현한다면, 방향 조건이 다른 환승 간선을 서로 같은 것으로 취급하지 않아야 한다.

### 발표할 SOLID 원칙

**S — 단일 책임:** Vertex는 정점 정보와 출발 연결만 관리한다. 비용 계산·혼잡도 계산·경로 탐색은 담당하지 않는다.

<a id="edge"></a>
## Edge — 탑승·환승 구간

[models/edge.py](models/edge.py)의 `Edge`는 출발·도착 정점, 소요시간, 거리를 보관한다. 소요시간은 0 이상의 정수이며 거리 누락은 `None`이다. `cost()`는 초 단위 비용을 반환한다. `RideEdge`는 혼잡도 데이터를 보관하고 `congestion_get(day, slot)`로 조회한다. `TransferEdge`는 진입·진출 방향에 맞춰 `next_state()`를 결정한다. 두 종류 모두 탐색기가 공통 이동 계약으로 처리한다.

<a id="routing"></a>
## 지하철 경로 탐색 인수인계

김민석 님이 경로 탐색 코드를 이해하고 대시보드에 연결할 수 있도록 정리한 문서다. 경로 탐색 담당 범위의 주요 구현 파일은 아래 네 개이며, 화면에서는 `SubwayGraph`를 통해 기능을 호출하면 된다.

### 1. 담당 구현 파일과 읽는 순서

| 읽는 순서 | 파일 | 직관적인 역할 | 중요 함수·메서드 |
|---|---|---|---|
| 1 | [service_time.py](service_time.py) | 시각을 계산하고 혼잡도 시간대 선택 | `departure_seconds`, `congestion_slot` |
| 2 | [route.py](models/route.py) | 찾은 경로의 시간·환승·거리·혼잡도 계산 | `total_time`, `transfer_count`, `stops`, `avg_congestion` |
| 3 | [subway_graph.py](routing/subway_graph.py) | 데이터를 지하철 지도로 만들고 조회·탐색 요청 | `build`, `_station`, `station_congestion`, `stations_between`, `shortest`, `route_options` |
| 4 | [route_finder.py](routing/route_finder.py) | 실제 경로 탐색 알고리즘 수행 | `_dijkstra`, `best_route`, `on_line`, `route_options` |

연관 파일인 `station.py`, `vertex.py`, `edge.py`, `data_loader.py`는 역·정점·이동 구간·데이터 읽기를 제공한다. 위 네 파일만 복사하면 실행되는 구조가 아니므로 프로젝트의 `classes`와 `Data` 구성을 함께 유지한다.

### 2. 알아둘 객체와 전체 흐름

- `Station`: 물리적인 역. 예를 들어 가락시장역 자체.
- `Vertex`: 역의 호선별 정점. 가락시장 3호선과 8호선은 서로 다른 정점이다.
- `RideEdge`: 열차로 인접 역까지 이동하는 구간.
- `TransferEdge`: 같은 역에서 다른 호선으로 환승하는 구간.
- `Route`: 탐색 결과의 간선들을 이동 순서대로 보관하는 객체.

```text
CSV 데이터 → SubwayGraph.build() → Station·Vertex·Edge로 그래프 구성
사용자 출발역·도착역 → SubwayGraph.shortest() 또는 route_options()
                    → RouteFinder에서 경로 탐색 → Route 반환
화면 → Route의 시간·환승·거리·혼잡도 계산 메서드 호출 → 결과 표시
```

### 3. 파일별 중요 함수

#### service_time.py — 시간 처리

| 이름 | 구현 내용 |
|---|---|
| `DAYS`, `SLOTS` | 요일 종류와 05:30부터 다음 날 00:30까지의 30분 시간대 정의 |
| `departure_seconds(departure_time)` | `HH:MM`을 초로 변환. 새벽 5시 이전은 24시간을 더해 운행일 기준으로 계산 |
| `congestion_slot(clock)` | 초 단위 시각을 30분 시간대로 내림. 예: 08:28 → 08:00. 05:30 이상 다음 날 01:00 미만 범위 밖이면 `None` |

#### route.py — 경로 결과 계산

| 메서드 | 구현 내용 |
|---|---|
| `__init__(edges)` | 탐색된 간선 목록을 `self.edges`에 순서대로 저장 |
| `total_time()` | 탑승·환승 시간을 합산해 초 단위로 반환 |
| `transfer_count()` | 환승 간선 수를 계산 |
| `stops()` | `(탑승 구간 수, 총거리 m)` 반환. 환승 보행도 거리에 포함하며, 거리 누락이 하나라도 있으면 총거리는 `None` |
| `avg_congestion(day, departure_time)` | 각 탑승 구간에 진입하는 시각의 혼잡도를 모아 산술평균 계산. 환승 시간은 다음 탑승 시각에 반영하지만 환승 구간 자체는 평균에서 제외 |

혼잡도는 `edge.py`의 `RideEdge.congestion_get(day, slot)`으로 가져온다. 모든 구간에 출발 시각을 고정해서 적용하지 않으며, 이동시간으로 가중한 평균도 아니다. 탑승이 없거나 필요한 값이 누락되면 `None`을 반환한다.

#### subway_graph.py — 지도 구성과 외부 호출 창구

| 메서드·함수 | 구현 내용 |
|---|---|
| `__init__(loader=None, finder_factory=RouteFinder)` | 데이터 공급자·탐색기 설정과 빈 저장 공간 준비. 실제 데이터는 아직 읽지 않음 |
| `build()` | 데이터 읽기 → 역과 정점 생성 → 탑승 연결 → 환승 연결 → 전체 목록 저장 |
| `_station(name_or_code, line=None)` | 역 이름이나 코드로 역 검색. 동명이역은 코드로 구분하도록 오류 안내 |
| `station_congestion(...)` | 바로 이웃한 역 방향으로 출발하는 열차의 시간대별 혼잡도 조회. 시간대 그래프에 사용 |
| `stations_between(start, end, line)` | 같은 호선에서 환승 없이 가장 빠른 경유 정점 목록 반환. 구간의 역 목록 표시에 사용 |
| `shortest(start, end, priority=...)` | 역을 찾고 탐색기에 위임. 기본은 최단시간, 동률이면 최소환승 |
| `route_options(start, end)` | 최단시간·최소환승·두 번째 최단시간 결과를 묶어 요청 |
| `_station_groups`, `_branch_order` | 환승으로 연결된 역코드 묶기, 지선별 역 순서 정리 |

`graph.vertices`는 `{역코드: Vertex}` 딕셔너리이고, `station.vertices`는 한 역에 속한 호선별 정점 목록이다.

#### route_finder.py — 실제 길 찾기

| 함수·메서드 | 구현 내용 |
|---|---|
| `time_first(edge)` | `(시간, 환승 여부)` 비용을 반환해 시간 우선 비교 |
| `transfers_first(edge)` | `(환승 여부, 시간)` 비용을 반환해 환승 횟수 우선 비교 |
| `_dijkstra(...)` | 비용이 가장 작은 상태부터 탐색. 성공하면 `(비용, Route)`, 실패하면 `None` 반환 |
| `_restore_route(previous_steps, end_state)` | 도착부터 이전 기록을 따라간 뒤 순서를 뒤집어 `Route` 생성 |
| `_cycle_rides(route)` | 같은 물리적 역을 재방문하는 구간의 탑승 간선 찾기 |
| `best_route(...)` | 다익스트라 결과에 역 재방문이 있으면 순환 간선을 하나씩 제외해 재탐색. 재방문 없는 `Route` 또는 `None` 반환 |
| `on_line(...)` | 해당 호선의 정점에서 출발하고 환승을 제외해 경로 탐색 |
| `route_options(...)` | 기본 경로·최소환승 경로와 기본 경로의 탑승 간선을 하나씩 제외한 대안 비교 |

알고리즘은 `_dijkstra()`를 먼저 읽고 `best_route()`를 읽으면 이해하기 쉽다.

```text
_dijkstra:
출발 후보 등록 → 가장 저렴한 후보 꺼내기 → 오래된 후보면 건너뛰기
→ 목적지면 경로 복원·반환
→ 이동 가능한 간선마다 비용 계산
→ 처음 발견했거나 기존보다 좋으면 비용·이동 기록 저장 후 큐에 추가
→ 후보가 없어질 때까지 반복

best_route:
다익스트라로 후보 생성 → 가장 저렴한 경로의 역 재방문 확인
→ 재방문 없으면 반환
→ 재방문 있으면 순환 간선을 하나씩 막은 별도 후보 생성 후 반복
```

| 탐색 변수 | 의미 |
|---|---|
| `queue` | 앞으로 탐색할 `(비용, 상태)` 후보. `heapq`로 가장 작은 비용부터 꺼냄 |
| `best_costs` | 상태별로 지금까지 찾은 최저 비용 |
| `previous_steps` | 다음 상태에 도달하기 전의 `(이전 상태, 이용 간선)` 기록 |
| `current_state` | `(현재 역코드, 직전 탑승역 코드, 환승 후 가야 할 역코드)` |
| `excluded` | 이번 탐색에서 사용하지 않을 간선 집합 |

상태에 방향을 포함하는 이유는 같은 역이라도 들어온 방향과 환승 후 나갈 방향에 따라 환승 조건이 달라지기 때문이다. 빈 문자열은 해당 정보나 방향 제한이 없음을 뜻한다.

### 4. 김민석 님이 화면에 연결할 때

프로젝트 루트에서 Python 3으로 실행한다. 경로 탐색에는 표준 라이브러리와 저장소의 CSV만 사용한다. 화면이 시작될 때 그래프를 한 번 만들고, 이후 사용자 요청에서 같은 객체를 재사용한다.

```python
from classes.routing.subway_graph import SubwayGraph

graph = SubwayGraph()
graph.build()
options = graph.route_options("서울역", "강남")

for key, route in options.items():
    if route is None:
        continue
    stops, meters = route.stops()
    print(key, route.total_time(), route.transfer_count(), stops, meters)
    print("평일 08:00 평균 혼잡도(%)", route.avg_congestion("평일", "08:00"))
```

현재 CSV의 경로 비교 결과는 다음과 같다.

| 반환 키 | 선택 기준 | 서울역 → 강남 |
|---|---|---|
| `fastest` | 총시간이 가장 짧은 경로. 동률이면 최소 환승 | 충무로·신사 환승, 22분 21초 |
| `fewest_transfers` | 환승 횟수가 가장 적은 경로. 동률이면 최단시간 | 사당 환승, 23분 22초 |
| `second_fastest` | 최단 경로와 탑승 구간이 다른 경로 중 가장 빠른 경로 | 충무로·교대 환승, 22분 49초 |

최단시간만 필요하면 `graph.shortest(start, end)`를 호출한다. 비교 카드를 그릴 때는 `route_options()` 한 번으로 세 값을 받는다. 서로 다른 경로가 같은 시간이면 두 번째 경로도 같은 시간일 수 있다. 최소 환승과 다른 기준이 같은 경로를 고르면 한 카드에 두 기준을 함께 표시할 수 있다. 동일 경로인지는 `route.edges` 목록을 비교한다.

### 5. 화면에서 쓸 값

| 호출 | 반환값과 단위 |
|---|---|
| `route.edges` | 이동 순서대로 정렬한 간선. `RideEdge`는 열차 탑승, `TransferEdge`는 환승이다. 각 간선의 `from_v`, `to_v`에서 호선과 역코드를 읽는다. |
| `route.total_time()` | 탑승과 환승 보행을 합한 초. 열차 대기시간은 데이터에 없다. |
| `route.transfer_count()` | 환승 횟수 |
| `route.stops()` | `(탑승 구간 수, 총 이동거리 m)`. 총거리에 환승 보행을 포함한다. 한 구간이라도 거리 누락이면 거리는 `None`이다. |
| `route.avg_congestion(day, departure_time)` | 구간별 혼잡도(%)의 산술평균. 각 탑승 시작 시각을 30분 단위로 내린다. 환승 시간도 다음 탑승 시각에 반영한다. 탑승이 없거나 구간 값이 하나라도 없으면 `None`이다. |
| `graph.station_congestion(station, next_station, line, day)` | 해당 역에서 지정한 **바로 다음 역** 방향으로 출발하는 시간대별 혼잡도 딕셔너리. 방향을 다음 역으로 고르면 분기점에서도 구분할 수 있다. 빈 시간칸은 `None`이다. |
| `graph.stations_between(start, end, line)` | 해당 호선에서 환승 없이 가장 빠른 구간의 `Vertex` 목록. 양 끝을 포함하고 방향상 연결이 없으면 빈 목록이다. |
| `graph.line_order[line][branch]` | 히트맵 축에 사용할 지선별 역 순서. 순환선의 시작역은 한 번만 나온다. |
| `graph.vertices[station_code]`, `graph.edges` | 역코드별 정점과 전체 방향별 간선 목록 |

```python
series = graph.station_congestion("수서", "가락시장", "3호선", "평일")
print(series["08:00"])  # 18.5
section = graph.stations_between("수서", "오금", "3호선")
print([v.station.name for v in section])  # 수서, 가락시장, 경찰병원, 오금
```

요일은 `평일`, `토요일`, `일요일` 중 하나이고 출발 시각은 24시간제 `HH:MM`이다. 자정 이후 00시대는 같은 운행일에 속한다. 혼잡도 관측 범위는 05:30부터 다음 날 01:00 직전까지다. 화면에서는 `None`을 ‘자료 없음’으로 표시한다. 혼잡도는 경로 비교 지표로 사용한다. 운행 여부나 출발 시각별 배차를 반영하는 시간표 탐색은 이 API의 범위 밖이다.

### 6. 입력과 예외 처리

- 그래프를 만들기 전 조회하면 `RuntimeError`, 알 수 없는 역이나 잘못된 호선·방향·요일은 `ValueError`다. 동명이역 오류에는 선택 가능한 호선과 코드가 포함된다.
- 코드는 앞자리 0을 포함한 문자열이다. `"0240"`과 `"1252"`는 각각 다른 신촌역을 선택한다. 최단 경로의 출발·도착은 물리적 역 단위라서 그 역의 모든 호선을 후보로 쓴다.
- 출발역과 도착역이 같으면 최단시간·최소환승은 0초인 빈 경로다. 연결 자체가 없으면 세 결과 모두 `None`이고, 다른 단순 경로만 없으면 `second_fastest`가 `None`이다.

### 7. 탐색을 수정할 때

다익스트라의 상태에는 현재 역코드, 직전 탑승역 코드, 환승 후 가야 하는 다음 역코드가 들어간다. 수서에서 가락시장에 들어와 8호선 송파 방향으로 갈아타면 122초, 문정 방향이면 112초다. 정점만으로 방문 기록을 합치면 이 차이가 사라진다.

두 번째 경로는 첫 경로의 탑승 간선을 하나씩 제외하고 다시 탐색한 결과 중 가장 빠른 것을 고른다. 물리적 역을 재방문하지 않는 다른 경로라면 첫 경로의 탑승 간선이 적어도 하나 빠진다. 싼 환승을 노려 직전 역을 왕복하는 후보는 순환 간선을 하나씩 제외해 다시 비교한다. 따라서 비교 조회는 단일 최단시간 조회보다 비용이 크다.

### 8. 경로 기능에 적용한 SOLID 원칙

경로 탐색 담당 코드에 적용한 원칙을 정리했다. 화면은 기존처럼 `SubwayGraph`를 호출하며, 기존 `from classes.routing.subway_graph import Route`도 지원한다.

| 원칙 | 적용 내용과 코드 근거 |
|---|---|
| **S — 단일 책임 원칙(SRP)** | `SubwayGraph`는 그래프 구성·역 조회, `RouteFinder`는 경로 탐색, `Route`는 결과 요약을 담당한다. 운행일·시간대 변환은 `service_time.py`로 분리했다. |
| **O — 개방·폐쇄 원칙(OCP)** | `shortest(..., priority=함수)`로 탐색 알고리즘을 수정하지 않고 비용 비교 기준을 확장한다. `time_first`는 시간 우선, `transfers_first`는 환승 횟수 우선이다. |
| **L — 리스코프 치환 원칙(LSP)** | `RideEdge`와 `TransferEdge`는 공통 `Edge` 계약을 따른다. 탐색기는 동일하게 `cost()`와 `next_state()`를 호출하며, 비용은 초 단위이고 다음 상태는 튜플 또는 이동 불가를 뜻하는 `None`이다. |
| **I — 인터페이스 분리 원칙(ISP)** | 공통 이동 기능은 `Edge`에 두고, 탑승에만 필요한 `congestion_get()`는 `RideEdge`에 둔다. `TransferEdge`에 불필요한 혼잡도 조회 구현을 요구하지 않는다. |
| **D — 의존성 역전 원칙(DIP)** | `SubwayGraph(loader=..., finder_factory=...)`로 데이터 공급자와 탐색기를 외부에서 주입한다. 같은 메서드 계약을 갖추면 교체할 수 있으며, 탐색기는 CSV 입출력을 알 필요가 없다. |

`priority(edge)`는 합산 가능한 **0 이상의 비용 두 개**를 반환해야 하며, 첫 번째 합계가 같을 때 두 번째 합계를 비교한다. 의존성 주입은 별도의 추상 클래스 대신 파이썬의 덕 타이핑(필요한 메서드를 제공하는 객체)을 사용한다.

예를 들어 최소 환승 하나만 요청하려면 다음과 같이 호출한다.

```python
from classes.models.route_finder import transfers_first

route = graph.shortest("서울역", "강남", priority=transfers_first)
print(route.transfer_count(), route.total_time())  # 1 1402
```
