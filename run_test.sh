#!/bin/bash

# Test runner script for Flask pagination normalization system
# Linux/macOS

set -e

echo "=========================================="
echo "Running Pagination Consistency Tests"
echo "=========================================="
echo ""

# Check if virtual environment exists
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
else
    echo "Virtual environment not found. Running setup..."
    ./setup.sh
    source venv/bin/activate
fi

# Check if dependencies are installed
echo ""
echo "Checking dependencies..."
python3 -c "import flask; import flask_sqlalchemy" 2>/dev/null || {
    echo "Dependencies not installed. Installing..."
    pip install -r requirements.txt
}

# Run tests
echo ""
echo "Running test suite..."
echo "----------------------------------------"
python3 -m pytest test_pagination_consistency.py -v --tb=short

# Run tests from input.json if available
if [ -f "input.json" ]; then
    echo ""
    echo "=========================================="
    echo "Running tests from input.json"
    echo "=========================================="
    python3 -c "
import sys
sys.path.insert(0, '.')
from test_pagination_consistency import run_tests_from_input_json
import json

try:
    results = run_tests_from_input_json()
    print(f\"\\nProcessed {len(results['test_results'])} test cases\")
    print(f\"Detected {len(results['issues_detected'])} issues\")
    print(f\"Applied {len(results['fixes_validated'])} fixes\")
    print(\"\\nTest Results:\")
    for test in results['test_results']:
        status = '✓' if test['status'] == 'passed' else '✗'
        print(f\"  {status} {test['test_id']}: {test['description']}\")
except Exception as e:
    print(f\"Error running JSON tests: {e}\")
    sys.exit(1)
"
fi

echo ""
echo "=========================================="
echo "Tests completed!"
echo "=========================================="

