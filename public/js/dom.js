// DOM 도우미: 요소 만들기, 오류 표시, 지도 툴팁.
export const $ = (id) => document.getElementById(id);

export function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (key === "class") node.className = value;
    else if (key === "style") node.style.cssText = value;
    else node.setAttribute(key, value);
  }
  node.append(...children);
  return node;
}

export function showError(err) {
  const box = $("error");
  box.hidden = !err;
  if (err) box.textContent = err.message || String(err);
}

// 지도 위 툴팁. 첫 줄은 굵게, 나머지는 한 줄씩.
export function showTip(event, title, ...lines) {
  const tip = $("tooltip");
  tip.replaceChildren(el("b", {}, title), ...lines.map((line) => el("div", {}, line)));
  tip.hidden = false;
  const box = tip.parentElement.getBoundingClientRect();
  const x = event.clientX - box.left + 14;
  const y = event.clientY - box.top + 14;
  tip.style.left = `${Math.min(x, box.width - tip.offsetWidth - 8)}px`;
  tip.style.top = `${Math.min(y, box.height - tip.offsetHeight - 8)}px`;
}

export function hideTip() {
  $("tooltip").hidden = true;
}
