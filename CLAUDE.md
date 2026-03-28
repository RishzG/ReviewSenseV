# CLAUDE.md — ReviewSense AI

## What This Project Is

ReviewSense AI is a Product Intelligence Platform that analyzes 200K+ Amazon Electronics reviews using Snowflake and Cortex AI. It combines structured analytics (Cortex Analyst) with semantic search (Cortex Search Service) through an intelligent query router to answer product research questions.

This is a resume-grade project, not a class demo. Every architectural decision should be defensible, auditable, and production-minded.

## Snowflake Environment

```
Account:    pgb87192
Role:       TRAINING_ROLE
Warehouse:  COMPUTE_WH
Database:   REVIEWSENSE_DB
```

Credentials are in `.env` (never commit this). Connection pattern:

```python
from dotenv import load_dotenv
import os
load_dotenv()

connection_params = {
    "account": os.getenv("SNOWFLAKE_ACCOUNT"),       # pgb87192
    "user": os.getenv("SNOWFLAKE_USER"),
    "password": os.getenv("SNOWFLAKE_PASSWORD"),
    "role": os.getenv("SNOWFLAKE_ROLE"),              # TRAINING_ROLE
    "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE"),    # COMPUTE_WH
    "database": os.getenv("SNOWFLAKE_DATABASE"),      # REVIEWSENSE_DB
}
```

## Architecture Overview

Three retrieval paths, one orchestrator:

- **Structured Path** → Cortex Analyst (natural language → SQL over aggregate marts)
- **Semantic Path** → Cortex Search Service (hybrid vector + keyword + structured filters)
- **Synthesis Path** → Both paths combined, merged by Cortex COMPLETE

The orchestrator classifies user intent and routes to the correct path(s).

The system is **category-and-theme-centric**, not product-centric. With 102K ASINs averaging <2 reviews each, product-level analysis is only meaningful for the ~300 ASINs with 20+ reviews. Category-level and theme-level analysis is always statistically valid.

## Data Profile

```
Total reviews:           183,457 (after dedup from 200K)
Unique ASINs:            102,583
Unique users:            32,858
Date range:              2001-10-26 to present (some bad timestamps, year 33579+)
Avg rating:              4.21 / 5
Rating distribution:     ★1: 16,040 · ★2: 8,826 · ★3: 13,536 · ★4: 27,680 · ★5: 117,375
                         (64% are 5-star, ~13.5% are 1-2 star)
Verified purchases:      151,390 (82.5%)
Reviews with votes:      47,153 (25.7%), avg 6.02 votes when present
Text length:             min 20, median 189, avg 365, p75 418, max 29,809 chars
```

### Critical Data Constraints

**No product metadata.** Only ASINs — no product names, categories, brands, or prices.
- Phase 1 derives product categories + names from review text using Cortex COMPLETE
- Two-level derivation: Category (all ASINs with 3+ reviews) + Name/Brand (ASINs with 20+ reviews)
- Derived categories are the primary dimension for all aggregation and filtering

**Extreme long-tail.** 102K ASINs, avg <2 reviews/product.
- Product-level aggregation only for ASINs with 20+ reviews (~300 products)
- Category-level aggregation is always meaningful (14 categories, thousands of reviews each)
- Anomaly detection only viable at category/theme level + top ~20 ASINs with 100+ reviews

**Short reviews.** Median 189 chars (~2 sentences).
- SUMMARIZE only for TEXT_LEN > 500 (reviews worth summarizing)
- Review quality tier: high (500+), medium (150-499), low (<150)
- CLASSIFY_TEXT runs on all but low-quality classifications are flagged
- RAG retrieval prefers high-quality reviews for context

**Bad timestamps.** Some review_ts values are far-future (year 33579+).
- dbt staging model MUST filter: WHERE YEAR(review_ts) <= 2026

**Rating skew.** 64% are 5-star.
- Negative review analysis works with ~25K reviews (rating 1-2)
- Document the skew, don't treat it as a bug

### Top Products by Volume (Good for Testing/Demos)

