#!/bin/bash

# Murphy System 1.0 - Quick Setup Script
# This script sets up Murphy System for first-time use
# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1 (Business Source License)

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}"
echo "================================================================================"
echo "                   MURPHY SYSTEM 1.0 - QUICK SETUP                           "
echo "================================================================================"
echo -e "${NC}"
echo ""

# Step 1: Check Python version
echo -e "${BLUE}Step 1/5: Checking Python version...${NC}"
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
REQUIRED_VERSION="3.11"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then 
    echo -e "${RED}✗ Error: Python $REQUIRED_VERSION or higher is required${NC}"
    echo -e "${RED}  Current version: $PYTHON_VERSION${NC}"
    echo ""
    echo "Install Python 3.11+ from https://www.python.org/downloads/"
    exit 1
fi

echo -e "${GREEN}✓ Python $PYTHON_VERSION detected${NC}"
echo ""

# Step 2: Create virtual environment
echo -e "${BLUE}Step 2/5: Setting up virtual environment...${NC}"
if [ -d "venv" ]; then
    echo -e "${YELLOW}⚠ Virtual environment already exists${NC}"
    read -p "Do you want to recreate it? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf venv
        python3 -m venv venv
        echo -e "${GREEN}✓ Virtual environment recreated${NC}"
    else
        echo -e "${YELLOW}  Using existing virtual environment${NC}"
    fi
else
    python3 -m venv venv
    echo -e "${GREEN}✓ Virtual environment created${NC}"
fi
echo ""

# Step 3: Activate and install dependencies
echo -e "${BLUE}Step 3/5: Installing dependencies...${NC}"
source venv/bin/activate

echo "  Upgrading pip..."
pip install --upgrade pip -q

echo "  Installing Murphy dependencies (this may take 2-3 minutes)..."
pip install -r requirements_murphy_1.0.txt -q

echo -e "${GREEN}✓ Dependencies installed${NC}"
echo ""

# Step 4: Create .env file
echo -e "${BLUE}Step 4/5: Creating configuration file...${NC}"

if [ -f ".env" ]; then
    echo -e "${YELLOW}⚠ .env file already exists${NC}"
    read -p "Do you want to overwrite it? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}  Keeping existing .env file${NC}"
        SKIP_ENV=true
    fi
fi

if [ ! "$SKIP_ENV" = true ]; then
    echo ""
    echo -e "${CYAN}To use Murphy, you need at least one LLM API key.${NC}"
    echo -e "${CYAN}Recommended: DeepInfra (primary, ~80% of calls) or Together AI (overflow)${NC}"
    echo ""
    echo "Get a DeepInfra API key at: https://deepinfra.com/"
    echo "Get a Together AI API key at: https://api.together.xyz/"
    echo ""
    read -p "Enter your DeepInfra API key (or press Enter to skip): " DEEPINFRA_KEY
    if [ -z "$DEEPINFRA_KEY" ]; then
        read -p "Enter your Together AI API key (or press Enter to skip): " TOGETHER_KEY
    fi
    echo ""
    
    # Create .env file
    cat > .env << EOF
# Murphy System 1.0 - Configuration
# Auto-generated on $(date)

# Core Configuration
MURPHY_VERSION=1.0.0
MURPHY_ENV=development
MURPHY_PORT=8000

# LLM API Keys
EOF
    
    if [ ! -z "$DEEPINFRA_KEY" ]; then
        echo "DEEPINFRA_API_KEY=$DEEPINFRA_KEY" >> .env
        echo -e "${GREEN}✓ Configuration file created with DeepInfra API key${NC}"
    elif [ ! -z "$TOGETHER_KEY" ]; then
        echo "TOGETHER_API_KEY=$TOGETHER_KEY" >> .env
        echo -e "${GREEN}✓ Configuration file created with Together AI API key${NC}"
    else
        echo "# DEEPINFRA_API_KEY=your_key_here" >> .env
        echo "# TOGETHER_API_KEY=your_key_here" >> .env
        echo -e "${YELLOW}⚠ Configuration file created without API key${NC}"
        echo -e "${YELLOW}  You'll need to add DEEPINFRA_API_KEY to .env before starting Murphy${NC}"
    fi
    
    cat >> .env << EOF

# Database (SQLite auto-created if not specified)
# DATABASE_URL=postgresql://user:pass@localhost:5432/murphy

# Cache (in-memory cache if not specified)
# REDIS_URL=redis://localhost:6379/0

# Security (auto-generated if not provided)
# MURPHY_JWT_SECRET=
# ENCRYPTION_KEY=

# See .env.example for more configuration options
EOF
fi

echo ""

# Step 5: Create necessary directories
echo -e "${BLUE}Step 5/5: Creating directories...${NC}"
mkdir -p logs
mkdir -p data
mkdir -p modules
mkdir -p sessions
mkdir -p repositories
echo -e "${GREEN}✓ Directories created${NC}"
echo ""

# Final instructions
echo -e "${CYAN}"
echo "================================================================================"
echo "                          SETUP COMPLETE!                                    "
echo "================================================================================"
echo -e "${NC}"
echo ""

if [ -z "$DEEPINFRA_KEY" ] && [ -z "$TOGETHER_KEY" ]; then
    echo -e "${YELLOW}⚠ IMPORTANT: You need to add an API key to .env before starting Murphy${NC}"
    echo ""
    echo "1. Get a DeepInfra API key: https://deepinfra.com/"
    echo "   Edit .env and add: DEEPINFRA_API_KEY=your_key_here"
    echo "   — or —"
    echo "2. Get a Together AI API key: https://api.together.xyz/"
    echo "   Edit .env and add: TOGETHER_API_KEY=your_key_here"
    echo "3. Save the file"
    echo ""
    echo -e "${CYAN}Then start Murphy with:${NC}"
else
    echo -e "${GREEN}✓ Murphy is ready to start!${NC}"
    echo ""
    echo -e "${CYAN}Start Murphy with:${NC}"
fi

echo ""
echo "  ./start_murphy_1.0.sh"
echo ""
echo -e "${CYAN}Once running, access:${NC}"
echo "  • API Documentation: http://localhost:8000/docs"
echo "  • Health Check:      http://localhost:8000/api/health"
echo "  • System Status:     http://localhost:8000/api/status"
echo ""
echo -e "${CYAN}For more information:${NC}"
echo "  • See GETTING_STARTED.md for detailed instructions"
echo "  • See .env.example for all configuration options"
echo "  • Run demo: make demo   (or)   python3 scripts/quick_demo.py"
echo ""
echo -e "${GREEN}Happy automating! 🚀${NC}"
echo ""
