# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Telemetry Learning Adapter for Murphy System Runtime
Provides telemetry data collection, analysis, and learning capabilities
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Union

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TelemetryAdapter:
    """
    Adapter for telemetry learning integration.

    Provides telemetry capabilities including:
    - Data collection from system components
    - Performance metrics tracking
    - Anomaly detection and learning
    - System behavior analysis
    - Predictive modeling insights
    - Adaptive optimization recommendations
    """

    def __init__(self, telemetry_learning_module=None):
        """
        Initialize the telemetry adapter.

        Args:
            telemetry_learning_module: Optional telemetry_learning module instance
        """
        self.telemetry_learning = telemetry_learning_module
        self.enabled = telemetry_learning_module is not None

        # Telemetry data storage
        self.metrics: Dict[str, List[Dict]] = {
            'performance': [],
            'errors': [],
            'warnings': [],
            'system_events': [],
            'user_actions': []
        }

        # Learning models and insights
        self.baselines: Dict[str, float] = {}
        self.anomalies: List[Dict] = []
        self.patterns: List[Dict] = []
        self.recommendations: List[Dict] = []

        # Configuration
        self.config = {
            'data_retention_hours': 24,
            'anomaly_threshold': 2.0,
            'pattern_min_confidence': 0.7,
            'auto_learning': True,
            'learning_interval_minutes': 5
        }

        if self.enabled:
            logger.info("Telemetry Adapter initialized with telemetry_learning module")
        else:
            logger.warning("Telemetry Adapter running in FALLBACK mode - telemetry_learning module not available")

    def is_enabled(self) -> bool:
        """Check if telemetry learning is enabled"""
        return self.enabled

    def collect_metric(
        self,
        metric_type: str = None,
        metric_name: str = None,
        value: float = None,
        labels: Optional[Dict] = None,
        timestamp: Optional[str] = None,
        *,
        name: str = None,
        category: str = None,
    ) -> Dict:
        """
        Collect a telemetry metric.

        Args:
            metric_type: Type of metric (performance, error, warning, system_event, user_action)
            metric_name: Name of the metric
            value: Metric value
            labels: Optional labels/dimensions for the metric
            timestamp: Optional timestamp (ISO format)
            name: Alias for metric_name (convenience)
            category: Alias for metric_type (convenience)

        Returns:
            Dict with collection status
        """
        # Handle convenience parameter aliases
        if metric_name is None and name is not None:
            metric_name = name
        if metric_type is None and category is not None:
            metric_type = category
        # Defaults
        if metric_type is None:
            metric_type = "performance"
        if metric_name is None:
            metric_name = "unnamed_metric"
        if value is None:
            value = 0.0
        if timestamp is None:
            timestamp = datetime.now(timezone.utc).isoformat()

        if labels is None:
            labels = {}

        try:
            metric = {
                'metric_type': metric_type,
                'metric_name': metric_name,
                'value': value,
                'labels': labels,
                'timestamp': timestamp
            }

            # Store metric
            if metric_type in self.metrics:
                self.metrics[metric_type].append(metric)
            else:
                self.metrics[metric_type] = [metric]

            # Clean old data based on retention policy
            self._cleanup_old_metrics()

            # Auto-learn if enabled
            if self.config['auto_learning']:
                self._auto_learn(metric)

            return {
                'success': True,
                'message': f'Metric {metric_name} collected successfully',
                'timestamp': timestamp
            }

        except Exception as exc:
            logger.error(f"Error in collect_metric: {exc}")
            return {
                'success': False,
                'error': str(exc),
                'timestamp': timestamp
            }

    def get_metrics(
        self,
        metric_type: Optional[str] = None,
        metric_name: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        limit: int = 100
    ) -> Dict:
        """
        Retrieve telemetry metrics with optional filtering.

        Args:
            metric_type: Filter by metric type
            metric_name: Filter by metric name
            start_time: Filter by start time (ISO format)
            end_time: Filter by end time (ISO format)
            limit: Maximum number of metrics to return

        Returns:
            Dict with filtered metrics
        """
        try:
            filtered = []

            # Iterate through all metric types or specific type
            types_to_search = [metric_type] if metric_type else self.metrics.keys()

            for mtype in types_to_search:
                if mtype not in self.metrics:
                    continue

                for metric in self.metrics[mtype]:
                    # Filter by metric name
                    if metric_name and metric['metric_name'] != metric_name:
                        continue

                    # Filter by time range
                    if start_time and metric['timestamp'] < start_time:
                        continue
                    if end_time and metric['timestamp'] > end_time:
                        continue

                    filtered.append(metric)

            # Apply limit
            filtered = filtered[-limit:]

            return {
                'success': True,
                'metrics': filtered,
                'count': len(filtered)
            }

        except Exception as exc:
            logger.error(f"Error in get_metrics: {exc}")
            return {
                'success': False,
                'error': str(exc),
                'metrics': [],
                'count': 0
            }

    def detect_anomalies(
        self,
        metric_type: Optional[str] = None,
        metric_name: Optional[str] = None,
        threshold: Optional[float] = None
    ) -> Dict:
        """
        Detect anomalies in telemetry data.

        Args:
            metric_type: Filter by metric type
            metric_name: Filter by metric name
            threshold: Anomaly threshold (standard deviations from mean)

        Returns:
            Dict with detected anomalies
        """
        try:
            if threshold is None:
                threshold = self.config['anomaly_threshold']

            anomalies = []

            # Get metrics
            metrics_result = self.get_metrics(
                metric_type=metric_type,
                metric_name=metric_name,
                limit=1000
            )

            if not metrics_result['success']:
                return metrics_result

            metrics = metrics_result['metrics']

            if len(metrics) < 10:
                return {
                    'success': True,
                    'anomalies': [],
                    'message': 'Insufficient data for anomaly detection',
                    'count': 0
                }

            # Group by metric name
            metric_groups = {}
            for metric in metrics:
                name = metric['metric_name']
                if name not in metric_groups:
                    metric_groups[name] = []
                metric_groups[name].append(metric['value'])

            # Detect anomalies for each metric
            for name, values in metric_groups.items():
                if len(values) < 10:
                    continue

                # Calculate statistics
                mean_val = sum(values) / len(values)
                variance = sum((x - mean_val) ** 2 for x in values) / (len(values) or 1)
                std_dev = variance ** 0.5 if variance > 0 else 0

                # Find anomalies (values > threshold standard deviations from mean)
                for metric in metrics:
                    if metric['metric_name'] != name:
                        continue

                    value = metric['value']
                    if std_dev > 0:
                        z_score = abs((value - mean_val) / std_dev)
                        if z_score > threshold:
                            anomaly = {
                                'metric_name': name,
                                'value': value,
                                'mean': round(mean_val, 4),
                                'std_dev': round(std_dev, 4),
                                'z_score': round(z_score, 4),
                                'threshold': threshold,
                                'timestamp': metric['timestamp'],
                                'severity': 'high' if z_score > threshold * 1.5 else 'medium'
                            }
                            anomalies.append(anomaly)

            # Store anomalies
            self.anomalies.extend(anomalies)

            return {
                'success': True,
                'anomalies': anomalies,
                'count': len(anomalies),
                'threshold_used': threshold
            }

        except Exception as exc:
            logger.error(f"Error in detect_anomalies: {exc}")
            return {
                'success': False,
                'error': str(exc),
                'anomalies': [],
                'count': 0
            }

    def discover_patterns(
        self,
        min_confidence: Optional[float] = None
    ) -> Dict:
        """
        Discover patterns in telemetry data.

        Args:
            min_confidence: Minimum confidence for pattern discovery

        Returns:
            Dict with discovered patterns
        """
        try:
            if min_confidence is None:
                min_confidence = self.config['pattern_min_confidence']

            patterns = []

            # Analyze performance metrics
            if 'performance' in self.metrics and len(self.metrics['performance']) >= 20:
                perf_patterns = self._analyze_performance_patterns()
                patterns.extend(perf_patterns)

            # Analyze error patterns
            if 'errors' in self.metrics and len(self.metrics['errors']) >= 10:
                error_patterns = self._analyze_error_patterns()
                patterns.extend(error_patterns)

            # Filter by confidence
            patterns = [p for p in patterns if p.get('confidence', 0) >= min_confidence]

            # Store patterns
            self.patterns = patterns

            return {
                'success': True,
                'patterns': patterns,
                'count': len(patterns),
                'min_confidence_used': min_confidence
            }

        except Exception as exc:
            logger.error(f"Error in discover_patterns: {exc}")
            return {
                'success': False,
                'error': str(exc),
                'patterns': [],
                'count': 0
            }

    def generate_recommendations(
        self,
        focus_area: Optional[str] = None
    ) -> Dict:
        """
        Generate optimization recommendations based on telemetry data.

        Args:
            focus_area: Focus area for recommendations (performance, reliability, security, etc.)

        Returns:
            Dict with recommendations
        """
        try:
            recommendations = []

            # Performance recommendations
            if focus_area in [None, 'performance']:
                perf_recs = self._generate_performance_recommendations()
                recommendations.extend(perf_recs)

            # Reliability recommendations
            if focus_area in [None, 'reliability']:
                rel_recs = self._generate_reliability_recommendations()
                recommendations.extend(rel_recs)

            # Security recommendations
            if focus_area in [None, 'security']:
                sec_recs = self._generate_security_recommendations()
                recommendations.extend(sec_recs)

            # Store recommendations
            self.recommendations = recommendations

            return {
                'success': True,
                'recommendations': recommendations,
                'count': len(recommendations),
                'focus_area': focus_area or 'all'
            }

        except Exception as exc:
            logger.error(f"Error in generate_recommendations: {exc}")
            return {
                'success': False,
                'error': str(exc),
                'recommendations': [],
                'count': 0
            }

    def get_telemetry_summary(self) -> Dict:
        """
        Get comprehensive telemetry summary.

        Returns:
            Dict with telemetry summary statistics
        """
        try:
            summary = {
                'metrics_collected': {},
                'anomalies_detected': len(self.anomalies),
                'patterns_discovered': len(self.patterns),
                'recommendations_generated': len(self.recommendations),
                'baselines_established': len(self.baselines),
                'enabled': self.enabled
            }

            # Count metrics by type
            for metric_type, metrics in self.metrics.items():
                summary['metrics_collected'][metric_type] = len(metrics)

            # Calculate total
            summary['total_metrics'] = sum(summary['metrics_collected'].values())

            # Add configuration
            summary['config'] = self.config.copy()

            return summary

        except Exception as exc:
            logger.error(f"Error in get_telemetry_summary: {exc}")
            return {
                'error': str(exc),
                'enabled': self.enabled
            }

    def update_config(self, config: Dict) -> Dict:
        """
        Update telemetry adapter configuration.

        Args:
            config: Configuration updates

        Returns:
            Dict with updated configuration
        """
        try:
            self.config.update(config)
            return {
                'success': True,
                'config': self.config.copy(),
                'message': 'Configuration updated successfully'
            }
        except Exception as exc:
            logger.error(f"Error in update_config: {exc}")
            return {
                'success': False,
                'error': str(exc),
                'config': self.config.copy()
            }

    def clear_metrics(self, metric_type: Optional[str] = None) -> Dict:
        """
        Clear collected metrics.

        Args:
            metric_type: Specific metric type to clear, or None for all

        Returns:
            Dict with clear status
        """
        try:
            if metric_type:
                if metric_type in self.metrics:
                    count = len(self.metrics[metric_type])
                    self.metrics[metric_type] = []
                    return {
                        'success': True,
                        'message': f'Cleared {count} {metric_type} metrics',
                        'cleared_count': count
                    }
                else:
                    return {
                        'success': False,
                        'message': f'Metric type {metric_type} not found',
                        'cleared_count': 0
                    }
            else:
                total = sum(len(m) for m in self.metrics.values())
                self.metrics = {k: [] for k in self.metrics.keys()}
                return {
                    'success': True,
                    'message': f'Cleared {total} metrics',
                    'cleared_count': total
                }
        except Exception as exc:
            logger.error(f"Error in clear_metrics: {exc}")
            return {
                'success': False,
                'error': str(exc),
                'cleared_count': 0
            }

    # ========== Private Helper Methods ==========

    def _cleanup_old_metrics(self):
        """Clean up metrics older than retention period"""
        retention_hours = self.config.get('data_retention_hours', 24)
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=retention_hours)
        cutoff_str = cutoff_time.isoformat()

        for metric_type in self.metrics:
            self.metrics[metric_type] = [
                m for m in self.metrics[metric_type]
                if m['timestamp'] >= cutoff_str
            ]

    def _auto_learn(self, metric: Dict):
        """Auto-learn from collected metric"""
        metric_name = metric['metric_name']
        value = metric['value']

        # Update baseline (simple moving average)
        if metric_name not in self.baselines:
            self.baselines[metric_name] = value
        else:
            # Update baseline with 0.1 learning rate
            self.baselines[metric_name] = (
                0.9 * self.baselines[metric_name] + 0.1 * value
            )

    def _analyze_performance_patterns(self) -> List[Dict]:
        """Analyze performance metrics for patterns"""
        patterns = []

        try:
            perf_metrics = self.metrics.get('performance', [])
            if len(perf_metrics) < 20:
                return patterns

            # Group by metric name
            metric_groups = {}
            for m in perf_metrics:
                name = m['metric_name']
                if name not in metric_groups:
                    metric_groups[name] = []
                metric_groups[name].append(m['value'])

            # Analyze trends
            for name, values in metric_groups.items():
                if len(values) < 20:
                    continue

                # Calculate trend (simple linear regression)
                n = len(values)
                x_values = list(range(n))

                # Calculate slope
                sum_x = sum(x_values)
                sum_y = sum(values)
                sum_xy = sum(x * y for x, y in zip(x_values, values))
                sum_x2 = sum(x ** 2 for x in x_values)

                denominator = n * sum_x2 - sum_x ** 2
                if denominator != 0:
                    slope = (n * sum_xy - sum_x * sum_y) / denominator
                else:
                    slope = 0

                # Determine pattern
                if slope > 0.1:
                    trend = 'increasing'
                    pattern_type = 'performance_degradation'
                elif slope < -0.1:
                    trend = 'decreasing'
                    pattern_type = 'performance_improvement'
                else:
                    trend = 'stable'
                    pattern_type = 'performance_stable'

                confidence = min(1.0, abs(slope) * 5)

                pattern = {
                    'pattern_type': pattern_type,
                    'metric_name': name,
                    'trend': trend,
                    'slope': round(slope, 4),
                    'confidence': round(confidence, 4),
                    'description': f"{name} is showing {trend} trend"
                }

                patterns.append(pattern)

        except Exception as exc:
            logger.error(f"Error in _analyze_performance_patterns: {exc}")

        return patterns

    def _analyze_error_patterns(self) -> List[Dict]:
        """Analyze error metrics for patterns"""
        patterns = []

        try:
            error_metrics = self.metrics.get('errors', [])
            if len(error_metrics) < 10:
                return patterns

            # Count errors by type
            error_counts = {}
            for m in error_metrics:
                error_type = m['labels'].get('error_type', 'unknown')
                error_counts[error_type] = error_counts.get(error_type, 0) + 1

            total_errors = len(error_metrics)

            # Identify frequent errors
            for error_type, count in error_counts.items():
                frequency = count / total_errors if total_errors > 0 else 0.0

                if frequency >= 0.1:  # 10% or more
                    pattern = {
                        'pattern_type': 'frequent_error',
                        'error_type': error_type,
                        'frequency': round(frequency, 4),
                        'count': count,
                        'confidence': round(frequency, 4),
                        'description': f"Error type '{error_type}' occurs {frequency*100:.1f}% of the time"
                    }
                    patterns.append(pattern)

        except Exception as exc:
            logger.error(f"Error in _analyze_error_patterns: {exc}")

        return patterns

    def _generate_performance_recommendations(self) -> List[Dict]:
        """Generate performance optimization recommendations"""
        recommendations = []

        try:
            # Check for performance degradation patterns
            for pattern in self.patterns:
                if pattern.get('pattern_type') == 'performance_degradation':
                    metric_name = pattern.get('metric_name')
                    recommendations.append({
                        'category': 'performance',
                        'priority': 'high' if pattern.get('confidence', 0) > 0.8 else 'medium',
                        'recommendation': f"Investigate {metric_name} degradation",
                        'details': f"{metric_name} is showing increasing trend with {pattern.get('confidence', 0):.1%} confidence",
                        'action': 'Analyze recent changes and optimize affected components'
                    })

        except Exception as exc:
            logger.error(f"Error in _generate_performance_recommendations: {exc}")

        return recommendations

    def _generate_reliability_recommendations(self) -> List[Dict]:
        """Generate reliability improvement recommendations"""
        recommendations = []

        try:
            # Check for frequent errors
            for pattern in self.patterns:
                if pattern.get('pattern_type') == 'frequent_error':
                    error_type = pattern.get('error_type')
                    frequency = pattern.get('frequency', 0)
                    recommendations.append({
                        'category': 'reliability',
                        'priority': 'high' if frequency > 0.2 else 'medium',
                        'recommendation': f"Address frequent error: {error_type}",
                        'details': f"Error type '{error_type}' occurs {frequency*100:.1f}% of all errors",
                        'action': 'Add error handling or fix root cause'
                    })

            # Check anomalies
            if len(self.anomalies) > 5:
                recommendations.append({
                    'category': 'reliability',
                    'priority': 'medium',
                    'recommendation': 'Investigate detected anomalies',
                    'details': f'{len(self.anomalies)} anomalies detected in telemetry data',
                    'action': 'Review anomalies and adjust system behavior'
                })

        except Exception as exc:
            logger.error(f"Error in _generate_reliability_recommendations: {exc}")

        return recommendations

    def _generate_security_recommendations(self) -> List[Dict]:
        """Generate security recommendations"""
        recommendations = []

        try:
            # Check for unusual error patterns
            error_metrics = self.metrics.get('errors', [])
            security_errors = [
                m for m in error_metrics
                if 'security' in m.get('metric_name', '').lower() or
                'security' in m.get('labels', {}).get('error_type', '').lower()
            ]

            if len(security_errors) > 0:
                recommendations.append({
                    'category': 'security',
                    'priority': 'high',
                    'recommendation': 'Review security-related errors',
                    'details': f'{len(security_errors)} security errors detected',
                    'action': 'Investigate security errors and implement fixes'
                })

        except Exception as exc:
            logger.error(f"Error in _generate_security_recommendations: {exc}")

        return recommendations
