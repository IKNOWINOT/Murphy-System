#!/bin/bash
# Start Murphy System

# Activate virtual environment if it exists
if [ -d "murphy_venv" ]; then
    source murphy_venv/bin/activate
fi

echo "Starting Murphy System..."
python3 murphy_complete_integrated.py