| ASIN | Reviews | Avg Rating |
|------|---------|------------|
| B01G8JO5F2 | 4,526 | 3.78 |
| B00ZV9RDKK | 551 | 4.33 |
| B079QHML21 | 465 | 4.57 |
| B01DFKC2SO | 370 | 4.24 |
| B0791TX5P5 | 317 | 4.53 |

### Derived Product Category Taxonomy

```
headphones_earbuds, speakers, streaming_devices, smart_home, cables_adapters,
chargers_batteries, phone_accessories, computer_peripherals, storage_media,
cameras_accessories, tv_accessories, gaming_accessories, wearables, other_electronics
```

## Complete Data Lineage

```
RAW.ELECTRONICS_REVIEWS_RAW (200K rows, VARIANT/Parquet)
  └─► CURATED.ELECTRONICS_REVIEWS (200K rows, typed + cleaned)
        └─► CURATED.V_ELECTRONICS_REVIEWS_DEDUP (deduped by REVIEW_ID)
              └─► ANALYTICS.V_REVIEWS_GENAI_BASE (explicit type casting)
                    └─► ANALYTICS.REVIEWS_FOR_GENAI (183,457 rows, +TEXT_LEN)
                          ├─► ANALYTICS.V_REVIEWS_CLEAN (regex, WHERE YEAR <= 2026)
                          │     └─► ANALYTICS.REVIEWS_CLEAN_FOR_EMBEDDINGS (183,447 rows)
                          │           ├─► ANALYTICS.REVIEW_EMBEDDINGS (183,447 + VECTOR(FLOAT,768))
                          │           └─► ANALYTICS.REVIEW_SEARCH (Cortex Search Service, ACTIVE)
                          │                 └─► RAG Generation (Consumer Q&A + Biz Analyst)
                          ├─► ANALYTICS.REVIEW_INSIGHTS (200 rows — POC) [Jiwei]
                          │
                          └─► [NEW] dbt pipeline
                                ├─► SILVER.stg_reviews (staging view)
                                ├─► SILVER.int_enriched_reviews (Cortex enrichment)
                                ├─► SILVER.int_product_categories (derive categories via COMPLETE)
                                ├─► GOLD.product_lookup (ASIN → category + name + confidence)
                                ├─► GOLD.enriched_reviews (enriched + product lookup joined)
                                ├─► GOLD.category_sentiment_summary (Tier 1 aggregation)
                                ├─► GOLD.category_monthly_trends (Tier 1 time-series)
                                ├─► GOLD.theme_category_analysis (Tier 3 cross-cutting)
                                ├─► GOLD.product_sentiment_summary (Tier 2, 20+ reviews only)
                                └─► GOLD.complaint_analysis (category-level complaints)
```

## Database Layout — All Objects

