# Murphy System Remediation Plan — Cycle 1

**Date:** 2026-02-26
**Source:** [Gap Analysis — Cycle 1](GAP_ANALYSIS.md)
**Repository:** IKNOWINOT/Murphy-System
**Runtime Directory:** `Murphy System/`

---

## Executive Summary

This plan provides concrete steps to close every gap identified in the Cycle 1 Gap Analysis. The remediation follows a priority order: fix what blocks the most downstream tasks first. After each fix is applied the affected component re-enters the **Test → Document → Fix → Retest** cycle until it passes.

**Goal:** Bring Murphy System from the current 78% operational state to **100% seamless operation** — including post-launch automation capabilities.

---

## 1. Remediation Priority Order

| Priority | Gap ID | Issue | Blocks | Effort |
|----------|--------|-------|--------|--------|
| P0 | GAP-002 | LLM features blocked without real API key | All content generation, task execution | Configuration only |
| P1 | GAP-001a | Inoni Business Automation not initialised | `/api/automation/*` endpoints, content gen, sales, marketing | Debug import chain |
| P1 | GAP-001b | Integration Engine not initialised | External service connections, Discord, Product Hunt | Debug import chain |
| P1 | GAP-001c | Control Plane not initialised | Unified control surface | Debug import chain |
| P1 | GAP-001d | Two-Phase Orchestrator not initialised | Setup → Execute pipeline | Debug import chain |
| P2 | GAP-003 | Compute Plane — 2 test failures | Edge-case reliability | Code fix |
| P3 | GAP-004 | No image generation capability | Logo generation only | Design decision |
| P4 | — | 6,254 deprecation warnings | Code hygiene | Incremental cleanup |

---

## 2. Detailed Remediation Steps

### REM-001: Configure Real LLM API Key (GAP-002)

**Priority:** P0 — Unblocks all LLM-dependent features

**Steps:**

1. Obtain a free Groq API key from https://console.groq.com/keys
2. Update `Murphy System/.env`:
   ```
   GROQ_API_KEY=gsk_your_real_key_here
   ```
3. Restart Murphy System
4. Verify confidence scores rise above 0.50 for basic tasks
5. Test `/api/execute` with a simple prompt — expect `status: "completed"`

**Acceptance Criteria:**
- [ ] `/api/execute` returns `status: "completed"` for a simple task
- [ ] Confidence score > 0.50 with real LLM backend
- [ ] Chat endpoint returns coherent LLM-generated responses

**Owner:** System operator (requires external account creation)

---

### REM-002: Debug Inoni Business Automation Init (GAP-001a)

**Priority:** P1 — Unblocks all `/api/automation/*` endpoints

**Steps:**

1. Identify the import failure:
   ```bash
   cd "Murphy System"
   python3 -c "import inoni_business_automation" 2>&1
   ```
2. Trace the missing dependency or module
3. Either:
   - Install the missing package, OR
   - Add a graceful fallback that provides basic automation without the full engine
4. Restart Murphy and verify `/api/automation/content/generate` returns a response
5. Update `EXECUTION_LOG.md` with the finding

**Acceptance Criteria:**
- [ ] `inoni_automation` shows `active` in `/api/status`
- [ ] `/api/automation/content/generate` returns success
- [ ] `/api/automation/sales/analyze` returns success

---

### REM-003: Debug Integration Engine Init (GAP-001b)

**Priority:** P1 — Unblocks external service connections

**Steps:**

1. Identify the import failure:
   ```bash
   cd "Murphy System"
   python3 -c "
   import sys; sys.path.insert(0, 'src')
   from integration_engine import IntegrationEngine
   " 2>&1
   ```
2. Resolve missing dependencies
3. Restart and verify `integration_engine: active` in `/api/status`

**Acceptance Criteria:**
- [ ] Integration Engine shows `active` in `/api/status`
- [ ] `/api/integrations/add` accepts integration requests

---

### REM-004: Debug Control Plane Init (GAP-001c)

**Priority:** P1

**Steps:**

1. Identify the import failure for the Universal Control Plane
2. Resolve missing dependencies or configuration
3. Restart and verify `control_plane: active` in `/api/status`

**Acceptance Criteria:**
- [ ] Control Plane shows `active` in `/api/status`

---

### REM-005: Debug Two-Phase Orchestrator Init (GAP-001d)

**Priority:** P1

**Steps:**

1. Identify the import failure for the Two-Phase Orchestrator
2. Resolve missing dependencies
3. Restart and verify `orchestrator: active` in `/api/status`

**Acceptance Criteria:**
- [ ] Orchestrator shows `active` in `/api/status`
- [ ] Task execution uses setup → execute pipeline

---

### REM-006: Fix Compute Plane Test Failures (GAP-003)

**Priority:** P2

**Failing Tests:**

1. `test_metadata_none_is_normalized_for_sympy_execution`
   - **Fix:** Add null-guard for `metadata` parameter in the sympy execution path
   - **Location:** `src/compute_plane/` — sympy handler

2. `test_submit_request_prevents_caller_mutation_of_queued_request`
   - **Fix:** Investigate worker thread startup; ensure queue processing completes within timeout
   - **Location:** `src/compute_plane/` — request queue handler

**Acceptance Criteria:**
- [ ] Both tests pass
- [ ] No regression in other compute-plane tests

---

### REM-007: Document Image Generation Limitation (GAP-004)

**Priority:** P3

**Steps:**

