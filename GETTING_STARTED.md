# Getting Started with Murphy System 1.0

This guide will help you get Murphy System running in less than 5 minutes.

---

## 🚀 One-Command Setup & Start (Recommended)

After cloning the repository, run **one command** from the repo root:

```bash
# Linux / macOS
bash setup_and_start.sh
```

```cmd
REM Windows
setup_and_start.bat
```

This single script:
1. ✓ Checks prerequisites (Python 3.10+, pip)
2. ✓ Creates (or reuses) a Python virtual environment
3. ✓ Installs **all** dependencies — main, optional, and extras
4. ✓ Configures `.env` (onboard LLM — no API key needed)
5. ✓ Creates runtime directories
6. ✓ Starts Murphy (backend server **or** terminal UI — your choice)

No manual activation, no missing packages, no platform-specific errors.

---

## 🌐 Remote One-Line Install

If you haven't cloned the repo yet:

```bash
curl -fsSL https://raw.githubusercontent.com/IKNOWINOT/Murphy-System/main/install.sh | bash
```

This downloads Murphy, creates a virtual environment, installs all dependencies, and sets up the `murphy` CLI. Then start automating:

```bash
murphy start          # Start in foreground
murphy start -d       # Start as background daemon
murphy status         # Check health
murphy stop           # Stop daemon
```

Install to a custom directory:
```bash
curl -fsSL https://raw.githubusercontent.com/IKNOWINOT/Murphy-System/main/install.sh | bash -s -- /opt/murphy
```

---

## What Works ✅
- ✅ 583 source modules across 54 packages
- ✅ 7,924 tests passing (345 test files)
- ✅ One-line installer and CLI tool
- ✅ Startup scripts for Linux/Mac/Windows
- ✅ Main runtime file is complete
- ✅ Universal Control Plane architecture implemented
- ✅ Integration Engine code present
- ✅ Business Automation engines coded
- ✅ 29-category code-quality audit — zero gaps remaining

---

## 📋 Manual Setup (Alternative)

### Prerequisites

1. **Python 3.11+** (required)
   ```bash
   python3 --version  # Must show 3.11 or higher
   ```

2. **Git** (to clone if needed)
   ```bash
   git --version
   ```

### Step 1: Navigate to Murphy Integrated

```bash
cd "Murphy System"
```

### Step 2: Install Dependencies

```bash
# Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements_murphy_1.0.txt
```

**Expected time:** 3-5 minutes (downloads packages)

### Step 3: Create Configuration File

Create a `.env` file in the `Murphy System` directory:

```bash
# Copy this template and save as .env

# ============= MURPHY SYSTEM CONFIGURATION =============

# Core Configuration
MURPHY_VERSION=1.0.0
MURPHY_ENV=development
MURPHY_PORT=8000

# LLM API Keys (at least one required for AI features)
# Get free API key from: https://console.groq.com
GROQ_API_KEY=your_groq_api_key_here

# Optional: OpenAI (for advanced features)
# OPENAI_API_KEY=your_openai_key_here

# Optional: Anthropic Claude
# ANTHROPIC_API_KEY=your_anthropic_key_here

# Database (Optional - SQLite used if not provided)
# DATABASE_URL=postgresql://user:pass@localhost:5432/murphy
# For development, SQLite is auto-created (no config needed)

# Cache (Optional - in-memory cache used if not provided)
# REDIS_URL=redis://localhost:6379

# Security (Auto-generated if not provided)
# JWT_SECRET=your-secret-key-here
# ENCRYPTION_KEY=your-encryption-key-here

# ============= OPTIONAL INTEGRATIONS =============

# GitHub (for repository integration features)
# GITHUB_TOKEN=your_github_token_here

# Payment Processing (for business automation)
# STRIPE_API_KEY=your_stripe_key_here
# PAYPAL_CLIENT_ID=your_paypal_id_here
# PAYPAL_CLIENT_SECRET=your_paypal_secret_here

# Email (for marketing automation)
# SENDGRID_API_KEY=your_sendgrid_key_here
# AWS_SES_ACCESS_KEY=your_aws_key_here
# AWS_SES_SECRET_KEY=your_aws_secret_here

# CRM (for sales automation)
# SALESFORCE_TOKEN=your_salesforce_token_here
# HUBSPOT_API_KEY=your_hubspot_key_here

# ============= END CONFIGURATION =============
```

