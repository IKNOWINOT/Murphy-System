# Prompt 01 — Full System Audit

> **Prerequisites:** Prompt 00 must pass completely before running this prompt.
> Read `IMMOVABLE_CONSTRAINTS.md` and `ENGINEERING_STANDARD.md` first.

---

## Goal

Produce the full system audit as described in the MURPHY SYSTEM UNIFIED
OPERATING PROMPT, Part 12 Step 1.  Every module in `Murphy System/src/` is
evaluated against Q1-Q10.  All wiring, event chains, and test coverage are
mapped.

---

## Success Criteria

- [ ] Q1-Q10 commissioning results recorded for every module in `src/`
- [ ] `tests/wiring_validation/` checks (G1-G9) executed and results recorded
- [ ] `MODULE_MANIFEST` scanned for orphan event producers/consumers
- [ ] `murphy_production_server.py` endpoints mapped (registered vs unregistered)
- [ ] VP Engineering Report produced with 4 Concept Blocks
- [ ] `[DOC-UPDATE]` tags added to all changed files
- [ ] No silent failures — every scan operation logged

---

## Steps

### Step 1 — Run the commissioning validator

```bash
cd "Murphy System"
python -c "
import sys
sys.path.insert(0, 'src')
from src.production_commissioning_validator import CommissioningValidator
v = CommissioningValidator()
results = v.validate_all()
import json
print(json.dumps(results, indent=2, default=str))
" 2>&1 | tee /tmp/commissioning_results.json
```

If `CommissioningValidator` does not yet exist or does not have a
`validate_all()` method, answer Q1-Q10 manually for each module by reading
the source.  Record results in the table in Step 5.

---

### Step 2 — Run wiring validation suite

```bash
cd "Murphy System"
python -m pytest tests/wiring_validation/ -v 2>&1 | tee /tmp/wiring_results.txt
```

Expected checks (G1-G9 from the COMMISSIONING_CHECKLIST.md):
- G1: All modules importable without crash
- G2: All health-check endpoints respond
- G3: Event producers match consumers in MODULE_MANIFEST
- G4: All registered API routes reachable
- G5: No dead-letter subscriptions
- G6: Required environment variables present
- G7: Database migrations in sync
- G8: No dangling foreign keys
- G9: CI and source-drift guard passing

Record PASS/FAIL per check.

---

### Step 3 — Scan MODULE_MANIFEST for orphan events

```bash
python -c "
import pathlib, re, json

src = pathlib.Path('Murphy System/src')
manifest_path = src / 'module_registry.yaml'
if manifest_path.exists():
    import yaml
    manifest = yaml.safe_load(manifest_path.read_text())
    print(json.dumps(manifest, indent=2, default=str))
else:
    print('MODULE_MANIFEST not found at', manifest_path)
    # Fall back: scan for emit/subscribe patterns
    producers = set()
    consumers = set()
    for f in src.rglob('*.py'):
        text = f.read_text(errors='ignore')
        producers.update(re.findall(r'emit\([\"\']([\w.]+)', text))
        consumers.update(re.findall(r'subscribe\([\"\']([\w.]+)', text))
    orphan_producers = producers - consumers
    orphan_consumers = consumers - producers
    print('Orphan producers:', sorted(orphan_producers))
    print('Orphan consumers:', sorted(orphan_consumers))
"
```

---

### Step 4 — Map registered vs unregistered endpoints

```bash
python -c "
import ast, pathlib, re

server = pathlib.Path('murphy_production_server.py')
if not server.exists():
    server = pathlib.Path('Murphy System/murphy_production_server.py')

text = server.read_text(errors='ignore')
routes = re.findall(r'@app\.(get|post|put|delete|patch)\([\"\'](.*?)[\"\']\)', text)
print(f'Total registered routes: {len(routes)}')
for method, path in sorted(routes, key=lambda x: x[1]):
    print(f'  {method.upper():6s}  {path}')
"
```

---

### Step 5 — Q1-Q10 results table (fill in from scans above)

