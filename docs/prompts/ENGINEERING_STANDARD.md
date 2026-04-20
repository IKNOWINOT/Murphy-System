# Engineering Standard Reference Card

> Use this card as a checklist whenever writing, reviewing, or commissioning
> any module in the Murphy System.

---

## Q1-Q10 Commissioning Questions

These questions are defined in `COMMISSIONING_CHECKLIST.md` and enforced
programmatically by `production_commissioning_validator.py`.

| # | Question | Minimum Answer Required | Severity if Missing |
|---|----------|------------------------|---------------------|
| **Q1** | Does the module do what it was designed to do? | YES | P0 |
| **Q2** | What exactly is the module supposed to do (knowing this may evolve)? | Documented | P1 |
| **Q3** | What conditions are possible based on the module? | Documented | P2 |
| **Q4** | Does the test profile reflect the full range of conditions? | YES (≥ 1 test per condition) | P1 |
| **Q5** | What is the expected result at all points of operation? | Documented | P1 |
| **Q6** | What is the actual result? | Matches Q5 | P0 |
| **Q7** | How do we restart from symptoms if problems persist? | Runbook exists | P2 |
| **Q8** | What monitoring/alerting is in place? | At least 1 log statement per error path | P1 |
| **Q9** | What documentation exists for this module? | At least a docstring | P2 |
| **Q10** | What CITL constraints apply from known failures? | Reviewed and recorded | P3 |

### Severity Levels

| Level | Name | Meaning |
|-------|------|---------|
| **P0** | Boot-blocking | System cannot start or revenue cannot be generated |
| **P1** | Feature-blocking | A primary feature is broken or untested |
| **P2** | Degraded | Feature works but has known limitations |
| **P3** | Minor | Low-impact issue or documentation gap |
| **P4** | Info | Informational finding, no action required |

---

## CLAUDE.md Behavioral Guidelines

### 1. Think Before Coding
State assumptions explicitly.  If uncertain, ask.  Surface tradeoffs.
Before writing any code, answer:
- What problem am I solving?
- What is the smallest change that solves it?
- What could break?

### 2. Simplicity First
Minimum code that solves the problem.  No speculative features.
- If a 5-line solution works, don't write 50 lines.
- No "while we're in here" changes.
- Delete before adding.

### 3. Surgical Changes
Touch only what you must.  Match existing style exactly.
- Check the surrounding code's style before writing.
- Preserve existing error handling patterns.
- Do not reformat code you're not changing.

### 4. Goal-Driven Execution
Transform tasks into verifiable goals with success criteria.
- Every task gets a "done when:" statement.
- Every change gets a test or manual verification step.
- No undefined success conditions.

### 5. No Silent Failures
Error handling everywhere.  Observable logging.
- Every `try` must have an `except` with `logger.error/warning`.
- Every except block must have a labeled error code comment.
- Never swallow exceptions silently.

---

## Wiring Checklist (6 Items Per Connection)

For every module → production server connection, complete all 6:

```
WIRING CHECKLIST — <module_name>
=================================
[ ] 1. Import succeeds without error
[ ] 2. Health check registered (status_probe or /api/health endpoint)
[ ] 3. Events produced registered in MODULE_MANIFEST
[ ] 4. Events consumed registered in MODULE_MANIFEST
[ ] 5. API endpoints added with try/except + logging + error labels
[ ] 6. Test file exists and all tests pass
```

---

## Error Label Convention

All error labels follow: `MODULE-SUBSYSTEM-ERR-NNN`

Examples:
- `MFGC-CORE-ERR-001` — error in mfgc_core.py core logic
- `AUTO-SAFE-ERR-003` — error in automation_safeguard_engine.py
- `LLM-PROVIDER-ERR-002` — error in llm_provider.py
- `REVENUE-WIRE-ERR-001` — error in revenue module wiring

Labels appear as comments on except lines AND in logger messages:

```python
try:
    result = module.run()
except Exception as e:  # MODULE-SUBSYSTEM-ERR-001
    logger.error("MODULE-SUBSYSTEM-ERR-001: %s", e)
    raise
```

---

## `[DOC-UPDATE]` Tagging Convention

When code changes affect documentation, add a `[DOC-UPDATE: ...]` tag as
a comment in the code and as a section at the bottom of the prompt file.

**In code:**
```python
# [DOC-UPDATE: API_ROUTES.md, ARCHITECTURE_MAP.md]
@app.post("/api/new-endpoint")
async def new_endpoint():
    ...
```

**At the bottom of prompt files:**
```markdown
## [DOC-UPDATE: API_ROUTES.md, ARCHITECTURE_MAP.md, CHANGELOG.md]
After completing this prompt, update these files.
```

**Known documentation files and what triggers updates:**

| File | Updated when... |
|------|----------------|
| `API_ROUTES.md` | New endpoints added or removed |
| `ARCHITECTURE_MAP.md` | Module wiring changes |
| `CHANGELOG.md` | Any functional change (always) |
| `STATUS.md` | System health or readiness changes |
| `GETTING_STARTED.md` | Onboarding or setup changes |
| `USER_MANUAL.md` | UI or user-facing feature changes |
| `ROADMAP.md` | Milestones completed or reprioritized |
| `LLM_SUBSYSTEM.md` | LLM routing, MSS, or CITL changes |

---

## Known CITL Constraints

> Add new constraints here after every sprint.  Format:
> `CITL-CONSTRAINT-NNN: <module> | <failure> | <constraint>`

_(No constraints recorded yet — add as they are discovered.)_

---

## Sync Direction Reference

```
Murphy System/src/  →  root src/      (always sync after changes)
Murphy System/tests/ → root tests/    (always sync after changes)
Murphy System/docs/  → root docs/     (docs are Murphy System canonical)
```

Never edit root copies without also updating `Murphy System/` copies.
CI enforces this via `tree-divergence-check` and `source-drift-guard`.
