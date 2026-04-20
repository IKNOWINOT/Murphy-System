# Murphy System Unified Operating Prompts

> **HOW TO USE**
>
> Each file in this directory is a self-contained, paste-and-execute prompt.
> Copy the prompt verbatim into your AI agent (or share it with the engineering
> team), execute every step top-to-bottom, and verify the stated success criteria
> before moving to the next prompt.
>
> **Before running any prompt**, read `IMMOVABLE_CONSTRAINTS.md` and
> `ENGINEERING_STANDARD.md` — every prompt is subject to all 6 immovable
> constraints and the Q1-Q10 commissioning standard.
>
> **Sync rule:** All edits are made inside `Murphy System/` first.  Root copies
> are kept byte-identical mirrors (`Murphy System/` → root).

---

## Execution Order & Table of Contents

| # | File | Goal |
|---|------|------|
| — | [`IMMOVABLE_CONSTRAINTS.md`](IMMOVABLE_CONSTRAINTS.md) | Reference card: 6 constraints every prompt must satisfy |
| — | [`ENGINEERING_STANDARD.md`](ENGINEERING_STANDARD.md) | Reference card: Q1-Q10, wiring checklist, `[DOC-UPDATE]` convention |
| 0 | [`00_PRIORITY_0_SYSTEM_BOOT.md`](00_PRIORITY_0_SYSTEM_BOOT.md) | **Boot health** — verify the system starts without error |
| 1 | [`01_SCAN_AND_AUDIT.md`](01_SCAN_AND_AUDIT.md) | **Full system audit** — commissioning Q1-Q10 per module, wiring map |
| 2 | [`02_PRIORITIZE_RED_LINE.md`](02_PRIORITIZE_RED_LINE.md) | **RED_LINE prioritization** — map modules to Rosetta positions P1-P4 |
| 3 | [`03_WIRE_REVENUE_MODULES.md`](03_WIRE_REVENUE_MODULES.md) | **Revenue wiring** — sales_automation, self_selling_engine, outreach |
| 4 | [`04_WIRE_ONBOARDING_MODULES.md`](04_WIRE_ONBOARDING_MODULES.md) | **Onboarding wiring** — setup_wizard, agentic_onboarding, deliverable_wizard |
| 5 | [`05_WIRE_QA_AND_GOVERNANCE.md`](05_WIRE_QA_AND_GOVERNANCE.md) | **QA + MFGC governance** — commissioning validator, 7-phase pipeline |
| 6 | [`06_WIRE_ROI_CALENDAR.md`](06_WIRE_ROI_CALENDAR.md) | **ROI Calendar** — unified dashboard, cost tracking, RBAC |
| 7 | [`07_WIRE_CEO_REPORT_HIERARCHY.md`](07_WIRE_CEO_REPORT_HIERARCHY.md) | **CEO report hierarchy** — CEO → VP → line report chain |
| 8 | [`08_WIRE_INFERENCE_AND_CITL.md`](08_WIRE_INFERENCE_AND_CITL.md) | **Inference + CITL** — inference_gate_engine, dual-level CITL loop |
| 9 | [`09_UI_SIMPLIFICATION_AUDIT.md`](09_UI_SIMPLIFICATION_AUDIT.md) | **UI audit** — role-based visibility, simplification opportunities |
| 10 | [`10_REPORT_AND_ITERATE.md`](10_REPORT_AND_ITERATE.md) | **Final report** — VP Eng report, CEO cycle, corrective constraints |

---

## Dependency Graph

```
IMMOVABLE_CONSTRAINTS  ←──  all prompts depend on this
ENGINEERING_STANDARD   ←──  all prompts depend on this
  00 (Boot)
   └─→ 01 (Audit)
        └─→ 02 (Prioritize)
              ├─→ 03 (Revenue)
              ├─→ 04 (Onboarding)
              ├─→ 05 (QA/Gov)
              ├─→ 06 (ROI Calendar)
              ├─→ 07 (CEO Report)
              └─→ 08 (Inference/CITL)
                    └─→ 09 (UI Audit)
                          └─→ 10 (Report & Iterate) ──→ feeds back to 00
```

---

## Tracking Execution

Use `src/prompt_execution_tracker.py` to record prompt completion status and
pending documentation updates:

```python
from src.prompt_execution_tracker import PromptExecutionTracker

tracker = PromptExecutionTracker()
tracker.mark_prompt_complete("00_PRIORITY_0_SYSTEM_BOOT", results={
    "boot_healthy": True,
    "concept_blocks": ["System Boot Health"],
})
print(tracker.get_execution_status())
print(tracker.get_pending_doc_updates())
```
