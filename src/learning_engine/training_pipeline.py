"""
Model Training Pipeline

This module implements the training pipeline with checkpointing and monitoring.
"""

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from uuid import UUID, uuid4

from .model_architecture import (
    DecisionTreeModel,
    HybridModel,
    ModelMetadata,
    ModelType,
    RandomForestModel,
    ShadowAgentModel,
)
from .models import DataSplitType, TrainingDataset

logger = logging.getLogger(__name__)


@dataclass
class TrainingConfig:
    """Configuration for training pipeline"""
    # Model selection
    model_type: ModelType = ModelType.HYBRID

    # Training parameters
    max_epochs: int = 100
    batch_size: int = 32
    learning_rate: float = 0.001

    # Checkpointing
    checkpoint_dir: str = "checkpoints"
    save_frequency: int = 10  # Save every N epochs
    keep_best_only: bool = True

    # Early stopping
    early_stopping: bool = True
    patience: int = 10
    min_delta: float = 0.001

    # Validation
    validation_frequency: int = 1  # Validate every N epochs

    # Logging
    log_frequency: int = 1  # Log every N epochs
    verbose: bool = True

    # Resource limits
    max_training_time_seconds: Optional[int] = None

    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TrainingCheckpoint:
    """Training checkpoint data"""
    id: UUID = field(default_factory=uuid4)
    epoch: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Metrics
    train_loss: float = 0.0
    train_accuracy: float = 0.0
    validation_loss: float = 0.0
    validation_accuracy: float = 0.0

    # Model state
    model_path: str = ""

    # Training state
    is_best: bool = False

    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TrainingMetrics:
    """Metrics tracked during training"""
    epoch: int = 0

    # Loss
    train_loss: float = 0.0
    validation_loss: float = 0.0

    # Accuracy
    train_accuracy: float = 0.0
    validation_accuracy: float = 0.0

    # Additional metrics
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0

    # Timing
    epoch_duration_seconds: float = 0.0

    metadata: Dict[str, Any] = field(default_factory=dict)


