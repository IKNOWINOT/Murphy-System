"""Behavioral anomaly detection for bots in the Murphy System."""
# Copyright © 2020 Inoni Limited Liability Company

from __future__ import annotations

import logging
import math
import statistics
import threading
import uuid
from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)


class AnomalyType(str, Enum):
    """Types of anomalies detected in bot behavior."""
    RESPONSE_TIME_SPIKE = "response_time_spike"
    API_CALL_SURGE = "api_call_surge"
    ERROR_RATE_SPIKE = "error_rate_spike"
    TOKEN_CONSUMPTION_SPIKE = "token_consumption_spike"
    COMMUNICATION_VOLUME_SPIKE = "communication_volume_spike"
    RESOURCE_SPIKE = "resource_spike"
    UNUSUAL_API_PATTERN = "unusual_api_pattern"


class AlertSeverity(str, Enum):
    """Severity levels for anomaly alerts."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class BotMetrics:
    """Rolling-window metric store for a single bot."""
    bot_id: str
    response_times: deque
    api_call_counts: deque
    error_counts: deque
    token_usage: deque
    communication_volumes: deque
    memory_usage: deque
    cpu_usage: deque
    api_patterns: deque

    @classmethod
    def create(cls, bot_id: str, window_size: int) -> BotMetrics:
        return cls(
            bot_id=bot_id,
            response_times=deque(maxlen=window_size),
            api_call_counts=deque(maxlen=window_size),
            error_counts=deque(maxlen=window_size),
            token_usage=deque(maxlen=window_size),
            communication_volumes=deque(maxlen=window_size),
            memory_usage=deque(maxlen=window_size),
            cpu_usage=deque(maxlen=window_size),
            api_patterns=deque(maxlen=window_size),
        )


@dataclass
class AnomalyAlert:
    """An alert raised when a bot metric deviates from its baseline."""
    alert_id: str
    bot_id: str
    anomaly_type: AnomalyType
    severity: AlertSeverity
    z_score: float
    current_value: float
    baseline_mean: float
    baseline_std: float
    timestamp: datetime
    context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "bot_id": self.bot_id,
            "anomaly_type": self.anomaly_type.value,
            "severity": self.severity.value,
            "z_score": round(self.z_score, 4),
            "current_value": round(self.current_value, 4),
            "baseline_mean": round(self.baseline_mean, 4),
            "baseline_std": round(self.baseline_std, 4),
            "timestamp": self.timestamp.isoformat(),
            "context": self.context,
        }


class BotAnomalyDetector:
    """Detects anomalous bot behavior using statistical analysis."""

    def __init__(
        self,
        window_size: int = 100,
        z_score_threshold: float = 3.0,
        spike_multiplier: float = 2.0,
        min_samples: int = 10,
        max_alerts: int = 10000,
    ) -> None:
        self._window_size = window_size
        self._z_score_threshold = z_score_threshold
        self._spike_multiplier = spike_multiplier
        self._min_samples = min_samples
        self._max_alerts = max_alerts

        self._metrics: Dict[str, BotMetrics] = {}
        self._alerts: deque = deque(maxlen=max_alerts)
        self._lock = threading.Lock()
        self._total_alerts_generated = 0
        logger.info(
            "BotAnomalyDetector initialised (window=%d, z=%.1f, spike=%.1f)",
            window_size,
            z_score_threshold,
            spike_multiplier,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record_metric(
        self,
        bot_id: str,
        response_time: Optional[float] = None,
        api_calls: Optional[int] = None,
        errors: Optional[int] = None,
        tokens: Optional[int] = None,
        communications: Optional[int] = None,
        memory_mb: Optional[float] = None,
        cpu_percent: Optional[float] = None,
        api_endpoint: Optional[str] = None,
    ) -> List[AnomalyAlert]:
        """Record metrics for *bot_id* and return any detected anomalies."""
        alerts: List[AnomalyAlert] = []
        with self._lock:
            metrics = self._ensure_metrics(bot_id)

            if response_time is not None:
                metrics.response_times.append(response_time)
                alert = self._check_z_score(
                    list(metrics.response_times), response_time,
                    bot_id, AnomalyType.RESPONSE_TIME_SPIKE,
                )
                if alert:
                    alerts.append(alert)

            if api_calls is not None:
                metrics.api_call_counts.append(api_calls)
                alert = self._check_z_score(
                    [float(v) for v in metrics.api_call_counts], float(api_calls),
                    bot_id, AnomalyType.API_CALL_SURGE,
                )
                if alert:
                    alerts.append(alert)

            if errors is not None:
                metrics.error_counts.append(errors)
                alert = self._check_z_score(
                    [float(v) for v in metrics.error_counts], float(errors),
                    bot_id, AnomalyType.ERROR_RATE_SPIKE,
                )
                if alert:
                    alerts.append(alert)

            if tokens is not None:
                metrics.token_usage.append(tokens)
                alert = self._check_z_score(
                    [float(v) for v in metrics.token_usage], float(tokens),
                    bot_id, AnomalyType.TOKEN_CONSUMPTION_SPIKE,
                )
                if alert:
                    alerts.append(alert)

            if communications is not None:
                metrics.communication_volumes.append(communications)
                alert = self._check_z_score(
                    [float(v) for v in metrics.communication_volumes],
                    float(communications),
                    bot_id, AnomalyType.COMMUNICATION_VOLUME_SPIKE,
                )
                if alert:
                    alerts.append(alert)

            if memory_mb is not None:
                metrics.memory_usage.append(memory_mb)
            if cpu_percent is not None:
                metrics.cpu_usage.append(cpu_percent)

            if api_endpoint is not None:
                metrics.api_patterns.append(api_endpoint)
                pattern_alert = self._check_api_pattern(bot_id)
                if pattern_alert:
                    alerts.append(pattern_alert)

            alerts.extend(self._check_resource_spike(bot_id))

            for alert in alerts:
                capped_append(self._alerts, alert)
                self._total_alerts_generated += 1
                logger.warning(
                    "Anomaly [%s] for bot %s — z=%.2f severity=%s",
                    alert.anomaly_type.value, bot_id,
                    alert.z_score, alert.severity.value,
                )
        return alerts

    def get_alerts(
        self,
        bot_id: Optional[str] = None,
        severity: Optional[AlertSeverity] = None,
        anomaly_type: Optional[AnomalyType] = None,
        limit: int = 100,
    ) -> List[AnomalyAlert]:
        """Return stored alerts, optionally filtered."""
        with self._lock:
            results = list(self._alerts)
        if bot_id is not None:
            results = [a for a in results if a.bot_id == bot_id]
        if severity is not None:
            results = [a for a in results if a.severity == severity]
        if anomaly_type is not None:
            results = [a for a in results if a.anomaly_type == anomaly_type]
        return results[-limit:]

    def get_bot_baseline(self, bot_id: str) -> Optional[Dict[str, Any]]:
        """Return baseline statistics for *bot_id*, or ``None``."""
        with self._lock:
            metrics = self._metrics.get(bot_id)
            if metrics is None:
                return None
            return self._compute_baseline(metrics)

    def clear_bot_data(self, bot_id: str) -> None:
        """Remove all metric history for *bot_id*."""
        with self._lock:
            self._metrics.pop(bot_id, None)
            logger.info("Cleared metric data for bot %s", bot_id)

    def get_stats(self) -> Dict[str, Any]:
        """Return high-level detector statistics."""
        with self._lock:
            return {
                "tracked_bots": len(self._metrics),
                "total_alerts": self._total_alerts_generated,
                "stored_alerts": len(self._alerts),
                "window_size": self._window_size,
                "z_score_threshold": self._z_score_threshold,
                "spike_multiplier": self._spike_multiplier,
                "min_samples": self._min_samples,
            }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_metrics(self, bot_id: str) -> BotMetrics:
        if bot_id not in self._metrics:
            self._metrics[bot_id] = BotMetrics.create(bot_id, self._window_size)
            logger.debug("Tracking new bot %s", bot_id)
        return self._metrics[bot_id]

    def _check_z_score(
        self,
        values: List[float],
        current: float,
        bot_id: str,
        anomaly_type: AnomalyType,
    ) -> Optional[AnomalyAlert]:
        """Return an alert if *current* deviates beyond the z-score threshold."""
        if len(values) < self._min_samples:
            return None
        mean = statistics.mean(values)
        std = statistics.stdev(values) if len(values) >= 2 else 0.0
        if std == 0.0:
            return None
        z = (current - mean) / std
        if abs(z) < self._z_score_threshold:
            return None
        severity = self._severity_from_z(abs(z))
        return AnomalyAlert(
            alert_id=uuid.uuid4().hex,
            bot_id=bot_id,
            anomaly_type=anomaly_type,
            severity=severity,
            z_score=z,
            current_value=current,
            baseline_mean=mean,
            baseline_std=std,
            timestamp=datetime.now(timezone.utc),
            context={"sample_count": len(values)},
        )

    def _check_resource_spike(self, bot_id: str) -> List[AnomalyAlert]:
        """Flag sudden increases in memory or CPU usage."""
        alerts: List[AnomalyAlert] = []
        metrics = self._metrics.get(bot_id)
        if metrics is None:
            return alerts
        for label, series in [("memory_mb", metrics.memory_usage),
                              ("cpu_percent", metrics.cpu_usage)]:
            vals = list(series)
            if len(vals) < self._min_samples:
                continue
            mean = statistics.mean(vals)
            if mean == 0.0:
                continue
            current = vals[-1]
            if current > mean * self._spike_multiplier:
                std = statistics.stdev(vals) if len(vals) >= 2 else 0.0
                if std == 0.0:
                    continue
                z = (current - mean) / std
                alerts.append(AnomalyAlert(
                    alert_id=uuid.uuid4().hex,
                    bot_id=bot_id,
                    anomaly_type=AnomalyType.RESOURCE_SPIKE,
                    severity=self._severity_from_z(abs(z)),
                    z_score=z,
                    current_value=current,
                    baseline_mean=mean,
                    baseline_std=std,
                    timestamp=datetime.now(timezone.utc),
                    context={"resource": label, "sample_count": len(vals)},
                ))
        return alerts

    def _check_api_pattern(self, bot_id: str) -> Optional[AnomalyAlert]:
        """Detect unusual API call sequences via bigram frequency analysis."""
        metrics = self._metrics.get(bot_id)
        if metrics is None or len(metrics.api_patterns) < self._min_samples:
            return None
        patterns = list(metrics.api_patterns)
        bigrams = [f"{patterns[i]}->{patterns[i+1]}" for i in range(len(patterns) - 1)]
        if len(bigrams) < 2:
            return None
        counts = Counter(bigrams)
        freqs = list(counts.values())
        mean_freq = statistics.mean(freqs)
        std_freq = statistics.stdev(freqs) if len(freqs) >= 2 else 0.0
        latest_bigram = bigrams[-1]
        latest_freq = counts[latest_bigram]
        if std_freq == 0.0:
            return None
        z = (latest_freq - mean_freq) / std_freq
        if abs(z) < self._z_score_threshold:
            return None
        return AnomalyAlert(
            alert_id=uuid.uuid4().hex,
            bot_id=bot_id,
            anomaly_type=AnomalyType.UNUSUAL_API_PATTERN,
            severity=self._severity_from_z(abs(z)),
            z_score=z,
            current_value=float(latest_freq),
            baseline_mean=mean_freq,
            baseline_std=std_freq,
            timestamp=datetime.now(timezone.utc),
            context={"bigram": latest_bigram, "unique_bigrams": len(counts)},
        )

    @staticmethod
    def _severity_from_z(z: float) -> AlertSeverity:
        if z >= 5.0:
            return AlertSeverity.CRITICAL
        if z >= 4.0:
            return AlertSeverity.HIGH
        if z >= 3.0:
            return AlertSeverity.MEDIUM
        return AlertSeverity.LOW

    @staticmethod
    def _compute_baseline(metrics: BotMetrics) -> Dict[str, Any]:
        """Compute mean/std summaries for every metric series."""
        def _summarise(vals: list) -> Dict[str, float]:
            if not vals:
                return {"mean": 0.0, "std": 0.0, "count": 0}
            m = statistics.mean(vals)
            s = statistics.stdev(vals) if len(vals) >= 2 else 0.0
            return {"mean": round(m, 4), "std": round(s, 4), "count": len(vals)}

        return {
            "bot_id": metrics.bot_id,
            "response_times": _summarise([float(v) for v in metrics.response_times]),
            "api_call_counts": _summarise([float(v) for v in metrics.api_call_counts]),
            "error_counts": _summarise([float(v) for v in metrics.error_counts]),
            "token_usage": _summarise([float(v) for v in metrics.token_usage]),
            "communication_volumes": _summarise([float(v) for v in metrics.communication_volumes]),
            "memory_usage": _summarise([float(v) for v in metrics.memory_usage]),
            "cpu_usage": _summarise([float(v) for v in metrics.cpu_usage]),
            "api_patterns_count": len(metrics.api_patterns),
        }
