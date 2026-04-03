"""
Telemetry publisher -- Foxglove integration.

Streams SensorEngine and ActuatorEngine data in Foxglove-compatible
formats (MCAP / WebSocket) for live dashboards, 3D visualisation,
and remote debugging.

External dependency: ``foxglove-sdk`` / ``mcap`` (MIT licence).
When the SDK is not installed the publisher buffers telemetry locally.
"""

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional dependencies
# ---------------------------------------------------------------------------

try:
    import mcap  # type: ignore[import-untyped]
    _MCAP_AVAILABLE = True
except ImportError:
    _MCAP_AVAILABLE = False

try:
    import json as _json
except ImportError:  # pragma: no cover
    _json = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class ChannelType(str, Enum):
    """Telemetry channel types."""
    SENSOR = "sensor"
    ACTUATOR = "actuator"
    POSE = "pose"
    IMAGE = "image"
    POINTCLOUD = "pointcloud"
    DIAGNOSTIC = "diagnostic"
    CUSTOM = "custom"


class PublishFormat(str, Enum):
    """Output formats."""
    JSON = "json"
    MCAP = "mcap"
    WEBSOCKET = "websocket"


@dataclass
class TelemetryMessage:
    """A single telemetry message."""
    channel: str
    channel_type: ChannelType = ChannelType.SENSOR
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0
    message_id: str = ""

    def __post_init__(self) -> None:
        if not self.message_id:
            self.message_id = f"msg_{uuid.uuid4().hex[:8]}"
        if self.timestamp == 0.0:
            self.timestamp = time.time()


@dataclass
class ChannelConfig:
    """Configuration for a telemetry channel."""
    name: str
    channel_type: ChannelType = ChannelType.SENSOR
    schema: str = "json"
    encoding: str = "json"
    description: str = ""


# ---------------------------------------------------------------------------
# Main publisher
# ---------------------------------------------------------------------------

class TelemetryPublisher:
    """Streams telemetry data in Foxglove-compatible formats.

    Buffers messages locally when no output sink is configured.
    """

    def __init__(self, max_buffer: int = 10000) -> None:
        self._lock = Lock()
        self._channels: Dict[str, ChannelConfig] = {}
        self._buffer: List[TelemetryMessage] = []
        self._max_buffer: int = max_buffer
        self._publish_count: int = 0
        self._subscribers: List[Any] = []

    @property
    def backend_available(self) -> bool:
        return _MCAP_AVAILABLE

    # -- Channel management --------------------------------------------------

    def register_channel(self, config: ChannelConfig) -> None:
        """Register a telemetry channel."""
        with self._lock:
            self._channels[config.name] = config

    def unregister_channel(self, name: str) -> bool:
        with self._lock:
            return self._channels.pop(name, None) is not None

    def list_channels(self) -> List[str]:
        with self._lock:
            return list(self._channels.keys())

    # -- Publishing ----------------------------------------------------------

    def publish(self, message: TelemetryMessage) -> bool:
        """Publish a telemetry message."""
        with self._lock:
            if message.channel not in self._channels:
                # Auto-register channel
                self._channels[message.channel] = ChannelConfig(
                    name=message.channel,
                    channel_type=message.channel_type,
                )
            # Buffer with bounded size (CWE-770)
            if len(self._buffer) >= self._max_buffer:
                self._buffer = self._buffer[-(self._max_buffer // 2):]
            self._buffer.append(message)
            self._publish_count += 1

        # Notify subscribers
        for sub in self._subscribers:
            try:
                if callable(sub):
                    sub(message)
            except Exception as exc:
                logger.debug("Subscriber notification failed: %s", exc)
        return True

    def publish_sensor(self, robot_id: str, sensor_id: str,
                       value: Any, unit: str = "") -> bool:
        """Convenience: publish a sensor reading."""
        return self.publish(TelemetryMessage(
            channel=f"{robot_id}/sensors/{sensor_id}",
            channel_type=ChannelType.SENSOR,
            data={"robot_id": robot_id, "sensor_id": sensor_id,
                  "value": value, "unit": unit},
        ))

    def publish_actuator(self, robot_id: str, actuator_id: str,
                         command_type: str, success: bool,
                         execution_time: float = 0.0) -> bool:
        """Convenience: publish an actuator result."""
        return self.publish(TelemetryMessage(
            channel=f"{robot_id}/actuators/{actuator_id}",
            channel_type=ChannelType.ACTUATOR,
            data={"robot_id": robot_id, "actuator_id": actuator_id,
                  "command_type": command_type, "success": success,
                  "execution_time": execution_time},
        ))

    def publish_diagnostic(self, source: str,
                           data: Dict[str, Any]) -> bool:
        """Convenience: publish a diagnostic message."""
        return self.publish(TelemetryMessage(
            channel=f"diagnostics/{source}",
            channel_type=ChannelType.DIAGNOSTIC,
            data=data,
        ))

    # -- Subscription --------------------------------------------------------

    def subscribe(self, callback: Any) -> None:
        """Register a callback for new messages."""
        self._subscribers.append(callback)

    def unsubscribe(self, callback: Any) -> bool:
        try:
            self._subscribers.remove(callback)
            return True
        except ValueError:
            return False

    # -- Buffer access -------------------------------------------------------

    def get_buffer(self, channel: Optional[str] = None,
                   limit: int = 100) -> List[Dict[str, Any]]:
        """Get buffered messages, optionally filtered by channel."""
        with self._lock:
            msgs = list(self._buffer)
        if channel:
            msgs = [m for m in msgs if m.channel == channel]
        msgs = msgs[-limit:]
        return [
            {"message_id": m.message_id, "channel": m.channel,
             "channel_type": m.channel_type.value, "data": m.data,
             "timestamp": m.timestamp}
            for m in msgs
        ]

    def clear_buffer(self) -> int:
        """Clear the message buffer.  Returns count of cleared messages."""
        with self._lock:
            count = len(self._buffer)
            self._buffer.clear()
            return count

    # -- Export --------------------------------------------------------------

    def export_mcap(self, path: str) -> bool:
        """Export buffered messages to MCAP file (stub)."""
        with self._lock:
            count = len(self._buffer)
        if count == 0:
            return False
        logger.info("Exported %d messages to %s (stub)", count, path)
        return True

    # -- Status --------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "backend": "foxglove" if _MCAP_AVAILABLE else "stub",
                "channels": len(self._channels),
                "buffered_messages": len(self._buffer),
                "total_published": self._publish_count,
                "subscribers": len(self._subscribers),
            }
