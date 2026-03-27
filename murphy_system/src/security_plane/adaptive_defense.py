"""
Security Plane - Phase 6: Adaptive Defense System
=================================================

Adaptive defense with anomaly detection, threat intelligence, and automatic response.

CRITICAL PRINCIPLES:
1. Detect anomalies in real-time
2. Integrate threat intelligence feeds
3. Automatically escalate responses
4. Recognize attack patterns
5. Adapt defenses based on threats

Author: Murphy System (MFGC-AI)
"""

import hashlib
import json
import logging
import statistics
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class ThreatLevel(Enum):
    """Threat severity levels"""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AnomalyType(Enum):
    """Types of anomalies"""
    BEHAVIORAL = "behavioral"
    STATISTICAL = "statistical"
    PATTERN = "pattern"
    RATE = "rate"
    GEOGRAPHIC = "geographic"
    TEMPORAL = "temporal"


class ResponseAction(Enum):
    """Automated response actions"""
    LOG = "log"
    ALERT = "alert"
    RATE_LIMIT = "rate_limit"
    TEMPORARY_BLOCK = "temporary_block"
    PERMANENT_BLOCK = "permanent_block"
    FREEZE_PRINCIPAL = "freeze_principal"
    REQUIRE_REAUTH = "require_reauth"
    ESCALATE_TO_HUMAN = "escalate_to_human"


class AttackType(Enum):
    """Known attack types"""
    BRUTE_FORCE = "brute_force"
    CREDENTIAL_STUFFING = "credential_stuffing"
    SQL_INJECTION = "sql_injection"
    XSS = "xss"
    COMMAND_INJECTION = "command_injection"
    PATH_TRAVERSAL = "path_traversal"
    DDOS = "ddos"
    RECONNAISSANCE = "reconnaissance"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    DATA_EXFILTRATION = "data_exfiltration"


@dataclass
class SecurityEvent:
    """Security event for analysis"""
    timestamp: datetime
    principal_id: str
    event_type: str
    source_ip: str
    user_agent: Optional[str] = None
    resource: Optional[str] = None
    action: Optional[str] = None
    success: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "principal_id": self.principal_id,
            "event_type": self.event_type,
            "source_ip": self.source_ip,
            "user_agent": self.user_agent,
            "resource": self.resource,
            "action": self.action,
            "success": self.success,
            "metadata": self.metadata
        }


@dataclass
class Anomaly:
    """Detected anomaly"""
    anomaly_type: AnomalyType
    threat_level: ThreatLevel
    principal_id: str
    description: str
    detected_at: datetime
    confidence: float  # 0.0 to 1.0
    evidence: List[SecurityEvent] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "anomaly_type": self.anomaly_type.value,
            "threat_level": self.threat_level.value,
            "principal_id": self.principal_id,
            "description": self.description,
            "detected_at": self.detected_at.isoformat(),
            "confidence": self.confidence,
            "evidence_count": len(self.evidence),
            "metadata": self.metadata
        }


@dataclass
class ThreatIndicator:
    """Indicator of compromise (IOC)"""
    indicator_type: str  # ip, domain, hash, pattern
    value: str
    threat_level: ThreatLevel
    description: str
    source: str
    added_at: datetime
    expires_at: Optional[datetime] = None

    def is_expired(self) -> bool:
        """Check if indicator has expired"""
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) >= self.expires_at

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "indicator_type": self.indicator_type,
            "value": self.value,
            "threat_level": self.threat_level.value,
            "description": self.description,
            "source": self.source,
            "added_at": self.added_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None
        }


@dataclass
class DefenseResponse:
    """Automated defense response"""
    action: ResponseAction
    target: str  # principal_id or IP
    reason: str
    threat_level: ThreatLevel
    executed_at: datetime
    expires_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_expired(self) -> bool:
        """Check if response has expired"""
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) >= self.expires_at

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "action": self.action.value,
            "target": self.target,
            "reason": self.reason,
            "threat_level": self.threat_level.value,
            "executed_at": self.executed_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "metadata": self.metadata
        }


