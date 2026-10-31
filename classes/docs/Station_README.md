# Station — 물리적 역 하나

## 역할

같은 물리적 역에 속한 호선별 정점(Vertex)을 묶는다.
예를 들어 교대역 Station 하나에 교대역 2호선·3호선 Vertex가 속한다.

## 속성과 메서드

| 항목 | 의미 |
|---|---|
| `name` | 물리적 역의 대표 이름(str) |
| `vertices` | 이 역에 등록한 Vertex들의 목록(list) |
| `__init__(name)` | 이름을 저장하고 빈 정점 목록을 만든다 |
| `add_vertex(vertex)` | 정점을 목록에 등록한다. 반환값은 None |

주요 메서드는 보고서의 `add_vertex()` 하나뿐이다.

## 사용 예

프로젝트 최상위에서 실행한다.

```python
from classes import Station, Vertex

station = Station("교대")
v2 = Vertex("0223", station, "2호선")
v3 = Vertex("0330", station, "3호선")

station.add_vertex(v2)
station.add_vertex(v3)

print(station.name)           # 교대
print(len(station.vertices))  # 2
```

Vertex 생성만으로 자동 등록되지는 않는다. `add_vertex()`를 명시적으로 호출한다.

## 코드 읽는 순서

1. `self`는 현재 Station 객체다.
2. `__init__()`에서 이름을 저장하고 `vertices = []`로 빈 목록을 만든다.
3. `vertex.station is self`는 정점의 소속이 현재 역 객체인지 확인한다.
4. 이미 등록된 같은 객체면 아무것도 하지 않는다.
5. 같은 역코드를 가진 다른 객체면 ValueError를 낸다.
6. `append()`로 목록 끝에 정점을 추가한다.

빈 이름도 ValueError로 막는다. 모든 검사는 생성자와 기존 메서드 안에서 처리한다.

## 다른 코드와의 경계

- CSV는 CongestionDataLoader가 읽는다.
- 같은 물리적 역으로 묶을 정점을 결정하는 작업은 SubwayGraph.build()가 한다.
- 역 이름만 같다고 묶으면 안 된다. 신촌·양평처럼 이름이 같아도 다른 역이 있다.
- 총신대입구·이수처럼 이름이 달라도 같은 환승역인 경우가 있어 환승 자료도 확인해야 한다.
- Station은 파일 읽기, 환승 판정, 경로 탐색을 하지 않는다.
- 역코드는 호선별 정점을 식별하므로 Vertex에 저장한다.


**직접 적용한 원칙은 S(단일 책임)다.** Station은 역 이름과 소속 정점의 등록·관리만 맡는다. 파일 형식이나 탐색 알고리즘이 바뀌어도 이 클래스의 책임은 그대로다.

- O(개방·폐쇄): 호선 이름별 분기 없이 정점을 등록하므로, 다른 호선 정점을 추가해도 add_vertex 코드를 바꿀 필요가 없다. 이것만으로 모든 확장에 O가 충족된다고 주장하지 않는다.
- L: 상속 관계가 없어 직접 적용하는 사례가 없다.
- I: 공개 동작을 정점 등록 하나로 제한했다. 별도의 인터페이스 분리를 구현한 것은 아니다.
- D: Vertex 객체를 외부에서 전달받지만, 이것만으로 의존 역전을 충족했다고 주장하지 않는다.

