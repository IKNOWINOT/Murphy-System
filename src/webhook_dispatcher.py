# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Outbound Webhook Dispatcher — WHK-001

Owner: Platform Engineering · Dep: thread_safe_operations (capped_append)

Programmatic outbound webhook dispatch system for the Murphy System —
subscription registry, event matching with wildcard support, HMAC-SHA256
payload signing, delivery with exponential-backoff retry, and full
delivery-history tracking.

Classes: WebhookStatus/DeliveryStatus/EventPriority (enums),
WebhookSubscription/WebhookEvent/DeliveryAttempt/DeliveryRecord
(dataclasses), WebhookDispatcher (thread-safe orchestrator).
``create_webhook_api(dispatcher)`` returns a Flask Blueprint (JSON error
envelope).

Safety: all mutable state guarded by threading.Lock; delivery/event lists
bounded via capped_append (CWE-770); webhook secrets redacted in
serialisation; no real HTTP calls — delivery callback is injected.
"""
from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import logging
import os
import random
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# Optional Flask import (mirrors oauth_oidc_provider pattern)
# ---------------------------------------------------------------------------
try:
    from flask import Blueprint, jsonify, request

    _HAS_FLASK = True
except ImportError:  # pragma: no cover
    _HAS_FLASK = False
    Blueprint = type("Blueprint", (), {"route": lambda *a, **k: lambda f: f})  # type: ignore[assignment,misc]

    def jsonify(*_a: Any, **_k: Any) -> dict:  # type: ignore[override]
        return {}

    class _FakeReq:  # type: ignore[no-redef]
        args: dict = {}

        @staticmethod
        def get_json(silent: bool = True) -> dict:
            return {}

    request = _FakeReq()  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Bounded-list helper
# ---------------------------------------------------------------------------
try:
    from .blueprint_auth import require_blueprint_auth
except ImportError:
    from blueprint_auth import require_blueprint_auth
try:
    from thread_safe_operations import capped_append
except ImportError:

    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)


logger = logging.getLogger(__name__)

# ===================================================================== #
#  Enums                                                                 #
# ===================================================================== #


class WebhookStatus(str, Enum):
    """Lifecycle status of a webhook subscription."""

    ACTIVE = "active"
    PAUSED = "paused"
    DISABLED = "disabled"
    DELETED = "deleted"


class DeliveryStatus(str, Enum):
    """Status of a delivery attempt or record."""

    PENDING = "pending"
    DELIVERING = "delivering"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"


class EventPriority(str, Enum):
    """Priority classification for webhook events."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


# ===================================================================== #
#  Dataclasses                                                           #
# ===================================================================== #


@dataclass
class WebhookSubscription:
    """A registered webhook endpoint with filtering and auth metadata."""

    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    name: str = ""
    url: str = ""
    secret: str = ""
    event_types: List[str] = field(default_factory=list)
    status: WebhookStatus = WebhookStatus.ACTIVE
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    headers: Dict[str, str] = field(default_factory=dict)
    max_retries: int = 5
    timeout_seconds: float = 10.0
    enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Serialise with secret redacted."""
        d = asdict(self)
        d["status"] = self.status.value
        if self.secret:
            d["secret"] = "***REDACTED***"
        return d


@dataclass
class WebhookEvent:
    """An event dispatched through the webhook system."""

    event_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    event_type: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    priority: EventPriority = EventPriority.NORMAL
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    source: str = "murphy"

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to plain dict."""
        d = asdict(self)
        d["priority"] = self.priority.value
        return d


@dataclass
class DeliveryAttempt:
    """A single delivery attempt for one subscription + event pair."""

    attempt_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    subscription_id: str = ""
    event_id: str = ""
    status: DeliveryStatus = DeliveryStatus.PENDING
    response_code: Optional[int] = None
    response_body: str = ""
    attempt_number: int = 1
    next_retry_at: Optional[float] = None
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    error: str = ""
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to plain dict."""
        d = asdict(self)
        d["status"] = self.status.value
        return d


@dataclass
class DeliveryRecord:
    """Aggregated delivery record tracking all attempts for one dispatch."""

    record_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    subscription_id: str = ""
    event_id: str = ""
    attempts: List[DeliveryAttempt] = field(default_factory=list)
    final_status: DeliveryStatus = DeliveryStatus.PENDING
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    completed_at: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to plain dict."""
        d: Dict[str, Any] = {
            "record_id": self.record_id,
            "subscription_id": self.subscription_id,
            "event_id": self.event_id,
            "attempts": [a.to_dict() for a in self.attempts],
            "final_status": self.final_status.value,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }
        return d


