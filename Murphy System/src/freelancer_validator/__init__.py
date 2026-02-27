"""
Freelancer Validator — External HITL via Freelance Platforms

Hires human validators on freelance platforms (Fiverr, Upwork, Freelancer.com)
for Human-in-the-Loop validation tasks. Enforces structured criteria, manages
organization budgets, and wires responses back into the HITL monitor.

Copyright © 2025 Inoni Limited Liability Company
"""

from .models import (
    FreelancerTask,
    FreelancerResponse,
    ValidationCriteria,
    CriterionItem,
    BudgetConfig,
    BudgetLedger,
    TaskStatus,
    PlatformType,
    ResponseVerdict,
)
from .platform_client import (
    FreelancerPlatformClient,
    FiverrClient,
    UpworkClient,
    GenericFreelancerClient,
)
from .budget_manager import BudgetManager
from .criteria_engine import CriteriaEngine
from .hitl_bridge import FreelancerHITLBridge

__all__ = [
    "FreelancerTask",
    "FreelancerResponse",
    "ValidationCriteria",
    "CriterionItem",
    "BudgetConfig",
    "BudgetLedger",
    "TaskStatus",
    "PlatformType",
    "ResponseVerdict",
    "FreelancerPlatformClient",
    "FiverrClient",
    "UpworkClient",
    "GenericFreelancerClient",
    "BudgetManager",
    "CriteriaEngine",
    "FreelancerHITLBridge",
]