class TrainingPipeline:
    """Manages model training with checkpointing and monitoring"""

    def __init__(self, config: Optional[TrainingConfig] = None):
        self.config = config or TrainingConfig()
        self.checkpoints: List[TrainingCheckpoint] = []
        self.metrics_history: List[TrainingMetrics] = []
        self.best_checkpoint: Optional[TrainingCheckpoint] = None

        # Create checkpoint directory
        Path(self.config.checkpoint_dir).mkdir(parents=True, exist_ok=True)

    def train(
        self,
        model: ShadowAgentModel,
        dataset: TrainingDataset,
        callbacks: Optional[List[Callable]] = None
    ) -> ShadowAgentModel:
        """Train model with full pipeline"""

        logger.info(f"Starting training pipeline for {model.metadata.model_type.value}")

        start_time = time.time()

        # Prepare data
        X_train, y_train = self._prepare_data(dataset, DataSplitType.TRAIN)
        X_val, y_val = self._prepare_data(dataset, DataSplitType.VALIDATION)

        logger.info(f"Training samples: {len(X_train)}, Validation samples: {len(X_val)}")

        # Train model
        try:
            model.train(X_train, y_train, X_val, y_val)

            # Calculate final metrics
            final_metrics = self._calculate_metrics(model, X_train, y_train, X_val, y_val)
            self.metrics_history.append(final_metrics)

            # Save final checkpoint
            checkpoint = self._save_checkpoint(model, final_metrics, is_best=True)
            self.best_checkpoint = checkpoint

            # Update model metadata
            model.metadata.training_duration_seconds = time.time() - start_time
            model.metadata.training_examples = len(X_train)
            model.metadata.train_accuracy = final_metrics.train_accuracy
            model.metadata.validation_accuracy = final_metrics.validation_accuracy

            logger.info(
                f"Training complete: train_acc={final_metrics.train_accuracy:.4f}, "
                f"val_acc={final_metrics.validation_accuracy:.4f}"
            )

        except Exception as exc:
            logger.error(f"Training failed: {exc}")
            raise

        return model

    def _prepare_data(self, dataset: TrainingDataset, split: DataSplitType):
        """Prepare data for training"""

        # Get examples for split
        if split == DataSplitType.TRAIN:
            examples = dataset.get_train_examples()
        elif split == DataSplitType.VALIDATION:
            examples = dataset.get_validation_examples()
        else:
            examples = dataset.get_test_examples()

        if not examples:
            return [], []

        # Extract features and labels
        X = []
        y = []

        for example in examples:
            # Convert features to vector
            feature_vector = [f.value for f in example.features]
            X.append(feature_vector)

            # Extract label
            if example.label:
                y.append(example.label.value)
            else:
                y.append(0)  # Default label

        return X, y

    def _calculate_metrics(
        self,
        model: ShadowAgentModel,
        X_train,
        y_train,
        X_val,
        y_val
    ) -> TrainingMetrics:
        """Calculate training metrics"""

        metrics = TrainingMetrics()

        try:
            # Training metrics
            train_predictions = model.predict(X_train)
            metrics.train_accuracy = self._calculate_accuracy(y_train, train_predictions)

            # Validation metrics
            if X_val and y_val:
                val_predictions = model.predict(X_val)
                metrics.validation_accuracy = self._calculate_accuracy(y_val, val_predictions)

                # Additional metrics
                metrics.precision, metrics.recall, metrics.f1_score = self._calculate_classification_metrics(
                    y_val, val_predictions
                )

        except Exception as exc:
            logger.warning(f"Failed to calculate metrics: {exc}")

        return metrics

    def _calculate_accuracy(self, y_true, y_pred) -> float:
        """Calculate accuracy"""
        if len(y_true) == 0:
            return 0.0

        correct = sum(1 for true, pred in zip(y_true, y_pred) if true == pred)
        return correct / len(y_true)

    def _calculate_classification_metrics(self, y_true, y_pred):
        """Calculate precision, recall, F1"""

        # Simple binary classification metrics
        tp = sum(1 for true, pred in zip(y_true, y_pred) if true == 1 and pred == 1)
        fp = sum(1 for true, pred in zip(y_true, y_pred) if true == 0 and pred == 1)
        fn = sum(1 for true, pred in zip(y_true, y_pred) if true == 1 and pred == 0)

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

        return precision, recall, f1

    def _save_checkpoint(
        self,
        model: ShadowAgentModel,
        metrics: TrainingMetrics,
        is_best: bool = False
    ) -> TrainingCheckpoint:
        """Save training checkpoint"""

        checkpoint = TrainingCheckpoint(
            epoch=metrics.epoch,
            train_loss=metrics.train_loss,
            train_accuracy=metrics.train_accuracy,
            validation_loss=metrics.validation_loss,
            validation_accuracy=metrics.validation_accuracy,
            is_best=is_best,
        )

        # Save model
        model_filename = f"model_epoch_{metrics.epoch}.pkl"
        if is_best:
            model_filename = "model_best.pkl"

        model_path = Path(self.config.checkpoint_dir) / model_filename
        checkpoint.model_path = str(model_path)

        # Save checkpoint metadata
        checkpoint_metadata = {
            "id": str(checkpoint.id),
            "epoch": checkpoint.epoch,
            "timestamp": checkpoint.timestamp.isoformat(),
            "train_accuracy": checkpoint.train_accuracy,
            "validation_accuracy": checkpoint.validation_accuracy,
            "is_best": checkpoint.is_best,
            "model_path": checkpoint.model_path,
        }

        metadata_path = Path(self.config.checkpoint_dir) / f"checkpoint_{metrics.epoch}.json"
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(checkpoint_metadata, f, indent=2)

        self.checkpoints.append(checkpoint)

        logger.info(f"Checkpoint saved: {model_filename}")

        return checkpoint

    def load_best_checkpoint(self) -> Optional[TrainingCheckpoint]:
        """Load best checkpoint"""
        if self.best_checkpoint:
            return self.best_checkpoint

        # Find best checkpoint from saved files
        checkpoint_dir = Path(self.config.checkpoint_dir)
        best_checkpoint_path = checkpoint_dir / "checkpoint_best.json"

        if best_checkpoint_path.exists():
            with open(best_checkpoint_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return TrainingCheckpoint(**data)

        return None

    def get_training_summary(self) -> Dict[str, Any]:
        """Get summary of training"""

        if not self.metrics_history:
            return {}

        final_metrics = self.metrics_history[-1]

        return {
            "total_epochs": len(self.metrics_history),
            "final_train_accuracy": final_metrics.train_accuracy,
            "final_validation_accuracy": final_metrics.validation_accuracy,
            "final_f1_score": final_metrics.f1_score,
            "best_validation_accuracy": max(
                m.validation_accuracy for m in self.metrics_history
            ) if self.metrics_history else 0.0,
            "checkpoints_saved": len(self.checkpoints),
        }


class ModelFactory:
    """Factory for creating models"""

    @staticmethod
    def create_model(model_type: ModelType, config: Optional[Any] = None) -> ShadowAgentModel:
        """Create model of specified type"""

        if model_type == ModelType.DECISION_TREE:
            return DecisionTreeModel(config)
        elif model_type == ModelType.RANDOM_FOREST:
            return RandomForestModel(config)
        elif model_type == ModelType.HYBRID:
            return HybridModel(config)
        else:
            raise ValueError(f"Unknown model type: {model_type}")
