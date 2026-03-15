"""Re-export ConfidenceEngine from mfgc_core for backward compatibility.

Provides a simplified wrapper that accepts artifact lists for integration tests.

Canonical Murphy Index definition (GAP-2):
    M_t = Σ_k(L_k × p_k)  — expected loss over all failure modes.

When risk data (loss/probability pairs) is available, the canonical
``EXPECTED_LOSS`` formula is used.  When only a confidence score exists the
``CONFIDENCE_COMPLEMENT`` fallback (``1.0 - confidence``) is applied instead.
"""

import logging
from enum import Enum

logger = logging.getLogger(__name__)

try:
    from ..mfgc_core import ConfidenceEngine as _CoreConfidenceEngine
except ImportError:
    try:
        from mfgc_core import ConfidenceEngine as _CoreConfidenceEngine
    except ImportError:
        # mfgc_core requires optional heavy dependencies (numpy, scipy).
        # The ConfidenceEngine wrapper below is fully self-contained and does
        # not delegate to _CoreConfidenceEngine at runtime, so a None stub is
        # sufficient to keep the module importable without those deps.
        _CoreConfidenceEngine = None  # type: ignore[assignment,misc]


class MurphyIndexMode(Enum):
    """Calculation mode for the Murphy Index (GAP-2).

    ``EXPECTED_LOSS`` is the canonical definition:
        M_t = Σ_k (L_k × p_k)
    ``CONFIDENCE_COMPLEMENT`` is the fallback used when no risk data exists:
        M_t = 1.0 - confidence
    """

    EXPECTED_LOSS = "expected_loss"
    CONFIDENCE_COMPLEMENT = "confidence_complement"


class _AwaitableDict(dict):
    """A dict that can also be awaited, returning itself."""

    def __await__(self):
        yield
        return self


class ConfidenceEngine:
    """Wrapper around the core ConfidenceEngine with a simplified API for integration tests."""

    def __init__(self):
        self._core = _CoreConfidenceEngine() if _CoreConfidenceEngine is not None else None

    def compute_confidence(self, artifacts):
        """Compute confidence from a list of artifact dicts.

        Each artifact should contain at least ``confidence`` and optionally
        ``type``, ``assumption_id``, ``loss``, and ``probability`` fields.

        Murphy Index (GAP-2):
            Uses the canonical expected-loss formula
            ``M_t = Σ_k (L_k × p_k)`` when any artifact supplies both
            ``loss`` and ``probability`` fields.  Falls back to
            ``1.0 - confidence`` (``CONFIDENCE_COMPLEMENT``) otherwise.

        Returns a dict with ``overall_confidence``, ``murphy_index``,
        ``murphy_index_mode``, and ``assumptions_verified``.  The returned
        dict is also awaitable so callers may use
        ``await engine.compute_confidence(...)`` in async code.
        """
        if not artifacts:
            return _AwaitableDict({
                "overall_confidence": 0.0,
                "murphy_index": 1.0,
                "murphy_index_mode": MurphyIndexMode.CONFIDENCE_COMPLEMENT.value,
                "assumptions_verified": 0,
            })

        # Handle single dict input (e2e test style)
        if isinstance(artifacts, dict):
            conf = artifacts.get("detection_confidence", artifacts.get("confidence", 0.85))
            authority = "high" if artifacts.get("severity") == "high" or artifacts.get("business_impact") == "critical" else "medium"

            # Use expected-loss if risk data present and values are numeric
            loss = artifacts.get("loss")
            prob = artifacts.get("probability")
            if isinstance(loss, (int, float)) and isinstance(prob, (int, float)):
                murphy_index = float(loss) * float(prob)
                mode = MurphyIndexMode.EXPECTED_LOSS.value
            else:
                murphy_index = max(0.0, 1.0 - conf)
                mode = MurphyIndexMode.CONFIDENCE_COMPLEMENT.value

            return _AwaitableDict({
                "confidence": round(conf, 4),
                "authority": authority,
                "overall_confidence": round(conf, 4),
                "murphy_index": round(murphy_index, 4),
                "murphy_index_mode": mode,
            })

        scores = [a.get("confidence", 0.0) for a in artifacts]
        overall = sum(scores) / (len(scores) or 1) if scores else 0.0

        invalidated = [a for a in artifacts if a.get("invalidated")]
        if invalidated:
            overall *= 0.3

        # GAP-2: use canonical expected-loss when risk data is available
        risk_artifacts = [
            a for a in artifacts
            if "loss" in a and "probability" in a
            and isinstance(a["loss"], (int, float))
            and isinstance(a["probability"], (int, float))
        ]
        if risk_artifacts:
            murphy_index = sum(a["loss"] * a["probability"] for a in risk_artifacts)
            murphy_index = min(1.0, murphy_index)
            mode = MurphyIndexMode.EXPECTED_LOSS.value
        else:
            murphy_index = max(0.0, 1.0 - overall)
            mode = MurphyIndexMode.CONFIDENCE_COMPLEMENT.value

        assumptions_verified = sum(
            1 for a in artifacts if a.get("type") == "verified"
        )

        return _AwaitableDict({
            "overall_confidence": round(overall, 4),
            "murphy_index": round(murphy_index, 4),
            "murphy_index_mode": mode,
            "assumptions_verified": assumptions_verified,
        })


__all__ = ['ConfidenceEngine', 'MurphyIndexMode']
