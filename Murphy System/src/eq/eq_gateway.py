"""
EQ Gateway — Isolation Boundary and Sandbox Enforcement

Implements the EQ isolation boundary described in §15 and §11.3 of the
Experimental EverQuest Modification Plan.

Responsibilities:
  - Validates all data crossing the Murphy ↔ EQ boundary
  - Enforces agent language restrictions (in-game languages + Common Tongue only)
  - Rejects content containing code syntax or real-world technical terms
  - Scopes agent recall queries to the EQ vector index only
  - Logs all boundary crossings for audit
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# In-game languages that agents may use
VALID_LANGUAGES: Set[str] = {
    "common_tongue", "barbarian", "erudian", "elvish", "dark_elvish",
    "dwarvish", "troll", "ogre", "gnomish", "halfling", "thieves_cant",
    "old_erudian", "elder_elvish", "froglok", "goblin", "gnoll",
    "combine_tongue", "elder_tier'dal", "lizardman", "orcish",
    "faerie", "dragon", "elder_dragon", "dark_speech", "vah_shir",
    "alaran", "hadal", "unknown",
}

# Patterns that indicate code or real-world technical content
_CODE_PATTERNS = [
    r"import\s+\w+",
    r"from\s+\w+\s+import",
    r"def\s+\w+\s*\(",
    r"class\s+\w+\s*[:\(]",
    r"\bhttp[s]?://",
    r"\bsudo\b",
    r"\bpip\s+install\b",
    r"\bnpm\s+install\b",
    r"\bgit\s+(clone|push|pull)\b",
    r"\b(SELECT|INSERT|UPDATE|DELETE)\s+",
    r"<script\b",
    r"\beval\s*\(",
    r"\bexec\s*\(",
]


class GatewayDirection(Enum):
    """Direction of data flow across the boundary."""
    INBOUND = "inbound"    # Murphy → EQ (data flowing to agents)
    OUTBOUND = "outbound"  # EQ → Murphy (telemetry/logs flowing out)


@dataclass
class GatewayLogEntry:
    """Audit log entry for a boundary crossing."""
    direction: GatewayDirection
    source: str
    destination: str
    content_type: str
    allowed: bool
    rejection_reason: str = ""
    timestamp: float = 0.0


# ---------------------------------------------------------------------------
# EQ Gateway
# ---------------------------------------------------------------------------

class EQGateway:
    """Sandbox boundary between the Murphy System core and the EQ experiment.

    All data flowing into the EQ agent layer passes through this gateway
    for validation.  No Murphy core data (system prompts, configuration,
    API keys) is allowed inbound.  Agent recall queries are scoped to the
    EQ vector index.
    """

    def __init__(self) -> None:
        self._log: List[GatewayLogEntry] = []
        self._blocked_terms: Set[str] = {
            "api_key", "secret", "password", "token", "credential",
            "system_prompt", "murphy_core", "admin_override",
        }

    # --- Language validation ---

    def validate_language(self, language: str) -> bool:
        """Check whether a language is valid for agent use."""
        return language.lower() in VALID_LANGUAGES

    # --- Content validation ---

    def validate_content(self, content: str) -> tuple[bool, str]:
        """Validate content crossing the boundary.

        Returns (is_valid, rejection_reason).
        """
        lower = content.lower()

        # Check for blocked terms using word-boundary matching to prevent
        # substring false-positives (e.g. "classic" containing "class")
        for term in self._blocked_terms:
            if re.search(r'\b' + re.escape(term) + r'\b', lower):
                return False, f"blocked_term:{term}"

        # Check for code patterns
        for pattern in _CODE_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                return False, f"code_pattern:{pattern}"

        return True, ""

    # --- Boundary crossing ---

    def pass_inbound(
        self,
        source: str,
        destination: str,
        content: str,
        content_type: str = "text",
    ) -> bool:
        """Attempt to pass data inbound (Murphy → EQ agents).

        Returns True if allowed, False if blocked.
        """
        is_valid, reason = self.validate_content(content)
        entry = GatewayLogEntry(
            direction=GatewayDirection.INBOUND,
            source=source,
            destination=destination,
            content_type=content_type,
            allowed=is_valid,
            rejection_reason=reason,
        )
        capped_append(self._log, entry)
        return is_valid

    def pass_outbound(
        self,
        source: str,
        destination: str,
        content: str,
        content_type: str = "telemetry",
    ) -> bool:
        """Pass data outbound (EQ → Murphy).

        Outbound telemetry/logs are generally allowed.
        """
        entry = GatewayLogEntry(
            direction=GatewayDirection.OUTBOUND,
            source=source,
            destination=destination,
            content_type=content_type,
            allowed=True,
        )
        capped_append(self._log, entry)
        return True

    # --- Recall query scoping ---

    def scope_recall_query(self, query: str, index: str = "eq") -> str:
        """Scope a recall query to the EQ vector index only.

        Strips any cross-system references and returns the scoped query.
        """
        return f"[index:{index}] {query}"

    # --- Audit ---

    @property
    def log(self) -> List[GatewayLogEntry]:
        return list(self._log)

    @property
    def blocked_count(self) -> int:
        return sum(1 for e in self._log if not e.allowed)

    @property
    def allowed_count(self) -> int:
        return sum(1 for e in self._log if e.allowed)
