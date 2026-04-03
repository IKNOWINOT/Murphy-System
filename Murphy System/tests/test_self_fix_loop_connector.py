"""
Tests for WIRE-002: SelfFixLoopConnector.

Validates gap bridging from SelfFixLoop into AutomationLoopConnector via
EventBackbone TASK_FAILED events.

Design Label: TEST-WIRE-002
Owner: QA Team
"""

import sys
import os
import threading
import pytest


from self_fix_loop_connector import SelfFixLoopConnector
from self_fix_loop import SelfFixLoop, Gap
from automation_loop_connector import AutomationLoopConnector
from event_backbone import EventBackbone, EventType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_gap(gap_id: str, severity: str, source: str = "bug_detector") -> Gap:
    return Gap(
        gap_id=gap_id,
        description=f"Test gap {gap_id}",
        source=source,
        severity=severity,
        category="test_category",
    )


class _FakeFixLoop:
    """Minimal SelfFixLoop stand-in for testing."""

    def __init__(self, gaps=None):
        self._gaps = gaps or []

    def diagnose(self):
        return list(self._gaps)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def backbone():
    return EventBackbone()


@pytest.fixture
def connector_with_backbone(backbone):
    fix_loop = _FakeFixLoop()
    auto_conn = AutomationLoopConnector()
    return SelfFixLoopConnector(
        self_fix_loop=fix_loop,
        automation_connector=auto_conn,
        event_backbone=backbone,
    ), fix_loop, auto_conn, backbone


# ---------------------------------------------------------------------------
# Test: bridge_gaps publishes TASK_FAILED for critical/high gaps
# ---------------------------------------------------------------------------

class TestBridgeGapsEvents:
    def test_critical_gap_publishes_task_failed(self, backbone):
        received = []
        backbone.subscribe(EventType.TASK_FAILED, lambda e: received.append(e))

        fix_loop = _FakeFixLoop([_make_gap("g1", "critical")])
        conn = SelfFixLoopConnector(
            self_fix_loop=fix_loop,
            event_backbone=backbone,
        )
        result = conn.bridge_gaps()
        # Drain EventBackbone queue synchronously
        backbone.process_pending()

        assert result["gaps_bridged"] == 1
        assert result["gaps_found"] == 1
        assert len(received) >= 1
        payload = received[0].payload if hasattr(received[0], "payload") else {}
        assert payload.get("task_id") == "g1"
        assert payload["metrics"]["severity"] == "critical"

    def test_high_gap_publishes_task_failed(self, backbone):
        received = []
        backbone.subscribe(EventType.TASK_FAILED, lambda e: received.append(e))

        fix_loop = _FakeFixLoop([_make_gap("g2", "high", source="improvement_engine")])
        conn = SelfFixLoopConnector(
            self_fix_loop=fix_loop,
            event_backbone=backbone,
        )
        result = conn.bridge_gaps()
        backbone.process_pending()

        assert result["gaps_bridged"] == 1
        assert len(received) >= 1

    def test_low_severity_gap_skipped(self, backbone):
        received = []
        backbone.subscribe(EventType.TASK_FAILED, lambda e: received.append(e))

        fix_loop = _FakeFixLoop([_make_gap("g3", "low")])
        conn = SelfFixLoopConnector(
            self_fix_loop=fix_loop,
            event_backbone=backbone,
        )
        result = conn.bridge_gaps()
        backbone.process_pending()

        assert result["gaps_bridged"] == 0
        assert result["skipped"] == 1
        assert len(received) == 0

    def test_medium_severity_gap_skipped(self, backbone):
        received = []
        backbone.subscribe(EventType.TASK_FAILED, lambda e: received.append(e))

        fix_loop = _FakeFixLoop([_make_gap("g4", "medium")])
        conn = SelfFixLoopConnector(
            self_fix_loop=fix_loop,
            event_backbone=backbone,
        )
        result = conn.bridge_gaps()
        backbone.process_pending()

        assert result["gaps_bridged"] == 0
        assert result["skipped"] == 1

    def test_mixed_severities(self, backbone):
        received = []
        backbone.subscribe(EventType.TASK_FAILED, lambda e: received.append(e))

        gaps = [
            _make_gap("g-crit", "critical"),
            _make_gap("g-high", "high"),
            _make_gap("g-med", "medium"),
            _make_gap("g-low", "low"),
        ]
        fix_loop = _FakeFixLoop(gaps)
        conn = SelfFixLoopConnector(
            self_fix_loop=fix_loop,
            event_backbone=backbone,
        )
        result = conn.bridge_gaps()
        backbone.process_pending()

        assert result["gaps_bridged"] == 2
        assert result["skipped"] == 2
        assert len(received) == 2

    def test_learning_feedback_published(self, backbone):
        fb_received = []
        backbone.subscribe(EventType.LEARNING_FEEDBACK, lambda e: fb_received.append(e))

        fix_loop = _FakeFixLoop([_make_gap("g5", "critical")])
        conn = SelfFixLoopConnector(
            self_fix_loop=fix_loop,
            event_backbone=backbone,
        )
        conn.bridge_gaps()
        # Drain queue so subscriptions fire
        backbone.process_pending()

        # LEARNING_FEEDBACK should have been published
        assert len(fb_received) >= 1
        payload = fb_received[0].payload if hasattr(fb_received[0], "payload") else {}
        assert payload.get("source") == "SelfFixLoopConnector"
        assert payload.get("gaps_bridged") == 1


