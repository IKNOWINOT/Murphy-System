"""
Shadow Agent Model Architecture

This module defines the hybrid decision tree/neural network model architecture.
"""

import logging
import pickle
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

import numpy as np

logger = logging.getLogger(__name__)

# Allowed top-level modules for unpickling (numpy, sklearn, builtins only)
_PICKLE_SAFE_MODULES = frozenset({
    "numpy", "numpy.core", "numpy.core.multiarray", "numpy.core.numeric",
    "numpy.random", "numpy.ma", "numpy.dtypes",
    "sklearn", "builtins", "collections", "copy", "copyreg",
    "_codecs", "encodings", "io",
})


class _RestrictedUnpickler(pickle.Unpickler):
    """Unpickler that refuses to load arbitrary modules.

    Only numpy, sklearn, and Python built-in types are allowed, which is
    sufficient for the ML models stored by this module while blocking
    code-execution exploits (CWE-502).
    """

    def find_class(self, module: str, name: str):
        top = module.split(".")[0]
        if top in _PICKLE_SAFE_MODULES:
            return super().find_class(module, name)
        raise pickle.UnpicklingError(
            f"Restricted unpickler refused module {module!r}"
        )


class ModelType(str, Enum):
    """Types of models"""
    DECISION_TREE = "decision_tree"
    RANDOM_FOREST = "random_forest"
    GRADIENT_BOOSTING = "gradient_boosting"
    NEURAL_NETWORK = "neural_network"
    HYBRID = "hybrid"


class ActivationFunction(str, Enum):
    """Neural network activation functions"""
    RELU = "relu"
    SIGMOID = "sigmoid"
    TANH = "tanh"
    SOFTMAX = "softmax"
    LEAKY_RELU = "leaky_relu"


@dataclass
class DecisionTreeConfig:
    """Configuration for decision tree models"""
    max_depth: int = 10
    min_samples_split: int = 2
    min_samples_leaf: int = 1
    max_features: Optional[str] = "sqrt"  # sqrt, log2, None
    criterion: str = "gini"  # gini, entropy
    splitter: str = "best"  # best, random

    # Pruning
    ccp_alpha: float = 0.0
    min_impurity_decrease: float = 0.0


@dataclass
class RandomForestConfig:
    """Configuration for random forest models"""
    n_estimators: int = 100
    max_depth: int = 10
    min_samples_split: int = 2
    min_samples_leaf: int = 1
    max_features: str = "sqrt"
    criterion: str = "gini"

    # Ensemble parameters
    bootstrap: bool = True
    oob_score: bool = True
    n_jobs: int = -1


@dataclass
class GradientBoostingConfig:
    """Configuration for gradient boosting models"""
    n_estimators: int = 100
    learning_rate: float = 0.1
    max_depth: int = 3
    min_samples_split: int = 2
    min_samples_leaf: int = 1
    subsample: float = 1.0
    max_features: Optional[str] = None

    # Loss function
    loss: str = "log_loss"  # log_loss, exponential


@dataclass
class NeuralNetworkConfig:
    """Configuration for neural network models"""
    # Architecture
    hidden_layers: List[int] = field(default_factory=lambda: [128, 64, 32])
    activation: ActivationFunction = ActivationFunction.RELU
    output_activation: ActivationFunction = ActivationFunction.SIGMOID

    # Regularization
    dropout_rate: float = 0.2
    l1_reg: float = 0.0
    l2_reg: float = 0.01

    # Batch normalization
    use_batch_norm: bool = True

    # Training
    learning_rate: float = 0.001
    batch_size: int = 32
    epochs: int = 100

    # Optimizer
    optimizer: str = "adam"  # adam, sgd, rmsprop

    # Early stopping
    early_stopping: bool = True
    patience: int = 10
    min_delta: float = 0.001


@dataclass
class HybridModelConfig:
    """Configuration for hybrid decision tree + neural network model"""
    # Decision tree for initial filtering
    tree_config: DecisionTreeConfig = field(default_factory=DecisionTreeConfig)

    # Neural network for refinement
    nn_config: NeuralNetworkConfig = field(default_factory=NeuralNetworkConfig)

    # Hybrid strategy
    use_tree_first: bool = True  # Use tree to filter, then NN
    tree_confidence_threshold: float = 0.8  # If tree confidence > threshold, skip NN

    # Ensemble
    ensemble_method: str = "weighted"  # weighted, voting, stacking


