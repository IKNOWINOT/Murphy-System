"""
Feature Engineering Pipeline

This module implements advanced feature engineering for training data.
"""

import logging
from collections import Counter
from typing import Any, Dict, List, Optional, Set

import numpy as np

from .models import (
    Feature,
    FeatureType,
    TrainingDataset,
    TrainingExample,
)
from .models import (
    FeatureEngineering as FeatureConfig,
)

logger = logging.getLogger(__name__)


class FeatureEngineer:
    """Handles feature engineering and transformation"""

    def __init__(self, config: Optional[FeatureConfig] = None):
        self.config = config or FeatureConfig()
        self.feature_stats = {}
        self.vocabulary = {}
        self.encoders = {}

    def fit_transform(self, dataset: TrainingDataset) -> TrainingDataset:
        """Fit feature engineering pipeline and transform dataset"""

        # Learn feature statistics
        self._fit(dataset)

        # Transform features
        transformed_dataset = self._transform(dataset)

        return transformed_dataset

    def transform(self, dataset: TrainingDataset) -> TrainingDataset:
        """Transform dataset using fitted pipeline"""
        return self._transform(dataset)

    def _fit(self, dataset: TrainingDataset):
        """Learn feature statistics from dataset"""

        logger.info("Fitting feature engineering pipeline...")

        # Collect all features by name and type
        features_by_name = {}
        for example in dataset.examples:
            for feature in example.features:
                if feature.name not in features_by_name:
                    features_by_name[feature.name] = []
                features_by_name[feature.name].append(feature)

        # Calculate statistics for each feature
        for feature_name, features in features_by_name.items():
            feature_type = features[0].type
            values = [f.value for f in features]

            if feature_type == FeatureType.NUMERICAL:
                self._fit_numerical_feature(feature_name, values)
            elif feature_type == FeatureType.CATEGORICAL:
                self._fit_categorical_feature(feature_name, values)
            elif feature_type == FeatureType.TEXT:
                self._fit_text_feature(feature_name, values)

        logger.info(f"Fitted {len(self.feature_stats)} features")

    def _fit_numerical_feature(self, name: str, values: List[Any]):
        """Fit numerical feature statistics"""

        # Convert to numpy array
        numeric_values = []
        for v in values:
            try:
                numeric_values.append(float(v))
            except (ValueError, TypeError):
                continue

        if not numeric_values:
            return

        arr = np.array(numeric_values)

        stats = {
            "type": "numerical",
            "mean": float(np.mean(arr)),
            "std": float(np.std(arr)),
            "min": float(np.min(arr)),
            "max": float(np.max(arr)),
            "median": float(np.median(arr)),
            "q25": float(np.percentile(arr, 25)),
            "q75": float(np.percentile(arr, 75)),
        }

        # Outlier detection using IQR
        if self.config.handle_outliers:
            iqr = stats["q75"] - stats["q25"]
            stats["outlier_lower"] = stats["q25"] - 1.5 * iqr
            stats["outlier_upper"] = stats["q75"] + 1.5 * iqr

        self.feature_stats[name] = stats

    def _fit_categorical_feature(self, name: str, values: List[Any]):
        """Fit categorical feature statistics"""

        # Count unique values
        value_counts = Counter(str(v) for v in values)

        stats = {
            "type": "categorical",
            "unique_values": len(value_counts),
            "value_counts": dict(value_counts),
            "most_common": value_counts.most_common(10),
        }

        # Create encoding
        if self.config.encoding_method == "onehot":
            unique_values = list(value_counts.keys())
            self.encoders[name] = {
                "type": "onehot",
                "values": unique_values,
                "mapping": {v: i for i, v in enumerate(unique_values)}
            }
        elif self.config.encoding_method == "label":
            unique_values = list(value_counts.keys())
            self.encoders[name] = {
                "type": "label",
                "mapping": {v: i for i, v in enumerate(unique_values)}
            }

        self.feature_stats[name] = stats

    def _fit_text_feature(self, name: str, values: List[Any]):
        """Fit text feature statistics"""

        # Build vocabulary
        if self.config.use_tfidf:
            word_counts = Counter()
            for text in values:
                words = str(text).lower().split()
                word_counts.update(words)

            # Keep top N words
            vocab = [word for word, _ in word_counts.most_common(self.config.max_vocab_size)]
            self.vocabulary[name] = {
                "words": vocab,
                "mapping": {word: i for i, word in enumerate(vocab)}
            }

        stats = {
            "type": "text",
            "vocab_size": len(self.vocabulary.get(name, {}).get("words", [])),
            "avg_length": np.mean([len(str(v)) for v in values]),
        }

        self.feature_stats[name] = stats

    def _transform(self, dataset: TrainingDataset) -> TrainingDataset:
        """Transform features in dataset"""

        logger.info("Transforming features...")

        transformed_examples = []

        for example in dataset.examples:
            transformed_features = []

            for feature in example.features:
                # Transform based on feature type
                if feature.type == FeatureType.NUMERICAL:
                    transformed = self._transform_numerical_feature(feature)
                elif feature.type == FeatureType.CATEGORICAL:
                    transformed = self._transform_categorical_feature(feature)
                elif feature.type == FeatureType.TEXT:
                    transformed = self._transform_text_feature(feature)
                else:
                    transformed = [feature]

                transformed_features.extend(transformed)

            # Create new example with transformed features
            new_example = TrainingExample(
                id=example.id,
                features=transformed_features,
                label=example.label,
                weight=example.weight,
                split=example.split,
                task_id=example.task_id,
                correction_id=example.correction_id,
                pattern_id=example.pattern_id,
                quality_score=example.quality_score,
                is_validated=example.is_validated,
                metadata=example.metadata,
            )

            transformed_examples.append(new_example)

        # Create new dataset
        transformed_dataset = TrainingDataset(
            id=dataset.id,
            name=dataset.name,
            description=dataset.description,
            examples=transformed_examples,
            feature_config=dataset.feature_config,
            split_config=dataset.split_config,
            quality_metrics=dataset.quality_metrics,
            source_corrections=dataset.source_corrections,
            source_patterns=dataset.source_patterns,
            metadata=dataset.metadata,
        )

        logger.info(f"Transformed {len(transformed_examples)} examples")

        return transformed_dataset

    def _transform_numerical_feature(self, feature: Feature) -> List[Feature]:
        """Transform numerical feature"""

        stats = self.feature_stats.get(feature.name, {})
        if not stats:
            return [feature]

        value = float(feature.value)

        # Handle outliers
        if self.config.handle_outliers and "outlier_lower" in stats:
            if value < stats["outlier_lower"]:
                value = stats["outlier_lower"]
            elif value > stats["outlier_upper"]:
                value = stats["outlier_upper"]

        # Normalize
        if self.config.normalize:
            if stats["std"] > 0:
                value = (value - stats["mean"]) / stats["std"]
            else:
                value = 0.0

        return [Feature(
            name=feature.name,
            type=FeatureType.NUMERICAL,
            value=value,
            importance=feature.importance,
            source=feature.source,
            metadata=feature.metadata,
        )]

    def _transform_categorical_feature(self, feature: Feature) -> List[Feature]:
        """Transform categorical feature"""

        encoder = self.encoders.get(feature.name)
        if not encoder:
            return [feature]

        value_str = str(feature.value)

        if encoder["type"] == "onehot":
            # Create one-hot encoded features
            features = []
            for encoded_value in encoder["values"]:
                features.append(Feature(
                    name=f"{feature.name}_{encoded_value}",
                    type=FeatureType.NUMERICAL,
                    value=1.0 if value_str == encoded_value else 0.0,
                    source=feature.source,
                ))
            return features

        elif encoder["type"] == "label":
            # Label encoding
            encoded_value = encoder["mapping"].get(value_str, -1)
            if encoded_value == -1 and self.config.handle_unknown == "use_default":
                encoded_value = 0

            return [Feature(
                name=feature.name,
                type=FeatureType.NUMERICAL,
                value=float(encoded_value),
                source=feature.source,
            )]

        return [feature]

    def _transform_text_feature(self, feature: Feature) -> List[Feature]:
        """Transform text feature"""

        vocab = self.vocabulary.get(feature.name)
        if not vocab or not self.config.use_tfidf:
            return [feature]

        text = str(feature.value).lower()
        words = text.split()

        # Create TF-IDF features
        features = []
        word_counts = Counter(words)

        for word in vocab["words"]:
            tf = word_counts.get(word, 0) / (len(words) or 1) if words else 0
            features.append(Feature(
                name=f"{feature.name}_tfidf_{word}",
                type=FeatureType.NUMERICAL,
                value=tf,
                source=feature.source,
            ))

        return features

    def get_feature_importance(self, feature_name: str) -> float:
        """Get importance score for a feature"""

        stats = self.feature_stats.get(feature_name, {})

        # Simple heuristic: features with more variance are more important
        if stats.get("type") == "numerical":
            std = stats.get("std", 0)
            return min(std / (stats.get("mean", 1) + 1e-6), 1.0)

        elif stats.get("type") == "categorical":
            # Features with more unique values might be more important
            unique = stats.get("unique_values", 1)
            return min(unique / 100, 1.0)

        return 0.5  # Default importance
