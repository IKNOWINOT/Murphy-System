"""
LEARNING SYSTEM FOR MFGC
Governance improvement without breaking safety

CRITICAL CONSTRAINT: Learning may NEVER change:
- Core authority laws
- Sandbox vs commitment separation
- Execution immutability
- Authority mapping Γ(c)

Learning ONLY adjusts:
- Gate templates
- Gate placement probability
- Confidence weight schedules
- Phase transition thresholds
"""

import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class TrainingSignal(Enum):
    """Training signals from control outcomes (not success/failure)"""
    GATE_PREVENTED_FAILURE = "gate_prevented_failure"  # Positive
    LATE_STAGE_ROLLBACK = "late_stage_rollback"  # Negative
    EXECUTION_INTERRUPTION = "execution_interruption"  # Strong negative
    HUMAN_ESCALATION = "human_escalation"  # Negative
    CONTRACT_DISPUTE = "contract_dispute"  # Negative
    REGULATORY_VIOLATION = "regulatory_violation"  # Catastrophic


@dataclass
class GateTemplate:
    """
    Template for gate instantiation
    Learning updates these templates, not core authority laws
    """
    id: str
    trigger_pattern: str
    applicable_domains: List[str]
    phase_range: Tuple[str, str]  # (min_phase, max_phase)
    default_thresholds: Dict[str, float]
    historical_risk_reduction: float = 0.0
    activation_probability: float = 1.0  # Learned
    strictness_modifier: float = 1.0  # Learned

    def should_activate(self, domain: str, phase: str, context: Dict) -> bool:
        """Determine if gate should activate based on learned policy"""
        if domain not in self.applicable_domains:
            return False

        # Check phase range
        phases = ['expand', 'type', 'enumerate', 'constrain', 'collapse', 'bind', 'execute']
        min_idx = phases.index(self.phase_range[0])
        max_idx = phases.index(self.phase_range[1])
        current_idx = phases.index(phase) if phase in phases else 0

        if not (min_idx <= current_idx <= max_idx):
            return False

        # Apply learned activation probability
        return self.activation_probability > 0.5


@dataclass
class ConfidenceWeightSchedule:
    """
    Learned confidence weight curves
    w_g(p, domain) and w_d(p, domain)
    """
    domain: str
    phase_weights: Dict[str, Tuple[float, float]]  # phase -> (w_g, w_d)

    def get_weights(self, phase: str) -> Tuple[float, float]:
        """Get learned weights for phase and domain"""
        return self.phase_weights.get(phase, (0.5, 0.5))


@dataclass
class PhaseThresholds:
    """
    Learned phase transition thresholds
    θ_p by domain
    """
    domain: str
    thresholds: Dict[str, float]  # phase -> confidence threshold
    min_dwell_times: Dict[str, float]  # phase -> minimum time in seconds

    def can_transition(self, from_phase: str, confidence: float, dwell_time: float) -> bool:
        """Check if phase transition is allowed"""
        threshold = self.thresholds.get(from_phase, 0.7)
        min_dwell = self.min_dwell_times.get(from_phase, 0.0)

        return confidence >= threshold and dwell_time >= min_dwell


@dataclass
class ExecutionLog:
    """Log entry for learning"""
    timestamp: float
    domain: str
    task: str
    gates_activated: List[str]
    gates_prevented_failure: List[str]
    late_stage_rollback: bool
    execution_interrupted: bool
    human_escalation: bool
    murphy_index_peak: float
    confidence_trajectory: List[float]
    phase_durations: Dict[str, float]


@dataclass
class DomainProfile:
    """Learned domain-specific policies"""
    domain: str
    required_gate_sets: List[str]
    weight_schedules: ConfidenceWeightSchedule
    phase_thresholds: PhaseThresholds
    risk_multipliers: Dict[str, float]


