# Prompt 05 — Wire QA and Governance (Priority 3)

> **Prerequisites:** Prompts 00-04 must pass.
> Read `IMMOVABLE_CONSTRAINTS.md` and `ENGINEERING_STANDARD.md` first.

---

## Goal

Wire every Priority 3 quality assurance and MFGC governance module.  After
this prompt, every output produced by Murphy passes through the quality floor
(≥ 0.80) and CITL dual-pass sensor before being delivered to clients.

---

## Modules in Scope

1. `production_commissioning_validator.py` — API endpoint + automated Q1-Q10
2. `mfgc_core.py` — 7-phase generative control pipeline
3. `information_quality.py` → `InformationQualityEngine.assess()`
4. `prompt_amplifier.py` — MSS pipeline (Stimulate → Magnify → Solidify)
5. CITL dual-pass sensor (archetype + element checks — Part 7.1)
6. HITL escalation path (Part 7.2)

---

## Success Criteria

- [ ] Q1-Q10 applied to each module
- [ ] `production_commissioning_validator.py` exposed as API endpoint
- [ ] `mfgc_core.py` 7-phase pipeline wired into the execution path
- [ ] `InformationQualityEngine.assess()` called on all report outputs
- [ ] `prompt_amplifier.py` MSS pipeline called on all agent task dispatches
- [ ] CITL dual-level evaluation active (Level 1: code; Level 2: user output)
- [ ] HITL escalation path active and tested
- [ ] CI passes after changes

---

## Steps

### Step 1 — Wire commissioning validator as API endpoint

```python
# murphy_production_server.py
# [DOC-UPDATE: API_ROUTES.md, ARCHITECTURE_MAP.md]
@app.post("/api/commissioning/validate")
async def validate_module(payload: dict):
    """Run Q1-Q10 commissioning validation for a module. QA-WIRE-001"""
    try:
        from src.production_commissioning_validator import CommissioningValidator
        validator = CommissioningValidator()
        module_name = payload.get("module_name", "")
        results = validator.validate_module(module_name)
        return {"status": "ok", "results": results}
    except Exception as e:  # QA-WIRE-ERR-001
        logger.error("commissioning_validator endpoint error: %s", e)
        return {"status": "error", "detail": str(e)}, 500

@app.get("/api/commissioning/status")
async def get_commissioning_status():
    """Return overall commissioning status for all modules. QA-WIRE-002"""
    try:
        from src.production_commissioning_validator import CommissioningValidator
        validator = CommissioningValidator()
        return {"status": "ok", "summary": validator.get_summary()}
    except Exception as e:  # QA-WIRE-ERR-002
        logger.error("commissioning_status endpoint error: %s", e)
        return {"status": "error", "detail": str(e)}, 500
```

---

### Step 2 — Wire MFGC 7-phase pipeline

Verify `mfgc_core.py` implements the 7 phases:

```bash
python -c "
import sys
sys.path.insert(0, 'Murphy System/src')
from src.mfgc_core import MFGCPipeline
import inspect
print([m for m in dir(MFGCPipeline) if not m.startswith('_')])
"
```

The 7 phases must be:
1. **Observe** — ingest raw input
2. **Orient** — apply domain context
3. **Decide** — select generation strategy
4. **Amplify** — MSS pipeline (Stimulate → Magnify → Solidify)
5. **Execute** — run swarm agents
6. **Validate** — quality floor ≥ 0.80 check
7. **Deliver** — return validated output

Wire MFGC into the main agent task dispatch path:

```python
# In the agent dispatch function / execution engine
# [DOC-UPDATE: ARCHITECTURE_MAP.md, LLM_SUBSYSTEM.md]
try:
    from src.mfgc_core import MFGCPipeline
    pipeline = MFGCPipeline()
    result = pipeline.run(task)
except Exception as e:  # QA-MFGC-ERR-001
    logger.error("MFGC pipeline error: %s", e)
    raise
```

---

### Step 3 — Wire InformationQualityEngine

```python
# In report generation chain
# [DOC-UPDATE: ARCHITECTURE_MAP.md]
try:
    from src.information_quality import InformationQualityEngine
    iq = InformationQualityEngine()
    quality = iq.assess(output_text)
    if quality.score < 0.80:
        logger.warning(  # QA-IQ-WARN-001
            "Output quality %.2f below floor 0.80 — triggering HITL",
            quality.score,
        )
        _escalate_to_hitl(output_text, quality)
except Exception as e:  # QA-IQ-ERR-001
    logger.error("InformationQualityEngine error: %s", e)
    # Non-fatal: log and continue, but flag for review
```

