# Copyright 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Module: errors/codes.py
Subsystem: Error Handling
Purpose: MURPHY-E error code definitions organised by subsystem.
Status: Production

Error namespace:
    MURPHY-E0xx  Core / Boot
    MURPHY-E1xx  Authentication / Authorisation
    MURPHY-E2xx  API / Request handling
    MURPHY-E3xx  Business logic (marketplace, billing, trading)
    MURPHY-E4xx  Integration (LLM, platform connectors)
    MURPHY-E5xx  Data / Persistence
    MURPHY-E6xx  Orchestration / Workflow
    MURPHY-E7xx  UI / Frontend
    MURPHY-E8xx  Infrastructure (Docker, K8s, monitoring)
    MURPHY-E9xx  Reserved / Internal
"""
from __future__ import annotations

from enum import Enum


class ErrorCode(str, Enum):
    """Every Murphy error code lives here."""

    # --- E0xx: Core / Boot -------------------------------------------------
    E001 = "MURPHY-E001"  # Generic internal error
    E002 = "MURPHY-E002"  # State operation failed (StateError)
    E003 = "MURPHY-E003"  # Configuration not loaded (NotConfiguredError)
    E004 = "MURPHY-E004"  # Stability violation (StabilityViolation)
    E005 = "MURPHY-E005"  # Runaway loop detected (RunawayLoopError)

    # --- E1xx: Authentication / Authorisation ------------------------------
    E100 = "MURPHY-E100"  # Generic auth failure
    E101 = "MURPHY-E101"  # Authentication failed (AuthError)
    E102 = "MURPHY-E102"  # Signup validation failed (SignupError)
    E103 = "MURPHY-E103"  # Tenant access denied (TenantAccessError)

    # --- E2xx: API / Request handling --------------------------------------
    E200 = "MURPHY-E200"  # Generic request error
    E201 = "MURPHY-E201"  # Input validation failed (ValidationError - hardening)
    E202 = "MURPHY-E202"  # Injection attempt detected (InjectionAttemptError)
    E203 = "MURPHY-E203"  # Output validation failed (ValidationError - llm_output)
    E204 = "MURPHY-E204"  # Approval not permitted (ApprovalError)

    # --- E3xx: Business logic ----------------------------------------------
    E300 = "MURPHY-E300"  # Generic business-logic error
    E301 = "MURPHY-E301"  # Marketplace validation (MarketplaceError)
    E302 = "MURPHY-E302"  # Sweep failure (SweepError)
    E303 = "MURPHY-E303"  # Circular dependency (CircularDependencyError)
    E304 = "MURPHY-E304"  # Task not found (TaskNotFoundError)
    E305 = "MURPHY-E305"  # Manifest validation (ManifestValidationError)

    # --- E4xx: Integration (LLM, platform connectors) ----------------------
    E400 = "MURPHY-E400"  # Generic integration error
    E401 = "MURPHY-E401"  # LLM response wiring (LLMResponseWiringError)
    E402 = "MURPHY-E402"  # Large Action Model (LAMError)
    E403 = "MURPHY-E403"  # Matrix client error (MatrixClientError)

    # --- E5xx: Data / Persistence ------------------------------------------
    E500 = "MURPHY-E500"  # Generic data error

    # --- E6xx: Orchestration / Workflow ------------------------------------
    E600 = "MURPHY-E600"  # Generic orchestration error
    E601 = "MURPHY-E601"  # Packet compilation (PacketCompilationError)
    E602 = "MURPHY-E602"  # Module compilation (CompilationError)

    # --- E7xx: UI / Frontend -----------------------------------------------
    E700 = "MURPHY-E700"  # Generic UI error

    # --- E8xx: Infrastructure ----------------------------------------------
    E800 = "MURPHY-E800"  # Generic infrastructure error

    # --- E9xx: Reserved / Internal -----------------------------------------
    E999 = "MURPHY-E999"  # Unclassified internal error


# Human-readable subsystem range descriptions.
SUBSYSTEM_RANGES: dict[str, str] = {
    "E0xx": "Core / Boot",
    "E1xx": "Authentication / Authorisation",
    "E2xx": "API / Request handling",
    "E3xx": "Business logic (marketplace, billing, trading)",
    "E4xx": "Integration (LLM, platform connectors)",
    "E5xx": "Data / Persistence",
    "E6xx": "Orchestration / Workflow",
    "E7xx": "UI / Frontend",
    "E8xx": "Infrastructure (Docker, K8s, monitoring)",
    "E9xx": "Reserved / Internal",
}
