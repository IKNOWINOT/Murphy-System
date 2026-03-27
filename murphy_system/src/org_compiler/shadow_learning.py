"""
Personal Assistant Builder — Shadow Learning System

YOUR assistant, built by YOU. This system observes your own workflow patterns
(task assignments, approvals, handoffs) and proposes automation templates
that you review and approve. Think of it as your "shadow" — a personal
apprentice that watches how you work and offers to handle the repetitive
parts, but only with your explicit permission.

The name "shadow" reflects the apprenticeship model: your assistant shadows
you to learn, just like a new team member would. It never acts autonomously
and all proposals require your signoff.

CRITICAL SAFETY CONSTRAINTS:
- Shadow agents can ONLY observe (no execution rights)
- All proposals are sandbox-only artifacts
- Cannot modify escalation paths
- Cannot bypass compliance constraints
- Substitution requires explicit gate satisfaction
"""

import logging
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Set, Tuple

from .schemas import (
    GateStatus,
    HandoffEvent,
    ProposalStatus,
    RoleTemplate,
    SubstitutionGate,
    TemplateProposalArtifact,
    WorkArtifact,
)

logger = logging.getLogger(__name__)


class TelemetryCollector:
    """
    Collects telemetry about your own work events to build your personal assistant.

    This is not surveillance of others — it records your own activity so that
    your shadow assistant can learn your patterns and propose time-saving
    automations for your review.

    Observes:
    - Task assignments (yours)
    - Approvals (yours)
    - Handoffs (yours)
    - Failure handling (yours)
    """

    def __init__(self):
        self.task_assignments: List[Dict] = []
        self.approvals: List[Dict] = []
        self.handoffs: List[HandoffEvent] = []
        self.failures: List[Dict] = []

    def record_task_assignment(self, role: str, task: str, timestamp: datetime, metadata: Dict = None):
        """Record a task assignment"""
        self.task_assignments.append({
            'role': role,
            'task': task,
            'timestamp': timestamp,
            'metadata': metadata or {}
        })

    def record_approval(self, role: str, approval_type: str, granted: bool, timestamp: datetime, metadata: Dict = None):
        """Record an approval event"""
        self.approvals.append({
            'role': role,
            'approval_type': approval_type,
            'granted': granted,
            'timestamp': timestamp,
            'metadata': metadata or {}
        })

    def record_handoff(self, event: HandoffEvent):
        """Record a handoff event"""
        self.handoffs.append(event)

    def record_failure(self, role: str, failure_type: str, timestamp: datetime, metadata: Dict = None):
        """Record a failure event"""
        self.failures.append({
            'role': role,
            'failure_type': failure_type,
            'timestamp': timestamp,
            'metadata': metadata or {}
        })

    def get_telemetry_for_role(self, role: str, days: int = 30) -> Dict:
        """Get telemetry data for a specific role"""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        return {
            'task_assignments': [t for t in self.task_assignments if t['role'] == role and t['timestamp'] >= cutoff],
            'approvals': [a for a in self.approvals if a['role'] == role and a['timestamp'] >= cutoff],
            'handoffs': [h for h in self.handoffs if (h.from_role == role or h.to_role == role) and h.timestamp >= cutoff],
            'failures': [f for f in self.failures if f['role'] == role and f['timestamp'] >= cutoff]
        }


