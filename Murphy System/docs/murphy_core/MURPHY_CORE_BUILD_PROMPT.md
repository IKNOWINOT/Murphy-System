# Murphy Core Build Prompt

Use this prompt as the canonical implementation brief for building Murphy Core inside the existing Murphy System repository. Do not start over in a new project. Build a clean internal spine that preserves reusable subsystems, keeps UI compatibility, and runs as a production webapp server.

## Mission

Build **Murphy Core** as the canonical runtime spine for the Murphy System webapp.

Murphy Core must:
- preserve existing working subsystems where possible
- run as a production server for a web application
- keep the UI side wired to real backend contracts
- centralize inference, routing, gating, execution, and tracing
- prevent architecture drift by following the linked documents in `docs/murphy_core/`
- remain additive and non-destructive: copy, wrap, adapt, and deprecate; do not casually delete legacy surfaces

## Non-negotiable outcome

The system must converge on one canonical execution path:

`request -> intake -> inference -> rosetta normalization -> gate/control expansion -> routing -> execution -> trace -> delivery`

Every implementation decision must reinforce that path.

## Project constraints

1. Work **inside the existing repo**.
2. Create new files under `src/murphy_core/` and `docs/murphy_core/`.
3. Preserve legacy modules by wrapping or adapting them unless they are clearly unusable.
4. Do not let docs, runtime wiring, and module registry drift apart.
5. Use the linked instruction files as hard contracts:
   - `docs/murphy_core/VIBE_CODE_SYSTEM.md`
   - `docs/murphy_core/MODULE_REGISTRY_STRATEGY.md`
   - `docs/murphy_core/WEBAPP_PRODUCTION_TARGET.md`
6. If a legacy module is kept, classify it explicitly as one of:
   - `core`
   - `adapter`
   - `optional`
   - `experimental`
   - `deprecated`
   - `declared_only`
7. Never allow raw LLM text output to directly trigger execution. It must be compiled into typed control objects first.

## Product intent

Murphy is not just a chatbot. It is a policy-gated, route-aware execution platform for a webapp.

Murphy Core should make the system behave like this:
- UI sends typed requests to backend API
- backend performs semantic inference through centralized provider layer
- rosetta/canonical semantic layer normalizes meaning
- gate system decides what is allowed
- routing selects deterministic, hybrid, swarm, or specialist execution path
- execution consumes only typed plans and typed actions
- every run emits a full trace
- UI can inspect health, readiness, trace summaries, capabilities, and active modules

## Required top-level architecture

Implement or formalize these layers under `src/murphy_core/`:

1. `contracts.py`
   - shared dataclasses / models for request, inference, control, execution, trace, capability status

2. `registry.py`
   - merged module registry using baseline inventory, manifest metadata, file existence, and runtime wiring status

3. `providers.py`
   - centralized inference provider abstraction with fallback chain

4. `rosetta.py`
   - canonical semantic normalization layer
   - input: inference + context
   - output: normalized intent, entities, constraints, domain tags, allowed module classes

5. `gates.py`
   - security, compliance, HITL, authority, confidence, budget and execution policy gates

6. `routing.py`
   - route typed tasks to deterministic, hybrid, swarm, or specialist handlers

7. `planner.py`
   - compile normalized inference into typed control expansions and execution plans

8. `executor.py`
   - execute typed plans only
   - wrap legacy execution engines instead of bypassing them

9. `tracing.py`
   - emit `ControlTrace` objects for every request

10. `capabilities.py`
   - effective capabilities computation
   - expose what is actually live, optional, experimental, or missing

11. `app.py`
   - FastAPI production app entrypoint for Murphy Core
   - expose health, readiness, capabilities, execute, chat, trace, and registry endpoints

## UI requirements

Assume Murphy is a real webapp, not a toy API.

The UI/backend contract must support:
- session-aware request handling
- `/api/health`
- `/api/readiness`
- `/api/capabilities/effective`
- `/api/registry/modules`
- `/api/execute`
- `/api/chat`
- `/api/traces/{trace_id}`
- `/api/traces/recent`
- `/api/system/map`

UI expectations:
- the frontend can ask which modules are live
- the frontend can inspect why a request was blocked
- the frontend can inspect which route was chosen
- the frontend can surface HITL requirements
- the frontend can present deterministic vs hybrid vs swarm execution mode
- the frontend can render trace summaries and health state

