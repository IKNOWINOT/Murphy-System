# © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
from __future__ import annotations

import pytest
from datetime import datetime, timedelta, timezone
from src.billing.grants.notifications.deadline_alerts import DeadlineAlertSystem, ALERT_THRESHOLDS_DAYS, _sent_alerts, _alerts


@pytest.fixture(autouse=True)
def clear_state():
    """Clear global state before each test."""
    _alerts.clear()
    _sent_alerts.clear()
    yield
    _alerts.clear()
    _sent_alerts.clear()


@pytest.fixture
def alert_system():
    return DeadlineAlertSystem()


def _grant(days_from_now: int, grant_id: str = "g1", title: str = "Test Grant") -> dict:
    deadline = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=days_from_now)
    return {"grant_id": grant_id, "title": title, "deadline": deadline}


def test_no_alerts_for_far_future(alert_system):
    grants = [_grant(60)]
    alerts = alert_system.check_deadlines(grants)
    assert len(alerts) == 0


def test_alert_fires_at_30_days(alert_system):
    grants = [_grant(29)]
    alerts = alert_system.check_deadlines(grants)
    assert any(a.days_before == 30 for a in alerts)


def test_alert_fires_at_14_days(alert_system):
    grants = [_grant(13)]
    alerts = alert_system.check_deadlines(grants)
    thresholds = {a.days_before for a in alerts}
    assert 14 in thresholds


def test_alert_fires_at_7_days(alert_system):
    grants = [_grant(6)]
    alerts = alert_system.check_deadlines(grants)
    thresholds = {a.days_before for a in alerts}
    assert 7 in thresholds


def test_alert_fires_at_3_days(alert_system):
    grants = [_grant(2)]
    alerts = alert_system.check_deadlines(grants)
    thresholds = {a.days_before for a in alerts}
    assert 3 in thresholds


def test_alert_fires_at_1_day(alert_system):
    grants = [_grant(0)]
    alerts = alert_system.check_deadlines(grants)
    thresholds = {a.days_before for a in alerts}
    assert 1 in thresholds


def test_max_one_alert_per_level_per_grant(alert_system):
    grants = [_grant(29)]
    alert_system.check_deadlines(grants)
    # Call again — should NOT fire same level again
    alerts2 = alert_system.check_deadlines(grants)
    level_30 = [a for a in alerts2 if a.days_before == 30 and a.grant_id == "g1"]
    assert len(level_30) == 0


def test_get_active_alerts_returns_undismissed(alert_system):
    grants = [_grant(6)]
    alert_system.check_deadlines(grants)
    active = alert_system.get_active_alerts()
    assert len(active) > 0
    assert all(not a.dismissed for a in active)


def test_dismiss_alert_removes_from_active(alert_system):
    grants = [_grant(6)]
    alerts = alert_system.check_deadlines(grants)
    alert_id = alerts[0].alert_id
    alert_system.dismiss_alert(alert_id)
    active = alert_system.get_active_alerts()
    assert all(a.alert_id != alert_id for a in active)


def test_alert_levels_are_correct(alert_system):
    assert alert_system._level(1) == "critical"
    assert alert_system._level(3) == "urgent"
    assert alert_system._level(7) == "high"
    assert alert_system._level(14) == "medium"
    assert alert_system._level(30) == "low"


def test_multiple_grants_get_independent_alerts(alert_system):
    grants = [
        _grant(6, "g_a", "Grant A"),
        _grant(6, "g_b", "Grant B"),
    ]
    alerts = alert_system.check_deadlines(grants)
    grant_ids = {a.grant_id for a in alerts}
    assert "g_a" in grant_ids
    assert "g_b" in grant_ids


def test_datetime_deadline_object_works(alert_system):
    grants = [{"grant_id": "g_dt", "title": "DT Grant", "deadline": datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=6)}]
    alerts = alert_system.check_deadlines(grants)
    assert len(alerts) > 0
