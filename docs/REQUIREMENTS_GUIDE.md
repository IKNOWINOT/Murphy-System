# Murphy System — Requirements Files Guide

> **Created:** 2026-03-27  
> **Addresses:** A-013 (Requirements file documentation)

---

## Requirements Files Overview

Murphy System uses multiple requirements files for different use cases:

| File | Purpose | Size | When to Use |
|------|---------|------|-------------|
| `requirements_core.txt` | Minimal API server | ~20 deps | Quick local dev |
| `requirements_ci.txt` | CI test runner | ~35 deps | GitHub Actions |
| `requirements_murphy_1.0.txt` | Full production | ~80 deps | Docker/Production |
| `requirements.txt` | Development | ~60 deps | Full local dev |
| `requirements_benchmarks.txt` | Performance tests | ~10 deps | Benchmarking only |

---

## Dependency Hierarchy

```
requirements_core.txt          ← Minimal (API only)
        ↓
requirements_ci.txt            ← + Testing + DB + Monitoring
        ↓
requirements.txt               ← + ML + NLP + Matrix
        ↓
requirements_murphy_1.0.txt    ← + All integrations
        ↓
requirements_benchmarks.txt    ← + Performance tools (optional)
```

---

## File Details

### `requirements_core.txt` — Minimal API Server

**Use case:** Fastest possible install for just running the API server

**Includes:**
- FastAPI + Uvicorn
- Pydantic validation
- Basic crypto (JWT, bcrypt)
- HTTP clients (httpx, requests)
- YAML/JSON parsing

**Install:**
```bash
pip install -r requirements_core.txt
python murphy_system_1.0_runtime.py
```

### `requirements_ci.txt` — CI Test Runner

**Use case:** GitHub Actions CI pipeline

**Includes everything in `core` plus:**
- Flask (for comparison tests)
- SQLAlchemy + Alembic (DB migrations)
- Prometheus client (metrics)
- Testing utilities (not pytest — installed separately)

**Install:**
```bash
pip install -r requirements_ci.txt
pytest tests/
```

### `requirements_murphy_1.0.txt` — Full Production

**Use case:** Docker container, production deployment

**Includes everything in `ci` plus:**
- Matrix integration (matrix-nio)
- ML/NLP (when optional deps installed)
- All platform integrations
- Hardware interfaces (Modbus, BACnet)

**Install:**
```bash
pip install -r requirements_murphy_1.0.txt
```

### `requirements.txt` — Development

**Use case:** Full local development with all features

**Similar to murphy_1.0 but may include:**
- Development tools
- Debug utilities
- Documentation generators

**Install:**
```bash
pip install -r requirements.txt
```

### `requirements_benchmarks.txt` — Performance Testing

**Use case:** Running performance benchmarks only

**Includes:**
- locust (load testing)
- memory-profiler
- line-profiler
- py-spy

**Install:**
```bash
pip install -r requirements_benchmarks.txt
python scripts/run_benchmarks.py
```

---

## Version Pinning Strategy

1. **Core dependencies:** Pinned to major.minor (e.g., `fastapi>=0.100.0`)
2. **Security deps:** Pinned to specific patch (e.g., `cryptography>=41.0.0`)
3. **Optional deps:** Loose pins or unpinned
4. **Lock file:** `requirements.lock` for reproducible builds

---

## Updating Dependencies

```bash
# Update all to latest compatible
pip install --upgrade -r requirements.txt

# Generate lock file
pip freeze > requirements.lock

# Check for security vulnerabilities
pip-audit -r requirements.txt
```

---

## Troubleshooting

### "ModuleNotFoundError" in CI

The CI uses `requirements_ci.txt` which excludes heavy dependencies.
If your code needs torch/spacy/etc., guard with try/except:

```python
try:
    import torch
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False
```

### Version conflicts

```bash
# Check what's installed
pip list

# Check for conflicts
pip check

# Force reinstall
pip install --force-reinstall -r requirements.txt
```
