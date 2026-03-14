"""
Factory Automation Connectors Module — Protocol connectors for factory floor
automation systems.

Design Label: FAC-001 — Factory Automation Protocol Connectors

Provides a unified interface for OPC-UA, EtherNet/IP (Rockwell), PROFINET
(Siemens), Modbus TCP, MTConnect, MQTT Sparkplug B, REST, and gRPC vendor
cloud APIs with thread-safe registry, ISA-95 layer-aware orchestration,
IEC 13849 safety-gate enforcement, and automatic capability mapping.

Supported Protocols / Standards:
  - OPC UA (IEC 62541)
  - EtherNet/IP  (ODVA CIP)
  - PROFINET     (IEC 61158)
  - Modbus TCP   (IEC 61158 / MODBUS-IDA)
  - MTConnect    (ANSI/MTC1.4-2018)
  - MQTT Sparkplug B (Eclipse Sparkplug 3.0)
  - REST / gRPC  (vendor cloud APIs — Rockwell FactoryTalk, PTC ThingWorx,
    Ignition, Siemens MindSphere, ABB Ability, KUKA iiQoT, etc.)

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

import logging
import re
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
# Module-level constants
# ---------------------------------------------------------------------------

_MAX_STR_LEN = 200
_ACTION_PATTERN = re.compile(r'^[a-zA-Z0-9_\-]{1,100}$')


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class FactoryAutomationProtocol(Enum):
    """Factory automation communication protocol (Enum subclass)."""
    OPCUA = "opcua"
    ETHERNET_IP = "ethernet_ip"
    PROFINET = "profinet"
    MODBUS_TCP = "modbus_tcp"
    MTCONNECT = "mtconnect"
    MQTT_SPARKPLUG = "mqtt_sparkplug"
    REST = "rest"
    GRPC = "grpc"


class FactorySystemLayer(Enum):
    """ISA-95 hierarchical layer (Enum subclass).

    Maps to the Purdue Model / ISA-95 levels:
      FIELD       — Level 0: sensors, actuators, drives
      CONTROL     — Level 1/2: PLCs, CNCs, robots
      SUPERVISORY — Level 2/3: SCADA, HMI, DCS
      MES         — Level 3: manufacturing execution systems
      ERP         — Level 4: enterprise resource planning
    """
    FIELD = "field"
    CONTROL = "control"
    SUPERVISORY = "supervisory"
    MES = "mes"
    ERP = "erp"


class ConnectorStatus(Enum):
    """Connector operational status (Enum subclass)."""
    ENABLED = "enabled"
    DISABLED = "disabled"
    ERROR = "error"


class MotionControlType(Enum):
    """Motion axis / robot kinematic type (Enum subclass)."""
    SERVO = "servo"
    STEPPER = "stepper"
    LINEAR = "linear"
    ROTARY = "rotary"
    DELTA = "delta"
    SCARA = "scara"
    SIX_AXIS = "six_axis"


class SafetyCategory(Enum):
    """IEC 13849-1 safety category (Enum subclass).

    Ordered by increasing safety integrity:
      NONE < CAT_B < CAT_1 < CAT_2 < CAT_3 < CAT_4
    """
    NONE = "none"
    CAT_B = "cat_b"
    CAT_1 = "cat_1"
    CAT_2 = "cat_2"
    CAT_3 = "cat_3"
    CAT_4 = "cat_4"


# Safety category integer rank — used for comparison.
_SAFETY_RANK: Dict[SafetyCategory, int] = {
    SafetyCategory.NONE: 0,
    SafetyCategory.CAT_B: 1,
    SafetyCategory.CAT_1: 2,
    SafetyCategory.CAT_2: 3,
    SafetyCategory.CAT_3: 4,
    SafetyCategory.CAT_4: 5,
}

# ISA-95 layer execution order (lower value = executed first).
_LAYER_ORDER: Dict[FactorySystemLayer, int] = {
    FactorySystemLayer.FIELD: 0,
    FactorySystemLayer.CONTROL: 1,
    FactorySystemLayer.SUPERVISORY: 2,
    FactorySystemLayer.MES: 3,
    FactorySystemLayer.ERP: 4,
}

# Default capabilities by ISA-95 layer.
_LAYER_CAPABILITIES: Dict[FactorySystemLayer, List[str]] = {
    FactorySystemLayer.FIELD: [
        "read_sensor", "write_output", "get_status", "calibrate", "reset_fault",
    ],
    FactorySystemLayer.CONTROL: [
        "read_program", "write_setpoint", "start_cycle", "stop_cycle",
        "e_stop", "get_alarms", "clear_faults", "get_diagnostics",
        "jog_axis", "home_axis", "get_position",
    ],
    FactorySystemLayer.SUPERVISORY: [
        "get_dashboard", "get_kpi", "create_job", "get_job_status",
        "update_recipe", "export_report", "get_alarms", "acknowledge_alarm",
    ],
    FactorySystemLayer.MES: [
        "get_work_order", "update_production_count", "report_downtime",
        "get_quality_data",
    ],
    FactorySystemLayer.ERP: [
        "get_work_order", "update_production_count", "report_downtime",
        "get_quality_data",
    ],
}


# ---------------------------------------------------------------------------
# Input sanitization helpers
# ---------------------------------------------------------------------------

def _sanitize_str(value: str, field: str = "field") -> str:
    """Strip null bytes and enforce maximum string length."""
    if not isinstance(value, str):
        raise TypeError(f"{field} must be a str")
    value = value.replace("\x00", "")
    if len(value) > _MAX_STR_LEN:
        raise ValueError(f"{field} exceeds {_MAX_STR_LEN} characters")
    return value


def _validate_port(port: int) -> int:
    """Validate TCP/UDP port is in range 0–65535."""
    if not isinstance(port, int) or not (0 <= port <= 65535):
        raise ValueError(f"port must be an integer 0–65535, got {port!r}")
    return port


def _validate_action_name(action_name: str) -> str:
    """Validate action_name: max 100 chars, alphanumeric + underscore + hyphen."""
    if not _ACTION_PATTERN.match(action_name):
        raise ValueError(
            f"action_name must be 1–100 alphanumeric/underscore/hyphen characters, "
            f"got {action_name!r}"
        )
    return action_name


# ---------------------------------------------------------------------------
# Connector
# ---------------------------------------------------------------------------

class FactoryAutomationConnector:
    """Adapter for a single factory automation protocol integration.

    Provides a uniform execute/configure/health-check interface over the
    ISA-95 device hierarchy regardless of underlying field protocol.
    """

    def __init__(
        self,
        vendor: str,
        model: str,
        protocol: FactoryAutomationProtocol,
        system_layer: FactorySystemLayer,
        host: str,
        port: int,
        endpoint: str = "",
        safety_category: SafetyCategory = SafetyCategory.NONE,
        motion_control_types: Optional[List[MotionControlType]] = None,
        credentials: Optional[Dict[str, str]] = None,
        enabled: bool = True,
        rate_limit_per_min: int = 60,
        capabilities: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.vendor = _sanitize_str(vendor, "vendor")
        self.model = _sanitize_str(model, "model")
        self.protocol = protocol
        self.system_layer = system_layer
        self.host = _sanitize_str(host, "host")
        self.port = _validate_port(port)
        self.endpoint = _sanitize_str(endpoint, "endpoint") if endpoint else ""
        self.safety_category = safety_category
        self.motion_control_types = list(motion_control_types) if motion_control_types else []
        self.rate_limit_per_min = max(1, int(rate_limit_per_min))
        self.metadata = dict(metadata) if metadata else {}

        # Auto-generate registry key as vendor_model slug.
        raw_key = f"{vendor}_{model}".lower()
        self.key = re.sub(r"[^a-z0-9_]", "_", raw_key)

        # Capabilities default to the ISA-95 layer set if not supplied.
        if capabilities is not None:
            self.capabilities: List[str] = list(capabilities)
        else:
            self.capabilities = list(_LAYER_CAPABILITIES.get(system_layer, []))

        self._lock = threading.RLock()
        self._status = ConnectorStatus.ENABLED if enabled else ConnectorStatus.DISABLED
        self._enabled = enabled
        self._request_count = 0
        self._error_count = 0
        self._window_start = time.time()
        self._window_requests = 0
        self._credentials: Dict[str, str] = dict(credentials) if credentials else {}
        self._action_log: List[Dict[str, Any]] = []

    # -- public interface ---------------------------------------------------

    def health_check(self) -> Dict[str, Any]:
        """Return current health status of the connector."""
        with self._lock:
            if not self._enabled:
                self._status = ConnectorStatus.DISABLED
            elif self._error_count > 0 and (
                self._error_count / max(self._request_count, 1) > 0.5
            ):
                self._status = ConnectorStatus.ERROR
            else:
                self._status = ConnectorStatus.ENABLED
            return {
                "key": self.key,
                "vendor": self.vendor,
                "model": self.model,
                "protocol": self.protocol.value,
                "system_layer": self.system_layer.value,
                "safety_category": self.safety_category.value,
                "status": self._status.value,
                "enabled": self._enabled,
                "request_count": self._request_count,
                "error_count": self._error_count,
                "timestamp": time.time(),
            }

    def execute_action(
        self, action_name: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Execute a named action against this connector.

        Validates the action name, enforces the rate limit, and dispatches
        to the real protocol client when credentials are configured.  Falls
        back to simulation when no credentials are present.
        """
        params = params or {}
        try:
            _validate_action_name(action_name)
        except ValueError as exc:
            return self._result(action_name, False, error=str(exc))

        with self._lock:
            if not self._enabled:
                return self._result(action_name, False, error="Connector is disabled")

            if action_name not in self.capabilities:
                return self._result(
                    action_name, False, error=f"Unsupported action: {action_name}"
                )

            if not self._check_rate_limit():
                return self._result(action_name, False, error="Rate limit exceeded")

            self._request_count += 1

            # Attempt real protocol dispatch if credentials are available.
            if self._credentials:
                real_result = self._dispatch_protocol(action_name, params)
                if real_result is not None:
                    return real_result

            # Simulated fallback.
            result = self._result(action_name, True, data={
                "action": action_name,
                "vendor": self.vendor,
                "model": self.model,
                "protocol": self.protocol.value,
                "system_layer": self.system_layer.value,
                "params": params,
                "simulated": True,
            })
            capped_append(self._action_log, result)
            return result

    def list_available_actions(self) -> List[str]:
        """Return list of supported action names."""
        return list(self.capabilities)

    def configure(self, credentials: Dict[str, str]) -> Dict[str, Any]:
        """Apply credentials / connection parameters."""
        with self._lock:
            self._credentials = dict(credentials)
            return {"configured": True, "key": self.key}

    def enable(self) -> None:
        """Enable this connector."""
        with self._lock:
            self._enabled = True
            self._status = ConnectorStatus.ENABLED

    def disable(self) -> None:
        """Disable this connector."""
        with self._lock:
            self._enabled = False
            self._status = ConnectorStatus.DISABLED

    def is_enabled(self) -> bool:
        """Return True if the connector is currently enabled."""
        with self._lock:
            return self._enabled

    def to_dict(self) -> Dict[str, Any]:
        """Return a serialisable snapshot of the connector state."""
        with self._lock:
            return {
                "key": self.key,
                "vendor": self.vendor,
                "model": self.model,
                "protocol": self.protocol.value,
                "system_layer": self.system_layer.value,
                "host": self.host,
                "port": self.port,
                "endpoint": self.endpoint,
                "safety_category": self.safety_category.value,
                "motion_control_types": [m.value for m in self.motion_control_types],
                "capabilities": self.capabilities,
                "enabled": self._enabled,
                "status": self._status.value,
                "request_count": self._request_count,
                "error_count": self._error_count,
                "metadata": self.metadata,
            }

    # -- internals ----------------------------------------------------------

    def _dispatch_protocol(
        self, action_name: str, params: dict
    ) -> Optional[Dict[str, Any]]:
        """Dispatch to the real protocol client if a suitable library is installed.

        Returns a result dict on success/real-error, or None to signal that
        the caller should fall through to simulation.
        """
        try:
            from src.protocols import (  # type: ignore[import]
                MurphyEtherNetIPClient,
                MurphyGRPCClient,
                MurphyModbusClient,
                MurphyMQTTSparkplugClient,
                MurphyMTConnectClient,
                MurphyOPCUAClient,
                MurphyProfinetClient,
                MurphyRESTClient,
            )
        except ImportError:
            logger.debug(
                "Protocol clients unavailable (simulation mode) for %s/%s — "
                "install murphy-protocols package to enable live dispatch",
                self.vendor, self.protocol.value,
            )
            return None

        proto = self.protocol
        host = self._credentials.get("host", self.host)
        port_str = self._credentials.get("port", str(self.port))

        client = None
        try:
            if proto == FactoryAutomationProtocol.OPCUA and MurphyOPCUAClient:
                url = self._credentials.get(
                    "url", f"opc.tcp://{host}:{port_str}"
                )
                client = MurphyOPCUAClient(url)
            elif proto == FactoryAutomationProtocol.MODBUS_TCP and MurphyModbusClient:
                client = MurphyModbusClient(host, port=int(port_str))
            elif proto == FactoryAutomationProtocol.ETHERNET_IP and MurphyEtherNetIPClient:
                client = MurphyEtherNetIPClient(host, port=int(port_str))
            elif proto == FactoryAutomationProtocol.PROFINET and MurphyProfinetClient:
                client = MurphyProfinetClient(host, port=int(port_str))
            elif proto == FactoryAutomationProtocol.MTCONNECT and MurphyMTConnectClient:
                client = MurphyMTConnectClient(host, port=int(port_str))
            elif proto == FactoryAutomationProtocol.MQTT_SPARKPLUG and MurphyMQTTSparkplugClient:
                client = MurphyMQTTSparkplugClient(host, port=int(port_str))
            elif proto == FactoryAutomationProtocol.REST and MurphyRESTClient:
                base_url = self._credentials.get(
                    "base_url",
                    f"https://{host}:{port_str}{self.endpoint}",
                )
                client = MurphyRESTClient(base_url)
            elif proto == FactoryAutomationProtocol.GRPC and MurphyGRPCClient:
                client = MurphyGRPCClient(host, port=int(port_str))
        except Exception as exc:
            logger.debug("Failed to build %s client: %s", proto.value, exc)
            return None

        if client is None:
            return None

        try:
            raw = client.execute(action_name, params)
            if raw.get("simulated"):
                return None
            result = self._result(
                action_name,
                True,
                data={**raw, "protocol": self.protocol.value, "vendor": self.vendor},
            )
            capped_append(self._action_log, result)
            return result
        except Exception as exc:
            self._error_count += 1
            result = self._result(action_name, False, error=str(exc))
            capped_append(self._action_log, result)
            return result

    def _check_rate_limit(self) -> bool:
        """Sliding-window rate limiter (one 60-second window)."""
        now = time.time()
        if now - self._window_start > 60:
            self._window_start = now
            self._window_requests = 0
        if self._window_requests >= self.rate_limit_per_min:
            return False
        self._window_requests += 1
        return True

    def _result(
        self,
        action: str,
        success: bool,
        data: Any = None,
        error: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Return a standard result shape."""
        return {
            "action": action,
            "connector": self.key,
            "vendor": self.vendor,
            "model": self.model,
            "success": success,
            "data": data,
            "error": error,
            "timestamp": time.time(),
        }


# ---------------------------------------------------------------------------
# Default connector catalogue
# ---------------------------------------------------------------------------

def _build_defaults() -> List[FactoryAutomationConnector]:
    """Instantiate the built-in catalogue of real vendor connectors.

    Each spec is wrapped in a try/except so a malformed entry never prevents
    the remaining connectors from loading.
    """
    specs: List[Dict[str, Any]] = [
        # 1. Rockwell Automation FactoryTalk — EtherNet/IP, SUPERVISORY
        {
            "vendor": "rockwell_automation",
            "model": "FactoryTalk",
            "protocol": FactoryAutomationProtocol.ETHERNET_IP,
            "system_layer": FactorySystemLayer.SUPERVISORY,
            "host": "api.rockwellautomation.com",
            "port": 443,
            "endpoint": "/api/v1",
            "safety_category": SafetyCategory.CAT_2,
            "motion_control_types": [],
            "rate_limit_per_min": 120,
            "capabilities": [
                "get_dashboard", "get_kpi", "create_job", "get_job_status",
                "update_recipe", "export_report", "get_alarms", "acknowledge_alarm",
            ],
            "metadata": {"product_family": "FactoryTalk", "protocol_alt": "rest"},
        },
        # 2. Siemens SIMATIC S7 — PROFINET, CONTROL
        {
            "vendor": "siemens",
            "model": "SIMATIC_S7",
            "protocol": FactoryAutomationProtocol.PROFINET,
            "system_layer": FactorySystemLayer.CONTROL,
            "host": "192.168.0.1",
            "port": 102,
            "endpoint": "",
            "safety_category": SafetyCategory.CAT_3,
            "motion_control_types": [MotionControlType.SERVO],
            "rate_limit_per_min": 200,
            "capabilities": [
                "read_program", "write_setpoint", "start_cycle", "stop_cycle",
                "e_stop", "get_alarms", "clear_faults", "get_diagnostics",
                "get_position",
            ],
            "metadata": {
                "product_family": "SIMATIC S7-1500",
                "tia_portal_version": "V18",
            },
        },
        # 3. Beckhoff TwinCAT 3 — OPC UA (ADS port 851), CONTROL
        {
            "vendor": "beckhoff",
            "model": "TwinCAT_3",
            "protocol": FactoryAutomationProtocol.OPCUA,
            "system_layer": FactorySystemLayer.CONTROL,
            "host": "192.168.0.10",
            "port": 851,
            "endpoint": "",
            "safety_category": SafetyCategory.CAT_3,
            "motion_control_types": [MotionControlType.SERVO, MotionControlType.LINEAR],
            "rate_limit_per_min": 300,
            "capabilities": [
                "read_program", "write_setpoint", "start_cycle", "stop_cycle",
                "e_stop", "get_alarms", "clear_faults", "get_diagnostics",
                "jog_axis", "home_axis", "get_position",
            ],
            "metadata": {"ads_port": 851, "tc_version": "3.1"},
        },
        # 4. FANUC CNC / Robot — OPC UA + MTConnect, CONTROL, SIX_AXIS
        {
            "vendor": "fanuc",
            "model": "CNC_Robot",
            "protocol": FactoryAutomationProtocol.OPCUA,
            "system_layer": FactorySystemLayer.CONTROL,
            "host": "192.168.0.20",
            "port": 4840,
            "endpoint": "",
            "safety_category": SafetyCategory.CAT_3,
            "motion_control_types": [MotionControlType.SIX_AXIS, MotionControlType.SERVO],
            "rate_limit_per_min": 150,
            "capabilities": [
                "read_program", "write_setpoint", "start_cycle", "stop_cycle",
                "e_stop", "get_alarms", "clear_faults", "get_diagnostics",
                "jog_axis", "home_axis", "get_position",
            ],
            "metadata": {"protocol_alt": "mtconnect", "focas_version": "2"},
        },
        # 5. ABB OmniCore — OPC UA, CONTROL, SIX_AXIS
        {
            "vendor": "abb",
            "model": "OmniCore",
            "protocol": FactoryAutomationProtocol.OPCUA,
            "system_layer": FactorySystemLayer.CONTROL,
            "host": "192.168.0.30",
            "port": 4840,
            "endpoint": "",
            "safety_category": SafetyCategory.CAT_3,
            "motion_control_types": [MotionControlType.SIX_AXIS],
            "rate_limit_per_min": 150,
            "capabilities": [
                "read_program", "write_setpoint", "start_cycle", "stop_cycle",
                "e_stop", "get_alarms", "clear_faults", "get_diagnostics",
                "jog_axis", "home_axis", "get_position",
            ],
            "metadata": {"rws_version": "7", "product": "OmniCore C30"},
        },
        # 6. KUKA KR C5 — OPC UA, CONTROL, SIX_AXIS
        {
            "vendor": "kuka",
            "model": "KR_C5",
            "protocol": FactoryAutomationProtocol.OPCUA,
            "system_layer": FactorySystemLayer.CONTROL,
            "host": "192.168.0.40",
            "port": 4840,
            "endpoint": "",
            "safety_category": SafetyCategory.CAT_3,
            "motion_control_types": [MotionControlType.SIX_AXIS],
            "rate_limit_per_min": 150,
            "capabilities": [
                "read_program", "write_setpoint", "start_cycle", "stop_cycle",
                "e_stop", "get_alarms", "clear_faults", "get_diagnostics",
                "jog_axis", "home_axis", "get_position",
            ],
            "metadata": {"iiqot_enabled": True, "krl_version": "5.x"},
        },
        # 7. Yaskawa Motoman — OPC UA + REST, CONTROL, SIX_AXIS
        {
            "vendor": "yaskawa",
            "model": "Motoman",
            "protocol": FactoryAutomationProtocol.OPCUA,
            "system_layer": FactorySystemLayer.CONTROL,
            "host": "192.168.0.50",
            "port": 4840,
            "endpoint": "",
            "safety_category": SafetyCategory.CAT_3,
            "motion_control_types": [MotionControlType.SIX_AXIS, MotionControlType.SCARA],
            "rate_limit_per_min": 150,
            "capabilities": [
                "read_program", "write_setpoint", "start_cycle", "stop_cycle",
                "e_stop", "get_alarms", "clear_faults", "get_diagnostics",
                "jog_axis", "home_axis", "get_position",
            ],
            "metadata": {"protocol_alt": "rest", "yrc_version": "YRC1000"},
        },
        # 8. Omron NX/NJ — OPC UA + EtherNet/IP, CONTROL, SERVO
        {
            "vendor": "omron",
            "model": "NX_NJ",
            "protocol": FactoryAutomationProtocol.OPCUA,
            "system_layer": FactorySystemLayer.CONTROL,
            "host": "192.168.0.60",
            "port": 4840,
            "endpoint": "",
            "safety_category": SafetyCategory.CAT_2,
            "motion_control_types": [MotionControlType.SERVO],
            "rate_limit_per_min": 200,
            "capabilities": [
                "read_program", "write_setpoint", "start_cycle", "stop_cycle",
                "e_stop", "get_alarms", "clear_faults", "get_diagnostics",
                "jog_axis", "home_axis", "get_position",
            ],
            "metadata": {
                "protocol_alt": "ethernet_ip",
                "sysmac_studio_version": "2.x",
            },
        },
        # 9. Mitsubishi MELSEC iQ-R — OPC UA + REST, CONTROL
        {
            "vendor": "mitsubishi",
            "model": "MELSEC_iQ_R",
            "protocol": FactoryAutomationProtocol.OPCUA,
            "system_layer": FactorySystemLayer.CONTROL,
            "host": "192.168.0.70",
            "port": 4840,
            "endpoint": "",
            "safety_category": SafetyCategory.CAT_2,
            "motion_control_types": [MotionControlType.SERVO],
            "rate_limit_per_min": 200,
            "capabilities": [
                "read_program", "write_setpoint", "start_cycle", "stop_cycle",
                "e_stop", "get_alarms", "clear_faults", "get_diagnostics",
                "get_position",
            ],
            "metadata": {"protocol_alt": "rest", "gx_works_version": "3"},
        },
        # 10. PTC ThingWorx — REST, SUPERVISORY (IIoT platform)
        {
            "vendor": "ptc",
            "model": "ThingWorx",
            "protocol": FactoryAutomationProtocol.REST,
            "system_layer": FactorySystemLayer.SUPERVISORY,
            "host": "company.thingworx.com",
            "port": 443,
            "endpoint": "/Thingworx/Things",
            "safety_category": SafetyCategory.NONE,
            "motion_control_types": [],
            "rate_limit_per_min": 300,
            "capabilities": [
                "get_dashboard", "get_kpi", "create_job", "get_job_status",
                "update_recipe", "export_report", "get_alarms", "acknowledge_alarm",
            ],
            "metadata": {"platform": "IIoT", "version": "9.x"},
        },
        # 11. Inductive Automation Ignition — REST + OPC UA, SUPERVISORY (SCADA/MES)
        {
            "vendor": "inductive_automation",
            "model": "Ignition",
            "protocol": FactoryAutomationProtocol.REST,
            "system_layer": FactorySystemLayer.SUPERVISORY,
            "host": "ignition.company.com",
            "port": 8088,
            "endpoint": "/api",
            "safety_category": SafetyCategory.CAT_1,
            "motion_control_types": [],
            "rate_limit_per_min": 300,
            "capabilities": [
                "get_dashboard", "get_kpi", "create_job", "get_job_status",
                "update_recipe", "export_report", "get_alarms", "acknowledge_alarm",
            ],
            "metadata": {"protocol_alt": "opcua", "edition": "Standard/Edge"},
        },
        # 12. Emerson DeltaV — OPC UA + PROFINET, CONTROL
        {
            "vendor": "emerson",
            "model": "DeltaV",
            "protocol": FactoryAutomationProtocol.OPCUA,
            "system_layer": FactorySystemLayer.CONTROL,
            "host": "192.168.0.80",
            "port": 4840,
            "endpoint": "",
            "safety_category": SafetyCategory.CAT_3,
            "motion_control_types": [],
            "rate_limit_per_min": 150,
            "capabilities": [
                "read_program", "write_setpoint", "start_cycle", "stop_cycle",
                "e_stop", "get_alarms", "clear_faults", "get_diagnostics",
            ],
            "metadata": {
                "protocol_alt": "profinet",
                "deltav_version": "14.LTS",
            },
        },
        # 13. Cognex In-Sight 9000 — REST + gRPC, FIELD (machine vision)
        {
            "vendor": "cognex",
            "model": "In_Sight_9000",
            "protocol": FactoryAutomationProtocol.REST,
            "system_layer": FactorySystemLayer.FIELD,
            "host": "192.168.0.90",
            "port": 8080,
            "endpoint": "/api/v1",
            "safety_category": SafetyCategory.NONE,
            "motion_control_types": [],
            "rate_limit_per_min": 120,
            "capabilities": [
                "read_sensor", "write_output", "get_status",
                "calibrate", "reset_fault",
            ],
            "metadata": {
                "protocol_alt": "grpc",
                "vision_type": "machine_vision",
            },
        },
        # 14. Keyence CV-X — REST, FIELD (machine vision)
        {
            "vendor": "keyence",
            "model": "CV_X",
            "protocol": FactoryAutomationProtocol.REST,
            "system_layer": FactorySystemLayer.FIELD,
            "host": "192.168.0.91",
            "port": 8500,
            "endpoint": "/api",
            "safety_category": SafetyCategory.NONE,
            "motion_control_types": [],
            "rate_limit_per_min": 120,
            "capabilities": [
                "read_sensor", "write_output", "get_status",
                "calibrate", "reset_fault",
            ],
            "metadata": {"vision_type": "machine_vision"},
        },
        # 15. Bosch Rexroth ctrlX — OPC UA + MQTT Sparkplug B, CONTROL
        {
            "vendor": "bosch_rexroth",
            "model": "ctrlX",
            "protocol": FactoryAutomationProtocol.OPCUA,
            "system_layer": FactorySystemLayer.CONTROL,
            "host": "192.168.0.100",
            "port": 4840,
            "endpoint": "",
            "safety_category": SafetyCategory.CAT_3,
            "motion_control_types": [
                MotionControlType.SERVO,
                MotionControlType.LINEAR,
            ],
            "rate_limit_per_min": 200,
            "capabilities": [
                "read_program", "write_setpoint", "start_cycle", "stop_cycle",
                "e_stop", "get_alarms", "clear_faults", "get_diagnostics",
                "jog_axis", "home_axis", "get_position",
            ],
            "metadata": {
                "protocol_alt": "mqtt_sparkplug",
                "ctrlx_os_version": "2.x",
            },
        },
    ]

    connectors: List[FactoryAutomationConnector] = []
    for spec in specs:
        try:
            connectors.append(FactoryAutomationConnector(**spec))
        except Exception as exc:
            logger.warning(
                "Failed to build default connector %r: %s",
                spec.get("vendor", "unknown"),
                exc,
            )
    return connectors


DEFAULT_FA_CONNECTORS: List[FactoryAutomationConnector] = _build_defaults()


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class FactoryAutomationRegistry:
    """Central registry for factory automation connectors."""

    def __init__(self, load_defaults: bool = True):
        self._lock = threading.RLock()
        self._connectors: Dict[str, FactoryAutomationConnector] = {}
        if load_defaults:
            for c in DEFAULT_FA_CONNECTORS:
                self._connectors[c.key] = c

    # -- registration -------------------------------------------------------

    def register(self, connector: FactoryAutomationConnector) -> Dict[str, Any]:
        """Register a connector under its auto-generated key."""
        with self._lock:
            self._connectors[connector.key] = connector
            return {"registered": True, "key": connector.key}

    def unregister(self, key: str) -> Dict[str, Any]:
        """Remove a connector from the registry."""
        with self._lock:
            if key in self._connectors:
                del self._connectors[key]
                return {"unregistered": True, "key": key}
            return {"unregistered": False, "error": f"Unknown key: {key}"}

    # -- discovery ----------------------------------------------------------

    def discover(
        self,
        protocol: Optional[FactoryAutomationProtocol] = None,
        layer: Optional[FactorySystemLayer] = None,
        safety_category: Optional[SafetyCategory] = None,
    ) -> List[Dict[str, Any]]:
        """Return connector snapshots matching the given filter criteria."""
        with self._lock:
            connectors = list(self._connectors.values())
        if protocol is not None:
            connectors = [c for c in connectors if c.protocol == protocol]
        if layer is not None:
            connectors = [c for c in connectors if c.system_layer == layer]
        if safety_category is not None:
            connectors = [
                c for c in connectors if c.safety_category == safety_category
            ]
        return [c.to_dict() for c in connectors]

    def get_connector(self, key: str) -> Optional[FactoryAutomationConnector]:
        """Return the connector registered under *key*, or None."""
        with self._lock:
            return self._connectors.get(key)

    # -- list helpers -------------------------------------------------------

    def list_vendors(self) -> List[str]:
        """Return sorted list of unique vendor identifiers."""
        with self._lock:
            return sorted({c.vendor for c in self._connectors.values()})

    def list_protocols(self) -> List[str]:
        """Return sorted list of unique protocol values."""
        with self._lock:
            return sorted({c.protocol.value for c in self._connectors.values()})

    def list_layers(self) -> List[str]:
        """Return sorted list of unique ISA-95 layer values."""
        with self._lock:
            return sorted({c.system_layer.value for c in self._connectors.values()})

    # -- execution ----------------------------------------------------------

    def execute(
        self,
        key: str,
        action: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute an action on the connector registered under *key*."""
        connector = self.get_connector(key)
        if connector is None:
            return {"success": False, "error": f"Unknown connector: {key}"}
        return connector.execute_action(action, params)

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

    # -- statistics ---------------------------------------------------------

    def statistics(self) -> Dict[str, Any]:
        """Return aggregate statistics for the registry."""
        with self._lock:
            total = len(self._connectors)
            enabled = sum(1 for c in self._connectors.values() if c.is_enabled())
            vendors = {c.vendor for c in self._connectors.values()}
            protocols = {c.protocol.value for c in self._connectors.values()}
            layers = {c.system_layer.value for c in self._connectors.values()}
            safety_cats = {
                c.safety_category.value for c in self._connectors.values()
            }
            return {
                "total_connectors": total,
                "enabled_connectors": enabled,
                "disabled_connectors": total - enabled,
                "vendors": sorted(vendors),
                "protocols": sorted(protocols),
                "layers": sorted(layers),
                "safety_categories": sorted(safety_cats),
                "keys": sorted(self._connectors.keys()),
            }


# ---------------------------------------------------------------------------
# Orchestrator — ISA-95 layer-aware workflow sequencing
# ---------------------------------------------------------------------------

class FactoryAutomationOrchestrator:
    """Coordinate multi-protocol factory automation workflows as ordered
    sequences of connector actions.

    Key behaviours:
    - Steps execute in ISA-95 layer order (FIELD → CONTROL → SUPERVISORY → MES)
      within the dependency-resolution loop.
    - Safety gate: sequences touching a connector with SafetyCategory < CAT_2
      require ``override_safety_gate=True`` in :meth:`execute_sequence`.
    """

    def __init__(self, registry: FactoryAutomationRegistry):
        self._registry = registry
        self._lock = threading.RLock()
        self._sequences: Dict[str, Dict[str, Any]] = {}

    def create_sequence(
        self,
        sequence_id: str,
        name: str,
        description: str = "",
    ) -> Dict[str, Any]:
        """Create a new execution sequence and return its definition."""
        with self._lock:
            seq: Dict[str, Any] = {
                "sequence_id": sequence_id,
                "name": name,
                "description": description,
                "steps": [],
                "created_at": time.time(),
                "status": "created",
                "aborted": False,
            }
            self._sequences[sequence_id] = seq
            return dict(seq)

    def add_step(
        self,
        sequence_id: str,
        step_id: str,
        connector_key: str,
        action_name: str,
        params: Optional[Dict[str, Any]] = None,
        timeout_seconds: int = 30,
        on_error: str = "abort",
    ) -> Dict[str, Any]:
        """Add a step to an existing sequence.

        Parameters
        ----------
        on_error:
            ``"abort"`` — stop the sequence on failure (default).
            ``"continue"`` — log the failure and proceed to the next step.
        """
        with self._lock:
            seq = self._sequences.get(sequence_id)
            if seq is None:
                return {"success": False, "error": f"Unknown sequence: {sequence_id}"}

            connector = self._registry.get_connector(connector_key)
            if connector is None:
                return {
                    "success": False,
                    "error": f"Unknown connector: {connector_key}",
                }

            if action_name not in connector.capabilities:
                return {
                    "success": False,
                    "error": f"Unsupported action '{action_name}' on {connector_key}",
                }

            step: Dict[str, Any] = {
                "step_id": step_id,
                "connector_key": connector_key,
                "action_name": action_name,
                "params": params or {},
                "timeout_seconds": max(1, int(timeout_seconds)),
                "on_error": on_error if on_error in ("abort", "continue") else "abort",
                "layer": connector.system_layer.value,
                "layer_order": _LAYER_ORDER.get(connector.system_layer, 99),
                "safety_rank": _SAFETY_RANK.get(connector.safety_category, 0),
                "status": "pending",
            }
            seq["steps"].append(step)
            return {"success": True, "step": step}

    def execute_sequence(
        self,
        sequence_id: str,
        override_safety_gate: bool = False,
    ) -> Dict[str, Any]:
        """Execute all steps in the sequence respecting ISA-95 layer order.

        Steps are sorted by ``layer_order`` (FIELD → CONTROL → SUPERVISORY → MES)
        before execution. If any step references a connector with
        SafetyCategory < CAT_2, execution is blocked unless
        ``override_safety_gate=True`` is passed.

        Parameters
        ----------
        override_safety_gate:
            Set to True to allow execution on sub-CAT_2 equipment.
        """
        with self._lock:
            seq = self._sequences.get(sequence_id)
            if seq is None:
                return {"success": False, "error": f"Unknown sequence: {sequence_id}"}
            if seq.get("aborted"):
                return {"success": False, "error": "Sequence has been aborted"}
            seq_steps = list(seq["steps"])
            seq["status"] = "running"

        # Safety gate check.
        _CAT_2_RANK = _SAFETY_RANK[SafetyCategory.CAT_2]
        low_safety_steps = [
            s for s in seq_steps if s["safety_rank"] < _CAT_2_RANK
        ]
        if low_safety_steps and not override_safety_gate:
            affected = [s["connector_key"] for s in low_safety_steps]
            with self._lock:
                seq["status"] = "blocked"
            return {
                "success": False,
                "error": (
                    "Safety gate: connectors with SafetyCategory < CAT_2 detected "
                    f"({affected}). Pass override_safety_gate=True to proceed."
                ),
                "affected_connectors": affected,
            }

        # Sort by ISA-95 layer order (stable sort preserves add_step insertion order
        # within the same layer).
        ordered_steps = sorted(seq_steps, key=lambda s: s["layer_order"])

        results: List[Dict[str, Any]] = []
        aborted = False

        for step in ordered_steps:
            with self._lock:
                if seq.get("aborted"):
                    aborted = True
                    break

            result = self._registry.execute(
                step["connector_key"], step["action_name"], step["params"]
            )
            result["step_id"] = step["step_id"]
            results.append(result)

            if result.get("success"):
                step["status"] = "completed"
            else:
                step["status"] = "failed"
                logger.warning(
                    "Sequence %s: step %s failed — %s",
                    sequence_id,
                    step["step_id"],
                    result.get("error"),
                )
                if step["on_error"] == "abort":
                    aborted = True
                    break

        if aborted:
            # Mark remaining steps as skipped.
            completed_ids = {r["step_id"] for r in results}
            for step in ordered_steps:
                if step["step_id"] not in completed_ids:
                    step["status"] = "skipped"
                    results.append({
                        "step_id": step["step_id"],
                        "success": False,
                        "error": "Sequence aborted",
                    })

        with self._lock:
            seq["status"] = "aborted" if aborted else "completed"

        all_ok = all(r.get("success") for r in results)
        return {
            "sequence_id": sequence_id,
            "success": all_ok and not aborted,
            "results": results,
            "status": seq["status"],
        }

    def get_sequence(self, sequence_id: str) -> Optional[Dict[str, Any]]:
        """Return a copy of the sequence definition, or None if not found."""
        with self._lock:
            seq = self._sequences.get(sequence_id)
            return dict(seq) if seq else None

    def list_sequences(self) -> List[Dict[str, Any]]:
        """Return a summary list of all sequences."""
        with self._lock:
            return [
                {
                    "sequence_id": sid,
                    "name": s["name"],
                    "status": s["status"],
                    "step_count": len(s["steps"]),
                }
                for sid, s in self._sequences.items()
            ]

    def abort_sequence(self, sequence_id: str) -> Dict[str, Any]:
        """Signal a running sequence to stop after its current step."""
        with self._lock:
            seq = self._sequences.get(sequence_id)
            if seq is None:
                return {"success": False, "error": f"Unknown sequence: {sequence_id}"}
            seq["aborted"] = True
            seq["status"] = "aborting"
            return {"success": True, "sequence_id": sequence_id, "status": "aborting"}


# ---------------------------------------------------------------------------
# Module-level status helper
# ---------------------------------------------------------------------------

def get_status() -> Dict[str, Any]:
    """Return module-level status information."""
    registry = FactoryAutomationRegistry(load_defaults=True)
    stats = registry.statistics()
    return {
        "module": "factory_automation_connectors",
        "design_label": "FAC-001",
        "version": "1.0.0",
        "protocols": [p.value for p in FactoryAutomationProtocol],
        "system_layers": [l.value for l in FactorySystemLayer],
        "safety_categories": [s.value for s in SafetyCategory],
        "default_connectors": stats["total_connectors"],
        "enabled_connectors": stats["enabled_connectors"],
        "vendors": stats["vendors"],
        "status": "operational",
        "timestamp": time.time(),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    "FactoryAutomationProtocol",
    "FactorySystemLayer",
    "ConnectorStatus",
    "MotionControlType",
    "SafetyCategory",
    "FactoryAutomationConnector",
    "FactoryAutomationRegistry",
    "FactoryAutomationOrchestrator",
    "DEFAULT_FA_CONNECTORS",
    "get_status",
]
