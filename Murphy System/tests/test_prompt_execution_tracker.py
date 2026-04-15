"""
Tests for prompt_execution_tracker module.

Design Label: PROMPT-TRACKER-TEST-001

Covers:
  - mark_prompt_complete() basic happy path
  - mark_prompt_complete() with doc_updates harvesting
  - mark_prompt_complete() raises on empty prompt_id
  - record_citl_result() pass and fail
  - get_execution_status() structure and completeness
  - get_pending_doc_updates() sorted output
  - add_doc_update() and resolve_doc_update()
  - reset() clears all state
  - Thread safety: concurrent mark_prompt_complete calls

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import threading
from typing import List

import pytest

from src.prompt_execution_tracker import PromptExecutionTracker


# ---------------------------------------------------------------------------
# Fixture: fresh tracker with reset state before each test
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_tracker():
    """Reset module-level tracker state before each test."""
    t = PromptExecutionTracker()
    t.reset()
    yield t
    t.reset()


# ---------------------------------------------------------------------------
# mark_prompt_complete
# ---------------------------------------------------------------------------


class TestMarkPromptComplete:
    def test_basic_happy_path(self, _clean_tracker):
        t = _clean_tracker
        record = t.mark_prompt_complete("00_PRIORITY_0_SYSTEM_BOOT")
        assert record.prompt_id == "00_PRIORITY_0_SYSTEM_BOOT"
        assert record.completed_at
        assert record.results == {}

    def test_stores_results(self, _clean_tracker):
        t = _clean_tracker
        record = t.mark_prompt_complete(
            "01_SCAN_AND_AUDIT",
            results={"modules_audited": 42, "p0_count": 1},
        )
        assert record.results["modules_audited"] == 42
        assert record.results["p0_count"] == 1

    def test_harvests_doc_updates_from_results(self, _clean_tracker):
        t = _clean_tracker
        t.mark_prompt_complete(
            "03_WIRE_REVENUE_MODULES",
            results={"doc_updates": ["API_ROUTES.md", "CHANGELOG.md"]},
        )
        pending = t.get_pending_doc_updates()
        assert "API_ROUTES.md" in pending
        assert "CHANGELOG.md" in pending

    def test_raises_on_empty_prompt_id(self, _clean_tracker):
        t = _clean_tracker
        with pytest.raises(ValueError):
            t.mark_prompt_complete("")

    def test_overwrites_existing_record(self, _clean_tracker):
        t = _clean_tracker
        t.mark_prompt_complete("00_PRIORITY_0_SYSTEM_BOOT", results={"boot_healthy": False})
        t.mark_prompt_complete("00_PRIORITY_0_SYSTEM_BOOT", results={"boot_healthy": True})
        status = t.get_execution_status()
        record = status["prompts"]["00_PRIORITY_0_SYSTEM_BOOT"]
        assert record["results"]["boot_healthy"] is True

    def test_non_list_doc_updates_ignored(self, _clean_tracker):
        """If doc_updates is not a list, no error should be raised."""
        t = _clean_tracker
        t.mark_prompt_complete(
            "02_PRIORITIZE_RED_LINE",
            results={"doc_updates": "CHANGELOG.md"},  # string, not list
        )
        # Should not crash; the string value is simply ignored
        # (only list values are harvested)
        status = t.get_execution_status()
        assert status["completed"] == 1


# ---------------------------------------------------------------------------
# record_citl_result
# ---------------------------------------------------------------------------


class TestRecordCitlResult:
    def test_records_pass(self, _clean_tracker):
        t = _clean_tracker
        t.record_citl_result("sales_automation", level=1, passed=True)
        status = t.get_execution_status()
        summary = status["citl_summary"]["sales_automation"]
        assert summary["pass"] == 1
        assert summary["fail"] == 0

    def test_records_fail(self, _clean_tracker):
        t = _clean_tracker
        t.record_citl_result(
            "mfgc_core",
            level=2,
            passed=False,
            failure_description="Quality score 0.72 < 0.80",
        )
        status = t.get_execution_status()
        summary = status["citl_summary"]["mfgc_core"]
        assert summary["pass"] == 0
        assert summary["fail"] == 1

    def test_accumulates_multiple_results(self, _clean_tracker):
        t = _clean_tracker
        t.record_citl_result("inference_gate_engine", level=1, passed=True)
        t.record_citl_result("inference_gate_engine", level=2, passed=True)
        t.record_citl_result("inference_gate_engine", level=2, passed=False)
        status = t.get_execution_status()
        summary = status["citl_summary"]["inference_gate_engine"]
        assert summary["pass"] == 2
        assert summary["fail"] == 1


# ---------------------------------------------------------------------------
# get_execution_status
# ---------------------------------------------------------------------------


class TestGetExecutionStatus:
    def test_empty_state(self, _clean_tracker):
        t = _clean_tracker
        status = t.get_execution_status()
        assert status["total_prompts"] == len(t.PROMPT_IDS)
        assert status["completed"] == 0
        assert len(status["pending"]) == len(t.PROMPT_IDS)
        assert status["prompts"] == {}
        assert status["citl_summary"] == {}

    def test_completed_count_increments(self, _clean_tracker):
        t = _clean_tracker
        t.mark_prompt_complete("00_PRIORITY_0_SYSTEM_BOOT")
        t.mark_prompt_complete("01_SCAN_AND_AUDIT")
        status = t.get_execution_status()
        assert status["completed"] == 2

    def test_pending_excludes_completed(self, _clean_tracker):
        t = _clean_tracker
        t.mark_prompt_complete("00_PRIORITY_0_SYSTEM_BOOT")
        status = t.get_execution_status()
        assert "00_PRIORITY_0_SYSTEM_BOOT" not in status["pending"]
        assert "01_SCAN_AND_AUDIT" in status["pending"]

    def test_returns_dict_with_required_keys(self, _clean_tracker):
        t = _clean_tracker
        status = t.get_execution_status()
        for key in ("total_prompts", "completed", "pending", "prompts", "citl_summary"):
            assert key in status, f"Missing key: {key}"

    def test_prompt_record_serialised_correctly(self, _clean_tracker):
        t = _clean_tracker
        t.mark_prompt_complete("05_WIRE_QA_AND_GOVERNANCE", results={"quality_floor_active": True})
        status = t.get_execution_status()
        record = status["prompts"]["05_WIRE_QA_AND_GOVERNANCE"]
        assert record["prompt_id"] == "05_WIRE_QA_AND_GOVERNANCE"
        assert "completed_at" in record
        assert record["results"]["quality_floor_active"] is True


# ---------------------------------------------------------------------------
# get_pending_doc_updates
# ---------------------------------------------------------------------------


class TestGetPendingDocUpdates:
    def test_empty_initially(self, _clean_tracker):
        t = _clean_tracker
        assert t.get_pending_doc_updates() == []

    def test_sorted_output(self, _clean_tracker):
        t = _clean_tracker
        t.mark_prompt_complete(
            "06_WIRE_ROI_CALENDAR",
            results={"doc_updates": ["USER_MANUAL.md", "API_ROUTES.md", "CHANGELOG.md"]},
        )
        pending = t.get_pending_doc_updates()
        assert pending == sorted(pending)

    def test_deduplicates(self, _clean_tracker):
        t = _clean_tracker
        t.mark_prompt_complete("03_WIRE_REVENUE_MODULES", results={"doc_updates": ["CHANGELOG.md"]})
        t.mark_prompt_complete("04_WIRE_ONBOARDING_MODULES", results={"doc_updates": ["CHANGELOG.md"]})
        pending = t.get_pending_doc_updates()
        assert pending.count("CHANGELOG.md") == 1


# ---------------------------------------------------------------------------
# add_doc_update / resolve_doc_update
# ---------------------------------------------------------------------------


class TestAddResolveDocUpdate:
    def test_add_doc_update(self, _clean_tracker):
        t = _clean_tracker
        t.add_doc_update("ROADMAP.md")
        assert "ROADMAP.md" in t.get_pending_doc_updates()

    def test_add_empty_string_ignored(self, _clean_tracker):
        t = _clean_tracker
        t.add_doc_update("")
        assert t.get_pending_doc_updates() == []

    def test_resolve_removes_entry(self, _clean_tracker):
        t = _clean_tracker
        t.add_doc_update("STATUS.md")
        removed = t.resolve_doc_update("STATUS.md")
        assert removed is True
        assert "STATUS.md" not in t.get_pending_doc_updates()

    def test_resolve_missing_returns_false(self, _clean_tracker):
        t = _clean_tracker
        result = t.resolve_doc_update("DOES_NOT_EXIST.md")
        assert result is False

    def test_resolve_is_idempotent(self, _clean_tracker):
        t = _clean_tracker
        t.add_doc_update("ARCHITECTURE_MAP.md")
        t.resolve_doc_update("ARCHITECTURE_MAP.md")
        result = t.resolve_doc_update("ARCHITECTURE_MAP.md")
        assert result is False


# ---------------------------------------------------------------------------
# reset
# ---------------------------------------------------------------------------


class TestReset:
    def test_reset_clears_records(self, _clean_tracker):
        t = _clean_tracker
        t.mark_prompt_complete("00_PRIORITY_0_SYSTEM_BOOT")
        t.reset()
        status = t.get_execution_status()
        assert status["completed"] == 0

    def test_reset_clears_citl_results(self, _clean_tracker):
        t = _clean_tracker
        t.record_citl_result("sales_automation", level=1, passed=True)
        t.reset()
        status = t.get_execution_status()
        assert status["citl_summary"] == {}

    def test_reset_clears_pending_doc_updates(self, _clean_tracker):
        t = _clean_tracker
        t.add_doc_update("CHANGELOG.md")
        t.reset()
        assert t.get_pending_doc_updates() == []


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------


class TestThreadSafety:
    def test_concurrent_mark_complete(self, _clean_tracker):
        """Multiple threads marking different prompts must not corrupt state."""
        t = _clean_tracker
        errors: List[Exception] = []

        def _worker(prompt_id: str) -> None:
            try:
                t.mark_prompt_complete(prompt_id, results={"thread": True})
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=_worker, args=(pid,))
            for pid in t.PROMPT_IDS
        ]
        for th in threads:
            th.start()
        for th in threads:
            th.join()

        assert errors == [], f"Thread errors: {errors}"
        status = t.get_execution_status()
        assert status["completed"] == len(t.PROMPT_IDS)

    def test_concurrent_add_doc_update(self, _clean_tracker):
        """Multiple threads adding doc updates must not corrupt the set."""
        t = _clean_tracker
        errors: List[Exception] = []
        docs = ["A.md", "B.md", "C.md", "D.md", "E.md"]

        def _worker(doc: str) -> None:
            try:
                for _ in range(10):
                    t.add_doc_update(doc)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=_worker, args=(d,)) for d in docs]
        for th in threads:
            th.start()
        for th in threads:
            th.join()

        assert errors == [], f"Thread errors: {errors}"
        pending = t.get_pending_doc_updates()
        assert set(pending) == set(docs)


# ---------------------------------------------------------------------------
# PromptRecord.to_dict
# ---------------------------------------------------------------------------


class TestPromptRecord:
    def test_to_dict_contains_all_fields(self, _clean_tracker):
        t = _clean_tracker
        record = t.mark_prompt_complete(
            "10_REPORT_AND_ITERATE",
            results={"ar_positive": True},
        )
        d = record.to_dict()
        assert d["prompt_id"] == "10_REPORT_AND_ITERATE"
        assert "completed_at" in d
        assert d["results"]["ar_positive"] is True
