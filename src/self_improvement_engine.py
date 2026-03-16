"""
Self-Improvement Engine for Murphy System Runtime

This module closes the feedback loop between execution outcomes and planning,
providing observability and recommendation capabilities including:
- Execution outcome tracking with metrics
- Recurring failure/success pattern extraction
- Correction proposal generation from failure patterns
- Confidence calibration based on historical outcomes
- Route optimization (deterministic vs. LLM) suggestions
- Remediation backlog management with priority and status
- Learning feedback loop for future planning decisions

Note: This engine provides observability and recommendations only.
It does not automatically modify source code or system behavior.
Proposals must be reviewed and implemented by a human operator.
"""

import logging
import threading
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class OutcomeType(str, Enum):
    """Classification of task execution outcomes."""
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    BLOCKED = "blocked"


@dataclass
class ExecutionOutcome:
    """Records the result of a single task execution."""
    task_id: str
    session_id: str
    outcome: OutcomeType
    metrics: Dict[str, Any] = field(default_factory=dict)
    corrections: Optional[List[str]] = None
    timestamp: Optional[str] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc).isoformat()


@dataclass
class ImprovementProposal:
    """A concrete proposal for system improvement."""
    proposal_id: str
    category: str  # routing, gating, delivery, confidence, etc.
    description: str
    priority: str  # critical, high, medium, low
    source_pattern: str
    suggested_action: str
    status: str = "pending"


PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


