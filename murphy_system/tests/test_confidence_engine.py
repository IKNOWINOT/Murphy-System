"""
Comprehensive test suite for Confidence Engine
Tests all critical functionality including adversarial scenarios
"""

import pytest
import os

# Add src to path

from confidence_engine.models import (
    ArtifactNode,
    ArtifactGraph,
    ArtifactType,
    ArtifactSource,
    VerificationEvidence,
    VerificationResult,
    SourceTrust,
    TrustModel,
    Phase,
    AuthorityBand
)
from confidence_engine.graph_analyzer import GraphAnalyzer
from confidence_engine.confidence_calculator import ConfidenceCalculator
from confidence_engine.murphy_calculator import MurphyCalculator
from confidence_engine.authority_mapper import AuthorityMapper
from confidence_engine.phase_controller import PhaseController


class TestArtifactGraph:
    """Test artifact graph functionality"""

    def test_add_node(self):
        """Test adding nodes to graph"""
        graph = ArtifactGraph()

        node = ArtifactNode(
            id="test1",
            type=ArtifactType.HYPOTHESIS,
            source=ArtifactSource.LLM,
            content={"text": "Test hypothesis"}
        )

        graph.add_node(node)

        assert len(graph.nodes) == 1
        assert "test1" in graph.nodes
        assert graph.get_node("test1") == node

    def test_dag_validation(self):
        """Test DAG validation"""
        graph = ArtifactGraph()

        # Create valid DAG
        node1 = ArtifactNode(id="n1", type=ArtifactType.HYPOTHESIS,
                            source=ArtifactSource.LLM, content={})
        node2 = ArtifactNode(id="n2", type=ArtifactType.DECISION,
                            source=ArtifactSource.LLM, content={},
                            dependencies=["n1"])

        graph.add_node(node1)
        graph.add_node(node2)

        assert graph.is_dag() == True

    def test_cycle_detection(self):
        """Test cycle detection"""
        graph = ArtifactGraph()

        # Create cycle: n1 -> n2 -> n3 -> n1
        node1 = ArtifactNode(id="n1", type=ArtifactType.HYPOTHESIS,
                            source=ArtifactSource.LLM, content={},
                            dependencies=["n3"])
        node2 = ArtifactNode(id="n2", type=ArtifactType.DECISION,
                            source=ArtifactSource.LLM, content={},
                            dependencies=["n1"])
        node3 = ArtifactNode(id="n3", type=ArtifactType.CONSTRAINT,
                            source=ArtifactSource.LLM, content={},
                            dependencies=["n2"])

        graph.add_node(node1)
        graph.add_node(node2)
        graph.add_node(node3)

        # Should detect cycle
        assert graph.is_dag() == False


class TestGraphAnalyzer:
    """Test graph analysis functionality"""

    def test_contradiction_detection(self):
        """Test contradiction detection"""
        analyzer = GraphAnalyzer()
        graph = ArtifactGraph()

        # Add contradictory constraints
        c1 = ArtifactNode(
            id="c1",
            type=ArtifactType.CONSTRAINT,
            source=ArtifactSource.HUMAN,
            content={"rule": "System must allow access"}
        )
        c2 = ArtifactNode(
            id="c2",
            type=ArtifactType.CONSTRAINT,
            source=ArtifactSource.HUMAN,
            content={"rule": "System must deny access"}
        )

        graph.add_node(c1)
        graph.add_node(c2)

        contradictions = analyzer.detect_contradictions(graph)

        assert len(contradictions) > 0
        assert any(c['type'] == 'incompatible_constraints' for c in contradictions)

    def test_entropy_calculation(self):
        """Test entropy calculation"""
        analyzer = GraphAnalyzer()
        graph = ArtifactGraph()

        # Add diverse nodes
        for i in range(5):
            node = ArtifactNode(
                id=f"n{i}",
                type=list(ArtifactType)[i % len(ArtifactType)],
                source=list(ArtifactSource)[i % len(ArtifactSource)],
                content={"data": f"node{i}"}
            )
            graph.add_node(node)

        entropy = analyzer.calculate_entropy(graph)

        assert 0.0 <= entropy <= 1.0
        assert entropy > 0.0  # Should have some entropy with diverse nodes


