# collect

서울교통공사 최단경로 API로 지하철 데이터를 수집해 `../Data/`에 CSV로 만드는 코드.
인증키는 `../.env`의 `SERVICE_KEY`에서 읽는다.

실행 순서: `fetch_lines.py` → `build_edges.py` → `fetch_transfers.py` → `build_transfers.py`
(이미 받은 응답은 캐시에서 읽으므로 다시 실행해도 API를 다시 호출하지 않는다)

## 파일

**api.py**
API 호출 공통 함수. 응답을 JSON 파일로 캐시하고, 호출 간 0.2초 대기, 네트워크 오류 시 재시도한다.

**seed_lines.py**
노선·지선별 역 목록. API에 역 목록 기능이 없어서 이 목록의 양 끝 역으로 노선을 조회한다.

**fetch_lines.py**
노선마다 양 끝 역을 왕복 조회해 `Data/Edge/json/`에 저장한다.
다른 노선을 타거나 빈 경로가 오면 역 목록을 반으로 나눠 다시 조회한다.

**build_edges.py**
`Data/Edge/json/` → `stations.csv`, `edges.csv`.
API 오류 보정을 적용하고 역 목록과의 차이를 리포트한다.

**fetch_transfers.py**
환승역마다 진입·진출 방향 조합을 모두 조회해 `Data/Transfer/json/`에 저장한다.
다른 역에서 환승해 버리면 그 역을 환승 제외역으로 지정해 다시 조회한다.

**build_transfers.py**
`Data/Transfer/json/` → `transfers.csv`.
API가 빠뜨린 방향 조합과 서울역 수동 입력값을 채운다.
