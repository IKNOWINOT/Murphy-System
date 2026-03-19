# Inventory Surface Adoption Plan

## Purpose

This document defines the app layer that exposes the machine-readable production inventory together with runtime, UI, and operations surfaces.

New file:

- `Murphy System/src/murphy_core/app_v3_inventory_surface.py`

## What this app adds

In addition to runtime and operator visibility, this app exposes:

- `GET /api/operator/production-inventory`
- `GET /api/operator/production-inventory-summary`
- `GET /api/ui/runtime-dashboard`
- `GET /api/ops/status`
- `GET /api/ops/runbook`

## Why this matters

The branch already had:

- runtime truth
- deployment mode truth
- operator/runtime summaries
- UI runtime models
- operations status models
- machine-readable production inventory

This app makes the backend itself responsible for serving those surfaces directly.

That means the webapp, operator tooling, and migration/admin views can query:

- what subsystem families are preserved
- what runtime order is intended
- which families belong to which layers
- what deployment mode exists
- what runbook should operators follow

## Recommended role

Treat this as the best current backend app target for:

- admin/operator UI integration
- migration visibility
- runtime architecture introspection
- subsystem preservation visibility

## Recommended next adoption

1. if runtime/admin visibility is the priority, prefer this app over earlier app variants
2. add bridge/startup surfaces if this should become the new preferred boot path
3. connect the webapp/admin layer to these new endpoints

## Strategic value

This is the first app layer in the branch that serves:

- runtime truth
- deployment truth
- production inventory truth
- UI dashboard payloads
- operations payloads

through one backend surface.