class TestConfidenceCalculator:
    """Test confidence calculation"""

    def test_generative_adequacy(self):
        """Test generative adequacy calculation"""
        calculator = ConfidenceCalculator()
        graph = ArtifactGraph()

        # Add hypotheses
        for i in range(5):
            node = ArtifactNode(
                id=f"h{i}",
                type=ArtifactType.HYPOTHESIS,
                source=ArtifactSource.LLM,
                content={"hypothesis": f"Hypothesis {i}"}
            )
            graph.add_node(node)

        G_score = calculator.calculate_generative_adequacy(graph)

        assert 0.0 <= G_score <= 1.0
        assert G_score > 0.0  # Should have some score with hypotheses

    def test_deterministic_grounding(self):
        """Test deterministic grounding calculation"""
        calculator = ConfidenceCalculator()
        graph = ArtifactGraph()
        trust_model = TrustModel()

        # Add verified artifact
        node = ArtifactNode(
            id="v1",
            type=ArtifactType.FACT,
            source=ArtifactSource.COMPUTE_PLANE,
            content={"fact": "2 + 2 = 4"}
        )
        graph.add_node(node)

        # Add trust for compute plane
        trust_model.add_source(SourceTrust(
            source_id="compute_plane",
            source_type=ArtifactSource.COMPUTE_PLANE,
            trust_weight=0.9,
            volatility=0.1
        ))

        # Add verification evidence
        evidence = [VerificationEvidence(
            artifact_id="v1",
            result=VerificationResult.PASS,
            stability_score=0.95
        )]

        D_score = calculator.calculate_deterministic_grounding(
            graph, evidence, trust_model
        )

        assert 0.0 <= D_score <= 1.0
        assert D_score > 0.5  # Should be high with verified artifact

    def test_confidence_computation(self):
        """Test complete confidence computation"""
        calculator = ConfidenceCalculator()
        graph = ArtifactGraph()
        trust_model = TrustModel()

        # Add some artifacts
        node = ArtifactNode(
            id="n1",
            type=ArtifactType.HYPOTHESIS,
            source=ArtifactSource.LLM,
            content={"text": "Test"}
        )
        graph.add_node(node)

        state = calculator.compute_confidence(
            graph,
            Phase.EXPAND,
            [],
            trust_model
        )

        assert 0.0 <= state.confidence <= 1.0
        assert state.phase == Phase.EXPAND


class TestMurphyCalculator:
    """Test Murphy index calculation"""

    def test_murphy_index_low_risk(self):
        """Test Murphy index with low risk scenario"""
        calculator = MurphyCalculator()
        graph = ArtifactGraph()

        # Create low-risk state
        from confidence_engine.models import ConfidenceState
        confidence_state = ConfidenceState(
            confidence=0.9,
            generative_score=0.8,
            deterministic_score=0.9,
            epistemic_instability=0.1,
            phase=Phase.EXPAND
        )
        confidence_state.verified_artifacts = 5
        confidence_state.total_artifacts = 5

        murphy_index = calculator.calculate_murphy_index(
            graph,
            confidence_state,
            Phase.EXPAND
        )

        assert 0.0 <= murphy_index <= 1.0
        assert murphy_index < 0.3  # Should be low risk

    def test_murphy_index_high_risk(self):
        """Test Murphy index with high risk scenario"""
        calculator = MurphyCalculator()
        graph = ArtifactGraph()

        # Add contradictions
        c1 = ArtifactNode(
            id="c1",
            type=ArtifactType.CONSTRAINT,
            source=ArtifactSource.HUMAN,
            content={"rule": "must allow"}
        )
        c2 = ArtifactNode(
            id="c2",
            type=ArtifactType.CONSTRAINT,
            source=ArtifactSource.HUMAN,
            content={"rule": "must deny"}
        )
        graph.add_node(c1)
        graph.add_node(c2)

        # Create high-risk state
        from confidence_engine.models import ConfidenceState
        confidence_state = ConfidenceState(
            confidence=0.3,
            generative_score=0.4,
            deterministic_score=0.2,
            epistemic_instability=0.8,
            phase=Phase.EXECUTE
        )
        confidence_state.verified_artifacts = 0
        confidence_state.total_artifacts = 10

        murphy_index = calculator.calculate_murphy_index(
            graph,
            confidence_state,
            Phase.EXECUTE
        )

        assert 0.0 <= murphy_index <= 1.0
        assert murphy_index > 0.5  # Should be high risk


