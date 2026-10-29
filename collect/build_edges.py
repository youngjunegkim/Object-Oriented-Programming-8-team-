"""Data/Edge/json/ → Data/Station/stations.csv, Data/Edge/edges.csv + 시드 대조 리포트.

- 역 하나 = (호선, 역코드). 같은 이름이라도 호선이 다르면 다른 역이다.
- 간선은 방향이 있다 (A→B, B→A를 각각 한 행). 시간은 초, 거리는 미터 그대로 둔다.
- 혼잡도는 시간대별이라 여기 두지 않고 build_congestion.py가 Data/Congestion/에 따로 만든다.
- API 원본 오류는 apply_fixes()에서 사람이 보정하고 note 컬럼에 사유를 남긴다 (Data/README.md 참고).
"""
import csv
import json
from collections import Counter, defaultdict

import api
from seed_lines import routes

JSON_DIR = api.DATA / "Edge" / "json"
STATION_CSV = api.DATA / "Station" / "stations.csv"
EDGE_CSV = api.DATA / "Edge" / "edges.csv"
ONEWAY = {("6호선", "응암순환")}


def usable(record):
    """간선으로 쓸 응답인지. 시드에 없는 역(예: 운천)을 거친 경우는 실제 노선이므로 쓴다."""
    if record["status"] == "ok":
        return True
    return record["status"] == "warn" and record["reason"].startswith("시드에 없는 역")


def main():
    records = json.loads((JSON_DIR / "manifest.json").read_text(encoding="utf-8"))

    # 시드 노선마다 API 노선명 결정 (가장 많이 나온 이름)
    api_line_of = {}
    for line in {r["line"] for r in records}:
        names = Counter(r["api_line"] for r in records if r["line"] == line and usable(r))
        api_line_of[line] = names.most_common(1)[0][0] if names else None

    stations = {}  # stnCd → row
    edges = {}  # (from_code, to_code) → row
    conflicts, wrong_line, skipped = [], [], []
    for r in records:
        if not usable(r):
            skipped.append(r)
            continue
        if r["api_line"] != api_line_of[r["line"]]:
            wrong_line.append(r)
            continue
        data = json.loads((JSON_DIR / r["file"]).read_text(encoding="utf-8"))
        for seg in data["body"]["paths"]:
            dpt, arv = seg["dptreStn"], seg["arvlStn"]
            for stn in (dpt, arv):
                stations.setdefault(stn["stnCd"], {
                    "station_code": stn["stnCd"], "station_no": stn["stnNo"], "name": stn["stnNm"],
                    "line": r["line"], "api_line": stn["lineNm"],
                })
            key = (dpt["stnCd"], arv["stnCd"])
            row = {
                "line": r["line"], "branch": r["branch"],
                "from_code": dpt["stnCd"], "from_name": dpt["stnNm"],
                "to_code": arv["stnCd"], "to_name": arv["stnNm"],
                "seconds": seg["reqHr"], "meters": seg["stnSctnDstc"], "note": "",
            }
            if key in edges and (edges[key]["seconds"], edges[key]["meters"]) != (row["seconds"], row["meters"]):
                conflicts.append((edges[key], row))
            edges.setdefault(key, row)

    fixes = apply_fixes(edges)

    # 지선은 보정이 끝난 간선 기준으로 매긴다 (가짜 경유로 붙은 지선이 남지 않도록)
    branches = defaultdict(set)
    for e in edges.values():
        branches[e["from_code"]].add(e["branch"])
        branches[e["to_code"]].add(e["branch"])
    write_csv(STATION_CSV, sorted(stations.values(), key=lambda s: (s["line"], s["station_code"])),
              ["station_code", "station_no", "name", "line", "api_line", "branch"],
              lambda s: {**s, "branch": "/".join(sorted(branches[s["station_code"]]))})
    write_csv(EDGE_CSV, list(edges.values()),
              ["line", "branch", "from_code", "from_name", "to_code", "to_name", "seconds", "meters", "note"])

    report(records, stations, edges, api_line_of, skipped, wrong_line, conflicts, fixes)


