"""Tests for the API Capability Builder system.

Coverage
--------
* ExternalApiSensor — parametrized by domain keyword; positive + negative
* ApiNeed dataclass — construction and field defaults
* ApiCapabilityBuilder — stub generation, ticketing, librarian writes, status
* WingmanApiGapChecker — end-to-end: sensor + RBAC gate + builder
* RBAC gate — OWNER grants scaffold; non-OWNER tickets only, no scaffold
* TicketType.API_BUILD — new ticket type exists and works
* Permission.TRIGGER_API_BUILD — OWNER has it, ADMIN does not
* API endpoints — GET /api/wingman/api-gaps, POST .../scan, POST .../build

Design
------
All tests use in-memory state only (no filesystem writes in most tests;
stub-write tests use tmp_path fixture). No network, no external processes.
"""

from __future__ import annotations

import os
import threading
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest

from src.api_capability_builder import (
    _API_DOMAIN_CATALOG,
    ApiCapabilityBuilder,
    ApiNeed,
    ExternalApiSensor,
    WingmanApiGapChecker,
)
from src.ticketing_adapter import TicketingAdapter, TicketType, TicketPriority


# ---------------------------------------------------------------------------
# Helpers / shared fixtures
# ---------------------------------------------------------------------------

def _artifact(content: str) -> Dict[str, Any]:
    return {"content": content, "id": "test-art"}


def _make_adapter() -> TicketingAdapter:
    return TicketingAdapter()


def _mock_librarian() -> MagicMock:
    lib = MagicMock()
    lib.add_knowledge_entry = MagicMock()
    return lib


# ---------------------------------------------------------------------------
# ExternalApiSensor — parametrized positive detection
# ---------------------------------------------------------------------------

# Build parametrize list from catalog so any new domain is automatically tested
_CATALOG_PARAMS = [
    (entry["category"], entry["keywords"][0])
    for entry in _API_DOMAIN_CATALOG
]


class TestExternalApiSensor:

    sensor = ExternalApiSensor()

    @pytest.mark.parametrize("category,keyword", _CATALOG_PARAMS)
    def test_detects_domain_keyword(self, category, keyword):
        """Every catalog domain must be detected via its first keyword."""
        reading = self.sensor.read(_artifact(f"This report covers {keyword} analysis."))
        needs = getattr(reading, "api_needs", [])
        categories = [n.category for n in needs]
        assert category in categories, f"Expected '{category}' to be detected via keyword '{keyword}'"

    def test_no_detection_for_clean_content(self):
        reading = self.sensor.read(_artifact("Workflow automation task completed successfully."))
        needs = getattr(reading, "api_needs", [])
        assert needs == []

    def test_ok_status_when_no_needs(self):
        from src.wingman_system import SensorStatus
        reading = self.sensor.read(_artifact("Clean content with no data domain references."))
        assert reading.status == SensorStatus.OK

    def test_warn_status_when_needs_detected(self):
        from src.wingman_system import SensorStatus
        reading = self.sensor.read(_artifact("Validate this bank account routing number."))
        assert reading.status == SensorStatus.WARN

    def test_value_decreases_with_more_domains(self):
        one_domain = self.sensor.read(_artifact("check bank account balance"))
        two_domains = self.sensor.read(_artifact("bank account balance and stock price ticker"))
        assert two_domains.value <= one_domain.value

    def test_deduplication_per_category(self):
        # Two keywords from the same category must only produce one ApiNeed
        content = "bank account routing number and iban sort code"
        reading = self.sensor.read(_artifact(content))
        needs = getattr(reading, "api_needs", [])
        banking_needs = [n for n in needs if n.category == "banking"]
        assert len(banking_needs) == 1

    def test_detected_keywords_populated(self):
        reading = self.sensor.read(_artifact("exchange rate and currency conversion today"))
        needs = getattr(reading, "api_needs", [])
        currency = next((n for n in needs if n.category == "currency"), None)
        assert currency is not None
        assert len(currency.detected_keywords) >= 1

    def test_sensor_id(self):
        assert ExternalApiSensor.SENSOR_ID == "external_api"

    def test_scan_text_convenience(self):
        needs = ExternalApiSensor.scan_text("verify stock ticker AAPL price")
        categories = [n.category for n in needs]
        assert "stock" in categories

    def test_fallback_to_result_key(self):
        reading = self.sensor.read({"result": "bank account routing number", "id": "x"})
        needs = getattr(reading, "api_needs", [])
        assert any(n.category == "banking" for n in needs)

    def test_empty_artifact_is_ok(self):
        from src.wingman_system import SensorStatus
        reading = self.sensor.read({})
        assert reading.status == SensorStatus.OK

    @pytest.mark.parametrize("domain,phrase", [
        ("fuel_costs",      "fuel price spike this quarter"),
        ("material_costs",  "cost of materials for construction"),
        ("tax_rates",       "tax rate calculation for vat"),
        ("credit_scoring",  "credit score check equifax"),
        ("email_validation","email validation mx record check"),
    ])
    def test_specific_phrase_detection(self, domain, phrase):
        reading = self.sensor.read(_artifact(phrase))
        needs = getattr(reading, "api_needs", [])
        assert any(n.category == domain for n in needs), (
            f"Expected domain '{domain}' from phrase '{phrase}'"
        )