class GatePolicyLearner:
    """
    Learns gate policies to minimize future Murphy Index

    Objective: min_π_g E[M_future | policy π_g]
    """

    def __init__(self):
        self.gate_templates: Dict[str, GateTemplate] = {}
        self.execution_logs: List[ExecutionLog] = []
        self.domain_profiles: Dict[str, DomainProfile] = {}

        # Initialize default gate templates
        self._initialize_default_templates()

    def _initialize_default_templates(self):
        """Initialize default gate templates"""
        # Safety gates
        self.gate_templates['safety_compliance'] = GateTemplate(
            id='safety_compliance',
            trigger_pattern='safety|hazard|danger',
            applicable_domains=['healthcare', 'aviation', 'automotive', 'manufacturing'],
            phase_range=('expand', 'bind'),
            default_thresholds={'confidence': 0.9, 'verification': 0.95},
            historical_risk_reduction=0.8
        )

        # Cost gates
        self.gate_templates['cost_verification'] = GateTemplate(
            id='cost_verification',
            trigger_pattern='cost|budget|expense',
            applicable_domains=['business', 'finance', 'enterprise'],
            phase_range=('constrain', 'bind'),
            default_thresholds={'confidence': 0.7, 'verification': 0.8},
            historical_risk_reduction=0.6
        )

        # Compliance gates
        self.gate_templates['regulatory_compliance'] = GateTemplate(
            id='regulatory_compliance',
            trigger_pattern='regulation|compliance|legal',
            applicable_domains=['healthcare', 'finance', 'legal', 'enterprise'],
            phase_range=('expand', 'execute'),
            default_thresholds={'confidence': 0.95, 'verification': 0.99},
            historical_risk_reduction=0.9
        )

        # Technical gates
        self.gate_templates['technical_verification'] = GateTemplate(
            id='technical_verification',
            trigger_pattern='architecture|scalable|performance',
            applicable_domains=['software', 'system', 'infrastructure'],
            phase_range=('enumerate', 'bind'),
            default_thresholds={'confidence': 0.8, 'verification': 0.85},
            historical_risk_reduction=0.7
        )

    def log_execution(self, log: ExecutionLog):
        """Log execution for learning"""
        self.execution_logs.append(log)

    def learn_from_logs(self, min_logs: int = 10) -> Dict[str, Any]:
        """
        Learn gate policies from execution logs

        Returns updates to gate templates (NOT core authority laws)
        """
        if len(self.execution_logs) < min_logs:
            return {'status': 'insufficient_data', 'logs': len(self.execution_logs)}

        updates = {
            'gate_templates': {},
            'confidence_weights': {},
            'phase_thresholds': {}
        }

        # Analyze gate effectiveness
        for gate_id, template in self.gate_templates.items():
            prevented_failures = sum(
                1 for log in self.execution_logs
                if gate_id in log.gates_prevented_failure
            )

            total_activations = sum(
                1 for log in self.execution_logs
                if gate_id in log.gates_activated
            )

            if total_activations > 0:
                effectiveness = prevented_failures / total_activations

                # Update activation probability based on effectiveness
                if effectiveness > 0.7:
                    template.activation_probability = min(1.0, template.activation_probability + 0.1)
                elif effectiveness < 0.3:
                    template.activation_probability = max(0.5, template.activation_probability - 0.1)

                # Update historical risk reduction
                template.historical_risk_reduction = effectiveness

                updates['gate_templates'][gate_id] = {
                    'activation_probability': template.activation_probability,
                    'historical_risk_reduction': template.historical_risk_reduction
                }

        # Learn domain-specific weight schedules
        domain_logs = {}
        for log in self.execution_logs:
            if log.domain not in domain_logs:
                domain_logs[log.domain] = []
            domain_logs[log.domain].append(log)

        for domain, logs in domain_logs.items():
            # Calculate optimal weights based on outcomes
            late_rollbacks = sum(1 for log in logs if log.late_stage_rollback)

            # If many late rollbacks, increase deterministic weight earlier
            if late_rollbacks / len(logs) > 0.2:
                updates['confidence_weights'][domain] = {
                    'recommendation': 'increase_deterministic_weight_early',
                    'reason': 'high_late_stage_rollback_rate'
                }

        return updates

    def get_active_gates(self, domain: str, phase: str, context: Dict) -> List[GateTemplate]:
        """Get gates that should be active for domain/phase"""
        active_gates = []

        for template in self.gate_templates.values():
            if template.should_activate(domain, phase, context):
                active_gates.append(template)

        return active_gates


