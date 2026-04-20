# Prompt 04 — Wire Onboarding Modules (Priority 2)

> **Prerequisites:** Prompts 00, 01, 02, 03 must pass.
> Read `IMMOVABLE_CONSTRAINTS.md` and `ENGINEERING_STANDARD.md` first.

---

## Goal

Wire every Priority 2 onboarding module into the production server.  A new
client must be able to complete onboarding without manual intervention.  When
onboarding completes, an ROI Calendar event must be created automatically.

---

## Modules in Scope

1. `setup_wizard.py` — 12-question intake wizard (Part 9.1)
2. `agentic_onboarding_engine.py` — automated onboarding execution
3. `production_deliverable_wizard.py` — deliverable configuration
4. `onboarding_flow.py` — pipeline orchestration
5. Tiered runtime packs — feature gating per subscription tier

---

## Success Criteria (per module)

- [ ] Q1-Q10 answered from reading the code
- [ ] Module imported without error
- [ ] Health check registered in `status_probe`
- [ ] Events registered in `MODULE_MANIFEST`
- [ ] API endpoints registered in `murphy_production_server.py`
- [ ] ROI Calendar event created on onboarding completion
- [ ] Tests exist and pass
- [ ] Commissioning checklist complete
- [ ] CI passes after changes

---

## The 12-Question Setup Wizard (Part 9.1)

The `setup_wizard.py` module must ask (and record answers to) these questions
during client onboarding.  Verify each question is implemented by reading the
code:

```
Q1.  What is your business name and industry?
Q2.  What is your primary revenue model?
Q3.  What is your target customer profile?
Q4.  What is your current monthly recurring revenue (MRR)?
Q5.  What are your top 3 business goals for the next 90 days?
Q6.  What manual processes do you most want to automate?
Q7.  How many employees will use the Murphy System?
Q8.  What integrations do you require? (CRM, email, accounting, etc.)
Q9.  What is your data residency requirement? (region)
Q10. Who is the primary technical contact?
Q11. What is your expected transaction volume per month?
Q12. What success metric defines "this is working" for you?
```

For each question, verify `setup_wizard.py` has a corresponding field or
prompt.  If any question is missing, add it with the minimal necessary change.

---

## Step-by-Step Procedure

### Step 1 — Apply Q1-Q10 to each module (read the code)

```bash
for module in setup_wizard agentic_onboarding_engine \
              production_deliverable_wizard onboarding_flow; do
    echo "=== $module ==="
    head -80 "Murphy System/src/${module}.py"
done
```

Answer Q1-Q10 for each module.  Record in the table below.

| Module | Q1 | Q2 | Q4 | Q6 | Q8 | Q9 | Q10 | Severity |
|--------|----|----|----|----|----|----|----|----------|
| setup_wizard.py | | | | | | | | |
| agentic_onboarding_engine.py | | | | | | | | |
| production_deliverable_wizard.py | | | | | | | | |
| onboarding_flow.py | | | | | | | | |

---

### Step 2 — Wire setup wizard endpoint

```python
# murphy_production_server.py
# [DOC-UPDATE: API_ROUTES.md, GETTING_STARTED.md]
@app.post("/api/onboarding/wizard")
async def run_setup_wizard(payload: dict):
    """Execute the 12-question setup wizard. ONBOARD-WIRE-001"""
    try:
        from src.setup_wizard import SetupWizard
        wizard = SetupWizard()
        result = wizard.run(payload)
        return {"status": "ok", "result": result}
    except Exception as e:  # ONBOARD-WIRE-ERR-001
        logger.error("setup_wizard endpoint error: %s", e)
        return {"status": "error", "detail": str(e)}, 500

@app.get("/api/onboarding/wizard/questions")
async def get_wizard_questions():
    """Return the list of 12 onboarding questions. ONBOARD-WIRE-002"""
    try:
        from src.setup_wizard import SetupWizard
        return {"questions": SetupWizard.QUESTIONS}
    except Exception as e:  # ONBOARD-WIRE-ERR-002
        logger.error("wizard questions error: %s", e)
        return {"status": "error", "detail": str(e)}, 500
```