@dataclass
class ModelMetadata:
    """Metadata about a trained model"""
    id: UUID = field(default_factory=uuid4)
    name: str = ""
    version: str = "1.0.0"
    model_type: ModelType = ModelType.HYBRID

    # Training info
    trained_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    training_duration_seconds: float = 0.0
    training_examples: int = 0

    # Performance metrics
    train_accuracy: float = 0.0
    validation_accuracy: float = 0.0
    test_accuracy: float = 0.0

    train_loss: float = 0.0
    validation_loss: float = 0.0
    test_loss: float = 0.0

    # Additional metrics
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0
    auc_roc: float = 0.0

    # Feature importance
    feature_importance: Dict[str, float] = field(default_factory=dict)

    # Configuration
    config: Dict[str, Any] = field(default_factory=dict)
    hyperparameters: Dict[str, Any] = field(default_factory=dict)

    # Deployment info
    is_deployed: bool = False
    deployment_date: Optional[datetime] = None

    metadata: Dict[str, Any] = field(default_factory=dict)


class ShadowAgentModel(ABC):
    """
    Base class for shadow-agent learning models.

    Provides serialisation (``save`` / ``load``) via :mod:`json` + :mod:`pickle`
    and default implementations for ``predict_proba`` and ``get_feature_importance``
    so that subclasses only need to override ``train`` and ``predict``.
    """

    def __init__(self, config: Any, metadata: Optional[ModelMetadata] = None):
        self.config = config
        self.metadata = metadata or ModelMetadata()
        self.model = None
        self.is_trained = False

    # ------------------------------------------------------------------
    # Training & Prediction — subclasses MUST override train/predict
    # ------------------------------------------------------------------

    @abstractmethod
    def train(self, X_train, y_train, X_val=None, y_val=None):
        """Train the model.  Subclasses must override."""
        ...

    @abstractmethod
    def predict(self, X):
        """Return predictions for *X*.  Subclasses must override."""
        ...

    def predict_proba(self, X):
        """
        Return class-probability estimates for *X*.

        Default implementation delegates to the underlying model's
        ``predict_proba`` when available, otherwise falls back to
        one-hot encoding of ``predict`` output.
        """
        if not self.is_trained:
            raise ValueError("Model not trained")
        if self.model is not None and hasattr(self.model, 'predict_proba'):
            return self.model.predict_proba(X)
        # Fallback: one-hot from predict
        import numpy as _np
        preds = self.predict(X)
        unique_classes = sorted(set(preds))
        class_idx = {c: i for i, c in enumerate(unique_classes)}
        proba = _np.zeros((len(preds), len(unique_classes)))
        for row, pred in enumerate(preds):
            proba[row, class_idx[pred]] = 1.0
        return proba

    def get_feature_importance(self) -> Dict[str, float]:
        """
        Return feature-importance scores from the underlying estimator.

        Default implementation inspects ``model.feature_importances_`` (sklearn
        convention) or ``model.coef_``, returning an empty dict when neither
        attribute exists.
        """
        if not self.is_trained or self.model is None:
            return {}
        if hasattr(self.model, 'feature_importances_'):
            imp = self.model.feature_importances_
            return {f"feature_{i}": float(v) for i, v in enumerate(imp)}
        if hasattr(self.model, 'coef_'):
            import numpy as _np
            coef = _np.abs(self.model.coef_).mean(axis=0) if self.model.coef_.ndim > 1 else _np.abs(self.model.coef_)
            return {f"feature_{i}": float(v) for i, v in enumerate(coef)}
        return {}

    # ------------------------------------------------------------------
    # Persistence — JSON metadata + pickle model
    # ------------------------------------------------------------------

    def save(self, path: str):
        """
        Persist the trained model and its metadata to *path*.

        Layout::

            <path>/
                metadata.json   — ModelMetadata as JSON
                model.pkl       — pickled sklearn / custom estimator
        """
        import json
        import os
        import pickle

        os.makedirs(path, exist_ok=True)

        # Metadata
        meta_dict = {
            'model_type': self.metadata.model_type.value if self.metadata.model_type else None,
            'train_accuracy': self.metadata.train_accuracy,
            'validation_accuracy': self.metadata.validation_accuracy,
            'is_trained': self.is_trained,
            'feature_importance': self.metadata.feature_importance,
            'config': {k: v for k, v in vars(self.config).items()} if hasattr(self.config, '__dict__') else {},
        }
        with open(os.path.join(path, 'metadata.json'), 'w', encoding='utf-8') as f:
            json.dump(meta_dict, f, indent=2, default=str)

        # Model binary
        if self.model is not None:
            with open(os.path.join(path, 'model.pkl'), 'wb') as f:
                pickle.dump(self.model, f, protocol=pickle.HIGHEST_PROTOCOL)

        logger.info("Model saved to %s", path)

    def load(self, path: str):
        """
        Load a previously persisted model from *path*.

        Restores both the model binary and its metadata.
        """
        import json
        import os
        import pickle

        meta_path = os.path.join(path, 'metadata.json')
        model_path = os.path.join(path, 'model.pkl')

        if os.path.isfile(meta_path):
            with open(meta_path, 'r', encoding='utf-8') as f:
                meta_dict = json.load(f)
            self.metadata.train_accuracy = meta_dict.get('train_accuracy', 0.0)
            self.metadata.validation_accuracy = meta_dict.get('validation_accuracy', 0.0)
            self.metadata.feature_importance = meta_dict.get('feature_importance', {})

        if os.path.isfile(model_path):
            with open(model_path, 'rb') as f:
                unpickler = _RestrictedUnpickler(f)
                self.model = unpickler.load()
            self.is_trained = True
        else:
            logger.warning("No model binary found at %s", model_path)
            self.is_trained = False

        logger.info("Model loaded from %s (trained=%s)", path, self.is_trained)


