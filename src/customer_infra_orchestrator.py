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
     Cloud server is created via the REST API with a cloud-init ``user_data``
     script that self-bootstraps Docker and starts the Murphy container —
     no SSH post-creation step is required.
  4. A tenant workspace is created via the existing ``TenantProvisioner``.
  5. DNS is configured (``{account_id}.murphy.systems``) via the existing
     ``CloudflareConnector``.
  6. A health-check loop confirms the instance is live.
  7. A welcome e-mail is sent via the existing ``EmailService``.
  8. Usage metering is activated by writing back to ``SubscriptionManager``.

Design principles
-----------------
- **HITL-safe** — ``supervised_mode=True`` buffers the DNS cutover; the
  founder calls ``approve_dns(account_id)`` before Cloudflare is updated.
- **Idempotent** — ``provision_customer`` twice for the same account returns
  the existing ``ACTIVE`` record without creating duplicates.
- **Rollback-capable** — if any step fails, previously created resources are
  cleaned up and the record transitions to ``FAILED``.
- **Thread-safe** — all record mutation is guarded by ``threading.Lock``.
- **Cost-aware** — ``cost_cap_per_hour`` mirrors ``automation_scaler.py``;
  provisioning is rejected when the estimated hourly cost exceeds the cap.
- **No legacy SSH** — dedicated-tier deployment is handled entirely by the
  Hetzner cloud-init ``user_data`` script at server-creation time.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import importlib
