-- Sample run: Test Cortex enrichment on 100 rows before full 183K run
-- Run this FIRST to validate output, then run int_enriched_reviews

{{ config(
    materialized='table',
    enabled=true
) }}

WITH staged AS (
    SELECT * FROM {{ ref('stg_reviews') }}
    LIMIT 100
)

SELECT
    REVIEW_ID,
    ASIN,
    USER_ID,
    RATING,
    TITLE,
    REVIEW_TEXT,
    REVIEW_TEXT_CLEAN,
    VERIFIED_PURCHASE,
    HELPFUL_VOTE,
    REVIEW_TS,
    TEXT_LEN,
    REVIEW_QUALITY,
    SNOWFLAKE.CORTEX.SENTIMENT(REVIEW_TEXT_CLEAN) AS SENTIMENT_SCORE,
    SNOWFLAKE.CORTEX.CLASSIFY_TEXT(
        REVIEW_TEXT_CLEAN,
        ['battery_life', 'build_quality', 'sound_quality', 'connectivity',
         'comfort', 'value_for_money', 'customer_service', 'durability',
         'ease_of_use', 'other']
    ):label::STRING AS REVIEW_THEME,
    CASE
        WHEN TEXT_LEN > 500 THEN SNOWFLAKE.CORTEX.SUMMARIZE(REVIEW_TEXT_CLEAN)
        ELSE REVIEW_TEXT_CLEAN
    END AS REVIEW_SUMMARY
FROM staged
