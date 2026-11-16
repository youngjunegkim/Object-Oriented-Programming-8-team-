"""로컬에서 대시보드 실행: python3 serve.py [포트]  →  http://localhost:8000

public/의 정적 파일과 /api/* 요청을 함께 처리한다. 표준 라이브러리만 사용한다.
"""

import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from api.index import handler as ApiHandler, view

PUBLIC = Path(__file__).resolve().parent / "public"


class DashboardHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/api/"):
            ApiHandler.do_GET(self)
        else:
            super().do_GET()


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    view()  # 시작할 때 그래프를 미리 구성한다.
    server = ThreadingHTTPServer(("127.0.0.1", port), partial(DashboardHandler, directory=str(PUBLIC)))
    print(f"대시보드: http://localhost:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
