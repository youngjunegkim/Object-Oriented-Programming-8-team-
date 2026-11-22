// 숫자·시간 표시 형식.
export function fmtMin(seconds) {
  const m = Math.round(seconds / 60);
  return m >= 60 ? `${Math.floor(m / 60)}시간 ${m % 60}분` : `${m}분`;
}

export const fmtPct = (v) => (v == null ? "—" : `${v.toFixed(1)}%`);
export const fmtKm = (m) => (m == null ? "—" : `${(m / 1000).toFixed(1)}km`);

export const SOURCE_LABEL = { measured: "실측", "measured-9": "실측(9호선)", generated: "추정" };

// "08:00" → "08:00–08:30"
export function slotRange(slot) {
  const [h, m] = slot.split(":").map(Number);
  const end = m === 0 ? `${String(h).padStart(2, "0")}:30` : `${String((h + 1) % 24).padStart(2, "0")}:00`;
  return `${slot}–${end}`;
}
