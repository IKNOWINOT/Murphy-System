"""
Training Data Validation and Quality Checks

This module validates training data quality and detects issues.
"""

import logging
from collections import Counter
from typing import Any, Dict, List, Tuple

from .models import (
    DataQualityMetrics,
    FeatureType,
    TrainingDataset,
    TrainingExample,
)

logger = logging.getLogger(__name__)


class DataValidator:
    """Validates training data quality"""

    def __init__(self, min_examples: int = 100):
        self.min_examples = min_examples

    def validate_dataset(self, dataset: TrainingDataset) -> DataQualityMetrics:
        """Validate entire dataset and return quality metrics"""

        logger.info(f"Validating dataset: {dataset.name}")

        metrics = DataQualityMetrics()

        # Basic counts
        metrics.total_examples = len(dataset.examples)
        metrics.train_examples = len(dataset.get_train_examples())
        metrics.validation_examples = len(dataset.get_validation_examples())
        metrics.test_examples = len(dataset.get_test_examples())

        # Check minimum examples
        if metrics.total_examples < self.min_examples:
            metrics.issues.append(
                f"Insufficient examples: {metrics.total_examples} < {self.min_examples}"
            )

        # Validate features
        feature_metrics = self._validate_features(dataset)
        metrics.missing_features = feature_metrics["missing"]
        metrics.invalid_features = feature_metrics["invalid"]
        metrics.feature_coverage = feature_metrics["coverage"]

        # Validate labels
        label_metrics = self._validate_labels(dataset)
        metrics.missing_labels = label_metrics["missing"]
        metrics.ambiguous_labels = label_metrics["ambiguous"]
        metrics.label_distribution = label_metrics["distribution"]

        # Check class balance
        balance_metrics = self._check_class_balance(dataset)
        metrics.class_balance_ratio = balance_metrics["ratio"]
        metrics.is_balanced = balance_metrics["is_balanced"]

        if not balance_metrics["is_balanced"]:
            metrics.warnings.append(
                f"Class imbalance detected: ratio = {balance_metrics['ratio']:.2f}"
            )

        # Validation rate
        metrics.validated_examples = sum(
            1 for ex in dataset.examples if ex.is_validated
        )
        metrics.validation_rate = (
            metrics.validated_examples / metrics.total_examples
            if metrics.total_examples > 0 else 0
        )

        # Calculate quality scores
        metrics.feature_quality_score = self._calculate_feature_quality(feature_metrics)
        metrics.label_quality_score = self._calculate_label_quality(label_metrics)
        metrics.overall_quality_score = (
            0.4 * metrics.feature_quality_score +
            0.4 * metrics.label_quality_score +
            0.2 * metrics.validation_rate
        )

        # Final assessment
        if metrics.overall_quality_score < 0.5:
            metrics.issues.append(
                f"Low overall quality: {metrics.overall_quality_score:.2f}"
            )
        elif metrics.overall_quality_score < 0.7:
            metrics.warnings.append(
                f"Moderate quality: {metrics.overall_quality_score:.2f}"
            )

        logger.info(
            f"Validation complete: {len(metrics.issues)} issues, "
            f"{len(metrics.warnings)} warnings"
        )

        return metrics

    def _validate_features(self, dataset: TrainingDataset) -> Dict[str, Any]:
        """Validate features in dataset"""

        missing_count = 0
        invalid_count = 0
        total_features = 0
        feature_presence = Counter()

        expected_features = set(dataset.get_feature_names())

        for example in dataset.examples:
            example_features = {f.name for f in example.features}
            total_features += len(example.features)

            # Check for missing features
            missing = expected_features - example_features
            missing_count += len(missing)

            # Track feature presence
            for feature_name in example_features:
                feature_presence[feature_name] += 1

            # Check for invalid values
            for feature in example.features:
                if not self._is_valid_feature_value(feature):
                    invalid_count += 1

        # Calculate coverage
        if expected_features:
            avg_presence = sum(feature_presence.values()) / (len(expected_features) or 1)
            coverage = avg_presence / (len(dataset.examples) or 1) if dataset.examples else 0
        else:
            coverage = 0

        return {
            "missing": missing_count,
            "invalid": invalid_count,
            "coverage": coverage,
            "total": total_features,
        }

    def _validate_labels(self, dataset: TrainingDataset) -> Dict[str, Any]:
        """Validate labels in dataset"""

        missing_count = 0
        ambiguous_count = 0
        label_values = []

        for example in dataset.examples:
            if example.label is None:
                missing_count += 1
            else:
                label_values.append(str(example.label.value))

                # Check for ambiguous labels (low confidence)
                if example.label.confidence < 0.5:
                    ambiguous_count += 1

        # Label distribution
        distribution = dict(Counter(label_values))

        return {
            "missing": missing_count,
            "ambiguous": ambiguous_count,
            "distribution": distribution,
        }

    def _check_class_balance(self, dataset: TrainingDataset) -> Dict[str, Any]:
        """Check if classes are balanced"""

        label_counts = Counter()

        for example in dataset.examples:
            if example.label:
                label_counts[str(example.label.value)] += 1

        if not label_counts:
            return {"ratio": 0.0, "is_balanced": False}

        # Calculate balance ratio (min/max)
        counts = list(label_counts.values())
        if not counts:
            return {"ratio": 0.0, "is_balanced": False}

        min_count = min(counts)
        max_count = max(counts)
        ratio = min_count / max_count if max_count > 0 else 0

        # Consider balanced if ratio > 0.5
        is_balanced = ratio > 0.5

        return {
            "ratio": ratio,
            "is_balanced": is_balanced,
            "counts": dict(label_counts),
        }

    def _is_valid_feature_value(self, feature) -> bool:
        """Check if feature value is valid"""

        if feature.value is None:
            return False

        if feature.type == FeatureType.NUMERICAL:
            try:
                float(feature.value)
                return True
            except (ValueError, TypeError):
                return False

        return True

    def _calculate_feature_quality(self, metrics: Dict[str, Any]) -> float:
        """Calculate feature quality score"""

        if metrics["total"] == 0:
            return 0.0

        # Penalize missing and invalid features
        valid_ratio = 1.0 - (
            (metrics["missing"] + metrics["invalid"]) / metrics["total"]
        )

        # Combine with coverage
        quality = 0.6 * valid_ratio + 0.4 * metrics["coverage"]

        return max(0.0, min(1.0, quality))

    def _calculate_label_quality(self, metrics: Dict[str, Any]) -> float:
        """Calculate label quality score"""

        total = sum(metrics["distribution"].values()) + metrics["missing"]
        if total == 0:
            return 0.0

        # Penalize missing and ambiguous labels
        valid_ratio = 1.0 - (
            (metrics["missing"] + metrics["ambiguous"]) / total
        )

        return max(0.0, min(1.0, valid_ratio))

    def suggest_improvements(self, metrics: DataQualityMetrics) -> List[str]:
        """Suggest improvements based on quality metrics"""

        suggestions = []

        # Feature suggestions
        if metrics.missing_features > 0:
            suggestions.append(
                f"Fill {metrics.missing_features} missing features using imputation"
            )

        if metrics.feature_coverage < 0.8:
            suggestions.append(
                f"Improve feature coverage from {metrics.feature_coverage:.2%} to >80%"
            )

        # Label suggestions
        if metrics.missing_labels > 0:
            suggestions.append(
                f"Label {metrics.missing_labels} unlabeled examples"
            )

        if metrics.ambiguous_labels > 0:
            suggestions.append(
                f"Review {metrics.ambiguous_labels} ambiguous labels"
            )

        # Balance suggestions
        if not metrics.is_balanced:
            suggestions.append(
                f"Address class imbalance (ratio: {metrics.class_balance_ratio:.2f})"
            )
            suggestions.append(
                "Consider: oversampling minority class, undersampling majority class, "
                "or using class weights"
            )

        # Validation suggestions
        if metrics.validation_rate < 0.5:
            suggestions.append(
                f"Increase validation rate from {metrics.validation_rate:.2%} to >50%"
            )

        # Size suggestions
        if metrics.total_examples < 1000:
            suggestions.append(
                f"Collect more examples (current: {metrics.total_examples}, "
                "recommended: >1000)"
            )

        return suggestions