```
REVIEWSENSE_DB
├── RAW                                     ← IMMUTABLE
│   ├── ELECTRONICS_REVIEWS_RAW             (Table — VARIANT, 200K rows)
│   ├── ELECTRONICS_STAGE                   (Internal Stage — Parquet source)
│   ├── V_ELECTRONICS_REVIEWS_RAW           (View — raw passthrough)
│   └── V_ELECTRONICS_RAW_KEYS             (View — key extraction)
│
├── CURATED                                 ← IMMUTABLE
│   ├── ELECTRONICS_REVIEWS                 (Table — typed, 200K rows)
│   │   Columns: REVIEW_ID, ASIN, USER_ID, RATING, TITLE, TEXT,
│   │            VERIFIED_PURCHASE, HELPFUL_VOTE, REVIEW_TS, CATEGORY
│   ├── V_ELECTRONICS_REVIEWS_DEDUP         (View — deduped, ROW_NUMBER) [Jiwei]
│   ├── V_ELECTRONICS_REVIEWS               (View — clean select)
│   ├── V_ELECTRONICS_REVIEWS_TEXT          (View — review_id + concat text)
│   └── V_ELECTRONICS_NEGATIVE_REVIEWS      (View — rating <= 2)
│
├── ANALYTICS                               ← Existing AI/ML layer
│   ├── V_REVIEWS_GENAI_BASE               (View — type casting) [Jiwei]
│   ├── REVIEWS_FOR_GENAI                   (Table — 183,457 rows, +TEXT_LEN) [Jiwei]
│   │   *** CENTRAL TABLE — all downstream flows from here ***
│   ├── V_REVIEWS_BASE                      (View — ORPHAN, unused downstream)
│   ├── V_REVIEWS_CLEAN                     (View — regex cleaning + WHERE YEAR <= 2026)
│   ├── REVIEWS_CLEAN_FOR_EMBEDDINGS        (Table — 183,447 rows)
│   ├── REVIEW_EMBEDDINGS                   (Table — 183,447 + VECTOR(FLOAT,768))
│   ├── REVIEW_SEARCH                       (Cortex Search Service — ACTIVE)
│   │   Search: REVIEW_TEXT_CLEAN
│   │   Filterable: ASIN, RATING, VERIFIED_PURCHASE, HELPFUL_VOTE, REVIEW_TS
│   │   TARGET_LAG: 1 hour
│   └── REVIEW_INSIGHTS                    (Table — 200 rows, POC) [Jiwei]
│       Columns: REVIEW_ID, ASIN, RATING, REVIEW_TS, REVIEW_TEXT,
│                SENTIMENT_LABEL, REVIEW_SUMMARY
│
├── SILVER                                  ← NEW — dbt staging + intermediate
│   └── (to be created by dbt)
│
└── GOLD                                    ← NEW — dbt marts + Cortex Analyst
    ├── ANALYST_STAGE                       (Stage — for semantic model YAML)
    └── (tables to be created by dbt)
```

## What's Already Built (Do NOT Rebuild)

- Data ingestion: 200K reviews → Parquet → RAW
- Curated layer: Typed, cleaned, timestamp handling, NULL filtering
- Deduplication: ROW_NUMBER dedup keeping most recent + longest text [Jiwei]
- Type-safe GenAI base: Explicit casting view [Jiwei]
- Materialized GenAI table: 183,457 rows with TEXT_LEN [Jiwei]
- Text cleaning: Regex pipeline (HTML, markup, URLs, whitespace, 8K truncation)
- Embeddings: 183,447 rows with snowflake-arctic-embed-m-v1.5 (768-dim)
- Cortex Search Service: ANALYTICS.REVIEW_SEARCH — hybrid search, TARGET_LAG 1 hour
- Manual vector search: 8.2s → 670ms = 12x improvement with Cortex Search
- RAG generation: Consumer Q&A + Business Analyst modes with mistral-large
- AI Insights POC: 200 rows with SENTIMENT_LABEL + REVIEW_SUMMARY [Jiwei]
- Validation: Row counts (~183,447), zero-contamination checks

## Implementation Phases

### Phase 1: Data Enrichment via dbt (Week 1-2)
- Scale REVIEW_INSIGHTS from 200 → 183K rows
- dbt source: ANALYTICS.REVIEWS_FOR_GENAI
- Staging: column renaming, text concat, regex cleaning, filter bad timestamps
- Intermediate: SENTIMENT(), CLASSIFY_TEXT(), conditional SUMMARIZE, review_quality tier
- Product category derivation: Cortex COMPLETE on sample reviews per ASIN
  - Level 1 (3+ reviews, ~10K ASINs): derive category from 14-item taxonomy
  - Level 2 (20+ reviews, ~300 ASINs): derive product name + brand
  - Validate on top 100 ASINs before full run
- Gold marts: 3-tier aggregation (category / product / theme × category)
- Output: GOLD.ENRICHED_REVIEWS, GOLD.PRODUCT_LOOKUP, aggregate marts

### Phase 2: Cortex Analyst + Search Upgrade (Week 2-3)
- Semantic model YAML over GOLD category + theme marts (NOT product mart)
- Upload to GOLD.ANALYST_STAGE
- Rebuild Cortex Search Service with enriched filters (review_theme, sentiment_score, derived_category, review_quality)

