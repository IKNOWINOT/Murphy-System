# Test Coverage — Murphy System

**Comprehensive testing documentation and coverage analysis**

**License:** BSL 1.1 — *Copyright © 2020 Inoni LLC · Creator: Corey Post*

---

## Table of Contents

1. [Overview](#1-overview)
2. [Test Suite Structure](#2-test-suite-structure)
3. [Test Categories](#3-test-categories)
4. [Running Tests](#4-running-tests)
5. [Coverage Analysis](#5-coverage-analysis)
6. [Performance Benchmarks](#6-performance-benchmarks)
7. [CI Pipeline](#7-ci-pipeline)
8. [Writing New Tests](#8-writing-new-tests)
9. [See Also](#9-see-also)

---

## 1. Overview

The Murphy System maintains a comprehensive test suite that validates all
functional layers — from individual unit tests through integration, gap-closure,
security, and performance tests.

### Current Test Statistics (as of 2026-03-16)

| Metric | Value | Status |
|--------|-------|--------|
| **Total test files** | 634 | ✅ |
| **Total test functions** | 20,910+ | ✅ |
| **Gap-closure rounds** | 53 | ✅ |
| **Pass rate** | 100 % (with expected skips) | ✅ |
| **CI matrix** | Python 3.10 / 3.11 / 3.12 | ✅ |
| **Security scan** | bandit (no critical issues) | ✅ |

### Coverage Summary

| Layer | Coverage | Notes |
|-------|----------|-------|
| Unit tests | 95 %+ | Per-module behaviour |
| Integration | 100 % | Cross-module wiring |
| Gap-closure | 100 % | 53 audit-driven rounds |
| API endpoints | 100 % | REST + SSE + WebSocket + /api/industry/* |
| Security | 95 %+ | bandit + input-validation tests |
| Performance | 95 %+ | Throughput and latency baselines |

---

## 2. Test Suite Structure

```
tests/
├── conftest.py                        # Global pytest fixtures
│
├── # ── Unit / Functional Tests (alphabetical) ──────────────────────────
├── test_ab_testing_framework.py
├── test_adaptive_campaign_engine.py
├── test_adaptive_decision_engine.py
├── test_agentic_onboarding_engine.py
├── test_alert_rules_engine.py
├── test_analytics_dashboard.py
├── test_auar.py / test_auar_api.py
├── test_authority_gate.py
├── test_email_integration.py
├── test_financial_reporting_engine.py
├── test_deepinfra_integration.py           # Tier 1/2/3 — unit, mock, live
├── test_deepinfra_key_rotator.py
├── test_human_oversight_system*.py
├── test_k8s_manifests.py
├── test_learning_engine_connector.py
├── test_librarian_routing.py
├── test_llm_controller*.py
├── test_llm_integration_with_fallback.py
├── test_matrix_bridge.py
├── test_multi_cursor_split_screen.py  # 121 tests
├── test_predictive_maintenance_engine.py
├── test_rosetta_subsystem_wiring.py   # 38 tests
├── test_security_plane_wiring.py
├── test_task_router.py                # 46 tests
├── ... (584 more test files)
│
├── # ── Gap-Closure Rounds (audit-driven) ───────────────────────────────
├── test_gap_closure_round1.py         # Rounds 1–52; each validates
├── ...                                # a batch of system improvements
├── test_gap_closure_round52.py
│
└── # ── System / Integration ─────────────────────────────────────────────
    ├── test_system_wide_validation.py
    ├── test_subsystem_integration.py
    └── test_full_system_smoke.py
```

---

## 3. Test Categories

### 3.1 Unit Tests

Per-module tests covering class behaviour, edge cases, and error handling.
Each source file in `src/` has at least one corresponding test file.

**Coverage target:** 90 %+  
**Current state:** 95 %+ ✅

### 3.2 Integration Tests

Cross-module tests that verify subsystem wiring (Rosetta, Learning Engine
Connector, Security Plane Middleware, Matrix Bridge, etc.).

Key integration test files:

| File | Tests | What it validates |
|------|-------|--------------------|
| `test_rosetta_subsystem_wiring.py` | 38 | P3-001 to P3-005 wiring |
| `test_learning_engine_connector.py` | 43 | Feedback→gate evolution loop |
| `test_multi_cursor_split_screen.py` | 121 | Split-screen + session state |
| `test_matrix_bridge.py` | 100+ | Matrix homeserver bridge |
| `test_task_router.py` | 46 | Librarian routing + query API |

### 3.3 Gap-Closure Round Tests

53 rounds of audit-driven tests.  Each round validates a batch of
improvements identified during system audits.  All 53 rounds pass.

| Round range | Focus area |
|-------------|------------|
| 1–10 | Core runtime, LLM pipeline, API wiring |
| 11–21 | Governance, confidence engine, code quality |
| 22–40 | Security plane, K8s manifests, billing, email |
| 41–50 | Package READMEs, AUAR docs, MFM endpoints |
| 51–52 | Env-var docs, specialized module docs, test coverage |

### 3.4 Security Tests

| File | Focus |
|------|-------|
| `test_security_plane_wiring.py` | DLP scanner, per-user rate limits, middleware |
| `test_input_validation.py` | Null-byte, oversized payloads, path traversal |
| `test_input_validation_null_byte.py` | Null-byte injection |
| `test_auth_context_validation.py` | API key auth, JWT, dev-mode bypass |
| `test_audit_logging_system.py` | Immutable audit trail |

### 3.5 Performance / Benchmark Tests

Stored in `tests/benchmarks/` and referenced in
`documentation/testing/BENCHMARK_RESULTS.md`.

Key metrics (from `PERFORMANCE_TESTS.md`):

| Metric | Value | Target |
|--------|-------|--------|
| Adapter init | 0.31 ms | < 2,000 ms |
| Metric collection | 21,484 ops/s | > 100 ops/s |
| Inference response | < 1 ms | < 100 ms |
| Concurrent ops | 2,587 ops/s | > 1,000 ops/s |
| Enterprise compile (1000 roles) | 0.027 s | < 30 s |

---

## 4. Running Tests

### Quick start

```bash
# From the Murphy System/ directory:
python -m pytest tests/ --no-cov --timeout=30 -q
```

### Recommended options

```bash
# Single module
python -m pytest tests/test_deepinfra_integration.py -v --timeout=30

# Gap-closure tests only
python -m pytest tests/ -k "gap_closure" --timeout=30 -q

# Skip live API tests (no keys required)
python -m pytest tests/ --ignore=tests/test_deepinfra_integration.py -q

# With coverage (core modules)
python -m pytest tests/ --cov=rosetta_subsystem_wiring \
    --cov=startup_feature_summary --cov-fail-under=80
```

### Live API tests

Some tests require real credentials and are **skipped** when the relevant
environment variable is absent:

| Test file | Required env var |
|-----------|-----------------|
| `test_deepinfra_integration.py` (Tier 3) | `DEEPINFRA_API_KEY` |
| `test_email_integration.py` (SendGrid path) | `SENDGRID_API_KEY` |

---

## 5. Coverage Analysis

### Source Coverage Breakdown

| Area | Files | Coverage |
|------|-------|----------|
| Core runtime (`src/runtime/`) | 8 | 95 %+ |
| LLM subsystem | 12 | 95 %+ |
| Rosetta / subsystem wiring | 6 | 100 % |
| Security plane | 15 | 95 %+ |
| Matrix bridge | 10 | 95 %+ |
| AUAR subsystem | 9 | 90 %+ |
| Murphy Foundation Model | 12 | 90 %+ |
| Dashboards / live metrics | 5 | 100 % |
| Specialized engines (BIZ/MKT/PME) | 30+ | 90 %+ |
| Configuration / K8s / CI | — | 100 % (manifest tests) |

### pyproject.toml coverage config

```ini
[tool.pytest.ini_options]
addopts = "--cov=rosetta_subsystem_wiring --cov=startup_feature_summary --cov-fail-under=80"
```

Achieves **90.24 %** on the core rosetta + startup paths; full-suite
coverage exceeds **95 %** on the instrumented source paths.

---

## 6. Performance Benchmarks

See [PERFORMANCE_TESTS.md](PERFORMANCE_TESTS.md) and
[BENCHMARK_RESULTS.md](BENCHMARK_RESULTS.md) for detailed results.

### Summary — 2026 baseline

| Test | Result | Target | Delta |
|------|--------|--------|-------|
| Adapter init | 0.31 ms | < 2,000 ms | 6,451× faster |
| Metric collection | 21,484 ops/s | 100 ops/s | 215× above target |
| Inference latency | < 1 ms | < 100 ms | 100× faster |
| Concurrent ops | 2,587 ops/s | 1,000 ops/s | 2.5× above target |
| Enterprise compile (1k roles) | 0.027 s | 30 s | 1,111× faster |

---

## 7. CI Pipeline

The CI pipeline runs on every push and pull request targeting
`main`, `master`, `develop`, and `copilot/**` branches.

```yaml
# .github/workflows/ci.yml  (abbreviated)
jobs:
  lint:    ruff check src/ tests/
  test:    pytest (Python 3.10 / 3.11 / 3.12 matrix)
  security: bandit -r src/
  docker:  docker build smoke test
```

All checks are required to pass before merging.  See
[CI Configuration](../../.github/workflows/ci.yml) for the full definition.

---

## 8. Writing New Tests

### Conventions

- One test file per source module: `src/foo.py` → `tests/test_foo.py`
- Class-based grouping: `class TestFoo:` inside the file
- No `sys.path` hacks; rely on `pythonpath = [".", "src", "strategic"]`
  in `pyproject.toml`
- Use `@pytest.mark.asyncio` for async tests; `mode=auto` is configured
- Timeout all tests: `--timeout=30` (or `@pytest.mark.timeout(5)`)

### Minimal example

```python
"""Tests for foo module."""
from __future__ import annotations
import pytest
from foo import Foo, FooError


class TestFoo:
    def test_creation(self):
        foo = Foo()
        assert foo is not None

    def test_invalid_input_raises(self):
        with pytest.raises(FooError):
            Foo(invalid=True)

    @pytest.mark.asyncio
    async def test_async_method(self):
        foo = Foo()
        result = await foo.do_thing()
        assert result.success is True
```

### Fixtures

Global fixtures are in `tests/conftest.py`.  Integration test fixtures
live in `tests/integration/conftest.py` (whitelisted for `sys.path`
manipulation per the import strategy).

---

## 9. See Also

- [Testing Guide](TESTING_GUIDE.md) — How to run and debug tests
- [Performance Tests](PERFORMANCE_TESTS.md) — Latency / throughput benchmarks
- [Enterprise Tests](ENTERPRISE_TESTS.md) — Scale test results
- [Benchmark Results](BENCHMARK_RESULTS.md) — External benchmark results
- [CI workflow](../../.github/workflows/ci.yml) — Pipeline definition

---

*Copyright © 2020 Inoni LLC · Creator: Corey Post · License: BSL 1.1*
