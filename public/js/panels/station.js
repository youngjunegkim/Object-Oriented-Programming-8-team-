// 역 패널: 선택한 역의 방향별 평일·토·일 혼잡도 비교 (/api/directions, /api/station).
import { api } from "../api.js";
import { state, update, subscribe } from "../state.js";
import { $, el, showError } from "../dom.js";
import { fmtPct, SOURCE_LABEL } from "../format.js";
import { LINE_COLORS } from "../colors.js";
import { css, baseLayout, slotMarker, PLOT_CONFIG } from "../charts.js";

let drawn = false;  // 차트가 그려져 있으면 시간대 표시만 옮긴다.

export function initStationPanel() {
  $("st-close").addEventListener("click", () => update({ station: null }));
  $("st-start").addEventListener("click", () => update({ start: state.station }));
  $("st-end").addEventListener("click", () => update({ end: state.station }));
  subscribe((changed) => {
    if ("station" in changed) load();
    if ("slot" in changed && drawn) Plotly.relayout("st-chart", { shapes: [slotMarker(state.slot)] });
  });
}

async function load() {
  const station = state.station;
  $("station-panel").hidden = !station;
  drawn = false;
  if (!station) return;
  $("st-name").textContent = station.label;
  $("st-lines").replaceChildren(...station.lines.map((line) =>
    el("span", { class: "line-chip", style: `--c:${LINE_COLORS[line] || "#777"}` }, line)));
  try {
    const data = await api("directions", { station: station.code });
    if (station !== state.station) return;  // 기다리는 동안 다른 역을 골랐으면 버린다.
    renderDirections(data.directions);
  } catch (e) { showError(e); }
}

// 방향 버튼: 호선마다 한 줄에 "OO 방면" 버튼을 나란히 둔다.
function renderDirections(directions) {
  const buttons = [];
  const rows = [...new Set(directions.map((d) => d.line))].map((line) => el("div", { class: "dir-row" },
    el("span", { class: "line-chip", style: `--c:${LINE_COLORS[line] || "#777"}`, title: line }, line),
    ...directions.filter((d) => d.line === line).map((d) => {
      const button = el("button", { type: "button", "aria-pressed": "false" }, `${d.next_name} 방면`);
      button.addEventListener("click", () => {
        buttons.forEach((b) => b.setAttribute("aria-pressed", String(b === button)));
        drawChart(d);
      });
      buttons.push(button);
      return button;
    })));
  $("st-directions").replaceChildren(...rows);
  buttons[0]?.click();
}

async function drawChart(dir) {
  const station = state.station;
  try {
    showError(null);
    const data = await api("station", { station: station.code, next: dir.next_code, line: dir.line });
    if (station !== state.station) return;
    const colors = [css("--series-1"), css("--series-2"), css("--series-3")];
    const traces = Object.entries(data.days).map(([day, d], i) => ({
      type: "scatter", mode: "lines", name: day, x: data.slots, y: d.values,
      line: { color: colors[i], width: 2 }, connectgaps: false,
      hovertemplate: `${day} %{x} · %{y:.1f}%<extra></extra>`,
    }));
    await Plotly.react("st-chart", traces, baseLayout({
      hovermode: "x unified",
      showlegend: true,
      legend: { orientation: "h", y: 1.15, x: 0, font: { color: css("--text-primary") } },
      margin: { l: 44, r: 8, t: 30, b: 40 },
      xaxis: { ...baseLayout().xaxis, nticks: 10 },
      shapes: [slotMarker(state.slot)],
    }), PLOT_CONFIG);
    drawn = true;

    $("st-source").textContent = "데이터 출처: " + Object.entries(data.days)
      .map(([day, d]) => `${day} ${SOURCE_LABEL[d.source] || "—"}`).join(" · ");

    // 요일별 가장 혼잡한 시간대와 하루 평균
    $("st-kpis").replaceChildren(...Object.entries(data.days).map(([day, d]) => {
      const valid = d.values.filter((v) => v != null);
      const peak = valid.length ? Math.max(...valid) : null;
      const avg = valid.length ? valid.reduce((a, b) => a + b, 0) / valid.length : null;
      return el("div", { class: "kpi" },
        el("div", { class: "k" }, `${day} 최고`),
        el("div", { class: "v" }, fmtPct(peak)),
        el("div", { class: "d" }, peak == null ? "데이터 없음" : `${data.slots[d.values.indexOf(peak)]} · 평균 ${fmtPct(avg)}`));
    }));
  } catch (e) { showError(e); }
}
