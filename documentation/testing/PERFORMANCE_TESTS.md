# Performance Tests

How to run performance and load tests for the Murphy System, what benchmarks exist,
and expected baseline numbers.

---

## Quick Start

Run the in-process benchmarks from the repository root:

```bash
python -m pytest tests/benchmarks/test_api_throughput.py -v
```

For HTTP load testing against a running server, use [Locust](https://locust.io/):

```bash
pip install locust
locust -f tests/benchmarks/locust_benchmark.py \
  --host http://localhost:8000 \
  --users 50 --spawn-rate 10 --run-time 60s --headless
```

---

## Benchmark Suite

### In-Process Throughput (`test_api_throughput.py`)

Measures raw function-call throughput without HTTP overhead.

| Component | ops/s | p50 | p95 | p99 |
|-----------|-------|-----|-----|-----|
| `UniversalControlPlane.create_automation()` | 1,242 | 0.71 ms | 1.51 ms | 2.00 ms |
| `GateExecutionWiring.evaluate_gates()` | 71,981 | 0.011 ms | 0.030 ms | — |
| `PlatformConnectorFramework.execute_action()` | 248 | 0.002 ms | 21.39 ms | — |

> Numbers recorded on a 2-vCPU CI runner (Linux, Python 3.12).
> Production hardware with dedicated CPUs will exceed these baselines.

### HTTP Load Test (`locust_benchmark.py`)

Simulates concurrent users hitting the REST API. Target: **1,000+ req/s** with a
multi-worker uvicorn deployment.

### Integration Pipeline (`test_integration_speed.py`)

Measures the SwissKiss integration pipeline (clone → analyse → risk scan → write audit).
Requires network access:

```bash
MURPHY_RUN_INTEGRATION_BENCHMARKS=1 \
  python -m pytest tests/benchmarks/test_integration_speed.py -v
```

SLA target: **< 300 seconds** per repository integration.

---

## Expected Baselines

| Metric | Baseline | Environment |
|--------|----------|-------------|
| Control plane create_automation | ≥ 1,200 ops/s | 2-vCPU |
| Gate evaluation (single gate) | ≥ 70,000 ops/s | 2-vCPU |
| Connector framework (simulated) | ≥ 200 ops/s | 2-vCPU |
| HTTP throughput (multi-worker) | ≥ 1,000 req/s | 4-vCPU |
| Integration pipeline | < 300 s | Network access required |

---

## Regression Tracking

Add a row to [BENCHMARK_RESULTS.md](BENCHMARK_RESULTS.md) each time benchmarks are
re-run so regressions are visible over time.

| Date | Component | ops/s | p95 (ms) | Notes |
|------|-----------|-------|----------|-------|
| 2026-03-10 | UCP create_automation | 1,242 | 1.51 | Baseline |
| 2026-03-10 | Gate evaluation | 71,981 | 0.030 | Baseline |
| 2026-03-10 | Connector framework | 248 | 21.39 | Baseline, simulated |

---

## See Also

- [Benchmark Results](BENCHMARK_RESULTS.md)
- [Testing Guide](TESTING_GUIDE.md)
- [Scaling Guide](../deployment/SCALING.md)
