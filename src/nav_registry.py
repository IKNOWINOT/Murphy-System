# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Navigation Registry — Murphy System

Provides a canonical map from every existing module/page to a top-level
navigation category so that:

- The front-end can build a consistent nav bar from a single source of truth.
- The grant / financing system is always surfaced under the "Finance" category.
- Role-based filtering is possible via ``get_nav_for_account(email)``.

Usage::

    from nav_registry import get_nav_structure, get_nav_for_account

    nav = get_nav_structure()
    pilot_nav = get_nav_for_account(os.environ.get("MURPHY_FOUNDER_EMAIL", ""))
"""
from __future__ import annotations

import os
from typing import Any

# ---------------------------------------------------------------------------
# Module registry — every page/module mapped to (category, label, path)
# ---------------------------------------------------------------------------
_MODULES: list[dict[str, Any]] = [
    # ── Operations ──────────────────────────────────────────────────────────
    {"category": "Operations",    "label": "Dashboard",              "path": "/ui/dashboard",               "icon": "📊"},
    {"category": "Operations",    "label": "Workspace",              "path": "/ui/workspace",               "icon": "🖥"},
    {"category": "Operations",    "label": "Management",             "path": "/ui/management",              "icon": "⚙"},
    {"category": "Operations",    "label": "Calendar",               "path": "/ui/calendar",                "icon": "📅"},
    {"category": "Operations",    "label": "Task Catalog",           "path": "/ui/scheduler",            "icon": "📋"},
    {"category": "Operations",    "label": "Production Wizard",      "path": "/ui/production-wizard",       "icon": "🏭"},
    {"category": "Operations",    "label": "Partner Request",        "path": "/ui/partner-request",         "icon": "🤝"},
    {"category": "Operations",    "label": "Org Portal",             "path": "/ui/org-portal",              "icon": "🏢"},
    # ── Intelligence ────────────────────────────────────────────────────────
    {"category": "Intelligence",  "label": "Terminal",               "path": "/ui/swarm-command",                "icon": "⌨"},
    {"category": "Intelligence",  "label": "Terminal Unified",       "path": "/ui/dashboard",        "icon": "🖥"},
    {"category": "Intelligence",  "label": "Ambient Intelligence",   "path": "/ui/ambient-intelligence",                 "icon": "🌐"},
    {"category": "Intelligence",  "label": "Meeting Intelligence",   "path": "/ui/meeting-intelligence",   "icon": "🎙"},
    {"category": "Intelligence",  "label": "System Visualizer",      "path": "/ui/swarm-command",       "icon": "🔭"},
    {"category": "Intelligence",  "label": "Matrix Integration",     "path": "/ui/matrix-integration",      "icon": "🔢"},
    {"category": "Intelligence",  "label": "Research",               "path": "/ui/world-intelligence",                "icon": "🔬"},
    # ── Finance ─────────────────────────────────────────────────────────────
    {"category": "Finance",       "label": "Grant Wizard",           "path": "/ui/onboarding-wizard",            "icon": "🎯"},
    {"category": "Finance",       "label": "Grant Dashboard",        "path": "/ui/management",         "icon": "📊"},
    {"category": "Finance",       "label": "Grant Application",      "path": "/ui/org-portal",       "icon": "📝"},
    {"category": "Finance",       "label": "Financing Options",      "path": "/ui/financing-options",       "icon": "💰"},
    {"category": "Finance",       "label": "Wallet",                 "path": "/ui/wallet",                  "icon": "💳"},
    {"category": "Finance",       "label": "Pricing",                "path": "/ui/pricing",                 "icon": "🏷"},
    {"category": "Finance",       "label": "Paper Trading",          "path": "/ui/paper-trading-dashboard",           "icon": "📈"},
    {"category": "Finance",       "label": "Trading Dashboard",      "path": "/ui/trading-dashboard",       "icon": "📉"},
    {"category": "Finance",       "label": "Terminal Costs",         "path": "/ui/management",          "icon": "🧾"},
    # ── Control ─────────────────────────────────────────────────────────────
    {"category": "Control",       "label": "Dispatch",               "path": "/ui/swarm-command",                "icon": "🚀"},
    {"category": "Control",       "label": "Automation Scheduler",   "path": "/ui/automations",             "icon": "⏱"},
    {"category": "Control",       "label": "Terminal Architect",     "path": "/ui/dev-module",      "icon": "🏗"},
    {"category": "Control",       "label": "Terminal Orchestrator",  "path": "/ui/swarm-command",   "icon": "🎛"},
    {"category": "Control",       "label": "Murphy UI Integrated",   "path": "/ui/dashboard",    "icon": "🔗"},
    # ── Automation ──────────────────────────────────────────────────────────
    {"category": "Automation",    "label": "AI Workflows",           "path": "/ui/workflow-canvas",               "icon": "🤖"},
    {"category": "Automation",    "label": "Communication Hub",      "path": "/ui/communication-hub",       "icon": "📡"},
    {"category": "Automation",    "label": "Admin Panel",            "path": "/ui/admin-panel",                   "icon": "🛡"},
    {"category": "Automation",    "label": "All Hands",              "path": "/ui/management",               "icon": "📢"},
    {"category": "Automation",    "label": "Agent Monitor",          "path": "/ui/swarm-command",           "icon": "👁"},
    # ── Communication ───────────────────────────────────────────────────────
    {"category": "Communication", "label": "Blog",                   "path": "/ui/blog",                    "icon": "✍"},
    {"category": "Communication", "label": "Community Forum",        "path": "/ui/community-forum",               "icon": "💬"},
    {"category": "Communication", "label": "Careers",                "path": "/ui/careers",                 "icon": "💼"},
    {"category": "Communication", "label": "Docs",                   "path": "/ui/docs",                    "icon": "📖"},
    # ── Compliance ──────────────────────────────────────────────────────────
    {"category": "Compliance",    "label": "Compliance Dashboard",   "path": "/ui/compliance-dashboard",              "icon": "🛡"},
    {"category": "Compliance",    "label": "Legal",                  "path": "/ui/legal",                   "icon": "⚖"},
    {"category": "Compliance",    "label": "Privacy",                "path": "/ui/privacy",                 "icon": "🔒"},
    {"category": "Compliance",    "label": "Security",               "path": "/ui/security-ops",                "icon": "🔐"},
    # ── Onboarding ──────────────────────────────────────────────────────────
    {"category": "Onboarding",    "label": "Onboarding Wizard",      "path": "/ui/onboarding-wizard",              "icon": "🧙"},
    {"category": "Onboarding",    "label": "Demo",                   "path": "/ui/demo",                    "icon": "🎬"},
    {"category": "Onboarding",    "label": "Getting Started",        "path": "/ui/onboarding-wizard",         "icon": "🚦"},
    # ── Settings ────────────────────────────────────────────────────────────
    {"category": "Settings",      "label": "Account Settings",       "path": "/ui/management",              "icon": "👤"},
    {"category": "Settings",      "label": "Change Password",        "path": "/ui/change-password",         "icon": "🔑"},
    {"category": "Settings",      "label": "Reset Password",         "path": "/ui/reset-password",          "icon": "🔄"},
    {"category": "Settings",      "label": "Login",                  "path": "/ui/login",                   "icon": "🔓"},
]

# ---------------------------------------------------------------------------
# Role → set of visible categories
# ---------------------------------------------------------------------------
_ROLE_VISIBILITY: dict[str, set[str]] = {
    "founder_admin": {
        "Operations", "Intelligence", "Finance", "Control",
        "Automation", "Communication", "Compliance", "Onboarding", "Settings",
    },
    "admin": {
        "Operations", "Intelligence", "Finance", "Control",
        "Automation", "Compliance", "Onboarding", "Settings",
    },
    "worker": {
        "Operations", "Intelligence", "Onboarding", "Settings",
    },
    "viewer": {
        "Operations", "Intelligence",
    },
}

# Pilot account always sees everything
_PILOT_EMAIL = os.environ.get("MURPHY_FOUNDER_EMAIL", "")


def get_nav_structure() -> dict[str, list[dict[str, Any]]]:
    """Return the full navigation tree keyed by category name.

    Returns:
        A dict mapping category names to a list of module dicts with keys
        ``label``, ``path``, and ``icon``.
    """
    tree: dict[str, list[dict[str, Any]]] = {}
    for module in _MODULES:
        cat = module["category"]
        tree.setdefault(cat, []).append(
            {
                "label": module["label"],
                "path": module["path"],
                "icon": module["icon"],
            }
        )
    return tree


def get_nav_for_account(email: str, role: str = "viewer") -> dict[str, list[dict[str, Any]]]:
    """Return the nav tree filtered by account *email* and *role*.

    The pilot account (``cpost@murphy.systems``) always receives the full
    navigation regardless of *role*.

    Args:
        email: The logged-in user's email address.
        role: The user's role slug (e.g. ``"founder_admin"``, ``"admin"``,
              ``"worker"``, ``"viewer"``).  Defaults to ``"viewer"``.

    Returns:
        A subset of :func:`get_nav_structure` limited to the visible
        categories for the given role.
    """
    if email.lower().strip() == _PILOT_EMAIL:
        return get_nav_structure()

    visible = _ROLE_VISIBILITY.get(role, _ROLE_VISIBILITY["viewer"])
    return {
        cat: items
        for cat, items in get_nav_structure().items()
        if cat in visible
    }


def list_all_modules() -> list[dict[str, Any]]:
    """Return a flat list of all registered modules."""
    return list(_MODULES)


def get_categories() -> list[str]:
    """Return the ordered list of unique category names."""
    seen: list[str] = []
    for module in _MODULES:
        cat = module["category"]
        if cat not in seen:
            seen.append(cat)
    return seen
