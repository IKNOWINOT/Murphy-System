# Benchmark Adapters

The `benchmark_adapters` package provides adapters that connect Murphy's
execution engine to standard AI benchmarks, enabling automated evaluation
of agent performance.

## Key Modules

| Module | Purpose |
|--------|---------|
| `base.py` | `BenchmarkAdapter` — abstract base class |
| `agent_bench_adapter.py` | Adapter for AgentBench evaluation tasks |
| `gaia_adapter.py` | Adapter for the GAIA benchmark |
| `swe_bench_adapter.py` | Adapter for SWE-bench (software engineering tasks) |
| `tau_bench_adapter.py` | Adapter for TAU-bench |

## Usage

```python
from benchmark_adapters.swe_bench_adapter import SWEBenchAdapter
adapter = SWEBenchAdapter()
score = await adapter.evaluate(agent=murphy_agent, task_set="lite")
```
