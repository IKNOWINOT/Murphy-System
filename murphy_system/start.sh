#!/bin/bash
# Murphy System 1.0 - Startup Script
# Quick and easy way to start Murphy

echo "================================================================================"
echo "  MURPHY SYSTEM 1.0 - Universal AI Automation System"
echo "================================================================================"
echo ""

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python 3 is not installed"
    echo "   Please install Python 3.10 or higher"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
echo "✅ Python $PYTHON_VERSION detected"

# Check if in correct directory
if [ ! -f "murphy_system_1.0_runtime.py" ]; then
    echo "❌ Error: murphy_system_1.0_runtime.py not found"
    echo "   Please run this script from the Murphy System directory"
    exit 1
fi

# Create .env if it doesn't exist
if [ ! -f ".env" ]; then
    echo "📝 Creating default .env file..."
    cat > .env << 'EOF'
# Murphy System 1.0 - Configuration
MURPHY_VERSION=1.0.0
MURPHY_ENV=development
MURPHY_PORT=8000

# API Keys — set your keys using:  set key groq gsk_yourKeyHere  (in the Murphy terminal)
# Or uncomment and fill in below:
# GROQ_API_KEY=
# OPENAI_API_KEY=

# Optional: Database (not required for basic operation)
# DATABASE_URL=postgresql://user:pass@localhost:5432/murphy
# REDIS_URL=redis://localhost:6379
EOF
    echo "✅ Created .env file (use 'set key groq <key>' in Murphy terminal to add API keys)"
fi

# Install dependencies if needed
echo ""
echo "📦 Checking dependencies..."
python3 -c "import fastapi, uvicorn" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "⚠️  Some dependencies missing. Installing from requirements_murphy_1.0.txt..."
    pip install --quiet -r requirements_murphy_1.0.txt 2>&1 | grep -v "Requirement already satisfied" || true
    echo "✅ Dependencies installed"
else
    echo "✅ Dependencies OK"
fi

# Start Murphy
echo ""
echo "🚀 Starting Murphy System 1.0..."
echo ""
echo "📊 API Documentation will be at: http://localhost:8000/docs"
echo "🔍 Health Check: http://localhost:8000/api/health"
echo "📈 System Status: http://localhost:8000/api/status"
echo ""
echo "Press CTRL+C to stop Murphy"
echo ""
echo "================================================================================"
echo ""

# Run Murphy
python3 murphy_system_1.0_runtime.py
