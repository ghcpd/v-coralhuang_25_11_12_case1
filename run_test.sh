#!/bin/bash

# Test runner for Linux/macOS
# Runs all test suites and generates validation logs

set -e

echo "==================================================="
echo "Pagination Normalization System - Test Suite"
echo "==================================================="
echo ""

# Check if virtual environment exists, if so activate it
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
fi

# Create logs directory
mkdir -p logs

LOG_FILE="logs/test_results_$(date +%Y%m%d_%H%M%S).log"

{
    echo "Test run: $(date)"
    echo "=================================================="
    echo ""
    
    # Run unit tests
    echo "Running pagination normalization unit tests..."
    python -m pytest test_pagination_consistency.py -v --tb=short 2>&1 || python -m unittest test_pagination_consistency -v 2>&1
    
    echo ""
    echo "=================================================="
    echo "Running mock gateway demonstration..."
    echo "=================================================="
    echo ""
    python mock_gateway.py
    
    echo ""
    echo "=================================================="
    echo "Test suite complete!"
    echo "=================================================="
    
} | tee "$LOG_FILE"

echo ""
echo "Test results saved to: $LOG_FILE"