---

### Step 4 — Wire MSS pipeline (prompt_amplifier.py)

The MSS pipeline runs Stimulate → Magnify → Solidify on every agent prompt
before dispatch:

```python
# In agent task dispatch
# [DOC-UPDATE: LLM_SUBSYSTEM.md]
try:
    from src.prompt_amplifier import PromptAmplifier
    amplifier = PromptAmplifier()
    amplified_prompt = amplifier.amplify(raw_prompt)
except Exception as e:  # QA-MSS-ERR-001
    logger.warning("PromptAmplifier error (using raw prompt): %s", e)
    amplified_prompt = raw_prompt  # Graceful degradation
```

Verify Magnify and Solidify failures are tracked independently per the MSS
error tracking pattern (MSS-MAGNIFY-ERR-001, MSS-SOLIDIFY-ERR-001).

---

### Step 5 — Wire CITL dual-pass sensor (Part 7.1)

CITL operates at two levels:

**Level 1 — Code output evaluation (building the system):**
- Archetype check: does the code match the module's intended purpose/persona?
- Element check: are all required functions/classes/error labels present?

**Level 2 — Production output evaluation (for end users):**
- Archetype check: does the output match the user's requested format/tone?
- Element check: are all required sections/data present in the output?

```python
# CITL dual-pass sensor (apply after every generation)
# [DOC-UPDATE: ARCHITECTURE_MAP.md]
def _run_citl_dual_pass(output: str, context: dict, level: int) -> dict:
    """Run CITL archetype + element checks. CITL-SENSOR-001"""
    results = {"level": level, "archetype": None, "element": None, "passed": False}
    try:
        # Archetype check
        archetype_ok = _check_archetype(output, context)
        results["archetype"] = archetype_ok
        # Element check
        element_ok = _check_elements(output, context)
        results["element"] = element_ok
        results["passed"] = archetype_ok and element_ok
        if not results["passed"]:
            logger.warning(  # CITL-SENSOR-WARN-001
                "CITL Level %d failed — archetype=%s element=%s",
                level, archetype_ok, element_ok,
            )
    except Exception as e:  # CITL-SENSOR-ERR-001
        logger.error("CITL dual-pass sensor error: %s", e)
    return results
```

Wire this function into the execution path after every agent output and
every code generation output.

---

### Step 6 — Wire HITL escalation path (Part 7.2)

```python
def _escalate_to_hitl(content: str, reason: str) -> None:
    """Escalate to human-in-the-loop review. HITL-ESC-001"""
    try:
        from src.hitl_execution_gate import HITLExecutionGate
        gate = HITLExecutionGate()
        gate.create_review_request(content=content, reason=reason)
        logger.info("HITL review request created: %s", reason)
    except Exception as e:  # HITL-ESC-ERR-001
        logger.error("HITL escalation failed: %s", e)
        # CITL iteration cap exceeded — log and alert
```

---

### Step 7 — Verify tests

```bash
cd "Murphy System"
python -m pytest tests/ -v -k "mfgc or quality or commissioning or amplifier or citl or hitl" \
    --tb=short 2>&1 | tail -40
```

---

### Record completion in tracker

```python
from src.prompt_execution_tracker import PromptExecutionTracker

tracker = PromptExecutionTracker()
tracker.mark_prompt_complete("05_WIRE_QA_AND_GOVERNANCE", results={
    "modules_wired": [
        "production_commissioning_validator", "mfgc_core",
        "information_quality", "prompt_amplifier",
        "citl_dual_pass", "hitl_escalation",
    ],
    "quality_floor_active": True,
    "citl_level1_active": True,
    "citl_level2_active": True,
    "hitl_active": True,
    "concept_blocks": ["QA Pipeline", "CITL Governance"],
    "doc_updates": ["ARCHITECTURE_MAP.md", "LLM_SUBSYSTEM.md", "CHANGELOG.md"],
})
```

---

## [DOC-UPDATE: ARCHITECTURE_MAP.md, LLM_SUBSYSTEM.md, CHANGELOG.md]
