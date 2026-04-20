# Prompt 09 — UI Simplification Audit

> **Prerequisites:** Prompts 00-08 must pass.
> Read `IMMOVABLE_CONSTRAINTS.md` and `ENGINEERING_STANDARD.md` first.

---

## Goal

Audit and simplify UI interfaces per user type (Part 6.1).  Every user type
(owner, admin, operator, viewer) should see only what they need.  The ROI
Calendar must serve as the single-pane-of-glass for all roles.

---

## Success Criteria

- [ ] All HTML UI files inventoried
- [ ] Role-based visibility matrix produced for each UI file
- [ ] Gaps in current UI per role identified
- [ ] Simplification opportunities identified
- [ ] ROI Calendar assessed as unified dashboard
- [ ] VP Engineering Concept Block report produced
- [ ] No changes to UI without corresponding test or documented rationale

---

## Steps

### Step 1 — Inventory all HTML UI files

```bash
find "Murphy System/" -name "*.html" | sort | while read f; do
    size=$(wc -l < "$f")
    echo "$size  $f"
done | sort -rn | head -40
```

Key UI files to audit (from the specification):

| File | Purpose | Expected Users |
|------|---------|----------------|
| `roi_calendar.html` | Unified dashboard | all roles |
| `admin_panel.html` | System administration | owner, admin |
| `dashboard.html` | General dashboard | all roles |
| `crm.html` | CRM and sales | admin, operator |
| `hitl_dashboard.html` | HITL review queue | admin, operator |
| `terminal_enhanced.html` | Developer terminal | owner, admin |
| `onboarding_wizard.html` | Client onboarding | operator |
| `pricing.html` | Pricing page | viewer (public) |

---

### Step 2 — Check murphy_terminal.py USER_TYPE_UI_LINKS

```bash
python -c "
import sys
sys.path.insert(0, 'Murphy System/src')
import inspect
src_text = open('Murphy System/murphy_terminal.py').read()
# Find USER_TYPE_UI_LINKS definition
import re
match = re.search(r'USER_TYPE_UI_LINKS\s*=\s*\{.*?\}', src_text, re.DOTALL)
if match:
    print(match.group()[:2000])
else:
    print('USER_TYPE_UI_LINKS not found')
"
```

---

### Step 3 — Produce role-based visibility matrix

For each user type, list which UI files should be visible vs hidden:

```
ROLE-BASED UI VISIBILITY MATRIX
=================================

OWNER (full access)
  ✓ roi_calendar.html     — primary dashboard
  ✓ admin_panel.html      — system admin
  ✓ dashboard.html        — overview
  ✓ crm.html              — all CRM features
  ✓ hitl_dashboard.html   — review queue
  ✓ terminal_enhanced.html — dev terminal
  ✓ pricing.html          — pricing management

ADMIN
  ✓ roi_calendar.html     — primary dashboard
  ✓ admin_panel.html      — limited admin
  ✓ dashboard.html        — overview
  ✓ crm.html              — CRM features
  ✓ hitl_dashboard.html   — review queue
  ✗ terminal_enhanced.html — NOT visible
  ✗ pricing.html          — NOT visible

OPERATOR
  ✓ roi_calendar.html     — primary dashboard
  ✗ admin_panel.html      — NOT visible
  ✓ dashboard.html        — limited overview
  ✓ crm.html              — assigned contacts only
  ✓ hitl_dashboard.html   — assigned items only
  ✗ terminal_enhanced.html — NOT visible
  ✗ pricing.html          — NOT visible

VIEWER (read-only)
  ✓ roi_calendar.html     — summary view only
  ✗ admin_panel.html      — NOT visible
  ✓ dashboard.html        — read-only metrics
  ✗ crm.html              — NOT visible
  ✗ hitl_dashboard.html   — NOT visible
  ✗ terminal_enhanced.html — NOT visible
  ✓ pricing.html          — public pricing
```

Verify this matrix matches the actual `USER_TYPE_UI_LINKS` in
`murphy_terminal.py`.  Record any discrepancies.

---

