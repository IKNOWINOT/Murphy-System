"""
Comprehensive tests for Org Compiler & Shadow Learning System

Tests:
1. Schema validation and safety constraints
2. Parser functionality
3. Compiler functionality
4. Shadow learning
5. Substitution gates
6. Visualization
7. Murphy integration
"""

import pytest
from datetime import datetime, timezone, timedelta
import json

from src.org_compiler.schemas import (
    RoleTemplate,
    TemplateProposalArtifact,
    SubstitutionGate,
    EscalationPath,
    ComplianceConstraint,
    RoleMetrics,
    AuthorityLevel,
    ArtifactType,
    ProposalStatus,
    GateStatus,
    OrgChartNode,
    ProcessFlow,
    WorkArtifact,
    HandoffEvent,
)
from src.org_compiler.parsers import (
    OrgChartParser,
    ProcessFlowParser,
    SOPDocumentParser,
    TicketEventIngestor,
)
from src.org_compiler.compiler import RoleTemplateCompiler
from src.org_compiler.shadow_learning import (
    TelemetryCollector,
    PatternRecognitionEngine,
    ShadowLearningAgent,
)
from src.org_compiler.substitution import (
    PerformanceEvidenceValidator,
    DeterministicVerificationChecker,
    ComplianceGateValidator,
    HumanSignoffEnforcer,
    SubstitutionGateEvaluator,
)
from src.org_compiler.visualization import (
    RoleWorkGraphGenerator,
    AutomationCoverageAnalyzer,
    GatingChecklistGenerator,
)
from src.org_compiler.murphy_integration import MurphySystemBridge


# ============================================================================
# SCHEMA TESTS
# ============================================================================

class TestSchemas:
    """Test schema validation and safety constraints"""

    def test_escalation_path_immutability(self):
        """Test that escalation paths are immutable"""
        with pytest.raises(ValueError, match="immutable must be True"):
            EscalationPath(
                path_id="test",
                from_role="A",
                to_role="B",
                trigger_conditions=["test"],
                sla_hours=24.0,
                immutable=False
            )

    def test_escalation_path_requires_human(self):
        """Test that escalation paths require human"""
        with pytest.raises(ValueError, match="requires_human must be True"):
            EscalationPath(
                path_id="test",
                from_role="A",
                to_role="B",
                trigger_conditions=["test"],
                sla_hours=24.0,
                requires_human=False
            )

    def test_compliance_constraint_immutability(self):
        """Test that compliance constraints are immutable"""
        with pytest.raises(ValueError, match="immutable must be True"):
            ComplianceConstraint(
                constraint_id="test",
                regulation="SOX",
                description="test",
                verification_required=True,
                human_signoff_required=True,
                audit_trail_required=True,
                immutable=False
            )

    def test_proposal_sandbox_only(self):
        """Test that proposals are sandbox-only"""
        with pytest.raises(ValueError, match="status MUST be 'sandbox'"):
            TemplateProposalArtifact(
                proposal_id="test",
                shadowed_role="Designer",
                proposed_automation_steps=["step1"],
                evidence_references=["evidence1"],
                risk_analysis={"risk": "low"},
                required_gates=["gate1"],
                human_retained_responsibilities=["resp1"],
                human_signoff_points=["point1"],
                observation_window_days=30,
                success_rate=0.95,
                error_patterns=[],
                status=ProposalStatus.APPROVED  # Should fail
            )

    def test_proposal_no_execution_rights(self):
        """Test that proposals cannot have execution rights"""
        with pytest.raises(ValueError, match="execution_rights MUST be False"):
            TemplateProposalArtifact(
                proposal_id="test",
                shadowed_role="Designer",
                proposed_automation_steps=["step1"],
                evidence_references=["evidence1"],
                risk_analysis={"risk": "low"},
                required_gates=["gate1"],
                human_retained_responsibilities=["resp1"],
                human_signoff_points=["point1"],
                observation_window_days=30,
                success_rate=0.95,
                error_patterns=[],
                execution_rights=True  # Should fail
            )

    def test_proposal_cannot_modify_escalation(self):
        """Test that proposals cannot modify escalation paths"""
        with pytest.raises(ValueError, match="can_modify_escalation MUST be False"):
            TemplateProposalArtifact(
                proposal_id="test",
                shadowed_role="Designer",
                proposed_automation_steps=["step1"],
                evidence_references=["evidence1"],
                risk_analysis={"risk": "low"},
                required_gates=["gate1"],
                human_retained_responsibilities=["resp1"],
                human_signoff_points=["point1"],
                observation_window_days=30,
                success_rate=0.95,
                error_patterns=[],
                can_modify_escalation=True  # Should fail
            )

    def test_proposal_cannot_bypass_compliance(self):
        """Test that proposals cannot bypass compliance"""
        with pytest.raises(ValueError, match="can_bypass_compliance MUST be False"):
            TemplateProposalArtifact(
                proposal_id="test",
                shadowed_role="Designer",
                proposed_automation_steps=["step1"],
                evidence_references=["evidence1"],
                risk_analysis={"risk": "low"},
                required_gates=["gate1"],
                human_retained_responsibilities=["resp1"],
                human_signoff_points=["point1"],
                observation_window_days=30,
                success_rate=0.95,
                error_patterns=[],
                can_bypass_compliance=True  # Should fail
            )

    def test_role_template_integrity(self):
        """Test role template integrity hash"""
        template = RoleTemplate(
            role_id="designer_1",
            role_name="Designer 1",
            responsibilities=["Create designs"],
            decision_authority=AuthorityLevel.MEDIUM,
            input_artifacts=[ArtifactType.DOCUMENT],
            output_artifacts=[ArtifactType.DESIGN],
            escalation_paths=[],
            compliance_constraints=[],
            requires_human_signoff=["Final approval"],
            metrics=RoleMetrics(
                sla_targets={"response_time_hours": 24.0},
                quality_gates=["Design review"]
            )
        )

        assert template.integrity_hash is not None
        assert template.verify_integrity()


