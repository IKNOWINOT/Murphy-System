# Production Runtime Separation Plan

## Purpose

This document converts the current runtime analysis into an operational preservation map.

The goal is **not** to remove major subsystem families. The goal is to separate them into the roles they already perform in the codebase so the platform can evolve from a broad capability surface into a legible production architecture.

The central finding is:

- the repository already contains a large production-capability surface
- the main problem is not missing capability families
- the main problem is that setup, guidance, gating, orchestration, production, and self-healing are blended together in the runtime shell instead of being represented as distinct operating layers

Primary grounding file:

- `Murphy System/src/runtime/app.py`

That file exposes the current execution surface, module load order, runtime wiring, API taxonomy, production workflow creation, gate wiring, HITL loops, onboarding generation, workflow generation, compliance scans, MFGC controls, MSS controls, UCP execution, self-healing surfaces, and business-facing automation families.

---

## Executive conclusion

Murphy System currently behaves like **multiple runtimes living in one runtime shell**:

1. a survival/control runtime
2. a generation and knowledge runtime
3. a business-guidance runtime
4. a production and execution runtime
5. a gate/review runtime
6. a delivery runtime
7. a learning and self-healing runtime

These layers already exist implicitly in the code.

The next architecture phase should therefore focus on **runtime separation and ordering**, not on adding more first-class capability families.

---

## What exists today

## 1. Runtime / control substrate

These systems keep the platform alive, secure, routable, and observable.

Preserve as substrate:

- security plane
- event backbone
- governance kernel
- database / persistence
- cache
- integration bus
- module loader
- request / trace middleware
- health / readiness / telemetry / metrics
- startup bootstrap
- account / auth / session plumbing

These are foundational and should remain the first runtime layer.

### Role

This layer should answer:

- is the platform alive?
- are requests authorized?
- are events moving?
- is state durable?
- are critical modules healthy?
- can other layers safely run?

### Rule

This layer should **not** directly own business prioritization or production behavior.

---

## 2. Knowledge / generation layer

These systems generate executable structure, plans, or routing candidates.

Preserve as generation layer:

- Librarian
- capability discovery
- TaskRouter
- AionMind cognitive execution and context building
- onboarding wizard configuration generation
- workflow terminal compilation
- MSS magnify / simplify / solidify
- UCP execution
- Concept Graph Engine
- golden-path recommendation logic

### Role

This layer should answer:

- what is this request?
- what capabilities can satisfy it?
- what plan or workflow should be generated?
- how should a concept be expanded, simplified, or solidified?

### Outputs

This layer should emit:

- candidate workflows
- ranked capability matches
- plans
- transformed structured content
- routing hints
- generated configuration

### Rule

This layer should generate and interpret structure, but should not directly deliver customer output without passing through orchestration and gating.

---

## 3. Business-guidance layer

These systems guide direction, budgets, market behavior, staffing, demand response, and operating priorities.

Preserve as business-guidance layer:

- cost kernel surfaces
- budget assignment and summaries
- CRM surfaces
- dashboards / portfolio / time tracking / billing surfaces
- marketing and sales automation families
- review and referral automation
- org chart / CEO / business scaling / niche / competitive intelligence families
- account lifecycle and subscription surfaces
- efficiency, supply, safety, causality, and operational status dashboards that influence prioritization

### Role

This layer should answer:

- what should be prioritized?
- where should people or agents spend time?
- what demand should be pursued?
- which cost constraints are active?
- what operational area is bottlenecked?
- should attention shift to advertising, fulfillment, support, sales, or product work?

### Outputs

This layer should emit:

- priorities
- budget envelopes
- queue weights
- escalation signals
- staffing directives
- market targets
- demand classifications
- campaign direction

### Rule

This layer should influence work, not directly produce deliverables unless it hands off into the production layer.

---

## 4. Execution / orchestration layer

These systems decide who performs work and in what order.

Preserve as orchestration layer:

- execution entrypoints
- execution engine
- execution orchestration
- workflow DAG / workflow storage
- queueing
- production routing
- swarms
- bot inventory
- agent dashboards and monitoring
- durable swarm orchestration
- visual swarm builder
- automation scheduler / scaler / marketplace / mode controllers

### Role

This layer should answer:

- which worker or subsystem should handle this task?
- in what sequence should work execute?
- which queue should receive it?
- does this use a workflow, swarm, form path, or production path?

### Outputs

This layer should emit:

- task assignments
- execution packets
- queue transitions
- workflow state transitions
- orchestration traces

### Rule

This layer should orchestrate execution but should not be confused with the business-guidance layer or the deliverable-creation layer.

---

## 5. Production layer

