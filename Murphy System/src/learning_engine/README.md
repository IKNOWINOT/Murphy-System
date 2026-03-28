# Learning Engine

The `learning_engine` package drives Murphy's closed-loop self-improvement.
It captures human corrections, learns from them via A/B testing and feature
engineering, and feeds evolved policies back into the execution plane.

## Key Modules

| Module | Purpose |
|--------|---------|
| `correction_capture.py` | Records human corrections with full provenance |
| `correction_storage.py` | Persists corrections to durable storage |
| `correction_models.py` | `Correction`, `CorrectionBatch` Pydantic models |
| `correction_metadata.py` | Metadata enrichment (timestamp, operator, confidence delta) |
| `ab_testing.py` | A/B test harness for policy variants |
| `adaptive_decision_engine.py` | Updates decision weights based on correction history |
| `feature_engineering.py` | Derives learning features from raw operational data |

## Usage

```python
from learning_engine.correction_capture import CorrectionCapture
capture = CorrectionCapture()
await capture.record(task_id="t-1", before={...}, after={...}, operator="alice")
```
