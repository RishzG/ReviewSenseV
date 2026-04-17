"""Compare endpoint — side-by-side category comparison."""

from fastapi import APIRouter
from api.db import get_cursor
from api.models.requests import CompareRequest

router = APIRouter(tags=["Compare"])


@router.post("/compare")
def compare_categories(request: CompareRequest):
    """Compare multiple categories on key metrics."""
    placeholders = ", ".join(["%s"] * len(request.categories))

    with get_cursor() as cur:
        cur.execute(f"""
            SELECT DERIVED_CATEGORY, REVIEW_COUNT, AVG_RATING,
                   AVG_SENTIMENT, NEGATIVE_RATE, AVG_HELPFUL_VOTES
            FROM GOLD.CATEGORY_SENTIMENT_SUMMARY
            WHERE DERIVED_CATEGORY IN ({placeholders})
            ORDER BY DERIVED_CATEGORY
        """, request.categories)

        results = [
            {
                "category": r[0], "review_count": r[1],
                "avg_rating": float(r[2]), "avg_sentiment": float(r[3]),
                "negative_rate": float(r[4]), "avg_helpful_votes": float(r[5]),
            }
            for r in cur.fetchall()
        ]

    return {"categories": results, "metric": request.metric}
