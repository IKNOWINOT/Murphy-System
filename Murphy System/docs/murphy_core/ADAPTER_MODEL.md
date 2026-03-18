# Murphy Core Adapter Model

This document defines how provider and gate adapters should work in Murphy Core.

## Goal

Centralize inference and policy while preserving useful legacy subsystems through typed adapters.

## New adapter families

### Provider adapters
Files:
- `src/murphy_core/provider_adapters.py`

Current adapters:
- `LocalRulesAdapter`
- `LegacyMurphyInferenceAdapter`

Purpose:
- unify all inference behind one typed contract
- allow Murphy Core to choose fallback/provider strategy without changing downstream code

### Gate adapters
Files:
- `src/murphy_core/gate_adapters.py`

Current adapters:
- security
- compliance
- authority
- confidence
- hitl
- budget

Purpose:
- unify all gate decisions behind one typed contract
- prepare for wiring real security/compliance/HITL modules later

## Why adapters matter

Murphy Core should not hardcode every inference path and every gate implementation directly in `app.py` or a single monolithic file.

Adapters let the system:
- preserve legacy functionality
- keep core contracts stable
- expose health and availability
- swap implementations without changing response contracts

## Required adapter behavior

### Provider adapter
Must provide:
- health state
- typed inference output

### Gate adapter
Must provide:
- health state
- typed gate evaluation

## Migration path

1. start with default/core adapters
2. add legacy-backed adapters
3. add modern provider-backed adapters
4. select adapters through central config/service wiring

## Truth rule

Even if a legacy subsystem is unavailable, the adapter layer must still tell the truth:
- available or not
- fallback used or not
- what provider/gate generated the result

## Next intended adoption

`providers.py` and `gates.py` should move toward using these adapters as the execution mechanism rather than embedding all logic locally.
