"""
Security Plane - Phase 4: Access Control & Authorization
========================================================

Zero-trust access control with continuous trust re-computation.

CRITICAL PRINCIPLES:
1. Never trust, always verify
2. Trust scores decay continuously
3. Authority bands enforce minimum trust thresholds
4. Credentials are capability-scoped (minimal privilege)
5. All access decisions are logged immutably

Author: Murphy System (MFGC-AI)
"""

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple

from .schemas import AuthorityLevel, SecurityAnomaly, SecurityArtifact, SecurityFreeze, TrustLevel, TrustScore

logger = logging.getLogger(__name__)


class AccessDecision(Enum):
    """Access decision outcomes"""
    GRANTED = "granted"
    DENIED = "denied"
    REQUIRES_ELEVATION = "requires_elevation"
    REQUIRES_REAUTH = "requires_reauth"
    FROZEN = "frozen"


class CapabilityScope(Enum):
    """Capability scopes for minimal privilege"""
    READ_ONLY = "read_only"
    WRITE_DATA = "write_data"
    EXECUTE_LOW = "execute_low"
    EXECUTE_MEDIUM = "execute_medium"
    EXECUTE_HIGH = "execute_high"
    ADMIN = "admin"


@dataclass
class Capability:
    """A capability grants specific permissions"""
    scope: CapabilityScope
    resource_pattern: str  # e.g., "execution_packets/*", "confidence_engine/read"
    expires_at: datetime
    granted_by: str
    granted_at: datetime
    conditions: Dict[str, any] = field(default_factory=dict)

    def is_expired(self) -> bool:
        """Check if capability has expired"""
        return datetime.now(timezone.utc) >= self.expires_at

    def matches_resource(self, resource: str) -> bool:
        """Check if capability matches requested resource"""
        # Simple wildcard matching
        pattern = self.resource_pattern.replace("*", ".*")
        import re
        return bool(re.match(f"^{pattern}$", resource))

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "scope": self.scope.value,
            "resource_pattern": self.resource_pattern,
            "expires_at": self.expires_at.isoformat(),
            "granted_by": self.granted_by,
            "granted_at": self.granted_at.isoformat(),
            "conditions": self.conditions
        }


@dataclass
class AccessRequest:
    """Request for access to a resource"""
    principal_id: str  # Human or machine ID
    resource: str
    action: str  # read, write, execute
    context: Dict[str, any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "principal_id": self.principal_id,
            "resource": self.resource,
            "action": self.action,
            "context": self.context,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class AccessGrant:
    """Grant of access with conditions"""
    request: AccessRequest
    decision: AccessDecision
    capabilities_used: List[Capability]
    trust_score_at_grant: float
    authority_level: AuthorityLevel
    conditions: Dict[str, any] = field(default_factory=dict)
    expires_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc) + timedelta(minutes=5))
    granted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def is_expired(self) -> bool:
        """Check if grant has expired"""
        return datetime.now(timezone.utc) >= self.expires_at

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "request": self.request.to_dict(),
            "decision": self.decision.value,
            "capabilities_used": [c.to_dict() for c in self.capabilities_used],
            "trust_score_at_grant": self.trust_score_at_grant,
            "authority_level": self.authority_level.value,
            "conditions": self.conditions,
            "expires_at": self.expires_at.isoformat(),
            "granted_at": self.granted_at.isoformat()
        }


