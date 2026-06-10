"""PCR-060j — requirement tracker regression suite."""
from unittest.mock import patch, MagicMock

import pytest

from src.pcr060_requirement_tracker import (
    Requirement,
    RequirementStatus,
    SolvedSet,
    BoundaryVerdict,
    extract_requirements,
    evaluate_solved,
    compute_boundary,
    solved_set_to_dict,
)


# ─────────────────────────────────────────────────────────────────────
# SolvedSet math
# ─────────────────────────────────────────────────────────────────────

class TestSolvedSet:
    def test_empty_ratio_is_zero(self):
        ss = SolvedSet(iteration=0, total_count=0)
        assert ss.solved_ratio == 0.0

    def test_all_solved_ratio_one(self):
        ss = SolvedSet(iteration=0, solved_count=4, total_count=4)
        assert ss.solved_ratio == 1.0

    def test_partial_counts_half(self):
        ss = SolvedSet(iteration=0, solved_count=2, partial_count=2, total_count=4)
        # (2 + 0.5*2) / 4 = 3/4 = 0.75
        assert ss.solved_ratio == 0.75

    def test_unaddressed_does_not_count(self):
        ss = SolvedSet(iteration=0, solved_count=1, unaddressed_count=3, total_count=4)
        assert ss.solved_ratio == 0.25

    def test_has_impossible_true(self):
        ss = SolvedSet(iteration=0, impossible_count=1, total_count=4)
        assert ss.has_impossible is True

    def test_has_impossible_false_when_zero(self):
        ss = SolvedSet(iteration=0, solved_count=4, total_count=4)
        assert ss.has_impossible is False


# ─────────────────────────────────────────────────────────────────────
# extract_requirements
# ─────────────────────────────────────────────────────────────────────

class TestExtract:
    def test_empty_prompt_returns_empty(self):
        assert extract_requirements("") == []
        assert extract_requirements("  ") == []
        assert extract_requirements("hi") == []  # too short

    def test_missing_api_key_returns_empty(self, monkeypatch):
        monkeypatch.delenv("MURPHY_FOUNDER_KEY", raising=False)
        assert extract_requirements("Build an accounting SaaS for CPAs in CA",
                                     api_key=None) == []

    def test_parses_llm_response(self):
        fake_response = {
            "reply": '''Here are the requirements:
[
  {"id":"req_001","text":"Targets CPAs","category":"domain",
   "evaluable_question":"Does the deliverable identify CPAs as users?"},
  {"id":"req_002","text":"California jurisdiction","category":"jurisdiction",
   "evaluable_question":"Does it address CA tax law?"}
]'''
        }
        with patch("urllib.request.urlopen") as mock_url:
            mock_resp = MagicMock()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = lambda *a: None
            mock_resp.read.return_value = __import__("json").dumps(fake_response).encode()
            mock_url.return_value = mock_resp

            reqs = extract_requirements(
                "Build an accounting SaaS for CPAs in California",
                api_key="test-key",
            )
            assert len(reqs) == 2
            assert reqs[0].id == "req_001"
            assert reqs[0].category == "domain"
            assert "CPAs" in reqs[0].text

    def test_handles_malformed_json_gracefully(self):
        with patch("urllib.request.urlopen") as mock_url:
            mock_resp = MagicMock()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = lambda *a: None
            mock_resp.read.return_value = b'{"reply": "no json here, sorry"}'
            mock_url.return_value = mock_resp

            reqs = extract_requirements("Build something", api_key="test-key")
            assert reqs == []

    def test_handles_network_failure_gracefully(self):
        with patch("urllib.request.urlopen", side_effect=Exception("network down")):
            reqs = extract_requirements("Build something", api_key="test-key")
            assert reqs == []

    def test_max_requirements_enforced(self):
        # Build a fake response with 20 requirements; should cap at max_requirements
        items = [
            {"id": f"req_{i:03d}", "text": f"req {i}", "category": "functional",
             "evaluable_question": f"is {i} addressed?"}
            for i in range(20)
        ]
        fake_response = {"reply": __import__("json").dumps(items)}
        with patch("urllib.request.urlopen") as mock_url:
            mock_resp = MagicMock()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = lambda *a: None
            mock_resp.read.return_value = __import__("json").dumps(fake_response).encode()
            mock_url.return_value = mock_resp

            reqs = extract_requirements("Build something",
                                         api_key="test-key", max_requirements=5)
            assert len(reqs) == 5

    def test_filters_incomplete_items(self):
        items = [
            {"id": "req_001", "text": "ok", "category": "functional",
             "evaluable_question": "is it ok?"},
            {"id": "req_002", "text": "", "category": "functional",
             "evaluable_question": "incomplete?"},  # empty text → filtered
            {"id": "req_003", "text": "valid", "category": "functional",
             "evaluable_question": ""},  # empty question → filtered
        ]
        fake_response = {"reply": __import__("json").dumps(items)}
        with patch("urllib.request.urlopen") as mock_url:
            mock_resp = MagicMock()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = lambda *a: None
            mock_resp.read.return_value = __import__("json").dumps(fake_response).encode()
            mock_url.return_value = mock_resp

            reqs = extract_requirements("Build something", api_key="test-key")
            assert len(reqs) == 1
            assert reqs[0].id == "req_001"


