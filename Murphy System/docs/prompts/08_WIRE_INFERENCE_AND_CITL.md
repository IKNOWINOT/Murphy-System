# Prompt 08 — Wire Inference Engine and CITL Loop

> **Prerequisites:** Prompts 00-07 must pass.
> Read `IMMOVABLE_CONSTRAINTS.md` and `ENGINEERING_STANDARD.md` first.

---

## Goal

Wire the inference engine and CITL (Continuous Iterative Training Loop) as
described in Parts 5 and 7.1.  After this prompt, every inference result is
evaluated at two levels, corrective constraints are written for failures, and
the iteration cap is enforced before HITL escalation.

---

## Modules in Scope

1. `inference_gate_engine.py` → `InferenceDomainGateEngine.infer()` (Steps 1-5)
2. CITL dual-level evaluation (Level 1: code; Level 2: user output)
3. Corrective constraint feedback loop
4. Iteration cap per operating mode
5. HITL escalation on cap breach

---

## Success Criteria

- [ ] Q1-Q10 applied to `inference_gate_engine.py`
- [ ] Full 5-step inference pipeline wired and callable
- [ ] CITL Level 1 (code output) evaluation active
- [ ] CITL Level 2 (user output) evaluation active
- [ ] Failed CITL evaluations write corrective constraints
- [ ] Iteration cap enforced per operating mode
- [ ] HITL escalation triggered on cap breach
- [ ] CI passes after changes

---

## Steps

### Step 1 — Apply Q1-Q10 to inference_gate_engine.py

```bash
python -c "
import sys
sys.path.insert(0, 'Murphy System/src')
from src.inference_gate_engine import InferenceDomainGateEngine
import inspect
print(inspect.getsource(InferenceDomainGateEngine))
" | head -100
```

The 5-step inference pipeline (verify each step exists in the code):

| Step | Name | Description |
|------|------|-------------|
| 1 | **Domain Classification** | Classify input into a domain (legal, finance, etc.) |
| 2 | **Gate Selection** | Select the appropriate inference gate for the domain |
| 3 | **Evidence Aggregation** | Gather context from relevant sources |
| 4 | **Inference** | Run inference with domain-specific rules |
| 5 | **Validation** | Validate output against domain constraints |

---

### Step 2 — Wire the full inference pipeline

```python
# murphy_production_server.py
# [DOC-UPDATE: API_ROUTES.md, ARCHITECTURE_MAP.md]
@app.post("/api/inference/run")
async def run_inference(payload: dict):
    """Run full 5-step inference pipeline. INFER-WIRE-001"""
    try:
        from src.inference_gate_engine import InferenceDomainGateEngine
        engine = InferenceDomainGateEngine()
        result = engine.infer(
            query=payload.get("query"),
            domain=payload.get("domain"),
            context=payload.get("context", {}),
        )
        # Run CITL Level 2 on the result
        citl_result = _run_citl_dual_pass(
            output=str(result),
            context=payload,
            level=2,
        )
        if not citl_result["passed"]:
            result["citl_warning"] = "Output quality check failed — flagged for review"
        return {"status": "ok", "result": result, "citl": citl_result}
    except Exception as e:  # INFER-WIRE-ERR-001
        logger.error("inference/run error: %s", e)
        return {"status": "error", "detail": str(e)}, 500
```

---

### Step 3 — CITL Level 1: Code output evaluation

Level 1 runs after every code generation task.  It checks:

**Archetype check (Level 1):**
- Does the generated code match the module's intended purpose?
- Is the code style consistent with the existing codebase?
- Are error labels present (MODULE-SUBSYSTEM-ERR-NNN pattern)?

**Element check (Level 1):**
- Are type hints present on all functions?
- Are docstrings present?
- Are try/except blocks present where needed?
- Are log calls present in except blocks?

```python
def _citl_level1_check(code_output: str, module_context: dict) -> dict:
    """CITL Level 1: evaluate code output. CITL-L1-001"""
    issues = []
    try:
        # Archetype check
        if "def " in code_output:
            if "->" not in code_output:
                issues.append("Missing return type annotations")
            if '"""' not in code_output and "'''" not in code_output:
                issues.append("Missing docstrings")
        # Element check
        if "except" in code_output:
            if "logger." not in code_output:
                issues.append("except block missing logger call")
            if "ERR-" not in code_output:
                issues.append("except block missing error label comment")
        passed = len(issues) == 0
        if not passed:
            logger.warning("CITL Level 1 issues: %s", issues)  # CITL-L1-WARN-001
        return {"passed": passed, "issues": issues, "level": 1}
    except Exception as e:  # CITL-L1-ERR-001
        logger.error("CITL Level 1 check error: %s", e)
        return {"passed": False, "issues": [str(e)], "level": 1}
```

