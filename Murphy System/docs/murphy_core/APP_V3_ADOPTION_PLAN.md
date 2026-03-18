# Murphy Core v3 Adoption Plan

This document defines how Murphy Core should adopt the new v3 app factory.

## New files

- `src/murphy_core/app_v3.py`
- `src/runtime/murphy_core_bridge_v3.py`
- `src/runtime/main_core_v3.py`

## Why v3 exists

The v2 app factory wired the config, provider, gate, registry, system map, and execution path.

The v3 app factory extends that by exposing operator-facing truth directly through API endpoints:
- `/api/operator/status`
- `/api/operator/summary`

and by folding operator summary into readiness.

## Recommended role

Treat v3 as the preferred app factory for:
- new development
- operator/admin UI work
- deployment verification
- startup guidance

## What v3 improves

- operator truth is directly exposed through API
- readiness includes operator summary
- capabilities endpoint can reflect runtime/provider/gate/registry/system-map state together
- startup can now prefer a path that is not just internally structured, but also operationally inspectable

## Recommended next adoption

1. use `src/runtime/main_core_v3.py` as the preferred startup path
2. use `src/runtime/murphy_core_bridge_v3.py` as the preferred compatibility bridge
3. treat v2 as fallback during migration
4. retire or freeze older app/bridge/startup layers once v3 is stable

## Completion signal

This adoption is complete when Murphy Core v3 is the unambiguous preferred backend path and older app factories exist only as compatibility or rollback layers.
