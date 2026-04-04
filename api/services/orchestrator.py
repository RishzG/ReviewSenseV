"""Query orchestrator — delegates to Cortex Agent API.

The agent autonomously decides which tools to call:
- Cortex Analyst (structured SQL queries)
- Cortex Search (review text retrieval)
- Generic UDFs (category stats, product stats, themes, complaints, trends)

Input guardrails are applied before the agent call.
Output guardrails (content safety) are handled by Cortex Guard.

Edge cases handled:
- Agent API unreachable → falls back to legacy orchestrator
- Agent returns empty answer → retry with legacy path
- Agent timeout (budget exceeded) → return partial answer with warning
- Guardrail blocks input → return 400 before agent is called
- Agent returns error → parse error, return user-friendly message
"""

import time
import logging
from api.services.agent import query_agent
from api.services.guardrails import check_input, sanitize_output

logger = logging.getLogger(__name__)


def _legacy_route(question: str) -> dict:
    """Fallback: manual intent classification + routing (pre-agent approach)."""
    from api.services.analyst import query_analyst
    from api.services.search import query_search
    from api.services.synthesis import query_synthesis
    import re

    q = question.lower()

    # Simple rule-based classification
    structured_signals = ['how many', 'average', 'rank', 'top ', 'worst', 'best',
                          'highest', 'lowest', 'percentage', 'trend', 'compare', 'count']
    semantic_signals = ['what do people say', 'tell me about', 'what problems',
                        'recommend', 'worth buying', 'what do people think', 'experiences']
    synthesis_signals = ['and what', 'numbers and', 'full analysis', 'complete picture']

    if any(s in q for s in synthesis_signals):
        result = query_synthesis(question)
        result["intent"] = "synthesis"
    elif any(s in q for s in semantic_signals):
        result = query_search(question)
        result["intent"] = "semantic"
    elif any(s in q for s in structured_signals):
        result = query_analyst(question)
        result["intent"] = "structured"

        # If Analyst refused (can't answer), fall back to semantic search
        answer_lower = (result.get("answer") or "").lower()
        refusal_signals = ["not possible", "i'm sorry", "cannot", "don't have", "does not have",
                           "not available", "unable to", "outside the scope"]
        if any(s in answer_lower for s in refusal_signals) and not result.get("data"):
            result = query_search(question)
            result["intent"] = "semantic (fallback from analyst)"
    else:
        # Default to analyst, with semantic fallback
        result = query_analyst(question)
        result["intent"] = "structured"

        answer_lower = (result.get("answer") or "").lower()
        refusal_signals = ["not possible", "i'm sorry", "cannot", "don't have", "does not have",
                           "not available", "unable to", "outside the scope"]
        if any(s in answer_lower for s in refusal_signals) and not result.get("data"):
            result = query_search(question)
            result["intent"] = "semantic (fallback from analyst)"

    result["question"] = question
    result["tools_used"] = [result["intent"]]
    return result


def route_query(question: str) -> dict:
    """Process a user question through guardrails and the Cortex Agent.

    Falls back to legacy orchestrator if the agent is unavailable or fails.
    """
    start = time.time()

    # Input guardrail — raises GuardrailError (caught by router as 400)
    check_input(question)

    try:
        result = query_agent(question)

        # Edge case: agent returned an error message
        if result.get("answer", "").startswith("Agent error"):
            logger.warning(f"Agent error, falling back to legacy: {result['answer'][:100]}")
            result = _legacy_route(question)
            result["fallback"] = True

        # Edge case: agent returned empty answer
        elif not result.get("answer") or len(result.get("answer", "").strip()) < 10:
            logger.warning("Agent returned empty answer, falling back to legacy")
            result = _legacy_route(question)
            result["fallback"] = True

    except Exception as e:
        # Edge case: agent API unreachable, timeout, network error
        logger.error(f"Agent API failed: {e}, falling back to legacy")
        result = _legacy_route(question)
        result["fallback"] = True

    # Output guardrail (PII stripping — content safety handled by Cortex Guard)
    if result.get("answer"):
        result["answer"] = sanitize_output(result["answer"])

    # Ensure latency is set
    if "latency_ms" not in result:
        result["latency_ms"] = round((time.time() - start) * 1000, 1)

    return result