# ============================================================================
# PARSER TESTS
# ============================================================================

class TestParsers:
    """Test input parsers"""

    def test_sop_parser_responsibilities(self):
        """Test SOP parser extracts responsibilities"""
        sop_text = """
        The Designer role is responsible for creating visual designs.
        Must ensure designs meet brand guidelines.
        Shall collaborate with product team.
        """

        result = SOPDocumentParser.parse(sop_text)
        assert len(result['responsibilities']) >= 2
        assert any('creating visual designs' in r.lower() for r in result['responsibilities'])

    def test_sop_parser_compliance(self):
        """Test SOP parser extracts compliance requirements"""
        sop_text = """
        This role must comply with SOX regulations.
        HIPAA compliance is required for all patient data.
        Subject to GDPR requirements.
        """

        result = SOPDocumentParser.parse(sop_text)
        assert len(result['compliance']) >= 2
        assert any('SOX' in c for c in result['compliance'])

    def test_process_flow_parser_tagged_text(self):
        """Test process flow parser with tagged text"""
        flow_text = """
        FLOW: Design Review Process
        STEP: step1 | Designer | Create initial design | requirements | design_v1
        STEP: step2 | Reviewer | Review design | design_v1 | feedback
        HANDOFF: Designer -> Reviewer | design_v1
        SLA: review_time_hours = 48
        COMPLIANCE: Design Standards
        """

        flow = ProcessFlowParser.parse_tagged_text(flow_text)
        assert flow.flow_name == "Design Review Process"
        assert len(flow.steps) == 2
        assert len(flow.handoffs) == 1
        assert flow.sla_targets['review_time_hours'] == 48.0


# ============================================================================
# COMPILER TESTS
# ============================================================================

class TestCompiler:
    """Test role template compiler"""

    def test_compiler_basic(self):
        """Test basic compilation"""
        compiler = RoleTemplateCompiler()

        # Add org chart
        node = OrgChartNode(
            node_id="designer_1",
            role_name="Designer 1",
            reports_to="manager_1",
            team="Design",
            department="Product",
            authority_level=AuthorityLevel.MEDIUM
        )
        compiler.add_org_chart([node])

        # Add SOP data
        compiler.add_sop_data("Designer 1", {
            'responsibilities': ["Create designs", "Review mockups"],
            'decisions': ["Design approach"],
            'approvals': ["Final design"],
            'compliance': ["Design Standards"],
            'escalations': ["Escalate to Design Manager"]
        })

        # Compile
        template = compiler.compile("Designer 1")

        assert template.role_name == "Designer 1"
        assert len(template.responsibilities) >= 2
        assert template.decision_authority == AuthorityLevel.MEDIUM

    def test_compiler_escalation_paths(self):
        """Test escalation path mapping"""
        compiler = RoleTemplateCompiler()

        # Add org chart with manager
        designer = OrgChartNode(
            node_id="designer_1",
            role_name="Designer 1",
            reports_to="manager_1",
            team="Design",
            department="Product",
            authority_level=AuthorityLevel.MEDIUM
        )
        manager = OrgChartNode(
            node_id="manager_1",
            role_name="Design Manager",
            reports_to=None,
            team="Design",
            department="Product",
            authority_level=AuthorityLevel.HIGH
        )
        compiler.add_org_chart([designer, manager])

        # Add SOP data (required for compilation)
        compiler.add_sop_data("Designer 1", {
            'responsibilities': ["Create designs"],
            'decisions': [],
            'approvals': [],
            'compliance': [],
            'escalations': []
        })

        # Compile
        template = compiler.compile("Designer 1")

        # Should have escalation to manager
        assert len(template.escalation_paths) >= 1
        assert any(p.to_role == "Design Manager" for p in template.escalation_paths)

        # All escalation paths must be immutable
        for path in template.escalation_paths:
            assert path.immutable
            assert path.requires_human


