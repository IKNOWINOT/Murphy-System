"""
Additive Manufacturing / 3D Printing Connectors Module — Protocol connectors
for all major 3D printing and additive manufacturing automation systems.

Provides a unified interface for FDM/FFF, SLA/DLP, SLS/SLM, PolyJet/MJF,
DMLS/EBM, binder jetting, and WAAM systems with thread-safe registry,
ISA-95 layer-aware workflow orchestration, OPC UA companion-spec support,
and automatic capability mapping.

Supported Protocols / Standards:
  - OPC UA (Companion Spec for AM — OPC 40564)
  - MTConnect (Additive device model)
  - MQTT / Sparkplug B (real-time telemetry)
  - 3MF / AMF (build-file interchange)
  - REST / gRPC (vendor cloud APIs — Stratasys GrabCAD, Ultimaker Digital Factory,
    HP 3D Command Center, Markforged Eiger, EOS EOSTATE, etc.)
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

class AdditiveProcess(Enum):
    """ISO/ASTM 52900 additive-manufacturing process categories."""
    FDM_FFF = "fdm_fff"                     # Fused Deposition Modeling / Fused Filament Fabrication
    SLA_DLP = "sla_dlp"                     # Stereolithography / Digital Light Processing
    SLS = "sls"                             # Selective Laser Sintering (polymers)
    SLM_DMLS = "slm_dmls"                   # Selective Laser Melting / Direct Metal Laser Sintering
    EBM = "ebm"                             # Electron Beam Melting
    POLYJET_MJF = "polyjet_mjf"             # PolyJet / Multi Jet Fusion
    BINDER_JETTING = "binder_jetting"       # Binder Jetting (sand, metal, full-color)
    DED_WAAM = "ded_waam"                   # Directed Energy Deposition / Wire Arc AM
    CONTINUOUS_FIBER = "continuous_fiber"    # Continuous fiber reinforcement (Markforged, etc.)


class AMProtocol(Enum):
    """Communication protocols used by AM systems."""
    OPC_UA_AM = "opc_ua_am"                 # OPC 40564 AM companion spec
    MTCONNECT = "mtconnect"                 # MTConnect additive device model
    MQTT_SPARKPLUG_B = "mqtt_sparkplug_b"   # MQTT/Sparkplug B telemetry
    REST_API = "rest_api"                   # Vendor REST APIs
    GRPC = "grpc"                           # gRPC streaming APIs
    THREE_MF = "3mf"                        # 3MF build-file interchange
    AMF = "amf"                             # Additive Manufacturing File Format
    GCODE_SERIAL = "gcode_serial"              # Serial / G-code CLI (Marlin, Klipper, etc.)


class AMSystemLayer(Enum):
    """ISA-95 layer mapping for AM systems."""
    ENTERPRISE = "L4"           # ERP / PLM / MES order management
    SITE_OPERATIONS = "L3"      # Build preparation, scheduling, fleet management
    SUPERVISORY = "L2"          # Printer dashboard / monitoring / job control
    DIRECT_CONTROL = "L1"       # Motion controller, laser/heater PID
    FIELD_DEVICE = "L0"         # Sensors, actuators, material feeders


class ConnectorStatus(Enum):
    """Connector status (Enum subclass)."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"
    DISABLED = "disabled"


class MaterialClass(Enum):
    """High-level material categories for AM."""
    THERMOPLASTIC = "thermoplastic"
    PHOTOPOLYMER = "photopolymer"
    METAL_POWDER = "metal_powder"
    METAL_WIRE = "metal_wire"
    CERAMIC = "ceramic"
    SAND = "sand"
    COMPOSITE = "composite"
    WAX = "wax"
    BIOINK = "bioink"


# ---------------------------------------------------------------------------
# Base Connector
# ---------------------------------------------------------------------------

