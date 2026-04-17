"""Category endpoints — browse and explore product categories."""

from fastapi import APIRouter, HTTPException
from api.db import get_cursor
from api.models.responses import CategorySummary, CategoryDetail

router = APIRouter(prefix="/categories", tags=["Categories"])


@router.get("", response_model=list[CategorySummary])
def list_categories():
    """List all product categories with summary stats."""
    with get_cursor() as cur:
        cur.execute("""
            SELECT DERIVED_CATEGORY, REVIEW_COUNT, AVG_RATING,
                   AVG_SENTIMENT, NEGATIVE_RATE
            FROM GOLD.CATEGORY_SENTIMENT_SUMMARY
            ORDER BY REVIEW_COUNT DESC
        """)
        return [
            CategorySummary(
                derived_category=r[0], review_count=r[1],
                avg_rating=float(r[2]) if r[2] is not None else 0.0,
                avg_sentiment=float(r[3]) if r[3] is not None else 0.0,
                negative_rate=float(r[4]) if r[4] is not None else 0.0,
            )
            for r in cur.fetchall()
        ]


@router.get("/{category}", response_model=CategoryDetail)
def get_category(category: str):
    """Get detailed stats for a specific category including themes, complaints, and trends."""
    with get_cursor() as cur:
        # Category summary
        cur.execute("""
            SELECT DERIVED_CATEGORY, REVIEW_COUNT, AVG_RATING,
                   AVG_SENTIMENT, NEGATIVE_RATE
            FROM GOLD.CATEGORY_SENTIMENT_SUMMARY
            WHERE DERIVED_CATEGORY = %s
               OR DERIVED_CATEGORY LIKE %s
        """, (category, f"%{category}%"))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Category '{category}' not found")

        # Top themes
        cur.execute("""
            SELECT REVIEW_THEME, REVIEW_COUNT, AVG_RATING, AVG_SENTIMENT, NEGATIVE_RATE
            FROM GOLD.THEME_CATEGORY_ANALYSIS
            WHERE DERIVED_CATEGORY = %s
            ORDER BY REVIEW_COUNT DESC
        """, (category,))
        themes = [
            {"theme": r[0], "review_count": r[1],
             "avg_rating": float(r[2]) if r[2] is not None else 0.0,
             "avg_sentiment": float(r[3]) if r[3] is not None else 0.0,
             "negative_rate": float(r[4]) if r[4] is not None else 0.0}
            for r in cur.fetchall()
        ]

        # Top complaints
        cur.execute("""
            SELECT REVIEW_THEME, COMPLAINT_COUNT, AVG_SENTIMENT, AVG_HELPFUL_VOTES
            FROM GOLD.COMPLAINT_ANALYSIS
            WHERE DERIVED_CATEGORY = %s
            ORDER BY COMPLAINT_COUNT DESC
        """, (category,))
        complaints = [
            {"theme": r[0], "complaint_count": r[1],
             "avg_sentiment": float(r[2]) if r[2] is not None else 0.0,
             "avg_helpful_votes": float(r[3]) if r[3] is not None else 0.0}
            for r in cur.fetchall()
        ]

        # Monthly trends
        cur.execute("""
            SELECT REVIEW_MONTH, REVIEW_COUNT, AVG_RATING, AVG_SENTIMENT, NEGATIVE_RATE
            FROM GOLD.CATEGORY_MONTHLY_TRENDS
            WHERE DERIVED_CATEGORY = %s
            ORDER BY REVIEW_MONTH
        """, (category,))
        trends = [
            {"month": str(r[0]), "review_count": r[1],
             "avg_rating": float(r[2]) if r[2] is not None else 0.0,
             "avg_sentiment": float(r[3]) if r[3] is not None else 0.0,
             "negative_rate": float(r[4]) if r[4] is not None else 0.0}
            for r in cur.fetchall()
        ]

        return CategoryDetail(
            derived_category=row[0], review_count=row[1],
            avg_rating=float(row[2]), avg_sentiment=float(row[3]),
            negative_rate=float(row[4]),
            top_themes=themes, top_complaints=complaints, monthly_trends=trends,
        )
