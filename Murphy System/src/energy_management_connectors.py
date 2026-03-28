"""
Energy Management Connectors Module — Connector adapters for energy management,
utility analytics, building EMS, and sustainability platforms.

Provides a unified interface for utility analytics, building energy management,
grid management, renewable integration, demand response, and sustainability
reporting platforms with thread-safe registry, workflow orchestration, and
automatic capability mapping.
"""

import logging
import threading
import time
import uuid
from enum import Enum
from typing import Any, Dict, List, Optional

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class EnergyManagementCategory(Enum):
    """Energy management category (Enum subclass)."""
    UTILITY_ANALYTICS = "utility_analytics"
    BUILDING_EMS = "building_ems"
    GRID_MANAGEMENT = "grid_management"
    RENEWABLE_INTEGRATION = "renewable_integration"
    DEMAND_RESPONSE = "demand_response"
    SUSTAINABILITY_REPORTING = "sustainability_reporting"


class EnergyProtocol(Enum):
    """Energy protocol (Enum subclass)."""
    MODBUS = "modbus"
    BACNET = "bacnet"
    OPC_UA = "opc_ua"
    MQTT = "mqtt"
    REST_API = "rest_api"
    GREEN_BUTTON = "green_button"
    ENERGY_STAR_PORTFOLIO = "energy_star_portfolio"


class ConnectorStatus(Enum):
    """Connector status (Enum subclass)."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"
    DISABLED = "disabled"


# ---------------------------------------------------------------------------
# Base Connector
# ---------------------------------------------------------------------------

class EnergyManagementConnector:
    """Base adapter for an energy management platform integration."""

    def __init__(
        self,
        name: str,
        category: EnergyManagementCategory,
        vendor: str,
        protocol: EnergyProtocol,
        connection_config: Dict[str, Any],
        capabilities: List[str],
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.name = name
        self.category = category
        self.vendor = vendor
        self.protocol = protocol
        self.connection_config = dict(connection_config)
        self.capabilities = list(capabilities)
        self.metadata = dict(metadata) if metadata else {}

        self._lock = threading.RLock()
        self._status = ConnectorStatus.UNKNOWN
        self._request_count = 0
        self._error_count = 0
        self._window_start = time.time()
        self._window_requests = 0
        self._enabled = True
        self._credentials: Dict[str, str] = {}
        self._action_log: List[Dict[str, Any]] = []

    # -- public interface ---------------------------------------------------

    def health_check(self) -> Dict[str, Any]:
        """Return current health status of the connector."""
        with self._lock:
            if not self._enabled:
                self._status = ConnectorStatus.DISABLED
            elif self._request_count == 0:
                self._status = ConnectorStatus.UNKNOWN
            else:
                error_rate = self._error_count / max(self._request_count, 1)
                if error_rate > 0.5:
                    self._status = ConnectorStatus.UNHEALTHY
                elif error_rate > 0.1:
                    self._status = ConnectorStatus.DEGRADED
                else:
                    self._status = ConnectorStatus.HEALTHY
            return {
                "name": self.name,
                "vendor": self.vendor,
                "status": self._status.value,
                "enabled": self._enabled,
                "request_count": self._request_count,
                "error_count": self._error_count,
                "timestamp": time.time(),
            }

    def execute_action(self, action_name: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute a named action against this connector."""
        params = params or {}
        with self._lock:
            if not self._enabled:
                return self._action_result(action_name, False, error="Connector is disabled")

            if action_name not in self.capabilities:
                return self._action_result(action_name, False, error=f"Unsupported action: {action_name}")

            if not self._check_rate_limit():
                return self._action_result(action_name, False, error="Rate limit exceeded")

            self._request_count += 1
            result = self._action_result(
                action_name,
                True,
                data={
                    "action": action_name,
                    "vendor": self.vendor,
                    "params": params,
                    "simulated": True,
                },
            )
            capped_append(self._action_log, result)
            return result

    # -- configuration ------------------------------------------------------

    def configure(self, credentials: Dict[str, str]) -> Dict[str, Any]:
        with self._lock:
            self._credentials = dict(credentials)
            return {"configured": True, "name": self.name}

    def enable(self) -> None:
        with self._lock:
            self._enabled = True

    def disable(self) -> None:
        with self._lock:
            self._enabled = False

    def is_enabled(self) -> bool:
        with self._lock:
            return self._enabled

    def to_dict(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "name": self.name,
                "category": self.category.value,
                "vendor": self.vendor,
                "protocol": self.protocol.value,
                "connection_config": self.connection_config,
                "capabilities": self.capabilities,
                "enabled": self._enabled,
                "status": self._status.value,
                "request_count": self._request_count,
                "error_count": self._error_count,
                "metadata": self.metadata,
            }

    # -- internals ----------------------------------------------------------

    def _check_rate_limit(self) -> bool:
        now = time.time()
        if now - self._window_start > 60:
            self._window_start = now
            self._window_requests = 0
        rpm = self.connection_config.get("rate_limit", {}).get("requests_per_minute", 60)
        if self._window_requests >= rpm:
            return False
        self._window_requests += 1
        return True

    def _action_result(self, action_name: str, success: bool, data: Any = None, error: Optional[str] = None) -> Dict[str, Any]:
        return {
            "action": action_name,
            "connector": self.name,
            "success": success,
            "data": data,
            "error": error,
            "timestamp": time.time(),
        }


