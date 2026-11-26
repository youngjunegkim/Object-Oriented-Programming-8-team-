"""로컬에서 대시보드 실행: python3 main.py [포트]  →  http://localhost:8000

public/의 정적 파일과 /api/* 요청을 함께 처리한다. 표준 라이브러리만 사용한다.
"""

import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from api.index import handler as ApiHandler, dashboard

PUBLIC = Path(__file__).resolve().parent / "public"


class DashboardHandler(SimpleHTTPRequestHandler):
    # Windows 레지스트리 설정에 따라 .js가 text/plain으로 나가면 브라우저가 ES 모듈을 거부한다.
    extensions_map = {**SimpleHTTPRequestHandler.extensions_map, ".js": "text/javascript"}

    def do_GET(self):
        if self.path.startswith("/api/"):
            ApiHandler.do_GET(self)
        else:
            super().do_GET()

    def end_headers(self):
        # 프론트 파일은 매번 바뀌었는지 확인하게 한다. 이 헤더가 없으면 브라우저가 수정 시각만 보고
        # 예전 JS·CSS를 한동안 그대로 써서, 고친 내용이 새로고침해도 반영되지 않는다.
        # (Vercel은 정적 파일에 같은 정책을 기본으로 쓴다. /api/*는 api/index.py가 따로 정한다.)
        if not self.path.startswith("/api/"):
            self.send_header("Cache-Control", "no-cache")
        super().end_headers()


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    dashboard()  # 시작할 때 그래프를 미리 구성한다.
    server = ThreadingHTTPServer(("127.0.0.1", port), partial(DashboardHandler, directory=str(PUBLIC)))
    print(f"대시보드: http://localhost:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