# ===================================================================== #
#  WebhookDispatcher — thread-safe orchestrator                          #
# ===================================================================== #


class WebhookDispatcher:
    """Thread-safe outbound webhook dispatch engine.

    Parameters
    ----------
    max_retries:
        Global cap on delivery retries.
    base_delay:
        Base delay in seconds for exponential backoff.
    max_delay:
        Upper bound in seconds for backoff delay.
    delivery_callback:
        ``(url, payload_dict, headers, timeout) -> (status_code, body)``.
        When *None* delivery is simulated (always succeeds with 200).
    """

    def __init__(
        self,
        max_retries: int = 5,
        base_delay: float = 1.0,
        max_delay: float = 300.0,
        delivery_callback: Optional[
            Callable[[str, dict, dict, float], Tuple[int, str]]
        ] = None,
    ) -> None:
        self._lock = threading.Lock()
        self._subscriptions: Dict[str, WebhookSubscription] = {}
        self._delivery_records: List[DeliveryRecord] = []
        self._event_log: List[WebhookEvent] = []
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self._delivery_callback = delivery_callback

    # ------------------------------------------------------------------ #
    #  Subscription management                                            #
    # ------------------------------------------------------------------ #

    # ------------------------------------------------------------------ #
    #  SSRF protection                                                     #
    # ------------------------------------------------------------------ #

    # Private/reserved IP ranges that must never be webhook targets (CWE-918)
    _BLOCKED_NETWORKS = [
        ipaddress.ip_network("0.0.0.0/8"),
        ipaddress.ip_network("10.0.0.0/8"),
        ipaddress.ip_network("100.64.0.0/10"),
        ipaddress.ip_network("127.0.0.0/8"),
        ipaddress.ip_network("169.254.0.0/16"),
        ipaddress.ip_network("172.16.0.0/12"),
        ipaddress.ip_network("192.0.0.0/24"),
        ipaddress.ip_network("192.0.2.0/24"),
        ipaddress.ip_network("192.168.0.0/16"),
        ipaddress.ip_network("198.18.0.0/15"),
        ipaddress.ip_network("198.51.100.0/24"),
        ipaddress.ip_network("203.0.113.0/24"),
        ipaddress.ip_network("224.0.0.0/4"),
        ipaddress.ip_network("240.0.0.0/4"),
        ipaddress.ip_network("255.255.255.255/32"),
        ipaddress.ip_network("::1/128"),
        ipaddress.ip_network("fc00::/7"),
        ipaddress.ip_network("fe80::/10"),
    ]

    @classmethod
    def validate_webhook_url(cls, url: str) -> None:
        """Validate a webhook URL is safe from SSRF attacks (CWE-918).

        Raises ``ValueError`` if the URL targets a private/reserved IP range,
        uses a non-HTTPS scheme in production, or is otherwise malformed.
        """
        if not url or not isinstance(url, str):
            raise ValueError("Webhook URL is required")

        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise ValueError(
                f"Webhook URL scheme must be http or https, got '{parsed.scheme}'"
            )

        # Enforce HTTPS in production/staging
        murphy_env = os.environ.get("MURPHY_ENV", "development").lower()
        if murphy_env in ("production", "staging") and parsed.scheme != "https":
            raise ValueError(
                "Webhook URLs must use HTTPS in production/staging environments"
            )

        hostname = parsed.hostname
        if not hostname:
            raise ValueError("Webhook URL must include a hostname")

        # Block IP-literal hostnames pointing to private ranges
        try:
            addr = ipaddress.ip_address(hostname)
            for net in cls._BLOCKED_NETWORKS:
                if addr in net:
                    raise ValueError(
                        f"Webhook URL must not target private/reserved IP: {hostname}"
                    )
        except ValueError as exc:
            if "private" in str(exc).lower() or "must not" in str(exc).lower():
                raise
            # hostname is a DNS name — allow it (DNS re-binding defence is at
            # delivery time, not registration time)

        if parsed.port is not None and parsed.port in (0, 22, 25, 53, 6379, 5432, 3306, 11211):
            raise ValueError(
                f"Webhook URL targets a restricted port: {parsed.port}"
            )

    def register_subscription(
        self,
        name: str,
        url: str,
        event_types: List[str],
        secret: str = "",
        headers: Optional[Dict[str, str]] = None,
        max_retries: int = 5,
        timeout_seconds: float = 10.0,
    ) -> WebhookSubscription:
        """Register a new webhook subscription and return it."""
        # SSRF protection: validate URL before registration
        self.validate_webhook_url(url)
        sub = WebhookSubscription(
            name=name,
            url=url,
            secret=secret,
            event_types=list(event_types),
            headers=dict(headers or {}),
            max_retries=max_retries,
            timeout_seconds=timeout_seconds,
        )
        with self._lock:
            self._subscriptions[sub.id] = sub
        logger.info("Registered webhook subscription %s (%s)", sub.id, name)
        return sub

    def get_subscription(self, subscription_id: str) -> Optional[WebhookSubscription]:
        """Retrieve a subscription by ID, or *None*."""
        with self._lock:
            return self._subscriptions.get(subscription_id)

    def list_subscriptions(
        self, status: Optional[WebhookStatus] = None
    ) -> List[WebhookSubscription]:
        """Return subscriptions, optionally filtered by status."""
        with self._lock:
            subs = list(self._subscriptions.values())
        if status is not None:
            subs = [s for s in subs if s.status == status]
        return subs

    def update_subscription(
        self, subscription_id: str, **kwargs: Any
    ) -> Optional[WebhookSubscription]:
        """Update mutable fields on a subscription.

        Allowed keys: name, url, event_types, headers, max_retries,
        timeout_seconds, enabled.
        """
        allowed = {
            "name", "url", "event_types", "headers",
            "max_retries", "timeout_seconds", "enabled",
        }
        # SSRF protection: validate URL if being updated
        if "url" in kwargs:
            self.validate_webhook_url(kwargs["url"])
        with self._lock:
            sub = self._subscriptions.get(subscription_id)
            if sub is None:
                return None
            for key, val in kwargs.items():
                if key in allowed:
                    setattr(sub, key, val)
            sub.updated_at = datetime.now(timezone.utc).isoformat()
        return sub

    def delete_subscription(self, subscription_id: str) -> bool:
        """Soft-delete a subscription (sets status to DELETED)."""
        with self._lock:
            sub = self._subscriptions.get(subscription_id)
            if sub is None:
                return False
            sub.status = WebhookStatus.DELETED
            sub.enabled = False
            sub.updated_at = datetime.now(timezone.utc).isoformat()
        logger.info("Deleted webhook subscription %s", subscription_id)
        return True

    def enable_subscription(self, subscription_id: str) -> bool:
        """Enable a subscription and set its status to ACTIVE."""
        with self._lock:
            sub = self._subscriptions.get(subscription_id)
            if sub is None or sub.status == WebhookStatus.DELETED:
                return False
            sub.enabled = True
            sub.status = WebhookStatus.ACTIVE
            sub.updated_at = datetime.now(timezone.utc).isoformat()
        return True

    def disable_subscription(self, subscription_id: str) -> bool:
        """Disable a subscription and set its status to DISABLED."""
        with self._lock:
            sub = self._subscriptions.get(subscription_id)
            if sub is None or sub.status == WebhookStatus.DELETED:
                return False
            sub.enabled = False
            sub.status = WebhookStatus.DISABLED
            sub.updated_at = datetime.now(timezone.utc).isoformat()
        return True

    # ------------------------------------------------------------------ #
    #  Event dispatch                                                     #
    # ------------------------------------------------------------------ #

    def dispatch_event(
        self,
        event_type: str,
        payload: Dict[str, Any],
        source: str = "murphy",
        priority: EventPriority = EventPriority.NORMAL,
    ) -> List[DeliveryRecord]:
        """Dispatch an event to all matching active subscriptions."""
        event = WebhookEvent(
            event_type=event_type,
            payload=payload,
            source=source,
            priority=priority,
        )
        with self._lock:
            capped_append(self._event_log, event)
            matching = [
                s
                for s in self._subscriptions.values()
                if self._matches(s, event_type)
            ]
        records: List[DeliveryRecord] = []
        for sub in matching:
            record = self._deliver(sub, event)
            with self._lock:
                capped_append(self._delivery_records, record)
            records.append(record)
        logger.info(
            "Dispatched event %s to %d subscriptions",
            event.event_id,
            len(records),
        )
        return records

    # ------------------------------------------------------------------ #
    #  Delivery internals                                                 #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _matches(sub: WebhookSubscription, event_type: str) -> bool:
        """Return True if *sub* should receive *event_type*."""
        if sub.status != WebhookStatus.ACTIVE or not sub.enabled:
            return False
        return "*" in sub.event_types or event_type in sub.event_types

    def _deliver(
        self, subscription: WebhookSubscription, event: WebhookEvent
    ) -> DeliveryRecord:
        """Attempt delivery with retries, returning a completed record."""
        record = DeliveryRecord(
            subscription_id=subscription.id,
            event_id=event.event_id,
        )
        retries = min(subscription.max_retries, self.max_retries)
        for attempt_num in range(1, retries + 1):
            attempt = self._attempt_delivery(subscription, event, attempt_num)
            record.attempts.append(attempt)
            if attempt.status == DeliveryStatus.DELIVERED:
                record.final_status = DeliveryStatus.DELIVERED
                record.completed_at = time.time()
                return record
            if attempt_num < retries:
                attempt.status = DeliveryStatus.RETRYING
                attempt.next_retry_at = (
                    time.time() + self._calculate_backoff(attempt_num)
                )
        record.final_status = DeliveryStatus.FAILED
        record.completed_at = time.time()
        return record

    def _attempt_delivery(
        self,
        subscription: WebhookSubscription,
        event: WebhookEvent,
        attempt_number: int,
    ) -> DeliveryAttempt:
        """Execute a single delivery attempt."""
        payload_dict = event.to_dict()
        payload_bytes = json.dumps(payload_dict, sort_keys=True).encode()
        headers = dict(subscription.headers)
        headers["Content-Type"] = "application/json"
        if subscription.secret:
            sig = self._sign_payload(payload_bytes, subscription.secret)
            headers["X-Murphy-Signature"] = sig
        start = time.monotonic()
        attempt = DeliveryAttempt(
            subscription_id=subscription.id,
            event_id=event.event_id,
            attempt_number=attempt_number,
            status=DeliveryStatus.DELIVERING,
        )
        try:
            code, body = self._do_deliver(
                subscription.url,
                payload_dict,
                headers,
                subscription.timeout_seconds,
            )
            elapsed = (time.monotonic() - start) * 1000
            attempt.response_code = code
            attempt.response_body = body[:4096]  # cap at 4 KB to limit memory
            attempt.duration_ms = round(elapsed, 2)
            attempt.status = (
                DeliveryStatus.DELIVERED if 200 <= code < 300
                else DeliveryStatus.FAILED
            )
        except Exception as exc:  # noqa: BLE001
            elapsed = (time.monotonic() - start) * 1000
            attempt.duration_ms = round(elapsed, 2)
            attempt.error = str(exc)[:1024]  # cap at 1 KB to limit memory
            attempt.status = DeliveryStatus.FAILED
        return attempt

    def _do_deliver(
        self,
        url: str,
        payload: dict,
        headers: dict,
        timeout: float,
    ) -> Tuple[int, str]:
        """Invoke the delivery callback or simulate success."""
        if self._delivery_callback is not None:
            return self._delivery_callback(url, payload, headers, timeout)
        return 200, '{"ok":true}'

    def _calculate_backoff(self, attempt_number: int) -> float:
        """Exponential backoff with jitter."""
        delay = min(self.base_delay * (2 ** attempt_number), self.max_delay)
        return delay * random.uniform(0.5, 1.5)

    @staticmethod
    def _sign_payload(payload_bytes: bytes, secret: str) -> str:
        """Compute HMAC-SHA256 hex digest for *payload_bytes*."""
        return hmac.new(
            secret.encode(), payload_bytes, hashlib.sha256
        ).hexdigest()

    # ------------------------------------------------------------------ #
    #  Retry / query helpers                                              #
    # ------------------------------------------------------------------ #

    def retry_failed(self, record_id: str) -> Optional[DeliveryRecord]:
        """Retry delivery for a previously-failed record."""
        with self._lock:
            old = self._find_record(record_id)
        if old is None or old.final_status != DeliveryStatus.FAILED:
            return None
        with self._lock:
            sub = self._subscriptions.get(old.subscription_id)
        if sub is None:
            return None
        event = self._find_event(old.event_id)
        if event is None:
            return None
        record = self._deliver(sub, event)
        with self._lock:
            capped_append(self._delivery_records, record)
        return record

    def get_delivery_record(self, record_id: str) -> Optional[DeliveryRecord]:
        """Retrieve a delivery record by ID."""
        with self._lock:
            return self._find_record(record_id)

    def list_delivery_records(
        self,
        subscription_id: Optional[str] = None,
        status: Optional[DeliveryStatus] = None,
        limit: int = 100,
    ) -> List[DeliveryRecord]:
        """Return delivery records, optionally filtered."""
        with self._lock:
            recs = list(self._delivery_records)
        if subscription_id is not None:
            recs = [r for r in recs if r.subscription_id == subscription_id]
        if status is not None:
            recs = [r for r in recs if r.final_status == status]
        return recs[-limit:]

    def get_event_log(self, limit: int = 100) -> List[WebhookEvent]:
        """Return the most recent events from the event log."""
        with self._lock:
            return list(self._event_log[-limit:])

    def stats(self) -> Dict[str, Any]:
        """Compute aggregate statistics for the dispatcher."""
        with self._lock:
            subs = list(self._subscriptions.values())
            recs = list(self._delivery_records)
            total_events = len(self._event_log)
        active = sum(
            1 for s in subs if s.status == WebhookStatus.ACTIVE and s.enabled
        )
        delivered = sum(
            1 for r in recs if r.final_status == DeliveryStatus.DELIVERED
        )
        failed = sum(
            1 for r in recs if r.final_status == DeliveryStatus.FAILED
        )
        total_del = len(recs)
        return {
            "total_subscriptions": len(subs),
            "active_subscriptions": active,
            "total_events_dispatched": total_events,
            "total_deliveries": total_del,
            "successful_deliveries": delivered,
            "failed_deliveries": failed,
            "success_rate": (
                round(delivered / total_del, 4) if total_del else 0.0
            ),
        }

    # ------------------------------------------------------------------ #
    #  Private look-ups (caller must hold _lock where noted)              #
    # ------------------------------------------------------------------ #

    def _find_record(self, record_id: str) -> Optional[DeliveryRecord]:
        """Find a delivery record by ID. Must hold _lock."""
        for r in self._delivery_records:
            if r.record_id == record_id:
                return r
        return None

    def _find_event(self, event_id: str) -> Optional[WebhookEvent]:
        """Find an event by ID (lock-safe, reads only)."""
        with self._lock:
            for e in self._event_log:
                if e.event_id == event_id:
                    return e
        return None


