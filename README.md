# 시간대별 서울 지하철 혼잡도 경로 추천 시스템

서울 지하철의 시간대별 혼잡도와 역간 소요시간, 환승시간을 이용하여 여러 경로를 비교해 주는 대시보드 웹사이트이다. 사용자가 출발역, 도착역, 요일, 출발 시간대를 입력하면 최단시간 경로와 혼잡도가 낮은 경로, 환승이 적은 경로를 확인할 수 있도록 구현할 예정입니다.

현재는 클래스 구조와 객체 간 상호작용을 설계하고 있으며 배포 주소에는 프로젝트 안내 화면이 표시됩니다.

## 대시보드 주소

https://object-oriented-programming-8-team.vercel.app/

## 주요 기능

- 출발역, 도착역, 요일, 출발 시간대 입력
- 다익스트라 알고리즘을 이용한 경로탐색
- 최단시간 경로와 설정한 허용시간 이내의 대안 경로 제공
- 경로별 총 소요시간, 평균 혼잡도, 환승 횟수 비교
- 노선과 방향에 따른 구간별 혼잡도 조회
- 시간대별 혼잡도 그래프와 히트맵 제공

## 사용 데이터

| 데이터 | 사용 목적 |
| --- | --- |
| 서울교통공사 1호선부터 8호선까지 지하철 혼잡도 정보 | 평일, 토요일, 일요일의 역별, 방향별, 30분 단위 혼잡도 조회 |
| 서울교통공사 역간거리 및 소요시간 정보 | 같은 호선의 인접 역 연결과 이동시간 설정 |
| 서울교통공사 환승역 거리 및 소요시간 정보 | 환승역의 호선 연결과 환승시간 설정 |

데이터셋마다 역 이름과 열 구성이 다를 수 있으므로 `CongestionDataLoader`에서 역 이름과 요일, 시간대 형식을 통일하여 사용할 예정.

## 그래프 구성

지하철 노선은 역과 구간으로 이루어진 그래프로 표현합니다.

- `Station`: 실제 물리적인 역
- `Vertex`: 역과 호선의 조합으로 만든 그래프 정점
- `RideEdge`: 같은 호선의 인접한 두 정점을 연결
- `TransferEdge`: 같은 환승역에 속한 서로 다른 호선의 정점을 연결

예를 들어 교대역은 하나의 정점으로 합치지 않고 `교대역 2호선 Vertex`와 `교대역 3호선 Vertex`로 나눈다. 두 정점은 환승시간을 가진 `TransferEdge`로 연결합니다.

```text
교대역 Station
 ├─ 교대역 2호선 Vertex
 └─ 교대역 3호선 Vertex
          ↑
    TransferEdge로 연결
```

## 클래스 설계

### 1. CongestionDataLoader

혼잡도 엑셀의 평일, 토요일, 일요일 시트와 역간 소요시간, 환승시간 데이터를 읽고 정리합니다.

**주요 속성**

- `file_path`: 읽을 데이터 파일의 경로
- `days`: 평일, 토요일, 일요일 목록
- `time_slots`: 30분 단위 시간대 목록

**주요 메서드**

- `load()`: 요일별 시트를 읽어 저장
- `get_rows(day)`: 선택한 요일의 행 목록 반환
- `normalize_name(name)`: 서로 다른 역 이름 표기를 하나로 통일

### 2. Station과 Vertex

`Station`은 여러 호선을 묶는 실제 역이고, `Vertex`는 역과 호선 단위의 그래프 정점입니다.

**Station 주요 속성 및 메서드**

- `name`: 역 이름
- `vertices`: 해당 역의 호선별 Vertex 목록
- `is_transfer()`: 두 개 이상의 Vertex를 가진 환승역인지 확인
- `add_vertex(vertex)`: 호선별 Vertex 등록

**Vertex 주요 속성 및 메서드**

- `station`: 소속 Station
- `line`: 호선
- `edges`: 해당 정점에서 출발하는 Edge 목록
- `add_edge(edge)`: 출발 가능한 Edge 등록

### 3. Edge, RideEdge, TransferEdge

`Edge`는 두 Vertex를 연결하는 추상 클래스이며 이동 종류에 따라 `RideEdge`와 `TransferEdge`로 나눕니다.

**공통 속성**

- `from_v`: 출발 Vertex
- `to_v`: 도착 Vertex
- `minutes`: 구간 소요시간 또는 환승시간

**RideEdge 추가 속성**

- `direction`: 상선, 하선, 내선, 외선 등의 운행 방향
- `congestion[day][slot]`: 요일과 시간대별 혼잡도

**주요 메서드**

- `get_cost(day, slot)`: 이동 비용 계산
- `RideEdge.get_congestion(day, slot)`: 해당 요일과 시간대의 혼잡도 반환

