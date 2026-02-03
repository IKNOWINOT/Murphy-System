# CRITICAL: You're Using the Wrong Package!

## The Error You're Seeing

```
ERROR: No module named 'groq_client'
ERROR: No module named 'aiohttp'
```

**This means you're running the OLD package that doesn't have these files!**

---

## Step-by-Step Installation (Follow Exactly)

### Step 1: Stop Everything

```bash
# Windows
taskkill /F /IM python.exe

# Linux/Mac
pkill -f python
```

### Step 2: Delete Old Installation

```bash
# Delete the old murphy_system folder completely
rm -rf murphy_system  # Linux/Mac
rmdir /S murphy_system  # Windows

# Or just rename it
mv murphy_system murphy_system_OLD
```

### Step 3: Extract NEW Package

**Download:** `murphy_system_v2.1_VERIFIED_20260130_2231.zip` (684 KB)

```bash
unzip murphy_system_v2.1_VERIFIED_20260130_2231.zip
cd murphy_system
```

### Step 4: VERIFY Files Are Present

**CRITICAL - Check these files exist:**

```bash
# Check groq_client.py (MUST be 4,933 bytes)
ls -l groq_client.py
# Should show: 4933 bytes

# Check requirements.txt has aiohttp
cat requirements.txt | grep aiohttp
# Should show: aiohttp==3.9.1
```

**If either file is missing or wrong, STOP! You have the wrong package!**

### Step 5: Install Dependencies

```bash
pip install -r requirements.txt
```

**VERIFY aiohttp installed:**
```bash
pip list | grep aiohttp
# Should show: aiohttp 3.9.1
```

**VERIFY groq_client can be imported:**
```bash
python -c "import groq_client; print('OK')"
# Should show: OK
```

### Step 6: Add API Keys

Edit `groq_keys.txt` and add your Groq API keys (one per line)

### Step 7: Start Server

```bash
# Windows
start_murphy.bat

# Linux/Mac
./start_murphy.sh
```

### Step 8: CHECK SERVER LOGS

**MUST see these lines:**
```
INFO: ✓ Enhanced LLM Provider initialized
INFO:   - Groq keys: 9
INFO:   - Aristotle: Available
```

**MUST NOT see these lines:**
```
ERROR: No module named 'groq_client'  ← If you see this, STOP!
ERROR: No module named 'aiohttp'      ← If you see this, STOP!
```

**If you see ANY errors, STOP and fix them before continuing!**

### Step 9: Test API Directly

```bash
curl -X POST http://localhost:3002/api/llm/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Say hello"}'
```

**Expected response:**
```json
{
  "response": "Hello! I'm Murphy...",
  "success": true
}
```

**NOT:**
```json
{
  "response": "Error: Generation failed",
  "success": true
}
```

### Step 10: Open Browser

```
http://localhost:3002
```

Use **Incognito mode** to avoid cache issues!

---

## Verification Checklist

Before testing in browser, verify ALL of these:

- [ ] Deleted old murphy_system folder
- [ ] Extracted NEW package (684 KB)
- [ ] groq_client.py exists (4,933 bytes)
- [ ] requirements.txt has aiohttp
- [ ] Ran: `pip install -r requirements.txt`
- [ ] Verified: `pip list | grep aiohttp` shows 3.9.1
- [ ] Verified: `python -c "import groq_client"` works
- [ ] Started server
- [ ] Server logs show "✓ Enhanced LLM Provider initialized"
- [ ] Server logs do NOT show "No module named" errors
- [ ] curl test returns real response (not error)

**If ANY checkbox is unchecked, the system will NOT work!**

---

## Common Mistake

**You're probably doing this:**
1. Extracting new package
2. But running server from OLD directory
3. Or not installing dependencies
4. Or not restarting server

**You MUST:**
1. Delete old directory completely
2. Extract new package
3. Install dependencies: `pip install -r requirements.txt`
4. Restart server
5. Verify logs show NO errors

---

## Quick Test Script

Save this as `test_installation.sh`:

```bash
#!/bin/bash

echo "=== Murphy Installation Test ==="
echo ""

# Test 1: Check groq_client.py
if [ -f "groq_client.py" ]; then
    SIZE=$(wc -c < groq_client.py)
    if [ "$SIZE" -eq 4933 ]; then
        echo "✓ groq_client.py present (4,933 bytes)"
    else
        echo "✗ groq_client.py wrong size: $SIZE bytes"
        exit 1
    fi
else
    echo "✗ groq_client.py MISSING!"
    exit 1
fi

# Test 2: Check aiohttp in requirements
if grep -q "aiohttp" requirements.txt; then
    echo "✓ requirements.txt has aiohttp"
else
    echo "✗ requirements.txt missing aiohttp!"
    exit 1
fi

# Test 3: Check aiohttp installed
if python -c "import aiohttp" 2>/dev/null; then
    echo "✓ aiohttp installed"
else
    echo "✗ aiohttp NOT installed! Run: pip install -r requirements.txt"
    exit 1
fi

# Test 4: Check groq_client imports
if python -c "import groq_client" 2>/dev/null; then
    echo "✓ groq_client imports successfully"
else
    echo "✗ groq_client import failed!"
    exit 1
fi

echo ""
echo "✓✓✓ ALL CHECKS PASSED ✓✓✓"
echo "You can now start the server!"
```

Run it:
```bash
chmod +x test_installation.sh
./test_installation.sh
```

---

## If Still Not Working

Share these with me:

1. **Output of:**
   ```bash
   ls -la groq_client.py
   cat requirements.txt | grep aiohttp
   pip list | grep aiohttp
   ```

2. **Server startup logs** (first 50 lines)

3. **Which package you downloaded** (file size?)

The package I created (684 KB) has ALL the files. If you're seeing errors, you're either:
- Using a different package
- Not installing dependencies
- Running from wrong directory