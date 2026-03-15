"""Bridge: src.bridge_layer.hypothesis_intake

Provides a simplified HypothesisIntakeService wrapper with a
``process_hypothesis`` helper expected by integration tests.
"""

import logging
import re
from typing import Any, Dict, List

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)


class HypothesisIntakeService:
    """Simplified intake service for integration tests."""

    def __init__(self):
        self._log = []

    def process_hypothesis(self, hypothesis: Dict[str, Any]) -> Dict[str, Any]:
        """Process a hypothesis dict, extracting assumptions and
        generating verification requests.

        Returns a dict with ``valid``, ``sandbox_constraints_enforced``,
        ``assumptions``, ``verification_requests``, and optionally ``error``.
        """

        status = hypothesis.get("status", "sandbox")
        confidence = hypothesis.get("confidence")

        # Sandbox constraint: confidence must be None while in sandbox
        if status == "sandbox" and confidence is not None:
            return {
                "valid": False,
                "sandbox_constraints_enforced": True,
                "error": "Sandbox hypothesis cannot have pre-set confidence",
                "assumptions": [],
                "verification_requests": [],
            }

        # Extract assumptions from plan_summary
        plan = hypothesis.get("plan_summary", "")
        assumptions = self._extract_assumptions(plan)

        verification_requests = [
            {
                "request_id": f"vr_{i:03d}",
                "assumption": a,
                "status": "pending",
            }
            for i, a in enumerate(assumptions, 1)
        ]

        result = {
            "valid": True,
            "sandbox_constraints_enforced": True,
            "assumptions": assumptions,
            "verification_requests": verification_requests,
        }
        capped_append(self._log, result)
        return result

    # ------------------------------------------------------------------
    @staticmethod
    def _extract_assumptions(text: str) -> List[str]:
        """Pull out numbered assumptions from the plan text."""
        # Patterns like "Assumes: 1) …, 2) …" or "Assumption: …"
        parts = re.split(r'\d+\)', text)
        assumptions = [p.strip().rstrip(",").strip() for p in parts[1:] if p.strip()]
        if not assumptions:
            # fallback: split on comma after "Assumes:"
            if "assumes:" in text.lower():
                after = text.lower().split("assumes:")[-1]
                assumptions = [a.strip().rstrip(",").strip() for a in after.split(",") if a.strip()]
        return assumptions if assumptions else ["(implicit assumption)"]


__all__ = ['HypothesisIntakeService']
