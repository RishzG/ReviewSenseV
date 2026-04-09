"""Custom agentic RAG tools.

Each tool is a self-contained function that queries Snowflake data.
Tools are called by the agent loop based on the user's question.
All tools return structured dicts — the agent synthesizes the final answer.
"""

import json
from api.db import get_cursor
from api.config import settings


# ============================================
# TOOL 1: search_reviews (enhanced)
# ============================================

def search_reviews(
    query: str,
    asin: str | None = None,
    category: str | None = None,
    theme: str | None = None,
    min_rating: int | None = None,
    max_rating: int | None = None,
    verified_only: bool = False,
    quality: str | None = None,
    limit: int = 5,
) -> dict:
    """Search reviews with optional filters on ASIN, category, theme, rating, quality.

    Uses GOLD.ENRICHED_REVIEW_SEARCH (Cortex Search Service) with structured filters.
    Returns review excerpts with metadata.

    Args:
        query: Natural language search query
        asin: Filter to a specific product ASIN
        category: Filter to a derived category (e.g., 'headphones_earbuds')
        theme: Filter to a review theme (e.g., 'battery_life')
        min_rating: Minimum star rating (1-5)
        max_rating: Maximum star rating (1-5)
        verified_only: Only return verified purchase reviews
        quality: Review quality tier ('high', 'medium', 'low')
        limit: Max results (default 5)

    Returns:
        dict with 'results' (list of review dicts) and 'query_info' (filter summary)
    """
    # Build filter object for Cortex Search
    filters = {}
    if asin:
        filters["@eq"] = {"ASIN": asin}
    if category:
        if "@eq" in filters:
            # Multiple eq filters need @and
            filters = {"@and": [{"@eq": {"ASIN": asin}}, {"@eq": {"DERIVED_CATEGORY": category}}]}
        else:
            filters["@eq"] = {"DERIVED_CATEGORY": category}
    if theme:
        eq_filter = {"@eq": {"REVIEW_THEME": theme}}
        if "@and" in filters:
            filters["@and"].append(eq_filter)
        elif "@eq" in filters:
            filters = {"@and": [{"@eq": filters["@eq"]}, eq_filter]}
        else:
            filters["@eq"] = {"REVIEW_THEME": theme}
    if max_rating and max_rating <= 2:
        # Filter for negative reviews (Cortex Search needs numeric, not string)
        lte_filter = {"@lte": {"RATING": max_rating}}
        if "@and" in filters:
            filters["@and"].append(lte_filter)
        elif "@eq" in filters:
            filters = {"@and": [{"@eq": filters["@eq"]}, lte_filter]}
        else:
            filters = lte_filter
    if min_rating and min_rating >= 4:
        # Filter for positive reviews (Cortex Search needs numeric, not string)
        gte_filter = {"@gte": {"RATING": min_rating}}
        if "@and" in filters:
            filters["@and"].append(gte_filter)
        elif "@eq" in filters:
            filters = {"@and": [{"@eq": filters["@eq"]}, gte_filter]}
        else:
            filters = gte_filter
    if verified_only:
        eq_filter = {"@eq": {"VERIFIED_PURCHASE": True}}
        if "@and" in filters:
            filters["@and"].append(eq_filter)
        elif "@eq" in filters:
            filters = {"@and": [{"@eq": filters["@eq"]}, eq_filter]}
        else:
            filters = eq_filter
    if quality:
        eq_filter = {"@eq": {"REVIEW_QUALITY": quality}}
        if "@and" in filters:
            filters["@and"].append(eq_filter)
        elif "@eq" in filters:
            filters = {"@and": [{"@eq": filters["@eq"]}, eq_filter]}
        else:
            filters = eq_filter

    # Build search query JSON
    search_params = {
        "query": query,
        "columns": ["REVIEW_TEXT_CLEAN", "RATING", "ASIN", "DERIVED_CATEGORY",
                     "REVIEW_THEME", "REVIEW_QUALITY"],
        "limit": limit,
    }
    if filters:
        search_params["filter"] = filters

    with get_cursor() as cur:
        cur.execute(
            f"""
            SELECT PARSE_JSON(
                SNOWFLAKE.CORTEX.SEARCH_PREVIEW(
                    '{settings.search_service}',
                    %s
                )
            ) AS results
            """,
            (json.dumps(search_params),)
        )
        row = cur.fetchone()

        if not row or not row[0]:
            return {
                "results": [],
                "query_info": {
                    "query": query,
                    "filters_applied": {k: v for k, v in {
                        "asin": asin, "category": category, "theme": theme,
                        "min_rating": min_rating, "max_rating": max_rating,
                        "verified_only": verified_only, "quality": quality,
                    }.items() if v},
                    "result_count": 0,
                },
            }

        search_results = json.loads(row[0]) if isinstance(row[0], str) else row[0]
        results = []
        for r in search_results.get("results", []):
            results.append({
                "text": r.get("REVIEW_TEXT_CLEAN", "")[:500],
                "rating": r.get("RATING", ""),
                "asin": r.get("ASIN", ""),
                "category": r.get("DERIVED_CATEGORY", ""),
                "theme": r.get("REVIEW_THEME", ""),
                "quality": r.get("REVIEW_QUALITY", ""),
            })

        return {
            "results": results,
            "query_info": {
                "query": query,
                "filters_applied": {k: v for k, v in {
                    "asin": asin, "category": category, "theme": theme,
                    "min_rating": min_rating, "max_rating": max_rating,
                    "verified_only": verified_only, "quality": quality,
                }.items() if v},
                "result_count": len(results),
            },
        }


