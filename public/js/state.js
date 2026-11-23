// 화면 전체가 함께 쓰는 상태. 값을 바꿀 때는 update()를 쓰고, 각 영역은 subscribe()로 바뀐 값만 확인해 다시 그린다.
export const state = {
  day: "평일",
  slot: "08:00",          // 30분 시간대 (SLOTS 중 하나)
  lines: new Set(),       // 색을 켤 호선. 비어 있으면 전체
  station: null,          // 선택한 역 (meta.stations 항목)
  start: null,            // 출발역
  end: null,              // 도착역
  route: null,            // 지도에 강조할 경로 (/api/route의 routes 항목)
};

const listeners = [];

export function subscribe(listener) {
  listeners.push(listener);
}

// changes: 바꿀 값만 담은 객체. 구독자는 같은 객체를 받아 어떤 키가 바뀌었는지 본다.
export function update(changes) {
  Object.assign(state, changes);
  for (const listener of listeners) listener(changes);
}
