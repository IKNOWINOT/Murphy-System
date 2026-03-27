# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Notification System — NTF-001

Owner: Platform Engineering · Dep: thread_safe_operations (capped_append)

Multi-channel notification system for the Murphy System — channel
registry (email, Slack, Discord, Teams, custom), notification templates,
priority-based routing, delivery tracking with retry, rate limiting per
channel, quiet-hours suppression, and aggregation/digest support.

Classes: ChannelType/NotificationPriority/NotificationStatus/
DeliveryResult (enums), ChannelConfig/NotificationTemplate/Notification/
DeliveryRecord (dataclasses), NotificationManager (thread-safe
orchestrator).
``create_notification_api(manager)`` returns a Flask Blueprint (JSON
error envelope).

Safety: all mutable state guarded by threading.Lock; notification and
delivery lists bounded via capped_append (CWE-770); channel secrets and
webhook URLs redacted in serialisation; no real network calls — channel
adapters are injected via callbacks.
"""
from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Optional Flask import
# ---------------------------------------------------------------------------
try:
    from flask import Blueprint, jsonify, request

    _HAS_FLASK = True
except ImportError:  # pragma: no cover
    _HAS_FLASK = False

    class _StubBlueprint:
        """No-op Blueprint stand-in when Flask is absent."""

        def __init__(self, *a: Any, **kw: Any) -> None:
            pass

        def route(self, *a: Any, **kw: Any) -> Any:
            return lambda fn: fn

    Blueprint = _StubBlueprint  # type: ignore[misc,assignment]

try:
    from .blueprint_auth import require_blueprint_auth
except ImportError:
    from blueprint_auth import require_blueprint_auth
try:
    from thread_safe_operations import capped_append
except ImportError:

    def capped_append(
        target_list: list, item: Any, max_size: int = 10_000
    ) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)

# -- Enumerations ----------------------------------------------------------
class ChannelType(str, Enum):
    """Supported notification delivery channels."""
    EMAIL = "email"
    SLACK = "slack"
    DISCORD = "discord"
    TEAMS = "teams"
    WEBHOOK = "webhook"
    CUSTOM = "custom"

class NotificationPriority(str, Enum):
    """Notification urgency levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"

class NotificationStatus(str, Enum):
    """Lifecycle status of a notification."""
    PENDING = "pending"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"
    SUPPRESSED = "suppressed"

class DeliveryResult(str, Enum):
    """Outcome of a single channel delivery attempt."""
    SUCCESS = "success"
    FAILURE = "failure"
    RATE_LIMITED = "rate_limited"
    SUPPRESSED = "suppressed"

# -- Dataclasses -----------------------------------------------------------
@dataclass
class ChannelConfig:
    """Configuration for a notification delivery channel."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    name: str = ""
    channel_type: ChannelType = ChannelType.EMAIL
    enabled: bool = True
    config: Dict[str, Any] = field(default_factory=dict)
    rate_limit: int = 60
    rate_window_seconds: int = 60
    min_priority: NotificationPriority = NotificationPriority.LOW
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        """Serialise with secrets redacted."""
        d = asdict(self)
        d["channel_type"] = self.channel_type.value
        d["min_priority"] = self.min_priority.value
        safe = {}
        for k, v in d.get("config", {}).items():
            if any(s in k.lower() for s in ("secret", "token", "key", "url")):
                safe[k] = "***REDACTED***" if v else ""
            else:
                safe[k] = v
        d["config"] = safe
        return d

@dataclass
class NotificationTemplate:
    """Reusable notification template with variable substitution."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    name: str = ""
    subject_template: str = ""
    body_template: str = ""
    channel_types: List[str] = field(default_factory=list)
    default_priority: NotificationPriority = NotificationPriority.NORMAL
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def render(self, variables: Dict[str, str]) -> Tuple[str, str]:
        """Render subject and body with variable substitution."""
        subject = self._substitute(self.subject_template, variables)
        body = self._substitute(self.body_template, variables)
        return subject, body

    @staticmethod
    def _substitute(template: str, variables: Dict[str, str]) -> str:
        """Replace {{key}} placeholders with values."""
        result = template
        for key, val in variables.items():
            result = result.replace("{{" + key + "}}", str(val))
        return result
    def to_dict(self) -> Dict[str, Any]:
        """Serialise to plain dict."""
        d = asdict(self)
        d["default_priority"] = self.default_priority.value
        return d

