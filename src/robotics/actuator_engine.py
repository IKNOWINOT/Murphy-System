"""
Unified actuator control engine across all robot platforms.
"""

import logging
import time
from threading import Lock
from typing import Any, Dict, List, Optional

from robotics.robot_registry import RobotRegistry
from robotics.robotics_models import ActuatorCommand, ActuatorResult, RobotStatus
try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)


class ActuatorEngine:
    """Unified actuator control engine across all robot platforms."""

    def __init__(self, registry: RobotRegistry) -> None:
        self._registry = registry
        self._command_log: List[ActuatorResult] = []
        self._lock = Lock()

    def execute(self, command: ActuatorCommand) -> ActuatorResult:
        """Execute an actuator command on any registered robot."""
        client = self._registry.get_client(command.robot_id)
        if client is None:
            raise ValueError(f"Unknown robot: {command.robot_id}")
        if client.status == RobotStatus.DISCONNECTED:
            raise RuntimeError(
                f"Robot {command.robot_id} is disconnected"
            )
        start = time.monotonic()
        result = client.execute_command(command)
        result.execution_time_seconds = time.monotonic() - start
        with self._lock:
            capped_append(self._command_log, result)
        return result

    def batch_execute(
        self, commands: List[ActuatorCommand]
    ) -> List[ActuatorResult]:
        """Execute multiple commands sequentially."""
        return [self.execute(cmd) for cmd in commands]

    def get_command_log(
        self, robot_id: Optional[str] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get recent command execution log entries."""
        with self._lock:
            entries = list(self._command_log)
        if robot_id is not None:
            entries = [e for e in entries if e.robot_id == robot_id]
        entries = entries[-limit:]
        return [e.model_dump() for e in entries]

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_commands_executed": len(self._command_log),
            }
