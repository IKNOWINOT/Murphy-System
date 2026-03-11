"""
CRM Module
============

Phase 8 of Monday.com feature parity for the Murphy System.

Copyright 2024 Inoni LLC – BSL-1.1
"""

__version__ = "0.1.0"
__codename__ = "CRM"

from .models import (
    ActivityType,
    CRMActivity,
    Contact,
    ContactType,
    Deal,
    DealStage,
    Pipeline,
    Stage,
)
from .crm_manager import CRMManager

try:
    from .api import create_crm_router
except Exception:  # pragma: no cover
    create_crm_router = None  # type: ignore[assignment]

__all__ = [
    "ActivityType",
    "CRMActivity",
    "Contact",
    "ContactType",
    "Deal",
    "DealStage",
    "Pipeline",
    "Stage",
    "CRMManager",
    "create_crm_router",
]
