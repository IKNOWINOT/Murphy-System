"""
Safety Hooks & Murphy Coupling

Integrates adapter safety with Murphy System control plane.

Features:
- Heartbeat watchdog (auto-freeze on missed heartbeat)
- Emergency stop (immediate freeze signal to orchestrator)
- Error code mapping (raises Murphy index, decays authority)
"""

import logging
import time
from threading import Event, Thread
from typing import Callable, Dict, List, Optional

import requests

logger = logging.getLogger("adapter_framework.safety_hooks")


class HeartbeatWatchdog:
    """
    Monitors adapter heartbeats and triggers freeze on timeout.

    CRITICAL: If heartbeat missed, system MUST freeze execution.
    """

    def __init__(
        self,
        adapter_id: str,
        heartbeat_interval_seconds: float = 5.0,
        timeout_seconds: float = 15.0,
        on_timeout: Optional[Callable] = None
    ):
        """
        Initialize watchdog.

        Args:
            adapter_id: Adapter ID to monitor
            heartbeat_interval_seconds: Expected heartbeat interval
            timeout_seconds: Timeout before triggering freeze
            on_timeout: Callback on timeout
        """
        self.adapter_id = adapter_id
        self.heartbeat_interval = heartbeat_interval_seconds
        self.timeout = timeout_seconds
        self.on_timeout = on_timeout

        self.last_heartbeat = time.time()
        self.is_running = False
        self.stop_event = Event()
        self.thread = None
        self.timeout_count = 0

    def heartbeat(self):
        """Record heartbeat"""
        self.last_heartbeat = time.time()

    def start(self):
        """Start watchdog"""
        if self.is_running:
            return

        self.is_running = True
        self.stop_event.clear()
        self.thread = Thread(target=self._monitor, daemon=True)
        self.thread.start()

        logger.info(f"[WATCHDOG] Started for {self.adapter_id}")

    def stop(self):
        """Stop watchdog"""
        self.is_running = False
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=1.0)

        logger.info(f"[WATCHDOG] Stopped for {self.adapter_id}")

    def _monitor(self):
        """Monitor heartbeat"""
        while self.is_running and not self.stop_event.is_set():
            # Check time since last heartbeat
            time_since_heartbeat = time.time() - self.last_heartbeat

            if time_since_heartbeat > self.timeout:
                # TIMEOUT - trigger freeze
                self.timeout_count += 1
                logger.info(f"[WATCHDOG] TIMEOUT for {self.adapter_id} ({time_since_heartbeat:.1f}s > {self.timeout}s)")

                if self.on_timeout:
                    self.on_timeout(self.adapter_id, time_since_heartbeat)

                # Reset to avoid repeated triggers
                self.last_heartbeat = time.time()

            # Sleep
            self.stop_event.wait(self.heartbeat_interval)

    def get_status(self) -> Dict:
        """Get watchdog status"""
        return {
            "adapter_id": self.adapter_id,
            "is_running": self.is_running,
            "last_heartbeat": self.last_heartbeat,
            "time_since_heartbeat": time.time() - self.last_heartbeat,
            "timeout_count": self.timeout_count
        }


class EmergencyStop:
    """
    Emergency stop coordinator.

    Sends immediate freeze signal to Execution Orchestrator.
    """

    def __init__(self, orchestrator_url: str = "http://localhost:8058"):
        """
        Initialize emergency stop.

        Args:
            orchestrator_url: Execution Orchestrator URL
        """
        self.orchestrator_url = orchestrator_url
        self.stop_history = []

    def trigger(self, adapter_id: str, reason: str) -> bool:
        """
        Trigger emergency stop.

        Args:
            adapter_id: Adapter ID
            reason: Reason for stop

        Returns:
            True if successful
        """
        logger.info(f"[EMERGENCY STOP] Adapter {adapter_id}: {reason}")

        # Send freeze signal to orchestrator
        try:
            response = requests.post(
                f"{self.orchestrator_url}/control-signal",
                json={
                    "mode": "emergency",
                    "allow_agent_spawn": False,
                    "allow_gate_synthesis": False,
                    "allow_planning": False,
                    "allow_execution": False,
                    "require_verification": True,
                    "require_deterministic": True,
                    "max_authority": "none",
                    "timestamp": time.time(),
                    "cycle_id": 0,
                    "reason": f"Emergency stop: {adapter_id} - {reason}"
                },
                timeout=5.0
            )

            success = response.status_code == 200

        except Exception as exc:
            logger.info(f"[ERROR] Failed to send emergency stop signal: {exc}")
            success = False

        # Record
        self.stop_history.append({
            "timestamp": time.time(),
            "adapter_id": adapter_id,
            "reason": reason,
            "success": success
        })

        return success

    def get_history(self) -> List[Dict]:
        """Get emergency stop history"""
        return self.stop_history


