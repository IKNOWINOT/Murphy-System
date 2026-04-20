# `src/benchmark_adapters` — External AI Agent Benchmark Adapters

Adapters for evaluating the Murphy System against major public AI agent benchmarks.

![License: BSL 1.1](https://img.shields.io/badge/License-BSL%201.1-blue.svg)

## Overview

The benchmark adapters package provides a uniform harness for running Murphy against seven established AI agent evaluation suites: SWE-bench, GAIA, AgentBench, WebArena, ToolBench/BFCL, τ-Bench, and Terminal-Bench. Each adapter implements the common `BenchmarkAdapter` interface, translating Murphy's execution model into the format expected by each benchmark. Results are returned as `BenchmarkResult` and aggregated into `BenchmarkSuiteResult` objects for comparison and regression tracking.

## Key Components

| Module | Purpose |
|--------|---------|
| `base.py` | `BenchmarkAdapter` ABC, `BenchmarkResult`, `BenchmarkSuiteResult` |
| `swe_bench_adapter.py` | Adapter for SWE-bench software engineering tasks |
| `gaia_adapter.py` | Adapter for GAIA general AI assistant tasks |
| `agent_bench_adapter.py` | Adapter for AgentBench multi-environment tasks |
| `web_arena_adapter.py` | Adapter for WebArena browser navigation tasks |
| `tool_bench_adapter.py` | Adapter for ToolBench / BFCL tool-use tasks |
| `tau_bench_adapter.py` | Adapter for τ-Bench long-horizon reasoning tasks |
| `terminal_bench_adapter.py` | Adapter for Terminal-Bench CLI task evaluation |

## Usage

```python
from benchmark_adapters import SWEBenchAdapter, BenchmarkSuiteResult

adapter = SWEBenchAdapter()
result = adapter.run(task_id="django__django-11099")
print(result.passed, result.score)
```

---
*Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1*
