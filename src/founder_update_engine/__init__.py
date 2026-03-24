"""
Founder Update Engine

Design Label: ARCH-007 — Founder Update Engine
Owner: Backend Team

Central system that monitors how Murphy updates itself, provides multiple
forms of recommendation for any subsystem, and coordinates maintenance
integrations.

Public exports:
  - RecommendationEngine
  - RecommendationType
  - RecommendationPriority
  - Recommendation
  - SubsystemRegistry
  - SubsystemInfo
  - UpdateCoordinator
  - MaintenanceWindow
  - UpdateRecord

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from .recommendation_engine import (
    Recommendation,
    RecommendationEngine,
    RecommendationPriority,
    RecommendationType,
)
from .subsystem_registry import (
    HEALTH_DEGRADED,
    HEALTH_FAILED,
    HEALTH_HEALTHY,
    HEALTH_UNKNOWN,
    SubsystemInfo,
    SubsystemRegistry,
)
from .update_coordinator import (
    MaintenanceWindow,
    UpdateCoordinator,
    UpdateRecord,
)

__all__ = [
    # recommendation_engine
    "Recommendation",
    "RecommendationEngine",
    "RecommendationPriority",
    "RecommendationType",
    # subsystem_registry
    "HEALTH_DEGRADED",
    "HEALTH_FAILED",
    "HEALTH_HEALTHY",
    "HEALTH_UNKNOWN",
    "SubsystemInfo",
    "SubsystemRegistry",
    # update_coordinator
    "MaintenanceWindow",
    "UpdateCoordinator",
    "UpdateRecord",
]
