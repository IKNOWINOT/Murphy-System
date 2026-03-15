"""
Building Automation Connectors Module — Protocol connectors for building
automation systems (BACnet, Modbus, KNX, LonWorks, DALI, OPC UA).

Provides a unified interface for HVAC, lighting, fire safety, access control,
elevator, energy metering, and building envelope systems with thread-safe
registry, multi-protocol orchestration, and automatic capability mapping.
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

class BuildingAutomationProtocol(Enum):
    """Building automation protocol (Enum subclass)."""
    BACNET = "bacnet"
    MODBUS = "modbus"
    KNX = "knx"
    LONWORKS = "lonworks"
    DALI = "dali"
    OPC_UA = "opc_ua"


class BuildingSystemCategory(Enum):
    """Building system category (Enum subclass)."""
    HVAC = "hvac"
    LIGHTING = "lighting"
    FIRE_SAFETY = "fire_safety"
    ACCESS_CONTROL = "access_control"
    ELEVATOR = "elevator"
    ENERGY_METERING = "energy_metering"
    BUILDING_ENVELOPE = "building_envelope"


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

class BuildingAutomationConnector:
    """Base adapter for a building automation protocol integration."""

    def __init__(
        self,
        protocol: BuildingAutomationProtocol,
        vendor: str,
        capabilities: List[str],
        name: str = "",
        system_category: Optional[BuildingSystemCategory] = None,
        connection_config: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.name = name
        self.protocol = protocol
        self.system_category = system_category
        self.vendor = vendor
        self.connection_config = dict(connection_config or {})
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
        self._rate_limit = {
            "requests_per_minute": self.connection_config.get("requests_per_minute", 60),
            "burst_limit": self.connection_config.get("burst_limit", 10),
        }

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
                "protocol": self.protocol.value,
                "vendor": self.vendor,
                "status": self._status.value,
                "enabled": self._enabled,
                "request_count": self._request_count,
                "error_count": self._error_count,
                "timestamp": time.time(),
            }

    def execute_action(self, action_name: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute a named action against this connector.

        When credentials are configured and the appropriate protocol library
        is installed, dispatches to the real protocol client. Falls back to
        simulation when no credentials are available.
        """
        params = params or {}
        with self._lock:
            if not self._enabled:
                return self._action_result(action_name, False, error="Connector is disabled")

            if action_name not in self.capabilities:
                return self._action_result(action_name, False, error=f"Unsupported action: {action_name}")

            if not self._check_rate_limit():
                return self._action_result(action_name, False, error="Rate limit exceeded")

            self._request_count += 1

            # Attempt real protocol dispatch if credentials are available
            if self._credentials:
                real_result = self._dispatch_protocol(action_name, params)
                if real_result is not None:
                    return real_result

            # Simulated fallback
            result = self._action_result(
                action_name,
                True,
                data={
                    "action": action_name,
                    "protocol": self.protocol.value,
                    "vendor": self.vendor,
                    "params": params,
                    "simulated": True,
                },
            )
            capped_append(self._action_log, result)
            return result

    def _dispatch_protocol(self, action_name: str, params: dict) -> Optional[dict]:
        """Dispatch to the real protocol client.

        Returns a result dict if the dispatch succeeded (or failed with a real
        error), or None to signal that the caller should fall through to simulation.
        """
        try:
            from src.protocols import (
                MurphyBACnetClient,
                MurphyKNXClient,
                MurphyModbusClient,
                MurphyOPCUAClient,
            )
        except ImportError:
            return None

        ip = self._credentials.get("ip", "")
        port_str = self._credentials.get("port", "")

        client = None
        proto = self.protocol.value
        if proto == "bacnet" and MurphyBACnetClient is not None:
            port = int(port_str) if port_str else 47808
            client = MurphyBACnetClient(ip, port=port)
        elif proto == "modbus" and MurphyModbusClient is not None:
            port = int(port_str) if port_str else 502
            client = MurphyModbusClient(ip, port=port)
        elif proto in ("opc_ua", "opcua") and MurphyOPCUAClient is not None:
            url = self._credentials.get("url", f"opc.tcp://{ip}:{port_str or 4840}")
            client = MurphyOPCUAClient(url)
        elif proto == "knx" and MurphyKNXClient is not None:
            port = int(port_str) if port_str else 3671
            client = MurphyKNXClient(ip, port=port)

        if client is None:
            return None

        try:
            raw = client.execute(action_name, params)
            if raw.get("simulated"):
                # Protocol library not installed — fall through to simulation
                return None
            result = self._action_result(
                action_name,
                True,
                data={**raw, "protocol": self.protocol.value, "vendor": self.vendor},
            )
            capped_append(self._action_log, result)
            return result
        except Exception as exc:
            self._error_count += 1
            result = self._action_result(action_name, False, error=str(exc))
            capped_append(self._action_log, result)
            return result

    def list_available_actions(self) -> List[str]:
        """Return list of supported action names."""
        return list(self.capabilities)

    # -- configuration ------------------------------------------------------

    def configure(self, credentials: Dict[str, str]) -> Dict[str, Any]:
        """Apply credentials / connection parameters."""
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
                "protocol": self.protocol.value,
                "system_category": self.system_category.value if self.system_category else None,
                "vendor": self.vendor,
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
        if self._window_requests >= self._rate_limit["requests_per_minute"]:
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

