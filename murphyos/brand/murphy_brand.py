# SPDX-License-Identifier: BSL-1.1
# © 2020 Inoni Limited Liability Company — Creator: Corey Post
"""
Murphy System — Brand Constants

Canonical colour palette, typography, and identity tokens extracted from
the Murphy design system (murphy-design-system.css, murphy-landing.css).
Import this module from any MurphyOS component that needs brand values.
"""

from __future__ import annotations

# ── Colour palette ──────────────────────────────────────────────────

TEAL = "#00D4AA"
GREEN = "#00ff41"
CYAN = "#00ffff"

BG_BASE = "#0C1017"
BG_SURFACE = "#131A24"
BG_ELEVATED = "#1A2332"

TEXT_PRIMARY = "#E6ECF2"
TEXT_SECONDARY = "#8899AA"
TEXT_MUTED = "#566778"

BORDER_SUBTLE = "#1E2A3A"
BORDER_DEFAULT = "#2A3A4E"

SUCCESS = "#22C55E"
WARNING = "#FFA63E"
DANGER = "#EF4444"
INFO = "#3B9EFF"

GATE_EXECUTIVE = "#FFD700"
GATE_OPERATIONS = "#00D4AA"
GATE_QA = "#8B6CE7"

# ── Typography ──────────────────────────────────────────────────────

FONT_UI = "Inter"
FONT_CODE = "JetBrains Mono"

# ── Identity ────────────────────────────────────────────────────────

BRAND_NAME = "Murphy System"
BRAND_TAGLINE = "AI Business Operating System"
COPYRIGHT = "© 2020 Inoni Limited Liability Company — Creator: Corey Post — BSL 1.1"

# ── ANSI escape helpers (for terminal output) ───────────────────────

ANSI_TEAL = "\033[38;2;0;212;170m"
ANSI_GREEN = "\033[38;2;0;255;65m"
ANSI_CYAN = "\033[38;2;0;255;255m"
ANSI_WARNING = "\033[38;2;255;166;62m"
ANSI_DANGER = "\033[38;2;239;68;68m"
ANSI_RESET = "\033[0m"
ANSI_BOLD = "\033[1m"
