"""Product endpoints — lookup by ASIN (only for products with 20+ reviews)."""

from fastapi import APIRouter, HTTPException
from api.db import get_cursor
from api.models.responses import ProductSummary

router = APIRouter(prefix="/products", tags=["Products"])


@router.get("/{asin}", response_model=ProductSummary)
def get_product(asin: str):
    """Get sentiment summary for a specific product (ASIN).

    Only available for products with 20+ reviews (~407 products).
    """
    with get_cursor() as cur:
        cur.execute("""
            SELECT ASIN, DERIVED_CATEGORY, REVIEW_COUNT, AVG_RATING,
                   AVG_SENTIMENT, NEGATIVE_RATE, TOP_THEME
            FROM GOLD.PRODUCT_SENTIMENT_SUMMARY
            WHERE ASIN = %s
        """, (asin,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(
                status_code=404,
                detail=f"Product '{asin}' not found. Only products with 20+ reviews are indexed."
            )
        return ProductSummary(
            asin=row[0], derived_category=row[1], review_count=row[2],
            avg_rating=float(row[3]), avg_sentiment=float(row[4]),
            negative_rate=float(row[5]), top_theme=row[6],
        )
