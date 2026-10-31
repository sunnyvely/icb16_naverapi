# NAVER API HUB 브랜드 경쟁 분석

유니클로·스파오·탑텐의 네이버 뉴스와 검색 추이를 수집·정리하고, 브랜드 마케터 관점의 경쟁 지표, 뉴스 내러티브 및 BoW/TF-IDF 키워드를 탐색하는 Streamlit 대시보드입니다.

## 로컬 실행

Python 환경에 앱 의존성과 분석 스크립트 의존성을 설치한 뒤 프로젝트 루트에서 실행합니다.

```powershell
python -m pip install -r requirements.txt -r requirements-analysis.txt
python analysis/run_dashboard.py
```

기본 주소는 <http://localhost:8501>입니다. Streamlit 설정 파일은 임시 폴더에 저장합니다.

## Streamlit Community Cloud 배포

저장소는 Community Cloud 기본 구조에 맞춰 구성했습니다. 앱은 루트의 `app.py`를 진입 파일로 사용하며, 배포 시 다음 값을 선택합니다.

- Repository: `sunnyvely/icb16_naverapi`
- Branch: `main`
- Main file path: `app.py`
- Python dependencies: 루트 `requirements.txt`

Community Cloud에서 **Create app**을 선택해 위 저장소·브랜치·진입 파일을 지정하면 됩니다. `.streamlit/config.toml`에는 기본 테마가 포함되어 있습니다. 대시보드는 이미 저장된 분석 자료만 읽으므로 NAVER API 키나 Cloud Secrets가 필요하지 않습니다. API 재수집을 Cloud에서 별도로 실행할 때에만 Secrets 기반 인증을 추가해야 하며, 키 파일을 Git에 올리지 않습니다.

배포에 쓰이는 `requirements.txt`는 앱 런타임에 필요한 패키지만 포함합니다. 수집·키워드 산출 스크립트에 필요한 추가 패키지는 `requirements-analysis.txt`에 분리했습니다. Community Cloud는 저장소의 앱 파일과 데이터를 함께 가져오므로 `data/processed/` 및 워드 클라우드 PNG는 저장소에 포함되어 있어야 합니다.

## 구성

- `app.py`: 뉴스, 주제 분류, 키워드, 워드 클라우드, 검색 추이 대시보드
- 브랜드 렌즈: 경쟁 브랜드마다 색상·카피를 전환하며 최신 검색지수, MoM/YoY 지수 차, 뉴스 메시지 신호를 연결
- `analysis/`: 검색 추이 수집·분석과 재실행 스크립트
- `data/raw/`: 수정하지 않은 NAVER API 응답
- `data/processed/`: 정리된 뉴스, 분류, 키워드 및 검색 추이 데이터
- `outputs/figures/`: 워드 클라우드 및 검색 추이 차트
- `CLAUDE.md`: 데이터 저장과 인증 정보 취급 규칙
- `data/processed/dashboard_marketing_upgrade_evaluation_20261031.md`: 대시보드 고도화 평가 기준과 결과
- `requirements.txt`: Streamlit 배포 런타임 의존성
- `requirements-analysis.txt`: 데이터 수집·분석 스크립트 추가 의존성

검색 추이 데이터를 다시 수집하려면 프로젝트 루트의 로컬 `api_keys.env`에 `NAVER_API_HUB_CLIENT_ID`, `NAVER_API_HUB_CLIENT_SECRET`을 설정하고 `python analysis/brand_search_trend.py`를 실행합니다. 키 파일은 저장소에서 제외됩니다.

## 데이터 해석

네이버 검색 추이는 상대 지수이며 실제 검색 횟수·매출·시장점유율이 아닙니다. 연령별 결과는 같은 연령대 안에서 브랜드를 비교하는 용도로 사용합니다. 한국어 키워드는 경량 토큰화 및 규칙 기반 정리 결과입니다.
