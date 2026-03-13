"""
Complete Shadow Agent Integration

This module provides the complete integration of all shadow agent components.
"""

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from .ab_testing import ABTestConfig, ABTestFramework, GradualRollout, VariantType
from .feature_engineering import FeatureEngineer
from .hyperparameter_tuning import HyperparameterTuner, TuningConfig, get_default_param_space
from .model_architecture import HybridModelConfig, ModelType
from .model_registry import ModelRegistry
from .shadow_agent import ShadowAgent, ShadowAgentConfig
from .shadow_evaluation import AutomatedTestSuite, ModelEvaluator
from .shadow_monitoring import FeedbackLoop, MonitoringConfig, MonitoringDashboard
from .training_data_transformer import (
    CorrectionToTrainingTransformer,
    FeedbackToTrainingTransformer,
    PatternToTrainingTransformer,
)
from .training_data_validator import DataSplitter, DataValidator
from .training_pipeline import ModelFactory, TrainingConfig, TrainingPipeline

try:
    from .correction_models import Correction, CorrectionType  # noqa: F401
    from .feedback_system import Feedback  # noqa: F401
    from .pattern_extraction import CorrectionPattern as Pattern  # noqa: F401
except ImportError:
    Correction = None  # type: ignore[assignment,misc]
    Feedback = None  # type: ignore[assignment,misc]
    Pattern = None  # type: ignore[assignment,misc]

logger = logging.getLogger(__name__)


