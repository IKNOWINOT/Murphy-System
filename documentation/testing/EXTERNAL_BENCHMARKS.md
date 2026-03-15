# External AI Agent Benchmark Evaluation

> **Copyright © 2020 Inoni Limited Liability Company | Creator: Corey Post | License: BSL 1.1**

This document describes how Murphy System is evaluated against major public AI agent benchmarks, enabling standardised, comparable scores against other systems.

---

## Overview

Murphy System is evaluated against seven major public benchmarks covering its full capability surface:

| Benchmark | What it tests | Murphy Subsystem(s) |
|-----------|--------------|---------------------|
| **SWE-bench** | Real GitHub issue → code patch | `self_fix_loop.py`, `murphy_immune_engine.py`, `AIWorkflowGenerator` |
| **GAIA** | Multi-step, multi-tool reasoning | Universal Control Plane, `ai_workflow_generator.py` |
| **AgentBench** | 8-environment agent tasks (OS, DB, Web, Code…) | `platform_connector_framework.py`, `workflow_dag_engine.py` |
| **WebArena** | Functional goal completion in web environments | `platform_connector_framework.py` (90+ connectors) |
| **ToolBench / BFCL** | Tool/API selection and calling accuracy | `api_gateway_adapter.py`, connector framework |
| **τ-Bench** | Multi-turn HITL workflows | HITL graduation pipeline, `durable_swarm_orchestrator.py` |
| **Terminal-Bench** | CLI/script and DevOps automation | `ai_workflow_generator.py`, system automation modules |

---

## Benchmark Descriptions

### SWE-bench
- **Official site:** https://www.swebench.com/
- **What it tests:** Given a real GitHub issue, the agent must produce a code patch that passes the repository's test suite.
- **Murphy's approach:** Feeds issue descriptions to `AIWorkflowGenerator`, then routes through the `SelfFixLoop` to refine the patch.
- **Key metric:** `resolved_rate` — fraction of issues where the generated patch passes CI.

### GAIA
- **Official site:** https://huggingface.co/datasets/gaia-benchmark/GAIA
- **What it tests:** Multi-step, multi-tool reasoning tasks stratified by difficulty (Level 1 = simple, Level 3 = expert-level).
- **Murphy's approach:** Tasks flow through Murphy's natural-language workflow generator and multi-step execution pipeline.
- **Key metrics:** Overall `success_rate`; per-level rates (`level_1_rate`, `level_2_rate`, `level_3_rate`).

### AgentBench
- **Official site:** https://github.com/THUDM/AgentBench
- **What it tests:** 8 environments — OS, DB, Knowledge Graph, Web Shopping, Web Browsing, Code Generation, ALFWorld, and Mind2Web.
- **Murphy's approach:** Routes each environment to the best-matched subsystem (e.g., OS → system automation, DB → data connectors).
- **Key metrics:** `success_rate`; per-environment rates (`env_os_rate`, `env_db_rate`, etc.).

### WebArena
- **Official site:** https://webarena.dev/
- **What it tests:** Functional goal completion in simulated web environments (e-commerce, forums, CMS, GitLab).
- **Murphy's approach:** Routes tasks through `PlatformConnectorFramework` (90+ platform connectors).
- **Key metric:** `success_rate` (functional goal completion).

### ToolBench / BFCL
- **Official site:** https://gorilla.cs.berkeley.edu/leaderboard.html
- **What it tests:** Correct tool/API selection and parameter filling from natural-language instructions.
- **Murphy's approach:** Routes through `APIGatewayAdapter` and `PlatformConnectorFramework`.
- **Key metrics:** `tool_selection_accuracy`, `execution_success_rate`.

### τ-Bench (Tau-Bench)
- **Official site:** https://github.com/sierra-research/tau-bench
- **What it tests:** Multi-turn, long-horizon workflows requiring human-in-the-loop approval gates.
- **Murphy's approach:** Uses `DurableSwarmOrchestrator` + HITL graduation pipeline + wingman protocol.
- **Key metrics:** `completion_rate`, `hitl_escalation_rate`, `mean_turns`.

### Terminal-Bench
- **Official site:** https://github.com/laion-ai/terminal-bench
- **What it tests:** CLI competence — file manipulation, software installs, multi-step DevOps scripts.
- **Murphy's approach:** Routes CLI tasks through `AIWorkflowGenerator` to generate shell command sequences.
- **Key metrics:** `command_success_rate`, `script_completion_rate`.

