#!/usr/bin/env bash
set -e
python3 -m venv venv
. venv/bin/activate
pip install -r project/requirements.txt
pytest -q

