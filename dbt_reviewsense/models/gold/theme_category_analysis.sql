-- Tier 3: Theme x Category cross-analysis
-- Answers: "What are the biggest pain points in headphones?"
-- Unique cross-cutting insight — included in Cortex Analyst semantic model

{{ config(materialized='table') }}

SELECT
    DERIVED_CATEGORY,
    REVIEW_THEME,
    COUNT(*) AS REVIEW_COUNT,
    ROUND(AVG(RATING), 2) AS AVG_RATING,
    ROUND(AVG(SENTIMENT_SCORE), 4) AS AVG_SENTIMENT,
    COUNT(CASE WHEN RATING <= 2 THEN 1 END) AS NEGATIVE_REVIEW_COUNT,
    ROUND(COUNT(CASE WHEN RATING <= 2 THEN 1 END)::FLOAT / NULLIF(COUNT(*), 0), 4) AS NEGATIVE_RATE,
    ROUND(AVG(CASE WHEN RATING <= 2 THEN SENTIMENT_SCORE END), 4) AS NEGATIVE_AVG_SENTIMENT
FROM {{ ref('enriched_reviews') }}
WHERE DERIVED_CATEGORY IS NOT NULL
  AND REVIEW_THEME IS NOT NULL
GROUP BY DERIVED_CATEGORY, REVIEW_THEME
HAVING COUNT(*) >= 10
