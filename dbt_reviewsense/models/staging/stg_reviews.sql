-- Staging view: column renaming, text concat, regex cleaning, timestamp filter
-- Source: ANALYTICS.REVIEWS_FOR_GENAI (183,457 rows)
-- Output: ~183,447 rows (filters bad timestamps with YEAR > 2026)

WITH source AS (
    SELECT * FROM {{ source('analytics', 'REVIEWS_FOR_GENAI') }}
),

cleaned AS (
    SELECT
        REVIEW_ID,
        ASIN,
        USER_ID,
        RATING,
        TITLE,
        REVIEW_TEXT,
        VERIFIED_PURCHASE,
        HELPFUL_VOTE,
        REVIEW_TS,
        TEXT_LEN,

        -- Concat title + text for enrichment
        COALESCE(TITLE, '') || ' ' || COALESCE(REVIEW_TEXT, '') AS REVIEW_TEXT_FULL,

        -- Regex cleaning: HTML tags, URLs, excessive whitespace
        REGEXP_REPLACE(
            REGEXP_REPLACE(
                REGEXP_REPLACE(
                    COALESCE(TITLE, '') || ' ' || COALESCE(REVIEW_TEXT, ''),
                    '<[^>]+>', ' '           -- Remove HTML tags
                ),
                'https?://\\S+', ' '         -- Remove URLs
            ),
            '\\s+', ' '                      -- Collapse whitespace
        ) AS REVIEW_TEXT_CLEAN,

        -- Review quality tier
        CASE
            WHEN TEXT_LEN >= 500 THEN 'high'
            WHEN TEXT_LEN >= 150 THEN 'medium'
            ELSE 'low'
        END AS REVIEW_QUALITY

    FROM source
    WHERE YEAR(REVIEW_TS) <= 2026
)

SELECT * FROM cleaned