# ---------------------------------------------------------------------------
# Default connector definitions
# ---------------------------------------------------------------------------

def _build_defaults() -> List[EnergyManagementConnector]:
    specs = [
        # ---- Leading EMS Platforms ----
        {
            "name": "Johnson Controls OpenBlue",
            "category": EnergyManagementCategory.BUILDING_EMS,
            "vendor": "johnson_controls",
            "protocol": EnergyProtocol.REST_API,
            "connection_config": {"rate_limit": {"requests_per_minute": 120, "burst_limit": 20}},
            "capabilities": [
                "energy_performance_monitoring", "fault_detection_diagnostics",
                "predictive_energy_analytics", "sustainability_tracking",
                "carbon_footprint_reporting", "smart_building_optimization",
                "demand_response_management", "occupancy_based_control",
            ],
        },
        {
            "name": "Honeywell Forge Energy",
            "category": EnergyManagementCategory.BUILDING_EMS,
            "vendor": "honeywell",
            "protocol": EnergyProtocol.REST_API,
            "connection_config": {"rate_limit": {"requests_per_minute": 100, "burst_limit": 15}},
            "capabilities": [
                "energy_optimization", "portfolio_analytics",
                "utility_rate_analysis", "predictive_maintenance",
                "carbon_management", "energy_benchmarking",
                "demand_forecasting", "renewable_integration_tracking",
            ],
        },
        {
            "name": "Schneider Electric EcoStruxure",
            "category": EnergyManagementCategory.BUILDING_EMS,
            "vendor": "schneider_electric",
            "protocol": EnergyProtocol.REST_API,
            "connection_config": {"rate_limit": {"requests_per_minute": 150, "burst_limit": 25}},
            "capabilities": [
                "power_monitoring", "energy_analytics",
                "microgrid_management", "power_quality_analysis",
                "electrical_distribution", "building_analytics",
                "demand_side_management", "sustainability_dashboard",
            ],
        },
        {
            "name": "Siemens Navigator",
            "category": EnergyManagementCategory.BUILDING_EMS,
            "vendor": "siemens",
            "protocol": EnergyProtocol.REST_API,
            "connection_config": {"rate_limit": {"requests_per_minute": 100, "burst_limit": 15}},
            "capabilities": [
                "building_performance_analytics", "energy_benchmarking",
                "fault_detection", "carbon_tracking",
                "portfolio_optimization", "weather_normalization",
                "utility_bill_management", "regression_analysis",
            ],
        },
        {
            "name": "EnergyCAP",
            "category": EnergyManagementCategory.UTILITY_ANALYTICS,
            "vendor": "energycap",
            "protocol": EnergyProtocol.REST_API,
            "connection_config": {"rate_limit": {"requests_per_minute": 80, "burst_limit": 12}},
            "capabilities": [
                "utility_bill_tracking", "energy_accounting",
                "cost_allocation", "budget_forecasting",
                "rate_analysis", "weather_normalization",
                "savings_verification", "sustainability_reporting",
            ],
        },
        {
            "name": "Lucid BuildingOS",
            "category": EnergyManagementCategory.BUILDING_EMS,
            "vendor": "lucid",
            "protocol": EnergyProtocol.REST_API,
            "connection_config": {"rate_limit": {"requests_per_minute": 90, "burst_limit": 15}},
            "capabilities": [
                "real_time_metering", "energy_dashboards",
                "portfolio_benchmarking", "utility_data_integration",
                "building_analytics", "sustainability_tracking",
                "occupant_engagement", "interval_data_analysis",
            ],
        },
        {
            "name": "ENERGY STAR Portfolio Manager",
            "category": EnergyManagementCategory.SUSTAINABILITY_REPORTING,
            "vendor": "epa",
            "protocol": EnergyProtocol.ENERGY_STAR_PORTFOLIO,
            "connection_config": {"rate_limit": {"requests_per_minute": 30, "burst_limit": 5}},
            "capabilities": [
                "energy_benchmarking", "water_benchmarking",
                "greenhouse_gas_tracking", "energy_star_certification",
                "property_management", "goal_tracking",
                "data_sharing", "reporting",
            ],
        },
        {
            "name": "Enel X Demand Response",
            "category": EnergyManagementCategory.DEMAND_RESPONSE,
            "vendor": "enel_x",
            "protocol": EnergyProtocol.REST_API,
            "connection_config": {"rate_limit": {"requests_per_minute": 60, "burst_limit": 10}},
            "capabilities": [
                "demand_response_enrollment", "load_curtailment",
                "capacity_bidding", "event_notification",
                "settlement_reporting", "baseline_calculation",
                "performance_tracking", "grid_service_participation",
            ],
        },
        {
            "name": "Alerton EMS",
            "category": EnergyManagementCategory.BUILDING_EMS,
            "vendor": "alerton",
            "protocol": EnergyProtocol.BACNET,
            "connection_config": {"rate_limit": {"requests_per_minute": 60, "burst_limit": 10}},
            "capabilities": [
                "energy_monitoring", "trend_analysis",
                "alarm_management", "scheduling",
                "setpoint_optimization", "equipment_tracking",
                "performance_reporting", "remote_monitoring",
            ],
        },
        {
            "name": "SolarEdge Monitoring",
            "category": EnergyManagementCategory.RENEWABLE_INTEGRATION,
            "vendor": "solaredge",
            "protocol": EnergyProtocol.REST_API,
            "connection_config": {"rate_limit": {"requests_per_minute": 100, "burst_limit": 15}},
            "capabilities": [
                "pv_production_monitoring", "inverter_management",
                "string_level_monitoring", "power_optimizer_tracking",
                "energy_forecasting", "grid_export_monitoring",
                "battery_management", "environmental_benefit_tracking",
            ],
        },
        # ---- Extended EMS Platforms ----
        {
            "name": "GridPoint Energy Management",
            "category": EnergyManagementCategory.BUILDING_EMS,
            "vendor": "gridpoint",
            "protocol": EnergyProtocol.REST_API,
            "connection_config": {"rate_limit": {"requests_per_minute": 80, "burst_limit": 12}},
            "capabilities": [
                "energy_optimization", "hvac_control_optimization",
                "demand_management", "portfolio_analytics",
                "fault_detection", "comfort_management",
                "sustainability_tracking", "utility_rate_analysis",
            ],
        },
        {
            "name": "Tridium Niagara Framework",
            "category": EnergyManagementCategory.BUILDING_EMS,
            "vendor": "tridium",
            "protocol": EnergyProtocol.REST_API,
            "connection_config": {"rate_limit": {"requests_per_minute": 120, "burst_limit": 18}},
            "capabilities": [
                "open_framework_integration", "multi_protocol_normalization",
                "energy_dashboards", "analytics_engine",
                "alarm_management", "equipment_scheduling",
                "data_historian", "edge_computing",
            ],
        },
        {
            "name": "ABB Ability Energy Manager",
            "category": EnergyManagementCategory.BUILDING_EMS,
            "vendor": "abb",
            "protocol": EnergyProtocol.REST_API,
            "connection_config": {"rate_limit": {"requests_per_minute": 90, "burst_limit": 14}},
            "capabilities": [
                "energy_monitoring", "power_quality_analysis",
                "load_management", "demand_forecasting",
                "energy_cost_optimization", "carbon_tracking",
                "asset_performance", "microgrid_management",
            ],
        },
        {
            "name": "Emerson Ovation/DeltaV Energy",
            "category": EnergyManagementCategory.GRID_MANAGEMENT,
            "vendor": "emerson",
            "protocol": EnergyProtocol.OPC_UA,
            "connection_config": {"rate_limit": {"requests_per_minute": 100, "burst_limit": 15}},
            "capabilities": [
                "power_plant_optimization", "turbine_control",
                "heat_rate_optimization", "emissions_monitoring",
                "grid_synchronization", "predictive_maintenance",
                "energy_efficiency_analytics", "asset_management",
            ],
        },
        {
            "name": "Enverus Power & Renewables",
            "category": EnergyManagementCategory.RENEWABLE_INTEGRATION,
            "vendor": "enverus",
            "protocol": EnergyProtocol.REST_API,
            "connection_config": {"rate_limit": {"requests_per_minute": 60, "burst_limit": 10}},
            "capabilities": [
                "renewable_asset_analytics", "power_market_data",
                "generation_forecasting", "ppa_management",
                "curtailment_analysis", "grid_integration",
                "environmental_credit_tracking", "portfolio_optimization",
            ],
        },
        {
            "name": "Brainbox AI",
            "category": EnergyManagementCategory.BUILDING_EMS,
            "vendor": "brainbox_ai",
            "protocol": EnergyProtocol.REST_API,
            "connection_config": {"rate_limit": {"requests_per_minute": 60, "burst_limit": 10}},
            "capabilities": [
                "autonomous_hvac_optimization", "deep_learning_prediction",
                "energy_reduction", "carbon_footprint_reduction",
                "occupant_comfort_optimization", "predictive_control",
                "cloud_ai_analytics", "real_time_monitoring",
            ],
        },
    ]
    return [EnergyManagementConnector(**s) for s in specs]