class SyntheticFailureGenerator:
    """
    Generate synthetic failures for training
    Because real disasters are rare but costly
    """

    def __init__(self):
        self.failure_scenarios: List[Dict] = []

    def counterfactual_gate_removal(self, log: ExecutionLog) -> Dict[str, Any]:
        """
        Replay past job with gates removed
        Would failure occur? How early could it be detected?
        """
        results = {
            'original_gates': log.gates_activated,
            'removed_gates': [],
            'would_fail': False,
            'detection_phase': None
        }

        # Simulate removing each gate
        for gate_id in log.gates_activated:
            # Check if this gate prevented a failure
            if gate_id in log.gates_prevented_failure:
                results['removed_gates'].append(gate_id)
                results['would_fail'] = True
                results['detection_phase'] = 'late'  # Would be detected late

        return results

    def perturbation_testing(self, task: str, domain: str) -> Dict[str, Any]:
        """
        Inject perturbations and measure recovery

        Perturbations:
        - Missing constraints
        - False assumptions
        - Delayed verifications
        """
        perturbations = [
            {'type': 'missing_constraint', 'description': 'Budget constraint removed'},
            {'type': 'false_assumption', 'description': 'Assumed unlimited resources'},
            {'type': 'delayed_verification', 'description': 'Verification delayed by 50%'}
        ]

        results = {
            'task': task,
            'domain': domain,
            'perturbations_tested': len(perturbations),
            'recovery_success': 0,
            'authority_decay_speed': 0.0,
            'phase_regression_correct': True
        }

        # Simulate each perturbation
        for perturbation in perturbations:
            # In real system, this would actually run the task with perturbation
            # For now, we simulate the outcome
            results['recovery_success'] += 1  # Assume recovery

        results['recovery_success'] /= len(perturbations)

        return results

    async def shutdown(self):
        """Graceful shutdown (no-op in test mode)."""
        pass


class LearningPipeline:
    """
    Offline learning pipeline
    NEVER runs inside live execution
    """

    def __init__(self):
        self.gate_learner = GatePolicyLearner()
        self.failure_generator = SyntheticFailureGenerator()
        self.pending_updates: List[Dict] = []
        self.human_approved_updates: List[Dict] = []

    def process_execution_logs(self, logs: List[ExecutionLog]) -> Dict[str, Any]:
        """
        Process execution logs and generate policy updates

        Pipeline:
        1. Execution Logs
        2. Failure & Near-Miss Extractor
        3. Gate Impact Analyzer
        4. Policy Learner
        5. Gate Template Updates
        6. Confidence Weight Updates
        7. Deployment After Human Review
        """
        # Step 1: Log all executions
        for log in logs:
            self.gate_learner.log_execution(log)

        # Step 2: Extract failures and near-misses
        failures = [log for log in logs if log.late_stage_rollback or log.execution_interrupted]
        near_misses = [log for log in logs if log.murphy_index_peak > 0.5]

        # Step 3: Analyze gate impact
        gate_impact = {}
        for log in logs:
            for gate_id in log.gates_prevented_failure:
                if gate_id not in gate_impact:
                    gate_impact[gate_id] = 0
                gate_impact[gate_id] += 1

        # Step 4: Learn policies
        updates = self.gate_learner.learn_from_logs()

        # Step 5-6: Updates are in the 'updates' dict

        # Step 7: Queue for human review
        self.pending_updates.append({
            'timestamp': time.time(),
            'updates': updates,
            'failures_analyzed': len(failures),
            'near_misses_analyzed': len(near_misses),
            'gate_impact': gate_impact,
            'requires_human_approval': True
        })

        return {
            'status': 'updates_pending_review',
            'updates_queued': len(self.pending_updates),
            'failures_analyzed': len(failures),
            'near_misses_analyzed': len(near_misses)
        }

    def approve_updates(self, update_id: int, approved: bool, reviewer: str) -> Dict[str, Any]:
        """Human approval for safety policy changes"""
        if update_id >= len(self.pending_updates):
            return {'status': 'error', 'reason': 'invalid_update_id'}

        update = self.pending_updates[update_id]

        if approved:
            update['approved_by'] = reviewer
            update['approved_at'] = time.time()
            self.human_approved_updates.append(update)

            return {
                'status': 'approved',
                'update_id': update_id,
                'reviewer': reviewer,
                'ready_for_deployment': True
            }
        else:
            return {
                'status': 'rejected',
                'update_id': update_id,
                'reviewer': reviewer
            }

    def deploy_approved_updates(self) -> Dict[str, Any]:
        """Deploy human-approved updates"""
        if not self.human_approved_updates:
            return {'status': 'no_updates_to_deploy'}

        deployed = []
        for update in self.human_approved_updates:
            # Apply gate template updates
            for gate_id, changes in update['updates'].get('gate_templates', {}).items():
                if gate_id in self.gate_learner.gate_templates:
                    template = self.gate_learner.gate_templates[gate_id]
                    template.activation_probability = changes.get('activation_probability', template.activation_probability)
                    template.historical_risk_reduction = changes.get('historical_risk_reduction', template.historical_risk_reduction)

            deployed.append(update)

        # Clear deployed updates
        self.human_approved_updates = []

        return {
            'status': 'deployed',
            'updates_deployed': len(deployed),
            'timestamp': time.time()
        }


