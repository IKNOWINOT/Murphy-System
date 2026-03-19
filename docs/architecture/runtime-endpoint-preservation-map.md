# Runtime Endpoint and Subsystem Preservation Map

## Purpose

This document turns the production runtime separation plan into a concrete preservation map for refactoring.

It is based on the currently confirmed runtime surface in:

- `Murphy System/src/runtime/app.py`

This is **not** presented as a perfect auto-generated route index. The GitHub connector did not provide a clean route-enumeration pass for the file. Instead, this map captures the confirmed subsystem families, endpoint groups, and runtime surfaces that should be preserved during restructuring.

The goal is to prevent accidental capability loss while the runtime is separated into cleaner layers.

---

## Tag set

Every runtime surface should eventually be tagged as one of:

- `substrate`
- `generation`
- `guidance`
- `orchestration`
- `production`
- `gate_review`
- `delivery`
- `learning`
- `hybrid`

Where useful, a preservation state is also assigned:

- `preserve_active`
- `preserve_wrap`
- `preserve_shell`
- `replace_equivalent`
- `needs_rebuild`

---

## Preservation map by subsystem family

## 1. Survival / control substrate

### Families

- security plane
- governance kernel
- event backbone
- persistence / database
- cache
- integration bus
- request middleware / trace plumbing
- health / readiness / metrics
- startup bootstrap
- auth / account / session support

### Tags

- layer: `substrate`
- state: `preserve_active`

### Refactor rule

Keep these foundational and early in startup order.
Do not bury them under business or production abstractions.

---

## 2. AionMind family

### Confirmed purpose

- cognitive enrichment
- task/form interpretation
- contextual execution support
- kernel-style runtime cognition support

### Tags

- primary layer: `generation`
- secondary layer: `hybrid`
- state: `preserve_wrap`

### Refactor rule

Preserve AionMind explicitly as an enrichment and interpretation system.
Do **not** force it to remain the top-level orchestration owner.
It should sit after request normalization and before final routing/planning.

---

## 3. Librarian / TaskRouter / capability lookup

### Confirmed purpose

- capability discovery
- ranking and lookup
- route hints
- knowledge-guided selection

### Tags

- layer: `generation`
- state: `preserve_active`

### Refactor rule

Preserve as first-class discovery and selection infrastructure.
This family should help determine candidate subsystems and workflows before execution.

---

## 4. MSS family

### Confirmed purpose

- magnify / simplify / solidify transforms
- structured content shaping
- document and context transformation

### Tags

- primary layer: `generation`
- secondary layer: `production`
- state: `preserve_wrap`

### Refactor rule

Preserve MSS as a specialized transformation toolkit.
Do not flatten it into a generic text-processing helper.
It should be intentionally selected when transformation semantics matter.

---

## 5. UCP family

### Confirmed purpose

- unified execution and control plane behavior
- specialized execution path
- system-level control execution support

### Tags

- primary layer: `orchestration`
- secondary layer: `generation`
- state: `preserve_wrap`

### Refactor rule

Preserve UCP as an execution/control subsystem.
It should remain an explicit selectable runtime path, not dead compatibility code.

---

## 6. MFGC family

### Confirmed purpose

- gate state
- gate config
- gate setup
- execution and document control decisions

### Tags

- layer: `gate_review`
- state: `preserve_active`

### Refactor rule

Preserve MFGC as a first-class gate/governance family.
Do not move it into business metrics or generic execution routing.
It should sit between generation/orchestration and progression into production/delivery.

---

## 7. Compliance family

### Confirmed purpose

- compliance toggles
- compliance reports
- scans
- rule/gate behavior

### Tags

- layer: `gate_review`
- state: `preserve_active`

### Refactor rule

Preserve as a hard gate layer.
Should remain close to MFGC and HITL, not hidden inside production logic.

---

## 8. HITL / QC / acceptance family

### Confirmed purpose

- review queues
- QC
- acceptance
- revision loop
- human approval

### Tags

- primary layer: `gate_review`
- secondary layer: `delivery`
- state: `preserve_active`

### Refactor rule

Preserve as the explicit review bridge between production and release.
Do not let it disappear into generic status flags.

---

## 9. Swarm / bot / agent families

### Confirmed purpose

- swarm crews
- durable swarms
- visual swarm builder
- bot inventory
- agent dashboards
- run records
- domain swarms
- advanced swarm control

### Tags

- primary layer: `orchestration`
- secondary layer: `hybrid`
- state: `preserve_active`

### Refactor rule

Preserve as execution-plane worker systems.
Do not misclassify them as top-level business strategy systems.
They belong under orchestration and assignment.

---

## 10. Business automation families

### Confirmed purpose

- CRM
- campaigns
- marketing
- sales
- portfolio
- dashboards
- org chart / CEO / business scaling
- account lifecycle
- billing / subscription
- review and referral automation
- efficiency / supply / safety / operational guidance surfaces

### Tags

- primary layer: `guidance`
- secondary layer: `hybrid`
- state: `preserve_active`

### Refactor rule

Preserve these as business-guidance systems.
They should influence priorities, demand, and allocation.
They should not be confused with production execution itself.

