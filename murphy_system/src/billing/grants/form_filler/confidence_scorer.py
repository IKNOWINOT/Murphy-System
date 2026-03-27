"""
Confidence Scorer — Assigns confidence tiers to form field values.
© 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

from src.billing.grants.form_filler.review_session import FilledField, FormDefinition, FormField

TIER_AUTO = "auto_filled"
TIER_REVIEW = "needs_review"
TIER_BLOCKED = "blocked_human_required"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$|^\d{2}/\d{2}/\d{4}$")

_SOURCE_ADJUSTMENTS: Dict[str, float] = {
    "saved_form_data": +0.05,
    "murphy_profile": 0.0,
    "llm_generated": -0.1,
    "computed": -0.05,
    "user_input": +0.1,
}


class ConfidenceScorer:
    def score_field(
        self,
        field: FormField,
        value: Any,
        source: str,
        mapped_confidence: float,
    ) -> Tuple[float, str]:
        if field.legal_certification:
            return (0.0, TIER_BLOCKED)

        if value is None or (isinstance(value, str) and not value.strip()):
            return (0.0, TIER_BLOCKED)

        confidence = mapped_confidence

        # Source adjustment
        confidence += _SOURCE_ADJUSTMENTS.get(source, 0.0)

        # Field type adjustments
        ft = field.field_type
        if ft == "text":
            if len(str(value)) < 20 and source in ("saved_form_data", "murphy_profile"):
                confidence += 0.05
        elif ft == "textarea":
            confidence -= 0.15
        elif ft == "number":
            try:
                float(value)
                confidence += 0.05
            except (ValueError, TypeError):
                confidence -= 0.1
        elif ft == "date":
            if _DATE_RE.match(str(value)):
                confidence += 0.05

        confidence = max(0.0, min(1.0, confidence))

        if confidence >= 0.9:
            return (confidence, TIER_AUTO)
        elif confidence >= 0.5:
            return (confidence, TIER_REVIEW)
        else:
            return (confidence, TIER_BLOCKED)

    def score_all_fields(
        self,
        form_def: FormDefinition,
        mapped_values: Dict[str, Any],
    ) -> List[FilledField]:
        results: List[FilledField] = []
        for field in form_def.fields:
            mapping = mapped_values.get(field.field_id)
            if mapping:
                value = mapping.get("value")
                source = mapping.get("source", "llm_generated")
                mapped_conf = float(mapping.get("confidence", 0.5))
            else:
                value = None
                source = "llm_generated"
                mapped_conf = 0.0

            final_conf, status = self.score_field(field, value, source, mapped_conf)

            reasoning = self._build_reasoning(field, value, source, mapped_conf, final_conf, status)

            results.append(
                FilledField(
                    field_id=field.field_id,
                    value=value,
                    confidence=round(final_conf, 4),
                    source=source,
                    status=status,
                    reasoning=reasoning,
                )
            )
        return results

    def _build_reasoning(
        self,
        field: FormField,
        value: Any,
        source: str,
        mapped_conf: float,
        final_conf: float,
        status: str,
    ) -> str:
        if field.legal_certification:
            return "Legal certification field — must be completed and signed by authorized representative."
        if value is None or (isinstance(value, str) and not value.strip()):
            return "No value found in saved data or profiles. Human input required."
        adj = _SOURCE_ADJUSTMENTS.get(source, 0.0)
        sign = "+" if adj >= 0 else ""
        return (
            f"Source '{source}' (adjustment {sign}{adj:.2f}), "
            f"mapped confidence {mapped_conf:.2f} → final {final_conf:.2f} ({status})."
        )
