"""
Risk Manager for Murphy System Runtime

This module provides comprehensive risk management capabilities:
- Risk assessment and scoring
- Risk mitigation strategies
- Risk monitoring and alerts
- Risk reporting and analysis
"""

import logging
import statistics
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class RiskSeverity(Enum):
    """Risk severity levels"""
    CRITICAL = 5  # Immediate action required
    HIGH = 4  # Action required within hours
    MEDIUM = 3  # Action required within days
    LOW = 2  # Monitor and plan
    NEGLIGIBLE = 1  # Accept


class RiskCategory(Enum):
    """Risk categories"""
    SECURITY = "security"
    PERFORMANCE = "performance"
    RELIABILITY = "reliability"
    AVAILABILITY = "availability"
    DATA_INTEGRITY = "data_integrity"
    COMPLIANCE = "compliance"
    FINANCIAL = "financial"
    OPERATIONAL = "operational"


@dataclass
class RiskFactor:
    """Represents a risk factor"""
    factor_id: str
    factor_name: str
    category: RiskCategory
    description: str
    severity: RiskSeverity
    probability: float  # 0.0 to 1.0
    impact: float  # 0.0 to 1.0
    risk_score: float  # probability * impact
    detected_at: datetime
    last_updated: datetime
    affected_components: List[str] = field(default_factory=list)
    mitigation_status: str = "none"  # none, in_progress, mitigated, accepted
    mitigation_actions: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RiskAlert:
    """Represents a risk alert"""
    alert_id: str
    risk_factor_id: str
    severity: RiskSeverity
    message: str
    triggered_at: datetime
    acknowledged: bool = False
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    resolution: Optional[str] = None
    resolved_at: Optional[datetime] = None


@dataclass
class MitigationAction:
    """Represents a mitigation action"""
    action_id: str
    action_name: str
    risk_factor_id: str
    action_type: str  # prevent, reduce, transfer, accept
    description: str
    priority: int
    estimated_cost: float
    estimated_benefit: float
    status: str = "proposed"  # proposed, approved, in_progress, completed, cancelled
    assigned_to: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    effectiveness: Optional[float] = None  # 0.0 to 1.0


class RiskAssessment:
    """Performs risk assessment"""

    def __init__(self):
        self.risk_factors: Dict[str, RiskFactor] = {}
        self.risk_history: List[Dict[str, Any]] = []
        self.lock = threading.Lock()

    def assess_risk(self, factor_id: str, factor_name: str,
                   category: RiskCategory, description: str,
                   probability: float, impact: float,
                   affected_components: List[str] = None,
                   metadata: Dict[str, Any] = None) -> RiskFactor:
        """Assess a new risk factor"""
        risk_score = probability * impact

        # Determine severity based on risk score
        if risk_score >= 0.8:
            severity = RiskSeverity.CRITICAL
        elif risk_score >= 0.6:
            severity = RiskSeverity.HIGH
        elif risk_score >= 0.4:
            severity = RiskSeverity.MEDIUM
        elif risk_score >= 0.2:
            severity = RiskSeverity.LOW
        else:
            severity = RiskSeverity.NEGLIGIBLE

        now = datetime.now(timezone.utc)
        risk_factor = RiskFactor(
            factor_id=factor_id,
            factor_name=factor_name,
            category=category,
            description=description,
            severity=severity,
            probability=probability,
            impact=impact,
            risk_score=risk_score,
            detected_at=now,
            last_updated=now,
            affected_components=affected_components or [],
            metadata=metadata or {}
        )

        with self.lock:
            self.risk_factors[factor_id] = risk_factor
            self.risk_history.append({
                'timestamp': now,
                'action': 'risk_assessed',
                'risk_id': factor_id,
                'risk_score': risk_score
            })

        return risk_factor

    def update_risk(self, factor_id: str, probability: Optional[float] = None,
                   impact: Optional[float] = None,
                   mitigation_status: Optional[str] = None,
                   mitigation_actions: Optional[List[str]] = None) -> Optional[RiskFactor]:
        """Update an existing risk factor"""
        with self.lock:
            risk_factor = self.risk_factors.get(factor_id)
            if not risk_factor:
                return None

            # Update probability if provided
            if probability is not None:
                risk_factor.probability = probability

            # Update impact if provided
            if impact is not None:
                risk_factor.impact = impact

            # Recalculate risk score and severity
            risk_factor.risk_score = risk_factor.probability * risk_factor.impact

            if risk_factor.risk_score >= 0.8:
                risk_factor.severity = RiskSeverity.CRITICAL
            elif risk_factor.risk_score >= 0.6:
                risk_factor.severity = RiskSeverity.HIGH
            elif risk_factor.risk_score >= 0.4:
                risk_factor.severity = RiskSeverity.MEDIUM
            elif risk_factor.risk_score >= 0.2:
                risk_factor.severity = RiskSeverity.LOW
            else:
                risk_factor.severity = RiskSeverity.NEGLIGIBLE

            # Update mitigation status if provided
            if mitigation_status is not None:
                risk_factor.mitigation_status = mitigation_status

            # Update mitigation actions if provided
            if mitigation_actions is not None:
                risk_factor.mitigation_actions = mitigation_actions

            risk_factor.last_updated = datetime.now(timezone.utc)

            # Record update
            self.risk_history.append({
                'timestamp': datetime.now(timezone.utc),
                'action': 'risk_updated',
                'risk_id': factor_id,
                'new_risk_score': risk_factor.risk_score
            })

            return risk_factor

    def get_risk_factor(self, factor_id: str) -> Optional[RiskFactor]:
        """Get a risk factor by ID"""
        return self.risk_factors.get(factor_id)

    def get_risks_by_severity(self, severity: RiskSeverity) -> List[RiskFactor]:
        """Get risk factors by severity"""
        return [rf for rf in self.risk_factors.values() if rf.severity == severity]

    def get_risks_by_category(self, category: RiskCategory) -> List[RiskFactor]:
        """Get risk factors by category"""
        return [rf for rf in self.risk_factors.values() if rf.category == category]

    def get_all_risks(self) -> List[RiskFactor]:
        """Get all risk factors"""
        return list(self.risk_factors.values())

    def get_high_priority_risks(self) -> List[RiskFactor]:
        """Get high priority risks (CRITICAL and HIGH)"""
        return [
            rf for rf in self.risk_factors.values()
            if rf.severity in [RiskSeverity.CRITICAL, RiskSeverity.HIGH]
        ]


