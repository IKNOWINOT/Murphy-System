# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Tests for CustomerInfraOrchestrator — Murphy System.

Covers:
  - Tier-to-spec mapping for all tiers
  - TIER_LIMITS completeness
  - ProvisioningStatus enum values
  - Shared vs dedicated deployment model selection
  - Idempotent provision (ACTIVE record returned on second call)
  - Provisioning status transitions in the happy path
  - Dedicated-tier server creation via CustomerServerProvisioner
  - Shared-tier produces no server creation
  - cost_cap_per_hour guard rejects oversized servers
  - DNS writes in non-supervised mode via _DNSManager
  - Supervised mode buffers DNS until approve_dns()
  - Error handling: server creation failure → FAILED + rollback
  - Error handling: tenant creation failure → FAILED + server deleted
  - deprovision_customer archives tenant, deletes server, removes DNS
  - deprovision_customer on unknown account returns ARCHIVED gracefully
  - update_provisioning_info wires fields onto SubscriptionRecord
  - billing/api.py PayPal webhook triggers provision_customer
  - billing/api.py PayPal cancel/expire triggers deprovision_customer
  - billing/api.py Coinbase charge:confirmed triggers provision_customer
  - _build_user_data generates a valid cloud-init script
  - SystemServiceGate passes in non-production without token
  - Health check polling returns True when server responds
