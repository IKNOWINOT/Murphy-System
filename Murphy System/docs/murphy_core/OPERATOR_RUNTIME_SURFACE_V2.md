# Operator Runtime Surface v2

This document defines the unified operator runtime surface that combines:
- live operator status
- runtime lineage
- deployment modes

## New file

- `src/murphy_core/operator_runtime_surface_v2.py`

## Goal

Provide one inspectable surface that answers all of these at once:
- what runtime identity is live?
- what provider/gate path is active?
- what runtime path is preferred?
- what rollback layers exist?
- what compatibility layers exist?
- what deployment mode should be used now?
- what transitional shell mode exists?

## New summary outputs

### Snapshot
Includes:
- operator snapshot
- lineage snapshot
- deployment modes snapshot
- preferred runtime layer
- preferred deployment mode
- transitional deployment mode

### UI summary
Includes:
- preferred factory
- preferred runtime name
- preferred runtime startup
- preferred deployment mode
- preferred deployment startup
- transitional deployment mode
- transitional deployment startup
- rollback layer count
- compatibility layer count

## Why this matters

The repo now has enough runtime layers and migration paths that separate surfaces are no longer enough.

The v2 operator runtime surface is the first place where UI/admin tooling can inspect:
- the canonical direct runtime-correct path
- the transitional legacy compat shell path
- the older rollback layers

without stitching together multiple docs and helper outputs.

## Intended next adoption

The preferred runtime-correct app path should eventually expose:
- `/api/operator/runtime`
- `/api/operator/runtime-summary`

using this v2 surface.
