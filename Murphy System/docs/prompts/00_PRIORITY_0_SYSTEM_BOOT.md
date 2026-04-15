# Prompt 00 — PRIORITY 0: System Boot Health

> **Before using this prompt:** Read `IMMOVABLE_CONSTRAINTS.md` and
> `ENGINEERING_STANDARD.md`.  All 6 immovable constraints apply.

---

## Goal

Ensure the system can start at all.  Identify and remove every roadblock that
prevents other systems from functioning.  **No other prompt should be run until
this one passes completely.**

---

## Success Criteria

- [ ] `murphy_production_server.py` imports and starts without error
- [ ] `Murphy System/src/__init__.py` exposes expected modules
- [ ] PYTHONPATH / `sys.path` wiring from root entrypoint → `Murphy System/src/` verified
- [ ] Smoke tests (`python -c "from src import config"` etc.) pass
- [ ] CI workflows (`.github/workflows/ci.yml`, `.github/workflows/source-drift-guard.yml`) can be located and executed
- [ ] No circular imports detected
- [ ] No missing hard dependencies (requirements.txt satisfied)
- [ ] VP Engineering Concept Block report produced

---

## Steps

### Step 1 — Locate root entrypoint and verify imports

```bash
# From the repository root
python -c "import murphy_production_server" 2>&1 | head -40
python -c "from src import config" 2>&1
python -c "from src import mfgc_core" 2>&1
python -c "from src import production_commissioning_validator" 2>&1
```

**If any import fails:**
1. Record the module name and error in the Concept Block (see Step 7).
2. Classify severity: P0 (boot-blocking) or P1 (feature-blocking).
3. Apply Q1-Q10 (see `ENGINEERING_STANDARD.md`) to the failing module.
4. Fix the import error with the smallest possible change.
5. Re-run until the import succeeds.

**Surgical change rule:** Touch only what is needed to make the import succeed.
Match existing code style exactly.

---

### Step 2 — Verify PYTHONPATH wiring

```bash
python - <<'EOF'
import sys, os
# Simulate the root entrypoint path insertion
sys.path.insert(0, os.path.join(os.getcwd(), "Murphy System", "src"))
from src import config
print("PYTHONPATH OK — src.config importable")
EOF
```

Check `murphy_production_server.py` lines 1-80 for `sys.path` manipulation and
`load_dotenv()` calls.  Confirm:
- `Murphy System/src` is on the path before any `from src import …` statement.
- `load_dotenv()` is called before any `os.getenv()` that reads API keys.

If either condition is not met, add the missing line (surgical change only).

---

### Step 3 — Verify `Murphy System/src/__init__.py`

```bash
python -c "
import sys, os
sys.path.insert(0, 'Murphy System/src')
import src
print(dir(src))
"
```

Confirm the `__init__.py` does not raise on import.  It should expose at
minimum `matrix_bridge` (lazy import with exception swallow) and the package
`__version__`.

---

### Step 4 — Run CI smoke tests

```bash
# Check CI workflow files exist and are valid YAML
python -c "
import yaml, pathlib
for f in ['.github/workflows/ci.yml',
          '.github/workflows/source-drift-guard.yml']:
    p = pathlib.Path(f)
    if not p.exists():
        print(f'MISSING: {f}')
    else:
        yaml.safe_load(p.read_text())
        print(f'OK: {f}')
"
```

---

### Step 5 — Circular import detection

```bash
python -c "
import sys, os, importlib, traceback
sys.path.insert(0, 'Murphy System/src')
modules_to_check = [
    'src.config',
    'src.mfgc_core',
    'src.production_commissioning_validator',
    'src.sales_automation',
    'src.prompt_execution_tracker',
]
for m in modules_to_check:
    try:
        importlib.import_module(m)
        print(f'OK: {m}')
    except ImportError as e:
        print(f'IMPORT ERROR ({m}): {e}')
    except Exception as e:
        print(f'ERROR ({m}): {e}')
"
```

For each failure, apply Q1 and Q7 from `ENGINEERING_STANDARD.md`.

---

### Step 6 — Check missing dependencies

```bash
pip check 2>&1 | head -30
python -m pip install -r "Murphy System/requirements.txt" --dry-run 2>&1 | grep -i "error\|conflict" | head -20
```

Document any unresolvable dependency conflicts in the Concept Block.

---

### Step 7 — Apply Q1-Q10 to the boot sequence

For each component verified in Steps 1-6, answer the Q1-Q10 commissioning
questions (from `ENGINEERING_STANDARD.md`) and record them below.

| Component | Q1 | Q4 | Q6 | Q8 | Q9 | Q10 | Severity |
|-----------|----|----|----|----|----|----|----------|
| murphy_production_server.py | ? | ? | ? | ? | ? | ? | P? |
| src/__init__.py | ? | ? | ? | ? | ? | ? | P? |
| sys.path wiring | ? | ? | ? | ? | ? | ? | P? |
| CI workflows | ? | ? | ? | ? | ? | ? | P? |
| requirements.txt | ? | ? | ? | ? | ? | ? | P? |

Fill this table by reading the actual code — code is primary truth.

---

### Step 8 — Produce VP Engineering Concept Block: System Boot Health

```
╔══════════════════════════════════════════════════════════════╗
║  VP ENGINEERING CONCEPT BLOCK — SYSTEM BOOT HEALTH          ║
║  Generated: <timestamp>                                      ║
╠══════════════════════════════════════════════════════════════╣
║  BOOT STATUS                                                 ║
║    Root entrypoint imports:   PASS / FAIL                    ║
║    PYTHONPATH wiring:         PASS / FAIL                    ║
║    src/__init__.py:           PASS / FAIL                    ║
║    CI workflow files:         PASS / FAIL                    ║
║    Circular imports:          NONE / <list>                  ║
║    Missing dependencies:      NONE / <list>                  ║
╠══════════════════════════════════════════════════════════════╣
║  BLOCKING ISSUES (P0)                                        ║
║    <list any P0 issues found>                                ║
╠══════════════════════════════════════════════════════════════╣
║  NON-BLOCKING ISSUES (P1-P4)                                 ║
║    <list any P1-P4 issues found>                             ║
╠══════════════════════════════════════════════════════════════╣
║  CORRECTIVE CONSTRAINTS ADDED                                ║
║    <list CITL constraints written>                           ║
╠══════════════════════════════════════════════════════════════╣
║  NEXT STEP                                                   ║
║    → If all PASS: proceed to 01_SCAN_AND_AUDIT.md            ║
║    → If any FAIL: fix P0s first, re-run this prompt          ║
╚══════════════════════════════════════════════════════════════╝
```

---

### Step 9 — Record completion in tracker

```python
from src.prompt_execution_tracker import PromptExecutionTracker

tracker = PromptExecutionTracker()
tracker.mark_prompt_complete("00_PRIORITY_0_SYSTEM_BOOT", results={
    "boot_healthy": True,          # or False
    "p0_issues": [],               # list any P0 issues
    "p1_issues": [],
    "concept_blocks": ["System Boot Health"],
    "doc_updates": [],             # [DOC-UPDATE: STATUS.md, CHANGELOG.md]
})
```

---

## [DOC-UPDATE: STATUS.md, CHANGELOG.md]

After completing this prompt, update:
- `STATUS.md` — record boot health status and date
- `CHANGELOG.md` — add entry for any fixes applied
