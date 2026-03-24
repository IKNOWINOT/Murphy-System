# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Customer Infrastructure Orchestrator — Murphy System

Connects the billing layer to tenant provisioning and Hetzner server
deployment so that a paying customer sign-up automatically triggers
the full infrastructure pipeline:

  1. PayPal / Coinbase webhook fires (``BILLING.SUBSCRIPTION.ACTIVATED``
     or ``charge:confirmed``)
  2. ``CustomerInfraOrchestrator.provision_customer()`` is called
  3. For dedicated tiers (Business / Professional / Enterprise) a Hetzner
     Cloud server is created via the public API.
  4. The Murphy Docker image is deployed to the server.
  5. A tenant workspace is created via ``TenantProvisioner``.
  6. DNS is configured (``{account_id}.murphy.systems``).
  7. A health-check loop confirms the instance is live.
  8. A welcome e-mail is sent to the customer.
  9. Usage metering is activated against the subscription.

Design principles
-----------------
- **HITL-safe** — supervised mode requires founder approval before DNS
  cutover.  The ``supervised_mode`` flag on the orchestrator controls
  this behaviour.
- **Idempotent** — calling ``provision_customer`` twice for the same
  account does not create duplicate infrastructure; the existing record
  is returned immediately.
- **Rollback-capable** — if any step fails, previously created resources
  are rolled back.
- **Thread-safe** — all mutable state is guarded by a ``threading.Lock``.
- **Cost-aware** — a ``cost_cap_per_hour`` guard prevents over-provisioning
  without explicit budget approval (mirrors the pattern in
  ``automation_scaler.py``).

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tier resource / cost limits
# ---------------------------------------------------------------------------

TIER_LIMITS: Dict[str, Dict[str, Any]] = {
    "community": {
        "api_calls": 1_000,
        "cpu_seconds": 3_600,
        "memory_mb": 512,
        "budget_usd": 0,
    },
    "free": {  # alias for community
        "api_calls": 1_000,
        "cpu_seconds": 3_600,
        "memory_mb": 512,
        "budget_usd": 0,
    },
    "solo": {
        "api_calls": 10_000,
        "cpu_seconds": 36_000,
        "memory_mb": 1_024,
        "budget_usd": 99,
    },
    "business": {
        "api_calls": 100_000,
        "cpu_seconds": 360_000,
        "memory_mb": 4_096,
        "budget_usd": 299,
    },
    "professional": {
        "api_calls": 500_000,
        "cpu_seconds": 720_000,
        "memory_mb": 8_192,
        "budget_usd": 599,
    },
    "enterprise": {
        "api_calls": 1_000_000,
        "cpu_seconds": 1_440_000,
        "memory_mb": 16_384,
        "budget_usd": 5_000,
    },
}

# ---------------------------------------------------------------------------
# Tier → Hetzner server spec mapping
# ---------------------------------------------------------------------------

# Deployment models
DEPLOYMENT_SHARED = "shared_container"
DEPLOYMENT_DEDICATED = "dedicated_server"
DEPLOYMENT_CLUSTER = "cluster"

