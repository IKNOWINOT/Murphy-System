# Murphy Core v2 Adoption Plan

This document defines how Murphy Core should adopt the new v2 app factory.

## New file

- `src/murphy_core/app_v2.py`

## Why v2 exists

The original `src/murphy_core/app.py` established the first canonical path.

The new `src/murphy_core/app_v2.py` goes further by wiring:
- `CoreConfig`
- adapter-backed provider service
- adapter-backed gate service
- system map service
- registry
- routing
- planner
- executor
- traces

through a single app factory.

## Recommended role

During migration, treat `app_v2.py` as the preferred Murphy Core factory for new development and testing.

## What v2 improves

- provider health is exposed through readiness
- gate health is exposed through readiness
- system map includes compatibility ownership metadata
- the canonical request path is wired through the central services stack

## Recommended next adoption

1. update bridge/startup guidance to target `app_v2.py`
2. optionally add a v2 bridge helper
3. use v2 for smoke tests and new deploy verification
4. retire or freeze the older `app.py` once v2 is stable

## Truth rule

Do not maintain two long-lived divergent Murphy Core app factories.

The v2 path should become the preferred path, then the older app should become:
- compatibility only, or
- deprecated

## Completion signal

This adoption is complete when the preferred startup path and runtime bridge point to the v2 factory and the older app is no longer the implied default.
