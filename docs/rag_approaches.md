# RAG Approaches — Evolution & Architecture

## Approach 1: Basic RAG

Search reviews → put into prompt → generate response

**Problems:**
- Single shot, no reasoning, couldn't handle follow-up questions or comparisons
- Questions with mixed intent were mishandled. "What are the main complaints about headphones and how many?" → needs both stats AND examples, basic RAG only does one
- Hallucinated statistics — asked "how many headphone reviews?" and the LLM made up numbers instead of querying actual data
- Wrong reviews returned — asked about a specific product (B01G8JO5F2) but got random reviews from other products because search had no ASIN filtering
- No context between messages — "What about the battery?" after discussing Echo Dot → searched "battery" generically, lost all context

## Approach 2: Orchestrated RAG

We built an intent-based orchestrator that classifies questions and routes them to specialized retrieval paths.

**Has 3 components:**

1. Intent classifier (rule-based + LLM fallback to CORTEX.COMPLETE for classification)
2. Deployed 3 retrieval paths:
   - a. Structured: Cortex Analyst generates verified SQL → executes against gold marts → returns data tables (no hallucinated stats)
   - b. Semantic: Cortex Search with auto-detected ASIN/rating filters → RAG with COMPLETE → returns answer with source reviews
   - c. Synthesis: runs both structured + semantic, merges via COMPLETE
3. Conversation Memory: follow-up detection via keyword signals ("it", "them", "how about"), session context tracking (products, brands, categories discussed), question resolution ("Should I get them?" → "Regarding product B01G8JO5F2: Should I get them?")

**Also added:**
- Smart fallbacks: Analyst refuses → auto-fallback to semantic search. Agent API fails → auto-fallback to orchestrated path
- ASIN auto-detection: if question mentions a product ID, search results are filtered to only that product
- Guardrails adapt: skip off-topic check for mid-conversation follow-ups, always check for prompt injection

**Problems:**
- Used one tool per question: "Suggest a waterproof headphone under $50 for running" → needs product search (metadata) + review search (user experience) + price filter, but orchestrator picks ONE path
- Can't compare: "Compare Logitech vs Sony" → falls back to 5 random reviews mentioning brands, no actual aggregation across hundreds of products
- Can't verify claims: "Is the 8-hour battery claim accurate?" → needs metadata features + review evidence + comparison logic, orchestrator doesn't join these data sources
- Can't do product intelligence: "Which brand has the best customer satisfaction?" → Analyst doesn't have brand data in semantic model, search returns random reviews
- Single-step reasoning only: "What products are people most disappointed with and why?" → needs to find worst products THEN search their reviews, but orchestrator does one or the other, not both

## Approach 3: Agentic RAG (current implementation)

Custom agent loop with purpose-built tools. COMPLETE plans which tools to call → our code executes them → COMPLETE synthesizes the final answer from combined results.

**How it solves the orchestrated RAG problems:**

| Problem | Orchestrated RAG | Agentic RAG |
|---------|-----------------|-------------|
| One tool per question | Picks ONE path | Plans multiple tool calls: search_products + search_reviews + compare |
| Can't compare | 5 random reviews | compare_brands aggregates across all products per brand |
| Can't verify claims | No metadata access | verify_claims joins metadata features vs review sentiment |
| No product intelligence | No brand data | get_brand_analysis queries metadata + review stats by brand |
| Single-step reasoning | One-and-done | Step 1: find worst products → Step 2: search their reviews → synthesize |

**Tools built (with tests passing):**

1. `search_reviews` (enhanced) — Cortex Search with 7 filters: ASIN, rating range, category, theme, verified purchase, review quality. 12/12 tests passing.
2. `get_product_detail` — combines metadata (title, brand, price, features from McAuley dataset) + review stats (rating, sentiment, negative rate) + category comparison (product vs category average) + theme breakdown. Joins 4 tables. 7/7 tests passing.
3. `search_products` — find products by price range, feature keywords, brand, category, minimum rating. Pure SQL against metadata + gold marts. 12/12 tests passing.

**Tools planned (not yet built):**

4. `compare_products` — side-by-side product comparison using get_product_detail for each ASIN
5. `verify_claims` — compare metadata feature claims vs actual review sentiment using CORTEX.EXTRACT_ANSWER + Search + COMPLETE verdict
6. `get_brand_analysis` + `compare_brands` — brand-level competitive intelligence
7. `find_similar_products` — uses also_buy metadata cross-references for recommendations
8. `price_value_analysis` — correlates price brackets with sentiment within a category

**Intelligent Decision Making — 4 levels:**

1. **Tool Selection** — COMPLETE reads the question and tool descriptions, picks which tools are needed. "Is the battery claim true?" → selects get_product_detail + search_reviews + verify_claims. Not hardcoded routing — the LLM reasons about what data it needs.

2. **Parameter Inference** — extracts structured parameters from natural language. "waterproof headphones under fifty dollars" → `search_products(category="headphones_earbuds", max_price=50, features_contain="waterproof")`. Infers ASIN from conversation context, sentiment from words like "complain" or "love".

3. **Result-Dependent Chaining** — adapts next steps based on what previous tools returned. If search_products returns 5 results → agent picks the top one and calls search_reviews for that specific product. If it returns 0 results → agent says "no products found" instead of blindly continuing. Each step informs the next.

4. **Answer Grounding** — before synthesizing the final answer, every number must come from a tool result (not hallucinated), every quote must come from search_reviews output. If a claim can't be verified with the data available, it says "insufficient data" instead of guessing.

**Agent loop (planned):**

```
User question
  → COMPLETE classifies what tools are needed (planning step)
  → Execute tools in sequence, each returns structured data
  → COMPLETE synthesizes final answer from all tool results
  → Return answer + tool trace (full transparency of what was used)
```

**Example: "Is the SENSO headphone battery really 8 hours?"**
1. Agent plans: need product features + battery reviews
2. `get_product_detail("B01G8JO5F2")` → features say "8 Hour Battery"
3. `search_reviews("battery life", asin="B01G8JO5F2", max_rating=2)` → negative battery reviews
4. `EXTRACT_ANSWER` on reviews: "How long does battery last?" → extracts "4 hours", "6 hours"
5. `COMPLETE` verdict: "Claim disputed — users report 3-6 hours active use, 8 hours is likely standby time"



