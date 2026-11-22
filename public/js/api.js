// 서버 API(/api/*)와 정적 데이터(public/data) 불러오기.

// API 응답 모양을 바꾸면 올린다. 서버는 응답을 1시간 캐시하게 하므로(max-age=3600),
// 주소가 같으면 브라우저가 예전 모양의 응답을 꺼내 쓴다. 번호가 바뀌면 주소가 달라져 새로 받는다.
const API_VERSION = 2;

export async function api(name, params = {}) {
  const res = await fetch(`/api/${name}?${new URLSearchParams({ ...params, v: API_VERSION })}`);
  const body = await res.json();
  if (!res.ok) throw new Error(body.error || `요청 실패 (${res.status})`);
  return body;
}

export async function loadJSON(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`${path}를 불러오지 못했습니다 (${res.status})`);
  return res.json();
}
