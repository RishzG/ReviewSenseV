"""Application configuration from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    snowflake_account: str
    snowflake_user: str
    snowflake_password: str = ""
    snowflake_private_key_path: str
    snowflake_role: str = "TRAINING_ROLE"
    snowflake_warehouse: str = "REVIEWSENSE_WH"
    snowflake_database: str = "REVIEWSENSE_DB"

    # Cortex Analyst (semantic model — stage file for agent, semantic view for legacy)
    semantic_model_file: str = "@REVIEWSENSE_DB.GOLD.SEMANTIC_STAGE/reviewsense_analytics.yaml"
    semantic_view: str = "REVIEWSENSE_DB.GOLD.REVIEWSENSE_ANALYTICS"

    # Cortex Search (enriched service)
    search_service: str = "REVIEWSENSE_DB.GOLD.ENRICHED_REVIEW_SEARCH"

    # Legacy search (Jiwei's, kept for fallback)
    legacy_search_service: str = "REVIEWSENSE_DB.ANALYTICS.REVIEW_SEARCH"

    # Agent
    agent_model: str = "claude-4-sonnet"
    agent_budget_seconds: int = 45
    agent_budget_tokens: int = 16000

    # LLM (for non-agent COMPLETE calls)
    llm_model: str = "mistral-large"

    class Config:
        env_file = ".env"


settings = Settings()
