"""
Shadow Agent Training Module

This module implements the shadow agent training system that learns from human corrections.
"""

from .models import (
    Feature,
    FeatureType,
    Label,
    LabelType,
    TrainingExample,
    TrainingDataset,
    FeatureEngineering,
    DataQualityMetrics,
    DataSplitConfig,
    DataSplitType,
)

from .data_transformer import (
    CorrectionToTrainingTransformer,
    FeedbackToTrainingTransformer,
    PatternToTrainingTransformer,
)

from .feature_engineering import FeatureEngineer

from .data_validator import DataValidator, DataSplitter

from .model_architecture import (
    ModelType,
    ShadowAgentModel,
    DecisionTreeModel,
    RandomForestModel,
    HybridModel,
    ModelMetadata,
)

from .training_pipeline import (
    TrainingPipeline,
    TrainingConfig,
    ModelFactory,
)

from .hyperparameter_tuning import (
    HyperparameterTuner,
    TuningConfig,
    get_default_param_space,
)

from .model_registry import ModelRegistry, ModelVersion

from .shadow_agent import ShadowAgent, ShadowAgentConfig, ShadowPrediction

from .ab_testing import (
    ABTestFramework,
    ABTestConfig,
    GradualRollout,
    VariantType,
)

from .evaluation import (
    ModelEvaluator,
    AutomatedTestSuite,
    EvaluationMetrics,
)

from .monitoring import (
    MonitoringDashboard,
    MonitoringConfig,
    FeedbackLoop,
    PerformanceMetrics,
)

from .integration import ShadowAgentSystem, create_shadow_agent_system

__all__ = [
    # Data models
    "Feature",
    "FeatureType",
    "Label",
    "LabelType",
    "TrainingExample",
    "TrainingDataset",
    "FeatureEngineering",
    "DataQualityMetrics",
    "DataSplitConfig",
    "DataSplitType",
    
    # Data transformation
    "CorrectionToTrainingTransformer",
    "FeedbackToTrainingTransformer",
    "PatternToTrainingTransformer",
    "FeatureEngineer",
    "DataValidator",
    "DataSplitter",
    
    # Model architecture
    "ModelType",
    "ShadowAgentModel",
    "DecisionTreeModel",
    "RandomForestModel",
    "HybridModel",
    "ModelMetadata",
    
    # Training
    "TrainingPipeline",
    "TrainingConfig",
    "ModelFactory",
    "HyperparameterTuner",
    "TuningConfig",
    "get_default_param_space",
    
    # Model management
    "ModelRegistry",
    "ModelVersion",
    
    # Shadow agent
    "ShadowAgent",
    "ShadowAgentConfig",
    "ShadowPrediction",
    
    # A/B testing
    "ABTestFramework",
    "ABTestConfig",
    "GradualRollout",
    "VariantType",
    
    # Evaluation
    "ModelEvaluator",
    "AutomatedTestSuite",
    "EvaluationMetrics",
    
    # Monitoring
    "MonitoringDashboard",
    "MonitoringConfig",
    "FeedbackLoop",
    "PerformanceMetrics",
    
    # Integration
    "ShadowAgentSystem",
    "create_shadow_agent_system",
]