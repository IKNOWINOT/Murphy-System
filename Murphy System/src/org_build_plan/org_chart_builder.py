# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Org Chart Builder — Step 3 of the org_build_plan pipeline.

Converts an :class:`OrganizationIntakeProfile` into a fully-wired
corporate org chart (via :class:`CorporateOrgChart`) and a
deterministic enforcement layer (via :class:`OrgChartEnforcement`).
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .organization_intake import DepartmentSpec, OrganizationIntakeProfile

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Mapping tables
# ---------------------------------------------------------------------------

DEPARTMENT_MAP: Dict[str, str] = {
    "engineering": "engineering",
    "operations": "operations",
    "sales": "sales",
    "marketing": "marketing",
    "finance": "finance",
    "hr": "hr",
    "legal": "legal",
    "product": "product",
    "executive": "executive",
    "it": "it",
    "research": "research",
    "customer_success": "customer_success",
}

LEVEL_MAP: Dict[str, str] = {
    "c_suite": "c_suite",
    "vp": "vp",
    "director": "director",
    "manager": "manager",
    "lead": "lead",
    "individual_contributor": "individual_contributor",
    "intern": "intern",
}

# Map escalation levels based on position level
_ESCALATION_LEVEL_MAP: Dict[str, str] = {
    "c_suite": "C_LEVEL",
    "vp": "VP",
    "director": "DEPARTMENT_HEAD",
    "manager": "DEPARTMENT_HEAD",
    "lead": "TEAM_LEAD",
    "individual_contributor": "TEAM_LEAD",
    "intern": "TEAM_LEAD",
}

# ---------------------------------------------------------------------------
# OrgChartResult dataclass
# ---------------------------------------------------------------------------


