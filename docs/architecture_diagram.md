# ReviewSense AI — Complete Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              STREAMLIT FRONTEND                                 │
│  ┌──────────────┐ ┌─────────────────┐ ┌──────────────┐ ┌───────────────────┐   │
│  │ Intelligence │ │    Category     │ │   Product    │ │    Business       │   │
│  │    Chat      │ │    Explorer     │ │   Analysis   │ │   Intelligence    │   │
│  │              │ │                 │ │              │ │                   │   │
│  │ Conversation │ │ 14 Categories   │ │ ASIN Lookup  │ │ Category Reports  │   │
│  │ Memory       │ │ Theme Charts    │ │ Stats + Meta │ │ Product Reports   │   │
│  │ Tool Trace   │ │ Trend Lines     │ │ Ask About    │ │ RED/YELLOW/GREEN  │   │
│  └──────┬───────┘ └────────┬────────┘ └──────┬───────┘ └────────┬──────────┘   │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                    Monitoring & Alerts Dashboard                         │   │
│  │         105 alerts | Severity Filtering | On-Demand Analysis             │   │
│  └──────────────────────────────────────┬──────────────────────────────────┘   │
└─────────────────────────────────────────┼──────────────────────────────────────┘
                                          │ HTTP (JSON)
                                          ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              FASTAPI BACKEND                                    │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                         INPUT GUARDRAILS                                │    │
│  │    Prompt Injection Detection | Off-Topic Check | Length Validation      │    │
│  │    ASIN Auto-Detection | Conversation-Aware (skip check if follow-up)   │    │
│  └─────────────────────────────────┬───────────────────────────────────────┘    │
│                                    ▼                                            │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                    CONVERSATION MEMORY                                   │    │
│  │    Follow-up Detection (keyword signals: "it", "them", "how about")     │    │
│  │    Session Context (products, brands, categories discussed)              │    │
│  │    Question Resolution: "Should I get them?" → "Regarding B01G8JO5F2"   │    │
│  └─────────────────────────────────┬───────────────────────────────────────┘    │
│                                    ▼                                            │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                       ORCHESTRATOR                                       │    │
│  │                                                                          │    │
│  │   ┌─────────────────────────────────────────────────────────────────┐    │    │
│  │   │              INTENT CLASSIFIER                                  │    │    │
│  │   │   Rule-based (80% of queries, zero LLM cost)                   │    │    │
│  │   │   + LLM fallback (CORTEX.COMPLETE for ambiguous cases)          │    │    │
│  │   └──────────┬──────────────────┬──────────────────┬────────────────┘    │    │
│  │              │                  │                  │                     │    │
│  │              ▼                  ▼                  ▼                     │    │
│  │   ┌──────────────┐   ┌──────────────┐   ┌──────────────────┐           │    │
│  │   │  STRUCTURED  │   │   SEMANTIC   │   │    SYNTHESIS     │           │    │
│  │   │    PATH      │   │    PATH      │   │      PATH        │           │    │
│  │   │              │   │              │   │                  │           │    │
│  │   │ Cortex       │   │ Cortex       │   │ Both paths +    │           │    │
│  │   │ Analyst      │   │ Search +     │   │ COMPLETE merge  │           │    │
│  │   │ → SQL        │   │ COMPLETE     │   │                  │           │    │
│  │   │ → Data       │   │ → RAG Answer │   │ → Stats + Quotes │           │    │
│  │   └──────┬───────┘   └──────┬───────┘   └────────┬─────────┘           │    │
│  │          │                  │                     │                     │    │
│  │          │    Smart Fallback: Analyst refuses → Search                  │    │
│  │          └──────────────────┴─────────────────────┘                     │    │
│  └─────────────────────────────────┬───────────────────────────────────────┘    │
│                                    ▼                                            │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                      OUTPUT GUARDRAILS                                   │    │
│  │              PII Stripping | URL Removal | Sanitization                  │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                    CUSTOM AGENTIC TOOLS                                  │    │
│  │                                                                          │    │
│  │  ┌────────────────┐ ┌──────────────────┐ ┌───────────────────┐          │    │
│  │  │ search_reviews │ │get_product_detail│ │  search_products  │          │    │
│  │  │ 7 filters      │ │ 4-table join     │ │ price/brand/feat  │          │    │
│  │  │ 12 tests ✅    │ │ 7 tests ✅       │ │ 12 tests ✅       │          │    │
│  │  └────────────────┘ └──────────────────┘ └───────────────────┘          │    │
│  │  ┌────────────────┐ ┌──────────────────┐ ┌───────────────────┐          │    │
│  │  │compare_products│ │  verify_claims   │ │  brand_analysis   │          │    │
│  │  │ side-by-side   │ │ features vs      │ │ + compare_brands  │          │    │
│  │  │ metric deltas  │ │ review reality   │ │ competitive intel │          │    │
│  │  │ 8 tests        │ │ PLANNED          │ │ PLANNED           │          │    │
│  │  └────────────────┘ └──────────────────┘ └───────────────────┘          │    │
│  │  ┌────────────────┐ ┌──────────────────┐                                │    │
│  │  │find_similar    │ │price_value       │                                │    │
│  │  │ also_buy data  │ │ price vs quality │                                │    │
│  │  │ PLANNED        │ │ PLANNED          │                                │    │
│  │  └────────────────┘ └──────────────────┘                                │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│                                                                                 │
│  API Endpoints:                                                                 │
│  POST /query          POST /query/stream      GET /health                      │
│  GET  /categories     GET  /categories/{cat}   GET /products/{asin}             │
│  POST /compare        GET  /alerts             POST /alerts/analyze             │
│  PATCH /alerts/{id}   GET  /report/category    GET /report/product              │
└─────────────────────────────────────────────────────────────────────────────────┘
                                          │
                                          │ Snowflake Connector (key-pair auth)
                                          ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           SNOWFLAKE + CORTEX AI                                 │
