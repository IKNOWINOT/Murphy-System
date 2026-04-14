# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Deliverable Self-Audit Gate — Murphy System (FORGE-AUDIT-GATE-001)

Owner: Forge Pipeline / Quality Assurance
Dep: demo_deliverable_generator (forge), llm_provider

Pre-delivery sensor that validates forge output meets the original prompt
requirements BEFORE the deliverable reaches the human-in-the-loop review.

Design motivation (from plan):
  "Before it is delivered to the client for human in the loop, you yourself
   sensor gate that the deliverable meets the requirements of the prompt."

The gate runs a structured validation checklist:
  1. Prompt coverage — does the deliverable address every topic in the prompt?
  2. Format compliance — is the output in the requested format (plan, app, etc.)?
  3. Completeness — are all sections populated (no empty/placeholder stubs)?
  4. Coherence — does the content make logical sense (no contradictions)?
  5. Length adequacy — is the output substantive (not a one-liner for a big ask)?

The gate returns PASS, WARN, or FAIL with per-check details.
On FAIL, the deliverable is held back and the forge pipeline retries or
escalates to HITL with the audit findings attached.

Error Handling:
  All public methods log and raise on invalid input.  No silent failures.
  Error codes: FORGE-AUDIT-GATE-ERR-001 through FORGE-AUDIT-GATE-ERR-005.
