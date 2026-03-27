# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Wingman Protocol for Murphy System Runtime

This module implements an executor/validator pairing protocol where each
task is assigned a "wingman" pair consisting of:
- An executor agent responsible for producing output
- A deterministic validator that independently checks executor outputs
  against a set of validation rules before they are released

Key capabilities:
- Executor/validator pairing per subject or task
- Reusable runbooks defining domain-specific validation rules
- Built-in checks for output presence, PII, confidence, budget, and gates
- Full validation history tracking
- Thread-safe operation
"""

import logging
import re
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ValidationSeverity(str, Enum):
    """Severity level for a validation rule."""
    BLOCK = "block"
    WARN = "warn"
    INFO = "info"


@dataclass
class ValidationRule:
    """A single validation rule within a runbook."""
    rule_id: str
    description: str
    check_fn_name: str
    severity: ValidationSeverity
    applicable_domains: List[str] = field(default_factory=list)


@dataclass
class ValidationResult:
    """The result of evaluating one validation rule against an output."""
    rule_id: str
    passed: bool
    severity: ValidationSeverity
    message: str
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ExecutionRunbook:
    """A reusable set of validation rules scoped to a domain."""
    runbook_id: str
    name: str
    domain: str
    validation_rules: List[ValidationRule] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class WingmanPair:
    """An executor/validator pairing for a given subject."""
    pair_id: str
    subject: str
    executor_id: str
    validator_id: str
    runbook_id: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ------------------------------------------------------------------
# Built-in validation checks
# ------------------------------------------------------------------

class BuiltinChecks:
    """Static methods implementing the default validation checks."""

    @staticmethod
    def check_has_output(output: Dict[str, Any]) -> ValidationResult:
        """Output dict must have a non-empty 'result' key."""
        result_val = output.get("result")
        passed = bool(result_val)
        return ValidationResult(
            rule_id="check_has_output",
            passed=passed,
            severity=ValidationSeverity.BLOCK,
            message="Output contains a non-empty result" if passed else "Output is missing or empty 'result' key",
        )

    @staticmethod
    def check_no_pii(output: Dict[str, Any]) -> ValidationResult:
        """Output must not contain patterns matching email, SSN, or phone."""
        text = str(output)
        pii_patterns = [
            r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",  # email
            r"\b\d{3}-\d{2}-\d{4}\b",                                # SSN
            r"\b\d{3}[.\-]\d{3}[.\-]\d{4}\b",                        # phone
        ]
        found: List[str] = []
        for pattern in pii_patterns:
            if re.search(pattern, text):
                found.append(pattern)
        passed = len(found) == 0
        return ValidationResult(
            rule_id="check_no_pii",
            passed=passed,
            severity=ValidationSeverity.BLOCK,
            message="No PII detected" if passed else f"Potential PII detected ({len(found)} pattern(s) matched)",
        )

    @staticmethod
    def check_confidence_threshold(output: Dict[str, Any]) -> ValidationResult:
        """If output has 'confidence', it must be >= 0.5."""
        confidence = output.get("confidence")
        if confidence is None:
            return ValidationResult(
                rule_id="check_confidence_threshold",
                passed=True,
                severity=ValidationSeverity.WARN,
                message="No confidence value present; skipping check",
            )
        passed = float(confidence) >= 0.5
        return ValidationResult(
            rule_id="check_confidence_threshold",
            passed=passed,
            severity=ValidationSeverity.WARN,
            message=f"Confidence {confidence} meets threshold" if passed else f"Confidence {confidence} is below 0.5 threshold",
        )

    @staticmethod
    def check_budget_limit(output: Dict[str, Any]) -> ValidationResult:
        """If output has 'cost', it must be <= budget from output metadata."""
        cost = output.get("cost")
        budget = output.get("budget")
        if cost is None:
            return ValidationResult(
                rule_id="check_budget_limit",
                passed=True,
                severity=ValidationSeverity.BLOCK,
                message="No cost value present; skipping check",
            )
        if budget is None:
            return ValidationResult(
                rule_id="check_budget_limit",
                passed=False,
                severity=ValidationSeverity.BLOCK,
                message="Cost is present but no budget defined",
            )
        passed = float(cost) <= float(budget)
        return ValidationResult(
            rule_id="check_budget_limit",
            passed=passed,
            severity=ValidationSeverity.BLOCK,
            message=f"Cost {cost} within budget {budget}" if passed else f"Cost {cost} exceeds budget {budget}",
        )

    @staticmethod
    def check_gate_clearance(output: Dict[str, Any]) -> ValidationResult:
        """If output has 'gates', all must have 'passed' == True."""
        gates = output.get("gates")
        if gates is None:
            return ValidationResult(
                rule_id="check_gate_clearance",
                passed=True,
                severity=ValidationSeverity.INFO,
                message="No gates present; skipping check",
            )
        failed_gates = [g for g in gates if not g.get("passed")]
        passed = len(failed_gates) == 0
        return ValidationResult(
            rule_id="check_gate_clearance",
            passed=passed,
            severity=ValidationSeverity.INFO,
            message="All gates passed" if passed else f"{len(failed_gates)} gate(s) did not pass",
        )


# Map from check function names to callables
_BUILTIN_CHECK_REGISTRY: Dict[str, Any] = {
    "check_has_output": BuiltinChecks.check_has_output,
    "check_no_pii": BuiltinChecks.check_no_pii,
    "check_confidence_threshold": BuiltinChecks.check_confidence_threshold,
    "check_budget_limit": BuiltinChecks.check_budget_limit,
    "check_gate_clearance": BuiltinChecks.check_gate_clearance,
}


def _build_default_runbook() -> ExecutionRunbook:
    """Construct the pre-registered default runbook."""
    return ExecutionRunbook(
        runbook_id="default",
        name="Default Validation Runbook",
        domain="general",
        validation_rules=[
            ValidationRule(
                rule_id="check_has_output",
                description="Ensure output contains a non-empty result",
                check_fn_name="check_has_output",
                severity=ValidationSeverity.BLOCK,
                applicable_domains=["general"],
            ),
            ValidationRule(
                rule_id="check_no_pii",
                description="Ensure output does not contain PII patterns",
                check_fn_name="check_no_pii",
                severity=ValidationSeverity.BLOCK,
                applicable_domains=["general"],
            ),
            ValidationRule(
                rule_id="check_confidence_threshold",
                description="Ensure confidence meets minimum threshold",
                check_fn_name="check_confidence_threshold",
                severity=ValidationSeverity.WARN,
                applicable_domains=["general"],
            ),
            ValidationRule(
                rule_id="check_budget_limit",
                description="Ensure cost does not exceed budget",
                check_fn_name="check_budget_limit",
                severity=ValidationSeverity.BLOCK,
                applicable_domains=["general"],
            ),
            ValidationRule(
                rule_id="check_gate_clearance",
                description="Ensure all gates have passed",
                check_fn_name="check_gate_clearance",
                severity=ValidationSeverity.INFO,
                applicable_domains=["general"],
            ),
        ],
    )


class WingmanProtocol:
    """Executor/validator pairing protocol with deterministic validation.

    Pairs an executor agent with a deterministic validator for each subject.
    The validator independently checks executor outputs against runbook rules
    before outputs are released downstream.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._runbooks: Dict[str, ExecutionRunbook] = {}
        self._pairs: Dict[str, WingmanPair] = {}
        self._validation_history: Dict[str, List[Dict[str, Any]]] = {}

        # Pre-register the default runbook
        default = _build_default_runbook()
        self._runbooks[default.runbook_id] = default

    # ------------------------------------------------------------------
    # Runbook management
    # ------------------------------------------------------------------

    def register_runbook(self, runbook: ExecutionRunbook) -> str:
        """Register a domain-specific runbook and return its runbook_id."""
        with self._lock:
            self._runbooks[runbook.runbook_id] = runbook
        logger.info("Registered runbook %s (%s)", runbook.runbook_id, runbook.name)
        return runbook.runbook_id

    def get_runbook(self, runbook_id: str) -> Optional[ExecutionRunbook]:
        """Return a runbook by id, or None if not found."""
        with self._lock:
            return self._runbooks.get(runbook_id)

    # ------------------------------------------------------------------
    # Pair management
    # ------------------------------------------------------------------

    def create_pair(
        self,
        subject: str,
        executor_id: str,
        validator_id: str,
        runbook_id: Optional[str] = None,
    ) -> WingmanPair:
        """Create an executor/validator pair for a given subject."""
        pair = WingmanPair(
            pair_id=f"wp-{uuid.uuid4().hex[:8]}",
            subject=subject,
            executor_id=executor_id,
            validator_id=validator_id,
            runbook_id=runbook_id,
        )
        with self._lock:
            self._pairs[pair.pair_id] = pair
            self._validation_history[pair.pair_id] = []
        logger.info(
            "Created wingman pair %s for subject '%s' (executor=%s, validator=%s)",
            pair.pair_id, subject, executor_id, validator_id,
        )
        return pair

    def get_pair(self, pair_id: str) -> Optional[WingmanPair]:
        """Return a pair by id, or None if not found."""
        with self._lock:
            return self._pairs.get(pair_id)

    def list_pairs(self, subject: Optional[str] = None) -> List[WingmanPair]:
        """List all pairs, optionally filtered by subject."""
        with self._lock:
            pairs = list(self._pairs.values())
        if subject is not None:
            pairs = [p for p in pairs if p.subject == subject]
        return pairs

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_output(self, pair_id: str, output: Dict[str, Any]) -> Dict[str, Any]:
        """Run the validator on an executor output.

        Returns a dict with:
            approved  – True only if no BLOCK-severity rules failed
            results   – list of all ValidationResult dicts
            blocking_failures – list of results where severity is BLOCK and passed is False
        """
        with self._lock:
            pair = self._pairs.get(pair_id)
        if pair is None:
            return {
                "approved": False,
                "results": [],
                "blocking_failures": [{"error": f"Pair {pair_id} not found"}],
            }

        runbook_id = pair.runbook_id or "default"
        with self._lock:
            runbook = self._runbooks.get(runbook_id)
        if runbook is None:
            return {
                "approved": False,
                "results": [],
                "blocking_failures": [{"error": f"Runbook {runbook_id} not found"}],
            }

        results: List[ValidationResult] = []
        for rule in runbook.validation_rules:
            check_fn = _BUILTIN_CHECK_REGISTRY.get(rule.check_fn_name)
            if check_fn is None:
                results.append(ValidationResult(
                    rule_id=rule.rule_id,
                    passed=False,
                    severity=rule.severity,
                    message=f"Check function '{rule.check_fn_name}' not found",
                ))
                continue
            result = check_fn(output)
            # Honor the severity declared in the runbook rule, not the check default
            result.severity = rule.severity
            result.rule_id = rule.rule_id
            results.append(result)

        blocking_failures = [
            r for r in results
            if not r.passed and r.severity == ValidationSeverity.BLOCK
        ]

        result_dicts = [
            {
                "rule_id": r.rule_id,
                "passed": r.passed,
                "severity": r.severity.value,
                "message": r.message,
                "checked_at": r.checked_at.isoformat(),
            }
            for r in results
        ]
        blocking_dicts = [
            {
                "rule_id": r.rule_id,
                "passed": r.passed,
                "severity": r.severity.value,
                "message": r.message,
                "checked_at": r.checked_at.isoformat(),
            }
            for r in blocking_failures
        ]

        approved = len(blocking_failures) == 0

        validation_record = {
            "pair_id": pair_id,
            "approved": approved,
            "results": result_dicts,
            "blocking_failures": blocking_dicts,
            "validated_at": datetime.now(timezone.utc).isoformat(),
        }

        with self._lock:
            self._validation_history.setdefault(pair_id, []).append(validation_record)

        logger.info(
            "Validation for pair %s: approved=%s (%d results, %d blocking failures)",
            pair_id, approved, len(results), len(blocking_failures),
        )
        return {
            "approved": approved,
            "results": result_dicts,
            "blocking_failures": blocking_dicts,
        }

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------

    def get_validation_history(self, pair_id: str) -> List[Dict[str, Any]]:
        """Return the validation history for a pair."""
        with self._lock:
            return list(self._validation_history.get(pair_id, []))

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """Return overall protocol status."""
        with self._lock:
            total_pairs = len(self._pairs)
            total_runbooks = len(self._runbooks)
            total_validations = sum(len(v) for v in self._validation_history.values())
            total_approved = sum(
                1 for records in self._validation_history.values()
                for r in records if r.get("approved")
            )
            total_rejected = total_validations - total_approved

        return {
            "total_pairs": total_pairs,
            "total_runbooks": total_runbooks,
            "total_validations": total_validations,
            "total_approved": total_approved,
            "total_rejected": total_rejected,
        }
