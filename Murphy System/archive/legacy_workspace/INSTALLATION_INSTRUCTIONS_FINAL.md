# Murphy System - Complete Installation Instructions

## Package Information

**File:** murphy_system_COMPLETE_FINAL_20260131_2224.zip  
**Size:** 160,801 bytes (157 KB)  
**Files:** 43  
**Status:** ✅ ALL VERIFICATIONS PASSED

---

## What's Verified

✅ groq_client.py (4,933 bytes) - Groq API client  
✅ murphy_ui_final.html (33,115 bytes) - Fixed UI with all bug fixes  
✅ murphy_complete_integrated.py (82,488 bytes) - Main server  
✅ requirements.txt contains aiohttp==3.9.1  
✅ install.bat contains `pip install aiohttp==3.9.1`  
✅ Server configured to serve murphy_ui_final.html  

---

## Installation Steps

### Step 1: Extract Package

```bash
# Extract to your desired location
unzip murphy_system_COMPLETE_FINAL_20260131_2224.zip

# Navigate to directory
cd murphy_system
```

### Step 2: Delete Old Virtual Environment (If Exists)

```bash
# Windows
rmdir /S murphy_venv

# Linux/Mac
rm -rf murphy_venv
```

**IMPORTANT:** This removes any corrupted packages from previous installs!

### Step 3: Run Install Script

```bash
# Windows
install.bat

# Linux/Mac
chmod +x install.sh
./install.sh
```

**What it does:**
- Creates fresh virtual environment
- Installs Python 3.12 (if needed)
- Installs ALL dependencies including:
  - flask
  - groq
  - requests
  - **aiohttp** ← Now included!
  - nest-asyncio
  - pydantic
  - All other packages

**You should see:**
```
Installing core packages...
...
pip install aiohttp==3.9.1
...
Successfully installed aiohttp-3.9.1
...
Verifying critical packages...
[OK] aiohttp installed: 3.9.1
[OK] nest_asyncio installed
[OK] groq installed
```

### Step 4: Add API Keys

Edit `groq_keys.txt` and add your Groq API keys (one per line):

```
gsk_your_key_here_1
gsk_your_key_here_2
```

Get free keys at: https://console.groq.com/keys

### Step 5: Start Murphy

```bash
# Windows
start_murphy.bat

# Linux/Mac
./start_murphy.sh
```

### Step 6: Verify Server Logs

**Should see:**
```
✓ Enhanced LLM Provider initialized
  - Groq keys: 9
  - Aristotle: Available
✓ LLM Manager initialized with key rotation
✓ Librarian System initialized
✓ All systems operational
```

**Should NOT see:**
```
ERROR: No module named 'aiohttp'          ← Should NOT appear
ERROR: No module named 'groq_client'      ← Should NOT appear
ERROR: No module named 'pydantic_core'    ← Should NOT appear
```

### Step 7: Open Browser

```
http://localhost:3002
```

Use **Incognito mode** to avoid cache issues!

### Step 8: Test Natural Language

Type in the chat:
```
hi how ya doing?
```

**Should get:**
```
Hello! I'm doing great, thanks for asking. I'm Murphy, your AI assistant...
```

**Should NOT get:**
```
Error: Generation failed  ← Should NOT happen
```

---

## Troubleshooting

### Issue: Still getting "No module named 'aiohttp'"

**Cause:** Old virtual environment not deleted

**Fix:**
```bash
cd murphy_system
rmdir /S murphy_venv
install.bat
```

### Issue: "No module named 'pydantic_core'"

**Cause:** Corrupted pydantic installation

**Fix:**
```bash
murphy_venv\Scripts\activate.bat
pip uninstall -y pydantic pydantic-core
pip install pydantic==2.5.0
```

### Issue: Python version wrong

**Check:**
```bash
python --version
```

**Should show:** Python 3.12.x

**If shows 3.13:** Downgrade to Python 3.12 (see DOWNGRADE_TO_PYTHON_312.md)

### Issue: install.bat doesn't install aiohttp

**Verify:**
```bash
type install.bat | findstr aiohttp
```

**Should show:**
```
pip install aiohttp==3.9.1
```

**If not:** You have the wrong package! Download murphy_system_COMPLETE_FINAL_20260131_2224.zip

---

## Verification Checklist

After installation, verify:

- [ ] Python 3.12 installed (`python --version`)
- [ ] Virtual environment created (murphy_venv folder exists)
- [ ] aiohttp installed (`pip list | findstr aiohttp`)
- [ ] groq_client.py exists (4,933 bytes)
- [ ] murphy_ui_final.html exists (33,115 bytes)
- [ ] Server starts without errors
- [ ] Server logs show "✓ Enhanced LLM Provider initialized"
- [ ] No "No module named" errors in logs
- [ ] Browser opens http://localhost:3002
- [ ] Natural language works (gets response, not error)

---

## What's Included

### Core Python Modules (28)
All required modules for Murphy to function

### Critical Dependencies (3)
- groq_client.py - Groq API client
- insurance_risk_gates.py - Risk assessment
- intelligent_system_generator.py - System generation

### UI Files (1)
- murphy_ui_final.html - Fixed UI with all bug fixes

### Installation Scripts (6)
- install.bat / install.sh
- start_murphy.bat / start_murphy.sh
- stop_murphy.bat / stop_murphy.sh

### Configuration Files (5)
- requirements.txt (with aiohttp!)
- groq_keys.txt
- aristotle_key.txt
- README.md
- LICENSE

---

## Support

If you encounter issues:

1. Check Python version: `python --version` (should be 3.12.x)
2. Delete virtual environment: `rmdir /S murphy_venv`
3. Reinstall: `install.bat`
4. Check server logs for errors
5. Verify aiohttp installed: `pip list | findstr aiohttp`

---

## Summary

This package has been **fully verified** to include:
- ✅ All 43 required files
- ✅ aiohttp in requirements.txt
- ✅ aiohttp in install.bat
- ✅ groq_client.py (correct size)
- ✅ murphy_ui_final.html (correct size)
- ✅ Server configured correctly

**Everything you need is in this package!**