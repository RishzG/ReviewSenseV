"""Deploy semantic model YAML to Snowflake as a Semantic View."""

import os
import tempfile
import snowflake.connector
from dotenv import load_dotenv

load_dotenv()

# Read the YAML file
yaml_path = os.path.join(
    os.path.dirname(__file__),
    "dbt_reviewsense", "models", "gold", "semantic", "reviewsense_analytics.yaml"
)
with open(yaml_path, "r") as f:
    yaml_content = f.read()

conn = snowflake.connector.connect(
    account=os.getenv("SNOWFLAKE_ACCOUNT"),
    user=os.getenv("SNOWFLAKE_USER"),
    private_key_file=os.getenv("SNOWFLAKE_PRIVATE_KEY_PATH"),
    role=os.getenv("SNOWFLAKE_ROLE"),
    warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
    database=os.getenv("SNOWFLAKE_DATABASE"),
)
cur = conn.cursor()

# Try semantic view first
print("Deploying semantic view REVIEWSENSE_ANALYTICS...")
try:
    cur.execute(
        "CALL SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML(%s, %s)",
        ('REVIEWSENSE_DB.GOLD', yaml_content)
    )
    result = cur.fetchone()
    print(f"Result: {result[0]}")
except Exception as e:
    print(f"Semantic view failed: {e}")
    print("\nFalling back to stage-based deployment...")

    # Clean up old files and recreate stage
    cur.execute("CREATE STAGE IF NOT EXISTS REVIEWSENSE_DB.GOLD.SEMANTIC_STAGE")
    cur.execute("REMOVE @REVIEWSENSE_DB.GOLD.SEMANTIC_STAGE")

    # Write yaml with proper filename
    tmp_dir = tempfile.mkdtemp()
    tmp_path = os.path.join(tmp_dir, "reviewsense_analytics.yaml")
    with open(tmp_path, 'w') as f:
        f.write(yaml_content)

    cur.execute(
        f"PUT file://{tmp_path} @REVIEWSENSE_DB.GOLD.SEMANTIC_STAGE "
        f"AUTO_COMPRESS=FALSE OVERWRITE=TRUE"
    )
    os.unlink(tmp_path)
    os.rmdir(tmp_dir)

    # Verify upload
    cur.execute("LIST @REVIEWSENSE_DB.GOLD.SEMANTIC_STAGE")
    for row in cur:
        print(f"  Uploaded: {row[0]}")

    print("\nStage-based deployment complete.")
    print("Reference in API calls:")
    print('  "@REVIEWSENSE_DB.GOLD.SEMANTIC_STAGE/reviewsense_analytics.yaml"')

conn.close()
print("\nDone.")