class TestAuthorityMapper:
    """Test authority mapping"""

    def test_authority_bands(self):
        """Test authority band mapping"""
        mapper = AuthorityMapper()

        test_cases = [
            (0.2, AuthorityBand.ASK_ONLY),
            (0.4, AuthorityBand.GENERATE),
            (0.6, AuthorityBand.PROPOSE),
            (0.8, AuthorityBand.NEGOTIATE),
            (0.9, AuthorityBand.EXECUTE)
        ]

        for confidence, expected_band in test_cases:
            from confidence_engine.models import ConfidenceState
            state = ConfidenceState(
                confidence=confidence,
                generative_score=0.5,
                deterministic_score=0.5,
                epistemic_instability=0.2,
                phase=Phase.EXPAND
            )

            authority_state = mapper.map_authority(state, 0.3)
            assert authority_state.authority_band == expected_band

    def test_execution_eligibility(self):
        """Test execution eligibility check"""
        mapper = AuthorityMapper()

        # All criteria met
        can_execute = mapper._check_execution_eligibility(
            confidence=0.9,
            murphy_index=0.3,
            gate_satisfaction=0.8,
            unknowns=1,
            phase=Phase.EXECUTE
        )
        assert can_execute == True

        # Low confidence
        can_execute = mapper._check_execution_eligibility(
            confidence=0.7,
            murphy_index=0.3,
            gate_satisfaction=0.8,
            unknowns=1,
            phase=Phase.EXECUTE
        )
        assert can_execute == False

        # High Murphy index
        can_execute = mapper._check_execution_eligibility(
            confidence=0.9,
            murphy_index=0.6,
            gate_satisfaction=0.8,
            unknowns=1,
            phase=Phase.EXECUTE
        )
        assert can_execute == False

    def test_authority_decay(self):
        """Test automatic authority decay"""
        mapper = AuthorityMapper()

        # Start with high authority
        current = AuthorityBand.EXECUTE

        # Confidence drops
        new_band = mapper.calculate_authority_decay(current, 0.6)

        # Should decay to lower band
        assert new_band == AuthorityBand.PROPOSE


class TestPhaseController:
    """Test phase control"""

    def test_phase_transition(self):
        """Test phase transition logic"""
        controller = PhaseController()

        # High confidence - should advance
        from confidence_engine.models import ConfidenceState
        state = ConfidenceState(
            confidence=0.9,
            generative_score=0.8,
            deterministic_score=0.9,
            epistemic_instability=0.1,
            phase=Phase.EXPAND
        )

        new_phase, transitioned, reason = controller.check_phase_transition(
            Phase.EXPAND,
            state
        )

        assert transitioned == True
        assert new_phase == Phase.TYPE

    def test_phase_no_transition(self):
        """Test phase stays when confidence insufficient"""
        controller = PhaseController()

        # Low confidence - should stay
        from confidence_engine.models import ConfidenceState
        state = ConfidenceState(
            confidence=0.2,
            generative_score=0.3,
            deterministic_score=0.1,
            epistemic_instability=0.5,
            phase=Phase.EXPAND
        )

        new_phase, transitioned, reason = controller.check_phase_transition(
            Phase.EXPAND,
            state
        )

        assert transitioned == False
        assert new_phase == Phase.EXPAND

    def test_no_phase_skipping(self):
        """Test that phase skipping is forbidden"""
        controller = PhaseController()

        assert controller.can_skip_phase() == False

    def test_no_reverse_transitions(self):
        """Test that reverse transitions are forbidden"""
        controller = PhaseController()

        assert controller.can_reverse_phase() == False


