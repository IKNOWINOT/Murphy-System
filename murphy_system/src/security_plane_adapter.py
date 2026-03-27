"""
Security Plane Adapter for Murphy System Runtime

Integrates core security capabilities:
- Input validation and hardening
- Trust scoring and computation
- Security gates
- Anomaly detection
- Security telemetry

This provides essential security features without requiring external dependencies.
"""

import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Import from security plane
try:
    from security_plane.hardening import InputType, InputValidator, ValidationRule, encode_output, sanitize_input
    from security_plane.schemas import (
        AnomalyType,
        SecurityAnomaly,
        SecurityGate,
        SecurityTelemetry,
        TrustLevel,
        TrustScore,
    )
    SECURITY_PLANE_AVAILABLE = True
except ImportError:
    SECURITY_PLANE_AVAILABLE = False
    # Fallback implementations
    class TrustLevel(Enum):
        """Trust level (Enum subclass)."""
        CRITICAL = "critical"
        HIGH = "high"
        MEDIUM = "medium"
        LOW = "low"
        NONE = "none"

    class AnomalyType(Enum):
        """Anomaly type (Enum subclass)."""
        UNAUTHORIZED_ACCESS = "unauthorized_access"
        SUSPICIOUS_PATTERN = "suspicious_pattern"
        RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
        INJECTION_ATTEMPT = "injection_attempt"
        PERMISSION_ESCALATION = "permission_escalation"


