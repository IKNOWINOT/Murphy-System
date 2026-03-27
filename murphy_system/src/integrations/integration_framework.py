"""
Integration Framework - Manage external system integrations
"""

import logging
import threading
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

try:
    from thread_safe_operations import CircuitBreaker, RateLimiter, ThreadSafeCounter, ThreadSafeDict
except ImportError:
    import threading as _fb_threading
    class CircuitBreaker:
        """Minimal fallback CircuitBreaker (pass-through, no tripping)."""
        def __init__(self, *args, **kwargs):
            pass
        def call(self, fn, *args, **kwargs):
            return fn(*args, **kwargs)
        @property
        def state(self):
            return "closed"
        def reset(self) -> None:
            pass
    class RateLimiter:
        """Minimal fallback RateLimiter (no limiting)."""
        def __init__(self, *args, **kwargs):
            pass
        def is_allowed(self, *args, **kwargs) -> bool:
            return True
        def acquire(self, *args, **kwargs) -> bool:
            return True
    class ThreadSafeCounter:
        """Minimal fallback ThreadSafeCounter."""
        def __init__(self, initial_value: int = 0):
            self._value = initial_value
            self._lock = _fb_threading.Lock()
        def increment(self, delta: int = 1) -> int:
            with self._lock:
                self._value += delta
                return self._value
        def decrement(self, delta: int = 1) -> int:
            with self._lock:
                self._value -= delta
                return self._value
        def get(self) -> int:
            with self._lock:
                return self._value
        def reset(self) -> int:
            with self._lock:
                self._value = 0
                return self._value
    class ThreadSafeDict:
        """Minimal fallback ThreadSafeDict."""
        def __init__(self):
            self._dict: dict = {}
            self._lock = _fb_threading.RLock()
        def get(self, key, default=None):
            with self._lock:
                return self._dict.get(key, default)
        def set(self, key, value) -> None:
            with self._lock:
                self._dict[key] = value
        def delete(self, key) -> bool:
            with self._lock:
                if key in self._dict:
                    del self._dict[key]
                    return True
                return False
        def keys(self):
            with self._lock:
                return list(self._dict.keys())
        def values(self):
            with self._lock:
                return list(self._dict.values())
        def items(self):
            with self._lock:
                return list(self._dict.items())
        def update(self, other: dict) -> None:
            with self._lock:
                self._dict.update(other)
        def clear(self) -> None:
            with self._lock:
                self._dict.clear()
        def get_dict(self) -> dict:
            with self._lock:
                return dict(self._dict)
        def __len__(self) -> int:
            with self._lock:
                return len(self._dict)
        def __contains__(self, key) -> bool:
            with self._lock:
                return key in self._dict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class IntegrationType(Enum):
    """Types of integrations"""
    HR = "hr"
    ERP = "erp"
    CRM = "crm"
    DATABASE = "database"
    API = "api"
    CUSTOM = "custom"


