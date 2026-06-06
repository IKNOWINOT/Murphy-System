# Murphy Architecture Documentation

## Canonical current map

The single source of truth for Murphy's current architecture lives at:

  `.agents/memory/murphy_architecture_map.md` (in the cyborg's workspace)

This file documents Murphy as it is TODAY — including layers, what
works, what's built-but-unwired (orphans), the canonical 8-step
wire-up pattern, the sequenced execution plan, and the reconciliation
with prior maps.

## Why we use the cyborg workspace as the source of truth

- It's version-controlled with the cyborg's identity and rules
- It's automatically loaded at the start of every cyborg session
- Updates flow through the same canon-update discipline as the rules
- It survives system rebuilds because it's outside `/opt/Murphy-System`

## Archive

Older architecture documents are preserved in:

  `documentation/architecture/archive/`

Each is tagged with its era:
- `ARCHITECTURE_MAP_v1_two_phase_era.*.md` — Feb-Apr 2026.
  Documents Two-Phase Orchestrator, Universal Control Plane,
  Inoni Business Automation. Mostly deprecated; some concepts
  (confidence_engine, aionmind, sensor_engine, actuator_engine)
  still in substrate.

- `ARCHITECTURE_OVERVIEW_v2_dual_plane_era.*.md` — Mar 2026.
  Documents Dual-Plane Architecture (control vs execution planes,
  HMAC-signed packets, deterministic FSM). Concepts mostly removed;
  the control-vs-execution split lost out to monolith + microservices.

These are kept as archaeology, not as current truth. Do not implement
patterns from them without first checking §11 of the canonical map.

## Updating the map

When the architecture changes materially:
1. Update `.agents/memory/murphy_architecture_map.md` in workspace
2. PSM-log the conceptual change (kind=architecture_evolution)
3. Add a row to the §11 reconciliation table if a subsystem is
   added, removed, or reclassified
4. Bump the date at the top of the map
