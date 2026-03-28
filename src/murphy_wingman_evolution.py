"""
Murphy System - Murphy Wingman Evolution
Copyright 2024-2026 Corey Post, Inoni LLC
License: BSL 1.1
"""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Validation Metrics
# ---------------------------------------------------------------------------

class ValidationMetrics(BaseModel):
    """Metrics container for validation measurement."""
    pair_id: str
    total_validations: int = 0
    approved_count: int = 0
    rejected_count: int = 0
    human_override_count: int = 0
    total_validation_time_s: float = 0.0
    false_positive_count: int = 0
    false_negative_count: int = 0

    @property
    def approval_rate(self) -> float:
        return self.approved_count / (self.total_validations or 1)

    @property
    def rejection_rate(self) -> float:
        return self.rejected_count / (self.total_validations or 1)

    @property
    def false_positive_rate(self) -> float:
        return self.false_positive_count / (self.rejected_count or 1)

    @property
    def false_negative_rate(self) -> float:
        return self.false_negative_count / (self.approved_count or 1)

    @property
    def avg_validation_time_s(self) -> float:
        return self.total_validation_time_s / (self.total_validations or 1)

    @property
    def human_override_rate(self) -> float:
        return self.human_override_count / (self.total_validations or 1)


class WingmanScorecard(BaseModel):
    """WingmanScorecard — wingman scorecard definition."""
    pair_id: str
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    computed_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @staticmethod
    def compute(metrics: ValidationMetrics) -> "WingmanScorecard":
        """Compute precision, recall, F1 from validation metrics."""
        tp = max(0, metrics.approved_count - metrics.false_positive_count)
        fp = metrics.false_positive_count
        fn = metrics.false_negative_count

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        return WingmanScorecard(
            pair_id=metrics.pair_id,
            precision=round(precision, 4),
            recall=round(recall, 4),
            f1=round(f1, 4),
        )


# ---------------------------------------------------------------------------
# Runbook Evolver
# ---------------------------------------------------------------------------

@dataclass
class RunbookSuggestion:
    """RunbookSuggestion — runbook suggestion definition."""
    suggestion_id: str
    pair_id: str
    rule_id: str
    suggestion_type: str  # "relax", "tighten", "remove", "add"
    description: str
    supporting_evidence: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class RunbookEvolver:
    """
    Analyze validation history to suggest runbook improvements.
    - Rules that never fail → suggest relaxing or removing
    - Rules that always fail → suggest the threshold is wrong
    - Patterns in human overrides → suggest new rules
    """

    def __init__(self) -> None:
        self._suggestions: List[RunbookSuggestion] = []

    def analyze(
        self,
        pair_id: str,
        validation_history: List[Dict[str, Any]],
        metrics: ValidationMetrics,
    ) -> List[RunbookSuggestion]:
        """
        Analyze validation history and produce improvement suggestions.
        """
        suggestions: List[RunbookSuggestion] = []

        # Count rule outcomes
        rule_pass: Dict[str, int] = {}
        rule_fail: Dict[str, int] = {}
        for record in validation_history:
            for r in record.get("results", []):
                rid = r.get("rule_id", "")
                if r.get("passed", True):
                    rule_pass[rid] = rule_pass.get(rid, 0) + 1
                else:
                    rule_fail[rid] = rule_fail.get(rid, 0) + 1

        for rule_id in set(list(rule_pass.keys()) + list(rule_fail.keys())):
            passes = rule_pass.get(rule_id, 0)
            fails = rule_fail.get(rule_id, 0)
            total = passes + fails

            if total == 0:
                continue

            fail_rate = fails / total

            if fail_rate == 0.0 and total >= 5:
                # Rule never fails — possibly too lenient or redundant
                suggestions.append(RunbookSuggestion(
                    suggestion_id=str(uuid.uuid4()),
                    pair_id=pair_id,
                    rule_id=rule_id,
                    suggestion_type="relax",
                    description=f"Rule '{rule_id}' has never failed in {total} validations. Consider relaxing or removing.",
                    supporting_evidence={"passes": passes, "fails": fails},
                ))
            elif fail_rate >= 0.9 and total >= 5:
                # Rule almost always fails — threshold may be wrong
                suggestions.append(RunbookSuggestion(
                    suggestion_id=str(uuid.uuid4()),
                    pair_id=pair_id,
                    rule_id=rule_id,
                    suggestion_type="tighten",
                    description=f"Rule '{rule_id}' fails {fail_rate*100:.0f}% of the time. Threshold may be too strict.",
                    supporting_evidence={"passes": passes, "fails": fails},
                ))

        # Suggest new rule if human override rate is high
        if metrics.human_override_rate > 0.3 and metrics.total_validations >= 5:
            suggestions.append(RunbookSuggestion(
                suggestion_id=str(uuid.uuid4()),
                pair_id=pair_id,
                rule_id="new_rule",
                suggestion_type="add",
                description=(
                    f"Human override rate is {metrics.human_override_rate*100:.0f}%. "
                    "Consider adding domain-specific rules to match human judgment."
                ),
                supporting_evidence={"human_override_count": metrics.human_override_count},
            ))

        self._suggestions.extend(suggestions)
        return suggestions

    def get_suggestions(self, pair_id: Optional[str] = None) -> List[RunbookSuggestion]:
        if pair_id:
            return [s for s in self._suggestions if s.pair_id == pair_id]
        return list(self._suggestions)


