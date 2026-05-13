# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Navigation Registry — Murphy System

Canonical map of every live module/page to its department category.
Mirrors the department structure in static/murphy-nav.js.

Usage:
    from nav_registry import get_nav_structure, get_nav_for_account
"""
from __future__ import annotations
import os
from typing import Any

_MODULES: list[dict[str, Any]] = [
    # ── AI Systems ───────────────────────────────────────────────────────────
    {"category": "AI Systems",   "label": "Swarm Command",        "path": "/ui/swarm-command",        "icon": "🧠"},
    {"category": "AI Systems",   "label": "Chain Center",         "path": "/ui/chain-center",         "icon": "🔗"},
    {"category": "AI Systems",   "label": "Ambient Intelligence", "path": "/ui/ambient",              "icon": "🌐"},
    {"category": "AI Systems",   "label": "World Intelligence",   "path": "/ui/world-intelligence",   "icon": "🌍"},
    {"category": "AI Systems",   "label": "Terminal",             "path": "/ui/terminal",             "icon": "⌨"},
    {"category": "AI Systems",   "label": "Terminal Unified",     "path": "/ui/terminal-unified",     "icon": "🖥"},
    {"category": "AI Systems",   "label": "System Visualizer",    "path": "/ui/system-visualizer",    "icon": "🔭"},
    {"category": "AI Systems",   "label": "Self Healing",         "path": "/ui/self-healing",         "icon": "🛠"},
    {"category": "AI Systems",   "label": "Self Vision",          "path": "/ui/self-vision",          "icon": "👁"},
    {"category": "AI Systems",   "label": "Dispatch",             "path": "/ui/dispatch",             "icon": "📡"},
    {"category": "AI Systems",   "label": "Meeting Intelligence", "path": "/ui/meeting-intelligence", "icon": "🎙"},
    # ── Org & People ─────────────────────────────────────────────────────────
    {"category": "Org & People", "label": "Org Chart",            "path": "/ui/orgchart",             "icon": "🗂"},
    {"category": "Org & People", "label": "Org Portal",           "path": "/ui/org-portal",           "icon": "🏢"},
    {"category": "Org & People", "label": "All Hands",            "path": "/ui/all-hands",            "icon": "📢"},
    {"category": "Org & People", "label": "Agent Monitor",        "path": "/ui/agent-monitor",        "icon": "👁"},
    {"category": "Org & People", "label": "Management",           "path": "/ui/management",           "icon": "📋"},
    {"category": "Org & People", "label": "Careers",              "path": "/ui/careers",              "icon": "💼"},
    {"category": "Org & People", "label": "Onboarding Wizard",    "path": "/ui/onboarding",           "icon": "🧙"},
    {"category": "Org & People", "label": "Getting Started",      "path": "/ui/getting-started",      "icon": "🚦"},
    # ── Operations ───────────────────────────────────────────────────────────
    {"category": "Operations",   "label": "Dashboard",            "path": "/ui/dashboard",            "icon": "📊"},
    {"category": "Operations",   "label": "Ops Center",           "path": "/ui/ops-center",           "icon": "🏭"},
    {"category": "Operations",   "label": "Automations",          "path": "/ui/automations",          "icon": "⏱"},
    {"category": "Operations",   "label": "Workflows",            "path": "/ui/workflows",            "icon": "🤖"},
    {"category": "Operations",   "label": "Task Catalog",         "path": "/ui/task-catalog",         "icon": "📋"},
    {"category": "Operations",   "label": "Calendar",             "path": "/ui/calendar",             "icon": "📅"},
    {"category": "Operations",   "label": "Production Wizard",    "path": "/ui/production-wizard",    "icon": "🏭"},
    {"category": "Operations",   "label": "Workspace",            "path": "/ui/workspace",            "icon": "🖥"},
    # ── Sales & CRM ──────────────────────────────────────────────────────────
    {"category": "Sales & CRM",  "label": "CRM",                  "path": "/ui/crm",                  "icon": "📇"},
    {"category": "Sales & CRM",  "label": "HITL Dashboard",       "path": "/ui/hitl-dashboard",       "icon": "✅"},
    {"category": "Sales & CRM",  "label": "Book Audit",           "path": "/book",                    "icon": "📅"},
    {"category": "Sales & CRM",  "label": "Pricing",              "path": "/ui/pricing",              "icon": "🏷"},
    {"category": "Sales & CRM",  "label": "Partner Request",      "path": "/ui/partner-request",      "icon": "🤝"},
    {"category": "Sales & CRM",  "label": "Demo",                 "path": "/ui/demo",                 "icon": "🎬"},
    {"category": "Sales & CRM",  "label": "Resume",               "path": "/ui/resume",               "icon": "📄"},
    {"category": "Sales & CRM",  "label": "How We Work",          "path": "/how-we-work",             "icon": "⚙"},
    # ── Finance ──────────────────────────────────────────────────────────────
    {"category": "Finance",      "label": "Grant Wizard",         "path": "/ui/grant-wizard",         "icon": "🎯"},
    {"category": "Finance",      "label": "Grant Dashboard",      "path": "/ui/grant-dashboard",      "icon": "📊"},
    {"category": "Finance",      "label": "Grant Application",    "path": "/ui/grant-application",    "icon": "📝"},
    {"category": "Finance",      "label": "Financing Options",    "path": "/ui/financing-options",    "icon": "💰"},
    {"category": "Finance",      "label": "Wallet",               "path": "/ui/wallet",               "icon": "💳"},
    {"category": "Finance",      "label": "ROI Calendar",         "path": "/ui/roi-calendar",         "icon": "📅"},
    {"category": "Finance",      "label": "Paper Trading",        "path": "/ui/paper-trading",        "icon": "📈"},
    {"category": "Finance",      "label": "Terminal Costs",       "path": "/ui/terminal-costs",       "icon": "🧾"},
    # ── Compliance ───────────────────────────────────────────────────────────
    {"category": "Compliance",   "label": "Compliance Dashboard", "path": "/ui/compliance",           "icon": "🛡"},
    {"category": "Compliance",   "label": "Security",             "path": "/ui/security",             "icon": "🔐"},
    {"category": "Compliance",   "label": "Security Ops",         "path": "/ui/security-ops",         "icon": "🔒"},
    {"category": "Compliance",   "label": "Legal",                "path": "/ui/legal",                "icon": "⚖"},
    {"category": "Compliance",   "label": "Privacy",              "path": "/ui/privacy",              "icon": "🔒"},
    {"category": "Compliance",   "label": "Admin Panel",          "path": "/ui/admin",                "icon": "🛡"},
    # ── Build ─────────────────────────────────────────────────────────────────
    {"category": "Build",        "label": "Forge",                "path": "/ui/forge",                "icon": "🔨"},
    {"category": "Build",        "label": "Game Studio",          "path": "/ui/game-studio",          "icon": "🎮"},
    {"category": "Build",        "label": "Terminal Architect",   "path": "/ui/terminal-architect",   "icon": "🏗"},
    {"category": "Build",        "label": "Orchestrator",         "path": "/ui/terminal-orchestrator","icon": "🎛"},
    {"category": "Build",        "label": "Research",             "path": "/ui/research",             "icon": "🔬"},
    {"category": "Build",        "label": "Communication Hub",    "path": "/ui/communication-hub",    "icon": "📡"},
    {"category": "Build",        "label": "Matrix Integration",   "path": "/ui/matrix-integration",   "icon": "🔢"},
    # ── Settings ──────────────────────────────────────────────────────────────
    {"category": "Settings",     "label": "Account Settings",     "path": "/ui/management",           "icon": "👤"},
    {"category": "Settings",     "label": "Change Password",      "path": "/ui/change-password",      "icon": "🔑"},
    {"category": "Settings",     "label": "Docs",                 "path": "/ui/docs",                 "icon": "📖"},
    {"category": "Settings",     "label": "Community",            "path": "/ui/community",            "icon": "💬"},
    {"category": "Settings",     "label": "Blog",                 "path": "/ui/blog",                 "icon": "✍"},
]

_CATEGORY_ORDER = [
    "AI Systems", "Org & People", "Operations", "Sales & CRM",
    "Finance", "Compliance", "Build", "Settings",
]

_ROLE_VISIBILITY: dict[str, set[str]] = {
    "founder_admin": set(_CATEGORY_ORDER),
    "admin":         set(_CATEGORY_ORDER),
    "pilot":         set(_CATEGORY_ORDER),
    "user":          {"Operations", "Sales & CRM", "Finance", "Onboarding", "Settings"},
    "guest":         {"Onboarding"},
}


def get_nav_structure() -> list[dict[str, Any]]:
    """Return full nav grouped by category in canonical order."""
    groups: dict[str, list[dict[str, Any]]] = {c: [] for c in _CATEGORY_ORDER}
    for m in _MODULES:
        cat = m["category"]
        if cat in groups:
            groups[cat].append({"label": m["label"], "path": m["path"], "icon": m.get("icon", "")})
    return [{"category": cat, "items": groups[cat]} for cat in _CATEGORY_ORDER if groups[cat]]


def get_nav_for_account(email: str) -> list[dict[str, Any]]:
    """Return nav filtered by role for the given account email."""
    founder_emails = {
        os.environ.get("MURPHY_FOUNDER_EMAIL", "cpost@murphy.systems"),
        "hpost@murphy.systems",
        "callmehandy@gmail.com",
        "corey.gfc@gmail.com",
    }
    if email in founder_emails:
        allowed = _ROLE_VISIBILITY["founder_admin"]
    else:
        allowed = _ROLE_VISIBILITY.get("user", set())
    full = get_nav_structure()
    return [g for g in full if g["category"] in allowed]
