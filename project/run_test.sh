#!/usr/bin/env bash
set -e
python3 -m venv venv
. venv/bin/activate
pip install --upgrade pip
pip install -r project/requirements.txt
pytest project/test_pagination_consistency.py -q --maxfail=1

# Generate output.json as a compact summary
python - <<'PY'
import json
summary = {
  "status": "tests_run",
  "tests": "project/test_pagination_consistency.py",
}
print(json.dumps(summary, indent=2))
PY

