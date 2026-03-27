# Testing Standards

Formal testing standards for the Murphy System, aligned with IEEE 829 / ISO 29119.

**License:** BSL 1.1 — *Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post*

---

## Table of Contents

1. [Test Classification](#1-test-classification)
2. [Performance Testing Standards](#2-performance-testing-standards)
3. [Coverage Standards](#3-coverage-standards)
4. [SLA Testing Standards](#4-sla-testing-standards)
5. [Benchmark Regression Policy](#5-benchmark-regression-policy)
6. [Mutation Testing (Future)](#6-mutation-testing-future)

---

## 1. Test Classification

### 1.1 Test ID Format

All tests must carry a unique Test ID in their docstring:

```
{TYPE}-{MODULE}-{NNN}
```

| Segment | Values | Examples |
|---------|--------|---------|
| `TYPE` | `UNIT`, `INT`, `E2E`, `PERF`, `SLA`, `COMM` | `PERF`, `SLA`, `UNIT` |
| `MODULE` | Short module abbreviation (3–6 chars) | `GATE`, `UCP`, `PCF`, `API`, `CONF` |
| `NNN` | Three-digit sequence number | `001`, `042`, `100` |

**Examples:** `PERF-GATE-001`, `SLA-API-001`, `UNIT-CONF-042`

### 1.2 Priority Levels

| Level | Definition | Build Impact |
|-------|-----------|-------------|
| **Critical** | Failure blocks release immediately | Fail build |
| **High** | Failure triggers mandatory review | Fail build |
| **Medium** | Failure creates a tracked issue | Warn only |
| **Low** | Informational / improvement target | Report only |

### 1.3 Required Fields per Test Case

Each test function's docstring must include:

| Field | Description |
|-------|-------------|
| **Test ID** | Unique identifier in `{TYPE}-{MODULE}-{NNN}` format |
| **Objective** | One-sentence description of what is being verified |
| **Preconditions** | Environment or state required before the test runs |
| **Input** | Exact data / parameters used |
| **Expected Result** | Exact pass/fail threshold or assertion condition |
| **Priority** | Critical / High / Medium / Low |
| **Traceability** | Link to the requirement, design target, or README section |

**Example:**

```python
def test_gate_evaluation_throughput(benchmark):
    """Gate evaluation must sustain >50,000 ops/s (pytest-benchmark, statistical).

    Test ID: PERF-GATE-001
    Objective: Verify gate evaluation meets throughput design target.
    Preconditions: GateExecutionWiring importable; one QA gate registered.
    Input: 500 iterations × benchmark rounds; task = {"type": "standard"}.
    Expected Result: benchmark mean ops/s > 50,000.
    Priority: Critical
    Traceability: README Design Target — Gate Evaluation Throughput
    """
```

---

## 2. Performance Testing Standards

### 2.1 Tooling

All performance benchmarks **must** use `pytest-benchmark` fixtures, not manual
`time.time()` loops.  `pytest-benchmark` provides:

- Automatic warm-up rounds (eliminates JIT / cache noise)
- Statistical output: mean, stddev, min, max, median, IQR
- Built-in `--benchmark-save` / `--benchmark-compare` for regression detection
- JSON output for CI dashboards

Install:

```bash
pip install pytest-benchmark>=4.0.0
```

### 2.2 Minimum Rounds and Iterations

| Parameter | Minimum | Notes |
|-----------|---------|-------|
| `--benchmark-min-rounds` | 5 | Statistical significance |
| Iterations per round | 3 | pytest-benchmark default calibration |
| Warm-up | Automatic | `pytest-benchmark` handles this |

Override in `pyproject.toml` if tighter control is needed:

```toml
[tool.pytest.ini_options]
addopts = "--benchmark-min-rounds=5"
```

### 2.3 Baseline Storage

- Baselines are stored in `tests/benchmarks/.benchmarks/` as JSON files.
- Commit baselines to the repository after every hardware change or intentional
  performance improvement.
- Never let CI auto-commit baselines — baseline updates require a PR review.

### 2.4 Regression Gate

Regressions greater than **10%** from the saved baseline fail the build:

```bash
pytest tests/benchmarks/ --benchmark-only \
    --benchmark-compare=0001_baseline \
    --benchmark-compare-fail=mean:10%
```

---

## 3. Coverage Standards

### 3.1 Minimum Coverage Thresholds

| Scope | Minimum Line Coverage |
|-------|-----------------------|
| All modules (`src/`) | **85%** |
| Security modules (`src/security_plane/`) | **90%** |
| New code (any PR) | Must include tests or written justification |

### 3.2 Enforcement

Coverage thresholds are enforced via `pyproject.toml`:

```toml
[tool.pytest.ini_options]
addopts = "--cov=src --cov-fail-under=85 --cov-report=term-missing"
```

The `--cov-fail-under=85` flag causes `pytest` to exit with a non-zero status
when line coverage drops below 85%, blocking the CI build.

### 3.3 Exclusions

Coverage exclusions must be documented in `.coveragerc` with a comment explaining
the justification.  Blanket `# pragma: no cover` without justification is not
permitted in `src/`.

---

## 4. SLA Testing Standards

### 4.1 SLA Test Requirements

Each "Design Target" listed in the README **must** have a corresponding
`@pytest.mark.sla` test in `tests/sla/`.

| README Design Target | Test ID | File |
|----------------------|---------|------|
| API throughput ≥ 1,000 req/s | `SLA-API-001` | `tests/sla/test_sla_enforcement.py` |
| Gate evaluation ≥ 50,000 ops/s | `SLA-GATE-001` | `tests/sla/test_sla_enforcement.py` |
| API latency p95 < 100 ms | `SLA-API-002` | `tests/sla/test_sla_enforcement.py` |
| Task execution ≥ 100 tasks/s | `SLA-TASK-001` | `tests/sla/test_sla_enforcement.py` |

### 4.2 Marker Declaration

The `sla` marker is declared in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
markers = [
    "sla: SLA enforcement tests that gate production releases",
    "benchmark: Performance benchmark tests",
]
```

### 4.3 Running SLA Tests

```bash
cd "murphy_system"
# Run SLA tests only
pytest tests/sla/ -m sla -v

# Run SLA tests as part of a release gate
pytest tests/sla/ -m sla --tb=short --strict-markers
```

### 4.4 Release Gate

SLA tests run on every release candidate.  A single SLA test failure **blocks
the release**.  There is no waiver mechanism — fix the regression or update the
design target in the README with justification before re-releasing.

---

## 5. Benchmark Regression Policy

### 5.1 Baseline Updates

| Scenario | Action Required |
|----------|----------------|
| Hardware change (new CI runner) | Re-run all benchmarks and save new baseline via PR |
| Legitimate performance improvement | Save new baseline via PR with before/after numbers in PR description |
| Unexplained regression | Investigate and fix — do **not** update baseline to hide the regression |

### 5.2 Review Requirements

All baseline updates must:

1. Include the old and new JSON baseline files in the PR diff.
2. Include a comment in the PR explaining the reason for the change.
3. Receive at least one code-owner approval before merging.

### 5.3 Historical Tracking

After each release, append a row to `documentation/testing/BENCHMARK_RESULTS.md`
with:

- Date
- Git SHA
- Environment (OS, CPU, RAM, Python version)
- ops/s for each tracked benchmark
- Notes (hardware change, improvement, etc.)

---

## 6. Mutation Testing (Future)

### 6.1 Recommended Tool

Use [`mutmut`](https://github.com/boxed/mutmut) for mutation testing:

```bash
pip install mutmut
mutmut run --paths-to-mutate src/
mutmut results
```

### 6.2 Kill-Rate Target

| Scope | Target Mutation Kill Rate |
|-------|--------------------------|
| Critical modules (`src/gate_execution_wiring.py`, `src/universal_control_plane.py`) | ≥ 80% |
| All `src/` modules | ≥ 70% (aspirational) |

### 6.3 Integration with CI

When mutation testing is added to CI, run it as a separate optional job (not
blocking) until the kill-rate targets are established as baselines.  Once
baselines exist, add a threshold gate similar to the coverage enforcement.

---

## Related Documents

- [Testing Guide](TESTING_GUIDE.md) — How to run and write tests
- [Test Coverage](TEST_COVERAGE.md) — Coverage reports and per-module results
- [Benchmark Results](BENCHMARK_RESULTS.md) — Historical benchmark data
- [Benchmark Infrastructure README](../../tests/benchmarks/README.md) — How to run and save benchmarks
- [SLA Enforcement Tests](../../tests/sla/test_sla_enforcement.py) — SLA test implementations