class DecisionTreeModel(ShadowAgentModel):
    """Decision tree model implementation"""

    def __init__(self, config: Optional[DecisionTreeConfig] = None):
        super().__init__(
            config=config or DecisionTreeConfig(),
            metadata=ModelMetadata(model_type=ModelType.DECISION_TREE)
        )

    def train(self, X_train, y_train, X_val=None, y_val=None):
        """Train decision tree"""
        try:
            from sklearn.tree import DecisionTreeClassifier

            self.model = DecisionTreeClassifier(
                max_depth=self.config.max_depth,
                min_samples_split=self.config.min_samples_split,
                min_samples_leaf=self.config.min_samples_leaf,
                max_features=self.config.max_features,
                criterion=self.config.criterion,
                splitter=self.config.splitter,
                ccp_alpha=self.config.ccp_alpha,
                min_impurity_decrease=self.config.min_impurity_decrease,
                random_state=42,
            )

            self.model.fit(X_train, y_train)
            self.is_trained = True

            # Calculate metrics
            self.metadata.train_accuracy = self.model.score(X_train, y_train)
            if X_val is not None and y_val is not None:
                self.metadata.validation_accuracy = self.model.score(X_val, y_val)

            logger.info(f"Decision tree trained: accuracy={self.metadata.train_accuracy:.4f}")

        except ImportError:
            logger.error("scikit-learn not installed. Install with: pip install scikit-learn")
            raise

    def predict(self, X):
        """Make predictions"""
        if not self.is_trained:
            raise ValueError("Model not trained")
        return self.model.predict(X)

    def predict_proba(self, X):
        """Predict probabilities"""
        if not self.is_trained:
            raise ValueError("Model not trained")
        return self.model.predict_proba(X)

    def get_feature_importance(self) -> Dict[str, float]:
        """Get feature importance"""
        if not self.is_trained:
            return {}

        importance = self.model.feature_importances_
        return {f"feature_{i}": float(imp) for i, imp in enumerate(importance)}