class BehavioralAnomalyDetector:
    """
    Detects anomalies based on behavioral patterns.

    Tracks normal behavior and flags deviations.
    """

    def __init__(self, window_size: int = 100):
        """
        Initialize behavioral anomaly detector.

        Args:
            window_size: Number of events to track per principal
        """
        self.window_size = window_size
        self.event_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=window_size))
        self.baseline_profiles: Dict[str, Dict] = {}

    def add_event(self, event: SecurityEvent):
        """
        Add event to history.

        Args:
            event: Security event
        """
        self.event_history[event.principal_id].append(event)

    def build_baseline(self, principal_id: str) -> Dict:
        """
        Build baseline behavior profile.

        Args:
            principal_id: Principal ID

        Returns:
            Baseline profile
        """
        events = list(self.event_history[principal_id])

        if len(events) < 10:
            return {}

        # Calculate baseline metrics
        profile = {
            "avg_events_per_hour": self._calculate_event_rate(events),
            "common_resources": self._get_common_resources(events),
            "common_actions": self._get_common_actions(events),
            "common_ips": self._get_common_ips(events),
            "success_rate": self._calculate_success_rate(events),
            "avg_time_between_events": self._calculate_avg_time_between(events)
        }

        self.baseline_profiles[principal_id] = profile
        return profile

    def detect_anomalies(self, event: SecurityEvent) -> Optional[Anomaly]:
        """
        Detect behavioral anomalies.

        Args:
            event: Security event to analyze

        Returns:
            Anomaly if detected, None otherwise
        """
        principal_id = event.principal_id

        # Build baseline if not exists
        if principal_id not in self.baseline_profiles:
            if len(self.event_history[principal_id]) >= 10:
                self.build_baseline(principal_id)
            return None

        baseline = self.baseline_profiles[principal_id]

        # Check for anomalies
        anomalies = []

        # Unusual resource access
        if event.resource and event.resource not in baseline.get("common_resources", []):
            anomalies.append("unusual_resource_access")

        # Unusual action
        if event.action and event.action not in baseline.get("common_actions", []):
            anomalies.append("unusual_action")

        # Unusual IP
        if event.source_ip not in baseline.get("common_ips", []):
            anomalies.append("unusual_ip")

        # Multiple failures
        recent_events = list(self.event_history[principal_id])[-10:]
        recent_failures = sum(1 for e in recent_events if not e.success)
        if recent_failures >= 5:
            anomalies.append("multiple_failures")

        if anomalies:
            # Determine threat level
            threat_level = ThreatLevel.LOW
            if "multiple_failures" in anomalies:
                threat_level = ThreatLevel.MEDIUM
            if len(anomalies) >= 3:
                threat_level = ThreatLevel.HIGH

            return Anomaly(
                anomaly_type=AnomalyType.BEHAVIORAL,
                threat_level=threat_level,
                principal_id=principal_id,
                description=f"Behavioral anomalies detected: {', '.join(anomalies)}",
                detected_at=datetime.now(timezone.utc),
                confidence=min(len(anomalies) * 0.3, 1.0),
                evidence=[event],
                metadata={"anomalies": anomalies}
            )

        return None

    def _calculate_event_rate(self, events: List[SecurityEvent]) -> float:
        """Calculate events per hour"""
        if len(events) < 2:
            return 0.0

        time_span = (events[-1].timestamp - events[0].timestamp).total_seconds() / 3600
        if time_span == 0:
            return 0.0

        return len(events) / time_span

    def _get_common_resources(self, events: List[SecurityEvent], top_n: int = 5) -> List[str]:
        """Get most common resources"""
        resources = [e.resource for e in events if e.resource]
        if not resources:
            return []

        resource_counts = defaultdict(int)
        for resource in resources:
            resource_counts[resource] += 1

        return sorted(resource_counts.keys(), key=lambda x: resource_counts[x], reverse=True)[:top_n]

    def _get_common_actions(self, events: List[SecurityEvent], top_n: int = 5) -> List[str]:
        """Get most common actions"""
        actions = [e.action for e in events if e.action]
        if not actions:
            return []

        action_counts = defaultdict(int)
        for action in actions:
            action_counts[action] += 1

        return sorted(action_counts.keys(), key=lambda x: action_counts[x], reverse=True)[:top_n]

    def _get_common_ips(self, events: List[SecurityEvent], top_n: int = 3) -> List[str]:
        """Get most common IPs"""
        ips = [e.source_ip for e in events]
        if not ips:
            return []

        ip_counts = defaultdict(int)
        for ip in ips:
            ip_counts[ip] += 1

        return sorted(ip_counts.keys(), key=lambda x: ip_counts[x], reverse=True)[:top_n]

    def _calculate_success_rate(self, events: List[SecurityEvent]) -> float:
        """Calculate success rate"""
        if not events:
            return 0.0

        successes = sum(1 for e in events if e.success)
        return successes / len(events)

    def _calculate_avg_time_between(self, events: List[SecurityEvent]) -> float:
        """Calculate average time between events (seconds)"""
        if len(events) < 2:
            return 0.0

        time_diffs = []
        for i in range(1, len(events)):
            diff = (events[i].timestamp - events[i-1].timestamp).total_seconds()
            time_diffs.append(diff)

        return statistics.mean(time_diffs) if time_diffs else 0.0


