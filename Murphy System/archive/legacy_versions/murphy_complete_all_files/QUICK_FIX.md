# QUICK FIX - Install Missing Dependencies

## The Problem

Your error:
```
ERROR: No module named 'aiohttp'
```

**This means you didn't run:** `pip install -r requirements.txt`

---

## The Fix (Run These Commands)

### Step 1: Navigate to murphy_system folder
```bash
cd murphy_system
```

### Step 2: Install dependencies
```bash
pip install -r requirements.txt
```

You should see:
```
Installing collected packages: aiohttp, nest-asyncio, ...
Successfully installed aiohttp-3.9.1 ...
```

### Step 3: Verify aiohttp installed
```bash
pip list | grep aiohttp
```

Should show:
```
aiohttp    3.9.1
```

### Step 4: Restart server
```bash
# Stop server (Ctrl+C)

# Start again
start_murphy.bat  # Windows
./start_murphy.sh  # Linux/Mac
```

### Step 5: Check logs
Should now see:
```
✓ Enhanced LLM Provider initialized
  - Groq keys: 9
```

Should NOT see:
```
ERROR: No module named 'aiohttp'  ← Should be gone!
```

---

## If pip install fails

Try:
```bash
# Upgrade pip first
python -m pip install --upgrade pip

# Then install requirements
pip install -r requirements.txt

# Or install manually
pip install aiohttp==3.9.1 nest-asyncio==1.5.8 groq==0.4.1
```

---

## Verify Installation

Run this to test:
```bash
python -c "import aiohttp; print('aiohttp version:', aiohttp.__version__)"
```

Should show:
```
aiohttp version: 3.9.1
```

---

## Summary

The package HAS requirements.txt with aiohttp listed.  
But you need to INSTALL it with: `pip install -r requirements.txt`

This is a standard Python step - the package contains the LIST of dependencies, but you must install them!