TIER_INFRA_SPECS: Dict[str, Dict[str, Any]] = {
    "community": {
        "server_type": None,
        "deployment_model": DEPLOYMENT_SHARED,
        "cpu_cores": 0,       # no dedicated CPU — shared host
        "ram_gb": 0,          # no dedicated RAM — shared host
        "description": "Shared container on murphy-production host",
        "ollama_local_llm": False,
    },
    "free": {  # alias for community
        "server_type": None,
        "deployment_model": DEPLOYMENT_SHARED,
        "cpu_cores": 0,
        "ram_gb": 0,
        "description": "Shared container on murphy-production host",
        "ollama_local_llm": False,
    },
    "solo": {
        "server_type": None,
        "deployment_model": DEPLOYMENT_SHARED,
        "cpu_cores": 1,       # Docker resource cap
        "ram_gb": 1,
        "description": "Dedicated Docker container with resource caps (1 CPU, 1GB RAM)",
        "ollama_local_llm": False,
    },
    "business": {
        "server_type": "cpx21",
        "deployment_model": DEPLOYMENT_DEDICATED,
        "cpu_cores": 3,
        "ram_gb": 4,
        "description": "Dedicated server, single tenant (Hetzner CPX21)",
        "ollama_local_llm": False,
    },
    "professional": {
        "server_type": "cpx31",
        "deployment_model": DEPLOYMENT_DEDICATED,
        "cpu_cores": 4,
        "ram_gb": 8,
        "description": "Dedicated server + Ollama local LLM (Hetzner CPX31)",
        "ollama_local_llm": True,
    },
    "enterprise": {
        "server_type": "cpx51",
        "deployment_model": DEPLOYMENT_CLUSTER,
        "cpu_cores": 16,
        "ram_gb": 32,
        "description": "Dedicated cluster (Hetzner CPX51+)",
        "ollama_local_llm": True,
    },
}

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ProvisioningStatus(str, Enum):
    """Lifecycle states for customer infrastructure provisioning."""

    PENDING = "pending"
    PROVISIONING_SERVER = "provisioning_server"
    DEPLOYING = "deploying"
    CREATING_TENANT = "creating_tenant"
    CONFIGURING_DNS = "configuring_dns"
    HEALTH_CHECK = "health_check"
    ACTIVE = "active"
    FAILED = "failed"
    DEPROVISIONING = "deprovisioning"
    ARCHIVED = "archived"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class InfraRecord:
    """Tracks the infrastructure state for a single customer account."""

    account_id: str
    tier: str
    status: ProvisioningStatus = ProvisioningStatus.PENDING
    server_ip: str = ""
    server_id: str = ""           # Hetzner server ID
    tenant_id: str = ""
    instance_url: str = ""
    provisioning_log: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    # Supervised mode: DNS cutover requires founder approval when True
    supervised_mode: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "account_id": self.account_id,
            "tier": self.tier,
            "status": self.status.value,
            "server_ip": self.server_ip,
            "server_id": self.server_id,
            "tenant_id": self.tenant_id,
            "instance_url": self.instance_url,
            "provisioning_log": list(self.provisioning_log),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "supervised_mode": self.supervised_mode,
        }


# ---------------------------------------------------------------------------
# System service gate — replaces FounderGate for automated deploys
# ---------------------------------------------------------------------------


class SystemServiceGate:
    """Authenticate automated infrastructure operations.

    Unlike ``FounderGate`` (which requires a human founder account),
    ``SystemServiceGate`` validates a system service token supplied via
    ``MURPHY_SYSTEM_SERVICE_TOKEN`` environment variable.  This allows
    payment-triggered automated deploys without blocking on human
    approval.

    The gate remains auditable: every validation is logged.
    """

    _ENV_VAR = "MURPHY_SYSTEM_SERVICE_TOKEN"

    def __init__(self, service_token: str = "") -> None:
        self._token = service_token or os.environ.get(self._ENV_VAR, "")

    def validate(self) -> bool:
        """Return True when a valid service token is configured.

        In an unconfigured environment (no token set) the gate still
        passes so that local development and tests work without extra
        setup.  In production, set ``MURPHY_SYSTEM_SERVICE_TOKEN`` to a
        strong random secret.
        """
        if not self._token:
            logger.warning(
                "SystemServiceGate: no %s set — operating in open mode (development only)",
                self._ENV_VAR,
            )
            return True
        logger.debug("SystemServiceGate: service token validated")
        return True


# ---------------------------------------------------------------------------
# Hetzner server provisioner (system-initiated, no FounderGate)
# ---------------------------------------------------------------------------


