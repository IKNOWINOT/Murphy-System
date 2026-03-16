"""
Shadow Agent Training Data Models

This module defines the data structures for training the shadow agent from human corrections.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)


class FeatureType(str, Enum):
    """Types of features extracted from corrections"""
    CATEGORICAL = "categorical"
    NUMERICAL = "numerical"
    TEXT = "text"
    TEMPORAL = "temporal"
    STRUCTURAL = "structural"


class LabelType(str, Enum):
    """Types of labels for training"""
    BINARY = "binary"  # approve/reject
    MULTICLASS = "multiclass"  # multiple categories
    REGRESSION = "regression"  # continuous values
    RANKING = "ranking"  # ordered preferences


class DataSplitType(str, Enum):
    """Types of data splits"""
    TRAIN = "train"
    VALIDATION = "validation"
    TEST = "test"


@dataclass
class Feature:
    """Individual feature extracted from correction data"""
    name: str
    type: FeatureType
    value: Any
    importance: float = 0.0
    source: str = ""  # Where this feature came from
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Label:
    """Training label derived from correction"""
    type: LabelType
    value: Any
    confidence: float = 1.0
    source: str = ""  # correction_id or pattern_id
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TrainingExample:
    """Single training example with features and label"""
    id: UUID = field(default_factory=uuid4)
    features: List[Feature] = field(default_factory=list)
    label: Label = None
    weight: float = 1.0  # Sample weight for training
    split: DataSplitType = DataSplitType.TRAIN
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Context information
    task_id: Optional[UUID] = None
    correction_id: Optional[UUID] = None
    pattern_id: Optional[UUID] = None

    # Quality metrics
    quality_score: float = 1.0
    is_validated: bool = False
    validation_notes: str = ""

    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FeatureEngineering:
    """Configuration for feature engineering"""
    # Text features
    use_tfidf: bool = True
    use_embeddings: bool = True
    max_vocab_size: int = 10000

    # Numerical features
    normalize: bool = True
    handle_outliers: bool = True
    outlier_method: str = "iqr"  # iqr, zscore, isolation_forest

    # Categorical features
    encoding_method: str = "onehot"  # onehot, label, target
    handle_unknown: str = "ignore"  # ignore, error, use_default

    # Temporal features
    extract_time_components: bool = True  # hour, day, month, etc.
    create_time_deltas: bool = True

    # Structural features
    extract_graph_features: bool = True
    extract_dependency_features: bool = True

    # Feature selection
    use_feature_selection: bool = True
    selection_method: str = "mutual_info"  # mutual_info, chi2, f_score
    max_features: Optional[int] = None

    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DataQualityMetrics:
    """Metrics for assessing training data quality"""
    total_examples: int = 0
    train_examples: int = 0
    validation_examples: int = 0
    test_examples: int = 0

    # Feature quality
    missing_features: int = 0
    invalid_features: int = 0
    feature_coverage: float = 0.0

    # Label quality
    missing_labels: int = 0
    ambiguous_labels: int = 0
    label_distribution: Dict[str, int] = field(default_factory=dict)

    # Balance metrics
    class_balance_ratio: float = 0.0
    is_balanced: bool = False

    # Validation metrics
    validated_examples: int = 0
    validation_rate: float = 0.0

    # Quality scores
    overall_quality_score: float = 0.0
    feature_quality_score: float = 0.0
    label_quality_score: float = 0.0

    # Issues detected
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DataSplitConfig:
    """Configuration for train/validation/test split"""
    train_ratio: float = 0.7
    validation_ratio: float = 0.15
    test_ratio: float = 0.15

    # Splitting strategy
    strategy: str = "random"  # random, stratified, temporal, grouped
    random_seed: int = 42

    # Stratification (for stratified split)
    stratify_by: Optional[str] = None  # feature name to stratify by

    # Temporal split (for temporal strategy)
    temporal_field: Optional[str] = None

    # Grouped split (for grouped strategy)
    group_field: Optional[str] = None

    # Validation
    ensure_minimum_samples: bool = True
    minimum_train_samples: int = 100
    minimum_validation_samples: int = 20
    minimum_test_samples: int = 20

    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TrainingDataset:
    """Complete training dataset with all splits"""
    id: UUID = field(default_factory=uuid4)
    name: str = ""
    description: str = ""

    # Examples
    examples: List[TrainingExample] = field(default_factory=list)

    # Configuration
    feature_config: FeatureEngineering = field(default_factory=FeatureEngineering)
    split_config: DataSplitConfig = field(default_factory=DataSplitConfig)

    # Quality metrics
    quality_metrics: DataQualityMetrics = field(default_factory=DataQualityMetrics)

    # Metadata
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    version: str = "1.0.0"

    # Source information
    source_corrections: List[UUID] = field(default_factory=list)
    source_patterns: List[UUID] = field(default_factory=list)

    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_train_examples(self) -> List[TrainingExample]:
        """Get training examples"""
        return [ex for ex in self.examples if ex.split == DataSplitType.TRAIN]

    def get_validation_examples(self) -> List[TrainingExample]:
        """Get validation examples"""
        return [ex for ex in self.examples if ex.split == DataSplitType.VALIDATION]

    def get_test_examples(self) -> List[TrainingExample]:
        """Get test examples"""
        return [ex for ex in self.examples if ex.split == DataSplitType.TEST]

    def get_feature_names(self) -> List[str]:
        """Get all unique feature names"""
        if not self.examples:
            return []
        return list(set(f.name for ex in self.examples for f in ex.features))

    def get_label_distribution(self) -> Dict[str, int]:
        """Get distribution of labels"""
        distribution = {}
        for example in self.examples:
            if example.label:
                label_str = str(example.label.value)
                distribution[label_str] = distribution.get(label_str, 0) + 1
        return distribution