# ─────────────────────────────────────────────────────────────────────
# evaluate_solved
# ─────────────────────────────────────────────────────────────────────

class TestEvaluate:
    def test_empty_requirements_returns_zero_total(self):
        ss = evaluate_solved({"foo": "bar"}, [], iteration=0)
        assert ss.total_count == 0
        assert ss.solved_ratio == 0.0

    def test_missing_api_key_returns_unscored(self, monkeypatch):
        monkeypatch.delenv("MURPHY_FOUNDER_KEY", raising=False)
        reqs = [Requirement(id="req_001", text="x", category="functional",
                             evaluable_question="?")]
        ss = evaluate_solved({"foo": "bar"}, reqs, api_key=None, iteration=0)
        assert ss.total_count == 1
        assert ss.solved_count == 0

    def test_parses_llm_verdicts(self):
        reqs = [
            Requirement(id="req_001", text="r1", category="functional",
                         evaluable_question="?"),
            Requirement(id="req_002", text="r2", category="functional",
                         evaluable_question="?"),
        ]
        fake_response = {
            "reply": '''[
  {"requirement_id":"req_001","status":"addressed","evidence":"section 2","confidence":"high"},
  {"requirement_id":"req_002","status":"partial","evidence":"mentioned briefly","confidence":"medium"}
]'''
        }
        with patch("urllib.request.urlopen") as mock_url:
            mock_resp = MagicMock()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = lambda *a: None
            mock_resp.read.return_value = __import__("json").dumps(fake_response).encode()
            mock_url.return_value = mock_resp

            ss = evaluate_solved({"deliverable": "stuff"}, reqs, api_key="test-key",
                                  iteration=0)
            assert ss.total_count == 2
            assert ss.solved_count == 1
            assert ss.partial_count == 1
            assert ss.solved_ratio == 0.75  # (1 + 0.5*1) / 2

    def test_carries_forward_addressed_requirements(self):
        """Z: sampled — addressed reqs from prior iter aren't re-evaluated."""
        reqs = [
            Requirement(id="req_001", text="r1", category="functional",
                         evaluable_question="?"),
            Requirement(id="req_002", text="r2", category="functional",
                         evaluable_question="?"),
        ]
        prior = SolvedSet(
            iteration=0,
            statuses=[
                RequirementStatus(requirement_id="req_001", status="addressed",
                                   evidence="prior win", confidence="high"),
                RequirementStatus(requirement_id="req_002", status="unaddressed",
                                   evidence="", confidence="medium"),
            ],
            solved_count=1, unaddressed_count=1, total_count=2,
        )
        # Mock evaluator returns verdict only for req_002 (the one being re-evaluated)
        fake_response = {
            "reply": '''[
  {"requirement_id":"req_002","status":"addressed","evidence":"now done","confidence":"high"}
]'''
        }
        with patch("urllib.request.urlopen") as mock_url:
            mock_resp = MagicMock()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = lambda *a: None
            mock_resp.read.return_value = __import__("json").dumps(fake_response).encode()
            mock_url.return_value = mock_resp

            ss = evaluate_solved({"deliverable": "improved"}, reqs,
                                  iteration=1, prior=prior, api_key="test-key")
            # Both should now be addressed (req_001 carried, req_002 re-evaluated)
            assert ss.solved_count == 2
            assert ss.solved_ratio == 1.0

    def test_impossible_status_tracked(self):
        reqs = [Requirement(id="req_001", text="quantum compliance",
                              category="constraint",
                              evaluable_question="?")]
        fake_response = {
            "reply": '''[
  {"requirement_id":"req_001","status":"impossible","evidence":"no such thing",
   "confidence":"high"}
]'''
        }
        with patch("urllib.request.urlopen") as mock_url:
            mock_resp = MagicMock()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = lambda *a: None
            mock_resp.read.return_value = __import__("json").dumps(fake_response).encode()
            mock_url.return_value = mock_resp

            ss = evaluate_solved({"x": "y"}, reqs, api_key="test-key", iteration=0)
            assert ss.has_impossible is True
            assert ss.impossible_count == 1

    def test_network_failure_marks_unaddressed(self):
        reqs = [Requirement(id="req_001", text="r1", category="functional",
                             evaluable_question="?")]
        with patch("urllib.request.urlopen", side_effect=Exception("down")):
            ss = evaluate_solved({"x": "y"}, reqs, api_key="test-key", iteration=0)
            assert ss.total_count == 1
            assert ss.unaddressed_count == 1
            assert ss.statuses[0].confidence == "low"


