"""
Tests for Session-5 Completion Implementations
===============================================

Covers:
- C1: HybridModel neural-network integration (tree+NN ensemble)
- C2: Credential verifier hardening (AWS/GitHub/Database format validation)
- C3: GradientBoostingModel full implementation
- C4: Regression — existing model classes still function correctly

Best-practice labels (30 yr+ team standards):
    [UNIT]  — isolated function/class test
    [INTEG] — cross-module integration
    [SEC]   — security-related
    [REGR]  — regression safety-net
"""

import sys
import os
import asyncio

_base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _base)
sys.path.insert(0, os.path.join(_base, "src"))

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

sklearn = pytest.importorskip("sklearn", reason="scikit-learn required for ML model tests")


def _make_binary_dataset(n_samples=200, n_features=4, seed=42):
    """Create a simple linearly-separable binary dataset for testing."""
    import numpy as np

    rng = np.random.RandomState(seed)
    X = rng.randn(n_samples, n_features)
    y = (X[:, 0] + X[:, 1] > 0).astype(int)
    # 70/30 split
    split = int(n_samples * 0.7)
    return X[:split], y[:split], X[split:], y[split:]


# ============================================================================
# C1 — HybridModel: tree + NN ensemble
# ============================================================================


class TestHybridModelNNIntegration:
    """[UNIT] Verify HybridModel trains both tree and NN components and
    produces ensemble predictions."""

    def test_hybrid_trains_successfully(self):
        """[UNIT] HybridModel.train() completes without error."""
        from learning_engine.model_architecture import HybridModel

        X_tr, y_tr, X_val, y_val = _make_binary_dataset()
        model = HybridModel()
        model.train(X_tr, y_tr, X_val, y_val)
        assert model.is_trained

    def test_hybrid_has_nn_component(self):
        """[UNIT] After training, nn_model is not None."""
        from learning_engine.model_architecture import HybridModel

        X_tr, y_tr, _, _ = _make_binary_dataset()
        model = HybridModel()
        model.train(X_tr, y_tr)
        assert model.nn_model is not None

    def test_hybrid_predict_returns_correct_shape(self):
        """[UNIT] predict() returns one label per sample."""
        from learning_engine.model_architecture import HybridModel
        import numpy as np

        X_tr, y_tr, X_val, _ = _make_binary_dataset()
        model = HybridModel()
        model.train(X_tr, y_tr)
        preds = model.predict(X_val)
        assert len(preds) == len(X_val)
        assert set(np.unique(preds)).issubset({0, 1})

    def test_hybrid_predict_proba_sums_to_one(self):
        """[UNIT] predict_proba() rows sum to ~1.0."""
        from learning_engine.model_architecture import HybridModel
        import numpy as np

        X_tr, y_tr, X_val, _ = _make_binary_dataset()
        model = HybridModel()
        model.train(X_tr, y_tr)
        proba = model.predict_proba(X_val)
        assert proba.shape == (len(X_val), 2)
        np.testing.assert_allclose(proba.sum(axis=1), 1.0, atol=1e-6)

    def test_hybrid_accuracy_above_chance(self):
        """[UNIT] Ensemble accuracy on a separable dataset > 60%."""
        from learning_engine.model_architecture import HybridModel
        import numpy as np

        X_tr, y_tr, X_val, y_val = _make_binary_dataset()
        model = HybridModel()
        model.train(X_tr, y_tr, X_val, y_val)
        preds = model.predict(X_val)
        accuracy = float(np.mean(preds == y_val))
        assert accuracy > 0.6, f"Accuracy {accuracy:.2f} below chance threshold"

    def test_hybrid_metadata_recorded(self):
        """[UNIT] Training populates metadata.train_accuracy."""
        from learning_engine.model_architecture import HybridModel

        X_tr, y_tr, X_val, y_val = _make_binary_dataset()
        model = HybridModel()
        model.train(X_tr, y_tr, X_val, y_val)
        assert model.metadata.train_accuracy > 0
        assert model.metadata.validation_accuracy > 0

    def test_hybrid_feature_importance_populated(self):
        """[UNIT] get_feature_importance() returns non-empty dict."""
        from learning_engine.model_architecture import HybridModel

        X_tr, y_tr, _, _ = _make_binary_dataset()
        model = HybridModel()
        model.train(X_tr, y_tr)
        importance = model.get_feature_importance()
        assert len(importance) > 0

    def test_hybrid_untrained_raises(self):
        """[UNIT] predict on untrained model raises ValueError."""
        from learning_engine.model_architecture import HybridModel
        import numpy as np

        model = HybridModel()
        with pytest.raises(ValueError, match="not trained"):
            model.predict(np.array([[1, 2, 3, 4]]))


