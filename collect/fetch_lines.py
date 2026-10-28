"""1단계 호출: 노선/지선마다 시점→종점, 종점→시점을 searchType=transfer로 호출해 Data/Edge/json/에 저장.

응답이 한 노선만 타지 않으면(환승 포함, 노선 변경, 시드에 없는 역 경유) 역 목록을 반으로 나눠 다시 호출한다.
결과 목록은 Data/Edge/json/manifest.json에 남기고 build_edges.py가 이를 읽는다.
"""
import json

import api
from seed_lines import routes

JSON_DIR = api.DATA / "Edge" / "json"
MANIFEST = JSON_DIR / "manifest.json"
FOREIGN_LIMIT = 0.2  # 시드에 없는 역 비율이 이보다 크면 다른 경로로 본다


def check(segments, seed):
    """응답 구간이 시드 노선 하나만 따라갔는지 확인. 문제가 없으면 None, 있으면 이유 문자열."""
    if not segments:
        return "빈 경로 (resultCode 00인데 paths가 비어 있음)"
    if any(s["trsitYn"] == "Y" for s in segments):
        return "환승 포함"
    lines = {s["dptreStn"]["lineNm"] for s in segments} | {s["arvlStn"]["lineNm"] for s in segments}
    if len(lines) > 1:
        return f"여러 노선: {sorted(lines)}"
    names = [segments[0]["dptreStn"]["stnNm"]] + [s["arvlStn"]["stnNm"] for s in segments]
    foreign = [n for n in names if n not in seed]
    if len(foreign) > FOREIGN_LIMIT * len(names):
        return f"시드에 없는 역 경유: {foreign}"
    return None


def fetch(line, branch, stations, direction, seed, records, depth=0):
    dpt, arv = stations[0], stations[-1]
    path = JSON_DIR / f"{api.safe_name(line)}_{api.safe_name(branch)}__{api.safe_name(dpt)}__{api.safe_name(arv)}.json"
    data = api.call({"dptreStn": dpt, "arvlStn": arv, "searchType": "transfer"}, path)
    record = {"line": line, "branch": branch, "direction": direction, "from": dpt, "to": arv, "file": path.name}
    indent = "  " * (depth + 1)

    if data is None:
        records.append({**record, "status": "error", "reason": "응답 없음"})
        print(f"{indent}[error] {dpt}→{arv} 응답 없음")
        return
    code = api.result_code(data)
    if code != "00":
        records.append({**record, "status": "api_error", "reason": f"{code} {api.result_msg(data)}"})
        print(f"{indent}[api {code}] {dpt}→{arv} {api.result_msg(data)}")
        return

    segments = data["body"]["paths"]
    reason = check(segments, seed)
    if reason and len(stations) > 2:
        print(f"{indent}[split] {dpt}→{arv}: {reason}")
        mid = len(stations) // 2
        fetch(line, branch, stations[: mid + 1], direction, seed, records, depth + 1)
        fetch(line, branch, stations[mid:], direction, seed, records, depth + 1)
        return

    api_line = segments[0]["dptreStn"]["lineNm"] if segments else None
    records.append({**record, "status": "warn" if reason else "ok", "reason": reason, "api_line": api_line})
    tag = f"[warn] {reason}" if reason else "[ok]"
    print(f"{indent}{tag} {dpt}→{arv} ({api_line}, {len(segments)}구간)")


def main():
    JSON_DIR.mkdir(parents=True, exist_ok=True)
    records = []
    for line, branch, stations, oneway in routes():
        print(f"{line} {branch}: {stations[0]} ~ {stations[-1]} ({len(stations)}역)")
        seed = set(stations)
        fetch(line, branch, stations, "forward", seed, records)
        if not oneway:
            fetch(line, branch, stations[::-1], "backward", seed, records)

    MANIFEST.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    bad = [r for r in records if r["status"] != "ok"]
    print(f"\n완료: 호출 {api.calls}건, 기록 {len(records)}건, 문제 {len(bad)}건")


if __name__ == "__main__":
    main()
