# ReviewSense AI — Project Log

## Week 1 — Data Pipeline Setup and Validation

### Completed

- Connected Snowflake warehouse and database
- Verified RAW and CURATED tables
- Validated row counts between RAW and CURATED layers
- Checked null rates for critical fields
- Analyzed rating distribution
- Identified negative review count
- Analyzed verified purchase ratio
- Examined helpful vote distribution

### Files added

- 01_setup.sql
- 03_curated.sql
- 04_analytics_prep.sql
- 05_views.sql
- data validation worksheet

### Status

Data pipeline and validation complete. Dataset ready for embedding, RAG, and GenAI analysis.

Next step: implement embeddings and Cortex LLM insights.