class ErrorCodeMapper:
    """
    Maps device error codes to Murphy index increases and authority decay.

    Couples adapter errors to Control Plane stability metrics.
    """

    # Error severity levels
    ERROR_SEVERITY = {
        "communication_lost": 0.5,
        "checksum_failed": 0.4,
        "temperature_exceeded": 0.6,
        "force_exceeded": 0.7,
        "velocity_exceeded": 0.6,
        "position_error": 0.3,
        "sensor_failure": 0.5,
        "actuator_failure": 0.7,
        "power_failure": 0.8,
        "emergency_stop": 0.9,
        "unknown_error": 0.3
    }

    def __init__(self, confidence_engine_url: str = "http://localhost:8055"):
        """
        Initialize error mapper.

        Args:
            confidence_engine_url: Confidence Engine URL
        """
        self.confidence_engine_url = confidence_engine_url
        self.error_history = []

    def map_error(self, adapter_id: str, error_codes: List[str]) -> Dict:
        """
        Map error codes to Murphy index increase.

        Args:
            adapter_id: Adapter ID
            error_codes: List of error codes

        Returns:
            Mapping result with murphy_increase and authority_decay
        """
        if not error_codes:
            return {
                "murphy_increase": 0.0,
                "authority_decay": 0.0
            }

        # Calculate Murphy index increase
        murphy_increase = 0.0
        for error_code in error_codes:
            severity = self.ERROR_SEVERITY.get(error_code, self.ERROR_SEVERITY["unknown_error"])
            murphy_increase += severity

        # Cap at 1.0
        murphy_increase = min(murphy_increase, 1.0)

        # Authority decay proportional to Murphy increase
        authority_decay = murphy_increase * 0.5  # 50% of Murphy increase

        # Record
        self.error_history.append({
            "timestamp": time.time(),
            "adapter_id": adapter_id,
            "error_codes": error_codes,
            "murphy_increase": murphy_increase,
            "authority_decay": authority_decay
        })

        logger.info(f"[ERROR MAPPING] {adapter_id}: {error_codes} -> Murphy +{murphy_increase:.2f}, Authority -{authority_decay:.2f}")

        return {
            "murphy_increase": murphy_increase,
            "authority_decay": authority_decay
        }

    def get_history(self) -> List[Dict]:
        """Get error mapping history"""
        return self.error_history


class SafetyHooks:
    """
    Integrates all safety hooks for adapter framework.

    Coordinates:
    - Heartbeat monitoring
    - Emergency stops
    - Error code mapping
    - Murphy coupling
    """

    def __init__(
        self,
        orchestrator_url: str = "http://localhost:8058",
        confidence_engine_url: str = "http://localhost:8055"
    ):
        """
        Initialize safety hooks.

        Args:
            orchestrator_url: Execution Orchestrator URL
            confidence_engine_url: Confidence Engine URL
        """
        self.watchdogs: Dict[str, HeartbeatWatchdog] = {}
        self.emergency_stop = EmergencyStop(orchestrator_url)
        self.error_mapper = ErrorCodeMapper(confidence_engine_url)

    def register_adapter(
        self,
        adapter_id: str,
        heartbeat_interval: float = 5.0,
        timeout: float = 15.0
    ):
        """
        Register adapter for monitoring.

        Args:
            adapter_id: Adapter ID
            heartbeat_interval: Expected heartbeat interval
            timeout: Timeout before freeze
        """
        # Create watchdog
        watchdog = HeartbeatWatchdog(
            adapter_id,
            heartbeat_interval,
            timeout,
            on_timeout=self._on_heartbeat_timeout
        )

        self.watchdogs[adapter_id] = watchdog
        watchdog.start()

        logger.info(f"[SAFETY] Registered {adapter_id} for monitoring")

    def heartbeat(self, adapter_id: str):
        """Record heartbeat for adapter"""
        if adapter_id in self.watchdogs:
            self.watchdogs[adapter_id].heartbeat()

    def handle_error(self, adapter_id: str, error_codes: List[str]) -> Dict:
        """
        Handle adapter errors.

        Args:
            adapter_id: Adapter ID
            error_codes: Error codes

        Returns:
            Mapping result
        """
        # Map errors to Murphy/authority
        mapping = self.error_mapper.map_error(adapter_id, error_codes)

        # Check for critical errors
        critical_errors = [
            "communication_lost",
            "power_failure",
            "emergency_stop",
            "actuator_failure"
        ]

        has_critical = any(e in error_codes for e in critical_errors)

        if has_critical:
            # Trigger emergency stop
            self.emergency_stop.trigger(adapter_id, f"Critical errors: {error_codes}")

        return mapping

    def _on_heartbeat_timeout(self, adapter_id: str, time_since: float):
        """Handle heartbeat timeout"""
        # Trigger emergency stop
        self.emergency_stop.trigger(
            adapter_id,
            f"Heartbeat timeout ({time_since:.1f}s)"
        )

    def get_status(self) -> Dict:
        """Get safety hooks status"""
        return {
            "watchdogs": {
                adapter_id: watchdog.get_status()
                for adapter_id, watchdog in self.watchdogs.items()
            },
            "emergency_stops": len(self.emergency_stop.get_history()),
            "error_mappings": len(self.error_mapper.get_history())
        }

    def shutdown(self):
        """Shutdown all safety hooks"""
        for watchdog in self.watchdogs.values():
            watchdog.stop()

        logger.info("[SAFETY] All watchdogs stopped")
