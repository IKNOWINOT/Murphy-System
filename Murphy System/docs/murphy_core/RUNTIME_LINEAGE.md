# Runtime Lineage

This document defines the runtime lineage for Murphy Core and identifies the preferred canonical path versus compatibility and rollback layers.

## New file

- `src/murphy_core/runtime_lineage.py`

## Goal

Provide one machine-readable and human-readable source of truth for:
- which runtime path is preferred
- which runtime paths are rollback only
- which runtime paths are compatibility only

## Current preferred path

The current preferred canonical path is:
- app factory: `src/murphy_core/app_v3_runtime.py`
- bridge: `src/runtime/murphy_core_bridge_v3_runtime_correct.py`
- startup: `src/runtime/main_core_v3_runtime_correct.py`

## Rollback / compatibility layers

The lineage file also records older layers such as:
- legacy runtime
- Murphy Core v1
- Murphy Core v2
- Murphy Core v3

These remain available during migration but should not be treated as the preferred backend path.

## Why this matters

Without a lineage map, the repo risks accumulating:
- many app factories
- many bridge files
- many startup paths
- no single runtime truth

The lineage map makes the runtime evolution explicit and testable.

## Intended next adoption

The operator status/system map/capability surfaces should eventually include lineage summary so UI and operators can see:
- preferred path
- rollback paths
- compatibility-only paths

## Truth rule

When a new preferred runtime path appears, update the lineage map and tests at the same time.
Do not leave the preferred path implied only in scattered docs.