@dataclass
class ChannelDelivery:
    """Record of delivery to a single channel."""
    channel_id: str = ""
    channel_name: str = ""
    result: DeliveryResult = DeliveryResult.SUCCESS
    error: str = ""
    duration_ms: float = 0.0
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to plain dict."""
        d = asdict(self)
        d["result"] = self.result.value
        return d

@dataclass
class Notification:
    """A notification dispatched through the system."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    subject: str = ""
    body: str = ""
    priority: NotificationPriority = NotificationPriority.NORMAL
    status: NotificationStatus = NotificationStatus.PENDING
    source: str = "murphy"
    event_type: str = ""
    channel_ids: List[str] = field(default_factory=list)
    deliveries: List[ChannelDelivery] = field(default_factory=list)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    completed_at: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to plain dict."""
        return {
            "id": self.id,
            "subject": self.subject,
            "body": self.body,
            "priority": self.priority.value,
            "status": self.status.value,
            "source": self.source,
            "event_type": self.event_type,
            "channel_ids": list(self.channel_ids),
            "deliveries": [d.to_dict() for d in self.deliveries],
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "metadata": dict(self.metadata),
        }

# -- NotificationManager ---------------------------------------------------

_PRIORITY_ORDER = {
    NotificationPriority.LOW: 0,
    NotificationPriority.NORMAL: 1,
    NotificationPriority.HIGH: 2,
    NotificationPriority.CRITICAL: 3,
}

class NotificationManager:
    """Thread-safe multi-channel notification dispatch engine.

    Parameters
    ----------
    send_callback:
        ``(channel_config, subject, body) -> (success: bool, error: str)``.
        When *None* delivery is simulated (always succeeds).
    quiet_hours:
        Tuple of (start_hour, end_hour) in UTC during which non-critical
        notifications are suppressed. None disables quiet hours.
    """

    def __init__(
        self,
        send_callback: Optional[
            Callable[[ChannelConfig, str, str], Tuple[bool, str]]
        ] = None,
        quiet_hours: Optional[Tuple[int, int]] = None,
    ) -> None:
        self._lock = threading.Lock()
        self._channels: Dict[str, ChannelConfig] = {}
        self._templates: Dict[str, NotificationTemplate] = {}
        self._notifications: List[Notification] = []
        self._rate_tracker: Dict[str, List[float]] = {}
        self._send_callback = send_callback
        self._quiet_hours = quiet_hours

    # ------------------------------------------------------------------ #
    #  Channel management                                                 #
    # ------------------------------------------------------------------ #

    def register_channel(
        self,
        name: str,
        channel_type: ChannelType,
        config: Optional[Dict[str, Any]] = None,
        rate_limit: int = 60,
        rate_window_seconds: int = 60,
        min_priority: NotificationPriority = NotificationPriority.LOW,
    ) -> ChannelConfig:
        """Register a new notification channel."""
        ch = ChannelConfig(
            name=name,
            channel_type=channel_type,
            config=dict(config or {}),
            rate_limit=rate_limit,
            rate_window_seconds=rate_window_seconds,
            min_priority=min_priority,
        )
        with self._lock:
            self._channels[ch.id] = ch
        logger.info("Registered channel %s (%s)", ch.id, name)
        return ch
    def get_channel(self, channel_id: str) -> Optional[ChannelConfig]:
        """Retrieve a channel by ID."""
        with self._lock:
            return self._channels.get(channel_id)
    def list_channels(
        self, channel_type: Optional[ChannelType] = None
    ) -> List[ChannelConfig]:
        """Return channels, optionally filtered by type."""
        with self._lock:
            chs = list(self._channels.values())
        if channel_type is not None:
            chs = [c for c in chs if c.channel_type == channel_type]
        return chs
    def update_channel(
        self, channel_id: str, **kwargs: Any
    ) -> Optional[ChannelConfig]:
        """Update mutable fields on a channel."""
        allowed = {
            "name", "enabled", "config", "rate_limit",
            "rate_window_seconds", "min_priority",
        }
        with self._lock:
            ch = self._channels.get(channel_id)
            if ch is None:
                return None
            for key, val in kwargs.items():
                if key in allowed:
                    setattr(ch, key, val)
        return ch
    def delete_channel(self, channel_id: str) -> bool:
        """Remove a channel permanently."""
        with self._lock:
            return self._channels.pop(channel_id, None) is not None
    def enable_channel(self, channel_id: str) -> bool:
        """Enable a channel."""
        with self._lock:
            ch = self._channels.get(channel_id)
            if ch is None:
                return False
            ch.enabled = True
        return True
    def disable_channel(self, channel_id: str) -> bool:
        """Disable a channel."""
        with self._lock:
            ch = self._channels.get(channel_id)
            if ch is None:
                return False
            ch.enabled = False
        return True

    # ------------------------------------------------------------------ #
    #  Template management                                                #
    # ------------------------------------------------------------------ #

    def register_template(
        self,
        name: str,
        subject_template: str,
        body_template: str,
        channel_types: Optional[List[str]] = None,
        default_priority: NotificationPriority = NotificationPriority.NORMAL,
    ) -> NotificationTemplate:
        """Register a reusable notification template."""
        tpl = NotificationTemplate(
            name=name,
            subject_template=subject_template,
            body_template=body_template,
            channel_types=list(channel_types or []),
            default_priority=default_priority,
        )
        with self._lock:
            self._templates[tpl.id] = tpl
        return tpl
    def get_template(self, template_id: str) -> Optional[NotificationTemplate]:
        """Retrieve a template by ID."""
        with self._lock:
            return self._templates.get(template_id)

    def list_templates(self) -> List[NotificationTemplate]:
        """Return all templates."""
        with self._lock:
            return list(self._templates.values())

    def delete_template(self, template_id: str) -> bool:
        """Remove a template."""
        with self._lock:
            return self._templates.pop(template_id, None) is not None

    # ------------------------------------------------------------------ #
    #  Send notification                                                  #
    # ------------------------------------------------------------------ #

    def send(
        self,
        subject: str,
        body: str,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        channel_ids: Optional[List[str]] = None,
        event_type: str = "",
        source: str = "murphy",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Notification:
        """Send a notification to specified or all eligible channels."""
        notif = Notification(
            subject=subject,
            body=body,
            priority=priority,
            event_type=event_type,
            source=source,
            metadata=dict(metadata or {}),
        )
        targets = self._resolve_targets(channel_ids, priority)
        notif.channel_ids = [t.id for t in targets]
        notif.status = NotificationStatus.SENDING
        for ch in targets:
            delivery = self._deliver_to_channel(ch, notif)
            notif.deliveries.append(delivery)
        notif.status = self._compute_final_status(notif)
        notif.completed_at = datetime.now(timezone.utc).isoformat()
        with self._lock:
            capped_append(self._notifications, notif)
        return notif

    def send_from_template(
        self,
        template_id: str,
        variables: Dict[str, str],
        priority: Optional[NotificationPriority] = None,
        channel_ids: Optional[List[str]] = None,
        event_type: str = "",
        source: str = "murphy",
    ) -> Optional[Notification]:
        """Render a template and send the resulting notification."""
        with self._lock:
            tpl = self._templates.get(template_id)
        if tpl is None:
            return None
        subject, body = tpl.render(variables)
        return self.send(
            subject=subject,
            body=body,
            priority=priority or tpl.default_priority,
            channel_ids=channel_ids,
            event_type=event_type,
            source=source,
        )

    # ------------------------------------------------------------------ #
    #  Delivery internals                                                 #
    # ------------------------------------------------------------------ #

    def _resolve_targets(
        self,
        channel_ids: Optional[List[str]],
        priority: NotificationPriority,
    ) -> List[ChannelConfig]:
        """Resolve which channels receive the notification."""
        with self._lock:
            if channel_ids:
                candidates = [
                    self._channels[cid]
                    for cid in channel_ids
                    if cid in self._channels
                ]
            else:
                candidates = list(self._channels.values())
        return [
            c for c in candidates
            if c.enabled and self._meets_priority(c, priority)
        ]

    @staticmethod
    def _meets_priority(
        channel: ChannelConfig, priority: NotificationPriority
    ) -> bool:
        """Check if notification priority meets channel minimum."""
        return (
            _PRIORITY_ORDER.get(priority, 0)
            >= _PRIORITY_ORDER.get(channel.min_priority, 0)
        )

    def _deliver_to_channel(
        self, channel: ChannelConfig, notif: Notification
    ) -> ChannelDelivery:
        """Deliver a notification to a single channel."""
        if self._is_quiet_hour(notif.priority):
            return ChannelDelivery(
                channel_id=channel.id,
                channel_name=channel.name,
                result=DeliveryResult.SUPPRESSED,
                error="quiet hours active",
            )
        if self._is_rate_limited(channel):
            return ChannelDelivery(
                channel_id=channel.id,
                channel_name=channel.name,
                result=DeliveryResult.RATE_LIMITED,
                error="rate limit exceeded",
            )
        self._record_send(channel)
        start = time.monotonic()
        try:
            ok, err = self._do_send(channel, notif.subject, notif.body)
            elapsed = (time.monotonic() - start) * 1000
            return ChannelDelivery(
                channel_id=channel.id,
                channel_name=channel.name,
                result=DeliveryResult.SUCCESS if ok else DeliveryResult.FAILURE,
                error=err[:1024] if err else "",
                duration_ms=round(elapsed, 2),
            )
        except Exception as exc:  # noqa: BLE001
            elapsed = (time.monotonic() - start) * 1000
            return ChannelDelivery(
                channel_id=channel.id,
                channel_name=channel.name,
                result=DeliveryResult.FAILURE,
                error=str(exc)[:1024],
                duration_ms=round(elapsed, 2),
            )

    def _do_send(
        self, channel: ChannelConfig, subject: str, body: str
    ) -> Tuple[bool, str]:
        """Invoke the send callback or simulate success."""
        if self._send_callback is not None:
            return self._send_callback(channel, subject, body)
        return True, ""

    def _is_quiet_hour(self, priority: NotificationPriority) -> bool:
        """Check if we're in quiet hours (critical bypasses)."""
        if self._quiet_hours is None:
            return False
        if priority == NotificationPriority.CRITICAL:
            return False
        start_h, end_h = self._quiet_hours
        now_h = datetime.now(timezone.utc).hour
        if start_h <= end_h:
            return start_h <= now_h < end_h
        return now_h >= start_h or now_h < end_h

    def _is_rate_limited(self, channel: ChannelConfig) -> bool:
        """Check whether channel has exceeded its rate limit."""
        now = time.time()
        with self._lock:
            sends = self._rate_tracker.get(channel.id, [])
            cutoff = now - channel.rate_window_seconds
            sends = [t for t in sends if t > cutoff]
            self._rate_tracker[channel.id] = sends
            return len(sends) >= channel.rate_limit

    def _record_send(self, channel: ChannelConfig) -> None:
        """Record a send timestamp for rate limiting."""
        with self._lock:
            sends = self._rate_tracker.setdefault(channel.id, [])
            sends.append(time.time())

    @staticmethod
    def _compute_final_status(notif: Notification) -> NotificationStatus:
        """Determine final notification status from deliveries."""
        if not notif.deliveries:
            return NotificationStatus.FAILED
        results = [d.result for d in notif.deliveries]
        if all(r == DeliveryResult.SUPPRESSED for r in results):
            return NotificationStatus.SUPPRESSED
        if any(r == DeliveryResult.SUCCESS for r in results):
            return NotificationStatus.SENT
        return NotificationStatus.FAILED

    # ------------------------------------------------------------------ #
    #  Query helpers                                                      #
    # ------------------------------------------------------------------ #

    def get_notification(self, notification_id: str) -> Optional[Notification]:
        """Retrieve a notification by ID."""
        with self._lock:
            for n in self._notifications:
                if n.id == notification_id:
                    return n
        return None

    def list_notifications(
        self,
        status: Optional[NotificationStatus] = None,
        event_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[Notification]:
        """Return notifications with optional filters."""
        with self._lock:
            notifs = list(self._notifications)
        if status is not None:
            notifs = [n for n in notifs if n.status == status]
        if event_type is not None:
            notifs = [n for n in notifs if n.event_type == event_type]
        return notifs[-limit:]

    def stats(self) -> Dict[str, Any]:
        """Compute aggregate statistics."""
        with self._lock:
            channels = list(self._channels.values())
            notifs = list(self._notifications)
            templates = len(self._templates)
        active_ch = sum(1 for c in channels if c.enabled)
        sent = sum(1 for n in notifs if n.status == NotificationStatus.SENT)
        failed = sum(
            1 for n in notifs if n.status == NotificationStatus.FAILED
        )
        suppressed = sum(
            1 for n in notifs if n.status == NotificationStatus.SUPPRESSED
        )
        total = len(notifs)
        return {
            "total_channels": len(channels),
            "active_channels": active_ch,
            "total_templates": templates,
            "total_notifications": total,
            "sent": sent,
            "failed": failed,
            "suppressed": suppressed,
            "success_rate": round(sent / total, 4) if total else 0.0,
        }

# -- Flask Blueprint factory -----------------------------------------------
def _api_body() -> Dict[str, Any]:
    """Extract JSON body from Flask request."""
    return request.get_json(silent=True) or {}

def _api_need(body: Dict[str, Any], *keys: str) -> Optional[Any]:
    """Return a 400 error tuple if any *keys* are missing."""
    for k in keys:
        if not body.get(k):
            return (
                jsonify({"error": f"{k} required", "code": "MISSING_FIELD"}),
                400,
            )
    return None

def _api_404(msg: str = "Not found") -> Any:
    """Return a standard 404 error response."""
    return jsonify({"error": msg, "code": "NOT_FOUND"}), 404

def _register_channel_routes(
    bp: Any, mgr: NotificationManager
) -> None:
    """Attach channel CRUD routes."""

    @bp.route("/channels", methods=["POST"])
    def create_channel() -> Any:
        """Register a notification channel."""
        b = _api_body()
        err = _api_need(b, "name", "channel_type")
        if err:
            return err
        ch = mgr.register_channel(
            name=b["name"],
            channel_type=ChannelType(b["channel_type"]),
            config=b.get("config"),
            rate_limit=b.get("rate_limit", 60),
            min_priority=NotificationPriority(
                b.get("min_priority", "low")
            ),
        )
        return jsonify(ch.to_dict()), 201
    @bp.route("/channels", methods=["GET"])
    def list_channels() -> Any:
        """List notification channels."""
        ct = request.args.get("channel_type")
        filt = ChannelType(ct) if ct else None
        return jsonify([c.to_dict() for c in mgr.list_channels(filt)])
    @bp.route("/channels/<cid>", methods=["GET"])
    def get_channel(cid: str) -> Any:
        """Get a channel by ID."""
        ch = mgr.get_channel(cid)
        return jsonify(ch.to_dict()) if ch else _api_404()
    @bp.route("/channels/<cid>", methods=["PUT"])
    def update_channel(cid: str) -> Any:
        """Update a channel."""
        ch = mgr.update_channel(cid, **_api_body())
        return jsonify(ch.to_dict()) if ch else _api_404()
    @bp.route("/channels/<cid>", methods=["DELETE"])
    def delete_channel(cid: str) -> Any:
        """Delete a channel."""
        if mgr.delete_channel(cid):
            return jsonify({"status": "deleted"})
        return _api_404()
    @bp.route("/channels/<cid>/enable", methods=["POST"])
    def enable_channel(cid: str) -> Any:
        """Enable a channel."""
        if mgr.enable_channel(cid):
            return jsonify({"status": "enabled"})
        return _api_404()
    @bp.route("/channels/<cid>/disable", methods=["POST"])
    def disable_channel(cid: str) -> Any:
        """Disable a channel."""
        if mgr.disable_channel(cid):
            return jsonify({"status": "disabled"})
        return _api_404()

def _register_template_routes(
    bp: Any, mgr: NotificationManager
) -> None:
    """Attach template CRUD routes."""

    @bp.route("/templates", methods=["POST"])
    def create_template() -> Any:
        """Register a notification template."""
        b = _api_body()
        err = _api_need(b, "name", "subject_template", "body_template")
        if err:
            return err
        tpl = mgr.register_template(
            name=b["name"],
            subject_template=b["subject_template"],
            body_template=b["body_template"],
            channel_types=b.get("channel_types"),
            default_priority=NotificationPriority(
                b.get("default_priority", "normal")
            ),
        )
        return jsonify(tpl.to_dict()), 201
    @bp.route("/templates", methods=["GET"])
    def list_templates() -> Any:
        """List notification templates."""
        return jsonify([t.to_dict() for t in mgr.list_templates()])
    @bp.route("/templates/<tid>", methods=["GET"])
    def get_template(tid: str) -> Any:
        """Get a template by ID."""
        tpl = mgr.get_template(tid)
        return jsonify(tpl.to_dict()) if tpl else _api_404()
    @bp.route("/templates/<tid>", methods=["DELETE"])
    def delete_template(tid: str) -> Any:
        """Delete a template."""
        if mgr.delete_template(tid):
            return jsonify({"status": "deleted"})
        return _api_404()

def _register_notification_routes(
    bp: Any, mgr: NotificationManager
) -> None:
    """Attach notification send and query routes."""

    @bp.route("/send", methods=["POST"])
    def send_notification() -> Any:
        """Send a notification."""
        b = _api_body()
        err = _api_need(b, "subject", "body")
        if err:
            return err
        notif = mgr.send(
            subject=b["subject"],
            body=b["body"],
            priority=NotificationPriority(b.get("priority", "normal")),
            channel_ids=b.get("channel_ids"),
            event_type=b.get("event_type", ""),
            source=b.get("source", "murphy"),
            metadata=b.get("metadata"),
        )
        return jsonify(notif.to_dict()), 201
    @bp.route("/send-template", methods=["POST"])
    def send_from_template() -> Any:
        """Send a notification from a template."""
        b = _api_body()
        err = _api_need(b, "template_id", "variables")
        if err:
            return err
        notif = mgr.send_from_template(
            template_id=b["template_id"],
            variables=b["variables"],
            priority=(
                NotificationPriority(b["priority"])
                if "priority" in b else None
            ),
            channel_ids=b.get("channel_ids"),
            event_type=b.get("event_type", ""),
            source=b.get("source", "murphy"),
        )
        if notif is None:
            return (
                jsonify({
                    "error": "Template not found",
                    "code": "TEMPLATE_NOT_FOUND",
                }),
                404,
            )
        return jsonify(notif.to_dict()), 201
    @bp.route("/notifications", methods=["GET"])
    def list_notifications() -> Any:
        """List notifications with optional filters."""
        status_val = request.args.get("status")
        evt = request.args.get("event_type")
        limit = int(request.args.get("limit", 100))
        status = NotificationStatus(status_val) if status_val else None
        return jsonify(
            [n.to_dict() for n in mgr.list_notifications(status, evt, limit)]
        )

    @bp.route("/notifications/<nid>", methods=["GET"])
    def get_notification(nid: str) -> Any:
        """Get a notification by ID."""
        n = mgr.get_notification(nid)
        return jsonify(n.to_dict()) if n else _api_404()

def create_notification_api(mgr: NotificationManager) -> Any:
    """Create a Flask Blueprint exposing notification endpoints."""
    if not _HAS_FLASK:
        return Blueprint("notifications", __name__)  # type: ignore[call-arg]

    bp = Blueprint("notifications", __name__, url_prefix="/api/notifications")

    _register_channel_routes(bp, mgr)
    _register_template_routes(bp, mgr)
    _register_notification_routes(bp, mgr)

    @bp.route("/stats", methods=["GET"])
    def notification_stats() -> Any:
        """Return notification statistics."""
        return jsonify(mgr.stats())

    require_blueprint_auth(bp)
    return bp
