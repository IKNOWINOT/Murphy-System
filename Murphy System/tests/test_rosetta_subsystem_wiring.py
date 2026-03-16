"""
Gap Closure Tests — Rosetta Subsystem Wiring (INC-07 Phase 3).

Validates the five P3 integration wiring points between the Rosetta
state-management layer and the Murphy System runtime (P3-001 to P3-005):

  P3-001  Rosetta ↔ Event Backbone
  P3-002  Rosetta ↔ Confidence Engine
  P3-003  Rosetta ↔ Learning Engine
  P3-004  Rosetta ↔ Governance Kernel
  P3-005  Rosetta ↔ Security Plane

Gaps addressed:
 1. WiringPoint, WiringStatus, WiringResult data structures
 2. RosettaSubsystemWiring.wire_all() — all 5 points
 3. RosettaSubsystemWiring.wire_point() — individual point
 4. WiringResult.is_ok() and to_dict()
 5. Adapter injection pattern (test-double adapters)
 6. Strict mode raises on FAILED points
 7. unwind_all() tears down wiring
 8. summary() reporting
 9. bootstrap_wiring() convenience function
10. Thread safety under concurrent wire_point() calls
"""

import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pytest


# ===========================================================================
# Helpers
# ===========================================================================

def _get_classes():
    from rosetta.subsystem_wiring import (
        WiringPoint,
        WiringStatus,
        WiringResult,
        RosettaSubsystemWiring,
        bootstrap_wiring,
    )
    return WiringPoint, WiringStatus, WiringResult, RosettaSubsystemWiring, bootstrap_wiring


# ===========================================================================
# Gap 1 — Data structures
# ===========================================================================

class TestGap1_DataStructures:
    def test_wiring_point_enum_values(self):
        WiringPoint, *_ = _get_classes()
        assert WiringPoint.EVENT_BACKBONE.value == "P3-001:event_backbone"
        assert WiringPoint.CONFIDENCE_ENGINE.value == "P3-002:confidence_engine"
        assert WiringPoint.LEARNING_ENGINE.value == "P3-003:learning_engine"
        assert WiringPoint.GOVERNANCE_KERNEL.value == "P3-004:governance_kernel"
        assert WiringPoint.SECURITY_PLANE.value == "P3-005:security_plane"

    def test_wiring_point_five_values(self):
        WiringPoint, *_ = _get_classes()
        assert len(list(WiringPoint)) == 5

    def test_wiring_status_values(self):
        _, WiringStatus, *_ = _get_classes()
        assert WiringStatus.PENDING.value == "pending"
        assert WiringStatus.WIRED.value == "wired"
        assert WiringStatus.DEGRADED.value == "degraded"
        assert WiringStatus.FAILED.value == "failed"
        assert WiringStatus.UNWIRED.value == "unwired"

    def test_wiring_result_creation(self):
        WiringPoint, WiringStatus, WiringResult, *_ = _get_classes()
        r = WiringResult(WiringPoint.EVENT_BACKBONE, WiringStatus.WIRED, "ok")
        assert r.point == WiringPoint.EVENT_BACKBONE
        assert r.status == WiringStatus.WIRED
        assert r.message == "ok"

    def test_wiring_result_is_ok_wired(self):
        WiringPoint, WiringStatus, WiringResult, *_ = _get_classes()
        r = WiringResult(WiringPoint.CONFIDENCE_ENGINE, WiringStatus.WIRED)
        assert r.is_ok() is True

    def test_wiring_result_is_ok_degraded(self):
        WiringPoint, WiringStatus, WiringResult, *_ = _get_classes()
        r = WiringResult(WiringPoint.CONFIDENCE_ENGINE, WiringStatus.DEGRADED)
        assert r.is_ok() is True

    def test_wiring_result_is_ok_failed(self):
        WiringPoint, WiringStatus, WiringResult, *_ = _get_classes()
        r = WiringResult(WiringPoint.CONFIDENCE_ENGINE, WiringStatus.FAILED)
        assert r.is_ok() is False

    def test_wiring_result_to_dict(self):
        WiringPoint, WiringStatus, WiringResult, *_ = _get_classes()
        r = WiringResult(WiringPoint.EVENT_BACKBONE, WiringStatus.WIRED, "done")
        d = r.to_dict()
        assert d["point"] == "P3-001:event_backbone"
        assert d["status"] == "wired"
        assert d["message"] == "done"
        assert "timestamp" in d
        assert "duration_ms" in d


