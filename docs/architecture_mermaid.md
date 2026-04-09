# ReviewSense AI — Mermaid Diagrams

Copy any of these into https://mermaid.live to generate images (export as PNG/SVG).

## 1. System Architecture (Full)

```mermaid
graph TB
    subgraph Frontend["🖥️ STREAMLIT FRONTEND"]
        Chat["Intelligence Chat<br/>Conversation Memory<br/>Tool Trace Display"]
        CatEx["Category Explorer<br/>14 Categories<br/>Theme Charts + Trends"]
        ProdAn["Product Analysis<br/>ASIN Lookup<br/>Stats + Metadata"]
        BI["Business Intelligence<br/>Category Reports<br/>Product Reports<br/>RED/YELLOW/GREEN"]
        Monitor["Monitoring & Alerts<br/>105 Alerts<br/>Severity Filtering"]
    end

    subgraph API["⚡ FASTAPI BACKEND"]
        Guard["🛡️ Input Guardrails<br/>Injection Detection | Off-Topic | ASIN Auto-Detect"]
        Memory["🧠 Conversation Memory<br/>Follow-up Detection | Session Context<br/>Question Resolution"]
        Orch["🎯 Orchestrator"]

        subgraph IntentRouter["Intent Classification"]
            RuleBased["Rule-Based<br/>(80% queries, zero cost)"]
            LLMFallback["LLM Fallback<br/>(CORTEX.COMPLETE)"]
        end

        subgraph Paths["Retrieval Paths"]
            Structured["📊 Structured<br/>Cortex Analyst → SQL"]
            Semantic["🔍 Semantic<br/>Cortex Search → RAG"]
            Synthesis["🔄 Synthesis<br/>Both → COMPLETE merge"]
        end

        subgraph Tools["🔧 Custom Agentic Tools"]
            T1["search_reviews<br/>7 filters ✅"]
            T2["get_product_detail<br/>4-table join ✅"]
            T3["search_products<br/>price/brand/feat ✅"]
            T4["compare_products<br/>side-by-side ✅"]
            T5["verify_claims<br/>features vs reality"]
            T6["brand_analysis<br/>competitive intel"]
            T7["find_similar<br/>also_buy data"]
            T8["price_value<br/>price vs quality"]
        end

        OutputGuard["🛡️ Output Guardrails<br/>PII Stripping | URL Removal"]
    end

    subgraph Snowflake["❄️ SNOWFLAKE + CORTEX AI"]
        subgraph Cortex["Cortex AI Services"]
            Analyst["Cortex Analyst<br/>Semantic Model<br/>NL → SQL"]
            Search["Cortex Search<br/>183K Reviews Indexed<br/>Hybrid Vector + Keyword"]
            Functions["Cortex Functions<br/>SENTIMENT | CLASSIFY_TEXT<br/>SUMMARIZE | COMPLETE"]
        end

        subgraph Pipeline["dbt Data Pipeline"]
            Raw["RAW<br/>200K Reviews<br/>786K Metadata"]
            Silver["SILVER<br/>stg_reviews<br/>int_enriched (183K)<br/>int_categories (12K)"]
            Gold["GOLD<br/>enriched_reviews (183K)<br/>7 Mart Tables<br/>product_lookup (12K)"]
            Monitoring["MONITORING<br/>review_anomalies (94)<br/>emerging_themes (18)<br/>data_quality (9)"]
        end

        AlertSys["Alert System<br/>ALERT_LOG (105)<br/>Stream + Task<br/>AI Summaries"]
    end

    Frontend -->|HTTP JSON| API
    Chat --> Guard
    Guard --> Memory
    Memory --> Orch
    Orch --> IntentRouter
    IntentRouter --> Paths
    Paths --> OutputGuard
    Tools -.->|"Used by Agent Loop"| Paths

    API -->|Snowflake Connector<br/>Key-Pair Auth| Snowflake
    Structured --> Analyst
    Semantic --> Search
    T1 --> Search
    T2 --> Gold
    T3 --> Gold
    T5 --> Search
    T6 --> Gold

    Raw --> Silver
    Silver -->|"Cortex AI Enrichment"| Gold
    Gold --> Monitoring
    Monitoring --> AlertSys

    style Frontend fill:#1a1a3e,stroke:#8b5cf6,color:#e0e7ff
    style API fill:#16213e,stroke:#06b6d4,color:#e0e7ff
    style Snowflake fill:#0f3460,stroke:#f43f5e,color:#e0e7ff
    style Tools fill:#312e81,stroke:#a78bfa,color:#e0e7ff
    style Cortex fill:#1e293b,stroke:#10b981,color:#e0e7ff
    style Pipeline fill:#1e293b,stroke:#f59e0b,color:#e0e7ff
```

