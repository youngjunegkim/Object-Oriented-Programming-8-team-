# 클래스 설계와 SOLID 적용

지하철 데이터를 그래프로 구성하고, 최단시간·최소환승·대안 경로를 찾는다. 설계의 핵심은 **데이터 읽기, 객체 관리, 경로 탐색, 결과 계산의 책임을 구분하고 필요한 동작을 객체에 맡기는 것**이다.

## 목차

1. [구조와 클래스별 책임](#structure)
2. [SOLID 적용 근거](#solid)
3. [경로 탐색 흐름](#flow)
4. [사용 예시와 반환 규칙](#usage)

<a id="structure"></a>
## 1. 구조와 클래스별 책임

```text
classes/
├─ loaders/data_loader.py
├─ models/
│  ├─ station.py
│  ├─ vertex.py
│  ├─ edge.py
│  └─ route.py
├─ routing/
│  ├─ subway_graph.py
│  └─ route_finder.py
├─ service_time.py
└─ views/                    # 프론트 담당 영역, 아직 화면 구현 없음
```

| 구현 | 책임 | 주요 메서드·함수 |
|---|---|---|
| [CongestionDataLoader](loaders/data_loader.py) | CSV 읽기, 필수 값·형식·중복 검사, 자료형 변환 | `load_stations`, `load_distance`, `load_transfers`, `load_congestion` |
| [Station](models/station.py) | 물리적 역과 그 역에 속한 호선별 정점 관리 | `add_vertex` |
| [Vertex](models/vertex.py) | 한 역의 한 호선 정점과 출발 간선 관리 | `add_edge` |
| [Edge · RideEdge · TransferEdge](models/edge.py) | 이동 비용, 탑승·환승 방향 규칙, 탑승 혼잡도 제공 | `cost`, `next_state`, `congestion_get` |
| [Route](models/route.py) | 찾은 경로의 시간·환승·거리·혼잡도 계산 | `total_time`, `transfer_count`, `stops`, `avg_congestion` |
| [SubwayGraph](routing/subway_graph.py) | 역·간선 구성과 조회, 탐색기로 요청 전달 | `build`, `shortest`, `route_options`, `station_congestion`, `stations_between` |
| [RouteFinder](routing/route_finder.py) | 경로 탐색, 복원, 역 재방문 없는 대안 비교 | `_dijkstra`, `best_route`, `on_line`, `route_options` |
| [service_time](service_time.py) | 운행일 기준 시간 변환과 30분 시간대 선택 | `departure_seconds`, `congestion_slot` |

예를 들어 가락시장 `Station` 하나에 3호선·8호선 `Vertex`가 속한다. 정점 사이는 탑승 또는 환승 간선으로 연결되고, 탐색 결과는 간선 목록을 가진 `Route`로 반환된다.

<a id="solid"></a>
## 2. SOLID 적용 근거

### 한눈에 보기

| 번호 | 원칙 | 우리 코드에서의 핵심 |
|---|---|---|
| **1. S** | 단일 책임 | 읽기는 로더, 탐색은 탐색기, 결과 계산은 Route |
| **2. O** | 개방·폐쇄 | 다익스트라를 수정하지 않고 비용 함수 교체 |
| **3. L** | 리스코프 치환 | 탑승·환승 간선을 같은 이동 계약으로 처리 |
| **4. I** | 인터페이스 분리 | 혼잡도 조회는 필요한 탑승 간선에만 제공 |
| **5. D** | 의존성 역전 | 로더·탐색기를 외부에서 받아 교체 가능하게 구성 |

---

### 1. S — 단일 책임 원칙 (SRP)

**뜻:** 클래스가 맡은 책임을 명확히 해서, 서로 다른 이유의 변경이 한 클래스에 몰리지 않도록 한다.

**우리 코드:** 읽기·탐색·계산을 각각 분리했다.

| 담당 | 책임 |
|---|---|
| `CongestionDataLoader` | CSV 읽기·입력 검사 |
| `Station`, `Vertex`, `Edge` | 역·정점·간선의 정보와 연결 규칙 관리 |
| `SubwayGraph` | 그래프 구성·조회 및 탐색 요청 전달 |
| `RouteFinder` | 경로 탐색 |
| `Route` | 경로 결과 계산 |
| `service_time.py` | 시간 변환 규칙 |

**예시:** CSV 열 구성이 달라지면 로더를, 시간대 계산 규칙이 달라지면 `service_time.py`를 수정한다. 화면 표시는 프론트가 담당한다.

**핵심:** 모델이 다른 역 소속 정점이나 음수 비용을 거부하는 것은 자기 규칙을 지키는 책임이다. 이를 모두 로더로 옮길 필요는 없다.

---

### 2. O — 개방·폐쇄 원칙 (OCP)

**뜻:** 기존 핵심 코드를 계속 고치기보다, 새로운 동작을 추가할 수 있는 지점을 마련한다.

**우리 코드:** `priority` 함수로 경로 비교 기준을 바꾼다.

```python
# 동일한 탐색 코드에 비용 기준만 다르게 전달
route = graph.shortest("서울역", "강남", priority=time_first)
route = graph.shortest("서울역", "강남", priority=transfers_first)
```

- `time_first`: 시간 우선, 동률이면 최소환승
- `transfers_first`: 환승 횟수 우선, 동률이면 최단시간

**핵심:** 다익스트라 본문은 그대로 두고 비용 함수를 바꾼다. 새 함수는 간선별로 합산 가능한 **음수가 아닌 비용 두 개**를 반환해야 한다.

---

### 3. L — 리스코프 치환 원칙 (LSP)

**뜻:** 부모 타입을 사용하는 코드에서 자식 객체도 약속된 동작을 지켜 사용할 수 있어야 한다.

**우리 코드:** `RideEdge`와 `TransferEdge`는 `Edge`를 상속하고 공통 이동 계약을 따른다.

```python
# edge가 탑승 간선이든 환승 간선이든 같은 방식으로 호출
seconds = edge.cost()
next_state = edge.next_state(previous_code, required_next)
```

| 기능 | 두 간선이 지키는 약속 |
|---|---|
| `cost()` | 0 이상의 소요시간을 초 단위로 반환 |
| `next_state()` | 이동 가능하면 상태 튜플, 불가능하면 `None` 반환 |
| `is_transfer` | 환승 여부를 불리언으로 제공 |

**핵심:** 탑승·환승의 방향 판단은 각 간선이 담당하고, 탐색기는 동일한 호출·반환 규칙으로 처리한다.

---

### 4. I — 인터페이스 분리 원칙 (ISP)

**뜻:** 객체가 사용하지 않는 기능까지 구현하도록 요구하지 않는다.

**우리 코드:** 공통 이동 기능과 탑승 전용 혼잡도 기능을 나눴다.

```text
Edge                 → cost(), next_state(), is_transfer
├─ RideEdge          → 공통 기능 + congestion_get()
└─ TransferEdge      → 공통 기능 + 환승 방향 처리
```

**예시:** 열차 탑승 구간에는 혼잡도가 필요하지만, 환승 보행 구간에는 같은 혼잡도 조회 기능을 구현하도록 요구하지 않는다.

**핵심:** `congestion_get()`는 `RideEdge`에만 있다. 별도의 인터페이스 클래스를 선언한 것은 아니며, 메서드의 범위를 역할별로 구분했다.

---

### 5. D — 의존성 역전 원칙 (DIP)

**뜻:** 상위 기능이 특정 구현에만 묶이지 않고, 필요한 동작의 계약을 통해 하위 기능을 사용하도록 한다.

**우리 코드:** `SubwayGraph`가 사용할 로더와 탐색기를 외부에서 전달받을 수 있다.

```python
# routing/subway_graph.py의 생성자
def __init__(self, loader=None, finder_factory=RouteFinder):
    self.loader = CongestionDataLoader() if loader is None else loader
    self.finder_factory = finder_factory
```

| 교체 대상 | 유지해야 할 계약 |
|---|---|
| `loader` | 네 가지 `load_*` 메서드와 기존 데이터 반환 구조 |
| `finder_factory` | 정점 정보를 받아 `best_route`, `on_line`, `route_options`를 제공하는 탐색기 생성 |

**핵심:** 같은 계약을 제공하면 다른 로더·탐색기로 교체할 수 있다. 탐색기는 CSV 경로나 화면 구현을 알 필요가 없다.

**현재 범위:** 덕 타이핑과 의존성 주입을 사용한다. 기본 구현을 import하는 의존은 남아 있으므로 완전한 추상화라고 설명하지 않는다.

---

**발표 시 적용 범위:** 폴더를 나누거나 상속했다고 SOLID가 자동으로 충족되는 것은 아니다. 위의 책임 분리·비용 함수·공통 계약·기능 분리·주입 지점을 근거로 설명한다. `Route`의 탑승 구간 계산과 대안 탐색 일부는 여전히 `isinstance(edge, RideEdge)`를 사용하므로 모든 종류의 간선에 수정 없이 확장되는 구조는 아니다.

<a id="flow"></a>
## 3. 경로 탐색 흐름

```text
CSV → CongestionDataLoader → SubwayGraph.build()
                            └─ Station · Vertex · Edge 구성
사용자 입력 → SubwayGraph.shortest() / route_options()
            → RouteFinder → Route → 프론트에서 결과 표시
```

1. `_dijkstra()`는 비용이 작은 상태부터 꺼내 이동 가능한 간선을 확인한다. 더 좋은 경로를 발견하면 비용과 이전 이동 기록을 갱신한다.
2. 도착하면 `_restore_route()`가 이전 기록을 따라 간선 목록을 복원한다.
3. `best_route()`는 역 재방문이 있으면 순환 구간의 탑승 간선을 하나씩 제외한 경우를 다시 탐색한다.
4. `route_options()`는 최단시간·최소환승 경로를 구하고, 최단 경로의 탑승 간선을 하나씩 제외해 두 번째 경로를 비교한다.

상태는 `(현재 역코드, 직전 탑승역 코드, 환승 후 가야 할 역코드)`이다. 같은 정점이라도 진입·진출 방향에 따라 환승 조건이 다르기 때문에 역코드만으로 방문 기록을 합치지 않는다. 두 번째 경로는 최단 경로와 탑승 구간이 다른 대안이며, 시간이 같을 수도 있다.

<a id="usage"></a>
## 4. 사용 예시와 반환 규칙

프로젝트 루트에서 Python 3으로 실행한다. `__init__.py` 없이 네임스페이스 패키지를 사용하므로 구체적인 모듈 경로로 import한다.

```python
from classes.routing.subway_graph import SubwayGraph
from classes.routing.route_finder import transfers_first

graph = SubwayGraph()
graph.build()  # 기본 혼잡도: Congestion_II. 한 번 구성한 후 재사용

options = graph.route_options("서울역", "강남")
for name, route in options.items():
    if route is None:
        continue
    print(name, route.total_time(), route.transfer_count(), route.stops())
    print(route.avg_congestion("평일", "08:00"))

# OCP 예시: 같은 탐색기에 다른 비용 기준 전달
route = graph.shortest("서울역", "강남", priority=transfers_first)
```

| 호출 | 반환·처리 규칙 |
|---|---|
| `shortest()` | `Route` 또는 경로가 없으면 `None` |
| `route_options()` | `fastest`, `fewest_transfers`, `second_fastest`별 `Route` 또는 `None` |
| `station_congestion(역, 다음역, 호선, 요일)` | 바로 이웃한 역으로 출발하는 방향의 시간대별 혼잡도 딕셔너리 |
| `stations_between(출발역, 도착역, 호선)` | 해당 호선에서 환승 없는 최단시간 경유 정점 목록. 양 끝 포함, 연결 없으면 빈 목록 |
| `total_time()` / `transfer_count()` | 탑승·환승 소요시간 합계(초) / 환승 횟수 |
| `stops()` | `(탑승 구간 수, 총거리 m)`. 환승 거리 포함, 거리 누락 시 총거리는 `None` |
| `avg_congestion(요일, 출발시각)` | 각 탑승 진입 시각의 혼잡도 산술평균(%). 환승 시간은 다음 진입 시각에 반영. 탑승이나 필요한 값이 없으면 `None` |

- 역코드는 앞자리 0을 포함하는 문자열이다. 동명이역은 코드로 구분한다.
- 요일은 `평일`, `토요일`, `일요일`, 시각은 `HH:MM`이다. 혼잡도 관측 범위는 05:30 이상 다음 날 01:00 미만이다.
- 구성 전 조회는 `RuntimeError`, 잘못된 역·방향·요일 등의 입력은 `ValueError`로 알린다.
- 혼잡도는 찾은 경로의 비교 정보이며 기본 경로 선택 비용에는 포함하지 않는다. 열차 대기시간·배차 시간표도 반영하지 않는다.
- 기본 혼잡도 파일은 `Data/Congestion_II/congestion.csv`이다. 기존 버전은 `CongestionDataLoader(congestion_path=CONGESTION_CSV)`로 선택한 로더를 `SubwayGraph(loader=loader)`에 전달한다. 두 이름은 `classes.loaders.data_loader`에서 import한다.
- CSV 출처·컬럼·생성 방법은 [Data README](../Data/README.md)를 참고한다.