# ---------------------------------------------------------------------------
# Auto Runbook Generator
# ---------------------------------------------------------------------------

class AutoRunbookGenerator:
    """Generate a starter runbook for a new subject/domain based on similar existing ones."""

    # Domain → default rule names
    _DOMAIN_RULES: Dict[str, List[str]] = {
        "engineering": ["check_has_output", "check_credential_active", "check_no_pii"],
        "safety": ["check_has_output", "check_gate_clearance", "check_confidence_threshold"],
        "finance": ["check_has_output", "check_no_pii", "check_budget_limit"],
        "autonomy": ["check_has_output", "check_gate_clearance", "check_confidence_threshold"],
        "default": ["check_has_output", "check_no_pii", "check_confidence_threshold"],
    }

    def generate(self, subject: str, domain: Optional[str] = None) -> Dict[str, Any]:
        """
        Return a runbook spec dict with suggested rules for the given subject/domain.
        """
        resolved_domain = domain or "default"
        rules = self._DOMAIN_RULES.get(resolved_domain, self._DOMAIN_RULES["default"])
        return {
            "runbook_id": f"auto-{uuid.uuid4().hex[:8]}",
            "name": f"Auto-generated runbook for {subject}",
            "domain": resolved_domain,
            "rules": rules,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "note": "Auto-generated starter runbook. Review and customize before production use.",
        }


# ---------------------------------------------------------------------------
# Cascading Wingman
# ---------------------------------------------------------------------------

@dataclass
class CascadeStage:
    """CascadeStage — cascade stage definition."""
    stage_id: str
    pair_id: str
    stage_name: str
    requires_credential: bool = False
    completed: bool = False
    result: Optional[Dict[str, Any]] = None


class CascadingWingman:
    """Chain multiple Wingman pairs for high-stakes operations."""

    def __init__(self, cascade_id: str, stages: List[CascadeStage]) -> None:
        self.cascade_id = cascade_id
        self.stages = stages
        self._lock = threading.Lock()

    def complete_stage(self, stage_id: str, result: Dict[str, Any]) -> bool:
        """Mark a stage complete with its result."""
        with self._lock:
            for stage in self.stages:
                if stage.stage_id == stage_id and not stage.completed:
                    stage.completed = True
                    stage.result = result
                    return True
        return False

    def is_complete(self) -> bool:
        return all(s.completed for s in self.stages)

    def current_stage(self) -> Optional[CascadeStage]:
        for stage in self.stages:
            if not stage.completed:
                return stage
        return None

    def get_summary(self) -> Dict[str, Any]:
        return {
            "cascade_id": self.cascade_id,
            "total_stages": len(self.stages),
            "completed_stages": sum(1 for s in self.stages if s.completed),
            "is_complete": self.is_complete(),
            "current_stage": self.current_stage().stage_name if self.current_stage() else None,
            "all_passed": all(
                s.result.get("approved", False) for s in self.stages if s.result
            ),
        }


# ---------------------------------------------------------------------------
# Wingman Factory
# ---------------------------------------------------------------------------

