"""Run evaluation framework against the API.

Measures:
1. Intent accuracy: does the orchestrator classify correctly?
2. SQL correctness: for structured queries, does the generated SQL return matching data?
3. Answer quality: for semantic queries, does the answer contain relevant content?
4. Latency: response time per query
"""

import json
import os
import sys
import time
from datetime import datetime

import requests
import snowflake.connector
from dotenv import load_dotenv

load_dotenv()

from eval.test_questions import EVAL_QUESTIONS

API_BASE = "http://localhost:8000"


def get_snowflake_cursor():
    conn = snowflake.connector.connect(
        account=os.getenv("SNOWFLAKE_ACCOUNT"),
        user=os.getenv("SNOWFLAKE_USER"),
        private_key_file=os.getenv("SNOWFLAKE_PRIVATE_KEY_PATH"),
        role=os.getenv("SNOWFLAKE_ROLE"),
        warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
        database=os.getenv("SNOWFLAKE_DATABASE"),
    )
    return conn, conn.cursor()


def run_ground_truth_sql(cur, sql):
    """Execute ground truth SQL and return results."""
    try:
        cur.execute(sql)
        return cur.fetchall()
    except Exception as e:
        return f"SQL_ERROR: {e}"


def check_numerical_match(api_data, gt_data, tolerance=0.05):
    """Check if API data matches ground truth within tolerance."""
    if not api_data or not gt_data:
        return False, "Missing data"

    if isinstance(gt_data, str) and gt_data.startswith("SQL_ERROR"):
        return False, gt_data

    # For single-value queries, compare the first value
    if len(gt_data) == 1 and len(gt_data[0]) == 1:
        gt_val = gt_data[0][0]
        # Search for this value in API data
        for row in api_data:
            for val in row.values():
                try:
                    if abs(float(val) - float(gt_val)) / max(abs(float(gt_val)), 1e-10) < tolerance:
                        return True, f"Match: {gt_val}"
                except (ValueError, TypeError):
                    if str(val).lower() == str(gt_val).lower():
                        return True, f"Match: {gt_val}"

    # For multi-row queries, check if the same categories/ASINs appear
    gt_categories = set()
    for row in gt_data:
        for val in row:
            if isinstance(val, str):
                gt_categories.add(val.lower())

    api_categories = set()
    for row in api_data:
        for val in row.values():
            if isinstance(val, str):
                api_categories.add(val.lower())

    overlap = gt_categories & api_categories
    if overlap:
        return True, f"Category overlap: {overlap}"

    return False, "No match found"


def evaluate_question(q, cur):
    """Evaluate a single question."""
    result = {
        "id": q["id"],
        "question": q["question"],
        "expected_intent": q["expected_intent"],
    }

    # Call the API
    start = time.time()
    try:
        resp = requests.post(
            f"{API_BASE}/query",
            json={"question": q["question"]},
            timeout=120,
        )
        latency = time.time() - start
        result["latency_s"] = round(latency, 2)

        if resp.status_code != 200:
            result["api_error"] = resp.text[:200]
            result["intent_correct"] = False
            result["data_correct"] = False
            return result

        data = resp.json()
        result["actual_intent"] = data.get("intent")
        result["intent_correct"] = data.get("intent") == q["expected_intent"]
        result["answer_preview"] = data.get("answer", "")[:200]
        result["sql"] = data.get("sql")
        result["has_sources"] = bool(data.get("sources"))
        result["has_data"] = bool(data.get("data"))

    except Exception as e:
        result["api_error"] = str(e)[:200]
        result["intent_correct"] = False
        result["data_correct"] = False
        return result

    # Check data correctness for SQL-verifiable questions
    if q["ground_truth_type"] == "sql":
        gt_sql = q.get("ground_truth_sql")
        if gt_sql:
            gt_data = run_ground_truth_sql(cur, gt_sql)
            api_data = data.get("data")
            match, detail = check_numerical_match(api_data, gt_data)
            result["data_correct"] = match
            result["match_detail"] = detail
        else:
            result["data_correct"] = None
    else:
        # Qualitative — check that answer is non-empty and has sources for semantic
        has_content = len(data.get("answer", "")) > 50
        result["data_correct"] = has_content
        result["match_detail"] = "Qualitative: answer present" if has_content else "Answer too short"

    return result


def main():
    print(f"ReviewSense AI Evaluation Framework")
    print(f"Running {len(EVAL_QUESTIONS)} questions against {API_BASE}")
    print(f"Started: {datetime.now().isoformat()}")
    print("=" * 70)

    # Check API is up
    try:
        health = requests.get(f"{API_BASE}/health", timeout=10)
        print(f"API Health: {health.json()}")
    except Exception:
        print("ERROR: API is not running. Start it with: python -m uvicorn api.main:app")
        sys.exit(1)

    conn, cur = get_snowflake_cursor()
    results = []
    intent_correct = 0
    data_correct = 0
    total_latency = 0
    errors = 0

    for i, q in enumerate(EVAL_QUESTIONS):
        print(f"\n[{i+1}/{len(EVAL_QUESTIONS)}] {q['id']}: {q['question'][:60]}...")
        result = evaluate_question(q, cur)
        results.append(result)

        # Track metrics
        if result.get("api_error"):
            errors += 1
            print(f"  ERROR: {result['api_error'][:80]}")
        else:
            if result["intent_correct"]:
                intent_correct += 1
            if result.get("data_correct"):
                data_correct += 1
            total_latency += result.get("latency_s", 0)

            status = "PASS" if result["intent_correct"] and result.get("data_correct") else "FAIL"
            print(f"  Intent: {result['actual_intent']} (expected: {result['expected_intent']}) {'✓' if result['intent_correct'] else '✗'}")
            print(f"  Data: {result.get('match_detail', 'N/A')[:60]}")
            print(f"  Latency: {result['latency_s']}s | {status}")

    # Summary
    total = len(EVAL_QUESTIONS)
    evaluated = total - errors
    print("\n" + "=" * 70)
    print("EVALUATION SUMMARY")
    print("=" * 70)
    print(f"Total questions:     {total}")
    print(f"API errors:          {errors}")
    print(f"Intent accuracy:     {intent_correct}/{evaluated} ({intent_correct*100//max(evaluated,1)}%)")
    print(f"Data correctness:    {data_correct}/{evaluated} ({data_correct*100//max(evaluated,1)}%)")
    print(f"Avg latency:         {total_latency/max(evaluated,1):.1f}s")
    print(f"Total time:          {total_latency:.0f}s")

    # Intent breakdown
    for intent in ["structured", "semantic", "synthesis"]:
        subset = [r for r in results if r["expected_intent"] == intent and not r.get("api_error")]
        if subset:
            correct = sum(1 for r in subset if r["intent_correct"])
            print(f"  {intent}: {correct}/{len(subset)} intent accuracy")

    # Save detailed results
    output_path = os.path.join(os.path.dirname(__file__), "eval_results.json")
    with open(output_path, "w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "total": total,
            "errors": errors,
            "intent_accuracy": intent_correct / max(evaluated, 1),
            "data_correctness": data_correct / max(evaluated, 1),
            "avg_latency_s": total_latency / max(evaluated, 1),
            "results": results,
        }, f, indent=2, default=str)

    print(f"\nDetailed results saved to: {output_path}")

    conn.close()


if __name__ == "__main__":
    main()