# ============================================
# TOOL 2: get_product_detail
# ============================================

def get_product_detail(asin: str) -> dict | None:
    """Get complete product profile: metadata + review stats + theme breakdown.

    Combines data from PRODUCT_LOOKUP (review stats + metadata),
    PRODUCT_SENTIMENT_SUMMARY (aggregations), and ENRICHED_REVIEWS (theme breakdown).

    Args:
        asin: Amazon product ASIN

    Returns:
        dict with product info, review stats, themes, or None if not found
    """
    with get_cursor() as cur:
        # Product lookup with metadata
        cur.execute("""
            SELECT
                p.ASIN,
                p.DERIVED_CATEGORY,
                p.REVIEW_COUNT,
                p.DERIVATION_CONFIDENCE,
                COALESCE(p.METADATA_TITLE, p.PRODUCT_NAME) AS PRODUCT_NAME,
                COALESCE(p.METADATA_BRAND, p.BRAND) AS BRAND,
                p.METADATA_PRICE AS PRICE,
                p.METADATA_FEATURES AS FEATURES,
                p.METADATA_CATEGORY_PATH AS CATEGORY_PATH,
                p.HAS_METADATA
            FROM GOLD.PRODUCT_LOOKUP p
            WHERE p.ASIN = %s
        """, (asin,))
        lookup = cur.fetchone()

        if not lookup:
            return None

        result = {
            "asin": lookup[0],
            "category": lookup[1],
            "review_count": lookup[2],
            "product_name": lookup[4],
            "brand": lookup[5],
            "price": float(lookup[6]) if lookup[6] else None,
            "features": lookup[7],
            "category_path": lookup[8],
            "has_real_metadata": bool(lookup[9]),
        }

        # Product sentiment summary (only for 20+ review products)
        cur.execute("""
            SELECT AVG_RATING, AVG_SENTIMENT, NEGATIVE_RATE, TOP_THEME
            FROM GOLD.PRODUCT_SENTIMENT_SUMMARY
            WHERE ASIN = %s
        """, (asin,))
        stats = cur.fetchone()

        if stats:
            result["avg_rating"] = float(stats[0])
            result["avg_sentiment"] = float(stats[1])
            result["negative_rate"] = float(stats[2])
            result["top_theme"] = stats[3]
        else:
            result["avg_rating"] = None
            result["avg_sentiment"] = None
            result["negative_rate"] = None
            result["top_theme"] = None

        # Category averages for comparison
        if lookup[1]:  # has derived_category
            cur.execute("""
                SELECT AVG_RATING, AVG_SENTIMENT, NEGATIVE_RATE
                FROM GOLD.CATEGORY_SENTIMENT_SUMMARY
                WHERE DERIVED_CATEGORY = %s
            """, (lookup[1],))
            cat_avg = cur.fetchone()
            if cat_avg:
                result["category_avg_rating"] = float(cat_avg[0])
                result["category_avg_sentiment"] = float(cat_avg[1])
                result["category_avg_negative_rate"] = float(cat_avg[2])

                # Delta vs category
                if result["avg_rating"]:
                    result["rating_vs_category"] = round(result["avg_rating"] - float(cat_avg[0]), 2)
                    result["sentiment_vs_category"] = round(result["avg_sentiment"] - float(cat_avg[1]), 4)

        # Theme breakdown for this product
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
            {
                "theme": r[0],
                "review_count": r[1],
                "avg_sentiment": float(r[2]),
                "avg_rating": float(r[3]),
                "negative_count": r[4],
            }
            for r in cur.fetchall()
        ]
        result["themes"] = themes

        return result