class TrustRecomputer:
    """
    Continuously re-computes trust scores based on behavior.

    Trust decays over time and must be refreshed through re-authentication
    and positive behavior signals.
    """

    def __init__(self, decay_rate: float = 0.1):
        """
        Initialize trust recomputer.

        Args:
            decay_rate: Trust decay per hour (0.1 = 10% per hour)
        """
        self.decay_rate = decay_rate
        self.behavior_signals: Dict[str, List[Tuple[datetime, float]]] = {}

    def recompute_trust(
        self,
        current_trust: TrustScore,
        principal_id: str
    ) -> TrustScore:
        """
        Recompute trust score with decay and behavior signals.

        Args:
            current_trust: Current trust score
            principal_id: Principal whose trust to recompute

        Returns:
            Updated trust score
        """
        # Apply time-based decay
        hours_elapsed = (datetime.now(timezone.utc) - current_trust.computed_at).total_seconds() / 3600
        decay_factor = (1 - self.decay_rate) ** hours_elapsed
        decayed_confidence = current_trust.confidence * decay_factor

        # Apply behavior signals
        signals = self.behavior_signals.get(principal_id, [])
        recent_signals = [
            signal for timestamp, signal in signals
            if (datetime.now(timezone.utc) - timestamp).total_seconds() < 3600  # Last hour
        ]

        if recent_signals:
            behavior_adjustment = sum(recent_signals) / (len(recent_signals) or 1)
            decayed_confidence = max(0.0, min(1.0, decayed_confidence + behavior_adjustment))

        # Determine trust level from confidence
        if decayed_confidence >= 0.9:
            trust_level = TrustLevel.HIGH
        elif decayed_confidence >= 0.7:
            trust_level = TrustLevel.MEDIUM
        elif decayed_confidence >= 0.5:
            trust_level = TrustLevel.LOW
        else:
            trust_level = TrustLevel.NONE

        # Create new trust score
        return TrustScore(
            identity_id=current_trust.identity_id,
            trust_level=trust_level,
            confidence=decayed_confidence,
            computed_at=datetime.now(timezone.utc),
            cryptographic_proof_strength=current_trust.cryptographic_proof_strength * decay_factor,
            behavioral_consistency=current_trust.behavioral_consistency * decay_factor,
            confidence_stability=current_trust.confidence_stability * decay_factor,
            artifact_lineage_valid=current_trust.artifact_lineage_valid,
            gate_history_clean=current_trust.gate_history_clean,
            telemetry_coherent=current_trust.telemetry_coherent,
            decay_rate=self.decay_rate
        )

    def add_behavior_signal(
        self,
        principal_id: str,
        signal: float,
        reason: str
    ):
        """
        Add a behavior signal (positive or negative).

        Args:
            principal_id: Principal ID
            signal: Signal strength (-0.1 to +0.1)
            reason: Reason for signal
        """
        if principal_id not in self.behavior_signals:
            self.behavior_signals[principal_id] = []

        self.behavior_signals[principal_id].append((datetime.now(timezone.utc), signal))

        # Keep only last 100 signals
        self.behavior_signals[principal_id] = self.behavior_signals[principal_id][-100:]


class AuthorityBandEnforcer:
    """
    Enforces authority bands based on trust scores.

    Authority levels require minimum trust thresholds:
    - NONE: Any trust score
    - LOW: >= 0.5
    - MEDIUM: >= 0.7
    - HIGH: >= 0.85
    - CRITICAL: >= 0.95
    """

    AUTHORITY_THRESHOLDS = {
        AuthorityLevel.NONE: 0.0,
        AuthorityLevel.LOW: 0.5,
        AuthorityLevel.MEDIUM: 0.7,
        AuthorityLevel.HIGH: 0.85,
        AuthorityLevel.CRITICAL: 0.95
    }

    def __init__(self):
        """Initialize authority band enforcer"""
        self.authority_history: Dict[str, List[Tuple[datetime, AuthorityLevel]]] = {}

    def compute_authority_level(self, trust_score: float) -> AuthorityLevel:
        """
        Compute authority level from trust score.

        Args:
            trust_score: Current trust score (0.0 to 1.0)

        Returns:
            Authority level
        """
        if trust_score >= self.AUTHORITY_THRESHOLDS[AuthorityLevel.CRITICAL]:
            return AuthorityLevel.CRITICAL
        elif trust_score >= self.AUTHORITY_THRESHOLDS[AuthorityLevel.HIGH]:
            return AuthorityLevel.HIGH
        elif trust_score >= self.AUTHORITY_THRESHOLDS[AuthorityLevel.MEDIUM]:
            return AuthorityLevel.MEDIUM
        elif trust_score >= self.AUTHORITY_THRESHOLDS[AuthorityLevel.LOW]:
            return AuthorityLevel.LOW
        else:
            return AuthorityLevel.NONE

    def check_authority_sufficient(
        self,
        current_authority: AuthorityLevel,
        required_authority: AuthorityLevel
    ) -> bool:
        """
        Check if current authority is sufficient for required level.

        Args:
            current_authority: Current authority level
            required_authority: Required authority level

        Returns:
            True if sufficient, False otherwise
        """
        authority_order = [
            AuthorityLevel.NONE,
            AuthorityLevel.LOW,
            AuthorityLevel.MEDIUM,
            AuthorityLevel.HIGH,
            AuthorityLevel.CRITICAL
        ]

        current_idx = authority_order.index(current_authority)
        required_idx = authority_order.index(required_authority)

        return current_idx >= required_idx

    def record_authority_change(
        self,
        principal_id: str,
        new_authority: AuthorityLevel
    ):
        """
        Record authority level change.

        Args:
            principal_id: Principal ID
            new_authority: New authority level
        """
        if principal_id not in self.authority_history:
            self.authority_history[principal_id] = []

        self.authority_history[principal_id].append((datetime.now(timezone.utc), new_authority))

        # Keep only last 100 changes
        self.authority_history[principal_id] = self.authority_history[principal_id][-100:]

    def get_authority_trend(self, principal_id: str) -> str:
        """
        Get authority trend (increasing, decreasing, stable).

        Args:
            principal_id: Principal ID

        Returns:
            Trend description
        """
        history = self.authority_history.get(principal_id, [])
        if len(history) < 2:
            return "stable"

        recent = history[-5:]  # Last 5 changes
        authority_order = [
            AuthorityLevel.NONE,
            AuthorityLevel.LOW,
            AuthorityLevel.MEDIUM,
            AuthorityLevel.HIGH,
            AuthorityLevel.CRITICAL
        ]

        indices = [authority_order.index(auth) for _, auth in recent]

        if all(indices[i] <= indices[i+1] for i in range(len(indices)-1)):
            return "increasing"
        elif all(indices[i] >= indices[i+1] for i in range(len(indices)-1)):
            return "decreasing"
        else:
            return "volatile"


