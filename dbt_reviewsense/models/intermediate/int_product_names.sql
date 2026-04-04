-- Derive product names and brands from review text using Cortex COMPLETE
-- Only for ASINs with 20+ reviews (enough context to identify the product)
-- Materialized as TABLE (LLM calls are expensive)

{{ config(materialized='table') }}

WITH top_asins AS (
    SELECT ASIN
    FROM {{ ref('stg_reviews') }}
    GROUP BY ASIN
    HAVING COUNT(*) >= 20
),

-- Pick top 5 longest reviews per ASIN for name derivation
top_reviews AS (
    SELECT
        s.ASIN,
        LEFT(s.TITLE || '. ' || s.REVIEW_TEXT, 200) AS SNIPPET,
        ROW_NUMBER() OVER (PARTITION BY s.ASIN ORDER BY s.TEXT_LEN DESC) AS rn
    FROM {{ ref('stg_reviews') }} s
    INNER JOIN top_asins a ON s.ASIN = a.ASIN
),

combined AS (
    SELECT
        ASIN,
        LISTAGG(SNIPPET, ' | ') WITHIN GROUP (ORDER BY rn) AS SAMPLE_TEXT
    FROM top_reviews
    WHERE rn <= 5
    GROUP BY ASIN
),

derived AS (
    SELECT
        ASIN,
        SNOWFLAKE.CORTEX.COMPLETE(
            'mistral-large',
            'Based on these reviews, what is the exact product name and brand? '
            || 'Respond with ONLY this format: Brand - Product Name. '
            || 'If brand is unknown, use "Unknown" as brand. '
            || 'If product name is unclear, describe the product type. '
            || 'Examples: "Amazon - Fire TV Stick 4K", "Sony - WH-1000XM4 Headphones", "Unknown - Wireless Earbuds". '
            || 'Reviews: ' || LEFT(SAMPLE_TEXT, 2000)
        ) AS RAW_NAME
    FROM combined
)

SELECT
    ASIN,
    TRIM(RAW_NAME) AS RAW_PRODUCT_NAME,
    CASE
        WHEN RAW_NAME LIKE '%-%'
        THEN TRIM(SPLIT_PART(RAW_NAME, '-', 1))
        ELSE 'Unknown'
    END AS BRAND,
    CASE
        WHEN RAW_NAME LIKE '%-%'
        THEN TRIM(SUBSTR(RAW_NAME, POSITION('-' IN RAW_NAME) + 1))
        ELSE TRIM(RAW_NAME)
    END AS PRODUCT_NAME
FROM derived
