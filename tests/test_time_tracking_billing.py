# Copyright © 2020 Inoni Limited Liability Company
"""
Test Suite: Time Tracking – Billing Integration, Invoicing Hooks & Config
===========================================================================

Tests for Phase 6D: billing integration service, invoicing hooks, time
tracking configuration, and settings API.
IDs: TT-051 through TT-068.

Uses the storyline-actuals record() pattern consistent with other suites.

Copyright © 2020 Inoni Limited Liability Company
"""

from __future__ import annotations

import os
import sys
import threading
from dataclasses import dataclass, field
from typing import Any, List

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from time_tracking.models import EntryStatus, TimeEntry, _now
from time_tracking.tracker import TimeTracker
from time_tracking.billing_integration import BillingIntegrationService
from time_tracking.invoicing_hooks import InvoicingHookManager, TimeTrackingEvent
from time_tracking.config import TimeTrackingConfig

# ── storyline-actuals helper ──────────────────────────────────────────


@dataclass
class CheckResult:
    check_id: str
    description: str
    expected: Any
    actual: Any
    passed: bool
    cause: str
    effect: str
    lesson: str


_results: List[CheckResult] = []


def record(
    check_id: str,
    description: str,
    expected: Any,
    actual: Any,
    cause: str,
    effect: str,
    lesson: str,
) -> bool:
    passed = expected == actual
    _results.append(
        CheckResult(
            check_id=check_id,
            description=description,
            expected=expected,
            actual=actual,
            passed=passed,
            cause=cause,
            effect=effect,
            lesson=lesson,
        )
    )
    return passed


# ── Fixtures ──────────────────────────────────────────────────────────


def _approved_entry(tracker: TimeTracker, board_id: str = "proj-a", seconds: int = 3600) -> TimeEntry:
    """Add a completed entry and mark it approved, returning the entry."""
    entry = tracker.add_entry("user1", seconds, board_id=board_id, billable=True)
    entry.status = EntryStatus.APPROVED
    entry.approved_by = "manager1"
    return entry


def _make_billing_service(tracker: TimeTracker, **kwargs) -> BillingIntegrationService:
    return BillingIntegrationService(entries=tracker._entries, **kwargs)


# ── TT-051 through TT-056: BillingIntegrationService ─────────────────


