# Prompt 10 — Final Report and Iterate

> **Prerequisites:** Prompts 00-09 must all pass.
> Read `IMMOVABLE_CONSTRAINTS.md` and `ENGINEERING_STANDARD.md` first.

---

## Goal

Produce the final VP Engineering Report, feed it to the CEO agent cycle, and
determine whether to declare the sprint complete or re-prioritize (Part 12
Steps 4-5).  Write corrective constraints for any remaining CITL failures.
Update all `[DOC-UPDATE]` tagged documentation.

---

## Success Criteria

- [ ] Final VP Engineering Report produced with all Concept Blocks
- [ ] CEO cycle evaluation complete
- [ ] AR > 0 check performed (if AR = 0, re-prioritize Sales)
- [ ] ROI summary generated
- [ ] All CITL failures have corrective constraints written
- [ ] All `[DOC-UPDATE]` tags resolved (files updated)
- [ ] `PromptExecutionTracker` shows all 11 prompts as complete
- [ ] CI passes

---

## Steps

### Step 1 — Retrieve all prompt execution results

```python
from src.prompt_execution_tracker import PromptExecutionTracker

tracker = PromptExecutionTracker()
status = tracker.get_execution_status()
print(status)

pending_docs = tracker.get_pending_doc_updates()
print("Pending doc updates:", pending_docs)
```

Verify all 11 prompts (00-09 + this one) are recorded.  If any are missing,
re-run the corresponding prompt before continuing.

---

### Step 2 — Check AR > 0 (Revenue Gate)

```python
# Query the CEO dashboard for current AR/MRR
import httpx
try:
    r = httpx.get("http://localhost:8000/api/ceo/dashboard", timeout=10)
    data = r.json()
    ar = data.get("report", {}).get("vp_sales", {}).get("accounts_receivable", 0)
    mrr = data.get("report", {}).get("vp_sales", {}).get("mrr", 0)
    print(f"AR: ${ar:,.2f}")
    print(f"MRR: ${mrr:,.2f}")
    if ar == 0 and mrr == 0:
        print("⚠️  AR = 0 and MRR = 0 — RE-PRIORITIZE SALES/MARKETING")
        print("   Return to Prompt 03 (Wire Revenue Modules) and verify:")
        print("   1. Outreach campaigns are running")
        print("   2. Demo endpoints are reachable by prospects")
        print("   3. Contact compliance governor is not blocking all outreach")
    else:
        print("✅ Revenue > 0 — proceed to documentation updates")
except Exception as e:
    print(f"Could not reach CEO dashboard: {e}")
    print("Run from the server or check the API endpoint")
```

**If AR = 0:**
1. Re-run Prompt 03 (Wire Revenue Modules)
2. Check that outreach campaigns are configured and running
3. Check that the self_selling_engine demo is accessible
4. Return to this prompt only after AR > 0

---

### Step 3 — Generate ROI summary

```python
# Calculate the human labor equivalent for all work done
import httpx
try:
    r = httpx.get("http://localhost:8000/api/roi-calendar/summary", timeout=10)
    roi = r.json().get("summary", {})
    human_hours = roi.get("human_cost_total", 0)
    system_cost = roi.get("actual_system_cost", 0)
    multiplier = roi.get("roi_multiplier", 0)
    print(f"Human labor equivalent:  {human_hours:.1f} hours")
    print(f"Actual system cost:      ${system_cost:.2f}")
    print(f"ROI multiplier:          {multiplier:.1f}x")
except Exception as e:
    print(f"Could not reach ROI Calendar: {e}")
```

---

### Step 4 — Write corrective constraints for remaining CITL failures

```python
from src.prompt_execution_tracker import PromptExecutionTracker

tracker = PromptExecutionTracker()
status = tracker.get_execution_status()

for prompt_id, data in status.get("prompts", {}).items():
    citl = data.get("citl_results", {})
    if citl.get("fail", 0) > 0:
        print(f"CITL failures in {prompt_id}: {citl['fail']}")
        print("  Write corrective constraints for each failure in ENGINEERING_STANDARD.md")
```

For each CITL failure, add a `CITL-CONSTRAINT-<NNN>` entry to
`ENGINEERING_STANDARD.md` under "Known CITL Constraints".

---

### Step 5 — Resolve all [DOC-UPDATE] tags

```python
from src.prompt_execution_tracker import PromptExecutionTracker

tracker = PromptExecutionTracker()
pending = tracker.get_pending_doc_updates()

print("Documentation files that need updating:")
for doc in sorted(pending):
    print(f"  [ ] {doc}")
```

For each pending document, open it and add the relevant changes.

**Minimum required updates after completing all prompts:**

| Document | What to add |
|----------|-------------|
| `STATUS.md` | Boot health, audit results, wiring status, date |
| `CHANGELOG.md` | Entry for each prompt completed, each module wired |
| `ARCHITECTURE_MAP.md` | Updated wiring map showing all wired modules |
| `API_ROUTES.md` | All new endpoints added in Prompts 03-08 |
| `GETTING_STARTED.md` | Updated onboarding flow with 12 wizard questions |
| `USER_MANUAL.md` | ROI Calendar usage, role-based access guide |
| `ROADMAP.md` | Mark completed items, update next priorities |