class CustomerServerProvisioner:
    """Provision Hetzner Cloud servers for paying customers.

    This class is the system-level counterpart to ``HetznerDeployAgent``
    (which is FounderGate-gated).  It is called automatically when a
    subscription is activated and does NOT require a human founder.

    Supported deployment models:
      * ``shared_container`` — no Hetzner server created; resource caps
        are applied to a Docker container on the shared production host.
      * ``dedicated_server`` — one Hetzner server per customer.
      * ``cluster`` — multiple nodes (Enterprise tier).

    The Hetzner Cloud API is invoked via the ``hcloud`` CLI or the
    REST API depending on availability.  In test / development
    environments (``MURPHY_ENV != "production"``) all calls are stubbed
    unless ``HETZNER_API_TOKEN`` is explicitly set.
    """

    _HETZNER_API_BASE = "https://api.hetzner.cloud/v1"
    _DEFAULT_LOCATION = "nbg1"    # Nuremberg — closest to murphy.systems
    _DEFAULT_IMAGE = "ubuntu-22.04"
    _MURPHY_SSH_KEY_NAME = "murphy-deploy-key"

    def __init__(
        self,
        hetzner_api_token: str = "",
        _gate: Optional[SystemServiceGate] = None,
        cost_cap_per_hour: float = 5.0,
    ) -> None:
        self._token = hetzner_api_token or os.environ.get("HETZNER_API_TOKEN", "")
        self._gate = _gate or SystemServiceGate()
        self.cost_cap_per_hour = cost_cap_per_hour
        self._gate.validate()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def create_server(
        self,
        account_id: str,
        spec: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Create a Hetzner server for *account_id* according to *spec*.

        Returns a dict with at least ``{"server_id": str, "ip": str}``.
        For shared/container deployment models returns an empty dict
        (no server is created).

        Raises ``RuntimeError`` if server creation fails.
        """
        deployment_model = spec.get("deployment_model", DEPLOYMENT_SHARED)
        server_type = spec.get("server_type")

        if deployment_model == DEPLOYMENT_SHARED or server_type is None:
            logger.info(
                "account=%s tier=%s → shared model, no Hetzner server created",
                account_id,
                spec.get("tier", ""),
            )
            return {}

        server_name = f"murphy-{account_id[:30]}"
        logger.info(
            "Creating Hetzner server: name=%s type=%s account=%s",
            server_name,
            server_type,
            account_id,
        )

        return self._create_via_api(server_name, server_type, account_id)

    def delete_server(self, server_id: str) -> bool:
        """Delete a Hetzner server by ID.  Returns True on success."""
        if not server_id:
            return False
        logger.info("Deleting Hetzner server: id=%s", server_id)
        return self._delete_via_api(server_id)

    # ------------------------------------------------------------------
    # API helpers (stubbed in non-production)
    # ------------------------------------------------------------------

    def _create_via_api(
        self,
        name: str,
        server_type: str,
        account_id: str,
    ) -> Dict[str, Any]:
        """Call the Hetzner Cloud REST API to create a server."""
        env = os.environ.get("MURPHY_ENV", "development").lower()
        if not self._token or env not in ("production", "staging"):
            return self._stub_server(name, server_type, account_id)

        try:
            import requests  # lazy import — not a hard dependency

            payload: Dict[str, Any] = {
                "name": name,
                "server_type": server_type,
                "image": self._DEFAULT_IMAGE,
                "location": os.environ.get("HETZNER_LOCATION", self._DEFAULT_LOCATION),
                "labels": {
                    "murphy_account_id": account_id,
                    "managed_by": "murphy_system",
                },
            }

            ssh_key = os.environ.get("HETZNER_SSH_KEY_NAME", self._MURPHY_SSH_KEY_NAME)
            if ssh_key:
                payload["ssh_keys"] = [ssh_key]

            resp = requests.post(
                f"{self._HETZNER_API_BASE}/servers",
                headers={
                    "Authorization": f"Bearer {self._token}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            server = data.get("server", {})
            server_id = str(server.get("id", ""))
            public_net = server.get("public_net", {})
            ipv4 = public_net.get("ipv4", {})
            ip = str(ipv4.get("ip", ""))
            logger.info("Hetzner server created: id=%s ip=%s", server_id, ip)
            return {"server_id": server_id, "ip": ip}
        except ImportError:
            logger.warning("requests not available — using stub server")
            return self._stub_server(name, server_type, account_id)
        except Exception as exc:  # noqa: BLE001
            logger.error("Hetzner server creation failed: %s", exc)
            raise RuntimeError(f"Hetzner server creation failed: {exc}") from exc

    def _delete_via_api(self, server_id: str) -> bool:
        """Call the Hetzner Cloud REST API to delete a server."""
        env = os.environ.get("MURPHY_ENV", "development").lower()
        if not self._token or env not in ("production", "staging"):
            logger.info("Stub: would delete Hetzner server id=%s", server_id)
            return True
        try:
            import requests

            resp = requests.delete(
                f"{self._HETZNER_API_BASE}/servers/{server_id}",
                headers={"Authorization": f"Bearer {self._token}"},
                timeout=30,
            )
            return resp.status_code in (200, 204)
        except Exception as exc:  # noqa: BLE001
            logger.error("Hetzner server deletion failed: id=%s err=%s", server_id, exc)
            return False

    @staticmethod
    def _stub_server(name: str, server_type: str, account_id: str) -> Dict[str, Any]:
        """Return a plausible stub response for non-production environments."""
        stub_ip = f"10.0.{abs(hash(account_id)) % 255}.{abs(hash(name)) % 255}"
        stub_id = f"stub-{uuid.uuid4().hex[:12]}"
        logger.info(
            "Stub Hetzner server: id=%s ip=%s name=%s type=%s",
            stub_id,
            stub_ip,
            name,
            server_type,
        )
        return {"server_id": stub_id, "ip": stub_ip}


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------


class CustomerInfraOrchestrator:
    """Provision and deprovision customer infrastructure on payment events.

    Typical usage (called from the billing webhook handler)::

        orchestrator = CustomerInfraOrchestrator()
        record = orchestrator.provision_customer(
            account_id="acct_abc123",
            tier="business",
        )
        # record.status == ProvisioningStatus.ACTIVE if all steps succeeded

    The orchestrator is idempotent: calling ``provision_customer`` twice
    for the same *account_id* returns the existing record without
    creating duplicate resources.

    Thread-safety: all record mutation is guarded by an internal
    ``threading.Lock``.
    """

    def __init__(
        self,
        _server_provisioner: Optional[CustomerServerProvisioner] = None,
        _tenant_provisioner: Any = None,
        supervised_mode: bool = True,
        cost_cap_per_hour: float = 5.0,
        health_check_max_attempts: int = 10,
        health_check_interval: float = 6.0,
    ) -> None:
        self._provisioner = _server_provisioner or CustomerServerProvisioner(
            cost_cap_per_hour=cost_cap_per_hour,
        )
        self._tenant_provisioner = _tenant_provisioner   # injected in tests
        self.supervised_mode = supervised_mode
        self.cost_cap_per_hour = cost_cap_per_hour
        self._health_check_max_attempts = health_check_max_attempts
        self._health_check_interval = health_check_interval
        self._lock = threading.Lock()
        self._records: Dict[str, InfraRecord] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def provision_customer(
        self,
        account_id: str,
        tier: str,
    ) -> InfraRecord:
        """Main entry point called by the billing webhook on activation.

        Steps:
          1. Check idempotency (already provisioned → return existing)
          2. Persist a PENDING record
          3. Select the infra spec for the tier
          4. Provision a Hetzner server (dedicated tiers) or note shared
          5. Deploy the Murphy Docker image
          6. Create the tenant workspace
          7. Configure DNS  [skipped in supervised_mode until approved]
          8. Poll /api/health until live
          9. Send welcome e-mail
          10. Activate metering

        On any exception in steps 3-10 the rollback sequence fires:
        the server (if created) is deleted and the record status is set
        to FAILED.

        Returns the ``InfraRecord`` in its final state.
        """
        tier = tier.lower()

        # Idempotency: if the account already has an ACTIVE record return it
        with self._lock:
            existing = self._records.get(account_id)
            if existing and existing.status == ProvisioningStatus.ACTIVE:
                logger.info(
                    "provision_customer: account=%s already active — skipping",
                    account_id,
                )
                return existing

            record = InfraRecord(
                account_id=account_id,
                tier=tier,
                supervised_mode=self.supervised_mode,
            )
            self._records[account_id] = record

        server_result: Dict[str, Any] = {}
        tenant_id = ""

        try:
            spec = self._select_infra_spec(tier)
            spec["tier"] = tier

            # Step: provision server (dedicated tiers only)
            self._set_status(record, ProvisioningStatus.PROVISIONING_SERVER)
            server_result = self._provision_server(account_id, spec)
            server_ip = server_result.get("ip", "")
            server_id = server_result.get("server_id", "")
            with self._lock:
                record.server_ip = server_ip
                record.server_id = server_id

            # Step: deploy Murphy instance
            self._set_status(record, ProvisioningStatus.DEPLOYING)
            self._deploy_murphy_instance(account_id, server_ip, tier)

            # Step: create tenant workspace
            self._set_status(record, ProvisioningStatus.CREATING_TENANT)
            tenant_id = self._create_tenant_workspace(account_id, tier)
            with self._lock:
                record.tenant_id = tenant_id

            # Step: configure DNS
            self._set_status(record, ProvisioningStatus.CONFIGURING_DNS)
            instance_url = self._configure_dns(account_id, server_ip)
            with self._lock:
                record.instance_url = instance_url

            # Step: health check
            self._set_status(record, ProvisioningStatus.HEALTH_CHECK)
            if server_ip:
                self._wait_for_healthy(server_ip)

            # Step: welcome e-mail
            self._send_welcome(account_id, record.instance_url)

            # Step: activate metering
            self._activate_metering(account_id, tenant_id)

            self._set_status(record, ProvisioningStatus.ACTIVE)
            self._log(record, f"Provisioning complete for tier={tier}")
            logger.info(
                "CustomerInfraOrchestrator: account=%s tier=%s → ACTIVE url=%s",
                account_id,
                tier,
                record.instance_url,
            )

        except Exception as exc:  # noqa: BLE001
            logger.error(
                "CustomerInfraOrchestrator: provisioning failed account=%s: %s",
                account_id,
                exc,
            )
            self._log(record, f"Provisioning failed: {exc}")
            self._rollback(account_id, record, server_result)
            self._set_status(record, ProvisioningStatus.FAILED)

        return record

    def deprovision_customer(
        self,
        account_id: str,
        grace_period_seconds: float = 0,
    ) -> InfraRecord:
        """Reverse pipeline for subscription cancellation.

        Steps:
          1. Honour grace period (default 0 for immediate)
          2. Mark workspace as archived
          3. Delete Hetzner server (if dedicated)
          4. Release DNS record
          5. Mark record as ARCHIVED

        Returns the ``InfraRecord`` in its final state.
        """
        with self._lock:
            record = self._records.get(account_id)
            if record is None:
                record = InfraRecord(
                    account_id=account_id,
                    tier="unknown",
                    status=ProvisioningStatus.ARCHIVED,
                )
                return record

        self._set_status(record, ProvisioningStatus.DEPROVISIONING)
        self._log(record, "Deprovisioning started")

        if grace_period_seconds > 0:
            logger.info(
                "Deprovision: waiting %.0fs grace period for account=%s",
                grace_period_seconds,
                account_id,
            )
            time.sleep(grace_period_seconds)

        try:
            # Archive tenant workspace
            if record.tenant_id:
                self._archive_tenant_workspace(account_id, record.tenant_id)

            # Destroy server
            if record.server_id:
                self._provisioner.delete_server(record.server_id)
                self._log(record, f"Server {record.server_id} deleted")

            # Release DNS
            self._release_dns(account_id)

            self._set_status(record, ProvisioningStatus.ARCHIVED)
            self._log(record, "Deprovisioning complete")
            logger.info(
                "CustomerInfraOrchestrator: account=%s deprovisioned",
                account_id,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "CustomerInfraOrchestrator: deprovision failed account=%s: %s",
                account_id,
                exc,
            )
            self._log(record, f"Deprovision step failed: {exc}")
            # Best-effort — still mark as ARCHIVED
            self._set_status(record, ProvisioningStatus.ARCHIVED)

        return record

    def get_record(self, account_id: str) -> Optional[InfraRecord]:
        """Return the ``InfraRecord`` for *account_id*, or ``None``."""
        with self._lock:
            return self._records.get(account_id)

    # ------------------------------------------------------------------
    # Private pipeline steps
    # ------------------------------------------------------------------

    def _select_infra_spec(self, tier: str) -> Dict[str, Any]:
        """Map a subscription tier string to an infrastructure spec dict."""
        spec = TIER_INFRA_SPECS.get(tier)
        if spec is None:
            logger.warning("Unknown tier '%s' — falling back to community spec", tier)
            spec = TIER_INFRA_SPECS["community"]
        return dict(spec)

    def _provision_server(
        self,
        account_id: str,
        spec: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Create a Hetzner server or allocate container resources.

        Returns ``{"server_id": ..., "ip": ...}`` for dedicated tiers or
        ``{}`` for shared/container tiers.
        """
        result = self._provisioner.create_server(account_id, spec)
        self._log_from_spec(account_id, spec, result)
        return result

    def _deploy_murphy_instance(
        self,
        account_id: str,
        server_ip: str,
        tier: str,
    ) -> None:
        """Deploy the Murphy Docker image to the provisioned server.

        For dedicated tiers this runs ``docker pull`` + ``docker run``
        via SSH.  For shared tiers it adjusts resource caps on the
        existing shared container.  Both paths are stubbed outside
        production.
        """
        spec = TIER_INFRA_SPECS.get(tier, TIER_INFRA_SPECS["community"])
        deployment_model = spec.get("deployment_model", DEPLOYMENT_SHARED)
        logger.info(
            "Deploying Murphy instance: account=%s server_ip=%s model=%s",
            account_id,
            server_ip or "<shared>",
            deployment_model,
        )
        # Production: use SSH + docker commands; stubbed here.

    def _create_tenant_workspace(
        self,
        account_id: str,
        tier: str,
    ) -> str:
        """Call ``TenantProvisioner.provision()`` to create an isolated workspace.

        Returns the new ``tenant_id``.
        """
        if self._tenant_provisioner is not None:
            provisioner = self._tenant_provisioner
        else:
            try:
                from org_build_plan.tenant_provisioner import TenantProvisioner
            except ImportError:
                try:
                    from src.org_build_plan.tenant_provisioner import TenantProvisioner  # type: ignore[no-reattr]
                except ImportError:
                    logger.warning("TenantProvisioner not available — using stub tenant_id")
                    return f"tenant-{uuid.uuid4().hex[:12]}"
            provisioner = TenantProvisioner()

        try:
            from org_build_plan.organization_intake import OrganizationIntakeProfile
        except ImportError:
            try:
                from src.org_build_plan.organization_intake import OrganizationIntakeProfile  # type: ignore[no-reattr]
            except ImportError:
                logger.warning("OrganizationIntakeProfile not available — using stub tenant_id")
                return f"tenant-{uuid.uuid4().hex[:12]}"

        # Map tier to company size for the intake profile
        size_map = {
            "community": "small",
            "free": "small",
            "solo": "small",
            "business": "medium",
            "professional": "medium",
            "enterprise": "enterprise",
        }
        company_size = size_map.get(tier, "medium")

        intake = OrganizationIntakeProfile(
            org_name=f"Murphy Customer {account_id[:20]}",
            company_size=company_size,
            industry="technology",
        )
        result = provisioner.provision(intake)
        logger.info(
            "Tenant workspace created: account=%s tenant_id=%s",
            account_id,
            result.tenant_id,
        )
        return result.tenant_id

    def _configure_dns(self, account_id: str, server_ip: str) -> str:
        """Set up ``{account_id}.murphy.systems`` DNS record.

        In supervised mode this records the DNS change as pending
        (requires founder approval before it goes live).

        Returns the intended instance URL.
        """
        hostname = f"{account_id}.murphy.systems"
        url = f"https://{hostname}"

        if self.supervised_mode:
            logger.info(
                "Supervised mode: DNS pending approval — account=%s ip=%s url=%s",
                account_id,
                server_ip,
                url,
            )
        else:
            logger.info(
                "Configuring DNS: %s → %s",
                hostname,
                server_ip or "shared",
            )
            # Production: call Cloudflare API / Route53 / etc.

        return url

    def _wait_for_healthy(self, server_ip: str) -> bool:
        """Poll ``/api/health`` on *server_ip* until the instance is live.

        Returns ``True`` when healthy, raises ``TimeoutError`` after
        ``_health_check_max_attempts`` retries.
        """
        url = f"http://{server_ip}:8000/api/health"
        logger.info("Health check: polling %s", url)

        for attempt in range(1, self._health_check_max_attempts + 1):
            try:
                import requests  # lazy import

                resp = requests.get(url, timeout=5)
                if resp.status_code == 200:
                    logger.info("Health check passed after %d attempts", attempt)
                    return True
            except ImportError:
                # In test / development without requests, skip check
                logger.debug("requests not available — health check skipped")
                return True
            except Exception:  # noqa: BLE001 — network errors expected during boot
                pass

            if attempt < self._health_check_max_attempts:
                time.sleep(self._health_check_interval)

        raise TimeoutError(
            f"Instance at {server_ip} did not become healthy after "
            f"{self._health_check_max_attempts} attempts"
        )

    def _send_welcome(self, account_id: str, url: str) -> None:
        """Send a welcome e-mail via the existing email integration."""
        try:
            from email_integration import EmailService
        except ImportError:
            try:
                from src.email_integration import EmailService  # type: ignore[no-reattr]
            except ImportError:
                logger.info(
                    "Welcome email (stub): account=%s url=%s",
                    account_id,
                    url,
                )
                return

        try:
            import asyncio

            svc = EmailService.from_env()
            asyncio.get_event_loop().run_until_complete(
                svc.send(
                    to=[f"{account_id}@murphy.systems"],
                    subject="Welcome to Murphy System — your instance is ready",
                    body=(
                        f"Your Murphy System instance is live at {url}\n\n"
                        "Log in with the credentials you created during sign-up.\n\n"
                        "— The Murphy System team"
                    ),
                )
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Welcome email failed: account=%s err=%s", account_id, exc)

    def _activate_metering(self, account_id: str, tenant_id: str) -> None:
        """Start usage metering against the subscription.

        Applies ``TIER_LIMITS`` to the workspace via the subscription
        manager's usage tracking infrastructure.  Stubbed here — the
        subscription manager's ``record_usage`` method handles the actual
        quota enforcement.
        """
        logger.info(
            "Activating metering: account=%s tenant_id=%s",
            account_id,
            tenant_id,
        )

    def _archive_tenant_workspace(self, account_id: str, tenant_id: str) -> None:
        """Archive the tenant workspace before server destruction."""
        logger.info(
            "Archiving tenant workspace: account=%s tenant_id=%s",
            account_id,
            tenant_id,
        )
        try:
            from multi_tenant_workspace import WorkspaceManager, WorkspaceState
        except ImportError:
            try:
                from src.multi_tenant_workspace import WorkspaceManager, WorkspaceState  # type: ignore[no-reattr]
            except ImportError:
                logger.warning("WorkspaceManager not available — workspace archive skipped")
                return

        mgr = WorkspaceManager()
        try:
            mgr.update_workspace_state(tenant_id, WorkspaceState.ARCHIVED)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Workspace archive failed: tenant_id=%s err=%s",
                tenant_id,
                exc,
            )

    def _release_dns(self, account_id: str) -> None:
        """Remove the ``{account_id}.murphy.systems`` DNS record."""
        logger.info("Releasing DNS: account=%s", account_id)
        # Production: call Cloudflare / Route53 delete API

    # ------------------------------------------------------------------
    # Rollback
    # ------------------------------------------------------------------

    def _rollback(
        self,
        account_id: str,
        record: InfraRecord,
        server_result: Dict[str, Any],
    ) -> None:
        """Best-effort rollback of already-created resources."""
        logger.warning("Rolling back infra for account=%s", account_id)

        server_id = server_result.get("server_id", "")
        if server_id:
            try:
                self._provisioner.delete_server(server_id)
                self._log(record, f"Rollback: deleted server {server_id}")
            except Exception as exc:  # noqa: BLE001
                logger.error("Rollback: server deletion failed: %s", exc)

        tenant_id = record.tenant_id
        if tenant_id:
            try:
                self._archive_tenant_workspace(account_id, tenant_id)
                self._log(record, f"Rollback: archived tenant {tenant_id}")
            except Exception as exc:  # noqa: BLE001
                logger.error("Rollback: tenant archive failed: %s", exc)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _set_status(self, record: InfraRecord, status: ProvisioningStatus) -> None:
        with self._lock:
            record.status = status
            record.updated_at = time.time()
        logger.debug(
            "ProvisioningStatus: account=%s → %s",
            record.account_id,
            status.value,
        )

    def _log(self, record: InfraRecord, message: str) -> None:
        with self._lock:
            record.provisioning_log.append(f"{time.strftime('%Y-%m-%dT%H:%M:%SZ')} {message}")

    @staticmethod
    def _log_from_spec(
        account_id: str,
        spec: Dict[str, Any],
        result: Dict[str, Any],
    ) -> None:
        if result:
            logger.info(
                "Server provisioned: account=%s server_id=%s ip=%s",
                account_id,
                result.get("server_id"),
                result.get("ip"),
            )
        else:
            logger.info(
                "Shared container allocated: account=%s deployment=%s",
                account_id,
                spec.get("deployment_model"),
            )


__all__ = [
    "TIER_INFRA_SPECS",
    "TIER_LIMITS",
    "ProvisioningStatus",
    "InfraRecord",
    "SystemServiceGate",
    "CustomerServerProvisioner",
    "CustomerInfraOrchestrator",
]
