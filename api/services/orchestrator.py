"""Intent classifier and query router.

Routes user questions to the correct retrieval path:
- Structured: quantitative questions → Cortex Analyst (SQL)
- Semantic: qualitative questions → Cortex Search (RAG)
- Synthesis: complex questions → both paths combined
"""

import json
import time
from api.db import get_cursor
from api.config import settings
from api.services.analyst import query_analyst
from api.services.search import query_search
from api.services.synthesis import query_synthesis


INTENT_PROMPT = """Classify the following user question about product reviews into exactly one category.

Categories:
- "structured": Questions about numbers, counts, rankings, ratings, trends, comparisons, percentages, or statistics. These need SQL queries over aggregate data.
- "semantic": Questions asking for specific examples, opinions, experiences, recommendations, or "what do people say about X". These need searching actual review text.
- "synthesis": Questions that need both numbers AND specific examples. For example "What are the main complaints about headphones and how many are there?"

Question: {question}

Respond with ONLY one word: structured, semantic, or synthesis"""


def classify_intent(question: str) -> str:
    with get_cursor() as cur:
        cur.execute(
            "SELECT SNOWFLAKE.CORTEX.COMPLETE(%s, %s)",
            (settings.llm_model, INTENT_PROMPT.format(question=question))
        )
        result = cur.fetchone()[0].strip().lower()

    if "structured" in result:
        return "structured"
    elif "semantic" in result:
        return "semantic"
    elif "synthesis" in result:
        return "synthesis"
    # Default to structured for ambiguous cases
    return "structured"


def route_query(question: str) -> dict:
    start = time.time()

    intent = classify_intent(question)

    if intent == "structured":
        result = query_analyst(question)
    elif intent == "semantic":
        result = query_search(question)
    else:
        result = query_synthesis(question)

    result["intent"] = intent
    result["question"] = question
    result["latency_ms"] = round((time.time() - start) * 1000, 1)

    return result