## 2. RAG Evolution (3 Approaches)

```mermaid
graph LR
    subgraph Basic["❌ Basic RAG"]
        B1["Question"] --> B2["Search Reviews"]
        B2 --> B3["Stuff into Prompt"]
        B3 --> B4["LLM Answers"]
        B4 --> B5["❌ Hallucinated stats<br/>❌ No follow-ups<br/>❌ Wrong products"]
    end

    subgraph Orchestrated["⚠️ Orchestrated RAG"]
        O1["Question"] --> O2["Intent Classifier"]
        O2 --> O3["Structured<br/>(Analyst → SQL)"]
        O2 --> O4["Semantic<br/>(Search → RAG)"]
        O2 --> O5["Synthesis<br/>(Both)"]
        O3 --> O6["+ Memory<br/>+ Fallbacks"]
        O4 --> O6
        O5 --> O6
        O6 --> O7["⚠️ One tool/question<br/>⚠️ Can't compare<br/>⚠️ Can't verify claims"]
    end

    subgraph Agentic["✅ Agentic RAG"]
        A1["Question"] --> A2["🧠 PLAN<br/>(COMPLETE Call 1)"]
        A2 --> A3["Tool 1: search_reviews<br/>(RAG Retrieval)"]
        A2 --> A4["Tool 2: get_product_detail<br/>(SQL Query)"]
        A2 --> A5["Tool 3: compare_products<br/>(SQL Aggregation)"]
        A3 --> A6["✨ SYNTHESIZE<br/>(COMPLETE Call 2)"]
        A4 --> A6
        A5 --> A6
        A6 --> A7["✅ Grounded Answer<br/>✅ Multi-source<br/>✅ Citations"]
    end

    style Basic fill:#991b1b,stroke:#ef4444,color:#fecaca
    style Orchestrated fill:#92400e,stroke:#f59e0b,color:#fef3c7
    style Agentic fill:#065f46,stroke:#10b981,color:#d1fae5
```

## 3. Data Flow Pipeline

