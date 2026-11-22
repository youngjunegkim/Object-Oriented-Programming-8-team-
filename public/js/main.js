// 초기화: 데이터를 불러와 지도·패널을 만들고, 상단 조건 바(요일·시간대)를 상태와 연결한다.
import { api, loadJSON } from "./api.js";
import { state, update, subscribe } from "./state.js";
import { $, el, showError } from "./dom.js";
import { slotRange } from "./format.js";
import { createMap } from "./map/network.js";
import { initMapControls } from "./map/controls.js";
import { initStationPanel } from "./panels/station.js";
import { initRoutePanel } from "./panels/route.js";

async function init() {
  const [meta, coords, river, boundary] = await Promise.all([
    api("meta"),
    loadJSON("data/station_coords.json"),
    loadJSON("data/han_river.geojson"),
    loadJSON("data/seoul_boundary.geojson"),
  ]);
  const { stations, days, slots } = meta;

  // 역 찾기: 호선별 역코드 → 역, 입력창 표시 이름 → 역
  const byCode = new Map();
  const byLabel = new Map();
  for (const s of stations) {
    for (const code of s.codes) byCode.set(code, s);
    byLabel.set(s.label, s);
  }
  $("station-list").replaceChildren(...stations.map((s) => el("option", { value: s.label })));

  const map = createMap({
    svgEl: $("map"), coords, river, boundary, stations, slots, byCode,
    onStation: (station) => update({ station }),
  });
  initMapControls({ lines: meta.lines, map });
  initStationPanel();
  initRoutePanel({ byLabel });

  // ---------- 요일 ----------
  const dayButtons = days.map((day) => {
    const b = el("button", { type: "button" }, day);
    b.addEventListener("click", () => update({ day }));
    return b;
  });
  $("day").replaceChildren(...dayButtons);

  async function loadNetwork() {
    dayButtons.forEach((b) => b.setAttribute("aria-pressed", String(b.textContent === state.day)));
    try {
      map.setNetwork(await api("network", { day: state.day }));
    } catch (e) { showError(e); }
  }

  // ---------- 시간대 ----------
  const slider = $("slot");
  slider.max = slots.length - 1;
  slider.addEventListener("input", () => {
    setPlaying(false);  // 슬라이더를 직접 잡으면 재생을 멈춘다.
    update({ slot: slots[slider.value] });
  });
  const showSlot = () => {
    slider.value = slots.indexOf(state.slot);
    $("slot-label").textContent = slotRange(state.slot);
  };

  // 재생: 0.7초마다 다음 30분 시간대로 넘긴다. 처음 열면 재생 상태로 시작한다.
  let playing = null;
  function setPlaying(on) {
    clearInterval(playing);
    playing = on ? setInterval(() => update({ slot: slots[(slots.indexOf(state.slot) + 1) % slots.length] }), 700) : null;
    $("play").textContent = on ? "❚❚" : "▶";
    $("play").setAttribute("aria-label", on ? "재생 멈춤" : "하루 흐름 재생");
  }
  $("play").addEventListener("click", () => setPlaying(!playing));

  subscribe((changed) => {
    if ("day" in changed) loadNetwork();
    if ("slot" in changed) showSlot();
    $("intro").hidden = Boolean(state.station || (state.start && state.end));
  });

  showSlot();
  await loadNetwork();
  setPlaying(true);
}

init().catch(showError);
