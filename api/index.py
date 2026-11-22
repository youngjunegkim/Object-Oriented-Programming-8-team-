"""대시보드 JSON API. Vercel Python 함수(handler)와 로컬 서버(main.py)가 함께 사용한다.

GET /api/meta
GET /api/directions?station=<역코드>
GET /api/station?station=<역코드>&next=<역코드>&line=<호선>
GET /api/route?start=<역코드>&end=<역코드>&day=<요일>&time=HH:MM
GET /api/departure?start=..&end=..&day=..
GET /api/network?day=<요일>
"""

import json
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from views.dashboard import Dashboard  # noqa: E402

_dashboard = None


def dashboard():
    """그래프는 한 번만 구성해 재사용한다."""
    global _dashboard
    if _dashboard is None:
        _dashboard = Dashboard()
    return _dashboard


def _required(params, name):
    value = params.get(name)
    if not value:
        raise ValueError(f"'{name}' 값이 필요합니다.")
    return value


# API 이름 → 화면 클래스 메서드
ROUTES = {
    "meta": lambda d, p: d.meta(),
    "directions": lambda d, p: d.stations.directions(_required(p, "station")),
    "station": lambda d, p: d.stations.compare_days(
        _required(p, "station"), _required(p, "next"), _required(p, "line")),
    "route": lambda d, p: d.routes.options(
        _required(p, "start"), _required(p, "end"), _required(p, "day"), _required(p, "time")),
    "departure": lambda d, p: d.routes.departure(
        _required(p, "start"), _required(p, "end"), _required(p, "day")),
    "network": lambda d, p: d.network.render(_required(p, "day")),
}


def dispatch(path, query):
    """(상태코드, 응답 dict)를 반환한다."""
    params = {key: values[0] for key, values in parse_qs(query).items()}
    # Vercel rewrite(/api/:name → /api/index?endpoint=:name)로 들어오면 endpoint를 우선 사용한다.
    name = params.pop("endpoint", None) or path.rstrip("/").rsplit("/", 1)[-1]
    if name not in ROUTES:
        return 404, {"error": f"알 수 없는 API입니다: {path}"}
    try:
        return 200, ROUTES[name](dashboard(), params)
    except (ValueError, RuntimeError) as e:
        return 400, {"error": str(e)}


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        url = urlparse(self.path)
        status, body = dispatch(url.path, url.query)
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        if status == 200:
            self.send_header("Cache-Control", "public, max-age=3600")
        self.end_headers()
        self.wfile.write(data)