```mermaid
graph TD
    subgraph Sources["Data Sources"]
        Reviews["Amazon Reviews<br/>200K rows"]
        Meta["McAuley Metadata<br/>786K products"]
        Scraped["Scraped Metadata<br/>282 top products"]
    end

    subgraph RAW["RAW Schema"]
        RawReviews["ELECTRONICS_REVIEWS_RAW"]
        RawMeta["PRODUCT_METADATA_RAW"]
    end

    subgraph CURATED["CURATED Schema"]
        CurMeta["PRODUCT_METADATA<br/>title, brand, price<br/>features, category"]
    end

    subgraph SILVER["SILVER Schema (dbt)"]
        Staging["stg_reviews<br/>VIEW | Clean + Filter<br/>Quality Tiers"]
        Enriched["int_enriched_reviews<br/>TABLE | 183K rows<br/>SENTIMENT + CLASSIFY_TEXT<br/>+ SUMMARIZE"]
        Categories["int_product_categories<br/>TABLE | 12K ASINs<br/>→ 14 categories"]
        Names["int_product_names<br/>TABLE | 407 ASINs<br/>BRAND + PRODUCT_NAME"]
    end

    subgraph GOLD["GOLD Schema (dbt marts)"]
        Lookup["product_lookup<br/>12K ASINs<br/>category + metadata"]
        Fact["enriched_reviews<br/>183K rows<br/>MAIN FACT TABLE"]
        T1Cat["category_sentiment<br/>_summary (14 rows)"]
        T1Trend["category_monthly<br/>_trends (1,715)"]
        T2Prod["product_sentiment<br/>_summary (407)"]
        T3Theme["theme_category<br/>_analysis (138)"]
        Complaint["complaint<br/>_analysis (118)"]
    end

    subgraph MONITOR["MONITORING (dbt)"]
        Anomalies["review_anomalies<br/>94 detected"]
        CrossCat["cross_category<br/>_alerts (6)"]
        Emerging["emerging_themes<br/>(18)"]
        DQ["data_quality<br/>_checks (9)"]
        ProdAnom["product_anomalies<br/>(1)"]
    end

    subgraph Output["Snowflake Services"]
        SearchSvc["Cortex Search<br/>ENRICHED_REVIEW_SEARCH"]
        AnalystSvc["Cortex Analyst<br/>Semantic Model"]
        AlertLog["ALERT_LOG<br/>105 alerts + AI summaries"]
    end

    Reviews --> RawReviews
    Meta --> RawMeta
    Scraped --> RawMeta
    RawMeta --> CurMeta
    RawReviews --> Staging
    Staging --> Enriched
    Staging --> Categories
    Staging --> Names
    CurMeta --> Lookup
    Categories --> Lookup
    Names --> Lookup
    Enriched --> Fact
    Lookup --> Fact
    Fact --> T1Cat
    Fact --> T1Trend
    Fact --> T2Prod
    Fact --> T3Theme
    Fact --> Complaint
    Fact --> SearchSvc
    T1Cat --> AnalystSvc
    T1Trend --> AnalystSvc
    T3Theme --> AnalystSvc
    Fact --> Anomalies
    Anomalies --> CrossCat
    Fact --> Emerging
    Fact --> DQ
    Fact --> ProdAnom
    Anomalies --> AlertLog

    style Sources fill:#1e293b,stroke:#8b5cf6,color:#e0e7ff
    style RAW fill:#1e293b,stroke:#64748b,color:#e0e7ff
    style CURATED fill:#1e293b,stroke:#64748b,color:#e0e7ff
    style SILVER fill:#1e293b,stroke:#f59e0b,color:#e0e7ff
    style GOLD fill:#1e293b,stroke:#10b981,color:#e0e7ff
    style MONITOR fill:#1e293b,stroke:#ef4444,color:#e0e7ff
    style Output fill:#1e293b,stroke:#06b6d4,color:#e0e7ff
```

## 4. Agentic Tool Architecture

```mermaid
graph TD
    Q["User Question"] --> Plan["🧠 PLANNING<br/>(CORTEX.COMPLETE)"]

    Plan --> |"Decides which tools"| Execute

    subgraph Execute["TOOL EXECUTION"]
        direction TB
        subgraph RAGTools["RAG Tools (Cortex Search)"]
            SR["search_reviews<br/>7 filters<br/>12 tests ✅"]
            VC["verify_claims<br/>EXTRACT_ANSWER + Search<br/>PLANNED"]
        end

        subgraph SQLTools["SQL Tools (Gold Marts + Metadata)"]
            GPD["get_product_detail<br/>4-table join<br/>7 tests ✅"]
            SP["search_products<br/>price/brand/features<br/>12 tests ✅"]
            CP["compare_products<br/>metric deltas<br/>8 tests"]
            BA["brand_analysis<br/>brand aggregation<br/>PLANNED"]
            FS["find_similar<br/>also_buy data<br/>PLANNED"]
            PV["price_value<br/>price vs sentiment<br/>PLANNED"]
        end
    end

    Execute --> Synth["✨ SYNTHESIS<br/>(CORTEX.COMPLETE)<br/>Grounded Answer + Citations"]

    Plan -.-> |"2 LLM calls total"| Synth
    SR -.-> |"Cortex Search<br/>(RAG Retrieval)"| CortexSearch["❄️ Cortex Search Service<br/>183K reviews indexed"]
    GPD -.-> |"SQL queries"| GoldMarts["❄️ Gold Marts<br/>7 tables"]
    SP -.-> |"SQL queries"| Metadata["❄️ Product Metadata<br/>786K products"]

    style Q fill:#4c1d95,stroke:#8b5cf6,color:#e0e7ff
    style Plan fill:#1e3a5f,stroke:#06b6d4,color:#e0e7ff
    style Synth fill:#1e3a5f,stroke:#06b6d4,color:#e0e7ff
    style RAGTools fill:#991b1b20,stroke:#ef4444,color:#e0e7ff
    style SQLTools fill:#065f4620,stroke:#10b981,color:#e0e7ff
    style Execute fill:#1e293b,stroke:#a78bfa,color:#e0e7ff
```

