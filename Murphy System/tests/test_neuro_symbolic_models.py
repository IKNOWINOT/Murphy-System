"""
Test Suite for Neuro-Symbolic Confidence Models
================================================

Tests model architecture, training, inference, and integration.
"""

import pytest
torch = pytest.importorskip("torch")
pytest.importorskip("torch_geometric")
import numpy as np
from unittest.mock import Mock, patch

from src.neuro_symbolic_models.models import (
    NeuroSymbolicConfidenceModel,
    ModelConfig,
    SymbolicFeatureProcessor,
    GraphEncoder,
    create_model
)
from src.neuro_symbolic_models.integration import (
    MLConfig,
    MLEnhancedConfidenceEngine,
    ConfidenceEngineWithML
)


class TestModelArchitecture:
    """Test neural network architecture."""

    def test_model_creation(self):
        """Test model can be created with default config."""
        model = create_model()
        assert model is not None
        assert isinstance(model, NeuroSymbolicConfidenceModel)

    def test_model_forward_pass(self):
        """Test forward pass produces correct output shapes."""
        config = ModelConfig(
            node_feature_dim=64,
            symbolic_feature_dim=32,
            hidden_dim=128
        )
        model = create_model(config)

        # Create dummy input
        num_nodes = 10
        node_features = torch.randn(num_nodes, config.node_feature_dim)
        edge_index = torch.tensor([[0, 1, 2], [1, 2, 3]], dtype=torch.long)
        symbolic_features = torch.randn(1, config.symbolic_feature_dim)

        # Forward pass
        H, D, R = model(node_features, edge_index, symbolic_features)

        # Check outputs
        assert H.shape == (1, 1)
        assert D.shape == (1, 1)
        assert R.shape == (1, 1)

        # Check bounds [0, 1]
        assert 0 <= H.item() <= 1
        assert 0 <= D.item() <= 1
        assert 0 <= R.item() <= 1

    def test_symbolic_feature_processor(self):
        """Test symbolic feature processor."""
        processor = SymbolicFeatureProcessor(input_dim=32, output_dim=128)

        symbolic_features = torch.randn(4, 32)
        output = processor(symbolic_features)

        assert output.shape == (4, 128)

    def test_graph_encoder(self):
        """Test graph encoder."""
        config = ModelConfig(hidden_dim=128)
        encoder = GraphEncoder(config)

        num_nodes = 10
        node_features = torch.randn(num_nodes, config.node_feature_dim)
        edge_index = torch.tensor([[0, 1, 2], [1, 2, 3]], dtype=torch.long)

        embeddings = encoder(node_features, edge_index)

        assert embeddings.shape == (num_nodes, config.hidden_dim)

    def test_model_parameters(self):
        """Test model has trainable parameters."""
        model = create_model()

        num_params = sum(p.numel() for p in model.parameters())
        assert num_params > 0

        # Check parameters are trainable
        trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
        assert trainable_params == num_params


class TestMLIntegration:
    """Test integration with existing Confidence Engine."""

    def test_ml_config_defaults(self):
        """Test ML config has safe defaults."""
        config = MLConfig()

        assert config.enable_ml == False  # Disabled by default
        assert config.ml_fallback_on_error == True
        assert 0 < config.ml_weight <= 0.3  # Bounded influence

    def test_enhanced_engine_without_ml(self):
        """Test enhanced engine works without ML (backward compatible)."""
        # Mock base engine
        base_engine = Mock()
        base_engine.compute_confidence.return_value = Mock(
            confidence=0.8,
            generative_adequacy=0.7,
            deterministic_grounding=0.9,
            murphy_index=0.3,
            authority="medium",
            phase="generative"
        )

        # Create enhanced engine with ML disabled
        config = MLConfig(enable_ml=False)
        enhanced_engine = MLEnhancedConfidenceEngine(base_engine, config)

        # Compute confidence
        result = enhanced_engine.compute_confidence(
            artifact_graph=Mock(),
            verification_evidence=[],
            trust_model=Mock(),
            phase="generative"
        )

        # Should use base confidence only
        assert result.confidence == 0.8
        assert result.base_confidence == 0.8
        assert result.ml_signal is None
        assert result.used_ml == False

    def test_enhanced_engine_with_ml_unavailable(self):
        """Test graceful degradation when ML unavailable."""
        # Mock base engine
        base_engine = Mock()
        base_engine.compute_confidence.return_value = Mock(
            confidence=0.8,
            generative_adequacy=0.7,
            deterministic_grounding=0.9,
            murphy_index=0.3,
            authority="medium",
            phase="generative"
        )

        # Create enhanced engine with ML enabled but unavailable
        config = MLConfig(
            enable_ml=True,
            ml_service_url="http://localhost:9999"  # Non-existent
        )
        enhanced_engine = MLEnhancedConfidenceEngine(base_engine, config)

        # Compute confidence
        result = enhanced_engine.compute_confidence(
            artifact_graph=Mock(),
            verification_evidence=[],
            trust_model=Mock(),
            phase="generative"
        )

        # Should fallback to base confidence
        assert result.confidence == 0.8
        assert result.ml_signal is None
        assert result.used_ml == False

    def test_ml_weight_bounds(self):
        """Test ML weight is properly bounded."""
        base_engine = Mock()
        config = MLConfig(enable_ml=True)
        enhanced_engine = MLEnhancedConfidenceEngine(base_engine, config)

        # Valid weight
        enhanced_engine.set_ml_weight(0.2)
        assert enhanced_engine.config.ml_weight == 0.2

        # Invalid weight (too high)
        with pytest.raises(ValueError):
            enhanced_engine.set_ml_weight(0.5)

        # Invalid weight (negative)
        with pytest.raises(ValueError):
            enhanced_engine.set_ml_weight(-0.1)

    def test_statistics_tracking(self):
        """Test ML usage statistics are tracked."""
        base_engine = Mock()
        base_engine.compute_confidence.return_value = Mock(
            confidence=0.8,
            generative_adequacy=0.7,
            deterministic_grounding=0.9,
            murphy_index=0.3,
            authority="medium",
            phase="generative"
        )

        config = MLConfig(enable_ml=True)
        enhanced_engine = MLEnhancedConfidenceEngine(base_engine, config)

        # Make some calls
        for _ in range(5):
            enhanced_engine.compute_confidence(
                artifact_graph=Mock(),
                verification_evidence=[],
                trust_model=Mock(),
                phase="generative"
            )

        # Check statistics
        stats = enhanced_engine.get_statistics()
        assert stats["ml_calls"] == 5
        assert stats["ml_enabled"] == True