# ─────────────────────────────────────────────────────────────────────
# compute_boundary
# ─────────────────────────────────────────────────────────────────────

class TestBoundary:
    def test_success_when_gate_and_polish_both_pass(self):
        ss = SolvedSet(iteration=2, solved_count=9, total_count=10)  # 0.9
        v = compute_boundary(ss, delta=0.10)
        assert v.state == "success"

    def test_polish_when_gate_passes_but_delta_high(self):
        ss = SolvedSet(iteration=2, solved_count=9, total_count=10)
        v = compute_boundary(ss, delta=0.40)
        assert v.state == "polish"

    def test_drilling_when_gate_not_met(self):
        ss = SolvedSet(iteration=1, solved_count=3, total_count=10)
        v = compute_boundary(ss, delta=0.50)
        assert v.state == "drilling"

    def test_failure_impossible_short_circuits(self):
        ss = SolvedSet(iteration=1, solved_count=8, impossible_count=1,
                        total_count=10)
        v = compute_boundary(ss, delta=0.10)
        # Even with high solved ratio + low delta, impossible wins
        assert v.state == "failure_impossible"
        assert v.has_impossible is True

    def test_failure_stalled_after_streak(self):
        ss = SolvedSet(iteration=3, solved_count=4, total_count=10)
        v = compute_boundary(
            ss, delta=0.40,
            d_solved_dt=0.005, d_delta_dt=0.005,
            flatline_streak=3, max_flatline_streak=2,
        )
        assert v.state == "failure_stalled"

    def test_not_stalled_when_only_one_signal_flat(self):
        ss = SolvedSet(iteration=3, solved_count=4, total_count=10)
        # delta still moving but solved flat — still drilling
        v = compute_boundary(
            ss, delta=0.40,
            d_solved_dt=0.005, d_delta_dt=0.10,
            flatline_streak=3, max_flatline_streak=2,
        )
        assert v.state == "drilling"

    def test_fallback_to_delta_only_when_no_solved_set(self):
        v = compute_boundary(None, delta=0.10, delta_threshold=0.20)
        assert v.state == "success"

        v = compute_boundary(None, delta=0.40, delta_threshold=0.20)
        assert v.state == "drilling"


# ─────────────────────────────────────────────────────────────────────
# Serialization
# ─────────────────────────────────────────────────────────────────────

class TestSerialization:
    def test_solved_set_to_dict_roundtrip(self):
        ss = SolvedSet(
            iteration=2,
            statuses=[
                RequirementStatus(requirement_id="req_001", status="addressed",
                                   evidence="works", confidence="high"),
            ],
            solved_count=1, total_count=2,
        )
        d = solved_set_to_dict(ss)
        assert d["iteration"] == 2
        assert d["solved_count"] == 1
        assert d["solved_ratio"] == 0.5
        assert len(d["statuses"]) == 1
        assert d["statuses"][0]["requirement_id"] == "req_001"
