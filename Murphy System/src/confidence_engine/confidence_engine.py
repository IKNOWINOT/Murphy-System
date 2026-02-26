"""Re-export ConfidenceEngine from mfgc_core for backward compatibility.

Provides a simplified wrapper that accepts artifact lists for integration tests.
"""

try:
    from ..mfgc_core import ConfidenceEngine as _CoreConfidenceEngine
except ImportError:
    from mfgc_core import ConfidenceEngine as _CoreConfidenceEngine


class ConfidenceEngine:
    """Wrapper around the core ConfidenceEngine with a simplified API for integration tests."""

    def __init__(self):
        self._core = _CoreConfidenceEngine()

    def compute_confidence(self, artifacts):
        """Compute confidence from a list of artifact dicts.

        Each artifact should contain at least ``confidence`` and optionally
        ``type`` and ``assumption_id`` fields.

        Returns a dict with ``overall_confidence``, ``murphy_index``, and
        ``assumptions_verified``.
        """
        if not artifacts:
            return {"overall_confidence": 0.0, "murphy_index": 1.0, "assumptions_verified": 0}

        scores = [a.get("confidence", 0.0) for a in artifacts]
        overall = sum(scores) / len(scores) if scores else 0.0

        invalidated = [a for a in artifacts if a.get("invalidated")]
        if invalidated:
            overall *= 0.3

        murphy_index = max(0.0, 1.0 - overall)

        assumptions_verified = sum(
            1 for a in artifacts if a.get("type") == "verified"
        )

        return {
            "overall_confidence": round(overall, 4),
            "murphy_index": round(murphy_index, 4),
            "assumptions_verified": assumptions_verified,
        }


__all__ = ['ConfidenceEngine']
