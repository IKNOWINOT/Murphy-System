# UI and Operations Next Phases

This document defines the next-phase repo-native surfaces for UI and operations.

## New files

- `src/murphy_core/ui_runtime_dashboard.py`
- `src/murphy_core/operations_status.py`

## Why these phases now

Murphy Core now has enough runtime truth to support:
- UI dashboard views
- admin/operator runtime views
- deployment mode guidance
- operations runbooks

Without these surfaces, UI and ops would still need to interpret raw backend JSON manually.

## UI runtime dashboard

The UI dashboard builder translates the unified runtime surface into frontend-friendly structures:
- cards
- actions
- summary
- tables

### Intended UI usage

Use it to render:
- preferred runtime card
- preferred deployment card
- transitional shell card
- preferred provider card
- quick actions for direct core boot vs compat shell boot
- rollback and compatibility layer tables

## Operations status

The operations status model translates runtime truth into:
- current operational snapshot
- preferred startup guidance
- transitional startup guidance
- verification runbook steps

### Intended operations usage

Use it to power:
- deploy checklist views
- incident response runbooks
- migration-state visibility
- operator guidance when switching between direct core and legacy compat shell

## Recommended next adoption

1. expose a UI/admin endpoint for dashboard payload
2. expose an operations endpoint for runbook/status payload
3. connect frontend/admin views to those endpoints
4. optionally add deployment mode toggles or environment-aware hints

## Suggested next endpoints

- `GET /api/ui/runtime-dashboard`
- `GET /api/ops/status`
- `GET /api/ops/runbook`

## Strategic value

These next phases matter because Murphy is no longer only a backend architecture problem.
It now has enough structure that UI and operations can become first-class consumers of runtime truth.