1. Update Launch Automation Plan § 2.1 dead-end tracking:
   - Issue: No built-in image generation capability
   - Alternative: Use external tools (DALL-E API, Midjourney, Canva) or add image-gen adapter
   - Status: ❌ Dead end for automated generation; manual fallback required
2. Optionally: design an image-generation adapter for future integration

**Acceptance Criteria:**
- [ ] Dead End Tracking table updated in `LAUNCH_AUTOMATION_PLAN.md`

---

### REM-008: Clean Up Deprecation Warnings (P4)

**Priority:** P4 — Code hygiene

**Key fixes:**

1. Replace `datetime.utcnow()` with `datetime.now(datetime.UTC)` across affected modules
2. Replace `ast.Num` / `node.n` with `ast.Constant` / `node.value` in `verification_layer.py`
3. Update Pydantic models from `schema_extra` to `json_schema_extra`

**Acceptance Criteria:**
- [ ] Warning count reduced by ≥ 50%

---

## 3. Post-Launch Automation Remediation

These steps ensure Murphy can automate its own operations after launch:

### REM-009: Validate End-to-End Automation Flow

After REM-001 through REM-005 are complete:

1. **Schedule a recurring task** via the Automation Scheduler:
   ```
   POST /api/execute
   {"task": "Generate daily operations summary", "type": "content_generation", "schedule": "daily"}
   ```
2. **Verify the Self-Improvement Engine** records outcomes and proposes improvements
3. **Verify the SLO Tracker** records latency and success metrics
4. **Verify the Event Backbone** publishes lifecycle events (TASK_SUBMITTED → TASK_COMPLETED)
5. **Test the Delivery Orchestrator** sends results through at least one channel

### REM-010: Create Automated Operations Workflow

Define a post-launch operations workflow that Murphy runs continuously:

| Step | Action | Mechanism | Frequency |
|------|--------|-----------|-----------|
| 1 | Health check | `/api/health` → SLO Tracker | Every 5 minutes |
| 2 | Component audit | `/api/diagnostics/activation` | Every hour |
| 3 | Performance metrics | SLO Tracker → Event Backbone | Continuous |
| 4 | Bug detection | Self-Improvement Engine analysis | After each task |
| 5 | Compliance check | Compliance Engine scan | Daily |
| 6 | Status report generation | Content gen → Delivery Orchestrator | Daily |
| 7 | Gap re-analysis | Compare metrics vs targets | Weekly |

---

## 4. Iteration Cycle

After each remediation is applied, the cycle repeats:

```
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│   ┌────────────┐    ┌──────────┐    ┌────────────────┐       │
│   │ Apply Fix  ├───►│ Restart  ├───►│ Test Endpoint  │       │
│   └────────────┘    │ Murphy   │    │ / Run Tests    │       │
│         ▲           └──────────┘    └───────┬────────┘       │
│         │                                   │                │
│         │           ┌──────────┐    ┌───────▼────────┐       │
│         └───────────┤  Update  │◄───┤ Document       │       │
│                     │  Docs    │    │ Results        │       │
│                     └────┬─────┘    └────────────────┘       │
│                          │                                   │
│                          ▼                                   │
│                   Gap Closed? ──Yes──► Next Remediation      │
│                        │                                     │
│                       No                                     │
│                        │                                     │
│                        ▼                                     │
│                   Refine Fix                                 │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### Completion Criteria

The remediation plan is **complete** when:

| # | Criterion | Verification |
|---|-----------|-------------|
| 1 | All 4 inactive subsystems show `active` in `/api/status` | Endpoint test |
| 2 | `/api/execute` completes tasks with `status: "completed"` | API test with real key |
| 3 | `/api/automation/*` endpoints return success | API test |
| 4 | Test suite: 0 failures | `pytest` exit code 0 |
| 5 | Post-launch automation workflow runs end-to-end | Scheduled task + delivery |
| 6 | All docs updated with results | Manual review |

---

## 5. Timeline Estimate

| Remediation | Effort | Depends On |
|-------------|--------|------------|
| REM-001 (API key) | 10 minutes | External account |
| REM-002 (Inoni engine) | 1–4 hours | Code investigation |
| REM-003 (Integration engine) | 1–4 hours | Code investigation |
| REM-004 (Control Plane) | 1–2 hours | Code investigation |
| REM-005 (Orchestrator) | 1–2 hours | Code investigation |
| REM-006 (Compute tests) | 1 hour | Code fix |
| REM-007 (Image gen doc) | 15 minutes | — |
| REM-008 (Warnings) | 2–4 hours | Incremental |
| REM-009 (E2E validation) | 1–2 hours | REM-001 through REM-005 |
| REM-010 (Ops workflow) | 2–4 hours | REM-009 |

**Total estimated effort:** 10–24 hours across multiple iterations

---

## Related Documents

- [Execution Log — Cycle 1](EXECUTION_LOG.md) — Raw test results feeding this plan
- [Gap Analysis — Cycle 1](GAP_ANALYSIS.md) — Gap identification
- [Launch Automation Plan](LAUNCH_AUTOMATION_PLAN.md) — Original launch strategy
- [Operations Testing Plan](OPERATIONS_TESTING_PLAN.md) — Iterative test-fix-document cycle
- [QA Audit Report](QA_AUDIT_REPORT.md) — Security audit findings

---

**Document Version:** 1.0 — Cycle 1
**Last Updated:** 2026-02-26
**Author:** Murphy System Remediation Agent

---

**Copyright © 2020 Inoni Limited Liability Company**
**Licensed under the Apache License, Version 2.0**
**Creator: Corey Post**
