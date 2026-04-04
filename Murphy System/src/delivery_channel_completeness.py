"""
Delivery Channel Completeness

Drives multi-channel delivery to 100% by filling gaps in the existing
delivery_adapters module. Provides delivery confirmation tracking, retry
with exponential backoff, template rendering, delivery analytics, and
channel health monitoring with auto-failover.

Pure Python stdlib only — no external dependencies.
"""

import logging
import math
import random
import re
import statistics
import threading
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class TrackingStatus(Enum):
    """Extended delivery lifecycle states."""
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"


class ChannelType(Enum):
    """Supported delivery channels."""
    DOCUMENT = "document"
    EMAIL = "email"
    CHAT = "chat"
    VOICE = "voice"
    TRANSLATION = "translation"


# ---------------------------------------------------------------------------
# 1. Delivery Confirmation Tracking
# ---------------------------------------------------------------------------

class DeliveryConfirmationTracker:
    """
    Tracks delivery status through the full lifecycle:
    queued -> sent -> delivered -> read -> failed.

    Thread-safe via RLock.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._deliveries: Dict[str, Dict[str, Any]] = {}

    def create_delivery(
        self,
        channel: str,
        recipient: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a new delivery record in QUEUED state."""
        delivery_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        record = {
            "delivery_id": delivery_id,
            "channel": channel,
            "recipient": recipient,
            "payload": payload or {},
            "status": TrackingStatus.QUEUED.value,
            "retry_count": 0,
            "created_at": now,
            "updated_at": now,
            "history": [{"status": TrackingStatus.QUEUED.value, "timestamp": now}],
        }
        with self._lock:
            self._deliveries[delivery_id] = record
        return dict(record)

    def update_status(
        self, delivery_id: str, new_status: str
    ) -> Dict[str, Any]:
        """Transition a delivery to a new status."""
        valid = {s.value for s in TrackingStatus}
        if new_status not in valid:
            raise ValueError(f"Invalid status: {new_status}")
        with self._lock:
            if delivery_id not in self._deliveries:
                raise KeyError(f"Unknown delivery_id: {delivery_id}")
            rec = self._deliveries[delivery_id]
            now = datetime.now(timezone.utc).isoformat()
            rec["status"] = new_status
            rec["updated_at"] = now
            rec["history"].append({"status": new_status, "timestamp": now})
            return dict(rec)

    def increment_retry(self, delivery_id: str) -> Dict[str, Any]:
        """Increment the retry counter for a delivery."""
        with self._lock:
            if delivery_id not in self._deliveries:
                raise KeyError(f"Unknown delivery_id: {delivery_id}")
            rec = self._deliveries[delivery_id]
            rec["retry_count"] += 1
            rec["updated_at"] = datetime.now(timezone.utc).isoformat()
            return dict(rec)

    def get_delivery(self, delivery_id: str) -> Dict[str, Any]:
        """Return a snapshot of a single delivery record."""
        with self._lock:
            if delivery_id not in self._deliveries:
                raise KeyError(f"Unknown delivery_id: {delivery_id}")
            return dict(self._deliveries[delivery_id])

    def get_confirmations_by_channel(self, channel: str) -> Dict[str, Any]:
        """Return confirmation counts grouped by status for a channel."""
        counts: Dict[str, int] = defaultdict(int)
        with self._lock:
            for rec in self._deliveries.values():
                if rec["channel"] == channel:
                    counts[rec["status"]] += 1
        return {"channel": channel, "confirmations": dict(counts)}

    def get_all_deliveries(self) -> List[Dict[str, Any]]:
        """Return all delivery records."""
        with self._lock:
            return [dict(r) for r in self._deliveries.values()]


# ---------------------------------------------------------------------------
# 2. Retry with Exponential Backoff
# ---------------------------------------------------------------------------

