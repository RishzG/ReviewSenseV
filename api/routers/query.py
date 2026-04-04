"""Main query endpoint — routes through the Cortex Agent orchestrator."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from api.models.requests import QueryRequest
from api.models.responses import QueryResponse
from api.services.orchestrator import route_query
from api.services.guardrails import GuardrailError, check_input
from api.services.agent import query_agent_stream

router = APIRouter(tags=["Query"])


@router.post("/query", response_model=QueryResponse)
def query(request: QueryRequest):
    """Ask a natural language question about product reviews.

    The Cortex Agent autonomously selects tools and chains results:
    - **Cortex Analyst**: SQL generation for numbers, rankings, trends
    - **Cortex Search**: Review retrieval for opinions, experiences
    - **Gold Mart UDFs**: Pre-computed category/product/theme/complaint stats
    - Falls back to legacy orchestrator if agent is unavailable
    """
    try:
        result = route_query(request.question)
        return QueryResponse(**result)
    except GuardrailError as e:
        raise HTTPException(status_code=400, detail=e.message)


@router.post("/query/stream")
def query_stream(request: QueryRequest):
    """Stream a response from the Cortex Agent.

    Returns Server-Sent Events (SSE) with real-time tool usage and answer generation.
    """
    try:
        check_input(request.question)
    except GuardrailError as e:
        raise HTTPException(status_code=400, detail=e.message)

    def event_generator():
        for event in query_agent_stream(request.question):
            yield f"{event}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