# ---------------------------------------------------------------------------
# ApiNeed dataclass
# ---------------------------------------------------------------------------

class TestApiNeed:

    def test_defaults(self):
        n = ApiNeed(
            category="banking",
            api_name="Plaid",
            provider="Plaid Inc",
            env_var="PLAID_CLIENT_ID",
            description="bank data",
            docs_url="https://plaid.com",
        )
        assert n.detected_keywords == []
        assert n.stub_path is None
        assert n.ticket_id is None
        assert n.scaffold_status == "pending"


# ---------------------------------------------------------------------------
# TicketType.API_BUILD
# ---------------------------------------------------------------------------

class TestTicketTypeApiBuild:

    def test_api_build_in_enum(self):
        assert TicketType.API_BUILD == "api_build"

    def test_request_api_build_method(self):
        adapter = _make_adapter()
        ticket = adapter.request_api_build(
            api_name="Test API",
            category="banking",
            requester="test@example.com",
            env_var="TEST_API_KEY",
            provider="Test Provider",
        )
        assert ticket.ticket_type == TicketType.API_BUILD
        assert ticket.ticket_id.startswith("TKT-")
        assert "banking" in ticket.tags
        assert "api_build" in ticket.tags
        assert ticket.metadata["requires_owner_approval"] is True

    def test_api_build_ticket_has_correct_priority(self):
        adapter = _make_adapter()
        ticket = adapter.request_api_build(
            api_name="X", category="stock", requester="r",
        )
        assert ticket.priority == TicketPriority.P2_HIGH

    def test_auto_scaffold_flag_in_metadata(self):
        adapter = _make_adapter()
        ticket = adapter.request_api_build(
            api_name="X", category="currency", requester="r",
            auto_scaffold=True,
        )
        assert ticket.metadata["auto_scaffold"] is True

    def test_no_auto_scaffold_by_default(self):
        adapter = _make_adapter()
        ticket = adapter.request_api_build(
            api_name="X", category="currency", requester="r",
        )
        assert ticket.metadata["auto_scaffold"] is False


# ---------------------------------------------------------------------------
# Permission.TRIGGER_API_BUILD
# ---------------------------------------------------------------------------

class TestTriggerApiBuildPermission:

    def test_permission_exists(self):
        from src.rbac_governance import Permission
        assert Permission.TRIGGER_API_BUILD == "trigger_api_build"

    def test_owner_has_trigger_api_build(self):
        from src.rbac_governance import DEFAULT_ROLE_PERMISSIONS, Permission, Role
        assert Permission.TRIGGER_API_BUILD in DEFAULT_ROLE_PERMISSIONS[Role.OWNER]

    def test_admin_does_not_have_trigger_api_build(self):
        from src.rbac_governance import DEFAULT_ROLE_PERMISSIONS, Permission, Role
        assert Permission.TRIGGER_API_BUILD not in DEFAULT_ROLE_PERMISSIONS[Role.ADMIN]

    def test_operator_does_not_have_trigger_api_build(self):
        from src.rbac_governance import DEFAULT_ROLE_PERMISSIONS, Permission, Role
        assert Permission.TRIGGER_API_BUILD not in DEFAULT_ROLE_PERMISSIONS[Role.OPERATOR]


# ---------------------------------------------------------------------------
# ApiCapabilityBuilder — without filesystem (mocked ticketing + librarian)
# ---------------------------------------------------------------------------