---

### Step 4 — CITL Level 2: User output evaluation

Level 2 runs after every user-facing content generation.  It checks:

**Archetype check (Level 2):**
- Does the output match the user's requested format/tone?
- Is the content domain-appropriate?

**Element check (Level 2):**
- Are all required sections present?
- Is the quality score ≥ 0.80?
- Are factual claims supported by evidence?

```python
def _citl_level2_check(output: str, user_context: dict) -> dict:
    """CITL Level 2: evaluate user-facing output. CITL-L2-001"""
    issues = []
    try:
        from src.information_quality import InformationQualityEngine
        iq = InformationQualityEngine()
        quality = iq.assess(output)
        if quality.score < 0.80:
            issues.append(f"Quality score {quality.score:.2f} < 0.80 floor")
        passed = len(issues) == 0
        if not passed:
            logger.warning("CITL Level 2 issues: %s", issues)  # CITL-L2-WARN-001
        return {"passed": passed, "issues": issues, "score": quality.score, "level": 2}
    except Exception as e:  # CITL-L2-ERR-001
        logger.error("CITL Level 2 check error: %s", e)
        return {"passed": False, "issues": [str(e)], "level": 2}
```

---

### Step 5 — Corrective constraint feedback

When CITL fails, write a new corrective constraint:

```python
def _write_corrective_constraint(
    failure_description: str,
    level: int,
    module: str,
) -> None:
    """Write a CITL corrective constraint after a failure. CITL-CONSTRAINT-001"""
    try:
        from src.prompt_execution_tracker import PromptExecutionTracker
        tracker = PromptExecutionTracker()
        tracker.record_citl_result(
            module=module,
            level=level,
            passed=False,
            failure_description=failure_description,
        )
        logger.info("Corrective constraint written for %s (L%d)", module, level)
    except Exception as e:  # CITL-CONSTRAINT-ERR-001
        logger.error("Failed to write corrective constraint: %s", e)
```

---

### Step 6 — Iteration cap per operating mode

The iteration cap prevents infinite CITL retry loops:

```python
# Iteration caps per operating mode
CITL_ITERATION_CAPS = {
    "RED_LINE": 2,       # Maximum urgency: 2 retries then HITL
    "STANDARD": 5,       # Normal operation: 5 retries
    "LEARNING": 10,      # Learning mode: 10 retries
    "MAINTENANCE": 3,    # Maintenance mode: 3 retries
}

def _get_iteration_cap(operating_mode: str) -> int:
    """Return CITL iteration cap for the current operating mode. CITL-CAP-001"""
    return CITL_ITERATION_CAPS.get(operating_mode, 5)
```

Wire the cap into the CITL loop:

```python
# In the inference/generation loop
iteration = 0
cap = _get_iteration_cap(current_operating_mode)
while iteration < cap:
    result = _generate(task)
    citl = _run_citl_dual_pass(result, context, level=2)
    if citl["passed"]:
        break
    _write_corrective_constraint(str(citl["issues"]), 2, module_name)
    iteration += 1
else:
    # Cap exceeded — escalate to HITL
    logger.warning(  # CITL-CAP-WARN-001
        "CITL cap (%d) exceeded for %s — escalating to HITL",
        cap, module_name,
    )
    _escalate_to_hitl(result, reason="CITL iteration cap exceeded")
```

---

### Step 7 — Verify tests

```bash
cd "Murphy System"
python -m pytest tests/ -v -k "inference or citl or gate_engine" \
    --tb=short 2>&1 | tail -40
```

---

### Record completion in tracker

```python
from src.prompt_execution_tracker import PromptExecutionTracker

tracker = PromptExecutionTracker()
tracker.mark_prompt_complete("08_WIRE_INFERENCE_AND_CITL", results={
    "modules_wired": ["inference_gate_engine"],
    "citl_level1_active": True,
    "citl_level2_active": True,
    "corrective_feedback_active": True,
    "iteration_caps": {"RED_LINE": 2, "STANDARD": 5},
    "hitl_on_cap_breach": True,
    "concept_blocks": ["Inference Pipeline", "CITL Dual-Level Loop"],
    "doc_updates": ["ARCHITECTURE_MAP.md", "CHANGELOG.md"],
})
```

---

## [DOC-UPDATE: ARCHITECTURE_MAP.md, CHANGELOG.md]