# ============================================
# TOOL 3: search_products
# ============================================

def search_products(
    category: str | None = None,
    brand: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    features_contain: str | None = None,
    min_rating: float | None = None,
    min_reviews: int = 5,
    sort_by: str = "review_count",
    limit: int = 10,
) -> dict:
    """Search products by metadata criteria: price, features, brand, category, rating.

    Queries CURATED.PRODUCT_METADATA joined with GOLD.PRODUCT_SENTIMENT_SUMMARY
    for review stats. Pure SQL — no Cortex functions at query time.

    Args:
        category: Derived category filter (e.g., 'headphones_earbuds')
        brand: Brand name filter (case-insensitive partial match)
        min_price: Minimum price
        max_price: Maximum price
        features_contain: Keyword to search in product features (e.g., 'waterproof', 'noise cancelling')
        min_rating: Minimum average rating
        min_reviews: Minimum review count (default 5)
        sort_by: Sort field — 'review_count', 'avg_rating', 'price', 'avg_sentiment'
        limit: Max results (default 10)

    Returns:
        dict with 'products' list and 'search_criteria' summary
    """
    conditions = ["p.REVIEW_COUNT >= %s"]
    params = [min_reviews]

    if category:
        conditions.append("p.DERIVED_CATEGORY = %s")
        params.append(category)
    if brand:
        conditions.append("LOWER(COALESCE(m.BRAND, '')) LIKE %s")
        params.append(f"%{brand.lower()}%")
    if min_price is not None:
        conditions.append("m.PRICE >= %s")
        params.append(min_price)
    if max_price is not None:
        conditions.append("m.PRICE <= %s")
        params.append(max_price)
    if features_contain:
        conditions.append("LOWER(COALESCE(m.FEATURES_TEXT, '')) LIKE %s")
        params.append(f"%{features_contain.lower()}%")
    if min_rating:
        conditions.append("s.AVG_RATING >= %s")
        params.append(min_rating)

    where_clause = " AND ".join(conditions)

    sort_map = {
        "review_count": "p.REVIEW_COUNT DESC",
        "avg_rating": "s.AVG_RATING DESC NULLS LAST",
        "price": "m.PRICE ASC NULLS LAST",
        "avg_sentiment": "s.AVG_SENTIMENT DESC NULLS LAST",
    }
    order_by = sort_map.get(sort_by, "p.REVIEW_COUNT DESC")

    with get_cursor() as cur:
        cur.execute(f"""
            SELECT
                p.ASIN,
                COALESCE(p.METADATA_TITLE, p.PRODUCT_NAME) AS PRODUCT_NAME,
                COALESCE(p.METADATA_BRAND, p.BRAND) AS BRAND,
                m.PRICE,
                p.DERIVED_CATEGORY,
                p.REVIEW_COUNT,
                s.AVG_RATING,
                s.AVG_SENTIMENT,
                s.NEGATIVE_RATE,
                s.TOP_THEME,
                m.FEATURES_TEXT AS FEATURES_STR
            FROM GOLD.PRODUCT_LOOKUP p
            LEFT JOIN CURATED.PRODUCT_METADATA m ON p.ASIN = m.ASIN
            LEFT JOIN GOLD.PRODUCT_SENTIMENT_SUMMARY s ON p.ASIN = s.ASIN
            WHERE {where_clause}
            ORDER BY {order_by}
            LIMIT {limit}
        """, params)

        products = []
        for r in cur.fetchall():
            products.append({
                "asin": r[0],
                "product_name": r[1],
                "brand": r[2],
                "price": float(r[3]) if r[3] else None,
                "category": r[4],
                "review_count": r[5],
                "avg_rating": float(r[6]) if r[6] else None,
                "avg_sentiment": float(r[7]) if r[7] else None,
                "negative_rate": float(r[8]) if r[8] else None,
                "top_theme": r[9],
                "features": r[10][:300] if r[10] else None,
            })

        return {
            "products": products,
            "search_criteria": {k: v for k, v in {
                "category": category, "brand": brand,
                "min_price": min_price, "max_price": max_price,
                "features_contain": features_contain,
                "min_rating": min_rating, "min_reviews": min_reviews,
                "sort_by": sort_by,
            }.items() if v is not None},
            "result_count": len(products),
        }


