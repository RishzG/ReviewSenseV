"""Business Intelligence Report Generator.

Generates structured reports using:
- Pre-computed gold mart stats (instant, no on-the-fly computation)
- CLASSIFY_TEXT themes (accurate, not keyword matching)
- Cortex Search for evidence quotes (targeted retrieval)
- COMPLETE for narrative only (does not compute stats)
"""

import json
from api.db import get_cursor
from api.config import settings


def _business_signal(avg_rating, negative_rate):
    avg_rating = float(avg_rating)
    negative_rate = float(negative_rate)
    if avg_rating < 3.5 or negative_rate > 0.30:
        return "RED"
    elif avg_rating < 4.0 or negative_rate > 0.15:
        return "YELLOW"
    return "GREEN"


def _search_reviews(query: str, limit: int = 5) -> list[dict]:
    """Fetch review quotes via Cortex Search."""
    with get_cursor() as cur:
        search_query = json.dumps({
            "query": query,
            "columns": ["REVIEW_TEXT_CLEAN", "RATING", "ASIN"],
            "limit": limit,
        })
        cur.execute(
            f"""
            SELECT PARSE_JSON(
                SNOWFLAKE.CORTEX.SEARCH_PREVIEW(
                    '{settings.search_service}',
                    %s
                )
            ) AS results
            """,
            (search_query,)
        )
        row = cur.fetchone()
        if not row or not row[0]:
            return []

        search_results = json.loads(row[0]) if isinstance(row[0], str) else row[0]
        return [
            {
                "text": r.get("REVIEW_TEXT_CLEAN", "")[:300],
                "rating": r.get("RATING", ""),
                "asin": r.get("ASIN", ""),
            }
            for r in search_results.get("results", [])
        ]


def _generate_narrative(prompt: str) -> str:
    """Call COMPLETE for narrative generation."""
    with get_cursor() as cur:
        cur.execute(
            "SELECT SNOWFLAKE.CORTEX.COMPLETE(%s, %s)",
            (settings.llm_model, prompt)
        )
        return cur.fetchone()[0]


