"""Health check endpoint."""

from fastapi import APIRouter
from api.db import get_cursor
from api.config import settings
from api.models.responses import HealthResponse

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
def health_check():
    """Check connectivity to Snowflake, Cortex Analyst, and Cortex Search."""
    sf_ok = False
    analyst_ok = False
    search_ok = False

    try:
        with get_cursor() as cur:
            cur.execute("SELECT 1")
            sf_ok = True

            # Check Analyst (semantic view exists)
            try:
                cur.execute("SHOW SEMANTIC VIEWS LIKE 'REVIEWSENSE_ANALYTICS' IN SCHEMA GOLD")
                analyst_ok = cur.fetchone() is not None
            except Exception:
                # Fallback: check if stage-based YAML exists
                try:
                    cur.execute("LIST @GOLD.SEMANTIC_STAGE")
                    analyst_ok = cur.fetchone() is not None
                except Exception:
                    analyst_ok = False

            # Check Search Service
            cur.execute("SHOW CORTEX SEARCH SERVICES IN SCHEMA ANALYTICS")
            search_ok = cur.fetchone() is not None
    except Exception:
        pass

    status = "healthy" if (sf_ok and analyst_ok and search_ok) else "degraded"
    return HealthResponse(
        status=status,
        snowflake_connected=sf_ok,
        analyst_available=analyst_ok,
        search_available=search_ok,
    )
