"""Data/Congestion/raw/ (실측 혼잡도 xlsx) + edges.csv → Data/Congestion/congestion.csv, generated_basis.csv.

- 실측: 서울교통공사 1~8호선(평일/토/일), 9호선(평일/휴일 → 토·일에 복사, 일반 열차만). 30분 단위 39칸.
- 실측 값은 "역 + 방향 = 그 역을 출발하는 열차"의 혼잡도라서 `그 역 → 그 방향 다음 역` 간선에 붙인다.
- 실측이 없는 간선은 생성한다: 같은 그룹(3도심까지 거리 5분 구간 × 도심행/도심발) 실측 간선의 시간칸별 평균.
- 0은 운행 없음으로 보고 빈칸으로 둔다. 생성 공식과 오차는 Data/README.md 참고.
API를 쓰지 않으므로 .env 인증키 없이 실행된다.
"""
import heapq
import re
import sys
import warnings
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "Data"
RAW = DATA / "Congestion" / "raw"
A_XLSX = RAW / "서울교통공사_지하철혼잡도정보_20260930.xlsx"
A9_XLSX = RAW / "2026년 9호선(종합) 역별 시간별 혼잡도 자료.xlsx"
CONGESTION_CSV = DATA / "Congestion" / "congestion.csv"
BASIS_CSV = DATA / "Congestion" / "generated_basis.csv"

sys.stdout.reconfigure(encoding="utf-8")
warnings.filterwarnings("ignore", message="Mean of empty slice")  # 운행 없는 시간칸은 평균이 NaN

DAYS = ["평일", "토요일", "일요일"]
SLOTS = [f"{h % 24:02d}:{m:02d}" for h in range(5, 25) for m in (0, 30)][1:]  # 05:30 ~ 00:30, 39칸
HUBS = ["시청", "강남", "여의도"]  # 서울시 도시기본계획 3도심
BINS = [0, 5, 10, 15, 20, 25, 30, np.inf]  # 도심까지 분
MIN_EDGES = 20  # 그룹 최소 실측 간선 수. 모자라면 안쪽 구간과 합친다

# (노선, 지선, 방향 라벨) → 그 방향 열차가 향하는 끝역. 상선 = 역번호 감소 쪽 (종착역의 0 행으로 확인)
TOWARD = {
    ("1호선", "본선", "상선"): "연천", ("1호선", "본선", "하선"): "구로",
    ("2호선", "성수지선", "외선"): "신설동", ("2호선", "성수지선", "내선"): "성수",
    ("2호선", "신도림지선", "내선"): "까치산", ("2호선", "신도림지선", "외선"): "신도림",
    ("3호선", "본선", "상선"): "대화", ("3호선", "본선", "하선"): "오금",
    ("4호선", "본선", "상선"): "진접", ("4호선", "본선", "하선"): "오이도",
    ("5호선", "본선", "상선"): "방화", ("5호선", "본선", "하선"): "강동",
    ("5호선", "하남선", "상선"): "강동", ("5호선", "하남선", "하선"): "하남검단산",
    ("5호선", "마천선", "상선"): "강동", ("5호선", "마천선", "하선"): "마천",
    ("6호선", "본선", "상선"): "응암", ("6호선", "본선", "하선"): "신내",
    ("7호선", "본선", "상선"): "장암", ("7호선", "본선", "하선"): "석남",
    ("8호선", "본선", "상선"): "별내", ("8호선", "본선", "하선"): "모란",
    ("9호선", "본선", "상선"): "중앙보훈병원", ("9호선", "본선", "하선"): "개화",
}
# 서울교통공사 파일의 특수행 (역번호, 방향) → (노선, 출발역, 도착역). 지선 분기점에서 갈래를 구분하는 행
SPECIAL = {
    (9001, "외선"): ("2호선", "성수", "건대입구"),
    (9002, "외선"): ("2호선", "성수", "용답"),
    (9003, "내선"): ("2호선", "신도림", "도림천"),
    (260, "외선"): ("2호선", "까치산", "신정네거리"),  # 우리 역코드는 0200
    (9005, "하선"): ("5호선", "강동", "둔촌동"),
    (9006, "하선"): ("6호선", "응암", "역촌"),
}


