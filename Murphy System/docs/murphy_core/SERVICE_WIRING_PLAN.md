# Murphy Core Service Wiring Plan

This document defines how Murphy Core should use the new config and service container.

## New additive files

- `src/murphy_core/config.py`
- `src/murphy_core/services.py`

## Purpose

These files separate:
- environment/config loading
- service construction
- FastAPI route ownership

This reduces drift and makes deployment more predictable.

## Intended next adoption

`src/murphy_core/app.py` should move toward:

1. load `CoreConfig.from_env()`
2. call `build_services(config)`
3. store one `CoreServices` object on `app.state`
4. route handlers use that container instead of local ad hoc wiring

## Why this matters

Without this step, Murphy Core still works, but app startup remains too manual.

With this step:
- startup is deterministic
- env-driven provider selection is centralized
- adapter preference is centralized
- tests can inject service containers more easily

## Migration rule

Do not duplicate config logic in bridge, startup script, and app factory.
Use `CoreConfig` as the config truth.

Do not duplicate service construction in multiple app files.
Use `build_services()` as the service truth.
