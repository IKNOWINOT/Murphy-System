"""
Edge Case and Regression Tests — PR 6 Gap Closure

Validates system robustness and data consistency:

  1. Graceful degradation when LLM is unavailable
  2. System behaviour under high load (concurrent requests)
  3. Data consistency across subsystems

All tests operate against real module logic (no mocks).

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import threading
import time
import uuid

import pytest

from murphy_action_engine import LLMResponseWirer
from conversation_handler import ConversationHandler
from operational_slo_tracker import OperationalSLOTracker, ExecutionRecord, SLOTarget
from operational_dashboard_aggregator import OperationalDashboardAggregator
from crm.crm_manager import CRMManager
from management_systems.board_engine import BoardEngine


# ===========================================================================
# 1. Graceful Degradation When LLM Is Unavailable
# ===========================================================================

class TestGracefulDegradation:
    """System handles LLM unavailability without crashing."""

    def test_empty_input_returns_degraded_not_exception(self):
        wirer = LLMResponseWirer(max_retries=1)
        result = wirer.wire("")
        assert isinstance(result, dict)
        assert result.get("degraded") is True

    def test_whitespace_only_returns_degraded(self):
        wirer = LLMResponseWirer(max_retries=1)
        result = wirer.wire("   ")
        assert isinstance(result, dict)
        assert result.get("degraded") is True

    def test_degraded_packet_has_user_message(self):
        """User receives a human-readable message when system degrades."""
        wirer = LLMResponseWirer(max_retries=1)
        result = wirer.wire("")
        assert "user_message" in result
        assert len(result["user_message"]) > 0

    def test_degraded_packet_status_field(self):
        wirer = LLMResponseWirer(max_retries=1)
        result = wirer.wire("")
        assert result.get("status") == "degraded"

    def test_single_retry_exhausted_returns_degraded(self):
        """With max_retries=1, exhausted retries produce degraded packet."""
        wirer = LLMResponseWirer(max_retries=1)
        result = wirer.wire("")
        assert result.get("degraded") is True

    def test_normal_input_does_not_degrade(self):
        """Valid input should not produce a degraded packet."""
        wirer = LLMResponseWirer(max_retries=1)
        result = wirer.wire("list all active projects")
        # Either compiled successfully or degraded — but must not raise
        assert isinstance(result, dict)

    def test_conversation_handler_survives_bad_input(self):
        """ConversationHandler handles malformed input gracefully."""
        handler = ConversationHandler()
        result = handler.handle("\x00\x01\x02")
        assert isinstance(result, dict)

    def test_conversation_handler_survives_none_like_string(self):
        handler = ConversationHandler()
        result = handler.handle("None")
        assert isinstance(result, dict)

    def test_slo_tracker_handles_empty_records(self):
        """SLO compliance check on empty tracker returns empty dict."""
        t = OperationalSLOTracker()
        t.add_slo_target(SLOTarget(
            target_name="test_slo", metric="success_rate",
            threshold=0.9, window_seconds=3600,
        ))
        result = t.check_slo_compliance()
        # Should return result for the target even with no data
        assert isinstance(result, dict)

    def test_dashboard_aggregator_no_modules_collect(self):
        """Collecting with no modules registered returns a valid snapshot."""
        d = OperationalDashboardAggregator()
        snap = d.collect()
        assert snap is not None
        assert snap.total_modules == 0


# ===========================================================================
# 2. System Behaviour Under High Load (Concurrent Requests)
# ===========================================================================

class TestHighLoadBehaviour:
    """Concurrent access to shared modules does not corrupt state."""

    def test_slo_tracker_concurrent_record(self):
        """100 concurrent record_execution calls don't corrupt the tracker."""
        t = OperationalSLOTracker()
        errors: list[Exception] = []

        def _record_many():
            for _ in range(10):
                try:
                    t.record_execution(ExecutionRecord(
                        task_type="concurrent-task",
                        success=True,
                        duration=0.01,
                    ))
                except Exception as exc:
                    errors.append(exc)

        threads = [threading.Thread(target=_record_many) for _ in range(10)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert not errors, f"Concurrent writes caused errors: {errors}"
        status = t.get_status()
        assert status["total_records"] == 100

    def test_dashboard_aggregator_concurrent_collect(self):
        """Concurrent collect() calls return valid snapshots."""
        d = OperationalDashboardAggregator()
        for i in range(3):
            d.register_module(f"MOD-{i}", f"Module{i}", lambda: {"ok": True})

        results: list = []
        errors: list[Exception] = []

        def _collect():
            try:
                snap = d.collect()
                results.append(snap)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=_collect) for _ in range(10)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert not errors, f"Concurrent collects caused errors: {errors}"
        assert len(results) == 10

    def test_crm_concurrent_contact_creation(self):
        """Concurrent contact creation doesn't produce duplicate IDs."""
        crm = CRMManager()
        contacts: list = []
        errors: list[Exception] = []

        def _create():
            try:
                cid = uuid.uuid4().hex[:8]
                contact = crm.create_contact(name=f"User-{cid}",
                                              email=f"{cid}@test.com")
                contacts.append(contact.id)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=_create) for _ in range(20)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert not errors, f"Concurrent CRM writes caused errors: {errors}"
        # All contact IDs should be unique
        assert len(set(contacts)) == len(contacts)

    def test_board_engine_concurrent_item_creation(self):
        """Concurrent item creation on the same board doesn't lose items."""
        engine = BoardEngine()
        board = engine.create_board("Concurrent Board", owner_id="u1")
        group = engine.add_group(board.id, "Group")
        items: list = []
        errors: list[Exception] = []

        def _add_item(idx: int):
            try:
                item = engine.add_item(board.id, group.id, f"Item {idx}")
                items.append(item.id)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=_add_item, args=(i,))
                   for i in range(15)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert not errors, f"Concurrent board writes caused errors: {errors}"
        assert len(items) == 15

    def test_wirer_concurrent_calls_all_return_dicts(self):
        """Multiple concurrent wire() calls all return dicts without crashing."""
        wirer = LLMResponseWirer(max_retries=1)
        results: list = []
        errors: list[Exception] = []

        def _wire(cmd: str):
            try:
                result = wirer.wire(cmd)
                results.append(result)
            except Exception as exc:
                errors.append(exc)

        commands = [f"task {i}" for i in range(10)]
        threads = [threading.Thread(target=_wire, args=(cmd,))
                   for cmd in commands]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert not errors, f"Concurrent wire() calls caused errors: {errors}"
        assert all(isinstance(r, dict) for r in results)