## 5. Monitoring & Alert Flow

```mermaid
graph LR
    subgraph dbt["dbt Monitoring Models"]
        RA["review_anomalies<br/>RATING_DROP<br/>SENTIMENT_SHIFT<br/>COMPLAINT_SPIKE<br/>DECLINING_TREND<br/>RANK_DROP"]
        ET["emerging_themes<br/>Growth 2x+"]
        CC["cross_category<br/>_alerts<br/>3+ categories"]
        PA["product_anomalies<br/>Top ASINs"]
        DQ["data_quality<br/>_checks"]
    end

    RA --> Stream["Snowflake Stream<br/>Detects new anomalies"]
    Stream --> Task["Snowflake Task<br/>Weekly CRON"]
    Task --> Proc["GENERATE_ALERTS()<br/>CORTEX.COMPLETE<br/>AI Summaries"]
    ET --> Proc
    CC --> Proc
    PA --> Proc
    DQ --> Proc
    Proc --> AL["ALERT_LOG<br/>105 alerts<br/>20 HIGH | 23 MED | 62 LOW"]
    AL --> API["GET /alerts<br/>POST /alerts/analyze<br/>PATCH /alerts/acknowledge"]
    API --> Dash["Monitoring Dashboard<br/>Severity Filter<br/>On-Demand Analysis"]

    style dbt fill:#1e293b,stroke:#f59e0b,color:#e0e7ff
    style AL fill:#991b1b,stroke:#ef4444,color:#fecaca
    style Dash fill:#1a1a3e,stroke:#8b5cf6,color:#e0e7ff
```

## 6. Agentic RAG — Detailed Flow

```mermaid
graph TD
    User["👤 User Question"] --> Guard["🛡️ Input Guardrails<br/>Injection | Off-Topic | Length"]
    Guard --> Memory["🧠 Conversation Memory<br/>Resolve follow-ups<br/>Session context"]
    Memory --> Decision{{"Is Agent<br/>Available?"}}

    Decision -->|"Yes"| AgentLoop
    Decision -->|"No (fallback)"| Legacy["Legacy Orchestrator<br/>Rule-based → One Path"]

    subgraph AgentLoop["🤖 AGENTIC RAG LOOP"]
        direction TB

        Plan["🧠 STEP 1: PLANNING<br/>(CORTEX.COMPLETE — Call 1)<br/><br/>System: You are a planning agent.<br/>Here are 10 tools with descriptions.<br/>Output a JSON plan.<br/><br/>Output:<br/>{'reasoning': '...', 'steps': [...]}"]

        Plan --> Validate{"Validate Plan<br/>Max 5 steps?<br/>Known tools?<br/>Valid params?"}

        Validate -->|"Valid"| ExecLoop
        Validate -->|"Invalid"| Legacy

        subgraph ExecLoop["⚙️ STEP 2: EXECUTE TOOLS"]
            direction TB

            Step1["Execute Step 1"] --> Check1{"Result<br/>empty?"}
            Check1 -->|"No"| Step2["Execute Step 2"]
            Check1 -->|"Yes, dependent"| Skip2["Skip Step 2"]
            Check1 -->|"Yes, independent"| Step2
            Step2 --> Check2{"Result<br/>empty?"}
            Check2 --> Step3["Execute Step 3<br/>(if in plan)"]
            Skip2 --> Step3
        end

        ExecLoop --> Timeout{"Time < 45s?<br/>Steps < 5?"}
        Timeout -->|"Yes"| Synth
        Timeout -->|"No"| PartialSynth["Synthesize with<br/>partial results"]

        Synth["✨ STEP 3: SYNTHESIS<br/>(CORTEX.COMPLETE — Call 2)<br/><br/>System: Answer using ONLY<br/>these tool results.<br/>Cite specific data + quotes.<br/>Never invent facts.<br/><br/>Input: All tool results as JSON"]
    end

    Synth --> OutputGuard["🛡️ Output Guardrails<br/>PII Strip | URL Remove"]
    PartialSynth --> OutputGuard
    Legacy --> OutputGuard
    OutputGuard --> Response["📤 Response<br/>answer + tool_trace + data<br/>+ sources + citations"]

    style User fill:#4c1d95,stroke:#8b5cf6,color:#e0e7ff
    style AgentLoop fill:#0f172a,stroke:#8b5cf6,color:#e0e7ff
    style Plan fill:#1e3a5f,stroke:#06b6d4,color:#e0e7ff
    style Synth fill:#1e3a5f,stroke:#06b6d4,color:#e0e7ff
    style ExecLoop fill:#1e293b,stroke:#a78bfa,color:#e0e7ff
    style Response fill:#065f46,stroke:#10b981,color:#d1fae5
    style Legacy fill:#92400e,stroke:#f59e0b,color:#fef3c7
```