These systems actually create output.

Preserve as production layer:

- production proposals
- production work orders
- production queue
- production routing
- forms task execution / validation / correction paths
- document creation and document transformation flows
- image generation
- industry automation endpoints
- as-built generation
- energy audit generation
- ingestion pipelines that become deliverable inputs
- configuration generation that directly supports deliverable creation

### Role

This layer should answer:

- what product or artifact is being created?
- what inputs are needed?
- which steps materially transform the work?
- what is the output that will be reviewed or delivered?

### Outputs

This layer should emit:

- documents
- proposals
- work orders
- deliverables
- diagrams
- generated assets
- validated task outputs
- packaged production artifacts

### Rule

This layer should focus on making product, not deciding overall business direction.

---

## 6. Gate / review layer

These systems determine whether work may proceed, must stop, or requires human intervention.

Preserve as gate / review layer:

- MFGC
- compliance toggles / reports / scans
- compliance gate wiring
- HITL queues
- HITL QC / acceptance
- credential profiles
- confidence / approval / authority surfaces
- customer acceptance and revision loops

### Role

This layer should answer:

- can the work continue?
- does it violate policy or regulation?
- does it require human approval?
- is it production-ready?
- does it pass customer or QC review?

### Outputs

This layer should emit:

- approve / block / needs-review decisions
- revision requests
- compliance reports
- QC acceptance states
- exception flags
- review traces

### Rule

This layer should mediate progression between production stages.

---

## 7. Delivery / verification layer

These systems move approved output outward and close the loop.

Preserve as delivery layer:

- deliverables listing and packaging
- outbound production steps
- email / domain surfaces when used as delivery channels
- reporting endpoints
- final verification stages in production workflows
- proposal/work-order completion states

### Role

This layer should answer:

- how is approved output packaged?
- where is it delivered?
- how is delivery confirmed?
- what final verification occurs after release?

### Outputs

This layer should emit:

- shipped artifacts
- sent communications
- final verification state
- completion markers
- delivery audit records

---

## 8. Learning / self-healing layer

These systems improve the platform or future behavior rather than producing the current customer output.

Preserve as learning / self-healing layer:

- corrections surfaces
- MurphyCodeHealer proposals and heal cycles
- trainer status / rewards
- self-learning toggle
- self-healing catalog surfaces
- shadow training
- autonomous repair and optimization families
- readiness scanning
- bootstrap diagnostics
- correction-pattern learning

### Role

This layer should answer:

- what failed?
- what pattern should be learned?
- what code or process should be corrected?
- what behavior should change next time?

### Outputs

This layer should emit:

- proposals for repair
- training signals
- learned patterns
- improved policies
- remediation actions
- diagnostics

### Rule

This layer should be downstream of production and review, not mixed into the primary customer-output flow.

---

## Automation inventory by class

## A. Runtime generation systems

These generate plans, structure, or capability matches.

Included families:

- AionMind
- Librarian
- TaskRouter
- onboarding config generation
- workflow terminal compiler
- MSS
- UCP
- Concept Graph Engine
- golden-path recommendation surfaces

## B. Business metric / guidance automations

These direct attention and allocation.

Included families:

- budget / cost summaries
- cost-by-project / department / bot
- CRM
- marketing / sales / campaign families
- org and CEO surfaces
- reviews / referrals / customer response automation
- dashboard and efficiency surfaces
- subscription / billing guidance

## C. Production automations

These create output.

Included families:

- task execution
- form execution and validation
- production proposals
- work orders
- document pipelines
- image generation
- industry engineering outputs
- deliverable builders

## D. Governance automations

These permit or stop progress.

Included families:

- MFGC
- compliance scans
- HITL
- QC / acceptance
- credential and authority checks

## E. Improvement automations

These alter future system quality.

Included families:

- code healer
- correction mining
- shadow trainer
- self-healing loops
- readiness / bootstrap diagnostics

## F. Swarm / bot / agent families

These are orchestration workers and should be modeled as execution-plane assets rather than as a separate business domain.

Included families:

- swarm crew
- advanced swarm
- durable swarm
- visual swarm builder
- domain swarms
- agent dashboards
- bot inventory
- run recorders

---

## Business-guidance vs production automation

## Business-guidance automation

This class changes direction.

Examples:

- campaign metrics shift effort toward acquisition
- cost kernel constrains bot or team spend
- CRM queues increase follow-up volume
- review automation pushes attention toward support or remediation
- org / CEO surfaces redirect operating focus

This class should output:

- priorities
- weights
- budgets
- staffing directives
- escalation decisions
- market or operational focus

## Production automation

This class changes the product state.

Examples:

