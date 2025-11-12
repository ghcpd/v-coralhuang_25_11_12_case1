@echo off
REM Test runner script for Flask pagination normalization system
REM Windows

echo ==========================================
echo Running Pagination Consistency Tests
echo ==========================================
echo.

REM Check if virtual environment exists
if exist venv (
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
) else (
    echo Virtual environment not found. Please run setup first.
    echo Creating virtual environment...
    python -m venv venv
    call venv\Scripts\activate.bat
    echo Installing dependencies...
    pip install -r requirements.txt
)

REM Check if dependencies are installed
echo.
echo Checking dependencies...
python -c "import flask; import flask_sqlalchemy" 2>nul || (
    echo Dependencies not installed. Installing...
    pip install -r requirements.txt
)

REM Run tests
echo.
echo Running test suite...
echo ----------------------------------------
python -m pytest test_pagination_consistency.py -v --tb=short

REM Run tests from input.json if available
if exist input.json (
    echo.
    echo ==========================================
    echo Running tests from input.json
    echo ==========================================
    python -c "import sys; sys.path.insert(0, '.'); from test_pagination_consistency import run_tests_from_input_json; import json; results = run_tests_from_input_json(); print(f'\nProcessed {len(results[\"test_results\"])} test cases'); print(f'Detected {len(results[\"issues_detected\"])} issues'); print(f'Applied {len(results[\"fixes_validated\"])} fixes'); print('\nTest Results:'); [print(f'  {'✓' if test['status'] == 'passed' else '✗'} {test['test_id']}: {test['description']}') for test in results['test_results']]"
)

echo.
echo ==========================================
echo Tests completed!
echo ==========================================
pause

