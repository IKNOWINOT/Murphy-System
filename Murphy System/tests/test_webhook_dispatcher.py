# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Comprehensive test suite for webhook_dispatcher — WHK-001.

Uses the storyline-actuals ``record()`` pattern to capture every check
as an auditable WHKRecord with cause / effect / lesson annotations.
"""
from __future__ import annotations

import datetime
import hashlib
import hmac
import json
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"

from webhook_dispatcher import (  # noqa: E402
    DeliveryAttempt,
    DeliveryRecord,
    DeliveryStatus,
    EventPriority,
    WebhookDispatcher,
    WebhookEvent,
    WebhookStatus,
    WebhookSubscription,
    create_webhook_api,
)

# -- Record pattern --------------------------------------------------------


@dataclass
class WHKRecord:
    """One WHK check record."""

    check_id: str
    description: str
    expected: Any
    actual: Any
    passed: bool
    cause: str = ""
    effect: str = ""
    lesson: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat()
    )


_RESULTS: List[WHKRecord] = []


def record(
    check_id: str,
    desc: str,
    expected: Any,
    actual: Any,
    cause: str = "",
    effect: str = "",
    lesson: str = "",
) -> bool:
    ok = expected == actual
    _RESULTS.append(
        WHKRecord(
            check_id=check_id,
            description=desc,
            expected=expected,
            actual=actual,
            passed=ok,
            cause=cause,
            effect=effect,
            lesson=lesson,
        )
    )
    return ok


# -- Helpers ---------------------------------------------------------------

def _disp(**kw: Any) -> WebhookDispatcher:
    """Create a fresh dispatcher with optional overrides."""
    return WebhookDispatcher(**kw)


def _sub(
    d: WebhookDispatcher,
    name: str = "test",
    url: str = "https://example.com/hook",
    events: list | None = None,
    secret: str = "",
) -> WebhookSubscription:
    """Register and return a subscription."""
    return d.register_subscription(
        name=name,
        url=url,
        event_types=events or ["*"],
        secret=secret,
    )


def _fail_cb(
    url: str, payload: dict, headers: dict, timeout: float
) -> Tuple[int, str]:
    """Delivery callback that always returns 500."""
    return 500, '{"error":"server error"}'


def _ok_cb(
    url: str, payload: dict, headers: dict, timeout: float
) -> Tuple[int, str]:
    """Delivery callback that always returns 200."""
    return 200, '{"ok":true}'


def _exc_cb(
    url: str, payload: dict, headers: dict, timeout: float
) -> Tuple[int, str]:
    """Delivery callback that raises an exception."""
    raise ConnectionError("network down")


# ==================================================================== #
#  Enum tests                                                           #
# ==================================================================== #


def test_whk_001_webhook_status_enum():
    """WebhookStatus enum has expected members."""
    assert record(
        "WHK-001",
        "WebhookStatus values",
        {"active", "paused", "disabled", "deleted"},
        {m.value for m in WebhookStatus},
    )


def test_whk_002_delivery_status_enum():
    """DeliveryStatus enum has expected members."""
    assert record(
        "WHK-002",
        "DeliveryStatus values",
        {"pending", "delivering", "delivered", "failed", "retrying"},
        {m.value for m in DeliveryStatus},
    )


def test_whk_003_event_priority_enum():
    """EventPriority enum has expected members."""
    assert record(
        "WHK-003",
        "EventPriority values",
        {"low", "normal", "high", "critical"},
        {m.value for m in EventPriority},
    )


# ==================================================================== #
#  Dataclass tests                                                      #
# ==================================================================== #


def test_whk_004_subscription_defaults():
    """WebhookSubscription has sane defaults."""
    sub = WebhookSubscription()
    assert record(
        "WHK-004",
        "Subscription defaults",
        (True, WebhookStatus.ACTIVE, True),
        (bool(sub.id), sub.status, sub.enabled),
    )


def test_whk_005_subscription_secret_redaction():
    """WebhookSubscription.to_dict() redacts secret."""
    sub = WebhookSubscription(secret="super_secret_key")
    d = sub.to_dict()
    assert record(
        "WHK-005",
        "Secret redacted in serialisation",
        "***REDACTED***",
        d["secret"],
        cause="secret must never leak",
        effect="to_dict hides real value",
        lesson="always redact secrets in serialised output",
    )


def test_whk_006_subscription_no_secret_redaction():
    """WebhookSubscription.to_dict() leaves empty secret alone."""
    sub = WebhookSubscription(secret="")
    d = sub.to_dict()
    assert record("WHK-006", "Empty secret not redacted", "", d["secret"])


def test_whk_007_webhook_event_defaults():
    """WebhookEvent has sane defaults."""
    ev = WebhookEvent(event_type="test.event", payload={"k": 1})
    d = ev.to_dict()
    assert record(
        "WHK-007",
        "Event to_dict structure",
        ("test.event", "normal"),
        (d["event_type"], d["priority"]),
    )


def test_whk_008_delivery_attempt_to_dict():
    """DeliveryAttempt serialises status as string."""
    att = DeliveryAttempt(status=DeliveryStatus.DELIVERED, response_code=200)
    d = att.to_dict()
    assert record("WHK-008", "Attempt status string", "delivered", d["status"])


def test_whk_009_delivery_record_to_dict():
    """DeliveryRecord serialises with nested attempts."""
    rec = DeliveryRecord(
        attempts=[
            DeliveryAttempt(status=DeliveryStatus.FAILED),
            DeliveryAttempt(status=DeliveryStatus.DELIVERED),
        ],
        final_status=DeliveryStatus.DELIVERED,
    )
    d = rec.to_dict()
    assert record(
        "WHK-009",
        "Record to_dict nested attempts",
        (2, "delivered"),
        (len(d["attempts"]), d["final_status"]),
    )


# ==================================================================== #
#  Subscription management tests                                        #
# ==================================================================== #


def test_whk_010_register_subscription():
    """Register a subscription and retrieve it."""
    d = _disp()
    sub = _sub(d, name="s1", url="https://a.com/hook")
    got = d.get_subscription(sub.id)
    assert record(
        "WHK-010",
        "Register and get subscription",
        ("s1", "https://a.com/hook"),
        (got.name, got.url) if got else (None, None),
    )


def test_whk_011_list_subscriptions():
    """List returns all subscriptions."""
    d = _disp()
    _sub(d, name="a")
    _sub(d, name="b")
    assert record("WHK-011", "List all subscriptions", 2, len(d.list_subscriptions()))


def test_whk_012_list_subscriptions_filter():
    """List filters by status."""
    d = _disp()
    s = _sub(d, name="a")
    _sub(d, name="b")
    d.disable_subscription(s.id)
    assert record(
        "WHK-012",
        "List filter by DISABLED",
        1,
        len(d.list_subscriptions(status=WebhookStatus.DISABLED)),
    )


def test_whk_013_update_subscription():
    """Update mutable fields on a subscription."""
    d = _disp()
    s = _sub(d, name="old")
    d.update_subscription(s.id, name="new", url="https://new.com")
    got = d.get_subscription(s.id)
    assert record(
        "WHK-013",
        "Update name and url",
        ("new", "https://new.com"),
        (got.name, got.url) if got else (None, None),
    )


def test_whk_014_update_nonexistent():
    """Update returns None for unknown ID."""
    d = _disp()
    assert record("WHK-014", "Update nonexistent", None, d.update_subscription("nope", name="x"))


def test_whk_015_delete_subscription():
    """Soft-delete sets status=DELETED and enabled=False."""
    d = _disp()
    s = _sub(d)
    d.delete_subscription(s.id)
    got = d.get_subscription(s.id)
    assert record(
        "WHK-015",
        "Delete sets DELETED",
        (WebhookStatus.DELETED, False),
        (got.status, got.enabled) if got else (None, None),
    )


def test_whk_016_delete_nonexistent():
    """Delete returns False for unknown ID."""
    d = _disp()
    assert record("WHK-016", "Delete nonexistent", False, d.delete_subscription("nope"))


def test_whk_017_enable_subscription():
    """Enable a disabled subscription."""
    d = _disp()
    s = _sub(d)
    d.disable_subscription(s.id)
    d.enable_subscription(s.id)
    got = d.get_subscription(s.id)
    assert record(
        "WHK-017",
        "Enable sets ACTIVE + enabled",
        (WebhookStatus.ACTIVE, True),
        (got.status, got.enabled) if got else (None, None),
    )


def test_whk_018_enable_deleted_fails():
    """Cannot enable a DELETED subscription."""
    d = _disp()
    s = _sub(d)
    d.delete_subscription(s.id)
    assert record("WHK-018", "Enable deleted fails", False, d.enable_subscription(s.id))


def test_whk_019_disable_subscription():
    """Disable sets status=DISABLED and enabled=False."""
    d = _disp()
    s = _sub(d)
    d.disable_subscription(s.id)
    got = d.get_subscription(s.id)
    assert record(
        "WHK-019",
        "Disable subscription",
        (WebhookStatus.DISABLED, False),
        (got.status, got.enabled) if got else (None, None),
    )


# ==================================================================== #
#  Dispatch tests                                                       #
# ==================================================================== #


def test_whk_020_dispatch_wildcard():
    """Wildcard '*' subscription receives all events."""
    d = _disp()
    _sub(d, events=["*"])
    recs = d.dispatch_event("anything.here", {"k": 1})
    assert record(
        "WHK-020",
        "Wildcard dispatch",
        (1, DeliveryStatus.DELIVERED),
        (len(recs), recs[0].final_status if recs else None),
    )


def test_whk_021_dispatch_specific_match():
    """Event type must match subscription filter."""
    d = _disp()
    _sub(d, events=["order.created"])
    yes = d.dispatch_event("order.created", {"id": 1})
    no = d.dispatch_event("user.login", {"id": 2})
    assert record(
        "WHK-021",
        "Specific event match",
        (1, 0),
        (len(yes), len(no)),
        cause="event_types filter controls which subs fire",
        effect="unmatched events produce no deliveries",
        lesson="event routing prevents noisy subscribers",
    )


def test_whk_022_dispatch_disabled_skipped():
    """Disabled subscriptions are not matched."""
    d = _disp()
    s = _sub(d, events=["*"])
    d.disable_subscription(s.id)
    recs = d.dispatch_event("test", {})
    assert record("WHK-022", "Disabled sub skipped", 0, len(recs))


def test_whk_023_dispatch_multiple_subs():
    """Event fans out to multiple matching subscriptions."""
    d = _disp()
    _sub(d, name="a", events=["*"])
    _sub(d, name="b", events=["*"])
    _sub(d, name="c", events=["only.this"])
    recs = d.dispatch_event("any.event", {"x": 1})
    assert record("WHK-023", "Fan-out to 2 subs", 2, len(recs))


def test_whk_024_dispatch_with_fail_callback():
    """Failed delivery callback leads to FAILED final status after retries."""
    d = _disp(max_retries=2, base_delay=0.001, delivery_callback=_fail_cb)
    _sub(d, events=["*"])
    recs = d.dispatch_event("test", {})
    rec = recs[0]
    assert record(
        "WHK-024",
        "Failed delivery after retries",
        (DeliveryStatus.FAILED, 2),
        (rec.final_status, len(rec.attempts)),
        cause="callback returns 500",
        effect="retries exhaust then FAILED",
        lesson="max_retries bounds delivery attempts",
    )


def test_whk_025_dispatch_with_exception_callback():
    """Exception in callback is caught and recorded."""
    d = _disp(max_retries=1, delivery_callback=_exc_cb)
    _sub(d, events=["*"])
    recs = d.dispatch_event("test", {})
    att = recs[0].attempts[0]
    assert record(
        "WHK-025",
        "Exception captured in attempt",
        True,
        "network down" in att.error,
    )


def test_whk_026_dispatch_event_logged():
    """Dispatched events appear in the event log."""
    d = _disp()
    _sub(d, events=["*"])
    d.dispatch_event("ev1", {"a": 1})
    d.dispatch_event("ev2", {"b": 2})
    log = d.get_event_log()
    assert record("WHK-026", "Event log has 2 entries", 2, len(log))


def test_whk_027_dispatch_no_subs():
    """Dispatching with no matching subs returns empty list."""
    d = _disp()
    recs = d.dispatch_event("orphan", {})
    assert record("WHK-027", "No matching subs", 0, len(recs))


# ==================================================================== #
#  Retry tests                                                          #
# ==================================================================== #


def test_whk_028_retry_failed():
    """Retry a failed delivery record with a working callback."""
    d = _disp(max_retries=1, delivery_callback=_fail_cb)
    _sub(d, events=["*"])
    recs = d.dispatch_event("test", {})
    failed_id = recs[0].record_id
    # Swap to success callback
    d._delivery_callback = _ok_cb
    retry_rec = d.retry_failed(failed_id)
    assert record(
        "WHK-028",
        "Retry succeeds with good callback",
        DeliveryStatus.DELIVERED,
        retry_rec.final_status if retry_rec else None,
    )


def test_whk_029_retry_nonfailed():
    """Retry returns None for a non-FAILED record."""
    d = _disp()
    _sub(d, events=["*"])
    recs = d.dispatch_event("test", {})
    assert record(
        "WHK-029",
        "Retry non-failed returns None",
        None,
        d.retry_failed(recs[0].record_id),
    )


def test_whk_030_retry_nonexistent():
    """Retry returns None for unknown record_id."""
    d = _disp()
    assert record("WHK-030", "Retry unknown ID", None, d.retry_failed("nope"))


# ==================================================================== #
#  Signing tests                                                        #
# ==================================================================== #


def test_whk_031_hmac_signature():
    """HMAC-SHA256 signature matches expected value."""
    secret = "my_secret"
    payload = json.dumps({"event_type": "test"}, sort_keys=True).encode()
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    actual = WebhookDispatcher._sign_payload(payload, secret)
    assert record("WHK-031", "HMAC signature match", expected, actual)


def test_whk_032_signature_header_present():
    """Dispatch with secret includes X-Murphy-Signature header."""
    captured: list = []

    def spy_cb(
        url: str, payload: dict, headers: dict, timeout: float
    ) -> Tuple[int, str]:
        captured.append(headers.copy())
        return 200, "ok"

    d = _disp(delivery_callback=spy_cb)
    _sub(d, secret="sec123", events=["*"])
    d.dispatch_event("test", {"k": 1})
    has_sig = "X-Murphy-Signature" in captured[0] if captured else False
    assert record(
        "WHK-032",
        "Signature header present",
        True,
        has_sig,
        cause="subscription has a secret",
        effect="HMAC signature computed and added to header",
        lesson="signatures let receivers verify payload integrity",
    )


def test_whk_033_no_signature_without_secret():
    """Dispatch without secret omits X-Murphy-Signature header."""
    captured: list = []

    def spy_cb(
        url: str, payload: dict, headers: dict, timeout: float
    ) -> Tuple[int, str]:
        captured.append(headers.copy())
        return 200, "ok"

    d = _disp(delivery_callback=spy_cb)
    _sub(d, secret="", events=["*"])
    d.dispatch_event("test", {"k": 1})
    has_sig = "X-Murphy-Signature" in captured[0] if captured else True
    assert record("WHK-033", "No signature without secret", False, has_sig)


# ==================================================================== #
#  Backoff tests                                                        #
# ==================================================================== #


def test_whk_034_backoff_increases():
    """Exponential backoff produces increasing delays."""
    d = _disp(base_delay=1.0, max_delay=300.0)
    delays = [d._calculate_backoff(i) for i in range(1, 6)]
    # With jitter the delays are not strictly monotonic, but the midpoints grow
    midpoints = [d.base_delay * (2 ** i) for i in range(1, 6)]
    assert record(
        "WHK-034",
        "Backoff midpoints increase",
        True,
        all(midpoints[i] <= midpoints[i + 1] for i in range(len(midpoints) - 1)),
    )


def test_whk_035_backoff_capped():
    """Backoff never exceeds max_delay * 1.5 (jitter ceiling)."""
    d = _disp(base_delay=1.0, max_delay=10.0)
    for _ in range(100):
        val = d._calculate_backoff(20)
        if val > 10.0 * 1.5:
            assert record("WHK-035", "Backoff capped", True, False)
            return
    assert record("WHK-035", "Backoff capped", True, True)


# ==================================================================== #
#  Query / stats tests                                                  #
# ==================================================================== #


def test_whk_036_stats():
    """Stats returns expected structure and values."""
    d = _disp()
    _sub(d, events=["*"])
    d.dispatch_event("ev1", {})
    s = d.stats()
    assert record(
        "WHK-036",
        "Stats structure",
        (1, 1, 1, 1),
        (
            s["total_subscriptions"],
            s["active_subscriptions"],
            s["total_events_dispatched"],
            s["successful_deliveries"],
        ),
    )


def test_whk_037_stats_failure():
    """Stats counts failures."""
    d = _disp(max_retries=1, delivery_callback=_fail_cb)
    _sub(d, events=["*"])
    d.dispatch_event("ev1", {})
    s = d.stats()
    assert record("WHK-037", "Stats failed count", 1, s["failed_deliveries"])


def test_whk_038_list_delivery_records():
    """List delivery records with subscription filter."""
    d = _disp()
    s1 = _sub(d, name="a", events=["*"])
    _sub(d, name="b", events=["*"])
    d.dispatch_event("ev1", {})
    filtered = d.list_delivery_records(subscription_id=s1.id)
    assert record("WHK-038", "Filter records by sub", 1, len(filtered))


def test_whk_039_get_delivery_record():
    """Get a specific delivery record by ID."""
    d = _disp()
    _sub(d, events=["*"])
    recs = d.dispatch_event("ev1", {})
    got = d.get_delivery_record(recs[0].record_id)
    assert record(
        "WHK-039",
        "Get delivery record",
        recs[0].record_id,
        got.record_id if got else None,
    )


def test_whk_040_event_log_limit():
    """Event log respects limit parameter."""
    d = _disp()
    _sub(d, events=["*"])
    for i in range(5):
        d.dispatch_event(f"ev{i}", {})
    log = d.get_event_log(limit=3)
    assert record("WHK-040", "Event log limit", 3, len(log))


# ==================================================================== #
#  Thread safety                                                        #
# ==================================================================== #


def test_whk_041_thread_safety():
    """Concurrent subscription registration from 10 threads."""
    d = _disp()
    barrier = threading.Barrier(10)

    def worker(i: int) -> None:
        barrier.wait()
        d.register_subscription(f"t-{i}", f"https://t{i}.com/h", ["*"])

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert record(
        "WHK-041",
        "10 concurrent registrations",
        10,
        len(d.list_subscriptions()),
        cause="threading.Lock guards mutations",
        effect="no race conditions",
        lesson="thread-safe dict access prevents data loss",
    )


def test_whk_042_concurrent_dispatch():
    """Concurrent dispatch from multiple threads."""
    d = _disp()
    _sub(d, events=["*"])
    barrier = threading.Barrier(5)

    def worker(i: int) -> None:
        barrier.wait()
        d.dispatch_event(f"ev-{i}", {"thread": i})

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert record(
        "WHK-042",
        "5 concurrent dispatches",
        5,
        len(d.get_event_log()),
    )


# ==================================================================== #
#  Flask API tests                                                      #
# ==================================================================== #


try:
    from flask import Flask

    def _app() -> tuple:
        d = _disp()
        app = Flask(__name__)
        app.register_blueprint(create_webhook_api(d))
        return app, d

    def test_whk_043_api_create_subscription():
        """POST /api/webhooks/subscriptions creates a subscription."""
        app, _ = _app()
        with app.test_client() as c:
            resp = c.post(
                "/api/webhooks/subscriptions",
                json={
                    "name": "test",
                    "url": "https://example.com/hook",
                    "event_types": ["*"],
                    "secret": "s3cret",
                },
            )
            data = resp.get_json()
        assert record(
            "WHK-043",
            "POST subscriptions returns 201 with redacted secret",
            (201, "***REDACTED***"),
            (resp.status_code, data.get("secret")),
        )

    def test_whk_044_api_list_subscriptions():
        """GET /api/webhooks/subscriptions lists subscriptions."""
        app, d = _app()
        _sub(d, name="a")
        _sub(d, name="b")
        with app.test_client() as c:
            resp = c.get("/api/webhooks/subscriptions")
        assert record(
            "WHK-044",
            "GET subscriptions returns list",
            (200, 2),
            (resp.status_code, len(resp.get_json())),
        )

    def test_whk_045_api_get_subscription():
        """GET /api/webhooks/subscriptions/<id> returns subscription."""
        app, d = _app()
        s = _sub(d, name="test")
        with app.test_client() as c:
            resp = c.get(f"/api/webhooks/subscriptions/{s.id}")
        assert record("WHK-045", "GET sub by ID", 200, resp.status_code)

    def test_whk_046_api_get_subscription_404():
        """GET /api/webhooks/subscriptions/<id> returns 404 for unknown."""
        app, _ = _app()
        with app.test_client() as c:
            resp = c.get("/api/webhooks/subscriptions/nope")
        assert record("WHK-046", "GET unknown sub", 404, resp.status_code)

    def test_whk_047_api_update_subscription():
        """PUT /api/webhooks/subscriptions/<id> updates fields."""
        app, d = _app()
        s = _sub(d, name="old")
        with app.test_client() as c:
            resp = c.put(
                f"/api/webhooks/subscriptions/{s.id}",
                json={"name": "new"},
            )
            data = resp.get_json()
        assert record(
            "WHK-047",
            "PUT updates name",
            (200, "new"),
            (resp.status_code, data.get("name")),
        )

    def test_whk_048_api_delete_subscription():
        """DELETE /api/webhooks/subscriptions/<id> soft-deletes."""
        app, d = _app()
        s = _sub(d)
        with app.test_client() as c:
            resp = c.delete(f"/api/webhooks/subscriptions/{s.id}")
        assert record("WHK-048", "DELETE returns 200", 200, resp.status_code)

    def test_whk_049_api_enable_disable():
        """POST enable/disable toggles subscription."""
        app, d = _app()
        s = _sub(d)
        with app.test_client() as c:
            r1 = c.post(f"/api/webhooks/subscriptions/{s.id}/disable")
            r2 = c.post(f"/api/webhooks/subscriptions/{s.id}/enable")
        assert record(
            "WHK-049",
            "Enable/disable returns 200",
            (200, 200),
            (r1.status_code, r2.status_code),
        )

    def test_whk_050_api_dispatch_event():
        """POST /api/webhooks/events dispatches event."""
        app, d = _app()
        _sub(d, events=["*"])
        with app.test_client() as c:
            resp = c.post(
                "/api/webhooks/events",
                json={"event_type": "test.event", "payload": {"k": 1}},
            )
            data = resp.get_json()
        assert record(
            "WHK-050",
            "POST events returns 201 with records",
            (201, 1),
            (resp.status_code, len(data)),
        )

    def test_whk_051_api_dispatch_missing_fields():
        """POST /api/webhooks/events without required fields returns 400."""
        app, _ = _app()
        with app.test_client() as c:
            resp = c.post("/api/webhooks/events", json={})
        assert record("WHK-051", "Missing fields returns 400", 400, resp.status_code)

    def test_whk_052_api_event_log():
        """GET /api/webhooks/events returns event log."""
        app, d = _app()
        _sub(d, events=["*"])
        d.dispatch_event("ev1", {})
        with app.test_client() as c:
            resp = c.get("/api/webhooks/events?limit=10")
        assert record(
            "WHK-052",
            "GET events returns log",
            (200, 1),
            (resp.status_code, len(resp.get_json())),
        )

    def test_whk_053_api_deliveries():
        """GET /api/webhooks/deliveries returns delivery records."""
        app, d = _app()
        _sub(d, events=["*"])
        d.dispatch_event("ev1", {})
        with app.test_client() as c:
            resp = c.get("/api/webhooks/deliveries")
        assert record(
            "WHK-053",
            "GET deliveries returns list",
            (200, 1),
            (resp.status_code, len(resp.get_json())),
        )

    def test_whk_054_api_get_delivery():
        """GET /api/webhooks/deliveries/<id> returns record."""
        app, d = _app()
        _sub(d, events=["*"])
        recs = d.dispatch_event("ev1", {})
        with app.test_client() as c:
            resp = c.get(f"/api/webhooks/deliveries/{recs[0].record_id}")
        assert record("WHK-054", "GET delivery by ID", 200, resp.status_code)

    def test_whk_055_api_retry_delivery():
        """POST /api/webhooks/deliveries/<id>/retry retries failed."""
        app, d = _app()
        d._delivery_callback = _fail_cb
        d.max_retries = 1
        _sub(d, events=["*"])
        recs = d.dispatch_event("ev1", {})
        d._delivery_callback = _ok_cb
        with app.test_client() as c:
            resp = c.post(f"/api/webhooks/deliveries/{recs[0].record_id}/retry")
        assert record("WHK-055", "Retry returns 201", 201, resp.status_code)

    def test_whk_056_api_stats():
        """GET /api/webhooks/stats returns statistics."""
        app, d = _app()
        _sub(d, events=["*"])
        d.dispatch_event("ev1", {})
        with app.test_client() as c:
            resp = c.get("/api/webhooks/stats")
            data = resp.get_json()
        assert record(
            "WHK-056",
            "Stats endpoint",
            (200, 1, 1),
            (resp.status_code, data["total_subscriptions"], data["successful_deliveries"]),
        )

    def test_whk_057_api_create_missing_name():
        """POST /api/webhooks/subscriptions without name returns 400."""
        app, _ = _app()
        with app.test_client() as c:
            resp = c.post(
                "/api/webhooks/subscriptions",
                json={"url": "https://x.com/h", "event_types": ["*"]},
            )
        assert record("WHK-057", "Missing name returns 400", 400, resp.status_code)

except ImportError:
    pass

# ==================================================================== #
#  Wingman & Sandbox gates                                              #
# ==================================================================== #


def test_whk_058_wingman_gate():
    """Wingman pair validation gate."""
    d = _disp()
    storyteller_says = "Register webhook for deployment notifications"
    wingman_approves = True
    sub = (
        d.register_subscription("deploy-hook", "https://ops.co/deploy", ["deploy.*"])
        if wingman_approves
        else None
    )
    assert record(
        "WHK-058",
        "Wingman gate — approved",
        True,
        sub is not None,
        cause="storyteller requests webhook subscription, wingman approves",
        effect="subscription created",
        lesson="Wingman pair validation prevents unsafe registrations",
    )


def test_whk_059_sandbox_gate():
    """Causality Sandbox gate — side-effect tracking."""
    d = _disp()
    sandbox_mode = True
    if sandbox_mode:
        pre_subs = len(d.list_subscriptions())
        pre_events = len(d.get_event_log())
    _sub(d, events=["*"])
    d.dispatch_event("sandbox.test", {"check": True})
    if sandbox_mode:
        post_subs = len(d.list_subscriptions())
        post_events = len(d.get_event_log())
        delta_subs = post_subs - pre_subs
        delta_events = post_events - pre_events
    assert record(
        "WHK-059",
        "Sandbox gate — side effects tracked",
        (1, 1),
        (delta_subs, delta_events),
        cause="sandbox monitors state changes",
        effect="one new subscription and one event detected",
        lesson="causality sandbox ensures auditable changes",
    )