- proposal generation
- work-order creation
- processing through integrations
- document or asset generation
- validation and packaging
- final deliverable creation

This class should output:

- artifacts
- transformed content
- deliverables
- verified work products

## Hybrid systems

Several families are correctly understood as translators between these two layers.

Examples:

- marketing content pipelines
- self-marketing orchestrator
- production scheduling
- onboarding config generation
- review-response automation

These should not be removed. They should be explicitly marked as **translation layers** between guidance and production.

---

## Multi-loop production model already present in the code

The production workflow creation path already implies multiple loops rather than one linear execution path.

### Existing loop set

1. **Intake / generation loop**
   - incoming request
   - classify and generate proposal/workflow

2. **Constraint / gate loop**
   - safety
   - compliance
   - MFGC
   - readiness decisions

3. **Production loop**
   - processing
   - integration actions
   - output generation

4. **Review / correction loop**
   - HITL review
   - failure returns to processing path
   - revision cycle

5. **Delivery / verification loop**
   - deliver
   - verify
   - close

6. **Learning / improvement loop**
   - accepted patterns
   - corrections
   - healer proposals
   - trainer and self-learning updates

This is the right underlying model and should be elevated into the architecture explicitly.

---

## Recommended runtime order

The system should be refactored conceptually into the following runtime order.

## Layer 0 — Survival substrate

- security
- persistence
- event backbone
- governance
- cache
- integration bus
- health / telemetry / metrics
- session and auth foundations

## Layer 1 — Interpretation and generation

- Librarian
- AionMind
- capability matching
- MSS
- UCP
- graph reasoning
- workflow generation
- onboarding generation

## Layer 2 — Business guidance

- org and CEO systems
- cost governance
- CRM
- marketing direction
- reviews / demand response
- planning and operational prioritization

## Layer 3 — Orchestration

- task routing
- execution engine
- queueing
- swarms
- agent assignment
- workflow state machines

## Layer 4 — Production

- proposals
- work orders
- forms execution
- document and asset creation
- industry pipelines
- deliverable generation

## Layer 5 — Gates and reviews

- MFGC
- compliance
- HITL
- QC
- acceptance
- authority and credential checks

## Layer 6 — Delivery and closure

- packaging
- outbound delivery
- final verification
- status closure
- customer-facing release state

## Layer 7 — Learning and self-healing

- correction learning
- code healer
- trainer
- replay / diagnostics
- self-healing and self-improvement loops

---

## Preservation rules

## Preserve completely

These families should remain first-class:

- AionMind
- MFGC
- MSS
- UCP
- Librarian / TaskRouter
- swarms / agents / bot inventory
- integration bus / event backbone
- HITL / compliance / governance
- production proposal / work-order / scheduling systems

## Rehome, do not remove

These should remain but move into cleaner operational placement:

- marketing and self-marketing into business guidance + hybrid execution
- org / CEO systems into business guidance
- onboarding into interpretation / generation
- self-healing into downstream improvement
- review / referral automation into demand and feedback guidance

## Separate explicitly

The architecture should separate:

- business guidance from execution orchestration
- orchestration from production creation
- production creation from gate / review
- gate / review from delivery
- customer-facing production from self-healing

---

## Immediate documentation and refactor implications

## 1. Stop describing the whole platform as one runtime blob

Future docs should distinguish:

- substrate
- guidance
- orchestration
- production
- gates
- delivery
- learning

## 2. Reframe swarms and bots as execution-plane assets

They should be treated as workers inside orchestration, not as their own top-level strategy layer.

## 3. Reframe production wizard as the visible face of the production layer

The production wizard should sit on top of:

- generated proposal structures
- orchestration
- gates
- HITL
- delivery verification

not on top of a mixed runtime shell.

## 4. Reframe onboarding as configuration generation, not runtime identity

Onboarding should produce configuration and workflow intent for downstream layers.

## 5. Reframe self-healing as downstream improvement

Self-healing should consume:

- traces
- failures
- corrections
- review outcomes

rather than competing with production execution in the same mental layer.

---

## Working architecture statement

Murphy System should be described as:

> a layered automation platform with a survival substrate, generation layer, business-guidance layer, orchestration layer, production layer, gate/review layer, delivery layer, and learning/self-healing layer.

That statement better matches the real execution surface in `src/runtime/app.py` than the current implicit model.

---

## Recommended next artifact

After this document, the next useful artifact should be a **preservation map by endpoint and subsystem family** that tags each existing runtime surface with one of the following labels:

- substrate
- generation
- guidance
- orchestration
- production
- gate/review
- delivery
- learning
- hybrid/translator

That would provide the concrete migration map for future refactoring without deleting capability families.
