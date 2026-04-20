"""
Murphy System — Machine Learning Strategy Engine
=================================================
Pure-Python ML strategy module providing anomaly detection, time-series
forecasting, pattern classification, recommendation, clustering,
reinforcement learning (Q-learning), feature importance, A/B testing,
ensemble methods, and online incremental learning.

All algorithms are implemented without external dependencies (no numpy,
scikit-learn, or pandas required) so the module runs anywhere Python 3.9+
is available.
"""

from __future__ import annotations

import logging
import math
import random
import statistics
import threading
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Tuple

try:
    from thread_safe_operations import capped_append, capped_append_paired
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)
    def capped_append_paired(*lists_and_items: Any, max_size: int = 10_000) -> None:
        """Fallback bounded paired append (CWE-770)."""
        pairs = list(zip(lists_and_items[::2], lists_and_items[1::2]))
        if not pairs:
            return
        ref_list = pairs[0][0]
        if len(ref_list) >= max_size:
            trim = max_size // 10
            for lst, _ in pairs:
                del lst[:trim]
        for lst, item in pairs:
            lst.append(item)

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────
# Shared helpers
# ──────────────────────────────────────────────────────────────────────

def _safe_mean(values: Sequence[float]) -> float:
    return statistics.mean(values) if values else 0.0


def _safe_stdev(values: Sequence[float]) -> float:
    return statistics.pstdev(values) if len(values) > 1 else 0.0


