# Murphy System - Quick Setup Reference Card

**One-page reference for setting up Murphy System**

---

## 🚀 Quick Start (10 Minutes)

### 1. Navigate to Directory
```bash
cd "Murphy System/murphy_integrated"
```

### 2. Create Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# OR
venv\Scripts\activate     # Windows
```

### 3. Install Dependencies
```bash
pip install --upgrade pip
pip install fastapi uvicorn pydantic aiohttp
```

### 4. Create Configuration
```bash
cat > .env << 'EOF'
MURPHY_VERSION=1.0.0
MURPHY_ENV=development
MURPHY_PORT=6666
# GROQ_API_KEY=your_key_here  # Optional
EOF
```

### 5. Create Directories
```bash
mkdir -p logs data modules sessions repositories
```

### 6. Start Murphy
```bash
python3 murphy_system_1.0_runtime.py
# OR in background:
nohup python3 murphy_system_1.0_runtime.py > startup.log 2>&1 &
```

---

## ✅ Verification Commands

### Check if Murphy is Running
```bash
curl http://localhost:6666/api/health
# Expected: {"status": "healthy", "version": "1.0.0"}
```

### View System Info
```bash
curl http://localhost:6666/api/info
```

### Access API Documentation
```
http://localhost:6666/docs
```

### List All Endpoints
```bash
curl -s http://localhost:6666/openapi.json | \
  python3 -m json.tool | grep '"paths"' -A 100
```

---

## 📊 Expected Output at Each Step

| Step | Command | Success Indicator |
|------|---------|------------------|
| 1 | `cd "Murphy System/murphy_integrated"` | Path shows murphy_integrated |
| 2 | `python3 -m venv venv` | venv/ directory created |
| 3 | `source venv/bin/activate` | (venv) in prompt |
| 4 | `pip install fastapi ...` | Successfully installed messages |
| 5 | `cat > .env` | .env file exists |
| 6 | `mkdir -p logs ...` | Directories visible with `ls` |
| 7 | `python3 murphy_system_1.0_runtime.py` | "MURPHY SYSTEM 1.0.0 - READY" |
| 8 | `curl .../api/health` | `{"status": "healthy"}` |

---

## 🛠️ Troubleshooting

| Problem | Solution |
|---------|----------|
| Port 6666 in use | Change `MURPHY_PORT` in .env |
| Python too old | Must be 3.11+ |
| Missing dependencies | `pip install fastapi uvicorn pydantic` |
| API returns errors | Normal without API key for some features |
| Can't access localhost:6666 | Check if Murphy process is running |

---

## 🔑 Optional: Add API Key

1. Get free key: https://console.groq.com
2. Edit `.env`: `GROQ_API_KEY=gsk_...`
3. Restart Murphy

---

## 📝 File Structure After Setup

```
murphy_integrated/
├── venv/                 # Virtual environment
├── logs/                 # System logs
├── data/                 # Persistent data
├── modules/              # Dynamic modules
├── sessions/             # Session data
├── repositories/         # Git repos
├── .env                  # Configuration
├── startup.log           # Startup logs
└── murphy_system_1.0_runtime.py  # Main file
```

---

## 🎯 Next Actions

After setup completes:

1. ✅ Visit http://localhost:6666/docs
2. ✅ Read [GETTING_STARTED.md](GETTING_STARTED.md)
3. ✅ Try example API calls
4. ✅ Add API key for full features
5. ✅ Explore capabilities

---

**Setup Time:** ~10 minutes  
**Required:** Python 3.11+  
**Optional:** API key (free at console.groq.com)

---

**See [VISUAL_SETUP_GUIDE.md](VISUAL_SETUP_GUIDE.md) for detailed step-by-step instructions with output examples.**
