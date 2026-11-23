// 호선 히트맵 패널: 지도에서 호선을 하나만 고르면 그 호선의 역 × 시간대 혼잡도를 보여 준다 (/api/heatmap).
// 지선·방향은 이 패널 안에서만 쓰는 값이고, 요일·시간대는 화면 전체 상태(state)를 따른다.
import { api } from "../api.js";
import { state, update, subscribe } from "../state.js";
import { $, el, showError } from "../dom.js";
import { SOURCE_LABEL } from "../format.js";
import { LINE_COLORS, HEAT_STOPS } from "../colors.js";
import { css, baseLayout, slotMarker, PLOT_CONFIG } from "../charts.js";

const ZMAX = HEAT_STOPS.at(-1)[0];
const COLORSCALE = HEAT_STOPS.map(([v, c]) => [v / ZMAX, c]);

let line = null;       // 지금 보여 주는 호선
let branch = null;     // null이면 서버가 첫 지선(본선)을 고른다.
let reverse = false;
let drawn = false;
let clickBound = false;

export function initHeatmapPanel() {
  $("hm-close").addEventListener("click", () => update({ lines: new Set() }));
  subscribe((changed) => {
    if ("lines" in changed) {
      const next = state.lines.size === 1 ? [...state.lines][0] : null;
      if (next !== line) {
        line = next;
        branch = null;
        reverse = false;
        load();
      }
    } else if ("day" in changed && line) {
      load();
    }
    if ("slot" in changed && drawn) Plotly.relayout("hm-chart", { shapes: [slotMarker(state.slot)] });
  });
}

async function load() {
  $("heatmap-panel").hidden = !line;
  drawn = false;
  if (!line) return;
  const requested = { line, branch, reverse, day: state.day };
  try {
    showError(null);
    const params = { line, day: state.day, reverse: reverse ? "1" : "0" };
    if (branch) params.branch = branch;
    const data = await api("heatmap", params);
    // 기다리는 동안 호선·지선·방향·요일이 바뀌었으면 버린다.
    if (line !== requested.line || branch !== requested.branch || reverse !== requested.reverse || state.day !== requested.day) return;
    renderHead(data);
    renderControls(data);
    renderChart(data);
  } catch (e) { showError(e); }
}

function renderHead(data) {
  $("hm-line").replaceChildren(el("span", { class: "line-chip", style: `--c:${LINE_COLORS[data.line] || "#777"}` }, data.line));
  $("hm-title").textContent = `${data.branch} · ${data.direction}${data.circular ? " (순환)" : ""}`;
  $("hm-when").textContent = `${data.day} · 역 ${data.rows.length}구간`;
}

// 지선 버튼(지선이 둘 이상일 때)과 방향 버튼
function renderControls(data) {
  const current = data.branches.find((b) => b.branch === data.branch);
  const branchButtons = data.branches.length < 2 ? [] : data.branches.map((b) => {
    const button = el("button", { type: "button", "aria-pressed": String(b.branch === data.branch), title: `${b.first} – ${b.last} · ${b.count}개 역` }, b.branch);
    button.addEventListener("click", () => { branch = b.branch; reverse = false; load(); });
    return button;
  });
  $("hm-branches").hidden = !branchButtons.length;
  $("hm-branches").replaceChildren(...branchButtons);

  const labels = data.circular
    ? ["정방향", "역방향"]
    : [`${current.last} 방면`, `${current.first} 방면`];
  $("hm-direction").replaceChildren(...labels.map((label, i) => {
    const button = el("button", { type: "button", "aria-pressed": String(data.reverse === (i === 1)) }, label);
    button.addEventListener("click", () => {
      if (reverse === (i === 1)) return;
      branch = data.branch;
      reverse = i === 1;
      load();
    });
    return button;
  }));
}

function renderChart(data) {
  // 같은 역 이름이 두 번 나오는 순환선도 행이 겹치지 않도록 번호를 붙인다.
  const labels = data.rows.map((r, i) => `${i + 1}. ${r.station}${r.source === "generated" ? " *" : ""}`);
  const custom = data.rows.map((r) => data.slots.map(() => [r.next, SOURCE_LABEL[r.source] || "운행 없음"]));
  Plotly.react("hm-chart", [{
    type: "heatmap", x: data.slots, y: labels, z: data.rows.map((r) => r.values),
    customdata: custom, colorscale: COLORSCALE, zmin: 0, zmax: ZMAX, xgap: 1, ygap: 1,
    hoverongaps: false,
    hovertemplate: "%{y} → %{customdata[0]}<br>%{x} · <b>%{z:.1f}%</b> (%{customdata[1]})<extra></extra>",
    colorbar: { thickness: 8, outlinewidth: 0, len: 0.6, tickfont: { size: 10, color: css("--text-muted") }, ticksuffix: "%" },
  }], baseLayout({
    // 행 높이를 고정해 정거장 수만큼만 늘어나게 한다.
    height: Math.max(160, data.rows.length * 16 + 60),
    margin: { l: 110, r: 8, t: 8, b: 40 },
    yaxis: { ...baseLayout().yaxis, autorange: "reversed", automargin: true, rangemode: undefined, tickfont: { size: 10, color: css("--text-secondary") } },
    xaxis: { ...baseLayout().xaxis, nticks: 10 },
    shapes: [slotMarker(state.slot)],
  }), PLOT_CONFIG);
  drawn = true;
  if (!clickBound) {
    clickBound = true;
    $("hm-chart").on("plotly_click", (event) => update({ slot: event.points[0].x }));  // 칸을 누르면 지도도 그 시간대로
  }
}