# ===========================================================================
# Gap 2 — wire_all() default (no-op) adapters
# ===========================================================================

class TestGap2_WireAll:
    def test_wire_all_returns_five_results(self):
        *_, RosettaSubsystemWiring, _ = _get_classes()
        wiring = RosettaSubsystemWiring()
        results = wiring.wire_all()
        assert len(results) == 5

    def test_wire_all_default_all_wired(self):
        *_, RosettaSubsystemWiring, _ = _get_classes()
        wiring = RosettaSubsystemWiring()
        results = wiring.wire_all()
        WiringPoint, WiringStatus, *_ = _get_classes()
        assert all(r.status == WiringStatus.WIRED for r in results)

    def test_wire_all_returns_all_points(self):
        WiringPoint, *_, RosettaSubsystemWiring, _ = _get_classes()
        wiring = RosettaSubsystemWiring()
        results = wiring.wire_all()
        points = {r.point for r in results}
        assert points == set(WiringPoint)

    def test_wire_all_duration_populated(self):
        *_, RosettaSubsystemWiring, _ = _get_classes()
        wiring = RosettaSubsystemWiring()
        results = wiring.wire_all()
        assert all(r.duration_ms >= 0 for r in results)

    def test_wire_all_message_populated(self):
        *_, RosettaSubsystemWiring, _ = _get_classes()
        wiring = RosettaSubsystemWiring()
        results = wiring.wire_all()
        assert all(r.message for r in results)


# ===========================================================================
# Gap 3 — wire_point() individual point
# ===========================================================================

class TestGap3_WirePoint:
    def test_wire_single_point_event_backbone(self):
        WiringPoint, WiringStatus, _, RosettaSubsystemWiring, _ = _get_classes()
        wiring = RosettaSubsystemWiring()
        result = wiring.wire_point(WiringPoint.EVENT_BACKBONE)
        assert result.status == WiringStatus.WIRED

    def test_wire_single_point_security_plane(self):
        WiringPoint, WiringStatus, _, RosettaSubsystemWiring, _ = _get_classes()
        wiring = RosettaSubsystemWiring()
        result = wiring.wire_point(WiringPoint.SECURITY_PLANE)
        assert result.status == WiringStatus.WIRED

    def test_wire_point_result_stored(self):
        WiringPoint, WiringStatus, _, RosettaSubsystemWiring, _ = _get_classes()
        wiring = RosettaSubsystemWiring()
        wiring.wire_point(WiringPoint.LEARNING_ENGINE)
        stored = wiring.get_result(WiringPoint.LEARNING_ENGINE)
        assert stored is not None
        assert stored.status == WiringStatus.WIRED

    def test_get_result_before_wire_returns_none(self):
        WiringPoint, _, _, RosettaSubsystemWiring, _ = _get_classes()
        wiring = RosettaSubsystemWiring()
        assert wiring.get_result(WiringPoint.GOVERNANCE_KERNEL) is None


# ===========================================================================
# Gap 4 — WiringResult is_ok / to_dict
# ===========================================================================