class AMConnector:
    """Adapter for a single additive-manufacturing system or fleet endpoint."""

    def __init__(
        self,
        name: str,
        vendor: str,
        process: AdditiveProcess,
        protocol: AMProtocol,
        layer: AMSystemLayer,
        protocol_version: str,
        connection_config: Dict[str, Any],
        capabilities: List[str],
        supported_materials: Optional[List[MaterialClass]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.name = name
        self.vendor = vendor
        self.process = process
        self.protocol = protocol
        self.layer = layer
        self.protocol_version = protocol_version
        self.connection_config = dict(connection_config)
        self.capabilities = list(capabilities)
        self.supported_materials = list(supported_materials) if supported_materials else []
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
                "process": self.process.value,
                "protocol": self.protocol.value,
                "layer": self.layer.value,
                "status": self._status.value,
                "enabled": self._enabled,
                "request_count": self._request_count,
                "error_count": self._error_count,
                "timestamp": time.time(),
            }

    def execute_action(self, action_name: str,
                       params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        params = params or {}
        with self._lock:
            if not self._enabled:
                return self._result(action_name, False, error="Connector is disabled")
            if action_name not in self.capabilities:
                return self._result(action_name, False,
                                    error=f"Unsupported action: {action_name}")
            if not self._check_rate_limit():
                return self._result(action_name, False, error="Rate limit exceeded")

            self._request_count += 1
            result = self._result(action_name, True, data={
                "action": action_name,
                "vendor": self.vendor,
                "process": self.process.value,
                "protocol": self.protocol.value,
                "layer": self.layer.value,
                "params": params,
                "simulated": True,
            })
            capped_append(self._action_log, result)
            return result

    def list_available_actions(self) -> List[str]:
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
                "vendor": self.vendor,
                "process": self.process.value,
                "protocol": self.protocol.value,
                "layer": self.layer.value,
                "protocol_version": self.protocol_version,
                "connection_config": self.connection_config,
                "capabilities": self.capabilities,
                "supported_materials": [m.value for m in self.supported_materials],
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

    def _result(self, action: str, success: bool,
                data: Any = None, error: Optional[str] = None) -> Dict[str, Any]:
        return {
            "action": action,
            "connector": self.name,
            "success": success,
            "data": data,
            "error": error,
            "timestamp": time.time(),
        }


# ---------------------------------------------------------------------------
# Default connector catalogue
# ---------------------------------------------------------------------------

def _build_defaults() -> List[AMConnector]:
    specs: List[Dict[str, Any]] = [
        # ---- FDM / FFF ---------------------------------------------------
        {
            "name": "Stratasys F-Series (GrabCAD Print)",
            "vendor": "stratasys",
            "process": AdditiveProcess.FDM_FFF,
            "protocol": AMProtocol.REST_API,
            "layer": AMSystemLayer.SITE_OPERATIONS,
            "protocol_version": "2.0",
            "connection_config": {"requests_per_minute": 120, "burst_limit": 20},
            "capabilities": [
                "submit_build_job", "cancel_job", "monitor_progress",
                "material_inventory", "nozzle_calibration",
                "fleet_status", "queue_management", "maintenance_alerts",
                "build_plate_level", "filament_change",
            ],
            "supported_materials": [MaterialClass.THERMOPLASTIC, MaterialClass.COMPOSITE],
        },
        {
            "name": "Ultimaker Digital Factory",
            "vendor": "ultimaker",
            "process": AdditiveProcess.FDM_FFF,
            "protocol": AMProtocol.REST_API,
            "layer": AMSystemLayer.SITE_OPERATIONS,
            "protocol_version": "7.0",
            "connection_config": {"requests_per_minute": 200, "burst_limit": 40},
            "capabilities": [
                "submit_build_job", "cancel_job", "monitor_progress",
                "material_inventory", "fleet_management",
                "printer_grouping", "digital_library", "print_profile_management",
                "remote_camera_stream", "usage_analytics",
            ],
            "supported_materials": [MaterialClass.THERMOPLASTIC, MaterialClass.COMPOSITE],
        },
        {
            "name": "Prusa Connect",
            "vendor": "prusa",
            "process": AdditiveProcess.FDM_FFF,
            "protocol": AMProtocol.REST_API,
            "layer": AMSystemLayer.SUPERVISORY,
            "protocol_version": "1.0",
            "connection_config": {"requests_per_minute": 100, "burst_limit": 20},
            "capabilities": [
                "submit_gcode", "cancel_job", "monitor_progress",
                "printer_telemetry", "filament_sensor",
                "remote_camera_stream", "fleet_overview",
                "crash_detection", "power_panic_recovery",
            ],
            "supported_materials": [MaterialClass.THERMOPLASTIC],
        },
        {
            "name": "Klipper / Moonraker API",
            "vendor": "klipper_community",
            "process": AdditiveProcess.FDM_FFF,
            "protocol": AMProtocol.REST_API,
            "layer": AMSystemLayer.DIRECT_CONTROL,
            "protocol_version": "0.8",
            "connection_config": {"requests_per_minute": 300, "burst_limit": 60},
            "capabilities": [
                "submit_gcode", "cancel_job", "monitor_progress",
                "pressure_advance_tuning", "input_shaper_calibration",
                "heater_control", "fan_control", "probe_calibration",
                "firmware_restart", "macro_execution",
            ],
            "supported_materials": [MaterialClass.THERMOPLASTIC],
        },
        {
            "name": "OctoPrint API",
            "vendor": "octoprint_community",
            "process": AdditiveProcess.FDM_FFF,
            "protocol": AMProtocol.REST_API,
            "layer": AMSystemLayer.SUPERVISORY,
            "protocol_version": "1.10",
            "connection_config": {"requests_per_minute": 120, "burst_limit": 30},
            "capabilities": [
                "submit_gcode", "cancel_job", "monitor_progress",
                "webcam_stream", "plugin_management",
                "temperature_control", "gcode_analysis",
                "timelapse_capture", "sd_card_management",
            ],
            "supported_materials": [MaterialClass.THERMOPLASTIC],
        },

        # ---- SLA / DLP ---------------------------------------------------
        {
            "name": "Formlabs Dashboard (PreForm)",
            "vendor": "formlabs",
            "process": AdditiveProcess.SLA_DLP,
            "protocol": AMProtocol.REST_API,
            "layer": AMSystemLayer.SITE_OPERATIONS,
            "protocol_version": "2.0",
            "connection_config": {"requests_per_minute": 100, "burst_limit": 20},
            "capabilities": [
                "submit_build_job", "cancel_job", "monitor_progress",
                "resin_inventory", "fleet_management",
                "wash_cure_scheduling", "print_quality_analytics",
                "cartridge_tracking", "tank_lifecycle",
            ],
            "supported_materials": [MaterialClass.PHOTOPOLYMER, MaterialClass.WAX],
        },

        # ---- SLS (Polymer) -----------------------------------------------
        {
            "name": "HP 3D Command Center (MJF)",
            "vendor": "hp",
            "process": AdditiveProcess.POLYJET_MJF,
            "protocol": AMProtocol.REST_API,
            "layer": AMSystemLayer.SITE_OPERATIONS,
            "protocol_version": "5.0",
            "connection_config": {"requests_per_minute": 150, "burst_limit": 30},
            "capabilities": [
                "submit_build_job", "cancel_job", "monitor_progress",
                "material_inventory", "fleet_management",
                "build_unit_status", "processing_station_control",
                "part_quality_analytics", "thermal_imaging",
                "predictive_maintenance",
            ],
            "supported_materials": [MaterialClass.THERMOPLASTIC],
        },
        {
            "name": "EOS EOSTATE (SLS/SLM)",
            "vendor": "eos",
            "process": AdditiveProcess.SLS,
            "protocol": AMProtocol.OPC_UA_AM,
            "layer": AMSystemLayer.SUPERVISORY,
            "protocol_version": "1.0",
            "connection_config": {"requests_per_minute": 200, "burst_limit": 40},
            "capabilities": [
                "submit_build_job", "cancel_job", "monitor_progress",
                "melt_pool_monitoring", "powder_bed_analysis",
                "laser_power_telemetry", "quality_assurance",
                "machine_diagnostics", "exposure_strategy",
            ],
            "supported_materials": [MaterialClass.THERMOPLASTIC, MaterialClass.METAL_POWDER],
        },

        # ---- Metal AM (DMLS / SLM / EBM) --------------------------------
        {
            "name": "SLM Solutions Build Processor",
            "vendor": "slm_solutions",
            "process": AdditiveProcess.SLM_DMLS,
            "protocol": AMProtocol.OPC_UA_AM,
            "layer": AMSystemLayer.SUPERVISORY,
            "protocol_version": "1.0",
            "connection_config": {"requests_per_minute": 100, "burst_limit": 20},
            "capabilities": [
                "submit_build_job", "cancel_job", "monitor_progress",
                "multi_laser_control", "melt_pool_monitoring",
                "powder_management", "gas_flow_control",
                "build_plate_preheat", "quality_metrics",
            ],
            "supported_materials": [MaterialClass.METAL_POWDER],
        },
        {
            "name": "GE Additive Arcam EBM",
            "vendor": "ge_additive",
            "process": AdditiveProcess.EBM,
            "protocol": AMProtocol.OPC_UA_AM,
            "layer": AMSystemLayer.SUPERVISORY,
            "protocol_version": "1.0",
            "connection_config": {"requests_per_minute": 80, "burst_limit": 15},
            "capabilities": [
                "submit_build_job", "cancel_job", "monitor_progress",
                "electron_beam_control", "vacuum_system_monitor",
                "powder_hopper_management", "preheat_control",
                "build_chamber_atmosphere", "in_situ_quality",
            ],
            "supported_materials": [MaterialClass.METAL_POWDER],
        },

        # ---- Continuous Fiber Reinforcement ------------------------------
        {
            "name": "Markforged Eiger",
            "vendor": "markforged",
            "process": AdditiveProcess.CONTINUOUS_FIBER,
            "protocol": AMProtocol.REST_API,
            "layer": AMSystemLayer.SITE_OPERATIONS,
            "protocol_version": "3.0",
            "connection_config": {"requests_per_minute": 120, "burst_limit": 25},
            "capabilities": [
                "submit_build_job", "cancel_job", "monitor_progress",
                "fiber_routing_preview", "material_inventory",
                "fleet_management", "inspection_reporting",
                "sintering_schedule", "part_strength_simulation",
            ],
            "supported_materials": [MaterialClass.THERMOPLASTIC, MaterialClass.COMPOSITE,
                                    MaterialClass.METAL_POWDER],
        },

        # ---- Binder Jetting ----------------------------------------------
        {
            "name": "ExOne / Desktop Metal Binder Jet",
            "vendor": "desktop_metal",
            "process": AdditiveProcess.BINDER_JETTING,
            "protocol": AMProtocol.REST_API,
            "layer": AMSystemLayer.SITE_OPERATIONS,
            "protocol_version": "2.0",
            "connection_config": {"requests_per_minute": 100, "burst_limit": 20},
            "capabilities": [
                "submit_build_job", "cancel_job", "monitor_progress",
                "binder_saturation_control", "depowdering_schedule",
                "sintering_furnace_control", "part_density_analytics",
                "material_recycling_ratio", "batch_traceability",
            ],
            "supported_materials": [MaterialClass.METAL_POWDER, MaterialClass.SAND,
                                    MaterialClass.CERAMIC],
        },

        # ---- DED / WAAM --------------------------------------------------
        {
            "name": "Lincoln Electric WAAM Controller",
            "vendor": "lincoln_electric",
            "process": AdditiveProcess.DED_WAAM,
            "protocol": AMProtocol.OPC_UA_AM,
            "layer": AMSystemLayer.DIRECT_CONTROL,
            "protocol_version": "1.0",
            "connection_config": {"requests_per_minute": 200, "burst_limit": 40},
            "capabilities": [
                "submit_build_job", "cancel_job", "monitor_progress",
                "wire_feed_rate_control", "arc_voltage_monitor",
                "interpass_temperature", "shielding_gas_flow",
                "layer_height_measurement", "path_planning_upload",
            ],
            "supported_materials": [MaterialClass.METAL_WIRE],
        },

        # ---- OPC UA AM companion-spec gateway ----------------------------
        {
            "name": "OPC UA AM Gateway (OPC 40564)",
            "vendor": "opc_foundation",
            "process": AdditiveProcess.FDM_FFF,   # generic — works across processes
            "protocol": AMProtocol.OPC_UA_AM,
            "layer": AMSystemLayer.SUPERVISORY,
            "protocol_version": "1.01",
            "connection_config": {"requests_per_minute": 500, "burst_limit": 100},
            "capabilities": [
                "node_browse", "node_read", "node_write",
                "job_management", "material_management",
                "condition_monitoring", "alarm_condition",
                "historical_access", "pub_sub_messaging",
            ],
            "supported_materials": [],
        },

        # ---- MTConnect Additive Agent ------------------------------------
        {
            "name": "MTConnect Additive Agent",
            "vendor": "mtconnect_institute",
            "process": AdditiveProcess.SLM_DMLS,   # generic
            "protocol": AMProtocol.MTCONNECT,
            "layer": AMSystemLayer.DIRECT_CONTROL,
            "protocol_version": "2.2",
            "connection_config": {"requests_per_minute": 300, "burst_limit": 60},
            "capabilities": [
                "device_stream", "current_data", "sample_data",
                "asset_management", "condition_monitoring",
                "laser_state", "powder_state", "build_layer_state",
            ],
            "supported_materials": [],
        },

        # ---- MQTT / Sparkplug B real-time telemetry ----------------------
        {
            "name": "AM Sparkplug B Telemetry",
            "vendor": "eclipse_sparkplug",
            "process": AdditiveProcess.FDM_FFF,
            "protocol": AMProtocol.MQTT_SPARKPLUG_B,
            "layer": AMSystemLayer.FIELD_DEVICE,
            "protocol_version": "3.0",
            "connection_config": {"requests_per_minute": 1000, "burst_limit": 200},
            "capabilities": [
                "device_birth_publish", "device_data_publish",
                "device_death_publish", "metric_reporting",
                "node_command", "state_management",
                "store_forward", "am_process_telemetry",
            ],
            "supported_materials": [],
        },
    ]
    return [AMConnector(**s) for s in specs]


DEFAULT_AM_CONNECTORS = _build_defaults()


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class AdditiveManufacturingRegistry:
    """Central registry for additive-manufacturing connectors."""

    def __init__(self, load_defaults: bool = True):
        self._lock = threading.RLock()
        self._connectors: Dict[str, AMConnector] = {}
        if load_defaults:
            for c in DEFAULT_AM_CONNECTORS:
                key = f"{c.vendor}_{c.protocol.value}"
                self._connectors[key] = c

    # -- registration -------------------------------------------------------

    def register(self, connector: AMConnector,
                 key: Optional[str] = None) -> Dict[str, Any]:
        with self._lock:
            k = key or f"{connector.vendor}_{connector.protocol.value}"
            self._connectors[k] = connector
            return {"registered": True, "key": k}

    def unregister(self, key: str) -> Dict[str, Any]:
        with self._lock:
            if key in self._connectors:
                del self._connectors[key]
                return {"unregistered": True, "key": key}
            return {"unregistered": False, "error": f"Unknown key: {key}"}

    # -- discovery ----------------------------------------------------------

    def discover(
        self,
        process: Optional[AdditiveProcess] = None,
        layer: Optional[AMSystemLayer] = None,
        vendor: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        with self._lock:
            connectors = list(self._connectors.values())
        if process is not None:
            connectors = [c for c in connectors if c.process == process]
        if layer is not None:
            connectors = [c for c in connectors if c.layer == layer]
        if vendor is not None:
            connectors = [c for c in connectors if c.vendor == vendor]
        return [c.to_dict() for c in connectors]

    def get_connector(self, key: str) -> Optional[AMConnector]:
        with self._lock:
            return self._connectors.get(key)

    def list_vendors(self) -> List[str]:
        with self._lock:
            return sorted({c.vendor for c in self._connectors.values()})

    def list_processes(self) -> List[str]:
        with self._lock:
            return sorted({c.process.value for c in self._connectors.values()})

    def list_protocols(self) -> List[str]:
        with self._lock:
            return sorted({c.protocol.value for c in self._connectors.values()})

    def list_layers(self) -> List[str]:
        with self._lock:
            return sorted({c.layer.value for c in self._connectors.values()})

    # -- execution ----------------------------------------------------------

    def execute(self, key: str, action_name: str,
                params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        connector = self.get_connector(key)
        if connector is None:
            return {"success": False, "error": f"Unknown connector: {key}"}
        return connector.execute_action(action_name, params)

    # -- health -------------------------------------------------------------

    def health_check(self, key: str) -> Dict[str, Any]:
        connector = self.get_connector(key)
        if connector is None:
            return {"status": "unknown", "error": f"Unknown connector: {key}"}
        return connector.health_check()

    def health_check_all(self) -> Dict[str, Dict[str, Any]]:
        with self._lock:
            connectors = dict(self._connectors)
        return {k: c.health_check() for k, c in connectors.items()}

    # -- statistics ---------------------------------------------------------

    def statistics(self) -> Dict[str, Any]:
        with self._lock:
            total = len(self._connectors)
            enabled = sum(1 for c in self._connectors.values() if c.is_enabled())
            vendors = {c.vendor for c in self._connectors.values()}
            processes = {c.process.value for c in self._connectors.values()}
            protocols = {c.protocol.value for c in self._connectors.values()}
            layers = {c.layer.value for c in self._connectors.values()}
            return {
                "total_connectors": total,
                "enabled_connectors": enabled,
                "disabled_connectors": total - enabled,
                "vendors": sorted(vendors),
                "processes": sorted(processes),
                "protocols": sorted(protocols),
                "layers": sorted(layers),
            }


# ---------------------------------------------------------------------------
# Workflow Binder — ISA-95 layer-aware orchestration
# ---------------------------------------------------------------------------

class AMWorkflowBinder:
    """Bind AM connectors into multi-step, dependency-aware workflows."""

    def __init__(self, registry: AdditiveManufacturingRegistry):
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
                 connector_key: str, action_name: str,
                 params: Optional[Dict[str, Any]] = None,
                 depends_on: Optional[List[str]] = None) -> Dict[str, Any]:
        with self._lock:
            wf = self._workflows.get(workflow_id)
            if wf is None:
                return {"success": False, "error": f"Unknown workflow: {workflow_id}"}

            connector = self._registry.get_connector(connector_key)
            if connector is None:
                return {"success": False, "error": f"Unknown connector: {connector_key}"}

            if action_name not in connector.capabilities:
                return {"success": False,
                        "error": f"Unsupported action: {action_name}"}

            step = {
                "step_id": step_id,
                "connector_key": connector_key,
                "vendor": connector.vendor,
                "process": connector.process.value,
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
        max_iter = len(steps) + 1
        iteration = 0

        while remaining and iteration < max_iter:
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
            results.append({"step_id": step["step_id"], "success": False,
                            "error": "Unmet dependencies"})

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
    registry = AdditiveManufacturingRegistry(load_defaults=True)
    stats = registry.statistics()
    health = registry.health_check_all()
    return {
        "module": "additive_manufacturing_connectors",
        "version": "1.0.0",
        "statistics": stats,
        "health": health,
        "timestamp": time.time(),
    }