---

### Step 6 — Produce Final VP Engineering Report

```
╔══════════════════════════════════════════════════════════════╗
║  FINAL VP ENGINEERING REPORT — SPRINT COMPLETE              ║
║  Generated: <timestamp>                                      ║
╠══════════════════════════════════════════════════════════════╣
║  CONCEPT BLOCK 1: SYSTEM BOOT HEALTH                        ║
║    (from Prompt 00 results)                                  ║
╠══════════════════════════════════════════════════════════════╣
║  CONCEPT BLOCK 2: SYSTEM AUDIT SUMMARY                      ║
║    Modules audited:          <count>                         ║
║    P0 remaining:             <count>                         ║
║    P1 remaining:             <count>                         ║
╠══════════════════════════════════════════════════════════════╣
║  CONCEPT BLOCK 3: MODULE WIRING COMPLETE                    ║
║    P1 Revenue modules wired: <count> / <total>               ║
║    P2 Onboarding modules:    <count> / <total>               ║
║    P3 QA/Gov modules:        <count> / <total>               ║
╠══════════════════════════════════════════════════════════════╣
║  CONCEPT BLOCK 4: QUALITY AND GOVERNANCE                    ║
║    MFGC pipeline: ACTIVE / INACTIVE                          ║
║    CITL Level 1:  ACTIVE / INACTIVE                          ║
║    CITL Level 2:  ACTIVE / INACTIVE                          ║
║    Quality floor ≥ 0.80: ENFORCED / NOT ENFORCED            ║
║    HITL escalation: ACTIVE / INACTIVE                        ║
╠══════════════════════════════════════════════════════════════╣
║  CONCEPT BLOCK 5: REVENUE STATUS                            ║
║    AR:  $<amount>                                            ║
║    MRR: $<amount>                                            ║
║    Status: REVENUE_GENERATING / RED_LINE (AR=0)              ║
╠══════════════════════════════════════════════════════════════╣
║  CONCEPT BLOCK 6: ROI SUMMARY                               ║
║    Human labor equivalent: <hours> hours                     ║
║    Actual system cost:     $<amount>                         ║
║    ROI multiplier:         <N>x                              ║
╠══════════════════════════════════════════════════════════════╣
║  CONCEPT BLOCK 7: DOCUMENTATION STATUS                      ║
║    Pending DOC-UPDATE items: <count>                         ║
║    Resolved DOC-UPDATE items: <count>                        ║
╠══════════════════════════════════════════════════════════════╣
║  CONCEPT BLOCK 8: CITL CORRECTIVE CONSTRAINTS               ║
║    Constraints written this sprint: <count>                  ║
║    Open constraints (not yet resolved): <count>              ║
╠══════════════════════════════════════════════════════════════╣
║  OPERATING MODE RECOMMENDATION                               ║
║    Current: RED_LINE / STANDARD / LEARNING                   ║
║    Recommended: <mode and rationale>                         ║
╠══════════════════════════════════════════════════════════════╣
║  NEXT SPRINT PRIORITIES                                      ║
║    1. <highest priority item>                                ║
║    2. <second priority item>                                 ║
║    3. <third priority item>                                  ║
╠══════════════════════════════════════════════════════════════╣
║  FEEDS BACK TO: 00_PRIORITY_0_SYSTEM_BOOT.md (next cycle)   ║
╚══════════════════════════════════════════════════════════════╝
```

---

### Step 7 — Record completion in tracker

```python
from src.prompt_execution_tracker import PromptExecutionTracker

tracker = PromptExecutionTracker()
tracker.mark_prompt_complete("10_REPORT_AND_ITERATE", results={
    "ar_positive": False,         # fill in
    "human_hours_equivalent": 0,  # fill in
    "actual_system_cost": 0.0,    # fill in
    "roi_multiplier": 0.0,        # fill in
    "citl_constraints_total": 0,  # fill in
    "doc_updates_resolved": [],   # list of docs updated
    "doc_updates_pending": [],    # list of docs still pending
    "concept_blocks": [
        "System Boot Health",
        "System Audit Summary",
        "Module Wiring Complete",
        "Quality and Governance",
        "Revenue Status",
        "ROI Summary",
        "Documentation Status",
        "CITL Corrective Constraints",
    ],
    "doc_updates": ["STATUS.md", "CHANGELOG.md", "ROADMAP.md"],
})

# Print final status
print(tracker.get_execution_status())
```

---

## [DOC-UPDATE: STATUS.md, CHANGELOG.md, ROADMAP.md]

After completing this prompt, update:
- `STATUS.md` — final system status, date, operating mode
- `CHANGELOG.md` — add entry for sprint completion
- `ROADMAP.md` — mark completed items, set next sprint priorities
