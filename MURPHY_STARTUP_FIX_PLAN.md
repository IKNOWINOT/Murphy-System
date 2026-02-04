# Murphy System 1.0 - Startup Fix Plan

**Date:** February 4, 2025  
**Status:** ACTIVE FIXES IN PROGRESS  
**Goal:** Make Murphy System run successfully

---

## Root Cause Analysis

### Issue 1: Import Errors
**Problem:** Multiple broken imports preventing system startup
- `visualization_bot.py` imports from non-existent `modern_arcana` module
- Files exist in `bots/` but imports reference wrong module path
- Circular dependency chain in bot initialization

**Impact:** System cannot start - fails at import time

### Issue 2: Missing Dependencies
**Problem:** Required Python packages not installed
- `jsonschema` - FIXED ✅
- `matplotlib` - FIXED ✅
- Heavy ML libraries (torch, transformers) - DEFERRED (disk space)

### Issue 3: Multiple Entry Points
**Problem:** Unclear which runtime to use
- murphy_system_1.0_runtime.py - Most comprehensive
- murphy_final_runtime.py - Alternative
- murphy_complete_backend.py - Backend-focused

**Decision:** Use murphy_system_1.0_runtime.py as primary

---

## Fix Strategy

### Phase 1: Fix Import Errors (IMMEDIATE)
1. Fix visualization_bot.py imports
2. Fix any other broken bot imports
3. Make bot imports optional (try/except)
4. Test basic system startup

### Phase 2: Minimal Runtime (IMMEDIATE)
1. Create minimal entry point that skips problematic imports
2. Get FastAPI server running
3. Test basic API endpoints
4. Verify core functionality

### Phase 3: Gradual Component Integration (SHORT TERM)
1. Add components one by one
2. Test after each addition
3. Fix issues as they arise
4. Document working configuration

---

## Execution Plan

### Step 1: Fix visualization_bot.py ✅ IN PROGRESS
```python
# Change from:
from modern_arcana.gpt_oss_runner import GPTOSSRunner

# To:
from .gpt_oss_runner import GPTOSSRunner
```

### Step 2: Make bot imports optional
Wrap problematic imports in try/except blocks

### Step 3: Create minimal runtime
Strip down to core functionality only

### Step 4: Test and iterate
Run system, fix errors, repeat

---

## Expected Outcome

**Working Murphy System with:**
- ✅ FastAPI server running
- ✅ Basic API endpoints accessible
- ✅ Core subsystems loaded
- ✅ Minimal bot framework
- ⏳ Full bot integration (gradual)
- ⏳ ML features (when disk space available)

---

**Status:** Executing fixes now...