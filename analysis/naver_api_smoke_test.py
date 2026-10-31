"""NAVER API HUB read-only smoke tests; credentials are loaded from project-root api_keys.env."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "https://naverapihub.apigw.ntruss.com"
SEOUL = ZoneInfo("Asia/Seoul")


def main() -> int:
    load_dotenv(ROOT / "api_keys.env", override=False)
    import os

    client_id = os.getenv("NAVER_API_HUB_CLIENT_ID")
    client_secret = os.getenv("NAVER_API_HUB_CLIENT_SECRET")
    if not client_id or not client_secret:
        print("중단: api_keys.env에 필요한 인증 항목이 없습니다.")
        return 2

    headers = {
        "X-NCP-APIGW-API-KEY-ID": client_id,
        "X-NCP-APIGW-API-KEY": client_secret,
    }
    today = date.today()
    start_date = (today - timedelta(days=90)).replace(day=1).isoformat()
    end_date = (today - timedelta(days=1)).isoformat()
    tests = [
        (
            "news",
            "GET",
            "/search/v1/news",
            {"query": "네이버 클라우드", "display": 3, "sort": "date", "format": "json"},
            None,
        ),
        (
            "search_trend",
            "POST",
            "/search-trend/v1/search",
            None,
            {
                "startDate": start_date,
                "endDate": end_date,
                "timeUnit": "month",
                "keywordGroups": [
                    {"groupName": "인공지능", "keywords": ["인공지능", "AI"]},
                    {"groupName": "클라우드", "keywords": ["클라우드", "클라우드 컴퓨팅"]},
                ],
            },
        ),
        (
            "shopping_categories",
            "POST",
            "/shopping/v1/categories",
            None,
            {
                "startDate": start_date,
                "endDate": end_date,
                "timeUnit": "month",
                "category": [
                    {"name": "패션의류", "param": ["50000000"]},
                    {"name": "화장품/미용", "param": ["50000002"]},
                ],
            },
        ),
    ]

    output_dir = ROOT / "data" / "raw"
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(SEOUL).strftime("%Y%m%d_%H%M%S")
    failures = 0
    for name, method, path, params, body in tests:
        try:
            response = requests.request(
                method,
                BASE_URL + path,
                headers={**headers, **({"Content-Type": "application/json"} if body else {})},
                params=params,
                json=body,
                timeout=30,
            )
            raw_path = output_dir / f"naver_api_{name}_{stamp}.json"
            raw_path.write_text(response.text, encoding="utf-8")
            try:
                payload = response.json()
            except ValueError:
                payload = None

            if response.ok and isinstance(payload, dict):
                if name == "news":
                    count = len(payload.get("items", []))
                    detail = f"items={count}, total={payload.get('total', 'n/a')}"
                else:
                    count = len(payload.get("results", []))
                    points = sum(len(item.get("data", [])) for item in payload.get("results", []))
                    detail = f"groups={count}, data_points={points}"
                outcome = "성공"
            else:
                failures += 1
                detail = f"오류 응답은 {raw_path.relative_to(ROOT)}에 저장"
                outcome = "실패"
            print(f"{name}: {outcome} (HTTP {response.status_code}; {detail})")
            print(f"  raw={raw_path.relative_to(ROOT)}")
        except requests.RequestException as exc:
            failures += 1
            print(f"{name}: 요청 실패 ({type(exc).__name__}; 타임아웃 또는 네트워크 오류)")

    print(f"조회 기간: {start_date} ~ {end_date}; 타임아웃: 30초")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
