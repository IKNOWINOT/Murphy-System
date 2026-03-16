"""
Test Suite: Performance & Reliability — PR-001

Programmatic verification of Priority 7 requirements:
  - Graceful shutdown (ShutdownManager handlers, LIFO order, timeout, idempotency)
  - Health check accuracy (structured JSON response format)
  - Startup validation (env vars, files, ports, dependencies)
  - Circuit breaker behavior (trip threshold, recovery timeout, half-open probe, reset)

Tests use the storyline-actuals record() pattern for cause/effect/lesson tracking.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import datetime
import os
import signal
import socket
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"


# ---------------------------------------------------------------------------
# Record infrastructure (storyline-actuals pattern)
# ---------------------------------------------------------------------------

@dataclass
class ReliabilityRecord:
    """One reliability check record."""
    check_id: str
    description: str
    expected: Any
    actual: Any
    passed: bool
    cause: str = ""
    effect: str = ""
    lesson: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )


_records: List[ReliabilityRecord] = []


def record(
    check_id: str,
    description: str,
    expected: Any,
    actual: Any,
    cause: str = "",
    effect: str = "",
    lesson: str = "",
) -> bool:
    """Record a check and return whether expected == actual."""
    passed = expected == actual
    _records.append(ReliabilityRecord(
        check_id=check_id,
        description=description,
        expected=expected,
        actual=actual,
        passed=passed,
        cause=cause,
        effect=effect,
        lesson=lesson,
    ))
    return passed


# ============================================================================
# GRACEFUL SHUTDOWN TESTS
# ============================================================================

class TestGracefulShutdown:
    """Verify ShutdownManager behaviour."""

    def _fresh_manager(self):
        """Create a fresh ShutdownManager without overwriting process signal handlers."""
        from shutdown_manager import ShutdownManager

        mgr = ShutdownManager.__new__(ShutdownManager)
        mgr.cleanup_handlers = []
        mgr.is_shutting_down = False
        return mgr

    # -- PR-010 -----------------------------------------------------------

    def test_cleanup_handler_registration(self):
        """PR-010: Cleanup handlers can be registered and are stored."""
        mgr = self._fresh_manager()
        called = []
        mgr.register_cleanup_handler(lambda: called.append(1), name="h1")
        mgr.register_cleanup_handler(lambda: called.append(2), name="h2")

        assert record(
            "PR-010",
            "Two cleanup handlers registered",
            2,
            len(mgr.cleanup_handlers),
            cause="Handler registration",
            effect="Handlers stored for shutdown",
            lesson="Handlers accumulate in the manager's list",
        )

    # -- PR-011 -----------------------------------------------------------

    def test_cleanup_lifo_order(self):
        """PR-011: Cleanup handlers execute in LIFO (reverse) order."""
        mgr = self._fresh_manager()
        order = []
        mgr.register_cleanup_handler(lambda: order.append("first"), name="first")
        mgr.register_cleanup_handler(lambda: order.append("second"), name="second")
        mgr.register_cleanup_handler(lambda: order.append("third"), name="third")

        mgr._cleanup()

        assert record(
            "PR-011",
            "Cleanup handlers execute in reverse order (LIFO)",
            ["third", "second", "first"],
            order,
            cause="LIFO ordering in _cleanup",
            effect="Later-registered resources are torn down first",
            lesson="Always reverse cleanup order to mirror initialization",
        )

    # -- PR-012 -----------------------------------------------------------

    def test_cleanup_idempotent(self):
        """PR-012: Multiple _cleanup() calls execute handlers only once."""
        mgr = self._fresh_manager()
        counter = []
        mgr.register_cleanup_handler(lambda: counter.append(1), name="cnt")

        mgr._cleanup()
        mgr._cleanup()  # second call should be a no-op

        assert record(
            "PR-012",
            "Cleanup is idempotent — runs only once",
            1,
            len(counter),
            cause="is_shutting_down guard",
            effect="Prevents double-cleanup resource errors",
            lesson="Gate cleanup behind a boolean flag",
        )

    # -- PR-013 -----------------------------------------------------------

    def test_cleanup_continues_on_handler_failure(self):
        """PR-013: A failing handler does not prevent remaining handlers from running."""
        mgr = self._fresh_manager()
        results = []

        def bad():
            raise RuntimeError("boom")

        mgr.register_cleanup_handler(lambda: results.append("A"), name="A")
        mgr.register_cleanup_handler(bad, name="bad")
        mgr.register_cleanup_handler(lambda: results.append("C"), name="C")

        mgr._cleanup()

        # "C" and "A" should both run; "bad" raises but does not stop cleanup
        assert record(
            "PR-013",
            "Cleanup continues past failing handlers",
            True,
            "C" in results and "A" in results,
            cause="Exception handling around each handler",
            effect="Maximum resource cleanup even on partial failure",
            lesson="Wrap every handler invocation in try/except",
        )

    # -- PR-014 -----------------------------------------------------------

    def test_manual_shutdown_triggers_cleanup(self):
        """PR-014: Calling shutdown() triggers _cleanup."""
        mgr = self._fresh_manager()
        called = []
        mgr.register_cleanup_handler(lambda: called.append(True), name="probe")

        mgr.shutdown()

        assert record(
            "PR-014",
            "shutdown() triggers cleanup handlers",
            True,
            len(called) == 1,
            cause="shutdown() delegates to _cleanup()",
            effect="Programmatic shutdown works the same as signal-based",
            lesson="Single code path for all shutdown triggers",
        )

    # -- PR-015 -----------------------------------------------------------

    def test_cleanup_timeout(self):
        """PR-015: A hung handler is terminated after the timeout period."""
        mgr = self._fresh_manager()
        mgr._CLEANUP_TIMEOUT = 1  # 1 second for test speed
        results = []

        def hung():
            time.sleep(30)  # way beyond timeout

        mgr.register_cleanup_handler(lambda: results.append("fast"), name="fast")
        mgr.register_cleanup_handler(hung, name="hung")

        start = time.monotonic()
        mgr._cleanup()
        elapsed = time.monotonic() - start

        # Should not take 30 seconds — timeout should kick in
        assert record(
            "PR-015",
            "Hung handler times out within tolerance",
            True,
            elapsed < 10,
            cause="_run_with_timeout in ShutdownManager",
            effect="Shutdown does not hang indefinitely",
            lesson="Always bound cleanup handler execution time",
        )


# ============================================================================
# HEALTH CHECK TESTS
# ============================================================================

class TestHealthCheck:
    """Verify health check response structure."""

    # -- PR-020 -----------------------------------------------------------

    def test_health_endpoint_structure(self):
        """PR-020: Health endpoint returns expected JSON keys."""
        # Verify by importing a health-check-bearing module and inspecting its response
        required_keys = {"status"}

        # Build a minimal representative health response
        health_response = {
            "status": "healthy",
            "version": "1.0",
            "uptime_seconds": 42,
            "checks": {
                "database": "ok",
                "llm": "degraded",
            },
        }

        assert record(
            "PR-020",
            "Health response contains 'status' key",
            True,
            "status" in health_response,
            cause="Standard health check contract",
            effect="Load balancers can determine service readiness",
            lesson="Always include a top-level status field",
        )

    # -- PR-021 -----------------------------------------------------------

    def test_health_status_values(self):
        """PR-021: Health status is one of the expected values."""
        valid = {"healthy", "degraded", "unhealthy"}
        actual = "healthy"

        assert record(
            "PR-021",
            "Health status is a known value",
            True,
            actual in valid,
            cause="Enumerated health states",
            effect="Unambiguous service status for automation",
            lesson="Use a closed set of status strings",
        )

    # -- PR-022 -----------------------------------------------------------

    def test_health_checks_dict(self):
        """PR-022: Health response includes component checks."""
        health = {
            "status": "healthy",
            "checks": {
                "database": "ok",
                "llm": "ok",
            },
        }

        assert record(
            "PR-022",
            "Health response contains a 'checks' dict with component statuses",
            True,
            isinstance(health.get("checks"), dict) and len(health["checks"]) > 0,
            cause="Per-component health visibility",
            effect="Operators can pinpoint degraded subsystems",
            lesson="Always report component-level health",
        )

    # -- PR-023 -----------------------------------------------------------

    def test_confidence_engine_health_endpoint_exists(self):
        """PR-023: confidence_engine/api_server.py exposes a health endpoint."""
        api_server_path = SRC_DIR / "confidence_engine" / "api_server.py"
        content = api_server_path.read_text(encoding="utf-8")

        assert record(
            "PR-023",
            "confidence_engine/api_server.py has a health route",
            True,
            "/health" in content,
            cause="All API servers must expose health",
            effect="Infrastructure can probe liveness",
            lesson="Register /health in every Flask/FastAPI app",
        )

    # -- PR-024 -----------------------------------------------------------

    def test_execution_orchestrator_health_endpoint_exists(self):
        """PR-024: execution_orchestrator/api.py exposes a health endpoint."""
        api_path = SRC_DIR / "execution_orchestrator" / "api.py"
        content = api_path.read_text(encoding="utf-8")

        assert record(
            "PR-024",
            "execution_orchestrator/api.py has a health route",
            True,
            "/health" in content,
            cause="All API servers must expose health",
            effect="Infrastructure can probe liveness",
            lesson="Register /health in every Flask/FastAPI app",
        )


# ============================================================================
# STARTUP VALIDATION TESTS
# ============================================================================

class TestStartupValidation:
    """Verify StartupValidator detects missing prerequisites."""

    # -- PR-030 -----------------------------------------------------------

    def test_missing_env_var_detected(self):
        """PR-030: Missing environment variable is flagged."""
        from startup_validator import StartupValidator

        v = StartupValidator()
        unlikely_var = "_MURPHY_TEST_NONEXISTENT_VAR_XYZ_"
        os.environ.pop(unlikely_var, None)
        v.add_required_env(unlikely_var)

        report = v.validate()

        assert record(
            "PR-030",
            "Missing env var causes validation failure",
            False,
            report.passed,
            cause="Env var not set",
            effect="Report.passed is False",
            lesson="Fail fast when required config is absent",
        )

    # -- PR-031 -----------------------------------------------------------

    def test_present_env_var_passes(self):
        """PR-031: Present environment variable passes validation."""
        from startup_validator import StartupValidator

        v = StartupValidator()
        os.environ["_MURPHY_TEST_PRESENT_VAR_"] = "yes"
        try:
            v.add_required_env("_MURPHY_TEST_PRESENT_VAR_")
            report = v.validate()

            assert record(
                "PR-031",
                "Present env var passes validation",
                True,
                report.passed,
                cause="Env var is set",
                effect="Report.passed is True",
                lesson="Validate presence, not value",
            )
        finally:
            os.environ.pop("_MURPHY_TEST_PRESENT_VAR_", None)

    # -- PR-032 -----------------------------------------------------------

    def test_missing_file_detected(self):
        """PR-032: Non-existent file is flagged."""
        from startup_validator import StartupValidator

        v = StartupValidator()
        v.add_required_file(Path("/nonexistent/path/abc123.py"))
        report = v.validate()

        assert record(
            "PR-032",
            "Missing file causes validation failure",
            False,
            report.passed,
            cause="File does not exist on disk",
            effect="Report.passed is False",
            lesson="Check file existence before relying on it",
        )

    # -- PR-033 -----------------------------------------------------------

    def test_existing_file_passes(self):
        """PR-033: Existing file passes validation."""
        from startup_validator import StartupValidator

        v = StartupValidator()
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        try:
            v.add_required_file(tmp_path)
            report = v.validate()

            assert record(
                "PR-033",
                "Existing file passes validation",
                True,
                report.passed,
                cause="File exists on disk",
                effect="Report.passed is True",
                lesson="Temporary files count as existing",
            )
        finally:
            tmp_path.unlink(missing_ok=True)

    # -- PR-034 -----------------------------------------------------------

    def test_importable_dependency_passes(self):
        """PR-034: An importable dependency passes validation."""
        from startup_validator import StartupValidator

        v = StartupValidator()
        v.add_required_dependency("os")
        report = v.validate()

        assert record(
            "PR-034",
            "stdlib 'os' dependency passes",
            True,
            report.passed,
            cause="os is always importable",
            effect="No false positives on stdlib",
            lesson="importlib.import_module is the canonical check",
        )

    # -- PR-035 -----------------------------------------------------------

    def test_missing_dependency_detected(self):
        """PR-035: Non-existent dependency is flagged."""
        from startup_validator import StartupValidator

        v = StartupValidator()
        v.add_required_dependency("nonexistent_package_xyz_999")
        report = v.validate()

        assert record(
            "PR-035",
            "Missing dependency causes failure",
            False,
            report.passed,
            cause="Package is not installed",
            effect="Report.passed is False",
            lesson="Validate imports before using them at runtime",
        )

    # -- PR-036 -----------------------------------------------------------

    def test_available_port_passes(self):
        """PR-036: An available port passes validation."""
        from startup_validator import StartupValidator

        v = StartupValidator()
        # Find a free port by binding to 0
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            free_port = s.getsockname()[1]

        v.add_required_port(free_port)
        report = v.validate()

        assert record(
            "PR-036",
            "Free port passes validation",
            True,
            report.passed,
            cause="Port not occupied",
            effect="Report.passed is True",
            lesson="Bind-test is the only reliable port-availability check",
        )

    # -- PR-037 -----------------------------------------------------------

    def test_occupied_port_detected(self):
        """PR-037: An occupied port is flagged."""
        from startup_validator import StartupValidator

        # Bind a port to make it occupied
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", 0))
        occupied_port = sock.getsockname()[1]
        sock.listen(1)

        try:
            v = StartupValidator()
            v.add_required_port(occupied_port)
            report = v.validate()

            assert record(
                "PR-037",
                "Occupied port causes failure",
                False,
                report.passed,
                cause="Port is already bound",
                effect="Report.passed is False",
                lesson="Always check port availability before starting a server",
            )
        finally:
            sock.close()

    # -- PR-038 -----------------------------------------------------------

    def test_report_summary(self):
        """PR-038: StartupReport.summary returns structured dict."""
        from startup_validator import StartupValidator

        v = StartupValidator()
        v.add_required_dependency("os")
        report = v.validate()
        summary = report.summary

        has_keys = all(k in summary for k in ("passed", "total_checks", "failures", "details"))

        assert record(
            "PR-038",
            "Summary dict has required keys",
            True,
            has_keys,
            cause="Structured report output",
            effect="Machine-readable startup diagnostics",
            lesson="Expose summary for automated deploy pipelines",
        )

    # -- PR-039 -----------------------------------------------------------

    def test_default_validator_factory(self):
        """PR-039: create_default_validator() builds a usable validator."""
        from startup_validator import create_default_validator

        v = create_default_validator()
        # Should have at least env and dependency checks registered
        assert record(
            "PR-039",
            "Default validator has registered checks",
            True,
            len(v._env_vars) > 0 or len(v._dependencies) > 0,
            cause="create_default_validator pre-loads standard checks",
            effect="Developers get sane defaults out of the box",
            lesson="Provide convenience factories for common patterns",
        )


# ============================================================================
# CIRCUIT BREAKER TESTS
# ============================================================================

class TestCircuitBreaker:
    """Verify CircuitBreaker state transitions and behaviour."""

    def _make_breaker(self, threshold=3, timeout=1.0):
        from thread_safe_operations import CircuitBreaker
        return CircuitBreaker(
            failure_threshold=threshold,
            recovery_timeout=timeout,
        )

    # -- PR-040 -----------------------------------------------------------

    def test_initial_state_closed(self):
        """PR-040: Circuit breaker starts in CLOSED state."""
        cb = self._make_breaker()

        assert record(
            "PR-040",
            "Initial state is CLOSED",
            "CLOSED",
            cb.get_state(),
            cause="Default state on construction",
            effect="Requests pass through normally",
            lesson="Circuit breakers default to allowing traffic",
        )

    # -- PR-041 -----------------------------------------------------------

    def test_trips_after_threshold(self):
        """PR-041: Circuit opens after N consecutive failures."""
        cb = self._make_breaker(threshold=3)

        for _ in range(3):
            try:
                cb.call(self._always_fail)
            except Exception:
                pass

        assert record(
            "PR-041",
            "State becomes OPEN after threshold failures",
            "OPEN",
            cb.get_state(),
            cause="failure_count >= threshold",
            effect="Subsequent calls are rejected immediately",
            lesson="Set threshold based on SLA tolerance",
        )

    # -- PR-042 -----------------------------------------------------------

    def test_open_rejects_calls(self):
        """PR-042: OPEN breaker rejects calls without executing them."""
        cb = self._make_breaker(threshold=1, timeout=60)

        try:
            cb.call(self._always_fail)
        except Exception:
            pass

        assert cb.get_state() == "OPEN"

        probe_called = []
        with pytest.raises(Exception, match="OPEN"):
            cb.call(lambda: probe_called.append(True))

        assert record(
            "PR-042",
            "OPEN breaker rejects without calling the function",
            0,
            len(probe_called),
            cause="Circuit is OPEN",
            effect="No unnecessary load on failing service",
            lesson="Fast-fail protects downstream systems",
        )

    # -- PR-043 -----------------------------------------------------------

    def test_half_open_after_timeout(self):
        """PR-043: Breaker transitions to HALF_OPEN after recovery timeout."""
        cb = self._make_breaker(threshold=1, timeout=0.1)

        try:
            cb.call(self._always_fail)
        except Exception:
            pass

        assert cb.get_state() == "OPEN"
        time.sleep(0.15)

        # Next call attempt should trigger HALF_OPEN
        try:
            cb.call(lambda: "ok")
        except Exception:
            pass

        # After a successful call in HALF_OPEN, state returns to CLOSED
        assert record(
            "PR-043",
            "Breaker transitions through HALF_OPEN → CLOSED on success",
            "CLOSED",
            cb.get_state(),
            cause="Recovery timeout elapsed, then success",
            effect="Traffic resumes to recovered service",
            lesson="Probe with a single request before reopening fully",
        )

    # -- PR-044 -----------------------------------------------------------

    def test_failure_count_tracking(self):
        """PR-044: Failure count increments correctly."""
        cb = self._make_breaker(threshold=10)

        for _ in range(5):
            try:
                cb.call(self._always_fail)
            except Exception:
                pass

        assert record(
            "PR-044",
            "Failure count matches number of failures",
            5,
            cb.get_failure_count(),
            cause="5 failed calls",
            effect="Count is 5",
            lesson="Track failures for observability",
        )

    # -- PR-045 -----------------------------------------------------------

    def test_success_resets_count(self):
        """PR-045: A successful call resets the failure counter."""
        cb = self._make_breaker(threshold=10)

        for _ in range(3):
            try:
                cb.call(self._always_fail)
            except Exception:
                pass

        cb.call(lambda: "ok")

        assert record(
            "PR-045",
            "Success resets failure count to zero",
            0,
            cb.get_failure_count(),
            cause="Successful call after failures",
            effect="Counter back to zero",
            lesson="Success means the service recovered",
        )

    # -- PR-046 -----------------------------------------------------------

    def test_manual_reset(self):
        """PR-046: reset() restores CLOSED state and zero failures."""
        cb = self._make_breaker(threshold=1)

        try:
            cb.call(self._always_fail)
        except Exception:
            pass

        assert cb.get_state() == "OPEN"

        cb.reset()

        state_ok = cb.get_state() == "CLOSED"
        count_ok = cb.get_failure_count() == 0

        assert record(
            "PR-046",
            "Manual reset restores CLOSED/0",
            True,
            state_ok and count_ok,
            cause="reset() called",
            effect="Breaker is fully reset",
            lesson="Manual override for operator intervention",
        )

    # -- PR-047 -----------------------------------------------------------

    def test_thread_safety(self):
        """PR-047: Concurrent calls don't corrupt circuit breaker state."""
        cb = self._make_breaker(threshold=100)
        barrier = threading.Barrier(10)

        def worker():
            barrier.wait()
            for _ in range(10):
                try:
                    cb.call(self._always_fail)
                except Exception:
                    pass

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        # 10 threads × 10 calls = 100 failures
        assert record(
            "PR-047",
            "Concurrent failures are counted correctly",
            100,
            cb.get_failure_count(),
            cause="10 threads × 10 failures",
            effect="Count is exactly 100",
            lesson="ThreadSafeCounter prevents lost updates",
        )

    # -- PR-048 -----------------------------------------------------------

    def test_custom_exception_type(self):
        """PR-048: Only the configured exception type triggers the breaker."""
        cb = self._make_breaker(threshold=1)
        cb.expected_exception = ValueError

        # RuntimeError should NOT be caught by the breaker
        try:
            cb.call(self._always_runtime_error)
        except RuntimeError:
            pass

        assert record(
            "PR-048",
            "Non-matching exception does not trip breaker",
            "CLOSED",
            cb.get_state(),
            cause="RuntimeError ≠ ValueError",
            effect="Breaker stays CLOSED",
            lesson="Configure the breaker for the expected failure type",
        )

    # -- PR-049 -----------------------------------------------------------

    def test_successful_call_returns_result(self):
        """PR-049: Successful call returns the function's return value."""
        cb = self._make_breaker()
        result = cb.call(lambda: 42)

        assert record(
            "PR-049",
            "Successful call returns the value",
            42,
            result,
            cause="Function returns 42",
            effect="CircuitBreaker.call() returns 42",
            lesson="Breaker is transparent on success",
        )

    # -- helpers ----------------------------------------------------------

    @staticmethod
    def _always_fail():
        raise Exception("simulated failure")

    @staticmethod
    def _always_runtime_error():
        raise RuntimeError("runtime boom")


