# Data Flows

How data moves through the Murphy System pipeline — from user input through the
control plane, gate evaluation, and execution engines to final output.

---

## High-Level Flow

```
User Request
    │
    ▼
REST API (FastAPI, port 8000)
    │
    ├──→ AionMind 2.0 cognitive pipeline (if available)
    │        │
    │        ▼
    │    Context Engine → Capability Registry → Reasoning Engine
    │        │
    │        ▼
    │    RSC Integration → Orchestration → Memory (STM/LTM)
    │        │
    │        ▼
    │    cognitive_execute() ──→ legacy fallback (if needed)
    │
    ▼
Universal Control Plane
    │
    ├── Engine selection (Sensor, Actuator, Database, API, Content, Command, Agent)
    │
    ▼
Two-Phase Orchestrator
    │
    ├── Phase 1: Generative Setup
    │     • Analyse request
    │     • Determine control type
    │     • Select engines
    │     • Discover constraints
    │     • Create ExecutionPacket
    │
    ├── Phase 2: Production Execution
    │     • Load session
    │     • Execute with selected engines
    │     • Deliver results
    │     • Learn from execution
    │
    ▼
Phase Controller (7-phase lifecycle)
    │
    EXPAND → TYPE → ENUMERATE → CONSTRAIN → COLLAPSE → BIND → EXECUTE
    │
    │  (confidence must meet threshold at each phase)
    │
    ▼
Gate Evaluation (COMPLIANCE → BUDGET → EXECUTIVE → OPERATIONS → QA → HITL)
    │
    ├── APPROVED  → continue
    ├── BLOCKED   → halt execution
    ├── NEEDS_REVIEW → route to HITL queue
    │
    ▼
Execution Engine
    │
    ├── Task Executor (individual tasks, retry logic)
    ├── Workflow Orchestrator (multi-step DAGs)
    ├── Decision Engine (rule-based autonomous decisions)
    ├── State Manager (state transitions, persistence)
    │
    ▼
Output / Response
```

---

## Key Data Objects

### ExecutionPacket

Created during Phase 1 (Generative Setup), the `ExecutionPacket` carries:

- Selected engines and their configuration
- Discovered constraints and risk profile
- Confidence score
- Session metadata

### Gate Evaluation Results

Each gate in the sequence produces a `GateEvaluation`:

```python
{
    "gate_id": "gate-abc123",
    "gate_type": "COMPLIANCE",
    "decision": "APPROVED",
    "reason": "All compliance rules passed",
    "policy": "ENFORCE",
    "evaluated_at": "2026-03-10T14:30:00Z"
}
```

### Memory Artifacts

Data flows through the 4-plane memory architecture:

1. **Sandbox** — unverified hypotheses and explorations
2. **Working** — verified and actively used artifacts
3. **Control** — high-confidence reusable patterns
4. **Execution** — production-ready validated artifacts

Artifacts promote upward as confidence increases.

---

## Integration Points

| Layer | External I/O |
|-------|-------------|
| REST API | HTTP clients, webhooks |
| Database tier | PostgreSQL (persistent), Redis (cache) |
| LLM integration | DeepInfra, OpenAI, or other providers via `MURPHY_LLM_PROVIDER` |
| Connector framework | External APIs, IoT sensors, third-party services |
| Board / CRM modules | Monday.com parity endpoints |

---

## See Also

- [Architecture Overview](ARCHITECTURE_OVERVIEW.md)
- [System Components](SYSTEM_COMPONENTS.md)
- [Phase Controller](../components/PHASE_CONTROLLER.md)
- [Gate Compiler](../components/GATE_COMPILER.md)
