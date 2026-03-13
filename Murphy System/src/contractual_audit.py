"""
Contractual Audit System
Detects productivity flow gaps and creates contractual agreements between agents
Monitors agent drift and triggers recalibration or domain knowledge expansion
"""

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("contractual_audit")


class GapType(Enum):
    """Types of productivity gaps"""
    COMMUNICATION = "communication"
    COORDINATION = "coordination"
    RESOURCE = "resource"
    KNOWLEDGE = "knowledge"
    CAPABILITY = "capability"
    PROCESS = "process"


class DriftLevel(Enum):
    """Agent drift levels"""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ProductivityGap:
    """Represents a productivity flow gap"""
    gap_id: str
    gap_type: GapType
    description: str
    affected_agents: List[str]
    severity: str  # low, medium, high, critical
    detected_at: str
    root_cause: Optional[str] = None
    suggested_solution: Optional[str] = None
    resolution_status: str = "open"  # open, in_progress, resolved

    def to_dict(self) -> Dict:
        return {
            "gap_id": self.gap_id,
            "gap_type": self.gap_type.value,
            "description": self.description,
            "affected_agents": self.affected_agents,
            "severity": self.severity,
            "detected_at": self.detected_at,
            "root_cause": self.root_cause,
            "suggested_solution": self.suggested_solution,
            "resolution_status": self.resolution_status
        }


@dataclass
class ContractualAgreement:
    """Contractual agreement between agents"""
    agreement_id: str
    agreement_type: str  # service_level, coordination, collaboration, handoff
    agent_1: str
    agent_2: str
    terms: Dict[str, Any]
    responsibilities: Dict[str, List[str]]
    obligations: List[str]
    metrics: List[str]
    created_at: str
    status: str = "active"  # active, suspended, terminated
    review_date: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "agreement_id": self.agreement_id,
            "agreement_type": self.agreement_type,
            "agent_1": self.agent_1,
            "agent_2": self.agent_2,
            "terms": self.terms,
            "responsibilities": self.responsibilities,
            "obligations": self.obligations,
            "metrics": self.metrics,
            "created_at": self.created_at,
            "status": self.status,
            "review_date": self.review_date
        }


@dataclass
class AgentDrift:
    """Represents agent drift from baseline"""
    drift_id: str
    agent_id: str
    drift_level: DriftLevel
    drift_type: str  # capability, knowledge, performance, behavior
    baseline_metrics: Dict[str, Any]
    current_metrics: Dict[str, Any]
    drift_description: str
    detected_at: str
    action_required: str  # recalibrate, expand_knowledge, retrain, no_action
    action_taken: Optional[str] = None
    action_timestamp: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "drift_id": self.drift_id,
            "agent_id": self.agent_id,
            "drift_level": self.drift_level.value,
            "drift_type": self.drift_type,
            "baseline_metrics": self.baseline_metrics,
            "current_metrics": self.current_metrics,
            "drift_description": self.drift_description,
            "detected_at": self.detected_at,
            "action_required": self.action_required,
            "action_taken": self.action_taken,
            "action_timestamp": self.action_timestamp
        }


