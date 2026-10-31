# Station — 물리적 역 하나

교대역처럼 같은 장소에 있는 역의 호선별 정점을 묶는다.
코드: [station.py](../station.py)

```text
교대 Station
 ├─ 교대 2호선 Vertex
 └─ 교대 3호선 Vertex
```

## 속성

| 속성 | 의미 |
|---|---|
| `name` | 역 이름 문자열 |
| `vertices` | 소속 Vertex들의 리스트 |

## 1. 생성자: Station(name)

**역할:** 역 이름과 빈 정점 목록을 가진 Station 객체를 만든다.

- **입력 인자:** 비어 있지 않은 역 이름 문자열. 앞뒤 공백은 제거한다.
- **생성 결과의 자료형: Station 객체.** `name`은 역 이름 **문자열**, `vertices`는 Vertex 객체들을 담는 **리스트**다. 처음에는 빈 리스트다.

사용 예시: 교대역 객체를 생성한다. 생성자는 이름과 빈 정점 목록을 준비하며, 마지막 print()는 저장된 이름을 확인하기 위한 코드다.

```python
from classes import Station, Vertex

station = Station("교대")
print(station.name)
```

실행 결과: 문자열 하나가 화면에 출력된다. 생성자가 이름을 출력하는 것은 아니다.

```text
교대
```

## 2. add_vertex(vertex)

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


## 등록할 때 알아둘 점

- `Vertex(..., station, ...)`은 정점에 소속 역을 알려준다. 역의 `vertices` 리스트에 넣으려면 `station.add_vertex(vertex)`를 별도로 호출한다.
- `add_vertex()`의 None 반환은 실패라는 뜻이 아니다. 등록 결과는 `station.vertices`에 저장되므로, 별도 데이터를 돌려주지 않는 것이다.
- 이미 등록한 같은 정점 객체를 다시 전달하면 추가하지 않는다. 다른 역 소속이거나, 같은 역코드의 다른 객체를 등록하면 오류가 난다.
- 같은 이름의 역을 자동으로 합치지 않는다. 경의중앙선 신촌과 2호선 신촌은 서로 다른 Station으로 만들어야 한다.

## 발표할 SOLID 원칙

**S — 단일 책임:** Station은 물리적 역과 소속 정점 관리만 담당한다. CSV 읽기·환승 판단·경로 탐색은 다른 코드가 맡는다.
