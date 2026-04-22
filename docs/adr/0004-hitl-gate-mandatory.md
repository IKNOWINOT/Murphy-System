# ADR-0004: Human-in-the-loop (HITL) gate is mandatory for all agent action

* **Status:** Accepted
* **Date:** 2026-04-22 (retroactive)

## Context

Murphy is an autonomous platform: agents propose actions across email, CRM,
financial systems, code repositories, infrastructure, and customer-facing
communication. Any of those actions, executed without oversight, can:

* leak PII or other regulated data;
* commit fraud (deliberate or accidental) on a tenant's behalf;
* destroy data through bad code generation;
* damage tenant reputation by sending poor-quality content to customers;
* incur material spend (LLM bills, compute, third-party API charges);
* violate per-region compliance requirements (GDPR, CCPA, EU AI Act).

Tenants will not — and should not — adopt a system where they cannot inspect
and veto these actions. At the same time, requiring a human approval for
*every* low-stakes action would defeat the purpose of automation.

## Decision

A Human-in-the-Loop **gate is mandatory** for every action with material
side-effects. The gate is implemented in `src/hitl_execution_gate.py`,
backed by `src/hitl_persistence.py`, and surfaced through the HITL dashboard
(`hitl_dashboard.html` + the HITL routers).

The gate has three operating modes per action class, controlled by
`automation_mode_controller.py`:

* **manual** — every action waits for a human approval (default for new
  tenants, new automations, and any flagged risk surface).
* **review** — actions execute after a configurable delay window during
  which a human can veto (graduates from manual once the action class proves
  reliable, see `hitl_graduation_engine.py`).
* **autonomous** — actions execute immediately; the human review queue
  receives a notification only on anomalies (graduates from review under
  the same engine).

Graduation between modes is **per-action-class per-tenant**, recorded in
the HITL persistence layer, and reversible from the dashboard at any time.

The `governance_kernel` enforces the gate: agent code that bypasses HITL
is rejected at the boundary, not policed in agent prompts.

## Consequences

* **Positive:** tenants retain veto power, which is the foundation of
  trust for any autonomous platform that touches their systems.
* **Positive:** graduation removes the "every click" toil once an
  action class earns it; the system becomes more autonomous over time
  without the operator having to push it.
* **Positive:** the HITL queue is itself a high-signal training corpus
  for improving the underlying agents.
* **Negative:** every domain integration must declare its action classes
  and route through the gate. This is non-trivial onboarding work for
  new connectors. We accept this; the alternative (silent execution) is
  not a product we are willing to ship.
* **Negative:** the HITL pathway is a hot path with strict latency
  requirements (an approval that takes 10 s to render is a 10 s outage of
  every action behind it). The HITL approval-time SLO (Class S Roadmap,
  Item 17) makes this measurable and alertable.
