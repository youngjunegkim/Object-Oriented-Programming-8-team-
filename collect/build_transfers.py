"""Data/Transfer/json/ → Data/Transfer/transfers.csv + 리포트.

한 행 = (노선 A의 역 X에 이웃 prev에서 도착) → (노선 B의 역 Y에서 이웃 next로 출발)하는 환승.
방향은 이웃역 코드로 정하고, API 방향 표기(상행/하행/내선/외선)는 사람이 읽기 위해 함께 둔다.
seconds는 걷는 시간(reqHr)이다. 열차 대기시간(wtngHr)은 시각마다 달라 쓰지 않는다.
API가 일부 방향 조합만 돌려준 환승은 fill_mirror()에서 반대로 걷는 값으로 채우고 note에 표시한다.
"""
import csv
import json
from collections import Counter, defaultdict

import api
from fetch_transfers import JSON_DIR, MANIFEST

TRANSFER_CSV = api.DATA / "Transfer" / "transfers.csv"
# API가 어느 시각에도 경로를 주지 않는 환승. 네이버 지도 도보 환승시간(분 단위)을 사람이 확인해 넣는다.
# (역, A호선, B호선, 초) — 양방향, 모든 진입·진출 방향 조합에 같은 값
MANUAL = [
    ("서울역", "경의중앙선", "1호선", 60),
    ("서울역", "경의중앙선", "4호선", 60),
    ("서울역", "경의중앙선", "공항철도", 240),
]
FIELDS = ["from_code", "from_name", "from_line", "from_prev_code", "from_prev_name", "from_dir",
          "to_code", "to_name", "to_line", "to_next_code", "to_next_name", "to_dir", "seconds", "meters", "note"]