### Phase 3: FastAPI Backend (Week 3-4)
- API layer with orchestrator (intent classifier + router)
- Endpoints: /query, /categories, /category/{id}, /product/{asin}, /alerts, /compare, /health
- Pydantic models for request/response schemas
- Snowflake connection pool
- pytest test suite
- Swagger docs auto-generated

### Phase 4: Evaluation Framework (Week 4-5)
- 100 Q&A pairs: 30 category-level, 40 high-volume product, 30 theme-level
- Ground truth: SQL for structured, manual annotation for semantic
- Metrics: intent accuracy, retrieval precision@10, answer faithfulness, numerical accuracy
- Also validates enrichment accuracy (compare CLASSIFY_TEXT output against manual labels)

### Phase 5: Monitoring Agent (Week 5-6)
- Category-level: monthly sentiment + complaint theme distribution shifts
- Theme-level: cross-category complaint trend detection
- Product-level: only top ~20 ASINs with 100+ reviews
- Snowflake Tasks for scheduling
- Cortex COMPLETE for alert summaries

### Phase 6: Frontend (Week 6-8)
⚠️ **DECISION POINT — ASK THE USER WHICH OPTION TO IMPLEMENT:**

**Option A: FastAPI + Next.js (Full Product)**
- Next.js 14 (App Router) + shadcn/ui + Tailwind + Recharts + TanStack Query
- Four views: Category Explorer, Category Detail, Intelligence Chat, Alerts
- Chat shows retrieval path transparency (intent, path, SQL, latency)
- Deploy: Vercel (frontend) + Railway/Render (API) — both free tier
- Adds ~2 weeks but looks like a real product
- Resume line: "Full-stack product intelligence platform"

**Option B: Streamlit (Quick Demo)**
- Streamlit in Snowflake or standalone Streamlit calling FastAPI
- Same four views but limited UI flexibility
- Faster to build (~1 week)
- FastAPI + Swagger docs still demonstrate API-first architecture
- Resume line focuses on backend + data engineering

**Either way, FastAPI is the product — the frontend is a client of the API.**
The orchestrator, retrieval paths, and eval framework are identical regardless of frontend choice.

When Phase 6 begins, ask: "We're at the frontend phase. Do you want to go with
Next.js (full product look, ~2 weeks) or Streamlit (quick demo, ~1 week)?"

## Tech Stack

- **Data Warehouse**: Snowflake (all compute runs here)
- **AI/ML**: Snowflake Cortex (SENTIMENT, CLASSIFY_TEXT, SUMMARIZE, COMPLETE, EMBED_TEXT_768)
- **Embedding Model**: snowflake-arctic-embed-m-v1.5 (768-dim, selected via MTEB benchmark)
- **LLM**: mistral-large (RAG generation, intent classification)
- **Transformations**: dbt-snowflake
- **API**: FastAPI (REST endpoints, Swagger docs, Pydantic schemas)
- **Orchestration**: dbt Cloud scheduler + Snowflake Tasks (no Airflow)
- **Frontend**: TBD at Phase 6 (Next.js or Streamlit)
- **Version Control**: Git/GitHub

## dbt Configuration

### Source Definition
```yaml
# models/staging/sources.yml
sources:
  - name: analytics
    database: REVIEWSENSE_DB
    schema: ANALYTICS
    tables:
      - name: REVIEWS_FOR_GENAI
        description: >
          Primary source. 183,457 deduplicated, typed reviews with TEXT_LEN.
          Created by teammate (Jiwei). Do NOT modify.
        columns:
          - name: REVIEW_ID
          - name: ASIN
          - name: USER_ID
          - name: RATING
          - name: TITLE
          - name: TEXT
          - name: VERIFIED_PURCHASE
          - name: HELPFUL_VOTE
          - name: REVIEW_TS
          - name: CATEGORY
          - name: TEXT_LEN
```

