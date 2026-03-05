"""
Layer 2 — Capability Registry.

Maintains a map of available bots / modules / services and their declared
capabilities.  Used by the Reasoning Engine to build candidate orchestration
graphs.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class Capability(BaseModel):
    """Describes a single capability offered by a bot / module / service."""

    capability_id: str
    name: str
    description: str = ""
    provider: str = Field(
        ..., description="ID of the bot/module/service that provides this capability."
    )
    input_schema: Dict[str, Any] = Field(
        default_factory=dict,
        description="JSON-schema-style description of expected inputs.",
    )
    output_schema: Dict[str, Any] = Field(
        default_factory=dict,
        description="JSON-schema-style description of produced outputs.",
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Free-form tags for matching (e.g. 'analysis', 'generation').",
    )
    risk_level: str = "low"
    requires_approval: bool = False
    max_concurrency: int = 1
    timeout_seconds: float = 300.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CapabilityRegistry:
    """Thread-safe in-memory registry of capabilities.

    In Murphy 2.0b this will be backed by an external service; for 2.0a
    an in-process dict suffices.
    """

    def __init__(self) -> None:
        self._capabilities: Dict[str, Capability] = {}

    def register(self, capability: Capability) -> None:
        """Add or overwrite a capability."""
        self._capabilities[capability.capability_id] = capability
        logger.info(
            "Registered capability %s (%s) from provider %s",
            capability.capability_id,
            capability.name,
            capability.provider,
        )

    def unregister(self, capability_id: str) -> None:
        self._capabilities.pop(capability_id, None)

    def get(self, capability_id: str) -> Optional[Capability]:
        return self._capabilities.get(capability_id)

    def list_all(self) -> List[Capability]:
        return list(self._capabilities.values())

    def search(
        self,
        *,
        tags: Optional[List[str]] = None,
        provider: Optional[str] = None,
        name_contains: Optional[str] = None,
    ) -> List[Capability]:
        """Return capabilities matching the given filter criteria."""
        results = self.list_all()
        if tags:
            tag_set = set(tags)
            results = [c for c in results if tag_set & set(c.tags)]
        if provider:
            results = [c for c in results if c.provider == provider]
        if name_contains:
            lc = name_contains.lower()
            results = [c for c in results if lc in c.name.lower()]
        return results

    def count(self) -> int:
        return len(self._capabilities)
