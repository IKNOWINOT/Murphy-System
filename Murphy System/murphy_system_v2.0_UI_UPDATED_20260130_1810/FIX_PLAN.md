# Murphy System - Fix Plan for Logger Error

## Problem Analysis

### Error 1 (Expected):
```
ModuleNotFoundError: No module named 'runtime_orchestrator_enhanced'
```
This is caught by try/except - GOOD

### Error 2 (Actual Problem):
```
NameError: name 'logger' is not defined
```
The `logger` is used in the except block but hasn't been defined yet at that point in the code.

## Root Cause

The import structure is:
1. Line 42-54: Try to import runtime_orchestrator_enhanced
2. Line 56: Use `logger.warning()` in except block
3. BUT: `logger` is defined LATER in the file after imports

## Solution Plan

### Option 1: Use print() instead of logger (SIMPLE)
- Replace `logger.warning()` with `print()`
- Works immediately, no dependencies
- ✅ RECOMMENDED for quick fix

### Option 2: Define logger earlier (PROPER)
- Move logger definition before the try/except
- More proper but requires restructuring
- Could break other things

### Option 3: Use warnings module (STANDARD)
- Import warnings at top
- Use `warnings.warn()`
- Standard Python approach

## Implementation Plan

### Step 1: Check where logger is defined
```bash
grep -n "^logger = " murphy_complete_integrated.py
```

### Step 2: Choose fix approach
- If logger is defined early: Move import after logger
- If logger is defined late: Use print() or warnings

### Step 3: Apply fix
Replace:
```python
except ImportError:
    RUNTIME_ORCHESTRATOR_AVAILABLE = False
    logger.warning("runtime_orchestrator_enhanced not available - some features disabled")
```

With:
```python
except ImportError:
    RUNTIME_ORCHESTRATOR_AVAILABLE = False
    print("⚠ runtime_orchestrator_enhanced not available - some features disabled")
```

### Step 4: Test
1. Import test: `python -c "import murphy_complete_integrated"`
2. Server start: `python murphy_complete_integrated.py`
3. Full test suite: `python real_test.py`

### Step 5: Rebuild package
- Create new ZIP with fixed file
- Test on Windows (if possible)
- Deliver to user

## Expected Outcome

After fix:
- ✅ No import errors
- ✅ Server starts successfully
- ✅ All tests pass (5/5)
- ✅ Warning message displays correctly
- ✅ Works on Windows

## Rollback Plan

If fix causes issues:
1. Revert to using logger
2. Move logger definition earlier
3. Test again

---

**Next: Execute this plan**