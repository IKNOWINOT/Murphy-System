"""
Visualization & Explainability

Provides views of:
- Role → Work graph
- Automation coverage
- Gating checklist
- Human vs automated work breakdown
"""

import json
import logging
from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple

from .schemas import (
    GateStatus,
    HandoffEvent,
    ProcessFlow,
    RoleTemplate,
    SubstitutionGate,
    TemplateProposalArtifact,
)

logger = logging.getLogger(__name__)


class RoleWorkGraphGenerator:
    """
    Generates Role → Work graph visualization

    Shows:
    - Responsibilities
    - Input/output artifacts
    - Handoffs to/from other roles
    - Decision points
    - Escalation paths
    """

    @staticmethod
    def generate_graph(role_template: RoleTemplate, handoffs: List[HandoffEvent] = None) -> Dict:
        """
        Generate role work graph

        Returns:
            Dict with nodes and edges for visualization
        """
        graph = {
            'nodes': [],
            'edges': [],
            'metadata': {
                'role_name': role_template.role_name,
                'authority_level': role_template.decision_authority.value,
                'compliance_constraints': len(role_template.compliance_constraints)
            }
        }

        # Central role node
        graph['nodes'].append({
            'id': role_template.role_name,
            'type': 'role',
            'label': role_template.role_name,
            'authority': role_template.decision_authority.value
        })

        # Responsibility nodes
        for i, resp in enumerate(role_template.responsibilities):
            node_id = f"resp_{i}"
            graph['nodes'].append({
                'id': node_id,
                'type': 'responsibility',
                'label': resp[:50] + '...' if len(resp) > 50 else resp
            })
            graph['edges'].append({
                'from': role_template.role_name,
                'to': node_id,
                'type': 'has_responsibility'
            })

        # Input artifact nodes
        for artifact_type in role_template.input_artifacts:
            node_id = f"input_{artifact_type.value}"
            if not any(n['id'] == node_id for n in graph['nodes']):
                graph['nodes'].append({
                    'id': node_id,
                    'type': 'artifact',
                    'label': artifact_type.value,
                    'direction': 'input'
                })
            graph['edges'].append({
                'from': node_id,
                'to': role_template.role_name,
                'type': 'input_artifact'
            })

        # Output artifact nodes
        for artifact_type in role_template.output_artifacts:
            node_id = f"output_{artifact_type.value}"
            if not any(n['id'] == node_id for n in graph['nodes']):
                graph['nodes'].append({
                    'id': node_id,
                    'type': 'artifact',
                    'label': artifact_type.value,
                    'direction': 'output'
                })
            graph['edges'].append({
                'from': role_template.role_name,
                'to': node_id,
                'type': 'output_artifact'
            })

        # Escalation path nodes
        for path in role_template.escalation_paths:
            node_id = f"escalate_{path.to_role}"
            if not any(n['id'] == node_id for n in graph['nodes']):
                graph['nodes'].append({
                    'id': node_id,
                    'type': 'escalation',
                    'label': path.to_role
                })
            graph['edges'].append({
                'from': role_template.role_name,
                'to': node_id,
                'type': 'escalation_path',
                'conditions': path.trigger_conditions
            })

        # Handoff edges (if provided)
        if handoffs:
            for handoff in handoffs:
                if handoff.from_role == role_template.role_name:
                    node_id = f"handoff_to_{handoff.to_role}"
                    if not any(n['id'] == node_id for n in graph['nodes']):
                        graph['nodes'].append({
                            'id': node_id,
                            'type': 'handoff',
                            'label': handoff.to_role
                        })
                    graph['edges'].append({
                        'from': role_template.role_name,
                        'to': node_id,
                        'type': 'handoff',
                        'artifact': handoff.artifact.artifact_type.value
                    })

        return graph

    @staticmethod
    def generate_mermaid(role_template: RoleTemplate) -> str:
        """
        Generate Mermaid diagram syntax for role work graph

        Returns:
            Mermaid diagram as string
        """
        lines = ["graph TD"]

        # Central role
        role_id = role_template.role_name.replace(' ', '_')
        lines.append(f"    {role_id}[{role_template.role_name}]")
        lines.append(f"    style {role_id} fill:#4CAF50,stroke:#333,stroke-width:2px")

        # Responsibilities
        for i, resp in enumerate(role_template.responsibilities[:5]):  # Limit to 5 for readability
            resp_id = f"resp_{i}"
            resp_label = resp[:30] + '...' if len(resp) > 30 else resp
            lines.append(f"    {resp_id}[{resp_label}]")
            lines.append(f"    {role_id} --> {resp_id}")

        # Escalation paths
        for path in role_template.escalation_paths:
            target_id = path.to_role.replace(' ', '_')
            lines.append(f"    {target_id}[{path.to_role}]")
            lines.append(f"    {role_id} -.escalate.-> {target_id}")
            lines.append(f"    style {target_id} fill:#FF9800,stroke:#333,stroke-width:2px")

        return '\n'.join(lines)


