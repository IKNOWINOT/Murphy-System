"""
Shutdown Manager
Handles graceful shutdown of the Murphy System
Ensures all resources are properly cleaned up
"""

import atexit
import logging
import signal
import sys
from typing import Callable, List, Optional

logger = logging.getLogger(__name__)


class ShutdownManager:
    """
    Manages graceful shutdown of system components.

    Features:
    - Registers cleanup handlers
    - Handles SIGTERM and SIGINT signals
    - Ensures proper resource cleanup
    - Prevents data loss on shutdown
    """

    def __init__(self):
        self.cleanup_handlers: List[Callable] = []
        self.is_shutting_down = False
        self._register_signal_handlers()

    def register_cleanup_handler(self, handler: Callable, name: Optional[str] = None):
        """
        Register a cleanup handler to be called on shutdown.

        Args:
            handler: Callable to execute on shutdown
            name: Optional name for the handler (for logging)
        """
        handler_name = name or handler.__name__
        self.cleanup_handlers.append((handler, handler_name))
        logger.info(f"Registered shutdown handler: {handler_name}")

    def _register_signal_handlers(self):
        """Register signal handlers for graceful shutdown"""
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        atexit.register(self._cleanup)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        signal_name = signal.Signals(signum).name
        logger.info(f"Received signal {signal_name}, initiating graceful shutdown...")
        self._cleanup()
        sys.exit(0)

    _CLEANUP_TIMEOUT = 5  # seconds per handler

    def _cleanup(self):
        """Execute all cleanup handlers"""
        if self.is_shutting_down:
            return  # Prevent multiple cleanup attempts

        self.is_shutting_down = True
        self._safe_log("🛑 Initiating Murphy System shutdown...")

        # Execute cleanup handlers in reverse order (LIFO)
        for handler, name in reversed(self.cleanup_handlers):
            try:
                self._safe_log(f"Executing cleanup handler: {name}")
                self._run_with_timeout(handler, name, self._CLEANUP_TIMEOUT)
                self._safe_log(f"✅ Cleanup handler completed: {name}")
            except Exception as exc:
                self._safe_log(f"❌ Cleanup handler failed: {name} - {exc}", level="error")

        self._safe_log("✅ Murphy System shutdown complete")

    @staticmethod
    def _safe_log(msg: str, level: str = "info"):
        """Log a message, falling back to stderr if the logger is broken."""
        try:
            log_fn = getattr(logger, level)
            # Check that all handlers can still write before calling
            for handler in logger.handlers + logging.getLogger().handlers:
                stream = getattr(handler, "stream", None)
                if stream is not None and getattr(stream, "closed", False):
                    raise ValueError("stream closed")
            log_fn(msg)
        except Exception:
            import sys
            try:
                print(msg, file=sys.stderr)
            except Exception as exc:  # noqa: BLE001
                logger.debug("stderr fallback also failed: %s", exc)

    def _run_with_timeout(self, handler, name, timeout):
        """Run a handler with a timeout to prevent hung shutdown."""
        import threading
        result = [None]
        exc_holder = [None]

        def target():
            try:
                handler()
            except Exception as exc:
                logger.debug("Caught exception: %s", exc)
                exc_holder[0] = exc

        t = threading.Thread(target=target, daemon=True)
        t.start()
        t.join(timeout)
        if t.is_alive():
            raise TimeoutError(f"Cleanup handler '{name}' timed out after {timeout}s")
        if exc_holder[0] is not None:
            raise exc_holder[0]

    def shutdown(self):
        """Manually trigger shutdown"""
        self._cleanup()


# Global shutdown manager instance
_shutdown_manager_instance = None


def get_shutdown_manager() -> ShutdownManager:
    """Get or create the global shutdown manager instance"""
    global _shutdown_manager_instance

    if _shutdown_manager_instance is None:
        _shutdown_manager_instance = ShutdownManager()

    return _shutdown_manager_instance


def register_cleanup(handler: Callable, name: Optional[str] = None):
    """
    Convenience function to register a cleanup handler.

    Args:
        handler: Callable to execute on shutdown
        name: Optional name for the handler
    """
    manager = get_shutdown_manager()
    manager.register_cleanup_handler(handler, name)