DEFAULT_ENERGY_CONNECTORS = _build_defaults()


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class EnergyManagementRegistry:
    """Central registry that manages energy connector lifecycle — register,
    discover, execute actions, and perform health checks."""

    def __init__(self, load_defaults: bool = True):
        self._lock = threading.RLock()
        self._connectors: Dict[str, EnergyManagementConnector] = {}
        if load_defaults:
            for c in DEFAULT_ENERGY_CONNECTORS:
                self._connectors[c.vendor] = c

    # -- registration -------------------------------------------------------

    def register(self, connector: EnergyManagementConnector) -> Dict[str, Any]:
        with self._lock:
            self._connectors[connector.vendor] = connector
            return {"registered": True, "vendor": connector.vendor}

    def unregister(self, vendor: str) -> Dict[str, Any]:
        with self._lock:
            if vendor in self._connectors:
                del self._connectors[vendor]
                return {"unregistered": True, "vendor": vendor}
            return {"unregistered": False, "error": f"Unknown vendor: {vendor}"}

    # -- discovery ----------------------------------------------------------

    def discover(self, category: Optional[EnergyManagementCategory] = None) -> List[Dict[str, Any]]:
        with self._lock:
            connectors = list(self._connectors.values())
        if category is not None:
            connectors = [c for c in connectors if c.category == category]
        return [c.to_dict() for c in connectors]

    def get_connector(self, vendor: str) -> Optional[EnergyManagementConnector]:
        with self._lock:
            return self._connectors.get(vendor)

    def list_categories(self) -> List[str]:
        with self._lock:
            return sorted({c.category.value for c in self._connectors.values()})

    def list_vendors(self) -> List[str]:
        with self._lock:
            return sorted(self._connectors.keys())

    # -- execution ----------------------------------------------------------

    def execute(self, vendor: str, action_name: str,
                params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        connector = self.get_connector(vendor)
        if connector is None:
            return {"success": False, "error": f"Unknown vendor: {vendor}"}
        return connector.execute_action(action_name, params)

    # -- health -------------------------------------------------------------

    def health_check(self, vendor: str) -> Dict[str, Any]:
        connector = self.get_connector(vendor)
        if connector is None:
            return {"status": "unknown", "error": f"Unknown vendor: {vendor}"}
        return connector.health_check()

    def health_check_all(self) -> Dict[str, Dict[str, Any]]:
        with self._lock:
            connectors = dict(self._connectors)
        return {v: c.health_check() for v, c in connectors.items()}

    # -- stats --------------------------------------------------------------

    def statistics(self) -> Dict[str, Any]:
        with self._lock:
            total = len(self._connectors)
            enabled = sum(1 for c in self._connectors.values() if c.is_enabled())
            cats = {c.category.value for c in self._connectors.values()}
            return {
                "total_connectors": total,
                "enabled_connectors": enabled,
                "disabled_connectors": total - enabled,
                "categories": sorted(cats),
                "vendors": sorted(self._connectors.keys()),
            }


# ---------------------------------------------------------------------------
# Workflow Orchestrator — coordinate multi-platform energy workflows
# ---------------------------------------------------------------------------

class EnergyWorkflowOrchestrator:
    """Coordinate multi-platform energy management workflows."""

    def __init__(self, registry: EnergyManagementRegistry):
        self._registry = registry
        self._lock = threading.RLock()
        self._workflows: Dict[str, Dict[str, Any]] = {}

    def create_workflow(self, workflow_id: str, name: str,
                        description: str = "") -> Dict[str, Any]:
        with self._lock:
            wf = {
                "workflow_id": workflow_id,
                "name": name,
                "description": description,
                "steps": [],
                "edges": [],
                "created_at": time.time(),
                "status": "created",
            }
            self._workflows[workflow_id] = wf
            return dict(wf)

    def add_step(self, workflow_id: str, step_id: str,
                 vendor: str, action_name: str,
                 params: Optional[Dict[str, Any]] = None,
                 depends_on: Optional[List[str]] = None) -> Dict[str, Any]:
        with self._lock:
            wf = self._workflows.get(workflow_id)
            if wf is None:
                return {"success": False, "error": f"Unknown workflow: {workflow_id}"}

            connector = self._registry.get_connector(vendor)
            if connector is None:
                return {"success": False, "error": f"Unknown vendor: {vendor}"}

            if action_name not in connector.capabilities:
                return {"success": False, "error": f"Unsupported action: {action_name}"}

            step = {
                "step_id": step_id,
                "vendor": vendor,
                "action_name": action_name,
                "params": params or {},
                "depends_on": depends_on or [],
                "status": "pending",
            }
            wf["steps"].append(step)

            for dep in (depends_on or []):
                wf["edges"].append({"from": dep, "to": step_id})

            return {"success": True, "step": step}

    def execute_workflow(self, workflow_id: str) -> Dict[str, Any]:
        with self._lock:
            wf = self._workflows.get(workflow_id)
            if wf is None:
                return {"success": False, "error": f"Unknown workflow: {workflow_id}"}
            wf_copy = dict(wf)
            wf["status"] = "running"

        results: List[Dict[str, Any]] = []
        completed: set = set()
        steps = list(wf_copy["steps"])
        remaining = list(steps)
        max_iterations = len(steps) + 1
        iteration = 0

        while remaining and iteration < max_iterations:
            iteration += 1
            progress = False
            next_remaining = []
            for step in remaining:
                deps = set(step.get("depends_on", []))
                if deps.issubset(completed):
                    result = self._registry.execute(
                        step["vendor"], step["action_name"], step["params"]
                    )
                    result["step_id"] = step["step_id"]
                    results.append(result)
                    if result.get("success"):
                        completed.add(step["step_id"])
                        step["status"] = "completed"
                    else:
                        step["status"] = "failed"
                    progress = True
                else:
                    next_remaining.append(step)
            remaining = next_remaining
            if not progress:
                break

        for step in remaining:
            step["status"] = "skipped"
            results.append({"step_id": step["step_id"], "success": False, "error": "Unmet dependencies"})

        with self._lock:
            wf["status"] = "completed" if not remaining else "partial"

        all_ok = all(r.get("success") for r in results)
        return {
            "workflow_id": workflow_id,
            "success": all_ok,
            "results": results,
            "status": wf["status"],
        }

    def get_workflow(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            wf = self._workflows.get(workflow_id)
            return dict(wf) if wf else None

    def list_workflows(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [
                {"workflow_id": wid, "name": w["name"], "status": w["status"],
                 "step_count": len(w["steps"])}
                for wid, w in self._workflows.items()
            ]


# ---------------------------------------------------------------------------
# Module-level status helper
# ---------------------------------------------------------------------------

def get_status() -> Dict[str, Any]:
    """Return module-level status summary."""
    registry = EnergyManagementRegistry(load_defaults=True)
    stats = registry.statistics()
    return {
        "module": "energy_management_connectors",
        "status": "operational",
        "default_connectors": stats["total_connectors"],
        "categories": stats["categories"],
        "vendors": stats["vendors"],
        "timestamp": time.time(),
    }
