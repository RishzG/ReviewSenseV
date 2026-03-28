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

    # Cortex Analyst
    semantic_view: str = "REVIEWSENSE_DB.GOLD.REVIEWSENSE_ANALYTICS"

    # Cortex Search
    search_service: str = "REVIEWSENSE_DB.ANALYTICS.REVIEW_SEARCH"

    # LLM
    llm_model: str = "mistral-large"

    class Config:
        env_file = ".env"


settings = Settings()
