"""Streamlit dashboard for the NAVER brand news and search-trend analysis."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


ROOT = Path(__file__).resolve().parent
PROCESSED = ROOT / "data" / "processed"
WORDCLOUD_DIR = ROOT / "outputs" / "figures" / "news_wordclouds"
TREND_FIGURE_DIR = ROOT / "outputs" / "figures" / "brand_search_trend"
BRANDS = ["유니클로", "스파오", "탑텐"]
BRAND_COLORS = {"유니클로": "#2878B5", "스파오": "#F28E2B", "탑텐": "#2E9D62"}
TOPIC_ORDER = ["제품 출시", "협업", "할인 혹은 행사", "실적 또는 사업", "기타"]


def latest(pattern: str) -> Path:
    matches = sorted(PROCESSED.glob(pattern), key=lambda path: path.stat().st_mtime)
    if not matches:
        raise FileNotFoundError(f"분석 데이터 파일을 찾지 못했습니다: {pattern}")
    return matches[-1]


@st.cache_data(show_spinner="분석 데이터를 불러오는 중…")
def load_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    news_path = latest("naver_news_3brands_50each_categorized_*.csv")
    trend_path = latest("brand_search_trend_monthly_*.csv")
    weight_path = latest("news_keyword_weights_bow_tfidf_*.csv")
    comparison_path = latest("news_keyword_method_comparison_*.csv")

    news = pd.read_csv(news_path, encoding="utf-8-sig")
    news["날짜"] = pd.to_datetime(news["날짜"], errors="coerce", utc=True).dt.tz_convert("Asia/Seoul").dt.tz_localize(None)
    # Shared articles are tagged for each queried brand, so explode to support brand filters.
    news["브랜드"] = news["브랜드"].fillna("").str.split(" / ")
    news = news.explode("브랜드").reset_index(drop=True)

    trend = pd.read_csv(trend_path, encoding="utf-8-sig")
    trend["월"] = pd.to_datetime(trend["월"], errors="coerce")
    weights = pd.read_csv(weight_path, encoding="utf-8-sig")
    comparison = pd.read_csv(comparison_path, encoding="utf-8-sig")
    return news, trend, weights, comparison


def slug_brand(brand: str) -> str:
    return {"유니클로": "uniqlo", "스파오": "spao", "탑텐": "topten"}[brand]


def slug_topic(topic: str) -> str:
    return {
        "제품 출시": "product_launch",
        "협업": "collaboration",
        "할인 혹은 행사": "discount_event",
        "실적 또는 사업": "performance_business",
        "기타": "other",
    }[topic]


def style_chart(fig: go.Figure, height: int = 400) -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=12, r=12, t=54, b=12),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Malgun Gothic, sans-serif", color="#334155"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode="x unified",
    )
    fig.update_xaxes(showgrid=False, linecolor="#E2E8F0")
    fig.update_yaxes(gridcolor="#E8EDF3", zeroline=False)
    return fig


def main() -> None:
    st.set_page_config(page_title="SPA 브랜드 경쟁 분석", page_icon="📊", layout="wide", initial_sidebar_state="expanded")
    st.markdown(
        """
        <style>
        .stApp { background: #F5F7FB; }
        [data-testid="stHeader"] { background: rgba(0,0,0,0); }
        .block-container { padding-top: 1.5rem; padding-bottom: 3rem; max-width: 1500px; }
        div[data-testid="stMetric"] { background: white; border: 1px solid #E7ECF3; padding: 16px 18px; border-radius: 14px; }
        div[data-testid="stMetricLabel"] { color: #64748B; }
        div[data-testid="stMetricValue"] { color: #172033; }
        .hero { background: linear-gradient(120deg,#172554,#1E3A8A 60%,#0F766E); padding: 25px 28px; border-radius: 18px; color: white; margin: 0 0 20px; }
        .hero h1 { margin: 0 0 6px; font-size: 30px; color: white; }
        .hero p { margin: 0; color: #DCE7FA; font-size: 14px; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    try:
        news, trend, weights, comparison = load_data()
    except (FileNotFoundError, KeyError, ValueError) as exc:
        st.error(f"대시보드 데이터를 불러오지 못했습니다: {exc}")
        st.stop()

    with st.sidebar:
        st.markdown("### 분석 조건")
        selected_brands = st.multiselect("브랜드", BRANDS, default=BRANDS)
        selected_topics = st.multiselect("뉴스 주제", TOPIC_ORDER, default=TOPIC_ORDER)
        st.divider()
        st.caption("데이터 출처: NAVER API HUB 검색어트렌드 및 뉴스 검색 API")
        st.caption("최신 기사 데이터와 저장된 검색 추이 데이터를 함께 탐색합니다.")

    if not selected_brands:
        st.warning("브랜드를 하나 이상 선택해 주세요.")
        st.stop()
    filtered_news = news[news["브랜드"].isin(selected_brands) & news["주제"].isin(selected_topics)].copy()
    filtered_trend = trend[trend["브랜드"].isin(selected_brands)].copy()
    filtered_weights = weights[weights["브랜드"].isin(selected_brands) & weights["주제"].isin(selected_topics)].copy()
    filtered_comparison = comparison[comparison["브랜드"].isin(selected_brands) & comparison["주제"].isin(selected_topics)].copy()

    st.markdown(
        "<div class='hero'><h1>SPA 브랜드 경쟁 분석</h1><p>뉴스 150건의 주제·키워드와 2022–2026 네이버 검색 관심도를 한곳에서 비교합니다.</p></div>",
        unsafe_allow_html=True,
    )

    overview_tab, news_tab, keyword_tab, trend_tab, method_tab = st.tabs(["한눈에 보기", "뉴스 탐색", "키워드 분석", "검색 추이", "데이터 기준"])

    with overview_tab:
        brand_counts = news.groupby("브랜드")["원문 링크"].nunique().reindex(BRANDS, fill_value=0)
        overall_trend = trend[trend["구분"] == "전체"]
        period = f"{overall_trend['월'].min():%Y.%m} – {overall_trend['월'].max():%Y.%m}"
        avg = overall_trend.groupby("브랜드")["검색지수"].mean()
        leader = avg.idxmax() if len(avg) else "-"
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("정리된 뉴스", f"{news['원문 링크'].nunique():,}건", "중복 URL 통합")
        c2.metric("브랜드별 기사", "50건", "각 브랜드 검색 결과 기준")
        c3.metric("검색 추이 기간", period, "월간 데이터")
        c4.metric("기간 평균 지수 선두", leader, f"상대 지수 {avg.get(leader, 0):.1f}")

        left, right = st.columns([1.45, 1])
        with left:
            st.subheader("월간 검색 관심도")
            fig = px.line(overall_trend, x="월", y="검색지수", color="브랜드", markers=True,
                          color_discrete_map=BRAND_COLORS, labels={"월": "월", "검색지수": "상대 검색지수", "브랜드": "브랜드"})
            st.plotly_chart(style_chart(fig, 420), use_container_width=True)
            st.caption("3개 브랜드를 같은 요청에서 비교한 상대 지수입니다. 검색량 원수치나 시장점유율은 아닙니다.")
        with right:
            st.subheader("뉴스 주제 구성")
            topic_counts = news[news["브랜드"].isin(selected_brands)].groupby(["브랜드", "주제"]).size().reset_index(name="기사 수")
            fig = px.bar(topic_counts, x="주제", y="기사 수", color="브랜드", barmode="group",
                         category_orders={"주제": TOPIC_ORDER}, color_discrete_map=BRAND_COLORS,
                         labels={"주제": "주제", "기사 수": "기사 수", "브랜드": "브랜드"})
            st.plotly_chart(style_chart(fig, 420), use_container_width=True)
        st.subheader("최신 수집 기사")
        latest_news = filtered_news.sort_values("날짜", ascending=False).drop_duplicates("원문 링크").head(8)
        st.dataframe(latest_news[["브랜드", "주제", "날짜", "제목", "원문 링크"]], hide_index=True, use_container_width=True,
                     column_config={"날짜": st.column_config.DatetimeColumn(format="YYYY-MM-DD"), "원문 링크": st.column_config.LinkColumn("원문", display_text="기사 열기")})

    with news_tab:
        st.subheader("수집 뉴스 검색")
        search_text = st.text_input("제목·요약에서 검색", placeholder="예: 경량패딩, 협업, 매장")
        view = filtered_news.copy()
        if search_text.strip():
            mask = view["제목"].fillna("").str.contains(search_text, case=False, regex=False) | view["요약"].fillna("").str.contains(search_text, case=False, regex=False)
            view = view[mask]
        view = view.sort_values("날짜", ascending=False).drop_duplicates(["브랜드", "원문 링크"])
        st.caption(f"조건에 맞는 기사 {len(view):,}건")
        st.download_button("현재 결과 CSV 다운로드", view.to_csv(index=False).encode("utf-8-sig"), "brand_news_filtered.csv", "text/csv")
        st.dataframe(view[["브랜드", "주제", "날짜", "제목", "요약", "원문 링크"]], hide_index=True, use_container_width=True, height=620,
                     column_config={"날짜": st.column_config.DatetimeColumn(format="YYYY-MM-DD HH:mm"), "원문 링크": st.column_config.LinkColumn("원문", display_text="기사 열기"), "요약": st.column_config.TextColumn(width="large"), "제목": st.column_config.TextColumn(width="large")})

    with keyword_tab:
        st.subheader("BoW와 TF-IDF 키워드 비교")
        brand_for_cloud = st.selectbox("워드 클라우드 브랜드", selected_brands, key="cloud_brand")
        topic_for_cloud = st.selectbox("워드 클라우드 주제", selected_topics, key="cloud_topic")
        method_col1, method_col2 = st.columns([1, 1.4])
        group_compare = filtered_comparison[(filtered_comparison["브랜드"] == brand_for_cloud) & (filtered_comparison["주제"] == topic_for_cloud)]
        if not group_compare.empty:
            row = group_compare.iloc[0]
            method_col1.metric("분석 기사 수", f"{int(row['기사 수'])}건")
            method_col2.metric("BoW·TF-IDF 상위 10 공통", f"{int(row['겹침 수'])}개", f"겹침률 {row['겹침률']:.0%}")

        cloud_cols = st.columns(2)
        for col, method, suffix in zip(cloud_cols, ["BoW", "TF-IDF"], ["bow", "tfidf"]):
            filename = f"{slug_brand(brand_for_cloud)}_{slug_topic(topic_for_cloud)}_{suffix}.png"
            image_path = WORDCLOUD_DIR / filename
            with col:
                st.markdown(f"#### {method} 워드 클라우드")
                if image_path.exists():
                    st.image(str(image_path), use_container_width=True)
                else:
                    st.info("이 조합의 워드 클라우드는 데이터가 없어 제공되지 않습니다.")

        st.markdown("#### 상위 키워드 나란히 보기")
        group_weights = filtered_weights[(filtered_weights["브랜드"] == brand_for_cloud) & (filtered_weights["주제"] == topic_for_cloud)]
        if not group_weights.empty:
            bow, tfidf = st.columns(2)
            for col, method in [(bow, "BoW"), (tfidf, "TF-IDF")]:
                with col:
                    st.markdown(f"**{method}**")
                    table = group_weights[group_weights["방법"] == method].sort_values("순위").head(15)[["순위", "키워드", "점수"]]
                    st.dataframe(table, hide_index=True, use_container_width=True)
            st.markdown("#### 방법 간 공통점")
            st.write(f"공통 키워드: {row['공통 키워드'] if not group_compare.empty else '비교 데이터 없음'}")
        st.caption("BoW는 그룹 내 출현 빈도 합계, TF-IDF는 기사별 정규화 가중치 평균입니다. 한국어는 경량 공백 토큰화·규칙 기반 정리 결과입니다.")

    with trend_tab:
        st.subheader("연령대별 월간 검색 추이")
        age_options = ["전체"] + sorted(filtered_trend.loc[filtered_trend["구분"] == "연령", "연령"].unique(), key=lambda x: int(re.match(r"\d+", x).group()))
        age_choice = st.selectbox("비교할 연령대", age_options, index=0)
        if age_choice == "전체":
            chart_data = filtered_trend[filtered_trend["구분"] == "전체"]
        else:
            chart_data = filtered_trend[(filtered_trend["구분"] == "연령") & (filtered_trend["연령"] == age_choice)]
        fig = px.line(chart_data, x="월", y="검색지수", color="브랜드", markers=True,
                      color_discrete_map=BRAND_COLORS, labels={"월": "월", "검색지수": "상대 검색지수", "브랜드": "브랜드"})
        st.plotly_chart(style_chart(fig, 490), use_container_width=True)
        if age_choice == "전체":
            st.caption("전체 추이는 세 브랜드를 같은 API 요청에서 비교한 지수입니다.")
        else:
            st.caption("선택한 연령대 안에서 세 브랜드를 비교할 수 있습니다. 서로 다른 연령대의 지수는 별도 정규화되어 연령 간 절대 비교에 사용할 수 없습니다.")
        age_data = filtered_trend[filtered_trend["구분"] == "연령"]
        if not age_data.empty:
            age_avg = age_data.groupby(["연령", "브랜드"], as_index=False)["검색지수"].mean()
            st.markdown("#### 연령대별 기간 평균 상대지수")
            st.caption("각 연령대 안에서 브랜드 간 평균 지수를 비교하세요. 연령대 간 평균값 자체는 직접 비교할 수 없습니다.")
            age_fig = px.line(age_avg, x="연령", y="검색지수", color="브랜드", markers=True,
                              category_orders={"연령": [age for age in age_options if age != "전체"]}, color_discrete_map=BRAND_COLORS,
                              labels={"연령": "연령대", "검색지수": "기간 평균 상대지수", "브랜드": "브랜드"})
            st.plotly_chart(style_chart(age_fig, 400), use_container_width=True)
        st.download_button("검색 추이 CSV 다운로드", filtered_trend.to_csv(index=False).encode("utf-8-sig"), "brand_search_trend_filtered.csv", "text/csv")

    with method_tab:
        st.subheader("데이터·분석 기준")
        st.markdown(
            """
            - **뉴스:** 네이버 뉴스 검색 결과를 브랜드별 최대 50건씩 검토·정리하고 제품 출시, 협업, 할인·행사, 실적·사업, 기타로 분류했습니다.
            - **검색 추이:** 2022년 1월부터 2026년 9월까지 월별 NAVER 통합검색 상대지수입니다. 브랜드별 한글·영문 표기를 한 그룹으로 구성했습니다.
            - **연령:** 네이버 API 연령 구간(0–12세, 13–18세, 이후 5세 단위, 60세 이상)을 사용했습니다.
            - **비교 해석:** 검색지수는 검색 횟수·매출·시장점유율이 아닙니다. 연령별 요청은 각 연령대에서 별도로 정규화되므로 같은 연령대 안에서 브랜드를 비교합니다.
            - **키워드:** BoW는 출현 빈도를, TF-IDF는 문서별 상대적 특징성을 반영합니다. 형태소 분석기가 아닌 경량 규칙 기반 토큰 처리이므로 복합어·어형에 오차가 있을 수 있습니다.
            """)
        st.markdown("#### 원본 보고서")
        reports = [
            ("뉴스 품질 검토", "naver_news_quality_review_*.md"),
            ("뉴스 주제 분류", "naver_news_3brands_topic_classification_*.md"),
            ("키워드 비교", "news_keyword_comparison_*.md"),
            ("검색 추이 경쟁 분석", "brand_search_trend_analysis_*.md"),
        ]
        for label, pattern in reports:
            matches = sorted(PROCESSED.glob(pattern), key=lambda p: p.stat().st_mtime)
            if matches:
                with st.expander(label):
                    st.markdown(matches[-1].read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
