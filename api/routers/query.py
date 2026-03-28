"""Main query endpoint — routes through the orchestrator."""

from fastapi import APIRouter
from api.models.requests import QueryRequest
from api.models.responses import QueryResponse
from api.services.orchestrator import route_query

router = APIRouter(tags=["Query"])


@router.post("/query", response_model=QueryResponse)
def query(request: QueryRequest):
    """Ask a natural language question about product reviews.

    The orchestrator classifies intent and routes to:
    - **Structured**: Cortex Analyst (numbers, rankings, trends)
    - **Semantic**: Cortex Search + RAG (opinions, examples, experiences)
    - **Synthesis**: Both paths combined (complex questions)
    """
    result = route_query(request.question)
    return QueryResponse(**result)
