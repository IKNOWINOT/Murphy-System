# Prompt 03 — Wire Revenue Modules (Priority 1)

> **Prerequisites:** Prompts 00, 01, 02 must pass.
> Read `IMMOVABLE_CONSTRAINTS.md` and `ENGINEERING_STANDARD.md` first.

---

## Goal

Wire every Priority 1 revenue module into the production server.  **Surgical
changes only** — touch only what is needed to wire each module.  No silent
failures.

---

## Modules in Scope

1. `sales_automation.py`
2. `self_selling_engine/`
3. `outreach_campaign_planner.py`
4. `contact_compliance_governor.py`
5. `inoni_business_automation.py`

---

## Success Criteria (per module)

- [ ] Q1-Q10 answered from reading the code
- [ ] Module imported in VP Sales subsystem without error
- [ ] Health check registered in `status_probe`
- [ ] Events registered in `MODULE_MANIFEST`
- [ ] API endpoints registered in `murphy_production_server.py` (if applicable)
- [ ] Tests exist and pass
- [ ] Commissioning checklist complete
- [ ] CI passes after changes

---

## Wiring Checklist (apply to each module)

For each module, complete all 6 items:

```
WIRING CHECKLIST — <module_name>
=================================
[ ] 1. Import succeeds: python -c "from src.<module> import <MainClass>"
[ ] 2. Health check registered in status_probe or /api/health endpoint
[ ] 3. Events emitted by this module registered in MODULE_MANIFEST
[ ] 4. Events consumed by this module registered in MODULE_MANIFEST
[ ] 5. API endpoint added to murphy_production_server.py with try/except + logging
[ ] 6. Test file exists at tests/<category>/test_<module>.py and passes
```

---

## Step-by-Step Procedure (repeat for each module)

### For each module:

#### 1. Apply Q1-Q10 (read the code — code is primary truth)

```bash
python -c "
import pathlib
src = pathlib.Path('Murphy System/src/<module_name>.py')
print(src.read_text()[:5000])
"
```

Answer each question:
- **Q1:** Does the module do what it was designed to do?
- **Q2:** What exactly is the module supposed to do?
- **Q3:** What conditions are possible based on the module?
- **Q4:** Does the test profile reflect the full range of conditions?
- **Q5:** What is the expected result at all points of operation?
- **Q6:** What is the actual result?
- **Q7:** If there are problems, how do we restart from symptoms?
- **Q8:** What monitoring/alerting is in place?
- **Q9:** What documentation exists?
- **Q10:** What CITL constraints apply?

#### 2. Verify import in VP Sales subsystem

```python
# Verify no import errors
try:
    from src.sales_automation import SalesAutomation
    print("OK: SalesAutomation imported")
except ImportError as e:
    print(f"IMPORT ERROR: {e}")
    # Fix: add missing dependency or fix circular import
```

If the import fails, apply the smallest possible fix (missing `__init__.py`,
wrong relative path, etc.) and re-test.

#### 3. Register health check

In `murphy_production_server.py`, add to the `/api/health` endpoint handler:

```python
# [DOC-UPDATE: API_ROUTES.md]
try:
    from src.sales_automation import SalesAutomation  # REVENUE-WIRE-001
    _sa = SalesAutomation()
    health_checks["sales_automation"] = {"status": "ok"}
except Exception as _err:  # REVENUE-WIRE-ERR-001
    logger.error("sales_automation health check failed: %s", _err)
    health_checks["sales_automation"] = {"status": "error", "detail": str(_err)}
```

Apply the same pattern for every revenue module.

#### 4. Register events in MODULE_MANIFEST

Open `Murphy System/src/module_registry.yaml` (or equivalent) and add entries:

```yaml
sales_automation:
  produces:
    - event.sales.lead_created
    - event.sales.deal_closed
  consumes:
    - event.crm.contact_updated
  health_endpoint: /api/sales/health
```

