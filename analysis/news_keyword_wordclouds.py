"""Create BoW/TF-IDF keyword comparisons and Korean word clouds for the curated news set."""

from __future__ import annotations

import csv
import html
import math
import random
import re
import zlib
from collections import Counter, defaultdict
from pathlib import Path
from unicodedata import normalize

from PIL import Image, ImageDraw, ImageFont
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "processed" / "naver_news_3brands_50each_categorized_20261031.csv"
KEYWORD_CSV = ROOT / "data" / "processed" / "news_keyword_weights_bow_tfidf_20261031.csv"
REPORT_MD = ROOT / "data" / "processed" / "news_keyword_comparison_20261031.md"
GALLERY = ROOT / "outputs" / "figures" / "news_wordclouds" / "index.html"
IMAGE_DIR = GALLERY.parent
FONT_PATH = Path("C:/Windows/Fonts/malgun.ttf")

BRANDS = {
    "유니클로": "uniqlo",
    "스파오": "spao",
    "탑텐": "topten",
}
CATEGORIES = {
    "제품 출시": "product_launch",
    "협업": "collaboration",
    "할인 혹은 행사": "discount_event",
    "실적 또는 사업": "performance_business",
    "기타": "other",
}
METHODS = {"BoW": "bow", "TF-IDF": "tfidf"}

STOPWORDS = {
    "가운데", "관련", "경우", "계획", "공개", "기자", "기준", "기존", "기자", "기록",
    "기획", "내용", "대상", "대해", "대해서", "동안", "등장", "때문", "모습", "모든",
    "발표", "밝혔다", "보도", "보도자료", "사업", "사진", "설명", "소개", "수준", "시작",
    "위해", "이번", "이날", "이후", "이유", "일환", "자체", "전했다", "전후", "제공",
    "주요", "중심", "지난", "지난해", "현재", "통해", "특히", "포함", "확인", "활용",
    "회장", "회사", "올해", "내년", "최근", "작년", "한편", "계속", "관련해", "등을",
    "브랜드", "브랜드별", "뉴스", "패션", "업계", "유통", "소비자", "고객", "제품", "상품",
    "유니클로", "유니클", "스파오", "탑텐", "탑텐키즈", "topten", "uniqlo", "spao", "spa",
    "무신사", "이랜드", "신성통상", "한국", "일본", "서울", "2026", "2025", "2024",
    "있다", "했다", "된다", "됐다", "한다", "했다", "위한", "따른", "등으",
}

# Strip common Korean postpositions/endings after whitespace tokenization. This keeps
# the workflow dependency-light while reducing variants such as 매출은/매출이.
SUFFIXES = sorted(
    {
        "으로부터", "에게서는", "으로서는", "으로부터", "에서부터", "에서처럼", "에게까지",
        "에서는", "으로는", "으로도", "에게는", "에게서", "으로서", "에 대한", "이라고",
        "이라는", "이라며", "하면서", "에서도", "에게", "에서", "으로", "로부터", "부터",
        "까지", "처럼", "보다", "하고", "이며", "에는", "의", "와", "과", "도", "만",
        "로", "에", "들", "은", "는", "이", "가", "을", "를",
    },
    key=len,
    reverse=True,
)

PALETTE = ["#155E75", "#0F766E", "#1D4ED8", "#C2410C", "#6D28D9", "#334155"]


def tokenize(text: str) -> list[str]:
    text = normalize("NFKC", html.unescape(re.sub(r"<[^>]+>", " ", text or ""))).lower()
    tokens: list[str] = []
    for raw in re.findall(r"[가-힣a-zA-Z0-9]+", text):
        word = raw
        # Exclude years, dates, sizes, prices and other number-attached fragments.
        if any(ch.isdigit() for ch in word) or len(word) < 2:
            continue
        for suffix in SUFFIXES:
            if len(word) >= len(suffix) + 2 and word.endswith(suffix):
                word = word[: -len(suffix)]
                break
        if (
            len(word) < 2
            or word in STOPWORDS
            or word.startswith("유니클")
            or word.startswith("탑텐")
            or re.fullmatch(r"[a-z0-9]+", word)
        ):
            continue
        tokens.append(word)
    return tokens


