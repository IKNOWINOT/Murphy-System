"""
Continuous Monitoring Dashboard

This module implements real-time monitoring and alerting for the shadow agent.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Real-time performance metrics"""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Prediction metrics
    total_predictions: int = 0
    successful_predictions: int = 0
    failed_predictions: int = 0

    # Accuracy metrics
    accuracy: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0

    # Confidence metrics
    avg_confidence: float = 0.0
    high_confidence_rate: float = 0.0
    low_confidence_rate: float = 0.0

    # Performance metrics
    avg_response_time_ms: float = 0.0
    p95_response_time_ms: float = 0.0
    p99_response_time_ms: float = 0.0

    # Error metrics
    error_rate: float = 0.0
    timeout_rate: float = 0.0

    # Resource metrics
    cpu_usage: float = 0.0
    memory_usage_mb: float = 0.0

    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Alert:
    """Alert for monitoring issues"""
    id: UUID = field(default_factory=uuid4)
    severity: str = "warning"  # info, warning, error, critical
    title: str = ""
    message: str = ""
    metric_name: str = ""
    metric_value: float = 0.0
    threshold: float = 0.0

    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: Optional[datetime] = None
    is_resolved: bool = False

    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MonitoringConfig:
    """Configuration for monitoring"""
    # Metric collection
    collection_interval_seconds: int = 60
    retention_days: int = 30

    # Alerting thresholds
    accuracy_threshold: float = 0.7
    error_rate_threshold: float = 0.1
    response_time_threshold_ms: float = 1000

    # Alert settings
    alert_cooldown_minutes: int = 15
    max_alerts_per_hour: int = 10

    # Notification channels
    notification_channels: List[str] = field(default_factory=list)

    metadata: Dict[str, Any] = field(default_factory=dict)


class MonitoringDashboard:
    """Real-time monitoring dashboard"""

    def __init__(self, config: Optional[MonitoringConfig] = None):
        self.config = config or MonitoringConfig()

        self.metrics_history: List[PerformanceMetrics] = []
        self.active_alerts: List[Alert] = []
        self.alert_history: List[Alert] = []

        self.last_alert_time: Dict[str, datetime] = {}

    def record_metrics(self, metrics: PerformanceMetrics):
        """Record performance metrics"""

        self.metrics_history.append(metrics)

        # Trim old metrics
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=self.config.retention_days)
        self.metrics_history = [
            m for m in self.metrics_history
            if m.timestamp > cutoff_date
        ]

        # Check for alerts
        self._check_alerts(metrics)

    def get_current_metrics(self) -> Optional[PerformanceMetrics]:
        """Get most recent metrics"""

        if not self.metrics_history:
            return None

        return self.metrics_history[-1]

    def get_metrics_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get summary of metrics over time period"""

        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        recent_metrics = [
            m for m in self.metrics_history
            if m.timestamp > cutoff
        ]

        if not recent_metrics:
            return {}

        return {
            "time_period_hours": hours,
            "total_predictions": sum(m.total_predictions for m in recent_metrics),
            "avg_accuracy": sum(m.accuracy for m in recent_metrics) / (len(recent_metrics) or 1),
            "avg_response_time_ms": sum(m.avg_response_time_ms for m in recent_metrics) / (len(recent_metrics) or 1),
            "avg_error_rate": sum(m.error_rate for m in recent_metrics) / (len(recent_metrics) or 1),
            "total_alerts": len([a for a in self.alert_history if a.created_at > cutoff]),
        }

    def get_trend_analysis(self, metric_name: str, hours: int = 24) -> Dict[str, Any]:
        """Analyze trend for a specific metric"""

        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        recent_metrics = [
            m for m in self.metrics_history
            if m.timestamp > cutoff
        ]

        if not recent_metrics:
            return {}

        # Get metric values
        values = []
        for m in recent_metrics:
            if hasattr(m, metric_name):
                values.append(getattr(m, metric_name))

        if not values:
            return {}

        # Calculate trend
        first_half = values[:len(values)//2]
        second_half = values[len(values)//2:]

        avg_first = sum(first_half) / (len(first_half) or 1) if first_half else 0
        avg_second = sum(second_half) / (len(second_half) or 1) if second_half else 0

        trend = "improving" if avg_second > avg_first else "declining" if avg_second < avg_first else "stable"
        change_pct = ((avg_second - avg_first) / avg_first * 100) if avg_first > 0 else 0

        return {
            "metric_name": metric_name,
            "current_value": values[-1],
            "avg_value": sum(values) / (len(values) or 1),
            "min_value": min(values),
            "max_value": max(values),
            "trend": trend,
            "change_percentage": change_pct,
        }

    def _check_alerts(self, metrics: PerformanceMetrics):
        """Check if any alerts should be triggered"""

        # Check accuracy
        if metrics.accuracy < self.config.accuracy_threshold:
            self._create_alert(
                severity="warning",
                title="Low Accuracy",
                message=f"Model accuracy ({metrics.accuracy:.2%}) below threshold ({self.config.accuracy_threshold:.2%})",
                metric_name="accuracy",
                metric_value=metrics.accuracy,
                threshold=self.config.accuracy_threshold,
            )

        # Check error rate
        if metrics.error_rate > self.config.error_rate_threshold:
            self._create_alert(
                severity="error",
                title="High Error Rate",
                message=f"Error rate ({metrics.error_rate:.2%}) above threshold ({self.config.error_rate_threshold:.2%})",
                metric_name="error_rate",
                metric_value=metrics.error_rate,
                threshold=self.config.error_rate_threshold,
            )

        # Check response time
        if metrics.avg_response_time_ms > self.config.response_time_threshold_ms:
            self._create_alert(
                severity="warning",
                title="Slow Response Time",
                message=f"Response time ({metrics.avg_response_time_ms:.0f}ms) above threshold ({self.config.response_time_threshold_ms:.0f}ms)",
                metric_name="avg_response_time_ms",
                metric_value=metrics.avg_response_time_ms,
                threshold=self.config.response_time_threshold_ms,
            )

    def _create_alert(
        self,
        severity: str,
        title: str,
        message: str,
        metric_name: str,
        metric_value: float,
        threshold: float
    ):
        """Create a new alert"""

        # Check cooldown
        if metric_name in self.last_alert_time:
            time_since_last = datetime.now(timezone.utc) - self.last_alert_time[metric_name]
            if time_since_last < timedelta(minutes=self.config.alert_cooldown_minutes):
                return

        # Create alert
        alert = Alert(
            severity=severity,
            title=title,
            message=message,
            metric_name=metric_name,
            metric_value=metric_value,
            threshold=threshold,
        )

        self.active_alerts.append(alert)
        self.alert_history.append(alert)
        self.last_alert_time[metric_name] = datetime.now(timezone.utc)

        logger.warning(f"Alert created: {title} - {message}")

        # Send notifications
        self._send_notifications(alert)

    def resolve_alert(self, alert_id: UUID):
        """Resolve an alert"""

        for alert in self.active_alerts:
            if alert.id == alert_id:
                alert.is_resolved = True
                alert.resolved_at = datetime.now(timezone.utc)
                self.active_alerts.remove(alert)
                logger.info(f"Alert resolved: {alert.title}")
                break

    def _send_notifications(self, alert: Alert):
        """Send alert notifications"""

        # In production, would send to configured channels
        # (email, Slack, PagerDuty, etc.)
        logger.info(f"Notification sent for alert: {alert.title}")

    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get complete dashboard data"""

        current_metrics = self.get_current_metrics()
        summary_24h = self.get_metrics_summary(hours=24)

        return {
            "current_metrics": current_metrics.__dict__ if current_metrics else {},
            "summary_24h": summary_24h,
            "active_alerts": [
                {
                    "id": str(a.id),
                    "severity": a.severity,
                    "title": a.title,
                    "message": a.message,
                    "created_at": a.created_at.isoformat(),
                }
                for a in self.active_alerts
            ],
            "trends": {
                "accuracy": self.get_trend_analysis("accuracy", hours=24),
                "response_time": self.get_trend_analysis("avg_response_time_ms", hours=24),
                "error_rate": self.get_trend_analysis("error_rate", hours=24),
            },
        }