`RideEdge`는 소요시간과 혼잡도 가중치를 이용해 비용을 계산하고, `TransferEdge`는 환승시간을 비용으로 사용합니다. 같은 메서드를 이동 종류에 따라 다르게 동작시키기 위해 오버라이딩과 다형성을 적용합니다.

### 4. SubwayGraph

전체 Station, Vertex, Edge를 생성하고 관리하며 경로를 탐색합니다.

**주요 속성**

- `stations`: 역 이름을 키로 사용하는 Station 목록
- `vertices`: 역과 호선 조합을 키로 사용하는 Vertex 목록
- `edges`: 전체 Edge 목록
- `line_order`: 호선별 운행 순서로 정렬된 Vertex 목록

**주요 메서드**

- `build(loader)`: 정제된 데이터로 Station, Vertex, Edge 생성
- `find_routes(start, goal, day, slot, tolerance)`: 최단시간 경로와 허용시간 이내의 대안 경로 탐색
- `get_line_edges(line, direction)`: 선택한 호선과 방향의 RideEdge를 노선 순서대로 반환

### 5. Route

탐색된 경로 하나의 정보를 저장하고 비교에 필요한 값을 계산합니다.

**주요 속성**

- `edges`: 경로가 지나는 Edge의 순서 목록
- `day`: 계산 기준 요일
- `slot`: 계산 기준 시간대

**주요 메서드**

- `total_time()`: 경로의 총 소요시간 계산
- `avg_congestion()`: 이동 구간의 평균 혼잡도 계산
- `transfer_count()`: 환승 횟수 계산

### 6. DashboardView

사용자 입력을 받아 `SubwayGraph`에 경로를 요청하고 탐색 결과를 화면에 출력합니다.

**주요 속성**

- `graph`: 사용하는 SubwayGraph 객체
- 선택 상태: 호선, 방향, 요일, 시간대

**주요 메서드**

- `render_route_cards()`: 추천 경로별 비교 카드 표시
- `render_line_strip()`: 노선도 위에 구간별 혼잡도 표시
- `render_edge_chart()`: 선택한 구간의 시간대별 혼잡도 그래프 표시
- `render_heatmap()`: 구간과 시간대별 혼잡도 히트맵 표시

## 객체 간 상호작용

1. `CongestionDataLoader`가 혼잡도와 소요시간 데이터를 읽고 역 이름을 통일합니다.
2. `SubwayGraph.build()`가 노선 순서에 따라 Station과 Vertex를 생성합니다.
3. 같은 호선의 인접한 Vertex는 `RideEdge`로 연결하고, 환승역의 다른 호선 Vertex는 `TransferEdge`로 연결합니다.
4. 사용자가 출발역, 도착역, 요일, 시간대를 선택하면 `DashboardView`가 `SubwayGraph.find_routes()`를 호출합니다.
5. 다익스트라 탐색 중 각 Edge의 `get_cost()`가 호출되며, `RideEdge`와 `TransferEdge`가 서로 다른 방법으로 비용을 계산합니다.
6. 탐색된 `Route`가 총 소요시간, 평균 혼잡도, 환승 횟수를 계산합니다.
7. `DashboardView`가 경로 비교 카드와 혼잡도 그래프, 히트맵을 화면에 표시합니다.

```text
데이터 파일
  ↓
CongestionDataLoader
  ↓
SubwayGraph.build()
  ↓
Station, Vertex, RideEdge, TransferEdge
  ↓
SubwayGraph.find_routes()
  ↓
Route
  ↓
DashboardView
```

## 대시보드 화면 구성

- **경로 비교 카드**: 경로별 소요시간, 평균 혼잡도, 환승 횟수 표시
- **노선별 구간 혼잡도**: 노선도 위 구간의 혼잡도를 색상으로 표시
- **구간별 시간대 혼잡도**: 선택한 구간의 하루 혼잡도 변화를 그래프로 표시
- **히트맵**: 여러 구간과 시간대의 혼잡도를 색상으로 비교

## 실행 방법

현재 배포된 페이지는 프로젝트 안내용 정적 HTML입니다. 저장소를 내려받은 뒤 `index.html` 파일을 브라우저에서 열면 확인할 수 있습니다.

```bash
git clone https://github.com/youngjunegkim/Object-Oriented-Programming-8-team-.git
```

최종 대시보드 구현에 필요한 패키지 설치 방법과 실행 명령은 개발 완료 후 이 항목에 추가할 예정입니다.

## 배포 방법

이 저장소의 `main` 브랜치는 Vercel 프로젝트와 연결되어 있습니다. `main` 브랜치에 변경사항을 올리면 아래 주소에 자동으로 반영됩니다.

https://object-oriented-programming-8-team.vercel.app/