# ===================================================================== #
#  Flask Blueprint factory                                               #
# ===================================================================== #


def _api_body() -> Dict[str, Any]:
    """Extract JSON body from Flask request."""
    return request.get_json(silent=True) or {}


def _api_need(body: Dict[str, Any], *keys: str) -> Optional[Any]:
    """Return a 400 error tuple if any *keys* are missing from *body*."""
    for k in keys:
        if not body.get(k):
            return jsonify({"error": f"{k} required", "code": "MISSING_FIELDS"}), 400
    return None


def _api_404(msg: str = "Not found") -> Any:
    """Return a standard 404 error response."""
    return jsonify({"error": msg, "code": "NOT_FOUND"}), 404


def _register_subscription_crud(
    bp: Any, dispatcher: WebhookDispatcher
) -> None:
    """Attach subscription create/read/update/delete routes to *bp*."""

    @bp.route("/subscriptions", methods=["POST"])
    def register_subscription() -> Any:
        """Register a webhook subscription."""
        b = _api_body()
        err = _api_need(b, "name", "url", "event_types")
        if err:
            return err
        sub = dispatcher.register_subscription(
            name=b["name"],
            url=b["url"],
            event_types=b["event_types"],
            secret=b.get("secret", ""),
            headers=b.get("headers"),
            max_retries=b.get("max_retries", 5),
            timeout_seconds=b.get("timeout_seconds", 10.0),
        )
        return jsonify(sub.to_dict()), 201

    @bp.route("/subscriptions", methods=["GET"])
    def list_subscriptions() -> Any:
        """List subscriptions with optional status filter."""
        status_val = request.args.get("status")
        status = WebhookStatus(status_val) if status_val else None
        return jsonify([s.to_dict() for s in dispatcher.list_subscriptions(status)])

    @bp.route("/subscriptions/<sub_id>", methods=["GET"])
    def get_subscription(sub_id: str) -> Any:
        """Get a single subscription."""
        sub = dispatcher.get_subscription(sub_id)
        return jsonify(sub.to_dict()) if sub else _api_404()

    @bp.route("/subscriptions/<sub_id>", methods=["PUT"])
    def update_subscription(sub_id: str) -> Any:
        """Update a subscription."""
        sub = dispatcher.update_subscription(sub_id, **_api_body())
        return jsonify(sub.to_dict()) if sub else _api_404()

    @bp.route("/subscriptions/<sub_id>", methods=["DELETE"])
    def delete_subscription(sub_id: str) -> Any:
        """Soft-delete a subscription."""
        if dispatcher.delete_subscription(sub_id):
            return jsonify({"status": "deleted"})
        return _api_404()