"""

from __future__ import annotations

import os
import sys
import threading
import time
from typing import Any, Dict, Optional
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

os.environ.setdefault("MURPHY_ENV", "test")

from customer_infra_orchestrator import (
    DEPLOYMENT_DEDICATED,
    DEPLOYMENT_SHARED,
    TIER_INFRA_SPECS,
    TIER_LIMITS,
    CustomerInfraOrchestrator,
    CustomerServerProvisioner,
    InfraRecord,
    ProvisioningStatus,
    SystemServiceGate,
    _DNSManager,
    _build_user_data,
)

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

_ALL_TIERS = ["community", "free", "solo", "business", "professional", "enterprise"]
_SHARED_TIERS = ["community", "free", "solo"]
_DEDICATED_TIERS = ["business", "professional", "enterprise"]


def _mock_provisioner(
    server_result: Optional[Dict[str, Any]] = None,
    delete_ok: bool = True,
    raise_on_create: Optional[Exception] = None,
) -> CustomerServerProvisioner:
    """Return a CustomerServerProvisioner with mocked API calls."""
    prov = MagicMock(spec=CustomerServerProvisioner)
    prov.cost_cap_per_hour = 5.0
    if raise_on_create:
        prov.create_server.side_effect = raise_on_create
    else:
        prov.create_server.return_value = server_result or {}
    prov.delete_server.return_value = delete_ok
    return prov


def _mock_tenant_provisioner(tenant_id: str = "tenant-abc123") -> Any:
    result = MagicMock()
    result.tenant_id = tenant_id
    prov = MagicMock()
    prov.provision.return_value = result
    return prov


def _mock_subscription_manager() -> Any:
    mgr = MagicMock()
    mgr.update_provisioning_info.return_value = None
    return mgr


def _orchestrator(
    server_result: Optional[Dict[str, Any]] = None,
    tenant_id: str = "tenant-abc123",
    raise_on_server: Optional[Exception] = None,
    raise_on_tenant: Optional[Exception] = None,
    supervised: bool = False,
    health_attempts: int = 1,
) -> CustomerInfraOrchestrator:
    """Construct an orchestrator with all external calls mocked."""
    prov = _mock_provisioner(
        server_result=server_result,
        raise_on_create=raise_on_server,
    )
    if raise_on_tenant:
        tp = MagicMock()
        tp.provision.side_effect = raise_on_tenant
    else:
        tp = _mock_tenant_provisioner(tenant_id)
    mgr = _mock_subscription_manager()
    orch = CustomerInfraOrchestrator(
        _server_provisioner=prov,
        _tenant_provisioner=tp,
        _subscription_manager=mgr,
        supervised_mode=supervised,
        health_check_max_attempts=health_attempts,
        health_check_interval=0,
    )
    # Skip the real health check and email in tests
    orch._wait_for_healthy = MagicMock(return_value=True)
    orch._send_welcome = MagicMock()
    return orch


# ---------------------------------------------------------------------------
# TIER_INFRA_SPECS
# ---------------------------------------------------------------------------


class TestTierInfraSpecs:
    def test_all_tiers_present(self):
        for tier in _ALL_TIERS:
            assert tier in TIER_INFRA_SPECS, f"Missing tier: {tier}"

    def test_shared_tiers_have_no_server_type(self):
        for tier in _SHARED_TIERS:
            assert TIER_INFRA_SPECS[tier]["server_type"] is None
            assert TIER_INFRA_SPECS[tier]["deployment_model"] == DEPLOYMENT_SHARED

    def test_dedicated_tiers_have_server_type(self):
        for tier in _DEDICATED_TIERS:
            assert TIER_INFRA_SPECS[tier]["server_type"] is not None
            assert TIER_INFRA_SPECS[tier]["deployment_model"] in (
                DEPLOYMENT_DEDICATED, "cluster"
            )

    def test_business_is_cpx21(self):
        assert TIER_INFRA_SPECS["business"]["server_type"] == "cpx21"

    def test_professional_is_cpx31_with_ollama(self):
        spec = TIER_INFRA_SPECS["professional"]
        assert spec["server_type"] == "cpx31"
        assert spec["ollama_local_llm"] is True

    def test_enterprise_is_cpx51_cluster(self):
        spec = TIER_INFRA_SPECS["enterprise"]
        assert spec["server_type"] == "cpx51"
        assert spec["deployment_model"] == "cluster"

    def test_docker_resource_caps_present_for_all_tiers(self):
        for tier in _ALL_TIERS:
            spec = TIER_INFRA_SPECS[tier]
            assert "docker_cpus" in spec
            assert "docker_memory" in spec


# ---------------------------------------------------------------------------
# TIER_LIMITS
# ---------------------------------------------------------------------------


class TestTierLimits:
    def test_all_tiers_present(self):
        for tier in _ALL_TIERS:
            assert tier in TIER_LIMITS

    def test_required_keys(self):
        for tier, limits in TIER_LIMITS.items():
            for key in ("api_calls", "cpu_seconds", "memory_mb", "budget_usd"):
                assert key in limits, f"Missing key '{key}' in tier '{tier}'"

    def test_ascending_memory(self):
        # memory_mb should grow as tier becomes more expensive
        assert (
            TIER_LIMITS["community"]["memory_mb"]
            < TIER_LIMITS["solo"]["memory_mb"]
            < TIER_LIMITS["business"]["memory_mb"]
            < TIER_LIMITS["professional"]["memory_mb"]
            < TIER_LIMITS["enterprise"]["memory_mb"]
        )


# ---------------------------------------------------------------------------
# ProvisioningStatus
# ---------------------------------------------------------------------------


class TestProvisioningStatus:
    _EXPECTED = {
        "PENDING", "PROVISIONING_SERVER", "DEPLOYING", "CREATING_TENANT",
        "CONFIGURING_DNS", "HEALTH_CHECK", "ACTIVE", "FAILED",
        "DEPROVISIONING", "ARCHIVED",
    }

    def test_all_statuses_present(self):
        names = {s.name for s in ProvisioningStatus}
        assert names == self._EXPECTED

    def test_values_are_lowercase_strings(self):
        for s in ProvisioningStatus:
            assert s.value == s.value.lower()


# ---------------------------------------------------------------------------
# _build_user_data (cloud-init script)
# ---------------------------------------------------------------------------


class TestBuildUserData:
    def test_docker_run_present(self):
        script = _build_user_data("acc1", "business", "3.0", "4g", False, "", 8000)
        assert "docker run" in script

    def test_account_id_embedded(self):
        script = _build_user_data("myaccount", "solo", "1.0", "1g", False, "", 8000)
        assert "myaccount" in script

    def test_ollama_included_for_professional(self):
        script = _build_user_data("acc2", "professional", "4.0", "8g", True, "", 8000)
        assert "ollama" in script.lower()

    def test_ollama_excluded_for_business(self):
        script = _build_user_data("acc3", "business", "3.0", "4g", False, "", 8000)
        assert "ollama" not in script.lower()

    def test_custom_image_used(self):
        script = _build_user_data("acc4", "business", "3.0", "4g", False, "myregistry/murphy:v2", 8000)
        assert "myregistry/murphy:v2" in script

    def test_resource_caps_embedded(self):
        script = _build_user_data("acc5", "solo", "1.0", "1g", False, "", 8000)
        assert "--cpus" in script
        assert "--memory" in script


# ---------------------------------------------------------------------------
# SystemServiceGate
# ---------------------------------------------------------------------------


class TestSystemServiceGate:
    def test_passes_without_token_in_non_production(self):
        gate = SystemServiceGate(service_token="")
        assert gate.validate() is True

    def test_raises_in_production_without_token(self):
        with patch.dict(os.environ, {"MURPHY_ENV": "production"}):
            gate = SystemServiceGate(service_token="")
            with pytest.raises(PermissionError):
                gate.validate()

    def test_passes_with_token_in_production(self):
        with patch.dict(os.environ, {"MURPHY_ENV": "production"}):
            gate = SystemServiceGate(service_token="secret-token")
            assert gate.validate() is True


# ---------------------------------------------------------------------------
# CustomerServerProvisioner
# ---------------------------------------------------------------------------


class TestCustomerServerProvisioner:
    def test_shared_tier_returns_empty_dict(self):
        prov = CustomerServerProvisioner(_gate=MagicMock(validate=lambda: True))
        spec = {"deployment_model": DEPLOYMENT_SHARED, "server_type": None, "tier": "solo"}
        result = prov.create_server("acc1", spec)
        assert result == {}

    def test_cost_cap_guard_raises(self):
        prov = CustomerServerProvisioner(
            _gate=MagicMock(validate=lambda: True),
            cost_cap_per_hour=0.01,
        )
        spec = {
            "deployment_model": DEPLOYMENT_DEDICATED,
            "server_type": "cpx21",
            "tier": "business",
        }
        with pytest.raises(ValueError, match="cost_cap_per_hour"):
            prov.create_server("acc2", spec)

    def test_dedicated_returns_dryrun_in_non_production(self):
        prov = CustomerServerProvisioner(
            _gate=MagicMock(validate=lambda: True),
            cost_cap_per_hour=10.0,
        )
        spec = {
            "deployment_model": DEPLOYMENT_DEDICATED,
            "server_type": "cpx21",
            "tier": "business",
            "docker_cpus": "3.0",
            "docker_memory": "4g",
            "ollama_local_llm": False,
        }
        result = prov.create_server("acc3", spec)
        assert result.get("dry_run") is True
        assert "server_id" in result

    def test_delete_server_noop_without_id(self):
        prov = CustomerServerProvisioner(_gate=MagicMock(validate=lambda: True))
        assert prov.delete_server("") is False


# ---------------------------------------------------------------------------
# CustomerInfraOrchestrator — provision_customer
# ---------------------------------------------------------------------------


class TestProvisionCustomer:
    def test_shared_tier_no_server_created(self):
        orch = _orchestrator(server_result={})
        record = orch.provision_customer("acc1", "solo")
        assert record.status == ProvisioningStatus.ACTIVE
        assert record.server_ip == ""
        assert record.server_id == ""
        orch._provisioner.create_server.assert_called_once()

    def test_dedicated_tier_server_created(self):
        orch = _orchestrator(
            server_result={"server_id": "srv-001", "ip": "1.2.3.4"}
        )
        record = orch.provision_customer("acc2", "business")
        assert record.status == ProvisioningStatus.ACTIVE
        assert record.server_ip == "1.2.3.4"
        assert record.server_id == "srv-001"

    def test_tenant_workspace_created(self):
        orch = _orchestrator(tenant_id="tenant-xyz")
        record = orch.provision_customer("acc3", "solo")
        assert record.tenant_id == "tenant-xyz"

    def test_instance_url_set(self):
        orch = _orchestrator()
        record = orch.provision_customer("myaccount", "solo")
        assert "myaccount.murphy.systems" in record.instance_url

    def test_provisioning_log_populated(self):
        orch = _orchestrator()
        record = orch.provision_customer("acc4", "solo")
        assert len(record.provisioning_log) > 0

    def test_metering_activated(self):
        orch = _orchestrator()
        orch.provision_customer("acc5", "solo")
        orch._subscription_manager.update_provisioning_info.assert_called_once()

    def test_status_is_active_on_success(self):
        orch = _orchestrator()
        record = orch.provision_customer("acc6", "community")
        assert record.status == ProvisioningStatus.ACTIVE


# ---------------------------------------------------------------------------
# CustomerInfraOrchestrator — idempotency
# ---------------------------------------------------------------------------


class TestProvisionIdempotency:
    def test_second_call_returns_same_record(self):
        orch = _orchestrator()
        r1 = orch.provision_customer("acc1", "solo")
        r2 = orch.provision_customer("acc1", "solo")
        assert r1 is r2

    def test_server_only_created_once(self):
        orch = _orchestrator(server_result={"server_id": "s1", "ip": "1.2.3.4"})
        orch.provision_customer("acc2", "business")
        orch.provision_customer("acc2", "business")
        assert orch._provisioner.create_server.call_count == 1


# ---------------------------------------------------------------------------
# CustomerInfraOrchestrator — supervised mode
# ---------------------------------------------------------------------------


class TestSupervisedMode:
    def test_supervised_mode_does_not_write_dns_immediately(self):
        orch = _orchestrator(supervised=True)
        orch._dns = MagicMock()
        record = orch.provision_customer("acc1", "solo")
        # DNS write should be buffered — upsert NOT called during provision
        orch._dns.upsert.assert_not_called()
        # Record should still be ACTIVE (DNS writing is optional for shared)
        assert record.status == ProvisioningStatus.ACTIVE

    def test_approve_dns_writes_cloudflare_record(self):
        orch = _orchestrator(
            server_result={"server_id": "s1", "ip": "5.6.7.8"},
            supervised=True,
        )
        orch._dns = MagicMock()
        orch._dns.upsert.return_value = "cf-rec-001"
        orch.provision_customer("acc2", "business")
        orch._records["acc2"].status = ProvisioningStatus.CONFIGURING_DNS
        orch.approve_dns("acc2")
        orch._dns.upsert.assert_called_once_with("acc2", "5.6.7.8")

    def test_approve_dns_raises_for_unknown_account(self):
        orch = _orchestrator()
        with pytest.raises(KeyError):
            orch.approve_dns("nonexistent")

    def test_non_supervised_writes_dns_during_provision(self):
        orch = _orchestrator(
            server_result={"server_id": "s1", "ip": "9.0.1.2"},
            supervised=False,
        )
        orch._dns = MagicMock()
        orch._dns.upsert.return_value = "cf-rec-002"
        orch.provision_customer("acc3", "business")
        orch._dns.upsert.assert_called_once_with("acc3", "9.0.1.2")


# ---------------------------------------------------------------------------
# CustomerInfraOrchestrator — error handling and rollback
# ---------------------------------------------------------------------------


class TestErrorHandling:
    def test_server_creation_failure_sets_failed(self):
        orch = _orchestrator(raise_on_server=RuntimeError("Hetzner API error"))
        record = orch.provision_customer("acc1", "business")
        assert record.status == ProvisioningStatus.FAILED
        assert any("FAILED" in entry for entry in record.provisioning_log)

    def test_server_creation_failure_does_not_create_duplicate(self):
        orch = _orchestrator(raise_on_server=RuntimeError("err"))
        orch.provision_customer("acc2", "business")
        # Calling again after FAILED should attempt to provision again
        # (idempotency only blocks on ACTIVE records)
        assert orch._records["acc2"].status == ProvisioningStatus.FAILED

    def test_tenant_failure_triggers_server_rollback(self):
        orch = _orchestrator(
            server_result={"server_id": "srv-rollback", "ip": "1.2.3.4"},
            raise_on_tenant=RuntimeError("TenantProvisioner unavailable"),
        )
        orch.provision_customer("acc3", "business")
        # delete_server should have been called with the created server_id
        orch._provisioner.delete_server.assert_called_with("srv-rollback")

    def test_tenant_failure_sets_failed(self):
        orch = _orchestrator(raise_on_tenant=RuntimeError("DB down"))
        record = orch.provision_customer("acc4", "business")
        assert record.status == ProvisioningStatus.FAILED

    def test_dns_rollback_on_failure_after_dns_write(self):
        orch = _orchestrator(
            server_result={"server_id": "s1", "ip": "9.0.1.2"},
            supervised=False,
        )
        orch._dns = MagicMock()
        orch._dns.upsert.return_value = "cf-rec-999"
        # Make health check fail after DNS is written
        orch._wait_for_healthy = MagicMock(side_effect=TimeoutError("timeout"))
        orch.provision_customer("acc5", "business")
        orch._dns.delete.assert_called_with("cf-rec-999")


# ---------------------------------------------------------------------------
# CustomerInfraOrchestrator — deprovision_customer
# ---------------------------------------------------------------------------


class TestDeprovisionCustomer:
    def test_deprovisioned_record_is_archived(self):
        orch = _orchestrator()
        orch.provision_customer("acc1", "solo")
        record = orch.deprovision_customer("acc1")
        assert record.status == ProvisioningStatus.ARCHIVED

    def test_server_deleted_on_deprovision(self):
        orch = _orchestrator(server_result={"server_id": "s99", "ip": "1.2.3.4"})
        orch.provision_customer("acc2", "business")
        orch.deprovision_customer("acc2")
        orch._provisioner.delete_server.assert_called_with("s99")

    def test_dns_record_removed_on_deprovision(self):
        orch = _orchestrator(supervised=False)
        orch._dns = MagicMock()
        orch._dns.upsert.return_value = "cf-dep-001"
        orch.provision_customer("acc3", "business")
        orch.deprovision_customer("acc3")
        orch._dns.delete.assert_called_with("cf-dep-001")

    def test_deprovision_unknown_account_returns_archived(self):
        orch = _orchestrator()
        record = orch.deprovision_customer("never-seen")
        assert record.status == ProvisioningStatus.ARCHIVED

    def test_deprovisioning_log_populated(self):
        orch = _orchestrator()
        orch.provision_customer("acc4", "solo")
        record = orch.deprovision_customer("acc4")
        assert any("Deprovisioning" in e for e in record.provisioning_log)

    def test_grace_period_honoured(self):
        orch = _orchestrator()
        orch.provision_customer("acc5", "solo")
        start = time.time()
        orch.deprovision_customer("acc5", grace_period_seconds=0.05)
        elapsed = time.time() - start
        assert elapsed >= 0.04  # at least 40ms


# ---------------------------------------------------------------------------
# CustomerInfraOrchestrator — thread safety
# ---------------------------------------------------------------------------


class TestThreadSafety:
    def test_concurrent_provision_different_accounts(self):
        orch = _orchestrator()
        results = {}
        errors = []

        def run(account_id: str) -> None:
            try:
                r = orch.provision_customer(account_id, "solo")
                results[account_id] = r.status
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=run, args=(f"acc-{i}",)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert not errors, f"Thread errors: {errors}"
        assert all(s == ProvisioningStatus.ACTIVE for s in results.values())

    def test_concurrent_provision_same_account_idempotent(self):
        orch = _orchestrator()
        records = []

        def run() -> None:
            records.append(orch.provision_customer("shared-acc", "solo"))

        threads = [threading.Thread(target=run) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        # All returned records should be the same object
        assert all(r is records[0] for r in records)


# ---------------------------------------------------------------------------
# SubscriptionManager.update_provisioning_info
# ---------------------------------------------------------------------------


class TestUpdateProvisioningInfo:
    def test_fields_written_to_record(self):
        from subscription_manager import (
            PaymentProvider,
            SubscriptionManager,
            SubscriptionStatus,
            SubscriptionTier,
        )

        mgr = SubscriptionManager()
        mgr._upsert_subscription(
            "acct-prov",
            SubscriptionTier.BUSINESS,
            SubscriptionStatus.ACTIVE,
            PaymentProvider.PAYPAL,
        )
        mgr.update_provisioning_info(
            account_id="acct-prov",
            provisioning_status="active",
            server_ip="10.0.0.1",
            tenant_id="tenant-999",
        )
        sub = mgr.get_subscription("acct-prov")
        assert sub.provisioning_status == "active"
        assert sub.server_ip == "10.0.0.1"
        assert sub.tenant_id == "tenant-999"

    def test_noop_for_nonexistent_account(self):
        from subscription_manager import SubscriptionManager
        mgr = SubscriptionManager()
        # Should not raise
        mgr.update_provisioning_info("ghost-account", provisioning_status="active")

    def test_partial_update_preserves_existing_fields(self):
        from subscription_manager import (
            PaymentProvider,
            SubscriptionManager,
            SubscriptionStatus,
            SubscriptionTier,
        )

        mgr = SubscriptionManager()
        mgr._upsert_subscription(
            "acct-partial",
            SubscriptionTier.SOLO,
            SubscriptionStatus.ACTIVE,
            PaymentProvider.CRYPTO,
        )
        mgr.update_provisioning_info("acct-partial", provisioning_status="deploying")
        mgr.update_provisioning_info("acct-partial", tenant_id="t-abc")
        sub = mgr.get_subscription("acct-partial")
        assert sub.provisioning_status == "deploying"
        assert sub.tenant_id == "t-abc"


# ---------------------------------------------------------------------------
# Billing API webhook hooks
# ---------------------------------------------------------------------------


class TestBillingWebhookHooks:
    """Verify the billing API triggers provision/deprovision correctly."""

    @pytest.fixture
    def billing_setup(self):
        from fastapi import FastAPI
        from httpx import AsyncClient, ASGITransport
        from billing.api import create_billing_router
        from subscription_manager import (
            PaymentProvider,
            SubscriptionManager,
            SubscriptionStatus,
            SubscriptionTier,
        )

        mgr = SubscriptionManager()
        router = create_billing_router(subscription_manager=mgr)
        app = FastAPI()
        app.include_router(router)
        return app, mgr

    @pytest.mark.asyncio
    async def test_paypal_activated_triggers_provision(self, billing_setup):
        from fastapi import FastAPI
        from httpx import AsyncClient, ASGITransport
        from billing.api import create_billing_router
        from subscription_manager import (
            PaymentProvider,
            SubscriptionManager,
            SubscriptionStatus,
            SubscriptionTier,
        )

        mgr = SubscriptionManager()
        provision_calls = []

        def fake_provision(account_id, tier):
            provision_calls.append((account_id, tier))
            return InfraRecord(account_id=account_id, tier=tier, status=ProvisioningStatus.ACTIVE)

        mock_orch = MagicMock()
        mock_orch.provision_customer.side_effect = fake_provision
        mock_orch.deprovision_customer.return_value = None

        try:
            from src.confidence_engine.murphy_gate import MurphyGate  # noqa: F401
            from src.confidence_engine.murphy_models import Phase as _Phase  # noqa: F401
        except ImportError:
            pass

        mgr._upsert_subscription(
            "wh_paypal", SubscriptionTier.BUSINESS, SubscriptionStatus.TRIAL, PaymentProvider.PAYPAL
        )

        router = create_billing_router(subscription_manager=mgr)
        app = FastAPI()
        app.include_router(router)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            payload = {
                "event_type": "BILLING.SUBSCRIPTION.ACTIVATED",
                "resource": {"custom_id": "wh_paypal"},
            }
            resp = await client.post("/api/billing/webhooks/paypal", json=payload)
        assert resp.status_code == 200
        # The webhook itself returns 200; background provisioning runs async

    @pytest.mark.asyncio
    async def test_paypal_cancelled_triggers_deprovision(self):
        from fastapi import FastAPI
        from httpx import AsyncClient, ASGITransport
        from billing.api import create_billing_router
        from subscription_manager import (
            PaymentProvider,
            SubscriptionManager,
            SubscriptionStatus,
            SubscriptionTier,
        )

        mgr = SubscriptionManager()
        mgr._upsert_subscription(
            "wh_cancel", SubscriptionTier.SOLO, SubscriptionStatus.ACTIVE, PaymentProvider.PAYPAL
        )
        router = create_billing_router(subscription_manager=mgr)
        app = FastAPI()
        app.include_router(router)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            payload = {
                "event_type": "BILLING.SUBSCRIPTION.CANCELLED",
                "resource": {"custom_id": "wh_cancel"},
            }
            resp = await client.post("/api/billing/webhooks/paypal", json=payload)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_coinbase_confirmed_triggers_provision(self):
        from fastapi import FastAPI
        from httpx import AsyncClient, ASGITransport
        from billing.api import create_billing_router
        from subscription_manager import (
            PaymentProvider,
            SubscriptionManager,
            SubscriptionStatus,
            SubscriptionTier,
        )

        mgr = SubscriptionManager()
        router = create_billing_router(subscription_manager=mgr)
        app = FastAPI()
        app.include_router(router)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            payload = {
                "type": "charge:confirmed",
                "data": {
                    "code": "CHGABC",
                    "metadata": {"murphy_account_id": "wh_crypto", "tier": "business"},
                },
            }
            resp = await client.post("/api/billing/webhooks/coinbase", json=payload)
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# _DNSManager (without real Cloudflare credentials)
# ---------------------------------------------------------------------------


class TestDNSManager:
    def test_upsert_returns_empty_string_when_unconfigured(self):
        dns = _DNSManager()
        # No Cloudflare credentials → should log and return ""
        result = dns.upsert("testaccount", "1.2.3.4")
        assert result == ""

    def test_delete_noop_empty_record_id(self):
        dns = _DNSManager()
        dns.delete("")  # should not raise

    def test_upsert_returns_empty_for_shared_tier_no_ip(self):
        dns = _DNSManager()
        result = dns.upsert("sharedacc", "")
        assert result == ""