class RiskMonitor:
    """Monitors risks and generates alerts"""

    def __init__(self, assessment: RiskAssessment):
        self.assessment = assessment
        self.alerts: Dict[str, RiskAlert] = []
        self.alert_rules: List[Dict[str, Any]] = []
        self.lock = threading.Lock()

        # Default alert rules
        self._initialize_default_rules()

    def _initialize_default_rules(self) -> None:
        """Initialize default alert rules"""
        self.alert_rules = [
            {
                'condition': lambda rf: rf.severity == RiskSeverity.CRITICAL,
                'action': 'alert_immediately',
                'message': 'CRITICAL risk detected: {factor_name}'
            },
            {
                'condition': lambda rf: rf.severity == RiskSeverity.HIGH and rf.mitigation_status == 'none',
                'action': 'alert_within_hour',
                'message': 'HIGH risk detected with no mitigation: {factor_name}'
            },
            {
                'condition': lambda rf: rf.probability > 0.8,
                'action': 'monitor_closely',
                'message': 'High probability risk detected: {factor_name}'
            },
            {
                'condition': lambda rf: rf.impact > 0.8,
                'action': 'assess_impact',
                'message': 'High impact risk detected: {factor_name}'
            }
        ]

    def monitor_risks(self) -> List[RiskAlert]:
        """Monitor risks and generate alerts"""
        new_alerts = []

        with self.lock:
            # Check each risk factor
            for risk_factor in self.assessment.get_all_risks():
                # Check against alert rules
                for rule in self.alert_rules:
                    if rule['condition'](risk_factor):
                        # Check if alert already exists
                        existing_alert = next(
                            (a for a in self.alerts
                             if a.risk_factor_id == risk_factor.factor_id and not a.resolved_at),
                            None
                        )

                        if not existing_alert:
                            # Create new alert
                            alert = RiskAlert(
                                alert_id=f"alert_{len(self.alerts)}",
                                risk_factor_id=risk_factor.factor_id,
                                severity=risk_factor.severity,
                                message=rule['message'].format(factor_name=risk_factor.factor_name),
                                triggered_at=datetime.now(timezone.utc)
                            )
                            self.alerts.append(alert)
                            new_alerts.append(alert)

        return new_alerts

    def acknowledge_alert(self, alert_id: str, acknowledged_by: str) -> bool:
        """Acknowledge an alert"""
        with self.lock:
            for alert in self.alerts:
                if alert.alert_id == alert_id:
                    alert.acknowledged = True
                    alert.acknowledged_by = acknowledged_by
                    alert.acknowledged_at = datetime.now(timezone.utc)
                    return True
            return False

    def resolve_alert(self, alert_id: str, resolution: str) -> bool:
        """Resolve an alert"""
        with self.lock:
            for alert in self.alerts:
                if alert.alert_id == alert_id:
                    alert.resolution = resolution
                    alert.resolved_at = datetime.now(timezone.utc)
                    return True
            return False

    def get_active_alerts(self) -> List[RiskAlert]:
        """Get active (unresolved) alerts"""
        return [a for a in self.alerts if not a.resolved_at]

    def get_alerts_by_severity(self, severity: RiskSeverity) -> List[RiskAlert]:
        """Get alerts by severity"""
        return [a for a in self.alerts if a.severity == severity and not a.resolved_at]