### Step 4 — Assess ROI Calendar as unified dashboard

For each user type, verify the ROI Calendar provides:

| Feature | owner | admin | operator | viewer |
|---------|-------|-------|----------|--------|
| Current MRR display | ✓ | ✓ | ✓ | ✗ |
| Cost vs savings chart | ✓ | ✓ | ✓ | ✓ |
| ROI multiplier | ✓ | ✓ | ✓ | ✓ |
| Live event feed | ✓ | ✓ | ✓ | ✓ |
| Task creation | ✓ | ✓ | ✓ | ✗ |
| Export data | ✓ | ✓ | ✗ | ✗ |
| HITL review queue | ✓ | ✓ | ✓ | ✗ |
| System health score | ✓ | ✓ | ✗ | ✗ |

Check `roi_calendar.html` for each feature.  Record PRESENT / MISSING.

---

### Step 5 — Compare against successful AI dashboards

Evaluate the Murphy System UI against these principles derived from
well-designed AI product dashboards:

**What's working well:**
- Single-pane ROI view (if implemented)
- Cost vs. human labor comparison
- Live activity feed

**Common gaps to check for:**
- [ ] No onboarding progress indicator visible to owner
- [ ] No "next recommended action" prompt
- [ ] No mobile-responsive layout
- [ ] No dark/light mode toggle
- [ ] No keyboard shortcuts documented

**Simplification opportunities:**
- [ ] Can any two pages be merged without losing functionality?
- [ ] Are there any features visible to viewer that should be hidden?
- [ ] Are there any 3-click paths that could be 1-click?

---

### Step 6 — Produce VP Engineering Concept Block: UI Audit

```
╔══════════════════════════════════════════════════════════════╗
║  VP ENGINEERING CONCEPT BLOCK — UI SIMPLIFICATION AUDIT     ║
║  Generated: <timestamp>                                      ║
╠══════════════════════════════════════════════════════════════╣
║  CONCEPT BLOCK 1: UI COVERAGE                               ║
║    Total HTML files:               <count>                   ║
║    Files with role-gating:         <count>                   ║
║    Files WITHOUT role-gating:      <count> — <list>          ║
╠══════════════════════════════════════════════════════════════╣
║  CONCEPT BLOCK 2: MISSING ELEMENTS                          ║
║    Features missing per role:                                ║
║      owner:    <list>                                        ║
║      admin:    <list>                                        ║
║      operator: <list>                                        ║
║      viewer:   <list>                                        ║
╠══════════════════════════════════════════════════════════════╣
║  CONCEPT BLOCK 3: SIMPLIFICATION OPPORTUNITIES              ║
║    Pages that could be merged:     <list>                    ║
║    Overly complex views:           <list>                    ║
║    Hidden-element gaps:            <list>                    ║
╠══════════════════════════════════════════════════════════════╣
║  CONCEPT BLOCK 4: UNIFIED DASHBOARD STATUS                  ║
║    ROI Calendar as single-pane:    YES / PARTIAL / NO        ║
║    Missing ROI Calendar features:  <list>                    ║
╠══════════════════════════════════════════════════════════════╣
║  NEXT STEP → 10_REPORT_AND_ITERATE.md                       ║
╚══════════════════════════════════════════════════════════════╝
```

---

### Step 7 — Record completion in tracker

```python
from src.prompt_execution_tracker import PromptExecutionTracker

tracker = PromptExecutionTracker()
tracker.mark_prompt_complete("09_UI_SIMPLIFICATION_AUDIT", results={
    "html_files_audited": 0,    # fill in
    "role_gates_present": 0,
    "role_gates_missing": 0,
    "roi_calendar_complete": False,  # fill in
    "simplification_items": [],
    "concept_blocks": [
        "UI Coverage",
        "Missing Elements",
        "Simplification Opportunities",
        "Unified Dashboard Status",
    ],
    "doc_updates": ["USER_MANUAL.md", "CHANGELOG.md"],
})
```

---

## [DOC-UPDATE: USER_MANUAL.md, CHANGELOG.md]
