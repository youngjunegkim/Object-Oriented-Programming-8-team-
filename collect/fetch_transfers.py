"""2단계 호출: 환승역의 방향별 환승시간. 결과는 Data/Transfer/json/에 저장.

환승 후보 = 이름이 같은 역이 여러 노선에 있는 경우 + 이름이 다른 환승역(ALIASES).
후보 X(노선 A의 역) → Y(노선 B의 역)마다, X로 들어오는 이웃 C와 Y에서 나가는 이웃 B의 모든 조합을
C→B, X 경유, 역코드 검색으로 호출한다. 응답이 정확히 C→X, X→Y(환승), Y→B 세 구간이면 채택한다.
동명이역(양평, 신촌 등)은 API가 환승 구간을 주지 않으므로 자연히 걸러진다.
"""
import csv
import json
from collections import defaultdict

import api

JSON_DIR = api.DATA / "Transfer" / "json"
MANIFEST = JSON_DIR / "manifest.json"
ALIASES = [(("총신대입구", "4호선"), ("이수", "7호선"))]
MAX_EXCLUDE = 3  # 다른 역에서 환승해 버릴 때 그 역을 제외하고 다시 부르는 최대 횟수


def load_graph():
    stations = list(csv.DictReader(open(api.DATA / "Station" / "stations.csv", encoding="utf-8-sig")))
    edges = list(csv.DictReader(open(api.DATA / "Edge" / "edges.csv", encoding="utf-8-sig")))
    incoming, outgoing = defaultdict(set), defaultdict(set)
    for e in edges:
        outgoing[e["from_code"]].add(e["to_code"])
        incoming[e["to_code"]].add(e["from_code"])
    return stations, incoming, outgoing


def candidate_groups(stations):
    by_name = defaultdict(list)
    for s in stations:
        by_name[s["name"]].append(s["station_code"])
    groups = [codes for codes in by_name.values() if len(codes) > 1]
    code_of = {(s["name"], s["line"]): s["station_code"] for s in stations}
    groups += [[code_of[a], code_of[b]] for a, b in ALIASES]
    return groups


def check(data, c, x, y, b):
    """응답이 C→X, X→Y(환승), Y→B 세 구간인지. 맞으면 None, 아니면 이유."""
    if not data:
        return "응답 없음"
    if api.result_code(data) != "00":
        return f"{api.result_code(data)} {api.result_msg(data)}"
    if not data.get("body"):
        return f"body 없음: {json.dumps(data, ensure_ascii=False)[:200]}"
    got = [(s["dptreStn"]["stnCd"], s["arvlStn"]["stnCd"], s["trsitYn"]) for s in data["body"]["paths"]]
    want = [(c, x, "N"), (x, y, "Y"), (y, b, "N")]
    if got != want:
        return f"경로 다름: {got}"
    return None


def fetch_one(c, x, y, b):
    """C→B를 X 경유로 호출. API가 X를 지나기만 하고 다른 역에서 환승하면,
    그 환승역을 exclTrfstns로 제외하고 다시 호출한다 (최대 MAX_EXCLUDE회). (마지막 파일 경로, 실패 이유) 반환."""
    params = {"dptreStn": c, "arvlStn": b, "thrghStns": x, "stationValueType": "code", "searchType": "transfer"}
    excluded = []
    for attempt in range(MAX_EXCLUDE + 1):
        suffix = f"__ex{attempt}" if attempt else ""
        path = JSON_DIR / f"{x}_{y}__{c}_{b}{suffix}.json"
        data = api.call({**params, "exclTrfstns": ",".join(excluded)} if excluded else params, path)
        reason = check(data, c, x, y, b)
        if reason is None or not reason.startswith("경로 다름") or not data["body"]["paths"]:
            return path, reason
        # 응답 경로에서 X가 아닌 곳의 환승 → 그 환승의 진입 쪽 역코드를 제외 목록에 추가
        others = [s["dptreStn"]["stnCd"] for s in data["body"]["paths"]
                  if s["trsitYn"] == "Y" and s["dptreStn"]["stnCd"] not in (x, y, c, b)]
        new = [code for code in others if code not in excluded]
        if not new:
            return path, reason
        excluded += new
    return path, reason


def main():
    stations, incoming, outgoing = load_graph()
    jobs = []
    for codes in candidate_groups(stations):
        for x in codes:
            for y in codes:
                if x != y:
                    jobs += [(c, x, y, b) for c in sorted(incoming[x]) for b in sorted(outgoing[y])]
    print(f"호출 대상 {len(jobs)}건")

    records = []
    for i, (c, x, y, b) in enumerate(jobs, 1):
        path, reason = fetch_one(c, x, y, b)
        records.append({"prev": c, "from": x, "to": y, "next": b, "file": path.name,
                        "status": "ok" if reason is None else "fail", "reason": reason})
        if i % 100 == 0:
            print(f"  {i}/{len(jobs)} (이번 실행 호출 {api.calls}건)")

    JSON_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    ok = sum(r["status"] == "ok" for r in records)
    print(f"완료: 호출 {api.calls}건, 채택 {ok}건, 실패 {len(records) - ok}건")


if __name__ == "__main__":
    main()
