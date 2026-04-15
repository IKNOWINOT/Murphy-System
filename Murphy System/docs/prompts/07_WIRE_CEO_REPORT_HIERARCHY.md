# Prompt 07 — Wire CEO Report Hierarchy

> **Prerequisites:** Prompts 00-06 must pass.
> Read `IMMOVABLE_CONSTRAINTS.md` and `ENGINEERING_STANDARD.md` first.

---

## Goal

Wire the CEO → VP → Line report hierarchy (Part 3).  The CEO agent receives
consolidated Concept Block reports from all VP subsystems on every tick cycle.
This is the autonomous BAS-style regulation loop: sensors provide data, the
CEO agent evaluates against goals, and corrections are issued.

---

## Modules in Scope

1. `ceo_branch_activation.py` → `CEOBranch` — requests VP reports on tick
2. VP report generators: VP Engineering, VP Sales, CFO, CMO, COO
3. `analytics_dashboard.py` → `AnalyticsDashboard.get_full_report()`
4. `unified_observability_engine.py` → `compute_health_score()`
5. `rosetta_soul_renderer.py` → `RosettaSoulRenderer` (L0+L1 wake-up context)
6. `character_network_engine.py` → `CharacterAssessor`

---

## Success Criteria

- [ ] Q1-Q10 applied to each module
- [ ] `CEOBranch` requests VP reports on each tick cycle
- [ ] Each VP report generator wired and returning Concept Block reports
- [ ] `AnalyticsDashboard.get_full_report()` returns CEO dashboard data
- [ ] `compute_health_score()` included in System Health Concept Block
- [ ] `RosettaSoulRenderer` generates wake-up context at L0 and L1
- [ ] `CharacterAssessor` scores character profiles
- [ ] CI passes after changes

---

## Steps

### Step 1 — Apply Q1-Q10 to each module

```bash
for module in ceo_branch_activation analytics_dashboard \
              unified_observability_engine rosetta_soul_renderer \
              character_network_engine; do
    echo "=== $module ==="
    python -c "
import sys
sys.path.insert(0, 'Murphy System/src')
import importlib
m = importlib.import_module(f'src.{module}')
print([x for x in dir(m) if not x.startswith('_')])
"
done
```

---

### Step 2 — Wire CEOBranch tick cycle

```bash
python -c "
import sys
sys.path.insert(0, 'Murphy System/src')
from src.ceo_branch_activation import CEOBranch
import inspect
print(inspect.getsource(CEOBranch))
" | head -80
```

Verify `CEOBranch` has a `tick()` or `run_cycle()` method.  Wire it into the
heartbeat runner or scheduler:

```python
# In activated_heartbeat_runner.py or scheduler
# [DOC-UPDATE: ARCHITECTURE_MAP.md]
try:
    from src.ceo_branch_activation import CEOBranch
    ceo = CEOBranch()
    # On each heartbeat tick:
    report = ceo.tick()
    logger.info("CEO tick completed: %s", report.get("summary", ""))
except Exception as e:  # CEO-WIRE-ERR-001
    logger.error("CEOBranch tick error: %s", e)
```

---

### Step 3 — Wire VP report generators

For each VP position, there should be a report generation function.  Map them
by reading `ceo_activation_plan.py`:

```bash
python -c "
import sys
sys.path.insert(0, 'Murphy System/src')
import inspect
from src import ceo_activation_plan
print(inspect.getsource(ceo_activation_plan))
" | head -120
```

Expected VP report structure (Concept Block format):

```
VP ENGINEERING REPORT
  → Module Readiness: P0-P4 summary
  → Wiring Completeness: wired vs unwired
  → CI Status: pass/fail
  → CITL Results: pass/fail counts

VP SALES REPORT
  → Revenue Pipeline: AR, MRR, pipeline value
  → Campaign Performance: outreach metrics
  → Conversion Rate: demo → close

CFO REPORT
  → Cost vs Budget: actual vs projected
  → Burn Rate: monthly / runway
  → ROI: system cost vs human cost equivalent

CMO REPORT
  → Brand reach metrics
  → Content performance
  → Inbound lead volume

COO REPORT
  → Operational SLOs: met/missed
  → Client satisfaction
  → Onboarding velocity
```

---

