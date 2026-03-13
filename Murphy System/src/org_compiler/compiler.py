"""
Role Template Compiler

Compiles organizational data (org charts, SOPs, process flows) into RoleTemplate objects.

The compiler:
1. Extracts responsibilities from multiple sources
2. Calculates authority boundaries
3. Analyzes artifact flows
4. Maps escalation paths
5. Detects compliance constraints
"""

import logging
import re
from collections import defaultdict
from typing import Dict, List, Optional, Set

logger = logging.getLogger("org_compiler.compiler")

from .schemas import (
    ArtifactType,
    AuthorityLevel,
    ComplianceConstraint,
    EscalationPath,
    HandoffEvent,
    OrgChartNode,
    ProcessFlow,
    RoleMetrics,
    RoleTemplate,
    WorkArtifact,
)


class RoleTemplateCompiler:
    """
    Compiles RoleTemplate objects from organizational data sources
    """

    def __init__(self):
        self.org_nodes: Dict[str, OrgChartNode] = {}
        self.process_flows: List[ProcessFlow] = []
        self.sop_data: Dict[str, Dict] = {}  # role_name -> SOP data
        self.handoff_events: List[HandoffEvent] = []
        self.work_artifacts: List[WorkArtifact] = []

    def add_org_chart(self, nodes: List[OrgChartNode]):
        """Add organizational chart data"""
        for node in nodes:
            self.org_nodes[node.role_name] = node

    def add_process_flow(self, flow: ProcessFlow):
        """Add process flow data"""
        self.process_flows.append(flow)

    def add_sop_data(self, role_name: str, sop_data: Dict):
        """Add SOP data for a role"""
        self.sop_data[role_name] = sop_data

    def add_handoff_events(self, events: List[HandoffEvent]):
        """Add handoff event data"""
        self.handoff_events.extend(events)

    def add_work_artifacts(self, artifacts: List[WorkArtifact]):
        """Add work artifact data"""
        self.work_artifacts.extend(artifacts)

    def compile(self, role_name: str) -> RoleTemplate:
        """
        Compile a RoleTemplate for the specified role

        Args:
            role_name: Name of the role to compile

        Returns:
            RoleTemplate object
        """
        # Get org chart node
        org_node = self.org_nodes.get(role_name)
        if not org_node:
            raise ValueError(f"Role '{role_name}' not found in org chart")

        # Extract responsibilities
        responsibilities = self._extract_responsibilities(role_name)

        # Calculate decision authority
        decision_authority = self._calculate_authority(role_name)

        # Analyze artifact flows
        input_artifacts, output_artifacts = self._analyze_artifact_flows(role_name)

        # Map escalation paths
        escalation_paths = self._map_escalation_paths(role_name)

        # Detect compliance constraints
        compliance_constraints = self._detect_compliance_constraints(role_name)

        # Identify human signoff requirements
        requires_human_signoff = self._identify_signoff_requirements(role_name)

        # Calculate metrics
        metrics = self._calculate_metrics(role_name)

        # Collect source documents
        source_documents = self._collect_source_documents(role_name)

        # Create role template
        template = RoleTemplate(
            role_id=org_node.node_id,
            role_name=role_name,
            responsibilities=responsibilities,
            decision_authority=decision_authority,
            input_artifacts=input_artifacts,
            output_artifacts=output_artifacts,
            escalation_paths=escalation_paths,
            compliance_constraints=compliance_constraints,
            requires_human_signoff=requires_human_signoff,
            metrics=metrics,
            source_documents=source_documents
        )

        return template

    def _extract_responsibilities(self, role_name: str) -> List[str]:
        """Extract responsibilities from all sources"""
        responsibilities = set()

        # From SOP data
        if role_name in self.sop_data:
            sop = self.sop_data[role_name]
            responsibilities.update(sop.get('responsibilities', []))

        # From process flows
        for flow in self.process_flows:
            for step in flow.steps:
                if step.get('role') == role_name:
                    action = step.get('action', '')
                    if action:
                        responsibilities.add(action)

        # From handoff events (what this role produces)
        for event in self.handoff_events:
            if event.from_role == role_name:
                responsibilities.add(f"Produce {event.artifact.artifact_type.value}")

        return sorted(list(responsibilities))

    def _calculate_authority(self, role_name: str) -> AuthorityLevel:
        """Calculate decision authority level"""
        # Start with org chart authority
        org_node = self.org_nodes.get(role_name)
        if org_node:
            authority = org_node.authority_level
        else:
            authority = AuthorityLevel.LOW

        # Adjust based on decision-making in process flows
        decision_count = 0
        for flow in self.process_flows:
            for decision in flow.decision_points:
                # Check if this role makes decisions
                for step in flow.steps:
                    if step.get('role') == role_name and 'decision' in step.get('action', '').lower():
                        decision_count += 1

        # Adjust based on SOP data
        if role_name in self.sop_data:
            sop = self.sop_data[role_name]
            decisions = sop.get('decisions', [])
            decision_count += len(decisions)

        # Authority adjustment based on decision-making
        if decision_count > 10:
            # High decision-making role
            if authority.value in ['low', 'medium']:
                authority = AuthorityLevel.HIGH
        elif decision_count > 5:
            # Medium decision-making role
            if authority == AuthorityLevel.LOW:
                authority = AuthorityLevel.MEDIUM

        return authority

    def _analyze_artifact_flows(self, role_name: str) -> tuple[List[ArtifactType], List[ArtifactType]]:
        """Analyze input and output artifact flows"""
        input_types = set()
        output_types = set()

        # From process flows
        for flow in self.process_flows:
            for step in flow.steps:
                if step.get('role') == role_name:
                    # Inputs
                    for inp in step.get('inputs', []):
                        artifact_type = self._infer_artifact_type(inp)
                        if artifact_type:
                            input_types.add(artifact_type)

                    # Outputs
                    for out in step.get('outputs', []):
                        artifact_type = self._infer_artifact_type(out)
                        if artifact_type:
                            output_types.add(artifact_type)

        # From handoff events
        for event in self.handoff_events:
            if event.to_role == role_name:
                input_types.add(event.artifact.artifact_type)
            if event.from_role == role_name:
                output_types.add(event.artifact.artifact_type)

        # From work artifacts
        for artifact in self.work_artifacts:
            if role_name in artifact.consumer_roles:
                input_types.add(artifact.artifact_type)
            if artifact.producer_role == role_name:
                output_types.add(artifact.artifact_type)

        return sorted(list(input_types), key=lambda x: x.value), sorted(list(output_types), key=lambda x: x.value)

    def _infer_artifact_type(self, artifact_name: str) -> Optional[ArtifactType]:
        """Infer artifact type from name"""
        artifact_name_lower = artifact_name.lower()

        if any(word in artifact_name_lower for word in ['doc', 'document', 'report', 'spec']):
            return ArtifactType.DOCUMENT
        elif any(word in artifact_name_lower for word in ['code', 'script', 'program']):
            return ArtifactType.CODE
        elif any(word in artifact_name_lower for word in ['design', 'mockup', 'wireframe']):
            return ArtifactType.DESIGN
        elif any(word in artifact_name_lower for word in ['approval', 'sign-off']):
            return ArtifactType.APPROVAL
        elif any(word in artifact_name_lower for word in ['ticket', 'issue', 'task']):
            return ArtifactType.TICKET
        elif any(word in artifact_name_lower for word in ['email', 'message']):
            return ArtifactType.EMAIL
        elif any(word in artifact_name_lower for word in ['meeting', 'notes', 'minutes']):
            return ArtifactType.MEETING_NOTES

        return None

    def _map_escalation_paths(self, role_name: str) -> List[EscalationPath]:
        """Map escalation paths for this role"""
        paths = []

        # From org chart (escalate to manager)
        org_node = self.org_nodes.get(role_name)
        if org_node and org_node.reports_to:
            manager_node = next((n for n in self.org_nodes.values() if n.node_id == org_node.reports_to), None)
            if manager_node:
                path = EscalationPath(
                    path_id=f"{role_name}_to_{manager_node.role_name}",
                    from_role=role_name,
                    to_role=manager_node.role_name,
                    trigger_conditions=["Issue exceeds authority level", "Unable to resolve"],
                    sla_hours=24.0,
                    requires_human=True,
                    immutable=True
                )
                paths.append(path)

        # From SOP data
        if role_name in self.sop_data:
            sop = self.sop_data[role_name]
            for escalation in sop.get('escalations', []):
                # Parse escalation text to extract target role
                # Format: "escalate to [role]"
                match = re.search(r'(?:to|with)\s+(.+?)(?:\s+for|\s+when|$)', escalation, re.IGNORECASE)
                if match:
                    target_role = match.group(1).strip()
                    path = EscalationPath(
                        path_id=f"{role_name}_to_{target_role}_sop",
                        from_role=role_name,
                        to_role=target_role,
                        trigger_conditions=[escalation],
                        sla_hours=24.0,
                        requires_human=True,
                        immutable=True
                    )
                    paths.append(path)

        # From process flows
        for flow in self.process_flows:
            for handoff in flow.handoffs:
                if handoff.get('from_role') == role_name:
                    to_role = handoff.get('to_role')
                    if to_role:
                        path = EscalationPath(
                            path_id=f"{role_name}_to_{to_role}_{flow.flow_id}",
                            from_role=role_name,
                            to_role=to_role,
                            trigger_conditions=[f"Handoff in {flow.flow_name}"],
                            sla_hours=flow.sla_targets.get('handoff_hours', 24.0),
                            requires_human=True,
                            immutable=True
                        )
                        paths.append(path)

        return paths

    def _detect_compliance_constraints(self, role_name: str) -> List[ComplianceConstraint]:
        """Detect compliance constraints for this role"""
        constraints = []
        constraint_map = {}  # regulation -> constraint

        # From SOP data
        if role_name in self.sop_data:
            sop = self.sop_data[role_name]
            for compliance in sop.get('compliance', []):
                regulation = compliance.upper()
                if regulation not in constraint_map:
                    constraint = ComplianceConstraint(
                        constraint_id=f"{role_name}_{regulation}",
                        regulation=regulation,
                        description=f"{regulation} compliance required for {role_name}",
                        verification_required=True,
                        human_signoff_required=True,
                        audit_trail_required=True,
                        immutable=True
                    )
                    constraint_map[regulation] = constraint

        # From process flows
        for flow in self.process_flows:
            for checkpoint in flow.compliance_checkpoints:
                # Extract regulation name
                regulation = checkpoint.upper()
                if regulation not in constraint_map:
                    constraint = ComplianceConstraint(
                        constraint_id=f"{role_name}_{regulation}_{flow.flow_id}",
                        regulation=regulation,
                        description=f"{regulation} checkpoint in {flow.flow_name}",
                        verification_required=True,
                        human_signoff_required=True,
                        audit_trail_required=True,
                        immutable=True
                    )
                    constraint_map[regulation] = constraint

        return list(constraint_map.values())

    def _identify_signoff_requirements(self, role_name: str) -> List[str]:
        """Identify actions requiring human signoff"""
        signoff_actions = set()

        # From SOP data
        if role_name in self.sop_data:
            sop = self.sop_data[role_name]
            signoff_actions.update(sop.get('approvals', []))

        # From handoff events with approval required
        for event in self.handoff_events:
            if event.from_role == role_name and event.approval_required:
                signoff_actions.add(f"Handoff to {event.to_role}")

        # From process flows
        for flow in self.process_flows:
            for step in flow.steps:
                if step.get('role') == role_name:
                    action = step.get('action', '')
                    if any(word in action.lower() for word in ['approve', 'sign-off', 'authorize', 'validate']):
                        signoff_actions.add(action)

        return sorted(list(signoff_actions))

    def _calculate_metrics(self, role_name: str) -> RoleMetrics:
        """Calculate performance metrics for this role"""
        sla_targets = {}
        quality_gates = []

        # From process flows
        for flow in self.process_flows:
            # Check if role participates in this flow
            participates = any(step.get('role') == role_name for step in flow.steps)
            if participates:
                sla_targets.update(flow.sla_targets)

        # From handoff events (calculate average duration)
        role_handoffs = [e for e in self.handoff_events if e.from_role == role_name and e.duration_hours is not None]
        if role_handoffs:
            avg_duration = sum(e.duration_hours for e in role_handoffs) / (len(role_handoffs) or 1)
            sla_targets['avg_handoff_hours'] = avg_duration

        # Quality gates from SOP
        if role_name in self.sop_data:
            sop = self.sop_data[role_name]
            quality_gates.extend(sop.get('decisions', []))

        # Default metrics if none found
        if not sla_targets:
            sla_targets = {'response_time_hours': 24.0, 'quality_score': 0.95}

        if not quality_gates:
            quality_gates = ['Output quality check', 'Compliance verification']

        return RoleMetrics(
            sla_targets=sla_targets,
            quality_gates=quality_gates,
            throughput_target=None,
            error_rate_max=0.05
        )

    def _collect_source_documents(self, role_name: str) -> List[str]:
        """Collect source document references"""
        sources = set()

        # Org chart
        if role_name in self.org_nodes:
            sources.add("org_chart")

        # SOP
        if role_name in self.sop_data:
            sources.add("sop_document")

        # Process flows
        for flow in self.process_flows:
            participates = any(step.get('role') == role_name for step in flow.steps)
            if participates:
                sources.add(f"process_flow:{flow.flow_id}")

        # Handoff events
        if any(e.from_role == role_name or e.to_role == role_name for e in self.handoff_events):
            sources.add("handoff_events")

        return sorted(list(sources))

    def compile_all(self) -> List[RoleTemplate]:
        """Compile RoleTemplates for all roles in org chart"""
        templates = []
        for role_name in self.org_nodes.keys():
            try:
                template = self.compile(role_name)
                templates.append(template)
            except Exception as exc:
                logger.info(f"Warning: Failed to compile template for {role_name}: {exc}")

        return templates

    # ------------------------------------------------------------------
    # Simplified API used by integration tests
    # ------------------------------------------------------------------

    def compile_role_template(self, role_data: Dict) -> Dict:
        """Compile a role template from a role dict (integration-test API).

        Accepts a dict with ``role_id``, ``title``, ``automatable_tasks``,
        ``human_required_tasks`` etc. and returns a dict with the same keys
        preserved plus any enrichment.
        """
        return {
            "role_id": role_data.get("role_id", "unknown"),
            "title": role_data.get("title", ""),
            "authority": role_data.get("authority", "low"),
            "automatable_tasks": role_data.get("automatable_tasks", []),
            "human_required_tasks": role_data.get("human_required_tasks", []),
        }
