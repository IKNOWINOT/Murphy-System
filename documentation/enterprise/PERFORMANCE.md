# Performance

Performance characteristics, benchmarks, and optimisation guidance for the Murphy System.

---

## Measured Throughput

All numbers recorded on a 2-vCPU CI runner (Linux, Python 3.12). Production hardware
with dedicated CPUs will exceed these baselines. See
[BENCHMARK_RESULTS.md](../testing/BENCHMARK_RESULTS.md) for full data.

### Control Plane

| Component | ops/s | p50 | p95 |
|-----------|-------|-----|-----|
| `UniversalControlPlane.create_automation()` | 1,242 | 0.71 ms | 1.51 ms |
| `GateExecutionWiring.evaluate_gates()` | 71,981 | 0.011 ms | 0.030 ms |
| `PlatformConnectorFramework.execute_action()` | 248 | 0.002 ms | 21.39 ms |

### HTTP API

- Multi-worker uvicorn deployment achieves **1,000+ req/s**.
- Run the Locust benchmark to verify:

```bash
locust -f tests/benchmarks/locust_benchmark.py \
  --host http://localhost:8000 \
  --users 50 --spawn-rate 10 --run-time 60s --headless
```

### Integration Pipeline

SwissKiss integration (clone → analyse → risk scan → audit): **< 300 s** per repository.

---

## Performance Characteristics

### Stateless API Tier

The FastAPI runtime is **stateless** — any instance can serve any request. This enables
horizontal scaling by adding workers or replicas without coordination.

### Gate Evaluation

Gate evaluation is the fastest path at **71,981 ops/s** with a single gate. Deployments
with all 6 gate types (COMPLIANCE → BUDGET → EXECUTIVE → OPERATIONS → QA → HITL) will
be proportionally slower but remain sub-millisecond for typical configurations.

### Connector Framework

The connector framework's 248 ops/s reflects rate-limit accounting and thread-safe
history appends. CPU-bound work is minimal; most latency comes from I/O operations
in real (non-simulated) deployments.

---

## Optimisation Recommendations

1. **Scale workers** — Use `uvicorn --workers N` where N = 2× CPU cores for
   CPU-bound workloads, or use async workers for I/O-bound loads.

2. **Enable caching** — Set `REDIS_URL` to activate the cache layer, reducing
   repeated LLM calls and database queries.

3. **Database connection pooling** — Configure `DATABASE_URL` with a connection
   pool (e.g., `pgbouncer`) for high-concurrency deployments.

4. **Gate policy tuning** — Set non-critical gates to `WARN` or `AUDIT` policy
   to reduce blocking evaluations on the hot path.

5. **Tenant resource limits** — Configure `max_concurrent_tasks` and `budget_limit`
   per tenant to prevent noisy-neighbour effects.

6. **Profile bottlenecks** — Use `py-spy` or `cProfile` to identify slow paths:
   ```bash
   py-spy record -o profile.svg -- python -m uvicorn src.runtime.app:create_app
   ```

---

## See Also

- [Enterprise Overview](ENTERPRISE_OVERVIEW.md)
- [Scaling Guide](SCALING_GUIDE.md)
- [Benchmark Results](../testing/BENCHMARK_RESULTS.md)
