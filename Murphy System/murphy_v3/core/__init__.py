"""
Murphy v3.0 Core Module

Provides foundational services for the entire system:
- Configuration management
- Structured logging
- Exception handling
- Event bus
"""

from .config import settings, Settings
from .logging import get_logger, setup_logging
from .exceptions import (
    MurphyException,
    ValidationError,
    AuthenticationError,
    AuthorizationError,
    ExecutionError,
    IntegrationError,
    ConfigurationError,
)
from .events import event_bus, Event

__all__ = [
    # Configuration
    'settings',
    'Settings',
    
    # Logging
    'get_logger',
    'setup_logging',
    
    # Exceptions
    'MurphyException',
    'ValidationError',
    'AuthenticationError',
    'AuthorizationError',
    'ExecutionError',
    'IntegrationError',
    'ConfigurationError',
    
    # Events
    'event_bus',
    'Event',
]

__version__ = '3.0.0'