## 7. Agentic RAG — Tool Execution Detail

```mermaid
graph LR
    subgraph Planning["🧠 COMPLETE Plans"]
        Q["'Suggest waterproof<br/>headphones under $50'"]
        Q --> P1["Step 1: search_products<br/>category=headphones<br/>max_price=50<br/>features=waterproof"]
        Q --> P2["Step 2: search_reviews<br/>query='waterproof swimming'<br/>for top results from Step 1"]
        Q --> P3["Step 3: compare_products<br/>top 3 ASINs from Step 1"]
    end

    subgraph Execution["⚙️ Tool Execution"]
        P1 --> E1["search_products()<br/>→ SQL query on metadata<br/>→ 5 products found"]
        P2 --> E2["search_reviews()<br/>→ Cortex Search (RAG)<br/>→ 5 reviews per product"]
        P3 --> E3["compare_products()<br/>→ SQL joins on gold marts<br/>→ side-by-side stats"]
    end

    subgraph DataSources["❄️ Data Sources"]
        E1 -.-> DS1["CURATED.PRODUCT_METADATA<br/>(price, features, brand)"]
        E1 -.-> DS2["GOLD.PRODUCT_SENTIMENT_SUMMARY<br/>(ratings, sentiment)"]
        E2 -.-> DS3["Cortex Search Service<br/>(183K reviews indexed)"]
        E3 -.-> DS4["GOLD.ENRICHED_REVIEWS<br/>(theme breakdown per ASIN)"]
    end

    subgraph Synthesis["✨ COMPLETE Synthesizes"]
        E1 --> S["All tool results → COMPLETE<br/><br/>'Based on 5 matching products:<br/>1. SENSO BT ($27, 4526 reviews, 3.78★)<br/>   IPX7 waterproof, users report...<br/>2. TOZO T10 ($25, 146 reviews, 4.2★)...<br/><br/>Recommendation: TOZO T10 offers<br/>best value with higher rating and<br/>verified waterproof performance.'"]
        E2 --> S
        E3 --> S
    end

    style Planning fill:#1e3a5f,stroke:#06b6d4,color:#e0e7ff
    style Execution fill:#1e293b,stroke:#a78bfa,color:#e0e7ff
    style DataSources fill:#0f3460,stroke:#f43f5e,color:#e0e7ff
    style Synthesis fill:#065f46,stroke:#10b981,color:#d1fae5
```

## 8. Agentic RAG — Intelligence Levels