class ContractualAuditSystem:
    """
    Contractual audit system for productivity flow gap detection
    Creates and manages contractual agreements between agents
    Monitors and handles agent drift
    """

    def __init__(self):
        self.gaps: Dict[str, ProductivityGap] = {}
        self.agreements: Dict[str, ContractualAgreement] = {}
        self.drifts: Dict[str, AgentDrift] = {}
        self.agent_baselines: Dict[str, Dict[str, Any]] = {}

        self.gap_count = 0
        self.agreement_count = 0
        self.drift_count = 0

        # Statistical knowledge of organization operations
        self.org_statistics = self._load_organization_statistics()

    def _load_organization_statistics(self) -> Dict[str, Any]:
        """Load statistical knowledge of typical organization operations"""
        return {
            "productivity_metrics": {
                "task_completion_rate": {"baseline": 0.85, "tolerance": 0.10},
                "response_time": {"baseline": 30.0, "tolerance": 10.0},
                "coordination_efficiency": {"baseline": 0.90, "tolerance": 0.05},
                "communication_frequency": {"baseline": 10.0, "tolerance": 3.0},
                "error_rate": {"baseline": 0.05, "tolerance": 0.02}
            },
            "collaboration_patterns": {
                "expert_validator_interaction": {"expected": 0.8, "tolerance": 0.15},
                "monitor_orchestrator_interaction": {"expected": 0.7, "tolerance": 0.15},
                "cross_role_coordination": {"expected": 0.6, "tolerance": 0.2}
            },
            "gap_thresholds": {
                "task_completion_rate": 0.70,
                "coordination_efficiency": 0.75,
                "communication_frequency": 5.0,
                "error_rate": 0.10
            }
        }

    def audit_productivity(
        self,
        system_state: Dict[str, Any],
        agent_metrics: Dict[str, Dict[str, Any]],
        timeframe: str = "daily"
    ) -> Tuple[List[ProductivityGap], Dict[str, Any]]:
        """
        Audit system productivity and detect gaps

        Args:
            system_state: Current system state
            agent_metrics: Metrics for each agent
            timeframe: Timeframe for audit (hourly, daily, weekly)

        Returns:
            Tuple of (detected_gaps, audit_summary)
        """
        detected_gaps = []
        audit_summary = {
            "timeframe": timeframe,
            "total_gaps_detected": 0,
            "by_severity": {},
            "by_type": {},
            "overall_score": 0.0
        }

        # Check task completion rates
        for agent_id, metrics in agent_metrics.items():
            if "task_completion_rate" in metrics:
                completion_rate = metrics["task_completion_rate"]
                threshold = self.org_statistics["gap_thresholds"]["task_completion_rate"]

                if completion_rate < threshold:
                    self.gap_count += 1
                    gap = ProductivityGap(
                        gap_id=f"gap_{self.gap_count}",
                        gap_type=GapType.CAPABILITY,
                        description=f"Agent {agent_id} task completion rate ({completion_rate:.2%}) below threshold ({threshold:.2%})",
                        affected_agents=[agent_id],
                        severity="high" if completion_rate < 0.5 else "medium",
                        detected_at=datetime.now(timezone.utc).isoformat(),
                        root_cause="Possible capability mismatch or resource constraint",
                        suggested_solution="Review agent capabilities and workload allocation"
                    )
                    detected_gaps.append(gap)
                    self.gaps[gap.gap_id] = gap

        # Check coordination efficiency
        if "coordination_efficiency" in system_state:
            coord_efficiency = system_state["coordination_efficiency"]
            threshold = self.org_statistics["gap_thresholds"]["coordination_efficiency"]

            if coord_efficiency < threshold:
                self.gap_count += 1
                gap = ProductivityGap(
                    gap_id=f"gap_{self.gap_count}",
                    gap_type=GapType.COORDINATION,
                    description=f"System coordination efficiency ({coord_efficiency:.2%}) below threshold ({threshold:.2%})",
                    affected_agents=[agent_id for agent_id in agent_metrics.keys()],
                    severity="high" if coord_efficiency < 0.6 else "medium",
                    detected_at=datetime.now(timezone.utc).isoformat(),
                    root_cause="Possible communication or workflow issues",
                    suggested_solution="Review inter-agent communication protocols"
                )
                detected_gaps.append(gap)
                self.gaps[gap.gap_id] = gap

        # Check communication patterns
        for agent_id, metrics in agent_metrics.items():
            if "communication_frequency" in metrics:
                comm_freq = metrics["communication_frequency"]
                threshold = self.org_statistics["gap_thresholds"]["communication_frequency"]

                if comm_freq < threshold:
                    self.gap_count += 1
                    gap = ProductivityGap(
                        gap_id=f"gap_{self.gap_count}",
                        gap_type=GapType.COMMUNICATION,
                        description=f"Agent {agent_id} communication frequency ({comm_freq}) below threshold ({threshold})",
                        affected_agents=[agent_id],
                        severity="medium",
                        detected_at=datetime.now(timezone.utc).isoformat(),
                        root_cause="Possible communication gap or isolation",
                        suggested_solution="Review agent communication protocols and workload"
                    )
                    detected_gaps.append(gap)
                    self.gaps[gap.gap_id] = gap

        # Update audit summary
        audit_summary["total_gaps_detected"] = len(detected_gaps)

        for gap in detected_gaps:
            # Count by severity
            severity = gap.severity
            audit_summary["by_severity"][severity] = audit_summary["by_severity"].get(severity, 0) + 1

            # Count by type
            gap_type = gap.gap_type.value
            audit_summary["by_type"][gap_type] = audit_summary["by_type"].get(gap_type, 0) + 1

        # Calculate overall score
        if detected_gaps:
            avg_severity_score = {
                "low": 0.1,
                "medium": 0.5,
                "high": 0.8,
                "critical": 1.0
            }
            total_severity = sum(avg_severity_score.get(gap.severity, 0.5) for gap in detected_gaps)
            audit_summary["overall_score"] = 1.0 - (total_severity / (len(detected_gaps) or 1))
        else:
            audit_summary["overall_score"] = 1.0

        return detected_gaps, audit_summary

    def detect_gaps(
        self,
        system_state: Dict[str, Any],
        requirements: List[str]
    ) -> List[ProductivityGap]:
        """
        Detect productivity flow gaps

        Args:
            system_state: Current system state
            requirements: System requirements

        Returns:
            List of detected gaps
        """
        gaps = []

        # Check if system meets requirements
        for requirement in requirements:
            # Parse requirement
            if "handle" in requirement.lower() and "concurrent" in requirement.lower():
                # Extract concurrent user requirement
                import re
                match = re.search(r'(\d+)\s*concurrent', requirement, re.IGNORECASE)
                if match:
                    required_users = int(match.group(1))
                    current_users = system_state.get("concurrent_users", 0)

                    if current_users < required_users:
                        self.gap_count += 1
                        gap = ProductivityGap(
                            gap_id=f"gap_{self.gap_count}",
                            gap_type=GapType.RESOURCE,
                            description=f"System capacity gap: {current_users} users vs required {required_users}",
                            affected_agents=[],
                            severity="high",
                            detected_at=datetime.now(timezone.utc).isoformat(),
                            root_cause="Insufficient resource allocation",
                            suggested_solution="Scale resources or optimize performance"
                        )
                        gaps.append(gap)
                        self.gaps[gap.gap_id] = gap

        # Check coordination gaps between agents
        if "agent_interactions" in system_state:
            interactions = system_state["agent_interactions"]
            expected_interaction = self.org_statistics["collaboration_patterns"]["expert_validator_interaction"]

            for agent_pair, interaction_rate in interactions.items():
                if interaction_rate < expected_interaction["expected"] - expected_interaction["tolerance"]:
                    self.gap_count += 1
                    gap = ProductivityGap(
                        gap_id=f"gap_{self.gap_count}",
                        gap_type=GapType.COORDINATION,
                        description=f"Coordination gap between {agent_pair}: {interaction_rate:.2%} vs expected {expected_interaction['expected']:.2%}",
                        affected_agents=agent_pair.split("_"),
                        severity="medium",
                        detected_at=datetime.now(timezone.utc).isoformat(),
                        root_cause="Insufficient agent coordination",
                        suggested_solution="Enhance inter-agent communication protocols"
                    )
                    gaps.append(gap)
                    self.gaps[gap.gap_id] = gap

        return gaps

    def generate_contract(
        self,
        gap_id: str,
        agents: List[str],
        agreement_type: str = "coordination"
    ) -> Optional[ContractualAgreement]:
        """
        Generate contractual agreement to close a gap

        Args:
            gap_id: ID of gap to close
            agents: Agents involved in agreement
            agreement_type: Type of agreement

        Returns:
            ContractualAgreement object or None if gap not found
        """
        if gap_id not in self.gaps:
            return None

        gap = self.gaps[gap_id]
        self.agreement_count += 1
        agreement_id = f"agreement_{self.agreement_count}"

        # Define agreement terms based on gap type
        if gap.gap_type == GapType.COMMUNICATION:
            terms = {
                "min_communication_frequency": 10,
                "response_time_limit": 30,
                "acknowledgment_required": True
            }
            obligations = [
                "Respond to all communications within 30 seconds",
                "Acknowledge receipt of all messages",
                "Maintain minimum communication frequency"
            ]
        elif gap.gap_type == GapType.COORDINATION:
            terms = {
                "coordination_frequency": "per_task",
                "sync_meetings": "daily",
                "shared_knowledge_base": True
            }
            obligations = [
                "Coordinate on all shared tasks",
                "Participate in daily sync meetings",
                "Update shared knowledge base"
            ]
        elif gap.gap_type == GapType.RESOURCE:
            terms = {
                "resource_sharing": True,
                "load_balancing": "auto",
                "escalation_threshold": 0.8
            }
            obligations = [
                "Share resources when available",
                "Participate in load balancing",
                "Escalate when capacity > 80%"
            ]
        else:
            terms = {}
            obligations = []

        # Define responsibilities
        responsibilities = {}
        for agent in agents:
            responsibilities[agent] = [
                f"Fulfill obligations related to {gap.gap_type.value}",
                "Report progress on gap closure",
                "Participate in agreement reviews"
            ]

        # Define metrics
        metrics = [
            "gap_closure_rate",
            "obligation_compliance_rate",
            "coordination_efficiency",
            "communication_frequency"
        ]

        # Create agreement
        agreement = ContractualAgreement(
            agreement_id=agreement_id,
            agreement_type=agreement_type,
            agent_1=agents[0] if len(agents) > 0 else "",
            agent_2=agents[1] if len(agents) > 1 else agents[0],
            terms=terms,
            responsibilities=responsibilities,
            obligations=obligations,
            metrics=metrics,
            created_at=datetime.now(timezone.utc).isoformat(),
            status="active"
        )

        self.agreements[agreement_id] = agreement

        # Update gap status
        gap.resolution_status = "in_progress"
        gap.suggested_solution = f"Addressed by contractual agreement {agreement_id}"

        return agreement

    def monitor_agent_drift(
        self,
        agent_id: str,
        current_metrics: Dict[str, Any]
    ) -> Optional[AgentDrift]:
        """
        Monitor agent for drift from baseline

        Args:
            agent_id: ID of agent to monitor
            current_metrics: Current metrics for agent

        Returns:
            AgentDrift object if drift detected, None otherwise
        """
        # Establish baseline if not exists
        if agent_id not in self.agent_baselines:
            self.agent_baselines[agent_id] = {
                "task_completion_rate": current_metrics.get("task_completion_rate", 0.85),
                "response_time": current_metrics.get("response_time", 30.0),
                "coordination_efficiency": current_metrics.get("coordination_efficiency", 0.90),
                "communication_frequency": current_metrics.get("communication_frequency", 10.0),
                "error_rate": current_metrics.get("error_rate", 0.05)
            }
            return None

        baseline = self.agent_baselines[agent_id]
        drift_detected = False
        drift_type = "performance"
        drift_level = DriftLevel.NONE
        drift_description = ""
        action_required = "no_action"

        # Check each metric for drift
        metric_baselines = self.org_statistics["productivity_metrics"]

        for metric_name, current_value in current_metrics.items():
            if metric_name not in baseline:
                continue

            baseline_value = baseline[metric_name]
            metric_config = metric_baselines.get(metric_name)

            if not metric_config:
                continue

            baseline_expected = metric_config["baseline"]
            tolerance = metric_config["tolerance"]

            # For metrics where higher is better
            if metric_name in ["task_completion_rate", "coordination_efficiency", "communication_frequency"]:
                if current_value < baseline_expected - tolerance:
                    drift_detected = True
                    drift_type = metric_name
                    drift_description = f"{metric_name} drifted from {baseline_value:.2%} to {current_value:.2%}"

                    # Determine drift level
                    if current_value < baseline_expected - 2 * tolerance:
                        drift_level = DriftLevel.CRITICAL
                        action_required = "retrain"
                    elif current_value < baseline_expected - tolerance:
                        drift_level = DriftLevel.HIGH
                        action_required = "recalibrate"
                    else:
                        drift_level = DriftLevel.MEDIUM
                        action_required = "expand_knowledge"

                    break

            # For metrics where lower is better
            elif metric_name in ["response_time", "error_rate"]:
                if current_value > baseline_expected + tolerance:
                    drift_detected = True
                    drift_type = metric_name
                    drift_description = f"{metric_name} drifted from {baseline_value} to {current_value}"

                    # Determine drift level
                    if current_value > baseline_expected + 2 * tolerance:
                        drift_level = DriftLevel.CRITICAL
                        action_required = "retrain"
                    elif current_value > baseline_expected + tolerance:
                        drift_level = DriftLevel.HIGH
                        action_required = "recalibrate"
                    else:
                        drift_level = DriftLevel.MEDIUM
                        action_required = "expand_knowledge"

                    break

        if drift_detected:
            self.drift_count += 1
            drift_id = f"drift_{self.drift_count}"

            drift = AgentDrift(
                drift_id=drift_id,
                agent_id=agent_id,
                drift_level=drift_level,
                drift_type=drift_type,
                baseline_metrics=baseline,
                current_metrics=current_metrics,
                drift_description=drift_description,
                detected_at=datetime.now(timezone.utc).isoformat(),
                action_required=action_required
            )

            self.drifts[drift_id] = drift
            return drift

        return None

    def handle_drift(self, drift_id: str, action: str) -> bool:
        """
        Handle detected agent drift

        Args:
            drift_id: ID of drift to handle
            action: Action taken (recalibrate, expand_knowledge, retrain)

        Returns:
            True if handled, False if not found
        """
        if drift_id not in self.drifts:
            return False

        drift = self.drifts[drift_id]
        drift.action_taken = action
        drift.action_timestamp = datetime.now(timezone.utc).isoformat()

        # Update baseline if action was successful
        if action in ["recalibrate", "expand_knowledge"]:
            # Update baseline to current metrics
            self.agent_baselines[drift.agent_id] = drift.current_metrics.copy()

        return True

    def get_active_gaps(self) -> List[ProductivityGap]:
        """Get all active gaps"""
        return [gap for gap in self.gaps.values() if gap.resolution_status == "open"]

    def get_active_agreements(self) -> List[ContractualAgreement]:
        """Get all active agreements"""
        return [agreement for agreement in self.agreements.values() if agreement.status == "active"]

    def get_pending_drifts(self) -> List[AgentDrift]:
        """Get all drifts awaiting action"""
        return [drift for drift in self.drifts.values() if drift.action_taken is None]

    def generate_audit_report(self) -> Dict[str, Any]:
        """Generate comprehensive audit report"""
        # Count gaps by status
        gaps_by_status = {}
        for gap in self.gaps.values():
            status = gap.resolution_status
            gaps_by_status[status] = gaps_by_status.get(status, 0) + 1

        # Count agreements by status
        agreements_by_status = {}
        for agreement in self.agreements.values():
            status = agreement.status
            agreements_by_status[status] = agreements_by_status.get(status, 0) + 1

        # Count drifts by level
        drifts_by_level = {}
        for drift in self.drifts.values():
            level = drift.drift_level.value
            drifts_by_level[level] = drifts_by_level.get(level, 0) + 1

        return {
            "total_gaps": len(self.gaps),
            "gaps_by_status": gaps_by_status,
            "total_agreements": len(self.agreements),
            "agreements_by_status": agreements_by_status,
            "total_drifts": len(self.drifts),
            "drifts_by_level": drifts_by_level,
            "agent_baselines": self.agent_baselines,
            "organization_statistics": self.org_statistics
        }