@dataclass
class RetryConfig:
    """Configuration for retry behaviour."""
    initial_delay: float = 1.0
    max_delay: float = 60.0
    max_retries: int = 3
    jitter: bool = True
    backoff_factor: float = 2.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "initial_delay": self.initial_delay,
            "max_delay": self.max_delay,
            "max_retries": self.max_retries,
            "jitter": self.jitter,
            "backoff_factor": self.backoff_factor,
        }


class RetryManager:
    """
    Manages automatic retries of failed deliveries with exponential backoff.

    Thread-safe via RLock.
    """

    def __init__(self, config: Optional[RetryConfig] = None) -> None:
        self._config = config or RetryConfig()
        self._lock = threading.RLock()
        self._attempts: Dict[str, List[Dict[str, Any]]] = {}

    @property
    def config(self) -> RetryConfig:
        return self._config

    def compute_delay(self, attempt: int) -> float:
        """Compute the backoff delay for a given attempt number (0-based)."""
        delay = self._config.initial_delay * (
            self._config.backoff_factor ** attempt
        )
        delay = min(delay, self._config.max_delay)
        if self._config.jitter:
            delay = delay * (0.5 + random.random() * 0.5)
        return round(delay, 4)

    def execute_with_retry(
        self,
        delivery_id: str,
        action: Callable[[], Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Execute *action* with retries on failure.

        *action* must return a dict with at least a ``"success"`` boolean key.
        Raises the last exception if all retries are exhausted.
        """
        attempts: List[Dict[str, Any]] = []
        last_error: Optional[Exception] = None

        for attempt in range(self._config.max_retries + 1):
            try:
                result = action()
                record = {
                    "attempt": attempt,
                    "success": True,
                    "result": result,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                attempts.append(record)
                with self._lock:
                    self._attempts[delivery_id] = attempts
                return {
                    "delivery_id": delivery_id,
                    "success": True,
                    "attempts": len(attempts),
                    "result": result,
                }
            except Exception as exc:
                logger.debug("Caught exception: %s", exc)
                last_error = exc
                record = {
                    "attempt": attempt,
                    "success": False,
                    "error": str(exc),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                attempts.append(record)

                if attempt < self._config.max_retries:
                    delay = self.compute_delay(attempt)
                    time.sleep(delay)

        with self._lock:
            self._attempts[delivery_id] = attempts

        return {
            "delivery_id": delivery_id,
            "success": False,
            "attempts": len(attempts),
            "error": str(last_error),
        }

    def get_attempts(self, delivery_id: str) -> Dict[str, Any]:
        """Return recorded attempts for a delivery."""
        with self._lock:
            attempts = self._attempts.get(delivery_id, [])
            return {"delivery_id": delivery_id, "attempts": list(attempts)}

    def get_config(self) -> Dict[str, Any]:
        return self._config.to_dict()


# ---------------------------------------------------------------------------
# 3. Template Rendering Engine
# ---------------------------------------------------------------------------

class TemplateRenderingEngine:
    """
    Lightweight template engine supporting:
      - Variable substitution: ``{{variable}}``
      - Conditional blocks: ``{% if condition %}...{% endif %}``
      - Iteration: ``{% for item in items %}...{% endfor %}``
      - Partials: ``{% include partial_name %}``

    Thread-safe via RLock.
    """

    _VAR_RE = re.compile(r"\{\{\s*(\w+(?:\.\w+)*)\s*\}\}")
    _IF_RE = re.compile(
        r"\{%\s*if\s+(\w+)\s*%\}(.*?)\{%\s*endif\s*%\}", re.DOTALL
    )
    _FOR_RE = re.compile(
        r"\{%\s*for\s+(\w+)\s+in\s+(\w+)\s*%\}(.*?)\{%\s*endfor\s*%\}",
        re.DOTALL,
    )
    _INCLUDE_RE = re.compile(r"\{%\s*include\s+(\w+)\s*%\}")

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._partials: Dict[str, str] = {}
        self._render_count: int = 0

    def register_partial(self, name: str, template: str) -> Dict[str, Any]:
        """Register a reusable partial template."""
        with self._lock:
            self._partials[name] = template
        return {"partial": name, "registered": True}

    def render(
        self,
        template: str,
        variables: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Render a template string with the given variables."""
        variables = variables or {}
        try:
            output = self._process(template, variables)
            with self._lock:
                self._render_count += 1
            return {
                "success": True,
                "output": output,
                "variables_used": list(variables.keys()),
            }
        except Exception as exc:
            logger.debug("Caught exception: %s", exc)
            return {"success": False, "error": str(exc)}

    # -- internal helpers ---------------------------------------------------

    def _resolve_var(self, name: str, variables: Dict[str, Any]) -> Any:
        """Resolve a dotted variable name against *variables*."""
        parts = name.split(".")
        current: Any = variables
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part, "")
            else:
                return ""
        return current

    def _process(self, template: str, variables: Dict[str, Any]) -> str:
        text = template

        # Includes
        def _include_repl(m: re.Match) -> str:
            partial_name = m.group(1)
            with self._lock:
                return self._partials.get(partial_name, "")

        text = self._INCLUDE_RE.sub(_include_repl, text)

        # Conditionals
        def _if_repl(m: re.Match) -> str:
            condition_var = m.group(1)
            body = m.group(2)
            if variables.get(condition_var):
                return self._process(body, variables)
            return ""

        text = self._IF_RE.sub(_if_repl, text)

        # Iteration
        def _for_repl(m: re.Match) -> str:
            item_var = m.group(1)
            collection_var = m.group(2)
            body = m.group(3)
            collection = variables.get(collection_var, [])
            if not isinstance(collection, (list, tuple)):
                return ""
            parts: List[str] = []
            for item in collection:
                local_vars = dict(variables)
                local_vars[item_var] = item
                parts.append(self._process(body, local_vars))
            return "".join(parts)

        text = self._FOR_RE.sub(_for_repl, text)

        # Variable substitution
        def _var_repl(m: re.Match) -> str:
            return str(self._resolve_var(m.group(1), variables))

        text = self._VAR_RE.sub(_var_repl, text)
        return text

    def get_stats(self) -> Dict[str, Any]:
        """Return rendering statistics."""
        with self._lock:
            return {
                "render_count": self._render_count,
                "registered_partials": list(self._partials.keys()),
            }


# ---------------------------------------------------------------------------
# 4. Delivery Analytics
# ---------------------------------------------------------------------------

class DeliveryAnalytics:
    """
    Collects and reports delivery metrics:
      - delivery rates per channel
      - latency percentiles (p50, p90, p99)
      - channel performance summaries
      - failure reasons
      - cost per delivery

    Thread-safe via RLock.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._events: List[Dict[str, Any]] = []
        self._costs: Dict[str, float] = {}

    def record_event(
        self,
        channel: str,
        success: bool,
        latency_ms: float,
        failure_reason: Optional[str] = None,
        cost: float = 0.0,
    ) -> Dict[str, Any]:
        """Record a single delivery event."""
        event = {
            "event_id": str(uuid.uuid4()),
            "channel": channel,
            "success": success,
            "latency_ms": latency_ms,
            "failure_reason": failure_reason,
            "cost": cost,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        with self._lock:
            capped_append(self._events, event)
        return event

    def set_channel_cost(self, channel: str, cost_per_unit: float) -> Dict[str, Any]:
        """Set the cost-per-delivery for a channel."""
        with self._lock:
            self._costs[channel] = cost_per_unit
        return {"channel": channel, "cost_per_unit": cost_per_unit}

    def get_delivery_rates(self) -> Dict[str, Any]:
        """Return success/failure rates per channel."""
        with self._lock:
            events = list(self._events)
        channels: Dict[str, Dict[str, int]] = defaultdict(lambda: {"success": 0, "failure": 0})
        for e in events:
            key = "success" if e["success"] else "failure"
            channels[e["channel"]][key] += 1

        rates: Dict[str, Any] = {}
        for ch, counts in channels.items():
            total = counts["success"] + counts["failure"]
            rates[ch] = {
                "total": total,
                "success": counts["success"],
                "failure": counts["failure"],
                "success_rate": round(counts["success"] / total, 4) if total else 0.0,
            }
        return {"delivery_rates": rates}

    def get_latency_percentiles(
        self, channel: Optional[str] = None
    ) -> Dict[str, Any]:
        """Return p50/p90/p99 latency for a channel (or all)."""
        with self._lock:
            events = list(self._events)
        if channel:
            latencies = [e["latency_ms"] for e in events if e["channel"] == channel and e["success"]]
        else:
            latencies = [e["latency_ms"] for e in events if e["success"]]

        if not latencies:
            return {"percentiles": {"p50": 0, "p90": 0, "p99": 0}, "sample_count": 0}

        latencies.sort()
        n = len(latencies)

        def _percentile(pct: float) -> float:
            idx = (pct / 100.0) * (n - 1)
            lower = int(math.floor(idx))
            upper = min(lower + 1, n - 1)
            frac = idx - lower
            return round(latencies[lower] * (1 - frac) + latencies[upper] * frac, 2)

        return {
            "channel": channel or "all",
            "percentiles": {
                "p50": _percentile(50),
                "p90": _percentile(90),
                "p99": _percentile(99),
            },
            "sample_count": n,
        }

    def get_channel_performance(self) -> Dict[str, Any]:
        """Aggregate performance summary across channels."""
        with self._lock:
            events = list(self._events)
        perf: Dict[str, Dict[str, Any]] = {}
        grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for e in events:
            grouped[e["channel"]].append(e)

        for ch, ch_events in grouped.items():
            latencies = [e["latency_ms"] for e in ch_events if e["success"]]
            total = len(ch_events)
            successes = sum(1 for e in ch_events if e["success"])
            perf[ch] = {
                "total": total,
                "success_rate": round(successes / total, 4) if total else 0.0,
                "avg_latency_ms": round(statistics.mean(latencies), 2) if latencies else 0.0,
                "total_cost": round(sum(e["cost"] for e in ch_events), 4),
            }
        return {"channel_performance": perf}

    def get_failure_reasons(
        self, channel: Optional[str] = None
    ) -> Dict[str, Any]:
        """Return aggregated failure reasons."""
        with self._lock:
            events = list(self._events)
        reasons: Dict[str, int] = defaultdict(int)
        for e in events:
            if not e["success"] and e.get("failure_reason"):
                if channel and e["channel"] != channel:
                    continue
                reasons[e["failure_reason"]] += 1
        return {"channel": channel or "all", "failure_reasons": dict(reasons)}

    def get_cost_report(self) -> Dict[str, Any]:
        """Return cost-per-delivery report."""
        with self._lock:
            events = list(self._events)
            costs_config = dict(self._costs)
        channel_costs: Dict[str, Dict[str, Any]] = {}
        grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for e in events:
            grouped[e["channel"]].append(e)
        for ch, ch_events in grouped.items():
            total_cost = sum(e["cost"] for e in ch_events)
            total = len(ch_events)
            channel_costs[ch] = {
                "total_cost": round(total_cost, 4),
                "total_deliveries": total,
                "avg_cost": round(total_cost / total, 4) if total else 0.0,
                "configured_unit_cost": costs_config.get(ch, 0.0),
            }
        return {"cost_report": channel_costs}


# ---------------------------------------------------------------------------
# 5. Channel Health Monitor
# ---------------------------------------------------------------------------

class ChannelHealthMonitor:
    """
    Monitors channel availability, latency, and error rates.
    Supports automatic failover to backup channels.

    Thread-safe via RLock.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._channels: Dict[str, Dict[str, Any]] = {}
        self._backup_map: Dict[str, str] = {}
        self._health_checks: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    def register_channel(
        self,
        channel: str,
        backup_channel: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Register a channel for health monitoring."""
        with self._lock:
            self._channels[channel] = {
                "channel": channel,
                "status": "healthy",
                "total_checks": 0,
                "failures": 0,
                "avg_latency_ms": 0.0,
                "last_check": None,
                "registered_at": datetime.now(timezone.utc).isoformat(),
            }
            if backup_channel:
                self._backup_map[channel] = backup_channel
        return {"channel": channel, "backup": backup_channel, "registered": True}

    def record_health_check(
        self,
        channel: str,
        healthy: bool,
        latency_ms: float = 0.0,
        error: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Record the result of a health check probe."""
        now = datetime.now(timezone.utc).isoformat()
        check = {
            "healthy": healthy,
            "latency_ms": latency_ms,
            "error": error,
            "timestamp": now,
        }
        with self._lock:
            if channel not in self._channels:
                raise KeyError(f"Channel not registered: {channel}")
            self._health_checks[channel].append(check)
            ch = self._channels[channel]
            ch["total_checks"] += 1
            if not healthy:
                ch["failures"] += 1
            ch["last_check"] = now
            # Rolling average latency
            checks = self._health_checks[channel]
            latencies = [c["latency_ms"] for c in checks if c["healthy"]]
            ch["avg_latency_ms"] = (
                round(statistics.mean(latencies), 2) if latencies else 0.0
            )
            # Auto-determine status
            recent = checks[-5:] if len(checks) >= 5 else checks
            recent_failures = sum(1 for c in recent if not c["healthy"])
            if recent_failures >= 3:
                ch["status"] = "unhealthy"
            elif recent_failures >= 1:
                ch["status"] = "degraded"
            else:
                ch["status"] = "healthy"
            return dict(ch)

    def get_channel_status(self, channel: str) -> Dict[str, Any]:
        """Return the current status of a channel."""
        with self._lock:
            if channel not in self._channels:
                raise KeyError(f"Channel not registered: {channel}")
            return dict(self._channels[channel])

    def get_all_channels_status(self) -> Dict[str, Any]:
        """Return status for every registered channel."""
        with self._lock:
            return {
                "channels": {
                    ch: dict(info) for ch, info in self._channels.items()
                }
            }

    def get_error_rates(self) -> Dict[str, Any]:
        """Return error rate per channel."""
        with self._lock:
            rates: Dict[str, float] = {}
            for ch, info in self._channels.items():
                total = info["total_checks"]
                rates[ch] = (
                    round(info["failures"] / total, 4) if total else 0.0
                )
            return {"error_rates": rates}

    def resolve_channel(self, channel: str) -> Dict[str, Any]:
        """
        Resolve the best channel to use, auto-failing-over to backup
        if the primary is unhealthy.
        """
        with self._lock:
            if channel not in self._channels:
                return {"resolved": channel, "failover": False, "reason": "unregistered"}
            status = self._channels[channel]["status"]
            if status == "healthy":
                return {"resolved": channel, "failover": False}
            backup = self._backup_map.get(channel)
            if backup and backup in self._channels:
                backup_status = self._channels[backup]["status"]
                if backup_status != "unhealthy":
                    return {
                        "resolved": backup,
                        "failover": True,
                        "original": channel,
                        "reason": f"primary {status}",
                    }
            return {
                "resolved": channel,
                "failover": False,
                "reason": f"no healthy backup (primary {status})",
            }

    def get_health_history(
        self, channel: str, limit: int = 10
    ) -> Dict[str, Any]:
        """Return recent health check history."""
        with self._lock:
            if channel not in self._channels:
                raise KeyError(f"Channel not registered: {channel}")
            checks = self._health_checks[channel][-limit:]
            return {"channel": channel, "history": list(checks)}