```mermaid
graph TD
    subgraph L1["Level 1: Tool Selection"]
        Q1["'Is battery claim true?'"] --> D1["Agent reasons:<br/>Need features (metadata)<br/>+ battery reviews (search)<br/>+ verification logic"]
        D1 --> T1["Select:<br/>get_product_detail<br/>search_reviews<br/>verify_claims"]
    end

    subgraph L2["Level 2: Parameter Inference"]
        Q2["'waterproof under $50'"] --> D2["Agent extracts:<br/>category = headphones<br/>max_price = 50<br/>features = waterproof"]
        D2 --> T2["search_products(<br/>  category='headphones_earbuds'<br/>  max_price=50<br/>  features_contain='waterproof'<br/>)"]
    end

    subgraph L3["Level 3: Adaptive Chaining"]
        Q3["search_products<br/>→ 5 results"] --> D3{"Results<br/>found?"}
        D3 -->|"Yes"| T3A["search_reviews<br/>for top product ASIN"]
        D3 -->|"No"| T3B["'No waterproof products<br/>found in that price range'"]
    end

    subgraph L4["Level 4: Answer Grounding"]
        Q4["All tool results<br/>collected"] --> D4["Verify:<br/>Every number from tool data ✅<br/>Every quote from search ✅<br/>No invented facts ✅<br/>Cite sources ✅"]
        D4 --> T4["Grounded answer<br/>with citations"]
    end

    L1 --> L2
    L2 --> L3
    L3 --> L4

    style L1 fill:#1e293b,stroke:#8b5cf6,color:#e0e7ff
    style L2 fill:#1e293b,stroke:#06b6d4,color:#e0e7ff
    style L3 fill:#1e293b,stroke:#f59e0b,color:#e0e7ff
    style L4 fill:#1e293b,stroke:#10b981,color:#e0e7ff
```

## 9. Agentic vs Orchestrated — Side by Side

```mermaid
graph TB
    subgraph Orch["⚠️ ORCHESTRATED RAG (Current Fallback)"]
        direction TB
        OQ["Question"] --> OC["Intent Classifier<br/>(rule-based)"]
        OC --> |"structured"| OA["Cortex Analyst<br/>ONE SQL query"]
        OC --> |"semantic"| OS["Cortex Search<br/>ONE search"]
        OC --> |"synthesis"| OB["Both<br/>(still 2 calls)"]
        OA --> OR["Answer<br/>(single data source)"]
        OS --> OR
        OB --> OR

        OR --> OX["❌ Can't combine 4 tools<br/>❌ Can't chain results<br/>❌ Can't adapt mid-query"]
    end

    subgraph Agent["✅ AGENTIC RAG (Target Architecture)"]
        direction TB
        AQ["Question"] --> AP["🧠 COMPLETE Plans<br/>(sees 10 tools)"]
        AP --> AT1["Tool 1 → result"]
        AP --> AT2["Tool 2 → result"]
        AP --> AT3["Tool 3 → result<br/>(uses Tool 1 output)"]
        AT1 --> AS["✨ COMPLETE Synthesizes<br/>(all results combined)"]
        AT2 --> AS
        AT3 --> AS
        AS --> AR["Answer<br/>(multi-source, grounded)"]

        AR --> AY["✅ Combines RAG + SQL<br/>✅ Chains results<br/>✅ Adapts if empty<br/>✅ 2 LLM calls only"]
    end

    style Orch fill:#92400e20,stroke:#f59e0b,color:#e0e7ff
    style Agent fill:#065f4620,stroke:#10b981,color:#e0e7ff
```

## How to Generate Images

1. Go to **https://mermaid.live**
2. Paste any diagram code above
3. Click **Actions → Export PNG** (or SVG for high quality)
4. For dark theme: toggle the theme in mermaid.live settings

Or use VS Code extension: **"Mermaid Markdown Syntax Highlighting"** + **"Markdown Preview Mermaid Support"** to preview directly in VS Code.

Or generate via CLI:
```bash
npm install -g @mermaid-js/mermaid-cli
mmdc -i architecture_mermaid.md -o architecture.png -t dark
```
