// 노선색과 혼잡도 색.
export const LINE_COLORS = {
  "1호선": "#0052A4", "2호선": "#00A84D", "3호선": "#EF7C1C", "4호선": "#00A5DE",
  "5호선": "#996CAC", "6호선": "#CD7C2F", "7호선": "#747F00", "8호선": "#E6186C",
  "9호선": "#BDB092", "수인분당선": "#F5A200", "신분당선": "#D4003B", "경의중앙선": "#77C4A3",
  "공항철도": "#0090D2", "경춘선": "#0C8E72", "경강선": "#003DA5", "서해선": "#8FC31F",
  "우이신설선": "#B0CE18", "신림선": "#6789CA", "인천1호선": "#7CA8D5", "인천2호선": "#ED8B00",
  "김포골드라인": "#A17800", "의정부경전철": "#FDA600", "용인에버라인": "#509F22",
};

const NO_DATA = "#c3c8d1";  // 운행 없음
export const DIMMED = "#e1e4ea";   // 선택하지 않은 호선

// [혼잡도 %, 색]: 여유(초록) → 보통(노랑) → 혼잡(주황·빨강) → 매우 혼잡(짙은 빨강)
// 평일 구간 혼잡도는 중앙값 ≈22%, 75% ≈34%에 몰려 있어 낮은 구간에서도 색이 조금씩 갈리도록 둔다.
export const HEAT_STOPS = [
  [0, "#2fa36b"], [25, "#8cc63f"], [50, "#f0c43a"], [75, "#ec8a35"], [100, "#dc4b2c"], [130, "#8c1020"],
];

const heat = d3.scaleLinear()
  .domain(HEAT_STOPS.map(([v]) => v))
  .range(HEAT_STOPS.map(([, c]) => c))
  .clamp(true);

export const congestionColor = (value) => (value == null ? NO_DATA : heat(value));
