# Canonical V5 Validation and Hardening Checklist — 2026-03-20

## Purpose

This checklist translates the remaining branch work after structural convergence into explicit validation and hardening passes.

## Current branch default runtime

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

## Validation pass 1 — E2E hero flow

### Goal
Validate that Describe → Execute → Refine works under the canonical v5 runtime with real route/family selection and trace persistence.

### Checks
- submit realistic describe-style requests through `/api/chat`
- submit realistic execute-style requests through `/api/execute`
- verify route selection is plausible for each case
- verify subsystem family selection is populated and coherent
- verify traces persist `execution_status`, `recovery`, and gate summaries
- verify output semantics match endpoint flags and trace recovery fields

## Validation pass 2 — Enforcement semantics

### Goal
Confirm that live gate behavior matches the current enforced semantics.

### Checks
- review outcomes produce `review_required` and `approval_pending=true`
- HITL outcomes produce `hitl_required` and `approval_pending=true`
- hard blocking gates produce `blocked` unless explicit fallback policy allows rollback execution
- planner/enforcement drift does not silently trigger fallback
- fallback only activates for hard blocking gates when policy opts in

## Validation pass 3 — Visibility parity

### Goal
Confirm all visibility surfaces remain in parity under realistic runtime traffic.

### Checks
- `/api/operator/runtime`
- `/api/operator/runtime-summary`
- `/api/ops/status`
- `/api/ui/runtime-dashboard`
- `/api/founder/visibility`
- `/api/founder/visibility-summary`
- `/api/traces/{trace_id}`

### Expected outcome
Recent execution outcomes, latest status, and recovery semantics should agree across all surfaces.

## Validation pass 4 — Live MurphySystem fallback behavior

### Goal
Confirm fallback behavior against live MurphySystem integrations instead of smoke-test simulations only.

### Checks
- validate fallback route execution with a real MurphySystem instance available
- confirm fallback does not bypass review or HITL pauses
- confirm fallback_result structure is stable enough for operator/trace consumers
- confirm fallback traces and endpoint flags remain aligned

## Hardening pass 5 — Deployment readiness

### Goal
Reduce operational risk for production promotion.

### Checks
- run the canonical v5 startup path in a production-like environment
- verify health, readiness, operator, ops, dashboard, and founder endpoints after boot
- verify dependency/configuration assumptions for providers and gate services
- verify logging/trace retention behavior is acceptable under repeated requests
- verify rollback path remains available without changing canonical default identity

## Suggested success criteria

The branch can be treated as ready for promotion once:

- hero-flow validation passes with realistic traffic
- enforcement semantics behave as documented under live conditions
- visibility surfaces remain in parity under repeated requests
- fallback behavior is validated against live MurphySystem integrations
- production boot/readiness checks pass without changing the canonical v5 default path

## Current weighted completion

- **~99%**