class CapabilityManager:
    """
    Manages capability-scoped credentials.

    Capabilities grant minimal privileges for specific resources
    with automatic expiration.
    """

    def __init__(self, default_ttl: timedelta = timedelta(minutes=15)):
        """
        Initialize capability manager.

        Args:
            default_ttl: Default time-to-live for capabilities
        """
        self.default_ttl = default_ttl
        self.capabilities: Dict[str, List[Capability]] = {}

    def grant_capability(
        self,
        principal_id: str,
        scope: CapabilityScope,
        resource_pattern: str,
        granted_by: str,
        ttl: Optional[timedelta] = None,
        conditions: Optional[Dict[str, any]] = None
    ) -> Capability:
        """
        Grant a capability to a principal.

        Args:
            principal_id: Principal ID
            scope: Capability scope
            resource_pattern: Resource pattern (supports wildcards)
            granted_by: Who granted the capability
            ttl: Time-to-live (default: 15 minutes)
            conditions: Additional conditions

        Returns:
            Granted capability
        """
        ttl = ttl or self.default_ttl
        capability = Capability(
            scope=scope,
            resource_pattern=resource_pattern,
            expires_at=datetime.now(timezone.utc) + ttl,
            granted_by=granted_by,
            granted_at=datetime.now(timezone.utc),
            conditions=conditions or {}
        )

        if principal_id not in self.capabilities:
            self.capabilities[principal_id] = []

        self.capabilities[principal_id].append(capability)

        return capability

    def get_capabilities(
        self,
        principal_id: str,
        resource: Optional[str] = None
    ) -> List[Capability]:
        """
        Get capabilities for a principal.

        Args:
            principal_id: Principal ID
            resource: Optional resource to filter by

        Returns:
            List of valid capabilities
        """
        capabilities = self.capabilities.get(principal_id, [])

        # Filter expired
        valid = [c for c in capabilities if not c.is_expired()]

        # Filter by resource if specified
        if resource:
            valid = [c for c in valid if c.matches_resource(resource)]

        return valid

    def revoke_capability(
        self,
        principal_id: str,
        resource_pattern: str
    ) -> int:
        """
        Revoke capabilities matching a pattern.

        Args:
            principal_id: Principal ID
            resource_pattern: Resource pattern to revoke

        Returns:
            Number of capabilities revoked
        """
        if principal_id not in self.capabilities:
            return 0

        original_count = len(self.capabilities[principal_id])
        self.capabilities[principal_id] = [
            c for c in self.capabilities[principal_id]
            if c.resource_pattern != resource_pattern
        ]

        return original_count - len(self.capabilities[principal_id])

    def cleanup_expired(self):
        """Remove expired capabilities"""
        for principal_id in self.capabilities:
            self.capabilities[principal_id] = [
                c for c in self.capabilities[principal_id]
                if not c.is_expired()
            ]