# ============================================
# TOOL 4: compare_products
# ============================================

def compare_products(asins: list[str]) -> dict:
    """Side-by-side comparison of 2-5 products.

    Calls get_product_detail for each ASIN, then computes deltas
    (which product is better on each metric).

    Args:
        asins: List of 2-5 Amazon ASINs to compare

    Returns:
        dict with 'products' (list of detail dicts), 'comparison' (metric deltas),
        and 'winner' (best on each metric)
    """
    if len(asins) < 2:
        return {"error": "Need at least 2 ASINs to compare", "products": [], "comparison": {}}
    if len(asins) > 5:
        asins = asins[:5]

    # Get detail for each product
    products = []
    for asin in asins:
        detail = get_product_detail(asin)
        if detail:
            products.append(detail)

    if len(products) < 2:
        return {
            "error": f"Only {len(products)} of {len(asins)} products found. Need at least 2.",
            "products": products,
            "comparison": {},
        }

    # Compute comparison metrics
    comparison = {}
    metrics = [
        ("avg_rating", "higher is better", True),
        ("avg_sentiment", "higher is better", True),
        ("negative_rate", "lower is better", False),
        ("review_count", "more reviews = more data", True),
        ("price", "lower is better", False),
    ]

    winners = {}
    for metric, description, higher_is_better in metrics:
        values = []
        for p in products:
            val = p.get(metric)
            if val is not None:
                values.append({"asin": p["asin"], "name": p.get("product_name", p["asin"]), "value": val})

        if len(values) >= 2:
            sorted_vals = sorted(values, key=lambda x: x["value"], reverse=higher_is_better)
            best = sorted_vals[0]
            worst = sorted_vals[-1]
            comparison[metric] = {
                "description": description,
                "values": {v["asin"]: v["value"] for v in values},
                "best": {"asin": best["asin"], "name": best["name"], "value": best["value"]},
                "worst": {"asin": worst["asin"], "name": worst["name"], "value": worst["value"]},
                "spread": round(abs(best["value"] - worst["value"]), 4),
            }
            winners[metric] = best["asin"]

    # Count wins per product
    win_counts = {}
    for asin in asins:
        win_counts[asin] = sum(1 for w in winners.values() if w == asin)

    overall_winner = max(win_counts, key=win_counts.get) if win_counts else None

    # Theme comparison — what themes dominate each product
    theme_comparison = {}
    for p in products:
        top_themes = sorted(p.get("themes", []), key=lambda t: t["review_count"], reverse=True)[:3]
        theme_comparison[p["asin"]] = [t["theme"] for t in top_themes]

    return {
        "products": products,
        "comparison": comparison,
        "winners": winners,
        "win_counts": win_counts,
        "overall_winner": overall_winner,
        "theme_comparison": theme_comparison,
    }
