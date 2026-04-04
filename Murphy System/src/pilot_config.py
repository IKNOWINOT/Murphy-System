# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Pilot Account Configuration — Murphy System

Defines the canonical pilot/founder account (cpost@murphy.systems) and the
routing table that wires every platform automation through that account.

All LCM automations, shadow agents, and module access are governed by the
constants defined here so that a single source of truth exists for the
bootstrap configuration.
"""
from __future__ import annotations

import os

PILOT_ACCOUNT: dict = {
    "email": os.environ.get("MURPHY_FOUNDER_EMAIL", ""),
    "name": os.environ.get("MURPHY_FOUNDER_NAME", ""),
    "role": "founder_admin",
    "org": "Inoni LLC",
    "automations_enabled": True,
    "lcm_enabled": True,
    "hitl_level": "graduated",  # Can auto-execute when confidence criteria are met
    "all_modules_visible": True,
}

# Every automation in the system routes through this account for piloting.
# shadow_agents lists the role slugs whose actions are mirrored to the pilot.
# modules lists the UI/API module slugs that are surfaced under this category.
PILOT_AUTOMATION_ROUTING: dict = {
    "sales": {
        "shadow_agents": [
            "chief_revenue_officer",
            "vp_sales",
            "partnership_manager",
        ],
    },
    "marketing": {
        "shadow_agents": ["vp_marketing"],
    },
    "engineering": {
        "shadow_agents": ["technical_operations"],
    },
    "research": {
        "shadow_agents": ["chief_research_officer"],
    },
    "communications": {
        "shadow_agents": ["ai_communications"],
    },
    "finance": {
        "modules": [
            "grant_wizard",
            "grant_dashboard",
            "financing_options",
        ],
    },
    "compliance": {
        "modules": ["compliance_dashboard"],
    },
    "onboarding": {
        "modules": [
            "onboarding_wizard",
            "task_catalog",
        ],
    },
}


def get_pilot_email() -> str:
    """Return the canonical pilot account email."""
    return PILOT_ACCOUNT["email"]


def is_pilot(email: str) -> bool:
    """Return True when *email* matches the pilot account."""
    return email.lower().strip() == PILOT_ACCOUNT["email"].lower()


def get_routing_for_category(category: str) -> dict:
    """Return the routing config for a given automation *category*.

    Returns an empty dict when the category is not registered.
    """
    return PILOT_AUTOMATION_ROUTING.get(category, {})