class SelfImprovementEngine:
    """Closes the feedback loop from execution outcomes to planning improvements.

    Tracks outcomes, extracts patterns, generates improvement proposals,
    calibrates confidence, and optimises task routing decisions.

    Note: This engine provides observability and recommendations only.
    It does not automatically modify source code or system behavior.
    Proposals must be reviewed and implemented by a human operator.

    Design Label: ARCH-001 — Persistence-Aware Self-Improvement Engine
    Owner: Backend Team
    Dependency: PersistenceManager (optional, graceful degradation)
    """

    # Persistence document IDs
    _PERSIST_DOC_ID = "self_improvement_engine_state"

    _MAX_OUTCOMES = 10_000
    _MAX_CORRECTIONS = 5_000

    def __init__(self, persistence_manager=None) -> None:
        self._lock = threading.Lock()
        self._outcomes: List[ExecutionOutcome] = []
        self._proposals: Dict[str, ImprovementProposal] = {}
        self._patterns: List[Dict[str, Any]] = []
        self._corrections_applied: List[Dict[str, Any]] = []
        self._persistence = persistence_manager

    # ------------------------------------------------------------------
    # Persistence integration  [ARCH-001]
    # ------------------------------------------------------------------

    def save_state(self) -> bool:
        """Persist current engine state via PersistenceManager.

        Returns True on success, False if persistence is unavailable.
        """
        if self._persistence is None:
            logger.debug("No PersistenceManager attached; skipping save_state")
            return False
        with self._lock:
            state = {
                "outcomes": [
                    {
                        "task_id": o.task_id,
                        "session_id": o.session_id,
                        "outcome": o.outcome.value,
                        "metrics": o.metrics,
                        "corrections": o.corrections,
                        "timestamp": o.timestamp,
                    }
                    for o in self._outcomes
                ],
                "proposals": {
                    pid: {
                        "proposal_id": p.proposal_id,
                        "category": p.category,
                        "description": p.description,
                        "priority": p.priority,
                        "source_pattern": p.source_pattern,
                        "suggested_action": p.suggested_action,
                        "status": p.status,
                    }
                    for pid, p in self._proposals.items()
                },
                "patterns": list(self._patterns),
                "corrections_applied": list(self._corrections_applied),
            }
        try:
            self._persistence.save_document(self._PERSIST_DOC_ID, state)
            logger.info("SelfImprovementEngine state persisted")
            return True
        except Exception as exc:
            logger.error("Failed to persist SelfImprovementEngine state: %s", exc)
            return False

    def load_state(self) -> bool:
        """Restore engine state from PersistenceManager.

        Returns True on success, False if persistence is unavailable or
        no prior state exists.
        """
        if self._persistence is None:
            logger.debug("No PersistenceManager attached; skipping load_state")
            return False
        try:
            state = self._persistence.load_document(self._PERSIST_DOC_ID)
        except Exception as exc:
            logger.error("Failed to load SelfImprovementEngine state: %s", exc)
            return False
        if state is None:
            logger.debug("No prior SelfImprovementEngine state found")
            return False
        with self._lock:
            self._outcomes = [
                ExecutionOutcome(
                    task_id=o["task_id"],
                    session_id=o["session_id"],
                    outcome=OutcomeType(o["outcome"]),
                    metrics=o.get("metrics", {}),
                    corrections=o.get("corrections"),
                    timestamp=o.get("timestamp"),
                )
                for o in state.get("outcomes", [])
            ]
            self._proposals = {
                pid: ImprovementProposal(
                    proposal_id=p["proposal_id"],
                    category=p["category"],
                    description=p["description"],
                    priority=p["priority"],
                    source_pattern=p["source_pattern"],
                    suggested_action=p["suggested_action"],
                    status=p.get("status", "pending"),
                )
                for pid, p in state.get("proposals", {}).items()
            }
            self._patterns = state.get("patterns", [])
            self._corrections_applied = state.get("corrections_applied", [])
        logger.info("SelfImprovementEngine state restored (%d outcomes, %d proposals)",
                     len(self._outcomes), len(self._proposals))
        return True

    # ------------------------------------------------------------------
    # Outcome recording
    # ------------------------------------------------------------------

    def record_outcome(self, outcome: ExecutionOutcome) -> str:
        """Record an execution outcome and return its task_id."""
        try:
            from src.self_learning_toggle import get_self_learning_toggle
            slt = get_self_learning_toggle()
            if not slt.is_enabled():
                slt.increment_skipped()
                return outcome.task_id
        except Exception as exc:
            logger.debug("Non-critical error: %s", exc)

        with self._lock:
            if len(self._outcomes) >= self._MAX_OUTCOMES:
                self._outcomes = self._outcomes[self._MAX_OUTCOMES // 10:]
            self._outcomes.append(outcome)
        logger.info("Recorded outcome for task %s: %s", outcome.task_id, outcome.outcome.value)
        return outcome.task_id

    # ------------------------------------------------------------------
    # Pattern extraction
    # ------------------------------------------------------------------

    def extract_patterns(self) -> List[Dict[str, Any]]:
        """Analyse recorded outcomes and return identified patterns."""
        with self._lock:
            outcomes = list(self._outcomes)

        patterns: List[Dict[str, Any]] = []

        # --- failure patterns grouped by category ---
        failure_cats: Dict[str, List[ExecutionOutcome]] = defaultdict(list)
        for o in outcomes:
            if o.outcome in (OutcomeType.FAILURE, OutcomeType.TIMEOUT, OutcomeType.BLOCKED):
                cat = o.metrics.get("task_type", "unknown")
                failure_cats[cat].append(o)

        for cat, items in failure_cats.items():
            if len(items) >= 2:
                patterns.append({
                    "pattern_id": f"fail-{cat}-{uuid.uuid4().hex[:8]}",
                    "type": "recurring_failure",
                    "category": cat,
                    "occurrences": len(items),
                    "outcome_types": list({i.outcome.value for i in items}),
                    "sample_task_ids": [i.task_id for i in items[:5]],
                })

        # --- success patterns ---
        success_cats: Dict[str, List[ExecutionOutcome]] = defaultdict(list)
        for o in outcomes:
            if o.outcome == OutcomeType.SUCCESS:
                cat = o.metrics.get("task_type", "unknown")
                success_cats[cat].append(o)

        for cat, items in success_cats.items():
            if len(items) >= 2:
                avg_dur = _safe_mean([i.metrics.get("duration", 0) for i in items])
                patterns.append({
                    "pattern_id": f"succ-{cat}-{uuid.uuid4().hex[:8]}",
                    "type": "success_pattern",
                    "category": cat,
                    "occurrences": len(items),
                    "avg_duration": avg_dur,
                    "sample_task_ids": [i.task_id for i in items[:5]],
                })

        # --- timeout pattern ---
        timeouts = [o for o in outcomes if o.outcome == OutcomeType.TIMEOUT]
        if len(timeouts) >= 2:
            patterns.append({
                "pattern_id": f"timeout-{uuid.uuid4().hex[:8]}",
                "type": "timeout_cluster",
                "occurrences": len(timeouts),
                "sample_task_ids": [t.task_id for t in timeouts[:5]],
            })

        with self._lock:
            self._patterns = patterns
        return patterns

    # ------------------------------------------------------------------
    # Proposal generation
    # ------------------------------------------------------------------

    def generate_proposals(self) -> List[ImprovementProposal]:
        """Generate improvement proposals from the latest extracted patterns."""
        patterns = self.extract_patterns()
        new_proposals: List[ImprovementProposal] = []

        for pat in patterns:
            pat_type = pat["type"]
            cat = pat.get("category", "general")
            occurrences = pat.get("occurrences", 0)

            if pat_type == "recurring_failure":
                priority = "critical" if occurrences >= 5 else "high" if occurrences >= 3 else "medium"
                proposal = ImprovementProposal(
                    proposal_id=f"prop-{uuid.uuid4().hex[:8]}",
                    category=cat,
                    description=f"Recurring failure in '{cat}' tasks ({occurrences} occurrences)",
                    priority=priority,
                    source_pattern=pat["pattern_id"],
                    suggested_action=f"Review and fix root cause for '{cat}' failures",
                )
                new_proposals.append(proposal)

            elif pat_type == "timeout_cluster":
                proposal = ImprovementProposal(
                    proposal_id=f"prop-{uuid.uuid4().hex[:8]}",
                    category="timeout",
                    description=f"Timeout cluster detected ({occurrences} occurrences)",
                    priority="high",
                    source_pattern=pat["pattern_id"],
                    suggested_action="Increase timeout thresholds or optimise task execution",
                )
                new_proposals.append(proposal)

            elif pat_type == "success_pattern":
                avg_dur = pat.get("avg_duration", 0)
                if avg_dur > 0:
                    proposal = ImprovementProposal(
                        proposal_id=f"prop-{uuid.uuid4().hex[:8]}",
                        category=cat,
                        description=f"Success pattern in '{cat}' (avg duration {avg_dur:.2f}s)",
                        priority="low",
                        source_pattern=pat["pattern_id"],
                        suggested_action=f"Codify '{cat}' success pattern as a template",
                    )
                    new_proposals.append(proposal)

        with self._lock:
            for p in new_proposals:
                self._proposals[p.proposal_id] = p

        logger.info("Generated %d improvement proposals", len(new_proposals))
        return new_proposals

    # ------------------------------------------------------------------
    # Remediation backlog
    # ------------------------------------------------------------------

    def get_remediation_backlog(self) -> List[ImprovementProposal]:
        """Return all pending proposals sorted by priority."""
        with self._lock:
            pending = [p for p in self._proposals.values() if p.status == "pending"]
        pending.sort(key=lambda p: PRIORITY_ORDER.get(p.priority, 99))
        return pending

    def apply_correction(self, proposal_id: str, result: str) -> bool:
        """Mark a proposal as applied and record the correction result.

        Note: This method only updates proposal metadata and records the
        correction in the audit log. It does NOT automatically modify source
        code or system behavior. The actual implementation of the correction
        must be performed by a human operator.
        """
        with self._lock:
            proposal = self._proposals.get(proposal_id)
            if proposal is None:
                logger.warning("Proposal %s not found", proposal_id)
                return False
            proposal.status = "applied"
            if len(self._corrections_applied) >= self._MAX_CORRECTIONS:
                self._corrections_applied = self._corrections_applied[self._MAX_CORRECTIONS // 10:]
            self._corrections_applied.append({
                "proposal_id": proposal_id,
                "result": result,
                "applied_at": datetime.now(timezone.utc).isoformat(),
            })
        logger.info("Applied correction for proposal %s: %s", proposal_id, result)
        return True

    # ------------------------------------------------------------------
    # Confidence calibration
    # ------------------------------------------------------------------

    def get_confidence_calibration(self, task_type: str) -> Dict[str, Any]:
        """Return calibrated confidence data for a given task type."""
        with self._lock:
            relevant = [
                o for o in self._outcomes
                if o.metrics.get("task_type") == task_type
            ]

        if not relevant:
            return {
                "task_type": task_type,
                "sample_size": 0,
                "calibrated_confidence": 0.5,
                "recommendation": "insufficient_data",
            }

        successes = sum(1 for o in relevant if o.outcome == OutcomeType.SUCCESS)
        total = len(relevant)
        success_rate = successes / total if total > 0 else 0.0

        reported_confs = [
            o.metrics["confidence"] for o in relevant
            if "confidence" in o.metrics
        ]
        avg_reported = _safe_mean(reported_confs) if reported_confs else None

        calibrated = success_rate
        recommendation = "maintain"
        if avg_reported is not None:
            gap = avg_reported - success_rate
            if gap > 0.2:
                recommendation = "decrease_confidence"
            elif gap < -0.2:
                recommendation = "increase_confidence"

        return {
            "task_type": task_type,
            "sample_size": total,
            "success_rate": round(success_rate, 4),
            "avg_reported_confidence": round(avg_reported, 4) if avg_reported is not None else None,
            "calibrated_confidence": round(calibrated, 4),
            "recommendation": recommendation,
        }

    # ------------------------------------------------------------------
    # Route optimisation
    # ------------------------------------------------------------------

    def get_route_optimization(self, task_type: str) -> Dict[str, Any]:
        """Suggest routing (deterministic vs. LLM) based on outcome data."""
        with self._lock:
            relevant = [
                o for o in self._outcomes
                if o.metrics.get("task_type") == task_type
            ]

        if not relevant:
            return {
                "task_type": task_type,
                "sample_size": 0,
                "recommended_route": "llm",
                "reason": "insufficient_data",
            }

        det_outcomes = [o for o in relevant if o.metrics.get("route") == "deterministic"]
        llm_outcomes = [o for o in relevant if o.metrics.get("route") == "llm"]

        det_success = (
            sum(1 for o in det_outcomes if o.outcome == OutcomeType.SUCCESS) / (len(det_outcomes) or 1)
            if det_outcomes else 0.0
        )
        llm_success = (
            sum(1 for o in llm_outcomes if o.outcome == OutcomeType.SUCCESS) / (len(llm_outcomes) or 1)
            if llm_outcomes else 0.0
        )

        if det_outcomes and det_success >= 0.8:
            recommended = "deterministic"
            reason = f"deterministic route has {det_success:.0%} success rate"
        elif llm_outcomes and llm_success > det_success:
            recommended = "llm"
            reason = f"llm route has higher success rate ({llm_success:.0%} vs {det_success:.0%})"
        else:
            recommended = "llm"
            reason = "default recommendation"

        return {
            "task_type": task_type,
            "sample_size": len(relevant),
            "deterministic_success_rate": round(det_success, 4) if det_outcomes else None,
            "llm_success_rate": round(llm_success, 4) if llm_outcomes else None,
            "recommended_route": recommended,
            "reason": reason,
        }

    # ------------------------------------------------------------------
    # Executable fix generation
    # ------------------------------------------------------------------

    def generate_executable_fix(self, proposal: "ImprovementProposal") -> Dict[str, Any]:
        """Convert a human-readable proposal into a structured executable plan.

        Returns a dictionary describing a FixPlan suitable for the SelfFixLoop.
        For runtime-adjustable issues (timeouts, confidence, routing), the plan
        contains executable steps. For code-level issues, the fix_type is
        'code_proposal' and the steps describe the change for human review.
        """
        fix_type = "code_proposal"
        fix_steps: List[Dict[str, Any]] = []
        rollback_steps: List[Dict[str, Any]] = []
        test_criteria: List[Dict[str, Any]] = []
        expected_outcome = proposal.suggested_action

        action_lower = proposal.suggested_action.lower()
        category_lower = proposal.category.lower()

        if "timeout" in action_lower or "timeout" in category_lower:
            fix_type = "threshold_tuning"
            fix_steps = [
                {
                    "action": "adjust_timeout",
                    "target": proposal.category,
                    "parameter": "timeout_seconds",
                    "delta": 30,
                    "reason": proposal.description,
                }
            ]
            rollback_steps = [
                {
                    "action": "adjust_timeout",
                    "target": proposal.category,
                    "parameter": "timeout_seconds",
                    "delta": -30,
                }
            ]
            test_criteria = [
                {"check": "timeout_errors_reduced", "category": proposal.category},
            ]
            expected_outcome = f"Timeout errors in '{proposal.category}' reduced by tuning timeout threshold"

        elif "confidence" in action_lower or "calibrat" in action_lower:
            fix_type = "threshold_tuning"
            fix_steps = [
                {
                    "action": "recalibrate_confidence",
                    "target": proposal.category,
                    "parameter": "confidence_threshold",
                    "reason": proposal.description,
                }
            ]
            rollback_steps = [
                {
                    "action": "restore_confidence",
                    "target": proposal.category,
                }
            ]
            test_criteria = [
                {"check": "confidence_calibrated", "category": proposal.category},
            ]
            expected_outcome = f"Confidence thresholds recalibrated for '{proposal.category}'"

        elif "rout" in action_lower:
            fix_type = "route_optimization"
            optimization = self.get_route_optimization(proposal.category)
            fix_steps = [
                {
                    "action": "apply_route_optimization",
                    "target": proposal.category,
                    "recommended_route": optimization.get("recommended_route", "llm"),
                    "reason": optimization.get("reason", ""),
                }
            ]
            rollback_steps = [
                {
                    "action": "restore_route",
                    "target": proposal.category,
                }
            ]
            test_criteria = [
                {"check": "route_success_rate_improved", "category": proposal.category},
            ]
            expected_outcome = f"Routing optimized for '{proposal.category}'"

        elif "recovery" in action_lower or "restart" in action_lower or "retry" in action_lower:
            fix_type = "recovery_registration"
            fix_steps = [
                {
                    "action": "register_recovery_procedure",
                    "target": proposal.category,
                    "description": proposal.suggested_action,
                    "reason": proposal.description,
                }
            ]
            rollback_steps = [
                {
                    "action": "unregister_recovery_procedure",
                    "target": proposal.category,
                }
            ]
            test_criteria = [
                {"check": "recovery_procedure_registered", "category": proposal.category},
            ]
            expected_outcome = f"Recovery procedure registered for '{proposal.category}'"

        else:
            fix_steps = [
                {
                    "action": "human_review",
                    "description": proposal.suggested_action,
                    "proposal_id": proposal.proposal_id,
                    "reason": proposal.description,
                }
            ]
            test_criteria = [
                {"check": "proposal_logged_for_review", "proposal_id": proposal.proposal_id},
            ]

        return {
            "proposal_id": proposal.proposal_id,
            "category": proposal.category,
            "description": proposal.description,
            "priority": proposal.priority,
            "fix_type": fix_type,
            "fix_steps": fix_steps,
            "rollback_steps": rollback_steps,
            "expected_outcome": expected_outcome,
            "test_criteria": test_criteria,
        }

    # ------------------------------------------------------------------
    # Status / summary
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """Return current engine status."""
        with self._lock:
            total_outcomes = len(self._outcomes)
            total_proposals = len(self._proposals)
            pending = sum(1 for p in self._proposals.values() if p.status == "pending")
            applied = sum(1 for p in self._proposals.values() if p.status == "applied")
            total_patterns = len(self._patterns)
            total_corrections = len(self._corrections_applied)

        return {
            "total_outcomes": total_outcomes,
            "total_patterns": total_patterns,
            "total_proposals": total_proposals,
            "pending_proposals": pending,
            "applied_corrections": applied,
            "corrections_log_size": total_corrections,
        }

    def get_learning_summary(self) -> Dict[str, Any]:
        """Return a high-level learning summary with outcome distribution and top issues."""
        with self._lock:
            outcomes = list(self._outcomes)
            patterns = list(self._patterns)
            proposals = dict(self._proposals)

        distribution: Dict[str, int] = defaultdict(int)
        for o in outcomes:
            distribution[o.outcome.value] += 1

        top_issues = sorted(
            [p for p in patterns if p["type"] == "recurring_failure"],
            key=lambda p: p.get("occurrences", 0),
            reverse=True,
        )[:5]

        critical_proposals = [
            p for p in proposals.values()
            if p.priority == "critical" and p.status == "pending"
        ]

        return {
            "total_outcomes": len(outcomes),
            "outcome_distribution": dict(distribution),
            "patterns_identified": len(patterns),
            "top_failure_patterns": top_issues,
            "critical_pending_proposals": len(critical_proposals),
            "feedback_loop_active": len(outcomes) > 0,
        }


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _safe_mean(values: List[float]) -> float:
    """Return the mean of *values*, or 0.0 for an empty list."""
    return sum(values) / (len(values) or 1) if values else 0.0
