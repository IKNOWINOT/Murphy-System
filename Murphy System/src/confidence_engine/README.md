# `src/confidence_engine` — Confidence & Authority Engine

Neuro-symbolic control core that computes confidence scores, authority bands, and
artifact trust for the Murphy System's two-phase decision pipeline.

## Public API

```python
from confidence_engine import (
    ConfidenceEngine,
    ArtifactGraph, ArtifactNode,
    ConfidenceState, AuthorityState, AuthorityBand,
    VerificationEvidence, VerificationResult,
    MurphyCalculator,
    Phase,
)

engine = ConfidenceEngine()
state: ConfidenceState = engine.evaluate(artifact_graph)
# state.murphy_index  → 0.0–1.0 (Murphy Confidence Index)
# state.phase         → Phase.MAGNIFY | SOLIDIFY | GATE_SYNTHESIS
```

## Confidence Pipeline

```
Input artifact  →  ArtifactGraph  →  GraphAnalyzer
                                           │
                           ┌──────────────┤
                           ▼              ▼
                    ConfidenceCalculator  AuthorityMapper
                           │              │
                           └──────────────┘
                                   │
                              MurphyCalculator
                                   │
                            ConfidenceState
                           (murphy_index, phase)
```

## Phases

| Phase | Typical Score | Description |
|-------|--------------|-------------|
| `MAGNIFY` | 0.45–0.55 | Initial: source collection |
| `SOLIDIFY` | 0.55–0.75 | Cross-validation in progress |
| `GATE_SYNTHESIS` | 0.75–0.95 | Final: gate evaluation |

## Key Files

| File | Purpose |
|------|---------|
| `confidence_engine.py` | Orchestrator; calls all calculators |
| `confidence_calculator.py` | Bayesian scoring of evidence |
| `authority_mapper.py` | Maps roles to authority bands |
| `murphy_calculator.py` | Computes Murphy Confidence Index |
| `phase_controller.py` | Manages phase transitions |
| `graph_analyzer.py` | Analyzes artifact dependency graph |
| `risk/` | Risk classification sub-package |

## Tests

`tests/test_confidence_engine*.py`, `tests/test_murphy_index*.py`