### dbt Conventions
- **Profile name**: `reviewsense`
- **profiles.yml**: uses `env_var()` from `.env` — never hardcode credentials
- **Target database**: `REVIEWSENSE_DB`
- **Source**: `REVIEWSENSE_DB.ANALYTICS.REVIEWS_FOR_GENAI` — the 183K-row table
- **Staging models** (`stg_`): Views in SILVER. Column renaming, text concat, regex cleaning, timestamp filter (YEAR <= 2026).
- **Intermediate models** (`int_`): Tables in SILVER. Cortex enrichment + product category derivation. Tables because LLM functions are expensive.
- **Gold models** (no prefix): Tables in GOLD. 3-tier aggregations, product lookup, marts for Cortex Analyst.
- **Tests**: Every enriched column needs schema.yml with not_null and accepted_values tests.

### Cortex Function Patterns
```sql
-- Sentiment (cheap, run on all rows)
SNOWFLAKE.CORTEX.SENTIMENT(review_text_clean) AS sentiment_score

-- Theme classification (run on all, flag low-quality)
SNOWFLAKE.CORTEX.CLASSIFY_TEXT(review_text_clean,
    ['battery_life', 'build_quality', 'sound_quality', 'connectivity',
     'comfort', 'value_for_money', 'customer_service', 'durability',
     'ease_of_use', 'other']) AS review_theme

-- Conditional summarize (only reviews worth summarizing)
CASE
    WHEN TEXT_LEN > 500 THEN SNOWFLAKE.CORTEX.SUMMARIZE(review_text_clean)
    ELSE review_text_clean
END AS review_summary

-- Review quality tier
CASE
    WHEN TEXT_LEN >= 500 THEN 'high'
    WHEN TEXT_LEN >= 150 THEN 'medium'
    ELSE 'low'
END AS review_quality

-- Always test on LIMIT 100 first before full 183K run
```

### Gold Mart Aggregation Tiers

**Tier 1 — Category-Level** (always statistically valid, 14 categories):
- category_sentiment_summary
- category_monthly_trends

**Tier 2 — Product-Level** (only ASINs with 20+ reviews, ~300 products):
- product_sentiment_summary (with HAVING COUNT(*) >= 20)

**Tier 3 — Theme × Category Cross-Analysis** (unique insight):
- theme_category_analysis ("biggest pain points in headphones?")

### Cortex Analyst Scope
Semantic model covers Tier 1 + Tier 3 marts ONLY.
Product-level lookups go through direct SQL in the orchestrator, NOT through Analyst.
This keeps the semantic model dense and reliable.

### Product Category Derivation
```sql
-- For each ASIN with 3+ reviews, use COMPLETE on 3 sample reviews to derive category
-- Validate on top 100 ASINs first (manual spot-check 20)
-- Add derivation_confidence: high (50+ reviews), medium (10-49), low (3-9)
-- Only include high+medium in Cortex Analyst semantic model
```

## Review Theme Categories

Standard categories for ALL CLASSIFY_TEXT calls, Search filters, and Analyst semantic model:

```
battery_life, build_quality, sound_quality, connectivity, comfort,
value_for_money, customer_service, durability, ease_of_use, other
```

## Existing SQL Scripts (Reference Only)

| Script | Purpose |
|--------|---------|
| 01_setup.sql | Created DB, schemas, file format, stage |
| 03_curated.sql | CTAS from raw → typed CURATED.ELECTRONICS_REVIEWS |
| 04_analytics_prep.sql | Created ANALYTICS schema + V_REVIEWS_BASE |
| 05_views.sql | Utility views across RAW, CURATED, ANALYTICS |
| 06_cleaning_embeddings_prep.sql | V_REVIEWS_CLEAN regex cleaning view |
| 07_validation_checks.sql | Row counts, contamination checks |
| 08_create_embeddings.sql | Materialized clean text + 183K embeddings |
| 09_similarity_search.sql | Manual VECTOR_COSINE_SIMILARITY demo |
| 10_cortex_search_service.sql | Created ANALYTICS.REVIEW_SEARCH |
| 11_cortex_search_test.sql | Tested with SEARCH_PREVIEW() |
| 12_rag_generation.sql | Consumer Q&A + Business Analyst RAG modes |