def _register_subscription_actions(
    bp: Any, dispatcher: WebhookDispatcher
) -> None:
    """Attach subscription enable/disable routes to *bp*."""

    @bp.route("/subscriptions/<sub_id>/enable", methods=["POST"])
    def enable_subscription(sub_id: str) -> Any:
        """Enable a subscription."""
        if dispatcher.enable_subscription(sub_id):
            return jsonify({"status": "enabled"})
        return _api_404()

    @bp.route("/subscriptions/<sub_id>/disable", methods=["POST"])
    def disable_subscription(sub_id: str) -> Any:
        """Disable a subscription."""
        if dispatcher.disable_subscription(sub_id):
            return jsonify({"status": "disabled"})
        return _api_404()


def _register_event_routes(bp: Any, dispatcher: WebhookDispatcher) -> None:
    """Attach event dispatch and log routes to *bp*."""

    @bp.route("/events", methods=["POST"])
    def dispatch_event() -> Any:
        """Dispatch a webhook event."""
        b = _api_body()
        err = _api_need(b, "event_type", "payload")
        if err:
            return err
        priority = (
            EventPriority(b["priority"]) if "priority" in b
            else EventPriority.NORMAL
        )
        records = dispatcher.dispatch_event(
            event_type=b["event_type"],
            payload=b["payload"],
            source=b.get("source", "murphy"),
            priority=priority,
        )
        return jsonify([r.to_dict() for r in records]), 201

    @bp.route("/events", methods=["GET"])
    def get_event_log() -> Any:
        """Return event log."""
        limit = int(request.args.get("limit", 100))
        return jsonify([e.to_dict() for e in dispatcher.get_event_log(limit)])


