-- Product lookup: ASIN → derived category + confidence
-- Cleans LLM output: strips whitespace, extracts category from verbose responses

{{ config(materialized='table') }}

WITH raw_categories AS (
    SELECT
        ASIN,
        REVIEW_COUNT,
        DERIVATION_CONFIDENCE,
        -- Clean: lowercase, strip whitespace/newlines, remove quotes
        TRIM(REPLACE(REPLACE(LOWER(DERIVED_CATEGORY), '\n', ''), '"', '')) AS CLEANED
    FROM {{ ref('int_product_categories') }}
),

extracted AS (
    SELECT
        ASIN,
        REVIEW_COUNT,
        DERIVATION_CONFIDENCE,
        CLEANED,
        -- Extract valid category name from verbose LLM responses
        CASE
            WHEN CLEANED IN ('headphones_earbuds', 'speakers', 'streaming_devices',
                'smart_home', 'cables_adapters', 'chargers_batteries', 'phone_accessories',
                'computer_peripherals', 'storage_media', 'cameras_accessories',
                'tv_accessories', 'gaming_accessories', 'wearables', 'other_electronics')
                THEN CLEANED
            WHEN CLEANED LIKE '%headphones_earbuds%' THEN 'headphones_earbuds'
            WHEN CLEANED LIKE '%speakers%' THEN 'speakers'
            WHEN CLEANED LIKE '%streaming_devices%' THEN 'streaming_devices'
            WHEN CLEANED LIKE '%smart_home%' THEN 'smart_home'
            WHEN CLEANED LIKE '%cables_adapters%' THEN 'cables_adapters'
            WHEN CLEANED LIKE '%chargers_batteries%' THEN 'chargers_batteries'
            WHEN CLEANED LIKE '%phone_accessories%' THEN 'phone_accessories'
            WHEN CLEANED LIKE '%computer_peripherals%' THEN 'computer_peripherals'
            WHEN CLEANED LIKE '%storage_media%' THEN 'storage_media'
            WHEN CLEANED LIKE '%cameras_accessories%' OR CLEANED LIKE '%camera_accessories%' THEN 'cameras_accessories'
            WHEN CLEANED LIKE '%tv_accessories%' THEN 'tv_accessories'
            WHEN CLEANED LIKE '%gaming_accessories%' THEN 'gaming_accessories'
            WHEN CLEANED LIKE '%wearables%' THEN 'wearables'
            WHEN CLEANED LIKE '%other_electronics%' THEN 'other_electronics'
            -- Common misclassifications
            WHEN CLEANED LIKE '%tablet%' THEN 'computer_peripherals'
            WHEN CLEANED LIKE '%networking%' THEN 'computer_peripherals'
            ELSE 'other_electronics'
        END AS DERIVED_CATEGORY
    FROM raw_categories
)

SELECT
    ASIN,
    DERIVED_CATEGORY,
    REVIEW_COUNT,
    DERIVATION_CONFIDENCE
FROM extracted
