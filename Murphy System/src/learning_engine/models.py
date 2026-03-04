"""
Learning Engine Models — Public Re-export

Re-exports all training-data model classes from shadow_models so that
``from .models import TrainingDataset`` works throughout the package.
"""

from .shadow_models import (  # noqa: F401
    DataQualityMetrics,
    DataSplitConfig,
    DataSplitType,
    Feature,
    FeatureEngineering,
    FeatureType,
    Label,
    LabelType,
    TrainingDataset,
    TrainingExample,
)
