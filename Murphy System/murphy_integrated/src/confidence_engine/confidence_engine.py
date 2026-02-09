"""
Compatibility Confidence Engine

Provides a lightweight confidence engine API expected by integration tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Union
import uuid


class ConfidenceResult(dict):
    """Dictionary-like confidence result that can be awaited in async tests."""

    def __await__(self):
        async def _wrap():
            return self

        return _wrap().__await__()


@dataclass
class ConfidenceAssessment:
    confidence: float
    authority: str
    overall_confidence: float
    murphy_index: float
    evidence_count: int
    assessment_id: str

    def to_result(self) -> ConfidenceResult:
        return ConfidenceResult(
            confidence=self.confidence,
            authority=self.authority,
            overall_confidence=self.overall_confidence,
            murphy_index=self.murphy_index,
            evidence_count=self.evidence_count,
            assessment_id=self.assessment_id,
        )


class ConfidenceEngine:
    """
    Lightweight confidence engine for test harnesses.

    Supports both synchronous and async invocation by returning an awaitable dict.
    """

    def compute_confidence(
        self,
        evidence: Union[Mapping[str, Any], Iterable[Mapping[str, Any]]],
    ) -> ConfidenceResult | Dict[str, Any]:
        if isinstance(evidence, list):
            if evidence:
                avg_confidence = sum(float(item.get("confidence", 0.0)) for item in evidence) / len(evidence)
            else:
                avg_confidence = 0.0
            return {
                "overall_confidence": avg_confidence,
                "assumptions_verified": len(evidence),
            }
        assessment = self._build_assessment(evidence)
        result = assessment.to_result()
        result["assumptions_verified"] = 0
        return result

    def _build_assessment(
        self,
        evidence: Union[Mapping[str, Any], Iterable[Mapping[str, Any]]],
    ) -> ConfidenceAssessment:
        if isinstance(evidence, Mapping):
            explicit_confidence = evidence.get("confidence") or evidence.get("detection_confidence")
            if explicit_confidence is None:
                numeric_values = [
                    float(value)
                    for value in evidence.values()
                    if isinstance(value, (int, float)) and 0.0 <= float(value) <= 1.0
                ]
                confidence = sum(numeric_values) / len(numeric_values) if numeric_values else 0.85
                if "order_complexity" in evidence:
                    confidence = min(confidence, 0.8)
            else:
                confidence = float(explicit_confidence)
            severity = str(evidence.get("severity", "")).lower()
            confidence = min(1.0, max(0.0, confidence))
            authority = self._authority_from_confidence(confidence, severity)
            return ConfidenceAssessment(
                confidence=confidence,
                authority=authority,
                overall_confidence=confidence,
                murphy_index=max(0.0, 1.0 - confidence),
                evidence_count=1,
                assessment_id=str(uuid.uuid4()),
            )

        artifacts: List[Mapping[str, Any]] = list(evidence)
        if not artifacts:
            return ConfidenceAssessment(
                confidence=0.0,
                authority="low",
                overall_confidence=0.0,
                murphy_index=1.0,
                evidence_count=0,
                assessment_id=str(uuid.uuid4()),
            )

        confidences = [float(item.get("confidence", 0.5)) for item in artifacts]
        average_confidence = sum(confidences) / len(confidences)
        authority = self._authority_from_confidence(average_confidence)
        return ConfidenceAssessment(
            confidence=average_confidence,
            authority=authority,
            overall_confidence=average_confidence,
            murphy_index=max(0.0, 1.0 - average_confidence),
            evidence_count=len(confidences),
            assessment_id=str(uuid.uuid4()),
        )

    @staticmethod
    def _authority_from_confidence(confidence: float, severity: str = "") -> str:
        if severity in {"critical", "high"} and confidence >= 0.85:
            return "high"
        if confidence >= 0.85:
            return "high"
        if confidence >= 0.6:
            return "medium"
        return "low"
