# 지하철 경로 탐색 인수인계

김민석 님이 경로 탐색 코드를 이해하고 대시보드에 연결할 수 있도록 정리한 문서다. 경로 탐색 담당 범위의 주요 구현 파일은 아래 네 개이며, 화면에서는 `SubwayGraph`를 통해 기능을 호출하면 된다.

## 1. 담당 구현 파일과 읽는 순서

| 읽는 순서 | 파일 | 직관적인 역할 | 중요 함수·메서드 |
|---|---|---|---|
| 1 | [service_time.py](../service_time.py) | 시각을 계산하고 혼잡도 시간대 선택 | `departure_seconds`, `congestion_slot` |
| 2 | [route.py](../route.py) | 찾은 경로의 시간·환승·거리·혼잡도 계산 | `total_time`, `transfer_count`, `stops`, `avg_congestion` |
| 3 | [subway_graph.py](../subway_graph.py) | 데이터를 지하철 지도로 만들고 조회·탐색 요청 | `build`, `_station`, `station_congestion`, `stations_between`, `shortest`, `route_options` |
| 4 | [route_finder.py](../route_finder.py) | 실제 경로 탐색 알고리즘 수행 | `_dijkstra`, `best_route`, `on_line`, `route_options` |

연관 파일인 `station.py`, `vertex.py`, `edge.py`, `data_loader.py`는 역·정점·이동 구간·데이터 읽기를 제공한다. 위 네 파일만 복사하면 실행되는 구조가 아니므로 프로젝트의 `classes`와 `Data` 구성을 함께 유지한다.

## 2. 알아둘 객체와 전체 흐름

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

## 3. 파일별 중요 함수

### service_time.py — 시간 처리

| 이름 | 구현 내용 |
|---|---|
| `DAYS`, `SLOTS` | 요일 종류와 05:30부터 다음 날 00:30까지의 30분 시간대 정의 |
| `departure_seconds(departure_time)` | `HH:MM`을 초로 변환. 새벽 5시 이전은 24시간을 더해 운행일 기준으로 계산 |
| `congestion_slot(clock)` | 초 단위 시각을 30분 시간대로 내림. 예: 08:28 → 08:00. 05:30 이상 다음 날 01:00 미만 범위 밖이면 `None` |

### route.py — 경로 결과 계산

| 메서드 | 구현 내용 |
|---|---|
| `__init__(edges)` | 탐색된 간선 목록을 `self.edges`에 순서대로 저장 |
| `total_time()` | 탑승·환승 시간을 합산해 초 단위로 반환 |
| `transfer_count()` | 환승 간선 수를 계산 |
| `stops()` | `(탑승 구간 수, 총거리 m)` 반환. 환승 보행도 거리에 포함하며, 거리 누락이 하나라도 있으면 총거리는 `None` |
| `avg_congestion(day, departure_time)` | 각 탑승 구간에 진입하는 시각의 혼잡도를 모아 산술평균 계산. 환승 시간은 다음 탑승 시각에 반영하지만 환승 구간 자체는 평균에서 제외 |

혼잡도는 `edge.py`의 `RideEdge.congestion_get(day, slot)`으로 가져온다. 모든 구간에 출발 시각을 고정해서 적용하지 않으며, 이동시간으로 가중한 평균도 아니다. 탑승이 없거나 필요한 값이 누락되면 `None`을 반환한다.

### subway_graph.py — 지도 구성과 외부 호출 창구

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

### route_finder.py — 실제 길 찾기

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

## 4. 김민석 님이 화면에 연결할 때

프로젝트 루트에서 Python 3으로 실행한다. 경로 탐색에는 표준 라이브러리와 저장소의 CSV만 사용한다. 화면이 시작될 때 그래프를 한 번 만들고, 이후 사용자 요청에서 같은 객체를 재사용한다.

```python
from classes.subway_graph import SubwayGraph

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

## 5. 화면에서 쓸 값

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

## 6. 입력과 예외 처리

- 그래프를 만들기 전 조회하면 `RuntimeError`, 알 수 없는 역이나 잘못된 호선·방향·요일은 `ValueError`다. 동명이역 오류에는 선택 가능한 호선과 코드가 포함된다.
- 코드는 앞자리 0을 포함한 문자열이다. `"0240"`과 `"1252"`는 각각 다른 신촌역을 선택한다. 최단 경로의 출발·도착은 물리적 역 단위라서 그 역의 모든 호선을 후보로 쓴다.
- 출발역과 도착역이 같으면 최단시간·최소환승은 0초인 빈 경로다. 연결 자체가 없으면 세 결과 모두 `None`이고, 다른 단순 경로만 없으면 `second_fastest`가 `None`이다.

## 7. 탐색을 수정할 때

다익스트라의 상태에는 현재 역코드, 직전 탑승역 코드, 환승 후 가야 하는 다음 역코드가 들어간다. 수서에서 가락시장에 들어와 8호선 송파 방향으로 갈아타면 122초, 문정 방향이면 112초다. 정점만으로 방문 기록을 합치면 이 차이가 사라진다.

두 번째 경로는 첫 경로의 탑승 간선을 하나씩 제외하고 다시 탐색한 결과 중 가장 빠른 것을 고른다. 물리적 역을 재방문하지 않는 다른 경로라면 첫 경로의 탑승 간선이 적어도 하나 빠진다. 싼 환승을 노려 직전 역을 왕복하는 후보는 순환 간선을 하나씩 제외해 다시 비교한다. 따라서 비교 조회는 단일 최단시간 조회보다 비용이 크다.

## 8. 경로 기능에 적용한 SOLID 원칙

경로 탐색 담당 코드에 적용한 원칙을 정리했다. 화면은 기존처럼 `SubwayGraph`를 호출하며, 기존 `from classes.subway_graph import Route`도 지원한다.

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
from classes.route_finder import transfers_first

route = graph.shortest("서울역", "강남", priority=transfers_first)
print(route.transfer_count(), route.total_time())  # 1 1402
```