class DataSplitter:
    """Splits data into train/validation/test sets"""

    def __init__(self, train_ratio: float = 0.7, val_ratio: float = 0.15):
        self.train_ratio = train_ratio
        self.val_ratio = val_ratio
        self.test_ratio = 1.0 - train_ratio - val_ratio

    def split_dataset(
        self,
        dataset: TrainingDataset,
        strategy: str = "random",
        random_seed: int = 42
    ) -> TrainingDataset:
        """Split dataset into train/val/test"""

        logger.info(f"Splitting dataset using {strategy} strategy")

        if strategy == "random":
            return self._random_split(dataset, random_seed)
        elif strategy == "stratified":
            return self._stratified_split(dataset, random_seed)
        elif strategy == "temporal":
            return self._temporal_split(dataset)
        else:
            raise ValueError(f"Unknown split strategy: {strategy}")

    def _random_split(
        self,
        dataset: TrainingDataset,
        random_seed: int
    ) -> TrainingDataset:
        """Random split"""

        import random
        random.seed(random_seed)

        examples = dataset.examples.copy()
        random.shuffle(examples)

        n = len(examples)
        train_end = int(n * self.train_ratio)
        val_end = train_end + int(n * self.val_ratio)

        # Assign splits
        for i, example in enumerate(examples):
            if i < train_end:
                example.split = "train"
            elif i < val_end:
                example.split = "validation"
            else:
                example.split = "test"

        dataset.examples = examples
        return dataset

    def _stratified_split(
        self,
        dataset: TrainingDataset,
        random_seed: int
    ) -> TrainingDataset:
        """Stratified split (maintains label distribution)"""

        import random
        random.seed(random_seed)

        # Group by label
        label_groups = {}
        for example in dataset.examples:
            if example.label:
                label_str = str(example.label.value)
                if label_str not in label_groups:
                    label_groups[label_str] = []
                label_groups[label_str].append(example)

        # Split each group
        all_examples = []
        for label, examples in label_groups.items():
            random.shuffle(examples)

            n = len(examples)
            train_end = int(n * self.train_ratio)
            val_end = train_end + int(n * self.val_ratio)

            for i, example in enumerate(examples):
                if i < train_end:
                    example.split = "train"
                elif i < val_end:
                    example.split = "validation"
                else:
                    example.split = "test"

            all_examples.extend(examples)

        dataset.examples = all_examples
        return dataset

    def _temporal_split(self, dataset: TrainingDataset) -> TrainingDataset:
        """Temporal split (chronological order)"""

        # Sort by creation time
        examples = sorted(dataset.examples, key=lambda x: x.created_at)

        n = len(examples)
        train_end = int(n * self.train_ratio)
        val_end = train_end + int(n * self.val_ratio)

        for i, example in enumerate(examples):
            if i < train_end:
                example.split = "train"
            elif i < val_end:
                example.split = "validation"
            else:
                example.split = "test"

        dataset.examples = examples
        return dataset
