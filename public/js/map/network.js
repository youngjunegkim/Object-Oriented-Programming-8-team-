// 노선도 지도: OSM 역 좌표 위에 /api/network의 구간별 혼잡도를 선 색으로 그린다.
//
// - 좌표: 경위도를 평면으로 펼친다(위도 37.55도 기준으로 경도를 줄임). 수도권 범위에서는 충분히 정확하다.
// - 줌: 선 굵기와 선 사이 간격이 화면 픽셀로 일정하도록, 줌할 때마다 화면 좌표를 다시 계산한다.
// - 같은 두 역을 잇는 구간은 호선마다 한 줄(lane), 방향마다 반 줄씩 옆으로 밀어 겹치지 않게 그린다.
// - 역 선택: 점을 정확히 누르지 않아도, 마우스에서 PICK px 안의 가장 가까운 역을 고른다(Delaunay).
// - 역 이름: 선택한 역 > 경로 출발·도착 > 환승 호선이 많은 역 순으로, 겹치지 않는 것만 표시한다.
import { state, subscribe } from "../state.js";
import { LINE_COLORS, DIMMED, congestionColor } from "../colors.js";
import { fmtPct, SOURCE_LABEL } from "../format.js";
import { showTip, hideTip } from "../dom.js";

const SCALE = 1000;                            // 위도 1도 = 1000 단위
const LON_RATIO = Math.cos((37.55 * Math.PI) / 180);
const LANE = 3.4;                              // 같은 구간을 지나는 호선 사이 간격(px)
const DIR = 1.3;                               // 상·하행 사이 간격의 절반(px)
const LABEL_ZOOM = 5;                          // 이 배율부터 환승역이 아닌 역 이름도 후보에 넣는다.
const PICK = 16;                               // 역 선택 반경(px)
const CENTER = [[126.84, 37.46], [127.14, 37.63]];  // "도심" 보기 범위 [서남, 동북]

const project = ([lon, lat]) => [lon * LON_RATIO * SCALE, -lat * SCALE];
const clamp = (min, max, v) => Math.max(min, Math.min(max, v));

function bounds(points) {
  const xs = points.map((p) => p[0]);
  const ys = points.map((p) => p[1]);
  return [[Math.min(...xs), Math.min(...ys)], [Math.max(...xs), Math.max(...ys)]];
}

const overlaps = (a, b) => a[0] < b[2] && b[0] < a[2] && a[1] < b[3] && b[1] < a[3];

