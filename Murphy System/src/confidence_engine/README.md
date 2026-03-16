# Confidence Engine

The `confidence_engine` package calculates, validates, and propagates
confidence scores for every decision the Murphy System makes.  Scores
flow from raw evidence through a graph analyser into gated execution paths.

## Key Modules

| Module | Purpose |
|--------|---------|
| `confidence_engine.py` | Core scoring pipeline; aggregates signals into a `[0, 1]` score |
| `confidence_calculator.py` | Weighted-average and Bayesian update formulas |
| `authority_mapper.py` | Maps source identities to authority weights |
| `graph_analyzer.py` | Traverses evidence graphs to propagate confidence upstream |
| `credential_verifier.py` | Validates external credentials that anchor trust |
| `credential_interface.py` | Protocol for plugging in custom credential sources |
| `external_validator.py` | Calls third-party attestation APIs |
| `models.py` | Pydantic models: `ConfidenceScore`, `EvidenceNode`, `AuthorityWeight` |
| `api_server.py` | FastAPI sub-application for confidence queries |

## Usage

```python
from confidence_engine.confidence_engine import ConfidenceEngine
engine = ConfidenceEngine()
score = engine.calculate(evidence_nodes=[...])  # returns float in [0, 1]
```