class PatternRecognitionEngine:
    """
    Recognizes patterns in your workflow telemetry to identify tasks your assistant could handle.

    Identifies:
    - Repetitive tasks
    - Deterministic workflows
    - Approval patterns
    - Error patterns
    """

    @staticmethod
    def identify_repetitive_tasks(telemetry: Dict) -> List[Dict]:
        """Identify repetitive tasks that could be automated"""
        task_assignments = telemetry['task_assignments']

        # Count task frequencies
        task_counter = Counter(t['task'] for t in task_assignments)

        # Identify high-frequency tasks (>10 occurrences)
        repetitive = []
        for task, count in task_counter.items():
            if count >= 10:
                # Analyze task pattern
                task_events = [t for t in task_assignments if t['task'] == task]

                # Calculate success rate (assume success if no failure recorded)
                repetitive.append({
                    'task': task,
                    'frequency': count,
                    'avg_interval_hours': PatternRecognitionEngine._calculate_avg_interval(task_events),
                    'pattern_type': 'repetitive'
                })

        return repetitive

    @staticmethod
    def identify_deterministic_workflows(telemetry: Dict) -> List[Dict]:
        """Identify deterministic workflows (same inputs → same outputs)"""
        handoffs = telemetry['handoffs']

        # Group handoffs by artifact type
        workflow_patterns = defaultdict(list)
        for handoff in handoffs:
            key = (handoff.from_role, handoff.to_role, handoff.artifact.artifact_type.value)
            workflow_patterns[key].append(handoff)

        # Identify deterministic patterns (consistent duration, high success rate)
        deterministic = []
        for key, events in workflow_patterns.items():
            if len(events) >= 5:  # Need at least 5 samples
                durations = [e.duration_hours for e in events if e.duration_hours is not None]
                if durations:
                    avg_duration = statistics.mean(durations)
                    std_duration = statistics.stdev(durations) if len(durations) > 1 else 0

                    # Low variance = deterministic
                    if std_duration < avg_duration * 0.2:  # CV < 20%
                        deterministic.append({
                            'from_role': key[0],
                            'to_role': key[1],
                            'artifact_type': key[2],
                            'frequency': len(events),
                            'avg_duration_hours': avg_duration,
                            'std_duration_hours': std_duration,
                            'pattern_type': 'deterministic'
                        })

        return deterministic

    @staticmethod
    def identify_approval_patterns(telemetry: Dict) -> List[Dict]:
        """Identify approval patterns"""
        approvals = telemetry['approvals']

        # Group by approval type
        approval_patterns = defaultdict(list)
        for approval in approvals:
            approval_patterns[approval['approval_type']].append(approval)

        patterns = []
        for approval_type, events in approval_patterns.items():
            if len(events) >= 5:
                granted_count = sum(1 for e in events if e['granted'])
                approval_rate = granted_count / len(events)

                patterns.append({
                    'approval_type': approval_type,
                    'frequency': len(events),
                    'approval_rate': approval_rate,
                    'pattern_type': 'approval'
                })

        return patterns

    @staticmethod
    def identify_error_patterns(telemetry: Dict) -> List[Dict]:
        """Identify error patterns"""
        failures = telemetry['failures']

        # Group by failure type
        error_patterns = defaultdict(list)
        for failure in failures:
            error_patterns[failure['failure_type']].append(failure)

        patterns = []
        for failure_type, events in error_patterns.items():
            patterns.append({
                'failure_type': failure_type,
                'frequency': len(events),
                'pattern_type': 'error'
            })

        return patterns

    @staticmethod
    def _calculate_avg_interval(events: List[Dict]) -> float:
        """Calculate average interval between events"""
        if len(events) < 2:
            return 0.0

        sorted_events = sorted(events, key=lambda x: x['timestamp'])
        intervals = []
        for i in range(1, len(sorted_events)):
            delta = sorted_events[i]['timestamp'] - sorted_events[i-1]['timestamp']
            intervals.append(delta.total_seconds() / 3600)  # Convert to hours

        return statistics.mean(intervals) if intervals else 0.0


class EvidenceAggregator:
    """
    Aggregates evidence for automation proposals
    """

    @staticmethod
    def aggregate_evidence(telemetry: Dict, patterns: List[Dict]) -> List[str]:
        """Aggregate evidence references"""
        evidence = []

        # Task frequency evidence
        for pattern in patterns:
            if pattern['pattern_type'] == 'repetitive':
                evidence.append(f"Task '{pattern['task']}' performed {pattern['frequency']} times")
            elif pattern['pattern_type'] == 'deterministic':
                evidence.append(f"Workflow {pattern['from_role']}→{pattern['to_role']} has {pattern['frequency']} samples with CV={pattern['std_duration_hours']/pattern['avg_duration_hours']:.2%}")
            elif pattern['pattern_type'] == 'approval':
                evidence.append(f"Approval '{pattern['approval_type']}' granted {pattern['approval_rate']:.1%} of the time ({pattern['frequency']} samples)")

        # Success rate evidence
        total_tasks = len(telemetry['task_assignments'])
        total_failures = len(telemetry['failures'])
        if total_tasks > 0:
            success_rate = 1.0 - (total_failures / total_tasks)
            evidence.append(f"Overall success rate: {success_rate:.1%} ({total_tasks} tasks, {total_failures} failures)")

        return evidence