│                                                                                 │
│  ┌─ CORTEX AI SERVICES ──────────────────────────────────────────────────────┐  │
│  │                                                                           │  │
│  │  ┌──────────────────┐  ┌───────────────────────────────────────────────┐  │  │
│  │  │  Cortex Analyst  │  │         Cortex Search Services                │  │  │
│  │  │                  │  │                                               │  │  │
│  │  │  Semantic Model: │  │  GOLD.ENRICHED_REVIEW_SEARCH (PRIMARY)       │  │  │
│  │  │  4 tables        │  │    183K reviews indexed                      │  │  │
│  │  │  3 relationships │  │    Filters: ASIN, RATING, CATEGORY,         │  │  │
│  │  │  5 verified      │  │      THEME, QUALITY, VERIFIED               │  │  │
│  │  │    queries       │  │                                               │  │  │
│  │  │  NL → SQL        │  │  ANALYTICS.REVIEW_SEARCH (LEGACY)           │  │  │
│  │  │                  │  │                        │  │  │
│  │  └──────────────────┘  └───────────────────────────────────────────────┘  │  │
│  │                                                                           │  │
│  │  ┌──────────────────────────────────────────────────────────────────────┐  │  │
│  │  │                    Cortex Functions (used in Phase 1 enrichment)     │  │  │
│  │  │  SENTIMENT() | CLASSIFY_TEXT() | SUMMARIZE() | COMPLETE()           │  │  │
│  │  │  Pre-computed on 183K rows, stored in gold marts                    │  │  │
│  │  └──────────────────────────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────────────────────┘  │
│                                                                                 │
│  ┌─ DATA PIPELINE (dbt) ────────────────────────────────────────────────────┐  │
│  │                                                                           │  │
│  │  RAW                          CURATED                                     │  │
│  │  ┌───────────────────┐       ┌─────────────────────┐                     │  │
│  │  │ ELECTRONICS_      │       │ PRODUCT_METADATA    │                     │  │
│  │  │ REVIEWS_RAW       │       │ 786K products       │                     │  │
│  │  │ 200K rows         │       │ title, brand, price │                     │  │
│  │  ├───────────────────┤       │ features, category  │                     │  │
│  │  │ PRODUCT_METADATA_ │       │ also_buy, rank      │                     │  │
│  │  │ RAW (786K)        │       └─────────────────────┘                     │  │
│  │  └───────────────────┘                                                    │  │
│  │           │                                                               │  │
│  │           ▼                                                               │  │
│  │  SILVER (dbt staging + intermediate)                                      │  │
│  │  ┌──────────────────┐  ┌─────────────────────┐  ┌──────────────────┐    │  │
│  │  │ stg_reviews      │  │ int_enriched_reviews│  │ int_product_     │    │  │
│  │  │ VIEW             │  │ TABLE               │  │ categories       │    │  │
│  │  │ Clean + filter   │  │ 183K rows           │  │ 12K ASINs → 14  │    │  │
│  │  │ Quality tier     │  │ SENTIMENT           │  │ categories       │    │  │
│  │  │ Regex cleaning   │  │ CLASSIFY_TEXT       │  ├──────────────────┤    │  │
│  │  └──────────────────┘  │ SUMMARIZE           │  │ int_product_     │    │  │
│  │                        └─────────────────────┘  │ names            │    │  │
│  │                                                  │ 407 ASINs       │    │  │
│  │                                                  └──────────────────┘    │  │
│  │           │                                                               │  │
│  │           ▼                                                               │  │
│  │  GOLD (dbt marts)                                                         │  │
│  │  ┌─────────────────────────────────────────────────────────────────────┐  │  │
│  │  │ enriched_reviews (183K) ─── MAIN FACT TABLE                        │  │  │
│  │  ├─────────────────────────────────────────────────────────────────────┤  │  │
│  │  │                                                                     │  │  │
│  │  │  Tier 1 (Category)           Tier 2 (Product)    Tier 3 (Theme)    │  │  │
│  │  │  ┌──────────────────┐       ┌──────────────┐    ┌──────────────┐  │  │  │
│  │  │  │category_sentiment│       │product_      │    │theme_category│  │  │  │
│  │  │  │_summary (14)     │       │sentiment_    │    │_analysis     │  │  │  │
│  │  │  ├──────────────────┤       │summary (407) │    │(138)         │  │  │  │
│  │  │  │category_monthly  │       └──────────────┘    └──────────────┘  │  │  │
│  │  │  │_trends (1,715)   │                                              │  │  │
│  │  │  └──────────────────┘       ┌──────────────┐    ┌──────────────┐  │  │  │
│  │  │                             │product_      │    │complaint_    │  │  │  │
│  │  │                             │lookup (12K)  │    │analysis (118)│  │  │  │
│  │  │                             │+metadata     │    └──────────────┘  │  │  │
│  │  │                             │+brand+price  │                      │  │  │
│  │  │                             └──────────────┘                      │  │  │
│  │  └─────────────────────────────────────────────────────────────────────┘  │  │
│  │           │                                                               │  │
│  │           ▼                                                               │  │
│  │  MONITORING (dbt)                                                         │  │
│  │  ┌──────────────────┐ ┌──────────────┐ ┌──────────────┐ ┌────────────┐  │  │
│  │  │review_anomalies  │ │cross_category│ │emerging_     │ │data_quality│  │  │
│  │  │94 anomalies      │ │_alerts (6)   │ │themes (18)   │ │_checks (9) │  │  │
│  │  │5 types: RATING   │ │Themes across │ │Growth 2x+    │ │Freshness   │  │  │
│  │  │DROP, SENTIMENT   │ │3+ categories │ │vs historical │ │Row counts  │  │  │
│  │  │SHIFT, COMPLAINT  │ └──────────────┘ └──────────────┘ │NULL rates  │  │  │
│  │  │SPIKE, DECLINING  │ ┌──────────────┐                  │Schema      │  │  │
│  │  │TREND, RANK_DROP  │ │product_      │                  └────────────┘  │  │
│  │  └────────┬─────────┘ │anomalies (1) │                                  │  │
│  │           │           └──────────────┘                                   │  │
│  │           ▼                                                               │  │
│  │  SNOWFLAKE OBJECTS                                                        │  │
│  │  ┌────────────────┐  ┌──────────────────┐  ┌──────────────────────────┐  │  │
│  │  │ALERT_LOG table │  │REVIEW_ANOMALIES_ │  │GENERATE_ALERTS()        │  │  │
│  │  │105 alerts      │  │STREAM            │  │Stored Proc              │  │  │
│  │  │AI summaries    │  │Triggers on new   │  │CORTEX.COMPLETE summaries│  │  │
│  │  │HIGH/MED/LOW    │  │anomalies         │  ├──────────────────────────┤  │  │
│  │  └────────────────┘  └──────────────────┘  │GENERATE_ALERTS_TASK     │  │  │
│  │                                             │Weekly CRON schedule     │  │  │
│  │  5 UDFs (Agent Tools):                      └──────────────────────────┘  │  │
│  │  GET_CATEGORY_SUMMARY | GET_PRODUCT_STATS | GET_THEME_BREAKDOWN          │  │
│  │  GET_COMPLAINT_DATA   | GET_MONTHLY_TRENDS                               │  │
│  └───────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## RAG Evolution