# ============================================================================
# C3 — GradientBoostingModel
# ============================================================================


class TestGradientBoostingModel:
    """[UNIT] Verify GradientBoostingModel trains and predicts correctly."""

    def test_trains_successfully(self):
        """[UNIT] GradientBoostingModel trains without error."""
        from learning_engine.model_architecture import GradientBoostingModel

        X_tr, y_tr, X_val, y_val = _make_binary_dataset()
        model = GradientBoostingModel()
        model.train(X_tr, y_tr, X_val, y_val)
        assert model.is_trained

    def test_predict_shape(self):
        """[UNIT] predict() returns correct number of labels."""
        from learning_engine.model_architecture import GradientBoostingModel

        X_tr, y_tr, X_val, _ = _make_binary_dataset()
        model = GradientBoostingModel()
        model.train(X_tr, y_tr)
        preds = model.predict(X_val)
        assert len(preds) == len(X_val)

    def test_predict_proba_shape(self):
        """[UNIT] predict_proba() returns (n, 2) array."""
        from learning_engine.model_architecture import GradientBoostingModel

        X_tr, y_tr, X_val, _ = _make_binary_dataset()
        model = GradientBoostingModel()
        model.train(X_tr, y_tr)
        proba = model.predict_proba(X_val)
        assert proba.shape == (len(X_val), 2)

    def test_feature_importance(self):
        """[UNIT] get_feature_importance() returns non-empty dict."""
        from learning_engine.model_architecture import GradientBoostingModel

        X_tr, y_tr, _, _ = _make_binary_dataset()
        model = GradientBoostingModel()
        model.train(X_tr, y_tr)
        importance = model.get_feature_importance()
        assert len(importance) == 4  # 4 features

    def test_untrained_raises(self):
        """[UNIT] predict on untrained model raises ValueError."""
        from learning_engine.model_architecture import GradientBoostingModel
        import numpy as np

        model = GradientBoostingModel()
        with pytest.raises(ValueError, match="not trained"):
            model.predict(np.array([[1, 2, 3, 4]]))

    def test_accuracy_above_chance(self):
        """[UNIT] Accuracy on separable data > 60%."""
        from learning_engine.model_architecture import GradientBoostingModel
        import numpy as np

        X_tr, y_tr, X_val, y_val = _make_binary_dataset()
        model = GradientBoostingModel()
        model.train(X_tr, y_tr, X_val, y_val)
        preds = model.predict(X_val)
        accuracy = float(np.mean(preds == y_val))
        assert accuracy > 0.6


# ============================================================================
# C2 — Credential verifier hardening
# ============================================================================

def _run_async(coro):
    """Helper to run an async coroutine synchronously."""
    return asyncio.run(coro)


