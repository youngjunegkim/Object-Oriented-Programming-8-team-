"use strict";

// 노선 표시용 색 (경로 카드의 호선 칩)
const LINE_COLORS = {
  "1호선": "#0052A4", "2호선": "#00A84D", "3호선": "#EF7C1C", "4호선": "#00A5DE",
  "5호선": "#996CAC", "6호선": "#CD7C2F", "7호선": "#747F00", "8호선": "#E6186C",
  "9호선": "#BDB092", "수인분당선": "#F5A200", "신분당선": "#D4003B", "경의중앙선": "#77C4A3",
  "공항철도": "#0090D2", "경춘선": "#0C8E72", "경강선": "#003DA5", "서해선": "#8FC31F",
  "우이신설선": "#B0CE18", "신림선": "#6789CA", "인천1호선": "#7CA8D5", "인천2호선": "#ED8B00",
  "김포골드라인": "#A17800", "의정부경전철": "#FDA600", "용인에버라인": "#509F22",
};

const $ = (id) => document.getElementById(id);
const state = { meta: null, byLabel: new Map(), byName: new Map(), byCode: new Map() };

// ---------- 공통 ----------
async function api(name, params = {}) {
  const res = await fetch(`/api/${name}?${new URLSearchParams(params)}`);
  const body = await res.json();
  if (!res.ok) throw new Error(body.error || `요청 실패 (${res.status})`);
  return body;
}

function showError(err) {
  const box = $("error");
  if (!err) { box.hidden = true; return; }
  box.textContent = err.message || String(err);
  box.hidden = false;
}

function css(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function baseLayout(extra = {}) {
  return {
    paper_bgcolor: css("--surface"),
    plot_bgcolor: css("--surface"),
    font: { family: getComputedStyle(document.body).fontFamily, color: css("--text-secondary"), size: 12 },
    margin: { l: 48, r: 12, t: 12, b: 44 },
    hoverlabel: { bgcolor: css("--surface"), bordercolor: css("--border"), font: { color: css("--text-primary") } },
    xaxis: { gridcolor: css("--grid"), linecolor: css("--border"), tickfont: { color: css("--text-muted") }, fixedrange: true },
    yaxis: { gridcolor: css("--grid"), zerolinecolor: css("--border"), tickfont: { color: css("--text-muted") }, fixedrange: true },
    ...extra,
  };
}

const PLOT_CONFIG = { displayModeBar: false, responsive: true };

function fmtMin(seconds) {
  const m = Math.round(seconds / 60);
  return m >= 60 ? `${Math.floor(m / 60)}시간 ${m % 60}분` : `${m}분`;
}
const fmtPct = (v) => (v == null ? "—" : `${v.toFixed(1)}%`);
const fmtKm = (m) => (m == null ? "—" : `${(m / 1000).toFixed(1)}km`);
const SOURCE_LABEL = { measured: "실측", "measured-9": "실측(9월)", generated: "추정" };

function resolveStation(text) {
  const t = (text || "").trim();
  return state.byLabel.get(t) || state.byName.get(t) || null;
}

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") node.className = v;
    else if (k === "style") node.style.cssText = v;
    else node.setAttribute(k, v);
  }
  for (const c of children) node.append(c);
  return node;
}

// ---------- 탭 ----------
const rendered = {};
function selectTab(tab) {
  document.querySelectorAll(".tabs button").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.tab === tab)));
  document.querySelectorAll(".tab").forEach((s) => (s.hidden = s.id !== `tab-${tab}`));
  showError(null);
  try { localStorage.setItem("dashboard-tab", tab); } catch (e) { /* 저장 불가 환경 */ }
  if (!rendered[tab]) { rendered[tab] = true; ({ station: loadStation, heatmap: loadHeatmap, route: loadRoute })[tab](); }
  else window.dispatchEvent(new Event("resize")); // 숨겨진 상태에서 그려진 차트 크기 보정
}

// ---------- 1. 역별 혼잡도 ----------
async function loadDirections() {
  const st = resolveStation($("st-station").value);
  if (!st) return;
  try {
    const data = await api("directions", { station: st.code });
    const sel = $("st-direction");
    sel.replaceChildren(...data.directions.map((d) =>
      el("option", { value: JSON.stringify({ line: d.line, next: d.next_code }) }, `${d.line} · ${d.next_name} 방면`)));
    await loadStationChart(st);
  } catch (e) { showError(e); }
}

