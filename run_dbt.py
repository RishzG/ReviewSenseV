"""Wrapper to run dbt commands with .env loaded."""

import os
import sys
import subprocess
from dotenv import load_dotenv

project_root = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(project_root, ".env"))

dbt_args = sys.argv[1:] if len(sys.argv) > 1 else ["debug"]
result = subprocess.run(
    ["dbt"] + dbt_args,
    cwd=os.path.join(project_root, "dbt_reviewsense"),
    env=os.environ,
)
sys.exit(result.returncode)
