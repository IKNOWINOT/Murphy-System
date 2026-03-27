"""
Founder Update Engine

Design Label: ARCH-007 — Founder Update Engine
Owner: Backend Team

Central system that monitors how Murphy updates itself, provides multiple
forms of recommendation for any subsystem, and coordinates maintenance
integrations.

Public exports:
  - RecommendationEngine / RecommendationType / RecommendationPriority / Recommendation
  - SubsystemRegistry / SubsystemInfo
  - UpdateCoordinator / MaintenanceWindow / UpdateRecord
  - SdkUpdateScanner / SdkScanReport / PackageScanRecord
  - AutoUpdateApplicator / ApplicationCycle / ApplicationRecord / ApplicationOutcome
  - BugResponseHandler / BugReport / BugResponse / BugSeverity / BugCategory
  - OperatingAnalysisDashboard / DashboardSnapshot / SubsystemHealthSummary

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from .auto_update_applicator import (
    ApplicationCycle,
    ApplicationOutcome,
    ApplicationRecord,
    AutoUpdateApplicator,
)
from .bug_response_handler import (
    BugCategory,
    BugReport,
    BugResponse,
    BugResponseHandler,
    BugSeverity,
)
from .digest_generator import (
    DigestPeriod,
    FounderDigest,
    FounderDigestGenerator,
)
from .operating_analysis_dashboard import (
    DashboardSnapshot,
    OperatingAnalysisDashboard,
    SubsystemHealthSummary,
)
from .recommendation_engine import (
    Recommendation,
    RecommendationEngine,
    RecommendationPriority,
    RecommendationType,
)
from .sdk_update_scanner import (
    PackageScanRecord,
    SdkScanReport,
    SdkUpdateScanner,
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
    # sdk_update_scanner
    "PackageScanRecord",
    "SdkScanReport",
    "SdkUpdateScanner",
    # auto_update_applicator
    "ApplicationCycle",
    "ApplicationOutcome",
    "ApplicationRecord",
    "AutoUpdateApplicator",
    # bug_response_handler
    "BugCategory",
    "BugReport",
    "BugResponse",
    "BugResponseHandler",
    "BugSeverity",
    # operating_analysis_dashboard
    "DashboardSnapshot",
    "OperatingAnalysisDashboard",
    "SubsystemHealthSummary",
    # digest_generator
    "DigestPeriod",
    "FounderDigest",
    "FounderDigestGenerator",
]
