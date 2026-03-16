# Autonomous Repair System — ARCH-006

> **Design Label:** ARCH-006 — Autonomous Self-Repair System  
> **Owner:** Backend Team  
> **License:** BSL 1.1  
> **Copyright:** © 2020 Inoni Limited Liability Company, Creator: Corey Post

---

## Overview

The Autonomous Repair System is Murphy's next-generation self-healing infrastructure.  It extends the existing `SelfFixLoop` (ARCH-005) with five new subsystems that together make Murphy the most capable autonomous self-repair platform available:

| Subsystem | What It Does |
|---|---|
| **Multi-Layer Diagnosis Engine** | Static, runtime, semantic, predictive, and wiring analysis in one pass |
| **Terminology Probability Lock-On** | Cross-module semantic consistency using Bayesian inference |
| **Reconciliation Loop** | Kubernetes-inspired desired-state enforcement |
| **Immune System Pattern** | Innate + adaptive fix memorisation with antibody generation |
| **Front-End ↔ Back-End Wiring Validator** | Detects API contract violations between HTML/JS and Flask back-end |

---

## File Structure

```
./
├── src/
│   ├── autonomous_repair_system.py      # Master repair orchestrator
│   ├── innovation_farmer.py             # Open-source innovation harvester
│   ├── generative_knowledge_builder.py  # Industry knowledge set generator
│   └── repair_api_endpoints.py          # REST API for repair system
├── tests/
│   └── test_autonomous_repair_system.py # Comprehensive test suite
└── docs/
    └── AUTONOMOUS_REPAIR_SYSTEM.md      # This document
```

---

## Architecture

```
                    AutonomousRepairSystem
                           │
          ┌────────────────┼────────────────────┐
          │                │                    │
   Multi-Layer       Terminology         Reconciliation
   Diagnosis         Lock-On Engine      Loop
   Engine                 │                    │
   │                Concordance Map     Drift Detector
   ├── Static              │              Convergence
   ├── Runtime       Bayesian Update     Tracker
   ├── Semantic            │
   ├── Predictive    Flagged Terms
   └── Wiring
          │
    Immune System
          │
    ┌─────┴──────┐
  Innate      Adaptive
  Immunity    Immunity
    │             │
  Pre-built   Memory Cells
  Patterns    Antibodies
```

---

## Subsystems

### A. Multi-Layer Diagnosis Engine

The diagnosis engine runs five independent layers in each repair iteration:

#### Static Layer (`StaticDiagnosisLayer`)
- AST-based syntax validation of all `.py` files in `src/`
- Delegates detailed issue detection to `CodeRepairEngine` when available
- Produces `DiagnosisResult` with `layer=DiagnosisLayer.STATIC`

#### Runtime Layer (`RuntimeDiagnosisLayer`)
- Integrates with `BugPatternDetector` to surface active bug patterns
- Consults `SelfImprovementEngine` remediation backlog
- Gracefully degrades when either dependency is unavailable

#### Semantic Layer (`SemanticDiagnosisLayer`)
- Uses `SemanticsBoundaryController` belief-state tracking
- Flags hypotheses with posterior confidence below 0.3 as semantic drift
- Detects boundary condition violations across modules

#### Predictive Layer (`PredictiveDiagnosisLayer`)
- Records time-series of error counts via `record_error_count(count)`
- Computes linear regression slope over the history
- Flags rising trends (slope > 0.5) as predicted failure risk

#### Wiring Layer (`WiringDiagnosisLayer`)
- Scans `onboarding_wizard.html`, `murphy_overlay.js`, `murphy_auth.js` for API calls
- Scans all Flask route registrations in backend files
- Flags: missing backend endpoints, port mismatches (non-8053/8054 ports)

---

### B. Terminology Probability Lock-On Engine (`TerminologyLockOnEngine`)

Builds a **Semantic Concordance Map** across the entire codebase:

1. Scans all `.py` files for 15 key terms: `gate`, `trigger`, `schedule`, `workflow`, `agent`, `task`, `action`, `event`, `pipeline`, `hook`, `session`, `context`, `payload`, `schema`, `model`
2. Computes a **consistency score** (0.0–1.0) using normalised entropy of usage distribution
3. Applies a **Bayesian update** to compute the probability that the term means the same thing across module boundaries
4. Terms with `consistency_score < 0.7` are flagged and `alignment_proposals` are generated

**Integration with No-Code Terminal and Workflow Generator:**  
The concordance map is exposed via `GET /api/repair/terminology` and can be consumed by `nocode_workflow_terminal.py` and `ai_workflow_generator.py` to maintain consistent meaning when building workflows.

---

### C. Reconciliation Loop (`ReconciliationLoop`)

Kubernetes-inspired desired-state enforcement:

1. **Desired State Declaration** — A JSON dict defining a healthy Murphy System:
   ```json
   {
     "all_modules_importable": true,
     "all_api_endpoints_responding": true,
     "all_tests_passing": true,
     "all_gates_functional": true,
     "wiring_connected": true
   }
   ```
2. **Current State Scanner** — `scan_actual_state()` checks real system state
3. **Drift Detector** — `detect_drift(actual)` identifies deviations from desired state
4. **Reconciler** — `reconcile()` produces a `ReconciliationState` with `drift_items`
5. **Convergence Tracker** — `convergence_iterations` increments on each reconcile call

---

### D. Immune System Pattern (`ImmuneSystem`)

#### Innate Immunity
Pre-built recovery procedures for 5 known failure categories:

| Failure Category | Signature | Fix |
|---|---|---|
| Timeout | `timeout` | Increase timeout / add retry backoff |
| Import Error | `ImportError` | Verify dependency installation |
| API Unreachable | `ConnectionRefused` | Check service health and port binding |
| Confidence Drift | `confidence_below_threshold` | Trigger recalibration cycle |
| Gate Bypass | `gate_bypassed` | Re-enable gate enforcement |

#### Adaptive Immunity
- `memorize_fix(error_description, fix_applied, signature)` stores a new `ImmuneMemoryCell`
- Next time the same error signature is detected, the fix is recalled immediately
- Persistent storage via `PersistenceManager` (key: `immune_memory_{cell_id}`)

#### Antibody Generation
When a novel failure is similar-but-not-identical to a memorised fix:
1. Token-overlap similarity is computed across all memory cells
2. If best match > 0.3 similarity, an **antibody** cell is generated
3. The antibody is marked `ImmunityType.ANTIBODY` and proposed for human review

---

### E. Front-End ↔ Back-End Wiring Validator (`WiringDiagnosisLayer`)

Scans:
- **Frontend files:** `onboarding_wizard.html`, `murphy_overlay.js`, `murphy_auth.js`
- **Backend files:** `bots/rest_api.py`, `src/module_compiler/api/endpoints.py`, `src/compute_plane/api/endpoints.py`, `src/execution_orchestrator/api.py`

Detects:
- `MISSING_BACKEND_ENDPOINT` — frontend calls an endpoint not registered in Flask
- `PORT_MISMATCH` — frontend uses a port other than 8053 or 8054
- Report available at `GET /api/repair/wiring`

---

## Innovation Farmer (`innovation_farmer.py`)

Discovers novel patterns and competitive gaps:

### Pattern Library
10 curated open-source patterns with relevance scores and tags:
- Kubernetes Reconciliation Loop (0.95)
- Temporal Workflow Orchestration (0.92)
- AutoGen Multi-Agent Conversation (0.91)
- n8n Node-Based Workflow Builder (0.90)
- LangChain Agent Executor (0.85)
- And more...

### Feature Proposals
For each high-relevance pattern (score ≥ 0.75), a `FeatureProposal` is generated with:
- `what_it_does` — description of the pattern
- `how_to_adapt` — adaptation plan for Murphy
- `murphy_modules_affected` — list of affected Murphy modules
- `implementation_complexity` — low / medium / high
- `expected_business_value` — low / medium / high / very_high

### Competitive Gaps
3 pre-identified gaps with business impact and roadmap entries:
1. No distributed tracing (OTel) — High priority
2. No visual no-code workflow canvas — Medium priority
3. No durable workflow execution — High priority

---

## Generative Knowledge Builder (`generative_knowledge_builder.py`)

Builds probabilistic terminology knowledge sets for any industry domain.

### Supported Domains
`healthcare`, `finance`, `manufacturing`, `legal`, `technology`, `retail`, `logistics`, `education`, `generic`

### Industry Packs
Each pack includes:
- **Terms** with primary and alternative meanings, probability weights, boundary conditions, and standard references
- **Relationships** (synonym, hypernym, hyponym, related, antonym, context_specific)
- **Standards** references (HL7 FHIR, FIX Protocol, OPC-UA, OSCOLA, etc.)

### Boundary Condition Checking
```python
bc = builder.check_boundary_ambiguity(
    term="order",
    industry="finance",
    sender_module="trade_service",
    receiver_module="procurement_service",
)
# Returns BoundaryCondition with ambiguity_detected=True
# because "order" in finance can mean trade order (P=0.85) OR purchase order (P=0.15)
```

### Term Probability Computation
```python
probs = builder.compute_term_probability(
    term="order",
    industry="healthcare",
    observed_context="The doctor placed a lab order for the patient",
)
# Returns: {"medical order": 0.92, "purchase order": 0.08}
```

---

## REST API Reference

