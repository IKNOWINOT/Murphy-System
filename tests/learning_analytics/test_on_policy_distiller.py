"""
Tests for On-Policy Distiller
==============================
Comprehensive test suite verifying all commissioning questions:

1. Does the module do what it was designed to do?
2. What conditions are possible?
3. Does the test profile reflect the full range of capabilities?
4. Expected vs actual results at all operation points.
5. Hardening: bounded collections, thread safety, input validation.

Run:
    PYTHONPATH="Murphy System/src:Murphy System:src:." \
        pytest "Murphy System/tests/learning_analytics/test_on_policy_distiller.py" -v
"""

import json
import threading
import unittest
from dataclasses import dataclass
from typing import Optional
from unittest.mock import MagicMock, patch

from on_policy_distiller import (
    DimensionScore,
    DistillationEpisode,
    DistillationPhase,
    FeedbackBuffer,
    FeedbackQuality,
    OnPolicyDistiller,
    PolicySnapshot,
    StudentPolicyTracker,
    TeacherFeedback,
    _DIMENSION_WEIGHTS,
    _parse_teacher_response,
    create_on_policy_distiller,
)


# ---------------------------------------------------------------------------
# Mock LLM provider
# ---------------------------------------------------------------------------

@dataclass
class _MockCompletion:
    content: str
    model: str
    provider: str = "mock"
    success: bool = True


class _MockLLMProvider:
    """Mock provider that returns predictable responses for student/teacher."""

    def __init__(
        self,
        student_response: str = "This is a student response with enough content to pass.",
        teacher_response: Optional[str] = None,
        student_error: bool = False,
        teacher_error: bool = False,
    ):
        self.student_response = student_response
        self.teacher_response = teacher_response or json.dumps({
            "correctness": {"score": 0.8, "rationale": "Mostly correct"},
            "completeness": {"score": 0.7, "rationale": "Covers main points"},
            "coherence": {"score": 0.9, "rationale": "Well structured"},
            "specificity": {"score": 0.6, "rationale": "Could be more specific"},
            "safety": {"score": 1.0, "rationale": "No issues"},
        })
        self.student_error = student_error
        self.teacher_error = teacher_error
        self.call_count = 0

    def complete(self, prompt: str, model_hint: str = "chat") -> _MockCompletion:
        self.call_count += 1
        if model_hint == "fast" and self.student_error:
            raise RuntimeError("Student LLM timeout")
        if model_hint == "chat" and self.teacher_error:
            raise RuntimeError("Teacher LLM timeout")
        if model_hint == "fast":
            return _MockCompletion(
                content=self.student_response, model="mock-8b"
            )
        return _MockCompletion(
            content=self.teacher_response, model="mock-70b"
        )


# ===================================================================
# Test: FeedbackQuality classification
# ===================================================================

class TestFeedbackQuality(unittest.TestCase):
    """Condition: score thresholds map correctly to quality levels."""

    def test_excellent(self):
        self.assertEqual(FeedbackQuality.from_score(0.90), FeedbackQuality.EXCELLENT)

    def test_good(self):
        self.assertEqual(FeedbackQuality.from_score(0.75), FeedbackQuality.GOOD)

    def test_fair(self):
        self.assertEqual(FeedbackQuality.from_score(0.55), FeedbackQuality.FAIR)

    def test_poor(self):
        self.assertEqual(FeedbackQuality.from_score(0.35), FeedbackQuality.POOR)

    def test_failing(self):
        self.assertEqual(FeedbackQuality.from_score(0.10), FeedbackQuality.FAILING)

    def test_boundary_excellent(self):
        self.assertEqual(FeedbackQuality.from_score(0.85), FeedbackQuality.EXCELLENT)

    def test_boundary_good(self):
        self.assertEqual(FeedbackQuality.from_score(0.70), FeedbackQuality.GOOD)

    def test_boundary_fair(self):
        self.assertEqual(FeedbackQuality.from_score(0.50), FeedbackQuality.FAIR)

    def test_boundary_poor(self):
        self.assertEqual(FeedbackQuality.from_score(0.30), FeedbackQuality.POOR)

    def test_zero(self):
        self.assertEqual(FeedbackQuality.from_score(0.0), FeedbackQuality.FAILING)

    def test_one(self):
        self.assertEqual(FeedbackQuality.from_score(1.0), FeedbackQuality.EXCELLENT)