class RandomForestModel(ShadowAgentModel):
    """Random forest model implementation"""

    def __init__(self, config: Optional[RandomForestConfig] = None):
        super().__init__(
            config=config or RandomForestConfig(),
            metadata=ModelMetadata(model_type=ModelType.RANDOM_FOREST)
        )

    def train(self, X_train, y_train, X_val=None, y_val=None):
        """Train random forest"""
        try:
            from sklearn.ensemble import RandomForestClassifier

            self.model = RandomForestClassifier(
                n_estimators=self.config.n_estimators,
                max_depth=self.config.max_depth,
                min_samples_split=self.config.min_samples_split,
                min_samples_leaf=self.config.min_samples_leaf,
                max_features=self.config.max_features,
                criterion=self.config.criterion,
                bootstrap=self.config.bootstrap,
                oob_score=self.config.oob_score,
                n_jobs=self.config.n_jobs,
                random_state=42,
            )

            self.model.fit(X_train, y_train)
            self.is_trained = True

            # Calculate metrics
            self.metadata.train_accuracy = self.model.score(X_train, y_train)
            if X_val is not None and y_val is not None:
                self.metadata.validation_accuracy = self.model.score(X_val, y_val)

            logger.info(f"Random forest trained: accuracy={self.metadata.train_accuracy:.4f}")

        except ImportError:
            logger.error("scikit-learn not installed")
            raise

    def predict(self, X):
        if not self.is_trained:
            raise ValueError("Model not trained")
        return self.model.predict(X)

    def predict_proba(self, X):
        if not self.is_trained:
            raise ValueError("Model not trained")
        return self.model.predict_proba(X)

    def get_feature_importance(self) -> Dict[str, float]:
        if not self.is_trained:
            return {}

        importance = self.model.feature_importances_
        return {f"feature_{i}": float(imp) for i, imp in enumerate(importance)}


class GradientBoostingModel(ShadowAgentModel):
    """Gradient boosting model implementation"""

    def __init__(self, config: Optional[GradientBoostingConfig] = None):
        super().__init__(
            config=config or GradientBoostingConfig(),
            metadata=ModelMetadata(model_type=ModelType.GRADIENT_BOOSTING),
        )

    def train(self, X_train, y_train, X_val=None, y_val=None):
        """Train gradient boosting classifier"""
        try:
            from sklearn.ensemble import GradientBoostingClassifier

            self.model = GradientBoostingClassifier(
                n_estimators=self.config.n_estimators,
                learning_rate=self.config.learning_rate,
                max_depth=self.config.max_depth,
                min_samples_split=self.config.min_samples_split,
                min_samples_leaf=self.config.min_samples_leaf,
                subsample=self.config.subsample,
                max_features=self.config.max_features,
                random_state=42,
            )

            self.model.fit(X_train, y_train)
            self.is_trained = True

            self.metadata.train_accuracy = self.model.score(X_train, y_train)
            if X_val is not None and y_val is not None:
                self.metadata.validation_accuracy = self.model.score(X_val, y_val)

            logger.info(
                "Gradient boosting trained: accuracy=%.4f",
                self.metadata.train_accuracy,
            )

        except ImportError:
            logger.error("scikit-learn not installed")
            raise

    def predict(self, X):
        if not self.is_trained:
            raise ValueError("Model not trained")
        return self.model.predict(X)

    def predict_proba(self, X):
        if not self.is_trained:
            raise ValueError("Model not trained")
        return self.model.predict_proba(X)

    def get_feature_importance(self) -> Dict[str, float]:
        if not self.is_trained:
            return {}
        importance = self.model.feature_importances_
        return {f"feature_{i}": float(imp) for i, imp in enumerate(importance)}


class _SimpleNeuralNetwork:
    """Lightweight NumPy-only neural network for the hybrid model.

    Implements a single-hidden-layer MLP with sigmoid activation so the
    ``HybridModel`` can combine tree and neural-network predictions
    without requiring an external deep-learning framework.
    """

    def __init__(self, hidden_size: int = 32, learning_rate: float = 0.01,
                 epochs: int = 100):
        self.hidden_size = hidden_size
        self.learning_rate = learning_rate
        self.epochs = epochs
        self._W1 = None
        self._b1 = None
        self._W2 = None
        self._b2 = None

    # ---- activation helpers ----
    @staticmethod
    def _sigmoid(z):
        return 1.0 / (1.0 + np.exp(-np.clip(z, -500, 500)))

    # ---- public API ----
    def fit(self, X, y):
        X = np.asarray(X, dtype=float)
        y = np.asarray(y, dtype=float).reshape(-1, 1)

        n_features = X.shape[1]
        rng = np.random.RandomState(42)
        self._W1 = rng.randn(n_features, self.hidden_size) * 0.1
        self._b1 = np.zeros((1, self.hidden_size))
        self._W2 = rng.randn(self.hidden_size, 1) * 0.1
        self._b2 = np.zeros((1, 1))

        for _ in range(self.epochs):
            # Forward
            z1 = X @ self._W1 + self._b1
            a1 = self._sigmoid(z1)
            z2 = a1 @ self._W2 + self._b2
            a2 = self._sigmoid(z2)

            # Backward (binary cross-entropy gradient)
            m = X.shape[0]
            dz2 = a2 - y
            dW2 = (a1.T @ dz2) / m
            db2 = np.sum(dz2, axis=0, keepdims=True) / m
            dz1 = (dz2 @ self._W2.T) * a1 * (1 - a1)
            dW1 = (X.T @ dz1) / m
            db1 = np.sum(dz1, axis=0, keepdims=True) / m

            self._W1 -= self.learning_rate * dW1
            self._b1 -= self.learning_rate * db1
            self._W2 -= self.learning_rate * dW2
            self._b2 -= self.learning_rate * db2

    def predict_proba(self, X):
        """Return P(class=1) for each sample."""
        X = np.asarray(X, dtype=float)
        z1 = X @ self._W1 + self._b1
        a1 = self._sigmoid(z1)
        z2 = a1 @ self._W2 + self._b2
        return self._sigmoid(z2).ravel()

    def predict(self, X):
        return (self.predict_proba(X) >= 0.5).astype(int)