class FeedbackLoop:
    """Implements continuous feedback loop for model improvement"""

    def __init__(self):
        self.feedback_queue: List[Dict[str, Any]] = []
        self.improvement_history: List[Dict[str, Any]] = []

    def collect_feedback(
        self,
        prediction_id: UUID,
        actual_outcome: Any,
        was_correct: bool,
        user_feedback: Optional[str] = None
    ):
        """Collect feedback on a prediction"""

        feedback = {
            "prediction_id": str(prediction_id),
            "actual_outcome": actual_outcome,
            "was_correct": was_correct,
            "user_feedback": user_feedback,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        self.feedback_queue.append(feedback)

        logger.info(f"Feedback collected: correct={was_correct}")

    def process_feedback_batch(self) -> Dict[str, Any]:
        """Process batch of feedback for model improvement"""

        if not self.feedback_queue:
            return {"processed": 0}

        # Analyze feedback
        total = len(self.feedback_queue)
        correct = sum(1 for f in self.feedback_queue if f["was_correct"])
        accuracy = correct / total if total > 0 else 0

        # Identify improvement opportunities
        incorrect_predictions = [
            f for f in self.feedback_queue if not f["was_correct"]
        ]

        improvement_summary = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_feedback": total,
            "accuracy": accuracy,
            "incorrect_predictions": len(incorrect_predictions),
            "improvement_opportunities": self._identify_improvements(incorrect_predictions),
        }

        self.improvement_history.append(improvement_summary)

        # Clear queue
        self.feedback_queue = []

        logger.info(f"Processed {total} feedback items, accuracy: {accuracy:.2%}")

        return improvement_summary

    def _identify_improvements(self, incorrect_predictions: List[Dict]) -> List[str]:
        """Identify improvement opportunities from incorrect predictions"""

        opportunities = []

        if len(incorrect_predictions) > 10:
            opportunities.append("High error rate - consider retraining model")

        # Analyze patterns in errors
        # In production, would do more sophisticated analysis

        return opportunities

    def get_improvement_recommendations(self) -> List[str]:
        """Get recommendations for model improvement"""

        if not self.improvement_history:
            return ["Collect more feedback data"]

        recent = self.improvement_history[-1]
        recommendations = []

        if recent["accuracy"] < 0.8:
            recommendations.append("Model accuracy below 80% - retrain with recent corrections")

        if recent["incorrect_predictions"] > 50:
            recommendations.append("High number of errors - review feature engineering")

        recommendations.extend(recent.get("improvement_opportunities", []))

        return recommendations
