# How to Downgrade from Python 3.13 to Python 3.12

## Step-by-Step Instructions for Windows

### Step 1: Download Python 3.12

1. Go to: https://www.python.org/downloads/release/python-3120/
2. Scroll down to "Files"
3. Download: **Windows installer (64-bit)** 
   - File: `python-3.12.0-amd64.exe`
   - Size: ~25 MB

### Step 2: Uninstall Python 3.13

**Option A: Using Windows Settings**
1. Press `Windows Key + I` (opens Settings)
2. Go to **Apps** → **Installed apps**
3. Search for "Python 3.13"
4. Click the three dots → **Uninstall**
5. Follow the prompts

**Option B: Using Control Panel**
1. Press `Windows Key + R`
2. Type: `appwiz.cpl` and press Enter
3. Find "Python 3.13" in the list
4. Right-click → **Uninstall**
5. Follow the prompts

### Step 3: Install Python 3.12

1. Run the downloaded `python-3.12.0-amd64.exe`
2. **IMPORTANT:** Check these boxes:
   - ✅ **"Add python.exe to PATH"** (at the bottom)
   - ✅ **"Install for all users"** (optional but recommended)
3. Click **"Install Now"**
4. Wait for installation to complete
5. Click **"Close"**

### Step 4: Verify Installation

Open a **NEW** Command Prompt (important - close old ones):

```bash
python --version
```

Should show:
```
Python 3.12.0
```

Also verify pip:
```bash
pip --version
```

Should show:
```
pip 23.x.x from C:\...\Python312\...
```

### Step 5: Install Murphy

Now that you have Python 3.12:

```bash
cd C:\Users\inoni\Downloads\murphy_system\murphy_system
install.bat
```

This time it will work because Python 3.12 has pre-built wheels for aiohttp!

You should see:
```
Installing core packages...
...
Successfully installed aiohttp-3.9.1
...
[OK] aiohttp installed: 3.9.1
```

### Step 6: Start Murphy

```bash
start_murphy.bat
```

Check the logs - should now see:
```
✓ Enhanced LLM Provider initialized
  - Groq keys: 9
  - Aristotle: Available
```

No more errors!

---

## Troubleshooting

### Issue: "python --version" still shows 3.13

**Solution:** You have multiple Python installations

1. Find where Python 3.12 is installed:
   ```bash
   where python
   ```
   
2. Use the full path:
   ```bash
   C:\Python312\python.exe --version
   ```

3. Or remove Python 3.13 from PATH:
   - Press `Windows Key`
   - Search: "Environment Variables"
   - Click "Edit the system environment variables"
   - Click "Environment Variables"
   - Under "System variables", find "Path"
   - Remove entries containing "Python313"
   - Add entry for "Python312"

### Issue: Can't uninstall Python 3.13

**Solution:** Use the Python installer

1. Run the Python 3.13 installer again
2. Choose "Uninstall"
3. Follow the prompts

### Issue: pip still uses Python 3.13

**Solution:** Use python -m pip

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

---

## Quick Summary

1. Download Python 3.12 installer
2. Uninstall Python 3.13 (Windows Settings → Apps)
3. Install Python 3.12 (check "Add to PATH")
4. Open NEW Command Prompt
5. Verify: `python --version` shows 3.12
6. Run: `install.bat`
7. Run: `start_murphy.bat`

---

## Why Python 3.12 Instead of 3.13?

- **Python 3.13** = Released October 2024 (very new)
  - Many packages don't have pre-built wheels yet
  - Requires compiling from source (needs Visual Studio)
  - Not recommended for production use yet

- **Python 3.12** = Released October 2023 (stable)
  - All packages have pre-built wheels
  - No compiler needed
  - Fully supported by all libraries
  - Recommended for production

---

## After Downgrading

Once you have Python 3.12 installed:

1. Extract Murphy package
2. Run `install.bat`
3. aiohttp will install without errors
4. Murphy will work perfectly

No more "Microsoft Visual C++ 14.0 required" errors!