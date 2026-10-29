"""Congestion_II: 기존 생성 공식(그룹 평균)에 역별 이용객 차이를 반영한 실험 버전.

생성값 = 그룹 평균 × (간선 이용객 지수 / 같은 그룹 실측 간선의 기하평균 지수) ^ α
- 그룹 평균, 실측 매핑은 collect/build_congestion.py와 같다 (함수를 그대로 가져다 쓴다).
- 이용객 지수 = 간선 양 끝 역(환승으로 이어진 역은 하나로 합침)의 그 시간대 승차+하차 인원.
  시간대 분포는 B1(시간대별, 월 합계), 요일 수준은 B2(일별)로 나눈다.
- α는 노선 단위 교차검증 오차가 가장 작은 값으로 고른다. α=0이면 기존 버전과 같다.
"""
import sys
import warnings
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / "collect"))
import build_congestion as base  # noqa: E402  실측 매핑, 그룹 공식 재사용
from build_congestion import DATA, DAYS, SLOTS, aliases  # noqa: E402

warnings.filterwarnings("ignore", message="Mean of empty slice")

B1_CSV = HERE / "raw" / "서울시 지하철 호선별 역별 시간대별 승하차 인원 정보_202609.csv"
B2_CSV = HERE / "raw" / "CARD_SUBWAY_MONTH_202609.csv"
HOLIDAYS = {20260924, 20260925, 20260926}  # 2026 추석 연휴 → 일요일로 본다
ALPHAS = np.round(np.arange(0, 1.01, 0.05), 2)

# 승하차 파일의 노선명 → 우리 노선 후보 (코레일 노선명은 여러 노선에 걸친다)
LINE_MAP = {
    "경부선": ["1호선"], "경원선": ["1호선", "경의중앙선"], "경인선": ["1호선"], "장항선": ["1호선"],
    "과천선": ["4호선"], "안산선": ["4호선"], "일산선": ["3호선"],
    "9호선2~3단계": ["9호선"],
    "경의선": ["경의중앙선", "서해선", "공항철도"], "중앙선": ["경의중앙선"],
    "분당선": ["수인분당선"], "수인선": ["수인분당선"],
    "공항철도 1호선": ["공항철도"],
}
HOUR_SLOT = {s: int(s[:2]) for s in SLOTS}  # 30분 칸 → 그 칸이 속한 시


