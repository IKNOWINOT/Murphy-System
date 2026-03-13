"""
HTTP Adapter

Generic HTTP-based device adapter.

Communicates with devices via HTTP REST API.
"""

import hashlib
import json
import logging
import time
from typing import Dict

import requests

from ..adapter_contract import AdapterAPI, AdapterManifest
from ..execution_packet_extension import DeviceExecutionPacket

logger = logging.getLogger("adapter_framework.adapters.http_adapter")


class HTTPAdapter(AdapterAPI):
    """
    Generic HTTP adapter.

    Communicates with devices via HTTP REST API with endpoints:
    - GET /telemetry - Read telemetry
    - POST /command - Execute command
    - POST /emergency_stop - Emergency stop
    - GET /heartbeat - Heartbeat
    """

    def __init__(self, manifest: AdapterManifest, base_url: str, timeout: float = 5.0):
        """
        Initialize HTTP adapter.

        Args:
            manifest: Adapter manifest
            base_url: Base URL of device HTTP API
            timeout: Request timeout
        """
        super().__init__(manifest)

        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.session = requests.Session()

    def get_manifest(self) -> AdapterManifest:
        """Get adapter manifest"""
        return self.manifest

    def read_telemetry(self) -> Dict:
        """Read telemetry from device"""
        try:
            response = self.session.get(
                f"{self.base_url}/telemetry",
                timeout=self.timeout
            )
            response.raise_for_status()

            telemetry = response.json()

            # Validate telemetry
            is_valid, errors = self.manifest.telemetry_schema.validate(telemetry)
            if not is_valid:
                raise ValueError(f"Invalid telemetry: {errors}")

            return telemetry

        except Exception as exc:
            # Return error telemetry
            logger.debug("Caught exception: %s", exc)
            return {
                "timestamp": time.time(),
                "device_id": self.manifest.adapter_id,
                "state_vector": {},
                "error_codes": [f"telemetry_read_failed: {exc}"],
                "health": "failed",
                "checksum": hashlib.sha256(b"{}").hexdigest(),
                "sequence_number": 0
            }

    def execute_command(self, execution_packet: DeviceExecutionPacket) -> Dict:
        """Execute command on device"""
        # Check rate limit
        allowed, reason = self.check_rate_limit()
        if not allowed:
            return {
                "success": False,
                "error": reason
            }

        # Check safety limits
        is_safe, violations = self.validate_safety_limits(execution_packet.command)
        if not is_safe:
            return {
                "success": False,
                "error": f"Safety violation: {violations}"
            }

        # Send command to device
        try:
            response = self.session.post(
                f"{self.base_url}/command",
                json=execution_packet.command,
                timeout=self.timeout
            )
            response.raise_for_status()

            result = response.json()

            # Update command tracking
            self.last_command_time = time.time()
            self.command_count += 1

            # Read post-execution telemetry
            telemetry = self.read_telemetry()

            return {
                "success": result.get('success', True),
                "telemetry": telemetry,
                "error": result.get('error')
            }

        except Exception as exc:
            logger.debug("Caught exception: %s", exc)
            return {
                "success": False,
                "error": f"Command execution failed: {exc}"
            }

    def emergency_stop(self) -> bool:
        """Execute emergency stop"""
        try:
            response = self.session.post(
                f"{self.base_url}/emergency_stop",
                timeout=self.timeout
            )
            response.raise_for_status()

            self.is_emergency_stopped = True

            return True

        except Exception as exc:
            logger.info(f"[ERROR] Emergency stop failed: {exc}")
            return False

    def heartbeat(self) -> Dict:
        """Send heartbeat"""
        try:
            response = self.session.get(
                f"{self.base_url}/heartbeat",
                timeout=self.timeout
            )
            response.raise_for_status()

            return response.json()

        except Exception as exc:
            logger.debug("Caught exception: %s", exc)
            return {
                "alive": False,
                "error": str(exc)
            }