if __name__ == "__main__":
    # Test contractual audit system
    audit_system = ContractualAuditSystem()

    # Test 1: Audit productivity
    logger.info("=== Test 1: Audit Productivity ===")
    system_state = {
        "coordination_efficiency": 0.65,
        "concurrent_users": 500
    }

    agent_metrics = {
        "agent_001": {
            "task_completion_rate": 0.65,
            "response_time": 45.0,
            "communication_frequency": 6.0
        },
        "agent_002": {
            "task_completion_rate": 0.88,
            "response_time": 25.0,
            "communication_frequency": 12.0
        }
    }

    gaps, summary = audit_system.audit_productivity(system_state, agent_metrics)
    logger.info(f"Gaps detected: {len(gaps)}")
    logger.info(f"Overall score: {summary['overall_score']:.2%}")
    for gap in gaps:
        logger.info(f"  - {gap.description} ({gap.severity})")

    # Test 2: Detect gaps from requirements
    logger.info("\n=== Test 2: Detect Gaps ===")
    requirements = [
        "System shall handle 1000 concurrent users",
        "System shall maintain 99.9% uptime"
    ]

    system_state = {
        "concurrent_users": 750,
        "uptime_percentage": 99.5,
        "agent_interactions": {
            "agent_001_agent_002": 0.60,
            "agent_002_agent_003": 0.85
        }
    }

    gaps = audit_system.detect_gaps(system_state, requirements)
    logger.info(f"Gaps detected: {len(gaps)}")
    for gap in gaps:
        logger.info(f"  - {gap.description}")

    # Test 3: Generate contract
    logger.info("\n=== Test 3: Generate Contract ===")
    if gaps:
        contract = audit_system.generate_contract(
            gaps[0].gap_id,
            ["agent_001", "agent_002"],
            "coordination"
        )
        logger.info(f"Contract generated: {contract.agreement_id}")
        logger.info(f"Type: {contract.agreement_type}")
        logger.info(f"Obligations: {len(contract.obligations)}")
        logger.info(f"Metrics: {contract.metrics}")

    # Test 4: Monitor agent drift
    logger.info("\n=== Test 4: Monitor Agent Drift ===")
    drift = audit_system.monitor_agent_drift(
        "agent_001",
        {
            "task_completion_rate": 0.55,
            "response_time": 60.0,
            "coordination_efficiency": 0.75,
            "communication_frequency": 4.0,
            "error_rate": 0.08
        }
    )

    if drift:
        logger.info(f"Drift detected: {drift.drift_level.value}")
        logger.info(f"Type: {drift.drift_type}")
        logger.info(f"Action required: {drift.action_required}")
        logger.info(f"Description: {drift.drift_description}")

    # Test 5: Handle drift
    logger.info("\n=== Test 5: Handle Drift ===")
    if drift:
        handled = audit_system.handle_drift(drift.drift_id, "recalibrate")
        logger.info(f"Drift handled: {handled}")

    # Test 6: Generate audit report
    logger.info("\n=== Test 6: Audit Report ===")
    report = audit_system.generate_audit_report()
    logger.info(f"Total gaps: {report['total_gaps']}")
    logger.info(f"Total agreements: {report['total_agreements']}")
    logger.info(f"Total drifts: {report['total_drifts']}")
    logger.info(f"Gaps by status: {report['gaps_by_status']}")
# Alias for backward compatibility
ContractualAudit = ContractualAuditSystem
