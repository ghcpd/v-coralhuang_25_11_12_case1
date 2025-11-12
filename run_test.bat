@echo off
pip install -r requirements.txt
pytest -q --maxfail=1
