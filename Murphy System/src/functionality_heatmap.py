"""
Functionality Heatmap & Capability Scanner for Murphy System.

Scans all registries and generates heat maps, elevation maps, and
cold/hot spot analysis showing where automation exists and where gaps
remain.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

from src.golden_path_bridge import GoldenPathBridge
from src.telemetry_adapter import TelemetryAdapter

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Domain capability registry
# ---------------------------------------------------------------------------

CAPABILITY_REGISTRY: Dict[str, Dict[str, List[str]]] = {
    "building_automation": {
        "fire_safety": [
            "smoke_detection",
            "sprinkler_control",
            "alarm_management",
            "evacuation_routing",
            "fire_panel_integration",
        ],
        "hvac": [
            "temperature_control",
            "ventilation",
            "humidity",
            "scheduling",
            "fault_detection",
        ],
        "lighting": [
            "occupancy_sensing",
            "daylight_harvesting",
            "scheduling",
            "emergency_lighting",
        ],
        "access_control": [
            "badge_readers",
            "visitor_management",
            "elevator_control",
            "parking",
        ],
        "energy_metering": [
            "submeter_reading",
            "demand_response",
            "solar_integration",
            "battery_management",
        ],
    },
    "manufacturing": {
        "production": [
            "scheduling",
            "quality_inspection",
            "downtime_tracking",
            "oee_calculation",
            "work_orders",
        ],
        "maintenance": [
            "preventive",
            "predictive",
            "spare_parts",
            "work_orders",
            "asset_registry",
        ],
        "supply_chain": [
            "procurement",
            "receiving",
            "inventory",
            "shipping",
            "vendor_management",
        ],
    },
    "enterprise": {
        "hr": [
            "onboarding",
            "payroll",
            "benefits",
            "performance_reviews",
            "time_tracking",
        ],
        "finance": [
            "accounts_payable",
            "accounts_receivable",
            "budgeting",
            "forecasting",
            "tax",
        ],
        "sales": [
            "lead_management",
            "pipeline",
            "quoting",
            "contracts",
            "commissions",
        ],
        "marketing": [
            "campaigns",
            "email",
            "social_media",
            "seo",
            "analytics",
        ],
    },
    "healthcare": {
        "clinical": [
            "patient_records",
            "prescriptions",
            "lab_orders",
            "imaging",
            "referrals",
        ],
        "administrative": [
            "scheduling",
            "billing",
            "insurance",
            "compliance",
            "reporting",
        ],
    },
    "logistics": {
        "fleet": [
            "vehicle_tracking",
            "driver_management",
            "fuel_monitoring",
            "maintenance",
        ],
        "warehouse": [
            "receiving",
            "putaway",
            "picking",
            "packing",
            "shipping",
        ],
        "routing": [
            "route_planning",
            "real_time_tracking",
            "delivery_confirmation",
            "returns",
        ],
    },
}

# ---------------------------------------------------------------------------
# ISA-95 elevation levels
# ---------------------------------------------------------------------------

ISA95_LEVELS: Dict[str, str] = {
    "L0": "Physical Process (Sensors/Actuators)",
    "L1": "Basic Control (PLC/RTU)",
    "L2": "Supervisory Control (SCADA/HMI)",
    "L3": "Manufacturing Operations (MES/MOM)",
    "L4": "Enterprise (ERP/Business Planning)",
}

# Keyword sets used to assign ISA-95 levels
_LEVEL_KEYWORDS: Dict[str, List[str]] = {
    "L0": ["sensor", "detection", "actuator", "meter"],
    "L1": ["control", "plc", "rtu"],
    "L2": ["monitoring", "alarm", "scheduling", "hmi"],
    "L3": ["management", "tracking", "orders", "inspection", "quality"],
    "L4": ["planning", "budgeting", "forecasting", "analytics", "reporting", "compliance"],
}

_VALID_STATUSES = frozenset(
    {"not_started", "planned", "in_progress", "automated", "optimized"}
)


def _assign_isa95_level(function_name: str) -> str:
    """Return the ISA-95 level for *function_name* based on keyword matching."""
    lowered = function_name.lower()
    for level in ("L0", "L1", "L2", "L3", "L4"):
        for kw in _LEVEL_KEYWORDS[level]:
            if kw in lowered:
                return level
    return "L3"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class CapabilityCell:
    """A single capability entry in the heatmap."""

    domain: str
    subdomain: str
    function_name: str
    temperature: float  # 0.0 (cold/unused) to 1.0 (hot/active)
    isa95_level: str  # "L0" through "L4"
    automation_status: str  # not_started | planned | in_progress | automated | optimized
    linked_automations: List[str] = field(default_factory=list)  # IDs of connected rules
    last_activity: str = ""  # ISO timestamp
    activity_count: int = 0


# ---------------------------------------------------------------------------
# Heatmap engine
# ---------------------------------------------------------------------------

class FunctionalityHeatmap:
    """Scans capability domains and generates heat maps and gap analysis.

    Wires together:
    - :class:`TelemetryAdapter` — activity metrics
    - :class:`GoldenPathBridge` — proven path data
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._telemetry = TelemetryAdapter()
        self._golden_paths = GoldenPathBridge()

        # Nested dict: domain → subdomain → function_name → CapabilityCell
        self._cells: Dict[str, Dict[str, Dict[str, CapabilityCell]]] = {}
        self._initialise_from_registry()

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def _initialise_from_registry(self) -> None:
        """Populate all cells from :data:`CAPABILITY_REGISTRY` as cold."""
        for domain, subdomains in CAPABILITY_REGISTRY.items():
            self._cells[domain] = {}
            for subdomain, functions in subdomains.items():
                self._cells[domain][subdomain] = {}
                for fn in functions:
                    self._cells[domain][subdomain][fn] = CapabilityCell(
                        domain=domain,
                        subdomain=subdomain,
                        function_name=fn,
                        temperature=0.0,
                        isa95_level=_assign_isa95_level(fn),
                        automation_status="not_started",
                    )

    # ------------------------------------------------------------------
    # Mutation helpers
    # ------------------------------------------------------------------

    def _get_cell(
        self, domain: str, subdomain: str, function_name: str
    ) -> Optional[CapabilityCell]:
        return (
            self._cells
            .get(domain, {})
            .get(subdomain, {})
            .get(function_name)
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record_activity(
        self,
        domain: str,
        subdomain: str,
        function_name: str,
        automation_id: Optional[str] = None,
    ) -> CapabilityCell:
        """Increment activity, raise temperature, and optionally link automation.

        Returns the updated :class:`CapabilityCell`.
        Raises :exc:`KeyError` if the combination is not in the registry.
        """
        with self._lock:
            cell = self._get_cell(domain, subdomain, function_name)
            if cell is None:
                raise KeyError(
                    f"Unknown capability: {domain}/{subdomain}/{function_name}"
                )
            cell.activity_count += 1
            cell.temperature = min(1.0, cell.activity_count / 100.0)
            cell.last_activity = datetime.now(timezone.utc).isoformat()
            if automation_id and automation_id not in cell.linked_automations:
                cell.linked_automations.append(automation_id)

            # Emit telemetry metric
            try:
                self._telemetry.collect_metric(
                    metric_type="user_actions",
                    metric_name=f"heatmap.activity.{domain}.{subdomain}.{function_name}",
                    value=float(cell.activity_count),
                )
            except Exception as exc:
                logger.warning("Telemetry collection failed: %s", exc)

        return cell

    def set_automation_status(
        self,
        domain: str,
        subdomain: str,
        function_name: str,
        status: str,
    ) -> bool:
        """Update the automation status for a capability cell.

        Returns ``True`` on success, ``False`` if the cell or status is invalid.
        """
        if status not in _VALID_STATUSES:
            logger.warning("Invalid automation status: %s", status)
            return False
        with self._lock:
            cell = self._get_cell(domain, subdomain, function_name)
            if cell is None:
                return False
            cell.automation_status = status
        return True

    def get_heatmap(
        self, domain: Optional[str] = None
    ) -> Dict[str, Dict[str, List[dict]]]:
        """Return the full nested heat map.

        Structure: ``domain → subdomain → [cell dicts]``.
        Pass *domain* to restrict output to a single domain.
        """
        with self._lock:
            if domain is not None:
                if domain not in self._cells:
                    return {}
                domains = {domain: self._cells[domain]}
            else:
                domains = dict(self._cells)
            result: Dict[str, Dict[str, List[dict]]] = {}
            for dom, subdomains in domains.items():
                result[dom] = {}
                for sub, functions in subdomains.items():
                    result[dom][sub] = [
                        {
                            "function_name": c.function_name,
                            "temperature": c.temperature,
                            "isa95_level": c.isa95_level,
                            "automation_status": c.automation_status,
                            "linked_automations": list(c.linked_automations),
                            "last_activity": c.last_activity,
                            "activity_count": c.activity_count,
                        }
                        for c in functions.values()
                    ]
        return result

    def get_elevation_map(self) -> Dict[str, Dict[str, int]]:
        """Return ISA-95 level → count of capabilities at each level.

        Structure: ``{"L0": {"count": N, "label": "..."}, ...}``.
        """
        counts: Dict[str, int] = {lvl: 0 for lvl in ISA95_LEVELS}
        with self._lock:
            for subdomains in self._cells.values():
                for functions in subdomains.values():
                    for cell in functions.values():
                        counts[cell.isa95_level] += 1
        return {
            lvl: {"count": counts[lvl], "label": ISA95_LEVELS[lvl]}
            for lvl in ISA95_LEVELS
        }

    def get_cold_spots(self, threshold: float = 0.1) -> List[CapabilityCell]:
        """Return registered but unused/barely-used capabilities.

        A cell is *cold* when its temperature is strictly below *threshold*.
        """
        result: List[CapabilityCell] = []
        with self._lock:
            for subdomains in self._cells.values():
                for functions in subdomains.values():
                    for cell in functions.values():
                        if cell.temperature < threshold:
                            result.append(cell)
        return result

    def get_hot_spots(self, threshold: float = 0.7) -> List[CapabilityCell]:
        """Return the most active capabilities.

        A cell is *hot* when its temperature is greater than or equal to
        *threshold*.
        """
        result: List[CapabilityCell] = []
        with self._lock:
            for subdomains in self._cells.values():
                for functions in subdomains.values():
                    for cell in functions.values():
                        if cell.temperature >= threshold:
                            result.append(cell)
        return sorted(result, key=lambda c: c.temperature, reverse=True)

    def get_coverage_report(self) -> Dict:
        """Return per-domain coverage statistics.

        Structure::

            {
                "building_automation": {
                    "total_functions": 18,
                    "automated_count": 3,
                    "coverage_percent": 16.67,
                    "avg_temperature": 0.05,
                },
                ...
            }
        """
        report: Dict = {}
        with self._lock:
            for domain, subdomains in self._cells.items():
                all_cells = [
                    cell
                    for functions in subdomains.values()
                    for cell in functions.values()
                ]
                total = len(all_cells)
                automated = sum(
                    1
                    for c in all_cells
                    if c.automation_status in ("automated", "optimized")
                )
                avg_temp = sum(c.temperature for c in all_cells) / (total or 1)
                coverage = (automated / (total or 1)) * 100.0
                report[domain] = {
                    "total_functions": total,
                    "automated_count": automated,
                    "coverage_percent": round(coverage, 2),
                    "avg_temperature": round(avg_temp, 4),
                }
        return report

    def get_dashboard_data(self) -> Dict:
        """Return a summary suitable for UI rendering.

        Includes totals, top hot spots, top cold spots, and coverage
        per domain.
        """
        with self._lock:
            all_cells = [
                cell
                for subdomains in self._cells.values()
                for functions in subdomains.values()
                for cell in functions.values()
            ]

        total_functions = len(all_cells)
        total_automated = sum(
            1 for c in all_cells if c.automation_status in ("automated", "optimized")
        )
        overall_coverage = (total_automated / (total_functions or 1)) * 100.0

        hot = sorted(
            (c for c in all_cells if c.temperature >= 0.7),
            key=lambda c: c.temperature,
            reverse=True,
        )[:10]
        cold = sorted(
            (c for c in all_cells if c.temperature < 0.1),
            key=lambda c: c.temperature,
        )[:10]

        return {
            "total_functions": total_functions,
            "total_automated": total_automated,
            "overall_coverage_percent": round(overall_coverage, 2),
            "top_hot_spots": [
                {
                    "domain": c.domain,
                    "subdomain": c.subdomain,
                    "function_name": c.function_name,
                    "temperature": c.temperature,
                    "automation_status": c.automation_status,
                }
                for c in hot
            ],
            "top_cold_spots": [
                {
                    "domain": c.domain,
                    "subdomain": c.subdomain,
                    "function_name": c.function_name,
                    "temperature": c.temperature,
                    "automation_status": c.automation_status,
                }
                for c in cold
            ],
            "coverage_per_domain": self.get_coverage_report(),
        }
