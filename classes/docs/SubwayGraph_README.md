# 지하철 경로 탐색 인수인계

## 처음 실행하기

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

## 화면에서 쓸 값

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

## 입력과 예외 처리

- 그래프를 만들기 전 조회하면 `RuntimeError`, 알 수 없는 역이나 잘못된 호선·방향·요일은 `ValueError`다. 동명이역 오류에는 선택 가능한 호선과 코드가 포함된다.
- 코드는 앞자리 0을 포함한 문자열이다. `"0240"`과 `"1252"`는 각각 다른 신촌역을 선택한다. 최단 경로의 출발·도착은 물리적 역 단위라서 그 역의 모든 호선을 후보로 쓴다.
- 출발역과 도착역이 같으면 최단시간·최소환승은 0초인 빈 경로다. 연결 자체가 없으면 세 결과 모두 `None`이고, 다른 단순 경로만 없으면 `second_fastest`가 `None`이다.

## 탐색을 수정할 때

다익스트라의 상태에는 현재 역코드, 직전 탑승역 코드, 환승 후 가야 하는 다음 역코드가 들어간다. 수서에서 가락시장에 들어와 8호선 송파 방향으로 갈아타면 122초, 문정 방향이면 112초다. 정점만으로 방문 기록을 합치면 이 차이가 사라진다.

두 번째 경로는 첫 경로의 탑승 간선을 하나씩 제외하고 다시 탐색한 결과 중 가장 빠른 것을 고른다. 물리적 역을 재방문하지 않는 다른 경로라면 첫 경로의 탑승 간선이 적어도 하나 빠진다. 싼 환승을 노려 직전 역을 왕복하는 후보는 순환 간선을 하나씩 제외해 다시 비교한다. 따라서 비교 조회는 단일 최단시간 조회보다 비용이 크다.

## 경로 기능에 적용한 SOLID 원칙

경로 탐색 담당 코드에 적용한 원칙을 정리했다. 화면은 기존처럼 `SubwayGraph`를 호출하며, 기존 `from classes.subway_graph import Route`도 지원한다.

| 원칙 | 적용 내용과 코드 근거 |
|---|---|
| **S — 단일 책임 원칙(SRP)** | `SubwayGraph`는 그래프 구성·역 조회, `RouteFinder`는 경로 탐색, `Route`는 결과 요약을 담당한다. 운행일·시간대 변환은 `service_time.py`로 분리했다. |
| **O — 개방·폐쇄 원칙(OCP)** | `shortest(..., priority=함수)`로 탐색 알고리즘을 수정하지 않고 비용 비교 기준을 확장한다. `time_first`는 시간 우선, `transfers_first`는 환승 횟수 우선이다. |
| **L — 리스코프 치환 원칙(LSP)** | `RideEdge`와 `TransferEdge`는 공통 `Edge` 계약을 따른다. 탐색기는 동일하게 `cost()`와 `next_state()`를 호출하며, 비용은 초 단위이고 다음 상태는 튜플 또는 이동 불가를 뜻하는 `None`이다. |
| **I — 인터페이스 분리 원칙(ISP)** | 공통 이동 기능은 `Edge`에 두고, 탑승에만 필요한 `congestion_get()`는 `RideEdge`에 둔다. `TransferEdge`에 불필요한 혼잡도 조회 구현을 요구하지 않는다. |
| **D — 의존성 역전 원칙(DIP)** | `SubwayGraph(loader=..., finder_factory=...)`로 데이터 공급자와 탐색기를 외부에서 주입한다. 같은 메서드 계약을 갖추면 교체할 수 있으며, 탐색기는 CSV 입출력을 알 필요가 없다. |

`priority(edge)`는 합산 가능한 **0 이상의 비용 두 개**를 반환해야 하며, 첫 번째 합계가 같을 때 두 번째 합계를 비교한다. 의존성 주입은 별도의 추상 클래스 대신 파이썬의 덕 타이핑(필요한 메서드를 제공하는 객체)을 사용한다. `tests/test_solid_contracts.py`에는 상속 없이 탐색기를 교체하는 테스트가 있다.

예를 들어 최소 환승 하나만 요청하려면 다음과 같이 호출한다.

```python
from classes.route_finder import transfers_first

route = graph.shortest("서울역", "강남", priority=transfers_first)
print(route.transfer_count(), route.total_time())  # 1 1402
```

## 검증

프로젝트 루트에서 다음 명령을 실행한다.

```shell
python -m unittest discover -s tests -v
```

회귀 테스트에 환승 방향, 세 경로의 차이, 동시간 대안, 대안 없음, 단방향 순환선, 자정 통과, 혼잡도·거리 누락을 포함했다. 실제 경로에 대한 기대값은 저장소의 현재 CSV 기준이다.