async function loadStationChart(st = resolveStation($("st-station").value)) {
  const raw = $("st-direction").value;
  if (!st || !raw) return;
  const dir = JSON.parse(raw);
  try {
    showError(null);
    const data = await api("station", { station: st.code, next: dir.next, line: dir.line });
    $("st-title").textContent = `${data.station} → ${data.next} (${data.line}) 시간대별 혼잡도`;
    const colors = [css("--series-1"), css("--series-2"), css("--series-3")];
    const traces = Object.entries(data.days).map(([day, d], i) => ({
      type: "scatter", mode: "lines+markers", name: day, x: data.slots, y: d.values,
      line: { color: colors[i], width: 2, shape: "linear" }, marker: { size: 5, color: colors[i] },
      connectgaps: false, hovertemplate: `${day} %{x}: %{y:.1f}%<extra></extra>`,
    }));
    Plotly.react("st-chart", traces, baseLayout({
      hovermode: "x unified",
      legend: { orientation: "h", y: 1.12, x: 0, font: { color: css("--text-primary") } },
      yaxis: { ...baseLayout().yaxis, title: { text: "혼잡도 (%)", font: { size: 12 } }, rangemode: "tozero" },
      xaxis: { ...baseLayout().xaxis, nticks: 14 },
      margin: { l: 56, r: 12, t: 36, b: 44 },
    }), PLOT_CONFIG);

    $("st-source").textContent = "데이터 출처: " + Object.entries(data.days)
      .map(([day, d]) => `${day} ${SOURCE_LABEL[d.source] || "—"}`).join(" · ");

    // KPI: 요일별 최대 혼잡 시간대
    const kpis = Object.entries(data.days).map(([day, d]) => {
      let best = -1;
      d.values.forEach((v, i) => { if (v != null && (best < 0 || v > d.values[best])) best = i; });
      const valid = d.values.filter((v) => v != null);
      const avg = valid.length ? valid.reduce((a, b) => a + b, 0) / valid.length : null;
      return el("div", { class: "kpi" },
        el("div", { class: "k" }, `${day} 최고 혼잡`),
        el("div", { class: "v" }, best < 0 ? "—" : fmtPct(d.values[best])),
        el("div", { class: "d" }, best < 0 ? "데이터 없음" : `${data.slots[best]} · 하루 평균 ${fmtPct(avg)}`));
    });
    $("st-kpis").replaceChildren(...kpis);
  } catch (e) { showError(e); }
}

function loadStation() {
  if (!$("st-station").value) $("st-station").value = state.byCode.get("0222")?.label || state.meta.stations[0].label;
  loadDirections();
}

// ---------- 2. 호선 히트맵 ----------
function fillBranches() {
  const line = state.meta.lines.find((l) => l.line === $("hm-line").value);
  $("hm-branch").replaceChildren(...line.branches.map((b) =>
    el("option", { value: b.branch }, `${b.branch} (${b.first}–${b.last})`)));
  updateDirectionLabels();
}

function updateDirectionLabels() {
  const line = state.meta.lines.find((l) => l.line === $("hm-line").value);
  const b = line.branches.find((x) => x.branch === $("hm-branch").value);
  const opts = $("hm-direction").options;
  opts[0].textContent = `${b.last} 방면`;
  opts[1].textContent = `${b.first} 방면`;
}

async function loadHeatmap() {
  try {
    showError(null);
    const data = await api("heatmap", {
      line: $("hm-line").value, branch: $("hm-branch").value,
      day: $("hm-day").value, reverse: $("hm-direction").value,
    });
    $("hm-title").textContent = `${data.line} ${data.branch} · ${data.direction}${data.circular ? " (순환)" : ""} · ${data.day}`;
    const heat = css("--heat").split(",").map((c) => c.trim());
    const colorscale = heat.map((c, i) => [i / (heat.length - 1), c]);
    const labels = data.rows.map((r, i) => `${i + 1}. ${r.station}${r.source === "generated" ? " *" : ""}`);
    const custom = data.rows.map((r) => data.slots.map(() => [r.next, SOURCE_LABEL[r.source] || "—"]));
    Plotly.react("hm-chart", [{
      type: "heatmap", x: data.slots, y: labels, z: data.rows.map((r) => r.values),
      customdata: custom, colorscale, zmin: 0, zmax: 120, xgap: 1, ygap: 1,
      hovertemplate: "%{y} → %{customdata[0]}<br>%{x} · <b>%{z:.1f}%</b> (%{customdata[1]})<extra></extra>",
      colorbar: { title: { text: "%", side: "top" }, thickness: 10, outlinewidth: 0, tickfont: { color: css("--text-muted") } },
    }], baseLayout({
      // 행 높이를 고정해 정거장 수만큼만 늘어나게 한다 (적은 구간에서 칸이 세로로 늘어지지 않도록)
      height: data.rows.length * (data.rows.length > 30 ? 18 : 26) + 60,
      margin: { l: 130, r: 12, t: 8, b: 44 },
      yaxis: { ...baseLayout().yaxis, autorange: "reversed", automargin: true, tickfont: { size: 11, color: css("--text-secondary") } },
      xaxis: { ...baseLayout().xaxis, side: "bottom", nticks: 14 },
    }), PLOT_CONFIG);
  } catch (e) { showError(e); }
}

