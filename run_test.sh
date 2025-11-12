#!/usr/bin/env bash
set -euo pipefail

if [ ! -d ".venv" ]; then
  echo "Creating virtualenv and installing dependencies..."
  python -m venv .venv
  source .venv/bin/activate
  pip install -r requirements.txt
fi

source .venv/bin/activate
pytest -q tests/test_pagination_consistency.py || true
python generate_output.py
