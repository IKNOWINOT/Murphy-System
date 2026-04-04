# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Copilot Tenant — Matrix Room (Founder Communication Channel)

Posts planned actions to a Matrix bridge room for founder approval.
Uses src/matrix_bridge/ to create a 'copilot-tenant' room.

The founder can:
  - Approve proposed actions (reply 'approve' or '✅')
  - Reject with reason (reply 'reject: <reason>')
  - Modify and approve (reply with modified action)
"""
from __future__ import annotations

import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional dependency imports
# ---------------------------------------------------------------------------

try:
    from matrix_bridge.matrix_client import MatrixClient
    _MATRIX_CLIENT_AVAILABLE = True
except Exception:  # pragma: no cover
    MatrixClient = None  # type: ignore[assignment,misc]
    _MATRIX_CLIENT_AVAILABLE = False

try:
    from matrix_bridge.hitl_matrix_adapter import HITLMatrixAdapter
    _HITL_ADAPTER_AVAILABLE = True
except Exception:  # pragma: no cover
    HITLMatrixAdapter = None  # type: ignore[assignment,misc]
    _HITL_ADAPTER_AVAILABLE = False


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class ApprovalResult:
    proposal_id: str
    approved: bool
    note: Optional[str]   = None
    decided_at: str        = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ---------------------------------------------------------------------------
# CopilotMatrixRoom
# ---------------------------------------------------------------------------

class CopilotMatrixRoom:
    """Posts planned actions to the 'copilot-tenant' Matrix room for founder approval.

    When the Matrix bridge is unavailable the class operates in stub mode:
    all posts are logged and ``check_approval()`` always returns None.
    """

    ROOM_ALIAS = "copilot-tenant"

    def __init__(self, founder_email: str = "") -> None:
        self._founder_email = founder_email or os.environ.get("MURPHY_FOUNDER_EMAIL", "")
        self._client: Any   = None
        self._adapter: Any  = None
        self._room_id: Optional[str] = None
        self._pending: Dict[str, Any] = {}   # proposal_id → proposal
        self._initialize()

    def _initialize(self) -> None:
        if _MATRIX_CLIENT_AVAILABLE:
            try:
                self._client = MatrixClient()
                room = self._client.get_or_create_room(self.ROOM_ALIAS)
                self._room_id = getattr(room, "room_id", None)
            except Exception as exc:
                logger.debug("MatrixClient init failed: %s", exc)
        if _HITL_ADAPTER_AVAILABLE:
            try:
                self._adapter = HITLMatrixAdapter()
            except Exception as exc:
                logger.debug("HITLMatrixAdapter init failed: %s", exc)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def post_proposal(self, proposal: Any) -> str:
        """Post a Proposal to the room and return the message_id."""
        proposal_id = getattr(proposal, "proposal_id", str(uuid.uuid4()))
        description = getattr(proposal, "description", str(proposal))
        message = (
            f"🤖 **Copilot Tenant Proposal** [{proposal_id}]\n"
            f"Action: {description}\n"
            f"Reply `approve` ✅  |  `reject: <reason>` ❌  |  modified action text to approve-and-modify"
        )
        self._pending[proposal_id] = proposal
        self._send_message(message)
        logger.info("CopilotMatrixRoom: posted proposal %s", proposal_id)
        return proposal_id

    def check_approval(self, proposal_id: str) -> Optional[ApprovalResult]:
        """Poll the room for a founder response to *proposal_id*.

        Returns an ApprovalResult if a response has been received, otherwise None.
        """
        if self._adapter is not None:
            try:
                resp = self._adapter.check_approval(proposal_id)
                if resp is not None:
                    return ApprovalResult(
                        proposal_id=proposal_id,
                        approved=bool(resp.get("approved", False)),
                        note=resp.get("note"),
                    )
            except Exception as exc:
                logger.debug("HITLMatrixAdapter.check_approval failed: %s", exc)
        return None

    def post_execution_result(self, result: Any) -> None:
        """Post an execution result summary to the room."""
        result_id = getattr(result, "result_id", "?")
        status    = getattr(result, "status", "?")
        message   = f"✅ **Execution Result** [{result_id}]  status={status}"
        self._send_message(message)

    def post_daily_summary(self, summary: Dict[str, Any]) -> None:
        """Post the daily operations summary to the room."""
        lines = [f"📊 **Daily Summary** — {datetime.now(timezone.utc).date()}"]
        for key, val in summary.items():
            lines.append(f"  • {key}: {val}")
        self._send_message("\n".join(lines))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _send_message(self, text: str) -> None:
        if self._client is not None and self._room_id:
            try:
                self._client.send_text(self._room_id, text)
                return
            except Exception as exc:
                logger.debug("Matrix send_text failed: %s", exc)
        logger.info("[CopilotMatrixRoom stub] %s", text)
