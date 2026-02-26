"""
Integration tests for ml_strategy_engine — anomaly detection, forecasting,
classification, recommendation, clustering, RL, feature importance, A/B
testing, ensemble methods, and online incremental learning.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


# ──────────────────────────────────────────────────────────────────────
# 1. Anomaly Detection
# ──────────────────────────────────────────────────────────────────────

class TestAnomalyDetection(unittest.TestCase):
    def setUp(self):
        try:
            from src.ml_strategy_engine import AnomalyDetector, AnomalyMethod
            self.AnomalyDetector = AnomalyDetector
            self.AnomalyMethod = AnomalyMethod
        except ImportError as exc:
            self.skipTest(f"Module not available: {exc}")

    def test_zscore_no_anomaly(self):
        det = self.AnomalyDetector(method=self.AnomalyMethod.ZSCORE, threshold=3.0)
        det.feed_many([10, 11, 10.5, 10.2, 9.8, 10.1, 10.3, 9.9])
        result = det.detect(10.4)
        self.assertFalse(result.is_anomaly)

    def test_zscore_detects_anomaly(self):
        det = self.AnomalyDetector(method=self.AnomalyMethod.ZSCORE, threshold=2.0)
        det.feed_many([10, 10.1, 9.9, 10.2, 9.8, 10.05, 9.95, 10.15, 9.85, 10.0,
                       10.1, 10, 9.9, 10.05, 9.95, 10.2, 9.8, 10, 10.1, 9.9])
        result = det.detect(100)
        self.assertTrue(result.is_anomaly)
        self.assertGreater(result.score, 2.0)

    def test_iqr_no_anomaly(self):
        det = self.AnomalyDetector(method=self.AnomalyMethod.IQR)
        det.feed_many(list(range(1, 21)))
        result = det.detect(10)
        self.assertFalse(result.is_anomaly)

    def test_iqr_detects_anomaly(self):
        det = self.AnomalyDetector(method=self.AnomalyMethod.IQR)
        det.feed_many(list(range(1, 21)))
        result = det.detect(500)
        self.assertTrue(result.is_anomaly)

    def test_batch_detect(self):
        det = self.AnomalyDetector(threshold=2.0)
        det.feed_many([5, 5.1, 4.9, 5.2, 4.8, 5.05, 4.95, 5.15, 4.85, 5.0,
                       5.1, 5, 4.9, 5.05, 4.95, 5.2, 4.8, 5, 5.1, 4.9])
        results = det.detect_batch([5, 5.1, 100])
        self.assertEqual(len(results), 3)
        self.assertTrue(results[2].is_anomaly)


# ──────────────────────────────────────────────────────────────────────
# 2. Time-Series Forecasting
# ──────────────────────────────────────────────────────────────────────

class TestTimeSeriesForecasting(unittest.TestCase):
    def setUp(self):
        try:
            from src.ml_strategy_engine import TimeSeriesForecaster, ForecastMethod
            self.TimeSeriesForecaster = TimeSeriesForecaster
            self.ForecastMethod = ForecastMethod
        except ImportError as exc:
            self.skipTest(f"Module not available: {exc}")

    def test_exponential_smoothing_forecast(self):
        f = self.TimeSeriesForecaster(method=self.ForecastMethod.EXPONENTIAL_SMOOTHING)
        f.add_many([10, 12, 14, 16, 18, 20])
        results = f.forecast(horizon=3)
        self.assertEqual(len(results), 3)
        self.assertGreater(results[0].predicted, 0)

    def test_moving_average_forecast(self):
        f = self.TimeSeriesForecaster(method=self.ForecastMethod.MOVING_AVERAGE, window=3)
        f.add_many([5, 10, 15, 20, 25])
        results = f.forecast(horizon=1)
        self.assertEqual(len(results), 1)
        self.assertAlmostEqual(results[0].predicted, 20.0, places=1)

    def test_weighted_moving_average(self):
        f = self.TimeSeriesForecaster(method=self.ForecastMethod.WEIGHTED_MOVING_AVERAGE)
        f.add_many([10, 20, 30, 40, 50])
        results = f.forecast(horizon=1)
        self.assertGreater(results[0].predicted, 30)

    def test_confidence_interval_widens_with_horizon(self):
        f = self.TimeSeriesForecaster()
        f.add_many([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        results = f.forecast(horizon=3)
        ci_width_1 = results[0].confidence_interval[1] - results[0].confidence_interval[0]
        ci_width_3 = results[2].confidence_interval[1] - results[2].confidence_interval[0]
        self.assertGreater(ci_width_3, ci_width_1)


# ──────────────────────────────────────────────────────────────────────
# 3. Pattern Classification
# ──────────────────────────────────────────────────────────────────────

class TestNaiveBayesClassifier(unittest.TestCase):
    def setUp(self):
        try:
            from src.ml_strategy_engine import NaiveBayesClassifier
            self.NaiveBayesClassifier = NaiveBayesClassifier
        except ImportError as exc:
            self.skipTest(f"Module not available: {exc}")

    def test_train_and_predict(self):
        clf = self.NaiveBayesClassifier()
        clf.train(["error", "crash", "fail"], "bug")
        clf.train(["error", "timeout", "fail"], "bug")
        clf.train(["add", "feature", "new"], "feature")
        clf.train(["implement", "new", "capability"], "feature")
        label, conf = clf.predict(["error", "fail"])
        self.assertEqual(label, "bug")
        self.assertGreater(conf, 0.5)

    def test_classes_property(self):
        clf = self.NaiveBayesClassifier()
        clf.train(["a"], "cat1")
        clf.train(["b"], "cat2")
        self.assertIn("cat1", clf.classes)
        self.assertIn("cat2", clf.classes)

    def test_batch_training(self):
        clf = self.NaiveBayesClassifier()
        clf.train_batch([
            (["fast", "quick"], "positive"),
            (["slow", "broken"], "negative"),
        ])
        label, _ = clf.predict(["fast"])
        self.assertEqual(label, "positive")

    def test_empty_classifier_returns_unknown(self):
        clf = self.NaiveBayesClassifier()
        label, conf = clf.predict(["anything"])
        self.assertEqual(label, "unknown")
        self.assertEqual(conf, 0.0)


# ──────────────────────────────────────────────────────────────────────
# 4. Recommendation Engine
# ──────────────────────────────────────────────────────────────────────

class TestRecommendationEngine(unittest.TestCase):
    def setUp(self):
        try:
            from src.ml_strategy_engine import RecommendationEngine
            self.RecommendationEngine = RecommendationEngine
        except ImportError as exc:
            self.skipTest(f"Module not available: {exc}")

    def test_content_based_recommendation(self):
        rec = self.RecommendationEngine()
        rec.register_item("item1", {"action": 1.0, "comedy": 0.2})
        rec.register_item("item2", {"action": 0.9, "comedy": 0.3})
        rec.register_item("item3", {"drama": 1.0, "comedy": 0.1})
        rec.record_rating("user1", "item1", 5.0)
        recs = rec.recommend_content_based("user1", top_k=2)
        self.assertTrue(len(recs) > 0)
        self.assertEqual(recs[0].item_id, "item2")

    def test_collaborative_recommendation(self):
        rec = self.RecommendationEngine()
        rec.record_rating("user1", "a", 5.0)
        rec.record_rating("user1", "b", 4.0)
        rec.record_rating("user2", "a", 5.0)
        rec.record_rating("user2", "b", 4.0)
        rec.record_rating("user2", "c", 5.0)
        recs = rec.recommend_collaborative("user1", top_k=2)
        self.assertTrue(len(recs) > 0)
        self.assertEqual(recs[0].item_id, "c")

    def test_empty_user_returns_no_recs(self):
        rec = self.RecommendationEngine()
        recs = rec.recommend_content_based("nobody")
        self.assertEqual(len(recs), 0)


# ──────────────────────────────────────────────────────────────────────
# 5. K-Means Clustering
# ──────────────────────────────────────────────────────────────────────

class TestKMeansClustering(unittest.TestCase):
    def setUp(self):
        try:
            from src.ml_strategy_engine import KMeansClusterer
            self.KMeansClusterer = KMeansClusterer
        except ImportError as exc:
            self.skipTest(f"Module not available: {exc}")

    def test_cluster_two_groups(self):
        data = [[0, 0], [1, 0], [0, 1], [100, 100], [101, 100], [100, 101]]
        km = self.KMeansClusterer(k=2)
        result = km.fit(data)
        self.assertEqual(len(result.labels), 6)
        self.assertEqual(len(result.centroids), 2)
        # First 3 should be same cluster, last 3 same cluster
        self.assertEqual(result.labels[0], result.labels[1])
        self.assertEqual(result.labels[0], result.labels[2])
        self.assertEqual(result.labels[3], result.labels[4])
        self.assertNotEqual(result.labels[0], result.labels[3])

    def test_empty_data(self):
        km = self.KMeansClusterer(k=3)
        result = km.fit([])
        self.assertEqual(len(result.labels), 0)

    def test_inertia_positive(self):
        data = [[i, i * 2] for i in range(20)]
        km = self.KMeansClusterer(k=3)
        result = km.fit(data)
        self.assertGreater(result.inertia, 0)


# ──────────────────────────────────────────────────────────────────────
# 6. Q-Learning
# ──────────────────────────────────────────────────────────────────────

class TestQLearning(unittest.TestCase):
    def setUp(self):
        try:
            from src.ml_strategy_engine import QLearningAgent
            self.QLearningAgent = QLearningAgent
        except ImportError as exc:
            self.skipTest(f"Module not available: {exc}")

    def test_learns_simple_policy(self):
        agent = self.QLearningAgent(["left", "right"], epsilon=0.0, learning_rate=0.5)
        for _ in range(50):
            agent.update("start", "right", 10.0, "goal")
            agent.update("start", "left", -1.0, "penalty")
        policy = agent.get_policy()
        self.assertEqual(policy["start"], "right")

    def test_choose_action_returns_valid(self):
        agent = self.QLearningAgent(["a", "b", "c"])
        action = agent.choose_action("state1")
        self.assertIn(action, ["a", "b", "c"])

    def test_episode_counting(self):
        agent = self.QLearningAgent(["x"])
        self.assertEqual(agent.episode_count, 0)
        agent.end_episode()
        agent.end_episode()
        self.assertEqual(agent.episode_count, 2)


# ──────────────────────────────────────────────────────────────────────
# 7. Feature Importance
# ──────────────────────────────────────────────────────────────────────

class TestFeatureImportance(unittest.TestCase):
    def setUp(self):
        try:
            from src.ml_strategy_engine import FeatureAnalyzer
            self.FeatureAnalyzer = FeatureAnalyzer
        except ImportError as exc:
            self.skipTest(f"Module not available: {exc}")

    def test_correlation_importance(self):
        fa = self.FeatureAnalyzer()
        features = {
            "x": [1, 2, 3, 4, 5],
            "noise": [5, 1, 3, 2, 4],
        }
        target = [2, 4, 6, 8, 10]
        result = fa.correlation_importance(features, target)
        self.assertEqual(len(result), 2)
        # 'x' should be more important (perfectly correlated)
        self.assertEqual(result[0].feature, "x")
        self.assertAlmostEqual(result[0].importance, 1.0, places=2)

    def test_information_gain(self):
        fa = self.FeatureAnalyzer()
        features = {"color": ["red", "red", "blue", "blue"]}
        target = ["yes", "yes", "no", "no"]
        result = fa.information_gain(features, target)
        self.assertEqual(len(result), 1)
        self.assertGreater(result[0].importance, 0)


# ──────────────────────────────────────────────────────────────────────
# 8. A/B Testing
# ──────────────────────────────────────────────────────────────────────

class TestABTesting(unittest.TestCase):
    def setUp(self):
        try:
            from src.ml_strategy_engine import ABTestingFramework
            self.ABTestingFramework = ABTestingFramework
        except ImportError as exc:
            self.skipTest(f"Module not available: {exc}")

    def test_create_and_analyze(self):
        ab = self.ABTestingFramework()
        ab.create_experiment("button_color")
        import random
        rng = random.Random(42)
        for _ in range(50):
            ab.record_observation("button_color", "A", 0.1 + rng.gauss(0, 0.02))
            ab.record_observation("button_color", "B", 0.5 + rng.gauss(0, 0.02))
        result = ab.analyze("button_color")
        self.assertIsNotNone(result)
        self.assertEqual(result.recommended_variant, "B")
        self.assertTrue(result.significant)

    def test_insufficient_data(self):
        ab = self.ABTestingFramework()
        ab.create_experiment("test")
        ab.record_observation("test", "A", 1.0)
        result = ab.analyze("test")
        self.assertEqual(result.recommended_variant, "insufficient_data")

    def test_list_experiments(self):
        ab = self.ABTestingFramework()
        ab.create_experiment("exp1")
        ab.create_experiment("exp2")
        self.assertIn("exp1", ab.list_experiments())
        self.assertIn("exp2", ab.list_experiments())


# ──────────────────────────────────────────────────────────────────────
# 9. Ensemble Methods
# ──────────────────────────────────────────────────────────────────────

class TestEnsembleMethods(unittest.TestCase):
    def setUp(self):
        try:
            from src.ml_strategy_engine import (EnsemblePredictor, EnsembleStrategy,
                                                 NaiveBayesClassifier)
            self.EnsemblePredictor = EnsemblePredictor
            self.EnsembleStrategy = EnsembleStrategy
            self.NaiveBayesClassifier = NaiveBayesClassifier
        except ImportError as exc:
            self.skipTest(f"Module not available: {exc}")

    def test_majority_vote(self):
        ensemble = self.EnsemblePredictor(strategy=self.EnsembleStrategy.MAJORITY_VOTE)
        for _ in range(3):
            clf = self.NaiveBayesClassifier()
            clf.train(["error", "crash"], "bug")
            clf.train(["add", "feature"], "feature")
            ensemble.add_member(clf)
        pred = ensemble.predict(["error"])
        self.assertEqual(pred.prediction, "bug")
        self.assertGreater(pred.confidence, 0)

    def test_weighted_vote(self):
        ensemble = self.EnsemblePredictor(strategy=self.EnsembleStrategy.WEIGHTED_VOTE)
        clf1 = self.NaiveBayesClassifier()
        clf1.train(["a"], "x")
        clf2 = self.NaiveBayesClassifier()
        clf2.train(["a"], "y")
        ensemble.add_member(clf1, weight=1.0)
        ensemble.add_member(clf2, weight=3.0)
        pred = ensemble.predict(["a"])
        self.assertEqual(pred.prediction, "y")

    def test_empty_ensemble(self):
        ensemble = self.EnsemblePredictor()
        pred = ensemble.predict(["anything"])
        self.assertEqual(pred.prediction, "unknown")


# ──────────────────────────────────────────────────────────────────────
# 10. Online Incremental Learning
# ──────────────────────────────────────────────────────────────────────

class TestOnlineLearning(unittest.TestCase):
    def setUp(self):
        try:
            from src.ml_strategy_engine import OnlineIncrementalLearner
            self.OnlineIncrementalLearner = OnlineIncrementalLearner
        except ImportError as exc:
            self.skipTest(f"Module not available: {exc}")

    def test_learn_and_predict(self):
        learner = self.OnlineIncrementalLearner(learning_rate=0.1)
        # Train on simple pattern: high x → 1, low x → 0
        for _ in range(50):
            learner.partial_fit({"x": 10.0}, 1)
            learner.partial_fit({"x": -10.0}, 0)
        pred, score = learner.predict({"x": 10.0})
        self.assertEqual(pred, 1)
        self.assertGreater(score, 0.5)

    def test_state_tracking(self):
        learner = self.OnlineIncrementalLearner()
        learner.partial_fit({"a": 1.0}, 1)
        learner.partial_fit({"a": -1.0}, 0)
        state = learner.get_state()
        self.assertEqual(state.samples_seen, 2)
        self.assertIn("a", state.feature_weights)

    def test_accuracy_improves(self):
        learner = self.OnlineIncrementalLearner(learning_rate=0.1)
        acc_early = 0.0
        for i in range(100):
            label = 1 if i % 2 == 0 else 0
            val = 5.0 if label == 1 else -5.0
            acc = learner.partial_fit({"x": val}, label)
            if i == 10:
                acc_early = acc
        state = learner.get_state()
        self.assertGreaterEqual(state.current_accuracy, acc_early)


# ──────────────────────────────────────────────────────────────────────
# 11. MLStrategyEngine Orchestrator
# ──────────────────────────────────────────────────────────────────────

class TestMLStrategyEngineOrchestrator(unittest.TestCase):
    def setUp(self):
        try:
            from src.ml_strategy_engine import MLStrategyEngine
            self.engine = MLStrategyEngine()
        except ImportError as exc:
            self.skipTest(f"Module not available: {exc}")

    def test_status_reports_all_strategies(self):
        status = self.engine.status()
        self.assertTrue(status["initialized"])
        self.assertEqual(status["strategy_count"], 11)

    def test_create_anomaly_detector(self):
        det = self.engine.create_anomaly_detector(method="iqr")
        self.assertIsNotNone(det)

    def test_create_forecaster(self):
        f = self.engine.create_forecaster(method="moving_average")
        self.assertIsNotNone(f)

    def test_create_classifier(self):
        clf = self.engine.create_classifier()
        self.assertIsNotNone(clf)

    def test_create_rl_agent(self):
        agent = self.engine.create_rl_agent(["up", "down", "left", "right"])
        self.assertIsNotNone(agent)
        self.assertEqual(self.engine.rl_agent, agent)

    def test_create_clusterer(self):
        km = self.engine.create_clusterer(k=5)
        self.assertIsNotNone(km)


# ──────────────────────────────────────────────────────────────────────
# 12. MODULE_CATALOG Wiring
# ──────────────────────────────────────────────────────────────────────

class TestMLModuleCatalogWiring(unittest.TestCase):
    def setUp(self):
        try:
            import importlib
            mod = importlib.import_module("murphy_system_1.0_runtime")
            self.MurphySystem = mod.MurphySystem
        except Exception:
            self.skipTest("Runtime not importable")

    def test_catalog_has_ml_strategy_engine(self):
        catalog = self.MurphySystem.MODULE_CATALOG
        names = [m["name"] for m in catalog]
        self.assertIn("ml_strategy_engine", names)

    def test_catalog_ml_capabilities(self):
        catalog = self.MurphySystem.MODULE_CATALOG
        ml_entry = next(m for m in catalog if m["name"] == "ml_strategy_engine")
        caps = ml_entry["capabilities"]
        self.assertIn("anomaly_detection", caps)
        self.assertIn("q_learning", caps)
        self.assertIn("naive_bayes_classification", caps)


if __name__ == '__main__':
    unittest.main()