class WingmanFactory:
    """Auto-create Wingman pairs for ANY new Murphy capability."""

    def __init__(self) -> None:
        self._pairs: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

    def auto_create_pair(
        self,
        subject: str,
        capability_type: str,
        executor_id: Optional[str] = None,
        validator_id: Optional[str] = None,
        domain: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Auto-create a Wingman pair for a new capability.

        capability_type: "action", "osmosis", "drawing", "sensor_fusion", "autonomy", etc.
        Returns a pair spec dict.
        """
        auto_exec = executor_id or f"exec-{capability_type}-{uuid.uuid4().hex[:6]}"
        auto_val = validator_id or f"val-{capability_type}-{uuid.uuid4().hex[:6]}"

        # Assign domain based on capability type
        domain_map: Dict[str, str] = {
            "action": "default",
            "osmosis": "default",
            "drawing": "engineering",
            "sensor_fusion": "safety",
            "autonomy": "safety",
            "credential": "engineering",
        }
        resolved_domain = domain or domain_map.get(capability_type, "default")

        runbook_gen = AutoRunbookGenerator()
        runbook_spec = runbook_gen.generate(subject, resolved_domain)

        pair = {
            "pair_id": f"wp-auto-{uuid.uuid4().hex[:8]}",
            "subject": subject,
            "executor_id": auto_exec,
            "validator_id": auto_val,
            "capability_type": capability_type,
            "domain": resolved_domain,
            "runbook_spec": runbook_spec,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        with self._lock:
            capped_append(self._pairs, pair)
        logger.debug("WingmanFactory: created pair for '%s' (type=%s)", subject, capability_type)
        return pair

    def list_pairs(self, capability_type: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._lock:
            if capability_type:
                return [p for p in self._pairs if p["capability_type"] == capability_type]
            return list(self._pairs)


# ---------------------------------------------------------------------------
# Wingman Evolution (top-level integration class)
# ---------------------------------------------------------------------------

class WingmanEvolution:
    """
    Wraps existing WingmanProtocol and adds learning capabilities.
    Integrates: ValidationMetrics, RunbookEvolver, AutoRunbookGenerator, WingmanFactory.
    """

    def __init__(self) -> None:
        self._metrics: Dict[str, ValidationMetrics] = {}
        self._evolver = RunbookEvolver()
        self._factory = WingmanFactory()
        self._lock = threading.Lock()

    def record_validation(
        self,
        pair_id: str,
        approved: bool,
        validation_time_s: float = 0.0,
        human_override: bool = False,
        false_positive: bool = False,
        false_negative: bool = False,
    ) -> None:
        """Record a validation outcome for metrics tracking."""
        with self._lock:
            if pair_id not in self._metrics:
                self._metrics[pair_id] = ValidationMetrics(pair_id=pair_id)
            m = self._metrics[pair_id]
            m.total_validations += 1
            if approved:
                m.approved_count += 1
            else:
                m.rejected_count += 1
            if human_override:
                m.human_override_count += 1
            if false_positive:
                m.false_positive_count += 1
            if false_negative:
                m.false_negative_count += 1
            m.total_validation_time_s += validation_time_s

    def get_metrics(self, pair_id: str) -> Optional[ValidationMetrics]:
        return self._metrics.get(pair_id)

    def get_scorecard(self, pair_id: str) -> Optional[WingmanScorecard]:
        m = self._metrics.get(pair_id)
        if m is None:
            return None
        return WingmanScorecard.compute(m)

    def evolve(
        self, pair_id: str, validation_history: List[Dict[str, Any]]
    ) -> List[RunbookSuggestion]:
        """Run the RunbookEvolver for a pair and return improvement suggestions."""
        metrics = self._metrics.get(pair_id) or ValidationMetrics(pair_id=pair_id)
        return self._evolver.analyze(pair_id, validation_history, metrics)

    def factory(self) -> WingmanFactory:
        return self._factory

    def get_all_metrics(self) -> Dict[str, ValidationMetrics]:
        return dict(self._metrics)

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_pairs_tracked": len(self._metrics),
                "total_validations": sum(m.total_validations for m in self._metrics.values()),
                "total_suggestions": len(self._evolver.get_suggestions()),
                "factory_pairs_created": len(self._factory.list_pairs()),
            }
