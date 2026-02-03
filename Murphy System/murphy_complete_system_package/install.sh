#!/bin/bash
# Murphy System Installation Script
# Copyright © 2020 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

echo "=========================================="
echo "Murphy System Installation"
echo "Copyright © 2020 Inoni Limited Liability Company"
echo "Created by: Corey Post"
echo "=========================================="

# Check Python version
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "Python version: $python_version"

# Create virtual environment
echo ""
echo "Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo ""
echo "Upgrading pip..."
pip install --upgrade pip

# Install requirements
echo ""
echo "Installing dependencies..."
pip install -r requirements.txt

echo ""
echo "=========================================="
echo "Installation Complete!"
echo "=========================================="
echo ""
echo "To start the Murphy Runtime System:"
echo "  1. Activate virtual environment: source venv/bin/activate"
echo "  2. Run: python murphy_runtime/murphy_complete_integrated.py"
echo ""
echo "To use Phase 1-5 implementations:"
echo "  1. Activate virtual environment: source venv/bin/activate"
echo "  2. Run: python -m murphy_implementation.main"
echo ""
