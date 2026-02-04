# Murphy System 1.0 - Startup Troubleshooting Guide

## Common Issues & Solutions

### Issue 1: "ERROR: No matching distribution found for python>=3.11"

**Problem:** The requirements file incorrectly listed `python>=3.11` as a pip package.

**Solution:** ✅ FIXED! This has been removed from requirements_murphy_1.0.txt.

**What was changed:**
```diff
- python>=3.11
+ # NOTE: Requires Python 3.11 or higher (check version with: python --version)
```

---

### Issue 2: "ModuleNotFoundError: No module named 'pydantic'"

**Problem:** Dependencies failed to install because of the python>=3.11 error above.

**Solution:** Run the installation again now that the requirements are fixed:

```bash
# Windows
start_murphy_1.0.bat

# Linux/Mac
./start.sh
```

Or manually install core dependencies:
```bash
pip install fastapi uvicorn pydantic aiohttp httpx matplotlib watchdog
```

---

### Issue 3: Crash at line 39 of murphy_system_1.0_runtime.py

**Problem:** Import errors caused unhandled exceptions.

**Solution:** ✅ FIXED! All imports now have proper error handling.

**What was changed:**
- Added try/except blocks around all major component imports
- Added null checks before instantiating components
- System now gracefully degrades if dependencies are missing
- Clear warning messages show which components couldn't load

---

### Issue 4: "Traceback (most recent call last)..." during startup

**Problem:** Missing dependencies or import errors.

**Solution:** 

1. **First, ensure Python version is correct:**
   ```bash
   python --version
   # Should show: Python 3.11.0 or higher
   ```

2. **Install/reinstall dependencies:**
   ```bash
   pip install -r requirements_murphy_1.0.txt
   ```

3. **If full install fails, install core dependencies:**
   ```bash
   pip install fastapi uvicorn pydantic aiohttp httpx
   ```

4. **Try starting Murphy again:**
   ```bash
   python murphy_system_1.0_runtime.py
   ```

---

## Verification Steps

### Step 1: Check Python Version
```bash
python --version
# Expected: Python 3.11.0 or higher
```

### Step 2: Check Dependencies
```bash
python -c "import fastapi, uvicorn, pydantic; print('Core dependencies OK')"
```

### Step 3: Test Import
```bash
python -c "from murphy_system_1.0_runtime import MurphySystem; print('Import successful')"
```

### Step 4: Start Murphy
```bash
python murphy_system_1.0_runtime.py
```

---

## Expected Startup Output (After Fixes)

```
================================================================================
                       MURPHY SYSTEM 1.0 - STARTUP
================================================================================

Checking Python version...
Python 3.12.0
[OK] Python 3.12.0

Installing dependencies...
[OK] Dependencies installed

Checking environment variables...
[OK] Port: 6666

Creating directories...
[OK] Directories created

================================================================================
                   STARTING MURPHY SYSTEM 1.0
================================================================================

Starting Murphy System on port 6666...
API Documentation: http://localhost:6666/docs
Health Check: http://localhost:6666/api/health

✓ Loaded module: SystemBuilder v1.0.0
✓ Loaded module: GateBuilder v1.0.0
✓ Loaded module: ModuleManager v1.0.0
✓ Loaded module: TaskExecutor v1.0.0

INFO: Initializing Universal Control Plane...
INFO: Initializing Inoni Business Automation...
INFO: Initializing Integration Engine...
INFO: Initializing Two-Phase Orchestrator...

================================================================================
MURPHY SYSTEM 1.0.0 - READY
================================================================================

INFO: Started server process [12345]
INFO: Waiting for application startup.
INFO: Application startup complete.
INFO: Uvicorn running on http://0.0.0.0:6666
```

---

## If You Still Have Issues

### Get Detailed Error Information

Run with verbose logging:
```bash
python murphy_system_1.0_runtime.py 2>&1 | tee startup.log
```

This will save all output to `startup.log` which you can share for debugging.

### Check Component Availability

The system will now show warnings for unavailable components:
```
⚠️  Warning: Could not import UniversalControlPlane: <error details>
⚠️  Warning: Could not import InoniBusinessAutomation: <error details>
⚠️  Warning: Could not import UnifiedIntegrationEngine: <error details>
```

These warnings are informational - Murphy will still start with available components.

### Manual Dependency Check

Check each major dependency:
```bash
python -c "import fastapi; print('fastapi OK')"
python -c "import uvicorn; print('uvicorn OK')"
python -c "import pydantic; print('pydantic OK')"
python -c "import aiohttp; print('aiohttp OK')"
python -c "import httpx; print('httpx OK')"
```

---

## What the Fixes Do

### 1. Requirements Fix
- **Before:** `python>=3.11` (invalid pip package)
- **After:** Comment explaining Python version requirement

### 2. Import Error Handling
- **Before:** Crashes if import fails
- **After:** Gracefully handles missing components with warnings

### 3. Null Safety
- **Before:** Tries to instantiate even if import failed
- **After:** Checks if class exists before instantiation

### 4. Better Feedback
- **Before:** Generic errors, hard to debug
- **After:** Clear warnings with specific error messages

---

## Quick Start After Fixes

```bash
# Windows
cd "Murphy System\murphy_integrated"
start_murphy_1.0.bat

# Linux/Mac
cd "Murphy System/murphy_integrated"
./start.sh

# Or directly
python murphy_system_1.0_runtime.py
```

---

## Success Indicators

✅ No "ERROR: No matching distribution found for python>=3.11"
✅ Dependencies install successfully
✅ Murphy starts without crashing
✅ Web server runs on http://localhost:6666
✅ API documentation accessible at /docs
✅ Health check responds at /api/health

---

## Contact

If issues persist after these fixes, please provide:
1. Python version (`python --version`)
2. Operating system
3. Full error output from `startup.log`
4. Output from dependency check commands above

---

**Last Updated:** 2026-02-04
**Fixes Applied:** requirements fix, import error handling, null safety checks
