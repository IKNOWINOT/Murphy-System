"""
Shadow Agent Model Architecture

This module defines the hybrid decision tree/neural network model architecture.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Any, Optional
from uuid import UUID, uuid4
import logging

logger = logging.getLogger(__name__)


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


class ShadowAgentModel:
    """Base class for shadow agent models"""
    
    def __init__(self, config: Any, metadata: Optional[ModelMetadata] = None):
        self.config = config
        self.metadata = metadata or ModelMetadata()
        self.model = None
        self.is_trained = False
    
    def train(self, X_train, y_train, X_val=None, y_val=None):
        """Train the model"""
        raise NotImplementedError
    
    def predict(self, X):
        """Make predictions"""
        raise NotImplementedError
    
    def predict_proba(self, X):
        """Predict probabilities"""
        raise NotImplementedError
    
    def get_feature_importance(self) -> Dict[str, float]:
        """Get feature importance scores"""
        raise NotImplementedError
    
    def save(self, path: str):
        """Save model to disk"""
        raise NotImplementedError
    
    def load(self, path: str):
        """Load model from disk"""
        raise NotImplementedError


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
        import numpy as np
        return 1.0 / (1.0 + np.exp(-np.clip(z, -500, 500)))

    # ---- public API ----
    def fit(self, X, y):
        import numpy as np
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
        import numpy as np
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
        import numpy as np

        logger.info("Training hybrid model...")

        # 1. Train decision tree
        logger.info("Training decision tree component...")
        self.tree_model.train(X_train, y_train, X_val, y_val)

        # 2. Train lightweight neural network
        logger.info("Training neural network component...")
        nn_cfg = self.config.nn_config
        self.nn_model = _SimpleNeuralNetwork(
            hidden_size=nn_cfg.hidden_layers[0] if nn_cfg.hidden_layers else 32,
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
        import numpy as np
        # For binary classification, take class with highest probability
        return (proba[:, 1] >= 0.5).astype(int)

    def predict_proba(self, X):
        """Return class probabilities from weighted ensemble."""
        if not self.is_trained:
            raise ValueError("Model not trained")

        import numpy as np
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