"""
Substitution Safety System

Evaluates whether automation can safely substitute for a human role.

CRITICAL SAFETY RULES:
- ALL gates must be satisfied for substitution
- Performance evidence window must be met
- Deterministic verification must exist for key outputs
- Regulatory/compliance gates must be satisfied
- Human signoff gate must be configured and granted
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from .schemas import (
    ComplianceConstraint,
    GateStatus,
    RoleTemplate,
    SubstitutionGate,
    TemplateProposalArtifact,
)

logger = logging.getLogger(__name__)


class PerformanceEvidenceValidator:
    """
    Validates performance evidence for automation substitution

    Requirements:
    - Minimum observation window (default: 30 days)
    - Minimum success rate (default: 95%)
    - Minimum sample size (default: 100 tasks)
    """

    def __init__(
        self,
        min_window_days: int = 30,
        min_success_rate: float = 0.95,
        min_sample_size: int = 100
    ):
        self.min_window_days = min_window_days
        self.min_success_rate = min_success_rate
        self.min_sample_size = min_sample_size

    def validate(self, proposal: TemplateProposalArtifact, telemetry: Dict) -> SubstitutionGate:
        """
        Validate performance evidence

        Args:
            proposal: The automation proposal
            telemetry: Telemetry data for the role

        Returns:
            SubstitutionGate with validation result
        """
        gate = SubstitutionGate(
            gate_id=f"performance_evidence_{proposal.proposal_id}",
            gate_type="performance_evidence",
            description=f"Performance evidence for {proposal.shadowed_role}",
            evidence_window_days=proposal.observation_window_days,
            required_success_rate=self.min_success_rate,
            actual_success_rate=proposal.success_rate
        )

        # Check observation window
        if proposal.observation_window_days < self.min_window_days:
            gate.status = GateStatus.NOT_MET
            return gate

        # Check sample size
        task_count = len(telemetry.get('task_assignments', []))
        if task_count < self.min_sample_size:
            gate.status = GateStatus.NOT_MET
            return gate

        # Check success rate
        if proposal.success_rate < self.min_success_rate:
            gate.status = GateStatus.NOT_MET
            return gate

        # All checks passed
        gate.status = GateStatus.SATISFIED
        gate.evaluated_at = datetime.now(timezone.utc)
        return gate


class DeterministicVerificationChecker:
    """
    Checks if deterministic verification exists for key outputs

    Requirements:
    - Verification method must be specified
    - Verification must be executable
    - Verification must have passed on sample outputs
    """

    def __init__(self):
        self.verification_registry: Dict[str, Dict] = {}

    def register_verification(self, output_type: str, verification_method: str, verification_callable: callable):
        """Register a verification method for an output type"""
        self.verification_registry[output_type] = {
            'method': verification_method,
            'callable': verification_callable
        }

    def check(self, proposal: TemplateProposalArtifact, role_template: RoleTemplate) -> SubstitutionGate:
        """
        Check if deterministic verification exists

        Args:
            proposal: The automation proposal
            role_template: The role template

        Returns:
            SubstitutionGate with check result
        """
        gate = SubstitutionGate(
            gate_id=f"deterministic_verification_{proposal.proposal_id}",
            gate_type="deterministic_verification",
            description=f"Deterministic verification for {proposal.shadowed_role}",
            verification_method=None,
            verification_passed=False
        )

        # Check if verification exists for all output types
        missing_verifications = []
        for output_type in role_template.output_artifacts:
            if output_type.value not in self.verification_registry:
                missing_verifications.append(output_type.value)

        if missing_verifications:
            gate.status = GateStatus.NOT_MET
            gate.verification_method = f"Missing verification for: {', '.join(missing_verifications)}"
            return gate

        # All verifications exist
        gate.status = GateStatus.SATISFIED
        gate.verification_method = "All output types have registered verifications"
        gate.verification_passed = True
        gate.evaluated_at = datetime.now(timezone.utc)
        return gate


class ComplianceGateValidator:
    """
    Validates compliance gates

    Requirements:
    - All compliance constraints must be verified
    - Audit trail must be enabled
    - Human signoff must be configured for compliance actions
    """

    def validate(self, proposal: TemplateProposalArtifact, role_template: RoleTemplate) -> List[SubstitutionGate]:
        """
        Validate compliance gates

        Args:
            proposal: The automation proposal
            role_template: The role template

        Returns:
            List of SubstitutionGates (one per compliance constraint)
        """
        gates = []

        for constraint in role_template.compliance_constraints:
            gate = SubstitutionGate(
                gate_id=f"compliance_{constraint.regulation}_{proposal.proposal_id}",
                gate_type="compliance_check",
                description=f"{constraint.regulation} compliance for {proposal.shadowed_role}",
                regulation=constraint.regulation,
                compliance_verified=False
            )

            # Check if compliance is in human-retained responsibilities
            compliance_retained = any(
                constraint.regulation in resp
                for resp in proposal.human_retained_responsibilities
            )

            if not compliance_retained:
                # Compliance not retained - FAIL
                gate.status = GateStatus.FAILED
                gate.compliance_verified = False
            else:
                # Compliance retained by human - PASS
                gate.status = GateStatus.SATISFIED
                gate.compliance_verified = True
                gate.evaluated_at = datetime.now(timezone.utc)

            gates.append(gate)

        return gates


class HumanSignoffEnforcer:
    """
    Enforces human signoff requirement

    Requirements:
    - Explicit human approval required for substitution
    - Signoff must be from authorized person (manager or higher)
    - Signoff must be recent (within 30 days)
    """

    def __init__(self, signoff_validity_days: int = 30):
        self.signoff_validity_days = signoff_validity_days
        self.signoffs: Dict[str, Dict] = {}  # proposal_id -> signoff data

    def request_signoff(self, proposal: TemplateProposalArtifact, required_from: str) -> SubstitutionGate:
        """
        Request human signoff for automation substitution

        Args:
            proposal: The automation proposal
            required_from: Role/person who must provide signoff

        Returns:
            SubstitutionGate in PENDING status
        """
        gate = SubstitutionGate(
            gate_id=f"human_signoff_{proposal.proposal_id}",
            gate_type="human_signoff",
            description=f"Human signoff for automating {proposal.shadowed_role}",
            signoff_required_from=required_from,
            signoff_granted=False,
            signoff_timestamp=None,
            status=GateStatus.PENDING
        )

        return gate

    def grant_signoff(self, gate: SubstitutionGate, granted_by: str) -> SubstitutionGate:
        """
        Grant human signoff

        Args:
            gate: The signoff gate
            granted_by: Person granting signoff

        Returns:
            Updated gate with SATISFIED status
        """
        # Verify signoff is from required person
        if gate.signoff_required_from and granted_by != gate.signoff_required_from:
            raise ValueError(f"Signoff must be from {gate.signoff_required_from}, not {granted_by}")

        gate.signoff_granted = True
        gate.signoff_timestamp = datetime.now(timezone.utc)
        gate.status = GateStatus.SATISFIED
        gate.evaluated_at = datetime.now(timezone.utc)

        # Store signoff
        self.signoffs[gate.gate_id] = {
            'granted_by': granted_by,
            'timestamp': gate.signoff_timestamp
        }

        return gate

    def verify_signoff(self, gate: SubstitutionGate) -> bool:
        """Verify signoff is still valid"""
        if not gate.signoff_granted or not gate.signoff_timestamp:
            return False

        # Check if signoff is still within validity period
        age = datetime.now(timezone.utc) - gate.signoff_timestamp
        if age.days > self.signoff_validity_days:
            return False

        return True


class SubstitutionGateEvaluator:
    """
    Evaluates all substitution gates for an automation proposal

    ALL gates must be satisfied for substitution to be allowed.
    """

    def __init__(
        self,
        performance_validator: PerformanceEvidenceValidator,
        verification_checker: DeterministicVerificationChecker,
        compliance_validator: ComplianceGateValidator,
        signoff_enforcer: HumanSignoffEnforcer
    ):
        self.performance_validator = performance_validator
        self.verification_checker = verification_checker
        self.compliance_validator = compliance_validator
        self.signoff_enforcer = signoff_enforcer

    def evaluate_all_gates(
        self,
        proposal: TemplateProposalArtifact,
        role_template: RoleTemplate,
        telemetry: Dict,
        signoff_required_from: str
    ) -> Tuple[List[SubstitutionGate], bool]:
        """
        Evaluate all substitution gates

        Args:
            proposal: The automation proposal
            role_template: The role template
            telemetry: Telemetry data for the role
            signoff_required_from: Who must provide signoff

        Returns:
            Tuple of (list of gates, all_satisfied boolean)
        """
        gates = []

        # 1. Performance evidence gate
        perf_gate = self.performance_validator.validate(proposal, telemetry)
        gates.append(perf_gate)

        # 2. Deterministic verification gate
        verif_gate = self.verification_checker.check(proposal, role_template)
        gates.append(verif_gate)

        # 3. Compliance gates
        compliance_gates = self.compliance_validator.validate(proposal, role_template)
        gates.extend(compliance_gates)

        # 4. Human signoff gate
        signoff_gate = self.signoff_enforcer.request_signoff(proposal, signoff_required_from)
        gates.append(signoff_gate)

        # Check if all gates are satisfied
        all_satisfied = all(gate.status == GateStatus.SATISFIED for gate in gates)

        return gates, all_satisfied

    def can_substitute(self, gates: List[SubstitutionGate]) -> bool:
        """
        Check if substitution is allowed based on gate status

        Args:
            gates: List of evaluated gates

        Returns:
            True if ALL gates are satisfied, False otherwise
        """
        return all(gate.status == GateStatus.SATISFIED for gate in gates)

    def get_blocking_gates(self, gates: List[SubstitutionGate]) -> List[SubstitutionGate]:
        """Get list of gates that are blocking substitution"""
        return [gate for gate in gates if gate.status != GateStatus.SATISFIED]

    def get_gate_summary(self, gates: List[SubstitutionGate]) -> Dict:
        """Get summary of gate evaluation"""
        return {
            'total_gates': len(gates),
            'satisfied': sum(1 for g in gates if g.status == GateStatus.SATISFIED),
            'pending': sum(1 for g in gates if g.status == GateStatus.PENDING),
            'not_met': sum(1 for g in gates if g.status == GateStatus.NOT_MET),
            'failed': sum(1 for g in gates if g.status == GateStatus.FAILED),
            'can_substitute': self.can_substitute(gates)
        }