class ZeroTrustAccessController:
    """
    Zero-trust access control system.

    PRINCIPLES:
    1. Never trust, always verify
    2. Continuous trust re-computation
    3. Capability-scoped credentials
    4. Authority band enforcement
    5. Automatic authority decay
    """

    def __init__(
        self,
        trust_recomputer: TrustRecomputer,
        authority_enforcer: AuthorityBandEnforcer,
        capability_manager: CapabilityManager
    ):
        """
        Initialize zero-trust access controller.

        Args:
            trust_recomputer: Trust score recomputer
            authority_enforcer: Authority band enforcer
            capability_manager: Capability manager
        """
        self.trust_recomputer = trust_recomputer
        self.authority_enforcer = authority_enforcer
        self.capability_manager = capability_manager
        self.access_log: List[AccessGrant] = []
        self.frozen_principals: Set[str] = set()

    def evaluate_access_request(
        self,
        request: AccessRequest,
        current_trust: TrustScore,
        required_authority: AuthorityLevel
    ) -> AccessGrant:
        """
        Evaluate an access request.

        Args:
            request: Access request
            current_trust: Current trust score
            required_authority: Required authority level

        Returns:
            Access grant with decision
        """
        # Check if principal is frozen
        if request.principal_id in self.frozen_principals:
            return AccessGrant(
                request=request,
                decision=AccessDecision.FROZEN,
                capabilities_used=[],
                trust_score_at_grant=0.0,
                authority_level=AuthorityLevel.NONE
            )

        # Recompute trust score
        updated_trust = self.trust_recomputer.recompute_trust(
            current_trust,
            request.principal_id
        )

        # Compute current authority level
        current_authority = self.authority_enforcer.compute_authority_level(
            updated_trust.confidence
        )

        # Record authority change
        self.authority_enforcer.record_authority_change(
            request.principal_id,
            current_authority
        )

        # Check if trust score requires re-authentication
        if updated_trust.confidence < 0.3:
            return AccessGrant(
                request=request,
                decision=AccessDecision.REQUIRES_REAUTH,
                capabilities_used=[],
                trust_score_at_grant=updated_trust.confidence,
                authority_level=current_authority
            )

        # Check if authority is sufficient
        if not self.authority_enforcer.check_authority_sufficient(
            current_authority,
            required_authority
        ):
            return AccessGrant(
                request=request,
                decision=AccessDecision.REQUIRES_ELEVATION,
                capabilities_used=[],
                trust_score_at_grant=updated_trust.confidence,
                authority_level=current_authority,
                conditions={"required_authority": required_authority.value}
            )

        # Check capabilities
        capabilities = self.capability_manager.get_capabilities(
            request.principal_id,
            request.resource
        )

        if not capabilities:
            return AccessGrant(
                request=request,
                decision=AccessDecision.DENIED,
                capabilities_used=[],
                trust_score_at_grant=updated_trust.confidence,
                authority_level=current_authority,
                conditions={"reason": "no_matching_capabilities"}
            )

        # Grant access
        grant = AccessGrant(
            request=request,
            decision=AccessDecision.GRANTED,
            capabilities_used=capabilities,
            trust_score_at_grant=updated_trust.confidence,
            authority_level=current_authority
        )

        # Log access
        self.access_log.append(grant)

        # Add positive behavior signal
        self.trust_recomputer.add_behavior_signal(
            request.principal_id,
            0.01,
            "successful_access"
        )

        return grant

    def freeze_principal(self, principal_id: str, reason: str):
        """
        Freeze a principal (revoke all access).

        Args:
            principal_id: Principal ID
            reason: Reason for freeze
        """
        self.frozen_principals.add(principal_id)

        # Revoke all capabilities
        if principal_id in self.capability_manager.capabilities:
            self.capability_manager.capabilities[principal_id] = []

        # Add negative behavior signal
        self.trust_recomputer.add_behavior_signal(
            principal_id,
            -0.5,
            f"frozen: {reason}"
        )

    def unfreeze_principal(self, principal_id: str):
        """
        Unfreeze a principal.

        Args:
            principal_id: Principal ID
        """
        self.frozen_principals.discard(principal_id)

    def get_access_statistics(self, principal_id: str) -> Dict:
        """
        Get access statistics for a principal.

        Args:
            principal_id: Principal ID

        Returns:
            Statistics dictionary
        """
        grants = [g for g in self.access_log if g.request.principal_id == principal_id]

        if not grants:
            return {
                "total_requests": 0,
                "granted": 0,
                "denied": 0,
                "requires_elevation": 0,
                "requires_reauth": 0,
                "frozen": 0
            }

        return {
            "total_requests": len(grants),
            "granted": sum(1 for g in grants if g.decision == AccessDecision.GRANTED),
            "denied": sum(1 for g in grants if g.decision == AccessDecision.DENIED),
            "requires_elevation": sum(1 for g in grants if g.decision == AccessDecision.REQUIRES_ELEVATION),
            "requires_reauth": sum(1 for g in grants if g.decision == AccessDecision.REQUIRES_REAUTH),
            "frozen": sum(1 for g in grants if g.decision == AccessDecision.FROZEN),
            "average_trust_score": sum(g.trust_score_at_grant for g in grants) / (len(grants) or 1)
        }
