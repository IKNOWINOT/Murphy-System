# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Tenant Provisioner — Step 2 of the org_build_plan pipeline.

Creates an isolated workspace for the incoming organization, selecting
the appropriate isolation level and resource limits based on the
intake profile.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .organization_intake import OrganizationIntakeProfile

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Resource-limit tiers keyed by company_size
# ---------------------------------------------------------------------------

_RESOURCE_LIMITS: Dict[str, Dict[str, int]] = {
    "small": {
        "max_storage_mb": 256,
        "max_api_calls": 10_000,
        "max_members": 20,
    },
    "medium": {
        "max_storage_mb": 1024,
        "max_api_calls": 100_000,
        "max_members": 50,
    },
    "enterprise": {
        "max_storage_mb": 4096,
        "max_api_calls": 500_000,
        "max_members": 200,
    },
}

# ---------------------------------------------------------------------------
# ProvisionResult dataclass
# ---------------------------------------------------------------------------


@dataclass
class ProvisionResult:
    """Result of a tenant provisioning operation."""

    tenant_id: str
    workspace_config: Dict[str, Any] = field(default_factory=dict)
    owner_added: bool = False
    isolation_level: str = "standard"
    resource_limits: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a JSON-compatible dictionary."""
        return {
            "tenant_id": self.tenant_id,
            "workspace_config": dict(self.workspace_config),
            "owner_added": self.owner_added,
            "isolation_level": self.isolation_level,
            "resource_limits": dict(self.resource_limits),
        }


# ---------------------------------------------------------------------------
# TenantProvisioner class
# ---------------------------------------------------------------------------


class TenantProvisioner:
    """Provisions isolated tenant workspaces from an intake profile.

    Injects or creates a :class:`WorkspaceManager`, determines
    isolation level from IP protection requirements, scales resource
    limits by company size, and adds the org founder as the ``owner``
    role.
    """

    def __init__(self, workspace_manager: Any = None) -> None:
        if workspace_manager is not None:
            self._manager = workspace_manager
        else:
            try:
                from multi_tenant_workspace import WorkspaceManager
            except ImportError:
                from src.multi_tenant_workspace import WorkspaceManager  # type: ignore[no-reattr]
            self._manager = WorkspaceManager()

    # ------------------------------------------------------------------
    # Core provisioning
    # ------------------------------------------------------------------

    def provision(self, intake: OrganizationIntakeProfile) -> ProvisionResult:
        """Create a tenant workspace from *intake* and return a :class:`ProvisionResult`.

        Isolation level mapping:
          - patent_pending → strict
          - trade_secret   → strict
          - standard       → standard

        Resource limits scale by *company_size*.
        """
        try:
            from multi_tenant_workspace import IsolationLevel, TenantConfig, TenantRole
        except ImportError:
            from src.multi_tenant_workspace import IsolationLevel, TenantConfig, TenantRole  # type: ignore[no-reattr]

        # Determine isolation level
        ip = intake.ip_protection_level
        if ip in ("patent_pending", "trade_secret"):
            isolation = IsolationLevel.STRICT
            isolation_str = "strict"
        else:
            isolation = IsolationLevel.STANDARD
            isolation_str = "standard"

        # Scale resource limits
        limits = _RESOURCE_LIMITS.get(
            intake.company_size, _RESOURCE_LIMITS["medium"]
        )

        # Build custom settings from intake metadata
        custom_settings: Dict[str, Any] = {
            "industry": intake.industry,
            "org_type": intake.org_type,
            "labor_model": intake.labor_model,
            "franchise_model": intake.franchise_model,
            "budget_tracking": intake.budget_tracking,
            "ip_protection_level": ip,
        }

        tenant_id = uuid.uuid4().hex[:12]

        config = TenantConfig(
            tenant_id=tenant_id,
            name=intake.org_name,
            isolation_level=isolation,
            max_storage_mb=limits["max_storage_mb"],
            max_api_calls=limits["max_api_calls"],
            max_members=limits["max_members"],
            custom_settings=custom_settings,
        )

        created_id = self._manager.create_workspace(config)

        # Add org founder / owner (derive a synthetic user_id from org name)
        owner_user_id = f"owner_{uuid.uuid4().hex[:8]}"
        owner_added = self._manager.add_member(
            created_id, owner_user_id, TenantRole.OWNER, added_by="system"
        )

        result = ProvisionResult(
            tenant_id=created_id,
            workspace_config=config.to_dict(),
            owner_added=owner_added,
            isolation_level=isolation_str,
            resource_limits=dict(limits),
        )

        logger.info(
            "Provisioned workspace '%s' for org '%s' (isolation=%s)",
            created_id,
            intake.org_name,
            isolation_str,
        )
        return result

    # ------------------------------------------------------------------
    # Workspace lookup
    # ------------------------------------------------------------------

    def get_tenant(self, tenant_id: str) -> Optional[Any]:
        """Return the :class:`TenantConfig` for *tenant_id*, or ``None``."""
        return self._manager.get_workspace(tenant_id)


__all__ = [
    "ProvisionResult",
    "TenantProvisioner",
]
