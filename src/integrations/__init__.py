"""
Integrations Package
External system integrations for the Murphy System Runtime.

World Model Connectors (20+ real API integrations):
  CRM, Email Marketing, Cloud Storage, Communication, Project Management,
  E-Commerce, Payments, Analytics, Social Media, Database, AI/ML,
  Monitoring, DNS/CDN, Market Data, Weather, Industrial/SCADA.
"""

from .integration_framework import (
    Integration,
    IntegrationFramework,
    IntegrationResult,
    IntegrationStatus,
    IntegrationType,
    create_integration,
    execute_call,
)
from .world_model_registry import WorldModelRegistry, get_registry

__all__ = [
    # Framework
    "IntegrationFramework",
    "Integration",
    "IntegrationResult",
    "IntegrationType",
    "IntegrationStatus",
    "create_integration",
    "execute_call",
    # World Model Registry
    "WorldModelRegistry",
    "get_registry",
]
