# © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
"""
Grant Database & Eligibility Engine - Murphy System financing infrastructure.

Track A: Murphy/Inoni LLC internal R&D grant applications (SBIR, ARPA-E, etc.)
Track B: Customer-facing grant/incentive matching for automation projects.

Combines Phase 2 HITL Agentic Form-Filling System and Phase 4 Grant Submission Integration.

Copyright 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""
from __future__ import annotations

# Phase 2: HITL Agentic Form-Filling System
from src.billing.grants.grant_database import GRANT_PROGRAMS, GrantProgram
from src.billing.grants.eligibility_engine import EligibilityEngine
from src.billing.grants.session_manager import GrantSessionManager
from src.billing.grants.hitl_task_queue import HITLTaskQueue
from src.billing.grants.prerequisites_tracker import PrerequisitesTracker
from src.billing.grants.murphy_profiles import MurphyGrantProfile, ProfileFlavor

# Phase 3: Core models and eligibility engine
from src.billing.grants.models import (
    ApplicationField,
    ApplicationStatus,
    FieldStatus,
    Grant,
    GrantApplication,
    GrantCategory,
    GrantProfile,
    GrantSession,
    HitlTask,
    HitlTaskQueue,
    HitlTaskState,
    Prerequisite,
    PrerequisiteStatus,
    SavedFormData,
    SessionCredential,
)
from src.billing.grants.engine import GrantEligibilityEngine
from src.billing.grants.sessions import SessionManager

__all__ = [
    # Phase 2 exports
    "GRANT_PROGRAMS",
    "GrantProgram",
    "EligibilityEngine",
    "GrantSessionManager",
    "HITLTaskQueue",
    "PrerequisitesTracker",
    "MurphyGrantProfile",
    "ProfileFlavor",
    # Phase 3 exports
    "Grant",
    "GrantCategory",
    "GrantProfile",
    "GrantSession",
    "SessionCredential",
    "SavedFormData",
    "GrantApplication",
    "ApplicationField",
    "ApplicationStatus",
    "FieldStatus",
    "HitlTask",
    "HitlTaskQueue",
    "HitlTaskState",
    "Prerequisite",
    "PrerequisiteStatus",
    "GrantEligibilityEngine",
    "SessionManager",
]