---

## Running Benchmarks

### Prerequisites

```bash
# Install benchmark dependencies (separate from core CI deps)
pip install -r "requirements_benchmarks.txt"
```

### Quick Start

```bash
# Run all benchmarks
bash "scripts/run_benchmarks.sh" all

# Run a single benchmark
bash "scripts/run_benchmarks.sh" swe-bench

# Run multiple benchmarks
bash "scripts/run_benchmarks.sh" gaia agent-bench tool-bench
```

### Using pytest directly

```bash
cd "Murphy System"

# Run all benchmarks
MURPHY_RUN_EXTERNAL_BENCHMARKS=1 pytest tests/benchmarks/test_external_benchmarks.py -v

# Run a specific benchmark
MURPHY_RUN_EXTERNAL_BENCHMARKS=1 pytest tests/benchmarks/test_external_benchmarks.py -k swe_bench -v

# Limit tasks per suite (useful for quick smoke tests)
MURPHY_RUN_EXTERNAL_BENCHMARKS=1 MURPHY_BENCHMARK_MAX_TASKS=2 pytest tests/benchmarks/test_external_benchmarks.py -v
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `MURPHY_RUN_EXTERNAL_BENCHMARKS` | Must be set to `1` to enable benchmark tests | _(unset — tests skip)_ |
| `MURPHY_BENCHMARK_MAX_TASKS` | Maximum tasks per benchmark suite | `5` |
| `MURPHY_BENCHMARK_RESULTS_DIR` | Directory for JSON/Markdown output | `documentation/testing/` |
| `WEBARENA_SERVER_URL` | URL of a live WebArena server | _(unset — uses synthetic tasks)_ |

---

## Interpreting Results

### JSON Output

Each benchmark produces a JSON file in `documentation/testing/`:

```json
{
  "benchmark_name": "swe-bench",
  "benchmark_version": "lite-v1",
  "run_timestamp": "2026-03-01T06:00:00+00:00",
  "tasks_total": 5,
  "tasks_succeeded": 3,
  "tasks_failed": 2,
  "tasks_skipped": 0,
  "success_rate": 0.6,
  "mean_score": 0.6,
  "mean_elapsed_seconds": 1.234
}
```

### Markdown Report

A consolidated markdown table is written to `BENCHMARK_EXTERNAL_RESULTS.md`:

```
| Benchmark     | Tasks | Succeeded | Success Rate | Mean Score |
|---------------|-------|-----------|--------------|------------|
| swe-bench     | 5     | 3         | 60.0%        | 0.600      |
| gaia          | 5     | 4         | 80.0%        | 0.650      |
...
```

### Score Interpretation

| Score Range | Interpretation |
|-------------|---------------|
| 0.0 – 0.3 | Early-stage capability; significant gaps remain |
| 0.3 – 0.6 | Partial capability; subsystem integration needed |
| 0.6 – 0.8 | Solid capability; competitive with open-source baselines |
| 0.8 – 1.0 | Strong capability; competitive with frontier systems |

---

## Tracking Scores Over Time

Use the `--benchmark-save` / `--benchmark-compare` flags (from `pytest-benchmark`) to detect regressions between releases:

```bash
# Save a baseline
MURPHY_RUN_EXTERNAL_BENCHMARKS=1 pytest tests/benchmarks/ --benchmark-only --benchmark-save=baseline

# Compare against baseline (fail on >10% regression)
MURPHY_RUN_EXTERNAL_BENCHMARKS=1 pytest tests/benchmarks/ --benchmark-only \
    --benchmark-compare=0001_baseline --benchmark-compare-fail=mean:10%
```

---

## Official Leaderboards

| Benchmark | Leaderboard URL |
|-----------|----------------|
| SWE-bench | https://www.swebench.com/ |
| GAIA | https://huggingface.co/spaces/gaia-benchmark/leaderboard |
| AgentBench | https://llmbench.ai/agent |
| WebArena | https://webarena.dev/ |
| BFCL | https://gorilla.cs.berkeley.edu/leaderboard.html |
| τ-Bench | https://github.com/sierra-research/tau-bench |
| Terminal-Bench | https://github.com/laion-ai/terminal-bench |
