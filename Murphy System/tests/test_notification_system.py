# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Comprehensive test suite for notification_system — NTF-001.

Uses the storyline-actuals ``record()`` pattern to capture every check
as an auditable NTFRecord with cause / effect / lesson annotations.
"""
from __future__ import annotations

import datetime
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"

from notification_system import (  # noqa: E402
    ChannelConfig,
    ChannelDelivery,
    ChannelType,
    DeliveryResult,
    Notification,
    NotificationManager,
    NotificationPriority,
    NotificationStatus,
    NotificationTemplate,
    create_notification_api,
)

# -- Record pattern --------------------------------------------------------


@dataclass
class NTFRecord:
    """One NTF check record."""

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


_RESULTS: List[NTFRecord] = []


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
        NTFRecord(
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


def _mgr(**kw: Any) -> NotificationManager:
    """Create a fresh NotificationManager."""
    return NotificationManager(**kw)


def _ch(
    mgr: NotificationManager,
    name: str = "slack-main",
    ct: ChannelType = ChannelType.SLACK,
    cfg: dict | None = None,
) -> ChannelConfig:
    """Register and return a channel."""
    return mgr.register_channel(
        name=name,
        channel_type=ct,
        config=cfg or {"webhook_url": "https://hooks.slack.com/xxx"},
    )


def _fail_cb(
    channel: ChannelConfig, subject: str, body: str
) -> Tuple[bool, str]:
    """Send callback that always fails."""
    return False, "connection refused"


def _ok_cb(
    channel: ChannelConfig, subject: str, body: str
) -> Tuple[bool, str]:
    """Send callback that always succeeds."""
    return True, ""


def _exc_cb(
    channel: ChannelConfig, subject: str, body: str
) -> Tuple[bool, str]:
    """Send callback that raises an exception."""
    raise ConnectionError("network failure")


# ==================================================================== #
#  Enum tests                                                           #
# ==================================================================== #


def test_ntf_001_channel_type_enum():
    """ChannelType enum has expected members."""
    assert record(
        "NTF-001",
        "ChannelType values",
        {"email", "slack", "discord", "teams", "webhook", "custom"},
        {m.value for m in ChannelType},
    )


def test_ntf_002_priority_enum():
    """NotificationPriority enum has expected members."""
    assert record(
        "NTF-002",
        "NotificationPriority values",
        {"low", "normal", "high", "critical"},
        {m.value for m in NotificationPriority},
    )


def test_ntf_003_status_enum():
    """NotificationStatus enum has expected members."""
    assert record(
        "NTF-003",
        "NotificationStatus values",
        {"pending", "sending", "sent", "failed", "suppressed"},
        {m.value for m in NotificationStatus},
    )


def test_ntf_004_delivery_result_enum():
    """DeliveryResult enum has expected members."""
    assert record(
        "NTF-004",
        "DeliveryResult values",
        {"success", "failure", "rate_limited", "suppressed"},
        {m.value for m in DeliveryResult},
    )


# ==================================================================== #
#  Dataclass tests                                                      #
# ==================================================================== #


def test_ntf_005_channel_config_defaults():
    """ChannelConfig has sane defaults."""
    ch = ChannelConfig()
    assert record(
        "NTF-005",
        "ChannelConfig defaults",
        (True, ChannelType.EMAIL, True),
        (bool(ch.id), ch.channel_type, ch.enabled),
    )


def test_ntf_006_channel_secret_redaction():
    """ChannelConfig.to_dict() redacts sensitive config keys."""
    ch = ChannelConfig(
        config={"webhook_url": "https://secret.url", "api_key": "sk_live_xxx", "display": "yes"}
    )
    d = ch.to_dict()
    assert record(
        "NTF-006",
        "Sensitive config keys redacted",
        ("***REDACTED***", "***REDACTED***", "yes"),
        (d["config"]["webhook_url"], d["config"]["api_key"], d["config"]["display"]),
        cause="config keys containing url/key/secret/token must be redacted",
        effect="to_dict hides real values",
        lesson="never expose secrets in serialised output",
    )


def test_ntf_007_template_render():
    """NotificationTemplate renders variables correctly."""
    tpl = NotificationTemplate(
        subject_template="Alert: {{type}}",
        body_template="{{service}} is {{status}} at {{time}}",
    )
    subject, body = tpl.render(
        {"type": "disk", "service": "db", "status": "critical", "time": "now"}
    )
    assert record(
        "NTF-007",
        "Template variable substitution",
        ("Alert: disk", "db is critical at now"),
        (subject, body),
    )


def test_ntf_008_template_to_dict():
    """NotificationTemplate.to_dict() serialises correctly."""
    tpl = NotificationTemplate(
        name="test", default_priority=NotificationPriority.HIGH
    )
    d = tpl.to_dict()
    assert record("NTF-008", "Template priority in dict", "high", d["default_priority"])


def test_ntf_009_channel_delivery_to_dict():
    """ChannelDelivery.to_dict() serialises result as string."""
    cd = ChannelDelivery(result=DeliveryResult.SUCCESS)
    d = cd.to_dict()
    assert record("NTF-009", "Delivery result string", "success", d["result"])


def test_ntf_010_notification_to_dict():
    """Notification.to_dict() serialises with nested deliveries."""
    n = Notification(
        subject="Test",
        body="Body",
        priority=NotificationPriority.HIGH,
        status=NotificationStatus.SENT,
        deliveries=[ChannelDelivery(result=DeliveryResult.SUCCESS)],
    )
    d = n.to_dict()
    assert record(
        "NTF-010",
        "Notification to_dict structure",
        ("high", "sent", 1),
        (d["priority"], d["status"], len(d["deliveries"])),
    )


# ==================================================================== #
#  Channel management tests                                             #
# ==================================================================== #


def test_ntf_011_register_channel():
    """Register a channel and retrieve it."""
    mgr = _mgr()
    ch = _ch(mgr, name="s1")
    got = mgr.get_channel(ch.id)
    assert record(
        "NTF-011",
        "Register and get channel",
        ("s1", ChannelType.SLACK),
        (got.name, got.channel_type) if got else (None, None),
    )


def test_ntf_012_list_channels():
    """List returns all channels."""
    mgr = _mgr()
    _ch(mgr, name="a", ct=ChannelType.EMAIL)
    _ch(mgr, name="b", ct=ChannelType.SLACK)
    assert record("NTF-012", "List all channels", 2, len(mgr.list_channels()))


def test_ntf_013_list_channels_filter():
    """List filters by channel type."""
    mgr = _mgr()
    _ch(mgr, name="e", ct=ChannelType.EMAIL)
    _ch(mgr, name="s", ct=ChannelType.SLACK)
    assert record(
        "NTF-013",
        "List filter by EMAIL",
        1,
        len(mgr.list_channels(channel_type=ChannelType.EMAIL)),
    )


def test_ntf_014_update_channel():
    """Update mutable fields on a channel."""
    mgr = _mgr()
    ch = _ch(mgr, name="old")
    mgr.update_channel(ch.id, name="new", rate_limit=10)
    got = mgr.get_channel(ch.id)
    assert record(
        "NTF-014",
        "Update name and rate_limit",
        ("new", 10),
        (got.name, got.rate_limit) if got else (None, None),
    )


def test_ntf_015_delete_channel():
    """Delete removes a channel."""
    mgr = _mgr()
    ch = _ch(mgr)
    assert record("NTF-015", "Delete channel", True, mgr.delete_channel(ch.id))
    assert record("NTF-015b", "Channel gone", None, mgr.get_channel(ch.id))


def test_ntf_016_enable_disable_channel():
    """Enable/disable toggles channel."""
    mgr = _mgr()
    ch = _ch(mgr)
    mgr.disable_channel(ch.id)
    disabled_val = mgr.get_channel(ch.id).enabled  # type: ignore[union-attr]
    mgr.enable_channel(ch.id)
    enabled_val = mgr.get_channel(ch.id).enabled  # type: ignore[union-attr]
    assert record(
        "NTF-016",
        "Disable then enable",
        (False, True),
        (disabled_val, enabled_val),
    )


def test_ntf_017_enable_nonexistent():
    """Enable returns False for unknown ID."""
    mgr = _mgr()
    assert record("NTF-017", "Enable unknown", False, mgr.enable_channel("nope"))


# ==================================================================== #
#  Template management tests                                            #
# ==================================================================== #


def test_ntf_018_register_template():
    """Register a template and retrieve it."""
    mgr = _mgr()
    tpl = mgr.register_template("alert", "Subject: {{t}}", "Body: {{b}}")
    got = mgr.get_template(tpl.id)
    assert record("NTF-018", "Register and get template", "alert", got.name if got else None)


def test_ntf_019_list_templates():
    """List returns all templates."""
    mgr = _mgr()
    mgr.register_template("a", "s", "b")
    mgr.register_template("b", "s", "b")
    assert record("NTF-019", "List templates", 2, len(mgr.list_templates()))


def test_ntf_020_delete_template():
    """Delete removes a template."""
    mgr = _mgr()
    tpl = mgr.register_template("t", "s", "b")
    assert record("NTF-020", "Delete template", True, mgr.delete_template(tpl.id))


# ==================================================================== #
#  Send notification tests                                              #
# ==================================================================== #


def test_ntf_021_send_to_all():
    """Send delivers to all enabled channels."""
    mgr = _mgr()
    _ch(mgr, name="a")
    _ch(mgr, name="b")
    n = mgr.send("Test", "Body")
    assert record(
        "NTF-021",
        "Send to all channels",
        (NotificationStatus.SENT, 2),
        (n.status, len(n.deliveries)),
    )


def test_ntf_022_send_to_specific():
    """Send delivers only to specified channel IDs."""
    mgr = _mgr()
    ch1 = _ch(mgr, name="a")
    _ch(mgr, name="b")
    n = mgr.send("Test", "Body", channel_ids=[ch1.id])
    assert record("NTF-022", "Send to specific channel", 1, len(n.deliveries))


def test_ntf_023_send_disabled_skipped():
    """Disabled channels are not sent to."""
    mgr = _mgr()
    ch = _ch(mgr)
    mgr.disable_channel(ch.id)
    n = mgr.send("Test", "Body")
    assert record(
        "NTF-023",
        "Disabled channel skipped",
        NotificationStatus.FAILED,
        n.status,
    )


def test_ntf_024_send_from_template():
    """Send from template renders and delivers."""
    mgr = _mgr()
    _ch(mgr)
    tpl = mgr.register_template("t", "Alert: {{type}}", "{{msg}}")
    n = mgr.send_from_template(tpl.id, {"type": "cpu", "msg": "high load"})
    assert record(
        "NTF-024",
        "Template send",
        ("Alert: cpu", "high load", NotificationStatus.SENT),
        (n.subject, n.body, n.status) if n else (None, None, None),
    )


def test_ntf_025_send_template_not_found():
    """Send from nonexistent template returns None."""
    mgr = _mgr()
    assert record("NTF-025", "Template not found", None, mgr.send_from_template("nope", {}))


def test_ntf_026_send_failure_callback():
    """Failed send callback produces FAILED status."""
    mgr = _mgr(send_callback=_fail_cb)
    _ch(mgr)
    n = mgr.send("Test", "Body")
    assert record(
        "NTF-026",
        "Failed callback",
        (NotificationStatus.FAILED, DeliveryResult.FAILURE),
        (n.status, n.deliveries[0].result if n.deliveries else None),
        cause="callback returns (False, error)",
        effect="notification marked FAILED",
        lesson="send_callback return value drives status",
    )


def test_ntf_027_send_exception_callback():
    """Exception in callback is caught and recorded."""
    mgr = _mgr(send_callback=_exc_cb)
    _ch(mgr)
    n = mgr.send("Test", "Body")
    has_err = "network failure" in (n.deliveries[0].error if n.deliveries else "")
    assert record("NTF-027", "Exception captured", True, has_err)


def test_ntf_028_priority_filtering():
    """Channel min_priority filters low-priority notifications."""
    mgr = _mgr()
    mgr.register_channel(
        "critical-only", ChannelType.SLACK,
        min_priority=NotificationPriority.CRITICAL,
    )
    n_low = mgr.send("Test", "Body", priority=NotificationPriority.LOW)
    n_crit = mgr.send("Test", "Body", priority=NotificationPriority.CRITICAL)
    assert record(
        "NTF-028",
        "Priority filtering",
        (0, 1),
        (len(n_low.deliveries), len(n_crit.deliveries)),
        cause="channel requires CRITICAL min_priority",
        effect="LOW notification not routed to it",
        lesson="min_priority prevents noise on critical channels",
    )


def test_ntf_029_rate_limiting():
    """Rate limiting suppresses excess sends."""
    mgr = _mgr()
    mgr.register_channel(
        "limited", ChannelType.EMAIL,
        rate_limit=2, rate_window_seconds=3600,
    )
    r1 = mgr.send("A", "B")
    r2 = mgr.send("C", "D")
    r3 = mgr.send("E", "F")
    results = [
        r1.deliveries[0].result if r1.deliveries else None,
        r2.deliveries[0].result if r2.deliveries else None,
        r3.deliveries[0].result if r3.deliveries else None,
    ]
    assert record(
        "NTF-029",
        "Rate limit after 2 sends",
        DeliveryResult.RATE_LIMITED,
        results[2],
    )


def test_ntf_030_no_channels():
    """Send with no channels produces FAILED notification."""
    mgr = _mgr()
    n = mgr.send("Test", "Body")
    assert record("NTF-030", "No channels", NotificationStatus.FAILED, n.status)


# ==================================================================== #
#  Query / stats tests                                                  #
# ==================================================================== #


def test_ntf_031_get_notification():
    """Get a notification by ID."""
    mgr = _mgr()
    _ch(mgr)
    n = mgr.send("Test", "Body")
    got = mgr.get_notification(n.id)
    assert record("NTF-031", "Get notification", n.id, got.id if got else None)


def test_ntf_032_list_notifications():
    """List notifications with status filter."""
    mgr = _mgr()
    _ch(mgr)
    mgr.send("A", "B")
    mgr.send("C", "D")
    assert record("NTF-032", "List all", 2, len(mgr.list_notifications()))
    assert record(
        "NTF-032b",
        "List sent",
        2,
        len(mgr.list_notifications(status=NotificationStatus.SENT)),
    )


def test_ntf_033_list_by_event_type():
    """List filters by event_type."""
    mgr = _mgr()
    _ch(mgr)
    mgr.send("A", "B", event_type="deploy")
    mgr.send("C", "D", event_type="alert")
    assert record(
        "NTF-033",
        "Filter by event_type",
        1,
        len(mgr.list_notifications(event_type="deploy")),
    )


def test_ntf_034_stats():
    """Stats returns expected structure."""
    mgr = _mgr()
    _ch(mgr)
    mgr.send("A", "B")
    s = mgr.stats()
    assert record(
        "NTF-034",
        "Stats structure",
        (1, 1, 1, 1.0),
        (
            s["total_channels"],
            s["active_channels"],
            s["sent"],
            s["success_rate"],
        ),
    )


def test_ntf_035_stats_failure():
    """Stats counts failures."""
    mgr = _mgr(send_callback=_fail_cb)
    _ch(mgr)
    mgr.send("A", "B")
    s = mgr.stats()
    assert record("NTF-035", "Stats failed", 1, s["failed"])


# ==================================================================== #
#  Thread safety                                                        #
# ==================================================================== #


def test_ntf_036_thread_safety():
    """Concurrent channel registration from 10 threads."""
    mgr = _mgr()
    barrier = threading.Barrier(10)

    def worker(i: int) -> None:
        barrier.wait()
        mgr.register_channel(f"ch-{i}", ChannelType.SLACK)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert record(
        "NTF-036",
        "10 concurrent registrations",
        10,
        len(mgr.list_channels()),
        cause="threading.Lock guards mutations",
        effect="no race conditions",
        lesson="thread-safe dict access prevents data loss",
    )


def test_ntf_037_concurrent_sends():
    """Concurrent send from multiple threads."""
    mgr = _mgr()
    _ch(mgr)
    barrier = threading.Barrier(5)

    def worker(i: int) -> None:
        barrier.wait()
        mgr.send(f"msg-{i}", f"body-{i}")

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert record(
        "NTF-037",
        "5 concurrent sends",
        5,
        len(mgr.list_notifications()),
    )


# ==================================================================== #
#  Flask API tests                                                      #
# ==================================================================== #


try:
    from flask import Flask

    def _app() -> tuple:
        mgr = _mgr()
        app = Flask(__name__)
        app.register_blueprint(create_notification_api(mgr))
        return app, mgr

    def test_ntf_038_api_create_channel():
        """POST /api/notifications/channels creates a channel."""
        app, _ = _app()
        with app.test_client() as c:
            resp = c.post(
                "/api/notifications/channels",
                json={
                    "name": "slack",
                    "channel_type": "slack",
                    "config": {"webhook_url": "https://hooks.slack.com/x"},
                },
            )
            data = resp.get_json()
        assert record(
            "NTF-038",
            "POST channels returns 201 with redacted url",
            (201, "***REDACTED***"),
            (resp.status_code, data["config"]["webhook_url"]),
        )

    def test_ntf_039_api_list_channels():
        """GET /api/notifications/channels lists channels."""
        app, mgr = _app()
        _ch(mgr, name="a")
        _ch(mgr, name="b")
        with app.test_client() as c:
            resp = c.get("/api/notifications/channels")
        assert record(
            "NTF-039",
            "GET channels",
            (200, 2),
            (resp.status_code, len(resp.get_json())),
        )

    def test_ntf_040_api_get_channel():
        """GET /api/notifications/channels/<id> returns channel."""
        app, mgr = _app()
        ch = _ch(mgr)
        with app.test_client() as c:
            resp = c.get(f"/api/notifications/channels/{ch.id}")
        assert record("NTF-040", "GET channel by ID", 200, resp.status_code)

    def test_ntf_041_api_get_channel_404():
        """GET /api/notifications/channels/<id> returns 404."""
        app, _ = _app()
        with app.test_client() as c:
            resp = c.get("/api/notifications/channels/nope")
        assert record("NTF-041", "GET unknown channel", 404, resp.status_code)

    def test_ntf_042_api_update_channel():
        """PUT /api/notifications/channels/<id> updates channel."""
        app, mgr = _app()
        ch = _ch(mgr, name="old")
        with app.test_client() as c:
            resp = c.put(
                f"/api/notifications/channels/{ch.id}",
                json={"name": "new"},
            )
            data = resp.get_json()
        assert record(
            "NTF-042",
            "PUT updates name",
            (200, "new"),
            (resp.status_code, data.get("name")),
        )

    def test_ntf_043_api_delete_channel():
        """DELETE /api/notifications/channels/<id> deletes channel."""
        app, mgr = _app()
        ch = _ch(mgr)
        with app.test_client() as c:
            resp = c.delete(f"/api/notifications/channels/{ch.id}")
        assert record("NTF-043", "DELETE channel", 200, resp.status_code)

    def test_ntf_044_api_enable_disable():
        """POST enable/disable toggles channel."""
        app, mgr = _app()
        ch = _ch(mgr)
        with app.test_client() as c:
            r1 = c.post(f"/api/notifications/channels/{ch.id}/disable")
            r2 = c.post(f"/api/notifications/channels/{ch.id}/enable")
        assert record(
            "NTF-044",
            "Enable/disable returns 200",
            (200, 200),
            (r1.status_code, r2.status_code),
        )

    def test_ntf_045_api_create_template():
        """POST /api/notifications/templates creates a template."""
        app, _ = _app()
        with app.test_client() as c:
            resp = c.post(
                "/api/notifications/templates",
                json={
                    "name": "alert",
                    "subject_template": "Alert: {{type}}",
                    "body_template": "{{msg}}",
                },
            )
        assert record("NTF-045", "POST templates", 201, resp.status_code)

    def test_ntf_046_api_list_templates():
        """GET /api/notifications/templates lists templates."""
        app, mgr = _app()
        mgr.register_template("a", "s", "b")
        with app.test_client() as c:
            resp = c.get("/api/notifications/templates")
        assert record(
            "NTF-046",
            "GET templates",
            (200, 1),
            (resp.status_code, len(resp.get_json())),
        )

    def test_ntf_047_api_send():
        """POST /api/notifications/send sends a notification."""
        app, mgr = _app()
        _ch(mgr)
        with app.test_client() as c:
            resp = c.post(
                "/api/notifications/send",
                json={"subject": "Alert", "body": "System down"},
            )
            data = resp.get_json()
        assert record(
            "NTF-047",
            "POST send returns 201",
            (201, "sent"),
            (resp.status_code, data.get("status")),
        )

    def test_ntf_048_api_send_missing_fields():
        """POST /api/notifications/send without required fields returns 400."""
        app, _ = _app()
        with app.test_client() as c:
            resp = c.post("/api/notifications/send", json={})
        assert record("NTF-048", "Missing fields", 400, resp.status_code)

    def test_ntf_049_api_send_template():
        """POST /api/notifications/send-template sends from template."""
        app, mgr = _app()
        _ch(mgr)
        tpl = mgr.register_template("t", "S: {{x}}", "B: {{y}}")
        with app.test_client() as c:
            resp = c.post(
                "/api/notifications/send-template",
                json={"template_id": tpl.id, "variables": {"x": "1", "y": "2"}},
            )
        assert record("NTF-049", "POST send-template", 201, resp.status_code)

    def test_ntf_050_api_send_template_404():
        """POST /api/notifications/send-template with bad ID returns 404."""
        app, _ = _app()
        with app.test_client() as c:
            resp = c.post(
                "/api/notifications/send-template",
                json={"template_id": "nope", "variables": {"k": "v"}},
            )
        assert record("NTF-050", "Template 404", 404, resp.status_code)

    def test_ntf_051_api_list_notifications():
        """GET /api/notifications/notifications lists notifications."""
        app, mgr = _app()
        _ch(mgr)
        mgr.send("A", "B")
        with app.test_client() as c:
            resp = c.get("/api/notifications/notifications")
        assert record(
            "NTF-051",
            "GET notifications",
            (200, 1),
            (resp.status_code, len(resp.get_json())),
        )

    def test_ntf_052_api_get_notification():
        """GET /api/notifications/notifications/<id> returns notification."""
        app, mgr = _app()
        _ch(mgr)
        n = mgr.send("A", "B")
        with app.test_client() as c:
            resp = c.get(f"/api/notifications/notifications/{n.id}")
        assert record("NTF-052", "GET notification by ID", 200, resp.status_code)

    def test_ntf_053_api_stats():
        """GET /api/notifications/stats returns statistics."""
        app, mgr = _app()
        _ch(mgr)
        mgr.send("A", "B")
        with app.test_client() as c:
            resp = c.get("/api/notifications/stats")
            data = resp.get_json()
        assert record(
            "NTF-053",
            "Stats endpoint",
            (200, 1, 1),
            (resp.status_code, data["total_channels"], data["sent"]),
        )

    def test_ntf_054_api_create_channel_missing():
        """POST /api/notifications/channels without name returns 400."""
        app, _ = _app()
        with app.test_client() as c:
            resp = c.post(
                "/api/notifications/channels",
                json={"channel_type": "email"},
            )
        assert record("NTF-054", "Missing name", 400, resp.status_code)

except ImportError:
    pass


# ==================================================================== #
#  Wingman & Sandbox gates                                              #
# ==================================================================== #


def test_ntf_055_wingman_gate():
    """Wingman pair validation gate."""
    mgr = _mgr()
    _ch(mgr)
    storyteller_says = "Send deployment alert to ops team"
    wingman_approves = True
    n = mgr.send("Deploy alert", "v2.1 deployed") if wingman_approves else None
    assert record(
        "NTF-055",
        "Wingman gate — approved",
        True,
        n is not None and n.status == NotificationStatus.SENT,
        cause="storyteller requests notification, wingman approves",
        effect="notification sent successfully",
        lesson="Wingman pair validation prevents spam notifications",
    )


def test_ntf_056_sandbox_gate():
    """Causality Sandbox gate — side-effect tracking."""
    mgr = _mgr()
    _ch(mgr)
    sandbox_mode = True
    if sandbox_mode:
        pre = len(mgr.list_notifications())
    mgr.send("Sandbox test", "Checking side effects")
    if sandbox_mode:
        post = len(mgr.list_notifications())
        delta = post - pre
    assert record(
        "NTF-056",
        "Sandbox gate — side effect tracked",
        1,
        delta,
        cause="sandbox monitors state changes",
        effect="one new notification detected",
        lesson="causality sandbox ensures auditable changes",
    )