class SecurityPlaneAdapter:
    """
    Adapter for Security Plane integration with SystemIntegrator.

    Provides:
    - Input validation and sanitization
    - Trust scoring
    - Security gates
    - Anomaly detection
    - Security telemetry
    """

    def __init__(self):
        """Initialize security plane adapter"""
        self.enabled = SECURITY_PLANE_AVAILABLE
        self.validator = InputValidator() if self.enabled else None
        self.trust_scores: Dict[str, TrustScore] = {}
        self.security_gates: List[SecurityGate] = []
        self.anomalies: List[SecurityAnomaly] = []
        self.telemetry_log: List[Dict] = []
        self.security_events: List[Dict] = []

        # Initialize default security rules
        if self.enabled:
            self._initialize_default_rules()

    def _initialize_default_rules(self):
        """Initialize default validation rules for common inputs"""
        # Rule for system commands
        self.validator.add_rule("command", ValidationRule(
            input_type=InputType.COMMAND,
            required=True,
            min_length=1,
            max_length=1000
        ))

        # Rule for user messages
        self.validator.add_rule("user_message", ValidationRule(
            input_type=InputType.STRING,
            required=True,
            min_length=1,
            max_length=10000
        ))

        # Rule for system prompts
        self.validator.add_rule("system_prompt", ValidationRule(
            input_type=InputType.STRING,
            required=False,
            max_length=50000
        ))

    def validate_input(self, field_name: str = None, value: Any = None) -> Tuple[bool, Optional[str]]:
        """
        Validate input against security rules.

        Args:
            field_name: Name of the field being validated (or value if called with single arg)
            value: Value to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Support single-arg calling: validate_input("some_value")
        if value is None and field_name is not None:
            value = field_name
            field_name = "input"
        if not self.enabled:
            return True, None

        try:
            result = self.validator.validate(field_name, value)
            return True, None
        except Exception as exc:
            # Log the validation failure
            logger.debug("Caught exception: %s", exc)
            self._log_security_event("validation_failed", {
                "field": field_name,
                "error": str(exc)
            })
            return False, str(exc)

    def sanitize_input(self, value: Any, input_type: str = "string") -> Any:
        """
        Sanitize input to prevent injection attacks.

        Args:
            value: Value to sanitize
            input_type: Type of input (string, command, json, etc.)

        Returns:
            Sanitized value
        """
        if not self.enabled:
            return value

        try:
            # Map input type string to enum
            type_map = {
                "string": InputType.STRING,
                "command": InputType.COMMAND,
                "json": InputType.JSON,
                "path": InputType.PATH,
                "url": InputType.URL
            }

            input_type_enum = type_map.get(input_type, InputType.STRING)
            return sanitize_input(value, input_type_enum)
        except Exception as exc:
            logger.debug("Caught exception: %s", exc)
            self._log_security_event("sanitize_failed", {
                "error": str(exc)
            })
            return value

    def compute_trust_score(self,
                           entity_id: str,
                           base_score: float = 0.5,
                           factors: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
        """
        Compute trust score for an entity.

        Args:
            entity_id: Unique identifier for the entity
            base_score: Base trust score (0.0 to 1.0)
            factors: Dictionary of trust factors with weights

        Returns:
            Dictionary with trust score and level
        """
        if not self.enabled:
            return {
                "entity_id": entity_id,
                "trust_score": base_score,
                "trust_level": "MEDIUM",
                "confidence": 0.5
            }

        # Apply factors
        factors = factors or {}
        adjusted_score = base_score

        for factor_name, factor_value in factors.items():
            weight = self._get_factor_weight(factor_name)
            adjusted_score += factor_value * weight

        # Clamp to 0-1 range
        adjusted_score = max(0.0, min(1.0, adjusted_score))

        # Determine trust level
        if adjusted_score >= 0.9:
            level = TrustLevel.CRITICAL
        elif adjusted_score >= 0.75:
            level = TrustLevel.HIGH
        elif adjusted_score >= 0.5:
            level = TrustLevel.MEDIUM
        elif adjusted_score >= 0.25:
            level = TrustLevel.LOW
        else:
            level = TrustLevel.NONE

        # Store trust score
        self.trust_scores[entity_id] = TrustScore(
            entity_id=entity_id,
            score=adjusted_score,
            level=level,
            confidence=0.7 + (adjusted_score * 0.3),
            last_updated=datetime.now(timezone.utc)
        )

        return {
            "entity_id": entity_id,
            "trust_score": adjusted_score,
            "trust_level": level.value,
            "confidence": self.trust_scores[entity_id].confidence,
            "factors_applied": list(factors.keys())
        }

    def _get_factor_weight(self, factor_name: str) -> float:
        """Get weight for a trust factor"""
        weights = {
            "auth_success": 0.2,
            "auth_failure": -0.3,
            "successful_tasks": 0.1,
            "failed_tasks": -0.15,
            "time_in_system": 0.05,
            "behavior_anomaly": -0.2,
            "security_violation": -0.4
        }
        return weights.get(factor_name, 0.0)

    def create_security_gate(self,
                            gate_id: str,
                            gate_name: str,
                            threshold: float = 0.7,
                            description: str = "") -> Any:
        """
        Create a security gate.

        Args:
            gate_id: Unique identifier for the gate
            gate_name: Name of the gate
            threshold: Trust threshold required (0.0 to 1.0)
            description: Description of the gate

        Returns:
            SecurityGate object or dict (fallback)
        """
        if self.enabled:
            gate = SecurityGate(
                gate_id=gate_id,
                gate_name=gate_name,
                threshold=threshold,
                description=description,
                active=True,
                created_at=datetime.now(timezone.utc)
            )
            self.security_gates.append(gate)
            return gate
        else:
            # Fallback: create dict
            gate = {
                "gate_id": gate_id,
                "gate_name": gate_name,
                "threshold": threshold,
                "description": description,
                "active": True,
                "created_at": datetime.now(timezone.utc)
            }
            self.security_gates.append(gate)
            return gate

    def check_security_gate(self,
                           gate_id: str,
                           trust_score: float) -> Tuple[bool, str]:
        """
        Check if a security gate allows passage.

        Args:
            gate_id: ID of the gate to check
            trust_score: Trust score of the entity

        Returns:
            Tuple of (allowed, reason)
        """
        if not self.enabled:
            return True, "Security plane not enabled"

        # Find gate
        gate = next((g for g in self.security_gates if g.gate_id == gate_id), None)
        if not gate:
            return True, f"Gate {gate_id} not found, allowing by default"

        if not gate.active:
            return True, f"Gate {gate_id} is inactive"

        # Check threshold
        if trust_score >= gate.threshold:
            return True, f"Passed gate {gate_id} (score: {trust_score:.2f} >= {gate.threshold:.2f})"
        else:
            return False, f"Failed gate {gate_id} (score: {trust_score:.2f} < {gate.threshold:.2f})"

    def detect_anomaly(self,
                      anomaly_type: str,
                      entity_id: str,
                      details: Dict[str, Any]) -> Any:
        """
        Detect and log a security anomaly.

        Args:
            anomaly_type: Type of anomaly
            entity_id: ID of the entity that caused it
            details: Details about the anomaly

        Returns:
            SecurityAnomaly object or dict (fallback)
        """
        if not self.enabled:
            # Create simple anomaly dict
            return {
                "anomaly_id": f"ANOM-{len(self.anomalies)}",
                "anomaly_type": "suspicious_pattern",
                "entity_id": entity_id,
                "severity": "LOW",
                "details": details,
                "detected_at": datetime.now(timezone.utc)
            }

        # Map anomaly type string to enum
        type_map = {
            "unauthorized_access": AnomalyType.UNAUTHORIZED_ACCESS,
            "suspicious_pattern": AnomalyType.SUSPICIOUS_PATTERN,
            "rate_limit_exceeded": AnomalyType.RATE_LIMIT_EXCEEDED,
            "injection_attempt": AnomalyType.INJECTION_ATTEMPT,
            "permission_escalation": AnomalyType.PERMISSION_ESCALATION
        }

        anomaly_type_enum = type_map.get(anomaly_type, AnomalyType.SUSPICIOUS_PATTERN)

        # Determine severity based on type
        severity_map = {
            AnomalyType.UNAUTHORIZED_ACCESS: "HIGH",
            AnomalyType.INJECTION_ATTEMPT: "CRITICAL",
            AnomalyType.PERMISSION_ESCALATION: "HIGH",
            AnomalyType.RATE_LIMIT_EXCEEDED: "MEDIUM",
            AnomalyType.SUSPICIOUS_PATTERN: "LOW"
        }
        severity = severity_map.get(anomaly_type_enum, "MEDIUM")

        anomaly = SecurityAnomaly(
            anomaly_id=f"ANOM-{len(self.anomalies)}",
            anomaly_type=anomaly_type_enum,
            entity_id=entity_id,
            severity=severity,
            details=details,
            detected_at=datetime.now(timezone.utc)
        )

        self.anomalies.append(anomaly)
        self._log_security_event("anomaly_detected", {
            "anomaly_id": anomaly.anomaly_id,
            "type": anomaly_type,
            "severity": severity,
            "entity": entity_id
        })

        return anomaly

    def _log_security_event(self, event_type: str, details: Dict[str, Any]):
        """Log a security event"""
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "details": details
        }
        self.security_events.append(event)
        self.telemetry_log.append(event)

    def get_security_summary(self) -> Dict[str, Any]:
        """
        Get summary of security state.

        Returns:
            Dictionary with security metrics
        """
        # Count anomalies by severity
        severity_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
        for anomaly in self.anomalies:
            if isinstance(anomaly, dict):
                severity = anomaly.get('severity', 'LOW')
            else:
                severity = anomaly.severity if hasattr(anomaly, 'severity') else "LOW"
            severity_counts[severity] = severity_counts.get(severity, 0) + 1

        # Count active gates
        active_gate_count = 0
        for gate in self.security_gates:
            if isinstance(gate, dict):
                if gate.get('active', True):
                    active_gate_count += 1
            else:
                if hasattr(gate, 'active') and gate.active:
                    active_gate_count += 1

        return {
            "enabled": self.enabled,
            "security_gates": len(self.security_gates),
            "active_gates": active_gate_count,
            "total_anomalies": len(self.anomalies),
            "anomalies_by_severity": severity_counts,
            "security_events": len(self.security_events),
            "trust_tracked": len(self.trust_scores),
            "last_event": self.security_events[-1] if self.security_events else None
        }

    def get_trust_score(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """
        Get trust score for an entity.

        Args:
            entity_id: Entity identifier

        Returns:
            Trust score dictionary or None
        """
        if entity_id in self.trust_scores:
            score = self.trust_scores[entity_id]
            return {
                "entity_id": entity_id,
                "trust_score": score.score,
                "trust_level": score.level.value if hasattr(score.level, 'value') else score.level,
                "confidence": score.confidence,
                "last_updated": score.last_updated.isoformat() if hasattr(score.last_updated, 'isoformat') else str(score.last_updated)
            }
        return None

    def get_active_security_gates(self) -> List[Dict[str, Any]]:
        """
        Get list of active security gates.

        Returns:
            List of gate dictionaries
        """
        active_gates = []
        for gate in self.security_gates:
            # Handle both object and dict
            if isinstance(gate, dict):
                if gate.get('active', True):
                    active_gates.append(gate)
            else:
                if gate.active:
                    active_gates.append({
                        "gate_id": gate.gate_id,
                        "gate_name": gate.gate_name,
                        "threshold": gate.threshold,
                        "active": gate.active,
                        "description": gate.description
                    })
        return active_gates

    def get_recent_anomalies(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent security anomalies.

        Args:
            limit: Maximum number to return

        Returns:
            List of anomaly dictionaries
        """
        recent = self.anomalies[-limit:] if self.anomalies else []
        return [
            {
                "anomaly_id": a.anomaly_id,
                "type": a.anomaly_type.value if hasattr(a.anomaly_type, 'value') else str(a.anomaly_type),
                "severity": a.severity,
                "entity_id": a.entity_id,
                "details": a.details,
                "detected_at": a.detected_at.isoformat() if hasattr(a.detected_at, 'isoformat') else str(a.detected_at)
            }
            for a in reversed(recent)
        ]


# Factory function
def create_security_adapter() -> SecurityPlaneAdapter:
    """Create and configure security plane adapter"""
    adapter = SecurityPlaneAdapter()

    # Create default security gates
    if adapter.enabled:
        adapter.create_security_gate(
            "system_access",
            "System Access Gate",
            threshold=0.6,
            description="Controls access to system operations"
        )

        adapter.create_security_gate(
            "command_execution",
            "Command Execution Gate",
            threshold=0.75,
            description="Controls execution of system commands"
        )

        adapter.create_security_gate(
            "sensitive_operations",
            "Sensitive Operations Gate",
            threshold=0.85,
            description="Controls access to sensitive operations"
        )

    return adapter