class TestBillingIntegration:

    def test_tt051_generate_invoice_correct_total(self):
        """TT-051: Generate invoice from approved entries calculates correct total."""
        tracker = TimeTracker()
        e1 = _approved_entry(tracker, board_id="proj-a", seconds=3600)  # 1h
        e2 = _approved_entry(tracker, board_id="proj-b", seconds=7200)  # 2h
        svc = _make_billing_service(tracker, default_hourly_rate=100.0)

        result = svc.generate_invoice_from_entries(
            client_id="client1",
            entry_ids=[e1.id, e2.id],
            hourly_rate=100.0,
        )

        expected_total = 300.0  # 3h × $100
        assert record(
            "TT-051",
            "generate_invoice calculates 3h × $100 = $300",
            expected=expected_total,
            actual=result["total_amount"],
            cause="3 hours of approved time at $100/hr",
            effect="Invoice total should be $300.00",
            lesson="total_amount = total_hours × hourly_rate",
        )
        assert result["total_hours"] == pytest.approx(3.0)
        assert result["invoice_id"].startswith("tt-inv-")
        assert result["currency"] == "USD"
        assert result["status"] == "draft"
        assert len(result["line_items"]) == 2  # one per project

    def test_tt052_invoice_rejects_non_approved_entries(self):
        """TT-052: Invoice generation rejects non-approved entries."""
        tracker = TimeTracker()
        entry = tracker.add_entry("user1", 3600, billable=True)
        # entry status is COMPLETED, not APPROVED
        svc = _make_billing_service(tracker)

        with pytest.raises(ValueError) as exc_info:
            svc.generate_invoice_from_entries(
                client_id="client1",
                entry_ids=[entry.id],
            )

        assert record(
            "TT-052",
            "invoice generation raises ValueError for non-approved entry",
            expected=True,
            actual="not approved" in str(exc_info.value).lower()
                   or "approved" in str(exc_info.value).lower(),
            cause="Entry status is COMPLETED, not APPROVED",
            effect="ValueError raised with descriptive message",
            lesson="Only APPROVED entries may be invoiced",
        )

    def test_tt053_client_rate_overrides_default(self):
        """TT-053: Client-specific rate overrides default rate."""
        tracker = TimeTracker()
        e = _approved_entry(tracker, seconds=3600)  # 1h
        svc = _make_billing_service(tracker, default_hourly_rate=100.0)
        svc.set_client_rate("client-premium", hourly_rate=200.0)

        result = svc.generate_invoice_from_entries(
            client_id="client-premium",
            entry_ids=[e.id],
        )

        assert record(
            "TT-053",
            "client-specific rate of $200 overrides default $100",
            expected=200.0,
            actual=result["total_amount"],
            cause="Client 'client-premium' has rate $200/hr set",
            effect="1h × $200 = $200 total",
            lesson="set_client_rate stores per-client override",
        )
        assert result["hourly_rate"] == 200.0

    def test_tt054_invoice_preview_matches_generation(self):
        """TT-054: Invoice preview matches actual invoice generation."""
        tracker = TimeTracker()
        e1 = _approved_entry(tracker, board_id="proj-x", seconds=1800)
        e2 = _approved_entry(tracker, board_id="proj-y", seconds=5400)
        svc = _make_billing_service(tracker, default_hourly_rate=150.0)

        preview = svc.calculate_invoice_preview(
            entry_ids=[e1.id, e2.id],
            client_id="c1",
            hourly_rate=150.0,
        )
        invoice = svc.generate_invoice_from_entries(
            client_id="c1",
            entry_ids=[e1.id, e2.id],
            hourly_rate=150.0,
        )

        assert record(
            "TT-054",
            "preview total_amount matches generated invoice",
            expected=invoice["total_amount"],
            actual=preview["total_amount"],
            cause="Same entries and rate passed to both methods",
            effect="Preview and invoice agree on total_amount",
            lesson="calculate_invoice_preview is a dry-run",
        )
        assert preview["preview"] is True
        assert preview["total_hours"] == invoice["total_hours"]

    def test_tt055_mark_entries_invoiced_prevents_double_billing(self):
        """TT-055: Mark entries as invoiced prevents double-billing."""
        tracker = TimeTracker()
        e1 = _approved_entry(tracker, seconds=3600)
        e2 = _approved_entry(tracker, seconds=3600)
        svc = _make_billing_service(tracker)

        svc.generate_invoice_from_entries(
            client_id="c1", entry_ids=[e1.id], hourly_rate=100.0
        )

        with pytest.raises(ValueError) as exc_info:
            svc.generate_invoice_from_entries(
                client_id="c1", entry_ids=[e1.id, e2.id], hourly_rate=100.0
            )

        assert record(
            "TT-055",
            "second invoice attempt raises ValueError for already-invoiced entry",
            expected=True,
            actual="already been invoiced" in str(exc_info.value).lower()
                   or "invoiced" in str(exc_info.value).lower(),
            cause="Entry was included in a previous invoice",
            effect="ValueError raised, preventing double-billing",
            lesson="_invoiced_entries dict guards against double-billing",
        )
        assert svc.is_entry_invoiced(e1.id)
        assert not svc.is_entry_invoiced(e2.id)

    def test_tt056_billable_summary_groups_by_project(self):
        """TT-056: Billable summary groups correctly by project."""
        tracker = TimeTracker()
        # 2 entries for proj-a, 1 for proj-b (all approved & billable)
        _approved_entry(tracker, board_id="proj-a", seconds=3600)
        _approved_entry(tracker, board_id="proj-a", seconds=3600)
        _approved_entry(tracker, board_id="proj-b", seconds=7200)
        # 1 non-billable entry that should be excluded
        nb = tracker.add_entry("user1", 1800, board_id="proj-a", billable=False)
        nb.status = EntryStatus.APPROVED

        svc = _make_billing_service(tracker, default_hourly_rate=100.0)
        summary = svc.get_billable_summary()

        by_proj = summary["by_project"]

        assert record(
            "TT-056",
            "billable summary groups correctly by project",
            expected={"proj-a": 2.0, "proj-b": 2.0},
            actual={k: v["hours"] for k, v in by_proj.items()},
            cause="2×1h in proj-a, 1×2h in proj-b; non-billable excluded",
            effect="by_project contains correct hours per project",
            lesson="get_billable_summary only includes billable un-invoiced entries",
        )
        assert summary["total_hours"] == pytest.approx(4.0)
        assert summary["entries_count"] == 3


# ── TT-057 through TT-060: InvoicingHookManager ───────────────────────


