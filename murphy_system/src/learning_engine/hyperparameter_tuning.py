"""
Hyperparameter Tuning System

This module implements automated hyperparameter optimization.
"""

import itertools
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID, uuid4

from .model_architecture import (
    DecisionTreeConfig,
    HybridModelConfig,
    ModelType,
    RandomForestConfig,
    ShadowAgentModel,
)
from .models import TrainingDataset
from .training_pipeline import ModelFactory, TrainingConfig, TrainingPipeline

logger = logging.getLogger(__name__)


@dataclass
class HyperparameterSpace:
    """Defines search space for hyperparameters"""
    name: str
    values: List[Any]
    type: str = "categorical"  # categorical, continuous, integer


@dataclass
class TuningConfig:
    """Configuration for hyperparameter tuning"""
    # Search strategy
    strategy: str = "grid"  # grid, random, bayesian

    # Search parameters
    n_trials: int = 50  # For random/bayesian search
    n_jobs: int = 1  # Parallel jobs

    # Evaluation
    cv_folds: int = 5  # Cross-validation folds
    scoring_metric: str = "accuracy"  # accuracy, f1, precision, recall

    # Early stopping
    early_stopping: bool = True
    patience: int = 10

    # Resource limits
    max_time_seconds: Optional[int] = None

    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TuningResult:
    """Result of hyperparameter tuning"""
    id: UUID = field(default_factory=uuid4)

    # Best configuration
    best_params: Dict[str, Any] = field(default_factory=dict)
    best_score: float = 0.0

    # All trials
    all_params: List[Dict[str, Any]] = field(default_factory=list)
    all_scores: List[float] = field(default_factory=list)

    # Timing
    tuning_duration_seconds: float = 0.0
    n_trials_completed: int = 0

    # Metadata
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


