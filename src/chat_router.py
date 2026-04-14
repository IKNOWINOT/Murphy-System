"""
chat_router.py — Murphy System Chat Intent Router
==================================================
Analyzes each user message to determine intent and routes to the
appropriate backend pipeline:

- **chat** → Direct LLM call with conversation context
- **forge** → Full MFGC → MSS → Swarm pipeline via generate_deliverable_with_progress()
- **analyze** → MFGC confidence scoring + structured analysis
- **status** → System diagnostics formatted as chat response

Replaces the rigid frontend ``_gateCheck()`` with server-side intelligence.

Error codes: CHAT-ROUTER-ERR-001 .. CHAT-ROUTER-ERR-010

Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · BSL 1.1
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Intent detection keywords
# ---------------------------------------------------------------------------

_FORGE_KEYWORDS = re.compile(
    r"\b(build|create|generate|make|write|design|develop|forge|construct|produce|draft|compose|architect)\b",
    re.IGNORECASE,
)

_FORGE_TYPE_KEYWORDS = re.compile(
    r"\b(game|app|mvp|application|website|platform|automation|workflow|course|"
    r"curriculum|book|ebook|plan|blueprint|system|engine|api|dashboard|"
    r"tool|service|pipeline|framework|module|plugin|extension|bot|agent)\b",
    re.IGNORECASE,
)

_ANALYZE_KEYWORDS = re.compile(
    r"\b(analyze|analyse|evaluate|assess|audit|review|score|rate|check|inspect|diagnose|benchmark)\b",
    re.IGNORECASE,
)

_STATUS_KEYWORDS = re.compile(
    r"\b(status|health|diagnostics|uptime|version|info|ping|check system)\b",
    re.IGNORECASE,
)

# Slash commands
_SLASH_COMMANDS = {
    "/forge": "forge",
    "/build": "forge",
    "/analyze": "analyze",
    "/status": "status",
    "/help": "help",
}


# ---------------------------------------------------------------------------
# Intent detection
# ---------------------------------------------------------------------------

class ChatIntent:
    """Detected intent from a user message."""

    CHAT = "chat"
    FORGE = "forge"
    ANALYZE = "analyze"
    STATUS = "status"
    HELP = "help"

    def __init__(
        self,
        intent: str = "chat",
        confidence: float = 0.5,
        detail: str = "",
        forge_query: str = "",
    ):
        self.intent = intent
        self.confidence = confidence
        self.detail = detail
        self.forge_query = forge_query  # cleaned query for forge pipeline

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent": self.intent,
            "confidence": self.confidence,
            "detail": self.detail,
        }


def detect_intent(message: str, mode: str = "chat") -> ChatIntent:
    """Analyze a user message and return the detected intent.

    Args:
        message: The user's raw message text.
        mode: Current conversation mode ("chat", "forge", "analyze").
              Acts as a bias toward that intent.

    Returns:
        ChatIntent with the classified intent and confidence.
    """
    text = (message or "").strip()
    if not text:
        return ChatIntent("chat", 0.0, "empty message")

    # ── Slash commands take priority ──────────────────────────────────
    first_word = text.split()[0].lower()
    if first_word in _SLASH_COMMANDS:
        cmd_intent = _SLASH_COMMANDS[first_word]
        remaining = text[len(first_word):].strip()
        if cmd_intent == "forge":
            return ChatIntent("forge", 1.0, "slash command", forge_query=remaining or text)
        return ChatIntent(cmd_intent, 1.0, "slash command")

    # ── Status intent ─────────────────────────────────────────────────
    if _STATUS_KEYWORDS.search(text) and len(text.split()) <= 6:
        return ChatIntent("status", 0.85, "status keyword match")

    # ── Forge intent: action verb + buildable noun ────────────────────
    has_action = bool(_FORGE_KEYWORDS.search(text))
    has_type = bool(_FORGE_TYPE_KEYWORDS.search(text))
    word_count = len(text.split())

    forge_score = 0.0
    if has_action:
        forge_score += 0.40
    if has_type:
        forge_score += 0.35
    if word_count >= 4:
        forge_score += 0.15
    if mode == "forge":
        forge_score += 0.20  # mode bias

    if forge_score >= 0.70:
        return ChatIntent("forge", min(forge_score, 1.0), "keyword+type match", forge_query=text)

    # ── Analyze intent ────────────────────────────────────────────────
    if _ANALYZE_KEYWORDS.search(text):
        score = 0.65
        if mode == "analyze":
            score += 0.20
        return ChatIntent("analyze", min(score, 1.0), "analysis keyword match")

    # ── Default: general chat ─────────────────────────────────────────
    return ChatIntent("chat", 0.8, "general conversation")


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

MURPHY_SYSTEM_PROMPT = (
    "You are Murphy, an AI business operating system built by Inoni LLC. "
    "You help users automate, plan, build, and analyze business operations. "
    "You have access to the Swarm Forge (multi-agent build system), MFGC "
    "(Murphy Fractal Gate Checks for confidence scoring), and MSS (Magnify-"
    "Simplify-Solidify pipeline for content refinement). "
    "Be concise, helpful, and technically precise. Use the Murphy teal "
    "aesthetic in your responses. When users ask you to build something, "
    "let them know you can route it through the Forge pipeline."
)

MURPHY_HELP_TEXT = """\
**Murphy Chat Commands**

| Command | Description |
|---------|-------------|
| `/forge <query>` | Build something with the Swarm Forge |
| `/analyze <topic>` | Run MFGC analysis on a topic |
| `/status` | Check system health |
| `/help` | Show this help message |

**Modes** — Click the mode chips above the input to bias intent detection:
- **Chat** — General conversation with Murphy
- **Forge** — Prioritize build/creation requests
- **Analyze** — Prioritize analysis/evaluation requests

You can also just type naturally — Murphy will detect your intent automatically.
"""
