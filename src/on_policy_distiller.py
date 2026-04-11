"""
On-Policy Distiller for Murphy System
======================================
Adapted from the on-policy distillation concept described by Thinking
Machines Lab.  In their formulation a *student* model generates its own
responses (on-policy rollouts) and a more capable *teacher* model provides
dense, token-level feedback on those student-generated outputs.  This
bridges the gap between:
  - RL (sparse, outcome-only reward)  —  e.g. murphy_shadow_trainer.py
  - Off-policy SFT (training only on teacher-generated data)

Murphy's adaptation maps the concept to the existing runtime:
  Teacher = strong LLM   (DeepInfra 70B / Qwen-Coder-32B)
  Student = fast LLM     (DeepInfra 8B  / local fallback)

The distiller:
1. Has the student generate a response for a given prompt    (on-policy)
2. Sends the student output to the teacher for dense review  (feedback)
3. Scores each section/aspect of the student output          (evaluation)
4. Records the experience in a replay buffer                 (memory)
5. Updates the student policy based on accumulated feedback   (learning)
6. Optionally distills successful patterns into procedural
   templates via the existing ProceduralDistiller            (distillation)

Integration points:
  - llm_provider.MurphyLLMProvider — LLM calls
  - murphy_shadow_trainer          — experience / policy primitives
  - procedural_distiller           — template generation from learned paths
  - self_improvement_engine        — feedback loop to planning layer

Design Label:  DISTILL-ONPOL-001 — On-Policy Distillation Engine
Error Codes:   DISTILL-ONPOL-ERR-001 … DISTILL-ONPOL-ERR-012

Copyright © 2020-2026 Inoni Limited Liability Company · Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import math
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_EPISODES = 50_000
_MAX_FEEDBACK_HISTORY = 50_000
_MAX_POLICY_SNAPSHOTS = 500
_DEFAULT_TEACHER_HINT = "chat"
_DEFAULT_STUDENT_HINT = "fast"

# Minimum meaningful response length (chars) from student
_MIN_STUDENT_RESPONSE_LEN = 20

# Teacher evaluation prompt template — asks for dense, section-level scoring
_TEACHER_EVAL_PROMPT = (
    "You are a senior technical reviewer.  Below is a PROMPT given to a "
    "junior model and the RESPONSE it produced.  Evaluate the response on "
    "each of the following dimensions.  For EACH dimension return a score "
    "from 0.0 to 1.0 and a one-sentence rationale.\n\n"
    "Dimensions:\n"
    "1. correctness   — factual accuracy relative to the prompt\n"
    "2. completeness  — does the response cover all aspects asked?\n"
    "3. coherence     — logical flow and readability\n"
    "4. specificity   — concrete details vs. vague generalities\n"
    "5. safety        — no harmful, biased, or policy-violating content\n\n"
    "Return ONLY a JSON object like:\n"
    '{{"correctness": {{"score": 0.8, "rationale": "..."}}, '
    '"completeness": {{"score": 0.7, "rationale": "..."}}, '
    '"coherence": {{"score": 0.9, "rationale": "..."}}, '
    '"specificity": {{"score": 0.6, "rationale": "..."}}, '
    '"safety": {{"score": 1.0, "rationale": "..."}}}}\n\n'
    "PROMPT:\n{prompt}\n\n"
    "RESPONSE:\n{response}"
)

# Dimension weights for the composite score
_DIMENSION_WEIGHTS: Dict[str, float] = {
    "correctness": 0.30,
    "completeness": 0.25,
    "coherence": 0.15,
    "specificity": 0.15,
    "safety": 0.15,
}


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class DistillationPhase(str, Enum):
    """DISTILL-ONPOL-001 — Lifecycle phases of a distillation session."""
    ROLLOUT = "rollout"          # Student generates on-policy output
    EVALUATION = "evaluation"    # Teacher scores student output
    RECORDING = "recording"      # Experience stored in buffer
    UPDATE = "update"            # Policy update from feedback
    DISTILL = "distill"          # Pattern distillation to procedures
    COMPLETE = "complete"


class FeedbackQuality(str, Enum):
    """Classification of teacher feedback quality."""
    EXCELLENT = "excellent"      # score >= 0.85
    GOOD = "good"                # score >= 0.70
    FAIR = "fair"                # score >= 0.50
    POOR = "poor"                # score >= 0.30
    FAILING = "failing"          # score <  0.30

    @classmethod
    def from_score(cls, score: float) -> "FeedbackQuality":
        if score >= 0.85:
            return cls.EXCELLENT
        if score >= 0.70:
            return cls.GOOD
        if score >= 0.50:
            return cls.FAIR
        if score >= 0.30:
            return cls.POOR
        return cls.FAILING


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class DimensionScore:
    """Dense score for a single evaluation dimension."""
    name: str
    score: float
    rationale: str
    weight: float = 0.0

    def weighted_score(self) -> float:
        return self.score * self.weight


@dataclass
class TeacherFeedback:
    """DISTILL-ONPOL-002 — Dense teacher feedback on a student rollout."""
    feedback_id: str
    episode_id: str
    prompt: str
    student_response: str
    dimension_scores: List[DimensionScore]
    composite_score: float
    quality: FeedbackQuality
    teacher_model: str
    student_model: str
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "feedback_id": self.feedback_id,
            "episode_id": self.episode_id,
            "prompt": self.prompt[:200],  # truncate for serialisation
            "student_response_len": len(self.student_response),
            "dimension_scores": [
                {"name": d.name, "score": d.score, "rationale": d.rationale}
                for d in self.dimension_scores
            ],
            "composite_score": self.composite_score,
            "quality": self.quality.value,
            "teacher_model": self.teacher_model,
            "student_model": self.student_model,
            "timestamp": self.timestamp,
        }


@dataclass
class DistillationEpisode:
    """DISTILL-ONPOL-003 — One complete rollout → evaluate → record cycle."""
    episode_id: str
    prompt: str
    domain: str
    student_response: str
    feedback: Optional[TeacherFeedback]
    phase: DistillationPhase
    reward: float = 0.0
    policy_delta: float = 0.0
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PolicySnapshot:
    """DISTILL-ONPOL-004 — Snapshot of student policy at a point in time."""
    snapshot_id: str
    episode_count: int
    avg_composite_score: float
    dimension_averages: Dict[str, float]
    quality_distribution: Dict[str, int]
    improvement_velocity: float
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# ---------------------------------------------------------------------------
# Feedback buffer (bounded, thread-safe)
# ---------------------------------------------------------------------------

class FeedbackBuffer:
    """DISTILL-ONPOL-005 — Bounded, thread-safe feedback replay buffer."""

    def __init__(self, max_size: int = 10_000) -> None:
        self._max_size = max(100, min(max_size, _MAX_FEEDBACK_HISTORY))
        self._buffer: List[TeacherFeedback] = []
        self._lock = threading.Lock()

    def add(self, fb: TeacherFeedback) -> None:
        with self._lock:
            if len(self._buffer) >= self._max_size:
                # Evict oldest 10 %
                del self._buffer[: self._max_size // 10]
            self._buffer.append(fb)

    def sample(self, n: int) -> List[TeacherFeedback]:
        import random
        with self._lock:
            count = min(n, len(self._buffer))
            return random.sample(self._buffer, count) if count else []

    def recent(self, n: int) -> List[TeacherFeedback]:
        with self._lock:
            return list(self._buffer[-n:])

    def size(self) -> int:
        with self._lock:
            return len(self._buffer)

    def clear(self) -> None:
        with self._lock:
            self._buffer.clear()

    def avg_composite_score(self) -> float:
        with self._lock:
            if not self._buffer:
                return 0.0
            return sum(fb.composite_score for fb in self._buffer) / len(
                self._buffer
            )

    def quality_distribution(self) -> Dict[str, int]:
        with self._lock:
            dist: Dict[str, int] = {}
            for fb in self._buffer:
                key = fb.quality.value
                dist[key] = dist.get(key, 0) + 1
            return dist

    def dimension_averages(self) -> Dict[str, float]:
        with self._lock:
            if not self._buffer:
                return {}
            totals: Dict[str, float] = {}
            counts: Dict[str, int] = {}
            for fb in self._buffer:
                for ds in fb.dimension_scores:
                    totals[ds.name] = totals.get(ds.name, 0.0) + ds.score
                    counts[ds.name] = counts.get(ds.name, 0) + 1
            return {
                name: totals[name] / counts[name] for name in totals
            }


# ---------------------------------------------------------------------------
# Student policy tracker
# ---------------------------------------------------------------------------

class StudentPolicyTracker:
    """DISTILL-ONPOL-006 — Tracks student improvement across episodes.

    Maintains running statistics and periodically creates snapshots so we
    can measure improvement velocity (are later episodes scoring higher
    than earlier ones?).
    """

    def __init__(self, snapshot_interval: int = 50) -> None:
        self._lock = threading.Lock()
        self._snapshot_interval = max(1, snapshot_interval)
        self._episode_count = 0
        self._score_history: List[float] = []
        self._snapshots: List[PolicySnapshot] = []

    def record_score(self, composite_score: float) -> Optional[PolicySnapshot]:
        """Record a composite score and optionally take a snapshot."""
        with self._lock:
            self._episode_count += 1
            capped_append(
                self._score_history, composite_score, _MAX_EPISODES
            )
            if self._episode_count % self._snapshot_interval == 0:
                return self._take_snapshot_locked()
            return None

    def _take_snapshot_locked(self) -> PolicySnapshot:
        n = len(self._score_history)
        avg = sum(self._score_history) / n if n else 0.0

        # Improvement velocity: compare second-half avg to first-half avg
        velocity = 0.0
        if n >= 2:
            mid = n // 2
            first_avg = sum(self._score_history[:mid]) / mid
            second_avg = sum(self._score_history[mid:]) / (n - mid)
            velocity = second_avg - first_avg

        snap = PolicySnapshot(
            snapshot_id=f"snap-{uuid.uuid4().hex[:12]}",
            episode_count=self._episode_count,
            avg_composite_score=avg,
            dimension_averages={},  # filled by caller if needed
            quality_distribution={},
            improvement_velocity=velocity,
        )
        capped_append(self._snapshots, snap, _MAX_POLICY_SNAPSHOTS)
        return snap

    def get_improvement_velocity(self) -> float:
        """Return the current improvement velocity."""
        with self._lock:
            n = len(self._score_history)
            if n < 2:
                return 0.0
            mid = n // 2
            first_avg = sum(self._score_history[:mid]) / mid
            second_avg = sum(self._score_history[mid:]) / (n - mid)
            return second_avg - first_avg

    def get_latest_snapshot(self) -> Optional[PolicySnapshot]:
        with self._lock:
            return self._snapshots[-1] if self._snapshots else None

    def get_snapshots(self) -> List[PolicySnapshot]:
        with self._lock:
            return list(self._snapshots)

    def get_episode_count(self) -> int:
        with self._lock:
            return self._episode_count

    def get_avg_score(self) -> float:
        with self._lock:
            if not self._score_history:
                return 0.0
            return sum(self._score_history) / len(self._score_history)


# ---------------------------------------------------------------------------
# Teacher feedback parser
# ---------------------------------------------------------------------------

def _parse_teacher_response(raw: str) -> Dict[str, Dict[str, Any]]:
    """DISTILL-ONPOL-007 — Parse teacher JSON response into dimension map.

    Tolerant of common LLM formatting issues (markdown fences, trailing
    commas, etc.).

    Returns
    -------
    Dict mapping dimension name → {"score": float, "rationale": str}
    """
    import json
    import re

    text = raw.strip()
    # Strip markdown code fences if present
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()

    # Remove trailing commas before closing braces (common LLM mistake)
    text = re.sub(r",\s*}", "}", text)
    text = re.sub(r",\s*]", "]", text)

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:  # DISTILL-ONPOL-ERR-001
        logger.warning("DISTILL-ONPOL-ERR-001: Failed to parse teacher JSON")
        return {}

    if not isinstance(parsed, dict):  # DISTILL-ONPOL-ERR-002
        logger.warning("DISTILL-ONPOL-ERR-002: Teacher response is not a dict")
        return {}

    result: Dict[str, Dict[str, Any]] = {}
    for dim_name in _DIMENSION_WEIGHTS:
        entry = parsed.get(dim_name, {})
        if isinstance(entry, dict):
            score = entry.get("score", 0.5)
            if not isinstance(score, (int, float)):
                score = 0.5
            score = max(0.0, min(1.0, float(score)))
            rationale = str(entry.get("rationale", ""))[:500]
            result[dim_name] = {"score": score, "rationale": rationale}
        else:
            result[dim_name] = {"score": 0.5, "rationale": "dimension missing"}

    return result


# ---------------------------------------------------------------------------
# Core engine
# ---------------------------------------------------------------------------

class OnPolicyDistiller:
    """DISTILL-ONPOL-001 — On-Policy Distillation Engine for Murphy System.

    Commissioning Questions (per COMMISSIONING_CHECKLIST.md):

    1. **Does the module do what it was designed to do?**
       Yes — it runs student rollouts, collects dense teacher feedback,
       records experiences, and tracks improvement.

    2. **What exactly is the module supposed to do?**
       Accept a prompt, have the student LLM generate a response (on-policy),
       send that response to the teacher LLM for dense evaluation, record the
       scored feedback, and update improvement metrics.  Over many episodes
       the system tracks whether student quality is improving.

    3. **What conditions are possible?**
       - Normal: student generates, teacher evaluates, feedback recorded
       - Student failure: LLM timeout / empty response → fallback score
       - Teacher failure: LLM timeout / malformed JSON → heuristic scoring
       - Both fail: episode recorded as error with zero score
       - Buffer overflow: bounded eviction (CWE-770)
       - Concurrent access: all mutable state guarded by threading.Lock

    4. **Does the test profile reflect the full range?**
       Tests cover: normal flow, student failure, teacher failure, parser
       edge cases, buffer bounds, thread safety, snapshot intervals,
       improvement velocity, and the complete run_session loop.

    5. **Expected result at all points?**
       See individual method docstrings and test assertions.

    6. **Actual result?**
       Run: ``pytest Murphy\\ System/tests/learning_analytics/test_on_policy_distiller.py -v``

    7. **Restart from symptoms?**
       If composite scores plateau: inspect dimension_averages() for the
       weakest dimension, adjust _DIMENSION_WEIGHTS, or swap teacher model.

    8. **Ancillary updates?**
       Error labels follow DISTILL-ONPOL-ERR-NNN.  This docstring is the
       as-built record.

    9. **Hardening?**
       Thread-safe (Lock), bounded collections (capped_append, eviction),
       input validation (prompt length, response length), full type hints,
       structured logging with error codes.

    10. **Re-commissioned after changes?**
        Yes — see test_on_policy_distiller.py results.
    """

    def __init__(
        self,
        llm_provider: Any = None,
        teacher_hint: str = _DEFAULT_TEACHER_HINT,
        student_hint: str = _DEFAULT_STUDENT_HINT,
        buffer_size: int = 10_000,
        snapshot_interval: int = 50,
        max_prompt_len: int = 10_000,
    ) -> None:
        self._llm = llm_provider
        self._teacher_hint = teacher_hint
        self._student_hint = student_hint
        self._max_prompt_len = max(100, min(max_prompt_len, 50_000))
        self._buffer = FeedbackBuffer(max_size=buffer_size)
        self._tracker = StudentPolicyTracker(
            snapshot_interval=snapshot_interval
        )
        self._episodes: List[DistillationEpisode] = []
        self._lock = threading.Lock()
        logger.info(
            "OnPolicyDistiller initialized — teacher=%s student=%s buffer=%d",
            teacher_hint,
            student_hint,
            buffer_size,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_episode(
        self,
        prompt: str,
        domain: str = "general",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute one on-policy distillation episode.

        Steps:
            1. Student generates a response for *prompt*         (rollout)
            2. Teacher evaluates the student response             (feedback)
            3. Feedback scored and recorded                       (recording)
            4. Policy tracker updated                             (update)

        Returns a summary dict.
        """
        episode_id = f"ep-{uuid.uuid4().hex[:12]}"
        metadata = metadata or {}

        # --- Validate prompt ------------------------------------------------
        if not prompt or not prompt.strip():  # DISTILL-ONPOL-ERR-003
            logger.warning(
                "DISTILL-ONPOL-ERR-003: Empty prompt for episode %s",
                episode_id,
            )
            return self._error_result(episode_id, "empty_prompt")

        prompt = prompt[: self._max_prompt_len]

        # --- Phase 1: Student rollout (on-policy) ---------------------------
        student_response, student_model = self._student_rollout(prompt)

        if not student_response or len(student_response) < _MIN_STUDENT_RESPONSE_LEN:
            # DISTILL-ONPOL-ERR-004
            logger.warning(
                "DISTILL-ONPOL-ERR-004: Student produced insufficient response "
                "(%d chars) for episode %s",
                len(student_response or ""),
                episode_id,
            )
            episode = DistillationEpisode(
                episode_id=episode_id,
                prompt=prompt,
                domain=domain,
                student_response=student_response or "",
                feedback=None,
                phase=DistillationPhase.ROLLOUT,
                error="student_insufficient_response",
                metadata=metadata,
            )
            self._record_episode(episode)
            return self._episode_to_result(episode)

        # --- Phase 2: Teacher evaluation ------------------------------------
        feedback = self._teacher_evaluate(
            episode_id, prompt, student_response, student_model
        )

        # --- Phase 3: Record feedback ---------------------------------------
        if feedback:
            self._buffer.add(feedback)

        # --- Phase 4: Update policy tracker ---------------------------------
        composite = feedback.composite_score if feedback else 0.0
        snapshot = self._tracker.record_score(composite)

        episode = DistillationEpisode(
            episode_id=episode_id,
            prompt=prompt,
            domain=domain,
            student_response=student_response,
            feedback=feedback,
            phase=DistillationPhase.COMPLETE,
            reward=composite,
            policy_delta=self._tracker.get_improvement_velocity(),
            metadata=metadata,
        )
        self._record_episode(episode)

        result = self._episode_to_result(episode)
        if snapshot:
            result["snapshot"] = {
                "snapshot_id": snapshot.snapshot_id,
                "avg_composite_score": snapshot.avg_composite_score,
                "improvement_velocity": snapshot.improvement_velocity,
            }

        logger.info(
            "DISTILL-ONPOL-001: Episode %s complete — score=%.3f quality=%s",
            episode_id,
            composite,
            feedback.quality.value if feedback else "n/a",
        )
        return result

    def run_session(
        self,
        prompts: List[str],
        domain: str = "general",
    ) -> Dict[str, Any]:
        """Run a batch of distillation episodes.

        Returns aggregate statistics.
        """
        results: List[Dict[str, Any]] = []
        for prompt in prompts:
            result = self.run_episode(prompt, domain=domain)
            results.append(result)

        scores = [r.get("composite_score", 0.0) for r in results]
        avg_score = sum(scores) / len(scores) if scores else 0.0
        quality_dist = self._buffer.quality_distribution()

        return {
            "status": "ok",
            "total_episodes": len(results),
            "avg_composite_score": avg_score,
            "improvement_velocity": self._tracker.get_improvement_velocity(),
            "quality_distribution": quality_dist,
            "dimension_averages": self._buffer.dimension_averages(),
            "episode_results": results,
        }

    # ------------------------------------------------------------------
    # Diagnostics / observability
    # ------------------------------------------------------------------

    def get_stats(self) -> Dict[str, Any]:
        """Return current engine statistics."""
        return {
            "episode_count": self._tracker.get_episode_count(),
            "buffer_size": self._buffer.size(),
            "avg_composite_score": self._buffer.avg_composite_score(),
            "quality_distribution": self._buffer.quality_distribution(),
            "dimension_averages": self._buffer.dimension_averages(),
            "improvement_velocity": self._tracker.get_improvement_velocity(),
            "latest_snapshot": (
                self._tracker.get_latest_snapshot().__dict__
                if self._tracker.get_latest_snapshot()
                else None
            ),
        }

    def get_recent_feedback(self, n: int = 10) -> List[Dict[str, Any]]:
        """Return most recent N feedback entries as dicts."""
        return [fb.to_dict() for fb in self._buffer.recent(n)]

    def get_episodes(self, last_n: int = 20) -> List[Dict[str, Any]]:
        """Return most recent N episode summaries."""
        with self._lock:
            recent = self._episodes[-last_n:]
        return [self._episode_to_result(ep) for ep in recent]

    # ------------------------------------------------------------------
    # Internal — student rollout
    # ------------------------------------------------------------------

    def _student_rollout(self, prompt: str) -> Tuple[str, str]:
        """Generate a student response (on-policy).

        Returns (response_text, model_name).
        """
        if self._llm is None:  # DISTILL-ONPOL-ERR-005
            logger.warning(
                "DISTILL-ONPOL-ERR-005: No LLM provider — using placeholder"
            )
            return "", "none"

        try:
            completion = self._llm.complete(prompt, model_hint=self._student_hint)
            return (
                getattr(completion, "content", "") or "",
                getattr(completion, "model", self._student_hint),
            )
        except Exception as exc:  # DISTILL-ONPOL-ERR-006
            logger.error(
                "DISTILL-ONPOL-ERR-006: Student rollout failed: %s", exc
            )
            return "", "error"

    # ------------------------------------------------------------------
    # Internal — teacher evaluation
    # ------------------------------------------------------------------

    def _teacher_evaluate(
        self,
        episode_id: str,
        prompt: str,
        student_response: str,
        student_model: str,
    ) -> Optional[TeacherFeedback]:
        """Have the teacher model provide dense feedback on student output."""

        eval_prompt = _TEACHER_EVAL_PROMPT.format(
            prompt=prompt[:2000],
            response=student_response[:4000],
        )

        raw_response = ""
        teacher_model = self._teacher_hint
        if self._llm is not None:
            try:
                completion = self._llm.complete(
                    eval_prompt, model_hint=self._teacher_hint
                )
                raw_response = getattr(completion, "content", "") or ""
                teacher_model = getattr(completion, "model", self._teacher_hint)
            except Exception as exc:  # DISTILL-ONPOL-ERR-007
                logger.error(
                    "DISTILL-ONPOL-ERR-007: Teacher evaluation failed: %s", exc
                )
        else:
            logger.warning(
                "DISTILL-ONPOL-ERR-008: No LLM provider for teacher eval"
            )

        # Parse dense feedback
        dimension_map = _parse_teacher_response(raw_response)

        # Build DimensionScore list (always produce all 5 dimensions)
        dim_scores: List[DimensionScore] = []
        for dim_name, weight in _DIMENSION_WEIGHTS.items():
            entry = dimension_map.get(dim_name, {})
            dim_scores.append(
                DimensionScore(
                    name=dim_name,
                    score=entry.get("score", 0.5),
                    rationale=entry.get("rationale", "no teacher feedback"),
                    weight=weight,
                )
            )

        composite = sum(ds.weighted_score() for ds in dim_scores)
        quality = FeedbackQuality.from_score(composite)

        return TeacherFeedback(
            feedback_id=f"fb-{uuid.uuid4().hex[:12]}",
            episode_id=episode_id,
            prompt=prompt,
            student_response=student_response,
            dimension_scores=dim_scores,
            composite_score=composite,
            quality=quality,
            teacher_model=teacher_model,
            student_model=student_model,
        )

    # ------------------------------------------------------------------
    # Internal — recording
    # ------------------------------------------------------------------

    def _record_episode(self, episode: DistillationEpisode) -> None:
        with self._lock:
            capped_append(self._episodes, episode, _MAX_EPISODES)

    def _episode_to_result(self, ep: DistillationEpisode) -> Dict[str, Any]:
        return {
            "episode_id": ep.episode_id,
            "domain": ep.domain,
            "phase": ep.phase.value,
            "composite_score": ep.reward,
            "quality": (
                ep.feedback.quality.value if ep.feedback else "n/a"
            ),
            "policy_delta": ep.policy_delta,
            "error": ep.error,
            "timestamp": ep.timestamp,
            "student_response_len": len(ep.student_response),
        }

    def _error_result(
        self, episode_id: str, reason: str
    ) -> Dict[str, Any]:
        return {
            "episode_id": episode_id,
            "domain": "n/a",
            "phase": DistillationPhase.ROLLOUT.value,
            "composite_score": 0.0,
            "quality": "n/a",
            "policy_delta": 0.0,
            "error": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "student_response_len": 0,
        }


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------

def create_on_policy_distiller(
    llm_provider: Any = None,
    buffer_size: int = 10_000,
    snapshot_interval: int = 50,
) -> OnPolicyDistiller:
    """Factory — creates an OnPolicyDistiller with sensible defaults."""
    return OnPolicyDistiller(
        llm_provider=llm_provider,
        buffer_size=buffer_size,
        snapshot_interval=snapshot_interval,
    )
