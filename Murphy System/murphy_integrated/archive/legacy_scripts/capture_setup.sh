#!/bin/bash

# Script to capture setup process with screenshots
SCREENSHOT_DIR="/home/runner/work/Murphy-System/Murphy-System/docs/screenshots"

echo "=== Murphy System Setup - Screenshot Capture ==="
echo ""
echo "Step 1: Check Python Version"
python3 --version

echo ""
echo "Step 2: Navigate to Murphy Integrated"
pwd
ls -la | head -10

echo ""
echo "Step 3: Check Available Scripts"
ls -lh setup_murphy.* start_murphy_1.0.*

echo ""
echo "This is a terminal capture for documentation purposes"