### Step 4 — Wire analytics dashboard as CEO endpoint

```python
# murphy_production_server.py
# [DOC-UPDATE: API_ROUTES.md]
@app.get("/api/ceo/dashboard")
async def get_ceo_dashboard():
    """Return full CEO dashboard report. CEO-WIRE-001"""
    try:
        from src.analytics_dashboard import AnalyticsDashboard
        dashboard = AnalyticsDashboard()
        report = dashboard.get_full_report()
        return {"status": "ok", "report": report}
    except Exception as e:  # CEO-WIRE-ERR-001
        logger.error("CEO dashboard error: %s", e)
        return {"status": "error", "detail": str(e)}, 500

@app.get("/api/ceo/health-score")
async def get_system_health_score():
    """Return system health score. CEO-WIRE-002"""
    try:
        from src.unified_observability_engine import UnifiedObservabilityEngine
        engine = UnifiedObservabilityEngine()
        score = engine.compute_health_score()
        return {"status": "ok", "health_score": score}
    except Exception as e:  # CEO-WIRE-ERR-002
        logger.error("health-score endpoint error: %s", e)
        return {"status": "error", "detail": str(e)}, 500
```

---

### Step 5 — Wire Rosetta Soul Renderer (L0 + L1 wake-up context)

```bash
python -c "
import sys
sys.path.insert(0, 'Murphy System/src')
from src.rosetta_soul_renderer import RosettaSoulRenderer
r = RosettaSoulRenderer()
print(dir(r))
"
```

`RosettaSoulRenderer` must generate:
- **L0** (system-level): "What is the current operating mode and top priority?"
- **L1** (role-level): "What does this position need to know to act now?"

Wire into the CEO tick cycle:

```python
# [DOC-UPDATE: ARCHITECTURE_MAP.md]
try:
    from src.rosetta_soul_renderer import RosettaSoulRenderer
    renderer = RosettaSoulRenderer()
    l0_context = renderer.render(level=0)
    l1_context = renderer.render(level=1)
    logger.info("Rosetta wake-up L0: %s", l0_context.get("summary", ""))
except Exception as e:  # ROSETTA-WIRE-ERR-001
    logger.warning("RosettaSoulRenderer unavailable: %s", e)
```

---

### Step 6 — Wire CharacterAssessor for character profile scoring

```bash
python -c "
import sys
sys.path.insert(0, 'Murphy System/src')
from src.character_network_engine import CharacterAssessor
a = CharacterAssessor()
print(dir(a))
"
```

Wire `CharacterAssessor` into the CEO report's morality check
(moral_fiber ≥ 0.80 across all 8 pillars is an immovable constraint):

```python
# [DOC-UPDATE: ARCHITECTURE_MAP.md]
try:
    from src.character_network_engine import CharacterAssessor
    assessor = CharacterAssessor()
    profile = assessor.assess_current_state()
    if profile.moral_fiber < 0.80:
        logger.warning(  # CHAR-MORAL-WARN-001
            "Moral fiber %.2f below threshold 0.80 — flagging for review",
            profile.moral_fiber,
        )
except Exception as e:  # CHAR-WIRE-ERR-001
    logger.warning("CharacterAssessor unavailable: %s", e)
```

---

### Step 7 — Verify tests

```bash
cd "Murphy System"
python -m pytest tests/ -v -k "ceo or dashboard or analytics or observability or rosetta" \
    --tb=short 2>&1 | tail -40
```

---

### Record completion in tracker

```python
from src.prompt_execution_tracker import PromptExecutionTracker

tracker = PromptExecutionTracker()
tracker.mark_prompt_complete("07_WIRE_CEO_REPORT_HIERARCHY", results={
    "modules_wired": [
        "ceo_branch_activation", "analytics_dashboard",
        "unified_observability_engine", "rosetta_soul_renderer",
        "character_network_engine",
    ],
    "ceo_tick_active": True,
    "vp_reports_active": True,
    "concept_blocks": ["CEO Report Hierarchy", "VP Reporting Chain"],
    "doc_updates": ["ARCHITECTURE_MAP.md", "CHANGELOG.md"],
})
```

---

## [DOC-UPDATE: ARCHITECTURE_MAP.md, CHANGELOG.md]