Teammate-created objects (not in scripts):
- CURATED.V_ELECTRONICS_REVIEWS_DEDUP [Jiwei]
- ANALYTICS.V_REVIEWS_GENAI_BASE [Jiwei]
- ANALYTICS.REVIEWS_FOR_GENAI (183,457 rows) [Jiwei]
- ANALYTICS.REVIEW_INSIGHTS (200 rows, POC) [Jiwei]

## Key Design Decisions (Defensible in Interviews)

1. **Why snowflake-arctic-embed-m-v1.5?** — Benchmarked all 9 Cortex embedding models against MTEB. Best English retrieval in 768-dim class.
2. **Why Cortex Search over manual vector search?** — 12x performance (8.2s → 670ms). Managed, auto-refresh, hybrid semantic+keyword.
3. **Why Cortex Analyst for stats, not RAG?** — LLM fabricated statistics. Analyst generates verified SQL.
4. **Why pre-compute enrichment in dbt?** — LLM functions expensive. Compute once, query instantly. Enables aggregation + filtering.
5. **Why regex cleaning, not LLM?** — Deterministic, auditable, zero per-query cost at 183K rows.
6. **Why source from REVIEWS_FOR_GENAI?** — Dedup + type casting already done upstream. Don't redo validated work.
7. **Why conditional SUMMARIZE (500+ chars)?** — Median review is 189 chars. Summarizing 2 sentences wastes credits and adds no value.
8. **Why derive product categories via LLM?** — No metadata in dataset. Extract from review text. Validate before trusting.
9. **Why category-centric, not product-centric?** — 102K ASINs, avg <2 reviews. Product-level stats are noise for 99.5%. Category-level is always meaningful.
10. **Why 3-tier aggregation?** — Category (always valid), product (20+ reviews only), theme×category (unique cross-cutting insight).
11. **Why FastAPI as the core, not Streamlit?** — API-first architecture. The product is the intelligence service, not a UI. Swagger docs, testable, any frontend can consume it.
12. **Why Analyst only on category/theme marts?** — Product mart is too sparse (102K rows, 99% with <5 reviews). Analyst needs dense, reliable tables.

## What NOT to Do

- Don't hardcode Snowflake credentials — always use .env
- Don't modify anything in RAW, CURATED, or existing ANALYTICS objects — immutable
- Don't re-implement deduplication or type casting — already done by Jiwei
- Don't delete REVIEW_INSIGHTS (200-row POC) — keep for validation comparison
- Don't rebuild Cortex Search Service until Phase 1 is complete
- Don't run LLM functions at query time for pre-computable things
- Don't use RAG for quantitative questions — route to Cortex Analyst
- Don't add Airflow — use dbt scheduler + Snowflake Tasks
- Don't skip dbt tests on enriched columns
- Don't aggregate products with <20 reviews — statistics meaningless at low volume
- Don't SUMMARIZE reviews under 500 chars — the review IS the summary
- Don't assume product_category or product_title exist — only ASIN is available, categories are DERIVED
- Don't ignore bad timestamps — filter WHERE YEAR(review_ts) <= 2026 in staging
- Don't put product-level mart in Cortex Analyst — too sparse, use direct SQL
- Don't trust derived categories without validation — spot-check top 100 ASINs first
- Don't start frontend before FastAPI backend is working — API-first, always

## Teammate

Jiwei Yang handles data validation, quality assessment, and shares presentation responsibilities. Built: dedup view, type-safe GenAI base, REVIEWS_FOR_GENAI table, 200-row REVIEW_INSIGHTS POC. System designed for live code demos, not slides.

## Project Files

- `ReviewSense_AI_Implementation_Plan.md` — Original 7-phase plan (being updated)
- `ReviewSense_Required_Changes.md` — Data-driven changes to the plan
- `ReviewSense_Updated_Architecture.md` — FastAPI + Next.js architecture (Option A reference)
- `ReviewSense_Local_Setup_Guide.md` — Step-by-step local setup