def _register_delivery_routes(
    bp: Any, dispatcher: WebhookDispatcher
) -> None:
    """Attach delivery record and retry routes to *bp*."""

    @bp.route("/deliveries", methods=["GET"])
    def list_deliveries() -> Any:
        """List delivery records with optional filters."""
        sub_id = request.args.get("subscription_id")
        status_val = request.args.get("status")
        limit = int(request.args.get("limit", 100))
        status = DeliveryStatus(status_val) if status_val else None
        return jsonify(
            [r.to_dict() for r in dispatcher.list_delivery_records(sub_id, status, limit)]
        )

    @bp.route("/deliveries/<rec_id>", methods=["GET"])
    def get_delivery(rec_id: str) -> Any:
        """Get a single delivery record."""
        rec = dispatcher.get_delivery_record(rec_id)
        return jsonify(rec.to_dict()) if rec else _api_404()

    @bp.route("/deliveries/<rec_id>/retry", methods=["POST"])
    def retry_delivery(rec_id: str) -> Any:
        """Retry a failed delivery."""
        rec = dispatcher.retry_failed(rec_id)
        if rec is None:
            return (
                jsonify({"error": "Record not found or not failed", "code": "RETRY_FAILED"}),
                400,
            )
        return jsonify(rec.to_dict()), 201


def create_webhook_api(dispatcher: WebhookDispatcher) -> Any:
    """Create a Flask Blueprint exposing webhook management endpoints."""
    if not _HAS_FLASK:
        return Blueprint("webhooks", __name__)  # type: ignore[call-arg]

    bp = Blueprint("webhooks", __name__, url_prefix="/api/webhooks")

    _register_subscription_crud(bp, dispatcher)
    _register_subscription_actions(bp, dispatcher)
    _register_event_routes(bp, dispatcher)
    _register_delivery_routes(bp, dispatcher)

    @bp.route("/stats", methods=["GET"])
    def get_stats() -> Any:
        """Return dispatcher statistics."""
        return jsonify(dispatcher.stats())

    require_blueprint_auth(bp)
    return bp
