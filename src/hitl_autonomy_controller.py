"""
HITL Autonomy Controller for Murphy System Runtime

This module implements Section 14.1 item 3 — runtime policy toggles for
human-in-the-loop arming/disarming and high-confidence autonomy enablement
(95%+ confidence thresholds under policy).

Features:
- Autonomy policy registration with configurable confidence thresholds
- Runtime HITL arm/disarm toggles per policy
- Confidence and risk-level based autonomy evaluation
- Action recording with outcome tracking
- Cooldown management after failures
- Autonomy statistics and reporting
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)


@dataclass
class AutonomyPolicy:
    """Defines an autonomy policy with confidence and risk thresholds."""
    policy_id: str
    name: str
    confidence_threshold: float = 0.95
    hitl_required: bool = True
    auto_approve_below_risk: float = 0.2
    max_autonomous_actions: int = 10
    cooldown_seconds: int = 300
    enabled: bool = True


class HITLAutonomyController:
    """Runtime controller for human-in-the-loop autonomy policy management.

    Manages autonomy policies, evaluates whether tasks can proceed
    autonomously based on confidence and risk levels, tracks action
    history, and enforces cooldown periods after failures.
    """

    def __init__(self) -> None:
        self._policies: Dict[str, AutonomyPolicy] = {}
        self._action_history: List[Dict[str, Any]] = []
        self._autonomy_sessions: Dict[str, Dict[str, Any]] = {}
        self._cooldowns: Dict[str, str] = {}

    # ------------------------------------------------------------------
    # Policy management
    # ------------------------------------------------------------------

    def register_policy(self, policy: AutonomyPolicy) -> str:
        """Register an autonomy policy and return its policy_id."""
        self._policies[policy.policy_id] = policy
        self._autonomy_sessions[policy.policy_id] = {
            "autonomous_action_count": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        logger.info("Registered autonomy policy %s (%s)", policy.policy_id, policy.name)
        return policy.policy_id

    def get_policy(self, policy_id: str) -> Dict[str, Any]:
        """Return policy details as a dict."""
        policy = self._policies.get(policy_id)
        if policy is None:
            return {"status": "error", "reason": "unknown_policy", "policy_id": policy_id}
        return {
            "status": "ok",
            "policy_id": policy.policy_id,
            "name": policy.name,
            "confidence_threshold": policy.confidence_threshold,
            "hitl_required": policy.hitl_required,
            "auto_approve_below_risk": policy.auto_approve_below_risk,
            "max_autonomous_actions": policy.max_autonomous_actions,
            "cooldown_seconds": policy.cooldown_seconds,
            "enabled": policy.enabled,
        }

    def list_policies(self) -> List[Dict[str, Any]]:
        """Return all registered policies."""
        return [self.get_policy(pid) for pid in self._policies]

    # ------------------------------------------------------------------
    # Autonomy evaluation
    # ------------------------------------------------------------------

    def evaluate_autonomy(
        self,
        task_type: str,
        confidence: float,
        risk_level: float,
        policy_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Evaluate whether a task can proceed autonomously.

        Returns a dict with the autonomy decision, reason, and metadata.
        """
        # Resolve policy
        if policy_id and policy_id in self._policies:
            policy = self._policies[policy_id]
        elif self._policies:
            policy = next(iter(self._policies.values()))
            policy_id = policy.policy_id
        else:
            return {
                "autonomous": False,
                "reason": "no_policies_registered",
                "policy_applied": None,
                "confidence": confidence,
                "risk_level": risk_level,
                "requires_hitl": True,
            }

        if not policy.enabled:
            return {
                "autonomous": False,
                "reason": "policy_disabled",
                "policy_applied": policy.policy_id,
                "confidence": confidence,
                "risk_level": risk_level,
                "requires_hitl": True,
            }

        # Check cooldown
        cooldown_status = self.check_cooldown(policy.policy_id)
        if cooldown_status.get("in_cooldown"):
            return {
                "autonomous": False,
                "reason": "policy_in_cooldown",
                "policy_applied": policy.policy_id,
                "confidence": confidence,
                "risk_level": risk_level,
                "requires_hitl": True,
            }

        # Check max autonomous actions
        session = self._autonomy_sessions.get(policy.policy_id, {})
        if session.get("autonomous_action_count", 0) >= policy.max_autonomous_actions:
            return {
                "autonomous": False,
                "reason": "max_autonomous_actions_reached",
                "policy_applied": policy.policy_id,
                "confidence": confidence,
                "risk_level": risk_level,
                "requires_hitl": True,
            }

        # HITL required and confidence below threshold
        if policy.hitl_required and confidence < policy.confidence_threshold:
            return {
                "autonomous": False,
                "reason": "confidence_below_threshold",
                "policy_applied": policy.policy_id,
                "confidence": confidence,
                "risk_level": risk_level,
                "requires_hitl": True,
            }

        # Risk too high (above auto-approve threshold and HITL required)
        if policy.hitl_required and risk_level >= policy.auto_approve_below_risk:
            if confidence < policy.confidence_threshold:
                return {
                    "autonomous": False,
                    "reason": "risk_too_high",
                    "policy_applied": policy.policy_id,
                    "confidence": confidence,
                    "risk_level": risk_level,
                    "requires_hitl": True,
                }

        # Low risk auto-approve path
        if risk_level < policy.auto_approve_below_risk and confidence >= policy.confidence_threshold:
            self._autonomy_sessions[policy.policy_id]["autonomous_action_count"] = (
                session.get("autonomous_action_count", 0) + 1
            )
            return {
                "autonomous": True,
                "reason": "low_risk_auto_approved",
                "policy_applied": policy.policy_id,
                "confidence": confidence,
                "risk_level": risk_level,
                "requires_hitl": False,
            }

        # High confidence autonomous execution (HITL not required or confidence above threshold)
        if not policy.hitl_required or confidence >= policy.confidence_threshold:
            self._autonomy_sessions[policy.policy_id]["autonomous_action_count"] = (
                session.get("autonomous_action_count", 0) + 1
            )
            return {
                "autonomous": True,
                "reason": "high_confidence_autonomous",
                "policy_applied": policy.policy_id,
                "confidence": confidence,
                "risk_level": risk_level,
                "requires_hitl": False,
            }

        # Default: require HITL
        return {
            "autonomous": False,
            "reason": "hitl_required",
            "policy_applied": policy.policy_id,
            "confidence": confidence,
            "risk_level": risk_level,
            "requires_hitl": True,
        }

    # ------------------------------------------------------------------
    # HITL arm/disarm
    # ------------------------------------------------------------------

    def arm_hitl(self, policy_id: str) -> Dict[str, Any]:
        """Arm HITL (require human approval) for a policy."""
        policy = self._policies.get(policy_id)
        if policy is None:
            return {"status": "error", "reason": "unknown_policy", "policy_id": policy_id}
        policy.hitl_required = True
        logger.info("Armed HITL for policy %s", policy_id)
        return {
            "status": "armed",
            "policy_id": policy_id,
            "hitl_required": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def disarm_hitl(self, policy_id: str) -> Dict[str, Any]:
        """Disarm HITL (allow autonomous execution) for a policy."""
        policy = self._policies.get(policy_id)
        if policy is None:
            return {"status": "error", "reason": "unknown_policy", "policy_id": policy_id}
        policy.hitl_required = False
        logger.info("Disarmed HITL for policy %s", policy_id)
        return {
            "status": "disarmed",
            "policy_id": policy_id,
            "hitl_required": False,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # Action recording
    # ------------------------------------------------------------------

    def record_action(
        self,
        task_type: str,
        autonomous: bool,
        outcome: str,
        confidence: float,
    ) -> str:
        """Record an action taken and return a unique action_id."""
        action_id = uuid.uuid4().hex[:12]
        record = {
            "action_id": action_id,
            "task_type": task_type,
            "autonomous": autonomous,
            "outcome": outcome,
            "confidence": confidence,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        capped_append(self._action_history, record)
        logger.info(
            "Recorded action %s: task_type=%s autonomous=%s outcome=%s",
            action_id, task_type, autonomous, outcome,
        )
        return action_id

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_autonomy_stats(self) -> Dict[str, Any]:
        """Return autonomy statistics."""
        total = len(self._action_history)
        if total == 0:
            return {
                "total_actions": 0,
                "autonomous_count": 0,
                "hitl_count": 0,
                "avg_confidence": 0.0,
                "outcomes": {},
            }

        autonomous_count = sum(1 for a in self._action_history if a["autonomous"])
        hitl_count = total - autonomous_count
        avg_confidence = sum(a["confidence"] for a in self._action_history) / total

        outcomes: Dict[str, int] = {}
        for a in self._action_history:
            outcomes[a["outcome"]] = outcomes.get(a["outcome"], 0) + 1

        return {
            "total_actions": total,
            "autonomous_count": autonomous_count,
            "hitl_count": hitl_count,
            "avg_confidence": round(avg_confidence, 4),
            "outcomes": outcomes,
        }

    # ------------------------------------------------------------------
    # Cooldown management
    # ------------------------------------------------------------------

    def check_cooldown(self, policy_id: str) -> Dict[str, Any]:
        """Check if a policy is in cooldown period after failure."""
        policy = self._policies.get(policy_id)
        if policy is None:
            return {"status": "error", "reason": "unknown_policy", "policy_id": policy_id}

        cooldown_until = self._cooldowns.get(policy_id)
        if cooldown_until is None:
            return {
                "status": "ok",
                "policy_id": policy_id,
                "in_cooldown": False,
            }

        cooldown_end = datetime.fromisoformat(cooldown_until)
        now = datetime.now(timezone.utc)
        if now < cooldown_end:
            return {
                "status": "ok",
                "policy_id": policy_id,
                "in_cooldown": True,
                "cooldown_until": cooldown_until,
                "remaining_seconds": int((cooldown_end - now).total_seconds()),
            }

        # Cooldown expired — clean up
        del self._cooldowns[policy_id]
        return {
            "status": "ok",
            "policy_id": policy_id,
            "in_cooldown": False,
        }

    def trigger_cooldown(self, policy_id: str) -> Dict[str, Any]:
        """Trigger cooldown for a policy (after failure)."""
        policy = self._policies.get(policy_id)
        if policy is None:
            return {"status": "error", "reason": "unknown_policy", "policy_id": policy_id}

        cooldown_until = (
            datetime.now(timezone.utc) + timedelta(seconds=policy.cooldown_seconds)
        ).isoformat()
        self._cooldowns[policy_id] = cooldown_until
        # Reset autonomous action count
        if policy_id in self._autonomy_sessions:
            self._autonomy_sessions[policy_id]["autonomous_action_count"] = 0
        logger.info("Triggered cooldown for policy %s until %s", policy_id, cooldown_until)
        return {
            "status": "cooldown_triggered",
            "policy_id": policy_id,
            "cooldown_until": cooldown_until,
            "cooldown_seconds": policy.cooldown_seconds,
        }

    # ------------------------------------------------------------------
    # Dynamic assist integration
    # ------------------------------------------------------------------

    def evaluate_dynamic_assist(
        self,
        task_type: str,
        dynamic_output: Any,
        policy_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Evaluate autonomy using dynamic assist engine output.

        Uses computed_confidence_threshold from the dynamic output instead of
        the static policy threshold, and forces HITL when requires_approval is
        set by the dynamic model.

        Args:
            task_type: the task type string for policy lookup.
            dynamic_output: a DynamicAssistOutput instance with computed
                confidence threshold and approval requirement.
            policy_id: optional policy_id to use (defaults to first registered).

        Returns:
            Autonomy evaluation dict, same shape as evaluate_autonomy().
        """
        if dynamic_output is None:
            return {
                "autonomous": False,
                "reason": "no_dynamic_output",
                "policy_applied": None,
                "confidence": 0.0,
                "risk_level": 0.0,
                "requires_hitl": True,
            }

        computed_confidence = getattr(dynamic_output, "computed_confidence_threshold", 0.95)
        requires_approval = getattr(dynamic_output, "requires_approval", True)
        may_execute = getattr(dynamic_output, "may_execute", False)

        # If the dynamic model says approval is required, short-circuit to HITL
        if requires_approval:
            return {
                "autonomous": False,
                "reason": "dynamic_assist_requires_approval",
                "policy_applied": policy_id,
                "confidence": computed_confidence,
                "risk_level": 0.0,
                "requires_hitl": True,
                "dynamic_confidence_threshold": computed_confidence,
            }

        # If may_execute is False, agent is in observe/suggest mode only
        if not may_execute:
            return {
                "autonomous": False,
                "reason": "dynamic_assist_observe_or_suggest_only",
                "policy_applied": policy_id,
                "confidence": computed_confidence,
                "risk_level": 0.0,
                "requires_hitl": True,
                "dynamic_confidence_threshold": computed_confidence,
            }

        # Delegate to evaluate_autonomy with the dynamic confidence threshold as the
        # effective confidence value (threshold was computed as 1.0 - recall * 0.4,
        # so we pass confidence = 1.0 - threshold to model "recall confidence").
        effective_confidence = max(0.0, min(1.0, 1.0 - computed_confidence))
        result = self.evaluate_autonomy(
            task_type=task_type,
            confidence=effective_confidence,
            risk_level=0.0,
            policy_id=policy_id,
        )
        result["dynamic_confidence_threshold"] = computed_confidence
        return result

    # ------------------------------------------------------------------
    # Reset
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Clear all state."""
        self._policies.clear()
        self._action_history.clear()
        self._autonomy_sessions.clear()
        self._cooldowns.clear()
        logger.info("HITLAutonomyController state reset")

    # ------------------------------------------------------------------
    # Permutation Calibration Integration (Spec Section 3.6)
    # ------------------------------------------------------------------

    def register_learned_procedure_policy(
        self,
        sequence_id: str,
        domain: str,
        stability_score: float,
        confidence_score: float,
        requires_review: bool = True,
    ) -> str:
        """Register a policy for a learned procedure from permutation calibration.

        This implements spec Section 3.6: Require human review for high-impact
        learned procedures.

        Args:
            sequence_id: The sequence ID from permutation registry
            domain: Domain for the procedure
            stability_score: Stability of the learned ordering (0.0-1.0)
            confidence_score: Confidence in the procedure (0.0-1.0)
            requires_review: Whether HITL is required for this procedure

        Returns:
            The policy_id for the registered policy
        """
        policy_id = f"learned-{domain}-{sequence_id[:8]}"

        # Adjust confidence threshold based on stability
        # Less stable procedures require higher confidence for autonomy
        adjusted_threshold = 0.95 - (stability_score * 0.15)

        policy = AutonomyPolicy(
            policy_id=policy_id,
            name=f"Learned Procedure: {domain}",
            confidence_threshold=adjusted_threshold,
            hitl_required=requires_review,
            auto_approve_below_risk=0.1 if stability_score > 0.8 else 0.05,
            max_autonomous_actions=20 if stability_score > 0.7 else 10,
            cooldown_seconds=180 if stability_score > 0.8 else 300,
            enabled=True,
        )

        self.register_policy(policy)

        # Store metadata about the learned procedure
        self._autonomy_sessions[policy_id].update({
            "sequence_id": sequence_id,
            "domain": domain,
            "stability_score": stability_score,
            "confidence_score": confidence_score,
            "source": "permutation_learning",
        })

        logger.info(
            "Registered learned procedure policy %s (stability=%.2f, conf_threshold=%.2f)",
            policy_id, stability_score, adjusted_threshold
        )
        return policy_id

    def evaluate_learned_procedure_autonomy(
        self,
        sequence_id: str,
        domain: str,
        execution_confidence: float,
        risk_level: float,
    ) -> Dict[str, Any]:
        """Evaluate autonomy for a learned procedure execution.

        This method adds specific checks for learned procedures, including
        stability-based throttling.

        Args:
            sequence_id: The sequence ID from permutation registry
            domain: Domain for lookup
            execution_confidence: Confidence for this execution
            risk_level: Risk level for the execution

        Returns:
            Autonomy decision with learned procedure metadata
        """
        # Find the learned procedure policy
        policy_id = f"learned-{domain}-{sequence_id[:8]}"

        if policy_id not in self._policies:
            return {
                "autonomous": False,
                "reason": "no_learned_procedure_policy",
                "policy_applied": None,
                "sequence_id": sequence_id,
                "requires_hitl": True,
            }

        session = self._autonomy_sessions.get(policy_id, {})
        stability = session.get("stability_score", 0.0)

        # Throttle autonomy when stability is weak (Spec 3.6: reduce autonomy
        # when policy stability is weak)
        if stability < 0.5:
            return {
                "autonomous": False,
                "reason": "policy_stability_too_weak",
                "policy_applied": policy_id,
                "sequence_id": sequence_id,
                "stability_score": stability,
                "requires_hitl": True,
            }

        # Evaluate standard autonomy
        result = self.evaluate_autonomy(
            task_type=f"learned_procedure:{domain}",
            confidence=execution_confidence,
            risk_level=risk_level,
            policy_id=policy_id,
        )

        # Add learned procedure metadata
        result["sequence_id"] = sequence_id
        result["stability_score"] = stability
        result["source"] = "permutation_learning"

        return result

    def request_procedure_promotion_review(
        self,
        sequence_id: str,
        domain: str,
        promotion_reason: str,
        metrics: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Request human review for promoting a learned procedure.

        This implements spec Section 3.6: Escalate when learned order-sensitivity
        is too high.

        Args:
            sequence_id: The sequence ID requesting promotion
            domain: Domain for the procedure
            promotion_reason: Why promotion is being requested
            metrics: Performance metrics for the procedure

        Returns:
            Review request details
        """
        review_id = uuid.uuid4().hex[:12]

        # Check if order sensitivity is high enough to require escalation
        sensitivity = metrics.get("order_sensitivity", 0.0)
        fragility = metrics.get("fragility", 0.0)

        escalation_required = sensitivity > 0.7 or fragility > 0.4

        review_record = {
            "review_id": review_id,
            "sequence_id": sequence_id,
            "domain": domain,
            "promotion_reason": promotion_reason,
            "metrics": metrics,
            "escalation_required": escalation_required,
            "status": "pending_review",
            "requested_at": datetime.now(timezone.utc).isoformat(),
        }

        capped_append(self._action_history, {
            "action_id": review_id,
            "task_type": "procedure_promotion_review",
            "autonomous": False,
            "outcome": "pending",
            "confidence": metrics.get("confidence", 0.0),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "review_details": review_record,
        })

        logger.info(
            "Requested procedure promotion review %s for sequence %s (escalation=%s)",
            review_id, sequence_id, escalation_required
        )

        return review_record

    def approve_procedure_promotion(
        self,
        review_id: str,
        approver: str,
    ) -> Dict[str, Any]:
        """Approve a procedure promotion request.

        Args:
            review_id: The review ID to approve
            approver: Who is approving

        Returns:
            Approval result
        """
        for action in self._action_history:
            if action.get("action_id") == review_id:
                if action.get("task_type") != "procedure_promotion_review":
                    continue

                action["outcome"] = "approved"
                review_details = action.get("review_details", {})
                review_details["status"] = "approved"
                review_details["approved_by"] = approver
                review_details["approved_at"] = datetime.now(timezone.utc).isoformat()

                logger.info("Approved procedure promotion %s by %s", review_id, approver)
                return {
                    "status": "approved",
                    "review_id": review_id,
                    "approver": approver,
                    "sequence_id": review_details.get("sequence_id"),
                }

        return {"status": "error", "reason": "review_not_found", "review_id": review_id}

    def reject_procedure_promotion(
        self,
        review_id: str,
        reviewer: str,
        reason: str,
    ) -> Dict[str, Any]:
        """Reject a procedure promotion request.

        Args:
            review_id: The review ID to reject
            reviewer: Who is rejecting
            reason: Reason for rejection

        Returns:
            Rejection result
        """
        for action in self._action_history:
            if action.get("action_id") == review_id:
                if action.get("task_type") != "procedure_promotion_review":
                    continue

                action["outcome"] = "rejected"
                review_details = action.get("review_details", {})
                review_details["status"] = "rejected"
                review_details["rejected_by"] = reviewer
                review_details["rejection_reason"] = reason
                review_details["rejected_at"] = datetime.now(timezone.utc).isoformat()

                logger.info("Rejected procedure promotion %s by %s: %s", review_id, reviewer, reason)
                return {
                    "status": "rejected",
                    "review_id": review_id,
                    "reviewer": reviewer,
                    "reason": reason,
                    "sequence_id": review_details.get("sequence_id"),
                }

        return {"status": "error", "reason": "review_not_found", "review_id": review_id}

    def get_pending_procedure_reviews(self) -> List[Dict[str, Any]]:
        """Get all pending procedure promotion reviews.

        Returns:
            List of pending reviews
        """
        pending = []
        for action in self._action_history:
            if action.get("task_type") == "procedure_promotion_review":
                review_details = action.get("review_details", {})
                if review_details.get("status") == "pending_review":
                    pending.append(review_details)
        return pending

    def get_learned_procedure_stats(self) -> Dict[str, Any]:
        """Get statistics for learned procedure policies.

        Returns:
            Stats on learned procedure autonomy
        """
        learned_policies = []
        for policy_id, session in self._autonomy_sessions.items():
            if session.get("source") == "permutation_learning":
                policy = self._policies.get(policy_id)
                if policy:
                    learned_policies.append({
                        "policy_id": policy_id,
                        "domain": session.get("domain"),
                        "sequence_id": session.get("sequence_id"),
                        "stability_score": session.get("stability_score", 0.0),
                        "autonomous_actions": session.get("autonomous_action_count", 0),
                        "enabled": policy.enabled,
                    })

        # Count reviews
        total_reviews = sum(
            1 for a in self._action_history
            if a.get("task_type") == "procedure_promotion_review"
        )
        pending_reviews = len(self.get_pending_procedure_reviews())
        approved_reviews = sum(
            1 for a in self._action_history
            if a.get("task_type") == "procedure_promotion_review" and a.get("outcome") == "approved"
        )
        rejected_reviews = sum(
            1 for a in self._action_history
            if a.get("task_type") == "procedure_promotion_review" and a.get("outcome") == "rejected"
        )

        return {
            "status": "ok",
            "learned_procedure_policies": len(learned_policies),
            "policies": learned_policies,
            "total_promotion_reviews": total_reviews,
            "pending_reviews": pending_reviews,
            "approved_reviews": approved_reviews,
            "rejected_reviews": rejected_reviews,
        }