// ---------- 3~5. 경로 분석 ----------
function renderCards(routes) {
  if (!routes.length) { $("rt-cards").replaceChildren(el("div", { class: "empty" }, "경로를 찾을 수 없습니다.")); return; }
  $("rt-cards").replaceChildren(...routes.map((r, idx) => {
    const legs = r.legs.map((leg) => {
      if (leg.type === "transfer") {
        return el("li", { class: "walk" }, el("span", { class: "chip" }, "환승"),
          el("div", {}, `${leg.station}: ${leg.from_line} → ${leg.to_line}`, el("div", { class: "meta" }, `도보 ${fmtMin(leg.seconds)}${leg.meters ? ` · ${leg.meters}m` : ""}`)));
      }
      const n = leg.stations.length - 1;
      return el("li", {}, el("span", { class: "chip", style: `background:${LINE_COLORS[leg.line] || "#777"}` }, leg.line),
        el("div", {}, `${leg.stations[0]} → ${leg.stations[n]}`,
          el("div", { class: "meta" }, `${n}개 역 · ${fmtMin(leg.seconds)} · ${leg.stations.slice(1, -1).join(", ") || "직행"}`)));
    });
    return el("article", { class: `route${idx === 0 ? " best" : ""}` },
      el("div", { class: "title" }, el("b", {}, r.label), el("span", { class: "same" }, r.same_as ? `${r.same_as}과 같은 경로` : "")),
      el("div", { class: "time" }, fmtMin(r.total_seconds)),
      el("div", { class: "stats" },
        el("div", {}, "환승", el("b", {}, `${r.transfers}회`)),
        el("div", {}, "정거장", el("b", {}, `${r.stops}개`)),
        el("div", {}, "거리", el("b", {}, fmtKm(r.meters))),
        el("div", {}, "평균 혼잡도", el("b", {}, fmtPct(r.avg_congestion)))),
      el("ul", { class: "legs" }, ...legs));
  }));
}

function renderSegments(segments) {
  if (!segments.length) { Plotly.purge("rt-seg"); $("rt-seg").replaceChildren(el("div", { class: "empty" }, "표시할 구간이 없습니다.")); return; }
  $("rt-seg").replaceChildren();
  let max = -1;
  segments.forEach((s, i) => { if (s.value != null && (max < 0 || s.value > segments[max].value)) max = i; });
  const x = segments.map((s, i) => `${i + 1}. ${s.from}→${s.to}`);
  Plotly.react("rt-seg", [{
    type: "bar", x, y: segments.map((s) => s.value),
    marker: { color: segments.map((_, i) => (i === max ? css("--series-2") : css("--neutral-bar"))) },
    customdata: segments.map((s) => [s.line, s.slot || "운행 시간 외", SOURCE_LABEL[s.source] || "—"]),
    hovertemplate: "%{x}<br>%{customdata[0]} · %{customdata[1]}<br><b>%{y:.1f}%</b> (%{customdata[2]})<extra></extra>",
  }], baseLayout({
    bargap: 0.25,
    margin: { l: 48, r: 12, t: 24, b: 90 },
    xaxis: { ...baseLayout().xaxis, tickangle: -45, tickfont: { size: 10, color: css("--text-muted") } },
    yaxis: { ...baseLayout().yaxis, title: { text: "혼잡도 (%)", font: { size: 12 } }, rangemode: "tozero" },
    annotations: max < 0 ? [] : [{
      x: x[max], y: segments[max].value, text: `최고 ${segments[max].value.toFixed(1)}%`, showarrow: false, yshift: 12,
      font: { color: css("--text-primary"), size: 12 },
    }],
  }), PLOT_CONFIG);
}

