"""
Alert Rules Engine for Murphy System.

Design Label: SAF-004 — Configurable Alert Rules with Severity & Cooldown
Owner: DevOps Team / Platform Engineering
Dependencies:
  - PersistenceManager (for durable alert history)
  - EventBackbone (publishes SYSTEM_HEALTH on triggered alerts)

Implements Plan §6.3 — Monitoring and Alerting:
  Evaluates configurable alert rules against observed metric values.
  Rules have severity (CRITICAL / WARNING / INFO), a threshold
  comparator (gt / lt / gte / lte / eq), a cooldown period to prevent
  duplicate alerts, and an optional description.

Flow:
  1. Define alert rules with name, severity, metric, comparator, threshold
  2. Evaluate rules against metric snapshots
  3. Fire alerts for rules whose conditions are met
  4. Apply cooldown to prevent duplicate alerts
  5. Persist fired alerts and publish events

Safety invariants:
  - Thread-safe: all shared state guarded by Lock
  - Bounded: configurable max alert history
  - Cooldown: prevents alert storms
  - Audit trail: every fired alert is logged

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_ALERTS = 10_000


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class AlertSeverity(str, Enum):
    """Alert severity (str subclass)."""
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class Comparator(str, Enum):
    """Comparator (str subclass)."""
    GT = "gt"      # greater than
    LT = "lt"      # less than
    GTE = "gte"    # greater than or equal
    LTE = "lte"    # less than or equal
    EQ = "eq"      # equal


@dataclass
class AlertRule:
    """Definition of a single alert rule."""
    rule_id: str
    name: str
    severity: AlertSeverity
    metric: str           # metric key to watch
    comparator: Comparator
    threshold: float
    cooldown_seconds: float = 300.0  # 5 min default
    description: str = ""
    enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "severity": self.severity.value,
            "metric": self.metric,
            "comparator": self.comparator.value,
            "threshold": self.threshold,
            "cooldown_seconds": self.cooldown_seconds,
            "description": self.description,
            "enabled": self.enabled,
        }


@dataclass
class FiredAlert:
    """Record of a single triggered alert."""
    alert_id: str
    rule_id: str
    rule_name: str
    severity: AlertSeverity
    metric: str
    observed_value: float
    threshold: float
    message: str = ""
    fired_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "severity": self.severity.value,
            "metric": self.metric,
            "observed_value": round(self.observed_value, 4),
            "threshold": self.threshold,
            "message": self.message,
            "fired_at": self.fired_at,
        }


# ---------------------------------------------------------------------------
# Default alert rules from Plan §6.3
# ---------------------------------------------------------------------------

def _default_rules() -> List[AlertRule]:
    return [
        AlertRule("rule-sys-down", "System Down", AlertSeverity.CRITICAL,
                  "uptime_pct", Comparator.LT, 99.0, 60.0, "System uptime below 99%"),
        AlertRule("rule-error-rate", "High Error Rate", AlertSeverity.WARNING,
                  "error_rate_pct", Comparator.GT, 1.0, 300.0, "Error rate above 1%"),
        AlertRule("rule-response-time", "Slow Response", AlertSeverity.WARNING,
                  "response_time_p95_ms", Comparator.GT, 1000.0, 300.0, "p95 latency > 1s"),
        AlertRule("rule-success-low", "Low Success Rate", AlertSeverity.WARNING,
                  "success_rate_pct", Comparator.LT, 90.0, 300.0, "Automation success < 90%"),
        AlertRule("rule-mode-change", "Automation Mode Changed", AlertSeverity.INFO,
                  "mode_changed", Comparator.EQ, 1.0, 60.0, "Automation mode has changed"),
    ]


# ---------------------------------------------------------------------------
# AlertRulesEngine
# ---------------------------------------------------------------------------

class AlertRulesEngine:
    """Configurable alert rules with severity, cooldown, and deduplication.

    Design Label: SAF-004
    Owner: DevOps Team / Platform Engineering

    Usage::

        engine = AlertRulesEngine()
        fired = engine.evaluate({"uptime_pct": 98.5, "error_rate_pct": 2.1})
    """

    def __init__(
        self,
        persistence_manager=None,
        event_backbone=None,
        rules: Optional[List[AlertRule]] = None,
    ) -> None:
        self._lock = threading.Lock()
        self._pm = persistence_manager
        self._backbone = event_backbone
        self._rules: Dict[str, AlertRule] = {}
        self._alerts: List[FiredAlert] = []
        # rule_id → monotonic time of last fire (for cooldown)
        self._last_fired: Dict[str, float] = {}

        for rule in (rules or _default_rules()):
            self._rules[rule.rule_id] = rule

    # ------------------------------------------------------------------
    # Rule management
    # ------------------------------------------------------------------

    def add_rule(self, rule: AlertRule) -> None:
        with self._lock:
            self._rules[rule.rule_id] = rule

    def remove_rule(self, rule_id: str) -> bool:
        with self._lock:
            removed = self._rules.pop(rule_id, None) is not None
            self._last_fired.pop(rule_id, None)
            return removed

    def enable_rule(self, rule_id: str) -> bool:
        with self._lock:
            rule = self._rules.get(rule_id)
            if rule:
                rule.enabled = True
                return True
            return False

    def disable_rule(self, rule_id: str) -> bool:
        with self._lock:
            rule = self._rules.get(rule_id)
            if rule:
                rule.enabled = False
                return True
            return False

    def list_rules(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [r.to_dict() for r in self._rules.values()]

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def evaluate(self, metrics: Dict[str, float]) -> List[FiredAlert]:
        """Evaluate all enabled rules against a metrics snapshot."""
        now = time.monotonic()
        fired: List[FiredAlert] = []

        with self._lock:
            rules = list(self._rules.values())

        for rule in rules:
            if not rule.enabled:
                continue
            if rule.metric not in metrics:
                continue
            observed = metrics[rule.metric]
            if not self._condition_met(observed, rule.comparator, rule.threshold):
                continue

            # Cooldown check (skip if rule has never fired)
            with self._lock:
                last = self._last_fired.get(rule.rule_id, float('-inf'))
                if now - last < rule.cooldown_seconds:
                    continue
                if rule.rule_id in self._last_fired:
                    last = self._last_fired[rule.rule_id]
                    if now - last < rule.cooldown_seconds:
                        continue
                self._last_fired[rule.rule_id] = now

            alert = FiredAlert(
                alert_id=f"al-{uuid.uuid4().hex[:8]}",
                rule_id=rule.rule_id,
                rule_name=rule.name,
                severity=rule.severity,
                metric=rule.metric,
                observed_value=observed,
                threshold=rule.threshold,
                message=f"{rule.name}: {rule.metric}={observed} {rule.comparator.value} {rule.threshold}",
            )

            with self._lock:
                if len(self._alerts) >= _MAX_ALERTS:
                    self._alerts = self._alerts[_MAX_ALERTS // 10:]
                self._alerts.append(alert)

            fired.append(alert)

            # Persist
            if self._pm is not None:
                try:
                    self._pm.save_document(doc_id=alert.alert_id, document=alert.to_dict())
                except Exception as exc:
                    logger.debug("Persistence skipped: %s", exc)

            # Publish
            if self._backbone is not None:
                self._publish_event(alert)

            logger.log(
                logging.CRITICAL if alert.severity == AlertSeverity.CRITICAL else logging.WARNING,
                "Alert fired: %s (severity=%s)", alert.message, alert.severity.value,
            )

        return fired

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_alerts(self, limit: int = 50, severity: Optional[AlertSeverity] = None) -> List[Dict[str, Any]]:
        with self._lock:
            filtered = self._alerts
            if severity:
                filtered = [a for a in filtered if a.severity == severity]
            return [a.to_dict() for a in filtered[-limit:]]

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_rules": len(self._rules),
                "enabled_rules": sum(1 for r in self._rules.values() if r.enabled),
                "total_alerts_fired": len(self._alerts),
                "persistence_attached": self._pm is not None,
                "backbone_attached": self._backbone is not None,
            }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _condition_met(value: float, comparator: Comparator, threshold: float) -> bool:
        if comparator == Comparator.GT:
            return value > threshold
        elif comparator == Comparator.LT:
            return value < threshold
        elif comparator == Comparator.GTE:
            return value >= threshold
        elif comparator == Comparator.LTE:
            return value <= threshold
        elif comparator == Comparator.EQ:
            return abs(value - threshold) < 1e-9
        return False

    def _publish_event(self, alert: FiredAlert) -> None:
        try:
            from event_backbone import Event
            from event_backbone import EventType as ET
            evt = Event(
                event_id=f"evt-{uuid.uuid4().hex[:8]}",
                event_type=ET.SYSTEM_HEALTH,
                payload={
                    "source": "alert_rules_engine",
                    "action": "alert_fired",
                    "alert_id": alert.alert_id,
                    "rule_id": alert.rule_id,
                    "severity": alert.severity.value,
                    "metric": alert.metric,
                    "observed_value": alert.observed_value,
                },
                timestamp=datetime.now(timezone.utc).isoformat(),
                source="alert_rules_engine",
            )
            self._backbone.publish_event(evt)
        except Exception as exc:
            logger.debug("EventBackbone publish skipped: %s", exc)
