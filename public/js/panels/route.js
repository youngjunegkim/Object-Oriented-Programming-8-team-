// 경로 패널: 경로 카드, 선택한 경로의 구간별 혼잡도, 출발 시간대 비교 (/api/route, /api/departure).
// 출발역·도착역·요일·시간대 중 하나가 바뀌면 다시 조회한다.
import { api } from "../api.js";
import { state, update, subscribe } from "../state.js";
import { $, el, showError } from "../dom.js";
import { fmtMin, fmtPct, fmtKm, SOURCE_LABEL } from "../format.js";
import { LINE_COLORS } from "../colors.js";
import { css, baseLayout, PLOT_CONFIG } from "../charts.js";

let timer = null;
let depClickBound = false;

export function initRoutePanel({ byLabel }) {
  const pick = (id) => byLabel.get($(id).value.trim()) || null;
  $("route-form").addEventListener("submit", (event) => {
    event.preventDefault();
    const start = pick("start");
    const end = pick("end");
    if (!start || !end) { showError(new Error("목록에 있는 역을 선택하세요.")); return; }
    update({ start, end });
  });
  $("swap").addEventListener("click", () => update({ start: state.end, end: state.start }));
  $("rt-clear").addEventListener("click", () => update({ start: null, end: null, route: null }));

  subscribe((changed) => {
    if ("start" in changed || "end" in changed) {
      $("start").value = state.start?.label || "";
      $("end").value = state.end?.label || "";
      schedule(0);
    } else if ("day" in changed || "slot" in changed) {
      schedule(300);  // 슬라이더를 끄는 동안 요청이 몰리지 않게 잠시 기다린다.
    }
  });
}

function schedule(delay) {
  clearTimeout(timer);
  timer = setTimeout(search, delay);
}

async function search() {
  const { start, end, day, slot } = state;
  $("route-panel").hidden = !(start && end);
  if (!start || !end) {
    if (state.route) update({ route: null });
    return;
  }
  try {
    showError(null);
    const params = { start: start.code, end: end.code, day };
    const [route, dep] = await Promise.all([
      api("route", { ...params, time: slot }),
      api("departure", params),
    ]);
    if (start !== state.start || end !== state.end || day !== state.day || slot !== state.slot) return;  // 오래된 응답

    $("rt-title").textContent = `${start.name} → ${end.name}`;
    $("rt-when").textContent = `${day} ${slot} 출발 기준`;
    const chosen = route.routes.find((r) => r.key === state.route?.key) || route.routes[0] || null;
    renderCards(route.routes, chosen);
    renderRides(chosen ? chosen.rides : []);
    renderDeparture(dep);
    update({ route: chosen });
  } catch (e) { showError(e); }
}

function renderCards(routes, chosen) {
  if (!routes.length) {
    $("rt-cards").replaceChildren(el("div", { class: "empty" }, "경로를 찾을 수 없습니다."));
    return;
  }
  const cards = routes.map((r) => {
    const legs = r.legs.map((leg) => {
      if (leg.type === "transfer") {
        return el("li", {}, el("span", { class: "walk-chip" }, "환승"),
          el("div", {}, `${leg.station} ${leg.from_line} → ${leg.to_line}`,
            el("div", { class: "meta" }, `도보 ${fmtMin(leg.seconds)}${leg.meters ? ` · ${leg.meters}m` : ""}`)));
      }
      const n = leg.stations.length - 1;
      return el("li", {}, el("span", { class: "line-chip", style: `--c:${LINE_COLORS[leg.line] || "#777"}` }, leg.line),
        el("div", {}, `${leg.stations[0]} → ${leg.stations[n]}`,
          el("div", { class: "meta" }, `${n}개 역 · ${fmtMin(leg.seconds)}`)));
    });
    const card = el("article", { class: `route-card${r === chosen ? " selected" : ""}`, tabindex: "0" },
      el("div", { class: "top" }, el("span", { class: "label" }, r.label), el("span", { class: "same" }, r.same_as ? `${r.same_as}과 같은 경로` : "")),
      el("div", { class: "time" }, fmtMin(r.total_seconds)),
      el("div", { class: "stats" },
        el("span", {}, "환승", el("b", {}, `${r.transfers}회`)),
        el("span", {}, "정거장", el("b", {}, `${r.stops}개`)),
        el("span", {}, "거리", el("b", {}, fmtKm(r.meters))),
        el("span", {}, "평균 혼잡", el("b", {}, fmtPct(r.avg_congestion)))),
      el("ul", { class: "legs" }, ...legs));
    const choose = () => {
      cards.forEach((c) => c.classList.toggle("selected", c === card));
      renderRides(r.rides);
      update({ route: r });
    };
    card.addEventListener("click", choose);
    card.addEventListener("keydown", (event) => { if (event.key === "Enter") choose(); });
    return card;
  });
  $("rt-cards").replaceChildren(...cards);
}

function renderRides(rides) {
  if (!rides.length) {
    Plotly.purge("rt-seg");
    $("rt-seg").replaceChildren(el("div", { class: "empty" }, "표시할 구간이 없습니다."));
    return;
  }
  let max = -1;
  rides.forEach((s, i) => { if (s.value != null && (max < 0 || s.value > rides[max].value)) max = i; });
  const x = rides.map((s, i) => `${i + 1}. ${s.from}`);
  Plotly.react("rt-seg", [{
    type: "bar", x, y: rides.map((s) => s.value),
    marker: { color: rides.map((_, i) => (i === max ? css("--series-2") : css("--neutral-bar"))) },
    customdata: rides.map((s) => [s.to, s.line, s.slot || "운행 시간 외", SOURCE_LABEL[s.source] || "—"]),
    hovertemplate: "%{x} → %{customdata[0]}<br>%{customdata[1]} · %{customdata[2]}<br><b>%{y:.1f}%</b> (%{customdata[3]})<extra></extra>",
  }], baseLayout({
    bargap: 0.25,
    margin: { l: 44, r: 8, t: 16, b: 80 },
    xaxis: { ...baseLayout().xaxis, tickangle: -50, tickfont: { size: 10, color: css("--text-muted") } },
  }), PLOT_CONFIG);
}

function renderDeparture(data) {
  let min = -1;
  data.values.forEach((v, i) => { if (v != null && (min < 0 || v < data.values[min])) min = i; });
  const colors = data.values.map((_, i) => {
    if (i === min) return css("--series-3");
    return data.slots[i] === state.slot ? css("--series-1") : css("--neutral-bar");
  });
  Plotly.react("rt-dep", [{
    type: "bar", x: data.slots, y: data.values, marker: { color: colors },
    hovertemplate: "%{x} 출발 · <b>%{y:.1f}%</b><extra></extra>",
  }], baseLayout({
    bargap: 0.2,
    xaxis: { ...baseLayout().xaxis, nticks: 10 },
  }), PLOT_CONFIG);
  if (!depClickBound) {
    depClickBound = true;
    $("rt-dep").on("plotly_click", (event) => update({ slot: event.points[0].x }));
  }
}
