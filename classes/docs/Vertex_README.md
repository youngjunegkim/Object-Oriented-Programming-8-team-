# Vertex — 한 역의 한 호선 정점

## 역할

경로 탐색에서 사용하는 호선별 정점이다. 여기서 출발 가능한 간선을 보관한다.
예를 들어 교대역 2호선 Vertex와 교대역 3호선 Vertex는 서로 다른 정점이다.

## 속성과 메서드

| 항목 | 의미 |
|---|---|
| `station_code` | CSV에서 사용하는 호선별 역코드(str) |
| `station` | 소속 Station 객체 |
| `line` | 호선 이름(str) |
| `edges` | 이 정점에서 출발하는 Edge들의 목록(list) |
| `__init__(station_code, station, line)` | 정점 정보를 저장하고 빈 간선 목록을 만든다 |
| `add_edge(edge)` | 출발 간선을 등록한다. 반환값은 None |

주요 메서드는 보고서의 `add_edge()` 하나뿐이다.
역코드와 노선도 역번호는 다르다. 기존 CSV의 station_code를 그대로 문자열로 전달한다.

## 사용 예

Edge 생성 예시는 3번 담당자가 합의한 통합 Edge를 구현한 뒤 사용할 수 있다.

```python
from classes import Station, Vertex
from classes.edge import Edge

station_a = Station("강남")
station_b = Station("역삼")
a = Vertex("0222", station_a, "2호선")
b = Vertex("0221", station_b, "2호선")
station_a.add_vertex(a)
station_b.add_vertex(b)

edge = Edge(a, b, 60, kind="ride", distance=800, branch="순환선")
a.add_edge(edge)

print(a.station_code)       # 0222
print(a.edges[0].to_v is b) # True
```

Vertex는 자동으로 Station에 등록되지 않는다. Edge 역시 생성 후 add_edge로 등록한다.
A→B를 등록해도 B→A가 자동 생성되지는 않는다. CSV의 각 방향을 따로 연결한다.

## 코드 읽는 순서

1. `__init__()`에서 역코드·소속 역·호선을 저장한다.
2. `edges = []`로 출발 간선의 빈 목록을 만든다.
3. `edge.from_v is self`는 간선이 이 정점에서 출발하는지 확인한다.
4. 이미 등록된 같은 객체면 아무것도 하지 않는다.
5. `append()`로 간선을 추가한다.

역코드는 숫자를 받지 않는다. "0222"를 int로 바꾸면 앞의 0이 사라지기 때문이다.
소속 역 누락, 빈 호선, 잘못된 출발 정점은 ValueError로 막는다.

## 왜 간선 목록을 리스트로 두는가

같은 도착 정점으로 가더라도, 진입·진출 방향에 따라 환승시간이 다를 수 있다. 도착 정점을 키로 간선 하나만 저장하면 일부 환승 정보가 사라진다.
따라서 같은 도착 정점을 가진 서로 다른 Edge는 모두 등록한다. 같은 Edge 객체를 두 번 등록하는 것만 막는다.
현재 클래스들은 별도 동등성(__eq__) 메서드를 정의하지 않아, 목록 중복 확인은 객체 기준으로 동작한다.

## 다른 코드와의 경계

- Vertex는 Edge를 생성하거나 CSV를 읽지 않는다.
- 탑승·환승 종류별로 분기하지 않고 출발 간선만 관리한다.
- cost(), 혼잡도 조회는 Edge의 역할이다.
- 방향에 맞는 환승 선택과 최단 경로 탐색은 SubwayGraph 담당이다.
- Edge에는 from_v와 to_v가 있어야 한다. 출발점이 자신인 간선만 받는다.

**직접 적용한 원칙은 S(단일 책임)다.** Vertex는 정점의 정보와 출발 연결만 관리한다. 비용 계산이나 탐색은 수행하지 않는다.

- O(개방·폐쇄): add_edge는 탑승·환승 종류를 검사하지 않는다. 같은 연결 규약(from_v)을 가진 간선이라면 등록 코드를 수정하지 않고 사용할 수 있다. 비용 계산의 확장성까지 이 클래스가 보장하는 것은 아니다.
- L: 상속 관계가 없어 직접 적용하는 사례가 없다.
- I: 공개 동작을 간선 등록 하나로 제한했다. 별도의 인터페이스 분리를 구현한 것은 아니다.
- D: 구체적인 Edge 클래스를 import하거나 생성하지 않고, 외부에서 받은 객체의 from_v만 사용한다. 파이썬의 속성 기반 연결 규약을 활용하지만, 프로젝트 전체의 의존 역전은 탐색 코드까지 확인해야 한다.