def generate_category_report(category: str) -> dict | None:
    """Generate a full business intelligence report for a product category."""
    with get_cursor() as cur:
        # 1. Category overview
        cur.execute("""
            SELECT DERIVED_CATEGORY, REVIEW_COUNT, AVG_RATING, AVG_SENTIMENT,
                   MEDIAN_SENTIMENT, NEGATIVE_REVIEW_COUNT, POSITIVE_REVIEW_COUNT,
                   NEGATIVE_RATE, VERIFIED_COUNT, AVG_HELPFUL_VOTES
            FROM GOLD.CATEGORY_SENTIMENT_SUMMARY
            WHERE DERIVED_CATEGORY = %s
        """, (category,))
        overview = cur.fetchone()
        if not overview:
            return None

        # 2. Overall averages for comparison
        cur.execute("""
            SELECT ROUND(AVG(AVG_RATING), 2), ROUND(AVG(AVG_SENTIMENT), 4),
                   ROUND(AVG(NEGATIVE_RATE), 4)
            FROM GOLD.CATEGORY_SENTIMENT_SUMMARY
        """)
        overall = cur.fetchone()

        # 3. Theme breakdown
        cur.execute("""
            SELECT REVIEW_THEME, REVIEW_COUNT, AVG_RATING, AVG_SENTIMENT, NEGATIVE_RATE
            FROM GOLD.THEME_CATEGORY_ANALYSIS
            WHERE DERIVED_CATEGORY = %s
            ORDER BY REVIEW_COUNT DESC
        """, (category,))
        themes = [
            {"theme": r[0], "review_count": r[1], "avg_rating": float(r[2]),
             "avg_sentiment": float(r[3]), "negative_rate": float(r[4])}
            for r in cur.fetchall()
        ]

        # 4. Complaint breakdown
        cur.execute("""
            SELECT REVIEW_THEME, COMPLAINT_COUNT, AVG_SENTIMENT, AVG_HELPFUL_VOTES,
                   HIGH_QUALITY_COMPLAINTS, HIGH_QUALITY_RATE
            FROM GOLD.COMPLAINT_ANALYSIS
            WHERE DERIVED_CATEGORY = %s
            ORDER BY COMPLAINT_COUNT DESC
        """, (category,))
        complaints = [
            {"theme": r[0], "complaint_count": r[1], "avg_sentiment": float(r[2]),
             "avg_helpful_votes": float(r[3]), "high_quality": r[4],
             "high_quality_rate": float(r[5])}
            for r in cur.fetchall()
        ]

        # 5. Recent trend (last 6 months)
        cur.execute("""
            SELECT REVIEW_MONTH, REVIEW_COUNT, AVG_RATING, AVG_SENTIMENT, NEGATIVE_RATE
            FROM GOLD.CATEGORY_MONTHLY_TRENDS
            WHERE DERIVED_CATEGORY = %s
            ORDER BY REVIEW_MONTH DESC
            LIMIT 6
        """, (category,))
        trends = [
            {"month": str(r[0]), "review_count": r[1], "avg_rating": float(r[2]),
             "avg_sentiment": float(r[3]), "negative_rate": float(r[4])}
            for r in cur.fetchall()
        ]

    signal = _business_signal(overview[2], overview[7])

    # 6. Get evidence quotes for top complaint theme
    top_complaint = complaints[0]["theme"] if complaints else "quality issues"
    negative_evidence = _search_reviews(
        f"{category} {top_complaint} problems complaints disappointed", limit=4
    )
    positive_evidence = _search_reviews(
        f"{category} great excellent love recommend best", limit=3
    )

    # 7. Build stats context for narrative
    stats_block = (
        f"Category: {category}\n"
        f"Total Reviews: {overview[1]}\n"
        f"Average Rating: {overview[2]}/5 (overall avg: {overall[0]}/5)\n"
        f"Average Sentiment: {overview[3]} (overall avg: {overall[1]})\n"
        f"Negative Rate: {float(overview[7])*100:.1f}% (overall avg: {float(overall[2])*100:.1f}%)\n"
        f"Positive Reviews: {overview[6]}, Negative Reviews: {overview[5]}\n"
        f"Business Signal: {signal}\n"
    )

    theme_block = "Theme Breakdown:\n"
    for t in themes[:7]:
        theme_block += f"- {t['theme']}: {t['review_count']} reviews, rating {t['avg_rating']}, sentiment {t['avg_sentiment']}, negative rate {t['negative_rate']*100:.1f}%\n"

    complaint_block = "Top Complaints (1-2 star reviews only):\n"
    for c in complaints[:5]:
        complaint_block += f"- {c['theme']}: {c['complaint_count']} complaints, sentiment {c['avg_sentiment']}, helpful votes avg {c['avg_helpful_votes']}\n"

    evidence_block = "Negative review quotes:\n"
    for e in negative_evidence:
        evidence_block += f'- [Rating: {e["rating"]}/5] "{e["text"][:200]}"\n'
    evidence_block += "\nPositive review quotes:\n"
    for e in positive_evidence:
        evidence_block += f'- [Rating: {e["rating"]}/5] "{e["text"][:200]}"\n'

    # 8. Generate narrative
    narrative = _generate_narrative(
        f"""Be precise and factual. You are a product intelligence analyst.
Generate a business intelligence report using ONLY the data below.
Use exact numbers. Quote directly from reviews.

=== DATA ===
{stats_block}
{theme_block}
{complaint_block}
{evidence_block}
=== END DATA ===

Write these sections:
1. Executive Summary (3-4 sentences, consistent with {signal} signal)
2. Key Strengths (top 2-3, with customer quotes)
3. Critical Issues (top 2-3, with customer quotes and complaint counts)
4. Recommended Actions (3 specific priorities with suggested owners: Engineering/Design/QA/Support)

Do not invent statistics or quotes not in the data."""
    )

    return {
        "category": category,
        "signal": signal,
        "narrative": narrative,
        "stats": {
            "review_count": overview[1],
            "avg_rating": float(overview[2]),
            "avg_sentiment": float(overview[3]),
            "negative_rate": float(overview[7]),
            "positive_reviews": overview[6],
            "negative_reviews": overview[5],
            "verified_count": overview[8],
            "avg_helpful_votes": float(overview[9]),
        },
        "overall_comparison": {
            "avg_rating": float(overall[0]),
            "avg_sentiment": float(overall[1]),
            "negative_rate": float(overall[2]),
        },
        "themes": themes,
        "complaints": complaints,
        "trends": trends,
        "evidence": {
            "negative": negative_evidence,
            "positive": positive_evidence,
        },
    }


