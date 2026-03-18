# Murphy Core Runtime-Surface App Plan

This document defines the app layer that exposes the unified operator/runtime surface directly through the backend.

## New file

- `src/murphy_core/app_v3_runtime_surface.py`

## Goal

Make the preferred runtime-correct backend path directly serve:
- live operator status
- runtime lineage
- deployment modes
- preferred runtime and deployment summaries

through dedicated API endpoints.

## New endpoints

### `/api/operator/runtime`
Returns the unified runtime/operator surface snapshot.

### `/api/operator/runtime-summary`
Returns the UI-oriented runtime summary.

### Readiness
`/api/readiness` now also includes:
- `runtime_summary`

## Why this matters

Before this step, the runtime/operator truth existed in service objects and docs, but UI/admin consumers still had to infer too much.

This app layer makes the running backend itself responsible for serving that truth.

## Recommended role

Treat this app as the current best app-level target for:
- admin/operator UI integration
- deployment verification
- migration observability

## Intended next adoption

1. prefer this app where runtime/operator visibility matters
2. update bridge/startup layers if the repo wants this to become the new primary app target
3. keep older app variants as rollback/compatibility only
