"""
Sensor/Robot Adapter Framework

Standardizes device telemetry ingestion and actuation with strict safety enforcement.

CRITICAL CONSTRAINTS:
- Sensors/robots are EXECUTION TARGETS only
- No free-form natural language or tool calls
- All actuation via compiled ExecutionPackets
- Gates checked before AND after actuation
- Telemetry flows through Artifact Graph to Control Plane
"""

from .adapter_contract import AdapterAPI, AdapterCapability, AdapterManifest
from .adapter_runtime import AdapterRegistry, AdapterRuntime
from .execution_packet_extension import DeviceExecutionPacket
from .safety_hooks import EmergencyStop, HeartbeatWatchdog, SafetyHooks
from .telemetry_artifact import TelemetryArtifact, TelemetryIngestionPipeline

__all__ = [
    'AdapterAPI',
    'AdapterCapability',
    'AdapterManifest',
    'TelemetryArtifact',
    'TelemetryIngestionPipeline',
    'DeviceExecutionPacket',
    'AdapterRuntime',
    'AdapterRegistry',
    'SafetyHooks',
    'EmergencyStop',
    'HeartbeatWatchdog'
]

__version__ = '1.0.0'