def font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_PATH), size=size)


def boxes_overlap(a: tuple[int, int, int, int], b: tuple[int, int, int, int], gap: int = 5) -> bool:
    return not (
        a[2] + gap <= b[0]
        or b[2] + gap <= a[0]
        or a[3] + gap <= b[1]
        or b[3] + gap <= a[1]
    )


def render_cloud(words: list[tuple[str, float]], title: str, subtitle: str, destination: Path, seed: int) -> None:
    width, height = 900, 650
    image = Image.new("RGB", (width, height), "#F8FAFC")
    draw = ImageDraw.Draw(image)
    draw.text((34, 20), title, font=font(31), fill="#0F172A")
    draw.text((35, 59), subtitle, font=font(19), fill="#475569")

    area = (32, 104, width - 32, height - 24)
    center_x = (area[0] + area[2]) // 2
    center_y = (area[1] + area[3]) // 2
    max_score = max((score for _, score in words), default=1.0) or 1.0
    placed: list[tuple[int, int, int, int]] = []
    rng = random.Random(seed)

    for index, (word, score) in enumerate(words[:34]):
        scale = math.sqrt(max(score, 0.0) / max_score)
        base_size = max(20, int(25 + 62 * scale))
        done = False
        for size in range(base_size, 16, -4):
            fnt = font(size)
            left, top, right, bottom = draw.textbbox((0, 0), word, font=fnt)
            text_width, text_height = right - left, bottom - top
            for attempt in range(700):
                # Gaussian placement makes a compact, center-weighted cloud while
                # allowing later words to spread across the full canvas.
                x = int(rng.gauss(center_x, width / 5) - text_width / 2)
                y = int(rng.gauss(center_y, height / 5) - text_height / 2)
                rect = (x, y, x + text_width, y + text_height)
                if rect[0] < area[0] or rect[1] < area[1] or rect[2] > area[2] or rect[3] > area[3]:
                    continue
                if any(boxes_overlap(rect, prev) for prev in placed):
                    continue
                color = PALETTE[(index + rng.randrange(len(PALETTE))) % len(PALETTE)]
                draw.text((x, y), word, font=fnt, fill=color)
                placed.append(rect)
                done = True
                break
            if done:
                break

    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination, format="PNG", optimize=True)


def markdown_table(rows: list[tuple[str, float]]) -> str:
    return "\n".join(["| 순위 | 키워드 | 점수 |", "|---:|---|---:|"] + [f"| {i} | {word} | {score:.4f} |" for i, (word, score) in enumerate(rows[:10], 1)])