export function createMap({ svgEl, coords, river, boundary, stations, slots, byCode, onStation }) {
  const svg = d3.select(svgEl);
  const riverLayer = svg.append("g").attr("class", "river");
  const boundaryLayer = svg.append("g").attr("class", "boundary");
  const edgeLayer = svg.append("g").attr("class", "edges");
  const routeLayer = svg.append("g").attr("class", "route");
  const casingLayer = routeLayer.append("g");
  const rideLayer = routeLayer.append("g");
  const endLayer = routeLayer.append("g");
  const stationLayer = svg.append("g").attr("class", "stations");
  const labelLayer = svg.append("g").attr("class", "labels");

  let transform = d3.zoomIdentity;
  let edgeSel = edgeLayer.selectAll("line");
  let casingSel = casingLayer.selectAll("path");
  let rideSel = rideLayer.selectAll("line");
  let endSel = endLayer.selectAll("g");
  let routeKey = "";
  let delaunay = null;
  let hovered = null;

  const sx = (p) => transform.x + transform.k * p[0];
  const sy = (p) => transform.y + transform.k * p[1];
  const at = (code) => project(coords[code]);
  const picked = (line) => state.lines.size === 0 || state.lines.has(line);

  // ---------- 배경: 한강, 서울 경계 ----------
  const geoPath = d3.geoPath(d3.geoTransform({
    point(lon, lat) { this.stream.point(...project([lon, lat])); },
  }));
  riverLayer.append("path").datum(river).attr("d", geoPath);
  boundaryLayer.append("path").datum(boundary).attr("d", geoPath);

  // ---------- 역 ----------
  const nodes = stations.map((s) => ({ ...s, p: at(s.code) }));
  const byPriority = [...nodes].sort((a, b) => b.lines.length - a.lines.length);
  const stationSel = stationLayer.selectAll("circle").data(nodes).join("circle");
  const labelSel = labelLayer.selectAll("text").data(nodes).join("text")
    .attr("class", (d) => (d.lines.length > 1 ? "major" : null))
    .text((d) => d.name);

  function nearest(event) {
    const [x, y] = d3.pointer(event, svgEl);
    const d = nodes[delaunay.find(x, y)];
    return Math.hypot(sx(d.p) - x, sy(d.p) - y) <= PICK ? d : null;
  }

  svg
    .on("pointermove.pick", (event) => {
      const d = nearest(event);
      if (d !== hovered) {
        hovered = d;
        stationSel.classed("hover", (n) => n === d);
        svgEl.classList.toggle("on-station", Boolean(d));
      }
      if (d) showTip(event, d.label, d.lines.join(" · "));
    })
    .on("pointerleave.pick", () => {
      hovered = null;
      stationSel.classed("hover", false);
      hideTip();
    })
    .on("click.pick", (event) => {
      const d = nearest(event);
      if (d) onStation(d);
    });

  // ---------- 구간 ----------
  function setNetwork(network) {
    const pairKey = (e) => {
      const a = coords[e.from].join();
      const b = coords[e.to].join();
      return a < b ? `${a}|${b}` : `${b}|${a}`;
    };
    const lanes = new Map();  // 두 역 사이 → 그 구간을 지나는 호선 목록
    for (const e of network.edges) {
      const list = lanes.get(pairKey(e)) || [];
      if (!list.includes(e.line)) list.push(e.line);
      lanes.set(pairKey(e), list);
    }
    const edges = network.edges.map((e) => {
      const a = at(e.from);
      const b = at(e.to);
      const forward = coords[e.from].join() < coords[e.to].join();
      const [p, q] = forward ? [a, b] : [b, a];  // 두 방향이 같은 법선을 쓰도록 기준 방향을 맞춘다.
      const len = Math.hypot(q[0] - p[0], q[1] - p[1]) || 1;
      const list = lanes.get(pairKey(e));
      return {
        ...e, a, b,
        nx: -(q[1] - p[1]) / len,
        ny: (q[0] - p[0]) / len,
        off: (list.indexOf(e.line) - (list.length - 1) / 2) * LANE + (forward ? DIR : -DIR),
      };
    });
    edgeSel = edgeLayer.selectAll("line").data(edges, (d) => `${d.from}>${d.to}`).join("line")
      .on("mousemove", (event, d) => {
        if (hovered) return;  // 역 근처에서는 역 툴팁을 보여준다.
        const value = d.values[slots.indexOf(state.slot)];
        showTip(event, `${d.line} · ${byCode.get(d.from).name} → ${byCode.get(d.to).name}`,
          `${state.day} ${state.slot} · ${fmtPct(value)}${value == null ? "" : ` (${SOURCE_LABEL[d.source]})`}`);
      })
      .on("mouseleave", () => { if (!hovered) hideTip(); });
    sortEdges();
    place();
    paint();
  }

  // 선택한 호선을 위에 그린다.
  function sortEdges() {
    edgeSel.sort((a, b) => picked(a.line) - picked(b.line));
  }

  // ---------- 색 ----------
  const rideColor = (r) => (state.colorBy === "line" ? LINE_COLORS[r.line] : congestionColor(r.value));

  function paint() {
    const i = slots.indexOf(state.slot);
    edgeSel
      .attr("stroke", (d) => {
        if (!picked(d.line)) return DIMMED;
        return state.colorBy === "line" ? LINE_COLORS[d.line] : congestionColor(d.values[i]);
      })
      .attr("stroke-width", (d) => (picked(d.line) ? 2.6 : 1.4));
    edgeLayer.classed("faded", Boolean(state.route));
    rideSel.attr("stroke", rideColor);
    stationSel
      .classed("dim", (d) => !d.lines.some(picked))
      .classed("selected", (d) => d.code === state.station?.code);
    labelSel.classed("selected", (d) => d.code === state.station?.code);
    placeLabels();
  }

  // ---------- 경로 강조: 구간마다 진입 시각의 혼잡도 색(노선색 모드에서는 호선색) ----------
  function drawRoute() {
    const route = state.route;
    const legs = route ? route.legs.filter((leg) => leg.type === "ride") : [];
    casingSel = casingLayer.selectAll("path").data(legs).join("path").attr("class", "casing");
    rideSel = rideLayer.selectAll("line").data(route ? route.rides : []).join("line")
      .attr("class", "leg")
      .on("mousemove", (event, r) => showTip(event, `${r.line} · ${r.from} → ${r.to}`,
        `${r.slot || "운행 시간 외"} 진입 · ${fmtPct(r.value)}`))
      .on("mouseleave", hideTip);

    const ends = legs.length
      ? [{ code: legs[0].codes[0], text: "출발" }, { code: legs.at(-1).codes.at(-1), text: "도착" }]
      : [];
    endSel = endLayer.selectAll("g").data(ends).join((enter) => {
      const g = enter.append("g").attr("class", "end");
      g.append("circle").attr("r", 6);
      g.append("text").attr("dx", 8).attr("dy", 20);  // 역 이름 라벨(오른쪽 위)과 겹치지 않게 아래에 둔다.
      return g;
    });
    endSel.select("text").text((d) => d.text);

    place();
    paint();
    // 경로가 바뀌었을 때만 화면을 경로에 맞춘다 (시간대만 바뀐 경우는 그대로 둔다).
    const key = legs.map((leg) => leg.codes.join()).join("|");
    if (key && key !== routeKey) fit(bounds(legs.flatMap((leg) => leg.codes.map(at))), 600);
    routeKey = key;
  }

  // ---------- 역 이름 배치 ----------
  function placeLabels() {
    const important = [state.station?.code, ...endSel.data().map((e) => byCode.get(e.code).code)];
    const candidates = [
      ...nodes.filter((d) => important.includes(d.code)),
      ...byPriority.filter((d) => !important.includes(d.code) && (d.lines.length > 1 || transform.k >= LABEL_ZOOM)),
    ];
    const { clientWidth: width, clientHeight: height } = svgEl;
    const boxes = [];
    const shown = new Set();
    const offset = (d) => Math.max(6, radius(d) + 2);  // 점이 커지면 라벨도 그만큼 오른쪽 위로 띄운다.
    for (const d of candidates) {
      const x = sx(d.p) + offset(d);
      const y = sy(d.p) - offset(d);
      if (x < 0 || y < 0 || x > width || y > height) continue;
      const box = [x - 2, y - 12, x + d.name.length * 11 + 2, y + 3];
      if (!important.includes(d.code) && boxes.some((b) => overlaps(b, box))) continue;
      boxes.push(box);
      shown.add(d);
    }
    labelSel
      .attr("display", (d) => (shown.has(d) ? null : "none"))
      .attr("x", (d) => sx(d.p) + offset(d))
      .attr("y", (d) => sy(d.p) - offset(d));
  }

  // ---------- 화면 좌표 ----------
  const line = d3.line().x(sx).y(sy);
  let kCenter = 1;  // "도심" 보기의 배율. 역 크기의 기준이다.
  // 도심 보기에서 5px. 확대할수록 빠르게 커지고(2배 확대 ≈ 8px, 4배 ≈ 13px) 축소하면 1.5px까지 작아진다. 환승역은 1.4배.
  const radius = (d) => clamp(1.5, 21, 5.25 * (transform.k / kCenter) ** 0.7) * (d.lines.length > 1 ? 1.4 : 1);

  function place() {
    riverLayer.attr("transform", transform);
    boundaryLayer.attr("transform", transform);
    edgeSel
      .attr("x1", (d) => sx(d.a) + d.nx * d.off).attr("y1", (d) => sy(d.a) + d.ny * d.off)
      .attr("x2", (d) => sx(d.b) + d.nx * d.off).attr("y2", (d) => sy(d.b) + d.ny * d.off);
    stationSel.attr("cx", (d) => sx(d.p)).attr("cy", (d) => sy(d.p)).attr("r", radius);
    casingSel.attr("d", (leg) => line(leg.codes.map(at)));
    rideSel
      .attr("x1", (r) => sx(at(r.from_code))).attr("y1", (r) => sy(at(r.from_code)))
      .attr("x2", (r) => sx(at(r.to_code))).attr("y2", (r) => sy(at(r.to_code)));
    endSel.attr("transform", (d) => `translate(${sx(at(d.code))},${sy(at(d.code))})`);
    delaunay = d3.Delaunay.from(nodes, (d) => sx(d.p), (d) => sy(d.p));
    placeLabels();
  }

  // ---------- 줌 ----------
  const zoom = d3.zoom().on("zoom", (event) => {
    transform = event.transform;
    hideTip();
    place();
  });
  svg.call(zoom).on("dblclick.zoom", null);

  // 왼쪽 호선 버튼 열을 뺀 나머지 영역에 box가 들어오도록 맞춘다.
  function fitTransform([[x0, y0], [x1, y1]]) {
    const { width, height } = svgEl.getBoundingClientRect();
    const left = document.getElementById("line-filter").offsetWidth + 24;
    const [kMin, kMax] = zoom.scaleExtent();
    const k = clamp(kMin, kMax, Math.min((width - left - 80) / (x1 - x0 || 1), (height - 160) / (y1 - y0 || 1)));
    const cx = left + (width - left) / 2;
    return d3.zoomIdentity.translate(cx - (k * (x0 + x1)) / 2, height / 2 - (k * (y0 + y1)) / 2).scale(k);
  }

  function fit(box, duration) {
    const target = fitTransform(box);
    if (duration) svg.transition().duration(duration).call(zoom.transform, target);
    else svg.call(zoom.transform, target);
  }

  const allBox = bounds(nodes.map((d) => d.p));
  const centerBox = bounds(CENTER.map(project));
  kCenter = fitTransform(centerBox).k;
  // 최소 배율: 수도권 전체가 딱 맞는 배율의 1.8배. 휠 한 칸이 2^0.2배이므로 예전 최소(0.6배)보다 약 8칸 덜 축소된다.
  zoom.scaleExtent([fitTransform(allBox).k * 1.8, kCenter * 12]);
  fit(centerBox, 0);

  subscribe((changed) => {
    if ("lines" in changed) sortEdges();
    if ("route" in changed) drawRoute();
    else if (["slot", "lines", "colorBy", "station"].some((key) => key in changed)) paint();
  });

  return {
    setNetwork,
    zoomCenter: () => fit(centerBox, 500),
    zoomAll: () => fit(allBox, 500),
  };
}
