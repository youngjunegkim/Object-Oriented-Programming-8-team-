// 지도 위 조작: 호선 선택, 줌 버튼, 범례.
import { state, update, subscribe } from "../state.js";
import { $, el } from "../dom.js";
import { LINE_COLORS, HEAT_STOPS } from "../colors.js";

export function initMapControls({ lines, map }) {
  // 호선 선택: 고른 호선만 색이 들어가고, "전체"는 선택을 비운다.
  const all = el("button", { class: "chip all", type: "button" }, "전체");
  all.addEventListener("click", () => update({ lines: new Set() }));
  const chips = lines.map((line) => {
    const chip = el("button", { class: "chip", type: "button", "data-line": line },
      el("span", { class: "dot", style: `background:${LINE_COLORS[line]}` }), line);
    chip.addEventListener("click", () => {
      const next = new Set(state.lines);
      if (next.has(line)) next.delete(line);
      else next.add(line);
      update({ lines: next });
    });
    return chip;
  });
  $("line-filter").replaceChildren(all, ...chips);

  $("zoom-center").addEventListener("click", map.zoomCenter);
  $("zoom-all").addEventListener("click", map.zoomAll);

  function sync() {
    all.setAttribute("aria-pressed", String(state.lines.size === 0));
    chips.forEach((chip) => chip.setAttribute("aria-pressed", String(state.lines.has(chip.dataset.line))));
    renderLegend();
  }
  subscribe((changed) => {
    if ("lines" in changed) sync();
  });
  sync();
}

function renderLegend() {
  const legend = $("legend");
  const max = HEAT_STOPS.at(-1)[0];
  const ramp = HEAT_STOPS.map(([v, c]) => `${c} ${(v / max) * 100}%`).join(", ");
  legend.replaceChildren(
    el("div", { class: "title" }, "혼잡도 (정원 대비 탑승 %)"),
    el("div", { class: "ramp", style: `background: linear-gradient(90deg, ${ramp})` }),
    el("div", { class: "ticks" }, ...HEAT_STOPS.map(([v], i) => el("span", { style: `left:${(v / max) * 100}%` },
      i === HEAT_STOPS.length - 1 ? `${v}+` : String(v)))),
    el("div", { class: "nodata" }, el("i"), "운행 없음 · 선 하나가 한 방향"),
  );
}
