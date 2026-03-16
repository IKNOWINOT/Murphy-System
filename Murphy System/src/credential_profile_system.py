"""
Credential Profile System
===========================
Human-in-the-loop credential profiles and automation statistics.
Tracks user interactions, approval patterns, and automation metrics
to build profiles of optimal automation. This data becomes System IP
licensed to Murphy for providing better metrics and recommendations.
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ProfileTier(Enum):
    """Credential profile tiers based on interaction history."""
    NEW = "new"
    LEARNING = "learning"
    ESTABLISHED = "established"
    EXPERT = "expert"
    AUTHORITY = "authority"


class InteractionType(Enum):
    """Types of human-in-the-loop interactions."""
    APPROVAL = "approval"
    REJECTION = "rejection"
    MODIFICATION = "modification"
    ESCALATION = "escalation"
    OVERRIDE = "override"
    DELEGATION = "delegation"
    REVIEW = "review"


@dataclass
class InteractionRecord:
    """Record of a single HITL interaction."""
    interaction_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    interaction_type: InteractionType = InteractionType.APPROVAL
    context: str = ""
    decision: str = ""
    confidence_before: float = 0.0
    confidence_after: float = 0.0
    response_time_ms: float = 0.0
    outcome: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "interaction_id": self.interaction_id,
            "interaction_type": self.interaction_type.value,
            "context": self.context,
            "decision": self.decision,
            "confidence_before": self.confidence_before,
            "confidence_after": self.confidence_after,
            "response_time_ms": self.response_time_ms,
            "outcome": self.outcome,
            "timestamp": self.timestamp,
        }


@dataclass
class AutomationMetric:
    """A single automation performance metric."""
    metric_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    metric_name: str = ""
    value: float = 0.0
    unit: str = ""
    context: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "metric_id": self.metric_id,
            "metric_name": self.metric_name,
            "value": self.value,
            "unit": self.unit,
            "context": self.context,
            "timestamp": self.timestamp,
        }


@dataclass
class CredentialProfile:
    """
    Human-in-the-loop credential profile.
    Tracks a user's interaction patterns, decisions, and automation metrics.
    """
    profile_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    user_name: str = ""
    role: str = ""
    tier: ProfileTier = ProfileTier.NEW
    interactions: list = field(default_factory=list)
    metrics: list = field(default_factory=list)
    total_approvals: int = 0
    total_rejections: int = 0
    total_modifications: int = 0
    total_escalations: int = 0
    avg_response_time_ms: float = 0.0
    automation_trust_score: float = 0.5
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "profile_id": self.profile_id,
            "user_id": self.user_id,
            "user_name": self.user_name,
            "role": self.role,
            "tier": self.tier.value,
            "total_interactions": len(self.interactions),
            "total_approvals": self.total_approvals,
            "total_rejections": self.total_rejections,
            "total_modifications": self.total_modifications,
            "total_escalations": self.total_escalations,
            "avg_response_time_ms": self.avg_response_time_ms,
            "automation_trust_score": self.automation_trust_score,
            "recent_metrics": [m.to_dict() for m in self.metrics[-10:]],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    def to_summary(self) -> dict:
        """Minimal summary for listing."""
        return {
            "profile_id": self.profile_id,
            "user_id": self.user_id,
            "user_name": self.user_name,
            "role": self.role,
            "tier": self.tier.value,
            "total_interactions": len(self.interactions),
            "automation_trust_score": self.automation_trust_score,
        }


class CredentialProfileSystem:
    """
    Manages human-in-the-loop credential profiles and automation statistics.
    Builds profiles from interaction patterns, computes optimal automation
    metrics, and provides system-level analytics that become System IP.
    """

    def __init__(self):
        self.profiles: dict[str, CredentialProfile] = {}
        self.max_profiles = 10000
        self.max_interactions_per_profile = 5000

    def create_profile(
        self,
        user_id: str,
        user_name: str,
        role: str = "",
    ) -> CredentialProfile:
        """Create a new credential profile for a user."""
        # Check for existing profile
        for profile in self.profiles.values():
            if profile.user_id == user_id:
                return profile

        profile = CredentialProfile(
            user_id=user_id,
            user_name=user_name,
            role=role,
        )
        self.profiles[profile.profile_id] = profile
        return profile

    def record_interaction(
        self,
        profile_id: str,
        interaction_type: str,
        context: str = "",
        decision: str = "",
        confidence_before: float = 0.0,
        confidence_after: float = 0.0,
        response_time_ms: float = 0.0,
        outcome: str = "",
    ) -> Optional[dict]:
        """Record a HITL interaction for a profile."""
        profile = self.profiles.get(profile_id)
        if not profile:
            return None

        int_type = InteractionType.APPROVAL
        for it in InteractionType:
            if it.value == interaction_type:
                int_type = it
                break

        record = InteractionRecord(
            interaction_type=int_type,
            context=context,
            decision=decision,
            confidence_before=confidence_before,
            confidence_after=confidence_after,
            response_time_ms=response_time_ms,
            outcome=outcome,
        )
        profile.interactions.append(record)

        # Update counters
        if int_type == InteractionType.APPROVAL:
            profile.total_approvals += 1
        elif int_type == InteractionType.REJECTION:
            profile.total_rejections += 1
        elif int_type == InteractionType.MODIFICATION:
            profile.total_modifications += 1
        elif int_type == InteractionType.ESCALATION:
            profile.total_escalations += 1

        # Update average response time
        self._update_avg_response_time(profile)

        # Update tier
        self._update_tier(profile)

        # Update trust score
        self._update_trust_score(profile)

        # Trim interactions if needed
        if len(profile.interactions) > self.max_interactions_per_profile:
            profile.interactions = profile.interactions[-self.max_interactions_per_profile:]

        profile.updated_at = datetime.now(timezone.utc).isoformat()

        return record.to_dict()

    def record_metric(
        self,
        profile_id: str,
        metric_name: str,
        value: float,
        unit: str = "",
        context: str = "",
    ) -> Optional[dict]:
        """Record an automation metric for a profile."""
        profile = self.profiles.get(profile_id)
        if not profile:
            return None

        metric = AutomationMetric(
            metric_name=metric_name,
            value=value,
            unit=unit,
            context=context,
        )
        profile.metrics.append(metric)

        # Keep metrics bounded
        if len(profile.metrics) > 1000:
            profile.metrics = profile.metrics[-1000:]

        profile.updated_at = datetime.now(timezone.utc).isoformat()
        return metric.to_dict()

    def get_profile(self, profile_id: str) -> Optional[dict]:
        """Get a profile by ID."""
        profile = self.profiles.get(profile_id)
        return profile.to_dict() if profile else None

    def get_profile_by_user(self, user_id: str) -> Optional[dict]:
        """Get a profile by user ID."""
        for profile in self.profiles.values():
            if profile.user_id == user_id:
                return profile.to_dict()
        return None

    def list_profiles(self, tier_filter: Optional[str] = None) -> list[dict]:
        """List all profiles with optional tier filtering."""
        results = []
        for profile in self.profiles.values():
            if tier_filter and profile.tier.value != tier_filter:
                continue
            results.append(profile.to_summary())
        return results

    def get_optimal_automation_metrics(self) -> dict:
        """
        Compute optimal automation metrics across all profiles.
        This becomes System IP - licensed to Murphy for better recommendations.
        """
        if not self.profiles:
            return {
                "total_profiles": 0,
                "ip_classification": "system_ip",
                "metrics": {},
            }

        total_interactions = 0
        total_approvals = 0
        total_rejections = 0
        total_response_times = []
        trust_scores = []
        tier_distribution = {}

        for profile in self.profiles.values():
            total_interactions += len(profile.interactions)
            total_approvals += profile.total_approvals
            total_rejections += profile.total_rejections
            if profile.avg_response_time_ms > 0:
                total_response_times.append(profile.avg_response_time_ms)
            trust_scores.append(profile.automation_trust_score)

            tier = profile.tier.value
            tier_distribution[tier] = tier_distribution.get(tier, 0) + 1

        avg_trust = sum(trust_scores) / (len(trust_scores) or 1) if trust_scores else 0.0
        avg_response = (
            sum(total_response_times) / (len(total_response_times) or 1)
            if total_response_times else 0.0
        )
        approval_rate = (
            total_approvals / total_interactions
            if total_interactions > 0 else 0.0
        )

        return {
            "total_profiles": len(self.profiles),
            "total_interactions": total_interactions,
            "approval_rate": round(approval_rate, 4),
            "avg_response_time_ms": round(avg_response, 2),
            "avg_trust_score": round(avg_trust, 4),
            "tier_distribution": tier_distribution,
            "ip_classification": "system_ip",
            "optimal_thresholds": {
                # Cap at 0.95 max; slightly above avg trust to encourage automation
                "auto_approve_confidence": round(min(0.95, avg_trust + 0.1), 2),
                # Floor at 0.2; below this trust level, escalate to human
                "escalation_confidence": round(max(0.2, avg_trust - 0.3), 2),
                # Target 20% faster than current average; default 1s if no data
                "target_response_time_ms": round(avg_response * 0.8, 2) if avg_response > 0 else 1000.0,
            },
        }

    def _update_avg_response_time(self, profile: CredentialProfile):
        """Update average response time from interactions."""
        times = [
            i.response_time_ms for i in profile.interactions
            if i.response_time_ms > 0
        ]
        if times:
            profile.avg_response_time_ms = sum(times) / len(times)

    def _update_tier(self, profile: CredentialProfile):
        """Update profile tier based on interaction count."""
        count = len(profile.interactions)
        if count >= 500:
            profile.tier = ProfileTier.AUTHORITY
        elif count >= 200:
            profile.tier = ProfileTier.EXPERT
        elif count >= 50:
            profile.tier = ProfileTier.ESTABLISHED
        elif count >= 10:
            profile.tier = ProfileTier.LEARNING
        else:
            profile.tier = ProfileTier.NEW

    def _update_trust_score(self, profile: CredentialProfile):
        """
        Update automation trust score based on interaction patterns.
        Higher approval rate + consistent decisions = higher trust.
        """
        total = len(profile.interactions)
        if total == 0:
            profile.automation_trust_score = 0.5
            return

        approval_ratio = profile.total_approvals / total
        modification_ratio = profile.total_modifications / total
        rejection_ratio = profile.total_rejections / total

        # Trust formula: high approval + low rejection = high trust
        # Modifications are neutral (human fine-tuning)
        trust = 0.5 + (approval_ratio * 0.3) - (rejection_ratio * 0.2)
        trust = max(0.0, min(1.0, trust))

        profile.automation_trust_score = round(trust, 4)
