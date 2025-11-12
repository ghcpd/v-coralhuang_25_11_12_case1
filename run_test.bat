@echo off
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pytest -q tests\test_pagination_consistency.py
python generate_output.py