**Minimum required:** Just set `GROQ_API_KEY` for basic functionality.

### Step 4: Start Murphy

```bash
# Make script executable (Linux/Mac only)
chmod +x start_murphy_1.0.sh

# Start Murphy
./start_murphy_1.0.sh  # Linux/Mac
# OR
start_murphy_1.0.bat   # Windows
```

### Step 5: Verify It's Running

Open your browser and visit:
- **API Docs:** http://localhost:8000/docs
- **Health Check:** http://localhost:8000/api/health
- **System Status:** http://localhost:8000/api/status

---

## 🔑 Getting API Keys

### Free Option: Groq (Recommended for Getting Started)

1. Visit https://console.groq.com
2. Sign up for free account
3. Create an API key
4. Add to `.env`: `GROQ_API_KEY=gsk_...`

**Why Groq?** 
- Free tier available
- Fast inference
- Good for development
- Works with Murphy out of the box

### Alternative: OpenAI

1. Visit https://platform.openai.com
2. Create account and add payment method
3. Create API key
4. Add to `.env`: `OPENAI_API_KEY=sk-...`

---

## 📋 What Can You Do Right Now?

Once Murphy is running, you can:

### 1. Check System Status

```bash
curl http://localhost:8000/api/status
```

Returns Murphy's current state and loaded components.

### 2. Execute a Simple Task

```bash
curl -X POST http://localhost:8000/api/execute \
  -H "Content-Type: application/json" \
  -d '{
    "task_description": "What is the capital of France?",
    "task_type": "query"
  }'
```

### 3. Add a GitHub Integration (Advanced)

```bash
curl -X POST http://localhost:8000/api/integrations/add \
  -H "Content-Type: application/json" \
  -d '{
    "source": "https://github.com/requests/requests",
    "category": "http-library"
  }'
```

Note: Requires `GITHUB_TOKEN` in `.env` for private repos.

---

## 🐛 Troubleshooting

### Issue: "FastAPI not installed"

**Solution:**
```bash
pip install fastapi uvicorn pydantic
```

### Issue: "No module named 'pydantic'"

**Solution:**
```bash
pip install -r requirements_murphy_1.0.txt
```

### Issue: "Port 8000 already in use"

**Solution:** Change port in `.env`:
```bash
MURPHY_PORT=7777
```

### Issue: "Python version too old"

**Current version:** Check with `python3 --version`  
**Required:** 3.11 or higher

**Solution:**
```bash
# Ubuntu/Debian
sudo apt install python3.11

# macOS
brew install python@3.11

# Windows
# Download from python.org
```

### Issue: "API key not working"

**Check:**
1. Is the `.env` file in the `Murphy System` directory?
2. Is the key in the correct format? (starts with `gsk_` for Groq)
3. Did you restart Murphy after adding the key?

---

## 📦 What's Actually Included

### Core System ✅
- **583 source modules** across 54 packages (209,701 lines of Python)
- **Control Plane:** Universal automation engine
- **Integration Engine:** GitHub ingestion with safety
- **Business Automation:** 5 engines (sales, marketing, R&D, etc.)
- **Two-Phase System:** Setup → Execute pattern
- **Code Quality:** 29-category static audit — zero gaps

### Tests ✅
- **345 test files** with **8,350 test functions**
- Gap-closure tests (rounds 3–12) verify code quality across all 583 source files
- Commissioning, integration, and unit tests for all subsystems

### Documentation 📚
- Complete API documentation (auto-generated at /docs)
- Architecture map and dependency graph
- User manual and deployment guide
- 10+ comprehensive docs

### What's NOT Included ⚠️
- **Database:** Uses SQLite by default (PostgreSQL optional)
- **Cache:** Uses in-memory cache (Redis optional)
- **API Keys:** You must provide your own
- **Training Data:** Shadow agent needs your corrections to learn
- **External Integrations:** GitHub, Stripe, etc. require your accounts

---

## 🎯 Minimal Working Setup

To get Murphy running with **minimal features**:

1. ✅ Python 3.11+
2. ✅ Dependencies installed (`pip install -r requirements_murphy_1.0.txt`)
3. ✅ One API key (Groq free tier works)
4. ✅ .env file with `GROQ_API_KEY`

**That's it!** Everything else is optional.

---

## 🔐 Security Notes

### Development vs Production

The instructions above are for **development/testing** only.