```
APPROACH 1: Basic RAG                    APPROACH 2: Orchestrated RAG
┌──────────────────────┐                ┌──────────────────────────────────┐
│ Question             │                │ Question                         │
│    ↓                 │                │    ↓                             │
│ Search reviews       │                │ Intent Classifier                │
│    ↓                 │                │    ↓         ↓          ↓       │
│ Stuff into prompt    │                │ Structured  Semantic  Synthesis  │
│    ↓                 │                │ (Analyst)   (Search)  (Both)     │
│ LLM answers          │                │    ↓         ↓          ↓       │
│                      │                │ Conversation Memory              │
│ Problems:            │                │ Smart Fallbacks                  │
│ - Hallucinated stats │                │                                  │
│ - No follow-ups      │                │ Problems:                        │
│ - Wrong products     │                │ - One tool per question          │
│ - No comparisons     │                │ - Can't compare brands           │
└──────────────────────┘                │ - Can't verify claims            │
                                        └──────────────────────────────────┘

APPROACH 3: Agentic RAG (Current)
┌────────────────────────────────────────────────────────────────────┐
│ Question                                                           │
│    ↓                                                               │
│ [COMPLETE Call 1: PLANNING]                                        │
│    "Which tools do I need? In what order?"                         │
│    ↓                                                               │
│ Plan: [{search_products, params}, {search_reviews, params}, ...]   │
│    ↓                                                               │
│ [EXECUTE: RAG Retrieval + SQL Queries — no LLM cost]               │
│    search_reviews  → Cortex Search (THIS IS THE RAG RETRIEVAL)     │
│    get_product_detail → SQL joins on 4 gold mart tables            │
│    search_products → SQL on metadata (price, brand, features)      │
│    compare_products → SQL aggregation across products              │
│    verify_claims  → Cortex Search + EXTRACT_ANSWER (RAG)           │
│    brand_analysis → SQL aggregation by brand                       │
│                                                                     │
│    Adaptive: skip tools if previous result is empty                │
│    ↓                                                               │
│ [COMPLETE Call 2: AUGMENTED GENERATION]                              │
│    "Answer using ONLY these tool results. Cite everything."         │
│    RAG retrieval results + SQL data → grounded answer               │
│    ↓                                                               │
│ Grounded Answer + Tool Trace + Citations                           │
│                                                                     │
│ Where is RAG?                                                       │
│   R (Retrieval) = search_reviews via Cortex Search                 │
│   A (Augmented) = tool results injected into synthesis prompt      │
│   G (Generation) = COMPLETE synthesizes final answer                │
│                                                                     │
│ What's beyond RAG?                                                  │
│   SQL tools (product stats, brand analysis, price comparison)      │
│   These query structured data directly — not retrieval-augmented   │
│   The agent decides WHEN to use RAG vs SQL vs both                 │
│                                                                     │
│ Total LLM cost: 2 COMPLETE calls (plan + synthesize)               │
│ Tool execution: Cortex Search + SQL queries (near zero LLM cost)   │
│ Safety: Max 5 steps | 45s timeout | Citation required               │
└────────────────────────────────────────────────────────────────────┘
```

