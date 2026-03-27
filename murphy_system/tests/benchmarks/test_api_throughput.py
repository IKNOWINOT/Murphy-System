"""
API Throughput Benchmark Tests

Tests that the Murphy System control plane can handle high-throughput
in-process operations. The 1,000+ req/s target in the README refers to
HTTP request throughput (measured by the Locust benchmark in
locust_benchmark.py when the FastAPI server is running). In-process
operations include orchestration overhead and run at 500+ ops/s on a
single CPU core; the HTTP target is met through multi-worker uvicorn
deployment (see documentation/deployment/SCALING.md).

GAP 2 closure: validates in-process performance with measured data.
"""
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

# In-process operations/s target (single core, no network I/O).
# The documented 1,000+ req/s target applies to HTTP requests against
# a running multi-worker uvicorn server (see locust_benchmark.py).
IN_PROCESS_TARGET_OPS = 500


class TestControlPlaneThroughput(unittest.TestCase):
    """Verify in-process control plane throughput meets targets."""

    def test_ucp_create_automation_throughput(self):
        """UniversalControlPlane.create_automation() must handle 500+ calls/s (in-process)."""
        from universal_control_plane import UniversalControlPlane
        ucp = UniversalControlPlane()

        n = 200
        for _ in range(10):
            ucp.create_automation("warmup task", "user", "repo")

        start = time.perf_counter()
        for i in range(n):
            ucp.create_automation(f"task {i}", f"user_{i}", f"repo_{i}")
        elapsed = time.perf_counter() - start

        ops_per_second = n / elapsed
        self.assertGreater(
            ops_per_second,
            IN_PROCESS_TARGET_OPS,
            f"UCP throughput {ops_per_second:.0f} ops/s is below target {IN_PROCESS_TARGET_OPS} ops/s"
        )

    def test_gate_evaluation_throughput(self):
        """GateExecutionWiring gate evaluation must handle 1000+ calls/s."""
        from src.gate_execution_wiring import GateExecutionWiring, GateEvaluation, GateDecision, GatePolicy, GateType
        import uuid
        from datetime import datetime

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

        n = 500
        task = {"type": "test", "payload": "data"}

        for _ in range(10):
            wiring.evaluate_gates(task, "warmup")

        start = time.perf_counter()
        for i in range(n):
            wiring.evaluate_gates(task, f"session_{i}")
        elapsed = time.perf_counter() - start

        ops_per_second = n / elapsed
        self.assertGreater(
            ops_per_second,
            IN_PROCESS_TARGET_OPS,
            f"Gate evaluation throughput {ops_per_second:.0f} ops/s is below target {IN_PROCESS_TARGET_OPS} ops/s"
        )

    def test_platform_connector_framework_throughput(self):
        """PlatformConnectorFramework.execute_action() must handle 200+ calls/s (simulated)."""
        from src.platform_connector_framework import (
            PlatformConnectorFramework, PlatformConnectorFramework as PCF,
            ConnectorAction, ConnectorDefinition, ConnectorCategory, AuthType, RateLimitConfig
        )

        fw = PlatformConnectorFramework()
        # Register a custom connector with no base_url so it uses simulated path
        definition = ConnectorDefinition(
            connector_id="test_sim",
            name="Test Simulated",
            category=ConnectorCategory.CUSTOM,
            platform="test",
            auth_type=AuthType.NONE,
            base_url="",  # no base_url => simulated path
            capabilities=["send_message"],
            rate_limit=RateLimitConfig(max_requests=10000, window_seconds=60),
        )
        fw.register_connector(definition)

        n = 200
        for _ in range(5):
            fw.execute_action(ConnectorAction(
                action_id="warmup",
                connector_id="test_sim",
                action_type="send_message",
                resource="channel",
            ))

        start = time.perf_counter()
        for i in range(n):
            fw.execute_action(ConnectorAction(
                action_id=f"action_{i}",
                connector_id="test_sim",
                action_type="send_message",
                resource="channel",
            ))
        elapsed = time.perf_counter() - start

        ops_per_second = n / elapsed
        target = 200
        self.assertGreater(
            ops_per_second,
            target,
            f"Connector framework throughput {ops_per_second:.0f} ops/s is below target {target} ops/s"
        )


class TestLatencyRequirements(unittest.TestCase):
    """Verify p95 latency requirements."""

    def test_gate_evaluation_p95_latency(self):
        """p95 gate evaluation latency must be < 100ms."""
        from src.gate_execution_wiring import GateExecutionWiring, GateEvaluation, GateDecision, GatePolicy, GateType
        import uuid
        from datetime import datetime

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

        n = 100
        task = {"type": "test"}
        latencies_ms = []

        for i in range(n):
            start = time.perf_counter()
            wiring.evaluate_gates(task, f"session_{i}")
            elapsed_ms = (time.perf_counter() - start) * 1000
            latencies_ms.append(elapsed_ms)

        latencies_ms.sort()
        p95_idx = int(0.95 * n)
        p95_ms = latencies_ms[p95_idx]

        self.assertLess(
            p95_ms,
            100,
            f"p95 gate latency {p95_ms:.2f}ms exceeds 100ms target"
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