class RiskAnalyzer:
    """
    Analyzes risks of automation proposals
    """

    @staticmethod
    def analyze_risks(role_template: RoleTemplate, telemetry: Dict, patterns: List[Dict]) -> Dict:
        """Analyze risks of automating this role"""
        risks = {
            'compliance_risk': 'low',
            'authority_risk': 'low',
            'quality_risk': 'low',
            'escalation_risk': 'low',
            'details': []
        }

        # Compliance risk
        if role_template.compliance_constraints:
            risks['compliance_risk'] = 'high'
            risks['details'].append(f"Role has {len(role_template.compliance_constraints)} compliance constraints")

        # Authority risk
        if role_template.decision_authority.value in ['high', 'executive']:
            risks['authority_risk'] = 'high'
            risks['details'].append(f"Role has {role_template.decision_authority.value} authority level")

        # Quality risk (based on error patterns)
        error_patterns = [p for p in patterns if p['pattern_type'] == 'error']
        if error_patterns:
            total_errors = sum(p['frequency'] for p in error_patterns)
            if total_errors > 10:
                risks['quality_risk'] = 'medium'
                risks['details'].append(f"Role has {total_errors} recorded failures")

        # Escalation risk
        if role_template.escalation_paths:
            risks['escalation_risk'] = 'medium'
            risks['details'].append(f"Role has {len(role_template.escalation_paths)} escalation paths")

        return risks


