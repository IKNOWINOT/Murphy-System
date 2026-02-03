#!/bin/bash

echo "=========================================="
echo "Murphy System - Backend Integrated Setup"
echo "=========================================="
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.8 or higher."
    exit 1
fi

echo "✓ Python 3 found: $(python3 --version)"
echo ""

# Check if pip is installed
if ! command -v pip3 &> /dev/null; then
    echo "❌ pip3 is not installed. Please install pip3."
    exit 1
fi

echo "✓ pip3 found"
echo ""

# Install dependencies
echo "Installing Python dependencies..."
pip3 install flask flask-cors flask-socketio python-socketio

echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "To start the Murphy System:"
echo ""
echo "1. Start the backend server:"
echo "   python3 murphy_backend_server.py"
echo ""
echo "2. Open the frontend in your browser:"
echo "   murphy_backend_integrated.html"
echo ""
echo "3. Click 'INITIALIZE' to start the system"
echo ""
echo "=========================================="
echo "Documentation:"
echo "  - MURPHY_INTEGRATION_GUIDE.md - Full integration guide"
echo "  - murphy_system/ - Murphy System Runtime source"
echo "=========================================="