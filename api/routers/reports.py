"""Business Intelligence Report endpoints."""

from fastapi import APIRouter, HTTPException
from api.services.report import generate_category_report, generate_product_report

router = APIRouter(prefix="/report", tags=["Reports"])


@router.get("/category/{category}")
def category_report(category: str):
    """Generate a full business intelligence report for a product category.

    Includes executive summary, theme analysis, complaint breakdown,
    strengths/issues with customer quotes, and recommended actions.
    """
    result = generate_category_report(category)
    if not result:
        raise HTTPException(status_code=404, detail=f"Category '{category}' not found")
    return result


@router.get("/product/{asin}")
def product_report(asin: str):
    """Generate a business intelligence report for a specific product.

    Only available for products with 20+ reviews. Includes comparison
    to category average, theme breakdown, and customer evidence.
    """
    result = generate_product_report(asin)
    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"Product '{asin}' not found. Only products with 20+ reviews are available."
        )
    return result
