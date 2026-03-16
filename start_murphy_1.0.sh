#!/bin/bash

# Murphy System 1.0 - Startup Script
# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1 (Business Source License)

set -e

echo ""
# Use pyfiglet banner if available, otherwise fall back to simple banner
python3 -c "
try:
    from src.cli_art import render_banner
    print(render_banner(color=False))
except Exception:
    print('  ☠  Murphy System v1.0  ☠')
" 2>/dev/null || {
echo "  ☠  ════════════════════════════════════════════════════  ☠"
echo "       💀  M U R P H Y   S Y S T E M   v 1 . 0  💀      "
echo "  ☠  ════════════════════════════════════════════════════  ☠"
}
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check Python version
echo -e "${BLUE}Checking Python version...${NC}"
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
REQUIRED_VERSION="3.10"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then 
    echo -e "${RED}Error: Python $REQUIRED_VERSION or higher is required${NC}"
    echo -e "${RED}Current version: $PYTHON_VERSION${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Python $PYTHON_VERSION${NC}"
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Virtual environment not found. Creating...${NC}"
    python3 -m venv venv
    echo -e "${GREEN}✓ Virtual environment created${NC}"
fi

# Activate virtual environment
echo -e "${BLUE}Activating virtual environment...${NC}"
source venv/bin/activate
echo -e "${GREEN}✓ Virtual environment activated${NC}"
echo ""

# Install/update dependencies
echo -e "${BLUE}Installing dependencies...${NC}"
pip install --upgrade pip
pip install -r requirements_murphy_1.0.txt
echo -e "${GREEN}✓ Dependencies installed${NC}"
echo ""

# Check environment variables
echo -e "${BLUE}Checking environment variables...${NC}"

if [ -f ".env" ]; then
    echo -e "${GREEN}✓ .env file found${NC}"
    export $(cat .env | grep -v '^#' | xargs)
else
    echo -e "${YELLOW}⚠ .env file not found. Using defaults.${NC}"
fi

# Set default port if not set
export MURPHY_PORT=${PORT:-${MURPHY_PORT:-8000}}
echo -e "${GREEN}✓ Port: $MURPHY_PORT${NC}"
echo ""

# Create necessary directories
echo -e "${BLUE}Creating directories...${NC}"
mkdir -p logs
mkdir -p data
mkdir -p modules
mkdir -p sessions
mkdir -p repositories
echo -e "${GREEN}✓ Directories created${NC}"
echo ""

# Start Murphy System
echo ""
python3 -c "
import os
port = os.getenv('PORT', os.getenv('MURPHY_PORT', '8000'))
try:
    from src.cli_art import render_panel
    print(render_panel('STARTUP', [
        'Starting Murphy System v1.0',
        f'  💀 Port:        {port}',
        f'  💀 API Docs:    http://localhost:{port}/docs',
        f'  💀 Health:      http://localhost:{port}/api/health',
        f'  💀 Status:      http://localhost:{port}/api/status',
        f'  💀 Onboarding:  http://localhost:{port}/api/onboarding/wizard/questions',
    ], color=False))
except Exception:
    print('  ☠  Starting Murphy System v1.0  ☠')
" 2>/dev/null || {
echo "  ☠  ════════════════════════════════════════════════════  ☠"
echo -e " 💀 ${GREEN}            STARTING MURPHY SYSTEM v1.0             ${NC} 💀"
echo "  ☠  ════════════════════════════════════════════════════  ☠"
echo ""
echo -e "  💀 ${BLUE}Port:        $MURPHY_PORT${NC}"
echo -e "  💀 ${BLUE}API Docs:    http://localhost:$MURPHY_PORT/docs${NC}"
echo -e "  💀 ${BLUE}Health:      http://localhost:$MURPHY_PORT/api/health${NC}"
echo -e "  💀 ${BLUE}Status:      http://localhost:$MURPHY_PORT/api/status${NC}"
echo -e "  💀 ${BLUE}Onboarding:  http://localhost:$MURPHY_PORT/api/onboarding/wizard/questions${NC}"
}
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop${NC}"
echo ""

# Run Murphy
python3 murphy_system_1.0_runtime.py