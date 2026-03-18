# Service Health and Fallback

This document defines how Murphy Core should report and use provider/gate service health.

## New service files

- `src/murphy_core/provider_service.py`
- `src/murphy_core/gate_service.py`

## Goal

Murphy Core must tell the truth about:
- which provider path is preferred
- which provider path was selected
- whether fallback occurred
- which gates are active
- which gates were skipped because unavailable

## Provider service behavior

The provider service should:
- select a preferred adapter from config
- check adapter health
- fall back to another healthy adapter if needed
- preserve typed inference output
- record selected provider and fallback order in metadata

## Gate service behavior

The gate service should:
- evaluate healthy gate adapters in a consistent order
- return typed gate results
- expose gate health for readiness/capability reporting

## Truth rules

### Provider truth
Every inference should be able to say:
- selected provider
- fallback order
- whether degraded fallback was used

### Gate truth
Every request should be able to say:
- which gates evaluated it
- which decisions were returned
- whether a gate family was unavailable

## Intended next adoption

`src/murphy_core/services.py` should move toward constructing these services instead of older local logic.

`src/murphy_core/app.py` should expose provider/gate health through readiness and system-map surfaces.

## Production value

This step is important because it turns Murphy Core from a generic typed shell into a truthful orchestrator that can explain how it made decisions.