# ============================================================================
# SHADOW LEARNING TESTS
# ============================================================================

class TestShadowLearning:
    """Test shadow learning system"""

    def test_telemetry_collector(self):
        """Test telemetry collection"""
        collector = TelemetryCollector()

        # Record events
        collector.record_task_assignment("Designer 1", "Create mockup", datetime.now(timezone.utc))
        collector.record_approval("Designer 1", "Design approval", True, datetime.now(timezone.utc))

        # Get telemetry
        telemetry = collector.get_telemetry_for_role("Designer 1", days=30)

        assert len(telemetry['task_assignments']) == 1
        assert len(telemetry['approvals']) == 1

    def test_pattern_recognition_repetitive(self):
        """Test repetitive task identification"""
        collector = TelemetryCollector()

        # Record 15 repetitive tasks
        for i in range(15):
            collector.record_task_assignment(
                "Designer 1",
                "Create mockup",
                datetime.now(timezone.utc) - timedelta(days=i)
            )

        telemetry = collector.get_telemetry_for_role("Designer 1", days=30)
        patterns = PatternRecognitionEngine.identify_repetitive_tasks(telemetry)

        assert len(patterns) >= 1
        assert patterns[0]['task'] == "Create mockup"
        assert patterns[0]['frequency'] == 15

    def test_shadow_agent_proposal_generation(self):
        """Test shadow agent generates proposals"""
        collector = TelemetryCollector()

        # Record sufficient telemetry
        for i in range(20):
            collector.record_task_assignment(
                "Designer 1",
                "Create mockup",
                datetime.now(timezone.utc) - timedelta(days=i)
            )

        # Create role template
        template = RoleTemplate(
            role_id="designer_1",
            role_name="Designer 1",
            responsibilities=["Create mockups", "Review designs"],
            decision_authority=AuthorityLevel.MEDIUM,
            input_artifacts=[ArtifactType.DOCUMENT],
            output_artifacts=[ArtifactType.DESIGN],
            escalation_paths=[],
            compliance_constraints=[],
            requires_human_signoff=["Final approval"],
            metrics=RoleMetrics(
                sla_targets={"response_time_hours": 24.0},
                quality_gates=["Design review"]
            )
        )

        # Generate proposal
        agent = ShadowLearningAgent(collector)
        proposal = agent.observe_role(template, observation_window_days=30)

        assert proposal is not None
        assert proposal.shadowed_role == "Designer 1"
        assert proposal.status == ProposalStatus.SANDBOX
        assert not proposal.execution_rights
        assert not proposal.can_modify_escalation
        assert not proposal.can_bypass_compliance


# ============================================================================
# SUBSTITUTION GATE TESTS
# ============================================================================

class TestSubstitutionGates:
    """Test substitution gate evaluation"""

    def test_performance_evidence_validator(self):
        """Test performance evidence validation"""
        validator = PerformanceEvidenceValidator(
            min_window_days=30,
            min_success_rate=0.95,
            min_sample_size=100
        )

        proposal = TemplateProposalArtifact(
            proposal_id="test",
            shadowed_role="Designer 1",
            proposed_automation_steps=["step1"],
            evidence_references=["evidence1"],
            risk_analysis={"risk": "low"},
            required_gates=["gate1"],
            human_retained_responsibilities=["resp1"],
            human_signoff_points=["point1"],
            observation_window_days=30,
            success_rate=0.96,
            error_patterns=[]
        )

        telemetry = {
            'task_assignments': [{'task': f'task_{i}'} for i in range(100)]
        }

        gate = validator.validate(proposal, telemetry)

        assert gate.status == GateStatus.SATISFIED

    def test_performance_evidence_fails_low_success_rate(self):
        """Test performance evidence fails with low success rate"""
        validator = PerformanceEvidenceValidator()

        proposal = TemplateProposalArtifact(
            proposal_id="test",
            shadowed_role="Designer 1",
            proposed_automation_steps=["step1"],
            evidence_references=["evidence1"],
            risk_analysis={"risk": "low"},
            required_gates=["gate1"],
            human_retained_responsibilities=["resp1"],
            human_signoff_points=["point1"],
            observation_window_days=30,
            success_rate=0.80,  # Below threshold
            error_patterns=[]
        )

        telemetry = {
            'task_assignments': [{'task': f'task_{i}'} for i in range(100)]
        }

        gate = validator.validate(proposal, telemetry)

        assert gate.status == GateStatus.NOT_MET

    def test_human_signoff_enforcer(self):
        """Test human signoff enforcement"""
        enforcer = HumanSignoffEnforcer()

        proposal = TemplateProposalArtifact(
            proposal_id="test",
            shadowed_role="Designer 1",
            proposed_automation_steps=["step1"],
            evidence_references=["evidence1"],
            risk_analysis={"risk": "low"},
            required_gates=["gate1"],
            human_retained_responsibilities=["resp1"],
            human_signoff_points=["point1"],
            observation_window_days=30,
            success_rate=0.95,
            error_patterns=[]
        )

        # Request signoff
        gate = enforcer.request_signoff(proposal, "Design Manager")
        assert gate.status == GateStatus.PENDING

        # Grant signoff
        gate = enforcer.grant_signoff(gate, "Design Manager")
        assert gate.status == GateStatus.SATISFIED
        assert gate.signoff_granted

    def test_compliance_gate_validator(self):
        """Test compliance gate validation"""
        validator = ComplianceGateValidator()

        template = RoleTemplate(
            role_id="designer_1",
            role_name="Designer 1",
            responsibilities=["Create designs"],
            decision_authority=AuthorityLevel.MEDIUM,
            input_artifacts=[ArtifactType.DOCUMENT],
            output_artifacts=[ArtifactType.DESIGN],
            escalation_paths=[],
            compliance_constraints=[
                ComplianceConstraint(
                    constraint_id="sox_1",
                    regulation="SOX",
                    description="SOX compliance",
                    verification_required=True,
                    human_signoff_required=True,
                    audit_trail_required=True
                )
            ],
            requires_human_signoff=["Final approval"],
            metrics=RoleMetrics(
                sla_targets={"response_time_hours": 24.0},
                quality_gates=["Design review"]
            )
        )

        proposal = TemplateProposalArtifact(
            proposal_id="test",
            shadowed_role="Designer 1",
            proposed_automation_steps=["step1"],
            evidence_references=["evidence1"],
            risk_analysis={"risk": "low"},
            required_gates=["gate1"],
            human_retained_responsibilities=["Compliance: SOX"],
            human_signoff_points=["point1"],
            observation_window_days=30,
            success_rate=0.95,
            error_patterns=[]
        )

        gates = validator.validate(proposal, template)

        assert len(gates) == 1
        assert gates[0].status == GateStatus.SATISFIED  # Compliance retained by human


# ============================================================================
# VISUALIZATION TESTS
# ============================================================================

class TestVisualization:
    """Test visualization components"""

    def test_role_work_graph_generation(self):
        """Test role work graph generation"""
        template = RoleTemplate(
            role_id="designer_1",
            role_name="Designer 1",
            responsibilities=["Create designs", "Review mockups"],
            decision_authority=AuthorityLevel.MEDIUM,
            input_artifacts=[ArtifactType.DOCUMENT],
            output_artifacts=[ArtifactType.DESIGN],
            escalation_paths=[
                EscalationPath(
                    path_id="esc_1",
                    from_role="Designer 1",
                    to_role="Design Manager",
                    trigger_conditions=["Issue exceeds authority"],
                    sla_hours=24.0
                )
            ],
            compliance_constraints=[],
            requires_human_signoff=["Final approval"],
            metrics=RoleMetrics(
                sla_targets={"response_time_hours": 24.0},
                quality_gates=["Design review"]
            )
        )

        graph = RoleWorkGraphGenerator.generate_graph(template)

        assert len(graph['nodes']) > 0
        assert len(graph['edges']) > 0
        assert graph['metadata']['role_name'] == "Designer 1"

    def test_automation_coverage_analyzer(self):
        """Test automation coverage analysis"""
        template = RoleTemplate(
            role_id="designer_1",
            role_name="Designer 1",
            responsibilities=["Create designs", "Review mockups", "Collaborate"],
            decision_authority=AuthorityLevel.MEDIUM,
            input_artifacts=[ArtifactType.DOCUMENT],
            output_artifacts=[ArtifactType.DESIGN],
            escalation_paths=[],
            compliance_constraints=[],
            requires_human_signoff=["Final approval"],
            metrics=RoleMetrics(
                sla_targets={"response_time_hours": 24.0},
                quality_gates=["Design review"]
            )
        )

        proposal = TemplateProposalArtifact(
            proposal_id="test",
            shadowed_role="Designer 1",
            proposed_automation_steps=["Automate mockup creation"],
            evidence_references=["evidence1"],
            risk_analysis={"compliance_risk": "low", "authority_risk": "low"},
            required_gates=["gate1"],
            human_retained_responsibilities=["Final approval", "Collaboration"],
            human_signoff_points=["Final approval"],
            observation_window_days=30,
            success_rate=0.95,
            error_patterns=[]
        )

        coverage = AutomationCoverageAnalyzer.analyze_coverage(template, proposal)

        assert coverage['total_responsibilities'] == 3
        assert coverage['automated_count'] == 1
        assert coverage['human_retained_count'] == 2

    def test_gating_checklist_generator(self):
        """Test gating checklist generation"""
        gates = [
            SubstitutionGate(
                gate_id="gate1",
                gate_type="performance_evidence",
                description="Performance gate",
                status=GateStatus.SATISFIED
            ),
            SubstitutionGate(
                gate_id="gate2",
                gate_type="human_signoff",
                description="Signoff gate",
                status=GateStatus.PENDING
            )
        ]

        checklist = GatingChecklistGenerator.generate_checklist(gates)

        assert checklist['summary']['total'] == 2
        assert checklist['summary']['satisfied'] == 1
        assert checklist['summary']['pending'] == 1
        assert not checklist['can_proceed']
        assert len(checklist['blocking_gates']) == 1


# ============================================================================
# MURPHY INTEGRATION TESTS
# ============================================================================

class TestMurphyIntegration:
    """Test Murphy System integration"""

    def test_role_template_to_artifact(self):
        """Test role template conversion to artifact"""
        from src.org_compiler.murphy_integration import ArtifactGraphIntegration

        template = RoleTemplate(
            role_id="designer_1",
            role_name="Designer 1",
            responsibilities=["Create designs"],
            decision_authority=AuthorityLevel.MEDIUM,
            input_artifacts=[ArtifactType.DOCUMENT],
            output_artifacts=[ArtifactType.DESIGN],
            escalation_paths=[],
            compliance_constraints=[],
            requires_human_signoff=["Final approval"],
            metrics=RoleMetrics(
                sla_targets={"response_time_hours": 24.0},
                quality_gates=["Design review"]
            )
        )

        artifact = ArtifactGraphIntegration.role_template_to_artifact(template)

        assert artifact['artifact_id'] == "designer_1"
        assert artifact['artifact_type'] == 'role_template'
        assert artifact['status'] == 'verified'

    def test_proposal_to_artifact_sandbox_only(self):
        """Test proposal conversion enforces sandbox status"""
        from src.org_compiler.murphy_integration import ArtifactGraphIntegration

        proposal = TemplateProposalArtifact(
            proposal_id="test",
            shadowed_role="Designer 1",
            proposed_automation_steps=["step1"],
            evidence_references=["evidence1"],
            risk_analysis={"risk": "low"},
            required_gates=["gate1"],
            human_retained_responsibilities=["resp1"],
            human_signoff_points=["point1"],
            observation_window_days=30,
            success_rate=0.95,
            error_patterns=[]
        )

        artifact = ArtifactGraphIntegration.proposal_to_artifact(proposal)

        assert artifact['status'] == 'sandbox'
        assert artifact['execution_rights'] == False

    def test_murphy_bridge_registration(self):
        """Test Murphy bridge role registration"""
        bridge = MurphySystemBridge()

        template = RoleTemplate(
            role_id="designer_1",
            role_name="Designer 1",
            responsibilities=["Create designs"],
            decision_authority=AuthorityLevel.MEDIUM,
            input_artifacts=[ArtifactType.DOCUMENT],
            output_artifacts=[ArtifactType.DESIGN],
            escalation_paths=[],
            compliance_constraints=[],
            requires_human_signoff=["Final approval"],
            metrics=RoleMetrics(
                sla_targets={"response_time_hours": 24.0},
                quality_gates=["Design review"]
            )
        )

        results = bridge.register_role_template(template)

        assert 'artifact_graph' in results
        assert 'telemetry' in results


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
