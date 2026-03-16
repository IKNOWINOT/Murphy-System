"""
Shadow Agent Implementation

This module implements the shadow agent that learns from corrections and makes predictions.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID, uuid4

from .model_architecture import ModelMetadata, ShadowAgentModel
from .model_registry import ModelRegistry, ModelVersion

try:
    from confidence_engine.murphy_models import UncertaintyScores as UncertaintyScore
except ImportError:
    UncertaintyScore = None  # type: ignore[assignment,misc]

logger = logging.getLogger(__name__)


@dataclass
class ShadowPrediction:
    """Prediction made by shadow agent"""
    id: UUID = field(default_factory=uuid4)

    # Prediction
    prediction: Any = None
    confidence: float = 0.0

    # Probabilities (for classification)
    probabilities: Dict[str, float] = field(default_factory=dict)

    # Model info
    model_id: UUID = None
    model_version: str = ""

    # Context
    task_id: Optional[UUID] = None
    input_features: Dict[str, Any] = field(default_factory=dict)

    # Uncertainty
    uncertainty_score: Optional[UncertaintyScore] = None

    # Timing
    prediction_time_ms: float = 0.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ShadowAgentConfig:
    """Configuration for shadow agent"""
    # Confidence thresholds
    min_confidence_threshold: float = 0.7
    high_confidence_threshold: float = 0.9

    # Fallback behavior
    use_murphy_gate_fallback: bool = True
    fallback_threshold: float = 0.7

    # Model selection
    use_ensemble: bool = False
    ensemble_models: List[UUID] = field(default_factory=list)

    # Performance tracking
    track_predictions: bool = True
    max_prediction_history: int = 10000

    # A/B testing
    ab_testing_enabled: bool = False
    ab_test_ratio: float = 0.1  # 10% of traffic

    metadata: Dict[str, Any] = field(default_factory=dict)


class ShadowAgent:
    """Shadow agent that learns from corrections and makes predictions"""

    def __init__(
        self,
        model_registry: ModelRegistry,
        config: Optional[ShadowAgentConfig] = None
    ):
        self.model_registry = model_registry
        self.config = config or ShadowAgentConfig()

        self.current_model: Optional[ShadowAgentModel] = None
        self.current_model_version: Optional[ModelVersion] = None

        self.prediction_history: List[ShadowPrediction] = []

        # Load deployed model
        self._load_deployed_model()

    def _load_deployed_model(self):
        """Load currently deployed model"""

        deployed = self.model_registry.get_deployed_model("production")
        if deployed:
            logger.info(f"Loaded deployed model: {deployed.name} v{deployed.version}")
            self.current_model_version = deployed
            # In production, would actually load the model here
        else:
            logger.warning("No deployed model found")

    def predict(
        self,
        input_features: Dict[str, Any],
        task_id: Optional[UUID] = None,
        uncertainty_score: Optional[UncertaintyScore] = None
    ) -> ShadowPrediction:
        """Make prediction using shadow agent"""

        start_time = datetime.now(timezone.utc)

        if not self.current_model:
            logger.warning("No model loaded, returning default prediction")
            return self._default_prediction(input_features, task_id)

        try:
            # Extract feature vector
            feature_vector = self._extract_features(input_features)

            # Make prediction
            prediction = self.current_model.predict([feature_vector])[0]

            # Get probabilities
            probabilities = {}
            if hasattr(self.current_model, 'predict_proba'):
                proba = self.current_model.predict_proba([feature_vector])[0]
                probabilities = {f"class_{i}": float(p) for i, p in enumerate(proba)}

            # Calculate confidence
            confidence = self._calculate_confidence(probabilities, uncertainty_score)

            # Create prediction
            shadow_prediction = ShadowPrediction(
                prediction=prediction,
                confidence=confidence,
                probabilities=probabilities,
                model_id=self.current_model_version.id if self.current_model_version else None,
                model_version=self.current_model_version.version if self.current_model_version else "",
                task_id=task_id,
                input_features=input_features,
                uncertainty_score=uncertainty_score,
                prediction_time_ms=(datetime.now(timezone.utc) - start_time).total_seconds() * 1000,
            )

            # Track prediction
            if self.config.track_predictions:
                self._track_prediction(shadow_prediction)

            return shadow_prediction

        except Exception as exc:
            logger.error(f"Prediction failed: {exc}")
            return self._default_prediction(input_features, task_id)

    def predict_with_fallback(
        self,
        input_features: Dict[str, Any],
        murphy_gate_prediction: Any,
        task_id: Optional[UUID] = None,
        uncertainty_score: Optional[UncertaintyScore] = None
    ) -> Tuple[Any, str]:
        """Make prediction with fallback to Murphy Gate"""

        # Get shadow agent prediction
        shadow_pred = self.predict(input_features, task_id, uncertainty_score)

        # Check if confidence is high enough
        if shadow_pred.confidence >= self.config.fallback_threshold:
            logger.info(
                f"Using shadow agent prediction (confidence: {shadow_pred.confidence:.2f})"
            )
            return shadow_pred.prediction, "shadow_agent"
        else:
            logger.info(
                f"Falling back to Murphy Gate (shadow confidence: {shadow_pred.confidence:.2f})"
            )
            return murphy_gate_prediction, "murphy_gate"

    def _extract_features(self, input_features: Dict[str, Any]) -> List[float]:
        """Extract feature vector from input"""

        # Simple feature extraction
        # In production, would use the same feature engineering as training
        feature_vector = []

        for key in sorted(input_features.keys()):
            value = input_features[key]

            # Convert to numeric
            if isinstance(value, (int, float)):
                feature_vector.append(float(value))
            elif isinstance(value, bool):
                feature_vector.append(1.0 if value else 0.0)
            elif isinstance(value, str):
                # Simple hash-based encoding
                feature_vector.append(float(hash(value) % 1000) / 1000)
            else:
                feature_vector.append(0.0)

        return feature_vector

    def _calculate_confidence(
        self,
        probabilities: Dict[str, float],
        uncertainty_score: Optional[UncertaintyScore]
    ) -> float:
        """Calculate prediction confidence"""

        # Base confidence from model probabilities
        if probabilities:
            base_confidence = max(probabilities.values())
        else:
            base_confidence = 0.5

        # Adjust by uncertainty score
        if uncertainty_score:
            # Lower confidence if uncertainty is high
            uncertainty_penalty = uncertainty_score.total_uncertainty / 100.0
            adjusted_confidence = base_confidence * (1.0 - uncertainty_penalty * 0.5)
            return max(0.0, min(1.0, adjusted_confidence))

        return base_confidence

    def _default_prediction(
        self,
        input_features: Dict[str, Any],
        task_id: Optional[UUID]
    ) -> ShadowPrediction:
        """Return default prediction when model unavailable"""

        return ShadowPrediction(
            prediction=None,
            confidence=0.0,
            task_id=task_id,
            input_features=input_features,
            metadata={"reason": "no_model_loaded"}
        )

    def _track_prediction(self, prediction: ShadowPrediction):
        """Track prediction for monitoring"""

        self.prediction_history.append(prediction)

        # Limit history size
        if len(self.prediction_history) > self.config.max_prediction_history:
            self.prediction_history = self.prediction_history[-self.config.max_prediction_history:]

    def get_prediction_stats(self) -> Dict[str, Any]:
        """Get statistics about predictions"""

        if not self.prediction_history:
            return {}

        confidences = [p.confidence for p in self.prediction_history]

        return {
            "total_predictions": len(self.prediction_history),
            "avg_confidence": sum(confidences) / (len(confidences) or 1),
            "min_confidence": min(confidences),
            "max_confidence": max(confidences),
            "high_confidence_rate": sum(
                1 for c in confidences if c >= self.config.high_confidence_threshold
            ) / (len(confidences) or 1),
            "avg_prediction_time_ms": sum(
                p.prediction_time_ms for p in self.prediction_history
            ) / (len(self.prediction_history) or 1),
        }

    def update_model(self, model_version: ModelVersion):
        """Update to a new model version"""

        logger.info(f"Updating to model: {model_version.name} v{model_version.version}")

        self.current_model_version = model_version
        # In production, would load the actual model here

        logger.info("Model updated successfully")

    def should_use_shadow_agent(
        self,
        uncertainty_score: Optional[UncertaintyScore] = None
    ) -> bool:
        """Determine if shadow agent should be used"""

        # Check if model is loaded
        if not self.current_model:
            return False

        # Check if uncertainty is too high
        if uncertainty_score and uncertainty_score.total_uncertainty > 80:
            return False

        # A/B testing
        if self.config.ab_testing_enabled:
            import random
            return random.random() > self.config.ab_test_ratio

        return True


class ShadowAgentIntegration:
    """Integrates shadow agent with Murphy Gate"""

    def __init__(
        self,
        shadow_agent: ShadowAgent,
        murphy_gate: Any  # MurphyGate from phase 2
    ):
        self.shadow_agent = shadow_agent
        self.murphy_gate = murphy_gate

    def make_decision(
        self,
        task_data: Dict[str, Any],
        uncertainty_score: UncertaintyScore
    ) -> Tuple[bool, str, float]:
        """Make decision using shadow agent or Murphy Gate"""

        # Check if shadow agent should be used
        if self.shadow_agent.should_use_shadow_agent(uncertainty_score):
            # Get shadow agent prediction
            prediction = self.shadow_agent.predict(
                input_features=task_data,
                uncertainty_score=uncertainty_score
            )

            # Check confidence
            if prediction.confidence >= self.shadow_agent.config.min_confidence_threshold:
                return (
                    bool(prediction.prediction),
                    "shadow_agent",
                    prediction.confidence
                )

        # Fall back to Murphy Gate
        murphy_decision = self.murphy_gate.should_proceed(uncertainty_score)
        return (
            murphy_decision,
            "murphy_gate",
            1.0 - (uncertainty_score.total_uncertainty / 100.0)
        )