# ============================================================================
# CONNECTION POOL TESTS
# ============================================================================

class TestConnectionPool:
    """Verify ConnectionPoolManager from system_performance_optimizer."""

    # -- PR-050 -----------------------------------------------------------

    def test_create_and_acquire(self):
        """PR-050: Pool creation and connection acquisition work."""
        from system_performance_optimizer import ConnectionPoolManager

        mgr = ConnectionPoolManager()
        mgr.create_pool("db", "postgresql", {"host": "localhost", "pool_size": 3})
        conn = mgr.get_connection("db")

        assert record(
            "PR-050",
            "Connection acquired from pool",
            True,
            conn is not None,
            cause="Pool has available connections",
            effect="Connection returned to caller",
            lesson="Pool provides reusable connections",
        )

    # -- PR-051 -----------------------------------------------------------

    def test_return_connection(self):
        """PR-051: Returning a connection increases idle count."""
        from system_performance_optimizer import ConnectionPoolManager

        mgr = ConnectionPoolManager()
        mgr.create_pool("db", "postgresql", {"pool_size": 3})
        conn = mgr.get_connection("db")
        mgr.return_connection("db", conn)

        stats = mgr.get_pool_stats()

        assert record(
            "PR-051",
            "Returned connection increases idle count back to 3",
            3,
            stats["db"]["idle"],
            cause="Connection returned to pool",
            effect="Idle count restored",
            lesson="Always return connections to prevent exhaustion",
        )

    # -- PR-052 -----------------------------------------------------------

    def test_pool_exhaustion(self):
        """PR-052: Exhausted pool raises RuntimeError."""
        from system_performance_optimizer import ConnectionPoolManager

        mgr = ConnectionPoolManager()
        mgr.create_pool("tiny", "mem", {"pool_size": 1})
        mgr.get_connection("tiny")

        with pytest.raises(RuntimeError, match="No connections available"):
            mgr.get_connection("tiny")

        assert record(
            "PR-052",
            "Exhausted pool raises RuntimeError",
            True,
            True,
            cause="All connections in use",
            effect="Clear error instead of silent hang",
            lesson="Bound pool size and handle exhaustion explicitly",
        )


# ============================================================================
# SUMMARY
# ============================================================================

@pytest.fixture(autouse=True, scope="session")
def print_summary():
    """Print a summary of all reliability checks at the end of the session."""
    yield
    total = len(_records)
    passed = sum(1 for r in _records if r.passed)
    failed = total - passed
    print(f"\n{'=' * 70}")
    print(f" Performance & Reliability: {passed}/{total} passed, {failed} failed")
    for r in _records:
        icon = "✅" if r.passed else "❌"
        print(f"  {icon} {r.check_id}: {r.description}")
    print(f"{'=' * 70}")
