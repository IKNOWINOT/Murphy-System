# Murphy System — Benchmark Results

> Measurements taken on 2026-03-10 on the CI runner environment.  
> Platform: Linux (runnervm), 2 vCPUs, Python 3.12.3.  
> All numbers are for in-process operations unless otherwise noted.

---

## Control Plane Throughput

| Component | ops/s | p50 latency | p95 latency | p99 latency |
|-----------|-------|-------------|-------------|-------------|
| `UniversalControlPlane.create_automation()` | 1,242 | 0.71 ms | 1.51 ms | 2.00 ms |
| `GateExecutionWiring.evaluate_gates()` | 71,981 | 0.011 ms | 0.030 ms | — |
| `PlatformConnectorFramework.execute_action()` (simulated) | 248 | 0.002 ms | 21.39 ms | — |

### Notes

- **HTTP throughput** (1,000+ req/s) is achieved via multi-worker uvicorn deployment.
  Use the Locust benchmark at `tests/benchmarks/locust_benchmark.py` against a running
  server to measure real HTTP throughput. See `documentation/deployment/SCALING.md`.
- In-process `create_automation` achieves **1,242 ops/s** on a 2-vCPU CI runner.
  Production servers with dedicated CPUs will exceed this.
- Gate evaluation is extremely fast at **71,981 ops/s** with a single registered gate.
  Real deployments with all 7 security plane gates registered will be slower.
- Connector framework simulated path is **248 ops/s** due to rate-limit accounting and
  thread-safe history appends.

---

## Integration Pipeline Timing

The SwissKiss integration pipeline (clone → analyze → detect license → parse requirements →
extract dependencies → detect languages → risk scan → create module YAML → write audit)
requires network access and git clone operations. Run with:

```bash
MURPHY_RUN_INTEGRATION_BENCHMARKS=1 python -m pytest tests/benchmarks/test_integration_speed.py -v
```

Measured SLA: < 300 seconds per repository integration.

---

## Performance Regression Tracking

| Date | Component | ops/s | p95 (ms) | Environment | Notes |
|------|-----------|-------|-----------|-------------|-------|
| 2026-03-10 | UCP create_automation | 1,242 | 1.51 | 2-vCPU CI runner | Baseline |
| 2026-03-10 | Gate evaluation | 71,981 | 0.030 | 2-vCPU CI runner | Baseline |
| 2026-03-10 | Connector framework | 248 | 21.39 | 2-vCPU CI runner | Baseline, simulated path |

---

## How to Re-run Benchmarks

```bash
cd "Murphy System"
python -m pytest tests/benchmarks/test_api_throughput.py -v
```

For HTTP load testing against a running server:
```bash
pip install locust
locust -f tests/benchmarks/locust_benchmark.py \
  --host http://localhost:8000 \
  --users 50 --spawn-rate 10 --run-time 60s --headless
```
