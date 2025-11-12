@echo off
python -m venv venv
call venv\Scripts\activate
pip install --upgrade pip
pip install -r project\requirements.txt
pytest project\test_pagination_consistency.py -q --maxfail=1