Base prefix: `/api/repair`

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/repair/run` | Trigger full repair cycle |
| `GET` | `/api/repair/status` | Current repair system status |
| `GET` | `/api/repair/history` | All past repair reports |
| `GET` | `/api/repair/wiring` | Front-end ↔ back-end wiring report |
| `POST` | `/api/repair/reconcile` | Trigger reconciliation loop |
| `GET` | `/api/repair/immune-memory` | View immune system memory cells |
| `GET` | `/api/repair/proposals` | View all repair proposals |
| `GET` | `/api/repair/terminology` | Get terminology concordance map |
| `POST` | `/api/repair/innovate` | Trigger innovation farming scan |
| `GET` | `/api/repair/innovation/proposals` | View innovation feature proposals |
| `POST` | `/api/repair/knowledge/build` | Build knowledge set for an industry |
| `GET` | `/api/repair/knowledge/<industry>` | Get knowledge set by industry |
| `GET` | `/api/health` | Extended system health |

### Example: Trigger Repair Cycle

```bash
curl -X POST /api/repair/run \
  -H "Content-Type: application/json" \
  -d '{"max_iterations": 10}'
```

Response:
```json
{
  "status": "ok",
  "report": {
    "report_id": "...",
    "status": "completed",
    "iterations_run": 3,
    "proposals_generated": 7,
    "immune_memories_used": 2,
    "antibodies_generated": 1,
    "wiring_issues_found": 0,
    "drift_items_found": 0,
    "terminology_flags": 1,
    "predictions_made": 0,
    "duration_seconds": 1.243,
    "layers_run": ["static", "runtime", "semantic", "predictive", "wiring"]
  }
}
```

### Example: Build Healthcare Knowledge Set

```bash
curl -X POST /api/repair/knowledge/build \
  -H "Content-Type: application/json" \
  -d '{"industry": "healthcare", "language": "python"}'
```

---

## Configuration

All parameters have sensible defaults; override via constructor arguments:

```python
from autonomous_repair_system import AutonomousRepairSystem

repair = AutonomousRepairSystem(
    src_root="src/",
    project_root=".",
    desired_state={
        "all_modules_importable": True,
        "all_api_endpoints_responding": True,
    },
)
report = repair.run_repair_cycle(
    max_iterations=20,
    timeout_seconds=300,
    layers=None,
)
```

---

## Integration with Existing Murphy Components

| Component | How It Integrates |
|---|---|
| `SelfFixLoop` | AutonomousRepairSystem extends SelfFixLoop concepts with 5 new layers |
| `BugPatternDetector` | Used by `RuntimeDiagnosisLayer` for active pattern detection |
| `SelfImprovementEngine` | Remediation backlog feeds `RuntimeDiagnosisLayer` |
| `SelfHealingCoordinator` | Passed as optional dependency; enables event-driven recovery |
| `CodeRepairEngine` | Used by `StaticDiagnosisLayer` for AST-based issue detection |
| `SemanticsBoundaryController` | Used by `SemanticDiagnosisLayer` and `TerminologyLockOnEngine` |
| `InferenceDomainGateEngine` | Used by `GenerativeKnowledgeBuilder` for clarification gate generation |
| `EventBackbone` | All events published on `EventType.SYSTEM_HEALTH` |
| `PersistenceManager` | Repair reports, immune memory, and knowledge sets are persisted |

---

## Safety Guarantees

1. **Never modifies source code automatically** — all code changes generate `RepairProposal` objects with `requires_human_review=True`
2. **Full audit trail** — every cycle start and completion published to `EventBackbone` and saved via `PersistenceManager`
3. **Bounded execution** — `max_iterations` (default 20) and `timeout_seconds` (default 300) cap every loop
4. **Thread-safe** — all shared state guarded by `threading.Lock`; concurrent cycle attempts raise `RuntimeError`
5. **Graceful degradation** — all external dependencies wrapped in `try/except`; system operates with reduced capability when sub-systems are unavailable

---

## Competitive Edge Features (Novel to Murphy)

1. **Semantic Concordance Mapping** — Probabilistic cross-module term consistency via Bayesian inference
2. **Immune System Memory with Antibody Generation** — Adaptive fix memorisation with variant generation
3. **Front-to-Back Wiring Validation** — Automated detection of API contract violations between HTML/JS and Flask
4. **Innovation Farming** — Automated scanning of open-source patterns for feature ideas and competitive gap analysis
5. **Industry-Agnostic Knowledge Generation** — Probabilistic terminology lock-on for any industry domain
6. **Reconciliation Loop with Convergence Tracking** — Kubernetes-style desired-state enforcement for the Murphy runtime
7. **Predictive Failure Prevention** — Time-series based prediction of failures before they occur