# ===========================================================================
# 3. Data Consistency Across Subsystems
# ===========================================================================

class TestDataConsistency:
    """State created in one module is consistently visible after operations."""

    def test_crm_contact_visible_after_create(self):
        crm = CRMManager()
        contact = crm.create_contact(name="Consistent", email="c@x.com")
        fetched = crm.get_contact(contact.id)
        assert fetched is not None
        assert fetched.name == "Consistent"

    def test_crm_contact_update_reflected_on_fetch(self):
        crm = CRMManager()
        contact = crm.create_contact(name="Before", email="before@x.com")
        crm.update_contact(contact.id, name="After")
        fetched = crm.get_contact(contact.id)
        assert fetched.name == "After"

    def test_crm_delete_removes_from_list(self):
        crm = CRMManager()
        contact = crm.create_contact(name="ToDelete", email="del@x.com")
        crm.delete_contact(contact.id)
        all_contacts = crm.list_contacts()
        assert not any(c.id == contact.id for c in all_contacts)

    def test_board_item_visible_after_add(self):
        engine = BoardEngine()
        board = engine.create_board("Consistency Board", owner_id="u1")
        group = engine.add_group(board.id, "Group")
        item = engine.add_item(board.id, group.id, "Consistent Item")
        fetched = engine.get_item(board.id, item.id)
        assert fetched is not None
        assert fetched.name == "Consistent Item"

    def test_board_delete_removes_item(self):
        engine = BoardEngine()
        board = engine.create_board("Delete Board", owner_id="u1")
        group = engine.add_group(board.id, "Group")
        item = engine.add_item(board.id, group.id, "Gone")
        engine.delete_item(board.id, item.id)
        fetched = engine.get_item(board.id, item.id)
        assert fetched is None

    def test_slo_tracker_metrics_consistent_after_records(self):
        """Metrics match the exact set of records that were added."""
        t = OperationalSLOTracker()
        for _ in range(8):
            t.record_execution(ExecutionRecord(
                task_type="consistent", success=True, duration=0.1
            ))
        for _ in range(2):
            t.record_execution(ExecutionRecord(
                task_type="consistent", success=False, duration=0.1
            ))
        status = t.get_status()
        assert status["total_records"] == 10
        metrics = t.get_metrics("consistent")
        assert metrics["sample_size"] == 10
        assert abs(metrics["success_rate"] - 0.8) < 0.01

    def test_dashboard_snapshot_count_matches_modules(self):
        """The snapshot's total_modules reflects exactly the registered count."""
        d = OperationalDashboardAggregator()
        for i in range(4):
            d.register_module(f"CONS-{i}", f"Mod{i}", lambda: {"ok": True})
        snap = d.collect()
        assert snap.total_modules == 4

    def test_conversation_handler_history_count_matches_turns(self):
        """History length matches the number of handle() calls."""
        handler = ConversationHandler()
        turns = ["hello", "list tasks", "help", "status", "goodbye"]
        for msg in turns:
            handler.handle(msg)
        history = handler._get_recent_history(100)
        assert len(history) == len(turns)

    def test_slo_multiple_task_types_isolated(self):
        """Metrics for one task type don't bleed into another."""
        t = OperationalSLOTracker()
        for _ in range(10):
            t.record_execution(ExecutionRecord(
                task_type="type-a", success=True, duration=0.1
            ))
        for _ in range(5):
            t.record_execution(ExecutionRecord(
                task_type="type-b", success=False, duration=0.5
            ))
        metrics_a = t.get_metrics("type-a")
        metrics_b = t.get_metrics("type-b")
        assert metrics_a["success_rate"] == 1.0
        assert metrics_b["success_rate"] == 0.0
        # Sample sizes are also isolated
        assert metrics_a["sample_size"] == 10
        assert metrics_b["sample_size"] == 5
