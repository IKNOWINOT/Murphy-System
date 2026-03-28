# Gate Synthesis

The `gate_synthesis` package generates, compiles, and manages quality-gates
that guard every execution path in the Murphy System.  Each gate encodes
acceptance criteria, failure modes, and escalation policies.

## Key Modules

| Module | Purpose |
|--------|---------|
| `gate_synthesis.py` | `GateSynthesizer` — generates gate specs from task descriptors |
| `gate_generator.py` | Template-based gate creation with parameterised thresholds |
| `gate_lifecycle_manager.py` | Tracks gate states: `PENDING → EVALUATING → PASSED / FAILED` |
| `failure_mode_enumerator.py` | FMEA-style enumeration of potential failure modes per gate |
| `murphy_estimator.py` | Statistical estimator for gate pass-rate prediction |
| `rsc_telemetry.py` | Emits gate metrics to the RSC telemetry bus |
| `models.py` | `Gate`, `GateSpec`, `GateResult`, `FailureMode` dataclasses |
| `api_server.py` | REST API for gate CRUD and evaluation triggering |

## Usage

```python
from gate_synthesis.gate_synthesis import GateSynthesizer
synthesizer = GateSynthesizer()
gate = synthesizer.synthesize(task_descriptor={...})
result = gate.evaluate(execution_result={...})
```
