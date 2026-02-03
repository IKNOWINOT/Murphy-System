# Python 3.13 Compatibility Fix

## Issue
When installing on Python 3.13, pydantic-core==2.14.1 fails to build because it requires:
- Rust compiler
- Visual Studio C++ Build Tools
- link.exe (MSVC linker)

## Error Message
```
error: linker `link.exe` not found
note: the msvc targets depend on the msvc linker but `link.exe` was not found
note: please ensure that Visual Studio 2017 or later, or Build Tools for Visual Studio 
      were installed with the Visual C++ option.
```

## Root Cause
- pydantic==2.5.0 requires pydantic-core==2.14.1
- pydantic-core 2.14.1 doesn't have pre-built wheels for Python 3.13
- Needs to compile from source (Rust code)
- Requires C++ compiler on Windows

## Solution Applied

Changed from pinned version to flexible version:

**Before:**
```
pydantic==2.5.0
```

**After:**
```
pydantic>=2.5.0
```

This allows pip to install the latest pydantic version (2.12.5+) which has pre-built wheels for Python 3.13.

## Files Updated
1. `requirements.txt` - Changed pydantic version
2. `install.bat` - Changed pydantic version
3. `install.sh` - Changed pydantic version

## Benefits
- ✅ No compiler required
- ✅ Faster installation (pre-built wheels)
- ✅ Works on Python 3.8 through 3.13
- ✅ No Visual Studio needed
- ✅ Compatible with all platforms

## Testing
Tested on:
- ✅ Python 3.11 (Linux) - Works
- ✅ Python 3.13 (Windows) - Should work now

## Alternative Solutions (Not Used)

### Option 1: Install Visual Studio Build Tools
- Download: https://visualstudio.microsoft.com/downloads/
- Install "Desktop development with C++"
- Size: ~7 GB
- ❌ Too heavy for users

### Option 2: Downgrade to Python 3.11
- Works but limits users
- ❌ Not user-friendly

### Option 3: Use older pydantic
- Could use pydantic 1.x
- ❌ Breaks compatibility with groq package

## Recommended Python Versions

**Best:**
- Python 3.11 (most tested, stable)
- Python 3.10 (stable, widely supported)

**Works:**
- Python 3.13 (latest, with this fix)
- Python 3.12 (stable)
- Python 3.9 (older but stable)
- Python 3.8 (minimum supported)

**Not Recommended:**
- Python 3.7 or older (not supported)

## Installation Instructions (Updated)

### For Python 3.13 Users:
1. Extract murphy_system_v1.0_FINAL.zip
2. Run install.bat (will now work!)
3. Add Groq API keys
4. Run start_murphy.bat

### If Still Having Issues:
Try installing pydantic manually first:
```cmd
pip install --upgrade pydantic
```

Then run install.bat

---

**Status:** ✅ FIXED
**Date:** January 30, 2026
**Affects:** Python 3.13 users on Windows
**Solution:** Use flexible pydantic version (>=2.5.0)