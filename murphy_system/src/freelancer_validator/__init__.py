"""
Freelancer Validator — External HITL via Freelance Platforms

Hires human validators on freelance platforms (Fiverr, Upwork, Freelancer.com)
for Human-in-the-Loop validation tasks. Enforces structured criteria, manages
organization budgets, verifies validator credentials against public records,
and wires responses back into the HITL monitor.

Copyright © 2025 Inoni Limited Liability Company
"""

from .budget_manager import BudgetManager
from .credential_verifier import CredentialVerifier
from .criteria_engine import CriteriaEngine
from .hitl_bridge import FreelancerHITLBridge
from .models import (
    BudgetConfig,
    BudgetLedger,
    CertificationType,
    ComplaintRecord,
    Credential,
    CredentialRequirement,
    CredentialStatus,
    CredentialVerificationResult,
    CriterionItem,
    FreelancerResponse,
    FreelancerTask,
    PlatformType,
    ResponseVerdict,
    TaskStatus,
    ValidationCriteria,
    ValidatorCredentialProfile,
)
from .platform_client import (
    FiverrClient,
    FreelancerPlatformClient,
    GenericFreelancerClient,
    UpworkClient,
)

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
    "CertificationType",
    "Credential",
    "CredentialRequirement",
    "CredentialStatus",
    "CredentialVerificationResult",
    "ComplaintRecord",
    "ValidatorCredentialProfile",
    "FreelancerPlatformClient",
    "FiverrClient",
    "UpworkClient",
    "GenericFreelancerClient",
    "BudgetManager",
    "CriteriaEngine",
    "CredentialVerifier",
    "FreelancerHITLBridge",
]