class TestGap4_WiringResult:
    def test_to_dict_has_all_keys(self):
        WiringPoint, WiringStatus, WiringResult, *_ = _get_classes()
        r = WiringResult(WiringPoint.GOVERNANCE_KERNEL, WiringStatus.WIRED, "ok")
        d = r.to_dict()
        assert set(d.keys()) >= {"point", "status", "message", "duration_ms", "timestamp", "metadata"}

    def test_pending_not_ok(self):
        WiringPoint, WiringStatus, WiringResult, *_ = _get_classes()
        r = WiringResult(WiringPoint.SECURITY_PLANE, WiringStatus.PENDING)
        assert r.is_ok() is False

    def test_unwired_not_ok(self):
        WiringPoint, WiringStatus, WiringResult, *_ = _get_classes()
        r = WiringResult(WiringPoint.EVENT_BACKBONE, WiringStatus.UNWIRED)
        assert r.is_ok() is False

    def test_metadata_preserved(self):
        WiringPoint, WiringStatus, WiringResult, *_ = _get_classes()
        r = WiringResult(
            WiringPoint.CONFIDENCE_ENGINE,
            WiringStatus.WIRED,
            metadata={"version": "2"},
        )
        assert r.to_dict()["metadata"]["version"] == "2"


# ===========================================================================
# Gap 5 — Adapter injection
# ===========================================================================

class TestGap5_AdapterInjection:
    def test_custom_adapter_called(self):
        WiringPoint, WiringStatus, _, RosettaSubsystemWiring, _ = _get_classes()
        called = {}

        def my_adapter(mgr):
            called["ok"] = True

        wiring = RosettaSubsystemWiring(
            adapters={WiringPoint.EVENT_BACKBONE: my_adapter}
        )
        wiring.wire_point(WiringPoint.EVENT_BACKBONE)
        assert called.get("ok") is True

    def test_failing_adapter_yields_failed_status(self):
        WiringPoint, WiringStatus, _, RosettaSubsystemWiring, _ = _get_classes()

        def bad_adapter(mgr):
            raise RuntimeError("simulated failure")

        wiring = RosettaSubsystemWiring(
            adapters={WiringPoint.CONFIDENCE_ENGINE: bad_adapter}
        )
        result = wiring.wire_point(WiringPoint.CONFIDENCE_ENGINE)
        assert result.status == WiringStatus.FAILED

    def test_adapter_receives_manager(self):
        WiringPoint, _, _, RosettaSubsystemWiring, _ = _get_classes()
        received = {}

        def capture(mgr):
            received["mgr"] = mgr

        sentinel = object()
        wiring = RosettaSubsystemWiring(
            rosetta_manager=sentinel,
            adapters={WiringPoint.LEARNING_ENGINE: capture},
        )
        wiring.wire_point(WiringPoint.LEARNING_ENGINE)
        assert received["mgr"] is sentinel

    def test_non_overridden_points_use_default(self):
        WiringPoint, WiringStatus, _, RosettaSubsystemWiring, _ = _get_classes()
        wiring = RosettaSubsystemWiring(
            adapters={WiringPoint.EVENT_BACKBONE: lambda _: None}
        )
        wiring.wire_all()
        result = wiring.get_result(WiringPoint.GOVERNANCE_KERNEL)
        assert result.status == WiringStatus.WIRED


# ===========================================================================
# Gap 6 — Strict mode
# ===========================================================================

class TestGap6_StrictMode:
    def test_strict_raises_on_failed_point(self):
        WiringPoint, _, _, RosettaSubsystemWiring, _ = _get_classes()

        def fail(mgr):
            raise ValueError("deliberate")

        wiring = RosettaSubsystemWiring(
            adapters={WiringPoint.SECURITY_PLANE: fail},
            strict=True,
        )
        with pytest.raises(RuntimeError, match="Rosetta subsystem wiring failed"):
            wiring.wire_all()

    def test_non_strict_no_raise_on_failed(self):
        WiringPoint, WiringStatus, _, RosettaSubsystemWiring, _ = _get_classes()

        def fail(mgr):
            raise ValueError("deliberate")

        wiring = RosettaSubsystemWiring(
            adapters={WiringPoint.SECURITY_PLANE: fail},
            strict=False,
        )
        results = wiring.wire_all()
        failed = [r for r in results if r.status == WiringStatus.FAILED]
        assert len(failed) == 1


# ===========================================================================
# Gap 7 — unwind_all()
# ===========================================================================

