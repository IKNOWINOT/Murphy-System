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


class HybridModel(ShadowAgentModel):
    """Hybrid decision tree + neural network model"""
    
    def __init__(self, config: Optional[HybridModelConfig] = None):
        super().__init__(
            config=config or HybridModelConfig(),
            metadata=ModelMetadata(model_type=ModelType.HYBRID)
        )
        
        # Initialize sub-models
        self.tree_model = DecisionTreeModel(self.config.tree_config)
        self.nn_model = None  # Will be initialized during training
    
    def train(self, X_train, y_train, X_val=None, y_val=None):
        """Train hybrid model"""
        
        logger.info("Training hybrid model...")
        
        # Train decision tree first
        logger.info("Training decision tree component...")
        self.tree_model.train(X_train, y_train, X_val, y_val)
        
        # For now, just use the tree model
        # Neural network component would be added here
        self.is_trained = True
        
        # Copy metrics from tree model
        self.metadata.train_accuracy = self.tree_model.metadata.train_accuracy
        self.metadata.validation_accuracy = self.tree_model.metadata.validation_accuracy
        
        logger.info(f"Hybrid model trained: accuracy={self.metadata.train_accuracy:.4f}")
    
    def predict(self, X):
        """Make predictions using hybrid approach"""
        if not self.is_trained:
            raise ValueError("Model not trained")
        
        # For now, just use tree predictions
        return self.tree_model.predict(X)
    
    def predict_proba(self, X):
        """Predict probabilities"""
        if not self.is_trained:
            raise ValueError("Model not trained")
        
        return self.tree_model.predict_proba(X)
    
    def get_feature_importance(self) -> Dict[str, float]:
        """Get combined feature importance"""
        if not self.is_trained:
            return {}
        
        return self.tree_model.get_feature_importance()