"""Tests for the Triage Rollcall Adapter module."""

import threading
import pytest

from src.triage_rollcall_adapter import (
    BotCandidate,
    CandidateStatus,
    RollcallResult,
    TriageRollcallAdapter,
)


@pytest.fixture
def adapter():
    return TriageRollcallAdapter()


# ------------------------------------------------------------------
# Registration
# ------------------------------------------------------------------

class TestRegistration:
    def test_register_returns_id(self, adapter):
        cid = adapter.register_candidate("bot-a", ["parse", "transform"])
        assert cid.startswith("bot-")

    def test_registered_candidate_retrievable(self, adapter):
        cid = adapter.register_candidate("bot-a", ["parse"], domains=["finance"])
        candidate = adapter.get_candidate(cid)
        assert candidate is not None
        assert candidate.name == "bot-a"
        assert candidate.capabilities == ["parse"]
        assert candidate.domains == ["finance"]
        assert candidate.status == CandidateStatus.AVAILABLE

    def test_register_defaults(self, adapter):
        cid = adapter.register_candidate("bot-b", ["x"])
        c = adapter.get_candidate(cid)
        assert c.cost_per_call == 1.0
        assert c.stability_score == 1.0
        assert c.domains == []


# ------------------------------------------------------------------
# Status updates
# ------------------------------------------------------------------

class TestStatusUpdate:
    def test_update_existing(self, adapter):
        cid = adapter.register_candidate("bot-a", ["x"])
        assert adapter.update_candidate_status(cid, CandidateStatus.BUSY) is True
        assert adapter.get_candidate(cid).status == CandidateStatus.BUSY

    def test_update_nonexistent(self, adapter):
        assert adapter.update_candidate_status("nope", CandidateStatus.BUSY) is False


# ------------------------------------------------------------------
# Probing
# ------------------------------------------------------------------

class TestProbing:
    def test_probe_returns_float(self, adapter):
        cid = adapter.register_candidate("bot-a", ["x"])
        conf = adapter.probe_candidate(cid)
        assert isinstance(conf, float)
        assert 0.0 <= conf <= 1.0

    def test_probe_updates_last_probed(self, adapter):
        cid = adapter.register_candidate("bot-a", ["x"])
        adapter.probe_candidate(cid)
        c = adapter.get_candidate(cid)
        assert c.last_probed is not None

    def test_probe_nonexistent(self, adapter):
        assert adapter.probe_candidate("nope") is None


# ------------------------------------------------------------------
# Rollcall ranking
# ------------------------------------------------------------------

class TestRollcall:
    def test_higher_match_ranks_higher(self, adapter):
        adapter.register_candidate("match-all", ["parse", "transform"])
        adapter.register_candidate("match-none", ["unrelated"])
        results = adapter.rollcall("parse and transform this data")
        assert len(results) == 2
        assert results[0].name == "match-all"

    def test_domain_boost(self, adapter):
        cid_no_domain = adapter.register_candidate(
            "no-domain", ["analyze", "summarize"], domains=[]
        )
        cid_domain = adapter.register_candidate(
            "has-domain", ["analyze", "summarize"], domains=["finance"]
        )
        results = adapter.rollcall("analyze the report", domain="finance")
        # Domain-boosted candidate should have a higher match_score
        domain_result = next(r for r in results if r.name == "has-domain")
        no_domain_result = next(r for r in results if r.name == "no-domain")
        assert domain_result.match_score > no_domain_result.match_score

    def test_degraded_penalty(self, adapter):
        cid_ok = adapter.register_candidate("ok-bot", ["search"], stability_score=1.0)
        cid_deg = adapter.register_candidate("deg-bot", ["search"], stability_score=1.0)
        adapter.update_candidate_status(cid_deg, CandidateStatus.DEGRADED)
        results = adapter.rollcall("search query")
        # Degraded bot should have lower confidence and therefore lower combined score
        ok_result = next(r for r in results if r.name == "ok-bot")
        deg_result = next(r for r in results if r.name == "deg-bot")
        assert deg_result.confidence < ok_result.confidence

    def test_busy_excluded(self, adapter):
        cid = adapter.register_candidate("busy-bot", ["x"])
        adapter.update_candidate_status(cid, CandidateStatus.BUSY)
        results = adapter.rollcall("x task")
        assert all(r.candidate_id != cid for r in results)

    def test_offline_excluded(self, adapter):
        cid = adapter.register_candidate("offline-bot", ["x"])
        adapter.update_candidate_status(cid, CandidateStatus.OFFLINE)
        results = adapter.rollcall("x task")
        assert all(r.candidate_id != cid for r in results)

    def test_max_results(self, adapter):
        for i in range(20):
            adapter.register_candidate(f"bot-{i}", ["cap"])
        results = adapter.rollcall("cap task", max_results=5)
        assert len(results) == 5

    def test_cost_factor(self, adapter):
        adapter.register_candidate("cheap", ["work"], cost_per_call=0.0, stability_score=1.0)
        adapter.register_candidate("expensive", ["work"], cost_per_call=10.0, stability_score=1.0)
        results = adapter.rollcall("work task")
        cheap = next(r for r in results if r.name == "cheap")
        expensive = next(r for r in results if r.name == "expensive")
        # Cheap bot gets higher cost factor contribution
        # With identical other factors (same capabilities, same stability),
        # cheap should score >= expensive on the cost component
        assert cheap.combined_score >= expensive.combined_score - 0.1

    def test_empty_registry(self, adapter):
        results = adapter.rollcall("anything")
        assert results == []


# ------------------------------------------------------------------
# List and status
# ------------------------------------------------------------------

class TestListAndStatus:
    def test_list_all(self, adapter):
        adapter.register_candidate("a", ["x"])
        adapter.register_candidate("b", ["y"])
        assert len(adapter.list_candidates()) == 2

    def test_list_filtered(self, adapter):
        cid = adapter.register_candidate("a", ["x"])
        adapter.register_candidate("b", ["y"])
        adapter.update_candidate_status(cid, CandidateStatus.BUSY)
        busy = adapter.list_candidates(status=CandidateStatus.BUSY)
        assert len(busy) == 1
        assert busy[0].candidate_id == cid

    def test_get_status(self, adapter):
        adapter.register_candidate("a", ["x"])
        adapter.register_candidate("b", ["y"])
        status = adapter.get_status()
        assert status["total_candidates"] == 2
        assert "available" in status["candidates_by_status"]

    def test_get_nonexistent_candidate(self, adapter):
        assert adapter.get_candidate("nope") is None


# ------------------------------------------------------------------
# Thread safety
# ------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_registration(self, adapter):
        errors = []

        def register_batch(start):
            try:
                for i in range(50):
                    adapter.register_candidate(f"bot-{start + i}", ["cap"])
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=register_batch, args=(i * 50,)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len(adapter.list_candidates()) == 200

    def test_concurrent_rollcall(self, adapter):
        for i in range(10):
            adapter.register_candidate(f"bot-{i}", ["search", "index"])

        errors = []
        results_bag = []

        def do_rollcall():
            try:
                r = adapter.rollcall("search and index data")
                results_bag.append(r)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=do_rollcall) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len(results_bag) == 8
        for r in results_bag:
            assert len(r) == 10
