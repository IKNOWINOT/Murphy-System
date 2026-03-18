# Operator Runtime Truth Fix

This document records the fix for stale operator runtime labels during Murphy Core migration.

## Problem

Earlier operator status logic hardcoded:
- `preferred_factory = murphy_core_v2`

That became stale once Murphy Core v3 became the preferred runtime path.

## New additive fix

A configurable runtime-truth service now exists at:
- `src/murphy_core/operator_status_runtime.py`

It lets each app factory provide its actual preferred runtime label instead of relying on a stale hardcoded value.

## Why this fix matters

The operator surface is supposed to be the truthful summary of the live runtime path.
If it lies about the preferred factory, then:
- readiness becomes misleading
- operator endpoints become misleading
- startup/docs drift from runtime truth

## Intended next adoption

`src/murphy_core/app_v3.py` should adopt `ConfigurableOperatorStatusService` and pass:
- `preferred_factory="murphy_core_v3"`

After that:
- operator endpoints should report v3 truth
- readiness operator summary should report v3 truth
- tests should align on v3 labels only

## Transition rule

Do not create another hardcoded operator label in a new version layer.
Use the configurable runtime-truth service so app factories can declare their identity explicitly.