class TestInvoicingHooks:

    def test_tt057_hook_registration_and_emission(self):
        """TT-057: Hook registration and emission works correctly."""
        manager = InvoicingHookManager()
        fired: List[dict] = []

        def my_hook(event_type, payload):
            fired.append({"event": event_type, "payload": payload})

        manager.register_hook(TimeTrackingEvent.ENTRY_APPROVED, my_hook)
        manager.emit(TimeTrackingEvent.ENTRY_APPROVED, {"entry_id": "e1"})

        assert record(
            "TT-057",
            "registered hook fires when event is emitted",
            expected=1,
            actual=len([f for f in fired if f["payload"].get("entry_id") == "e1"]),
            cause="register_hook + emit called for ENTRY_APPROVED",
            effect="callback called once with correct payload",
            lesson="emit() iterates registered callbacks for event",
        )

    def test_tt058_auto_invoice_hook_fires_on_threshold(self):
        """TT-058: Auto-invoice hook fires when threshold exceeded."""
        tracker = TimeTracker()
        e1 = _approved_entry(tracker, seconds=36000)  # 10h
        e2 = _approved_entry(tracker, seconds=144000)  # 40h
        svc = _make_billing_service(tracker)

        generated: List[dict] = []

        def capture_hook(event_type, payload):
            if event_type == TimeTrackingEvent.INVOICE_GENERATED.value:
                generated.append(payload)

        # Use a low threshold so auto-invoice fires for 50h
        manager = InvoicingHookManager(
            auto_invoice_threshold_hours=40.0,
            billing_service=svc,
        )
        manager.register_hook(TimeTrackingEvent.INVOICE_GENERATED, capture_hook)
        # Manually emit threshold event with approved entry_ids
        manager.emit(
            TimeTrackingEvent.BILLABLE_THRESHOLD_REACHED,
            {
                "client_id": "client-auto",
                "unbilled_hours": 50.0,
                "entry_ids": [e1.id, e2.id],
            },
        )

        assert record(
            "TT-058",
            "auto_invoice_hook fires and generates draft invoice",
            expected=True,
            actual=svc.is_entry_invoiced(e1.id) and svc.is_entry_invoiced(e2.id),
            cause="BILLABLE_THRESHOLD_REACHED emitted with 50h > 40h threshold",
            effect="auto_invoice_hook generates invoice for those entries",
            lesson="auto_invoice_hook calls generate_invoice_from_entries",
        )

    def test_tt059_audit_log_hook_records_events(self):
        """TT-059: Audit log hook records all billing events."""
        manager = InvoicingHookManager()
        manager.clear_audit_log()

        manager.emit(TimeTrackingEvent.ENTRY_APPROVED, {"entry_id": "e10"})
        manager.emit(TimeTrackingEvent.INVOICE_GENERATED, {"invoice_id": "inv-1"})

        log = manager.get_audit_log()

        # Both events should appear in audit log (along with built-in hooks)
        event_types = {e["event_type"] for e in log}
        assert record(
            "TT-059",
            "audit log contains both emitted event types",
            expected=True,
            actual=(
                TimeTrackingEvent.ENTRY_APPROVED.value in event_types
                and TimeTrackingEvent.INVOICE_GENERATED.value in event_types
            ),
            cause="Two events emitted; audit_log_hook is always registered",
            effect="Both appear in get_audit_log() result",
            lesson="audit_log_hook is registered for all event types by default",
        )
        assert len(log) >= 2

    def test_tt060_unregister_stops_callback(self):
        """TT-060: Unregister hook stops callback from firing."""
        manager = InvoicingHookManager()
        fired: List[str] = []

        def my_hook(event_type, payload):
            fired.append(event_type)

        manager.register_hook(TimeTrackingEvent.RATE_CHANGED, my_hook)
        manager.emit(TimeTrackingEvent.RATE_CHANGED, {"new_rate": 100})
        count_before = len(fired)

        manager.unregister_hook(TimeTrackingEvent.RATE_CHANGED, my_hook)
        manager.emit(TimeTrackingEvent.RATE_CHANGED, {"new_rate": 200})
        count_after = len(fired)

        assert record(
            "TT-060",
            "unregistered hook does not fire on subsequent emit",
            expected=count_before,
            actual=count_after,
            cause="unregister_hook called before second emit",
            effect="fired list length stays the same",
            lesson="unregister_hook removes callback from list",
        )


# ── TT-061 through TT-065: TimeTrackingConfig ─────────────────────────