class MitigationPlanner:
    """Plans and tracks mitigation actions"""

    def __init__(self):
        self.mitigation_actions: Dict[str, MitigationAction] = []
        self.action_templates: Dict[str, Dict[str, Any]] = {}
        self.lock = threading.Lock()

        # Initialize action templates
        self._initialize_templates()

    def _initialize_templates(self) -> None:
        """Initialize mitigation action templates"""
        self.action_templates = {
            'reduce_probability': {
                'action_type': 'reduce',
                'priority': 1,
                'estimated_cost': 0.5,
                'estimated_benefit': 0.8
            },
            'reduce_impact': {
                'action_type': 'reduce',
                'priority': 2,
                'estimated_cost': 0.6,
                'estimated_benefit': 0.7
            },
            'implement_controls': {
                'action_type': 'prevent',
                'priority': 1,
                'estimated_cost': 0.8,
                'estimated_benefit': 0.9
            },
            'transfer_risk': {
                'action_type': 'transfer',
                'priority': 3,
                'estimated_cost': 0.3,
                'estimated_benefit': 0.5
            },
            'accept_risk': {
                'action_type': 'accept',
                'priority': 4,
                'estimated_cost': 0.1,
                'estimated_benefit': 0.2
            }
        }

    def create_mitigation_action(self, risk_factor_id: str,
                                action_type: str,
                                action_name: str,
                                description: str,
                                priority: int = 1,
                                estimated_cost: float = 0.5,
                                estimated_benefit: float = 0.8) -> MitigationAction:
        """Create a new mitigation action"""
        action = MitigationAction(
            action_id=f"mitigation_{len(self.mitigation_actions)}",
            action_name=action_name,
            risk_factor_id=risk_factor_id,
            action_type=action_type,
            description=description,
            priority=priority,
            estimated_cost=estimated_cost,
            estimated_benefit=estimated_benefit,
            status="proposed"
        )

        with self.lock:
            self.mitigation_actions.append(action)

        return action

    def get_actions_for_risk(self, risk_factor_id: str) -> List[MitigationAction]:
        """Get mitigation actions for a specific risk"""
        return [ma for ma in self.mitigation_actions if ma.risk_factor_id == risk_factor_id]

    def approve_action(self, action_id: str) -> bool:
        """Approve a mitigation action"""
        with self.lock:
            for action in self.mitigation_actions:
                if action.action_id == action_id:
                    action.status = "approved"
                    return True
            return False

    def start_action(self, action_id: str, assigned_to: str) -> bool:
        """Start executing a mitigation action"""
        with self.lock:
            for action in self.mitigation_actions:
                if action.action_id == action_id:
                    action.status = "in_progress"
                    action.assigned_to = assigned_to
                    action.started_at = datetime.now(timezone.utc)
                    return True
            return False

    def complete_action(self, action_id: str, effectiveness: float) -> bool:
        """Complete a mitigation action"""
        with self.lock:
            for action in self.mitigation_actions:
                if action.action_id == action_id:
                    action.status = "completed"
                    action.completed_at = datetime.now(timezone.utc)
                    action.effectiveness = effectiveness
                    return True
            return False

    def get_action_status(self, action_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a mitigation action"""
        for action in self.mitigation_actions:
            if action.action_id == action_id:
                return {
                    'action_id': action.action_id,
                    'action_name': action.action_name,
                    'risk_factor_id': action.risk_factor_id,
                    'action_type': action.action_type,
                    'status': action.status,
                    'priority': action.priority,
                    'estimated_cost': action.estimated_cost,
                    'estimated_benefit': action.estimated_benefit,
                    'assigned_to': action.assigned_to,
                    'started_at': action.started_at.isoformat() if action.started_at else None,
                    'completed_at': action.completed_at.isoformat() if action.completed_at else None,
                    'effectiveness': action.effectiveness
                }
        return None


class RiskManager:
    """
    Main risk manager that coordinates all risk management activities

    The risk manager:
    - Assesses risks
    - Monitors risks for changes
    - Generates alerts
    - Plans and tracks mitigation actions
    - Provides risk reporting
    """

    def __init__(self, enable_risk_management: bool = True):
        self.enable_risk_management = enable_risk_management
        self.assessment = RiskAssessment()
        self.monitor = RiskMonitor(self.assessment)
        self.mitigation_planner = MitigationPlanner()
        self.lock = threading.Lock()

    def assess_risk(self, factor_id: str, factor_name: str,
                   category: RiskCategory, description: str,
                   probability: float, impact: float,
                   affected_components: List[str] = None,
                   metadata: Dict[str, Any] = None) -> RiskFactor:
        """Assess a new risk"""
        if not self.enable_risk_management:
            return None

        risk_factor = self.assessment.assess_risk(
            factor_id, factor_name, category, description,
            probability, impact, affected_components, metadata
        )

        # Check for alerts
        self.monitor.monitor_risks()

        return risk_factor

    def update_risk(self, factor_id: str, probability: Optional[float] = None,
                   impact: Optional[float] = None,
                   mitigation_status: Optional[str] = None,
                   mitigation_actions: Optional[List[str]] = None) -> Optional[RiskFactor]:
        """Update an existing risk"""
        if not self.enable_risk_management:
            return None

        risk_factor = self.assessment.update_risk(
            factor_id, probability, impact, mitigation_status, mitigation_actions
        )

        if risk_factor:
            # Check for alerts
            self.monitor.monitor_risks()

        return risk_factor

    def create_mitigation_action(self, risk_factor_id: str,
                                action_type: str,
                                action_name: str,
                                description: str,
                                priority: int = 1,
                                estimated_cost: float = 0.5,
                                estimated_benefit: float = 0.8) -> MitigationAction:
        """Create a mitigation action"""
        if not self.enable_risk_management:
            return None

        return self.mitigation_planner.create_mitigation_action(
            risk_factor_id, action_type, action_name, description,
            priority, estimated_cost, estimated_benefit
        )

    def get_risk_summary(self) -> Dict[str, Any]:
        """Get summary of all risks"""
        risks = self.assessment.get_all_risks()

        # Group by severity
        by_severity = defaultdict(list)
        for risk in risks:
            by_severity[risk.severity.name].append(risk)

        # Group by category
        by_category = defaultdict(list)
        for risk in risks:
            by_category[risk.category.value].append(risk)

        # Calculate aggregate metrics
        if risks:
            avg_risk_score = statistics.mean([r.risk_score for r in risks])
            max_risk_score = max([r.risk_score for r in risks])
            high_priority_count = len([r for r in risks if r.severity in [RiskSeverity.CRITICAL, RiskSeverity.HIGH]])
        else:
            avg_risk_score = 0.0
            max_risk_score = 0.0
            high_priority_count = 0

        return {
            'total_risks': len(risks),
            'average_risk_score': avg_risk_score,
            'max_risk_score': max_risk_score,
            'high_priority_risks': high_priority_count,
            'by_severity': {
                severity: len(risks_list)
                for severity, risks_list in by_severity.items()
            },
            'by_category': {
                category: len(risks_list)
                for category, risks_list in by_category.items()
            },
            'active_alerts': len(self.monitor.get_active_alerts())
        }

    def get_active_alerts(self) -> List[Dict[str, Any]]:
        """Get active risk alerts"""
        alerts = self.monitor.get_active_alerts()
        return [
            {
                'alert_id': a.alert_id,
                'risk_factor_id': a.risk_factor_id,
                'severity': a.severity.name,
                'message': a.message,
                'triggered_at': a.triggered_at.isoformat(),
                'acknowledged': a.acknowledged,
                'acknowledged_by': a.acknowledged_by,
                'acknowledged_at': a.acknowledged_at.isoformat() if a.acknowledged_at else None
            }
            for a in alerts
        ]

    def get_risk_matrix(self) -> Dict[str, Dict[str, int]]:
        """Get risk matrix (probability vs impact)"""
        risks = self.assessment.get_all_risks()

        matrix = {
            'critical': 0,  # High probability, High impact
            'high': 0,     # Medium probability, High impact
            'medium': 0,   # Low probability, High impact or High probability, Low impact
            'low': 0       # Low probability, Low impact
        }

        for risk in risks:
            if risk.probability >= 0.7 and risk.impact >= 0.7:
                matrix['critical'] += 1
            elif risk.probability >= 0.4 and risk.impact >= 0.7:
                matrix['high'] += 1
            elif risk.probability >= 0.7 or risk.impact >= 0.7:
                matrix['medium'] += 1
            else:
                matrix['low'] += 1

        return matrix

    def export_risk_data(self) -> Dict[str, Any]:
        """Export all risk data"""
        return {
            'summary': self.get_risk_summary(),
            'risk_factors': [
                {
                    'factor_id': rf.factor_id,
                    'factor_name': rf.factor_name,
                    'category': rf.category.value,
                    'description': rf.description,
                    'severity': rf.severity.name,
                    'probability': rf.probability,
                    'impact': rf.impact,
                    'risk_score': rf.risk_score,
                    'mitigation_status': rf.mitigation_status,
                    'affected_components': rf.affected_components
                }
                for rf in self.assessment.get_all_risks()
            ],
            'alerts': self.get_active_alerts(),
            'risk_matrix': self.get_risk_matrix()
        }