class TestAWSCredentialVerifier:
    """[UNIT][SEC] AWS credential verification logic."""

    def _make_credential(self, value="AKIAIOSFODNN7EXAMPLE", ctype=None):
        from confidence_engine.credential_verifier import (
            Credential, CredentialType,
        )
        return Credential(
            id="aws-test-1",
            credential_type=ctype or CredentialType.API_KEY,
            service_name="aws",
            credential_value=value,
        )

    def test_verify_token_valid_type(self):
        """[UNIT][SEC] verify_token accepts API_KEY type."""
        from confidence_engine.credential_interface import AWSCredentialVerifier
        v = AWSCredentialVerifier()
        cred = self._make_credential()
        assert _run_async(v.verify_token(cred)) is True

    def test_verify_token_rejects_wrong_type(self):
        """[UNIT][SEC] verify_token rejects unsupported credential types."""
        from confidence_engine.credential_interface import AWSCredentialVerifier
        from confidence_engine.credential_verifier import CredentialType
        v = AWSCredentialVerifier()
        cred = self._make_credential(ctype=CredentialType.SSH_KEY)
        assert _run_async(v.verify_token(cred)) is False

    def test_verify_api_call_empty_value(self):
        """[UNIT][SEC] Empty credential value fails API verification."""
        from confidence_engine.credential_interface import AWSCredentialVerifier
        v = AWSCredentialVerifier()
        cred = self._make_credential(value="")
        assert _run_async(v.verify_api_call(cred)) is False

    def test_verify_api_call_format_check(self):
        """[UNIT] Valid-length key passes format check when boto3 unavailable."""
        from confidence_engine.credential_interface import AWSCredentialVerifier
        v = AWSCredentialVerifier()
        cred = self._make_credential(value="AKIAIOSFODNN7EXAMPLE")
        result = _run_async(v.verify_api_call(cred))
        assert result is True

    def test_check_permissions_returns_all(self):
        """[UNIT] check_permissions returns one entry per requested permission."""
        from confidence_engine.credential_interface import AWSCredentialVerifier
        v = AWSCredentialVerifier()
        cred = self._make_credential()
        perms = _run_async(v.check_permissions(cred, ["s3:GetObject", "ec2:DescribeInstances"]))
        assert len(perms) == 2

    def test_rate_limits_none(self):
        """[UNIT] AWS returns None for rate limits (per-service)."""
        from confidence_engine.credential_interface import AWSCredentialVerifier
        v = AWSCredentialVerifier()
        cred = self._make_credential()
        remaining, reset = _run_async(v.check_rate_limits(cred))
        assert remaining is None
        assert reset is None


class TestGitHubCredentialVerifier:
    """[UNIT][SEC] GitHub credential verification logic."""

    def _make_credential(self, value="ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"):
        from confidence_engine.credential_verifier import (
            Credential, CredentialType,
        )
        return Credential(
            id="gh-test-1",
            credential_type=CredentialType.OAUTH_TOKEN,
            service_name="github",
            credential_value=value,
        )

    def test_verify_token_valid_prefix(self):
        """[UNIT][SEC] Token with ghp_ prefix passes."""
        from confidence_engine.credential_interface import GitHubCredentialVerifier
        v = GitHubCredentialVerifier()
        assert _run_async(v.verify_token(self._make_credential())) is True

    def test_verify_token_fine_grained(self):
        """[UNIT][SEC] Fine-grained token prefix github_pat_ passes."""
        from confidence_engine.credential_interface import GitHubCredentialVerifier
        v = GitHubCredentialVerifier()
        cred = self._make_credential(value="github_pat_abcdefghijklmnop")
        assert _run_async(v.verify_token(cred)) is True

    def test_verify_token_invalid_prefix(self):
        """[UNIT][SEC] Random string fails token validation."""
        from confidence_engine.credential_interface import GitHubCredentialVerifier
        v = GitHubCredentialVerifier()
        cred = self._make_credential(value="not_a_token_12345")
        assert _run_async(v.verify_token(cred)) is False

    def test_verify_token_empty(self):
        """[UNIT][SEC] Empty token fails."""
        from confidence_engine.credential_interface import GitHubCredentialVerifier
        v = GitHubCredentialVerifier()
        cred = self._make_credential(value="")
        assert _run_async(v.verify_token(cred)) is False

    def test_rate_limits_returns_tuple(self):
        """[UNIT] Rate limits return (int, datetime) tuple."""
        from confidence_engine.credential_interface import GitHubCredentialVerifier
        v = GitHubCredentialVerifier()
        remaining, reset = _run_async(v.check_rate_limits(self._make_credential()))
        assert remaining == 5000
        assert reset is not None


