# murphy-confidence

> **Zero-dependency** Multi-Factor Generative-Deterministic (MFGC) confidence-scoring
> engine with dynamic safety gate compilation for autonomous AI systems.

Part of the **Murphy System** — created by **Corey Post**, Murphy Collective.

---

## Installation

```bash
pip install murphy-confidence
```

Or from source:

```bash
cd Murphy\ System/strategic/murphy_confidence
pip install .
```

---

## Quick Start

```python
from murphy_confidence import compute_confidence, GateCompiler
from murphy_confidence.types import Phase

# Score a potential AI action
result = compute_confidence(
    goodness=0.82,   # G(x): how good is the generated output?
    domain=0.75,     # D(x): how well does it match domain knowledge?
    hazard=0.10,     # H(x): what is the risk/hazard level?
    phase=Phase.EXECUTE,
)

print(result.score)    # e.g. 0.6185
print(result.action)   # GateAction.PROCEED_WITH_MONITORING
print(result.allowed)  # True / False
print(result.rationale)

# Compile safety gates from the result
compiler = GateCompiler()
gates = compiler.compile_gates(result, context={"compliance_required": True})
for gate in gates:
    gate_result = gate.evaluate(result)
    print(gate_result.message)
```

---

## MFGC Formula

```
C(t) = w_g · G(x)  +  w_d · D(x)  −  κ · H(x)
```

| Symbol | Meaning                                    | Range   |
|--------|--------------------------------------------|---------|
| G(x)   | Generative quality score                   | [0, 1]  |
| D(x)   | Domain-deterministic match score           | [0, 1]  |
| H(x)   | Hazard / risk factor                       | [0, 1]  |
| w_g    | Weight for generative component            | 0–1     |
| w_d    | Weight for domain component                | 0–1     |
| κ      | Hazard penalty multiplier                  | 0–1     |

Weights are **phase-locked** and become more conservative as the pipeline
progresses from `EXPAND` → `EXECUTE`.

---

## Pipeline Phases

| Phase      | Threshold | Description                        |
|------------|-----------|------------------------------------|
| EXPAND     | 0.50      | Broad idea generation              |
| TYPE       | 0.55      | Type-system constraint application |
| ENUMERATE  | 0.60      | Candidate enumeration              |
| CONSTRAIN  | 0.65      | Constraint solving                 |
| COLLAPSE   | 0.70      | Option collapse                    |
| BIND       | 0.78      | Variable binding                   |
| EXECUTE    | 0.85      | Actual execution                   |

---

## Six-Tier Action Classification

| Score Range | Action                     |
|-------------|----------------------------|
| ≥ 0.90      | PROCEED_AUTOMATICALLY      |
| ≥ 0.80      | PROCEED_WITH_MONITORING    |
| ≥ 0.70      | PROCEED_WITH_CAUTION       |
| ≥ 0.55      | REQUEST_HUMAN_REVIEW       |
| ≥ 0.40      | REQUIRE_HUMAN_APPROVAL     |
| < 0.40      | BLOCK_EXECUTION            |

---

## Safety Gates

Six gate types are supported:

| GateType    | Blocking by Default | Default Threshold |
|-------------|---------------------|-------------------|
| EXECUTIVE   | Yes                 | 0.85              |
| OPERATIONS  | No                  | 0.70              |
| QA          | No                  | 0.75              |
| HITL        | Yes                 | 0.80              |
| COMPLIANCE  | Yes                 | 0.90              |
| BUDGET      | No                  | 0.65              |

```python
from murphy_confidence import SafetyGate
from murphy_confidence.types import GateType

hipaa_gate = SafetyGate("hipaa_phi", GateType.COMPLIANCE, blocking=True, threshold=0.95)
gr = hipaa_gate.evaluate(result)
if not gr.passed and gr.blocking:
    raise RuntimeError(f"HIPAA gate blocked execution: {gr.message}")
```

---

## Running Tests

```bash
python -m pytest murphy_confidence/tests/ -v
# or without pytest:
python -m unittest discover murphy_confidence/tests/ -v
```

---

## License

Apache 2.0 — see `LICENSE_COMMUNITY`.

© 2020-2026 Inoni Limited Liability Company. All rights reserved. Created by: Corey Post.