def main():
    stations = pd.read_csv(DATA / "Station" / "stations.csv", encoding="utf-8-sig", dtype=str)
    edges = pd.read_csv(DATA / "Edge" / "edges.csv", encoding="utf-8-sig", dtype=str)
    transfers = pd.read_csv(DATA / "Transfer" / "transfers.csv", encoding="utf-8-sig", dtype=str)
    edges["key"] = edges["from_code"] + ">" + edges["to_code"]
    code_of = {(r.line, r.name): r.station_code for r in stations.itertuples()}
    line_of = dict(zip(edges["key"], edges["line"]))

    measured, source, _ = base.load_measured(edges, code_of)
    group = base.edge_groups(edges, transfers, stations)
    complex_of = station_complexes(stations, transfers)
    activity, matched, unmatched = load_activity(stations, complex_of)
    covered = covered_lines(stations, matched)
    log_idx = edge_log_index(edges[edges["line"].isin(covered)], complex_of, activity)

    # α 고르기: 노선 단위 교차검증
    scores = {a: cross_validate(a, measured, source, group, log_idx, line_of) for a in ALPHAS}
    alpha = min(scores, key=lambda a: scores[a]["MAE"])

    means, merged = base.group_means(measured, source, group)
    centers = group_centers(sorted(source), group, merged, log_idx)
    rows, ratio_rows = [], []
    for e in edges.itertuples():
        for day in DAYS:
            vals = measured.get((e.key, day))
            src = source.get(e.key) if vals is not None else "generated"
            ratio = adjust_ratio(e.key, day, group, merged, log_idx, centers)
            if vals is None:
                z, direction = group[e.key]
                vals = means[(merged[direction][z], direction, day)][0] * ratio ** alpha
            rows.append({"line": e.line, "branch": e.branch, "from_code": e.from_code, "from_name": e.from_name,
                         "to_code": e.to_code, "to_name": e.to_name, "day": day, "source": src,
                         **dict(zip(SLOTS, np.round(vals, 1)))})
            hourly = dict(zip([HOUR_SLOT[s] for s in SLOTS], ratio))
            ratio_rows.append({"line": e.line, "from_code": e.from_code, "from_name": e.from_name,
                               "to_code": e.to_code, "to_name": e.to_name, "day": day,
                               **{f"{h:02d}시": round(v, 3) for h, v in hourly.items()}})
    out = pd.DataFrame(rows)
    out.to_csv(HERE / "congestion.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(ratio_rows).to_csv(HERE / "activity_ratio.csv", index=False, encoding="utf-8-sig")
    # 그룹 평균은 ../Congestion/generated_basis.csv와 같으므로 따로 쓰지 않는다

    print(f"승하차 자료가 있는 노선 (조정 대상): {covered}")
    report(out, scores, alpha, unmatched, log_idx, edges, source)


# ---------------------------------------------------------------- 이용객 지수
def station_complexes(stations, transfers):
    """환승으로 이어진 역들을 하나의 묶음으로 (union-find). 역코드 → 묶음 대표 코드."""
    parent = {c: c for c in stations["station_code"]}

    def find(c):
        while parent[c] != c:
            parent[c] = parent[parent[c]]
            c = parent[c]
        return c

    for f, t in zip(transfers["from_code"], transfers["to_code"]):
        parent[find(f)] = find(t)
    return {c: find(c) for c in parent}


def match_station(stations, file_line, name):
    """승하차 파일의 (노선명, 역명) → 우리 역코드. 후보 노선 중 역명이 맞는 첫 역."""
    for line in LINE_MAP.get(file_line, [file_line]):
        cand = stations[(stations["line"] == line) & stations["name"].map(lambda n: bool(aliases(n) & aliases(name)))]
        if len(cand):
            return cand["station_code"].iloc[0]
    return None


def load_activity(stations, complex_of):
    """묶음 → {요일: 24시간 하루 평균 승하차 인원}.
    B1의 시간대 분포(월 합계)를 B2의 요일별 하루 평균 총량에 맞춰 나눈다."""
    b1 = pd.read_csv(B1_CSV, encoding="utf-8-sig")
    b2 = pd.read_csv(B2_CSV, encoding="utf-8-sig", index_col=False)
    date = pd.to_datetime(b2["사용일자"].astype(str))
    b2["day"] = np.where(b2["사용일자"].isin(HOLIDAYS) | (date.dt.dayofweek == 6), "일요일",
                         np.where(date.dt.dayofweek == 5, "토요일", "평일"))

    unmatched, matched = set(), set()
    hourly = defaultdict(lambda: np.zeros(24))  # 묶음 → 시간대별 월 합계 (인덱스 = 시)
    on = [f"{h:02d}시-{h + 1:02d}시 승차인원" for h in range(24)]
    off = [f"{h:02d}시-{h + 1:02d}시 하차인원" for h in range(24)]
    counts = b1[on].values + b1[off].values
    for (file_line, name), row in zip(zip(b1["호선명"], b1["지하철역"]), counts):
        code = match_station(stations, file_line, name)
        if code is None:
            unmatched.add(f"{file_line} {name}")
            continue
        matched.add(code)
        hourly[complex_of[code]] += row

    daily = defaultdict(lambda: defaultdict(float))  # 묶음 → 요일 → 하루 평균 총량
    n_days = b2.groupby("day")["사용일자"].nunique()
    for (line, name, day), g in b2.groupby(["노선명", "역명", "day"]):
        code = match_station(stations, line, name)
        if code is not None:
            daily[complex_of[code]][day] += (g["승차총승객수"] + g["하차총승객수"]).sum() / n_days[day]

    activity = {}
    for cx, h in hourly.items():
        share = h / h.sum()  # 시간대 분포 (월 전체)
        activity[cx] = {day: share * daily[cx][day] for day in DAYS if daily[cx][day] > 0}
    return activity, matched, sorted(unmatched)


def covered_lines(stations, matched, min_share=0.5):
    """자기 역의 절반 이상이 승하차 자료에 있는 노선만 조정한다.
    (예: 신분당선은 자료가 없어서, 판교 지수가 경강선 개찰구만으로 잡히는 왜곡을 막는다)"""
    share = stations["station_code"].isin(matched).groupby(stations["line"]).mean()
    return sorted(share[share >= min_share].index)


def edge_log_index(edges, complex_of, activity):
    """(간선, 요일) → 24시간 log(양 끝 역 이용객 평균). 승하차 자료가 없는 끝은 빼고, 둘 다 없으면 없음."""
    out = {}
    for e in edges.itertuples():
        for day in DAYS:
            ends = [activity[cx][day] for cx in (complex_of[e.from_code], complex_of[e.to_code])
                    if cx in activity and day in activity[cx]]
            if ends:
                out[(e.key, day)] = np.log(np.mean(ends, axis=0) + 1)
    return out


def group_centers(train_keys, group, merged, log_idx):
    """(합친 구간, 방향, 요일) → 그룹 실측 간선의 평균 log 지수 (= 기하평균)."""
    pool = defaultdict(list)
    for k in train_keys:
        z, direction = group[k]
        for day in DAYS:
            if (k, day) in log_idx:
                pool[(merged[direction][z], direction, day)].append(log_idx[(k, day)])
    return {g: np.mean(v, axis=0) for g, v in pool.items()}


def adjust_ratio(key, day, group, merged, log_idx, centers):
    """39칸 조정 비율 (지수 / 그룹 기하평균). 지수가 없으면 1."""
    z, direction = group[key]
    g = (merged[direction][z], direction, day)
    if (key, day) not in log_idx or g not in centers:
        return np.ones(len(SLOTS))
    ratio24 = np.exp(log_idx[(key, day)] - centers[g])
    return np.array([ratio24[HOUR_SLOT[s]] for s in SLOTS])


# ---------------------------------------------------------------- 검증과 리포트
def cross_validate(alpha, measured, source, group, log_idx, line_of):
    """실측 노선 하나씩 숨기고 생성했을 때의 오차."""
    meas = sorted(source)
    errs, preds = [], []
    for held in sorted({line_of[k] for k in meas}):
        train = [k for k in meas if line_of[k] != held]
        means, merged = base.group_means(measured, source, group, train)
        centers = group_centers(train, group, merged, log_idx)
        for k in meas:
            if line_of[k] != held:
                continue
            z, direction = group[k]
            for day in DAYS:
                if (k, day) in measured:
                    p = means[(merged[direction][z], direction, day)][0] \
                        * adjust_ratio(k, day, group, merged, log_idx, centers) ** alpha
                    e = p - measured[(k, day)]
                    ok = ~np.isnan(e)
                    errs.append(e[ok])
                    preds.append(p[ok])
    errs, preds = np.concatenate(errs), np.concatenate(preds)
    return {"MAE": np.abs(errs).mean(), "편향": errs.mean(), "10%p 이내": (np.abs(errs) <= 10).mean() * 100,
            "예측 표준편차": preds.std(), "예측 100%+": (preds >= 100).mean() * 100}


def report(out, scores, alpha, unmatched, log_idx, edges, source):
    print(f"혼잡도 {len(out)}행 → Data/Congestion_II/congestion.csv, source: {out['source'].value_counts().to_dict()}")
    print(f"승하차 자료와 매칭 안 된 역: {len(unmatched)}개 {unmatched}")
    gen_keys = edges.loc[~edges["key"].isin(source), "key"]
    with_idx = sum((k, "평일") in log_idx for k in gen_keys)
    print(f"생성 간선 {len(gen_keys)}개 중 이용객 지수가 있는 간선: {with_idx}개 (나머지는 그룹 평균 그대로)")

    print("\n[α별 교차검증] (실측 노선 하나씩 숨기고 생성)")
    df = pd.DataFrame(scores).T.round(1)
    df.index.name = "α"
    print(df.to_string())
    print(f"→ 채택 α = {alpha}")

    gen = out[out["source"] == "generated"]
    meas = out[out["source"] != "generated"]
    v_gen, v_meas = gen[SLOTS].stack(), meas[SLOTS].stack()
    print("\n[값의 다양성] 실측 / 생성")
    print(f"  표준편차 {v_meas.std():.1f} / {v_gen.std():.1f}, 최대 {v_meas.max():.1f} / {v_gen.max():.1f}, "
          f"100%+ 칸 {(v_meas >= 100).mean() * 100:.2f}% / {(v_gen >= 100).mean() * 100:.2f}%")
    wk = gen[gen["day"] == "평일"]
    print(f"  평일 생성 간선 {len(wk)}개의 고유 시간 패턴: {wk[SLOTS].round(1).astype(str).agg('|'.join, axis=1).nunique()}종류")


if __name__ == "__main__":
    main()
