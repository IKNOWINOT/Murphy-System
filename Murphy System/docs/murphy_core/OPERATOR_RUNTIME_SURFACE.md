# Operator Runtime Surface

This document defines the combined operator runtime surface for Murphy Core.

## New file

- `src/murphy_core/operator_runtime_surface.py`

## Goal

Expose one machine-readable and UI-friendly surface that combines:
- live operator status
- runtime lineage
- preferred runtime path
- rollback layers
- compatibility layers

## Why this matters

Murphy now has multiple runtime layers and migration stages.
Operators should not have to inspect multiple endpoints or documents to learn:
- which path is live
- which path is preferred
- which older paths are rollback only
- which layers are compatibility shells

## Surface contents

### Operator snapshot
Built from the configured runtime services:
- runtime identity
- provider health
- gate health
- registry truth
- system map truth

### Lineage snapshot
Built from the runtime lineage map:
- preferred runtime layer
- all layers
- each layer's role and status

### UI summary
Should summarize:
- preferred factory
- preferred runtime name
- preferred startup entrypoint
- rollback layer count
- compatibility layer count

## Intended next adoption

The preferred app path should eventually expose:
- `/api/operator/runtime`
- `/api/operator/runtime-summary`

so the UI and operators can inspect runtime truth without stitching together multiple surfaces.
