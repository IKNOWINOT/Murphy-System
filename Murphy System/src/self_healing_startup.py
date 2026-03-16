"""
Self-Healing Startup — Register recovery handlers and wire EventBackbone.

Design Label: OBS-004-S — System Bootstrap
Owner: Platform Engineering

Call ``bootstrap_self_healing(event_backbone)`` once during system startup
to register all five concrete recovery procedures and connect the
SelfHealingCoordinator to the EventBackbone TASK_FAILED feed.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


def bootstrap_self_healing(event_backbone: Optional[Any] = None) -> Any:
    """Create, configure, and return a fully wired SelfHealingCoordinator.

    Registers all five top-observed failure-category recovery procedures:
      - LLM_PROVIDER_TIMEOUT
      - GATE_CONFIDENCE_TOO_LOW
      - EXTERNAL_API_UNAVAILABLE
      - SANDBOX_RESOURCE_EXCEEDED
      - AUTH_TOKEN_EXPIRED

    The coordinator is subscribed to TASK_FAILED events on *event_backbone*
    if one is provided.

    Returns the configured SelfHealingCoordinator instance.
    """
    from self_healing_coordinator import SelfHealingCoordinator, RecoveryProcedure
    from self_healing_handlers import (
        LLM_PROVIDER_TIMEOUT,
        GATE_CONFIDENCE_TOO_LOW,
        EXTERNAL_API_UNAVAILABLE,
        SANDBOX_RESOURCE_EXCEEDED,
        AUTH_TOKEN_EXPIRED,
        handle_llm_provider_timeout,
        handle_gate_confidence_too_low,
        handle_external_api_unavailable,
        handle_sandbox_resource_exceeded,
        handle_auth_token_expired,
    )

    coordinator = SelfHealingCoordinator(event_backbone=event_backbone)

    procedures = [
        RecoveryProcedure(
            procedure_id="recover-llm-timeout",
            category=LLM_PROVIDER_TIMEOUT,
            description=(
                "Retry with fallback LLM provider chain "
                "(OpenAI → Groq → Anthropic → local) using exponential backoff"
            ),
            handler=handle_llm_provider_timeout,
            max_attempts=5,
            cooldown_seconds=10.0,
        ),
        RecoveryProcedure(
            procedure_id="recover-gate-confidence",
            category=GATE_CONFIDENCE_TOO_LOW,
            description=(
                "Widen information search, inject additional context, "
                "and re-evaluate the gate with enriched signals"
            ),
            handler=handle_gate_confidence_too_low,
            max_attempts=3,
            cooldown_seconds=30.0,
        ),
        RecoveryProcedure(
            procedure_id="recover-external-api",
            category=EXTERNAL_API_UNAVAILABLE,
            description=(
                "Circuit breaker (CLOSED → OPEN → HALF_OPEN); "
                "queue request and retry after cooldown"
            ),
            handler=handle_external_api_unavailable,
            max_attempts=3,
            cooldown_seconds=15.0,
        ),
        RecoveryProcedure(
            procedure_id="recover-sandbox-resources",
            category=SANDBOX_RESOURCE_EXCEEDED,
            description=(
                "Scale sandbox memory/CPU/timeout limits and retry; "
                "fall back to chunked execution if scaled retry still fails"
            ),
            handler=handle_sandbox_resource_exceeded,
            max_attempts=3,
            cooldown_seconds=20.0,
        ),
        RecoveryProcedure(
            procedure_id="recover-auth-token",
            category=AUTH_TOKEN_EXPIRED,
            description=(
                "Refresh the expired credential from the credential store "
                "and retry the original request with the new token"
            ),
            handler=handle_auth_token_expired,
            max_attempts=3,
            cooldown_seconds=5.0,
        ),
    ]

    for proc in procedures:
        coordinator.register_procedure(proc)

    logger.info(
        "SelfHealingCoordinator bootstrapped with %d recovery procedures: %s",
        len(procedures),
        [p.category for p in procedures],
    )

    return coordinator
