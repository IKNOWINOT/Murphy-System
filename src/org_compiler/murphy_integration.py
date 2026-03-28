"""
Integration with Murphy System

Integrates Org Compiler with:
- Artifact Graph (Confidence Engine)
- Gate Synthesis Engine
- Execution Orchestrator
- Telemetry Pipeline
"""

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from .schemas import (
    HandoffEvent,
    RoleTemplate,
    SubstitutionGate,
    TemplateProposalArtifact,
    WorkArtifact,
)

logger = logging.getLogger(__name__)


class ArtifactGraphIntegration:
    """
    Integrates with Murphy's Artifact Graph

    Converts org compiler artifacts into graph nodes and edges.
    """

    @staticmethod
    def role_template_to_artifact(role_template: RoleTemplate) -> Dict:
        """
        Convert RoleTemplate to Artifact Graph node

        Returns:
            Dict compatible with Artifact Graph API
        """
        return {
            'artifact_id': role_template.role_id,
            'artifact_type': 'role_template',
            'content': {
                'role_name': role_template.role_name,
                'responsibilities': role_template.responsibilities,
                'authority_level': role_template.decision_authority.value,
                'input_artifacts': [a.value for a in role_template.input_artifacts],
                'output_artifacts': [a.value for a in role_template.output_artifacts],
                'compliance_constraints': [c.regulation for c in role_template.compliance_constraints],
                'escalation_paths': [p.to_role for p in role_template.escalation_paths]
            },
            'metadata': {
                'version': role_template.version,
                'created_at': role_template.created_at.isoformat(),
                'source_documents': role_template.source_documents
            },
            'integrity_hash': role_template.integrity_hash,
            'confidence': None,  # Will be computed by Confidence Engine
            'status': 'verified'  # Role templates are verified by compilation
        }

    @staticmethod
    def proposal_to_artifact(proposal: TemplateProposalArtifact) -> Dict:
        """
        Convert TemplateProposalArtifact to Artifact Graph node

        CRITICAL: Proposals are ALWAYS sandbox-only

        Returns:
            Dict compatible with Artifact Graph API
        """
        return {
            'artifact_id': proposal.proposal_id,
            'artifact_type': 'automation_proposal',
            'content': {
                'shadowed_role': proposal.shadowed_role,
                'automation_steps': proposal.proposed_automation_steps,
                'human_retained': proposal.human_retained_responsibilities,
                'success_rate': proposal.success_rate,
                'observation_window_days': proposal.observation_window_days
            },
            'metadata': {
                'created_at': proposal.created_at.isoformat(),
                'created_by': proposal.created_by,
                'evidence_references': proposal.evidence_references,
                'risk_analysis': proposal.risk_analysis
            },
            'integrity_hash': proposal.integrity_hash,
            'confidence': None,  # Will be computed by Confidence Engine
            'status': 'sandbox',  # ALWAYS sandbox
            'execution_rights': False  # NEVER has execution rights
        }

    @staticmethod
    def create_dependency_edges(role_template: RoleTemplate, handoffs: List[HandoffEvent]) -> List[Dict]:
        """
        Create dependency edges between roles

        Returns:
            List of edges for Artifact Graph
        """
        edges = []

        # Escalation edges
        for path in role_template.escalation_paths:
            edges.append({
                'from_artifact': role_template.role_id,
                'to_artifact': path.to_role,
                'edge_type': 'escalation',
                'metadata': {
                    'trigger_conditions': path.trigger_conditions,
                    'sla_hours': path.sla_hours
                }
            })

        # Handoff edges
        for handoff in handoffs:
            if handoff.from_role == role_template.role_name:
                edges.append({
                    'from_artifact': role_template.role_id,
                    'to_artifact': handoff.to_role,
                    'edge_type': 'handoff',
                    'metadata': {
                        'artifact_type': handoff.artifact.artifact_type.value,
                        'approval_required': handoff.approval_required
                    }
                })

        return edges


