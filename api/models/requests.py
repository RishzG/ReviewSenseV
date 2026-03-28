"""Pydantic request models."""

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=1000, description="Natural language question")

    model_config = {"json_schema_extra": {"examples": [
        {"question": "Which product categories have the worst reviews?"},
        {"question": "What do people complain about in headphones?"},
        {"question": "Tell me about battery life issues in wireless earbuds"},
    ]}}


class CompareRequest(BaseModel):
    categories: list[str] = Field(..., min_length=2, max_length=5, description="Categories to compare")
    metric: str = Field(default="sentiment", description="Metric to compare: sentiment, rating, negative_rate")
