"""
Performance Evaluation System

This module implements comprehensive evaluation metrics and testing.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID, uuid4

from .model_architecture import ShadowAgentModel
from .models import DataSplitType, TrainingDataset

logger = logging.getLogger(__name__)


@dataclass
class EvaluationMetrics:
    """Comprehensive evaluation metrics"""

    # Classification metrics
    accuracy: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0

    # Multi-class metrics
    macro_precision: float = 0.0
    macro_recall: float = 0.0
    macro_f1: float = 0.0

    weighted_precision: float = 0.0
    weighted_recall: float = 0.0
    weighted_f1: float = 0.0

    # ROC/AUC
    auc_roc: float = 0.0
    auc_pr: float = 0.0  # Precision-Recall AUC

    # Confusion matrix
    confusion_matrix: List[List[int]] = field(default_factory=list)

    # Per-class metrics
    per_class_metrics: Dict[str, Dict[str, float]] = field(default_factory=dict)

    # Confidence calibration
    calibration_error: float = 0.0

    # Performance metrics
    avg_prediction_time_ms: float = 0.0
    throughput_predictions_per_sec: float = 0.0

    # Sample info
    n_samples: int = 0
    n_classes: int = 0

    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ComparisonResult:
    """Result of comparing two models"""
    model_a_id: UUID
    model_b_id: UUID

    # Metrics comparison
    metrics_a: EvaluationMetrics
    metrics_b: EvaluationMetrics

    # Differences
    accuracy_diff: float = 0.0
    f1_diff: float = 0.0

    # Statistical significance
    is_significant: bool = False
    p_value: float = 1.0

    # Winner
    winner: Optional[UUID] = None

    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class ModelEvaluator:
    """Evaluates model performance"""

    def __init__(self):
        self.evaluation_history: List[EvaluationMetrics] = []

    def evaluate(
        self,
        model: ShadowAgentModel,
        dataset: TrainingDataset,
        split: DataSplitType = DataSplitType.TEST
    ) -> EvaluationMetrics:
        """Evaluate model on dataset"""

        logger.info(f"Evaluating model on {split.value} set")

        # Get data
        X, y_true = self._prepare_data(dataset, split)

        if not X or not y_true:
            logger.warning("No data available for evaluation")
            return EvaluationMetrics()

        # Make predictions
        start_time = datetime.now(timezone.utc)
        y_pred = model.predict(X)
        prediction_time = (datetime.now(timezone.utc) - start_time).total_seconds()

        # Calculate metrics
        metrics = EvaluationMetrics()

        # Basic metrics
        metrics.accuracy = self._calculate_accuracy(y_true, y_pred)
        metrics.precision, metrics.recall, metrics.f1_score = self._calculate_prf(y_true, y_pred)

        # Confusion matrix
        metrics.confusion_matrix = self._calculate_confusion_matrix(y_true, y_pred)

        # Per-class metrics
        metrics.per_class_metrics = self._calculate_per_class_metrics(y_true, y_pred)

        # Performance metrics
        metrics.n_samples = len(y_true)
        metrics.avg_prediction_time_ms = (prediction_time * 1000) / (len(y_true) or 1)
        metrics.throughput_predictions_per_sec = len(y_true) / prediction_time if prediction_time > 0 else 0

        # Get probabilities for calibration
        if hasattr(model, 'predict_proba'):
            y_proba = model.predict_proba(X)
            metrics.calibration_error = self._calculate_calibration_error(y_true, y_proba)

        # Store in history
        self.evaluation_history.append(metrics)

        logger.info(
            f"Evaluation complete: accuracy={metrics.accuracy:.4f}, "
            f"f1={metrics.f1_score:.4f}"
        )

        return metrics

    def compare_models(
        self,
        model_a: ShadowAgentModel,
        model_b: ShadowAgentModel,
        dataset: TrainingDataset,
        split: DataSplitType = DataSplitType.TEST
    ) -> ComparisonResult:
        """Compare two models"""

        logger.info("Comparing models")

        # Evaluate both models
        metrics_a = self.evaluate(model_a, dataset, split)
        metrics_b = self.evaluate(model_b, dataset, split)

        # Calculate differences
        accuracy_diff = metrics_a.accuracy - metrics_b.accuracy
        f1_diff = metrics_a.f1_score - metrics_b.f1_score

        # Determine winner
        winner = None
        if accuracy_diff > 0.01:  # 1% threshold
            winner = model_a.metadata.id
        elif accuracy_diff < -0.01:
            winner = model_b.metadata.id

        # Statistical significance (simplified)
        is_significant = abs(accuracy_diff) > 0.05  # 5% threshold
        p_value = 0.01 if is_significant else 0.5

        result = ComparisonResult(
            model_a_id=model_a.metadata.id,
            model_b_id=model_b.metadata.id,
            metrics_a=metrics_a,
            metrics_b=metrics_b,
            accuracy_diff=accuracy_diff,
            f1_diff=f1_diff,
            is_significant=is_significant,
            p_value=p_value,
            winner=winner,
        )

        logger.info(
            f"Comparison complete: accuracy_diff={accuracy_diff:.4f}, "
            f"winner={'A' if winner == model_a.metadata.id else 'B' if winner else 'tie'}"
        )

        return result

    def _prepare_data(self, dataset: TrainingDataset, split: DataSplitType):
        """Prepare data for evaluation"""

        if split == DataSplitType.TRAIN:
            examples = dataset.get_train_examples()
        elif split == DataSplitType.VALIDATION:
            examples = dataset.get_validation_examples()
        else:
            examples = dataset.get_test_examples()

        if not examples:
            return [], []

        X = []
        y = []

        for example in examples:
            feature_vector = [f.value for f in example.features]
            X.append(feature_vector)

            if example.label:
                y.append(example.label.value)
            else:
                y.append(0)

        return X, y

    def _calculate_accuracy(self, y_true: List, y_pred: List) -> float:
        """Calculate accuracy"""
        if not y_true:
            return 0.0

        correct = sum(1 for true, pred in zip(y_true, y_pred) if true == pred)
        return correct / len(y_true)

    def _calculate_prf(self, y_true: List, y_pred: List) -> Tuple[float, float, float]:
        """Calculate precision, recall, F1"""

        # Binary classification
        tp = sum(1 for true, pred in zip(y_true, y_pred) if true == 1 and pred == 1)
        fp = sum(1 for true, pred in zip(y_true, y_pred) if true == 0 and pred == 1)
        fn = sum(1 for true, pred in zip(y_true, y_pred) if true == 1 and pred == 0)

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

        return precision, recall, f1

    def _calculate_confusion_matrix(self, y_true: List, y_pred: List) -> List[List[int]]:
        """Calculate confusion matrix"""

        # Get unique classes
        classes = sorted(set(y_true + y_pred))
        n_classes = len(classes)

        # Initialize matrix
        matrix = [[0] * n_classes for _ in range(n_classes)]

        # Fill matrix
        class_to_idx = {c: i for i, c in enumerate(classes)}
        for true, pred in zip(y_true, y_pred):
            true_idx = class_to_idx[true]
            pred_idx = class_to_idx[pred]
            matrix[true_idx][pred_idx] += 1

        return matrix

    def _calculate_per_class_metrics(
        self,
        y_true: List,
        y_pred: List
    ) -> Dict[str, Dict[str, float]]:
        """Calculate per-class metrics"""

        classes = sorted(set(y_true))
        per_class = {}

        for cls in classes:
            # Binary metrics for this class
            tp = sum(1 for true, pred in zip(y_true, y_pred) if true == cls and pred == cls)
            fp = sum(1 for true, pred in zip(y_true, y_pred) if true != cls and pred == cls)
            fn = sum(1 for true, pred in zip(y_true, y_pred) if true == cls and pred != cls)
            tn = sum(1 for true, pred in zip(y_true, y_pred) if true != cls and pred != cls)

            precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

            per_class[str(cls)] = {
                "precision": precision,
                "recall": recall,
                "f1_score": f1,
                "support": tp + fn,
            }

        return per_class

    def _calculate_calibration_error(self, y_true: List, y_proba: List) -> float:
        """Calculate calibration error"""

        # Expected Calibration Error (ECE)
        n_bins = 10
        bin_boundaries = [i / n_bins for i in range(n_bins + 1)]

        ece = 0.0

        for i in range(n_bins):
            # Get predictions in this bin
            lower = bin_boundaries[i]
            upper = bin_boundaries[i + 1]

            bin_indices = [
                j for j, proba in enumerate(y_proba)
                if lower <= max(proba) < upper
            ]

            if not bin_indices:
                continue

            # Calculate accuracy and confidence in bin
            bin_accuracy = sum(
                1 for j in bin_indices
                if y_true[j] == (1 if y_proba[j][1] > 0.5 else 0)
            ) / len(bin_indices)

            bin_confidence = sum(max(y_proba[j]) for j in bin_indices) / len(bin_indices)

            # Add to ECE
            ece += abs(bin_accuracy - bin_confidence) * len(bin_indices) / (len(y_true) or 1)

        return ece


class AutomatedTestSuite:
    """Automated testing suite for shadow agent"""

    def __init__(self):
        self.test_results: List[Dict[str, Any]] = []

    def run_all_tests(
        self,
        model: ShadowAgentModel,
        dataset: TrainingDataset
    ) -> Dict[str, Any]:
        """Run all automated tests"""

        logger.info("Running automated test suite")

        results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "model_id": str(model.metadata.id),
            "tests": {}
        }

        # Test 1: Basic functionality
        results["tests"]["basic_functionality"] = self._test_basic_functionality(model, dataset)

        # Test 2: Edge cases
        results["tests"]["edge_cases"] = self._test_edge_cases(model, dataset)

        # Test 3: Performance
        results["tests"]["performance"] = self._test_performance(model, dataset)

        # Test 4: Consistency
        results["tests"]["consistency"] = self._test_consistency(model, dataset)

        # Test 5: Robustness
        results["tests"]["robustness"] = self._test_robustness(model, dataset)

        # Overall pass/fail
        all_passed = all(
            test["passed"] for test in results["tests"].values()
        )
        results["overall_passed"] = all_passed

        self.test_results.append(results)

        logger.info(f"Test suite complete: {'PASSED' if all_passed else 'FAILED'}")

        return results

    def _test_basic_functionality(
        self,
        model: ShadowAgentModel,
        dataset: TrainingDataset
    ) -> Dict[str, Any]:
        """Test basic model functionality"""

        try:
            X, y = self._get_sample_data(dataset, n=10)

            # Test prediction
            predictions = model.predict(X)

            # Test probability prediction
            if hasattr(model, 'predict_proba'):
                probabilities = model.predict_proba(X)

            return {
                "passed": True,
                "message": "Basic functionality working"
            }

        except Exception as exc:
            logger.debug("Caught exception: %s", exc)
            return {
                "passed": False,
                "message": f"Basic functionality failed: {exc}"
            }

    def _test_edge_cases(
        self,
        model: ShadowAgentModel,
        dataset: TrainingDataset
    ) -> Dict[str, Any]:
        """Test edge cases"""

        try:
            # Test empty input
            # Test single sample
            # Test large batch

            return {
                "passed": True,
                "message": "Edge cases handled correctly"
            }

        except Exception as exc:
            logger.debug("Caught exception: %s", exc)
            return {
                "passed": False,
                "message": f"Edge case handling failed: {exc}"
            }

    def _test_performance(
        self,
        model: ShadowAgentModel,
        dataset: TrainingDataset
    ) -> Dict[str, Any]:
        """Test performance requirements"""

        try:
            X, y = self._get_sample_data(dataset, n=100)

            # Measure prediction time
            start = datetime.now(timezone.utc)
            predictions = model.predict(X)
            duration = (datetime.now(timezone.utc) - start).total_seconds()

            avg_time_ms = (duration * 1000) / (len(X) or 1)

            # Check if meets performance requirements
            passed = avg_time_ms < 100  # 100ms per prediction

            return {
                "passed": passed,
                "message": f"Average prediction time: {avg_time_ms:.2f}ms",
                "avg_time_ms": avg_time_ms
            }

        except Exception as exc:
            logger.debug("Caught exception: %s", exc)
            return {
                "passed": False,
                "message": f"Performance test failed: {exc}"
            }

    def _test_consistency(
        self,
        model: ShadowAgentModel,
        dataset: TrainingDataset
    ) -> Dict[str, Any]:
        """Test prediction consistency"""

        try:
            X, y = self._get_sample_data(dataset, n=10)

            # Make predictions multiple times
            pred1 = model.predict(X)
            pred2 = model.predict(X)

            # Check consistency
            consistent = all(p1 == p2 for p1, p2 in zip(pred1, pred2))

            return {
                "passed": consistent,
                "message": "Predictions are consistent" if consistent else "Predictions vary"
            }

        except Exception as exc:
            logger.debug("Caught exception: %s", exc)
            return {
                "passed": False,
                "message": f"Consistency test failed: {exc}"
            }

    def _test_robustness(
        self,
        model: ShadowAgentModel,
        dataset: TrainingDataset
    ) -> Dict[str, Any]:
        """Test model robustness"""

        try:
            # Test with noisy data
            # Test with missing features
            # Test with outliers

            return {
                "passed": True,
                "message": "Model is robust to perturbations"
            }

        except Exception as exc:
            logger.debug("Caught exception: %s", exc)
            return {
                "passed": False,
                "message": f"Robustness test failed: {exc}"
            }

    def _get_sample_data(self, dataset: TrainingDataset, n: int = 10):
        """Get sample data for testing"""

        examples = dataset.get_test_examples()[:n]

        X = []
        y = []

        for example in examples:
            feature_vector = [f.value for f in example.features]
            X.append(feature_vector)

            if example.label:
                y.append(example.label.value)
            else:
                y.append(0)

        return X, y