def _build_defaults() -> List[BuildingAutomationConnector]:
    specs = [
        # ---- Protocol Connectors ----
        {
            "name": "BACnet Gateway",
            "protocol": BuildingAutomationProtocol.BACNET,
            "system_category": BuildingSystemCategory.HVAC,
            "vendor": "generic",
            "connection_config": {"transport": "ip", "port": 47808, "requests_per_minute": 300, "burst_limit": 50},
            "capabilities": [
                "read_property", "write_property", "subscribe_cov",
                "who_is_discovery", "trend_log_retrieval",
                "schedule_management", "alarm_monitoring",
            ],
        },
        {
            "name": "Modbus TCP/RTU",
            "protocol": BuildingAutomationProtocol.MODBUS,
            "system_category": BuildingSystemCategory.ENERGY_METERING,
            "vendor": "generic",
            "connection_config": {"transport": "tcp", "port": 502, "requests_per_minute": 500, "burst_limit": 80},
            "capabilities": [
                "read_holding_registers", "write_holding_registers",
                "read_input_registers", "read_coils",
                "write_coils", "device_identification",
            ],
        },
        {
            "name": "KNX IP",
            "protocol": BuildingAutomationProtocol.KNX,
            "system_category": BuildingSystemCategory.LIGHTING,
            "vendor": "generic",
            "connection_config": {"transport": "ip", "port": 3671, "requests_per_minute": 200, "burst_limit": 30},
            "capabilities": [
                "group_read", "group_write", "group_response",
                "device_programming", "ets_project_import",
                "scene_management",
            ],
        },
        {
            "name": "LonWorks/LON",
            "protocol": BuildingAutomationProtocol.LONWORKS,
            "system_category": BuildingSystemCategory.HVAC,
            "vendor": "generic",
            "connection_config": {"transport": "ip", "port": 1628, "requests_per_minute": 150, "burst_limit": 20},
            "capabilities": [
                "network_variable_read", "network_variable_write",
                "device_discovery", "configuration_management",
                "scheduler_control",
            ],
        },
        {
            "name": "DALI Gateway",
            "protocol": BuildingAutomationProtocol.DALI,
            "system_category": BuildingSystemCategory.LIGHTING,
            "vendor": "generic",
            "connection_config": {"transport": "serial", "baud_rate": 1200, "requests_per_minute": 100, "burst_limit": 15},
            "capabilities": [
                "lamp_control", "group_control", "scene_recall",
                "emergency_testing", "ballast_monitoring",
                "color_temperature_control",
            ],
        },
        {
            "name": "OPC UA Server",
            "protocol": BuildingAutomationProtocol.OPC_UA,
            "system_category": BuildingSystemCategory.HVAC,
            "vendor": "generic",
            "connection_config": {"transport": "tcp", "port": 4840, "requests_per_minute": 600, "burst_limit": 100},
            "capabilities": [
                "node_browse", "node_read", "node_write",
                "subscription_create", "method_call",
                "historical_data_access", "alarm_condition_monitoring",
            ],
        },
        # ---- Vendor Connectors ----
        {
            "name": "Johnson Controls Metasys",
            "protocol": BuildingAutomationProtocol.BACNET,
            "system_category": BuildingSystemCategory.HVAC,
            "vendor": "johnson_controls",
            "connection_config": {"transport": "ip", "port": 47808, "api_version": "v10", "requests_per_minute": 200, "burst_limit": 30},
            "capabilities": [
                "space_temperature_control", "air_handler_management",
                "chiller_plant_optimization", "vav_box_control",
                "energy_dashboard", "fault_detection_diagnostics",
                "setpoint_scheduling", "equipment_runtime_tracking",
            ],
        },
        {
            "name": "Honeywell Niagara/EBI",
            "protocol": BuildingAutomationProtocol.BACNET,
            "system_category": BuildingSystemCategory.HVAC,
            "vendor": "honeywell",
            "connection_config": {"transport": "ip", "port": 47808, "framework": "niagara4", "requests_per_minute": 200, "burst_limit": 30},
            "capabilities": [
                "niagara_station_management", "webs_n4_integration",
                "ebi_alarm_management", "comfort_control",
                "energy_optimization", "predictive_maintenance",
                "occupancy_analytics", "equipment_scheduling",
            ],
        },
        {
            "name": "Siemens Desigo CC",
            "protocol": BuildingAutomationProtocol.BACNET,
            "system_category": BuildingSystemCategory.HVAC,
            "vendor": "siemens",
            "connection_config": {"transport": "ip", "port": 47808, "platform": "desigo_cc", "requests_per_minute": 200, "burst_limit": 30},
            "capabilities": [
                "desigo_room_automation", "building_performance_monitoring",
                "fire_safety_integration", "access_control_integration",
                "energy_management", "comfort_optimization",
                "fault_rule_engine", "sustainability_reporting",
            ],
        },
        {
            "name": "Alerton Ascent",
            "protocol": BuildingAutomationProtocol.BACNET,
            "system_category": BuildingSystemCategory.HVAC,
            "vendor": "alerton",
            "connection_config": {"transport": "ip", "port": 47808, "platform": "ascent", "requests_per_minute": 150, "burst_limit": 20},
            "capabilities": [
                "bac_talk_integration", "ascent_control_engine",
                "microset_controller_management", "vlc_controller_programming",
                "energy_analytics", "trend_analysis",
                "alarm_management", "remote_monitoring",
            ],
        },
        # ---- Extended Vendor Connectors ----
        {
            "name": "Trane Tracer SC/ES",
            "protocol": BuildingAutomationProtocol.BACNET,
            "system_category": BuildingSystemCategory.HVAC,
            "vendor": "trane",
            "connection_config": {"transport": "ip", "port": 47808, "platform": "tracer_sc", "requests_per_minute": 180, "burst_limit": 25},
            "capabilities": [
                "chiller_plant_management", "air_handler_control",
                "variable_frequency_drive", "energy_optimization",
                "fault_detection_diagnostics", "comfort_management",
                "equipment_scheduling", "trend_logging",
            ],
        },
        {
            "name": "Carrier i-Vu/Automated Logic WebCTRL",
            "protocol": BuildingAutomationProtocol.BACNET,
            "system_category": BuildingSystemCategory.HVAC,
            "vendor": "carrier_automated_logic",
            "connection_config": {"transport": "ip", "port": 47808, "platform": "webctrl", "requests_per_minute": 180, "burst_limit": 25},
            "capabilities": [
                "webctrl_server_management", "environmental_index_control",
                "energy_reports", "equipment_scheduling",
                "alarm_console", "trend_viewer",
                "optimal_start_stop", "demand_limiting",
            ],
        },
        {
            "name": "Schneider Electric EcoStruxure BMS",
            "protocol": BuildingAutomationProtocol.BACNET,
            "system_category": BuildingSystemCategory.HVAC,
            "vendor": "schneider_electric",
            "connection_config": {"transport": "ip", "port": 47808, "platform": "ecostruxure_bms", "requests_per_minute": 200, "burst_limit": 30},
            "capabilities": [
                "smartx_controller_management", "room_automation",
                "energy_management", "fire_safety_integration",
                "access_control_integration", "building_analytics",
                "sustainability_reporting", "asset_management",
            ],
        },
        {
            "name": "ABB HVAC Controls",
            "protocol": BuildingAutomationProtocol.BACNET,
            "system_category": BuildingSystemCategory.HVAC,
            "vendor": "abb",
            "connection_config": {"transport": "ip", "port": 47808, "platform": "ability_bms", "requests_per_minute": 150, "burst_limit": 20},
            "capabilities": [
                "variable_speed_drives", "motor_control",
                "energy_efficiency_monitoring", "predictive_maintenance",
                "building_energy_management", "power_quality",
                "remote_monitoring", "asset_health",
            ],
        },
        {
            "name": "Delta Controls enteliWEB",
            "protocol": BuildingAutomationProtocol.BACNET,
            "system_category": BuildingSystemCategory.HVAC,
            "vendor": "delta_controls",
            "connection_config": {"transport": "ip", "port": 47808, "platform": "enteliweb", "requests_per_minute": 150, "burst_limit": 20},
            "capabilities": [
                "enteliweb_management", "o3_sensor_integration",
                "orca_controller_programming", "energy_dashboards",
                "trend_analysis", "alarm_management",
                "scheduling", "remote_access",
            ],
        },
        {
            "name": "Distech Controls ECLYPSE",
            "protocol": BuildingAutomationProtocol.BACNET,
            "system_category": BuildingSystemCategory.HVAC,
            "vendor": "distech",
            "connection_config": {"transport": "ip", "port": 47808, "platform": "eclypse", "requests_per_minute": 150, "burst_limit": 20},
            "capabilities": [
                "eclypse_connected_controller", "envysion_web_interface",
                "allure_unitouch_integration", "room_automation",
                "energy_optimization", "iot_edge_computing",
                "cloud_analytics", "scheduling",
            ],
        },
    ]
    return [BuildingAutomationConnector(**s) for s in specs]