class ShadowAgentSystem:
    """Complete shadow agent system integrating all components"""

    def __init__(
        self,
        model_registry_dir: str = "model_registry",
        checkpoint_dir: str = "checkpoints"
    ):
        # Core components
        self.model_registry = ModelRegistry(model_registry_dir)
        self.shadow_agent = ShadowAgent(self.model_registry)

        # Training components
        self.training_data_transformer = CorrectionToTrainingTransformer()
        self.feature_engineer = FeatureEngineer()
        self.training_data_validator = DataValidator()
        self.data_splitter = DataSplitter()

        # Model training
        self.training_pipeline = TrainingPipeline(
            TrainingConfig(checkpoint_dir=checkpoint_dir)
        )
        self.hyperparameter_tuner = HyperparameterTuner()

        # Evaluation and monitoring
        self.evaluator = ModelEvaluator()
        self.test_suite = AutomatedTestSuite()
        self.shadow_monitoring = MonitoringDashboard()
        self.feedback_loop = FeedbackLoop()

        # A/B testing and rollout
        self.ab_test: Optional[ABTestFramework] = None
        self.gradual_rollout = GradualRollout(initial_traffic=0.1)

        logger.info("Shadow Agent System initialized")

    def train_from_corrections(
        self,
        corrections: List[Correction],
        model_name: str = "shadow_agent",
        model_version: str = "1.0.0",
        tune_hyperparameters: bool = False
    ) -> UUID:
        """Train shadow agent from corrections"""

        logger.info(f"Training shadow agent from {len(corrections)} corrections")

        # Step 1: Transform corrections to training data
        logger.info("Step 1: Transforming corrections to training data...")
        dataset = self.training_data_transformer.transform_corrections(corrections)

        # Step 2: Feature engineering
        logger.info("Step 2: Applying feature engineering...")
        dataset = self.feature_engineer.fit_transform(dataset)

        # Step 3: Data validation
        logger.info("Step 3: Validating data quality...")
        quality_metrics = self.training_data_validator.validate_dataset(dataset)
        logger.info(f"Data quality score: {quality_metrics.overall_quality_score:.2f}")

        if quality_metrics.overall_quality_score < 0.5:
            logger.warning("Low data quality - training may not be effective")

        # Step 4: Split data
        logger.info("Step 4: Splitting data...")
        dataset = self.data_splitter.split_dataset(dataset, strategy="stratified")

        # Step 5: Hyperparameter tuning (optional)
        model_config = None
        if tune_hyperparameters:
            logger.info("Step 5: Tuning hyperparameters...")
            param_space = get_default_param_space(ModelType.HYBRID)
            tuning_result = self.hyperparameter_tuner.tune(
                ModelType.HYBRID,
                dataset,
                param_space
            )
            logger.info(f"Best parameters: {tuning_result.best_params}")
            # Would use best_params to create config

        # Step 6: Train model
        logger.info("Step 6: Training model...")
        model = ModelFactory.create_model(ModelType.HYBRID, model_config)
        trained_model = self.training_pipeline.train(model, dataset)

        # Step 7: Evaluate model
        logger.info("Step 7: Evaluating model...")
        eval_metrics = self.evaluator.evaluate(trained_model, dataset)
        logger.info(
            f"Evaluation: accuracy={eval_metrics.accuracy:.4f}, "
            f"f1={eval_metrics.f1_score:.4f}"
        )

        # Step 8: Run automated tests
        logger.info("Step 8: Running automated tests...")
        test_results = self.test_suite.run_all_tests(trained_model, dataset)

        if not test_results["overall_passed"]:
            logger.warning("Some tests failed - review before deployment")

        # Step 9: Register model
        logger.info("Step 9: Registering model...")
        model_version_obj = self.model_registry.register_model(
            trained_model,
            name=model_name,
            version=model_version,
            tags=["trained_from_corrections"]
        )

        logger.info(f"Training complete: model_id={model_version_obj.id}")

        return model_version_obj.id

    def deploy_model(
        self,
        model_id: UUID,
        environment: str = "production",
        use_ab_test: bool = False,
        use_gradual_rollout: bool = True
    ):
        """Deploy model to production"""

        logger.info(f"Deploying model {model_id} to {environment}")

        # Deploy to registry
        model_version = self.model_registry.deploy_model(model_id, environment)

        # Update shadow agent
        self.shadow_agent.update_model(model_version)

        # Setup A/B test if requested
        if use_ab_test:
            logger.info("Setting up A/B test...")
            ab_config = ABTestConfig(
                name=f"shadow_agent_vs_murphy_gate_{model_version.version}",
                variants={
                    VariantType.SHADOW_AGENT: 0.5,
                    VariantType.MURPHY_GATE: 0.5,
                },
                primary_metric="accuracy",
            )
            self.ab_test = ABTestFramework(ab_config)

        # Setup gradual rollout if requested
        if use_gradual_rollout:
            logger.info("Starting gradual rollout...")
            self.gradual_rollout = GradualRollout(initial_traffic=0.1)

        logger.info("Deployment complete")

    def make_prediction(
        self,
        input_features: Dict[str, Any],
        task_id: Optional[UUID] = None,
        use_fallback: bool = True
    ) -> Dict[str, Any]:
        """Make prediction using shadow agent"""

        # Check if should use shadow agent (gradual rollout)
        if not self.gradual_rollout.should_use_shadow_agent():
            return {
                "source": "murphy_gate",
                "prediction": None,
                "confidence": 0.0,
                "reason": "gradual_rollout"
            }

        # Make prediction
        prediction = self.shadow_agent.predict(
            input_features=input_features,
            task_id=task_id
        )

        # Check if confidence is sufficient
        if use_fallback and prediction.confidence < self.shadow_agent.config.fallback_threshold:
            return {
                "source": "murphy_gate_fallback",
                "prediction": prediction.prediction,
                "confidence": prediction.confidence,
                "reason": "low_confidence"
            }

        return {
            "source": "shadow_agent",
            "prediction": prediction.prediction,
            "confidence": prediction.confidence,
            "prediction_id": str(prediction.id)
        }

    def record_feedback(
        self,
        prediction_id: UUID,
        actual_outcome: Any,
        was_correct: bool,
        user_feedback: Optional[str] = None
    ):
        """Record feedback on a prediction"""

        self.feedback_loop.collect_feedback(
            prediction_id=prediction_id,
            actual_outcome=actual_outcome,
            was_correct=was_correct,
            user_feedback=user_feedback
        )

    def process_feedback_and_improve(self) -> Dict[str, Any]:
        """Process feedback and get improvement recommendations"""

        # Process feedback batch
        summary = self.feedback_loop.process_feedback_batch()

        # Get recommendations
        recommendations = self.feedback_loop.get_improvement_recommendations()

        # Auto-adjust rollout based on performance
        if summary.get("accuracy", 0) > 0.9:
            self.gradual_rollout.increase_traffic(0.1)
        elif summary.get("accuracy", 0) < 0.7:
            self.gradual_rollout.decrease_traffic(0.1)

        return {
            "summary": summary,
            "recommendations": recommendations,
            "rollout_status": self.gradual_rollout.get_rollout_status(),
        }

    def get_system_status(self) -> Dict[str, Any]:
        """Get complete system status"""

        return {
            "shadow_agent": {
                "model_loaded": self.shadow_agent.current_model is not None,
                "prediction_stats": self.shadow_agent.get_prediction_stats(),
            },
            "model_registry": self.model_registry.get_registry_summary(),
            "monitoring": self.shadow_monitoring.get_dashboard_data(),
            "rollout": self.gradual_rollout.get_rollout_status(),
            "ab_test": self.ab_test.get_summary().__dict__ if self.ab_test else None,
        }


# Convenience function for quick setup
def create_shadow_agent_system(
    model_registry_dir: str = "model_registry",
    checkpoint_dir: str = "checkpoints"
) -> ShadowAgentSystem:
    """Create and initialize shadow agent system"""

    return ShadowAgentSystem(
        model_registry_dir=model_registry_dir,
        checkpoint_dir=checkpoint_dir
    )