def _euclidean(a: Sequence[float], b: Sequence[float]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def _cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


# ──────────────────────────────────────────────────────────────────────
# 1. Anomaly Detection
# ──────────────────────────────────────────────────────────────────────

class AnomalyMethod(str, Enum):
    """Anomaly method (str subclass)."""
    ZSCORE = "zscore"
    IQR = "iqr"


@dataclass
class AnomalyResult:
    """Anomaly result."""
    value: float
    is_anomaly: bool
    score: float
    method: str
    threshold: float


class AnomalyDetector:
    """Statistical anomaly detection using z-score and IQR methods."""

    def __init__(self, method: AnomalyMethod = AnomalyMethod.ZSCORE,
                 threshold: float = 3.0, iqr_factor: float = 1.5):
        self.method = method
        self.threshold = threshold
        self.iqr_factor = iqr_factor
        self._history: List[float] = []
        self._lock = threading.Lock()

    def feed(self, value: float) -> None:
        with self._lock:
            capped_append(self._history, value)

    def feed_many(self, values: Sequence[float]) -> None:
        with self._lock:
            self._history.extend(values)

    def detect(self, value: float) -> AnomalyResult:
        with self._lock:
            if len(self._history) < 3:
                return AnomalyResult(value, False, 0.0, self.method.value, self.threshold)
            if self.method == AnomalyMethod.ZSCORE:
                return self._zscore_detect(value)
            return self._iqr_detect(value)

    def detect_batch(self, values: Sequence[float]) -> List[AnomalyResult]:
        return [self.detect(v) for v in values]

    # -- internals --

    def _zscore_detect(self, value: float) -> AnomalyResult:
        mu = _safe_mean(self._history)
        sigma = _safe_stdev(self._history)
        if sigma == 0:
            score = 0.0
        else:
            score = abs(value - mu) / sigma
        return AnomalyResult(value, score > self.threshold, score,
                             AnomalyMethod.ZSCORE.value, self.threshold)

    def _iqr_detect(self, value: float) -> AnomalyResult:
        s = sorted(self._history)
        n = len(s)
        q1 = s[n // 4]
        q3 = s[(3 * n) // 4]
        iqr = q3 - q1
        lower = q1 - self.iqr_factor * iqr
        upper = q3 + self.iqr_factor * iqr
        is_anomaly = value < lower or value > upper
        score = 0.0
        if iqr > 0:
            score = max(abs(value - q1), abs(value - q3)) / iqr
        return AnomalyResult(value, is_anomaly, score,
                             AnomalyMethod.IQR.value, self.iqr_factor)


# ──────────────────────────────────────────────────────────────────────
# 2. Time-Series Forecasting
# ──────────────────────────────────────────────────────────────────────

class ForecastMethod(str, Enum):
    """Forecast method (str subclass)."""
    MOVING_AVERAGE = "moving_average"
    EXPONENTIAL_SMOOTHING = "exponential_smoothing"
    WEIGHTED_MOVING_AVERAGE = "weighted_moving_average"


@dataclass
class ForecastResult:
    """Forecast result."""
    predicted: float
    confidence_interval: Tuple[float, float]
    method: str
    horizon: int


class TimeSeriesForecaster:
    """Lightweight time-series forecasting."""

    def __init__(self, method: ForecastMethod = ForecastMethod.EXPONENTIAL_SMOOTHING,
                 alpha: float = 0.3, window: int = 5):
        self.method = method
        self.alpha = alpha
        self.window = window
        self._series: List[float] = []
        self._lock = threading.Lock()

    def add(self, value: float) -> None:
        with self._lock:
            capped_append(self._series, value)

    def add_many(self, values: Sequence[float]) -> None:
        with self._lock:
            self._series.extend(values)

    def forecast(self, horizon: int = 1) -> List[ForecastResult]:
        with self._lock:
            if len(self._series) < 2:
                return [ForecastResult(0.0, (0.0, 0.0), self.method.value, h)
                        for h in range(1, horizon + 1)]
            if self.method == ForecastMethod.MOVING_AVERAGE:
                return self._ma_forecast(horizon)
            if self.method == ForecastMethod.WEIGHTED_MOVING_AVERAGE:
                return self._wma_forecast(horizon)
            return self._es_forecast(horizon)

    # -- internals --

    def _ma_forecast(self, horizon: int) -> List[ForecastResult]:
        w = min(self.window, len(self._series))
        recent = self._series[-w:]
        pred = _safe_mean(recent)
        sigma = _safe_stdev(recent)
        results = []
        for h in range(1, horizon + 1):
            ci = (pred - 1.96 * sigma * math.sqrt(h),
                  pred + 1.96 * sigma * math.sqrt(h))
            results.append(ForecastResult(pred, ci,
                                          ForecastMethod.MOVING_AVERAGE.value, h))
        return results

    def _wma_forecast(self, horizon: int) -> List[ForecastResult]:
        w = min(self.window, len(self._series))
        recent = self._series[-w:]
        weights = list(range(1, len(recent) + 1))
        total_w = sum(weights)
        pred = sum(v * wt for v, wt in zip(recent, weights)) / total_w
        sigma = _safe_stdev(recent)
        results = []
        for h in range(1, horizon + 1):
            ci = (pred - 1.96 * sigma * math.sqrt(h),
                  pred + 1.96 * sigma * math.sqrt(h))
            results.append(ForecastResult(pred, ci,
                                          ForecastMethod.WEIGHTED_MOVING_AVERAGE.value, h))
        return results

    def _es_forecast(self, horizon: int) -> List[ForecastResult]:
        level = self._series[0]
        for v in self._series[1:]:
            level = self.alpha * v + (1 - self.alpha) * level
        sigma = _safe_stdev(self._series)
        results = []
        for h in range(1, horizon + 1):
            ci = (level - 1.96 * sigma * math.sqrt(h),
                  level + 1.96 * sigma * math.sqrt(h))
            results.append(ForecastResult(level, ci,
                                          ForecastMethod.EXPONENTIAL_SMOOTHING.value, h))
        return results


# ──────────────────────────────────────────────────────────────────────
# 3. Pattern Classification (Naive Bayes)
# ──────────────────────────────────────────────────────────────────────

class NaiveBayesClassifier:
    """Multinomial Naive Bayes for text/feature classification."""

    def __init__(self, laplace_smoothing: float = 1.0):
        self.alpha = laplace_smoothing
        self._class_counts: Dict[str, int] = defaultdict(int)
        self._feature_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._vocab: set = set()
        self._total_samples = 0
        self._lock = threading.Lock()

    def train(self, features: Sequence[str], label: str) -> None:
        with self._lock:
            self._class_counts[label] += 1
            self._total_samples += 1
            for f in features:
                self._feature_counts[label][f] += 1
                self._vocab.add(f)

    def train_batch(self, samples: Sequence[Tuple[Sequence[str], str]]) -> None:
        for features, label in samples:
            self.train(features, label)

    def predict(self, features: Sequence[str]) -> Tuple[str, float]:
        with self._lock:
            if not self._class_counts:
                return ("unknown", 0.0)
            scores: Dict[str, float] = {}
            v = len(self._vocab)
            for cls, count in self._class_counts.items():
                log_prior = math.log(count / self._total_samples)
                total_feat = sum(self._feature_counts[cls].values())
                log_likelihood = 0.0
                for f in features:
                    fc = self._feature_counts[cls].get(f, 0)
                    log_likelihood += math.log((fc + self.alpha) / (total_feat + self.alpha * v))
                scores[cls] = log_prior + log_likelihood
            best_cls = max(scores, key=scores.get)  # type: ignore[arg-type]
            # Convert log-score to confidence via softmax-like normalization
            max_score = max(scores.values())
            exp_scores = {c: math.exp(s - max_score) for c, s in scores.items()}
            total_exp = sum(exp_scores.values())
            confidence = exp_scores[best_cls] / total_exp if total_exp > 0 else 0.0
            return (best_cls, confidence)

    @property
    def classes(self) -> List[str]:
        return list(self._class_counts.keys())


# ──────────────────────────────────────────────────────────────────────
# 4. Recommendation Engine
# ──────────────────────────────────────────────────────────────────────

@dataclass
class Recommendation:
    """Recommendation."""
    item_id: str
    score: float
    reason: str


class RecommendationEngine:
    """Content-based + collaborative filtering recommendation engine."""

    def __init__(self):
        # item_id → feature_vector (dict of feature_name → weight)
        self._item_features: Dict[str, Dict[str, float]] = {}
        # user_id → {item_id: rating}
        self._user_ratings: Dict[str, Dict[str, float]] = defaultdict(dict)
        self._lock = threading.Lock()

    def register_item(self, item_id: str, features: Dict[str, float]) -> None:
        with self._lock:
            self._item_features[item_id] = features

    def record_rating(self, user_id: str, item_id: str, rating: float) -> None:
        with self._lock:
            self._user_ratings[user_id][item_id] = rating

    def recommend_content_based(self, user_id: str, top_k: int = 5) -> List[Recommendation]:
        """Recommend items similar to what user rated highly."""
        with self._lock:
            rated = self._user_ratings.get(user_id, {})
            if not rated or not self._item_features:
                return []
            # Build user profile from positively-rated items
            profile: Dict[str, float] = defaultdict(float)
            positive_count = 0
            for item_id, rating in rated.items():
                if rating > 0 and item_id in self._item_features:
                    for feat, val in self._item_features[item_id].items():
                        profile[feat] += val * rating
                    positive_count += 1
            if positive_count == 0:
                return []
            for feat in profile:
                profile[feat] /= positive_count
            # Score unrated items
            candidates = []
            profile_vec = list(profile.values())
            profile_keys = list(profile.keys())
            for item_id, features in self._item_features.items():
                if item_id in rated:
                    continue
                item_vec = [features.get(k, 0.0) for k in profile_keys]
                sim = _cosine_similarity(profile_vec, item_vec)
                candidates.append(Recommendation(item_id, sim, "content_similarity"))
            candidates.sort(key=lambda r: r.score, reverse=True)
            return candidates[:top_k]

    def recommend_collaborative(self, user_id: str, top_k: int = 5) -> List[Recommendation]:
        """Recommend items based on similar users' ratings."""
        with self._lock:
            my_ratings = self._user_ratings.get(user_id, {})
            if not my_ratings:
                return []
            # Find similar users
            user_sims: List[Tuple[str, float]] = []
            for other_id, other_ratings in self._user_ratings.items():
                if other_id == user_id:
                    continue
                common = set(my_ratings) & set(other_ratings)
                if not common:
                    continue
                a = [my_ratings[i] for i in common]
                b = [other_ratings[i] for i in common]
                sim = _cosine_similarity(a, b)
                user_sims.append((other_id, sim))
            user_sims.sort(key=lambda x: x[1], reverse=True)
            # Aggregate scores from top similar users
            item_scores: Dict[str, float] = defaultdict(float)
            weight_sums: Dict[str, float] = defaultdict(float)
            for other_id, sim in user_sims[:10]:
                if sim <= 0:
                    continue
                for item_id, rating in self._user_ratings[other_id].items():
                    if item_id not in my_ratings:
                        item_scores[item_id] += sim * rating
                        weight_sums[item_id] += sim
            results = []
            for item_id, score in item_scores.items():
                ws = weight_sums[item_id]
                results.append(Recommendation(item_id, score / ws if ws > 0 else 0,
                                              "collaborative_filtering"))
            results.sort(key=lambda r: r.score, reverse=True)
            return results[:top_k]


# ──────────────────────────────────────────────────────────────────────
# 5. K-Means Clustering
# ──────────────────────────────────────────────────────────────────────

@dataclass
class ClusterResult:
    """Cluster result."""
    labels: List[int]
    centroids: List[List[float]]
    iterations: int
    inertia: float


class KMeansClusterer:
    """K-means clustering for grouping similar data points."""

    def __init__(self, k: int = 3, max_iterations: int = 100, seed: int = 42):
        self.k = k
        self.max_iterations = max_iterations
        self._rng = random.Random(seed)

    def fit(self, data: Sequence[Sequence[float]]) -> ClusterResult:
        if not data or len(data) < self.k:
            return ClusterResult([], [], 0, 0.0)
        n = len(data)
        dim = len(data[0])
        # Initialize centroids via random selection
        indices = self._rng.sample(range(n), self.k)
        centroids = [list(data[i]) for i in indices]
        labels = [0] * n
        for iteration in range(self.max_iterations):
            # Assignment step
            new_labels = []
            for point in data:
                dists = [_euclidean(point, c) for c in centroids]
                new_labels.append(dists.index(min(dists)))
            # Check convergence
            if new_labels == labels and iteration > 0:
                labels = new_labels
                break
            labels = new_labels
            # Update step
            for ci in range(self.k):
                members = [data[j] for j in range(n) if labels[j] == ci]
                if members:
                    centroids[ci] = [sum(m[d] for m in members) / (len(members) or 1)
                                     for d in range(dim)]
        # Compute inertia
        inertia = sum(_euclidean(data[j], centroids[labels[j]]) ** 2
                      for j in range(n))
        return ClusterResult(labels, centroids, iteration + 1, inertia)  # type: ignore[possibly-undefined]


# ──────────────────────────────────────────────────────────────────────
# 6. Reinforcement Learning — Q-Learning
# ──────────────────────────────────────────────────────────────────────

class QLearningAgent:
    """Tabular Q-learning agent for discrete state-action spaces."""

    def __init__(self, actions: Sequence[str], learning_rate: float = 0.1,
                 discount: float = 0.95, epsilon: float = 0.1, seed: int = 42):
        self.actions = list(actions)
        self.lr = learning_rate
        self.discount = discount
        self.epsilon = epsilon
        self._q: Dict[str, Dict[str, float]] = defaultdict(lambda: {a: 0.0 for a in self.actions})
        self._rng = random.Random(seed)
        self._episodes = 0
        self._lock = threading.Lock()

    def choose_action(self, state: str) -> str:
        with self._lock:
            if self._rng.random() < self.epsilon:
                return self._rng.choice(self.actions)
            q_vals = self._q[state]
            return max(q_vals, key=q_vals.get)  # type: ignore[arg-type]

    def update(self, state: str, action: str, reward: float, next_state: str) -> float:
        with self._lock:
            old_q = self._q[state][action]
            best_next = max(self._q[next_state].values())
            new_q = old_q + self.lr * (reward + self.discount * best_next - old_q)
            self._q[state][action] = new_q
            return new_q

    def end_episode(self) -> None:
        with self._lock:
            self._episodes += 1

    def get_policy(self) -> Dict[str, str]:
        with self._lock:
            return {s: max(acts, key=acts.get) for s, acts in self._q.items()}  # type: ignore[arg-type]

    @property
    def episode_count(self) -> int:
        return self._episodes


# ──────────────────────────────────────────────────────────────────────
# 7. Feature Importance Analysis
# ──────────────────────────────────────────────────────────────────────

@dataclass
class FeatureImportance:
    """Feature importance."""
    feature: str
    importance: float
    method: str


class FeatureAnalyzer:
    """Compute feature importance via correlation and information gain."""

    def correlation_importance(self, features: Dict[str, List[float]],
                                target: List[float]) -> List[FeatureImportance]:
        """Pearson correlation coefficient as importance proxy."""
        results = []
        n = len(target)
        if n < 2:
            return results
        t_mean = _safe_mean(target)
        t_std = _safe_stdev(target)
        if t_std == 0:
            return [FeatureImportance(f, 0.0, "correlation") for f in features]
        for fname, fvals in features.items():
            if len(fvals) != n:
                continue
            f_mean = _safe_mean(fvals)
            f_std = _safe_stdev(fvals)
            if f_std == 0:
                results.append(FeatureImportance(fname, 0.0, "correlation"))
                continue
            cov = sum((fvals[i] - f_mean) * (target[i] - t_mean) for i in range(n)) / n
            r = cov / (f_std * t_std)
            results.append(FeatureImportance(fname, abs(r), "correlation"))
        results.sort(key=lambda fi: fi.importance, reverse=True)
        return results

    def information_gain(self, features: Dict[str, List[str]],
                          target: List[str]) -> List[FeatureImportance]:
        """Information gain (reduction in entropy) for categorical features."""
        results = []
        n = len(target)
        if n == 0:
            return results
        base_entropy = self._entropy(target)
        for fname, fvals in features.items():
            if len(fvals) != n:
                continue
            # Split by feature values
            splits: Dict[str, List[str]] = defaultdict(list)
            for i, fv in enumerate(fvals):
                splits[fv].append(target[i])
            cond_entropy = sum(len(subset) / n * self._entropy(subset)
                               for subset in splits.values())
            ig = base_entropy - cond_entropy
            results.append(FeatureImportance(fname, ig, "information_gain"))
        results.sort(key=lambda fi: fi.importance, reverse=True)
        return results

    @staticmethod
    def _entropy(values: List[str]) -> float:
        n = len(values)
        if n == 0:
            return 0.0
        counts: Dict[str, int] = defaultdict(int)
        for v in values:
            counts[v] += 1
        return -sum((c / n) * math.log2(c / n) for c in counts.values() if c > 0)


# ──────────────────────────────────────────────────────────────────────
# 8. A/B Testing Framework
# ──────────────────────────────────────────────────────────────────────

@dataclass
class ABTestResult:
    """AB test result."""
    test_name: str
    variant_a_mean: float
    variant_b_mean: float
    p_value: float
    significant: bool
    recommended_variant: str
    sample_size_a: int
    sample_size_b: int


class ABTestingFramework:
    """Statistical A/B testing for system configuration experiments."""

    def __init__(self, significance_level: float = 0.05):
        self.significance = significance_level
        self._experiments: Dict[str, Dict[str, List[float]]] = {}
        self._lock = threading.Lock()

    def create_experiment(self, name: str) -> None:
        with self._lock:
            self._experiments[name] = {"A": [], "B": []}

    def record_observation(self, experiment: str, variant: str, value: float) -> None:
        with self._lock:
            if experiment in self._experiments and variant in self._experiments[experiment]:
                self._experiments[experiment][variant].append(value)

    def analyze(self, experiment: str) -> Optional[ABTestResult]:
        with self._lock:
            if experiment not in self._experiments:
                return None
            a = self._experiments[experiment]["A"]
            b = self._experiments[experiment]["B"]
            if len(a) < 2 or len(b) < 2:
                return ABTestResult(experiment, _safe_mean(a), _safe_mean(b),
                                    1.0, False, "insufficient_data",
                                    len(a), len(b))
            mean_a, mean_b = _safe_mean(a), _safe_mean(b)
            var_a = statistics.variance(a)
            var_b = statistics.variance(b)
            se = math.sqrt(var_a / (len(a) or 1) + var_b / (len(b) or 1))
            if se == 0:
                p_value = 1.0
            else:
                t_stat = abs(mean_a - mean_b) / se
                # Approximate p-value using normal distribution for large samples
                p_value = 2 * (1 - self._normal_cdf(t_stat))
            significant = p_value < self.significance
            recommended = "A" if mean_a >= mean_b else "B"
            return ABTestResult(experiment, mean_a, mean_b, p_value,
                                significant, recommended, len(a), len(b))

    def list_experiments(self) -> List[str]:
        return list(self._experiments.keys())

    @staticmethod
    def _normal_cdf(x: float) -> float:
        """Approximation of the standard normal CDF."""
        return 0.5 * (1 + math.erf(x / math.sqrt(2)))


# ──────────────────────────────────────────────────────────────────────
# 9. Ensemble Methods
# ──────────────────────────────────────────────────────────────────────

class EnsembleStrategy(str, Enum):
    """Ensemble strategy (str subclass)."""
    MAJORITY_VOTE = "majority_vote"
    WEIGHTED_VOTE = "weighted_vote"
    AVERAGE = "average"
    STACKING = "stacking"


@dataclass
class EnsemblePrediction:
    """Ensemble prediction."""
    prediction: Any
    confidence: float
    strategy: str
    member_predictions: List[Any]


class EnsemblePredictor:
    """Combine multiple classifiers / predictors for robust output."""

    def __init__(self, strategy: EnsembleStrategy = EnsembleStrategy.MAJORITY_VOTE):
        self.strategy = strategy
        self._classifiers: List[NaiveBayesClassifier] = []
        self._weights: List[float] = []

    def add_member(self, classifier: NaiveBayesClassifier, weight: float = 1.0) -> None:
        capped_append_paired(self._classifiers, classifier, self._weights, weight)

    def predict(self, features: Sequence[str]) -> EnsemblePrediction:
        if not self._classifiers:
            return EnsemblePrediction("unknown", 0.0, self.strategy.value, [])
        preds = [clf.predict(features) for clf in self._classifiers]
        member_preds = [p[0] for p in preds]
        if self.strategy == EnsembleStrategy.MAJORITY_VOTE:
            return self._majority_vote(preds, member_preds)
        if self.strategy == EnsembleStrategy.WEIGHTED_VOTE:
            return self._weighted_vote(preds, member_preds)
        return self._majority_vote(preds, member_preds)

    def _majority_vote(self, preds, member_preds) -> EnsemblePrediction:
        votes: Dict[str, int] = defaultdict(int)
        for label, _ in preds:
            votes[label] += 1
        best = max(votes, key=votes.get)  # type: ignore[arg-type]
        conf = votes[best] / (len(preds) or 1)
        return EnsemblePrediction(best, conf, EnsembleStrategy.MAJORITY_VOTE.value,
                                  member_preds)

    def _weighted_vote(self, preds, member_preds) -> EnsemblePrediction:
        scores: Dict[str, float] = defaultdict(float)
        total_w = sum(self._weights)
        for (label, conf), w in zip(preds, self._weights):
            scores[label] += w * conf
        best = max(scores, key=scores.get)  # type: ignore[arg-type]
        final_conf = scores[best] / total_w if total_w > 0 else 0.0
        return EnsemblePrediction(best, final_conf, EnsembleStrategy.WEIGHTED_VOTE.value,
                                  member_preds)


# ──────────────────────────────────────────────────────────────────────
# 10. Online Incremental Learner
# ──────────────────────────────────────────────────────────────────────

@dataclass
class OnlineLearnerState:
    """Online learner state."""
    samples_seen: int
    current_accuracy: float
    feature_weights: Dict[str, float]
    last_updated: str


class OnlineIncrementalLearner:
    """Perceptron-style online learner for streaming data."""

    def __init__(self, learning_rate: float = 0.01):
        self.lr = learning_rate
        self._weights: Dict[str, float] = defaultdict(float)
        self._bias = 0.0
        self._samples_seen = 0
        self._correct = 0
        self._lock = threading.Lock()

    def partial_fit(self, features: Dict[str, float], label: int) -> float:
        """Train on a single sample. Label should be 0 or 1."""
        with self._lock:
            raw = self._bias + sum(self._weights.get(f, 0.0) * v
                                   for f, v in features.items())
            pred = 1 if raw >= 0.5 else 0
            error = label - pred
            if error != 0:
                for f, v in features.items():
                    self._weights[f] += self.lr * error * v
                self._bias += self.lr * error
            else:
                self._correct += 1
            self._samples_seen += 1
            return self._correct / self._samples_seen if self._samples_seen > 0 else 0.0

    def predict(self, features: Dict[str, float]) -> Tuple[int, float]:
        with self._lock:
            raw = self._bias + sum(self._weights.get(f, 0.0) * v
                                   for f, v in features.items())
            score = 1 / (1 + math.exp(-raw)) if abs(raw) < 500 else (1.0 if raw > 0 else 0.0)
            return (1 if score >= 0.5 else 0, score)

    def get_state(self) -> OnlineLearnerState:
        with self._lock:
            acc = self._correct / self._samples_seen if self._samples_seen > 0 else 0.0
            return OnlineLearnerState(
                samples_seen=self._samples_seen,
                current_accuracy=acc,
                feature_weights=dict(self._weights),
                last_updated=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            )


# ──────────────────────────────────────────────────────────────────────
# Top-Level Orchestrator
# ──────────────────────────────────────────────────────────────────────

class MLStrategyEngine:
    """
    Central orchestrator that exposes all ML strategies as a single
    module for the Murphy System runtime.
    """

    def __init__(self):
        self.anomaly_detector = AnomalyDetector()
        self.iqr_detector = AnomalyDetector(method=AnomalyMethod.IQR)
        self.forecaster = TimeSeriesForecaster()
        self.classifier = NaiveBayesClassifier()
        self.recommender = RecommendationEngine()
        self.clusterer = KMeansClusterer()
        self.rl_agent: Optional[QLearningAgent] = None
        self.feature_analyzer = FeatureAnalyzer()
        self.ab_testing = ABTestingFramework()
        self.ensemble = EnsemblePredictor()
        self.online_learner = OnlineIncrementalLearner()
        self._initialized = True
        logger.info("MLStrategyEngine initialized with 10 ML strategies")

    # -- convenience factory methods --

    def create_anomaly_detector(self, method: str = "zscore",
                                 threshold: float = 3.0) -> AnomalyDetector:
        m = AnomalyMethod(method)
        return AnomalyDetector(method=m, threshold=threshold)

    def create_forecaster(self, method: str = "exponential_smoothing",
                           alpha: float = 0.3, window: int = 5) -> TimeSeriesForecaster:
        m = ForecastMethod(method)
        return TimeSeriesForecaster(method=m, alpha=alpha, window=window)

    def create_classifier(self, smoothing: float = 1.0) -> NaiveBayesClassifier:
        return NaiveBayesClassifier(laplace_smoothing=smoothing)

    def create_rl_agent(self, actions: Sequence[str], lr: float = 0.1,
                         discount: float = 0.95, epsilon: float = 0.1) -> QLearningAgent:
        agent = QLearningAgent(actions, learning_rate=lr, discount=discount,
                               epsilon=epsilon)
        self.rl_agent = agent
        return agent

    def create_clusterer(self, k: int = 3, max_iter: int = 100) -> KMeansClusterer:
        return KMeansClusterer(k=k, max_iterations=max_iter)

    def status(self) -> Dict[str, Any]:
        return {
            "initialized": self._initialized,
            "strategies": [
                "anomaly_detection_zscore",
                "anomaly_detection_iqr",
                "time_series_forecasting",
                "naive_bayes_classification",
                "recommendation_engine",
                "kmeans_clustering",
                "q_learning_reinforcement",
                "feature_importance_analysis",
                "ab_testing_framework",
                "ensemble_methods",
                "online_incremental_learning",
                "sequence_scoring",  # Permutation calibration
            ],
            "strategy_count": 12,
            "classifier_classes": self.classifier.classes,
            "forecaster_method": self.forecaster.method.value,
            "ab_experiments": self.ab_testing.list_experiments(),
            "online_learner_state": {
                "samples_seen": self.online_learner._samples_seen,
            },
        }

    # ------------------------------------------------------------------
    # Permutation Calibration Integration (Spec Section 3.2)
    # ------------------------------------------------------------------

    def score_sequence_family(
        self,
        sequence_id: str,
        evaluations: List[Dict[str, float]],
    ) -> Dict[str, Any]:
        """Score a sequence family based on evaluation history.

        This implements spec Section 3.2: Score sequence families, detect
        robust vs brittle orderings.

        Args:
            sequence_id: The sequence ID being scored
            evaluations: List of evaluation dicts with scores

        Returns:
            Comprehensive scoring result
        """
        if not evaluations:
            return {
                "status": "insufficient_data",
                "sequence_id": sequence_id,
                "sample_count": 0,
            }

        # Extract metrics
        outcome_scores = [e.get("outcome_quality", 0.5) for e in evaluations]
        calibration_scores = [e.get("calibration_quality", 0.5) for e in evaluations]
        stability_scores = [e.get("stability_score", 0.5) for e in evaluations]

        # Calculate aggregate scores
        avg_outcome = _safe_mean(outcome_scores)
        avg_calibration = _safe_mean(calibration_scores)
        avg_stability = _safe_mean(stability_scores)

        # Calculate variance/robustness
        outcome_variance = _safe_stdev(outcome_scores) ** 2
        calibration_variance = _safe_stdev(calibration_scores) ** 2
        stability_variance = _safe_stdev(stability_scores) ** 2

        # Detect brittleness (high variance = brittle)
        brittleness = (outcome_variance + calibration_variance + stability_variance) / 3
        is_robust = brittleness < 0.02
        is_brittle = brittleness > 0.1

        # Calculate composite score using spec weights
        composite_score = (
            avg_outcome * 0.35 +
            avg_calibration * 0.35 +
            avg_stability * 0.20 +
            (1 - brittleness) * 0.10
        )

        # Determine promotion readiness
        promotion_ready = (
            len(evaluations) >= 10 and
            avg_outcome >= 0.65 and
            avg_calibration >= 0.6 and
            avg_stability >= 0.6 and
            not is_brittle
        )

        return {
            "status": "ok",
            "sequence_id": sequence_id,
            "sample_count": len(evaluations),
            "avg_outcome_quality": round(avg_outcome, 4),
            "avg_calibration_quality": round(avg_calibration, 4),
            "avg_stability_score": round(avg_stability, 4),
            "outcome_variance": round(outcome_variance, 6),
            "calibration_variance": round(calibration_variance, 6),
            "stability_variance": round(stability_variance, 6),
            "brittleness": round(brittleness, 4),
            "is_robust": is_robust,
            "is_brittle": is_brittle,
            "composite_score": round(composite_score, 4),
            "promotion_ready": promotion_ready,
        }

    def rank_sequence_candidates(
        self,
        candidates: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Rank sequence candidates for procedural promotion.

        This implements spec Section 3.2: Rank candidate paths for
        procedural promotion.

        Args:
            candidates: List of candidate dicts with sequence_id and evaluations

        Returns:
            Ranked list of candidates with scores
        """
        scored_candidates = []

        for candidate in candidates:
            sequence_id = candidate.get("sequence_id")
            evaluations = candidate.get("evaluations", [])

            score_result = self.score_sequence_family(sequence_id, evaluations)

            scored_candidates.append({
                "sequence_id": sequence_id,
                "domain": candidate.get("domain", "unknown"),
                "ordering": candidate.get("ordering", []),
                "composite_score": score_result.get("composite_score", 0.0),
                "promotion_ready": score_result.get("promotion_ready", False),
                "is_robust": score_result.get("is_robust", False),
                "is_brittle": score_result.get("is_brittle", True),
                "sample_count": score_result.get("sample_count", 0),
                "full_score": score_result,
            })

        # Rank by composite score (descending)
        scored_candidates.sort(key=lambda c: c["composite_score"], reverse=True)

        # Add rank position
        for i, candidate in enumerate(scored_candidates):
            candidate["rank"] = i + 1

        return scored_candidates

    def detect_ordering_anomalies(
        self,
        domain: str,
        recent_scores: List[float],
        historical_scores: List[float],
    ) -> Dict[str, Any]:
        """Detect anomalous performance changes in ordering outcomes.

        This helps identify drift or sudden changes in sequence effectiveness.

        Args:
            domain: Domain being analyzed
            recent_scores: Recent outcome scores
            historical_scores: Historical baseline scores

        Returns:
            Anomaly detection result
        """
        if len(historical_scores) < 5 or len(recent_scores) < 3:
            return {
                "status": "insufficient_data",
                "domain": domain,
                "historical_count": len(historical_scores),
                "recent_count": len(recent_scores),
            }

        # Calculate baseline statistics
        historical_mean = _safe_mean(historical_scores)
        historical_std = _safe_stdev(historical_scores)

        # Calculate recent statistics
        recent_mean = _safe_mean(recent_scores)

        # Z-score of recent mean relative to historical distribution
        if historical_std > 0:
            z_score = (recent_mean - historical_mean) / historical_std
        else:
            z_score = 0.0

        # Detect significant drift
        drift_detected = abs(z_score) > 2.0
        improvement = z_score > 2.0
        degradation = z_score < -2.0

        # Check individual anomalies in recent scores using a fresh detector
        detector = AnomalyDetector(threshold=2.0)
        detector.feed_many(historical_scores)

        anomalies = []
        for i, score in enumerate(recent_scores):
            result = detector.detect(score)
            if result.is_anomaly:
                anomalies.append({
                    "index": i,
                    "score": score,
                    "anomaly_score": result.score,
                })

        return {
            "status": "ok",
            "domain": domain,
            "historical_mean": round(historical_mean, 4),
            "historical_std": round(historical_std, 4),
            "recent_mean": round(recent_mean, 4),
            "z_score": round(z_score, 4),
            "drift_detected": drift_detected,
            "improvement": improvement,
            "degradation": degradation,
            "individual_anomalies": anomalies,
            "recommendation": (
                "reopen_exploration" if degradation else
                "maintain_procedure" if not drift_detected else
                "investigate_improvement"
            ),
        }

    def online_sequence_learning(
        self,
        sequence_id: str,
        features: Dict[str, float],
        success: bool,
    ) -> Dict[str, Any]:
        """Perform online learning for sequence success prediction.

        This supports online learning over feed changes (spec Section 3.2).

        Args:
            sequence_id: The sequence being learned
            features: Feature dict (e.g., ordering entropy, domain metrics)
            success: Whether the execution was successful

        Returns:
            Learning update result
        """
        # Add sequence-specific feature
        enriched_features = dict(features)
        enriched_features[f"seq:{sequence_id}"] = 1.0

        # Perform online learning update
        accuracy = self.online_learner.partial_fit(enriched_features, 1 if success else 0)

        return {
            "status": "ok",
            "sequence_id": sequence_id,
            "success": success,
            "model_accuracy": round(accuracy, 4),
            "samples_seen": self.online_learner._samples_seen,
        }

    def predict_sequence_success(
        self,
        sequence_id: str,
        features: Dict[str, float],
    ) -> Dict[str, Any]:
        """Predict whether a sequence execution will succeed.

        Args:
            sequence_id: The sequence to predict for
            features: Feature dict for prediction

        Returns:
            Success prediction
        """
        enriched_features = dict(features)
        enriched_features[f"seq:{sequence_id}"] = 1.0

        prediction, confidence = self.online_learner.predict(enriched_features)

        return {
            "status": "ok",
            "sequence_id": sequence_id,
            "predicted_success": bool(prediction),
            "confidence": round(confidence, 4),
        }
