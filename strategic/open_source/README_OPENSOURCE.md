# murphy-confidence

> **AI Safety Infrastructure** — Zero-dependency Multi-Factor
> Generative-Deterministic (MFGC) confidence-scoring engine with dynamic
> safety gate compilation.

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE_COMMUNITY)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://python.org)
[![PyPI](https://img.shields.io/pypi/v/murphy-confidence.svg)](https://pypi.org/project/murphy-confidence/)

**Part of the Murphy System** — created by **Corey Post**, [Inoni LLC](https://inoni.com).

---

## What is murphy-confidence?

`murphy-confidence` is a standalone Python library that gives any AI system
a **principled, auditable confidence score** for every decision — and
automatically compiles the right safety gates to enforce that confidence.

It is the open-source core of the **Murphy System**, a full AI safety
operating system designed for regulated industries: healthcare, finance,
manufacturing, and government.

### Key capabilities

- 📐 **MFGC Formula** — `C(t) = w_g·G(x) + w_d·D(x) − κ·H(x)`
- 🔄 **7-Phase Pipeline** — EXPAND → TYPE → ENUMERATE → CONSTRAIN → COLLAPSE → BIND → EXECUTE
- 🚦 **6-Tier Action Classification** — from `PROCEED_AUTOMATICALLY` to `BLOCK_EXECUTION`
- 🛡️ **Dynamic Safety Gates** — EXECUTIVE, OPERATIONS, QA, HITL, COMPLIANCE, BUDGET
- 🔌 **LangChain / LangGraph compatible** — drop-in callback and runnable interfaces
- ✅ **EU AI Act ready** — satisfies Articles 9, 13, and 14 requirements
- ⚡ **Zero external dependencies** — runs anywhere Python 3.10+ runs

---

## Installation

```bash
pip install murphy-confidence
```

---

## Quick Start

### Basic Confidence Scoring

```python
from murphy_confidence import compute_confidence
from murphy_confidence.types import Phase

result = compute_confidence(
    goodness=0.82,   # How good is the AI output?
    domain=0.75,     # How well does it match domain knowledge?
    hazard=0.10,     # What is the risk level?
    phase=Phase.EXECUTE,
)

print(f"Score:   {result.score:.4f}")
print(f"Action:  {result.action.value}")
print(f"Allowed: {result.allowed}")
print(f"Why:     {result.rationale}")
```

Output:
```
Score:   0.6185
Action:  PROCEED_WITH_MONITORING
Allowed: False
Why:     [BLOCKED] Phase=EXECUTE | C=0.6185 (threshold=0.85) | ...
```

### Safety Gate Evaluation

```python
from murphy_confidence import SafetyGate
from murphy_confidence.types import GateType

# HIPAA compliance gate — blocks execution if confidence < 0.90
hipaa_gate = SafetyGate("hipaa_phi", GateType.COMPLIANCE, blocking=True, threshold=0.90)
gate_result = hipaa_gate.evaluate(result)

if gate_result.blocking and not gate_result.passed:
    raise RuntimeError(f"HIPAA gate blocked: {gate_result.message}")
```

### Dynamic Gate Compilation

```python
from murphy_confidence import GateCompiler

compiler = GateCompiler()
gates = compiler.compile_gates(
    result,
    context={"compliance_required": True}
)

for gate in gates:
    gr = gate.evaluate(result)
    print(f"[{gate.gate_id}] {'✓' if gr.passed else '✗'} {gr.message}")
```

### LangChain Integration

```python
from integrations.langchain_safety_layer import MurphyConfidenceRunnable
from murphy_confidence.types import Phase

def my_llm_call(data):
    # ... your LLM logic here
    return {"output": "treatment recommendation..."}

runnable = MurphyConfidenceRunnable(
    inner_fn=my_llm_call,
    phase=Phase.EXECUTE,
    hazard_fn=lambda i, o: 0.25,   # healthcare = elevated hazard
)

result = runnable.invoke({"question": "What medication for patient X?"})
```

---

## The MFGC Formula

```
C(t) = w_g · G(x)  +  w_d · D(x)  −  κ · H(x)
```

| Input | Meaning | Range |
|-------|---------|-------|
| `G(x)` | Generative quality — how good is the AI output? | [0, 1] |
| `D(x)` | Domain match — does it fit the knowledge domain? | [0, 1] |
| `H(x)` | Hazard — what is the risk if this is wrong? | [0, 1] |

Weights (`w_g`, `w_d`, `κ`) are **phase-locked**: as the pipeline moves from
EXPAND → EXECUTE, the system becomes progressively more conservative.

---

## Pipeline Phases & Thresholds

| Phase | Min Threshold | Use |
|-------|--------------|-----|
| EXPAND | 0.50 | Broad ideation |
| TYPE | 0.55 | Type constraints |
| ENUMERATE | 0.60 | Candidate generation |
| CONSTRAIN | 0.65 | Constraint solving |
| COLLAPSE | 0.70 | Option selection |
| BIND | 0.78 | Variable binding |
| **EXECUTE** | **0.85** | **Actual execution** |

---

## Six-Tier Action Classification

| Score | Action | Meaning |
|-------|--------|---------|
| ≥ 0.90 | `PROCEED_AUTOMATICALLY` | Full confidence — no human needed |
| ≥ 0.80 | `PROCEED_WITH_MONITORING` | Proceed but log for review |
| ≥ 0.70 | `PROCEED_WITH_CAUTION` | Proceed with extra checks |
| ≥ 0.55 | `REQUEST_HUMAN_REVIEW` | Surface to a human reviewer |
| ≥ 0.40 | `REQUIRE_HUMAN_APPROVAL` | Must get explicit human sign-off |
| < 0.40 | `BLOCK_EXECUTION` | Hard stop — do not proceed |

---

## Vertical Demos

| Industry | Demo | Gates Used |
|----------|------|-----------|
| Healthcare | `demos/healthcare_ai_safety_demo.py` | COMPLIANCE, HITL, EXECUTIVE |
| Finance | `demos/financial_compliance_demo.py` | BUDGET, COMPLIANCE, HITL |
| Manufacturing | `demos/manufacturing_iot_demo.py` | EXECUTIVE (emergency stop), QA, HITL |

---

## Running the Tests

```bash
# All tests (no external dependencies required)
python -m unittest discover murphy_confidence/tests/ -v

# Or with pytest if available
pytest murphy_confidence/tests/ -v
```

---

## EU AI Act Compliance

`murphy-confidence` is designed to help you comply with the EU AI Act 2024/1689:

| Article | Requirement | Murphy Feature |
|---------|-------------|----------------|
| Art. 9 | Risk Management | MFGC hazard scoring, phase thresholds |
| Art. 13 | Transparency | `ConfidenceResult.rationale` |
| Art. 14 | Human Oversight | HITL gate, `BLOCK_EXECUTION` action |

---

## License

**Community Edition:** Apache License 2.0 — see [LICENSE_COMMUNITY](LICENSE_COMMUNITY)

**Enterprise Edition:** Commercial license for production use in regulated
environments — see [LICENSE_ENTERPRISE](LICENSE_ENTERPRISE) or contact
enterprise@inoni.com.

---

## About

Created by **Corey Post** at **Inoni LLC**.  
The MFGC formula and dynamic gate compilation are patent-pending inventions.

© 2020-2026 Inoni Limited Liability Company. All rights reserved.
