#!/bin/bash

# Setup script for Flask pagination normalization system
# Linux/macOS

set -e

echo "=========================================="
echo "Flask Pagination Normalization Setup"
echo "=========================================="
echo ""

# Check Python version
echo "Checking Python version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "Found Python $python_version"

# Create virtual environment
echo ""
echo "Creating virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "Virtual environment created."
else
    echo "Virtual environment already exists."
fi

# Activate virtual environment
echo ""
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo ""
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo ""
echo "Installing dependencies..."
pip install -r requirements.txt

# Verify installation
echo ""
echo "Verifying installation..."
python3 -c "import flask; import flask_sqlalchemy; print('✓ Flask and Flask-SQLAlchemy installed successfully')"

echo ""
echo "=========================================="
echo "Setup complete!"
echo "=========================================="
echo ""
echo "To activate the virtual environment, run:"
echo "  source venv/bin/activate"
echo ""
echo "To run tests, use:"
echo "  ./run_test.sh"
echo "  or"
echo "  python -m pytest test_pagination_consistency.py -v"
echo ""