class GateSynthesisIntegration:
    """
    Integrates with Gate Synthesis Engine

    Converts substitution gates into Murphy gates.
    """

    @staticmethod
    def substitution_gate_to_murphy_gate(gate: SubstitutionGate, proposal: TemplateProposalArtifact) -> Dict:
        """
        Convert SubstitutionGate to Murphy Gate

        Returns:
            Dict compatible with Gate Synthesis API
        """
        murphy_gate = {
            'gate_id': gate.gate_id,
            'gate_type': 'substitution_gate',
            'description': gate.description,
            'status': gate.status.value,
            'criteria': [],
            'metadata': {
                'proposal_id': proposal.proposal_id,
                'shadowed_role': proposal.shadowed_role,
                'gate_subtype': gate.gate_type
            }
        }

        # Add type-specific criteria
        if gate.gate_type == 'performance_evidence':
            murphy_gate['criteria'].append({
                'criterion': 'observation_window',
                'required': gate.evidence_window_days,
                'actual': gate.evidence_window_days,
                'satisfied': gate.status.value == 'satisfied'
            })
            murphy_gate['criteria'].append({
                'criterion': 'success_rate',
                'required': gate.required_success_rate,
                'actual': gate.actual_success_rate,
                'satisfied': gate.actual_success_rate >= gate.required_success_rate if gate.actual_success_rate else False
            })

        elif gate.gate_type == 'deterministic_verification':
            murphy_gate['criteria'].append({
                'criterion': 'verification_exists',
                'required': True,
                'actual': gate.verification_passed,
                'satisfied': gate.verification_passed
            })

        elif gate.gate_type == 'compliance_check':
            murphy_gate['criteria'].append({
                'criterion': 'compliance_verified',
                'required': True,
                'actual': gate.compliance_verified,
                'satisfied': gate.compliance_verified,
                'regulation': gate.regulation
            })

        elif gate.gate_type == 'human_signoff':
            murphy_gate['criteria'].append({
                'criterion': 'signoff_granted',
                'required': True,
                'actual': gate.signoff_granted,
                'satisfied': gate.signoff_granted,
                'signoff_from': gate.signoff_required_from
            })

        return murphy_gate

    @staticmethod
    def create_gate_policy(proposal: TemplateProposalArtifact, gates: List[SubstitutionGate]) -> Dict:
        """
        Create gate policy for automation substitution

        Returns:
            Dict compatible with Gate Synthesis API
        """
        return {
            'policy_id': f"substitution_policy_{proposal.proposal_id}",
            'policy_type': 'automation_substitution',
            'target_role': proposal.shadowed_role,
            'gates': [gate.gate_id for gate in gates],
            'enforcement': 'all_gates_required',  # ALL gates must be satisfied
            'metadata': {
                'proposal_id': proposal.proposal_id,
                'created_at': datetime.now(timezone.utc).isoformat(),
                'risk_level': max(
                    proposal.risk_analysis.get('compliance_risk', 'low'),
                    proposal.risk_analysis.get('authority_risk', 'low'),
                    proposal.risk_analysis.get('quality_risk', 'low')
                )
            }
        }


class ExecutionOrchestratorIntegration:
    """
    Integrates with Execution Orchestrator

    Registers automation agents and enforces substitution gates.
    """

    @staticmethod
    def register_automation_agent(proposal: TemplateProposalArtifact, gates: List[SubstitutionGate]) -> Dict:
        """
        Register automation agent with Execution Orchestrator

        CRITICAL: Agent can only be registered if ALL gates are satisfied

        Returns:
            Dict compatible with Execution Orchestrator API
        """
        # Check if all gates are satisfied
        all_satisfied = all(gate.status.value == 'satisfied' for gate in gates)

        if not all_satisfied:
            raise ValueError("Cannot register automation agent: Not all gates are satisfied")

        return {
            'agent_id': f"automation_agent_{proposal.proposal_id}",
            'agent_type': 'role_automation',
            'shadowed_role': proposal.shadowed_role,
            'authority_level': 'low',  # Automation agents start with low authority
            'capabilities': proposal.proposed_automation_steps,
            'constraints': {
                'human_signoff_required': proposal.human_signoff_points,
                'escalation_paths_immutable': True,
                'compliance_constraints_enforced': True
            },
            'gates': [gate.gate_id for gate in gates],
            'status': 'registered',
            'metadata': {
                'proposal_id': proposal.proposal_id,
                'registered_at': datetime.now(timezone.utc).isoformat()
            }
        }

    @staticmethod
    def create_execution_constraints(role_template: RoleTemplate, proposal: TemplateProposalArtifact) -> Dict:
        """
        Create execution constraints for automation agent

        Returns:
            Dict with execution constraints
        """
        return {
            'agent_id': f"automation_agent_{proposal.proposal_id}",
            'constraints': {
                # Authority constraints
                'max_authority': 'low',
                'cannot_escalate': False,  # Can escalate but cannot modify paths
                'escalation_paths': [
                    {
                        'to_role': path.to_role,
                        'conditions': path.trigger_conditions,
                        'immutable': True
                    }
                    for path in role_template.escalation_paths
                ],

                # Compliance constraints
                'compliance_required': [
                    {
                        'regulation': c.regulation,
                        'verification_required': c.verification_required,
                        'human_signoff_required': c.human_signoff_required,
                        'immutable': True
                    }
                    for c in role_template.compliance_constraints
                ],

                # Human signoff constraints
                'human_signoff_points': proposal.human_signoff_points,

                # Execution constraints
                'can_create_execution_packets': False,  # Must go through compiler
                'can_modify_gates': False,
                'can_bypass_compliance': False
            }
        }