For **production deployment**, you need:
- ✅ Proper database (PostgreSQL recommended)
- ✅ Redis for caching
- ✅ Strong JWT secret
- ✅ Encryption keys
- ✅ HTTPS/SSL certificates
- ✅ Firewall rules
- ✅ Monitoring setup

See [DEPLOYMENT_GUIDE.md](Murphy%20System/DEPLOYMENT_GUIDE.md) for production setup.

---

## 📊 Expected Performance

### Development Setup (This Guide)
- **Startup time:** <10 seconds
- **API response:** <500ms
- **Memory usage:** ~200MB
- **Concurrent users:** 1-5

### Production Setup (With Database/Redis)
- **Startup time:** <5 seconds
- **API response:** <100ms p95
- **Memory usage:** ~500MB
- **Concurrent users:** 100+
- **Throughput:** 1000+ req/s

---

## 🆘 Still Having Issues?

### Quick Diagnostics

Run this to check your setup:

```bash
cd "Murphy System"
python3 -c "
import sys
print(f'Python: {sys.version}')
try:
    import fastapi
    print('✓ FastAPI installed')
except:
    print('✗ FastAPI missing - run: pip install fastapi')
try:
    import pydantic
    print('✓ Pydantic installed')
except:
    print('✗ Pydantic missing - run: pip install pydantic')
try:
    import uvicorn
    print('✓ Uvicorn installed')
except:
    print('✗ Uvicorn missing - run: pip install uvicorn')
"
```

### Common Solutions

1. **Dependencies missing:** `pip install -r requirements_murphy_1.0.txt`
2. **Old Python version:** Upgrade to 3.11+
3. **Port in use:** Change `MURPHY_PORT` in .env
4. **API key issues:** Check .env file location and format

### Get Help

- **GitHub Issues:** Report bugs or ask questions
- **Documentation:** Check other .md files in the repository
- **Examples:** See `demo_murphy.py` for code examples

---

## ✅ Success Checklist

Before moving forward, verify:

- [ ] Python 3.11+ installed
- [ ] Dependencies installed (no import errors)
- [ ] .env file created with GROQ_API_KEY
- [ ] Murphy starts without errors
- [ ] Can access http://localhost:8000/docs
- [ ] Health check returns {"status": "healthy"}

If all checked ✅, you're ready to use Murphy!

---

## 🎉 Next Steps

Once Murphy is running:

1. **Explore API Docs:** http://localhost:8000/docs
2. **Try Examples:** Run `python3 demo_murphy.py`
3. **Read Specification:** [MURPHY_SYSTEM_1.0_SPECIFICATION.md](Murphy%20System/MURPHY_SYSTEM_1.0_SPECIFICATION.md)
4. **Add Integrations:** Try adding a GitHub repo
5. **Run Automation:** Test business automation engines
6. **Launch Automation:** Follow the [Launch Automation Plan](<Murphy System/docs/LAUNCH_AUTOMATION_PLAN.md>) to automate Murphy's own launch
7. **Operations & Testing:** Use the [Operations, Testing & Iteration Plan](<Murphy System/docs/OPERATIONS_TESTING_PLAN.md>) for systematic verification
8. **Review Gap Analysis:** See [Gap Analysis](<Murphy System/docs/GAP_ANALYSIS.md>) for what works vs what needs fixing
9. **Follow Remediation Plan:** See [Remediation Plan](<Murphy System/docs/REMEDIATION_PLAN.md>) for concrete next steps

---

## 💡 Pro Tips

1. **Start Simple:** Get basic task execution working first
2. **Add API Keys Gradually:** Start with just Groq, add others as needed
3. **Monitor Logs:** Check console output for warnings
4. **Use Virtual Environment:** Keeps dependencies isolated
5. **Read Error Messages:** Murphy provides helpful error messages

---

## 📝 Summary

**Question:** "Is it lacking anything to try and use now?"

**Answer:** The code is complete, but you need:

1. ✅ **Install dependencies** (5 minutes): `pip install -r requirements_murphy_1.0.txt`
2. ✅ **Create .env file** (2 minutes): Add `GROQ_API_KEY` 
3. ✅ **Start Murphy** (1 minute): `./start_murphy_1.0.sh`

**Total time to first run:** ~10 minutes

Everything else (database, Redis, additional integrations) is optional for getting started.

---

**Created:** February 9, 2026  
**Last Updated:** February 26, 2026  
**Status:** Ready to use with setup steps above
