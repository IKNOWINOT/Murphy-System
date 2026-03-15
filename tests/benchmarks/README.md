# Benchmark Infrastructure

This directory holds `pytest-benchmark` statistical benchmark tests for the Murphy System.

## Quick Reference

### Run all benchmarks

```bash
cd "Murphy System"
pytest tests/benchmarks/ --benchmark-only -v
```

### Run only statistical benchmarks (pytest-benchmark)

```bash
pytest tests/benchmarks/test_benchmark_statistical.py --benchmark-only -v
```

### Save a baseline

Baselines are stored in `.benchmarks/` as JSON files.  Commit them to the repo
so that CI can compare future runs against them.

```bash
pytest tests/benchmarks/ --benchmark-only --benchmark-save=baseline
```

This creates `.benchmarks/Linux-CPython-3.10-64bit/0001_baseline.json` (or similar
depending on platform and Python version).

### Compare against a saved baseline

```bash
pytest tests/benchmarks/ --benchmark-only --benchmark-compare=0001_baseline
```

### Fail the build on >10% regression from baseline

```bash
pytest tests/benchmarks/ --benchmark-only \
    --benchmark-compare=0001_baseline \
    --benchmark-compare-fail=mean:10%
```

Exit code is non-zero when any benchmark regresses by more than the specified
percentage, causing the CI job to fail.

## Baseline Policy

| Action | Rule |
|--------|------|
| **Update baseline** | Only on hardware changes or legitimate performance improvements — requires PR review |
| **Commit baseline** | Always commit `.benchmarks/` JSON after updating — never let CI auto-commit baselines |
| **Historical tracking** | Summarise results in `documentation/testing/BENCHMARK_RESULTS.md` after each release |

## Design Targets

| Component | Target | Test ID |
|-----------|--------|---------|
| Gate evaluation | ≥ 50,000 ops/s | `PERF-GATE-001` |
| Control plane creation | ≥ 1,000 ops/s | `PERF-UCP-001` |
| Platform connector (sim) | ≥ 200 ops/s | `PERF-PCF-001` |

See also `tests/sla/test_sla_enforcement.py` for the corresponding SLA tests.