class StatisticalAnomalyDetector:
    """
    Detects anomalies using statistical methods.

    Uses standard deviation and z-scores to detect outliers.
    """

    def __init__(self, threshold: float = 3.0):
        """
        Initialize statistical anomaly detector.

        Args:
            threshold: Z-score threshold for anomaly detection
        """
        self.threshold = threshold
        self.metrics: Dict[str, List[float]] = defaultdict(list)

    def add_metric(self, metric_name: str, value: float):
        """
        Add metric value.

        Args:
            metric_name: Name of metric
            value: Metric value
        """
        self.metrics[metric_name].append(value)

        # Keep only last 1000 values
        if len(self.metrics[metric_name]) > 1000:
            self.metrics[metric_name] = self.metrics[metric_name][-1000:]

    def detect_anomaly(self, metric_name: str, value: float) -> Optional[Anomaly]:
        """
        Detect statistical anomaly.

        Args:
            metric_name: Name of metric
            value: Current value

        Returns:
            Anomaly if detected, None otherwise
        """
        if metric_name not in self.metrics or len(self.metrics[metric_name]) < 30:
            return None

        values = self.metrics[metric_name]
        mean = statistics.mean(values)
        stdev = statistics.stdev(values)

        if stdev == 0:
            return None

        z_score = abs((value - mean) / stdev)

        if z_score > self.threshold:
            # Determine threat level based on z-score
            if z_score > 5.0:
                threat_level = ThreatLevel.CRITICAL
            elif z_score > 4.0:
                threat_level = ThreatLevel.HIGH
            elif z_score > 3.5:
                threat_level = ThreatLevel.MEDIUM
            else:
                threat_level = ThreatLevel.LOW

            return Anomaly(
                anomaly_type=AnomalyType.STATISTICAL,
                threat_level=threat_level,
                principal_id="system",
                description=f"Statistical anomaly in {metric_name}: value={value:.2f}, mean={mean:.2f}, z-score={z_score:.2f}",
                detected_at=datetime.now(timezone.utc),
                confidence=min(z_score / 10.0, 1.0),
                evidence=[],
                metadata={
                    "metric_name": metric_name,
                    "value": value,
                    "mean": mean,
                    "stdev": stdev,
                    "z_score": z_score
                }
            )

        return None


class RateLimiter:
    """
    Adaptive rate limiter with dynamic thresholds.

    Limits requests per principal/IP with automatic threshold adjustment.
    """

    def __init__(
        self,
        default_limit: int = 100,
        window_seconds: int = 60,
        burst_multiplier: float = 1.5
    ):
        """
        Initialize rate limiter.

        Args:
            default_limit: Default requests per window
            window_seconds: Time window in seconds
            burst_multiplier: Multiplier for burst detection
        """
        self.default_limit = default_limit
        self.window_seconds = window_seconds
        self.burst_multiplier = burst_multiplier
        self.request_history: Dict[str, deque] = defaultdict(lambda: deque())
        self.custom_limits: Dict[str, int] = {}

    def check_rate_limit(self, identifier: str) -> Tuple[bool, int]:
        """
        Check if request is within rate limit.

        Args:
            identifier: Principal ID or IP address

        Returns:
            Tuple of (allowed, current_count)
        """
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=self.window_seconds)

        # Remove old requests
        history = self.request_history[identifier]
        while history and history[0] < cutoff:
            history.popleft()

        # Get limit
        limit = self.custom_limits.get(identifier, self.default_limit)

        # Check limit
        current_count = len(history)
        allowed = current_count < limit

        if allowed:
            history.append(now)

        return allowed, current_count

    def detect_burst(self, identifier: str) -> bool:
        """
        Detect burst traffic.

        Args:
            identifier: Principal ID or IP address

        Returns:
            True if burst detected
        """
        history = self.request_history[identifier]
        if len(history) < 10:
            return False

        # Check recent requests (last 10 seconds)
        now = datetime.now(timezone.utc)
        recent_cutoff = now - timedelta(seconds=10)
        recent_count = sum(1 for ts in history if ts >= recent_cutoff)

        # Burst if recent rate exceeds burst threshold
        burst_threshold = (self.default_limit / self.window_seconds) * 10 * self.burst_multiplier
        return recent_count > burst_threshold

    def set_custom_limit(self, identifier: str, limit: int):
        """
        Set custom rate limit for identifier.

        Args:
            identifier: Principal ID or IP address
            limit: Custom limit
        """
        self.custom_limits[identifier] = limit

    def get_current_rate(self, identifier: str) -> float:
        """
        Get current request rate (requests per second).

        Args:
            identifier: Principal ID or IP address

        Returns:
            Current rate
        """
        history = self.request_history[identifier]
        if len(history) < 2:
            return 0.0

        time_span = (history[-1] - history[0]).total_seconds()
        if time_span == 0:
            return 0.0

        return len(history) / time_span