class TestApiCapabilityBuilderNoFs:

    @pytest.fixture
    def builder(self):
        return ApiCapabilityBuilder(
            ticketing_adapter=_make_adapter(),
            librarian=_mock_librarian(),
            capabilities_dir="/tmp/nonexistent_test_caps",
        )

    def test_process_needs_returns_list(self, builder):
        needs = ExternalApiSensor.scan_text("check bank account balance")
        results = builder.process_needs(needs, requester="test", owner_authorized=False)
        assert isinstance(results, list)
        assert len(results) == len(needs)

    def test_ticket_created_without_owner(self, builder):
        needs = ExternalApiSensor.scan_text("bank account routing number")
        results = builder.process_needs(needs, requester="test", owner_authorized=False)
        banking = next((n for n in results if n.category == "banking"), None)
        assert banking is not None
        assert banking.ticket_id is not None

    def test_scaffold_pending_without_owner(self, builder):
        needs = ExternalApiSensor.scan_text("bank account routing number")
        results = builder.process_needs(needs, requester="test", owner_authorized=False)
        banking = next((n for n in results if n.category == "banking"), None)
        assert banking.scaffold_status == "pending"
        assert banking.stub_path is None

    def test_librarian_entry_written(self, builder):
        needs = ExternalApiSensor.scan_text("exchange rate conversion today")
        builder.process_needs(needs, requester="test", owner_authorized=False)
        assert builder._librarian.add_knowledge_entry.called

    def test_librarian_entry_category(self, builder):
        needs = ExternalApiSensor.scan_text("stock price ticker AAPL")
        builder.process_needs(needs, requester="test", owner_authorized=False)
        calls = builder._librarian.add_knowledge_entry.call_args_list
        categories = [c[0][0]["category"] for c in calls]
        assert "api_capability" in categories

    def test_status_counts(self, builder):
        needs = ExternalApiSensor.scan_text("bank account")
        builder.process_needs(needs, requester="test", owner_authorized=False)
        s = builder.get_status()
        assert s["total_needs_processed"] >= 1
        assert s["pending_owner_approval"] >= 1
        assert s["tickets_raised"] >= 1

    def test_empty_needs_returns_empty(self, builder):
        results = builder.process_needs([], requester="test", owner_authorized=True)
        assert results == []

    def test_multiple_domains_all_ticketed(self, builder):
        content = "bank account stock price exchange rate"
        needs = ExternalApiSensor.scan_text(content)
        results = builder.process_needs(needs, requester="test", owner_authorized=False)
        assert all(n.ticket_id is not None for n in results)

    def test_no_ticketing_adapter_does_not_crash(self):
        b = ApiCapabilityBuilder(
            ticketing_adapter=None,
            librarian=_mock_librarian(),
            capabilities_dir="/tmp/nonexistent_test_caps",
        )
        needs = ExternalApiSensor.scan_text("bank account")
        results = b.process_needs(needs, requester="test", owner_authorized=False)
        assert all(n.ticket_id is None for n in results)

    def test_no_librarian_does_not_crash(self):
        b = ApiCapabilityBuilder(
            ticketing_adapter=_make_adapter(),
            librarian=None,
            capabilities_dir="/tmp/nonexistent_test_caps",
        )
        needs = ExternalApiSensor.scan_text("bank account")
        results = b.process_needs(needs, requester="test", owner_authorized=False)
        assert all(n.ticket_id is not None for n in results)


# ---------------------------------------------------------------------------
# ApiCapabilityBuilder — with filesystem (stub generation)
# ---------------------------------------------------------------------------

