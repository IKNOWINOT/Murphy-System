# Legacy Endpoint Family Migration Plan

This document defines ownership for legacy endpoint families during migration to Murphy Core.

## Goal

Prevent legacy runtime and Murphy Core from competing for authority.

## Ownership model

Each endpoint family must be marked as one of:
- `canonical_core`
- `adapter_owned`
- `compatibility_only`
- `legacy_until_replaced`

## Current recommended ownership

### canonical_core
Murphy Core should own:
- `/api/health`
- `/api/readiness`
- `/api/capabilities/effective`
- `/api/registry/modules`
- `/api/system/map`
- `/api/chat`
- `/api/execute`
- `/api/traces/recent`
- `/api/traces/{trace_id}`

### adapter_owned
Bridge or adapters should temporarily own:
- document/workflow orchestration
- HITL review surfaces
- swarm specialized execution
- selected integration-backed flows

These should feed Murphy Core trace and route metadata whenever possible.

### compatibility_only
Large legacy domain endpoint groups remain compatibility-only until:
- registry truth exists
- effective capability truth exists
- typed core equivalents exist

Examples may include:
- CRM families
- dashboards and boards families
- billing families
- portfolio families
- miscellaneous utility surfaces with placeholder returns

### legacy_until_replaced
Highly specialized surfaces that do not yet have typed contracts may remain legacy until explicitly migrated.

## Chat and execute rule

The most important rule:

Legacy `/api/chat` and `/api/execute` should not remain independent orchestration authorities.
They should delegate into Murphy Core once compatibility handling is ready.

## Swarm rule

Swarm routes may remain specialized, but they should still emit:
- route type
- gate summary
- trace ID
- execution status

through Murphy Core contracts.

## HITL rule

HITL queues may remain legacy-backed during migration, but Murphy Core must be able to:
- signal `requires_hitl`
- expose gate rationale
- preserve trace continuity

## Completion signal

This migration plan is complete when endpoint-family ownership is no longer ambiguous and Murphy Core is the only canonical orchestrator.
