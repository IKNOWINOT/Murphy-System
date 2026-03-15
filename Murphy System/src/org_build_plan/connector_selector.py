# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Connector Selector — Step 4 of the org_build_plan pipeline.

Combines platform connectors from the industry preset, the organization's
existing systems, and any additional connector needs declared in the
intake profile into a de-duplicated, categorised selection.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List

from .organization_intake import OrganizationIntakeProfile

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Connector catalogue — all known connector IDs grouped by category
# ---------------------------------------------------------------------------

_CONNECTOR_CATEGORIES: Dict[str, List[str]] = {
    "communication": ["slack", "teams", "discord", "zoom", "gmail", "outlook"],
    "crm_sales": ["salesforce", "hubspot", "pipedrive", "zoho_crm"],
    "finance": ["quickbooks", "xero", "stripe", "paypal", "freshbooks"],
    "project_management": ["jira", "clickup", "asana", "trello", "linear", "monday"],
    "devops": ["github", "gitlab", "bitbucket", "jenkins", "circleci", "confluence"],
    "analytics": ["google_analytics", "power_bi", "tableau", "mixpanel", "amplitude"],
    "marketing": ["mailchimp", "hubspot_marketing", "canva", "hootsuite", "buffer"],
    "cloud": ["aws", "azure", "gcp", "digitalocean"],
    "iot_scada": [
        "scada_modbus",
        "scada_bacnet",
        "scada_opcua",
        "johnson_controls_metasys",
        "honeywell_niagara",
        "schneider_ecostruxure",
    ],
    "manufacturing": ["additive_manufacturing", "solidworks", "fusion360", "autocad"],
    "erp": ["sap", "oracle_erp", "netsuite", "dynamics_365"],
    "ecommerce": ["shopify", "woocommerce", "magento", "bigcommerce"],
    "data": ["snowflake", "databricks", "bigquery", "redshift", "mongodb", "postgres"],
}

# Flat set of all known connector IDs for validation
_ALL_CONNECTORS: List[str] = [
    connector
    for connectors in _CONNECTOR_CATEGORIES.values()
    for connector in connectors
]

# Reverse map: connector_id → category
_CONNECTOR_TO_CATEGORY: Dict[str, str] = {
    connector: category
    for category, connectors in _CONNECTOR_CATEGORIES.items()
    for connector in connectors
}

# ---------------------------------------------------------------------------
# ConnectorSelectionResult dataclass
# ---------------------------------------------------------------------------


@dataclass
class ConnectorSelectionResult:
    """Result of the connector selection step."""

    selected_connectors: List[str] = field(default_factory=list)
    from_preset: List[str] = field(default_factory=list)
    from_existing: List[str] = field(default_factory=list)
    from_needs: List[str] = field(default_factory=list)
    categories: Dict[str, List[str]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a JSON-compatible dictionary."""
        return {
            "selected_connectors": list(self.selected_connectors),
            "from_preset": list(self.from_preset),
            "from_existing": list(self.from_existing),
            "from_needs": list(self.from_needs),
            "categories": {k: list(v) for k, v in self.categories.items()},
        }


# ---------------------------------------------------------------------------
# ConnectorSelector class
# ---------------------------------------------------------------------------


class ConnectorSelector:
    """Selects and categorises platform connectors for a new tenant.

    Merges connectors from three sources (industry preset,
    existing systems, declared needs), de-duplicates, and
    groups them by category for wiring into the workspace.
    """

    def __init__(self) -> None:
        pass

    def select_connectors(
        self, intake: OrganizationIntakeProfile
    ) -> ConnectorSelectionResult:
        """Return the de-duplicated connector selection for *intake*.

        Sources (in priority order):
        1. Industry preset ``recommended_connectors``
        2. ``intake.existing_systems``
        3. ``intake.connector_needs``
        """
        from .presets import get_preset

        # --- source 1: industry preset ---
        preset_connectors: List[str] = []
        preset = get_preset(intake.industry)
        if preset is None:
            # Try to find a preset matching by industry field
            from .presets import INDUSTRY_PRESETS
            for p in INDUSTRY_PRESETS.values():
                if p.industry == intake.industry:
                    preset = p
                    break
        if preset is not None:
            preset_connectors = list(preset.recommended_connectors)

        # --- source 2: existing systems ---
        existing_connectors = list(intake.existing_systems)

        # --- source 3: declared needs ---
        needs_connectors = list(intake.connector_needs)

        # --- de-duplicate while preserving order ---
        seen: set = set()
        selected: List[str] = []
        for connector in preset_connectors + existing_connectors + needs_connectors:
            if connector and connector not in seen:
                seen.add(connector)
                selected.append(connector)

        # --- categorise ---
        categories: Dict[str, List[str]] = {}
        for connector in selected:
            cat = _CONNECTOR_TO_CATEGORY.get(connector, "other")
            categories.setdefault(cat, []).append(connector)

        # Track provenance (may overlap)
        from_preset = [c for c in selected if c in preset_connectors]
        from_existing = [c for c in selected if c in existing_connectors]
        from_needs = [c for c in selected if c in needs_connectors]

        result = ConnectorSelectionResult(
            selected_connectors=selected,
            from_preset=from_preset,
            from_existing=from_existing,
            from_needs=from_needs,
            categories=categories,
        )

        logger.info(
            "Selected %d connectors for '%s' (%d from preset, %d existing, %d needs)",
            len(selected),
            intake.org_name,
            len(from_preset),
            len(from_existing),
            len(from_needs),
        )
        return result

    def get_available_connectors(self) -> List[str]:
        """Return a sorted list of all known connector IDs."""
        return sorted(_ALL_CONNECTORS)


__all__ = [
    "ConnectorSelectionResult",
    "ConnectorSelector",
]
