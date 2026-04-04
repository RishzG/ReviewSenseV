"""Semantic path: Cortex Search Service for qualitative queries (RAG)."""

import json
from api.db import get_cursor
from api.config import settings


def query_search(question: str, limit: int = 5) -> dict:
    with get_cursor() as cur:
        # Use Cortex Search to find relevant reviews
        search_query = json.dumps({
            "query": question,
            "columns": ["REVIEW_TEXT_CLEAN", "RATING", "ASIN"],
            "limit": limit,
        })
        cur.execute(
            f"""
            SELECT PARSE_JSON(
                SNOWFLAKE.CORTEX.SEARCH_PREVIEW(
                    '{settings.search_service}',
                    %s
                )
            ) AS results
            """,
            (search_query,)
        )
        row = cur.fetchone()

        if not row or not row[0]:
            return {
                "answer": "No relevant reviews found.",
                "sql": None,
                "data": None,
                "sources": [],
            }

        search_results = json.loads(row[0]) if isinstance(row[0], str) else row[0]
        results = search_results.get("results", [])

        # Build context from search results
        context_parts = []
        sources = []
        for r in results:
            text = r.get("REVIEW_TEXT_CLEAN", "")
            rating = r.get("RATING", "")
            asin = r.get("ASIN", "")
            context_parts.append(f"[Rating: {rating}/5] {text}")
            sources.append({"asin": asin, "rating": rating, "text": text[:200]})

        context = "\n---\n".join(context_parts)

        # Generate answer using Cortex COMPLETE with retrieved context
        rag_prompt = f"""Be precise and factual. Do not add creative elaboration.
Answer the user's question using ONLY the reviews below.

Format your response using markdown:
- Start with a brief 1-2 sentence summary
- Use **bold** for key points
- Use bullet points for distinct findings
- Group by theme if multiple aspects are discussed
- Include specific ratings when referencing a review (e.g., "One reviewer (4/5) noted...")
- Keep each bullet point to 1-2 sentences max

Do not invent information not present in the reviews. If the reviews don't answer the question, say so.

Reviews:
{context}

Question: {question}

Answer:"""

        cur.execute(
            "SELECT SNOWFLAKE.CORTEX.COMPLETE(%s, %s)",
            (settings.llm_model, rag_prompt)
        )
        answer = cur.fetchone()[0]

        return {
            "answer": answer,
            "sql": None,
            "data": None,
            "sources": sources,
        }
