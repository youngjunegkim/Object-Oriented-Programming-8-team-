// Plotly 공통 설정. 색은 style.css의 변수를 읽는다.
export function css(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

export const PLOT_CONFIG = { displayModeBar: false, responsive: true };

export function baseLayout(extra = {}) {
  const axis = { gridcolor: css("--grid"), linecolor: css("--border"), tickfont: { color: css("--text-muted"), size: 11 }, fixedrange: true };
  return {
    paper_bgcolor: css("--surface"),
    plot_bgcolor: css("--surface"),
    font: { family: getComputedStyle(document.body).fontFamily, color: css("--text-secondary"), size: 12 },
    margin: { l: 44, r: 8, t: 16, b: 40 },
    hoverlabel: { bgcolor: css("--surface"), bordercolor: css("--border"), font: { color: css("--text-primary") } },
    xaxis: axis,
    yaxis: { ...axis, zerolinecolor: css("--border"), rangemode: "tozero" },
    showlegend: false,
    ...extra,
  };
}

// 현재 시간대를 표시하는 세로 점선
export function slotMarker(slot) {
  return { type: "line", xref: "x", yref: "paper", x0: slot, x1: slot, y0: 0, y1: 1, line: { color: css("--accent"), width: 1, dash: "dot" } };
}