class TestSafetyProperties:
    """Test safety properties of ML models."""

    def test_output_bounds(self):
        """Test model outputs are bounded in [0, 1]."""
        model = create_model()
        model.eval()

        # Test with random inputs
        for _ in range(100):
            num_nodes = np.random.randint(5, 20)
            node_features = torch.randn(num_nodes, 64)
            edge_index = torch.randint(0, num_nodes, (2, num_nodes))
            symbolic_features = torch.randn(1, 32)

            with torch.no_grad():
                H, D, R = model(node_features, edge_index, symbolic_features)

            # Check bounds
            assert 0 <= H.item() <= 1, f"H out of bounds: {H.item()}"
            assert 0 <= D.item() <= 1, f"D out of bounds: {D.item()}"
            assert 0 <= R.item() <= 1, f"R out of bounds: {R.item()}"

    def test_authority_independence(self):
        """Test ML never directly controls authority."""
        # This is enforced by design - ML only provides signals
        # Authority is always computed by base engine

        base_engine = Mock()
        base_engine.compute_confidence.return_value = Mock(
            confidence=0.8,
            generative_adequacy=0.7,
            deterministic_grounding=0.9,
            murphy_index=0.3,
            authority="medium",  # Authority from base engine
            phase="generative"
        )

        config = MLConfig(enable_ml=True)
        enhanced_engine = MLEnhancedConfidenceEngine(base_engine, config)

        result = enhanced_engine.compute_confidence(
            artifact_graph=Mock(),
            verification_evidence=[],
            trust_model=Mock(),
            phase="generative"
        )

        # Authority comes from base engine, not ML
        assert result.authority == "medium"

    def test_graceful_degradation(self):
        """Test system degrades gracefully on ML errors."""
        base_engine = Mock()
        base_engine.compute_confidence.return_value = Mock(
            confidence=0.8,
            generative_adequacy=0.7,
            deterministic_grounding=0.9,
            murphy_index=0.3,
            authority="medium",
            phase="generative"
        )

        config = MLConfig(
            enable_ml=True,
            ml_fallback_on_error=True
        )
        enhanced_engine = MLEnhancedConfidenceEngine(base_engine, config)

        # Even with ML enabled, should work if ML fails
        result = enhanced_engine.compute_confidence(
            artifact_graph=Mock(),
            verification_evidence=[],
            trust_model=Mock(),
            phase="generative"
        )

        # Should have valid result (from base engine)
        assert result.confidence == 0.8
        assert result.base_confidence == 0.8


class TestBackwardCompatibility:
    """Test backward compatibility with existing system."""

    def test_drop_in_replacement(self):
        """Test ConfidenceEngineWithML is drop-in replacement."""
        base_engine = Mock()
        base_engine.compute_confidence.return_value = Mock(
            confidence=0.8,
            generative_adequacy=0.7,
            deterministic_grounding=0.9,
            murphy_index=0.3,
            authority="medium",
            phase="generative"
        )

        # Create wrapper (ML disabled by default)
        engine = ConfidenceEngineWithML(base_engine)

        # Use exactly like base engine
        result = engine.compute_confidence(
            artifact_graph=Mock(),
            verification_evidence=[],
            trust_model=Mock(),
            phase="generative"
        )

        # Should work identically to base engine
        assert result.confidence == 0.8

    def test_no_breaking_changes(self):
        """Test no breaking changes to API."""
        base_engine = Mock()
        base_engine.some_method = Mock(return_value="test")

        engine = ConfidenceEngineWithML(base_engine)

        # Should forward unknown methods to base engine
        result = engine.some_method()
        assert result == "test"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