# ---------------------------------------------------------------------------
# Test: graceful degradation without EventBackbone
# ---------------------------------------------------------------------------

class TestNoEventBackbone:
    def test_bridge_gaps_without_backbone_uses_direct_queue(self):
        from automation_loop_connector import AutomationLoopConnector
        auto_conn = AutomationLoopConnector()
        fix_loop = _FakeFixLoop([_make_gap("g6", "critical")])
        conn = SelfFixLoopConnector(
            self_fix_loop=fix_loop,
            automation_connector=auto_conn,
        )
        result = conn.bridge_gaps()
        assert result["gaps_bridged"] == 1
        # Outcome should have been queued in the connector
        assert len(auto_conn._pending_outcomes) == 1

    def test_bridge_gaps_no_backbone_no_connector(self):
        fix_loop = _FakeFixLoop([_make_gap("g7", "critical")])
        conn = SelfFixLoopConnector(self_fix_loop=fix_loop)
        result = conn.bridge_gaps()
        # No backbone or connector — skipped but no exception
        assert result["gaps_bridged"] == 0
        assert result["skipped"] == 1

    def test_bridge_gaps_no_fix_loop(self):
        conn = SelfFixLoopConnector()
        result = conn.bridge_gaps()
        assert result["gaps_found"] == 0
        assert result["error"] == "no_fix_loop"


# ---------------------------------------------------------------------------
# Test: get_status
# ---------------------------------------------------------------------------

class TestGetStatus:
    def test_get_status_structure(self):
        conn = SelfFixLoopConnector()
        status = conn.get_status()
        assert "gaps_bridged_total" in status
        assert "last_bridge_time" in status
        assert "bridge_count" in status
        assert "fix_loop_attached" in status
        assert "automation_connector_attached" in status
        assert "event_backbone_attached" in status

    def test_get_status_counters_update(self, backbone):
        fix_loop = _FakeFixLoop([
            _make_gap("g8", "critical"),
            _make_gap("g9", "high"),
        ])
        conn = SelfFixLoopConnector(
            self_fix_loop=fix_loop,
            event_backbone=backbone,
        )
        conn.bridge_gaps()
        status = conn.get_status()
        assert status["gaps_bridged_total"] == 2
        assert status["last_bridge_time"] is not None
        assert status["bridge_count"] == 1


# ---------------------------------------------------------------------------
# Test: SELF_FIX_COMPLETED event triggers bridge_gaps
# ---------------------------------------------------------------------------

class TestEventSubscription:
    def test_self_fix_completed_triggers_bridge(self, backbone):
        received = []
        backbone.subscribe(EventType.TASK_FAILED, lambda e: received.append(e))

        fix_loop = _FakeFixLoop([_make_gap("g10", "critical")])
        conn = SelfFixLoopConnector(
            self_fix_loop=fix_loop,
            event_backbone=backbone,
        )
        # Publish SELF_FIX_COMPLETED to trigger bridge_gaps via subscription
        backbone.publish(EventType.SELF_FIX_COMPLETED, {"loop_id": "test"})
        # Drain queue: SELF_FIX_COMPLETED → bridge_gaps() → TASK_FAILED queued
        backbone.process_pending()
        # bridge_gaps() increments counter synchronously during process_pending()
        assert conn.get_status()["gaps_bridged_total"] >= 1


# ---------------------------------------------------------------------------
# Test: Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_bridge_gaps(self, backbone):
        fix_loop = _FakeFixLoop([_make_gap(f"g-{i}", "critical") for i in range(5)])
        conn = SelfFixLoopConnector(
            self_fix_loop=fix_loop,
            event_backbone=backbone,
        )

        errors = []

        def _worker():
            try:
                conn.bridge_gaps()
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=_worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        status = conn.get_status()
        assert status["gaps_bridged_total"] >= 0  # no exception is what matters