class TestAdversarialScenarios:
    """Test adversarial scenarios"""

    def test_contradiction_injection(self):
        """Test system response to contradiction injection"""
        analyzer = GraphAnalyzer()
        calculator = ConfidenceCalculator()
        graph = ArtifactGraph()
        trust_model = TrustModel()

        # Add contradictory constraints
        c1 = ArtifactNode(
            id="c1",
            type=ArtifactType.CONSTRAINT,
            source=ArtifactSource.HUMAN,
            content={"rule": "System must be secure"}
        )
        c2 = ArtifactNode(
            id="c2",
            type=ArtifactType.CONSTRAINT,
            source=ArtifactSource.HUMAN,
            content={"rule": "System must not be secure"}
        )

        graph.add_node(c1)
        graph.add_node(c2)

        # Should detect contradictions
        contradictions = analyzer.detect_contradictions(graph)
        assert len(contradictions) > 0

        # Confidence should be affected
        state = calculator.compute_confidence(graph, Phase.EXPAND, [], trust_model)
        assert state.epistemic_instability >= 0.3

    def test_trust_poisoning(self):
        """Test system response to trust poisoning"""
        trust_model = TrustModel()

        # Add source with high trust
        source = SourceTrust(
            source_id="malicious",
            source_type=ArtifactSource.API,
            trust_weight=0.9,
            volatility=0.1
        )
        trust_model.add_source(source)

        # Simulate failures
        for _ in range(5):
            trust_model.update_source("malicious", success=False)

        # Trust should decay
        final_trust = trust_model.get_trust("malicious")
        assert final_trust < 0.5

    def test_late_verification(self):
        """Test system response to late verification"""
        calculator = ConfidenceCalculator()
        graph = ArtifactGraph()
        trust_model = TrustModel()

        # Add unverified artifact
        node = ArtifactNode(
            id="late",
            type=ArtifactType.FACT,
            source=ArtifactSource.LLM,
            content={"claim": "Unverified claim"}
        )
        graph.add_node(node)

        # Compute confidence without verification
        state1 = calculator.compute_confidence(graph, Phase.EXECUTE, [], trust_model)

        # Add verification
        evidence = [VerificationEvidence(
            artifact_id="late",
            result=VerificationResult.FAIL,
            stability_score=0.9
        )]

        # Recompute
        state2 = calculator.compute_confidence(graph, Phase.EXECUTE, evidence, trust_model)

        # Confidence should not increase with failed verification
        assert state2.deterministic_score <= state1.deterministic_score

    def test_fake_certainty_detection(self):
        """Test detection of fake certainty"""
        calculator = ConfidenceCalculator()
        murphy_calc = MurphyCalculator()
        graph = ArtifactGraph()
        trust_model = TrustModel()

        # Add many unverified hypotheses (fake certainty)
        for i in range(20):
            node = ArtifactNode(
                id=f"fake{i}",
                type=ArtifactType.HYPOTHESIS,
                source=ArtifactSource.LLM,
                content={"claim": f"Unverified claim {i}"}
            )
            graph.add_node(node)

        # Compute state
        state = calculator.compute_confidence(graph, Phase.EXECUTE, [], trust_model)
        murphy_index = murphy_calc.calculate_murphy_index(graph, state, Phase.EXECUTE)

        # Should have high Murphy index (high risk)
        assert murphy_index > 0.5

        # Should have low deterministic score
        assert state.deterministic_score < 0.3


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
