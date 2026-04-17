"""Cortex Agent API client.

Uses Snowflake's native agent orchestration instead of manual intent routing.
The agent decides which tools to call, chains results, and generates a final answer.

Tools available to the agent:
- cortex_analyst_text_to_sql: natural language → SQL over gold marts
- cortex_search: search enriched reviews with filters
- generic UDFs: category stats, product stats, theme breakdown, complaints, trends
"""

import json
import time
import hashlib
from datetime import datetime, timedelta, timezone

import jwt
import requests
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend

from api.config import settings

# Cache the JWT token (valid for ~59 min, refresh at 50 min)
_token_cache = {"token": None, "expires_at": 0}


def _get_jwt_token() -> str:
    """Generate a JWT token from the RSA private key for Snowflake REST API auth."""
    now = time.time()
    if _token_cache["token"] and now < _token_cache["expires_at"]:
        return _token_cache["token"]

    with open(settings.snowflake_private_key_path, "rb") as f:
        private_key = serialization.load_pem_private_key(f.read(), password=None, backend=default_backend())

    # Get public key fingerprint for the issuer
    public_key_der = private_key.public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    sha256 = hashlib.sha256(public_key_der).digest()
    import base64
    fingerprint = base64.b64encode(sha256).decode("utf-8")

    account_upper = settings.snowflake_account.upper()
    user_upper = settings.snowflake_user.upper()
    qualified_username = f"{account_upper}.{user_upper}"

    now_dt = datetime.now(timezone.utc)
    payload = {
        "iss": f"{qualified_username}.SHA256:{fingerprint}",
        "sub": qualified_username,
        "iat": now_dt,
        "exp": now_dt + timedelta(minutes=59),
    }

    token = jwt.encode(payload, private_key, algorithm="RS256")

    _token_cache["token"] = token
    _token_cache["expires_at"] = now + 3000  # refresh after 50 min

    return token


def _build_agent_request(question: str, stream: bool = False) -> dict:
    """Build the Cortex Agent API request payload."""
    return {
        "stream": stream,
        "models": {"orchestration": settings.agent_model},
        "instructions": {
            "system": (
                "You are ReviewSense AI, a product review intelligence agent. "
                "You analyze 183,000+ Amazon Electronics reviews across 14 product categories. "
                "Always use tools to get real data — never guess numbers. "
                "When answering, cite specific data points and review quotes."
            ),
            "orchestration": (
                "For numerical questions (ratings, counts, rankings, trends, comparisons), "
                "use the analyst tool to generate SQL. "
                "For opinion/experience questions (what do people say, complaints, recommendations), "
                "use the review_search tool. "
                "For category-specific lookups, use the appropriate generic tool. "
                "For complex questions needing both data and examples, use multiple tools. "
                "Always verify claims with data before responding."
            ),
            "response": (
                "Be concise and factual. Include specific numbers when available. "
                "Reference actual review quotes when citing opinions. "
                "Do not invent statistics or reviews."
            ),
        },
        "orchestration": {
            "budget": {
                "seconds": settings.agent_budget_seconds,
                "tokens": settings.agent_budget_tokens,
            }
        },
        "tools": [
            {
                "tool_spec": {
                    "type": "cortex_analyst_text_to_sql",
                    "name": "analyst",
                    "description": (
                        "Query structured review metrics: ratings, counts, trends, "
                        "sentiment scores, negative rates by category and theme. "
                        "Use for any question about numbers, rankings, or statistics."
                    ),
                }
            },
            {
                "tool_spec": {
                    "type": "cortex_search",
                    "name": "review_search",
                    "description": (
                        "Search actual customer review text for opinions, experiences, "
                        "complaints, and product feedback. Supports filtering by ASIN, "
                        "RATING, DERIVED_CATEGORY, REVIEW_THEME, REVIEW_QUALITY, and VERIFIED_PURCHASE."
                    ),
                }
            },
            {
                "tool_spec": {
                    "type": "generic",
                    "name": "category_lookup",
                    "description": "Get pre-computed sentiment summary for a specific product category",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "category": {
                                "type": "string",
                                "description": (
                                    "Product category. Valid values: headphones_earbuds, speakers, "
                                    "streaming_devices, smart_home, cables_adapters, chargers_batteries, "
                                    "phone_accessories, computer_peripherals, storage_media, "
                                    "cameras_accessories, tv_accessories, gaming_accessories, "
                                    "wearables, other_electronics"
                                ),
                            }
                        },
                        "required": ["category"],
                    },
                }
            },
            {
                "tool_spec": {
                    "type": "generic",
                    "name": "product_lookup",
                    "description": "Get pre-computed stats for a specific product by ASIN (only products with 20+ reviews)",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "asin": {"type": "string", "description": "Amazon product ID (e.g., B01G8JO5F2)"}
                        },
                        "required": ["asin"],
                    },
                }
            },
            {
                "tool_spec": {
                    "type": "generic",
                    "name": "theme_breakdown",
                    "description": "Get review theme breakdown (battery_life, sound_quality, etc.) for a category",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "category": {"type": "string", "description": "Product category name"}
                        },
                        "required": ["category"],
                    },
                }
            },
            {
                "tool_spec": {
                    "type": "generic",
                    "name": "complaint_data",
                    "description": "Get complaint analysis (negative reviews only) by theme for a category",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "category": {"type": "string", "description": "Product category name"}
                        },
                        "required": ["category"],
                    },
                }
            },
            {
                "tool_spec": {
                    "type": "generic",
                    "name": "monthly_trends",
                    "description": "Get monthly sentiment and rating trends for a category",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "category": {"type": "string", "description": "Product category name"}
                        },
                        "required": ["category"],
                    },
                }
            },
        ],
        "tool_resources": {
            "analyst": {
                "semantic_model_file": settings.semantic_model_file,
                "execution_environment": {
                    "type": "warehouse",
                    "warehouse": settings.snowflake_warehouse,
                    "query_timeout": 60,
                },
            },
            "review_search": {
                "search_service": settings.search_service,
                "id_column": "REVIEW_ID",
                "columns_and_descriptions": {
                    "REVIEW_TEXT_CLEAN": {
                        "description": "Cleaned review text with title and body",
                        "type": "string",
                        "searchable": True,
                        "filterable": False,
                    },
                    "ASIN": {
                        "description": "Amazon product ID",
                        "type": "string",
                        "searchable": False,
                        "filterable": True,
                    },
                    "RATING": {
                        "description": "Star rating 1-5",
                        "type": "string",
                        "searchable": False,
                        "filterable": True,
                    },
                    "DERIVED_CATEGORY": {
                        "description": "Product category (e.g., headphones_earbuds, speakers)",
                        "type": "string",
                        "searchable": False,
                        "filterable": True,
                    },
                    "REVIEW_THEME": {
                        "description": "Review theme (e.g., battery_life, sound_quality, comfort)",
                        "type": "string",
                        "searchable": False,
                        "filterable": True,
                    },
                    "REVIEW_QUALITY": {
                        "description": "Review quality tier: high, medium, low",
                        "type": "string",
                        "searchable": False,
                        "filterable": True,
                    },
                    "VERIFIED_PURCHASE": {
                        "description": "Whether the reviewer made a verified purchase",
                        "type": "string",
                        "searchable": False,
                        "filterable": True,
                    },
                },
            },
            "category_lookup": {
                "type": "function",
                "execution_environment": {
                    "type": "warehouse",
                    "warehouse": settings.snowflake_warehouse,
                    "query_timeout": 30,
                },
                "identifier": "REVIEWSENSE_DB.GOLD.GET_CATEGORY_SUMMARY",
            },
            "product_lookup": {
                "type": "function",
                "execution_environment": {
                    "type": "warehouse",
                    "warehouse": settings.snowflake_warehouse,
                    "query_timeout": 30,
                },
                "identifier": "REVIEWSENSE_DB.GOLD.GET_PRODUCT_STATS",
            },
            "theme_breakdown": {
                "type": "function",
                "execution_environment": {
                    "type": "warehouse",
                    "warehouse": settings.snowflake_warehouse,
                    "query_timeout": 30,
                },
                "identifier": "REVIEWSENSE_DB.GOLD.GET_THEME_BREAKDOWN",
            },
            "complaint_data": {
                "type": "function",
                "execution_environment": {
                    "type": "warehouse",
                    "warehouse": settings.snowflake_warehouse,
                    "query_timeout": 30,
                },
                "identifier": "REVIEWSENSE_DB.GOLD.GET_COMPLAINT_DATA",
            },
            "monthly_trends": {
                "type": "function",
                "execution_environment": {
                    "type": "warehouse",
                    "warehouse": settings.snowflake_warehouse,
                    "query_timeout": 30,
                },
                "identifier": "REVIEWSENSE_DB.GOLD.GET_MONTHLY_TRENDS",
            },
        },
        "messages": [
            {"role": "user", "content": [{"type": "text", "text": question}]}
        ],
    }


def query_agent(question: str) -> dict:
    """Send a question to the Cortex Agent API and return the response."""
    start = time.time()

    token = _get_jwt_token()
    account = settings.snowflake_account
    url = f"https://{account}.snowflakecomputing.com/api/v2/cortex/agent:run"

    headers = {
        "Authorization": f"Bearer {token}",
        "X-Snowflake-Authorization-Token-Type": "KEYPAIR_JWT",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    payload = _build_agent_request(question, stream=False)
    resp = requests.post(url, headers=headers, json=payload, timeout=60)

    if resp.status_code != 200:
        return {
            "question": question,
            "intent": "agent",
            "answer": f"Agent error ({resp.status_code}): {resp.text[:300]}",
            "sql": None,
            "data": None,
            "sources": None,
            "tools_used": [],
            "latency_ms": round((time.time() - start) * 1000, 1),
        }

    result = resp.json()

    # Parse agent response
    answer = ""
    sql = None
    data = None
    sources = []
    tools_used = []

    for item in result.get("content", []):
        if item.get("type") == "text":
            answer += item.get("text", "")
        elif item.get("type") == "tool_result":
            tool_info = item.get("tool_result", {})
            tools_used.append(tool_info.get("name", "unknown"))
            # Extract SQL from analyst tool results
            if tool_info.get("name") == "analyst":
                for content in tool_info.get("content", []):
                    if content.get("type") == "sql":
                        sql = content.get("statement")
                    elif content.get("type") == "json":
                        data = content.get("json")
            # Extract search results as sources
            elif tool_info.get("name") == "review_search":
                for content in tool_info.get("content", []):
                    if content.get("type") == "json":
                        search_data = content.get("json", {})
                        for r in search_data.get("results", []):
                            sources.append({
                                "asin": r.get("ASIN", ""),
                                "rating": r.get("RATING", ""),
                                "text": r.get("REVIEW_TEXT_CLEAN", "")[:200],
                            })

    return {
        "question": question,
        "intent": "agent",
        "answer": answer,
        "sql": sql,
        "data": data,
        "sources": sources if sources else None,
        "tools_used": tools_used,
        "latency_ms": round((time.time() - start) * 1000, 1),
    }


def query_agent_stream(question: str):
    """Stream a response from the Cortex Agent API. Yields SSE events."""
    token = _get_jwt_token()
    account = settings.snowflake_account
    url = f"https://{account}.snowflakecomputing.com/api/v2/cortex/agent:run"

    headers = {
        "Authorization": f"Bearer {token}",
        "X-Snowflake-Authorization-Token-Type": "KEYPAIR_JWT",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }

    payload = _build_agent_request(question, stream=True)
    resp = requests.post(url, headers=headers, json=payload, timeout=60, stream=True)

    for line in resp.iter_lines():
        if line:
            decoded = line.decode("utf-8")
            if decoded.startswith("data: "):
                yield decoded
