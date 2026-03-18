# Capability-Aware Gating Plan

This document answers where capability-preserving gating should happen in Murphy Core.

## Short answer

Capability gating should happen **after inference and Rosetta normalization, but before final route/planning decisions are locked in**.

In practice, the ideal order is:
- request
- inference
- Rosetta normalization
- generic policy gates
- capability-aware gating
- route selection
- planning
- execution
- trace

## Why this timing is right

If capability gating happens too early:
- the system does not yet know the normalized intent/domain/module-class hints
- capabilities get filtered with weak context

If capability gating happens too late:
- the planner may already collapse distinct capabilities into a generic plan
- you lose the ability to preserve specialized subsystems intentionally

So the right place is **in the middle**, once the request meaning is normalized but before execution plans are finalized.

## Current state in the repo

Murphy Core already has generic gates for:
- security
- compliance
- authority
- confidence
- hitl
- budget

The new additive file:
- `src/murphy_core/capability_gating.py`

adds a capability-aware selection/review/block layer on top of those gates.

## What capability gating does

For the normalized request, it asks:
- which registered capabilities/modules match the normalized module classes?
- which of those are eligible?
- which require review because they are adapter/experimental under risk?
- which are blocked because they are drifted or missing dependencies?

That is the correct mechanism for preserving distinct capabilities instead of flattening them.

## Recommended next adoption

1. include capability gating in the preferred app path after Rosetta and generic gates
2. record its result in traces
3. use its eligible module set to influence planner module-family selection
4. expose capability gating summaries in operator/runtime/admin views if needed

## Direct answer to your concern

You said you have distinct capabilities you do not want to lose.

That is exactly why this layer should exist.
It lets the system preserve and intentionally select capabilities **before** the planner turns the request into a generic execution plan.