class AutomationCoverageAnalyzer:
    """
    Analyzes automation coverage for roles

    Shows:
    - What can be automated
    - What must remain human
    - Coverage percentage
    - Risk breakdown
    """

    @staticmethod
    def analyze_coverage(role_template: RoleTemplate, proposal: TemplateProposalArtifact) -> Dict:
        """
        Analyze automation coverage

        Returns:
            Dict with coverage analysis
        """
        total_responsibilities = len(role_template.responsibilities)
        automated_count = len(proposal.proposed_automation_steps)
        human_retained_count = len(proposal.human_retained_responsibilities)

        coverage = {
            'total_responsibilities': total_responsibilities,
            'automated_count': automated_count,
            'human_retained_count': human_retained_count,
            'coverage_percentage': (automated_count / total_responsibilities * 100) if total_responsibilities > 0 else 0,
            'automation_steps': proposal.proposed_automation_steps,
            'human_retained': proposal.human_retained_responsibilities,
            'human_signoff_points': proposal.human_signoff_points,
            'risk_breakdown': proposal.risk_analysis
        }

        return coverage

    @staticmethod
    def generate_coverage_report(role_template: RoleTemplate, proposal: TemplateProposalArtifact) -> str:
        """
        Generate human-readable coverage report

        Returns:
            Formatted text report
        """
        coverage = AutomationCoverageAnalyzer.analyze_coverage(role_template, proposal)

        lines = [
            f"# Automation Coverage Report: {role_template.role_name}",
            "",
            "## Summary",
            f"- Total Responsibilities: {coverage['total_responsibilities']}",
            f"- Automated: {coverage['automated_count']} ({coverage['coverage_percentage']:.1f}%)",
            f"- Human Retained: {coverage['human_retained_count']}",
            "",
            "## Proposed Automation Steps",
        ]

        for i, step in enumerate(coverage['automation_steps'], 1):
            lines.append(f"{i}. {step}")

        lines.extend([
            "",
            "## Human-Retained Responsibilities",
        ])

        for i, resp in enumerate(coverage['human_retained'], 1):
            lines.append(f"{i}. {resp}")

        lines.extend([
            "",
            "## Human Signoff Points",
        ])

        for i, point in enumerate(coverage['human_signoff_points'], 1):
            lines.append(f"{i}. {point}")

        lines.extend([
            "",
            "## Risk Analysis",
            f"- Compliance Risk: {coverage['risk_breakdown']['compliance_risk']}",
            f"- Authority Risk: {coverage['risk_breakdown']['authority_risk']}",
            f"- Quality Risk: {coverage['risk_breakdown']['quality_risk']}",
            f"- Escalation Risk: {coverage['risk_breakdown']['escalation_risk']}",
        ])

        if coverage['risk_breakdown']['details']:
            lines.append("")
            lines.append("### Risk Details")
            for detail in coverage['risk_breakdown']['details']:
                lines.append(f"- {detail}")

        return '\n'.join(lines)