def main():
    stations = {s["station_code"]: s for s in csv.DictReader(open(api.DATA / "Station" / "stations.csv", encoding="utf-8-sig"))}
    records = json.loads(MANIFEST.read_text(encoding="utf-8"))

    rows = []
    for r in records:
        if r["status"] != "ok":
            continue
        arrive, walk, depart = json.loads((JSON_DIR / r["file"]).read_text(encoding="utf-8"))["body"]["paths"]
        x, y = stations[r["from"]], stations[r["to"]]
        rows.append({
            "from_code": r["from"], "from_name": x["name"], "from_line": x["line"],
            "from_prev_code": r["prev"], "from_prev_name": stations[r["prev"]]["name"], "from_dir": arrive["upbdnbSe"],
            "to_code": r["to"], "to_name": y["name"], "to_line": y["line"],
            "to_next_code": r["next"], "to_next_name": stations[r["next"]]["name"], "to_dir": depart["upbdnbSe"],
            "seconds": walk["reqHr"], "meters": walk["stnSctnDstc"], "note": "",
        })
    filled, unfilled = fill_mirror(records, rows, stations)
    rows += filled + manual_rows(stations)
    rows.sort(key=lambda w: (w["from_name"], w["from_line"], w["to_line"], w["from_prev_code"], w["to_next_code"]))

    TRANSFER_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(TRANSFER_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    report(records, rows, stations, filled, unfilled)


def fill_mirror(records, rows, stations):
    """일부 방향 조합만 성공한 노선쌍의 빈 조합을 채운다.

    C에서 와서 X→Y 환승 후 B로 가는 환승은, B 반대편에서 와서 Y→X 환승 후 C 반대편으로 가는 환승과
    같은 승강장 쌍을 반대로 걷는다 (검증에서 93% 일치). 반대편 = 그 역의 다른 이웃,
    종점이라 이웃이 하나뿐이면 같은 승강장이므로 그 이웃 그대로. 분기역(이웃 3개 이상)은 정할 수 없어 채우지 않는다.
    """
    neighbors = defaultdict(set)
    for e in csv.DictReader(open(api.DATA / "Edge" / "edges.csv", encoding="utf-8-sig")):
        neighbors[e["to_code"]].add(e["from_code"])

    def opposite(station, neighbor):
        others = neighbors[station] - {neighbor}
        if not others:
            return neighbor
        return next(iter(others)) if len(others) == 1 else None

    value = {(w["from_prev_code"], w["from_code"], w["to_code"], w["to_next_code"]): w for w in rows}
    has_ok = {(r["from"], r["to"]) for r in records if r["status"] == "ok"}
    filled, unfilled = [], []
    for r in records:
        c, x, y, b = r["prev"], r["from"], r["to"], r["next"]
        if r["status"] == "ok" or (x, y) not in has_ok:
            continue
        b2, c2 = opposite(y, b), opposite(x, c)
        src = value.get((b2, y, x, c2)) if b2 and c2 else None
        note = "fix:mirror"
        if src is None:
            # 반대 조합도 없으면 같은 노선쌍(X→Y)의 다른 조합 평균
            same = [w for w in rows if (w["from_code"], w["to_code"]) == (x, y)]
            if not same:
                unfilled.append(r)
                continue
            src = {"seconds": round(sum(w["seconds"] for w in same) / len(same)), "meters": same[0]["meters"]}
            note = "fix:pair-mean"
        xs, ys = stations[x], stations[y]
        filled.append({
            "from_code": x, "from_name": xs["name"], "from_line": xs["line"],
            "from_prev_code": c, "from_prev_name": stations[c]["name"], "from_dir": "",
            "to_code": y, "to_name": ys["name"], "to_line": ys["line"],
            "to_next_code": b, "to_next_name": stations[b]["name"], "to_dir": "",
            "seconds": src["seconds"], "meters": src["meters"], "note": note,
        })
    return filled, unfilled


def manual_rows(stations):
    neighbors = defaultdict(set)
    for e in csv.DictReader(open(api.DATA / "Edge" / "edges.csv", encoding="utf-8-sig")):
        neighbors[e["to_code"]].add(e["from_code"])
    code_of = {(s["name"], s["line"]): code for code, s in stations.items()}

    rows = []
    for name, line_a, line_b, seconds in MANUAL:
        a, b = code_of[(name, line_a)], code_of[(name, line_b)]
        for x, y in [(a, b), (b, a)]:
            for prev in sorted(neighbors[x]):
                for nxt in sorted(neighbors[y]):
                    rows.append({
                        "from_code": x, "from_name": name, "from_line": stations[x]["line"],
                        "from_prev_code": prev, "from_prev_name": stations[prev]["name"], "from_dir": "",
                        "to_code": y, "to_name": name, "to_line": stations[y]["line"],
                        "to_next_code": nxt, "to_next_name": stations[nxt]["name"], "to_dir": "",
                        "seconds": seconds, "meters": "", "note": "fix:manual",
                    })
    return rows


def report(records, rows, stations, filled, unfilled):
    label = lambda code: f"{stations[code]['name']}({stations[code]['line']})"
    pairs = defaultdict(lambda: {"ok": 0, "fail": 0, "reasons": Counter()})
    for r in records:
        p = pairs[(r["from"], r["to"])]
        p[r["status"]] += 1
        if r["reason"]:
            p["reasons"][r["reason"].split(":")[0]] += 1

    found = [k for k, p in pairs.items() if p["ok"]]
    print(f"환승 {len(rows)}행 → {TRANSFER_CSV.relative_to(api.ROOT)}")
    print(f"환승 노선쌍(방향 포함) {len(found)}개, 환승역 {len({stations[x]['name'] for x, _ in found})}곳\n")

    print("== 환승 구간이 전혀 없는 후보 (동명이역이거나 API 경로 문제) ==")
    for (x, y), p in pairs.items():
        if not p["ok"]:
            print(f"  {label(x)} → {label(y)}: {dict(p['reasons'])}")

    print(f"\n== 일부 방향 조합만 성공 → 반대로 걷는 값으로 채움: {len(filled)}행, 못 채움: {len(unfilled)}행 ==")
    for r in unfilled:
        print(f"  못 채움: {label(r['prev'])}에서 와서 {label(r['from'])} → {label(r['to'])}, {label(r['next'])}로")

    # 반대로 걷는 환승은 같은 승강장 쌍이므로 값이 같아야 한다 (양쪽 이웃이 정확히 2개인 역만 확인)
    value = {(w["from_prev_code"], w["from_code"], w["to_code"], w["to_next_code"]): w["seconds"]
             for w in rows if not w["note"]}
    neighbors = defaultdict(set)
    for c, x, y, b in value:
        neighbors[x].add(c)
        neighbors[y].add(b)
    same = diff = 0
    for (c, x, y, b), sec in value.items():
        other_y, other_x = neighbors[y] - {b}, neighbors[x] - {c}
        if len(other_y) == 1 and len(other_x) == 1:
            key = (other_y.pop(), y, x, other_x.pop())
            if key in value:
                same += value[key] == sec
                diff += value[key] != sec
    print(f"\n== 반대로 걷는 환승 값 일치: 같음 {same} / 다름 {diff} ==")

    secs = sorted(w["seconds"] for w in rows)
    if secs:
        print(f"\n== 환승시간 분포: 최소 {secs[0]}초, 중앙 {secs[len(secs) // 2]}초, 최대 {secs[-1]}초 ==")
        for w in rows:
            if w["seconds"] > 600 or w["seconds"] <= 0:
                print(f"  확인 필요: {w['from_name']} {w['from_line']}→{w['to_line']} "
                      f"({w['from_prev_name']}에서 와서 {w['to_next_name']}로) {w['seconds']}초")


if __name__ == "__main__":
    main()