function renderDeparture(data, chosenSlot) {
  let min = -1;
  data.values.forEach((v, i) => { if (v != null && (min < 0 || v < data.values[min])) min = i; });
  const colors = data.values.map((_, i) => (i === min ? css("--series-3") : data.slots[i] === chosenSlot ? css("--series-1") : css("--neutral-bar")));
  Plotly.react("rt-dep", [{
    type: "bar", x: data.slots, y: data.values, marker: { color: colors },
    hovertemplate: "%{x} 출발<br><b>%{y:.1f}%</b><extra></extra>",
  }], baseLayout({
    bargap: 0.2,
    margin: { l: 48, r: 12, t: 24, b: 44 },
    xaxis: { ...baseLayout().xaxis, nticks: 12 },
    yaxis: { ...baseLayout().yaxis, title: { text: "평균 혼잡도 (%)", font: { size: 12 } }, rangemode: "tozero" },
    annotations: min < 0 ? [] : [{
      x: data.slots[min], y: data.values[min], text: `최저 ${data.slots[min]}`, showarrow: false, yshift: 12,
      font: { color: css("--text-primary"), size: 12 },
    }],
  }), PLOT_CONFIG);
}

function slotOf(time) {
  // service_time.congestion_slot과 같은 규칙으로 선택 시각이 속한 30분 시간대 표시
  const [h, m] = time.split(":").map(Number);
  return `${String(h).padStart(2, "0")}:${m < 30 ? "00" : "30"}`;
}

async function loadRoute() {
  if (!$("rt-start").value) $("rt-start").value = state.byCode.get("0150")?.label || "";
  if (!$("rt-end").value) $("rt-end").value = state.byCode.get("0222")?.label || "";
  const start = resolveStation($("rt-start").value);
  const end = resolveStation($("rt-end").value);
  if (!start || !end) { showError(new Error("목록에 있는 역을 선택하세요.")); return; }
  const day = $("rt-day").value;
  const time = $("rt-time").value || "08:00";
  try {
    showError(null);
    const [route, seg, dep] = await Promise.all([
      api("route", { start: start.code, end: end.code, day, time }),
      api("segments", { start: start.code, end: end.code, day, time }),
      api("departure", { start: start.code, end: end.code, day }),
    ]);
    renderCards(route.routes);
    renderSegments(seg.segments);
    renderDeparture(dep, slotOf(time));
  } catch (e) { showError(e); }
}

// ---------- 초기화 ----------
async function init() {
  try {
    state.meta = await api("meta");
  } catch (e) { showError(e); return; }
  const { stations, lines, days } = state.meta;
  for (const s of stations) {
    state.byLabel.set(s.label, s);
    state.byCode.set(s.code, s);
    if (s.label === s.name) state.byName.set(s.name, s);
  }
  $("station-list").replaceChildren(...stations.map((s) => el("option", { value: s.label })));
  document.querySelectorAll(".day-select").forEach((sel) => sel.replaceChildren(...days.map((d) => el("option", { value: d }, d))));
  $("hm-line").replaceChildren(...lines.map((l) => el("option", { value: l.line }, l.line)));
  $("hm-line").value = "2호선";
  fillBranches();

  $("st-station").addEventListener("change", loadDirections);
  $("st-direction").addEventListener("change", () => loadStationChart());
  $("hm-line").addEventListener("change", () => { fillBranches(); loadHeatmap(); });
  $("hm-branch").addEventListener("change", () => { updateDirectionLabels(); loadHeatmap(); });
  ["hm-direction", "hm-day"].forEach((id) => $(id).addEventListener("change", loadHeatmap));
  $("rt-go").addEventListener("click", loadRoute);
  ["rt-day", "rt-time"].forEach((id) => $(id).addEventListener("change", loadRoute));
  ["rt-start", "rt-end"].forEach((id) => $(id).addEventListener("keydown", (e) => { if (e.key === "Enter") loadRoute(); }));
  $("rt-swap").addEventListener("click", () => {
    [$("rt-start").value, $("rt-end").value] = [$("rt-end").value, $("rt-start").value];
    loadRoute();
  });

  document.querySelectorAll(".tabs button").forEach((b) => b.addEventListener("click", () => selectTab(b.dataset.tab)));
  let tab = "station";
  try { tab = localStorage.getItem("dashboard-tab") || tab; } catch (e) { /* 저장 불가 환경 */ }
  selectTab(["station", "heatmap", "route"].includes(tab) ? tab : "station");

  // 시스템 다크 모드 전환 시 차트 색 다시 적용
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
    for (const t of Object.keys(rendered)) rendered[t] = false;
    const current = document.querySelector('.tabs button[aria-selected="true"]').dataset.tab;
    selectTab(current);
  });
}

init();