class ShadowLearningAgent:
    """
    Your shadow assistant — OBSERVATION-ONLY. It watches how you work and proposes
    ways to automate repetitive tasks, but it can never execute, modify, or control
    anything without your explicit approval.

    Think of it as a new team member shadowing you to learn the ropes. Once it has
    observed enough of your workflow, it drafts an automation proposal for you to
    review. You decide what gets approved and what stays manual.

    CRITICAL: This agent is OBSERVATION-ONLY. It cannot execute, modify, or control anything.
    All proposals are sandbox-only artifacts with zero execution rights.
    """

    def __init__(self, telemetry_collector: TelemetryCollector):
        self.telemetry = telemetry_collector
        self.pattern_engine = PatternRecognitionEngine()
        self.evidence_aggregator = EvidenceAggregator()
        self.risk_analyzer = RiskAnalyzer()

    def observe_role(self, role_template: RoleTemplate, observation_window_days: int = 30) -> Optional[TemplateProposalArtifact]:
        """
        Observe a role and generate automation proposal if patterns detected

        Args:
            role_template: The role template to observe
            observation_window_days: Number of days to observe

        Returns:
            TemplateProposalArtifact if automation is feasible, None otherwise
        """
        # Collect telemetry for this role
        telemetry = self.telemetry.get_telemetry_for_role(
            role_template.role_name,
            days=observation_window_days
        )

        # Need minimum data to make proposal
        if len(telemetry['task_assignments']) < 10:
            return None

        # Identify patterns
        patterns = []
        patterns.extend(self.pattern_engine.identify_repetitive_tasks(telemetry))
        patterns.extend(self.pattern_engine.identify_deterministic_workflows(telemetry))
        patterns.extend(self.pattern_engine.identify_approval_patterns(telemetry))
        error_patterns = self.pattern_engine.identify_error_patterns(telemetry)
        patterns.extend(error_patterns)

        # Need patterns to propose automation
        if not patterns:
            return None

        # Generate automation steps
        automation_steps = self._generate_automation_steps(patterns)

        # Identify what remains human
        human_retained = self._identify_human_retained(role_template, patterns)

        # Aggregate evidence
        evidence = self.evidence_aggregator.aggregate_evidence(telemetry, patterns)

        # Analyze risks
        risk_analysis = self.risk_analyzer.analyze_risks(role_template, telemetry, patterns)

        # Calculate success rate
        total_tasks = len(telemetry['task_assignments'])
        total_failures = len(telemetry['failures'])
        success_rate = 1.0 - (total_failures / total_tasks) if total_tasks > 0 else 0.0

        # Generate required gates
        required_gates = self._generate_required_gates(role_template, risk_analysis, success_rate)

        # Create proposal artifact
        proposal = TemplateProposalArtifact(
            proposal_id=f"proposal_{role_template.role_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
            shadowed_role=role_template.role_name,
            proposed_automation_steps=automation_steps,
            evidence_references=evidence,
            risk_analysis=risk_analysis,
            required_gates=required_gates,
            human_retained_responsibilities=human_retained['responsibilities'],
            human_signoff_points=human_retained['signoff_points'],
            observation_window_days=observation_window_days,
            success_rate=success_rate,
            error_patterns=[p['failure_type'] for p in error_patterns],
            status=ProposalStatus.SANDBOX,  # ALWAYS sandbox
            execution_rights=False,  # NEVER has execution rights
            can_modify_escalation=False,  # CANNOT modify escalation
            can_bypass_compliance=False  # CANNOT bypass compliance
        )

        return proposal

    def _generate_automation_steps(self, patterns: List[Dict]) -> List[str]:
        """Generate proposed automation steps from patterns"""
        steps = []

        for pattern in patterns:
            if pattern['pattern_type'] == 'repetitive':
                steps.append(f"Automate repetitive task: {pattern['task']}")
            elif pattern['pattern_type'] == 'deterministic':
                steps.append(f"Automate deterministic workflow: {pattern['from_role']}→{pattern['to_role']}")
            elif pattern['pattern_type'] == 'approval':
                if pattern['approval_rate'] > 0.95:
                    steps.append(f"Auto-approve {pattern['approval_type']} (95%+ approval rate)")
                else:
                    steps.append(f"Pre-screen {pattern['approval_type']} for human review")

        return steps

    def _identify_human_retained(self, role_template: RoleTemplate, patterns: List[Dict]) -> Dict:
        """Identify what must remain human"""
        # CRITICAL: Certain things ALWAYS remain human
        human_retained = {
            'responsibilities': [],
            'signoff_points': []
        }

        # All compliance-related responsibilities remain human
        for constraint in role_template.compliance_constraints:
            human_retained['responsibilities'].append(f"Compliance: {constraint.regulation}")

        # All escalation paths remain human
        for path in role_template.escalation_paths:
            human_retained['responsibilities'].append(f"Escalation: {path.to_role}")

        # All required signoffs remain human
        human_retained['signoff_points'].extend(role_template.requires_human_signoff)

        # High-authority decisions remain human
        if role_template.decision_authority.value in ['high', 'executive']:
            human_retained['responsibilities'].append("High-authority decision making")

        return human_retained

    def _generate_required_gates(self, role_template: RoleTemplate, risk_analysis: Dict, success_rate: float) -> List[str]:
        """Generate list of required gate IDs"""
        gates = []

        # Performance evidence gate (always required)
        gates.append("performance_evidence_gate")

        # Deterministic verification gate (if any deterministic steps)
        gates.append("deterministic_verification_gate")

        # Compliance gates (if compliance constraints exist)
        if role_template.compliance_constraints:
            for constraint in role_template.compliance_constraints:
                gates.append(f"compliance_gate_{constraint.regulation}")

        # Human signoff gate (always required for substitution)
        gates.append("human_signoff_gate")

        return gates


class TemplateProposalGenerator:
    """
    Generates template proposals for multiple roles
    """

    def __init__(self, telemetry_collector: TelemetryCollector):
        self.shadow_agent = ShadowLearningAgent(telemetry_collector)

    def generate_proposals(self, role_templates: List[RoleTemplate], observation_window_days: int = 30) -> List[TemplateProposalArtifact]:
        """Generate proposals for all roles"""
        proposals = []

        for template in role_templates:
            proposal = self.shadow_agent.observe_role(template, observation_window_days)
            if proposal:
                proposals.append(proposal)

        return proposals