---

## 11. Onboarding / configuration generation family

### Confirmed purpose

- generate configuration
- select modules and integrations
- create initial workflow intent

### Tags

- primary layer: `generation`
- secondary layer: `hybrid`
- state: `preserve_wrap`

### Refactor rule

Preserve as configuration generation, not runtime identity.
Its outputs should feed later layers rather than defining the entire runtime model.

---

## 12. Workflow compiler / terminal / workflow storage family

### Confirmed purpose

- compile workflow definitions
- store workflow state
- represent execution graphs

### Tags

- primary layer: `orchestration`
- secondary layer: `generation`
- state: `preserve_active`

### Refactor rule

Preserve as orchestration infrastructure.
This family should become one of the clearest bridges between generated plans and executable production flows.

---

## 13. Production proposal / work-order / queue family

### Confirmed purpose

- production proposal generation
- work-order creation
- production queueing
- routing
- production scheduling

### Tags

- primary layer: `production`
- secondary layer: `orchestration`
- state: `preserve_active`

### Refactor rule

Preserve as the top of the production layer.
This family is the visible handoff from guidance/orchestration into actual product creation.

---

## 14. Form execution / validation / correction family

### Confirmed purpose

- structured task execution
- validation
- correction loops
- task result shaping

### Tags
n- primary layer: `production`
- secondary layer: `gate_review`
- state: `preserve_active`

### Refactor rule

Preserve as a production execution family with an integrated correction loop.
Do not collapse this into generic chat execution.

---

## 15. Document / artifact / image generation family

### Confirmed purpose

- document generation
- content transformation
- image generation
- artifact creation
- report-like output generation

### Tags

- primary layer: `production`
- secondary layer: `delivery`
- state: `preserve_active`

### Refactor rule

Preserve as deliverable-building systems.
These are direct output producers and should remain visible as such.

---

## 16. Delivery and verification family

### Confirmed purpose

- deliverables
- final verification
- packaging
- release states
- output listing and closure

### Tags

- layer: `delivery`
- state: `preserve_active`

### Refactor rule

Preserve as a distinct layer after review/acceptance.
Do not merge final delivery with the production transformation steps.

---

## 17. Self-healing / trainer / correction-learning family

### Confirmed purpose

- code healer
- corrections proposals
- trainer status/rewards
- self-learning toggle
- readiness diagnostics
- repair loops

### Tags

- layer: `learning`
- state: `preserve_wrap`

### Refactor rule

Preserve as downstream improvement infrastructure.
Do not let it compete with customer-facing production flow in the same conceptual layer.

---

## 18. Cost / budget / assignment kernel

### Confirmed purpose

- cost summary
- budget constraints
- assignment visibility
- resource and spend guidance

### Tags

- primary layer: `guidance`
- secondary layer: `gate_review`
- state: `preserve_active`

### Refactor rule

Preserve as a business-guidance family with policy implications.
It should influence allocation and approval, not directly own execution.

---

## 19. Integrations and external connectors

### Confirmed purpose

- external service access
- cross-system workflow steps
- delivery and production dependencies

### Tags

- primary layer: `substrate`
- secondary layer: `hybrid`
- state: `preserve_active`

### Refactor rule

Preserve as substrate-access systems used by higher layers.
Integration wiring should stay reusable rather than being duplicated inside each business or production family.

---

## 20. Hybrid translator families

These are the families that bridge business guidance and production execution.

### Included examples

- marketing content pipelines
- self-marketing orchestrator
- onboarding-generated workflow systems
- review-response automation
- production scheduling

### Tags

- layer: `hybrid`
- state: `preserve_wrap`

### Refactor rule

Preserve these as translators.
Do not force them into a false choice of guidance-only or production-only.

---

## Runtime ordering map

This preservation map implies the following ordering:

1. `substrate`
2. `generation`
3. `guidance`
4. `orchestration`
5. `production`
6. `gate_review`
7. `delivery`
8. `learning`

### Important note

Some families are intentionally dual-tagged because they bridge layers.
The dual tags are not drift. They reflect actual hybrid role.

---

## Refactor constraints

During future runtime separation work, the following constraints should hold.

### Constraint 1

Do not remove first-class families just because their current wiring is broken.
Broken ordering is not evidence that the family should disappear.

### Constraint 2

Do not preserve old call chains merely because they existed.
Preserve capability, endpoint intent, and output semantics instead.

### Constraint 3

Do not flatten MSS, UCP, MFGC, AionMind, swarms, or business-automation families into generic chat execution.
They should remain intentionally selectable subsystem families.

### Constraint 4

Do not let business-guidance systems directly become production systems unless the handoff is explicit.

### Constraint 5

Do not let learning/self-healing systems sit inside the same conceptual layer as delivery or customer-facing product generation.

---

## Recommended next artifact

The next useful artifact after this document is a code-side inventory structure, for example:

- `src/murphy_core/production_inventory.py`

That structure should define each subsystem family, its layer tags, preservation state, and intended runtime order so the runtime/operator/admin surfaces can expose this map directly.