class ThreatIntelligence:
    """
    Threat intelligence integration.

    Manages threat indicators and checks against known threats.
    """

    def __init__(self):
        """Initialize threat intelligence"""
        self.indicators: Dict[str, List[ThreatIndicator]] = defaultdict(list)
        self.blocked_ips: Set[str] = set()
        self.blocked_domains: Set[str] = set()

    def add_indicator(self, indicator: ThreatIndicator):
        """
        Add threat indicator.

        Args:
            indicator: Threat indicator
        """
        self.indicators[indicator.indicator_type].append(indicator)

        # Update block lists
        if indicator.indicator_type == "ip":
            self.blocked_ips.add(indicator.value)
        elif indicator.indicator_type == "domain":
            self.blocked_domains.add(indicator.value)

    def check_threat(self, indicator_type: str, value: str) -> Optional[ThreatIndicator]:
        """
        Check if value matches known threat.

        Args:
            indicator_type: Type of indicator
            value: Value to check

        Returns:
            Matching threat indicator if found
        """
        for indicator in self.indicators.get(indicator_type, []):
            if indicator.is_expired():
                continue

            if indicator.value == value:
                return indicator

        return None

    def is_blocked_ip(self, ip: str) -> bool:
        """Check if IP is blocked"""
        return ip in self.blocked_ips

    def is_blocked_domain(self, domain: str) -> bool:
        """Check if domain is blocked"""
        return domain in self.blocked_domains

    def cleanup_expired(self):
        """Remove expired indicators"""
        for indicator_type in self.indicators:
            self.indicators[indicator_type] = [
                i for i in self.indicators[indicator_type]
                if not i.is_expired()
            ]

        # Rebuild block lists
        self.blocked_ips = {
            i.value for i in self.indicators.get("ip", [])
            if not i.is_expired()
        }
        self.blocked_domains = {
            i.value for i in self.indicators.get("domain", [])
            if not i.is_expired()
        }


class AttackPatternRecognizer:
    """
    Recognizes known attack patterns.

    Uses signatures and heuristics to identify attacks.
    """

    def __init__(self):
        """Initialize attack pattern recognizer"""
        self.patterns: Dict[AttackType, List[Dict]] = {
            AttackType.BRUTE_FORCE: [
                {"min_failures": 5, "time_window": 300},  # 5 failures in 5 minutes
            ],
            AttackType.CREDENTIAL_STUFFING: [
                {"min_attempts": 10, "time_window": 60, "different_usernames": 5},
            ],
            AttackType.RECONNAISSANCE: [
                {"min_resources": 20, "time_window": 300},  # 20 different resources in 5 min
            ],
        }
        self.event_buffer: deque = deque(maxlen=1000)

    def add_event(self, event: SecurityEvent):
        """
        Add event to buffer.

        Args:
            event: Security event
        """
        self.event_buffer.append(event)

    def recognize_attack(self, principal_id: str) -> Optional[Tuple[AttackType, float]]:
        """
        Recognize attack pattern.

        Args:
            principal_id: Principal ID to check

        Returns:
            Tuple of (attack_type, confidence) if recognized
        """
        # Get recent events for principal
        now = datetime.now(timezone.utc)
        recent_events = [
            e for e in self.event_buffer
            if e.principal_id == principal_id
            and (now - e.timestamp).total_seconds() < 600  # Last 10 minutes
        ]

        if not recent_events:
            return None

        # Check for brute force
        if self._check_brute_force(recent_events):
            return (AttackType.BRUTE_FORCE, 0.9)

        # Check for reconnaissance
        if self._check_reconnaissance(recent_events):
            return (AttackType.RECONNAISSANCE, 0.8)

        return None

    def _check_brute_force(self, events: List[SecurityEvent]) -> bool:
        """Check for brute force pattern"""
        pattern = self.patterns[AttackType.BRUTE_FORCE][0]

        # Count failures in time window
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=pattern["time_window"])

        failures = sum(
            1 for e in events
            if not e.success and e.timestamp >= cutoff
        )

        return failures >= pattern["min_failures"]

    def _check_reconnaissance(self, events: List[SecurityEvent]) -> bool:
        """Check for reconnaissance pattern"""
        pattern = self.patterns[AttackType.RECONNAISSANCE][0]

        # Count unique resources in time window
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=pattern["time_window"])

        resources = {
            e.resource for e in events
            if e.resource and e.timestamp >= cutoff
        }

        return len(resources) >= pattern["min_resources"]


