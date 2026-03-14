"""
Manufacturing Automation Standards Module — Protocol and standard connectors
for industrial manufacturing automation within the Murphy System.

Provides a unified interface for ISA-95, OPC UA, MTConnect, PackML,
MQTT/Sparkplug B, and IEC 61131 manufacturing protocols with thread-safe
registry, ISA-95 layer-aware workflow orchestration, and automatic
capability mapping.
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

class ManufacturingStandard(Enum):
    """Manufacturing standard (Enum subclass)."""
    ISA_95 = "isa_95"
    OPC_UA = "opc_ua"
    MTCONNECT = "mtconnect"
    PACKML = "packml"
    MQTT_SPARKPLUG_B = "mqtt_sparkplug_b"
    IEC_61131 = "iec_61131"


class ManufacturingLayer(Enum):
    """Manufacturing layer (Enum subclass)."""
    ENTERPRISE = "L4"
    SITE_OPERATIONS = "L3"
    SUPERVISORY = "L2"
    DIRECT_CONTROL = "L1"
    FIELD_DEVICE = "L0"


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

class ManufacturingConnector:
    """Base adapter for a manufacturing automation protocol connector."""

    def __init__(
        self,
        name: str,
        standard: ManufacturingStandard,
        layer: ManufacturingLayer,
        protocol_version: str,
        connection_config: Dict[str, Any],
        capabilities: List[str],
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.name = name
        self.standard = standard
        self.layer = layer
        self.protocol_version = protocol_version
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
                "standard": self.standard.value,
                "layer": self.layer.value,
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
                    "standard": self.standard.value,
                    "layer": self.layer.value,
                    "params": params,
                    "simulated": True,
                },
            )
            capped_append(self._action_log, result)
            return result

    def list_available_actions(self) -> List[str]:
        """Return list of supported action names."""
        return list(self.capabilities)

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
                "standard": self.standard.value,
                "layer": self.layer.value,
                "protocol_version": self.protocol_version,
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
        if self._window_requests >= self.connection_config.get("requests_per_minute", 60):
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

def _build_defaults() -> List[ManufacturingConnector]:
    specs = [
        {
            "name": "ISA-95 Integration",
            "standard": ManufacturingStandard.ISA_95,
            "layer": ManufacturingLayer.ENTERPRISE,
            "protocol_version": "6.0",
            "connection_config": {"requests_per_minute": 120, "burst_limit": 20},
            "capabilities": [
                "production_order_management", "material_tracking",
                "quality_management", "maintenance_management",
                "inventory_operations", "production_scheduling",
                "performance_analysis", "resource_management",
            ],
        },
        {
            "name": "OPC UA Manufacturing",
            "standard": ManufacturingStandard.OPC_UA,
            "layer": ManufacturingLayer.SUPERVISORY,
            "protocol_version": "1.05",
            "connection_config": {"requests_per_minute": 500, "burst_limit": 100},
            "capabilities": [
                "node_browse", "node_read", "node_write",
                "subscription_management", "method_invocation",
                "alarm_condition", "historical_access",
                "companion_spec_support", "pub_sub_messaging",
            ],
        },
        {
            "name": "MTConnect Agent",
            "standard": ManufacturingStandard.MTCONNECT,
            "layer": ManufacturingLayer.DIRECT_CONTROL,
            "protocol_version": "2.2",
            "connection_config": {"requests_per_minute": 300, "burst_limit": 60},
            "capabilities": [
                "device_stream", "current_data", "sample_data",
                "asset_management", "condition_monitoring",
                "component_stream", "interface_management",
                "composition_tracking",
            ],
        },
        {
            "name": "PackML State Machine",
            "standard": ManufacturingStandard.PACKML,
            "layer": ManufacturingLayer.DIRECT_CONTROL,
            "protocol_version": "5.0",
            "connection_config": {"requests_per_minute": 200, "burst_limit": 40},
            "capabilities": [
                "state_machine_control", "mode_management",
                "unit_control", "pack_tag_management",
                "status_reporting", "alarm_management",
                "counter_management", "parameter_management",
            ],
        },
        {
            "name": "MQTT/Sparkplug B",
            "standard": ManufacturingStandard.MQTT_SPARKPLUG_B,
            "layer": ManufacturingLayer.FIELD_DEVICE,
            "protocol_version": "3.0",
            "connection_config": {"requests_per_minute": 1000, "burst_limit": 200},
            "capabilities": [
                "device_birth_publish", "device_data_publish",
                "device_death_publish", "node_birth_publish",
                "node_command", "metric_reporting",
                "state_management", "store_forward",
            ],
        },
        {
            "name": "IEC 61131 PLC",
            "standard": ManufacturingStandard.IEC_61131,
            "layer": ManufacturingLayer.DIRECT_CONTROL,
            "protocol_version": "3.0",
            "connection_config": {"requests_per_minute": 150, "burst_limit": 30},
            "capabilities": [
                "structured_text_execution", "ladder_logic_execution",
                "function_block_execution", "sequential_function_chart",
                "instruction_list_execution", "variable_management",
                "io_configuration", "program_download",
            ],
        },
    ]
    return [ManufacturingConnector(**s) for s in specs]


DEFAULT_MANUFACTURING_CONNECTORS = _build_defaults()


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class ManufacturingAutomationRegistry:
    """Central registry that manages manufacturing connector lifecycle —
    register, discover, execute actions, and perform health checks."""

    def __init__(self, load_defaults: bool = True):
        self._lock = threading.RLock()
        self._connectors: Dict[str, ManufacturingConnector] = {}
        if load_defaults:
            for c in DEFAULT_MANUFACTURING_CONNECTORS:
                self._connectors[c.standard.value] = c

    # -- registration -------------------------------------------------------

    def register(self, connector: ManufacturingConnector) -> Dict[str, Any]:
        with self._lock:
            self._connectors[connector.standard.value] = connector
            return {"registered": True, "standard": connector.standard.value}

    def unregister(self, standard_key: str) -> Dict[str, Any]:
        with self._lock:
            if standard_key in self._connectors:
                del self._connectors[standard_key]
                return {"unregistered": True, "standard": standard_key}
            return {"unregistered": False, "error": f"Unknown standard: {standard_key}"}

    # -- discovery ----------------------------------------------------------

    def discover(self, layer: Optional[ManufacturingLayer] = None) -> List[Dict[str, Any]]:
        with self._lock:
            connectors = list(self._connectors.values())
        if layer is not None:
            connectors = [c for c in connectors if c.layer == layer]
        return [c.to_dict() for c in connectors]

    def get_connector(self, standard_key: str) -> Optional[ManufacturingConnector]:
        with self._lock:
            return self._connectors.get(standard_key)

    def list_standards(self) -> List[str]:
        with self._lock:
            return sorted({c.standard.value for c in self._connectors.values()})

    def list_layers(self) -> List[str]:
        with self._lock:
            return sorted({c.layer.value for c in self._connectors.values()})

    # -- execution ----------------------------------------------------------

    def execute(self, standard_key: str, action_name: str,
                params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        connector = self.get_connector(standard_key)
        if connector is None:
            return {"success": False, "error": f"Unknown standard: {standard_key}"}
        return connector.execute_action(action_name, params)

    # -- health -------------------------------------------------------------

    def health_check(self, standard_key: str) -> Dict[str, Any]:
        connector = self.get_connector(standard_key)
        if connector is None:
            return {"status": "unknown", "error": f"Unknown standard: {standard_key}"}
        return connector.health_check()

    def health_check_all(self) -> Dict[str, Dict[str, Any]]:
        with self._lock:
            connectors = dict(self._connectors)
        return {key: c.health_check() for key, c in connectors.items()}

    # -- stats --------------------------------------------------------------

    def statistics(self) -> Dict[str, Any]:
        with self._lock:
            total = len(self._connectors)
            enabled = sum(1 for c in self._connectors.values() if c.is_enabled())
            standards = {c.standard.value for c in self._connectors.values()}
            layers = {c.layer.value for c in self._connectors.values()}
            return {
                "total_connectors": total,
                "enabled_connectors": enabled,
                "disabled_connectors": total - enabled,
                "standards": sorted(standards),
                "layers": sorted(layers),
            }


# ---------------------------------------------------------------------------
# Workflow Binder — ISA-95 layer-aware workflow orchestration
# ---------------------------------------------------------------------------

class ManufacturingWorkflowBinder:
    """Bind manufacturing connectors as step handlers in an ISA-95
    layer-aware workflow."""

    def __init__(self, registry: ManufacturingAutomationRegistry):
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
                 standard_key: str, action_name: str,
                 params: Optional[Dict[str, Any]] = None,
                 depends_on: Optional[List[str]] = None) -> Dict[str, Any]:
        with self._lock:
            wf = self._workflows.get(workflow_id)
            if wf is None:
                return {"success": False, "error": f"Unknown workflow: {workflow_id}"}

            connector = self._registry.get_connector(standard_key)
            if connector is None:
                return {"success": False, "error": f"Unknown standard: {standard_key}"}

            if action_name not in connector.capabilities:
                return {"success": False, "error": f"Unsupported action: {action_name}"}

            step = {
                "step_id": step_id,
                "standard_key": standard_key,
                "layer": connector.layer.value,
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
                        step["standard_key"], step["action_name"], step["params"]
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
    registry = ManufacturingAutomationRegistry(load_defaults=True)
    stats = registry.statistics()
    health = registry.health_check_all()
    return {
        "module": "manufacturing_automation_standards",
        "version": "1.0.0",
        "statistics": stats,
        "health": health,
        "timestamp": time.time(),
    }