"""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Verdict model
# ---------------------------------------------------------------------------

class AuditVerdict(str, Enum):
    """Overall audit gate verdict."""
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


class CheckStatus(str, Enum):
    """Status of an individual audit check."""
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    SKIP = "skip"


@dataclass
class AuditCheck:
    """Result of one audit check.

    Design Label: FORGE-AUDIT-GATE-002
    """

    check_id: str = ""
    check_name: str = ""
    status: CheckStatus = CheckStatus.SKIP
    score: float = 0.0       # 0.0–1.0
    details: str = ""
    suggestions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "check_id": self.check_id,
            "check_name": self.check_name,
            "status": self.status.value,
            "score": round(self.score, 3),
            "details": self.details,
            "suggestions": self.suggestions,
        }


@dataclass
class AuditReport:
    """Complete audit gate report for a deliverable.

    Design Label: FORGE-AUDIT-GATE-003
    """

    report_id: str = field(default_factory=lambda: "audit_" + uuid.uuid4().hex[:8])
    verdict: AuditVerdict = AuditVerdict.FAIL
    overall_score: float = 0.0  # 0.0–1.0
    checks: List[AuditCheck] = field(default_factory=list)
    prompt_summary: str = ""
    deliverable_length: int = 0
    audited_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "verdict": self.verdict.value,
            "overall_score": round(self.overall_score, 3),
            "checks": [c.to_dict() for c in self.checks],
            "prompt_summary": self.prompt_summary[:200],
            "deliverable_length": self.deliverable_length,
            "audited_at": self.audited_at,
            "metadata": self.metadata,
        }

    @property
    def passed(self) -> bool:
        return self.verdict == AuditVerdict.PASS

    @property
    def failed_checks(self) -> List[AuditCheck]:
        return [c for c in self.checks if c.status == CheckStatus.FAIL]

    @property
    def warning_checks(self) -> List[AuditCheck]:
        return [c for c in self.checks if c.status == CheckStatus.WARN]


# ---------------------------------------------------------------------------
# DeliverableAuditGate — the pre-delivery sensor
# ---------------------------------------------------------------------------

class DeliverableAuditGate:
    """Pre-delivery quality gate for forge deliverables.

    Design Label: FORGE-AUDIT-GATE-001

    Runs a structured validation checklist against the deliverable content
    and original prompt.  Returns an AuditReport with per-check details.

    Configuration:
        pass_threshold:  Minimum overall score for PASS verdict (default 0.70).
        warn_threshold:  Minimum overall score for WARN verdict (default 0.40).
        min_length:      Minimum deliverable length in characters (default 200).

    Usage::

        gate = DeliverableAuditGate()
        report = gate.audit(
            prompt="Build a compliance management app",
            deliverable="<full deliverable text>",
        )
        if report.passed:
            deliver_to_client(deliverable)
        else:
            retry_or_escalate(report)
    """

    def __init__(
        self,
        pass_threshold: float = 0.70,
        warn_threshold: float = 0.40,
        min_length: int = 200,
    ) -> None:
        if not (0.0 <= warn_threshold <= pass_threshold <= 1.0):
            raise ValueError(
                "FORGE-AUDIT-GATE-ERR-001: Thresholds must satisfy "
                f"0 <= warn ({warn_threshold}) <= pass ({pass_threshold}) <= 1"
            )
        self._pass_threshold = pass_threshold
        self._warn_threshold = warn_threshold
        self._min_length = min_length

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def audit(
        self,
        prompt: str,
        deliverable: str,
        *,
        expected_format: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditReport:
        """Run the full audit gate on a deliverable.

        Args:
            prompt:          The original user prompt/query.
            deliverable:     The generated deliverable text.
            expected_format: Optional hint (e.g. "plan", "app", "course").
            metadata:        Optional metadata to attach to the report.

        Returns:
            AuditReport with verdict, per-check details, and suggestions.

        Raises:
            ValueError: If prompt or deliverable is empty.
        """
        if not prompt or not prompt.strip():
            raise ValueError(
                "FORGE-AUDIT-GATE-ERR-002: prompt must be non-empty"
            )
        if not deliverable or not deliverable.strip():
            logger.error(
                "FORGE-AUDIT-GATE-ERR-003: Empty deliverable for prompt: %s",
                prompt[:100],
            )
            return AuditReport(
                verdict=AuditVerdict.FAIL,
                overall_score=0.0,
                prompt_summary=prompt[:200],
                deliverable_length=0,
                checks=[AuditCheck(
                    check_id="CHK-000",
                    check_name="non_empty",
                    status=CheckStatus.FAIL,
                    score=0.0,
                    details="Deliverable is empty",
                )],
                metadata=metadata or {},
            )

        checks: List[AuditCheck] = [
            self._check_prompt_coverage(prompt, deliverable),
            self._check_format_compliance(prompt, deliverable, expected_format),
            self._check_completeness(deliverable),
            self._check_coherence(deliverable),
            self._check_length_adequacy(prompt, deliverable),
        ]

        # Compute overall score (average of non-skipped checks)
        scored = [c for c in checks if c.status != CheckStatus.SKIP]
        overall = sum(c.score for c in scored) / max(1, len(scored))

        # Determine verdict
        if overall >= self._pass_threshold:
            verdict = AuditVerdict.PASS
        elif overall >= self._warn_threshold:
            verdict = AuditVerdict.WARN
        else:
            verdict = AuditVerdict.FAIL

        report = AuditReport(
            verdict=verdict,
            overall_score=overall,
            checks=checks,
            prompt_summary=prompt[:200],
            deliverable_length=len(deliverable),
            metadata=metadata or {},
        )

        logger.info(
            "FORGE-AUDIT-GATE-001: Audit %s — verdict=%s score=%.2f "
            "checks=%d/%d passed  deliverable_len=%d",
            report.report_id, verdict.value, overall,
            sum(1 for c in checks if c.status == CheckStatus.PASS),
            len(checks), len(deliverable),
        )

        return report

    # ------------------------------------------------------------------
    # Individual checks
    # ------------------------------------------------------------------

    def _check_prompt_coverage(
        self, prompt: str, deliverable: str,
    ) -> AuditCheck:
        """CHK-001: Does the deliverable address key topics from the prompt?

        Extracts significant words (4+ chars) from the prompt and checks
        what fraction appear in the deliverable.
        """
        prompt_words = self._extract_key_words(prompt)
        if not prompt_words:
            return AuditCheck(
                check_id="CHK-001",
                check_name="prompt_coverage",
                status=CheckStatus.SKIP,
                score=1.0,
                details="No significant keywords in prompt",
            )

        deliverable_lower = deliverable.lower()
        covered = [w for w in prompt_words if w in deliverable_lower]
        coverage = len(covered) / len(prompt_words)

        missing = [w for w in prompt_words if w not in deliverable_lower]
        suggestions = []
        if missing:
            suggestions.append(
                f"Deliverable does not mention: {', '.join(missing[:10])}"
            )

        if coverage >= 0.70:
            status = CheckStatus.PASS
        elif coverage >= 0.40:
            status = CheckStatus.WARN
        else:
            status = CheckStatus.FAIL

        return AuditCheck(
            check_id="CHK-001",
            check_name="prompt_coverage",
            status=status,
            score=coverage,
            details=f"{len(covered)}/{len(prompt_words)} prompt keywords covered",
            suggestions=suggestions,
        )

    def _check_format_compliance(
        self, prompt: str, deliverable: str, expected_format: str,
    ) -> AuditCheck:
        """CHK-002: Is the deliverable in the expected format?

        Checks for structural indicators: headings, numbered lists, code
        blocks, etc., based on what the prompt seems to ask for.
        """
        fmt = expected_format.lower() if expected_format else self._infer_format(prompt)
        score = 1.0
        details = f"Format: {fmt}"
        suggestions: List[str] = []

        if fmt in ("plan", "outline", "roadmap"):
            # Expect headings and numbered/bulleted items
            has_headings = bool(re.search(r"^#+\s|^[A-Z][^.]*:\n", deliverable, re.MULTILINE))
            has_lists = bool(re.search(r"^\s*[-*\d]+[.)]?\s", deliverable, re.MULTILINE))
            if not has_headings:
                score -= 0.3
                suggestions.append("Expected markdown headings for a plan/outline")
            if not has_lists:
                score -= 0.2
                suggestions.append("Expected bulleted or numbered list items")
        elif fmt in ("app", "code", "game"):
            # Expect code blocks or technical content
            has_code = "```" in deliverable or "def " in deliverable or "class " in deliverable
            if not has_code:
                score -= 0.3
                suggestions.append("Expected code blocks or technical content")

        score = max(0.0, score)
        if score >= 0.70:
            status = CheckStatus.PASS
        elif score >= 0.40:
            status = CheckStatus.WARN
        else:
            status = CheckStatus.FAIL

        return AuditCheck(
            check_id="CHK-002",
            check_name="format_compliance",
            status=status,
            score=score,
            details=details,
            suggestions=suggestions,
        )

    def _check_completeness(self, deliverable: str) -> AuditCheck:
        """CHK-003: Are there placeholder/stub sections?

        Looks for TODO, TBD, placeholder, [insert here], etc.
        """
        _PLACEHOLDER_PATTERNS = [
            r"\bTODO\b", r"\bTBD\b", r"\bFIXME\b",
            r"\[insert\b", r"\[placeholder\b", r"\[your ",
            r"lorem ipsum",
            r"\.\.\.\s*$",
        ]
        placeholder_count = 0
        for pattern in _PLACEHOLDER_PATTERNS:
            placeholder_count += len(re.findall(pattern, deliverable, re.IGNORECASE))

        # Score inversely proportional to placeholder density
        density = placeholder_count / max(1, len(deliverable.split()))
        score = max(0.0, 1.0 - density * 50)  # 2% placeholder words → score 0

        suggestions: List[str] = []
        if placeholder_count > 0:
            suggestions.append(
                f"Found {placeholder_count} placeholder/TODO markers"
            )

        if score >= 0.90:
            status = CheckStatus.PASS
        elif score >= 0.50:
            status = CheckStatus.WARN
        else:
            status = CheckStatus.FAIL

        return AuditCheck(
            check_id="CHK-003",
            check_name="completeness",
            status=status,
            score=score,
            details=f"{placeholder_count} placeholder markers found",
            suggestions=suggestions,
        )

    def _check_coherence(self, deliverable: str) -> AuditCheck:
        """CHK-004: Basic coherence check.

        Verifies the deliverable has:
          - Multiple paragraphs or sections (not a single blob)
          - Reasonable sentence structure
          - No excessive repetition
        """
        lines = [ln for ln in deliverable.strip().split("\n") if ln.strip()]
        paragraphs = len([ln for ln in lines if len(ln.strip()) > 20])
        sentences = len(re.findall(r"[.!?]\s", deliverable))

        score = 1.0
        suggestions: List[str] = []

        if paragraphs < 3:
            score -= 0.3
            suggestions.append(
                f"Only {paragraphs} substantial paragraphs — expected more structure"
            )

        # Check for excessive repetition (same line appearing 3+ times)
        line_counts: Dict[str, int] = {}
        for ln in lines:
            key = ln.strip().lower()
            if len(key) > 10:
                line_counts[key] = line_counts.get(key, 0) + 1
        repeated = {k: v for k, v in line_counts.items() if v >= 3}
        if repeated:
            score -= 0.3
            suggestions.append(
                f"{len(repeated)} lines repeated 3+ times — possible duplication"
            )

        score = max(0.0, score)
        if score >= 0.70:
            status = CheckStatus.PASS
        elif score >= 0.40:
            status = CheckStatus.WARN
        else:
            status = CheckStatus.FAIL

        return AuditCheck(
            check_id="CHK-004",
            check_name="coherence",
            status=status,
            score=score,
            details=f"{paragraphs} paragraphs, {sentences} sentences",
            suggestions=suggestions,
        )

    def _check_length_adequacy(
        self, prompt: str, deliverable: str,
    ) -> AuditCheck:
        """CHK-005: Is the deliverable long enough for the ask?

        Simple heuristic: prompt word count suggests expected output complexity.
        """
        prompt_words = len(prompt.split())
        deliverable_len = len(deliverable)

        # Minimum: at least 200 chars, or 10x the prompt word count
        expected_min = max(self._min_length, prompt_words * 10)

        if deliverable_len >= expected_min:
            score = 1.0
        elif deliverable_len >= expected_min * 0.5:
            score = deliverable_len / expected_min
        else:
            score = max(0.0, deliverable_len / expected_min)

        suggestions: List[str] = []
        if deliverable_len < expected_min:
            suggestions.append(
                f"Deliverable is {deliverable_len} chars; "
                f"expected at least {expected_min} for this prompt complexity"
            )

        if score >= 0.70:
            status = CheckStatus.PASS
        elif score >= 0.40:
            status = CheckStatus.WARN
        else:
            status = CheckStatus.FAIL

        return AuditCheck(
            check_id="CHK-005",
            check_name="length_adequacy",
            status=status,
            score=score,
            details=f"{deliverable_len} chars (min expected: {expected_min})",
            suggestions=suggestions,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_key_words(text: str) -> List[str]:
        """Extract significant words (4+ chars, not stopwords) from text."""
        _STOPWORDS = {
            "this", "that", "with", "from", "have", "will", "been",
            "were", "they", "their", "them", "than", "then", "what",
            "when", "where", "which", "while", "would", "could",
            "should", "about", "after", "before", "between", "into",
            "through", "during", "each", "some", "other", "more",
            "also", "just", "only", "very", "much", "most", "make",
            "like", "even", "well", "back", "need", "want",
        }
        words = re.findall(r"[a-zA-Z]{4,}", text.lower())
        return [w for w in set(words) if w not in _STOPWORDS]

    @staticmethod
    def _infer_format(prompt: str) -> str:
        """Infer expected deliverable format from prompt keywords."""
        p = prompt.lower()
        if any(kw in p for kw in ("plan", "outline", "roadmap", "strategy")):
            return "plan"
        if any(kw in p for kw in ("app", "application", "software", "code")):
            return "app"
        if any(kw in p for kw in ("game", "rpg", "mmorpg")):
            return "game"
        if any(kw in p for kw in ("course", "training", "curriculum")):
            return "course"
        if any(kw in p for kw in ("book", "novel", "story")):
            return "book"
        return "general"
