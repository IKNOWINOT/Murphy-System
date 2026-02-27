"""
Freelancer Validator — Criteria Engine

Builds structured validation criteria, formats them into deliverable
instructions for freelancers, and scores incoming responses against
the criteria to produce a normalized verdict.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .models import (
    CriterionItem,
    CriterionScore,
    FreelancerResponse,
    ResponseVerdict,
    ValidationCriteria,
)

logger = logging.getLogger(__name__)


class CriteriaEngine:
    """
    Manages validation criteria lifecycle:

    1. **Build** — create criteria sets from templates or ad-hoc specs.
    2. **Format** — render criteria into human-readable instructions.
    3. **Score** — evaluate a ``FreelancerResponse`` against its criteria
       and compute the weighted overall score + verdict.
    """

    # ── Build ────────────────────────────────────────────────────────

    @staticmethod
    def build_criteria(
        title: str,
        items: List[Dict[str, Any]],
        pass_threshold: float = 0.7,
        description: str = "",
    ) -> ValidationCriteria:
        """
        Build a ``ValidationCriteria`` from a list of item dicts.

        Each dict in *items* must contain at least ``name`` and
        ``description``.  Optional keys: ``scoring_type``, ``required``,
        ``weight``.
        """
        criterion_items = [
            CriterionItem(
                name=item["name"],
                description=item["description"],
                scoring_type=item.get("scoring_type", "boolean"),
                required=item.get("required", True),
                weight=item.get("weight", 1.0),
            )
            for item in items
        ]
        return ValidationCriteria(
            title=title,
            description=description,
            items=criterion_items,
            pass_threshold=pass_threshold,
        )

    # ── Format ───────────────────────────────────────────────────────

    @staticmethod
    def format_instructions(criteria: ValidationCriteria) -> str:
        """
        Render criteria into human-readable instructions suitable for
        posting to a freelance platform.
        """
        lines = [
            f"# Validation Task: {criteria.title}",
            "",
            criteria.description,
            "",
            "## Criteria (answer ALL required items)",
            "",
        ]
        for idx, item in enumerate(criteria.items, 1):
            req = "REQUIRED" if item.required else "optional"
            lines.append(
                f"{idx}. **{item.name}** [{req}] — {item.description} "
                f"(answer type: {item.scoring_type})"
            )
        lines += [
            "",
            "## Response Format (JSON)",
            "",
            "```json",
            "{",
            '  "verdict": "pass | fail | needs_revision | inconclusive",',
            '  "criterion_scores": [',
            '    {"criterion_id": "<id>", "value": <bool|int|string>, "notes": "..."}',
            "  ],",
            '  "feedback": "overall comments",',
            '  "evidence": {"urls": [], "screenshots": []}',
            "}",
            "```",
            "",
            f"A score ≥ {criteria.pass_threshold:.0%} on the weighted criteria "
            f"is required for a PASS verdict.",
        ]
        return "\n".join(lines)

    # ── Score ────────────────────────────────────────────────────────

    def score_response(
        self,
        response: FreelancerResponse,
        criteria: ValidationCriteria,
    ) -> FreelancerResponse:
        """
        Compute ``overall_score`` and normalize ``verdict`` for a
        ``FreelancerResponse`` based on its ``criterion_scores``.

        Mutates and returns the same response object.
        """
        score_map: Dict[str, CriterionScore] = {
            cs.criterion_id: cs for cs in response.criterion_scores
        }

        total_weight = 0.0
        weighted_sum = 0.0
        missing_required = []

        for item in criteria.items:
            cs = score_map.get(item.criterion_id)
            if cs is None:
                if item.required:
                    missing_required.append(item.criterion_id)
                continue

            normalized = self._normalize_value(cs.value, item.scoring_type)
            weighted_sum += normalized * item.weight
            total_weight += item.weight

        if missing_required:
            logger.warning(
                "Response %s missing required criteria: %s",
                response.response_id,
                missing_required,
            )

        overall = weighted_sum / total_weight if total_weight > 0 else 0.0
        response.overall_score = round(overall, 4)

        # Derive verdict from score if the validator left INCONCLUSIVE
        if response.verdict == ResponseVerdict.INCONCLUSIVE:
            if missing_required:
                response.verdict = ResponseVerdict.NEEDS_REVISION
            elif overall >= criteria.pass_threshold:
                response.verdict = ResponseVerdict.PASS
            else:
                response.verdict = ResponseVerdict.FAIL

        return response

    # ── Validation ───────────────────────────────────────────────────

    @staticmethod
    def validate_response_format(
        response: FreelancerResponse,
        criteria: ValidationCriteria,
    ) -> List[str]:
        """
        Check that a response conforms to the expected format.

        Returns a list of error messages (empty == valid).
        """
        errors: List[str] = []
        known_ids = {item.criterion_id for item in criteria.items}
        required_ids = {
            item.criterion_id for item in criteria.items if item.required
        }
        submitted_ids = {cs.criterion_id for cs in response.criterion_scores}

        for cid in submitted_ids - known_ids:
            errors.append(f"Unknown criterion_id: {cid}")

        for cid in required_ids - submitted_ids:
            errors.append(f"Missing required criterion: {cid}")

        if not isinstance(response.verdict, ResponseVerdict):
            errors.append(f"Invalid verdict: {response.verdict}")

        return errors

    # ── Internals ────────────────────────────────────────────────────

    @staticmethod
    def _normalize_value(value: Any, scoring_type: str) -> float:
        """Normalize a criterion score to a 0–1 float."""
        if scoring_type == "boolean":
            if isinstance(value, bool):
                return 1.0 if value else 0.0
            return 1.0 if str(value).lower() in ("true", "1", "yes") else 0.0

        if scoring_type == "scale_1_5":
            try:
                return (float(value) - 1) / 4.0
            except (TypeError, ValueError):
                return 0.0

        if scoring_type == "scale_1_10":
            try:
                return (float(value) - 1) / 9.0
            except (TypeError, ValueError):
                return 0.0

        # text — presence counts as full score
        return 1.0 if value else 0.0