class HybridModel(ShadowAgentModel):
    """Hybrid decision tree + neural network model.

    Uses a decision tree for interpretable rule extraction and a lightweight
    neural network for residual refinement.  Predictions are combined via
    a configurable weighted ensemble (default 70% tree / 30% NN).
    """

    def __init__(self, config: Optional[HybridModelConfig] = None):
        super().__init__(
            config=config or HybridModelConfig(),
            metadata=ModelMetadata(model_type=ModelType.HYBRID),
        )

        # Sub-models
        self.tree_model = DecisionTreeModel(self.config.tree_config)
        self.nn_model: Optional[_SimpleNeuralNetwork] = None

        # Ensemble weight for tree component (NN gets 1 - tree_weight)
        self.tree_weight: float = 0.7

    def train(self, X_train, y_train, X_val=None, y_val=None):
        """Train both tree and neural-network components."""

        logger.info("Training hybrid model...")

        # 1. Train decision tree
        logger.info("Training decision tree component...")
        self.tree_model.train(X_train, y_train, X_val, y_val)

        # 2. Train lightweight neural network
        logger.info("Training neural network component...")
        nn_cfg = self.config.nn_config
        hidden_size = (
            nn_cfg.hidden_layers[0]
            if nn_cfg.hidden_layers and len(nn_cfg.hidden_layers) > 0
            else 32
        )
        self.nn_model = _SimpleNeuralNetwork(
            hidden_size=hidden_size,
            learning_rate=nn_cfg.learning_rate,
            epochs=nn_cfg.epochs,
        )
        self.nn_model.fit(X_train, y_train)
        self.is_trained = True

        # 3. Compute ensemble accuracy
        train_preds = self.predict(X_train)
        self.metadata.train_accuracy = float(
            np.mean(np.asarray(train_preds) == np.asarray(y_train))
        )
        if X_val is not None and y_val is not None:
            val_preds = self.predict(X_val)
            self.metadata.validation_accuracy = float(
                np.mean(np.asarray(val_preds) == np.asarray(y_val))
            )

        logger.info(
            "Hybrid model trained: accuracy=%.4f", self.metadata.train_accuracy
        )

    def predict(self, X):
        """Predict using weighted ensemble of tree + NN."""
        if not self.is_trained:
            raise ValueError("Model not trained")

        proba = self.predict_proba(X)
        # For binary classification, take class with highest probability
        return (proba[:, 1] >= 0.5).astype(int)

    def predict_proba(self, X):
        """Return class probabilities from weighted ensemble."""
        if not self.is_trained:
            raise ValueError("Model not trained")

        tree_proba = self.tree_model.predict_proba(X)  # (n, n_classes)

        if self.nn_model is not None:
            nn_p1 = self.nn_model.predict_proba(X)  # (n,) — P(class=1)
            nn_proba = np.column_stack([1 - nn_p1, nn_p1])
            combined = (
                self.tree_weight * tree_proba
                + (1 - self.tree_weight) * nn_proba
            )
        else:
            combined = tree_proba

        return combined

    def get_feature_importance(self) -> Dict[str, float]:
        """Get feature importance from the tree component.

        The NN does not expose per-feature importance natively, so the
        tree importance is returned (the primary interpretability lever).
        """
        if not self.is_trained:
            return {}

        return self.tree_model.get_feature_importance()