---

### Step 3 — Wire agentic onboarding engine

```python
# murphy_production_server.py
# [DOC-UPDATE: API_ROUTES.md]
@app.post("/api/onboarding/start")
async def start_onboarding(payload: dict):
    """Start the automated onboarding pipeline. ONBOARD-WIRE-003"""
    try:
        from src.agentic_onboarding_engine import AgenticOnboardingEngine
        engine = AgenticOnboardingEngine()
        session = engine.start_onboarding(payload)
        # Trigger ROI Calendar event creation
        _create_roi_calendar_event(session)
        return {"status": "ok", "session": session}
    except Exception as e:  # ONBOARD-WIRE-ERR-003
        logger.error("agentic_onboarding_engine error: %s", e)
        return {"status": "error", "detail": str(e)}, 500
```

---

### Step 4 — ROI Calendar event creation on onboarding

When a new client onboards, create a task entry in the ROI Calendar:

```python
def _create_roi_calendar_event(session: dict) -> None:
    """Create ROI Calendar entry for a new onboarded client. ONBOARD-ROI-001"""
    try:
        import httpx
        event_payload = {
            "event_type": "client_onboarded",
            "client_id": session.get("client_id"),
            "description": f"New client onboarded: {session.get('business_name')}",
            "human_cost_estimate": session.get("estimated_setup_hours", 8.0),
        }
        # Internal call to ROI Calendar API
        httpx.post(
            "http://localhost:8000/api/roi-calendar/events",
            json=event_payload,
            timeout=5.0,
        )
    except Exception as _e:  # ONBOARD-ROI-ERR-001
        logger.warning("ROI Calendar event creation failed (non-blocking): %s", _e)
        # Non-blocking: onboarding continues even if ROI Calendar is unavailable
```

The ROI Calendar event must include:
- `human_cost_estimate` (hours of human labor equivalent)
- `event_type`: "client_onboarded"
- `client_id` and `description`

---

### Step 5 — Verify tiered runtime pack feature gating

```bash
python -c "
import sys
sys.path.insert(0, 'Murphy System/src')
# Check if tiered runtime pack logic exists
try:
    from src.modular_runtime import ModularRuntime
    print('ModularRuntime OK')
except ImportError as e:
    print(f'Import error: {e}')
"
```

Verify that the tiered runtime packs (free/starter/pro/enterprise) correctly
gate features.  Each tier should only expose features listed in the tier
specification.

---

### Step 6 — Verify tests

```bash
cd "Murphy System"
python -m pytest tests/onboarding/ -v --tb=short 2>&1 | tail -40
```

If tests are missing for any module, create minimal smoke tests following
the pattern in `tests/onboarding/test_agentic_onboarding_engine.py`.

---

### Record completion in tracker

```python
from src.prompt_execution_tracker import PromptExecutionTracker

tracker = PromptExecutionTracker()
tracker.mark_prompt_complete("04_WIRE_ONBOARDING_MODULES", results={
    "modules_wired": [
        "setup_wizard", "agentic_onboarding_engine",
        "production_deliverable_wizard", "onboarding_flow",
    ],
    "wizard_questions_verified": 12,
    "roi_calendar_integrated": True,
    "endpoints_added": [
        "/api/onboarding/wizard",
        "/api/onboarding/wizard/questions",
        "/api/onboarding/start",
    ],
    "citl_results": {"pass": 0, "fail": 0},
    "concept_blocks": ["Onboarding Module Wiring", "ROI Calendar Integration"],
    "doc_updates": ["GETTING_STARTED.md", "API_ROUTES.md", "CHANGELOG.md"],
})
```

---

## [DOC-UPDATE: GETTING_STARTED.md, API_ROUTES.md, CHANGELOG.md]

After completing this prompt, update:
- `GETTING_STARTED.md` — document the onboarding flow and wizard questions
- `API_ROUTES.md` — add all new onboarding endpoints
- `CHANGELOG.md` — add entry for onboarding module wiring
