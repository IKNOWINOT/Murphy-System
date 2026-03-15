"""
Unified sensor reading engine across all robot platforms.
"""

import logging
from threading import Lock
from typing import Any, Dict, List, Optional

from robotics.robot_registry import RobotRegistry
from robotics.robotics_models import RobotStatus, SensorReading

logger = logging.getLogger(__name__)


class SensorEngine:
    """Unified sensor reading engine across all robot platforms."""

    def __init__(self, registry: RobotRegistry) -> None:
        self._registry = registry
        self._cache: Dict[str, SensorReading] = {}
        self._lock = Lock()

    def read_sensor(self, robot_id: str, sensor_type: str,
                    sensor_id: str) -> SensorReading:
        """Read a sensor value from any registered robot."""
        client = self._registry.get_client(robot_id)
        if client is None:
            raise ValueError(f"Unknown robot: {robot_id}")
        if client.status == RobotStatus.DISCONNECTED:
            raise RuntimeError(f"Robot {robot_id} is disconnected")
        reading = client.read_sensor(sensor_id, sensor_type)
        cache_key = f"{robot_id}:{sensor_id}"
        with self._lock:
            self._cache[cache_key] = reading
        return reading

    def read_all_sensors(self, robot_id: str) -> List[SensorReading]:
        """Read all known sensors from a robot.

        Uses the robot's configured capabilities to determine which sensors
        are available.  Capabilities that start with ``"sense_"`` are treated
        as sensor types (e.g. ``"sense_temperature"`` → sensor type
        ``"temperature"``).
        """
        config = self._registry.get(robot_id)
        if config is None:
            raise ValueError(f"Unknown robot: {robot_id}")
        readings: List[SensorReading] = []
        for cap in config.capabilities:
            if cap.startswith("sense_"):
                sensor_type = cap[len("sense_"):]
                sensor_id = f"{robot_id}_{sensor_type}"
                try:
                    readings.append(
                        self.read_sensor(robot_id, sensor_type, sensor_id)
                    )
                except RuntimeError:
                    logger.warning("Skipping sensor %s — robot disconnected",
                                   sensor_id)
        return readings

    def get_cached_reading(self, robot_id: str,
                           sensor_id: str) -> Optional[SensorReading]:
        cache_key = f"{robot_id}:{sensor_id}"
        with self._lock:
            return self._cache.get(cache_key)

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "cached_readings": len(self._cache),
            }
