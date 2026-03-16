"""
Example Adapters

Provides reference implementations:
- MockAdapter: Simulated device for testing
- HTTPAdapter: Generic HTTP-based device adapter
"""

from .http_adapter import HTTPAdapter
from .mock_adapter import MockAdapter

__all__ = ['MockAdapter', 'HTTPAdapter']