import logging
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from textwrap import dedent
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def _import_first(*module_paths: str) -> Any:
    """Try each dotted module path in order and return the first successful
    ``importlib.import_module`` result, or ``None`` if all fail.

    Used throughout this module to handle both installed-package imports
    (``src.foo.bar``) and in-``sys.path`` imports (``foo.bar``).
    """
    for path in module_paths:
        try:
            return importlib.import_module(path)
        except ImportError:
            continue
    return None

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
    "free": {
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

DEPLOYMENT_SHARED = "shared_container"
DEPLOYMENT_DEDICATED = "dedicated_server"
DEPLOYMENT_CLUSTER = "cluster"

# Estimated hourly cost in USD per server type (Hetzner list pricing Apr 2025)
_SERVER_HOURLY_COST: Dict[str, float] = {
    "cpx21": 0.027,
    "cpx31": 0.044,
    "cpx51": 0.109,
}

TIER_INFRA_SPECS: Dict[str, Dict[str, Any]] = {
    "community": {
        "server_type": None,
        "deployment_model": DEPLOYMENT_SHARED,
        "cpu_cores": 0,
        "ram_gb": 0,
        "docker_cpus": "0.5",
        "docker_memory": "512m",
        "description": "Shared container on murphy-production host",
        "ollama_local_llm": False,
    },
    "free": {
        "server_type": None,
        "deployment_model": DEPLOYMENT_SHARED,
        "cpu_cores": 0,
        "ram_gb": 0,
        "docker_cpus": "0.5",
        "docker_memory": "512m",
        "description": "Shared container on murphy-production host",
        "ollama_local_llm": False,
    },
    "solo": {
        "server_type": None,
        "deployment_model": DEPLOYMENT_SHARED,
        "cpu_cores": 1,
        "ram_gb": 1,
        "docker_cpus": "1.0",
        "docker_memory": "1g",
        "description": "Dedicated Docker container with resource caps (1 CPU, 1 GB RAM)",
        "ollama_local_llm": False,
    },
    "business": {
        "server_type": "cpx21",
        "deployment_model": DEPLOYMENT_DEDICATED,
        "cpu_cores": 3,
        "ram_gb": 4,
        "docker_cpus": "3.0",
        "docker_memory": "4g",
        "description": "Dedicated Hetzner CPX21 server, single tenant",
        "ollama_local_llm": False,
    },
    "professional": {
        "server_type": "cpx31",
        "deployment_model": DEPLOYMENT_DEDICATED,
        "cpu_cores": 4,
        "ram_gb": 8,
        "docker_cpus": "4.0",
        "docker_memory": "8g",
        "description": "Dedicated Hetzner CPX31 server + Ollama local LLM",
        "ollama_local_llm": True,
    },
    "enterprise": {
        "server_type": "cpx51",
        "deployment_model": DEPLOYMENT_CLUSTER,
        "cpu_cores": 16,
        "ram_gb": 32,
        "docker_cpus": "16.0",
        "docker_memory": "32g",
        "description": "Dedicated Hetzner CPX51 cluster",
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
    server_id: str = ""
    dns_record_id: str = ""       # Cloudflare DNS record ID for cleanup
    tenant_id: str = ""
    instance_url: str = ""
    provisioning_log: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    supervised_mode: bool = True   # DNS cutover requires founder approval when True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "account_id": self.account_id,
            "tier": self.tier,
            "status": self.status.value,
            "server_ip": self.server_ip,
            "server_id": self.server_id,
            "dns_record_id": self.dns_record_id,
            "tenant_id": self.tenant_id,
            "instance_url": self.instance_url,
            "provisioning_log": list(self.provisioning_log),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "supervised_mode": self.supervised_mode,
        }


# ---------------------------------------------------------------------------
# System service gate (replaces FounderGate for automated deploys)
# ---------------------------------------------------------------------------


class SystemServiceGate:
    """Authenticate automated infrastructure operations.

    Unlike ``FounderGate`` (which requires a human founder account),
    ``SystemServiceGate`` validates a service token from the
    ``MURPHY_SYSTEM_SERVICE_TOKEN`` environment variable, allowing
    payment-triggered automated deploys without blocking on human approval.

    In non-production environments without a token the gate passes so that
    local development and CI work without extra setup.  In production the
    token is mandatory.
    """

    _ENV_VAR = "MURPHY_SYSTEM_SERVICE_TOKEN"

    def __init__(self, service_token: str = "") -> None:
        self._token = service_token or os.environ.get(self._ENV_VAR, "")

    def validate(self) -> bool:
        env = os.environ.get("MURPHY_ENV", "development").lower()
        if not self._token:
            if env == "production":
                raise PermissionError(
                    f"SystemServiceGate: {self._ENV_VAR} must be set in production"
                )
            logger.warning(
                "SystemServiceGate: no %s configured — open mode (non-production only)",
                self._ENV_VAR,
            )
        logger.debug("SystemServiceGate: validated for env=%s", env)
        return True


# ---------------------------------------------------------------------------
# Cloud-init bootstrap script (baked into Hetzner server creation)
# ---------------------------------------------------------------------------


def _build_user_data(
    account_id: str,
    tier: str,
    docker_cpus: str,
    docker_memory: str,
    with_ollama: bool,
    murphy_image: str,
    murphy_port: int,
) -> str:
    """Return the cloud-init ``user_data`` script embedded in the Hetzner
    server creation request.

    The script runs once on first boot and:
      1. Installs Docker CE from the official Docker APT repository
      2. Optionally installs and starts Ollama (Professional / Enterprise)
      3. Pulls the Murphy Docker image from the registry
      4. Starts the Murphy container with per-tier CPU / memory caps

    No SSH post-creation step is needed — the server is fully
    self-provisioning.
    """
    ollama_block = ""
    if with_ollama:
        ollama_model = os.environ.get("OLLAMA_MODEL", "llama3").split(":")[0]
        ollama_block = dedent(f"""
            # Install and start Ollama for local LLM inference
            curl -fsSL https://ollama.ai/install.sh | sh
            systemctl enable ollama --now
            # Pull the default model in the background (non-blocking)
            nohup ollama pull {ollama_model} &>/var/log/ollama-pull.log &
        """).strip()

    registry = os.environ.get("MURPHY_REGISTRY", "ghcr.io/iknowinot/murphy-system")
    image_tag = os.environ.get("MURPHY_IMAGE_TAG", "latest")
    full_image = murphy_image or f"{registry}:{image_tag}"

    db_url = os.environ.get("MURPHY_DB_URL", "")
    secret_key = os.environ.get("MURPHY_SECRET_KEY", "")

    script_lines = [
        "#!/bin/bash",
        "set -euo pipefail",
        "exec > /var/log/murphy-init.log 2>&1",
        "",
        "# System update",
        "apt-get update -qq",
        "apt-get install -y ca-certificates curl gnupg lsb-release",
        "",
        "# Docker CE",
        "install -m 0755 -d /etc/apt/keyrings",
        "curl -fsSL https://download.docker.com/linux/ubuntu/gpg "
        "| gpg --dearmor -o /etc/apt/keyrings/docker.gpg",
        "chmod a+r /etc/apt/keyrings/docker.gpg",
        'echo "deb [arch=$(dpkg --print-architecture) '
        'signed-by=/etc/apt/keyrings/docker.gpg] '
        'https://download.docker.com/linux/ubuntu '
        '$(lsb_release -cs) stable" > /etc/apt/sources.list.d/docker.list',
        "apt-get update -qq",
        "apt-get install -y docker-ce docker-ce-cli containerd.io",
        "systemctl enable docker --now",
        "",
    ]

    if ollama_block:
        script_lines += ["", ollama_block, ""]

    script_lines += [
        f"# Pull Murphy image",
        f"docker pull {full_image}",
        "",
        f"# Launch Murphy container for account {account_id} (tier={tier})",
        "docker run -d \\",
        f'    --name murphy-{account_id[:20]} \\',
        "    --restart unless-stopped \\",
        f'    --cpus="{docker_cpus}" \\',
        f'    --memory="{docker_memory}" \\',
        f"    -p {murphy_port}:8000 \\",
        '    -e MURPHY_ENV=production \\',
        f'    -e MURPHY_ACCOUNT_ID="{account_id}" \\',
        f'    -e MURPHY_TIER="{tier}" \\',
        f'    -e MURPHY_DB_URL="{db_url}" \\',
        f'    -e MURPHY_SECRET_KEY="{secret_key}" \\',
        f"    {full_image}",
        "",
        f'echo "Murphy container started: account={account_id} tier={tier}"',
    ]
    return "\n".join(script_lines)


# ---------------------------------------------------------------------------
# Hetzner server provisioner (system-initiated, no FounderGate, no SSH)
# ---------------------------------------------------------------------------


class CustomerServerProvisioner:
    """Provision and destroy Hetzner Cloud servers for paying customers.

    Unlike ``HetznerDeployAgent`` (which is FounderGate-gated and
    uses SSH post-creation), this class:

    * Is invoked automatically by the billing webhook — no human required.
    * Embeds a cloud-init ``user_data`` script in the Hetzner server
      creation payload so the server self-configures Docker and starts
      Murphy on first boot.
    * Never opens an SSH connection.

    Deployment models
    -----------------
    ``shared_container``
        No Hetzner server created.  Resource caps for shared/solo tiers
        are enforced by the shared production host's container scheduler.
    ``dedicated_server``
        One Hetzner server per customer (Business / Professional).
    ``cluster``
        Two nodes (Enterprise) — first node receives the DNS record.
    """

    _HETZNER_API_BASE = "https://api.hetzner.cloud/v1"
    _DEFAULT_LOCATION = "nbg1"
    _DEFAULT_IMAGE = "ubuntu-22.04"
    _MURPHY_PORT = 8000

    def __init__(
        self,
        hetzner_api_token: str = "",
        _gate: Optional[SystemServiceGate] = None,
        cost_cap_per_hour: float = 5.0,
        murphy_image: str = "",
    ) -> None:
        self._token = hetzner_api_token or os.environ.get("HETZNER_API_TOKEN", "")
        self._gate = _gate or SystemServiceGate()
        self.cost_cap_per_hour = cost_cap_per_hour
        self._murphy_image = murphy_image
        self._gate.validate()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def create_server(
        self,
        account_id: str,
        spec: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Create a Hetzner server for *account_id* based on *spec*.

        Returns ``{"server_id": str, "ip": str}`` for dedicated/cluster
        tiers, or ``{}`` for shared tiers.

        In non-production environments without ``HETZNER_API_TOKEN`` a
        dry-run dict ``{"server_id": "dryrun-...", "ip": "", "dry_run": True}``
        is returned so that the rest of the pipeline can be exercised
        without incurring cloud costs.

        Raises ``ValueError`` if the estimated hourly cost exceeds
        ``cost_cap_per_hour``.  Raises ``RuntimeError`` on API failure.
        """
        deployment_model = spec.get("deployment_model", DEPLOYMENT_SHARED)
        server_type = spec.get("server_type")

        if deployment_model == DEPLOYMENT_SHARED or server_type is None:
            logger.info(
                "account=%s tier=%s → shared deployment, no Hetzner server created",
                account_id, spec.get("tier", ""),
            )
            return {}

        # Cost-cap guard (mirrors automation_scaler.py pattern)
        hourly = _SERVER_HOURLY_COST.get(server_type, 0.0)
        if hourly > self.cost_cap_per_hour:
            raise ValueError(
                f"Server type '{server_type}' costs ${hourly:.3f}/hr which exceeds "
                f"cost_cap_per_hour=${self.cost_cap_per_hour:.2f}. "
                "Raise the cap or choose a smaller server type."
            )

        node_count = 2 if deployment_model == DEPLOYMENT_CLUSTER else 1
        primary: Dict[str, Any] = {}
        for idx in range(node_count):
            suffix = f"-n{idx}" if node_count > 1 else ""
            name = f"murphy-{account_id[:28]}{suffix}"
            result = self._create_via_api(name, server_type, account_id, spec)
            if idx == 0:
                primary = result

        logger.info(
            "Provisioned %d server(s) for account=%s primary_id=%s primary_ip=%s",
            node_count, account_id, primary.get("server_id"), primary.get("ip"),
        )
        return primary

    def delete_server(self, server_id: str) -> bool:
        """Delete a Hetzner server by ID.  Returns True on success."""
        if not server_id:
            return False
        logger.info("Deleting Hetzner server: id=%s", server_id)
        return self._delete_via_api(server_id)

    # ------------------------------------------------------------------
    # API helpers
    # ------------------------------------------------------------------

    def _create_via_api(
        self,
        name: str,
        server_type: str,
        account_id: str,
        spec: Dict[str, Any],
    ) -> Dict[str, Any]:
        """POST to the Hetzner Cloud REST API to create a server.

        The cloud-init ``user_data`` is embedded in the payload so the
        server self-configures on first boot — no SSH step required.
        """
        user_data = _build_user_data(
            account_id=account_id,
            tier=spec.get("tier", ""),
            docker_cpus=spec.get("docker_cpus", "1.0"),
            docker_memory=spec.get("docker_memory", "1g"),
            with_ollama=bool(spec.get("ollama_local_llm", False)),
            murphy_image=self._murphy_image,
            murphy_port=self._MURPHY_PORT,
        )

        payload: Dict[str, Any] = {
            "name": name,
            "server_type": server_type,
            "image": os.environ.get("HETZNER_IMAGE", self._DEFAULT_IMAGE),
            "location": os.environ.get("HETZNER_LOCATION", self._DEFAULT_LOCATION),
            "user_data": user_data,
            "labels": {
                "murphy_account_id": account_id,
                "murphy_tier": spec.get("tier", ""),
                "managed_by": "murphy_system",
            },
        }
        ssh_key = os.environ.get("HETZNER_SSH_KEY_NAME", "")
        if ssh_key:
            payload["ssh_keys"] = [ssh_key]

        env = os.environ.get("MURPHY_ENV", "development").lower()
        if not self._token or env not in ("production", "staging"):
            logger.info(
                "Non-production (env=%s): Hetzner server creation recorded but not executed. "
                "Set HETZNER_API_TOKEN + MURPHY_ENV=production to provision real servers.",
                env,
            )
            return {
                "server_id": f"dryrun-{uuid.uuid4().hex[:12]}",
                "ip": "",
                "dry_run": True,
            }

        try:
            import requests

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
            ip = str(server.get("public_net", {}).get("ipv4", {}).get("ip", ""))
            logger.info("Hetzner server created: id=%s ip=%s name=%s", server_id, ip, name)
            return {"server_id": server_id, "ip": ip}
        except ImportError:
            logger.error("requests library not available — cannot provision Hetzner servers")
            raise RuntimeError("requests library required for Hetzner provisioning")
        except Exception as exc:
            logger.error("Hetzner server creation failed: %s", exc)
            raise RuntimeError(f"Hetzner server creation failed: {exc}") from exc

    def _delete_via_api(self, server_id: str) -> bool:
        env = os.environ.get("MURPHY_ENV", "development").lower()
        if not self._token or env not in ("production", "staging"):
            logger.info(
                "Non-production: Hetzner server deletion recorded (id=%s)", server_id
            )
            return True
        try:
            import requests

            resp = requests.delete(
                f"{self._HETZNER_API_BASE}/servers/{server_id}",
                headers={"Authorization": f"Bearer {self._token}"},
                timeout=30,
            )
            return resp.status_code in (200, 204)
        except Exception as exc:
            logger.error("Hetzner server deletion failed: id=%s err=%s", server_id, exc)
            return False


# ---------------------------------------------------------------------------
# Cloudflare DNS helper (wraps the existing CloudflareConnector)
# ---------------------------------------------------------------------------


class _DNSManager:
    """Thin wrapper around the existing ``CloudflareConnector``.

    Exposes only the two operations needed by the orchestrator —
    ``upsert`` (create-or-update) and ``delete`` — and degrades
    gracefully to no-op logging when Cloudflare credentials are absent.
    """

    _MURPHY_DOMAIN = "murphy.systems"

    def __init__(self) -> None:
        CloudflareConnector = None
        cf_mod = _import_first(
            "src.integrations.cloudflare_connector",
            "integrations.cloudflare_connector",
        )
        if cf_mod is not None:
            CloudflareConnector = getattr(cf_mod, "CloudflareConnector", None)
        self._cf = CloudflareConnector() if CloudflareConnector is not None else None

    def upsert(self, account_id: str, ip: str) -> str:
        """Create or update an A record for ``{account_id}.murphy.systems``.

        Returns the Cloudflare DNS record ID, or ``""`` when Cloudflare
        is not configured or no IP is provided (shared tier).
        """
        hostname = f"{account_id}.{self._MURPHY_DOMAIN}"

        if self._cf is None or not self._cf.is_configured():
            logger.info(
                "Cloudflare not configured — DNS record %s → %s not written "
                "(set CLOUDFLARE_API_TOKEN + CLOUDFLARE_ZONE_ID to enable)",
                hostname, ip or "shared",
            )
            return ""

        if not ip:
            logger.info("Shared tier: no IP to register for %s", hostname)
            return ""

        # Check for an existing record with this name to avoid duplicates
        existing_resp = self._cf.list_dns_records(type_filter="A")
        existing_records = (existing_resp.get("data") or {}).get("result", [])
        for rec in existing_records:
            if rec.get("name") == hostname:
                record_id: str = rec["id"]
                self._cf.update_dns_record(record_id, {"content": ip, "proxied": True})
                logger.info("DNS updated: %s → %s (record_id=%s)", hostname, ip, record_id)
                return record_id

        result = self._cf.create_dns_record(
            name=hostname, type_="A", content=ip, proxied=True
        )
        record_id = (result.get("data") or {}).get("result", {}).get("id", "")
        logger.info("DNS created: %s → %s (record_id=%s)", hostname, ip, record_id)
        return record_id

    def delete(self, record_id: str) -> None:
        """Remove a DNS record by *record_id*."""
        if not record_id:
            return
        if self._cf is None or not self._cf.is_configured():
            logger.info(
                "Cloudflare not configured — DNS record %s not deleted", record_id
            )
            return
        self._cf.delete_dns_record(record_id)
        logger.info("DNS record deleted: id=%s", record_id)


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------


class CustomerInfraOrchestrator:
    """Provision and deprovision customer infrastructure on payment events.

    Typical usage (called from the billing webhook handler after the
    ``SubscriptionManager`` has confirmed payment)::

        orchestrator = CustomerInfraOrchestrator()
        record = orchestrator.provision_customer(
            account_id="acct_abc123",
            tier="business",
        )
        # record.status == ProvisioningStatus.ACTIVE when all steps succeeded

    Idempotency: calling ``provision_customer`` twice for the same
    *account_id* returns the existing record when it is already ACTIVE.

    Thread-safety: all record mutation is guarded by ``threading.Lock``.
    """

    def __init__(
        self,
        _server_provisioner: Optional[CustomerServerProvisioner] = None,
        _tenant_provisioner: Any = None,
        _subscription_manager: Any = None,
        supervised_mode: bool = True,
        cost_cap_per_hour: float = 5.0,
        health_check_max_attempts: int = 10,
        health_check_interval: float = 6.0,
    ) -> None:
        self._provisioner = _server_provisioner or CustomerServerProvisioner(
            cost_cap_per_hour=cost_cap_per_hour,
        )
        self._tenant_provisioner = _tenant_provisioner
        self._subscription_manager = _subscription_manager
        self._dns = _DNSManager()
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
        """Main entry point — called by the billing webhook on activation.

        Pipeline
        --------
        1. Idempotency check (ACTIVE record → return immediately)
        2. Select infra spec for the tier
        3. Create Hetzner server with cloud-init user_data (dedicated tiers)
           — cloud-init handles Docker install + Murphy container start
        4. Create tenant workspace via ``TenantProvisioner``
        5. Configure Cloudflare DNS (or buffer for founder approval when
           ``supervised_mode=True``)
        6. Poll ``/api/health`` until the instance responds
        7. Send welcome e-mail
        8. Write provisioning info back to ``SubscriptionManager``

        On any exception the rollback sequence fires: the server (if
        created) is deleted, the DNS record (if created) is removed, and
        the record transitions to ``FAILED``.
        """
        tier = tier.lower()

        with self._lock:
            existing = self._records.get(account_id)
            if existing and existing.status == ProvisioningStatus.ACTIVE:
                logger.info(
                    "provision_customer: account=%s already ACTIVE — idempotent skip",
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
        dns_record_id = ""

        try:
            spec = self._select_infra_spec(tier)

            # Step 1 — Provision Hetzner server (dedicated tiers)
            # cloud-init user_data baked in: no separate SSH/deploy step needed
            self._set_status(record, ProvisioningStatus.PROVISIONING_SERVER)
            server_result = self._provisioner.create_server(account_id, spec)
            server_ip = server_result.get("ip", "")
            server_id = server_result.get("server_id", "")
            with self._lock:
                record.server_ip = server_ip
                record.server_id = server_id

            # Step 2 — Deployment (cloud-init for dedicated; cap recording for shared)
            self._set_status(record, ProvisioningStatus.DEPLOYING)
            self._record_shared_caps(account_id, spec)

            # Step 3 — Create tenant workspace
            self._set_status(record, ProvisioningStatus.CREATING_TENANT)
            tenant_id = self._create_tenant_workspace(account_id, tier)
            with self._lock:
                record.tenant_id = tenant_id

            # Step 4 — Configure DNS (Cloudflare, or buffered for supervised mode)
            self._set_status(record, ProvisioningStatus.CONFIGURING_DNS)
            instance_url, dns_record_id = self._configure_dns(account_id, server_ip)
            with self._lock:
                record.instance_url = instance_url
                record.dns_record_id = dns_record_id

            # Step 5 — Health check (only for dedicated tiers with a real IP)
            self._set_status(record, ProvisioningStatus.HEALTH_CHECK)
            if server_ip:
                self._wait_for_healthy(server_ip)

            # Step 6 — Welcome e-mail
            self._send_welcome(account_id, record.instance_url)

            # Step 7 — Activate metering (write back to SubscriptionManager)
            self._activate_metering(account_id, tenant_id, server_ip)

            self._set_status(record, ProvisioningStatus.ACTIVE)
            self._log(record, f"Provisioning complete: tier={tier} url={instance_url}")
            logger.info(
                "CustomerInfraOrchestrator: account=%s tier=%s ACTIVE url=%s",
                account_id, tier, record.instance_url,
            )

        except Exception as exc:
            logger.error(
                "CustomerInfraOrchestrator: provisioning failed account=%s: %s",
                account_id, exc,
            )
            self._log(record, f"FAILED: {exc}")
            self._rollback(account_id, record, server_result, dns_record_id)
            self._set_status(record, ProvisioningStatus.FAILED)

        return record

    def approve_dns(self, account_id: str) -> InfraRecord:
        """Founder approval step for supervised mode.

        When ``supervised_mode=True`` the DNS write is buffered until
        the founder calls this method.  It writes the Cloudflare A record
        and advances the pipeline to ACTIVE.

        Returns the existing record unchanged if already ACTIVE.
        """
        with self._lock:
            record = self._records.get(account_id)
        if record is None:
            raise KeyError(f"No infra record found for account '{account_id}'")
        if record.status == ProvisioningStatus.ACTIVE:
            return record

        try:
            dns_record_id = self._dns.upsert(account_id, record.server_ip)
            with self._lock:
                record.dns_record_id = dns_record_id
            self._log(record, f"DNS approved by founder — record_id={dns_record_id}")

            if record.server_ip:
                self._wait_for_healthy(record.server_ip)
            self._send_welcome(account_id, record.instance_url)
            self._activate_metering(account_id, record.tenant_id, record.server_ip)
            self._set_status(record, ProvisioningStatus.ACTIVE)
        except Exception as exc:
            logger.error("approve_dns failed for account=%s: %s", account_id, exc)
            self._log(record, f"approve_dns failed: {exc}")
            self._set_status(record, ProvisioningStatus.FAILED)

        return record

    def deprovision_customer(
        self,
        account_id: str,
        grace_period_seconds: float = 0,
    ) -> InfraRecord:
        """Reverse pipeline for subscription cancellation.

        Steps
        -----
        1. Honour grace period (default 0 = immediate)
        2. Archive tenant workspace via ``WorkspaceManager``
        3. Delete Hetzner server (dedicated tiers)
        4. Remove Cloudflare DNS record
        5. Mark record ``ARCHIVED``
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
                "Deprovision: %.0fs grace period for account=%s",
                grace_period_seconds, account_id,
            )
            time.sleep(grace_period_seconds)

        try:
            if record.tenant_id:
                self._archive_tenant_workspace(account_id, record.tenant_id)

            if record.server_id:
                self._provisioner.delete_server(record.server_id)
                self._log(record, f"Server {record.server_id} deleted")

            if record.dns_record_id:
                self._dns.delete(record.dns_record_id)
                self._log(record, f"DNS record {record.dns_record_id} removed")

            self._set_status(record, ProvisioningStatus.ARCHIVED)
            self._log(record, "Deprovisioning complete")
            logger.info(
                "CustomerInfraOrchestrator: account=%s deprovisioned", account_id
            )
        except Exception as exc:
            logger.error(
                "CustomerInfraOrchestrator: deprovision error account=%s: %s",
                account_id, exc,
            )
            self._log(record, f"Deprovision error (best-effort, continuing): {exc}")
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
        """Map a subscription tier string to an infra spec dict."""
        spec = TIER_INFRA_SPECS.get(tier)
        if spec is None:
            logger.warning("Unknown tier '%s' — falling back to community spec", tier)
            spec = TIER_INFRA_SPECS["community"]
        result = dict(spec)
        result["tier"] = tier
        return result

    def _record_shared_caps(self, account_id: str, spec: Dict[str, Any]) -> None:
        """Log Docker resource caps for shared-tier accounts.

        The shared production host's container scheduler reads these
        caps from the provisioning record and enforces them.
        """
        if spec.get("deployment_model") != DEPLOYMENT_SHARED:
            return
        logger.info(
            "Shared resource caps: account=%s cpus=%s memory=%s",
            account_id, spec.get("docker_cpus"), spec.get("docker_memory"),
        )

    def _create_tenant_workspace(self, account_id: str, tier: str) -> str:
        """Call ``TenantProvisioner.provision()`` and return the new tenant_id."""
        if self._tenant_provisioner is not None:
            provisioner = self._tenant_provisioner
        else:
            tp_mod = _import_first(
                "src.org_build_plan.tenant_provisioner",
                "org_build_plan.tenant_provisioner",
            )
            if tp_mod is None:
                logger.warning(
                    "TenantProvisioner not importable — generating tenant_id locally"
                )
                return f"tenant-{uuid.uuid4().hex[:12]}"
            provisioner = tp_mod.TenantProvisioner()

        intake_mod = _import_first(
            "src.org_build_plan.organization_intake",
            "org_build_plan.organization_intake",
        )
        if intake_mod is None:
            logger.warning(
                "OrganizationIntakeProfile not importable — generating tenant_id locally"
            )
            return f"tenant-{uuid.uuid4().hex[:12]}"
        OrganizationIntakeProfile = intake_mod.OrganizationIntakeProfile

        size_map = {
            "community": "small", "free": "small", "solo": "small",
            "business": "medium", "professional": "medium", "enterprise": "enterprise",
        }
        intake = OrganizationIntakeProfile(
            org_name=f"Murphy Customer {account_id[:20]}",
            company_size=size_map.get(tier, "medium"),
            industry="technology",
        )
        result = provisioner.provision(intake)
        logger.info(
            "Tenant workspace created: account=%s tenant_id=%s",
            account_id, result.tenant_id,
        )
        return result.tenant_id

    def _configure_dns(
        self, account_id: str, server_ip: str
    ) -> Tuple[str, str]:
        """Write a Cloudflare A record for ``{account_id}.murphy.systems``.

        In ``supervised_mode`` the Cloudflare write is buffered and
        ``approve_dns()`` must be called by the founder first.

        Returns ``(instance_url, dns_record_id)``.
        """
        hostname = f"{account_id}.murphy.systems"
        url = f"https://{hostname}"

        if self.supervised_mode:
            logger.info(
                "Supervised mode: DNS write buffered for founder approval "
                "(account=%s ip=%s url=%s)",
                account_id, server_ip or "shared", url,
            )
            return url, ""

        dns_record_id = self._dns.upsert(account_id, server_ip)
        return url, dns_record_id

    def _wait_for_healthy(self, server_ip: str) -> bool:
        """Poll ``http://{server_ip}:8000/api/health`` until it returns 200.

        Raises ``TimeoutError`` after ``_health_check_max_attempts`` retries.
        """
        url = f"http://{server_ip}:8000/api/health"
        logger.info("Health check polling: %s", url)
        for attempt in range(1, self._health_check_max_attempts + 1):
            try:
                import requests
                resp = requests.get(url, timeout=5)
                if resp.status_code == 200:
                    logger.info("Health check passed (attempt %d)", attempt)
                    return True
            except ImportError:
                logger.debug(
                    "requests not available — health check skipped in this environment"
                )
                return True
            except Exception:
                pass
            if attempt < self._health_check_max_attempts:
                time.sleep(self._health_check_interval)

        raise TimeoutError(
            f"Instance at {server_ip} did not become healthy after "
            f"{self._health_check_max_attempts} attempts "
            f"({int(self._health_check_max_attempts * self._health_check_interval)}s)"
        )

    def _send_welcome(self, account_id: str, url: str) -> None:
        """Send a welcome e-mail via the existing ``EmailService``."""
        email_mod = _import_first("src.email_integration", "email_integration")
        if email_mod is None:
            logger.info(
                "EmailService not importable — welcome email for account=%s not sent",
                account_id,
            )
            return

        try:
            import asyncio
            svc = email_mod.EmailService.from_env()
            loop = asyncio.new_event_loop()
            loop.run_until_complete(
                svc.send(
                    to=[f"{account_id}@murphy.systems"],
                    subject="Your Murphy System instance is ready",
                    body=(
                        f"Your Murphy System instance is live at {url}\n\n"
                        "Log in with the credentials you created during sign-up.\n\n"
                        "— The Murphy System team"
                    ),
                )
            )
            loop.close()
        except Exception as exc:
            logger.warning(
                "Welcome email failed (non-fatal): account=%s err=%s", account_id, exc
            )

    def _activate_metering(
        self, account_id: str, tenant_id: str, server_ip: str
    ) -> None:
        """Write provisioning info back to ``SubscriptionManager``.

        Calls ``update_provisioning_info`` to record ``provisioning_status``,
        ``server_ip``, and ``tenant_id`` on the ``SubscriptionRecord`` so
        the billing layer reflects the live infrastructure state.
        """
        mgr = self._subscription_manager
        if mgr is None:
            sm_mod = _import_first("src.subscription_manager", "subscription_manager")
            if sm_mod is None:
                logger.warning(
                    "SubscriptionManager not importable — metering not activated "
                    "for account=%s",
                    account_id,
                )
                return
            mgr = sm_mod.SubscriptionManager()

        if hasattr(mgr, "update_provisioning_info"):
            mgr.update_provisioning_info(
                account_id=account_id,
                provisioning_status=ProvisioningStatus.ACTIVE.value,
                server_ip=server_ip,
                tenant_id=tenant_id,
            )
            logger.info(
                "Metering activated: account=%s tenant_id=%s server_ip=%s",
                account_id, tenant_id, server_ip or "shared",
            )

    def _archive_tenant_workspace(self, account_id: str, tenant_id: str) -> None:
        """Archive the tenant workspace via ``WorkspaceManager``."""
        logger.info(
            "Archiving workspace: account=%s tenant_id=%s", account_id, tenant_id
        )
        mtw_mod = _import_first("src.multi_tenant_workspace", "multi_tenant_workspace")
        if mtw_mod is None:
            logger.warning(
                "WorkspaceManager not importable — archive skipped for tenant_id=%s",
                tenant_id,
            )
            return

        workspace_mgr = mtw_mod.WorkspaceManager()
        try:
            workspace_mgr.update_workspace_state(tenant_id, mtw_mod.WorkspaceState.ARCHIVED)
        except Exception as exc:
            logger.warning(
                "Workspace archive failed: tenant_id=%s err=%s", tenant_id, exc
            )

    # ------------------------------------------------------------------
    # Rollback
    # ------------------------------------------------------------------

    def _rollback(
        self,
        account_id: str,
        record: InfraRecord,
        server_result: Dict[str, Any],
        dns_record_id: str,
    ) -> None:
        """Best-effort cleanup of resources created before the failure."""
        logger.warning("Rolling back infra for account=%s", account_id)

        server_id = server_result.get("server_id", "")
        is_dry_run = server_result.get("dry_run", False)
        if server_id and not is_dry_run:
            try:
                self._provisioner.delete_server(server_id)
                self._log(record, f"Rollback: server {server_id} deleted")
            except Exception as exc:
                logger.error("Rollback: server deletion failed: %s", exc)

        if dns_record_id:
            try:
                self._dns.delete(dns_record_id)
                self._log(record, f"Rollback: DNS record {dns_record_id} removed")
            except Exception as exc:
                logger.error("Rollback: DNS deletion failed: %s", exc)

        if record.tenant_id:
            try:
                self._archive_tenant_workspace(account_id, record.tenant_id)
                self._log(record, f"Rollback: tenant {record.tenant_id} archived")
            except Exception as exc:
                logger.error("Rollback: tenant archive failed: %s", exc)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _set_status(self, record: InfraRecord, status: ProvisioningStatus) -> None:
        with self._lock:
            record.status = status
            record.updated_at = time.time()
        logger.debug("Status: account=%s → %s", record.account_id, status.value)

    def _log(self, record: InfraRecord, message: str) -> None:
        with self._lock:
            record.provisioning_log.append(
                f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} {message}"
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
