# Prompt 02 — RED_LINE Prioritization

> **Prerequisites:** Prompts 00 and 01 must pass.
> Read `IMMOVABLE_CONSTRAINTS.md` and `ENGINEERING_STANDARD.md` first.

---

## Goal

Apply RED_LINE operating mode prioritization (Part 8.1 + Part 12 Step 2).
Map every module to a priority tier and a Rosetta position.  Produce a
prioritized task list that drives the order of subsequent wiring prompts.

---

## Success Criteria

- [ ] All modules assigned to P1-P4 tiers
- [ ] Each tier mapped to Rosetta positions (CEO, CTO, VP Sales, VP Eng, CFO, CMO, COO)
- [ ] Guiding Principles filled for each position
- [ ] Tools (modules) assigned per `ceo_activation_plan.py` mapping
- [ ] CITL corrective constraints from known failures documented
- [ ] Prioritized task list produced

---

## Priority Tiers

### Priority 1 — Revenue Generation (RED_LINE)

> **Rosetta Position: VP Sales / CEO**
>
> Nothing else matters if AR = 0.  These modules must be wired and working
> before any P2-P4 work proceeds.

| Module | Purpose | Status |
|--------|---------|--------|
| `sales_automation.py` | Automated outreach and deal pipeline | ? |
| `self_selling_engine/` | Self-service demo and conversion funnel | ? |
| `outreach_campaign_planner.py` | Campaign scheduling and targeting | ? |
| `contact_compliance_governor.py` | CAN-SPAM/GDPR outreach compliance | ? |
| `inoni_business_automation.py` | Business process automation for clients | ? |
| `murphy_production_server.py` demo endpoints | Live demo for prospects | ? |

**Guiding Principles (VP Sales position):**
- Regulatory: CAN-SPAM, GDPR, CASL
- Domain best practice: value-first outreach, qualification gates
- Dominant character pillar: courage (make the ask), integrity (no dark patterns)
- Cornerstone directive: "guardians making creators' lives easier"

---

### Priority 2 — Client Onboarding

> **Rosetta Position: COO / VP Eng**
>
> Once a client signs, they must be able to onboard without friction.
> Broken onboarding = churn before first invoice.

| Module | Purpose | Status |
|--------|---------|--------|
| `setup_wizard.py` | 12-question intake wizard (Part 9.1) | ? |
| `agentic_onboarding_engine.py` | Automated onboarding flow execution | ? |
| `production_deliverable_wizard.py` | Deliverable configuration and delivery | ? |
| `onboarding_flow.py` | Onboarding pipeline orchestration | ? |
| Tiered runtime packs | Feature gating per subscription tier | ? |

**Guiding Principles (COO position):**
- Regulatory: data residency, privacy-by-design
- Domain best practice: time-to-value < 24 hours
- Dominant character pillar: diligence (complete every step), care (client experience)
- Cornerstone directive: "guardians making creators' lives easier"

---

### Priority 3 — Quality Assurance

> **Rosetta Position: CTO / VP Eng**
>
> Quality gates protect client trust and prevent regressions.

| Module | Purpose | Status |
|--------|---------|--------|
| `production_commissioning_validator.py` | Q1-Q10 automated checks | ? |
| `gate_behavior_model_engine.py` | Gate behavior validation | ? |
| `mfgc_core.py` | 7-phase generative control | ? |
| `information_quality.py` | Output quality assessment | ? |
| `prompt_amplifier.py` | MSS pipeline | ? |

**Guiding Principles (CTO position):**
- Regulatory: SOC 2, ISO 27001
- Domain best practice: test coverage ≥ 80%, quality floor ≥ 0.80
- Dominant character pillar: wisdom (choose the right solution), integrity
- Cornerstone directive: "guardians making creators' lives easier"

---

### Priority 4 — Everything Else

> **Rosetta Position: CFO / CMO**
>
> All remaining modules: analytics, reporting, advanced integrations, research
> engines, trading, gaming, etc.  Important but non-blocking for revenue.

---

## Steps

### Step 1 — Read `ceo_activation_plan.py` to verify module-to-role mapping

```bash
python -c "
import sys
sys.path.insert(0, 'Murphy System/src')
from src.ceo_activation_plan import *
# Print any exported role/module maps
import inspect
src_text = open('Murphy System/src/ceo_activation_plan.py').read()
print(src_text[:3000])
"
```

Map each function/class to a Rosetta position.  Update the tables above if
the actual code differs from the specification.

---

### Step 2 — Fill CITL corrective constraints from known failures

For each P0 or P1 issue found in Prompt 01, write a corrective constraint:

```
CITL-CONSTRAINT-<NNN>:
  Module: <module_name>
  Failure: <description of what failed>
  Archetype check: <what archetype violation caused this?>
  Element check: <what element-level error caused this?>
  Constraint: <the new guiding principle that prevents recurrence>
  Severity: P<0-4>
```

Record all constraints in `ENGINEERING_STANDARD.md` under the "Known CITL
Constraints" section.

---

### Step 3 — Produce prioritized task list

```
PRIORITIZED TASK LIST — RED_LINE MODE
======================================

P1 — REVENUE (must complete before AR = 0 becomes permanent)
  [ ] Wire sales_automation.py                → Prompt 03
  [ ] Wire self_selling_engine/               → Prompt 03
  [ ] Wire outreach_campaign_planner.py       → Prompt 03
  [ ] Wire contact_compliance_governor.py     → Prompt 03
  [ ] Wire inoni_business_automation.py       → Prompt 03

P2 — ONBOARDING (must complete before first client can be served)
  [ ] Wire setup_wizard.py (12-question)      → Prompt 04
  [ ] Wire agentic_onboarding_engine.py       → Prompt 04
  [ ] Wire production_deliverable_wizard.py   → Prompt 04
  [ ] Wire ROI Calendar event creation        → Prompt 04 + 06

P3 — QA (must complete before production release)
  [ ] Wire production_commissioning_validator → Prompt 05
  [ ] Wire mfgc_core.py 7-phase pipeline      → Prompt 05
  [ ] Wire information_quality.py             → Prompt 05
  [ ] Wire prompt_amplifier.py (MSS)          → Prompt 05
  [ ] Wire CITL dual-pass sensor              → Prompt 08

P4 — EVERYTHING ELSE
  [ ] ROI Calendar dashboard                  → Prompt 06
  [ ] CEO report hierarchy                    → Prompt 07
  [ ] Inference engine                        → Prompt 08
  [ ] UI simplification                       → Prompt 09
  [ ] Final report                            → Prompt 10
```

---

### Step 4 — Record completion in tracker

```python
from src.prompt_execution_tracker import PromptExecutionTracker

tracker = PromptExecutionTracker()
tracker.mark_prompt_complete("02_PRIORITIZE_RED_LINE", results={
    "p1_modules": [
        "sales_automation", "self_selling_engine",
        "outreach_campaign_planner", "contact_compliance_governor",
        "inoni_business_automation",
    ],
    "p2_modules": [
        "setup_wizard", "agentic_onboarding_engine",
        "production_deliverable_wizard",
    ],
    "p3_modules": [
        "production_commissioning_validator", "mfgc_core",
        "information_quality", "prompt_amplifier",
    ],
    "citl_constraints_written": 0,   # fill in actual count
    "concept_blocks": ["RED_LINE Priority Map", "Rosetta Position Assignments"],
    "doc_updates": ["CHANGELOG.md"],
})
```

---

## [DOC-UPDATE: CHANGELOG.md]

After completing this prompt, update:
- `CHANGELOG.md` — add entry for priority map creation
