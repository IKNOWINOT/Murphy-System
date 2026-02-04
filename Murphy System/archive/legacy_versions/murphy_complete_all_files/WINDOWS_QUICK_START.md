# Murphy System - Windows Quick Start Guide

## What You're Getting

**Murphy System v1.0** - Complete AI Business Automation Platform
- **Size:** 0.13 MB (compressed)
- **Files:** 42 files
- **License:** Apache 2.0 (Free & Open Source)
- **Platform:** Windows 10/11

## Installation (5 Minutes)

### Step 1: Extract the ZIP
1. Download `murphy_system_v1.0_20260129.zip`
2. Right-click → Extract All
3. Choose a folder (e.g., `C:\Murphy`)

### Step 2: Install Python (if needed)
1. Download Python 3.11 from: https://www.python.org/downloads/
2. **IMPORTANT:** Check "Add Python to PATH" during installation
3. Verify: Open Command Prompt and type `python --version`

### Step 3: Run the Installer
1. Open Command Prompt in the Murphy folder
2. Run: `install.bat`
3. Wait 2-3 minutes for dependencies to install

### Step 4: Add Your API Keys
1. Open `groq_keys.txt` in Notepad
2. Get free API keys from: https://console.groq.com/keys
3. Add your keys (one per line)
4. Save the file

### Step 5: Start Murphy
1. Double-click `start_murphy.bat`
2. Wait for "Running on http://127.0.0.1:3002"
3. Open browser: http://localhost:3002

## Testing (2 Minutes)

### Quick Test
1. Open Command Prompt in Murphy folder
2. Run: `python real_test.py`
3. Expected: 5/5 tests passing

### Browser Test
1. Open: http://localhost:3002
2. You should see the Murphy dashboard
3. Click "Initialize System"

## Running the Demo (10 Minutes)

### Self-Selling Demo
1. Make sure Murphy is running (`start_murphy.bat`)
2. Open new Command Prompt
3. Run: `python demo_murphy_sells_itself.py`
4. Watch Murphy create and sell its own business!

**Demo shows:**
- Product creation (2 min)
- Payment setup (instant)
- Marketing generation (1 min)
- Autonomous sales (5 min)
- First sale closed (2 min)

## What's Included

### Core Systems (21 Total):
1. LLM (AI text generation)
2. Librarian (knowledge management)
3. Monitoring (health tracking)
4. Artifacts (document creation)
5. Shadow Agents (background tasks)
6. Cooperative Swarm (multi-agent)
7. Commands (61 registered)
8. Learning Engine (optimization)
9. Workflow Orchestrator (automation)
10. Database (data storage)
11. Business Automation (products, sales)
12. Production Readiness (deployment)
13. Payment Verification (sales tracking)
14. Artifact Download (delivery)
15. Scheduled Automation (cron-like)
16. Librarian Integration (AI commands)
17. Agent Communication (messaging)
18. Generative Gates (decisions)
19. Enhanced Gates (multi-type)
20. Dynamic Projection Gates (CEO agent)
21. Autonomous Business Development (lead gen)

### API Endpoints (82+):
- System management
- LLM generation
- Business automation
- Payment processing
- Workflow orchestration
- And much more...

## Common Issues

### "Python not found"
- Reinstall Python with "Add to PATH" checked
- Or add manually: System → Environment Variables → Path

### "pip not found"
- Run: `python -m ensurepip --upgrade`

### Port 3002 already in use
- Run: `stop_murphy.bat`
- Or: `taskkill /F /IM python.exe`

### API key errors
- Check `groq_keys.txt` has valid keys
- Get free keys: https://console.groq.com/keys
- Each key on new line

### Import errors
- Run: `pip install -r requirements.txt`
- Make sure all files extracted

## System Requirements

**Minimum:**
- Windows 10/11
- 2 CPU cores
- 2 GB RAM
- 5 GB disk space
- Python 3.8+
- Internet connection

**Actual Usage:**
- Murphy: ~3 MB RAM (very lightweight!)
- CPU: <1% when idle
- Disk: 0.13 MB installed

## Next Steps

### After Installation:
1. ✅ Run tests: `python real_test.py`
2. ✅ Run demo: `python demo_murphy_sells_itself.py`
3. ✅ Explore dashboard: http://localhost:3002
4. ✅ Read docs: `README_INSTALL.md`

### Start Building:
1. Create your first automation
2. Generate content with LLM
3. Set up business workflows
4. Launch autonomous campaigns

### Get Help:
1. Check logs: `murphy_server.log`
2. Test system: `python real_test.py`
3. View status: http://localhost:3002/api/status

## File Structure

```
murphy_system/
├── install.bat              ← Run this first
├── start_murphy.bat         ← Start Murphy
├── stop_murphy.bat          ← Stop Murphy
├── demo_murphy_sells_itself.py  ← Run demo
├── real_test.py             ← Test suite
├── requirements.txt         ← Dependencies
├── groq_keys.txt           ← Add your keys here
├── README_INSTALL.md        ← Full guide
├── LICENSE                  ← Apache 2.0
└── *.py                     ← System files
```

## Quick Commands

```cmd
# Install
install.bat

# Start
start_murphy.bat

# Test
python real_test.py

# Demo
python demo_murphy_sells_itself.py

# Stop
stop_murphy.bat

# Check status
curl http://localhost:3002/api/status
```

## What Murphy Can Do

### Content Creation:
- Write articles, books, documentation
- Generate marketing copy
- Create sales materials
- Produce social media content

### Business Automation:
- Autonomous lead generation
- Email campaigns
- Payment processing
- Customer management

### AI Operations:
- Multi-agent coordination
- Workflow orchestration
- Decision making
- Pattern learning

### Development:
- Code generation
- API integration
- System monitoring
- Performance optimization

## Success Checklist

After installation, you should have:
- ✅ Python installed and in PATH
- ✅ All dependencies installed
- ✅ Groq API keys added
- ✅ Murphy running on port 3002
- ✅ 5/5 tests passing
- ✅ Dashboard accessible
- ✅ Demo completed successfully

## Support

**Documentation:**
- README_INSTALL.md (complete guide)
- DEMO_MURPHY_SELLS_ITSELF.md (demo details)
- ASYNCIO_FIX_COMPLETE.md (technical details)

**Testing:**
- real_test.py (5 tests)
- murphy_server.log (error logs)

**API:**
- http://localhost:3002/api/status (system status)
- http://localhost:3002/api/monitoring/health (health check)

---

**Ready to automate your business? Start Murphy now!** 🚀

```cmd
start_murphy.bat
```