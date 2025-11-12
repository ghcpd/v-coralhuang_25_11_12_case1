#!/usr/bin/env bash
set -euo pipefail
python -m pip install -r requirements.txt
pytest -q --maxfail=1
