#!/bin/bash

# Murphy System - Installation Script
# This script installs Murphy on your local machine

set -e  # Exit on any error

echo "============================================================"
echo "Murphy System - Installation Script"
echo "============================================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if Python 3 is installed
echo "Checking Python installation..."
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 is not installed${NC}"
    echo "Please install Python 3.8 or higher from https://www.python.org/"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
echo -e "${GREEN}✅ Python $PYTHON_VERSION found${NC}"

# Check Python version (need 3.8+)
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d'.' -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d'.' -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 8 ]); then
    echo -e "${RED}❌ Python 3.8+ required, you have $PYTHON_VERSION${NC}"
    exit 1
fi

# Check if pip is installed
echo ""
echo "Checking pip installation..."
if ! command -v pip3 &> /dev/null; then
    echo -e "${RED}❌ pip3 is not installed${NC}"
    echo "Installing pip..."
    python3 -m ensurepip --upgrade
fi
echo -e "${GREEN}✅ pip3 found${NC}"

# Create virtual environment (optional but recommended)
echo ""
read -p "Create virtual environment? (recommended) [Y/n]: " CREATE_VENV
CREATE_VENV=${CREATE_VENV:-Y}

if [[ $CREATE_VENV =~ ^[Yy]$ ]]; then
    echo "Creating virtual environment..."
    python3 -m venv murphy_venv
    source murphy_venv/bin/activate
    echo -e "${GREEN}✅ Virtual environment created and activated${NC}"
fi

# Install dependencies
echo ""
echo "Installing Python dependencies..."
pip3 install --upgrade pip

# Core dependencies
echo "Installing core packages..."
pip3 install flask==3.0.0
pip3 install flask-cors==4.0.0
pip3 install flask-socketio==5.3.5
pip3 install python-socketio==5.10.0
pip3 install groq==0.4.1
pip3 install requests==2.31.0
pip3 install psutil==5.9.6
pip3 install "pydantic>=2.5.0"

# Asyncio fix for nested event loops
echo "Installing asyncio fix..."
pip3 install nest-asyncio==1.5.8

# Optional but useful
echo "Installing optional packages..."
pip3 install python-dotenv==1.0.0

echo -e "${GREEN}✅ All dependencies installed${NC}"

# Check for API keys
echo ""
echo "============================================================"
echo "API Keys Setup"
echo "============================================================"

if [ ! -f "groq_keys.txt" ]; then
    echo -e "${YELLOW}⚠️  groq_keys.txt not found${NC}"
    echo "Creating groq_keys.txt..."
    cat > groq_keys.txt << 'EOF'
# Add your Groq API keys here (one per line)
# Get free keys at: https://console.groq.com/keys
# Example:
# REDACTED_GROQ_KEY_PLACEHOLDER
EOF
    echo -e "${YELLOW}⚠️  Please add your Groq API keys to groq_keys.txt${NC}"
else
    KEY_COUNT=$(grep -v '^#' groq_keys.txt | grep -v '^$' | wc -l)
    echo -e "${GREEN}✅ Found $KEY_COUNT Groq API key(s)${NC}"
fi

if [ ! -f "aristotle_key.txt" ]; then
    echo "Creating aristotle_key.txt (optional)..."
    echo "# Add your Aristotle API key here (optional)" > aristotle_key.txt
fi

# Create .env file
echo ""
echo "Creating .env file..."
if [ ! -f ".env" ]; then
    cat > .env << 'EOF'
# Murphy System Configuration
FLASK_ENV=development
FLASK_DEBUG=False
SECRET_KEY=your-secret-key-change-this
DATABASE_URL=sqlite:///murphy.db
PORT=3002
HOST=0.0.0.0
EOF
    echo -e "${GREEN}✅ .env file created${NC}"
else
    echo -e "${YELLOW}⚠️  .env file already exists, skipping${NC}"
fi

# Create startup script
echo ""
echo "Creating startup script..."
cat > start_murphy.sh << 'EOF'
#!/bin/bash
# Start Murphy System

# Activate virtual environment if it exists
if [ -d "murphy_venv" ]; then
    source murphy_venv/bin/activate
fi

echo "Starting Murphy System..."
python3 murphy_complete_integrated.py
EOF

chmod +x start_murphy.sh
echo -e "${GREEN}✅ Startup script created (start_murphy.sh)${NC}"

# Create stop script
cat > stop_murphy.sh << 'EOF'
#!/bin/bash
# Stop Murphy System
echo "Stopping Murphy System..."
pkill -f murphy_complete_integrated.py
echo "Murphy stopped."
EOF

chmod +x stop_murphy.sh
echo -e "${GREEN}✅ Stop script created (stop_murphy.sh)${NC}"

# Final instructions
echo ""
echo "============================================================"
echo "Installation Complete!"
echo "============================================================"
echo ""
echo "Next steps:"
echo ""
echo "1. Add your Groq API keys to groq_keys.txt"
echo "   Get free keys at: https://console.groq.com/keys"
echo ""
echo "2. Start Murphy:"
echo "   ./start_murphy.sh"
echo ""
echo "3. Access Murphy:"
echo "   Dashboard: http://localhost:3002"
echo "   API: http://localhost:3002/api/status"
echo ""
echo "4. Stop Murphy:"
echo "   ./stop_murphy.sh"
echo ""
echo "5. Run tests:"
echo "   python3 real_test.py"
echo ""
echo "============================================================"
echo ""

if [[ $CREATE_VENV =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Note: Virtual environment is activated.${NC}"
    echo "To deactivate: deactivate"
    echo "To reactivate: source murphy_venv/bin/activate"
    echo ""
fi

echo -e "${GREEN}Happy automating! 🚀${NC}"