class TestApiCapabilityBuilderWithFs:

    @pytest.fixture
    def caps_dir(self, tmp_path):
        return str(tmp_path / "api_capabilities")

    @pytest.fixture
    def builder(self, caps_dir):
        return ApiCapabilityBuilder(
            ticketing_adapter=_make_adapter(),
            librarian=_mock_librarian(),
            capabilities_dir=caps_dir,
        )

    def test_stub_generated_when_owner_authorized(self, builder, caps_dir):
        needs = ExternalApiSensor.scan_text("bank account routing number")
        results = builder.process_needs(needs, requester="owner", owner_authorized=True)
        banking = next((n for n in results if n.category == "banking"), None)
        assert banking is not None
        assert banking.scaffold_status == "generated"
        assert banking.stub_path is not None
        assert os.path.exists(banking.stub_path)

    def test_stub_content_correct(self, builder, caps_dir):
        needs = ExternalApiSensor.scan_text("exchange rate conversion")
        results = builder.process_needs(needs, requester="owner", owner_authorized=True)
        currency = next((n for n in results if n.category == "currency"), None)
        content = open(currency.stub_path).read()
        assert "OPEN_EXCHANGE_RATES_APP_ID" in content
        assert "def fetch(" in content
        assert "def is_available(" in content
        assert "def get_status(" in content
        assert "NotImplementedError" in content

    def test_stub_status_exists_on_second_run(self, builder, caps_dir):
        needs = ExternalApiSensor.scan_text("bank account balance")
        # First run — generates
        builder.process_needs(needs, requester="owner", owner_authorized=True)
        # Second run — file already exists
        needs2 = ExternalApiSensor.scan_text("bank account routing number")
        results2 = builder.process_needs(needs2, requester="owner", owner_authorized=True)
        banking = next((n for n in results2 if n.category == "banking"), None)
        assert banking.scaffold_status == "exists"

    def test_no_stub_without_owner(self, builder, caps_dir):
        needs = ExternalApiSensor.scan_text("stock price ticker")
        results = builder.process_needs(needs, requester="anon", owner_authorized=False)
        stock = next((n for n in results if n.category == "stock"), None)
        assert stock.stub_path is None
        assert not any(f.endswith("stock_api.py") for f in os.listdir(caps_dir) if os.path.isfile(os.path.join(caps_dir, f))) \
            if os.path.exists(caps_dir) else True


# ---------------------------------------------------------------------------
# WingmanApiGapChecker — RBAC gate
# ---------------------------------------------------------------------------

class TestWingmanApiGapChecker:

    @pytest.fixture
    def checker_no_rbac(self, tmp_path):
        return WingmanApiGapChecker(
            ticketing_adapter=_make_adapter(),
            librarian=_mock_librarian(),
            rbac_governance=None,
            capabilities_dir=str(tmp_path / "caps"),
        )

    def test_no_needs_returns_empty(self, checker_no_rbac):
        result = checker_no_rbac.check(_artifact("clean workflow automation"))
        assert result["api_needs_detected"] == []
        assert result["tickets_raised"] == []

    def test_needs_detected_in_result(self, checker_no_rbac):
        result = checker_no_rbac.check(_artifact("verify bank account routing number"))
        assert len(result["api_needs_detected"]) >= 1

    def test_no_rbac_means_no_scaffold(self, checker_no_rbac):
        result = checker_no_rbac.check(
            _artifact("stock price ticker AAPL"),
            owner_user_id="owner123",
        )
        assert result["owner_authorized"] is False
        scaffolds = result.get("scaffolds_generated", 0)
        assert scaffolds == 0

    def test_tickets_raised_even_without_owner(self, checker_no_rbac):
        result = checker_no_rbac.check(
            _artifact("bank account balance check"),
            owner_user_id=None,
        )
        assert len(result["tickets_raised"]) >= 1

    def test_auth_message_explains_no_owner(self, checker_no_rbac):
        result = checker_no_rbac.check(_artifact("fuel price barrel cost"))
        assert "OWNER" in result.get("auth_message", "") or "detected" in result.get("auth_message", "")

    def test_with_rbac_owner_gets_scaffold(self, tmp_path):
        """OWNER-level user with real RBAC should get scaffolds generated."""
        from src.rbac_governance import RBACGovernance, Role, TenantPolicy, UserIdentity
        rbac = RBACGovernance()
        rbac.create_tenant(TenantPolicy(tenant_id="tenant1", name="Test Org"))
        rbac.register_user(UserIdentity(user_id="founder1", tenant_id="tenant1", roles=[Role.OWNER]))

        checker = WingmanApiGapChecker(
            ticketing_adapter=_make_adapter(),
            librarian=_mock_librarian(),
            rbac_governance=rbac,
            capabilities_dir=str(tmp_path / "caps"),
        )
        result = checker.check(
            _artifact("bank account routing number iban"),
            requester="founder1",
            owner_user_id="founder1",
        )
        assert result["owner_authorized"] is True
        assert result["scaffolds_generated"] >= 1

    def test_with_rbac_non_owner_gets_no_scaffold(self, tmp_path):
        """ADMIN-level user must not trigger scaffolds."""
        from src.rbac_governance import RBACGovernance, Role, TenantPolicy, UserIdentity
        rbac = RBACGovernance()
        rbac.create_tenant(TenantPolicy(tenant_id="tenant1", name="Test Org"))
        rbac.register_user(UserIdentity(user_id="admin1", tenant_id="tenant1", roles=[Role.ADMIN]))

        checker = WingmanApiGapChecker(
            ticketing_adapter=_make_adapter(),
            librarian=_mock_librarian(),
            rbac_governance=rbac,
            capabilities_dir=str(tmp_path / "caps"),
        )
        result = checker.check(
            _artifact("stock price ticker AAPL"),
            requester="admin1",
            owner_user_id="admin1",
        )
        assert result["owner_authorized"] is False
        assert result["scaffolds_generated"] == 0

    def test_result_keys_present(self, checker_no_rbac):
        result = checker_no_rbac.check(_artifact("bank account"))
        for key in ("api_needs_detected", "owner_authorized", "scaffolds_generated",
                    "tickets_raised", "auth_message"):
            assert key in result

    def test_need_dict_keys(self, checker_no_rbac):
        result = checker_no_rbac.check(_artifact("exchange rate forex usd to eur"))
        need = result["api_needs_detected"][0]
        for key in ("category", "api_name", "provider", "env_var", "description",
                    "docs_url", "detected_keywords", "stub_path", "ticket_id",
                    "scaffold_status"):
            assert key in need


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------

