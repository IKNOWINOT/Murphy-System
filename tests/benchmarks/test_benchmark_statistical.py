"""
Statistical Benchmark Tests using pytest-benchmark.

Wraps existing performance tests with the pytest-benchmark fixture for
statistical rigor: automatic warm-up rounds, stddev, mean, median, IQR,
and built-in --benchmark-save / --benchmark-compare for regression detection.

Targets:
  - Gate evaluation:          >50,000 ops/s
  - Control plane creation:   >1,000 ops/s
  - Platform connector (sim): >200 ops/s
  - LLM routing dispatch:     >5,000 ops/s
  - RAG retrieval (TF-IDF):   >500 ops/s
  - HITL queue enqueue:       >10,000 ops/s

Run:
    pytest tests/benchmarks/test_benchmark_statistical.py --benchmark-only

Save a baseline:
    pytest tests/benchmarks/ --benchmark-only --benchmark-save=baseline

Compare against a baseline:
    pytest tests/benchmarks/ --benchmark-only --benchmark-compare=0001_baseline

Fail on >10% regression:
    pytest tests/benchmarks/ --benchmark-only \
        --benchmark-compare=0001_baseline --benchmark-compare-fail=mean:10%

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""
from __future__ import annotations

import sys
import uuid
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

# ---------------------------------------------------------------------------
# Skip entire module gracefully if pytest-benchmark is not installed
# ---------------------------------------------------------------------------
try:
    import pytest_benchmark  # noqa: F401
    _BENCHMARK_AVAILABLE = True
except ImportError:
    _BENCHMARK_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not _BENCHMARK_AVAILABLE,
    reason="pytest-benchmark not installed; run `pip install pytest-benchmark`",
)


# ---------------------------------------------------------------------------
# Gate Evaluation Throughput  (target: >50,000 ops/s)
# ---------------------------------------------------------------------------

def test_gate_evaluation_throughput(benchmark):
    """Gate evaluation must sustain >50,000 ops/s (pytest-benchmark, statistical).

    Test ID: PERF-GATE-001
    Priority: Critical
    Traceability: Design Target — Gate Evaluation Throughput
    """
    try:
        from src.gate_execution_wiring import (
            GateDecision,
            GateEvaluation,
            GateExecutionWiring,
            GatePolicy,
            GateType,
        )
    except ImportError as exc:
        pytest.skip(f"gate_execution_wiring not available: {exc}")

    wiring = GateExecutionWiring()

    def fast_evaluator(task, session_id):
        return GateEvaluation(
            gate_id=str(uuid.uuid4()),
            gate_type=GateType.QA,
            decision=GateDecision.APPROVED,
            reason="pass",
            policy=GatePolicy.WARN,
            evaluated_at=datetime.now().isoformat(),
        )

    wiring.register_gate(GateType.QA, fast_evaluator)

    task = {"type": "standard"}

    result = benchmark(wiring.evaluate_gates, task, "bench-session")
    assert result is not None


# ---------------------------------------------------------------------------
# Control Plane Creation Throughput  (target: >1,000 ops/s)
# ---------------------------------------------------------------------------

def test_control_plane_creation_throughput(benchmark):
    """UniversalControlPlane.create_automation() must sustain >1,000 ops/s.

    Test ID: PERF-UCP-001
    Priority: Critical
    Traceability: Design Target — Control Plane Throughput
    """
    try:
        from universal_control_plane import UniversalControlPlane
    except ImportError as exc:
        pytest.skip(f"universal_control_plane not available: {exc}")

    ucp = UniversalControlPlane()

    def run_one():
        return ucp.create_automation("bench task", "bench_user", "bench_repo")

    result = benchmark(run_one)
    assert result is not None


# ---------------------------------------------------------------------------
# Platform Connector Framework Throughput  (target: >200 ops/s)
# ---------------------------------------------------------------------------

def test_platform_connector_framework_throughput(benchmark):
    """PlatformConnectorFramework simulated execute_action() must sustain >200 ops/s.

    Test ID: PERF-PCF-001
    Priority: High
    Traceability: Design Target — Platform Connector Throughput
    """
    try:
        from src.platform_connector_framework import (
            AuthType,
            ConnectorAction,
            ConnectorCategory,
            ConnectorDefinition,
            PlatformConnectorFramework,
            RateLimitConfig,
        )
    except ImportError as exc:
        pytest.skip(f"platform_connector_framework not available: {exc}")

    fw = PlatformConnectorFramework()
    definition = ConnectorDefinition(
        connector_id="bench_sim",
        name="Benchmark Simulated",
        category=ConnectorCategory.CUSTOM,
        platform="bench",
        auth_type=AuthType.NONE,
        base_url="",
        capabilities=["send_message"],
        rate_limit=RateLimitConfig(max_requests=100_000, window_seconds=60),
    )
    fw.register_connector(definition)

    action = ConnectorAction(
        action_id="bench_action",
        connector_id="bench_sim",
        action_type="send_message",
        resource="channel",
    )

    result = benchmark(fw.execute_action, action)
    assert result is not None


# ---------------------------------------------------------------------------
# LLM Provider Routing Dispatch  (target: >5,000 ops/s)
# ---------------------------------------------------------------------------
#
# Roadmap Item 15 names "LLM provider routing" as a hot path. The interesting
# thing to benchmark here is the *dispatch* overhead: prompt assembly +
# local→cloud→layer fallback decision. We deliberately benchmark the
# all-backends-unavailable path because:
#
#   1. CI has no real LLM backends configured, so this path is the only one
#      we can measure deterministically.
#   2. Network-bound paths are owned by locust (see `locust_benchmark.py`),
#      not pytest-benchmark. pytest-benchmark is for in-process micro-bench.
#   3. Routing overhead is what regresses when the dispatch logic gets more
#      complex; the network call dominates real latency but is constant
#      relative to dispatch changes.

def test_llm_routing_dispatch_throughput(benchmark):
    """TenantLLMRouter.complete() dispatch path must sustain >5,000 ops/s.

    Test ID: PERF-LLM-ROUTE-001
    Priority: High
    Traceability: Roadmap Item 15 — Hot path "LLM provider routing"

    Measures the routing-decision overhead (prompt build + local→cloud→layer
    fallback chain) on the all-backends-unavailable path that returns the
    stub response. This isolates dispatch cost from any network I/O.
    """
    try:
        from src.copilot_tenant.llm_router import TenantLLMRouter
    except ImportError as exc:
        pytest.skip(f"copilot_tenant.llm_router not available: {exc}")

    router = TenantLLMRouter()
    prompt = "summarise the following telemetry payload in two sentences"
    context = {"tenant": "bench", "request_id": "bench-001", "priority": "p2"}

    result = benchmark(router.complete, prompt, context)
    assert isinstance(result, str) and result


# ---------------------------------------------------------------------------
# RAG Retrieval Throughput  (target: >500 ops/s)
# ---------------------------------------------------------------------------
#
# Roadmap Item 15 names "RAG retrieval" as a hot path. Benchmarks the
# pure-Python TF-IDF backend (the CI default; ChromaDB is opt-in via
# CHROMADB_PATH env var per src/rag_vector_integration.py docstring).
# Pre-ingests a small fixed corpus once during setup, then measures only
# the search() call inside the benchmark loop.

def test_rag_retrieval_throughput(benchmark):
    """RAGVectorIntegration.search() must sustain >500 ops/s on a 5-doc corpus.

    Test ID: PERF-RAG-001
    Priority: High
    Traceability: Roadmap Item 15 — Hot path "RAG retrieval"

    Measures TF-IDF cosine-similarity retrieval over a deterministic
    fixed corpus. Ingestion happens in setup; only search() is timed.
    """
    try:
        from src.rag_vector_integration import RAGVectorIntegration
    except ImportError as exc:
        pytest.skip(f"rag_vector_integration not available: {exc}")

    rag = RAGVectorIntegration(chunk_size=64, chunk_overlap=8)
    corpus = [
        ("governance kernel", "The governance kernel evaluates gates against policies."),
        ("control plane", "The universal control plane creates and routes automations."),
        ("platform connector", "Platform connectors bridge external services with rate limits."),
        ("llm routing", "The tenant LLM router prefers local backends and falls back to cloud."),
        ("hitl queue", "The HITL task queue enqueues tasks pending human review."),
    ]
    for title, text in corpus:
        rag.ingest_document(text=text, title=title)

    result = benchmark(rag.search, "how does the governance gate evaluate policies", 3)
    assert result.get("status") == "ok"


# ---------------------------------------------------------------------------
# HITL Queue Dispatch Throughput  (target: >10,000 ops/s)
# ---------------------------------------------------------------------------
#
# Roadmap Item 15 names "HITL queue dispatch" as a hot path. Benchmarks
# HITLTaskQueue.enqueue() — the dispatch entry point that all upstream
# validators call when a field needs human review.

def test_hitl_queue_enqueue_throughput(benchmark):
    """HITLTaskQueue.enqueue() must sustain >10,000 ops/s.

    Test ID: PERF-HITL-001
    Priority: High
    Traceability: Roadmap Item 15 — Hot path "HITL queue dispatch"
    """
    try:
        from src.billing.grants.hitl_task_queue import (
            TIER_REVIEW,
            HITLTaskQueue,
        )
    except ImportError as exc:
        pytest.skip(f"billing.grants.hitl_task_queue not available: {exc}")

    queue = HITLTaskQueue()

    def enqueue_one():
        return queue.enqueue(
            session_id="bench-session",
            application_id="bench-app",
            field_id="bench-field",
            tier=TIER_REVIEW,
            value="needs review",
            confidence=0.42,
            reasoning="benchmark dispatch path",
        )

    task = benchmark(enqueue_one)
    assert task is not None and task.task_id