## Production server requirements

Implement Murphy Core as a production-oriented FastAPI server:
- explicit startup/shutdown lifecycle
- health and readiness registration
- structured logging
- request IDs / trace IDs
- configurable provider fallback
- dependency-injected service container or service registry
- no duplicate routes
- no shim confusion about runtime authority
- one canonical app entrypoint

Prefer:
- `src/murphy_core/app.py` as canonical app
- a small wrapper from existing runtime only if compatibility is required

## Inference contract

Every request must become a typed `InferenceEnvelope`:
- request id
- user intent
- inferred goals
- inferred entities
- inferred constraints
- domain tags
- confidence
- risk score
- proposed route classes
- required approvals
- provider provenance

## Rosetta contract

Rosetta is Murphy's semantic constitution.

It must normalize:
- intent names
- entity names
- domain vocabulary
- capability names
- gate vocabulary
- execution classes

Rosetta output should answer:
- what the user wants in canonical terms
- which modules may satisfy it
- which gates are relevant
- whether the task belongs to deterministic, hybrid, specialist, or swarm execution

## Planner contract

Planner must convert normalized inference into `ControlExpansion`:
- selected route
- selected module families
- execution constraints
- allowed actions
- fallback policy
- approval requirements
- expected outputs

Then compile into `GatedExecutionPlan`:
- typed steps only
- module-safe action payloads only
- no raw provider prose

## Gate contract

Gate evaluation must be centralized and explicit.

Every execution plan must pass through gates for:
- security
- compliance
- authority
- confidence
- HITL
- budget / cost
- execution policy

Gate output should always be typed:
- allow
- review
- block
- requires_hitl
- rationale list

## Routing contract

Router should support these modes:
- `deterministic`
- `hybrid`
- `specialist`
- `swarm`
- `legacy_adapter`

Route choice must be visible in trace and UI.

## Trace contract

Every request must produce `ControlTrace` with:
- request summary
- inference summary
- rosetta normalization result
- gate decisions
- selected route
- selected modules
- execution status
- outcome
- recovery/fallback path
- timestamps

## Registry contract

The registry must merge multiple sources of truth:
- capability baseline inventory
- matrix/module manifest metadata
- file existence in repo
- runtime wiring status
- effective capability state

Per module track:
- module name
- source path
- category
- runtime role
- status
- emits
- consumes
- commands
- used by runtime
- notes

## Legacy preservation strategy

Preserve useful legacy subsystems via adapters.

Examples of likely adapter families:
- runtime / existing API handlers
- control-plane separation
- deterministic routing engine
- AI workflow generator
- self-codebase swarm
- visual swarm builder
- event backbone
- integration bus
- HITL controller
- security plane
- delivery adapters

Do not re-implement mature logic blindly. Wrap it behind Murphy Core contracts.

## Definition of done

Murphy Core is done when:
- one canonical FastAPI app runs as the production webapp backend
- one canonical request path exists
- one centralized provider layer exists
- one registry reports actual module state
- one capabilities endpoint reports effective capability truth
- one trace format exists
- UI can inspect route, gates, and status
- docs in `docs/murphy_core/` still match runtime and contracts

## Working style

Build in small, linked steps.

For every new change:
1. update or preserve the contract in `contracts.py`
2. update registry/capability truth if module state changed
3. update docs if runtime path changed
4. preserve adapters for legacy behavior
5. prefer additive migration over destructive rewrite

## Immediate first implementation tasks

1. Create `src/murphy_core/` package.
2. Add contracts for request/inference/control/trace/capability.
3. Add registry model and status enums.
4. Add production FastAPI app skeleton.
5. Add capabilities and registry endpoints.
6. Add centralized provider abstraction.
7. Add Rosetta normalization stub with canonical fields.
8. Add gate evaluation pipeline stub.
9. Add deterministic route and legacy adapter route.
10. Wire trace creation end-to-end.

## Forbidden failure modes

Do not:
- create a second accidental runtime authority
- leave docs disconnected from code
- bypass gates for convenience
- let provider prose drive execution directly
- claim capabilities that are not actually wired
- silently overwrite legacy files without a compatibility strategy

## Final instruction

Build Murphy Core as the strict, typed, production-ready center of the existing Murphy System. Preserve useful legacy work, but force everything through one canonical semantic, gate, route, execute, and trace path.