# NAVER API HUB 브랜드 경쟁 분석

유니클로·스파오·탑텐의 네이버 뉴스와 검색 추이를 수집·정리하고, 브랜드 마케터 관점의 경쟁 지표, 뉴스 내러티브 및 BoW/TF-IDF 키워드를 탐색하는 Streamlit 대시보드입니다.

## 대시보드 실행

Python 환경에 의존성을 설치한 뒤 프로젝트 루트에서 실행합니다.

```powershell
python -m pip install -r requirements.txt
python analysis/run_dashboard.py
```

기본 주소는 <http://localhost:8501>입니다. Streamlit 설정 파일은 임시 폴더에 저장하며, API 자격 증명은 대시보드 표시에는 필요하지 않습니다.

## 구성

- `app.py`: 뉴스, 주제 분류, 키워드, 워드 클라우드, 검색 추이 대시보드
- 브랜드 렌즈: 경쟁 브랜드마다 색상·카피를 전환하며 최신 검색지수, MoM/YoY 지수 차, 뉴스 메시지 신호를 연결
- `analysis/`: 검색 추이 수집·분석과 재실행 스크립트
- `data/raw/`: 수정하지 않은 NAVER API 응답
- `data/processed/`: 정리된 뉴스, 분류, 키워드 및 검색 추이 데이터
- `outputs/figures/`: 워드 클라우드 및 검색 추이 차트
- `CLAUDE.md`: 데이터 저장과 인증 정보 취급 규칙
- `data/processed/dashboard_marketing_upgrade_evaluation_20261031.md`: 대시보드 고도화 평가 기준과 결과

검색 추이 데이터를 다시 수집하려면 프로젝트 루트의 로컬 `api_keys.env`에 `NAVER_API_HUB_CLIENT_ID`, `NAVER_API_HUB_CLIENT_SECRET`을 설정하고 `python analysis/brand_search_trend.py`를 실행합니다. 키 파일은 저장소에서 제외됩니다.

## 데이터 해석

네이버 검색 추이는 상대 지수이며 실제 검색 횟수·매출·시장점유율이 아닙니다. 연령별 결과는 같은 연령대 안에서 브랜드를 비교하는 용도로 사용합니다. 한국어 키워드는 경량 토큰화 및 규칙 기반 정리 결과입니다.