# ===================================================================
# Test: DimensionScore
# ===================================================================

class TestDimensionScore(unittest.TestCase):
    """Expected: weighted_score = score * weight."""

    def test_weighted_score(self):
        ds = DimensionScore(name="correctness", score=0.8, rationale="ok", weight=0.3)
        self.assertAlmostEqual(ds.weighted_score(), 0.24, places=5)

    def test_zero_weight(self):
        ds = DimensionScore(name="x", score=1.0, rationale="", weight=0.0)
        self.assertAlmostEqual(ds.weighted_score(), 0.0)

    def test_full_marks(self):
        ds = DimensionScore(name="x", score=1.0, rationale="", weight=1.0)
        self.assertAlmostEqual(ds.weighted_score(), 1.0)


# ===================================================================
# Test: _parse_teacher_response
# ===================================================================

class TestParseTeacherResponse(unittest.TestCase):
    """Condition: teacher may return clean JSON, fenced JSON, or garbage."""

    def test_valid_json(self):
        raw = json.dumps({
            "correctness": {"score": 0.9, "rationale": "Good"},
            "completeness": {"score": 0.8, "rationale": "OK"},
            "coherence": {"score": 0.7, "rationale": "Decent"},
            "specificity": {"score": 0.6, "rationale": "Vague"},
            "safety": {"score": 1.0, "rationale": "Safe"},
        })
        result = _parse_teacher_response(raw)
        self.assertEqual(len(result), 5)
        self.assertAlmostEqual(result["correctness"]["score"], 0.9)

    def test_markdown_fenced_json(self):
        raw = '```json\n{"correctness": {"score": 0.9, "rationale": "ok"}, "completeness": {"score": 0.8, "rationale": "ok"}, "coherence": {"score": 0.7, "rationale": "ok"}, "specificity": {"score": 0.6, "rationale": "ok"}, "safety": {"score": 1.0, "rationale": "ok"}}\n```'
        result = _parse_teacher_response(raw)
        self.assertEqual(len(result), 5)
        self.assertAlmostEqual(result["correctness"]["score"], 0.9)

    def test_trailing_commas(self):
        raw = '{"correctness": {"score": 0.9, "rationale": "ok",}, "completeness": {"score": 0.8, "rationale": "ok",}, "coherence": {"score": 0.7, "rationale": "ok",}, "specificity": {"score": 0.6, "rationale": "ok",}, "safety": {"score": 1.0, "rationale": "ok",},}'
        result = _parse_teacher_response(raw)
        self.assertEqual(len(result), 5)

    def test_garbage_input(self):
        result = _parse_teacher_response("this is not json at all!")
        self.assertEqual(result, {})

    def test_empty_input(self):
        result = _parse_teacher_response("")
        self.assertEqual(result, {})

    def test_missing_dimensions(self):
        """Missing dimensions should get default score 0.5."""
        raw = json.dumps({"correctness": {"score": 0.9, "rationale": "ok"}})
        result = _parse_teacher_response(raw)
        self.assertEqual(len(result), 5)
        self.assertAlmostEqual(result["completeness"]["score"], 0.5)

    def test_score_clamped_high(self):
        raw = json.dumps({"correctness": {"score": 5.0, "rationale": "too high"},
                          "completeness": {"score": 0.5, "rationale": ""},
                          "coherence": {"score": 0.5, "rationale": ""},
                          "specificity": {"score": 0.5, "rationale": ""},
                          "safety": {"score": 0.5, "rationale": ""}})
        result = _parse_teacher_response(raw)
        self.assertAlmostEqual(result["correctness"]["score"], 1.0)

    def test_score_clamped_low(self):
        raw = json.dumps({"correctness": {"score": -1.0, "rationale": "too low"},
                          "completeness": {"score": 0.5, "rationale": ""},
                          "coherence": {"score": 0.5, "rationale": ""},
                          "specificity": {"score": 0.5, "rationale": ""},
                          "safety": {"score": 0.5, "rationale": ""}})
        result = _parse_teacher_response(raw)
        self.assertAlmostEqual(result["correctness"]["score"], 0.0)

    def test_non_numeric_score_defaults(self):
        raw = json.dumps({"correctness": {"score": "bad", "rationale": ""},
                          "completeness": {"score": 0.5, "rationale": ""},
                          "coherence": {"score": 0.5, "rationale": ""},
                          "specificity": {"score": 0.5, "rationale": ""},
                          "safety": {"score": 0.5, "rationale": ""}})
        result = _parse_teacher_response(raw)
        self.assertAlmostEqual(result["correctness"]["score"], 0.5)

    def test_array_input(self):
        result = _parse_teacher_response("[1, 2, 3]")
        self.assertEqual(result, {})

    def test_rationale_truncated(self):
        """Rationale should be truncated to 500 chars."""
        long_rat = "x" * 1000
        raw = json.dumps({"correctness": {"score": 0.9, "rationale": long_rat},
                          "completeness": {"score": 0.5, "rationale": ""},
                          "coherence": {"score": 0.5, "rationale": ""},
                          "specificity": {"score": 0.5, "rationale": ""},
                          "safety": {"score": 0.5, "rationale": ""}})
        result = _parse_teacher_response(raw)
        self.assertLessEqual(len(result["correctness"]["rationale"]), 500)


