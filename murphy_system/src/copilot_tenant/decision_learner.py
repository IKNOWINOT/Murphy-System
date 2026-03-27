# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Copilot Tenant — Shadow Learning Engine (Decision Learner)

Learns from founder decisions to improve future suggestions.  Wraps:
  - src/murphy_shadow_trainer.py
  - src/shadow_agent_integration.py
  - src/confidence_engine/  (for accuracy tracking)
"""
from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Bounded append (CWE-770)
# ---------------------------------------------------------------------------

try:
    from thread_safe_operations import capped_append
except ImportError:  # pragma: no cover
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:  # type: ignore[misc]
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

# ---------------------------------------------------------------------------
# Optional dependency imports
# ---------------------------------------------------------------------------

try:
    from murphy_shadow_trainer import MurphyShadowTrainer
    _SHADOW_TRAINER_AVAILABLE = True
except Exception:  # pragma: no cover
    MurphyShadowTrainer = None  # type: ignore[assignment,misc]
    _SHADOW_TRAINER_AVAILABLE = False

try:
    from shadow_agent_integration import ShadowAgentIntegration
    _SHADOW_INTEGRATION_AVAILABLE = True
except Exception:  # pragma: no cover
    ShadowAgentIntegration = None  # type: ignore[assignment,misc]
    _SHADOW_INTEGRATION_AVAILABLE = False


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class DecisionRecord:
    record_id: str              = field(default_factory=lambda: str(uuid.uuid4()))
    context: Dict[str, Any]     = field(default_factory=dict)
    decision: str               = ""
    reasoning: str              = ""
    predicted: Optional[str]    = None
    correct: Optional[bool]     = None
    recorded_at: str            = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ---------------------------------------------------------------------------
# DecisionLearner
# ---------------------------------------------------------------------------

class DecisionLearner:
    """Learns from founder decisions to improve the Copilot Tenant's suggestions.

    The corpus grows over time; accuracy metrics are recomputed on each
    ``get_accuracy_metrics()`` call.

    ── MCB AGENT CONTROLLER ──────────────────────────────────────────
    DecisionLearner checks out a MultiCursorBrowser controller at init,
    keyed as ``"copilot_decision_learner"``.  This makes MCB the single
    browser/UI controller for any UI validation steps the learner
    performs (e.g. scraping decision context from live pages).
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._corpus: List[DecisionRecord] = []
        self._trainer: Any = None
        self._integration: Any = None

        # ── MCB controller checkout ───────────────────────────────────
        try:
            from agent_module_loader import MultiCursorBrowser as _MCB
            self._mcb = _MCB.get_controller(agent_id="copilot_decision_learner")
        except Exception:
            self._mcb = None

        self._initialize()

    def _initialize(self) -> None:
        if _SHADOW_TRAINER_AVAILABLE:
            try:
                self._trainer = MurphyShadowTrainer()
                self._trainer.start()
            except Exception as exc:
                logger.debug("MurphyShadowTrainer init failed: %s", exc)
        if _SHADOW_INTEGRATION_AVAILABLE:
            try:
                self._integration = ShadowAgentIntegration()
                self._integration.initialize()
            except Exception as exc:
                logger.debug("ShadowAgentIntegration init failed: %s", exc)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record_decision(
        self,
        context: Dict[str, Any],
        decision: str,
        reasoning: str,
    ) -> str:
        """Record a founder decision and return the record_id."""
        record = DecisionRecord(context=context, decision=decision, reasoning=reasoning)
        # Mark whether our prediction (if any) was correct
        if record.predicted is not None:
            record.correct = record.predicted == decision
        with self._lock:
            capped_append(self._corpus, record)
        # Delegate to shadow trainer if available
        if self._trainer is not None:
            try:
                self._trainer.record(
                    context=context,
                    decision=decision,
                    reasoning=reasoning,
                )
            except Exception as exc:
                logger.debug("shadow trainer record failed: %s", exc)
        logger.debug("DecisionLearner: recorded decision %s", record.record_id)
        return record.record_id

    def predict_decision(self, context: Dict[str, Any]) -> Tuple[str, float]:
        """Return (predicted_decision, confidence_score) for the given context.

        Falls back to the shadow trainer when available; otherwise uses a
        simple frequency-based heuristic over the local corpus.
        """
        # Try shadow trainer first
        if self._trainer is not None:
            try:
                result = self._trainer.predict(context)
                if isinstance(result, (tuple, list)) and len(result) >= 2:
                    return str(result[0]), float(result[1])
                if isinstance(result, dict):
                    return str(result.get("decision", "")), float(result.get("confidence", 0.0))
            except Exception as exc:
                logger.debug("shadow trainer predict failed: %s", exc)
        # Simple frequency heuristic
        with self._lock:
            if not self._corpus:
                return ("no_prediction", 0.0)
            counts: Dict[str, int] = {}
            for rec in self._corpus:
                counts[rec.decision] = counts.get(rec.decision, 0) + 1
            best = max(counts, key=counts.__getitem__)
            confidence = counts[best] / len(self._corpus)
            return (best, round(confidence, 4))

    def get_accuracy_metrics(self) -> Dict[str, float]:
        """Return accuracy metrics over all decisions that had predictions."""
        with self._lock:
            evaluated = [r for r in self._corpus if r.correct is not None]
        if not evaluated:
            return {"accuracy": 0.0, "evaluated_count": 0.0, "corpus_size": float(len(self._corpus))}
        correct = sum(1 for r in evaluated if r.correct)
        return {
            "accuracy":        round(correct / len(evaluated), 4),
            "evaluated_count": float(len(evaluated)),
            "corpus_size":     float(len(self._corpus)),
        }

    def get_decision_corpus_size(self) -> int:
        """Return the total number of decisions in the corpus."""
        with self._lock:
            return len(self._corpus)
