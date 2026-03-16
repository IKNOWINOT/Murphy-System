"""
Simple wrapper for Telemetry Learning Module
Removes external dependencies while maintaining interface compatibility
"""

import logging
import statistics
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SimpleTelemetryLearningEngine:
    """
    Simplified telemetry learning engine without external dependencies.

    Provides basic learning capabilities including:
    - Pattern recognition
    - Anomaly detection
    - Predictive analytics
    - Trend analysis
    """

    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize the simplified telemetry learning engine.

        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {
            'learning_rate': 0.1,
            'anomaly_threshold': 2.0,
            'pattern_min_occurrences': 3,
            'prediction_horizon': 10
        }

        # Learning data storage
        self.metrics_history: Dict[str, List[Dict]] = {}
        self.patterns: List[Dict] = []
        self.anomalies: List[Dict] = []
        self.baselines: Dict[str, float] = {}

        # Statistics
        self.stats = {
            'metrics_processed': 0,
            'patterns_discovered': 0,
            'anomalies_detected': 0,
            'predictions_made': 0
        }

        logger.info("Simple Telemetry Learning Engine initialized")

    def process_metrics(self, metrics: List[Dict]) -> Dict:
        """
        Process a batch of metrics for learning.

        Args:
            metrics: List of metric dictionaries

        Returns:
            Processing results with insights
        """
        try:
            results = {
                'processed_count': 0,
                'patterns_found': [],
                'anomalies_detected': [],
                'predictions': []
            }

            for metric in metrics:
                metric_name = metric.get('metric_name', 'unknown')
                value = metric.get('value', 0)
                timestamp = metric.get('timestamp', datetime.now(timezone.utc).isoformat())

                # Store metric history
                if metric_name not in self.metrics_history:
                    self.metrics_history[metric_name] = []

                self.metrics_history[metric_name].append({
                    'value': value,
                    'timestamp': timestamp
                })

                # Update baseline
                self._update_baseline(metric_name, value)

                # Detect anomalies
                anomaly = self._detect_anomaly(metric_name, value)
                if anomaly:
                    self.anomalies.append(anomaly)
                    results['anomalies_detected'].append(anomaly)
                    self.stats['anomalies_detected'] += 1

                results['processed_count'] += 1
                self.stats['metrics_processed'] += 1

            # Discover patterns
            patterns = self._discover_patterns()
            results['patterns_found'] = patterns
            self.stats['patterns_discovered'] += len(patterns)

            # Generate predictions
            predictions = self._generate_predictions()
            results['predictions'] = predictions
            self.stats['predictions_made'] += len(predictions)

            logger.info(f"Processed {results['processed_count']} metrics")
            return results

        except Exception as exc:
            logger.error(f"Error processing metrics: {exc}")
            return {'error': str(exc)}

    def _update_baseline(self, metric_name: str, value: float):
        """
        Update baseline value for a metric.

        Args:
            metric_name: Name of the metric
            value: Current value
        """
        if metric_name not in self.baselines:
            self.baselines[metric_name] = value
        else:
            # Exponential moving average
            learning_rate = self.config['learning_rate']
            self.baselines[metric_name] = (
                (1 - learning_rate) * self.baselines[metric_name] +
                learning_rate * value
            )

    def _detect_anomaly(self, metric_name: str, value: float) -> Optional[Dict]:
        """
        Detect if a value is anomalous.

        Args:
            metric_name: Name of the metric
            value: Current value

        Returns:
            Anomaly dictionary if anomalous, None otherwise
        """
        if metric_name not in self.metrics_history or len(self.metrics_history[metric_name]) < 10:
            return None

        values = [m['value'] for m in self.metrics_history[metric_name][-20:]]

        if len(values) < 10:
            return None

        # Calculate statistics
        mean_val = statistics.mean(values)
        try:
            stdev_val = statistics.stdev(values)
        except statistics.StatisticsError:
            stdev_val = 0

        if stdev_val == 0:
            return None

        # Calculate z-score
        z_score = abs((value - mean_val) / stdev_val)

        threshold = self.config['anomaly_threshold']

        if z_score > threshold:
            return {
                'metric_name': metric_name,
                'value': value,
                'mean': round(mean_val, 4),
                'std_dev': round(stdev_val, 4),
                'z_score': round(z_score, 4),
                'threshold': threshold,
                'severity': 'high' if z_score > threshold * 1.5 else 'medium',
                'timestamp': datetime.now(timezone.utc).isoformat()
            }

        return None

    def _discover_patterns(self) -> List[Dict]:
        """
        Discover patterns in metric data.

        Returns:
            List of discovered patterns
        """
        patterns = []

        for metric_name, history in self.metrics_history.items():
            if len(history) < 20:
                continue

            values = [m['value'] for m in history[-20:]]

            # Trend analysis
            if len(values) >= 10:
                # Simple linear regression
                n = len(values)
                x_values = list(range(n))

                sum_x = sum(x_values)
                sum_y = sum(values)
                sum_xy = sum(x * y for x, y in zip(x_values, values))
                sum_x2 = sum(x ** 2 for x in x_values)

                denominator = n * sum_x2 - sum_x ** 2
                if denominator != 0:
                    slope = (n * sum_xy - sum_x * sum_y) / denominator

                    if slope > 0.1:
                        pattern_type = 'increasing_trend'
                        confidence = min(1.0, abs(slope) * 3)
                    elif slope < -0.1:
                        pattern_type = 'decreasing_trend'
                        confidence = min(1.0, abs(slope) * 3)
                    else:
                        pattern_type = 'stable'
                        confidence = 0.8

                    pattern = {
                        'metric_name': metric_name,
                        'pattern_type': pattern_type,
                        'slope': round(slope, 4),
                        'confidence': round(confidence, 4),
                        'description': f"{metric_name} shows {pattern_type}"
                    }

                    patterns.append(pattern)

        return patterns

    def _generate_predictions(self) -> List[Dict]:
        """
        Generate predictions for future metric values.

        Returns:
            List of predictions
        """
        predictions = []

        for metric_name, history in self.metrics_history.items():
            if len(history) < 10:
                continue

            values = [m['value'] for m in history[-10:]]

            # Simple moving average prediction
            predicted_value = statistics.mean(values)

            # Calculate prediction interval
            try:
                stdev = statistics.stdev(values)
                confidence_interval = 1.96 * stdev  # 95% confidence
            except statistics.StatisticsError:
                confidence_interval = 0

            prediction = {
                'metric_name': metric_name,
                'predicted_value': round(predicted_value, 4),
                'confidence_interval': round(confidence_interval, 4),
                'method': 'moving_average',
                'horizon': self.config['prediction_horizon'],
                'timestamp': datetime.now(timezone.utc).isoformat()
            }

            predictions.append(prediction)

        return predictions

    def get_insights(self) -> Dict:
        """
        Get comprehensive insights from learned data.

        Returns:
            Dictionary with insights and recommendations
        """
        insights = {
            'patterns': self.patterns[-10:],  # Last 10 patterns
            'recent_anomalies': self.anomalies[-5:],  # Last 5 anomalies
            'baselines': self.baselines.copy(),
            'recommendations': self._generate_recommendations()
        }

        return insights

    def _generate_recommendations(self) -> List[Dict]:
        """
        Generate recommendations based on learned patterns.

        Returns:
            List of recommendations
        """
        recommendations = []

        # Check for concerning patterns
        for pattern in self.patterns[-10:]:
            if pattern['pattern_type'] == 'increasing_trend' and pattern['confidence'] > 0.7:
                recommendations.append({
                    'type': 'optimization',
                    'priority': 'high' if pattern['confidence'] > 0.8 else 'medium',
                    'message': f"Investigate increasing trend in {pattern['metric_name']}",
                    'suggested_action': 'Review recent changes and optimize affected components'
                })

        # Check for frequent anomalies
        recent_anomalies = [a for a in self.anomalies
                          if datetime.fromisoformat(a['timestamp']) > datetime.now(timezone.utc) - timedelta(hours=1)]

        if len(recent_anomalies) > 5:
            recommendations.append({
                'type': 'investigation',
                'priority': 'high',
                'message': f"High anomaly rate detected: {len(recent_anomalies)} in the last hour",
                'suggested_action': 'Review system logs and investigate potential issues'
            })

        return recommendations

    def get_statistics(self) -> Dict:
        """
        Get learning engine statistics.

        Returns:
            Dictionary with statistics
        """
        stats = self.stats.copy()
        stats['metrics_tracked'] = len(self.metrics_history)
        stats['patterns_tracked'] = len(self.patterns)
        stats['anomalies_tracked'] = len(self.anomalies)
        return stats

    def reset_learning(self):
        """Reset all learned data."""
        self.metrics_history.clear()
        self.patterns.clear()
        self.anomalies.clear()
        self.baselines.clear()
        self.stats = {
            'metrics_processed': 0,
            'patterns_discovered': 0,
            'anomalies_detected': 0,
            'predictions_made': 0
        }
        logger.info("Learning data reset")


# Create an alias for compatibility
TelemetryLearningEngine = SimpleTelemetryLearningEngine
