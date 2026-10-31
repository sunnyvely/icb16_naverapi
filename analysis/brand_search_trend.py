"""Fetch NAVER DataLab brand search trends and create competitor visualizations."""

from __future__ import annotations

import json
import os
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import matplotlib.pyplot as plt
import pandas as pd
import requests
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
FIGURES = ROOT / "outputs" / "figures"
URL = "https://naverapihub.apigw.ntruss.com/search-trend/v1/search"
BRANDS = {
    "유니클로": ["유니클로", "UNIQLO"],
    "스파오": ["스파오", "SPAO"],
    "탑텐": ["탑텐", "TOPTEN", "탑텐키즈"],
}
AGES = {
    "0-12세": "1", "13-18세": "2", "19-24세": "3", "25-29세": "4",
    "30-34세": "5", "35-39세": "6", "40-44세": "7", "45-49세": "8",
    "50-54세": "9", "55-59세": "10", "60세 이상": "11",
}
START_DATE = "2022-01-01"
END_DATE = "2026-09-30"  # latest complete month as of the collection date
SEOUL = ZoneInfo("Asia/Seoul")


def main() -> None:
    load_dotenv(ROOT / "api_keys.env", override=False)
    client_id = os.getenv("NAVER_API_HUB_CLIENT_ID")
    client_secret = os.getenv("NAVER_API_HUB_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise SystemExit("중단: 프로젝트 루트 api_keys.env에서 NAVER API HUB 인증값을 찾지 못했습니다.")

    RAW.mkdir(parents=True, exist_ok=True)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    (FIGURES / "brand_search_trend").mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(SEOUL).strftime("%Y%m%d_%H%M%S")
    headers = {
        "X-NCP-APIGW-API-KEY-ID": client_id,
        "X-NCP-APIGW-API-KEY": client_secret,
        "Content-Type": "application/json",
    }
    groups = [{"groupName": brand, "keywords": terms} for brand, terms in BRANDS.items()]
    session = requests.Session()
    records: list[dict[str, object]] = []
    raw_files: list[str] = []

    def fetch(segment: str, ages: list[str] | None = None) -> None:
        body: dict[str, object] = {
            "startDate": START_DATE,
            "endDate": END_DATE,
            "timeUnit": "month",
            "keywordGroups": groups,
        }
        if ages:
            body["ages"] = ages
        response = session.post(URL, headers=headers, json=body, timeout=30)
        response.raise_for_status()
        payload = response.json()
        path = RAW / f"naver_api_brand_search_trend_{segment}_{stamp}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        raw_files.append(str(path.relative_to(ROOT)))
        if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
            raise RuntimeError(f"응답 형식이 예상과 다릅니다: {path.name}")
        for result in payload["results"]:
            brand = result.get("title")
            for point in result.get("data", []):
                records.append({
                    "구분": "전체" if segment == "overall" else "연령",
                    "연령": "전체" if segment == "overall" else segment,
                    "브랜드": brand,
                    "월": point.get("period"),
                    "검색지수": point.get("ratio"),
                })

    fetch("overall")
    for age_name, age_code in AGES.items():
        fetch(age_name, [age_code])

    data = pd.DataFrame(records)
    if data.empty or data["검색지수"].isna().any():
        raise RuntimeError("검색 추이 응답이 비었거나 검색지수 값이 없습니다.")
    data["월"] = pd.to_datetime(data["월"])
    data.to_csv(PROCESSED / f"brand_search_trend_monthly_{stamp}.csv", index=False, encoding="utf-8-sig")

    make_monthly_chart(data, stamp)
    make_age_chart(data, stamp)
    write_report(data, stamp, raw_files)
    print(f"수집 완료: {len(data)}개 관측치, 기간 {START_DATE}~{END_DATE}")
    print(f"원본 응답 {len(raw_files)}개 저장, 그래프 2개 생성")


def setup_plot() -> None:
    plt.rcParams["font.family"] = "Malgun Gothic"
    plt.rcParams["axes.unicode_minus"] = False


def make_monthly_chart(data: pd.DataFrame, stamp: str) -> None:
    setup_plot()
    overall = data[data["구분"] == "전체"].copy()
    fig, ax = plt.subplots(figsize=(15, 7))
    for brand, rows in overall.groupby("브랜드", sort=False):
        rows = rows.sort_values("월")
        ax.plot(rows["월"], rows["검색지수"], marker="o", markersize=3, linewidth=2, label=brand)
    ax.set_title("브랜드별 월간 통합검색 추이 (네이버 검색어트렌드)", fontsize=16, pad=16)
    ax.set_ylabel("검색지수 (기간 내 상대값, 최대 100)")
    ax.set_xlabel("월")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(title="브랜드", ncol=3, frameon=False)
    fig.autofmt_xdate()
    fig.text(0.01, 0.01, "3개 브랜드를 같은 API 요청에서 비교한 상대 검색지수입니다. 실제 검색량이나 시장점유율은 아닙니다.", fontsize=9, color="#475569")
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(FIGURES / "brand_search_trend" / f"monthly_search_trend_{stamp}.png", dpi=180)
    plt.close(fig)


def make_age_chart(data: pd.DataFrame, stamp: str) -> None:
    setup_plot()
    age = data[data["구분"] == "연령"].copy()
    fig, axes = plt.subplots(len(AGES), 1, figsize=(15, 26), sharex=True)
    palette = {"유니클로": "#2563EB", "스파오": "#EA580C", "탑텐": "#059669"}
    for ax, (age_name, _) in zip(axes, AGES.items()):
        subset = age[age["연령"] == age_name]
        for brand in BRANDS:
            rows = subset[subset["브랜드"] == brand].sort_values("월")
            ax.plot(rows["월"], rows["검색지수"], linewidth=1.5, color=palette[brand], label=brand)
        ax.set_ylabel(age_name, rotation=0, labelpad=54, va="center")
        ax.grid(axis="y", alpha=0.2)
        if age_name == next(iter(AGES)):
            ax.legend(ncol=3, loc="upper right", frameon=False)
    axes[0].set_title("연령대별 브랜드 월간 통합검색 추이", fontsize=16, pad=14)
    axes[-1].set_xlabel("월")
    fig.text(0.01, 0.005, "연령별 호출 결과도 브랜드·연령 그룹마다 별도 정규화된 상대지수이며, 연령 간 절대 검색량이나 연령 구성비 비교에는 사용할 수 없습니다.", fontsize=9, color="#475569")
    fig.autofmt_xdate()
    fig.tight_layout(rect=(0.02, 0.025, 1, 1))
    fig.savefig(FIGURES / "brand_search_trend" / f"age_monthly_search_trend_{stamp}.png", dpi=180)
    plt.close(fig)


def write_report(data: pd.DataFrame, stamp: str, raw_files: list[str]) -> None:
    overall = data[data["구분"] == "전체"]
    peaks = overall.loc[overall.groupby("브랜드")["검색지수"].idxmax()].sort_values("브랜드")
    age = data[data["구분"] == "연령"]
    mean_idx = age.groupby(["연령", "브랜드"], as_index=False)["검색지수"].mean()
    annual = overall.assign(연도=overall["월"].dt.year).groupby(["연도", "브랜드"], as_index=False)["검색지수"].mean()
    leaders = overall.pivot(index="월", columns="브랜드", values="검색지수").idxmax(axis=1).value_counts()
    seasonal = overall.assign(월번호=overall["월"].dt.month)
    seasonal["기간"] = seasonal["월번호"].map(lambda month: "10-12월" if month >= 10 else "1-9월")
    seasonal_mean = seasonal.groupby(["브랜드", "기간"], as_index=False)["검색지수"].mean()
    age_pivot = mean_idx.pivot(index="연령", columns="브랜드", values="검색지수")
    lines = [
        "# 유니클로·스파오·탑텐 네이버 검색 추이 경쟁 분석",
        "",
        f"- 수집 시각: {datetime.now(SEOUL).strftime('%Y-%m-%d %H:%M:%S %Z')}",
        f"- 분석 기간: {START_DATE} ~ {END_DATE} (월간, 완결된 월 기준)",
        "- 지표: 네이버 통합검색어트렌드 상대 검색지수. 전체 추이는 세 브랜드 그룹을 한 번의 요청으로 비교했고, 연령 추이는 연령대별로 세 브랜드를 함께 비교했습니다.",
        "- 브랜드 그룹 검색어: 유니클로(유니클로, UNIQLO), 스파오(스파오, SPAO), 탑텐(탑텐, TOPTEN, 탑텐키즈)",
        "- 연령 구간은 네이버 검색어트렌드 API 구간을 사용했습니다.",
        "- 한계: 상대지수는 실제 검색 횟수나 검색 점유율이 아닙니다. 연령별 요청은 연령대마다 따로 정규화되므로 서로 다른 연령대의 지수 평균을 비교해 연령 규모·구성비를 추론하면 안 됩니다. 같은 연령대 안에서 브랜드 간 상대 움직임을 비교하십시오.",
        "- 한계: API의 연령 필터는 연령대별 검색 추이만 제공하며 사용자의 구매·매출 데이터를 나타내지 않습니다.",
        "",
        "## 브랜드별 최고 검색지수 월",
        "",
        "| 브랜드 | 최고 월 | 상대 검색지수 |",
        "|---|---|---:|",
    ]
    for _, row in peaks.iterrows():
        lines.append(f"| {row['브랜드']} | {row['월']:%Y-%m} | {row['검색지수']:.2f} |")
    lines.extend(["", "## 경쟁 관점 요약", "", f"- 57개월 모두 유니클로가 세 브랜드 중 가장 높은 상대 검색지수를 기록했습니다 ({int(leaders.get('유니클로', 0))}/57개월). 이 값은 설정한 브랜드 검색어 묶음 기준이며 검색량·매출 점유율은 아닙니다."])
    overall_mean = overall.groupby("브랜드")["검색지수"].mean().sort_values(ascending=False)
    lines.append("- 전체 기간 평균 상대지수 순서는 " + " > ".join(f"{brand} ({value:.1f})" for brand, value in overall_mean.items()) + "입니다.")
    season_lines = []
    for brand in BRANDS:
        vals = seasonal_mean[seasonal_mean["브랜드"] == brand].set_index("기간")["검색지수"]
        season_lines.append(f"{brand}: 1-9월 {vals['1-9월']:.1f}, 10-12월 {vals['10-12월']:.1f}")
    lines.append("- 세 브랜드 모두 10-12월 평균 지수가 1-9월보다 높았습니다 (계절성 신호): " + "; ".join(season_lines) + ".")
    young_leaders = ", ".join(f"{age_name} {age_pivot.loc[age_name].idxmax()}" for age_name in ["0-12세", "13-18세"])
    adult_leaders = ", ".join(f"{age_name} {age_pivot.loc[age_name].idxmax()}" for age_name in ["19-24세", "25-29세", "30-34세", "35-39세", "40-44세", "45-49세", "50-54세", "55-59세", "60세 이상"])
    lines.append(f"- 연령대별 기간 평균지수에서 0-18세는 {young_leaders}가 우세했고, 19세 이상 구간은 {adult_leaders}가 우세했습니다. 연령대별 상대지수는 각 구간 안에서만 비교한 결과입니다.")
    lines.extend(["", "## 연도별 평균 상대지수", "", "| 연도 | 브랜드 | 평균 지수 |", "|---:|---|---:|"])
    for _, row in annual.iterrows():
        lines.append(f"| {int(row['연도'])} | {row['브랜드']} | {row['검색지수']:.2f} |")
    lines.extend(["", "## 연령별 평균 상대지수 (참고; 같은 연령대 내 브랜드 비교용)", "", "| 연령 | 브랜드 | 기간 평균 지수 |", "|---|---|---:|"])
    for _, row in mean_idx.iterrows():
        lines.append(f"| {row['연령']} | {row['브랜드']} | {row['검색지수']:.2f} |")
    lines.extend(["", "## 산출물", "", f"- 월별 차트: `../../outputs/figures/brand_search_trend/monthly_search_trend_{stamp}.png`", f"- 연령별 월간 차트: `../../outputs/figures/brand_search_trend/age_monthly_search_trend_{stamp}.png`", f"- 통합 관측치 CSV: `brand_search_trend_monthly_{stamp}.csv`", "", "## 원본 API 응답", ""])
    lines.extend(f"- `{file}`" for file in raw_files)
    report = PROCESSED / f"brand_search_trend_analysis_{stamp}.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"report={report.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