@dataclass
class OrgChartResult:
    """Result of building an org chart from an intake profile."""

    positions_created: int = 0
    enforcement_nodes: int = 0
    reporting_chains: int = 0
    org_chart: Dict[str, Any] = field(default_factory=dict)
    departments_mapped: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a JSON-compatible dictionary."""
        return {
            "positions_created": self.positions_created,
            "enforcement_nodes": self.enforcement_nodes,
            "reporting_chains": self.reporting_chains,
            "org_chart": dict(self.org_chart),
            "departments_mapped": list(self.departments_mapped),
        }


# ---------------------------------------------------------------------------
# OrgChartBuilder class
# ---------------------------------------------------------------------------


class OrgChartBuilder:
    """Builds a corporate org chart and enforcement layer from an intake profile."""

    def __init__(self) -> None:
        pass

    # ------------------------------------------------------------------
    # Department / level mapping helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _map_department(name: str) -> str:
        """Return the canonical :class:`DepartmentType` value for *name*."""
        key = name.lower().replace(" ", "_").replace("-", "_")
        return DEPARTMENT_MAP.get(key, "operations")

    @staticmethod
    def _map_level(level: str) -> str:
        """Return the canonical :class:`PositionLevel` value for *level*."""
        return LEVEL_MAP.get(level.lower(), "individual_contributor")

    @staticmethod
    def _map_escalation_level(level: str) -> Any:
        """Return the :class:`EscalationLevel` appropriate for *level*."""
        try:
            from org_chart_enforcement import EscalationLevel
        except ImportError:
            from src.org_chart_enforcement import EscalationLevel  # type: ignore[no-reattr]

        label = _ESCALATION_LEVEL_MAP.get(level.lower(), "TEAM_LEAD")
        return EscalationLevel[label]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build_from_intake(self, intake: OrganizationIntakeProfile) -> OrgChartResult:
        """Build a full org chart from *intake* and return an :class:`OrgChartResult`.

        Creates a virtual CEO node as the root, then adds one head
        position per department.  For departments with headcount > 1 an
        individual-contributor position is added beneath the head.
        """
        try:
            from onboarding_flow import CorporateOrgChart
        except ImportError:
            from src.onboarding_flow import CorporateOrgChart  # type: ignore[no-reattr]

        org_chart = CorporateOrgChart()

        # Create a synthetic CEO root position
        ceo_id = f"ceo_{uuid.uuid4().hex[:6]}"
        ceo_pos = org_chart.add_position(
            title=f"CEO ({intake.org_name or 'Organization'})",
            level="c_suite",
            department="executive",
        )
        ceo_pos_id = ceo_pos.position_id

        positions_created = 1  # CEO
        reporting_chains = 0
        departments_mapped: List[str] = []
        chart_nodes: Dict[str, Any] = {
            ceo_pos_id: ceo_pos.to_dict(),
        }

        for dept in intake.departments:
            dept_type = self._map_department(dept.name)
            pos_level = self._map_level(dept.level)

            # Create department head
            head_pos = org_chart.add_position(
                title=f"{dept.head_name} ({dept.name})" if dept.head_name else dept.name,
                level=pos_level,
                department=dept_type,
                reports_to=ceo_pos_id,
                responsibilities=dept.responsibilities,
                automation_scope=dept.automation_priorities,
            )
            positions_created += 1
            reporting_chains += 1
            chart_nodes[head_pos.position_id] = head_pos.to_dict()
            departments_mapped.append(dept.name)

            # Add IC positions for headcount > 1
            if dept.headcount > 1:
                ic_count = min(dept.headcount - 1, 3)  # cap at 3 representative ICs
                for i in range(ic_count):
                    ic_pos = org_chart.add_position(
                        title=f"{dept.name} Team Member {i + 1}",
                        level="individual_contributor",
                        department=dept_type,
                        reports_to=head_pos.position_id,
                        responsibilities=dept.responsibilities,
                        automation_scope=dept.automation_priorities,
                    )
                    positions_created += 1
                    reporting_chains += 1
                    chart_nodes[ic_pos.position_id] = ic_pos.to_dict()

        enforcement = self.build_enforcement(intake)

        result = OrgChartResult(
            positions_created=positions_created,
            enforcement_nodes=enforcement._nodes.__len__() if hasattr(enforcement, "_nodes") else 0,
            reporting_chains=reporting_chains,
            org_chart=chart_nodes,
            departments_mapped=departments_mapped,
        )

        logger.info(
            "Built org chart for '%s': %d positions, %d reporting chains",
            intake.org_name,
            positions_created,
            reporting_chains,
        )
        return result

    def build_enforcement(self, intake: OrganizationIntakeProfile) -> Any:
        """Build and return the :class:`OrgChartEnforcement` layer.

        Creates enforcement nodes for each department head with
        permissions derived from their responsibilities list.
        """
        try:
            from org_chart_enforcement import OrgChartEnforcement
        except ImportError:
            from src.org_chart_enforcement import OrgChartEnforcement  # type: ignore[no-reattr]

        enforcement = OrgChartEnforcement()
        ceo_node_id = f"enf_ceo_{uuid.uuid4().hex[:6]}"
        enforcement.add_node(
            node_id=ceo_node_id,
            role="CEO",
            department="executive",
            reports_to=None,
            permissions=["read", "write", "approve", "admin"],
            escalation_level=self._map_escalation_level("c_suite"),
        )

        for dept in intake.departments:
            dept_type = self._map_department(dept.name)
            escalation = self._map_escalation_level(dept.level)

            # Derive permissions from responsibilities
            permissions = _responsibilities_to_permissions(dept.responsibilities)

            node_id = f"enf_{uuid.uuid4().hex[:8]}"
            enforcement.add_node(
                node_id=node_id,
                role=dept.head_name or dept.name,
                department=dept_type,
                reports_to=ceo_node_id,
                permissions=permissions,
                escalation_level=escalation,
            )

        return enforcement


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _responsibilities_to_permissions(responsibilities: List[str]) -> List[str]:
    """Convert a list of responsibility strings into permission tokens."""
    permissions: List[str] = ["read"]
    for resp in responsibilities:
        r = resp.lower()
        if any(k in r for k in ("report", "audit", "compliance")):
            if "write" not in permissions:
                permissions.append("write")
        if any(k in r for k in ("approve", "review", "signoff")):
            if "approve" not in permissions:
                permissions.append("approve")
        if any(k in r for k in ("manage", "admin", "director", "vp")):
            if "admin" not in permissions:
                permissions.append("admin")
    return permissions


__all__ = [
    "OrgChartResult",
    "OrgChartBuilder",
    "DEPARTMENT_MAP",
    "LEVEL_MAP",
]
