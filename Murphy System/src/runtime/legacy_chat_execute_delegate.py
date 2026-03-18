"""Patch-ready delegation helper for legacy /api/chat and /api/execute.

This module is designed to be imported into the monolithic legacy runtime
once the repo is ready to make chat/execute subordinate to Murphy Core.
It preserves the legacy handler surface while routing orchestration through
Murphy Core's preferred runtime-correct path.
"""

from __future__ import annotations

from typing import Any, Dict

from src.runtime.core_handoff import CoreHandoff


class LegacyChatExecuteDelegate:
    """Delegate legacy chat/execute requests into Murphy Core.

    This is intentionally thin: it keeps the old endpoint payload shape but
    makes the orchestration authority live in Murphy Core.
    """

    def __init__(self, prefer_core: bool = True) -> None:
        self.handoff = CoreHandoff(prefer_core=prefer_core)

    def delegate_chat(self, data: Dict[str, Any]) -> Dict[str, Any]:
        payload = {
            "message": data.get("message", ""),
            "session_id": data.get("session_id"),
            "context": data.get("context", {}),
        }
        result = self.handoff.handoff_chat(payload)
        return {
            "delegated": True,
            "delegated_to": result.get("delegated_to"),
            "status_code": result.get("status_code"),
            "payload": result.get("payload"),
        }

    def delegate_execute(self, data: Dict[str, Any]) -> Dict[str, Any]:
        payload = {
            "task_description": data.get("task_description") or data.get("message") or "",
            "session_id": data.get("session_id"),
            "parameters": data.get("parameters", {}),
        }
        result = self.handoff.handoff_execute(payload)
        return {
            "delegated": True,
            "delegated_to": result.get("delegated_to"),
            "status_code": result.get("status_code"),
            "payload": result.get("payload"),
        }
