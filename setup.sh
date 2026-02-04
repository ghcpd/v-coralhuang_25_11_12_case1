#!/bin/bash

# Setup script for Linux/macOS
# Installs dependencies and sets up the environment

set -e

echo "==================================================="
echo "Pagination Normalization System - Setup Script"
echo "==================================================="

# Check Python version
echo "Checking Python installation..."
python3 --version || (echo "Python 3 is required" && exit 1)

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip setuptools wheel

# Install requirements
echo "Installing dependencies..."
pip install -r requirements.txt

echo ""
echo "==================================================="
echo "Setup complete!"
echo "==================================================="
echo ""
echo "To activate the virtual environment, run:"
echo "  source venv/bin/activate"
echo ""
echo "To run tests, run:"
echo "  ./run_test.sh"
echo ""
echo "To start the Flask app, run:"
echo "  python app.py"
echo ""