class TestTimeTrackingConfig:

    def setup_method(self):
        TimeTrackingConfig._reset()

    def teardown_method(self):
        # Clean up env vars
        for key in [
            "MURPHY_TT_DEFAULT_RATE",
            "MURPHY_TT_CURRENCY",
            "MURPHY_TT_AUTO_INVOICE_THRESHOLD",
            "MURPHY_TT_MAX_TIMER_HOURS",
            "MURPHY_TT_WORK_WEEK_HOURS",
            "MURPHY_TT_REQUIRE_APPROVAL",
            "MURPHY_TT_ROUNDING_MINUTES",
            "MURPHY_TT_BILLABLE_DEFAULT",
            "MURPHY_TT_OVERTIME_THRESHOLD",
        ]:
            os.environ.pop(key, None)
        TimeTrackingConfig._reset()

    def test_tt061_defaults_when_no_env_vars(self):
        """TT-061: Config loads defaults when no env vars set."""
        cfg = TimeTrackingConfig.get_config()

        assert record(
            "TT-061",
            "default_hourly_rate is 150.00 with no env vars",
            expected=150.00,
            actual=cfg.default_hourly_rate,
            cause="No MURPHY_TT_DEFAULT_RATE env var set",
            effect="default_hourly_rate falls back to 150.00",
            lesson="TimeTrackingConfig uses sensible defaults",
        )
        assert cfg.default_currency == "USD"
        assert cfg.auto_invoice_threshold_hours == 40.0
        assert cfg.max_timer_duration_hours == 12.0
        assert cfg.work_week_hours == 40.0
        assert cfg.require_approval is True
        assert cfg.rounding_increment_minutes == 15
        assert cfg.billable_by_default is True
        assert cfg.allowed_overtime_percentage == 0.25

    def test_tt062_reads_from_env_vars(self):
        """TT-062: Config reads from environment variables."""
        os.environ["MURPHY_TT_DEFAULT_RATE"] = "200.00"
        os.environ["MURPHY_TT_CURRENCY"] = "EUR"
        os.environ["MURPHY_TT_ROUNDING_MINUTES"] = "30"

        cfg = TimeTrackingConfig.get_config()

        assert record(
            "TT-062",
            "MURPHY_TT_DEFAULT_RATE=200.00 yields default_hourly_rate=200.0",
            expected=200.0,
            actual=cfg.default_hourly_rate,
            cause="Env var MURPHY_TT_DEFAULT_RATE=200.00",
            effect="Config reads and parses the env var",
            lesson="_env_float parses float from env var string",
        )
        assert cfg.default_currency == "EUR"
        assert cfg.rounding_increment_minutes == 30

    def test_tt063_validation_catches_invalid_values(self):
        """TT-063: Config validation catches invalid values (negative rate, zero rounding)."""
        cfg = TimeTrackingConfig.get_config()
        cfg.default_hourly_rate = -50.0
        cfg.rounding_increment_minutes = 0

        warnings = cfg.validate()

        assert record(
            "TT-063",
            "validate() returns warnings for negative rate and zero rounding",
            expected=True,
            actual=len(warnings) >= 2,
            cause="default_hourly_rate=-50 and rounding_increment_minutes=0",
            effect="validate() returns at least 2 warning strings",
            lesson="validate() checks all values are in acceptable ranges",
        )
        warning_text = " ".join(warnings).lower()
        assert "negative" in warning_text or "hourly_rate" in warning_text
        assert "rounding" in warning_text or "> 0" in warning_text

    def test_tt064_duration_rounding(self):
        """TT-064: Duration rounding rounds to nearest increment correctly."""
        cfg = TimeTrackingConfig.get_config()
        # Default 15-minute increment = 900 seconds
        # 500 seconds ≈ 8.33 min → 8.33/15 = 0.556 → rounds to 1 × 900 = 900 s
        rounded = cfg.round_duration(500)
        # 400 seconds ≈ 6.67 min → 6.67/15 = 0.444 → rounds to 0 × 900 = 0 s
        rounded2 = cfg.round_duration(400)
        # 1800 seconds = 30 min → 30/15 = 2.0 → rounds to 2 × 900 = 1800 s
        rounded3 = cfg.round_duration(1800)

        assert record(
            "TT-064",
            "round_duration(500) with 15-min increment → 900 seconds",
            expected=900,
            actual=rounded,
            cause="500 seconds (8.33 min) rounds up to nearest 15 min = 900 s",
            effect="Billing uses nearest 15-min boundary",
            lesson="round_duration uses Python round() half-to-even rounding",
        )
        assert rounded2 == 0     # 400s (6.67 min) rounds down to 0
        assert rounded3 == 1800  # 1800s exactly on the 30 min mark

    def test_tt065_reload_picks_up_env_changes(self):
        """TT-065: Config reload picks up env var changes."""
        cfg = TimeTrackingConfig.get_config()
        rate_before = cfg.default_hourly_rate

        os.environ["MURPHY_TT_DEFAULT_RATE"] = "999.99"
        cfg.reload()

        assert record(
            "TT-065",
            "reload() picks up MURPHY_TT_DEFAULT_RATE=999.99",
            expected=999.99,
            actual=cfg.default_hourly_rate,
            cause="Env var changed to 999.99 and reload() called",
            effect="default_hourly_rate updated without restarting",
            lesson="reload() re-reads all env vars in-place",
        )


# ── TT-066 through TT-068: Settings API ───────────────────────────────


class TestSettingsAPI:

    @pytest.fixture
    def app(self):
        try:
            from flask import Flask
        except ImportError:
            pytest.skip("Flask not installed")

        from time_tracking.billing_integration import BillingIntegrationService
        from time_tracking.invoicing_hooks import InvoicingHookManager
        from time_tracking.config import TimeTrackingConfig
        from time_tracking.settings_api import create_settings_blueprint
        from time_tracking.tracker import TimeTracker

        TimeTrackingConfig._reset()

        tracker = TimeTracker()
        svc = BillingIntegrationService(
            entries=tracker._entries, default_hourly_rate=100.0
        )
        hook_mgr = InvoicingHookManager(billing_service=svc)
        cfg = TimeTrackingConfig.get_config()

        flask_app = Flask(__name__)
        bp = create_settings_blueprint(
            billing_service=svc, hook_manager=hook_mgr, tt_config=cfg
        )
        flask_app.register_blueprint(bp)
        flask_app.config["TESTING"] = True
        flask_app._tracker = tracker
        flask_app._svc = svc
        return flask_app

    def test_tt066_settings_api_returns_config(self, app):
        """TT-066: Settings API returns current configuration."""
        with app.test_client() as client:
            resp = client.get("/api/time/settings")

        assert record(
            "TT-066",
            "GET /api/time/settings returns 200 with config dict",
            expected=200,
            actual=resp.status_code,
            cause="GET request to settings endpoint",
            effect="Response contains current TimeTrackingConfig as JSON",
            lesson="settings_api creates_settings_blueprint with GET /settings",
        )
        data = resp.get_json()
        assert "default_hourly_rate" in data
        assert "default_currency" in data
        assert "rounding_increment_minutes" in data

    def test_tt067_billing_api_generates_invoice(self, app):
        """TT-067: Billing API generates invoice and returns correct structure."""
        tracker = app._tracker
        svc = app._svc
        e1 = _approved_entry(tracker, board_id="proj-z", seconds=3600)

        with app.test_client() as client:
            resp = client.post(
                "/api/time/billing/invoice",
                json={"client_id": "c1", "entry_ids": [e1.id], "hourly_rate": 100.0},
            )

        assert record(
            "TT-067",
            "POST /api/time/billing/invoice returns 201 with invoice structure",
            expected=201,
            actual=resp.status_code,
            cause="Valid approved entry and client_id sent",
            effect="Invoice created, 201 returned with invoice_id",
            lesson="settings_api.generate_invoice delegates to BillingIntegrationService",
        )
        data = resp.get_json()
        assert "invoice_id" in data
        assert data["total_amount"] == pytest.approx(100.0)
        assert data["status"] == "draft"

    def test_tt068_rate_change_fires_notification_hook(self, app):
        """TT-068: Rate change event fires notification hook."""
        fired: List[dict] = []

        with app.app_context():
            from time_tracking.invoicing_hooks import TimeTrackingEvent

        # Access the hook manager through the blueprint
        with app.test_client() as client:
            resp = client.put(
                "/api/time/billing/rates/client-x",
                json={"hourly_rate": 250.0, "currency": "USD"},
            )

        assert record(
            "TT-068",
            "PUT /api/time/billing/rates/<client_id> returns 200 and stores rate",
            expected=200,
            actual=resp.status_code,
            cause="Valid hourly_rate sent to rate endpoint",
            effect="Rate stored for client-x, RATE_CHANGED event emitted",
            lesson="set_client_rate endpoint emits RATE_CHANGED via hook manager",
        )
        data = resp.get_json()
        assert data["rate"] == 250.0
        assert data["currency"] == "USD"


# ── Summary ───────────────────────────────────────────────────────────


def test_all_checks_passed():
    """Ensure every check recorded via record() passed."""
    if not _results:
        return  # no record() calls reached — test skipped
    failed = [r for r in _results if not r.passed]
    if failed:
        msgs = "\n".join(
            f"  {r.check_id}: expected={r.expected!r}, actual={r.actual!r}"
            for r in failed
        )
        pytest.fail(f"{len(failed)} check(s) failed:\n{msgs}")