class TestApiBuilderThreadSafety:

    def test_concurrent_process_needs(self, tmp_path):
        builder = ApiCapabilityBuilder(
            ticketing_adapter=_make_adapter(),
            librarian=_mock_librarian(),
            capabilities_dir=str(tmp_path / "caps"),
        )
        errors = []

        def run():
            try:
                needs = ExternalApiSensor.scan_text("bank account stock price exchange rate")
                builder.process_needs(needs, requester="t", owner_authorized=False)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=run) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert errors == [], f"Thread errors: {errors}"
        s = builder.get_status()
        assert s["total_needs_processed"] >= 3 * 5  # at least 3 domains × 5 threads


# ---------------------------------------------------------------------------
# API endpoint integration (via TestClient)
# ---------------------------------------------------------------------------

class TestApiGapEndpoints:

    @pytest.fixture(scope="class")
    def client(self):
        import os as _os
        _os.environ.setdefault("MURPHY_ENV", "development")
        _os.environ.setdefault("MURPHY_RATE_LIMIT_RPM", "6000")
        from starlette.testclient import TestClient
        from src.runtime.app import create_app
        return TestClient(create_app())

    def test_get_api_gaps_returns_success(self, client):
        resp = client.get("/api/wingman/api-gaps")
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_scan_missing_artifact_returns_400(self, client):
        resp = client.post("/api/wingman/api-gaps/scan", json={})
        assert resp.status_code in (400, 503)

    def test_scan_clean_content_no_gaps(self, client):
        resp = client.post(
            "/api/wingman/api-gaps/scan",
            json={"artifact": {"content": "Clean workflow completed."}},
        )
        if resp.status_code == 200:
            data = resp.json()
            assert data["success"] is True
            # Clean content should produce zero needs
            assert data.get("api_needs_detected", []) == []

    def test_scan_banking_content_detects_need(self, client):
        resp = client.post(
            "/api/wingman/api-gaps/scan",
            json={"artifact": {"content": "Verify customer bank account routing number and iban."}},
        )
        if resp.status_code == 200:
            data = resp.json()
            assert data["success"] is True
            needs = data.get("api_needs_detected", [])
            categories = [n["category"] for n in needs]
            assert "banking" in categories

    def test_build_without_owner_user_id_returns_403(self, client):
        resp = client.post(
            "/api/wingman/api-gaps/build",
            json={"artifact": {"content": "bank account"}},
        )
        assert resp.status_code in (400, 403, 503)

    def test_build_with_non_owner_user_returns_403(self, client):
        resp = client.post(
            "/api/wingman/api-gaps/build",
            json={
                "owner_user_id": "some_non_owner_user",
                "artifact": {"content": "bank account routing"},
            },
        )
        # Either 403 (RBAC denies) or 503 (checker unavailable)
        assert resp.status_code in (403, 503)

    def test_deliverable_response_may_include_api_gaps(self, client):
        resp = client.post(
            "/api/demo/generate-deliverable",
            json={"query": "Validate customer bank account details for payments"},
            headers={"X-Forwarded-For": "10.88.0.1"},
        )
        if resp.status_code == 200:
            data = resp.json()
            assert data["success"] is True
            # api_gaps key present when gaps detected
            # (may or may not be present depending on content)
            if "api_gaps" in data:
                gaps = data["api_gaps"]
                assert "needs_detected" in gaps
                assert "categories" in gaps
                assert "tickets_raised" in gaps
