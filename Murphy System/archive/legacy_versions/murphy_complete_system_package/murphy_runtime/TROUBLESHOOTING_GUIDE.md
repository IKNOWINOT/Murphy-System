# Troubleshooting Guide - LLM Not Working

## The Problem

You're seeing:
```
User: hi how ya doing?
Murphy: Error: Generation failed
```

But the LLM IS working on the server! When I test it directly:
```bash
curl -X POST http://localhost:3002/api/llm/generate -d '{"prompt": "hi"}'
# Returns: "I'm doing well, thanks for asking..."
```

## Root Cause

One of these issues:

1. **Old server still running** - You didn't restart after installing new package
2. **Browser cache** - Browser is using old cached UI file
3. **Wrong package** - You're using an old package without groq_client.py
4. **Dependencies not installed** - aiohttp not installed

---

## Step-by-Step Fix

### Step 1: Stop ALL Murphy Processes

**Windows:**
```bash
# Stop via script
stop_murphy.bat

# Force kill if needed
taskkill /F /IM python.exe /FI "WINDOWTITLE eq murphy*"

# Verify nothing running
tasklist | findstr python
```

**Linux/Mac:**
```bash
# Stop via script
./stop_murphy.sh

# Force kill if needed
pkill -f murphy_complete_integrated.py

# Verify nothing running
ps aux | grep murphy
```

### Step 2: Verify Package Contents

Check these critical files exist:

```bash
cd murphy_system

# Check groq_client.py exists
ls -la groq_client.py
# Should show: 4,933 bytes

# Check requirements.txt has aiohttp
grep aiohttp requirements.txt
# Should show: aiohttp==3.9.1

# Check UI file size
ls -la murphy_ui_final.html
# Should show: 33,115 bytes
```

**If any file is missing or wrong size, you have the WRONG package!**

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

**Verify aiohttp installed:**
```bash
pip list | grep aiohttp
# Should show: aiohttp 3.9.1
```

### Step 4: Start Fresh Server

```bash
# Windows
start_murphy.bat

# Linux/Mac
./start_murphy.sh
```

**Watch the logs carefully!**

### Step 5: Check Server Logs

**GOOD logs (should see):**
```
INFO: ✓ Enhanced LLM Provider initialized
INFO:   - Groq keys: 9
INFO:   - Aristotle: Available
INFO: ✓ LLM Manager initialized with key rotation
```

**BAD logs (should NOT see):**
```
ERROR: No module named 'groq_client'
ERROR: No module named 'aiohttp'
ERROR: Groq API error
```

**If you see BAD logs, STOP and fix the issue before continuing!**

### Step 6: Clear Browser Cache COMPLETELY

**Chrome/Edge:**
1. Press F12 (open DevTools)
2. Right-click the refresh button
3. Select "Empty Cache and Hard Reload"

**Firefox:**
1. Press Ctrl+Shift+Delete
2. Select "Cached Web Content"
3. Click "Clear Now"

**Or just use Incognito/Private mode:**
- Chrome: Ctrl+Shift+N
- Firefox: Ctrl+Shift+P

### Step 7: Test LLM Directly

Before testing in browser, test the API directly:

```bash
curl -X POST http://localhost:3002/api/llm/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Say hello"}'
```

**Expected response:**
```json
{
  "response": "Hello! I'm Murphy, your AI assistant...",
  "success": true
}
```

**If you see "Error: Generation failed", check server logs for errors!**

### Step 8: Test in Browser

1. Open http://localhost:3002 (in incognito mode)
2. Type: `hi how ya doing?`
3. Should get friendly response

**If still seeing "Error: Generation failed":**
- Check browser console (F12) for errors
- Check network tab to see what API returned
- Verify you're hitting the right server (localhost:3002)

---

## Common Issues

### Issue 1: "No module named 'groq_client'"

**Cause:** groq_client.py not in package or not in same directory as server

**Fix:**
```bash
# Check file exists
ls murphy_system/groq_client.py

# If missing, you have wrong package!
# Download: murphy_system_v2.1_VERIFIED_20260130_2231.zip
```

### Issue 2: "No module named 'aiohttp'"

**Cause:** Dependencies not installed

**Fix:**
```bash
pip install aiohttp==3.9.1 nest-asyncio==1.5.8
```

### Issue 3: Still seeing "Error: Generation failed"

**Cause:** Browser cached old UI or hitting old server

**Fix:**
1. Stop ALL Python processes
2. Clear browser cache completely
3. Start server fresh
4. Use incognito mode

### Issue 4: Server logs show errors but curl works

**Cause:** Multiple servers running, curl hitting different one

**Fix:**
```bash
# Find all Python processes
ps aux | grep python  # Linux/Mac
tasklist | findstr python  # Windows

# Kill ALL Murphy processes
pkill -f murphy  # Linux/Mac
taskkill /F /IM python.exe  # Windows

# Start ONE server
./start_murphy.sh
```

---

## Diagnostic Commands

Run these to diagnose issues:

```bash
# 1. Check if server is running
curl http://localhost:3002/api/status

# 2. Check LLM endpoint
curl -X POST http://localhost:3002/api/llm/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "test"}'

# 3. Check which Python processes are running
ps aux | grep murphy  # Linux/Mac
tasklist | findstr python  # Windows

# 4. Check if aiohttp is installed
python -c "import aiohttp; print('aiohttp OK')"

# 5. Check if groq_client exists
python -c "import groq_client; print('groq_client OK')"

# 6. Check server logs
tail -f murphy.log  # Linux/Mac
type murphy.log  # Windows
```

---

## Still Not Working?

If you've done ALL the above and it still doesn't work:

1. **Share your server logs** - Copy the entire startup log
2. **Share the curl test result** - What does the API return?
3. **Share browser console errors** - Press F12, check Console tab
4. **Verify package** - Run: `ls -la murphy_system/groq_client.py`

---

## Quick Checklist

Before asking for help, verify:

- [ ] Stopped ALL old Murphy processes
- [ ] Using package: murphy_system_v2.1_VERIFIED_20260130_2231.zip
- [ ] groq_client.py exists (4,933 bytes)
- [ ] requirements.txt has aiohttp
- [ ] Ran: pip install -r requirements.txt
- [ ] aiohttp installed: `pip list | grep aiohttp`
- [ ] Started fresh server
- [ ] Server logs show "✓ Enhanced LLM Provider initialized"
- [ ] Server logs do NOT show "No module named" errors
- [ ] Cleared browser cache completely
- [ ] Tested in incognito mode
- [ ] curl test works: returns actual response, not error

If ALL checkboxes are checked and it still doesn't work, then we have a different issue to investigate.