class TestGap7_UnwindAll:
    def test_unwind_all_returns_results(self):
        WiringPoint, WiringStatus, _, RosettaSubsystemWiring, _ = _get_classes()
        wiring = RosettaSubsystemWiring()
        wiring.wire_all()
        unwound = wiring.unwind_all()
        assert len(unwound) == 5

    def test_unwind_sets_unwired_status(self):
        WiringPoint, WiringStatus, _, RosettaSubsystemWiring, _ = _get_classes()
        wiring = RosettaSubsystemWiring()
        wiring.wire_all()
        unwound = wiring.unwind_all()
        assert all(r.status == WiringStatus.UNWIRED for r in unwound)

    def test_fully_wired_false_after_unwind(self):
        WiringPoint, _, _, RosettaSubsystemWiring, _ = _get_classes()
        wiring = RosettaSubsystemWiring()
        wiring.wire_all()
        wiring.unwind_all()
        assert wiring.is_fully_wired() is False


# ===========================================================================
# Gap 8 — summary()
# ===========================================================================

class TestGap8_Summary:
    def test_summary_after_wire_all(self):
        *_, RosettaSubsystemWiring, _ = _get_classes()
        wiring = RosettaSubsystemWiring()
        wiring.wire_all()
        s = wiring.summary()
        assert s["total_points"] == 5
        assert s["wired"] == 5
        assert s["fully_wired"] is True
        assert s["failed"] == 0

    def test_summary_before_wire(self):
        *_, RosettaSubsystemWiring, _ = _get_classes()
        wiring = RosettaSubsystemWiring()
        s = wiring.summary()
        assert s["pending"] == 5
        assert s["wired"] == 0

    def test_summary_partial_failure(self):
        WiringPoint, WiringStatus, _, RosettaSubsystemWiring, _ = _get_classes()

        def fail(mgr):
            raise RuntimeError()

        wiring = RosettaSubsystemWiring(
            adapters={WiringPoint.EVENT_BACKBONE: fail}
        )
        wiring.wire_all()
        s = wiring.summary()
        assert s["failed"] == 1
        assert s["wired"] == 4
        assert s["fully_wired"] is False


# ===========================================================================
# Gap 9 — bootstrap_wiring()
# ===========================================================================

class TestGap9_BootstrapWiring:
    def test_bootstrap_returns_wiring_instance(self):
        *_, RosettaSubsystemWiring, bootstrap_wiring = _get_classes()
        w = bootstrap_wiring()
        assert isinstance(w, RosettaSubsystemWiring)

    def test_bootstrap_all_wired(self):
        *_, bootstrap_wiring = _get_classes()
        w = bootstrap_wiring()
        assert w.is_fully_wired() is True

    def test_bootstrap_with_manager(self):
        *_, bootstrap_wiring = _get_classes()
        sentinel = object()
        w = bootstrap_wiring(rosetta_manager=sentinel)
        assert w._manager is sentinel

    def test_bootstrap_strict_false_no_raise(self):
        *_, bootstrap_wiring = _get_classes()
        w = bootstrap_wiring(strict=False)
        assert w is not None

    def test_bootstrap_all_results_populated(self):
        WiringPoint, *_, bootstrap_wiring = _get_classes()
        w = bootstrap_wiring()
        results = w.all_results()
        assert len(results) == 5


# ===========================================================================
# Gap 10 — Thread safety
# ===========================================================================

class TestGap10_ThreadSafety:
    def test_concurrent_wire_point(self):
        WiringPoint, WiringStatus, _, RosettaSubsystemWiring, _ = _get_classes()
        wiring = RosettaSubsystemWiring()
        results = []
        lock = threading.Lock()

        def wire(point):
            r = wiring.wire_point(point)
            with lock:
                results.append(r)

        threads = [
            threading.Thread(target=wire, args=(p,)) for p in WiringPoint
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(results) == 5
        assert all(r.status == WiringStatus.WIRED for r in results)

    def test_concurrent_wire_all(self):
        *_, RosettaSubsystemWiring, _ = _get_classes()
        wiring = RosettaSubsystemWiring()
        errors = []

        def run():
            try:
                wiring.wire_all()
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=run) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors
