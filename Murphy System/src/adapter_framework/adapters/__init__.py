"""
Example Adapters

Provides reference implementations:
- MockAdapter: Simulated device for testing
- HTTPAdapter: Generic HTTP-based device adapter
"""

from .mock_adapter import MockAdapter
from .http_adapter import HTTPAdapter

__all__ = ['MockAdapter', 'HTTPAdapter']
