"""
Thread-safe registry of robots and their protocol clients.
"""

import logging
from threading import Lock
from typing import Any, Dict, List, Optional

from robotics.protocol_clients import ProtocolClient, create_client
from robotics.robotics_models import RobotConfig, RobotStatus, RobotType

logger = logging.getLogger(__name__)


class RobotRegistry:
    """Thread-safe registry of robots and their protocol clients."""

    def __init__(self) -> None:
        self._robots: Dict[str, RobotConfig] = {}
        self._clients: Dict[str, ProtocolClient] = {}
        self._lock = Lock()

    # -- CRUD ----------------------------------------------------------------

    def register(self, config: RobotConfig) -> bool:
        """Register a robot configuration. Returns False if ID already exists."""
        with self._lock:
            if config.robot_id in self._robots:
                return False
            self._robots[config.robot_id] = config
            return True

    def unregister(self, robot_id: str) -> bool:
        """Remove a robot (and its client) from the registry."""
        with self._lock:
            if robot_id not in self._robots:
                return False
            client = self._clients.pop(robot_id, None)
            if client and client.status != RobotStatus.DISCONNECTED:
                client.disconnect()
            del self._robots[robot_id]
            return True

    def get(self, robot_id: str) -> Optional[RobotConfig]:
        with self._lock:
            return self._robots.get(robot_id)

    def get_client(self, robot_id: str) -> Optional[ProtocolClient]:
        """Get or lazily create the protocol client for a robot."""
        with self._lock:
            if robot_id not in self._robots:
                return None
            if robot_id not in self._clients:
                self._clients[robot_id] = create_client(self._robots[robot_id])
            return self._clients[robot_id]

    def list_robots(self, robot_type: Optional[RobotType] = None) -> List[RobotConfig]:
        with self._lock:
            configs = list(self._robots.values())
        if robot_type is not None:
            configs = [c for c in configs if c.robot_type == robot_type]
        return configs

    # -- connection helpers --------------------------------------------------

    def connect(self, robot_id: str) -> bool:
        client = self.get_client(robot_id)
        if client is None:
            return False
        return client.connect()

    def disconnect(self, robot_id: str) -> bool:
        client = self.get_client(robot_id)
        if client is None:
            return False
        return client.disconnect()

    def emergency_stop_all(self) -> Dict[str, bool]:
        with self._lock:
            clients = dict(self._clients)
        results: Dict[str, bool] = {}
        for rid, client in clients.items():
            try:
                results[rid] = client.emergency_stop()
            except Exception as exc:
                logger.debug("Suppressed exception: %s", exc)
                logger.exception("Emergency stop failed for %s", rid)
                results[rid] = False
        return results

    # -- status --------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            total = len(self._robots)
            client_statuses = {
                rid: c.status.value for rid, c in self._clients.items()
            }
        return {
            "total_robots": total,
            "clients": client_statuses,
        }