def apply_fixes(edges):
    """API 원본 오류 보정. 바꾼 내용을 문자열 목록으로 돌려준다."""
    fixes = []

    # 1. 5호선 강동 분기: 마천선 응답에 하남선 역(하남검단산, 길동)이 0m 구간으로 끼어 있음 → 합쳐서 강동↔둔촌동
    GANGDONG, HANAM_END, DUNCHON, GILDONG = "2549", "2566", "2555", "2550"
    t_out = edges.pop((GANGDONG, HANAM_END))["seconds"] + edges.pop((HANAM_END, DUNCHON))["seconds"]
    t_in = edges.pop((DUNCHON, GILDONG))["seconds"] + edges[(GILDONG, GANGDONG)]["seconds"]
    for (a, a_name, b, b_name, sec) in [(GANGDONG, "강동", DUNCHON, "둔촌동", t_out), (DUNCHON, "둔촌동", GANGDONG, "강동", t_in)]:
        edges[(a, b)] = {
            "line": "5호선", "branch": "마천선", "from_code": a, "from_name": a_name, "to_code": b, "to_name": b_name,
            "seconds": sec, "meters": 0, "note": "fix:branch-merge",
        }
        fixes.append(f"5호선 {a_name}→{b_name}: 가짜 경유 합침 {sec}초")

    # 2. 인천2호선 독정→검암: 도착 시각이 출발보다 빨라 84,873초로 나옴 → 시간표 기반 추정 120초
    edge = edges[("3206", "3207")]
    fixes.append(f"인천2호선 독정→검암: {edge['seconds']}초 → 120초")
    edge.update(seconds=120, note="fix:timetable")

    # 3. 반대 방향이 없는 간선 → 반대 방향 값 복사 (단방향 노선 제외)
    for (a, b), e in list(edges.items()):
        if (b, a) not in edges and (e["line"], e["branch"]) not in ONEWAY:
            edges[(b, a)] = {
                **e, "from_code": b, "from_name": e["to_name"], "to_code": a, "to_name": e["from_name"],
                "note": "fix:mirror",
            }
            fixes.append(f"{e['line']} {e['to_name']}→{e['from_name']}: 반대 방향 값 복사 {e['seconds']}초")

    # 5. 거리 0m는 '거리 미제공' → 빈칸 (시간은 그대로)
    zero = [e for e in edges.values() if e["meters"] == 0]
    for e in zero:
        e["meters"] = ""
    fixes.append(f"거리 0m → 빈칸: {len(zero)}개")
    return fixes


def write_csv(path, rows, fields, transform=lambda r: r):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:  # utf-8-sig: 엑셀에서 한글이 안 깨지도록
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(transform(row))


def report(records, stations, edges, api_line_of, skipped, wrong_line, conflicts, fixes):
    print(f"역 {len(stations)}개 → {STATION_CSV.relative_to(api.ROOT)}")
    print(f"간선 {len(edges)}개 → {EDGE_CSV.relative_to(api.ROOT)}\n")

    print("== 사람이 보정한 내용 ==")
    for f in fixes:
        print(f"  {f}")
    long = [e for e in edges.values() if e["seconds"] > 600]
    print(f"  600초 초과 간선: {len(long)}개\n")

    print("== 노선명 대응 (시드 → API) ==")
    for line, name in api_line_of.items():
        print(f"  {line} → {name}")

    # 노선·지선별 역 개수와 시드 대조
    seed_names = defaultdict(set)
    for line, branch, names, _ in routes():
        seed_names[(line, branch)].update(names)
    api_names = defaultdict(set)
    for e in edges.values():
        api_names[(e["line"], e["branch"])].update([e["from_name"], e["to_name"]])

    print("\n== 노선·지선별 역 개수 (시드 / API) ==")
    for key, names in seed_names.items():
        got = api_names.get(key, set())
        only_seed, only_api = sorted(names - got), sorted(got - names)
        mark = "" if not (only_seed or only_api) else "  <-- 차이"
        print(f"  {key[0]} {key[1]}: {len(names)} / {len(got)}{mark}")
        if only_seed:
            print(f"      시드에만: {only_seed}")
        if only_api:
            print(f"      API에만: {only_api}")

    # 한쪽 방향만 있는 간선
    print("\n== 한쪽 방향만 있는 간선 (단방향 노선 제외) ==")
    for (a, b), e in edges.items():
        if (b, a) not in edges and (e["line"], e["branch"]) not in ONEWAY:
            print(f"  {e['line']} {e['branch']}: {e['from_name']}→{e['to_name']} (반대 방향 없음)")

    print("\n== 쓰지 않은 응답 ==")
    for r in skipped:
        print(f"  {r['line']} {r['branch']} {r['from']}→{r['to']}: {r['status']} {r['reason']}")
    for r in wrong_line:
        print(f"  {r['line']} {r['branch']} {r['from']}→{r['to']}: API 노선 {r['api_line']} (기대 {api_line_of[r['line']]})")

    print(f"\n== 같은 간선인데 값이 다른 경우: {len(conflicts)}건 ==")
    for old, new in conflicts:
        print(f"  {old['from_name']}→{old['to_name']}: {old['seconds']}초/{old['meters']}m vs {new['seconds']}초/{new['meters']}m")

    dup = Counter((s["name"], s["line"]) for s in stations.values())
    print("\n== 같은 노선에 같은 이름이 여러 코드로 있는 역 ==")
    for (name, line), n in dup.items():
        if n > 1:
            codes = [s["station_code"] for s in stations.values() if (s["name"], s["line"]) == (name, line)]
            print(f"  {line} {name}: {codes}")


if __name__ == "__main__":
    main()