def main() -> None:
    if not SOURCE.exists():
        raise FileNotFoundError(SOURCE)
    if not FONT_PATH.exists():
        raise FileNotFoundError(f"Korean font not found: {FONT_PATH}")

    with SOURCE.open(encoding="utf-8-sig", newline="") as f:
        articles = list(csv.DictReader(f))

    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for article in articles:
        for brand in article["브랜드"].split(" / "):
            grouped[(brand, article["주제"])].append(article)

    all_scores: list[dict[str, object]] = []
    comparison: list[dict[str, object]] = []
    images: dict[tuple[str, str, str], str] = {}
    report = [
        "# 브랜드·주제별 BoW / TF-IDF 키워드 비교",
        "",
        "- 원자료: 최종 분류된 뉴스 50건씩 (같은 URL은 브랜드 태그로 연결)",
        "- 분석 문서: 기사 제목과 요약을 합친 텍스트. 동일 기사는 해당 브랜드 태그마다 집계합니다.",
        "- 토큰 처리: 공백 기반 한국어 토큰화, 기본 조사/어미 제거, 일반 뉴스어와 분석 대상 브랜드명 제외",
        "- BoW 점수: 그룹 내 토큰 출현 횟수 합계",
        "- TF-IDF 점수: 기사별 L2 정규화 TF-IDF 가중치의 그룹 평균",
        "- 워드 클라우드 크기는 각 방법 내부 점수에 비례합니다. 그룹 간 글자 크기를 직접 비교하면 안 됩니다.",
        "- 한국어 형태소 분석기 대신 경량 토큰 정리를 사용했으므로 일부 조사 결합형/복합명사는 남을 수 있습니다.",
        "",
        "## 그룹별 문서 수와 방법 간 상위 10개 키워드 겹침",
        "",
        "| 브랜드 | 주제 | 기사 수 | 상위 10개 겹침 | 겹침률 |",
        "|---|---|---:|---:|---:|",
    ]

    category_order = ["제품 출시", "협업", "할인 혹은 행사", "실적 또는 사업", "기타"]
    for brand in BRANDS:
        for category in category_order:
            docs = grouped.get((brand, category), [])
            if not docs:
                continue
            texts = [f"{row['제목']} {row['요약']}" for row in docs]
            bow = CountVectorizer(tokenizer=tokenize, token_pattern=None, lowercase=False, min_df=1)
            bow_matrix = bow.fit_transform(texts)
            bow_totals = bow_matrix.sum(axis=0).A1
            bow_words = bow.get_feature_names_out()
            bow_scores = sorted(zip(bow_words, bow_totals), key=lambda x: (-float(x[1]), x[0]))

            tfidf = TfidfVectorizer(
                tokenizer=tokenize,
                token_pattern=None,
                lowercase=False,
                min_df=1,
                sublinear_tf=True,
                smooth_idf=True,
                norm="l2",
            )
            tfidf_matrix = tfidf.fit_transform(texts)
            tfidf_means = tfidf_matrix.mean(axis=0).A1
            tfidf_words = tfidf.get_feature_names_out()
            tfidf_scores = sorted(zip(tfidf_words, tfidf_means), key=lambda x: (-float(x[1]), x[0]))

            bow_top10 = {word for word, _ in bow_scores[:10]}
            tfidf_top10 = {word for word, _ in tfidf_scores[:10]}
            overlap = bow_top10 & tfidf_top10
            overlap_rate = len(overlap) / 10
            comparison.append(
                {
                    "브랜드": brand,
                    "주제": category,
                    "기사 수": len(docs),
                    "BoW 상위 10": ", ".join(word for word, _ in bow_scores[:10]),
                    "TF-IDF 상위 10": ", ".join(word for word, _ in tfidf_scores[:10]),
                    "공통 키워드": ", ".join(sorted(overlap)),
                    "겹침 수": len(overlap),
                    "겹침률": overlap_rate,
                }
            )
            report.append(f"| {brand} | {category} | {len(docs)} | {len(overlap)} | {overlap_rate:.0%} |")

            for method_name, ranked in (("BoW", bow_scores), ("TF-IDF", tfidf_scores)):
                for rank, (term, score) in enumerate(ranked[:30], 1):
                    all_scores.append(
                        {
                            "브랜드": brand,
                            "주제": category,
                            "기사 수": len(docs),
                            "방법": method_name,
                            "순위": rank,
                            "키워드": term,
                            "점수": float(score),
                        }
                    )
                filename = f"{BRANDS[brand]}_{CATEGORIES[category]}_{METHODS[method_name]}.png"
                image_path = IMAGE_DIR / filename
                render_cloud(
                    [(word, float(score)) for word, score in ranked[:34]],
                    f"{brand} · {category}",
                    f"{method_name}  |  기사 {len(docs)}건",
                    image_path,
                    seed=zlib.crc32(f"{brand}|{category}|{method_name}".encode("utf-8")),
                )
                images[(brand, category, method_name)] = filename

            report += [
                "",
                f"## {brand} · {category} ({len(docs)}건)",
                "",
                f"BoW / TF-IDF 공통 상위 키워드: {', '.join(sorted(overlap)) if overlap else '없음'}",
                "",
                "### BoW 상위 10",
                "",
                markdown_table([(w, float(s)) for w, s in bow_scores]),
                "",
                "### TF-IDF 상위 10",
                "",
                markdown_table([(w, float(s)) for w, s in tfidf_scores]),
                "",
                f"워드 클라우드: [BoW](../../outputs/figures/news_wordclouds/{images[(brand, category, 'BoW')]}) · [TF-IDF](../../outputs/figures/news_wordclouds/{images[(brand, category, 'TF-IDF')]})",
                "",
            ]

    KEYWORD_CSV.parent.mkdir(parents=True, exist_ok=True)
    with KEYWORD_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["브랜드", "주제", "기사 수", "방법", "순위", "키워드", "점수"])
        writer.writeheader()
        writer.writerows(all_scores)

    comparison_csv = ROOT / "data" / "processed" / "news_keyword_method_comparison_20261031.csv"
    with comparison_csv.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(comparison[0].keys()))
        writer.writeheader()
        writer.writerows(comparison)

    REPORT_MD.write_text("\n".join(report), encoding="utf-8")

    page = [
        "<!doctype html><html lang='ko'><head><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width, initial-scale=1'>",
        "<title>브랜드별 BoW / TF-IDF 워드 클라우드</title>",
        "<style>body{font-family:'Malgun Gothic',sans-serif;background:#f1f5f9;color:#0f172a;margin:0;padding:32px}h1{margin-bottom:8px}p{color:#475569}.group{background:white;border-radius:14px;padding:22px;margin:24px 0;box-shadow:0 4px 18px #0f172a12}.pair{display:grid;grid-template-columns:1fr 1fr;gap:16px}.pair img{width:100%;height:auto;border:1px solid #e2e8f0;border-radius:8px}.label{font-weight:700;margin:6px 0}.meta{font-size:14px;color:#475569}@media(max-width:900px){.pair{grid-template-columns:1fr}}</style>",
        "</head><body><h1>브랜드·주제별 키워드 워드 클라우드</h1>",
        "<p>왼쪽은 BoW 출현 횟수, 오른쪽은 TF-IDF 평균 가중치입니다. 그룹 안에서 각각 비교하세요.</p>",
    ]
    for row in comparison:
        b, c = row["브랜드"], row["주제"]
        bow_file = images[(b, c, "BoW")]
        tf_file = images[(b, c, "TF-IDF")]
        page += [
            "<section class='group'>",
            f"<h2>{html.escape(b)} · {html.escape(c)}</h2>",
            f"<p class='meta'>기사 {row['기사 수']}건 · 상위 10개 공통 키워드 {row['겹침 수']}개 ({row['겹침률']:.0%})</p>",
            "<div class='pair'>",
            f"<div><div class='label'>BoW</div><img src='{bow_file}' alt='{html.escape(b)} {html.escape(c)} BoW word cloud'></div>",
            f"<div><div class='label'>TF-IDF</div><img src='{tf_file}' alt='{html.escape(b)} {html.escape(c)} TF-IDF word cloud'></div>",
            "</div>",
            f"<p class='meta'><b>BoW:</b> {html.escape(row['BoW 상위 10'])}<br><b>TF-IDF:</b> {html.escape(row['TF-IDF 상위 10'])}</p>",
            "</section>",
        ]
    page.append("</body></html>")
    GALLERY.write_text("\n".join(page), encoding="utf-8")
    print(f"groups={len(comparison)}; clouds={len(images)}; keywords={len(all_scores)}")
    print(f"gallery={GALLERY}")
    print(f"keyword_csv={KEYWORD_CSV}")
    print(f"comparison_csv={comparison_csv}")
    print(f"report={REPORT_MD}")


if __name__ == "__main__":
    main()
