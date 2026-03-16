# Compute Plane

The `compute_plane` package is Murphy's deterministic symbolic-computation
layer.  It runs analyses, parses structured data, and solves constraint
problems without relying on probabilistic LLM inference.

## Key Modules

| Module | Purpose |
|--------|---------|
| `service.py` | `ComputeService` — orchestrates analysis / parse / solve workflows |
| `analyzers/` | Domain-specific analysers (financial, code, document, …) |
| `parsers/` | Structured-data parsers (JSON schema, CSV, XML, …) |
| `models/` | Pydantic models for compute requests and results |
| `api/` | FastAPI sub-application exposing compute endpoints |

## Usage

```python
from compute_plane.service import ComputeService
svc = ComputeService()
result = svc.analyze(domain="financial", data={...})
```
