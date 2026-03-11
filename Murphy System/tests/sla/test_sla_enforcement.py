"""
SLA Enforcement Tests.

Each test maps directly to a "Design Target" listed in the Murphy System README.
All tests are marked with @pytest.mark.sla.  Failing any SLA test blocks release.

SLA targets:
  SLA-API-001  API throughput        >= 1,000 req/s  (simulated in-process)
  SLA-GATE-001 Gate evaluation       >= 50,000 ops/s
  SLA-API-002  API latency p95       < 100 ms
  SLA-TASK-001 Task execution        >= 100 tasks/s

Run only SLA tests:
    pytest tests/sla/ -m sla -v

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""
from __future__ import annotations

import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

# ---------------------------------------------------------------------------
# SLA-API-001  API throughput >= 1,000 req/s (in-process simulation)
# ---------------------------------------------------------------------------

@pytest.mark.sla
def test_api_throughput_sla():
    """SLA-API-001: API throughput must sustain >= 1,000 req/s (in-process).

    The README design target is 1,000+ req/s for a multi-worker uvicorn
    deployment.  This test validates the in-process control-plane call rate
    as a proxy; actual HTTP throughput is validated by the Locust suite.

    Priority: Critical
    Traceability: README Design Target — API Throughput
    """
    try:
        from universal_control_plane import UniversalControlPlane
    except ImportError as exc:
        pytest.skip(f"universal_control_plane not available: {exc}")

    ucp = UniversalControlPlane()
    # Warm-up
    for _ in range(10):
        ucp.create_automation("warmup", "user", "repo")

    n = 1000
    start = time.perf_counter()
    for i in range(n):
        ucp.create_automation(f"task_{i}", f"user_{i}", f"repo_{i}")
    elapsed = time.perf_counter() - start

    ops_per_second = n / elapsed
    assert ops_per_second >= 1_000, (
        f"SLA-API-001 FAILED: in-process throughput {ops_per_second:.0f} ops/s "
        f"is below 1,000 ops/s SLA"
    )


# ---------------------------------------------------------------------------
# SLA-GATE-001  Gate evaluation >= 50,000 ops/s
# ---------------------------------------------------------------------------

@pytest.mark.sla
def test_gate_evaluation_throughput_sla():
    """SLA-GATE-001: Gate evaluation must sustain >= 50,000 ops/s.

    Priority: Critical
    Traceability: README Design Target — Gate Evaluation Throughput
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

    # Warm-up
    for _ in range(20):
        wiring.evaluate_gates(task, "warmup")

    n = 5000
    start = time.perf_counter()
    for i in range(n):
        wiring.evaluate_gates(task, f"session_{i}")
    elapsed = time.perf_counter() - start

    ops_per_second = n / elapsed
    assert ops_per_second >= 50_000, (
        f"SLA-GATE-001 FAILED: gate evaluation {ops_per_second:.0f} ops/s "
        f"is below 50,000 ops/s SLA"
    )


# ---------------------------------------------------------------------------
# SLA-API-002  API latency p95 < 100 ms
# ---------------------------------------------------------------------------

@pytest.mark.sla
def test_api_latency_p95_sla():
    """SLA-API-002: Gate evaluation p95 latency must be < 100 ms.

    Uses in-process measurement as a proxy for API latency.  The FastAPI
    HTTP layer adds negligible overhead at this scale.

    Priority: Critical
    Traceability: README Design Target — API Latency p95
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

    n = 200
    latencies_ms: list[float] = []
    for i in range(n):
        t0 = time.perf_counter()
        wiring.evaluate_gates(task, f"session_{i}")
        latencies_ms.append((time.perf_counter() - t0) * 1000)

    latencies_ms.sort()
    p95_ms = latencies_ms[int(0.95 * n)]

    assert p95_ms < 100.0, (
        f"SLA-API-002 FAILED: p95 latency {p95_ms:.3f} ms exceeds 100 ms SLA"
    )


# ---------------------------------------------------------------------------
# SLA-TASK-001  Task execution >= 100 tasks/s
# ---------------------------------------------------------------------------

@pytest.mark.sla
def test_task_execution_throughput_sla():
    """SLA-TASK-001: Task execution must sustain >= 100 tasks/s.

    Priority: High
    Traceability: README Design Target — Task Execution Throughput
    """
    try:
        from universal_control_plane import UniversalControlPlane
    except ImportError as exc:
        pytest.skip(f"universal_control_plane not available: {exc}")

    ucp = UniversalControlPlane()
    # Warm-up
    for _ in range(5):
        ucp.create_automation("warmup", "user", "repo")

    n = 500
    start = time.perf_counter()
    for i in range(n):
        ucp.create_automation(f"sla_task_{i}", "sla_user", "sla_repo")
    elapsed = time.perf_counter() - start

    ops_per_second = n / elapsed
    assert ops_per_second >= 100, (
        f"SLA-TASK-001 FAILED: task execution {ops_per_second:.0f} tasks/s "
        f"is below 100 tasks/s SLA"
    )
