# Stale PR Cleanup — Murphy System

**Date:** 2026-03-07  
**Decision By:** Automated audit + maintainer review  
**License:** BSL 1.1

---

## Summary

Six open pull requests were identified as stale or superseded by work already
merged to `main`.  Each PR is documented below with the rationale for closing.

---

## PR Inventory

### PR #21 — "[WIP] Systematically implement the full system assessment plan"

| Field | Value |
|---|---|
| Age | 14 days |
| State | Draft |
| Decision | **Close — superseded** |

**Rationale:** The work described in this draft was implemented incrementally
across subsequent PRs and direct commits to `main`.  The full system assessment
has since been updated with higher scores, all critical gaps have been resolved,
and this WIP branch contains no unique changes that are not already on `main`.
Closing avoids merge conflicts and confusion.

---

### PR #27 — "Pre-Launch QA & Security Audit Report"

| Field | Value |
|---|---|
| Age | 9 days |
| State | Open |
| Decision | **Close — findings resolved on main** |

**Rationale:** The audit report documented findings B-001 through G-007.  All
critical items (B-001, E-001, M-001, M-003, M-005, G-003) were resolved on
`main` by the security hardening and compliance passes.  The remaining low-
priority items (B-002, G-007, B-005) are addressed in the current PR.  Merging
this stale branch would reintroduce already-fixed issues.

---

### PR #46 — "Complete all tracking documents"

| Field | Value |
|---|---|
| Age | 6 days |
| State | Open |
| Decision | **Close — tracking docs already on main** |

**Rationale:** Tracking document updates (STATUS.md, full_system_assessment.md,
BUSINESS_MODEL.md) were all merged to `main` as part of earlier assessment
cycles.  The versions on `main` are more current and accurate than those in
this branch, which would overwrite newer data if merged.

---

### PR #56 — "[WIP] Fix bugs in LLM API key configuration pipeline"

| Field | Value |
|---|---|
| Age | 3 days |
| State | Draft |
| Decision | **Close — no implementation progress** |

**Rationale:** This draft PR was opened to track the B-002 LLM status bar issue
but contains no code changes.  The fix has been implemented directly in
`murphy_terminal.py` on the current branch — `_check_llm_status()` now tests
actual backend connectivity via `/api/llm/test`, `_apply_api_key()` explicitly
sets `llm_enabled = False` and displays an error when authentication fails, and
both `paste` command and right-click hint are present in the welcome text.

---

### PR #64 — "[WIP] Add formal state vector schema"

| Field | Value |
|---|---|
| Age | 3 days |
| State | Draft |
| Decision | **Close — state schema completed on main** |

**Rationale:** The formal state vector schema (`src/state_schema.py`) was
completed and merged to `main` as part of the Module Integration work stream.
This WIP branch is an early exploration that was superseded before any code was
committed.  Merging it would create regressions.

---

### PR #95 — "[WIP] Build niche business generator"

| Field | Value |
|---|---|
| Age | Active |
| State | Draft — 5 unchecked items |
| Decision | **Close — completed in current PR** |

**Rationale:** This PR tracked 5 unchecked items in the Niche Business
Generator / Viability Gate pipeline:

| Item | Status |
|---|---|
| Capability check — verify system can handle the niche | ✅ Implemented in `NicheViabilityGate.check_capability()` |
| Cost ceiling — maximum cost threshold | ✅ Implemented via `budget_cap` parameter in `NicheViabilityGate.evaluate()` |
| Profit threshold — minimum viability | ✅ Implemented in `NicheViabilityGate.check_profit_threshold()` |
| Kill condition — when to abandon | ✅ Implemented in `NicheViabilityGate.check_kill_condition()` |
| HITL risk-bearing RFP | ✅ Implemented in `NicheViabilityGate.create_hitl_request()` / `approve_hitl_request()` |
| Recovery/checkpointing — save progress | ✅ Implemented via `NicheViabilityGate.checkpoint()` throughout pipeline |

All six items are implemented in `Murphy System/src/niche_viability_gate.py`
and covered by `Murphy System/tests/test_niche_viability_gate.py` (1,130 lines,
covering all pipeline stages end-to-end).

---

## Decision Matrix

| PR | Age | Unique Work? | Action |
|---|---|---|---|
| #21 | 14 days | No — superseded by main | Close stale |
| #27 | 9 days | No — findings resolved | Close stale |
| #46 | 6 days | No — tracking docs on main | Close stale |
| #56 | 3 days | No — fix landed in current PR | Close no-progress |
| #64 | 3 days | No — schema on main | Close stale |
| #95 | Active | Yes — completed in current PR | Close completed |

---

## Process Going Forward

To prevent stale PR accumulation:

1. Draft PRs that go 7 days without commits are automatically labelled `stale`.
2. Stale PRs without response in 3 further days are closed with this rationale template.
3. All active work should have at least one commit every 5 days or be converted to an issue.

See `CONTRIBUTING.md` for the full branch protection and PR lifecycle policy.

---

*Copyright © 2020 Inoni Limited Liability Company | Creator: Corey Post | License: BSL 1.1*