class TestDatabaseCredentialVerifier:
    """[UNIT][SEC] Database credential verification logic."""

    def _make_credential(self, value="host=localhost;database=mydb;user=admin"):
        from confidence_engine.credential_verifier import (
            Credential, CredentialType,
        )
        return Credential(
            id="db-test-1",
            credential_type=CredentialType.DATABASE_CREDENTIALS,
            service_name="postgres",
            credential_value=value,
        )

    def test_verify_token_connection_string(self):
        """[UNIT] Connection string with host= keyword passes."""
        from confidence_engine.credential_interface import DatabaseCredentialVerifier
        v = DatabaseCredentialVerifier()
        assert _run_async(v.verify_token(self._make_credential())) is True

    def test_verify_token_mongodb_uri(self):
        """[UNIT] MongoDB URI passes."""
        from confidence_engine.credential_interface import DatabaseCredentialVerifier
        v = DatabaseCredentialVerifier()
        cred = self._make_credential(value="mongodb://user:pass@host:27017/db")
        assert _run_async(v.verify_token(cred)) is True

    def test_verify_token_postgresql_uri(self):
        """[UNIT] PostgreSQL URI passes."""
        from confidence_engine.credential_interface import DatabaseCredentialVerifier
        v = DatabaseCredentialVerifier()
        cred = self._make_credential(value="postgresql://user:pass@localhost/db")
        assert _run_async(v.verify_token(cred)) is True

    def test_verify_token_random_string_fails(self):
        """[UNIT][SEC] Random string without keywords fails."""
        from confidence_engine.credential_interface import DatabaseCredentialVerifier
        v = DatabaseCredentialVerifier()
        cred = self._make_credential(value="just_a_password")
        assert _run_async(v.verify_token(cred)) is False

    def test_verify_api_call_empty_fails(self):
        """[UNIT][SEC] Empty credential value fails."""
        from confidence_engine.credential_interface import DatabaseCredentialVerifier
        v = DatabaseCredentialVerifier()
        cred = self._make_credential(value="")
        assert _run_async(v.verify_api_call(cred)) is False

    def test_rate_limits_none(self):
        """[UNIT] Database returns None for rate limits."""
        from confidence_engine.credential_interface import DatabaseCredentialVerifier
        v = DatabaseCredentialVerifier()
        remaining, reset = _run_async(v.check_rate_limits(self._make_credential()))
        assert remaining is None


# ============================================================================
# C4 — Regression: existing model classes still work
# ============================================================================


class TestDecisionTreeRegression:
    """[REGR] DecisionTreeModel still works after model_architecture changes."""

    def test_train_and_predict(self):
        from learning_engine.model_architecture import DecisionTreeModel
        import numpy as np

        X_tr, y_tr, X_val, y_val = _make_binary_dataset()
        model = DecisionTreeModel()
        model.train(X_tr, y_tr, X_val, y_val)
        preds = model.predict(X_val)
        accuracy = float(np.mean(preds == y_val))
        assert accuracy > 0.5


class TestRandomForestRegression:
    """[REGR] RandomForestModel still works after model_architecture changes."""

    def test_train_and_predict(self):
        from learning_engine.model_architecture import RandomForestModel
        import numpy as np

        X_tr, y_tr, X_val, y_val = _make_binary_dataset()
        model = RandomForestModel()
        model.train(X_tr, y_tr, X_val, y_val)
        preds = model.predict(X_val)
        accuracy = float(np.mean(preds == y_val))
        assert accuracy > 0.5


class TestSimpleNeuralNetwork:
    """[UNIT] Standalone verification of _SimpleNeuralNetwork."""

    def test_fits_xor_like_pattern(self):
        """[UNIT] NN can learn a non-trivial pattern."""
        from learning_engine.model_architecture import _SimpleNeuralNetwork
        import numpy as np

        rng = np.random.RandomState(0)
        X = rng.randn(200, 2)
        y = (X[:, 0] * X[:, 1] > 0).astype(float)  # XOR-like
        nn = _SimpleNeuralNetwork(hidden_size=16, learning_rate=0.5, epochs=500)
        nn.fit(X, y)
        preds = nn.predict(X)
        accuracy = float(np.mean(preds == y))
        assert accuracy > 0.52, f"NN accuracy {accuracy:.2f} too low"

    def test_predict_proba_range(self):
        """[UNIT] Probabilities are in [0, 1]."""
        from learning_engine.model_architecture import _SimpleNeuralNetwork
        import numpy as np

        X = np.array([[1, 2], [3, 4], [-1, -2]])
        y = np.array([1, 1, 0])
        nn = _SimpleNeuralNetwork(hidden_size=4, epochs=10)
        nn.fit(X, y)
        proba = nn.predict_proba(X)
        assert all(0 <= p <= 1 for p in proba)