#### 5. Register API endpoints

For each module that exposes callable functionality, add minimal endpoints:

```python
# murphy_production_server.py
# [DOC-UPDATE: API_ROUTES.md, ARCHITECTURE_MAP.md]
@app.post("/api/sales/outreach")
async def run_sales_outreach(payload: dict):
    """Trigger outreach campaign for a lead. REVENUE-WIRE-002"""
    try:
        from src.outreach_campaign_planner import OutreachCampaignPlanner
        planner = OutreachCampaignPlanner()
        result = planner.create_campaign(payload)
        return {"status": "ok", "result": result}
    except Exception as e:  # REVENUE-WIRE-ERR-002
        logger.error("outreach endpoint error: %s", e)
        return {"status": "error", "detail": str(e)}, 500
```

**Important:** Every endpoint must have:
- A try/except block
- A labeled error code in the except comment
- A `logger.error(...)` call
- A meaningful error response (never a bare 500 with no body)

#### 6. Verify tests exist and pass

```bash
cd "Murphy System"
python -m pytest tests/crm_sales/ -v -k "sales or outreach or automation" 2>&1
```

If tests do not exist, create minimal smoke tests:

```python
# Murphy System/tests/crm_sales/test_sales_automation.py
"""Smoke tests for sales_automation module — REVENUE-TEST-001"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

def test_sales_automation_import():
    from src.sales_automation import SalesAutomation
    assert SalesAutomation is not None

def test_outreach_campaign_planner_import():
    from src.outreach_campaign_planner import OutreachCampaignPlanner
    assert OutreachCampaignPlanner is not None

def test_contact_compliance_governor_import():
    from src.contact_compliance_governor import ContactComplianceGovernor
    assert ContactComplianceGovernor is not None
```

---

## Module-Specific Notes

### `sales_automation.py`
- Verify `SalesAutomation` class has `run()` or equivalent entry point
- Check CAN-SPAM compliance headers in outreach functions

### `self_selling_engine/`
- This is a sub-package; check `self_selling_engine/__init__.py` exports
- Verify demo endpoints in `murphy_production_server.py` reference this package

### `outreach_campaign_planner.py`
- Verify campaign scheduling integrates with `automation_scheduler.py`
- Check GDPR consent flags are checked before sending

### `contact_compliance_governor.py`
- This is a compliance module — Q8 (monitoring) is especially critical
- Ensure every contact_compliance check logs its decision

### `inoni_business_automation.py`
- Root copy at `/inoni_business_automation.py` must mirror `Murphy System/` copy
- Verify both files are byte-identical after any change

---

## Final Verification

```bash
cd "Murphy System"
python -m pytest tests/ -v -k "sales or outreach or automation or compliance" \
    --tb=short 2>&1 | tail -30
```

All tests must pass.  CI must pass.

---

### Record completion in tracker

```python
from src.prompt_execution_tracker import PromptExecutionTracker

tracker = PromptExecutionTracker()
tracker.mark_prompt_complete("03_WIRE_REVENUE_MODULES", results={
    "modules_wired": [
        "sales_automation", "self_selling_engine",
        "outreach_campaign_planner", "contact_compliance_governor",
        "inoni_business_automation",
    ],
    "endpoints_added": [],    # list endpoint paths added
    "tests_added": [],        # list test files added/updated
    "citl_results": {"pass": 0, "fail": 0},
    "concept_blocks": ["Revenue Module Wiring"],
    "doc_updates": ["API_ROUTES.md", "ARCHITECTURE_MAP.md", "CHANGELOG.md"],
})
```

---

## [DOC-UPDATE: API_ROUTES.md, ARCHITECTURE_MAP.md, CHANGELOG.md]

After completing this prompt, update:
- `API_ROUTES.md` — add all new endpoints
- `ARCHITECTURE_MAP.md` — mark revenue modules as wired
- `CHANGELOG.md` — add entry for revenue module wiring