def generate_product_report(asin: str) -> dict | None:
    """Generate a business intelligence report for a specific product."""
    with get_cursor() as cur:
        # 1. Product stats
        cur.execute("""
            SELECT p.ASIN, p.DERIVED_CATEGORY, p.REVIEW_COUNT, p.AVG_RATING,
                   p.AVG_SENTIMENT, p.NEGATIVE_RATE, p.TOP_THEME,
                   l.BRAND, l.PRODUCT_NAME
            FROM GOLD.PRODUCT_SENTIMENT_SUMMARY p
            LEFT JOIN GOLD.PRODUCT_LOOKUP l ON p.ASIN = l.ASIN
            WHERE p.ASIN = %s
        """, (asin,))
        product = cur.fetchone()
        if not product:
            return None

        category = product[1]

        # 2. Category averages for comparison
        cur.execute("""
            SELECT AVG_RATING, AVG_SENTIMENT, NEGATIVE_RATE
            FROM GOLD.CATEGORY_SENTIMENT_SUMMARY
            WHERE DERIVED_CATEGORY = %s
        """, (category,))
        cat_avg = cur.fetchone()

        # 3. Theme breakdown for this product
        cur.execute("""
            SELECT REVIEW_THEME, COUNT(*) AS cnt,
                   ROUND(AVG(SENTIMENT_SCORE), 3) AS avg_sent,
                   ROUND(AVG(RATING), 2) AS avg_rat,
                   COUNT(CASE WHEN RATING <= 2 THEN 1 END) AS neg_cnt
            FROM GOLD.ENRICHED_REVIEWS
            WHERE ASIN = %s
            GROUP BY REVIEW_THEME
            ORDER BY cnt DESC
        """, (asin,))
        themes = [
            {"theme": r[0], "review_count": r[1], "avg_sentiment": float(r[2]),
             "avg_rating": float(r[3]), "negative_count": r[4]}
            for r in cur.fetchall()
        ]

    signal = _business_signal(product[3], product[5])
    brand = (product[7] or "Unknown").replace("\n", "").strip()
    prod_name = (product[8] or asin).replace("\n", "").strip()
    display_name = f"{brand} - {prod_name}" if brand != "Unknown" else prod_name

    # 4. Evidence quotes
    negative_evidence = _search_reviews(
        f"{asin} problems complaints disappointed broken", limit=4
    )
    positive_evidence = _search_reviews(
        f"{asin} great excellent love recommend amazing", limit=3
    )

    # 5. Build narrative
    stats_block = (
        f"Product: {display_name}\n"
        f"ASIN: {asin}\n"
        f"Category: {category}\n"
        f"Reviews: {product[2]}\n"
        f"Average Rating: {product[3]}/5 (category avg: {float(cat_avg[0])}/5)\n"
        f"Average Sentiment: {product[4]} (category avg: {float(cat_avg[1])})\n"
        f"Negative Rate: {float(product[5])*100:.1f}% (category avg: {float(cat_avg[2])*100:.1f}%)\n"
        f"Top Theme: {product[6]}\n"
        f"Signal: {signal}\n"
    )

    theme_block = "Theme Breakdown:\n"
    for t in themes[:7]:
        theme_block += f"- {t['theme']}: {t['review_count']} reviews, sentiment {t['avg_sentiment']}, {t['negative_count']} negative\n"

    evidence_block = "Negative review quotes:\n"
    for e in negative_evidence:
        evidence_block += f'- [Rating: {e["rating"]}/5] "{e["text"][:200]}"\n'
    evidence_block += "\nPositive review quotes:\n"
    for e in positive_evidence:
        evidence_block += f'- [Rating: {e["rating"]}/5] "{e["text"][:200]}"\n'

    narrative = _generate_narrative(
        f"""Be precise and factual. You are a product intelligence analyst.
Generate a product report using ONLY the data below.

=== DATA ===
{stats_block}
{theme_block}
{evidence_block}
=== END DATA ===

Write these sections:
1. Executive Summary (3-4 sentences, consistent with {signal} signal, compare to category average)
2. Strengths (top 2-3, with customer quotes)
3. Issues (top 2-3, with customer quotes and review counts)
4. Recommended Actions (3 priorities)

Do not invent statistics or quotes not in the data."""
    )

    return {
        "asin": asin,
        "product_name": display_name,
        "category": category,
        "signal": signal,
        "narrative": narrative,
        "stats": {
            "review_count": product[2],
            "avg_rating": float(product[3]),
            "avg_sentiment": float(product[4]),
            "negative_rate": float(product[5]),
            "top_theme": product[6],
        },
        "category_comparison": {
            "avg_rating": float(cat_avg[0]),
            "avg_sentiment": float(cat_avg[1]),
            "negative_rate": float(cat_avg[2]),
        },
        "themes": themes,
        "evidence": {
            "negative": negative_evidence,
            "positive": positive_evidence,
        },
    }