class GatingChecklistGenerator:
    """
    Generates gating checklist for automation substitution

    Shows:
    - All required gates
    - Gate status
    - Blocking reasons
    - Next steps
    """

    @staticmethod
    def generate_checklist(gates: List[SubstitutionGate]) -> Dict:
        """
        Generate gating checklist

        Returns:
            Dict with checklist data
        """
        checklist = {
            'gates': [],
            'summary': {
                'total': len(gates),
                'satisfied': 0,
                'pending': 0,
                'not_met': 0,
                'failed': 0
            },
            'can_proceed': True,
            'blocking_gates': []
        }

        for gate in gates:
            gate_info = {
                'gate_id': gate.gate_id,
                'gate_type': gate.gate_type,
                'description': gate.description,
                'status': gate.status.value,
                'details': {}
            }

            # Add type-specific details
            if gate.gate_type == 'performance_evidence':
                gate_info['details'] = {
                    'evidence_window_days': gate.evidence_window_days,
                    'required_success_rate': gate.required_success_rate,
                    'actual_success_rate': gate.actual_success_rate
                }
            elif gate.gate_type == 'deterministic_verification':
                gate_info['details'] = {
                    'verification_method': gate.verification_method,
                    'verification_passed': gate.verification_passed
                }
            elif gate.gate_type == 'compliance_check':
                gate_info['details'] = {
                    'regulation': gate.regulation,
                    'compliance_verified': gate.compliance_verified
                }
            elif gate.gate_type == 'human_signoff':
                gate_info['details'] = {
                    'signoff_required_from': gate.signoff_required_from,
                    'signoff_granted': gate.signoff_granted,
                    'signoff_timestamp': gate.signoff_timestamp.isoformat() if gate.signoff_timestamp else None
                }

            checklist['gates'].append(gate_info)

            # Update summary
            if gate.status == GateStatus.SATISFIED:
                checklist['summary']['satisfied'] += 1
            elif gate.status == GateStatus.PENDING:
                checklist['summary']['pending'] += 1
                checklist['can_proceed'] = False
                checklist['blocking_gates'].append(gate.gate_id)
            elif gate.status == GateStatus.NOT_MET:
                checklist['summary']['not_met'] += 1
                checklist['can_proceed'] = False
                checklist['blocking_gates'].append(gate.gate_id)
            elif gate.status == GateStatus.FAILED:
                checklist['summary']['failed'] += 1
                checklist['can_proceed'] = False
                checklist['blocking_gates'].append(gate.gate_id)

        return checklist

    @staticmethod
    def generate_checklist_report(gates: List[SubstitutionGate]) -> str:
        """
        Generate human-readable checklist report

        Returns:
            Formatted text report
        """
        checklist = GatingChecklistGenerator.generate_checklist(gates)

        lines = [
            "# Substitution Gating Checklist",
            "",
            "## Summary",
            f"- Total Gates: {checklist['summary']['total']}",
            f"- ✅ Satisfied: {checklist['summary']['satisfied']}",
            f"- ⏳ Pending: {checklist['summary']['pending']}",
            f"- ❌ Not Met: {checklist['summary']['not_met']}",
            f"- 🚫 Failed: {checklist['summary']['failed']}",
            "",
            f"**Can Proceed:** {'✅ YES' if checklist['can_proceed'] else '❌ NO'}",
            "",
            "## Gate Details",
            ""
        ]

        for gate_info in checklist['gates']:
            status_emoji = {
                'satisfied': '✅',
                'pending': '⏳',
                'not_met': '❌',
                'failed': '🚫'
            }.get(gate_info['status'], '❓')

            lines.append(f"### {status_emoji} {gate_info['description']}")
            lines.append(f"- **Type:** {gate_info['gate_type']}")
            lines.append(f"- **Status:** {gate_info['status']}")

            if gate_info['details']:
                lines.append("- **Details:**")
                for key, value in gate_info['details'].items():
                    if value is not None:
                        lines.append(f"  - {key}: {value}")

            lines.append("")

        if checklist['blocking_gates']:
            lines.append("## Blocking Gates")
            lines.append("")
            lines.append("The following gates are blocking substitution:")
            for gate_id in checklist['blocking_gates']:
                lines.append(f"- {gate_id}")
            lines.append("")
            lines.append("**Next Steps:** Address blocking gates before proceeding with automation substitution.")

        return '\n'.join(lines)


class HumanVsAutomatedVisualizer:
    """
    Visualizes human vs automated work breakdown
    """

    @staticmethod
    def generate_breakdown(role_template: RoleTemplate, proposal: TemplateProposalArtifact) -> Dict:
        """
        Generate human vs automated breakdown

        Returns:
            Dict with breakdown data
        """
        breakdown = {
            'role_name': role_template.role_name,
            'automated': {
                'count': len(proposal.proposed_automation_steps),
                'items': proposal.proposed_automation_steps,
                'percentage': 0
            },
            'human': {
                'count': len(proposal.human_retained_responsibilities),
                'items': proposal.human_retained_responsibilities,
                'percentage': 0
            },
            'signoff_points': {
                'count': len(proposal.human_signoff_points),
                'items': proposal.human_signoff_points
            }
        }

        total = breakdown['automated']['count'] + breakdown['human']['count']
        if total > 0:
            breakdown['automated']['percentage'] = (breakdown['automated']['count'] / total) * 100
            breakdown['human']['percentage'] = (breakdown['human']['count'] / total) * 100

        return breakdown

    @staticmethod
    def generate_ascii_chart(breakdown: Dict) -> str:
        """
        Generate ASCII bar chart

        Returns:
            ASCII chart as string
        """
        lines = [
            f"Human vs Automated Work: {breakdown['role_name']}",
            "",
            "Automated: " + "█" * int(breakdown['automated']['percentage'] / 2) + f" {breakdown['automated']['percentage']:.1f}%",
            "Human:     " + "█" * int(breakdown['human']['percentage'] / 2) + f" {breakdown['human']['percentage']:.1f}%",
            "",
            f"Automated Tasks: {breakdown['automated']['count']}",
            f"Human Tasks: {breakdown['human']['count']}",
            f"Human Signoff Points: {breakdown['signoff_points']['count']}"
        ]

        return '\n'.join(lines)
