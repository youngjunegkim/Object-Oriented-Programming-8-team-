"""getShtrmPath2 공통 호출: .env 인증키, 파일 캐시, 호출 간 대기, 호출 횟수 집계."""
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import unquote

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "Data"
URL = "https://apis.data.go.kr/B553766/path2/getShtrmPath2"
SEARCH_DT = "2026-11-04 14:00:00"
DELAY = 0.2
RETRIES = 3

load_dotenv(ROOT / ".env")
# 포털의 Encoding 키를 넣었어도 requests가 다시 인코딩하지 않도록 디코딩해 둔다
SERVICE_KEY = unquote(os.environ["SERVICE_KEY"].strip())

# 콘솔 한글 깨짐 방지
sys.stdout.reconfigure(encoding="utf-8")

calls = 0  # 이번 실행에서 실제로 API를 호출한 횟수
CACHEABLE = {"00", "10", "12", "13", "20", "21"}  # 다시 불러도 결과가 같은 코드만 캐시


def safe_name(text):
    return re.sub(r'[\\/:*?"<>|\s]+', "_", text)


def call(params, cache_path):
    """params로 호출하고 응답 dict를 반환. cache_path에 파일이 있으면 호출하지 않는다."""
    global calls
    cache_path = Path(cache_path)
    if cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))

    query = {
        "serviceKey": SERVICE_KEY,
        "dataType": "JSON",
        "schInclYn": "N",
        "searchDt": SEARCH_DT,
        **params,
    }
    for attempt in range(RETRIES):
        try:
            res = requests.get(URL, params=query, timeout=30)
            break
        except requests.RequestException as e:
            # 예외 메시지에는 인증키가 든 URL이 들어 있으므로 예외 종류만 출력한다
            print(f"  [네트워크 오류 {type(e).__name__}] {attempt + 1}/{RETRIES}회, {5 * (attempt + 1)}초 후 재시도")
            time.sleep(5 * (attempt + 1))
    else:
        return None
    calls += 1
    time.sleep(DELAY)
    try:
        data = res.json()
    except ValueError:
        print(f"  [HTTP {res.status_code}] JSON 아님: {res.text[:200]}")
        return None

    if result_code(data) in CACHEABLE:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def result_code(data):
    # header가 없는 응답(포털 게이트웨이 오류 등)은 빈 코드로 두어 성공으로 오인하지 않게 한다
    code = data.get("header", {}).get("resultCode")
    return "" if code is None else str(code).zfill(2)


def result_msg(data):
    return data.get("header", {}).get("resultMsg", "")
