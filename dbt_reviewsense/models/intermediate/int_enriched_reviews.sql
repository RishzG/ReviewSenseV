-- Intermediate: Cortex AI enrichment on staged reviews
-- Materialized as TABLE (LLM functions are expensive — compute once)
-- Source: stg_reviews (~183,447 rows)
-- IMPORTANT: Test on LIMIT 100 first before full run (see int_enriched_reviews_sample.sql)

{{ config(materialized='table') }}

WITH staged AS (
    SELECT * FROM {{ ref('stg_reviews') }}
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

    -- Sentiment score (cheap, run on all rows)
    SNOWFLAKE.CORTEX.SENTIMENT(REVIEW_TEXT_CLEAN) AS SENTIMENT_SCORE,

    -- Theme classification (run on all, but low-quality results should be treated cautiously)
    SNOWFLAKE.CORTEX.CLASSIFY_TEXT(
        REVIEW_TEXT_CLEAN,
        ['battery_life', 'build_quality', 'sound_quality', 'connectivity',
         'comfort', 'value_for_money', 'customer_service', 'durability',
         'ease_of_use', 'other']
    ):label::STRING AS REVIEW_THEME,

    -- Conditional summarize (only reviews worth summarizing)
    CASE
        WHEN TEXT_LEN > 500 THEN SNOWFLAKE.CORTEX.SUMMARIZE(REVIEW_TEXT_CLEAN)
        ELSE REVIEW_TEXT_CLEAN
    END AS REVIEW_SUMMARY

FROM staged
