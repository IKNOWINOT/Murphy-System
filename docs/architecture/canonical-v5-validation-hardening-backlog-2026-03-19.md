# Canonical V5 Validation & Hardening Backlog — 2026-03-19

## Purpose

This document converts the remaining post-alignment work on `corey/murphy-core-vibe-system` into concrete validation and hardening slices.

The branch is structurally aligned around canonical execution v5.
The remaining work is primarily about proving the system under realistic conditions and tightening production readiness.

## Current canonical target

### App
- `Murphy System/src/murphy_core/app_v3_canonical_execution_surface_v5.py`

### Bridge
- `Murphy System/src/runtime/murphy_core_bridge_v3_canonical_execution_surface_v5.py`

### Startup
- `Murphy System/src/runtime/main_core_v3_canonical_execution_surface_v5.py`

### Run command
```bash
python -m src.runtime.main_core_v3_canonical_execution_surface_v5
```

## Validation backlog

### 1. End-to-end hero flow validation

Goal:
- prove Describe → Execute → Refine behavior on the canonical v5 runtime using realistic requests

Needed work:
- run end-to-end scenarios through `/api/chat` and `/api/execute`
- verify route selection, family selection, trace creation, and final execution status
- verify review-required, hitl-required, fallback-completed, and blocked outcomes on realistic requests
- verify operator, ops, dashboard, and founder surfaces reflect the resulting recent execution outcomes

Suggested output:
- a scenario matrix with request, expected route, expected status, actual status, and trace id

### 2. Fallback behavior validation against live MurphySystem integrations

Goal:
- prove the explicit legacy fallback path behaves correctly when real MurphySystem adapters are available

Needed work:
- validate fallback with `allow_automatic_fallback=True` and hard blocking gates present
- verify fallback does not trigger for planner/enforcement drift without blocking gates
- verify fallback does not bypass review or HITL pauses
- verify `use_mfgc=False` path behaves as intended on chat fallback
- verify execute-task fallback results remain observable in endpoint payloads and traces

Suggested output:
- pass/fail matrix for fallback policy combinations and observed execution results

### 3. Endpoint and trace consistency validation

Goal:
- prove endpoint flags, trace recovery state, and surface summaries stay mutually consistent under live execution

Needed work:
- compare endpoint payloads to `/api/traces/{trace_id}` for the same request
- verify `approval_pending`, `fallback_engaged`, and `blocked` match trace recovery fields
- verify `/api/operator/runtime`, `/api/operator/runtime-summary`, `/api/ops/status`, `/api/ui/runtime-dashboard`, `/api/founder/visibility`, and `/api/founder/visibility-summary` all reflect the same recent execution outcome mix

Suggested output:
- consistency checklist with trace ids and endpoint payload excerpts

### 4. Production deployment hardening

Goal:
- confirm the canonical v5 path is production-safe under real boot conditions

Needed work:
- verify environment configuration requirements for provider selection and gate behavior
- verify startup behavior under production process manager settings
- verify health, readiness, runtime, ops, and founder endpoints under production boot
- verify observability behavior for repeated boot cycles and trace growth
- verify rollback path documentation remains accurate for compat shell and runtime-correct fallback core

Suggested output:
- production boot checklist with successful commands and endpoint probes

### 5. Load and stability sampling

Goal:
- get lightweight confidence that canonical v5 behavior remains stable over repeated requests

Needed work:
- run repeated chat and execute requests through the canonical v5 startup path
- confirm recent execution outcomes remain coherent as trace volume increases
- verify no unexpected drift in route/family selection under repeated scenarios
- verify operator-facing recent-outcome summaries remain performant and correct over a larger trace window

Suggested output:
- sampling summary with request counts, failure counts, and notable anomalies

## Exit criteria for calling the branch production-validation complete

- realistic hero-flow scenarios executed on canonical v5 with expected statuses
- fallback policy verified against live MurphySystem integrations
- endpoint, trace, operator, ops, dashboard, and founder surfaces confirmed mutually consistent
- production boot and readiness checks completed successfully
- no newly discovered architecture drift requiring versioned truth-surface correction

## Current weighted completion

- **~99%**

## Interpretation

Further work should generally be framed as validation or hardening unless testing reveals new structural drift.