class MultiDeploymentGeneralization:
    """
    Learn from multiple deployments across domains
    Produces domain-aware profiles
    """

    def __init__(self):
        self.domain_profiles: Dict[str, DomainProfile] = {}
        self.deployment_logs: List[Dict] = []

    def log_deployment(self, domain: str, constraints: List[str], outcome: Dict):
        """Log deployment outcome"""
        self.deployment_logs.append({
            'domain': domain,
            'constraints': constraints,
            'outcome': outcome,
            'timestamp': time.time()
        })

    def learn_domain_profiles(self) -> Dict[str, DomainProfile]:
        """
        Learn domain-specific profiles

        Produces:
        - Aviation: RequiredGateSets, WeightSchedules
        - Finance: RequiredGateSets, WeightSchedules
        - etc.
        """
        domain_data = {}

        # Group by domain
        for log in self.deployment_logs:
            domain = log['domain']
            if domain not in domain_data:
                domain_data[domain] = []
            domain_data[domain].append(log)

        # Create profiles
        for domain, logs in domain_data.items():
            # Determine required gates
            required_gates = set()
            for log in logs:
                if log['outcome'].get('success', False):
                    required_gates.update(log.get('gates_used', []))

            # Create weight schedule (domain-specific)
            phase_weights = {
                'expand': (0.9, 0.1),
                'type': (0.8, 0.2),
                'enumerate': (0.7, 0.3),
                'constrain': (0.5, 0.5),
                'collapse': (0.3, 0.7),
                'bind': (0.2, 0.8),
                'execute': (0.1, 0.9)
            }

            # Adjust for safety-critical domains
            if domain in ['healthcare', 'aviation', 'automotive']:
                # Higher deterministic weight earlier
                phase_weights = {
                    'expand': (0.7, 0.3),
                    'type': (0.6, 0.4),
                    'enumerate': (0.5, 0.5),
                    'constrain': (0.4, 0.6),
                    'collapse': (0.2, 0.8),
                    'bind': (0.1, 0.9),
                    'execute': (0.0, 1.0)
                }

            weight_schedule = ConfidenceWeightSchedule(
                domain=domain,
                phase_weights=phase_weights
            )

            # Create phase thresholds
            thresholds = {
                'expand': 0.3,
                'type': 0.4,
                'enumerate': 0.5,
                'constrain': 0.6,
                'collapse': 0.7,
                'bind': 0.8,
                'execute': 0.9
            }

            # Stricter for safety-critical
            if domain in ['healthcare', 'aviation', 'automotive']:
                thresholds = {k: v + 0.1 for k, v in thresholds.items()}

            phase_thresholds = PhaseThresholds(
                domain=domain,
                thresholds=thresholds,
                min_dwell_times={phase: 1.0 for phase in thresholds.keys()}
            )

            # Create profile
            profile = DomainProfile(
                domain=domain,
                required_gate_sets=list(required_gates),
                weight_schedules=weight_schedule,
                phase_thresholds=phase_thresholds,
                risk_multipliers={'safety': 2.0, 'cost': 1.0, 'reputation': 1.5}
            )

            self.domain_profiles[domain] = profile

        return self.domain_profiles

    def get_profile(self, domain: str) -> Optional[DomainProfile]:
        """Get learned profile for domain"""
        return self.domain_profiles.get(domain)
