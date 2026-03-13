"""Enforces compliance rules on avatar interactions."""

import logging
import re
import uuid
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Dict, List, Optional

from .avatar_models import ComplianceViolation

logger = logging.getLogger(__name__)


class ComplianceGuard:
    """Enforces compliance rules on avatar interactions."""

    RULES = {
        "no_pii_disclosure": "Avatar must not disclose personally identifiable information",
        "no_financial_advice": "Avatar must not provide specific financial advice",
        "no_medical_advice": "Avatar must not provide specific medical advice",
        "content_safety": "Avatar must not generate harmful or inappropriate content",
        "data_retention": "Avatar interactions must comply with data retention policies",
    }

    def __init__(self) -> None:
        self._violations: List[ComplianceViolation] = []
        self._lock = Lock()
        self._blocked_patterns: List[re.Pattern] = [
            re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),  # SSN pattern
            re.compile(r"\b\d{16}\b"),  # Credit card pattern
        ]

    def check_content(self, avatar_id: str, content: str) -> List[ComplianceViolation]:
        """Check content for compliance violations."""
        violations: List[ComplianceViolation] = []
        for pattern in self._blocked_patterns:
            if pattern.search(content):
                v = ComplianceViolation(
                    violation_id=str(uuid.uuid4()),
                    avatar_id=avatar_id,
                    rule="no_pii_disclosure",
                    description=f"PII pattern detected: {pattern.pattern}",
                    severity="high",
                    timestamp=datetime.now(timezone.utc),
                )
                violations.append(v)
        with self._lock:
            self._violations.extend(violations)
        return violations

    def check_prompt(self, avatar_id: str, prompt: str) -> List[ComplianceViolation]:
        """Check prompt for compliance issues before sending to LLM."""
        violations: List[ComplianceViolation] = []
        lower = prompt.lower()

        financial_keywords = ["invest in", "buy stock", "sell stock", "financial advice"]
        for kw in financial_keywords:
            if kw in lower:
                v = ComplianceViolation(
                    violation_id=str(uuid.uuid4()),
                    avatar_id=avatar_id,
                    rule="no_financial_advice",
                    description=f"Financial advice keyword detected: '{kw}'",
                    severity="medium",
                    timestamp=datetime.now(timezone.utc),
                )
                violations.append(v)
                break

        medical_keywords = ["prescribe", "diagnosis", "medical advice"]
        for kw in medical_keywords:
            if kw in lower:
                v = ComplianceViolation(
                    violation_id=str(uuid.uuid4()),
                    avatar_id=avatar_id,
                    rule="no_medical_advice",
                    description=f"Medical advice keyword detected: '{kw}'",
                    severity="medium",
                    timestamp=datetime.now(timezone.utc),
                )
                violations.append(v)
                break

        # Also check for PII in prompts
        violations.extend(self.check_content(avatar_id, prompt))
        with self._lock:
            # Only add the non-PII violations (PII already added in check_content)
            self._violations.extend(
                v for v in violations if v.rule != "no_pii_disclosure"
            )
        return violations

    def get_violations(
        self, avatar_id: Optional[str] = None
    ) -> List[ComplianceViolation]:
        """Get recorded violations, optionally filtered by avatar."""
        with self._lock:
            violations = list(self._violations)
        if avatar_id:
            violations = [v for v in violations if v.avatar_id == avatar_id]
        return violations

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            total = len(self._violations)
            unresolved = sum(1 for v in self._violations if not v.resolved)
        return {
            "total_violations": total,
            "unresolved_violations": unresolved,
            "rules_count": len(self.RULES),
        }
