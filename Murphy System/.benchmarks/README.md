# Benchmark baselines

This directory holds committed `pytest-benchmark` baselines used by the
**`benchmark-regression`** CI job (defined in `.github/workflows/ci.yml`).

## What is committed

- `Linux-CPython-3.12-64bit/0001_baseline.json` — the reference run for
  the four roadmap-named **dispatch-overhead** benchmarks
  (governance gate, platform-connector framework, LLM provider routing,
  HITL queue enqueue). Generated on a CI-equivalent runner with
  `--benchmark-min-rounds=20 --benchmark-warmup=on`.

## What is **not** committed

- `test_rag_retrieval_throughput` is intentionally excluded from the
  baseline. RAG retrieval has 5× higher run-to-run variance (it is
  I/O-shaped: O(N) cosine over chunk vectors), so a committed baseline
  for it produces unreliable signal on shared CI runners.
- Per-PR result files (in `.gitignore`).

## Threshold rationale (read this before tightening)

The gate compares HEAD's `min` time against the committed baseline's
`min` and fails if HEAD is **>25% slower**. Two conscious choices:

1. **`min` not `mean`** — the minimum is the most stable statistic on
   shared runners; `mean` is dragged by GC pauses and noisy neighbours.
2. **25%, not 10%** — measured variance on `ubuntu-latest` runners is
   roughly 20–40% on micro-benchmarks. A 10% gate generates false
   positives within the first week and trains contributors to ignore
   the signal. We keep it loose, then tighten *after* soaking the
   actual variance with real PR data.

## Soak → promotion plan

1. **Now (advisory):** the `benchmark-regression` job runs with
   `continue-on-error: true`. Failures appear in the PR status checks
   but do **not** block merge.
2. **After ≥2 weeks** of real PR data: collect the per-run min/median
   distribution from the CI logs, compute the empirical p99 delta,
   choose a defensible threshold, and remove `continue-on-error`.
3. **Refreshing the baseline:** when an intentional perf change lands,
   regenerate with:
   ```bash
   python -m pytest tests/benchmarks/test_benchmark_statistical.py \
     -k "test_gate_evaluation_throughput or \
         test_platform_connector_framework_throughput or \
         test_llm_routing_dispatch_throughput or \
         test_hitl_queue_enqueue_throughput" \
     --benchmark-only --benchmark-min-rounds=20 \
     --benchmark-warmup=on --benchmark-warmup-iterations=100 \
     --benchmark-save=baseline
   ```
   Then commit the resulting `0001_baseline.json` (overwrite, do not
   accumulate `0002_*`, `0003_*`).

Roadmap reference: `docs/ROADMAP_TO_CLASS_S.md` Item 15.