class TelemetryIntegration:
    """
    Integrates with Murphy's Telemetry Pipeline

    Sends org compiler events to telemetry system.
    """

    @staticmethod
    def send_role_compiled_event(role_template: RoleTemplate) -> Dict:
        """Send role compiled event"""
        return {
            'event_type': 'role_compiled',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'data': {
                'role_id': role_template.role_id,
                'role_name': role_template.role_name,
                'authority_level': role_template.decision_authority.value,
                'responsibilities_count': len(role_template.responsibilities),
                'compliance_constraints_count': len(role_template.compliance_constraints),
                'escalation_paths_count': len(role_template.escalation_paths)
            }
        }

    @staticmethod
    def send_proposal_generated_event(proposal: TemplateProposalArtifact) -> Dict:
        """Send proposal generated event"""
        return {
            'event_type': 'automation_proposal_generated',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'data': {
                'proposal_id': proposal.proposal_id,
                'shadowed_role': proposal.shadowed_role,
                'automation_steps_count': len(proposal.proposed_automation_steps),
                'success_rate': proposal.success_rate,
                'observation_window_days': proposal.observation_window_days,
                'risk_level': max(
                    proposal.risk_analysis.get('compliance_risk', 'low'),
                    proposal.risk_analysis.get('authority_risk', 'low'),
                    proposal.risk_analysis.get('quality_risk', 'low')
                )
            }
        }

    @staticmethod
    def send_gate_evaluated_event(gate: SubstitutionGate, proposal: TemplateProposalArtifact) -> Dict:
        """Send gate evaluated event"""
        return {
            'event_type': 'substitution_gate_evaluated',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'data': {
                'gate_id': gate.gate_id,
                'gate_type': gate.gate_type,
                'status': gate.status.value,
                'proposal_id': proposal.proposal_id,
                'shadowed_role': proposal.shadowed_role
            }
        }

    @staticmethod
    def send_substitution_approved_event(proposal: TemplateProposalArtifact, gates: List[SubstitutionGate]) -> Dict:
        """Send substitution approved event"""
        return {
            'event_type': 'automation_substitution_approved',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'data': {
                'proposal_id': proposal.proposal_id,
                'shadowed_role': proposal.shadowed_role,
                'gates_satisfied': len(gates),
                'automation_steps': proposal.proposed_automation_steps,
                'human_retained': proposal.human_retained_responsibilities
            }
        }


class MurphySystemBridge:
    """
    Complete bridge to Murphy System

    Provides unified interface for all Murphy integrations.
    """

    def __init__(self):
        self.artifact_graph = ArtifactGraphIntegration()
        self.gate_synthesis = GateSynthesisIntegration()
        self.orchestrator = ExecutionOrchestratorIntegration()
        self.telemetry = TelemetryIntegration()

    def register_role_template(self, role_template: RoleTemplate, handoffs: List[HandoffEvent] = None) -> Dict:
        """
        Register role template with Murphy System

        Returns:
            Dict with registration results
        """
        results = {}

        # 1. Add to Artifact Graph
        artifact = self.artifact_graph.role_template_to_artifact(role_template)
        results['artifact_graph'] = artifact

        # 2. Create dependency edges
        if handoffs:
            edges = self.artifact_graph.create_dependency_edges(role_template, handoffs)
            results['dependency_edges'] = edges

        # 3. Send telemetry
        telemetry_event = self.telemetry.send_role_compiled_event(role_template)
        results['telemetry'] = telemetry_event

        return results

    def register_automation_proposal(
        self,
        proposal: TemplateProposalArtifact,
        role_template: RoleTemplate,
        gates: List[SubstitutionGate]
    ) -> Dict:
        """
        Register automation proposal with Murphy System

        Returns:
            Dict with registration results
        """
        results = {}

        # 1. Add proposal to Artifact Graph (sandbox-only)
        artifact = self.artifact_graph.proposal_to_artifact(proposal)
        results['artifact_graph'] = artifact

        # 2. Create Murphy gates
        murphy_gates = [
            self.gate_synthesis.substitution_gate_to_murphy_gate(gate, proposal)
            for gate in gates
        ]
        results['murphy_gates'] = murphy_gates

        # 3. Create gate policy
        gate_policy = self.gate_synthesis.create_gate_policy(proposal, gates)
        results['gate_policy'] = gate_policy

        # 4. Send telemetry
        telemetry_event = self.telemetry.send_proposal_generated_event(proposal)
        results['telemetry'] = telemetry_event

        return results

    def approve_substitution(
        self,
        proposal: TemplateProposalArtifact,
        role_template: RoleTemplate,
        gates: List[SubstitutionGate]
    ) -> Dict:
        """
        Approve automation substitution (after all gates satisfied)

        CRITICAL: Can only be called if ALL gates are satisfied

        Returns:
            Dict with approval results
        """
        # Verify all gates are satisfied
        all_satisfied = all(gate.status.value == 'satisfied' for gate in gates)
        if not all_satisfied:
            raise ValueError("Cannot approve substitution: Not all gates are satisfied")

        results = {}

        # 1. Register automation agent with Orchestrator
        agent_registration = self.orchestrator.register_automation_agent(proposal, gates)
        results['agent_registration'] = agent_registration

        # 2. Create execution constraints
        constraints = self.orchestrator.create_execution_constraints(role_template, proposal)
        results['execution_constraints'] = constraints

        # 3. Send telemetry
        telemetry_event = self.telemetry.send_substitution_approved_event(proposal, gates)
        results['telemetry'] = telemetry_event

        return results