# ===================================================================
# Test: FeedbackBuffer
# ===================================================================

class TestFeedbackBuffer(unittest.TestCase):
    """Conditions: normal add/sample, overflow eviction, thread safety."""

    def _make_feedback(self, score: float = 0.7) -> TeacherFeedback:
        return TeacherFeedback(
            feedback_id="fb-test",
            episode_id="ep-test",
            prompt="test prompt",
            student_response="test response",
            dimension_scores=[
                DimensionScore("correctness", score, "ok", 0.3),
                DimensionScore("completeness", score, "ok", 0.25),
                DimensionScore("coherence", score, "ok", 0.15),
                DimensionScore("specificity", score, "ok", 0.15),
                DimensionScore("safety", score, "ok", 0.15),
            ],
            composite_score=score,
            quality=FeedbackQuality.from_score(score),
            teacher_model="mock",
            student_model="mock",
        )

    def test_add_and_size(self):
        buf = FeedbackBuffer(max_size=100)
        buf.add(self._make_feedback())
        self.assertEqual(buf.size(), 1)

    def test_sample(self):
        buf = FeedbackBuffer(max_size=100)
        for _ in range(10):
            buf.add(self._make_feedback())
        sampled = buf.sample(5)
        self.assertEqual(len(sampled), 5)

    def test_sample_more_than_available(self):
        buf = FeedbackBuffer(max_size=100)
        buf.add(self._make_feedback())
        sampled = buf.sample(50)
        self.assertEqual(len(sampled), 1)

    def test_sample_empty(self):
        buf = FeedbackBuffer(max_size=100)
        sampled = buf.sample(5)
        self.assertEqual(len(sampled), 0)

    def test_recent(self):
        buf = FeedbackBuffer(max_size=100)
        for i in range(10):
            fb = self._make_feedback(score=i * 0.1)
            buf.add(fb)
        recent = buf.recent(3)
        self.assertEqual(len(recent), 3)

    def test_overflow_eviction(self):
        buf = FeedbackBuffer(max_size=100)
        for i in range(150):
            buf.add(self._make_feedback())
        # Should have evicted and still be under max_size
        self.assertLessEqual(buf.size(), 100)

    def test_clear(self):
        buf = FeedbackBuffer(max_size=100)
        buf.add(self._make_feedback())
        buf.clear()
        self.assertEqual(buf.size(), 0)

    def test_avg_composite_score(self):
        buf = FeedbackBuffer(max_size=100)
        buf.add(self._make_feedback(score=0.6))
        buf.add(self._make_feedback(score=0.8))
        self.assertAlmostEqual(buf.avg_composite_score(), 0.7)

    def test_avg_composite_score_empty(self):
        buf = FeedbackBuffer(max_size=100)
        self.assertAlmostEqual(buf.avg_composite_score(), 0.0)

    def test_quality_distribution(self):
        buf = FeedbackBuffer(max_size=100)
        buf.add(self._make_feedback(score=0.9))  # excellent
        buf.add(self._make_feedback(score=0.9))  # excellent
        buf.add(self._make_feedback(score=0.5))  # fair
        dist = buf.quality_distribution()
        self.assertEqual(dist.get("excellent", 0), 2)
        self.assertEqual(dist.get("fair", 0), 1)

    def test_dimension_averages(self):
        buf = FeedbackBuffer(max_size=100)
        buf.add(self._make_feedback(score=0.6))
        buf.add(self._make_feedback(score=0.8))
        avgs = buf.dimension_averages()
        self.assertAlmostEqual(avgs["correctness"], 0.7)

    def test_dimension_averages_empty(self):
        buf = FeedbackBuffer(max_size=100)
        self.assertEqual(buf.dimension_averages(), {})

    def test_thread_safety(self):
        """Condition: concurrent access should not corrupt state."""
        buf = FeedbackBuffer(max_size=500)
        errors = []

        def writer():
            try:
                for _ in range(100):
                    buf.add(self._make_feedback())
            except Exception as e:
                errors.append(e)

        def reader():
            try:
                for _ in range(100):
                    buf.sample(5)
                    buf.size()
                    buf.avg_composite_score()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer) for _ in range(4)]
        threads += [threading.Thread(target=reader) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Thread errors: {errors}")

    def test_min_buffer_size_clamped(self):
        buf = FeedbackBuffer(max_size=10)
        self.assertEqual(buf._max_size, 100)  # clamped to minimum 100


# ===================================================================
# Test: StudentPolicyTracker
# ===================================================================

class TestStudentPolicyTracker(unittest.TestCase):
    """Conditions: score tracking, snapshots, improvement velocity."""

    def test_record_score(self):
        tracker = StudentPolicyTracker(snapshot_interval=10)
        for _ in range(5):
            tracker.record_score(0.7)
        self.assertEqual(tracker.get_episode_count(), 5)

    def test_avg_score(self):
        tracker = StudentPolicyTracker(snapshot_interval=100)
        tracker.record_score(0.6)
        tracker.record_score(0.8)
        self.assertAlmostEqual(tracker.get_avg_score(), 0.7)

    def test_avg_score_empty(self):
        tracker = StudentPolicyTracker()
        self.assertAlmostEqual(tracker.get_avg_score(), 0.0)

    def test_snapshot_at_interval(self):
        tracker = StudentPolicyTracker(snapshot_interval=5)
        for i in range(10):
            snap = tracker.record_score(0.5 + i * 0.05)
        # Snapshot at episodes 5 and 10
        snapshots = tracker.get_snapshots()
        self.assertEqual(len(snapshots), 2)

    def test_no_snapshot_before_interval(self):
        tracker = StudentPolicyTracker(snapshot_interval=100)
        snap = tracker.record_score(0.5)
        self.assertIsNone(snap)

    def test_improvement_velocity_positive(self):
        """Later scores higher → positive velocity."""
        tracker = StudentPolicyTracker(snapshot_interval=100)
        for i in range(10):
            tracker.record_score(0.3 + i * 0.05)
        vel = tracker.get_improvement_velocity()
        self.assertGreater(vel, 0.0)

    def test_improvement_velocity_negative(self):
        """Later scores lower → negative velocity."""
        tracker = StudentPolicyTracker(snapshot_interval=100)
        for i in range(10):
            tracker.record_score(0.9 - i * 0.05)
        vel = tracker.get_improvement_velocity()
        self.assertLess(vel, 0.0)

    def test_improvement_velocity_single_episode(self):
        tracker = StudentPolicyTracker()
        tracker.record_score(0.5)
        self.assertAlmostEqual(tracker.get_improvement_velocity(), 0.0)

    def test_get_latest_snapshot_none(self):
        tracker = StudentPolicyTracker()
        self.assertIsNone(tracker.get_latest_snapshot())

    def test_get_latest_snapshot(self):
        tracker = StudentPolicyTracker(snapshot_interval=3)
        for _ in range(3):
            tracker.record_score(0.6)
        snap = tracker.get_latest_snapshot()
        self.assertIsNotNone(snap)
        self.assertEqual(snap.episode_count, 3)


# ===================================================================
# Test: TeacherFeedback serialization
# ===================================================================

class TestTeacherFeedback(unittest.TestCase):
    """Expected: to_dict produces a JSON-serialisable dict."""

    def test_to_dict(self):
        fb = TeacherFeedback(
            feedback_id="fb-001",
            episode_id="ep-001",
            prompt="test prompt",
            student_response="test response content here with enough chars",
            dimension_scores=[
                DimensionScore("correctness", 0.8, "ok", 0.3),
            ],
            composite_score=0.8,
            quality=FeedbackQuality.GOOD,
            teacher_model="mock-70b",
            student_model="mock-8b",
        )
        d = fb.to_dict()
        self.assertEqual(d["feedback_id"], "fb-001")
        self.assertEqual(d["quality"], "good")
        self.assertIsInstance(d["dimension_scores"], list)
        # prompt should be truncated
        self.assertLessEqual(len(d["prompt"]), 200)

    def test_to_dict_long_prompt_truncated(self):
        fb = TeacherFeedback(
            feedback_id="fb-002",
            episode_id="ep-002",
            prompt="x" * 500,
            student_response="response",
            dimension_scores=[],
            composite_score=0.5,
            quality=FeedbackQuality.FAIR,
            teacher_model="m",
            student_model="m",
        )
        d = fb.to_dict()
        self.assertLessEqual(len(d["prompt"]), 200)


# ===================================================================
# Test: OnPolicyDistiller — normal operation
# ===================================================================

class TestOnPolicyDistillerNormal(unittest.TestCase):
    """Condition: both student and teacher succeed."""

    def setUp(self):
        self.provider = _MockLLMProvider()
        self.distiller = OnPolicyDistiller(
            llm_provider=self.provider,
            buffer_size=1000,
            snapshot_interval=5,
        )

    def test_run_episode_success(self):
        result = self.distiller.run_episode("Build a CRM application")
        self.assertIsNone(result["error"])
        self.assertEqual(result["phase"], "complete")
        self.assertGreater(result["composite_score"], 0.0)
        self.assertNotEqual(result["quality"], "n/a")

    def test_run_episode_records_feedback(self):
        self.distiller.run_episode("Build a CRM application")
        self.assertEqual(self.distiller._buffer.size(), 1)

    def test_run_episode_increments_count(self):
        self.distiller.run_episode("Build an app")
        self.assertEqual(self.distiller._tracker.get_episode_count(), 1)

    def test_composite_score_in_range(self):
        result = self.distiller.run_episode("Build a CRM")
        self.assertGreaterEqual(result["composite_score"], 0.0)
        self.assertLessEqual(result["composite_score"], 1.0)

    def test_run_session(self):
        prompts = ["Build A", "Build B", "Build C"]
        session = self.distiller.run_session(prompts)
        self.assertEqual(session["status"], "ok")
        self.assertEqual(session["total_episodes"], 3)
        self.assertIn("avg_composite_score", session)
        self.assertIn("quality_distribution", session)
        self.assertIn("dimension_averages", session)

    def test_run_session_creates_snapshot(self):
        """Run enough episodes to trigger a snapshot."""
        prompts = ["Build " + str(i) for i in range(6)]
        self.distiller.run_session(prompts)
        snap = self.distiller._tracker.get_latest_snapshot()
        self.assertIsNotNone(snap)

    def test_get_stats(self):
        self.distiller.run_episode("Build something")
        stats = self.distiller.get_stats()
        self.assertEqual(stats["episode_count"], 1)
        self.assertEqual(stats["buffer_size"], 1)
        self.assertGreater(stats["avg_composite_score"], 0.0)

    def test_get_recent_feedback(self):
        self.distiller.run_episode("Build something")
        recent = self.distiller.get_recent_feedback(5)
        self.assertEqual(len(recent), 1)
        self.assertIn("composite_score", recent[0])

    def test_get_episodes(self):
        self.distiller.run_episode("Build something")
        eps = self.distiller.get_episodes()
        self.assertEqual(len(eps), 1)
        self.assertEqual(eps[0]["phase"], "complete")


# ===================================================================
# Test: OnPolicyDistiller — error conditions
# ===================================================================

class TestOnPolicyDistillerErrors(unittest.TestCase):
    """Conditions: empty prompt, student failure, teacher failure, no provider."""

    def test_empty_prompt(self):
        distiller = OnPolicyDistiller(llm_provider=_MockLLMProvider())
        result = distiller.run_episode("")
        self.assertEqual(result["error"], "empty_prompt")
        self.assertEqual(result["composite_score"], 0.0)

    def test_whitespace_prompt(self):
        distiller = OnPolicyDistiller(llm_provider=_MockLLMProvider())
        result = distiller.run_episode("   \n\t  ")
        self.assertEqual(result["error"], "empty_prompt")

    def test_student_failure(self):
        provider = _MockLLMProvider(student_error=True)
        distiller = OnPolicyDistiller(llm_provider=provider)
        result = distiller.run_episode("Build something")
        self.assertEqual(result["error"], "student_insufficient_response")
        self.assertEqual(result["phase"], "rollout")

    def test_student_empty_response(self):
        provider = _MockLLMProvider(student_response="")
        distiller = OnPolicyDistiller(llm_provider=provider)
        result = distiller.run_episode("Build something")
        self.assertEqual(result["error"], "student_insufficient_response")

    def test_student_short_response(self):
        provider = _MockLLMProvider(student_response="short")
        distiller = OnPolicyDistiller(llm_provider=provider)
        result = distiller.run_episode("Build something")
        self.assertEqual(result["error"], "student_insufficient_response")

    def test_teacher_failure_still_produces_feedback(self):
        """Even if teacher LLM fails, we produce default-scored feedback."""
        provider = _MockLLMProvider(teacher_error=True)
        distiller = OnPolicyDistiller(llm_provider=provider)
        result = distiller.run_episode("Build something")
        # Teacher failure → defaults to 0.5 per dimension
        self.assertIsNone(result["error"])
        self.assertGreater(result["composite_score"], 0.0)

    def test_no_llm_provider(self):
        distiller = OnPolicyDistiller(llm_provider=None)
        result = distiller.run_episode("Build something")
        # No provider → student produces empty response
        self.assertEqual(result["error"], "student_insufficient_response")

    def test_teacher_garbage_json(self):
        """Teacher returns unparseable response → default scores."""
        provider = _MockLLMProvider(
            teacher_response="I don't know how to evaluate this."
        )
        distiller = OnPolicyDistiller(llm_provider=provider)
        result = distiller.run_episode("Build something")
        self.assertIsNone(result["error"])
        # Default 0.5 per dimension × weights = 0.5
        self.assertAlmostEqual(result["composite_score"], 0.5, places=1)


# ===================================================================
# Test: OnPolicyDistiller — prompt length validation
# ===================================================================

class TestOnPolicyDistillerPromptValidation(unittest.TestCase):
    """Condition: oversized prompts are truncated, not rejected."""

    def test_long_prompt_truncated(self):
        provider = _MockLLMProvider()
        distiller = OnPolicyDistiller(
            llm_provider=provider, max_prompt_len=100
        )
        result = distiller.run_episode("x" * 500)
        self.assertIsNone(result["error"])

    def test_max_prompt_len_clamped_low(self):
        distiller = OnPolicyDistiller(max_prompt_len=10)
        self.assertEqual(distiller._max_prompt_len, 100)

    def test_max_prompt_len_clamped_high(self):
        distiller = OnPolicyDistiller(max_prompt_len=999_999)
        self.assertEqual(distiller._max_prompt_len, 50_000)


# ===================================================================
# Test: OnPolicyDistiller — composite score calculation
# ===================================================================

class TestCompositeScoreCalculation(unittest.TestCase):
    """Expected: composite = Σ(score_i × weight_i)."""

    def test_dimension_weights_sum_to_one(self):
        total = sum(_DIMENSION_WEIGHTS.values())
        self.assertAlmostEqual(total, 1.0, places=5)

    def test_all_perfect_scores(self):
        provider = _MockLLMProvider(
            teacher_response=json.dumps({
                "correctness": {"score": 1.0, "rationale": ""},
                "completeness": {"score": 1.0, "rationale": ""},
                "coherence": {"score": 1.0, "rationale": ""},
                "specificity": {"score": 1.0, "rationale": ""},
                "safety": {"score": 1.0, "rationale": ""},
            })
        )
        distiller = OnPolicyDistiller(llm_provider=provider)
        result = distiller.run_episode("Build something")
        self.assertAlmostEqual(result["composite_score"], 1.0, places=2)

    def test_all_zero_scores(self):
        provider = _MockLLMProvider(
            teacher_response=json.dumps({
                "correctness": {"score": 0.0, "rationale": ""},
                "completeness": {"score": 0.0, "rationale": ""},
                "coherence": {"score": 0.0, "rationale": ""},
                "specificity": {"score": 0.0, "rationale": ""},
                "safety": {"score": 0.0, "rationale": ""},
            })
        )
        distiller = OnPolicyDistiller(llm_provider=provider)
        result = distiller.run_episode("Build something")
        self.assertAlmostEqual(result["composite_score"], 0.0, places=2)


# ===================================================================
# Test: Factory function
# ===================================================================

class TestFactory(unittest.TestCase):
    """Expected: create_on_policy_distiller returns a working instance."""

    def test_factory_no_provider(self):
        d = create_on_policy_distiller()
        self.assertIsInstance(d, OnPolicyDistiller)

    def test_factory_with_provider(self):
        d = create_on_policy_distiller(llm_provider=_MockLLMProvider())
        result = d.run_episode("Build something")
        self.assertIsNotNone(result)

    def test_factory_custom_buffer(self):
        d = create_on_policy_distiller(buffer_size=200)
        self.assertIsInstance(d, OnPolicyDistiller)

    def test_factory_custom_snapshot_interval(self):
        d = create_on_policy_distiller(snapshot_interval=10)
        self.assertIsInstance(d, OnPolicyDistiller)


# ===================================================================
# Test: Thread safety of OnPolicyDistiller
# ===================================================================

class TestOnPolicyDistillerThreadSafety(unittest.TestCase):
    """Condition: concurrent episode execution must not corrupt state."""

    def test_concurrent_episodes(self):
        provider = _MockLLMProvider()
        distiller = OnPolicyDistiller(
            llm_provider=provider, buffer_size=500
        )
        errors = []

        def runner(tid):
            try:
                for i in range(10):
                    distiller.run_episode(f"Thread {tid} prompt {i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=runner, args=(t,)) for t in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Thread errors: {errors}")
        self.assertEqual(distiller._tracker.get_episode_count(), 40)
        self.assertGreater(distiller._buffer.size(), 0)


# ===================================================================
# Test: DistillationPhase enum
# ===================================================================

class TestDistillationPhase(unittest.TestCase):

    def test_all_phases_exist(self):
        phases = [p.value for p in DistillationPhase]
        self.assertIn("rollout", phases)
        self.assertIn("evaluation", phases)
        self.assertIn("recording", phases)
        self.assertIn("update", phases)
        self.assertIn("distill", phases)
        self.assertIn("complete", phases)


# ===================================================================
# Test: DistillationEpisode dataclass
# ===================================================================

class TestDistillationEpisode(unittest.TestCase):

    def test_defaults(self):
        ep = DistillationEpisode(
            episode_id="ep-001",
            prompt="test",
            domain="general",
            student_response="response",
            feedback=None,
            phase=DistillationPhase.ROLLOUT,
        )
        self.assertEqual(ep.reward, 0.0)
        self.assertIsNone(ep.error)
        self.assertIsNotNone(ep.timestamp)


# ===================================================================
# Test: PolicySnapshot dataclass
# ===================================================================

class TestPolicySnapshot(unittest.TestCase):

    def test_defaults(self):
        snap = PolicySnapshot(
            snapshot_id="snap-001",
            episode_count=10,
            avg_composite_score=0.7,
            dimension_averages={"correctness": 0.8},
            quality_distribution={"good": 5},
            improvement_velocity=0.05,
        )
        self.assertEqual(snap.episode_count, 10)
        self.assertIsNotNone(snap.timestamp)


if __name__ == "__main__":
    unittest.main()