DEFAULT_BUILDING_AUTOMATION_CONNECTORS = _build_defaults()


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class BuildingAutomationRegistry:
    """Central registry that manages building automation connector lifecycle —
    register, discover, execute actions, and perform health checks."""

    def __init__(self, load_defaults: bool = True):
        self._lock = threading.RLock()
        self._connectors: Dict[str, BuildingAutomationConnector] = {}
        if load_defaults:
            for c in DEFAULT_BUILDING_AUTOMATION_CONNECTORS:
                key = f"{c.vendor}_{c.protocol.value}"
                self._connectors[key] = c

    # -- registration -------------------------------------------------------

    def register(self, connector: BuildingAutomationConnector) -> Dict[str, Any]:
        """Register a connector in the registry."""
        with self._lock:
            key = f"{connector.vendor}_{connector.protocol.value}"
            self._connectors[key] = connector
            return {"registered": True, "key": key}

    def unregister(self, key: str) -> Dict[str, Any]:
        """Remove a connector from the registry."""
        with self._lock:
            if key in self._connectors:
                del self._connectors[key]
                return {"unregistered": True, "key": key}
            return {"unregistered": False, "error": f"Unknown connector: {key}"}

    # -- discovery ----------------------------------------------------------

    def discover(
        self,
        protocol: Optional[BuildingAutomationProtocol] = None,
        system_category: Optional[BuildingSystemCategory] = None,
    ) -> List[Dict[str, Any]]:
        """Discover connectors, optionally filtered by protocol or category."""
        with self._lock:
            connectors = list(self._connectors.values())
        if protocol is not None:
            connectors = [c for c in connectors if c.protocol == protocol]
        if system_category is not None:
            connectors = [c for c in connectors if c.system_category == system_category]
        return [c.to_dict() for c in connectors]

    def get_connector(self, key: str) -> Optional[BuildingAutomationConnector]:
        """Retrieve a connector by its registry key."""
        with self._lock:
            return self._connectors.get(key)

    def list_protocols(self) -> List[str]:
        """Return sorted list of unique protocol values in the registry."""
        with self._lock:
            return sorted({c.protocol.value for c in self._connectors.values()})

    def list_vendors(self) -> List[str]:
        """Return sorted list of unique vendor identifiers in the registry."""
        with self._lock:
            return sorted({c.vendor for c in self._connectors.values()})

    # -- execution ----------------------------------------------------------

    def execute(self, key: str, action_name: str,
                params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute an action on a registered connector."""
        connector = self.get_connector(key)
        if connector is None:
            return {"success": False, "error": f"Unknown connector: {key}"}
        return connector.execute_action(action_name, params)

    # -- health -------------------------------------------------------------

    def health_check(self, key: str) -> Dict[str, Any]:
        """Health-check a single connector."""
        connector = self.get_connector(key)
        if connector is None:
            return {"status": "unknown", "error": f"Unknown connector: {key}"}
        return connector.health_check()

    def health_check_all(self) -> Dict[str, Dict[str, Any]]:
        """Health-check every registered connector."""
        with self._lock:
            connectors = dict(self._connectors)
        return {k: c.health_check() for k, c in connectors.items()}

    # -- stats --------------------------------------------------------------

    def statistics(self) -> Dict[str, Any]:
        """Return aggregate statistics for the registry."""
        with self._lock:
            total = len(self._connectors)
            enabled = sum(1 for c in self._connectors.values() if c.is_enabled())
            protocols = {c.protocol.value for c in self._connectors.values()}
            vendors = {c.vendor for c in self._connectors.values()}
            return {
                "total_connectors": total,
                "enabled_connectors": enabled,
                "disabled_connectors": total - enabled,
                "protocols": sorted(protocols),
                "vendors": sorted(vendors),
                "keys": sorted(self._connectors.keys()),
            }


# ---------------------------------------------------------------------------
# Orchestrator — coordinate multi-protocol workflows
# ---------------------------------------------------------------------------

class BuildingAutomationOrchestrator:
    """Coordinate multi-protocol building automation workflows as ordered
    sequences of connector actions."""

    def __init__(self, registry: BuildingAutomationRegistry):
        self._registry = registry
        self._lock = threading.RLock()
        self._sequences: Dict[str, Dict[str, Any]] = {}

    def create_sequence(self, sequence_id: str, name: str,
                        description: str = "") -> Dict[str, Any]:
        """Create a new execution sequence."""
        with self._lock:
            seq = {
                "sequence_id": sequence_id,
                "name": name,
                "description": description,
                "steps": [],
                "created_at": time.time(),
                "status": "created",
            }
            self._sequences[sequence_id] = seq
            return dict(seq)

    def add_step(self, sequence_id: str, step_id: str,
                 connector_key: str, action_name: str,
                 params: Optional[Dict[str, Any]] = None,
                 depends_on: Optional[List[str]] = None) -> Dict[str, Any]:
        """Add a step to an existing sequence."""
        with self._lock:
            seq = self._sequences.get(sequence_id)
            if seq is None:
                return {"success": False, "error": f"Unknown sequence: {sequence_id}"}

            connector = self._registry.get_connector(connector_key)
            if connector is None:
                return {"success": False, "error": f"Unknown connector: {connector_key}"}

            if action_name not in connector.capabilities:
                return {"success": False, "error": f"Unsupported action: {action_name}"}

            step = {
                "step_id": step_id,
                "connector_key": connector_key,
                "action_name": action_name,
                "params": params or {},
                "depends_on": depends_on or [],
                "status": "pending",
            }
            seq["steps"].append(step)

            return {"success": True, "step": step}

    def execute_sequence(self, sequence_id: str) -> Dict[str, Any]:
        """Execute all steps in a sequence, respecting dependency order."""
        with self._lock:
            seq = self._sequences.get(sequence_id)
            if seq is None:
                return {"success": False, "error": f"Unknown sequence: {sequence_id}"}
            seq_copy = dict(seq)
            seq["status"] = "running"

        results: List[Dict[str, Any]] = []
        completed: set = set()
        steps = list(seq_copy["steps"])
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
                        step["connector_key"], step["action_name"], step["params"]
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
            seq["status"] = "completed" if not remaining else "partial"

        all_ok = all(r.get("success") for r in results)
        return {
            "sequence_id": sequence_id,
            "success": all_ok,
            "results": results,
            "status": seq["status"],
        }

    def get_sequence(self, sequence_id: str) -> Optional[Dict[str, Any]]:
        """Return a copy of the sequence definition."""
        with self._lock:
            seq = self._sequences.get(sequence_id)
            return dict(seq) if seq else None

    def list_sequences(self) -> List[Dict[str, Any]]:
        """Return summary of all sequences."""
        with self._lock:
            return [
                {"sequence_id": sid, "name": s["name"], "status": s["status"],
                 "step_count": len(s["steps"])}
                for sid, s in self._sequences.items()
            ]


# ---------------------------------------------------------------------------
# Module-level status helper
# ---------------------------------------------------------------------------

def get_status() -> Dict[str, Any]:
    """Return module-level status information."""
    registry = BuildingAutomationRegistry(load_defaults=True)
    stats = registry.statistics()
    return {
        "module": "building_automation_connectors",
        "version": "1.0.0",
        "protocols": [p.value for p in BuildingAutomationProtocol],
        "system_categories": [c.value for c in BuildingSystemCategory],
        "default_connectors": stats["total_connectors"],
        "enabled_connectors": stats["enabled_connectors"],
        "vendors": stats["vendors"],
        "status": "operational",
        "timestamp": time.time(),
    }