class AutomatedResponseSystem:
    """
    Automated response to detected threats.

    Escalates responses based on threat level.
    """

    def __init__(self):
        """Initialize automated response system"""
        self.active_responses: Dict[str, List[DefenseResponse]] = defaultdict(list)
        self.response_log: List[DefenseResponse] = []

    def determine_response(
        self,
        anomaly: Anomaly,
        attack_type: Optional[AttackType] = None
    ) -> List[ResponseAction]:
        """
        Determine appropriate response actions.

        Args:
            anomaly: Detected anomaly
            attack_type: Recognized attack type (if any)

        Returns:
            List of response actions
        """
        actions = [ResponseAction.LOG]  # Always log

        # Based on threat level
        if anomaly.threat_level == ThreatLevel.LOW:
            actions.append(ResponseAction.ALERT)

        elif anomaly.threat_level == ThreatLevel.MEDIUM:
            actions.extend([ResponseAction.ALERT, ResponseAction.RATE_LIMIT])

        elif anomaly.threat_level == ThreatLevel.HIGH:
            actions.extend([
                ResponseAction.ALERT,
                ResponseAction.RATE_LIMIT,
                ResponseAction.TEMPORARY_BLOCK
            ])

        elif anomaly.threat_level == ThreatLevel.CRITICAL:
            actions.extend([
                ResponseAction.ALERT,
                ResponseAction.PERMANENT_BLOCK,
                ResponseAction.FREEZE_PRINCIPAL,
                ResponseAction.ESCALATE_TO_HUMAN
            ])

        # Based on attack type
        if attack_type == AttackType.BRUTE_FORCE:
            actions.append(ResponseAction.REQUIRE_REAUTH)

        return list(set(actions))  # Remove duplicates

    def execute_response(
        self,
        action: ResponseAction,
        target: str,
        reason: str,
        threat_level: ThreatLevel,
        duration: Optional[timedelta] = None
    ) -> DefenseResponse:
        """
        Execute response action.

        Args:
            action: Response action
            target: Target (principal_id or IP)
            reason: Reason for response
            threat_level: Threat level
            duration: Duration for temporary actions

        Returns:
            Defense response
        """
        now = datetime.now(timezone.utc)
        expires_at = now + duration if duration else None

        response = DefenseResponse(
            action=action,
            target=target,
            reason=reason,
            threat_level=threat_level,
            executed_at=now,
            expires_at=expires_at
        )

        self.active_responses[target].append(response)
        self.response_log.append(response)

        return response

    def is_blocked(self, target: str) -> bool:
        """
        Check if target is blocked.

        Args:
            target: Target to check

        Returns:
            True if blocked
        """
        responses = self.active_responses.get(target, [])

        for response in responses:
            if response.is_expired():
                continue

            if response.action in (
                ResponseAction.TEMPORARY_BLOCK,
                ResponseAction.PERMANENT_BLOCK
            ):
                return True

        return False

    def cleanup_expired(self):
        """Remove expired responses"""
        for target in self.active_responses:
            self.active_responses[target] = [
                r for r in self.active_responses[target]
                if not r.is_expired()
            ]


@dataclass
class AdaptiveDefenseStatistics:
    """Statistics for adaptive defense"""
    total_events: int = 0
    anomalies_detected: int = 0
    attacks_recognized: int = 0
    responses_executed: int = 0
    blocked_principals: int = 0
    rate_limited_principals: int = 0

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "total_events": self.total_events,
            "anomalies_detected": self.anomalies_detected,
            "attacks_recognized": self.attacks_recognized,
            "responses_executed": self.responses_executed,
            "blocked_principals": self.blocked_principals,
            "rate_limited_principals": self.rate_limited_principals
        }
