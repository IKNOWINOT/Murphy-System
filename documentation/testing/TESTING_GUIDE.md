# Testing Guide

How to run, write, and maintain tests for the Murphy System.

**License:** BSL 1.1 — *Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post*

---

## Table of Contents

1. [Quick Start](#1-quick-start)
2. [Test Suite Overview](#2-test-suite-overview)
3. [Test Categories](#3-test-categories)
4. [Running Tests](#4-running-tests)
5. [Writing New Tests](#5-writing-new-tests)
6. [Test Fixtures and Helpers](#6-test-fixtures-and-helpers)
7. [CI Configuration](#7-ci-configuration)
8. [Coverage](#8-coverage)
9. [Troubleshooting](#9-troubleshooting)
10. [Benchmarks and SLA Tests](#10-benchmarks-and-sla-tests)

---

## 1. Quick Start

```bash
# From the Murphy System/ directory:
cd "Murphy System"
source venv/bin/activate           # Linux/macOS
# venv\Scripts\activate            # Windows

python -m pytest --timeout=60 -v --tb=short
```

All 250+ test files run in isolation. A passing suite prints a summary line like:

```
=========== 1423 passed, 7 skipped in 84.32s ===========
```

---

## 2. Test Suite Overview

```
Murphy System/
└── tests/
    ├── conftest.py                  # global fixtures
    ├── e2e/                         # end-to-end API tests
    │   ├── conftest.py
    │   ├── test_api_endpoints_e2e.py
    │   ├── test_llm_pipeline_e2e.py
    │   └── test_phase3_*.py
    ├── integration/                 # cross-module integration tests
    │   ├── mocks/
    │   ├── test_enterprise_system_integration.py
    │   ├── test_murphy_core_integration.py
    │   ├── test_phase1_murphy_integration.py
    │   ├── test_phase2_cross_module.py
    │   └── test_phase2_enterprise_integration.py
    ├── system/                      # system-level tests
    ├── commissioning/               # startup / import tests
    ├── test_aionmind/               # AionMind kernel tests
    ├── test_auar*.py                # AUAR routing tests (62 tests)
    ├── test_concept_graph*.py       # Concept graph engine (48 tests)
    ├── test_session_context*.py     # Session context manager (37 tests)
    └── test_*.py                    # 200+ unit test files
```

**Key test suites by component:**

| Component | Files | Tests |
|-----------|-------|-------|
| AUAR routing pipeline | `test_auar*.py` | 62 |
| Concept graph engine | `test_concept_graph*.py` | 48 |
| Session context manager | `test_session_context*.py` | 37 |
| Unified Control Protocol | `test_unified_control*.py` | 62 |
| LLM controller | `test_llm*.py` | varies |
| AionMind kernel | `test_aionmind/` | varies |
| API endpoints (e2e) | `e2e/` | varies |

---

## 3. Test Categories

### Unit tests

Located at `tests/test_*.py`. Each file targets a single module or class. Tests are fast (milliseconds) and use no external services.

```
tests/test_confidence_engine.py
tests/test_gate_controller.py
tests/test_constraint_engine.py
...
```

### Integration tests

Located at `tests/integration/`. These tests wire two or more modules together. External services (LLM, database) are mocked via fixtures in `tests/integration/mocks/`.

```
tests/integration/test_murphy_core_integration.py
tests/integration/test_phase2_cross_module.py
```

### End-to-end tests

Located at `tests/e2e/`. These tests spin up a real FastAPI test client (`TestClient` from Starlette) and exercise the full HTTP API stack.

```python
# tests/e2e/test_api_endpoints_e2e.py
from fastapi.testclient import TestClient
from src.runtime.app import create_app

client = TestClient(create_app())

def test_health():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
```

E2e tests require `MURPHY_ENV=test` (set automatically by CI) so that auth is in test mode and no real LLM calls are made.

### Commissioning tests

Located at `tests/commissioning/`. Verify that all 620+ modules import cleanly and register correctly at startup. Run these first when diagnosing import errors.

---

## 4. Running Tests

### All tests

```bash
python -m pytest --timeout=60 -v --tb=short
```

### Specific file or directory

```bash
# Single file
python -m pytest tests/test_auar.py -v

# Directory
python -m pytest tests/integration/ -v

# E2e only
python -m pytest tests/e2e/ -v
```

### By keyword

```bash
# Run tests whose names contain "confidence"
python -m pytest -k "confidence" -v

# Exclude slow tests
python -m pytest -k "not slow" --timeout=60 -v
```

### By marker

```bash
# Unit tests only
python -m pytest -m unit -v

# Integration tests only
python -m pytest -m integration -v

# Skip tests requiring a live LLM key
python -m pytest -m "not llm_live" -v
```

### Stop on first failure

```bash
python -m pytest --timeout=60 -v --tb=short -x
```

### Parallel execution (faster on multi-core)

```bash
pip install pytest-xdist
python -m pytest --timeout=60 -v --tb=short -n auto
```

### With coverage

```bash
python -m pytest --timeout=60 -v --tb=short \
  --cov=. --cov-report=term-missing --cov-report=html
# Open htmlcov/index.html
```

---

## 5. Writing New Tests

### File naming

Place new tests in `tests/` following the naming convention `test_<module_name>.py`.

```
tests/test_my_new_module.py
```

### Minimal unit test

```python
# tests/test_my_new_module.py
"""
Unit tests for MyNewModule.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
"""
import pytest
from bots.my_new_module import MyNewModule


class TestMyNewModule:
    def setup_method(self):
        self.module = MyNewModule()

    def test_basic_operation(self):
        result = self.module.process("input")
        assert result is not None
        assert result["success"] is True

    def test_invalid_input_raises(self):
        with pytest.raises(ValueError, match="input cannot be empty"):
            self.module.process("")

    @pytest.mark.parametrize("value,expected", [
        ("low",    0.2),
        ("medium", 0.5),
        ("high",   0.9),
    ])
    def test_confidence_levels(self, value, expected):
        score = self.module.confidence(value)
        assert abs(score - expected) < 0.1
```

### E2e test with TestClient

```python
# tests/e2e/test_my_endpoint.py
import os
import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("MURPHY_ENV", "test")

from src.runtime.app import create_app  # noqa: E402

client = TestClient(create_app())


def test_my_endpoint_returns_200():
    resp = client.post(
        "/api/execute",
        json={"task": "test task"},
        headers={"Authorization": "Bearer test_key"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "audit_id" in data


def test_my_endpoint_422_on_missing_task():
    resp = client.post(
        "/api/execute",
        json={},
        headers={"Authorization": "Bearer test_key"},
    )
    assert resp.status_code == 422
```

### Test markers

Register custom markers in `pytest.ini` / `pyproject.toml`:

```ini
[pytest]
markers =
    unit: fast, isolated unit tests
    integration: multi-module integration tests
    e2e: full HTTP stack tests
    llm_live: requires a real LLM API key (skipped in CI)
    slow: tests that take > 5s
```

Decorate tests:

```python
@pytest.mark.unit
def test_fast():
    ...

@pytest.mark.llm_live
def test_real_llm_call():
    ...
```

---

## 6. Test Fixtures and Helpers

### Global fixtures (`tests/conftest.py`)

The project `conftest.py` provides:

| Fixture | Scope | Description |
|---------|-------|-------------|
| `test_client` | function | FastAPI `TestClient` with test env |
| `auth_headers` | function | `{"Authorization": "Bearer test_key"}` |
| `mock_llm` | function | Monkeypatched LLM that returns canned responses |
| `tmp_db` | function | Temporary SQLite database (cleaned up after test) |
| `sample_task` | function | Pre-built `POST /api/execute` payload dict |

### Using fixtures

```python
def test_execute_with_mocked_llm(test_client, auth_headers, mock_llm):
    resp = test_client.post(
        "/api/execute",
        json={"task": "Summarize report"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    mock_llm.assert_called_once()
```

### Mocking external LLM calls

```python
from unittest.mock import patch, AsyncMock

@patch("src.llm_controller.call_deepinfra", new_callable=AsyncMock)
async def test_execute_mocks_llm(mock_call):
    mock_call.return_value = {"text": "mocked response", "tokens": 42}
    # ... test body
```

---

## 7. CI Configuration

Tests run automatically via GitHub Actions on every push and pull request to `main`.

### Workflow: `.github/workflows/ci.yml`

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: "Murphy System"
    env:
      MURPHY_ENV: test
      PYTHONPATH: ${{ github.workspace }}/Murphy System
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements_murphy_1.0.txt
      - run: python -m pytest --timeout=60 -v --tb=short
```

### Environment variables in CI

Set secrets in **GitHub → Settings → Secrets and variables → Actions**:

| Secret | Purpose |
|--------|---------|
| `DEEPINFRA_API_KEY` | Required only for `llm_live` tests |
| `MURPHY_API_KEYS` | Test API keys |

The standard test suite runs with `MURPHY_ENV=test` and does **not** require a real LLM key — all LLM calls are mocked.

### Skipping LLM-live tests in CI

```bash
python -m pytest --timeout=60 -v --tb=short -m "not llm_live"
```

---

## 8. Coverage

The project includes a `.coveragerc` configuration:

```bash
# Run tests with coverage
python -m pytest --timeout=60 -v --tb=short \
  --cov=. --cov-report=term-missing

# Generate HTML report
python -m pytest --timeout=60 --cov=. --cov-report=html
open htmlcov/index.html
```

Target coverage: **≥ 80%** for all modules in `src/` and `bots/`.

Exclude files from coverage in `.coveragerc`:

```ini
[coverage:run]
omit =
    */tests/*
    */conftest.py
    setup.py
    murphy_system_1.0_runtime.py   # thin entry point — covered by e2e tests
```

---

## 9. Troubleshooting

### `ModuleNotFoundError` when running pytest

```bash
# Ensure PYTHONPATH includes the Murphy System directory
export PYTHONPATH="/path/to/Murphy System"
python -m pytest ...
```

Or run pytest from inside the `Murphy System/` directory (recommended).

### Tests hang (timeout)

The default timeout is 60 seconds per test. If a test hangs waiting for an external API:

1. Confirm `MURPHY_ENV=test` is set — this disables real LLM calls.
2. Check for missing mock patches on network calls.
3. Use `pytest-timeout` and `--timeout=60` to kill hung tests.

### `401 Unauthorized` in e2e tests

Set `MURPHY_ENV=test` before importing the app, or use the `auth_headers` fixture which provides a pre-configured test key.

### Database errors in tests

Tests use SQLite by default. If a test modifies shared state, use the `tmp_db` fixture to get a fresh isolated database per test.

### Import errors from a specific bot module

```bash
# Run commissioning tests first
python -m pytest tests/commissioning/ -v

# Or check a single import
python -c "from bots.my_module import MyClass"
```

---

## See Also

- [Test Coverage Report](TEST_COVERAGE.md)
- [Testing Standards](TESTING_STANDARDS.md) — IEEE 829/ISO 29119 classification, SLA policy, benchmark regression policy
- [Benchmark Infrastructure](../../tests/benchmarks/README.md) — How to save and compare benchmarks
- [CI Workflow](../../.github/workflows/ci.yml)
- [Contributing Guide](../../CONTRIBUTING.md)

---

## 10. Benchmarks and SLA Tests

The Murphy System includes two layers of production-quality performance validation
in addition to the existing manual benchmarks:

### Statistical Benchmarks (`tests/benchmarks/test_benchmark_statistical.py`)

Uses `pytest-benchmark` for statistically rigorous microbenchmarks with automatic
warm-up, stddev, and regression comparison.

```bash
# Run statistical benchmarks only
pytest tests/benchmarks/test_benchmark_statistical.py --benchmark-only -v

# Save a baseline for regression detection
pytest tests/benchmarks/ --benchmark-only --benchmark-save=baseline

# Fail the build on >10% regression
pytest tests/benchmarks/ --benchmark-only \
    --benchmark-compare=0001_baseline \
    --benchmark-compare-fail=mean:10%
```

See `tests/benchmarks/README.md` for full instructions and the baseline policy.

### SLA Enforcement Tests (`tests/sla/test_sla_enforcement.py`)

Each README "Design Target" has a matching `@pytest.mark.sla` test that fails
the build if the target is not met.

```bash
# Run SLA tests only
pytest tests/sla/ -m sla -v
```

| SLA Test ID | Design Target | Threshold |
|------------|---------------|-----------|
| `SLA-API-001` | API throughput | ≥ 1,000 ops/s |
| `SLA-GATE-001` | Gate evaluation | ≥ 50,000 ops/s |
| `SLA-API-002` | API latency p95 | < 100 ms |
| `SLA-TASK-001` | Task execution | ≥ 100 tasks/s |

For the full testing standards, see [TESTING_STANDARDS.md](TESTING_STANDARDS.md).

---

*Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1*
