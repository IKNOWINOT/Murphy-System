# Founder Privilege Overlay and Scoped HITL Policy — v1

## Purpose

This document records the branch policy that founder remains a privileged overlay on the canonical execution runtime, while validation responsibility is routed by scope.

## Canonical default runtime

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

## Core rules

1. Canonical execution remains the default runtime identity for users and automations.
2. Founder is a privileged overlay on that runtime, not the default audience identity.
3. Founder workstation can make direct platform changes and direct coding additions.
4. Founder automations are full-bore and may use all founder-scoped automation features.
5. Standard accounts remain constrained and do not inherit founder-scoped platform privileges.

## Founder privilege overlay

The founder overlay now exposes machine-readable policy through:

- `GET /api/founder/workstation-policy`
- `GET /api/founder/automation-policy`
- `GET /api/founder/account-policy-matrix`
- `GET /api/founder/visibility`
- `GET /api/founder/visibility-summary`

### Founder workstation privileges
- direct platform changes
- direct code additions
- direct runtime configuration
- privileged module creation and patching
- privileged boot-path triggering

### Founder automation privileges
- all available automation features
- privileged runtime actions
- privileged code generation and code patch execution
- privileged route/family override review
- privileged inventory and visibility access
- privileged recovery and fallback controls

## Scoped HITL routing policy

Validation responsibility is now routed by request scope.

### Platform-changing requests
Requests that change the platform, runtime, codebase, modules, repository, or founder workstation path must go through:

- **founder HITL validation**

These requests are surfaced with:
- `target_scope = platform`
- `hitl_scope = founder`

### Organization-scoped requests
Requests that affect an organization, workspace, tenant, team, or company-level settings without changing the shared platform must go through:

- **organization HITL validation**

These requests are surfaced with:
- `target_scope = organization`
- `hitl_scope = organization`

### Generic HITL
Generic risk-based HITL remains available only when a request is neither platform-changing nor organization-scoped.

## Visibility surfaces

Scoped HITL routing is now visible across the canonical v5 surfaces through recent execution outcome summaries and HITL scope summaries:

- `GET /api/operator/runtime`
- `GET /api/operator/runtime-summary`
- `GET /api/ops/status`
- `GET /api/ui/runtime-dashboard`
- `GET /api/founder/visibility`
- `GET /api/founder/visibility-summary`
- `GET /api/traces/{trace_id}`

## Interpretation

The founder now has broader direct platform and coding capability than standard accounts, but the runtime identity model is unchanged:

- founder is still overlay-only
- standard users still run on the canonical default runtime
- validation routing now distinguishes between platform responsibility and organization responsibility explicitly