def main():
    stations = pd.read_csv(DATA / "Station" / "stations.csv", encoding="utf-8-sig", dtype=str)
    edges = pd.read_csv(DATA / "Edge" / "edges.csv", encoding="utf-8-sig", dtype=str)
    transfers = pd.read_csv(DATA / "Transfer" / "transfers.csv", encoding="utf-8-sig", dtype=str)
    edges["key"] = edges["from_code"] + ">" + edges["to_code"]
    code_of = {(r.line, r.name): r.station_code for r in stations.itertuples()}

    measured, source, problems = load_measured(edges, code_of)
    group = edge_groups(edges, transfers, stations)
    means, merged = group_means(measured, source, group)

    rows = []
    for e in edges.itertuples():
        for day in DAYS:
            vals = measured.get((e.key, day))
            src = source.get(e.key) if vals is not None else "generated"
            if vals is None:
                z, direction = group[e.key]
                vals = means[(merged[direction][z], direction, day)][0]
            rows.append({"line": e.line, "branch": e.branch, "from_code": e.from_code, "from_name": e.from_name,
                         "to_code": e.to_code, "to_name": e.to_name, "day": day, "source": src,
                         **dict(zip(SLOTS, np.round(vals, 1)))})
    out = pd.DataFrame(rows)
    out.to_csv(CONGESTION_CSV, index=False, encoding="utf-8-sig")  # utf-8-sig: 엑셀에서 한글이 안 깨지도록

    basis = []
    for (zones, direction, day), (vals, n) in sorted(means.items(), key=lambda x: (x[0][1], x[0][0], DAYS.index(x[0][2]))):
        hi = BINS[zones[-1] + 1]
        basis.append({"direction": direction, "min_from": BINS[zones[0]], "min_to": "" if hi == np.inf else hi,
                      "day": day, "n_edges": n, **dict(zip(SLOTS, np.round(vals, 1)))})
    pd.DataFrame(basis).to_csv(BASIS_CSV, index=False, encoding="utf-8-sig")

    print(f"혼잡도 {len(out)}행 (간선 {len(edges)}개 × 요일 {len(DAYS)}) → {CONGESTION_CSV.relative_to(ROOT)}")
    print(f"  source: {out['source'].value_counts().to_dict()}")
    print(f"생성 근거 {len(basis)}행 → {BASIS_CSV.relative_to(ROOT)}")
    print(f"실측 행 중 간선에 못 붙인 것: {len(problems)}건")
    for p in problems:
        print(f"  {p}")
    validate(measured, source, group, dict(zip(edges["key"], edges["line"])))


# ---------------------------------------------------------------- 실측 → 간선
def aliases(name):
    """역명 표기 차이를 흡수한 후보 이름 집합. 괄호 안 부기명도 후보로 넣는다."""
    name = str(name).strip()
    parts = [re.sub(r"\(.*?\)", "", name)] + re.findall(r"\((.*?)\)", name)
    out = set()
    for p in parts:
        p = re.sub(r"[.·\s]", "", p)
        if len(p) > 2 and p.endswith("역"):
            p = p[:-1]
        if p:
            out.add(p)
    return out


def slot_values(values, columns):
    """원본 시간 열(05:30~06:00, 24:00~24:30 등) → 39칸 배열. 0은 운행 없음이라 NaN."""
    slots = [f"{int(str(c)[:2]) % 24:02d}:{str(c)[3:5]}" for c in columns]
    s = pd.Series(list(values), index=slots).reindex(SLOTS).astype(float)
    return s.replace(0, np.nan).values


def load_measured(edges, code_of):
    """실측 xlsx → {(간선 key, 요일): 39칸}, {간선 key: source}, 못 붙인 행 목록."""
    hops = {}
    for (line, branch, label), end in TOWARD.items():
        g = edges[(edges["line"] == line) & (edges["branch"] == branch)]
        adj = defaultdict(list)
        for f, t in zip(g["from_code"], g["to_code"]):
            adj[f].append(t)
        dist, queue = {code_of[(line, end)]: 0}, [code_of[(line, end)]]
        for c in queue:  # 끝역에서 BFS: 끝역까지 몇 정거장인지
            for n in adj[c]:
                if n not in dist:
                    dist[n] = dist[c] + 1
                    queue.append(n)
        hops[(line, branch, label)] = dist
    special_keys = {code_of[(ln, f)] + ">" + code_of[(ln, t)] for ln, f, t in SPECIAL.values()}

    def edge_for(line, code, label):
        """(역, 방향) → 그 역을 출발하는 간선. 특수행이 가져간 간선은 제외한다."""
        out = edges[(edges["line"] == line) & (edges["from_code"] == code) & ~edges["key"].isin(special_keys)]
        hits = []
        for e in out.itertuples():
            if line == "2호선" and e.branch == "순환선":
                step = (int(e.to_code) - int(e.from_code)) % 43  # 0201~0243 순환, 외선 = 번호 증가
                if (label == "외선") == (step == 1):
                    hits.append(e.key)
            elif e.branch == "응암순환":
                if label == "하선":  # 한 방향 운행
                    hits.append(e.key)
            elif (line, e.branch, label) in hops:
                h = hops[(line, e.branch, label)]
                if h.get(e.to_code, 1e9) < h.get(e.from_code, 1e9):
                    hits.append(e.key)
        return hits

    measured, source, problems = {}, {}, []
    sheets = pd.read_excel(A_XLSX, sheet_name=None)
    for day in DAYS:
        d = sheets[day]
        for r in d.itertuples(index=False):
            line, no, name, label = r[0], int(r[1]), r[2], r[3]
            vals = slot_values(r[4:], d.columns[4:])
            if (no, label) in SPECIAL:
                ln, f, t = SPECIAL[(no, label)]
                keys = [code_of[(ln, f)] + ">" + code_of[(ln, t)]]
            elif no >= 9000 or no == 260:
                keys = []
            else:
                keys = edge_for(line, f"{no:04d}", label)
            if len(keys) == 1:
                measured[(keys[0], day)] = vals
                source[keys[0]] = "measured"
            elif not np.isnan(vals).all() or keys:  # 전부 0인 종착역 방향 행은 문제 아님
                problems.append(f"{day} {line} {name} {label}: 간선 {len(keys)}개")

    for label in ("상선", "하선"):
        for src_day, days in (("평일", ["평일"]), ("휴일", ["토요일", "일요일"])):
            d = pd.read_excel(A9_XLSX, sheet_name=f"{label}일반({src_day})", header=1)
            for r in d.itertuples(index=False):
                code = next((c for (ln, n), c in code_of.items() if ln == "9호선" and aliases(n) & aliases(r[0])), None)
                keys = edge_for("9호선", code, label) if code else []
                vals = slot_values(r[1:], d.columns[1:])
                if len(keys) == 1:
                    for day in days:
                        measured[(keys[0], day)] = vals
                    source[keys[0]] = "measured-9"
                elif not np.isnan(vals).all():
                    problems.append(f"{src_day} 9호선 {r[0]} {label}: 간선 {len(keys)}개")
    return measured, source, problems