class IntegrationStatus(Enum):
    """Integration status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    CONNECTING = "connecting"
    DISCONNECTED = "disconnected"


class Integration:
    """External system integration"""

    def __init__(
        self,
        integration_id: Optional[str] = None,
        name: str = "",
        system_type: IntegrationType = IntegrationType.CUSTOM,
        connection_params: Optional[Dict] = None,
        authentication: Optional[Dict] = None,
        rate_limits: Optional[Dict] = None,
        endpoints: Optional[Dict] = None,
        metadata: Optional[Dict] = None
    ):
        self.integration_id = integration_id or str(uuid.uuid4())
        self.name = name
        self.system_type = system_type
        self.connection_params = connection_params or {}
        self.authentication = authentication or {}
        self.rate_limits = rate_limits or {}
        self.endpoints = endpoints or {}
        self.metadata = metadata or {}

        # Status
        self.status = IntegrationStatus.INACTIVE
        self.created_at = datetime.now(timezone.utc)
        self.last_connected_at: Optional[datetime] = None
        self.last_error: Optional[str] = None
        self.connection_attempts = 0
        self.successful_calls = 0
        self.failed_calls = 0

    def to_dict(self) -> Dict:
        """Convert integration to dictionary"""
        return {
            'integration_id': self.integration_id,
            'name': self.name,
            'system_type': self.system_type.value,
            'status': self.status.value,
            'created_at': self.created_at.isoformat(),
            'last_connected_at': self.last_connected_at.isoformat() if self.last_connected_at else None,
            'last_error': self.last_error,
            'connection_attempts': self.connection_attempts,
            'successful_calls': self.successful_calls,
            'failed_calls': self.failed_calls,
            'success_rate': self.successful_calls / (self.successful_calls + self.failed_calls)
                          if (self.successful_calls + self.failed_calls) > 0 else 0.0
        }


class IntegrationResult:
    """Result of integration call"""

    def __init__(
        self,
        success: bool,
        data: Any = None,
        error: Optional[str] = None,
        metadata: Optional[Dict] = None
    ):
        self.success = success
        self.data = data
        self.error = error
        self.metadata = metadata or {}
        self.timestamp = datetime.now(timezone.utc)

    def to_dict(self) -> Dict:
        """Convert result to dictionary"""
        return {
            'success': self.success,
            'data': self.data,
            'error': self.error,
            'metadata': self.metadata,
            'timestamp': self.timestamp.isoformat()
        }


class IntegrationFramework:
    """Framework for managing external system integrations"""

    def __init__(self):
        self.integrations: ThreadSafeDict = ThreadSafeDict()
        self.call_history: ThreadSafeDict = ThreadSafeDict()
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.rate_limiters: Dict[str, RateLimiter] = {}
        self._lock = threading.Lock()
        self._monitoring_active = False

    def register_integration(self, integration: Integration) -> str:
        """Register an integration"""
        integration_id = integration.integration_id

        # Create circuit breaker
        self.circuit_breakers[integration_id] = CircuitBreaker(
            failure_threshold=integration.rate_limits.get('failure_threshold', 5),
            recovery_timeout=integration.rate_limits.get('recovery_timeout', 60.0)
        )

        # Create rate limiter
        max_calls = integration.rate_limits.get('max_calls', 100)
        time_window = integration.rate_limits.get('time_window', 60.0)
        self.rate_limiters[integration_id] = RateLimiter(max_calls, time_window)

        # Store integration
        self.integrations.set(integration_id, integration)

        logger.info(f"Integration registered: {integration_id} - {integration.name}")
        return integration_id

    def unregister_integration(self, integration_id: str) -> bool:
        """Unregister an integration"""
        with self._lock:
            if integration_id in self.circuit_breakers:
                del self.circuit_breakers[integration_id]
            if integration_id in self.rate_limiters:
                del self.rate_limiters[integration_id]

            if self.integrations.delete(integration_id):
                logger.info(f"Integration unregistered: {integration_id}")
                return True
            return False

    def get_integration(self, integration_id: str) -> Optional[Integration]:
        """Get integration by ID"""
        return self.integrations.get(integration_id)

    def get_all_integrations(self) -> List[Dict]:
        """Get all integrations"""
        return [integration.to_dict() for integration in self.integrations.values()]

    def connect(self, integration_id: str) -> bool:
        """Connect to an integration"""
        integration = self.get_integration(integration_id)
        if not integration:
            return False

        try:
            integration.status = IntegrationStatus.CONNECTING
            integration.connection_attempts += 1

            # Simulate connection (override in specific integrations)
            connection_success = self._connect_to_system(integration)

            if connection_success:
                integration.status = IntegrationStatus.ACTIVE
                integration.last_connected_at = datetime.now(timezone.utc)
                integration.last_error = None
                logger.info(f"Connected to integration: {integration_id}")
                return True
            else:
                integration.status = IntegrationStatus.ERROR
                integration.last_error = "Connection failed"
                logger.error(f"Failed to connect to integration: {integration_id}")
                return False

        except Exception as exc:
            integration.status = IntegrationStatus.ERROR
            integration.last_error = str(exc)
            logger.error(f"Error connecting to integration {integration_id}: {exc}")
            return False

    def disconnect(self, integration_id: str) -> bool:
        """Disconnect from an integration"""
        integration = self.get_integration(integration_id)
        if not integration:
            return False

        integration.status = IntegrationStatus.DISCONNECTED
        logger.info(f"Disconnected from integration: {integration_id}")
        return True

    def execute_integration_call(
        self,
        integration_id: str,
        method: str,
        parameters: Optional[Dict] = None,
        retry_on_failure: bool = True
    ) -> IntegrationResult:
        """Execute an integration call"""
        integration = self.get_integration(integration_id)
        if not integration:
            return IntegrationResult(
                success=False,
                error=f"Integration not found: {integration_id}"
            )

        if integration.status != IntegrationStatus.ACTIVE:
            return IntegrationResult(
                success=False,
                error=f"Integration not active: {integration_id}"
            )

        # Check rate limit
        rate_limiter = self.rate_limiters.get(integration_id)
        if rate_limiter and not rate_limiter.acquire():
            return IntegrationResult(
                success=False,
                error="Rate limit exceeded"
            )

        # Execute with circuit breaker
        circuit_breaker = self.circuit_breakers.get(integration_id)

        def execute_call():
            return self._execute_call(integration, method, parameters)

        try:
            result = circuit_breaker.call(execute_call) if circuit_breaker else execute_call()

            integration.successful_calls += 1

            # Log call
            self._log_call(integration_id, method, result)

            return result

        except Exception as exc:
            logger.debug("Caught exception: %s", exc)
            integration.failed_calls += 1
            integration.last_error = str(exc)

            error_result = IntegrationResult(
                success=False,
                error=str(exc)
            )

            # Log failed call
            self._log_call(integration_id, method, error_result)

            return error_result

    def _connect_to_system(self, integration: Integration) -> bool:
        """Connect to external system (override in subclasses)"""
        # Default implementation - just simulate connection
        return True

    def _execute_call(
        self,
        integration: Integration,
        method: str,
        parameters: Optional[Dict] = None
    ) -> IntegrationResult:
        """Execute integration call (override in subclasses)"""
        # Default implementation - return success
        return IntegrationResult(
            success=True,
            data={'method': method, 'parameters': parameters}
        )

    def _log_call(self, integration_id: str, method: str, result: IntegrationResult) -> None:
        """Log integration call"""
        call_record = {
            'integration_id': integration_id,
            'method': method,
            'success': result.success,
            'error': result.error,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

        history_key = f"{integration_id}_{method}"
        current_history = self.call_history.get(history_key, [])
        current_history.append(call_record)
        self.call_history.set(history_key, current_history)

    def get_call_history(self, integration_id: str, method: Optional[str] = None, limit: int = 100) -> List[Dict]:
        """Get call history"""
        if method:
            history_key = f"{integration_id}_{method}"
            return self.call_history.get(history_key, [])[-limit:]

        # Get all history for integration
        all_history = []
        for key, history in self.call_history.items():
            if key.startswith(integration_id):
                all_history.extend(history)

        return all_history[-limit:]

    def get_integration_statistics(self, integration_id: str) -> Optional[Dict]:
        """Get integration statistics"""
        integration = self.get_integration(integration_id)
        if not integration:
            return None

        circuit_breaker = self.circuit_breakers.get(integration_id)
        rate_limiter = self.rate_limiters.get(integration_id)

        return {
            'integration_id': integration_id,
            'status': integration.status.value,
            'connection_attempts': integration.connection_attempts,
            'successful_calls': integration.successful_calls,
            'failed_calls': integration.failed_calls,
            'success_rate': integration.successful_calls / (integration.successful_calls + integration.failed_calls)
                          if (integration.successful_calls + integration.failed_calls) > 0 else 0.0,
            'circuit_breaker_state': circuit_breaker.get_state() if circuit_breaker else None,
            'circuit_breaker_failures': circuit_breaker.get_failure_count() if circuit_breaker else 0,
            'current_rate': rate_limiter.get_call_count() if rate_limiter else 0
        }

    def monitor_integrations(self, interval: float = 60.0) -> None:
        """Monitor integrations health"""
        self._monitoring_active = True

        def monitor_loop():
            while self._monitoring_active:
                for integration_id, integration in self.integrations.items():
                    if integration.status == IntegrationStatus.ACTIVE:
                        # Check if integration is still responsive
                        try:
                            result = self.execute_integration_call(
                                integration_id,
                                method='health_check',
                                parameters={}
                            )

                            if not result.success:
                                logger.warning(f"Integration health check failed: {integration_id}")

                        except Exception as exc:
                            logger.error(f"Error monitoring integration {integration_id}: {exc}")

                time.sleep(interval)

        import threading
        monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        monitor_thread.start()
        logger.info("Integration monitoring started")

    def stop_monitoring(self) -> None:
        """Stop integration monitoring"""
        self._monitoring_active = False
        logger.info("Integration monitoring stopped")


# Convenience functions

def create_integration(
    name: str,
    system_type: IntegrationType,
    connection_params: Optional[Dict] = None,
    **kwargs
) -> Integration:
    """Create an integration"""
    return Integration(
        name=name,
        system_type=system_type,
        connection_params=connection_params,
        **kwargs
    )


def execute_call(
    framework: IntegrationFramework,
    integration_id: str,
    method: str,
    parameters: Optional[Dict] = None
) -> Dict:
    """Execute an integration call"""
    result = framework.execute_integration_call(integration_id, method, parameters)
    return result.to_dict()