## Data Flow Summary

```
Amazon Reviews (200K)                    McAuley Metadata (786K)
       │                                        │
       ▼                                        ▼
  RAW.REVIEWS_RAW                    RAW.PRODUCT_METADATA_RAW
       │                                        │
       ▼                                        ▼
  ANALYTICS.REVIEWS_FOR_GENAI       CURATED.PRODUCT_METADATA
  (183K deduplicated)                (title, brand, price, features)
       │                                        │
       ▼                                        │
  ┌─ dbt pipeline ─────────────────────────┐    │
  │ SILVER.stg_reviews (clean, filter)     │    │
  │    ↓                                   │    │
  │ SILVER.int_enriched_reviews            │    │
  │ (SENTIMENT + CLASSIFY_TEXT + SUMMARIZE) │    │
  │    ↓                                   │    │
  │ SILVER.int_product_categories (12K)    │    │
  │    ↓                    ←──────────────┼────┘
  │ GOLD.product_lookup (COALESCE real metadata, LLM-derived)
  │    ↓                                   │
  │ GOLD.enriched_reviews (183K fact)      │
  │    ↓                                   │
  │ GOLD marts (7 tables)                  │
  │    ↓                                   │
  │ GOLD monitoring (5 models)             │
  └────────────────────────────────────────┘
       │              │              │
       ▼              ▼              ▼
  Cortex Search   Cortex Analyst   Alert System
  (review search) (SQL generation) (AI summaries)
       │              │              │
       └──────────────┴──────────────┘
                      │
                      ▼
              FastAPI Backend
                      │
                      ▼
              Streamlit Frontend
```

## Key Numbers

| Metric | Value |
|--------|-------|
| Total reviews | 183,447 |
| Unique products | 102,583 |
| Products with metadata | 25,408 (24.8%) |
| Product categories | 14 |
| Review themes | 10 |
| Gold mart tables | 7 |
| Monitoring models | 5 |
| Alerts generated | 105 (20 HIGH, 23 MED, 62 LOW) |
| API endpoints | 12 |
| Custom tools (built) | 4 (31 tests passing) |
| Custom tools (planned) | 6 |
| Eval questions | 100 |
| Cortex functions used | 6 (SENTIMENT, CLASSIFY_TEXT, SUMMARIZE, COMPLETE, SEARCH_PREVIEW, Analyst) |