| Module | Q1 ✓ | Q4 ✓ | Q5 ✓ | Q6 ✓ | Q8 ✓ | Q9 ✓ | Q10 ✓ | Severity |
|--------|------|------|------|------|------|------|-------|----------|
| sales_automation.py | | | | | | | | |
| self_selling_engine/ | | | | | | | | |
| outreach_campaign_planner.py | | | | | | | | |
| setup_wizard.py | | | | | | | | |
| agentic_onboarding_engine.py | | | | | | | | |
| production_deliverable_wizard.py | | | | | | | | |
| production_commissioning_validator.py | | | | | | | | |
| mfgc_core.py | | | | | | | | |
| information_quality.py | | | | | | | | |
| prompt_amplifier.py | | | | | | | | |
| inference_gate_engine.py | | | | | | | | |
| cost_explosion_gate.py | | | | | | | | |
| cost_optimization_advisor.py | | | | | | | | |
| ceo_branch_activation.py | | | | | | | | |
| analytics_dashboard.py | | | | | | | | |
| unified_observability_engine.py | | | | | | | | |
| rosetta_soul_renderer.py | | | | | | | | |
| character_network_engine.py | | | | | | | | |
| prompt_execution_tracker.py | | | | | | | | |

Add rows for every other module in `src/`.

---

### Step 6 — Produce VP Engineering Report

```
╔══════════════════════════════════════════════════════════════╗
║  VP ENGINEERING REPORT — FULL SYSTEM AUDIT                  ║
║  Generated: <timestamp>                                      ║
╠══════════════════════════════════════════════════════════════╣
║  CONCEPT BLOCK 1: MODULE READINESS                          ║
║    P0 modules (boot-blocking):    <count> — <list>           ║
║    P1 modules (feature-blocking): <count> — <list>           ║
║    P2 modules (degraded):         <count> — <list>           ║
║    P3-P4 modules (minor/info):    <count>                    ║
╠══════════════════════════════════════════════════════════════╣
║  CONCEPT BLOCK 2: WIRING COMPLETENESS                       ║
║    Modules wired to production server: <count>               ║
║    Modules NOT wired:                  <count> — <list>      ║
║    G1-G9 results: <PASS/FAIL per check>                      ║
╠══════════════════════════════════════════════════════════════╣
║  CONCEPT BLOCK 3: EVENT CHAIN INTEGRITY                     ║
║    Orphan event producers: <count> — <list>                  ║
║    Disconnected subscriptions: <count> — <list>              ║
╠══════════════════════════════════════════════════════════════╣
║  CONCEPT BLOCK 4: TEST COVERAGE                             ║
║    Modules with tests:    <count>                            ║
║    Modules WITHOUT tests: <count> — <list>                   ║
╠══════════════════════════════════════════════════════════════╣
║  NEXT STEP → 02_PRIORITIZE_RED_LINE.md                      ║
╚══════════════════════════════════════════════════════════════╝
```

---

### Step 7 — Record completion in tracker

```python
from src.prompt_execution_tracker import PromptExecutionTracker

tracker = PromptExecutionTracker()
tracker.mark_prompt_complete("01_SCAN_AND_AUDIT", results={
    "modules_audited": 0,          # fill in actual count
    "p0_count": 0,
    "p1_count": 0,
    "wiring_pass": 0,
    "wiring_fail": 0,
    "orphan_events": [],
    "concept_blocks": [
        "Module Readiness",
        "Wiring Completeness",
        "Event Chain Integrity",
        "Test Coverage",
    ],
    "doc_updates": [
        "ARCHITECTURE_MAP.md",
        "STATUS.md",
        "CHANGELOG.md",
    ],
})
```

---

## [DOC-UPDATE: ARCHITECTURE_MAP.md, STATUS.md, CHANGELOG.md]

After completing this prompt, update:
- `ARCHITECTURE_MAP.md` — reflect current wiring state
- `STATUS.md` — record audit results and date
- `CHANGELOG.md` — add entry for audit completion