# ---------------------------------------------------------------- 생성 공식
def edge_groups(edges, transfers, stations):
    """간선 key → (거리 구간 번호, 도심행/도심발). 거리는 3도심까지 최단 소요시간(분, 환승 포함)."""
    graph = defaultdict(dict)
    for f, t, s in zip(edges["from_code"], edges["to_code"], edges["seconds"].astype(float)):
        graph[f][t] = min(s, graph[f].get(t, np.inf))
    for f, t, s in zip(transfers["from_code"], transfers["to_code"], transfers["seconds"].astype(float)):
        graph[f][t] = min(s, graph[f].get(t, np.inf))
        graph[t][f] = min(s, graph[t].get(f, np.inf))

    hubs = stations.loc[stations["name"].isin(HUBS), "station_code"]
    dist = {c: 0.0 for c in hubs}
    pq = [(0.0, c) for c in hubs]
    while pq:  # 다익스트라 (출발점 여러 개)
        d, c = heapq.heappop(pq)
        if d > dist[c]:
            continue
        for n, w in graph[c].items():
            if d + w < dist.get(n, np.inf):
                dist[n] = d + w
                heapq.heappush(pq, (d + w, n))
    assert set(stations["station_code"]) <= dist.keys(), "도심에서 닿지 않는 역이 있음"

    d_from = edges["from_code"].map(dist) / 60
    d_to = edges["to_code"].map(dist) / 60
    zone = np.digitize(d_from, BINS[1:-1])
    direction = np.where(d_to < d_from, "도심행", "도심발")
    return dict(zip(edges["key"], zip(zone, direction)))


def group_means(measured, source, group, keys=None):
    """(합친 구간, 방향, 요일) → (39칸 평균, 실측 간선 수), 그리고 {방향: {구간: 합친 구간}}."""
    keys = sorted(source) if keys is None else keys
    merged = {}
    for direction in ("도심행", "도심발"):
        counts = defaultdict(int)
        for k in keys:
            if group[k][1] == direction:
                counts[group[k][0]] += 1
        z_map, acc = {}, []
        for z in range(len(BINS) - 1):
            acc.append(z)
            if sum(counts[x] for x in acc) >= MIN_EDGES:
                z_map.update({x: tuple(acc) for x in acc})
                acc = []
        if acc:  # 남은 바깥 구간은 직전 그룹에 붙인다
            prev = z_map[max(z_map)]
            z_map.update({x: prev + tuple(acc) for x in prev + tuple(acc)})
        merged[direction] = z_map

    pool = defaultdict(list)
    for k in keys:
        z, direction = group[k]
        for day in DAYS:
            if (k, day) in measured:
                pool[(merged[direction][z], direction, day)].append(measured[(k, day)])
    return {g: (np.nanmean(np.vstack(v), axis=0), len(v)) for g, v in pool.items()}, merged


def validate(measured, source, group, line_of):
    """노선 하나씩 실측을 숨기고 생성 공식으로 맞혀 본 오차 (README의 MAE 근거)."""
    meas = sorted(source)
    errs = []
    for held in sorted({line_of[k] for k in meas}):
        train = [k for k in meas if line_of[k] != held]
        means, merged = group_means(measured, source, group, train)
        for k in meas:
            if line_of[k] != held:
                continue
            z, direction = group[k]
            for day in DAYS:
                if (k, day) in measured:
                    e = means[(merged[direction][z], direction, day)][0] - measured[(k, day)]
                    errs.append(e[~np.isnan(e)])
    errs = np.concatenate(errs)
    print(f"\n교차검증 (노선 하나씩 숨기고 생성): MAE {np.abs(errs).mean():.1f}%p, 편향 {errs.mean():+.1f}%p, "
          f"오차 10%p 이내 {(np.abs(errs) <= 10).mean() * 100:.0f}%")


if __name__ == "__main__":
    main()
