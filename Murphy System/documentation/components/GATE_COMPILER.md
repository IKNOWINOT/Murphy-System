# Gate Compiler

The Gate Compiler synthesizes safety gates from domain templates, risk profiles, and
phase requirements. It is implemented across two modules:

- **`gate_execution_wiring.py`** — runtime evaluation of gates in dependency order.
- **`gate_builder.py`** — template-based gate generation for common system types.

---

## Gate Types

Gates are categorised by the organisational concern they protect:

| Gate Type | Purpose |
|-----------|---------|
| `COMPLIANCE` | Regulatory and policy adherence |
| `BUDGET` | Cost and resource budget limits |
| `EXECUTIVE` | Strategic and executive-level approval |
| `OPERATIONS` | Operational safety and stability |
| `QA` | Quality assurance and testing |
| `HITL` | Human-in-the-loop review |

---

## Gate Decisions

Each gate evaluation returns one of four decisions:

| Decision | Meaning |
|----------|---------|
| `APPROVED` | Gate passed — execution may continue |
| `BLOCKED` | Gate failed — execution halted |
| `NEEDS_REVIEW` | Requires human review before proceeding |
| `ESCALATED` | Forwarded to a higher authority |

---

## Gate Policies

Policies control what happens when a gate blocks execution:

| Policy | Behaviour |
|--------|-----------|
| `ENFORCE` | Block execution if the gate fails |
| `WARN` | Log a warning but allow execution to continue |
| `AUDIT` | Record the result for audit trail only |

---

## Evaluation Sequence

Gates are evaluated in a fixed dependency order defined by `GATE_SEQUENCE`:

```
COMPLIANCE → BUDGET → EXECUTIVE → OPERATIONS → QA → HITL
```

This ensures that regulatory checks run first and human review runs last, after
all automated checks have passed.

```python
wiring = GateExecutionWiring()
wiring.register_gate(GateType.COMPLIANCE, my_compliance_check)
wiring.register_gate(GateType.QA, my_qa_check)

results = wiring.evaluate_gates(execution_context)
if wiring.can_execute(results):
    # All ENFORCE-policy gates passed
    proceed_with_execution()
```

---

## GateBuilder Templates

`GateBuilder` provides pre-configured gate sets for common system types. Each
template maps a list of **safety concerns** to concrete gate definitions:

### Safety Concerns (10 built-in)

| Concern | Gate Name |
|---------|-----------|
| `data_loss` | Data Loss Prevention Gate |
| `security_breach` | Security Gate |
| `invalid_input` | Input Validation Gate |
| `system_overload` | Load Balancing Gate |
| `data_corruption` | Data Integrity Gate |
| `unauthorized_action` | Authorization Gate |
| `performance_degradation` | Performance Gate |
| `compliance_violation` | Compliance Gate |
| `resource_exhaustion` | Resource Gate |
| `dependency_failure` | Dependency Gate |

### System Templates

| System Type | Default Gates |
|-------------|---------------|
| **Web apps** | security_breach, invalid_input, system_overload, unauthorized_action |
| **Data systems** | data_loss, data_corruption, compliance_violation, resource_exhaustion |
| **AI systems** | invalid_input, performance_degradation, resource_exhaustion, compliance_violation |

---

## See Also

- [Confidence Engine](CONFIDENCE_ENGINE.md)
- [Phase Controller](PHASE_CONTROLLER.md)
- [Architecture Overview](../architecture/ARCHITECTURE_OVERVIEW.md)