class HyperparameterTuner:
    """Automated hyperparameter tuning"""

    def __init__(self, config: Optional[TuningConfig] = None):
        self.config = config or TuningConfig()
        self.results: List[TuningResult] = []

    def tune(
        self,
        model_type: ModelType,
        dataset: TrainingDataset,
        param_space: Dict[str, HyperparameterSpace]
    ) -> TuningResult:
        """Tune hyperparameters for model"""

        logger.info(f"Starting hyperparameter tuning for {model_type.value}")
        logger.info(f"Strategy: {self.config.strategy}, Trials: {self.config.n_trials}")

        start_time = datetime.now(timezone.utc)

        if self.config.strategy == "grid":
            result = self._grid_search(model_type, dataset, param_space)
        elif self.config.strategy == "random":
            result = self._random_search(model_type, dataset, param_space)
        else:
            raise ValueError(f"Unknown strategy: {self.config.strategy}")

        result.tuning_duration_seconds = (datetime.now(timezone.utc) - start_time).total_seconds()
        self.results.append(result)

        logger.info(
            f"Tuning complete: best_score={result.best_score:.4f}, "
            f"trials={result.n_trials_completed}"
        )

        return result

    def _grid_search(
        self,
        model_type: ModelType,
        dataset: TrainingDataset,
        param_space: Dict[str, HyperparameterSpace]
    ) -> TuningResult:
        """Grid search over parameter space"""

        # Generate all combinations
        param_names = list(param_space.keys())
        param_values = [param_space[name].values for name in param_names]

        all_combinations = list(itertools.product(*param_values))

        logger.info(f"Grid search: {len(all_combinations)} combinations")

        best_params = {}
        best_score = 0.0
        all_params = []
        all_scores = []

        for i, combination in enumerate(all_combinations):
            # Create parameter dict
            params = {name: value for name, value in zip(param_names, combination)}

            # Evaluate
            score = self._evaluate_params(model_type, dataset, params)

            all_params.append(params)
            all_scores.append(score)

            if score > best_score:
                best_score = score
                best_params = params
                logger.info(f"New best: score={score:.4f}, params={params}")

            if (i + 1) % 10 == 0:
                logger.info(f"Progress: {i + 1}/{len(all_combinations)} combinations")

        return TuningResult(
            best_params=best_params,
            best_score=best_score,
            all_params=all_params,
            all_scores=all_scores,
            n_trials_completed=len(all_combinations),
        )

    def _random_search(
        self,
        model_type: ModelType,
        dataset: TrainingDataset,
        param_space: Dict[str, HyperparameterSpace]
    ) -> TuningResult:
        """Random search over parameter space"""

        import random

        logger.info(f"Random search: {self.config.n_trials} trials")

        best_params = {}
        best_score = 0.0
        all_params = []
        all_scores = []

        for i in range(self.config.n_trials):
            # Sample random parameters
            params = {}
            for name, space in param_space.items():
                params[name] = random.choice(space.values)

            # Evaluate
            score = self._evaluate_params(model_type, dataset, params)

            all_params.append(params)
            all_scores.append(score)

            if score > best_score:
                best_score = score
                best_params = params
                logger.info(f"New best: score={score:.4f}, params={params}")

            if (i + 1) % 10 == 0:
                logger.info(f"Progress: {i + 1}/{self.config.n_trials} trials")

        return TuningResult(
            best_params=best_params,
            best_score=best_score,
            all_params=all_params,
            all_scores=all_scores,
            n_trials_completed=self.config.n_trials,
        )

    def _evaluate_params(
        self,
        model_type: ModelType,
        dataset: TrainingDataset,
        params: Dict[str, Any]
    ) -> float:
        """Evaluate a parameter configuration"""

        try:
            # Create model config from params
            config = self._create_model_config(model_type, params)

            # Create and train model
            model = ModelFactory.create_model(model_type, config)
            pipeline = TrainingPipeline()

            trained_model = pipeline.train(model, dataset)

            # Return validation accuracy as score
            return trained_model.metadata.validation_accuracy

        except Exception as exc:
            logger.warning(f"Evaluation failed for params {params}: {exc}")
            return 0.0

    def _create_model_config(self, model_type: ModelType, params: Dict[str, Any]) -> Any:
        """Create model config from parameters"""

        if model_type == ModelType.DECISION_TREE:
            return DecisionTreeConfig(**params)
        elif model_type == ModelType.RANDOM_FOREST:
            return RandomForestConfig(**params)
        elif model_type == ModelType.HYBRID:
            return HybridModelConfig(**params)
        else:
            raise ValueError(f"Unknown model type: {model_type}")

    def get_best_params(self) -> Optional[Dict[str, Any]]:
        """Get best parameters from all tuning runs"""

        if not self.results:
            return None

        best_result = max(self.results, key=lambda r: r.best_score)
        return best_result.best_params


def get_default_param_space(model_type: ModelType) -> Dict[str, HyperparameterSpace]:
    """Get default parameter search space for model type"""

    if model_type == ModelType.DECISION_TREE:
        return {
            "max_depth": HyperparameterSpace(
                name="max_depth",
                values=[3, 5, 7, 10, 15, 20],
                type="integer"
            ),
            "min_samples_split": HyperparameterSpace(
                name="min_samples_split",
                values=[2, 5, 10, 20],
                type="integer"
            ),
            "min_samples_leaf": HyperparameterSpace(
                name="min_samples_leaf",
                values=[1, 2, 4, 8],
                type="integer"
            ),
            "criterion": HyperparameterSpace(
                name="criterion",
                values=["gini", "entropy"],
                type="categorical"
            ),
        }

    elif model_type == ModelType.RANDOM_FOREST:
        return {
            "n_estimators": HyperparameterSpace(
                name="n_estimators",
                values=[50, 100, 200, 300],
                type="integer"
            ),
            "max_depth": HyperparameterSpace(
                name="max_depth",
                values=[5, 10, 15, 20, None],
                type="integer"
            ),
            "min_samples_split": HyperparameterSpace(
                name="min_samples_split",
                values=[2, 5, 10],
                type="integer"
            ),
            "max_features": HyperparameterSpace(
                name="max_features",
                values=["sqrt", "log2"],
                type="categorical"
            ),
        }

    else:
        return {}
