# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""RenderAgent — MURPHY-AGENT-RENDER-001

Owner: Platform Engineering
Dep: AgentOutput schema

Routes upstream AgentOutput to the correct render_type.  Never falls back
to raw text — unknown content_type always returns FAIL.

Routing table (content_type → render_type):
  svg                → diagram
  html               → widget
  zip                → download
  pdf                → document
  compliance_report  → document
  code               → syntax_highlight
  chart              → data_viz
  matrix_message     → message
  json_manifest      → syntax_highlight
  test_suite         → syntax_highlight
  pass_fail          → syntax_highlight
  automation_proposal → widget
  audit_entry        → document

Error codes: RENDER-ERR-001 through RENDER-ERR-003.
"""

from __future__ import annotations

import logging
import uuid

from murphy.rosetta.org_lookup import get_rosetta_state_hash
from murphy.schemas.agent_output import AgentOutput, ContentType, RenderType

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Routing table  (RENDER-ROUTE-001)
# ---------------------------------------------------------------------------

_RENDER_ROUTES: dict[ContentType, RenderType] = {
    ContentType.SVG: RenderType.DIAGRAM,
    ContentType.HTML: RenderType.WIDGET,
    ContentType.ZIP: RenderType.DOWNLOAD,
    ContentType.PDF: RenderType.DOCUMENT,
    ContentType.COMPLIANCE_REPORT: RenderType.DOCUMENT,
    ContentType.CODE: RenderType.SYNTAX_HIGHLIGHT,
    ContentType.CHART: RenderType.DATA_VIZ,
    ContentType.MATRIX_MESSAGE: RenderType.MESSAGE,
    ContentType.JSON_MANIFEST: RenderType.SYNTAX_HIGHLIGHT,
    ContentType.TEST_SUITE: RenderType.SYNTAX_HIGHLIGHT,
    ContentType.PASS_FAIL: RenderType.SYNTAX_HIGHLIGHT,
    ContentType.AUTOMATION_PROPOSAL: RenderType.WIDGET,
    ContentType.AUDIT_ENTRY: RenderType.DOCUMENT,
}


class RenderAgent:
    """Route upstream agent output to the correct renderer.

    Hard rules:
      - Unknown content_type → FAIL (never fall back to raw text)
      - All render routing is deterministic via _RENDER_ROUTES
    """

    AGENT_NAME = "RenderAgent"

    def __init__(self, *, org_node_id: str = "platform-engineering") -> None:
        self.agent_id = f"render-{uuid.uuid4().hex[:8]}"
        self.org_node_id = org_node_id

    def run(self, upstream_output: AgentOutput) -> AgentOutput:
        """Route upstream output to the correct renderer.

        Args:
            upstream_output: AgentOutput from any upstream agent.

        Returns:
            AgentOutput with the resolved render_type, or FAIL if
            content_type is unknown.
        """
        try:
            render_type = _RENDER_ROUTES.get(upstream_output.content_type)
            if render_type is None:
                return AgentOutput.from_error(
                    agent_id=self.agent_id,
                    agent_name=self.AGENT_NAME,
                    file_path=upstream_output.file_path,
                    org_node_id=self.org_node_id,
                    error_message=(
                        f"RENDER-ERR-002: Unknown content_type "
                        f"'{upstream_output.content_type}' — "
                        f"cannot route to renderer"
                    ),
                )

            state_hash = get_rosetta_state_hash()

            return AgentOutput(
                agent_id=self.agent_id,
                agent_name=self.AGENT_NAME,
                file_path=upstream_output.file_path,
                content_type=upstream_output.content_type,
                content=upstream_output.content,
                lang=upstream_output.lang,
                depends_on=[upstream_output.file_path],
                org_node_id=self.org_node_id,
                rosetta_state_hash=state_hash,
                render_type=render_type,
                hitl_required=upstream_output.hitl_required,
                hitl_authority_node_id=upstream_output.hitl_authority_node_id,
                bat_seal_required=upstream_output.bat_seal_required,
                error=upstream_output.error,
            )

        except Exception as exc:  # RENDER-ERR-001
            logger.error("RENDER-ERR-001: %s", exc)
            return AgentOutput.from_error(
                agent_id=self.agent_id,
                agent_name=self.AGENT_NAME,
                file_path=upstream_output.file_path,
                org_node_id=self.org_node_id,
                error_message=f"RENDER-ERR-001: {exc}",
            )

    @staticmethod
    def get_routing_table() -> dict[str, str]:
        """Return the routing table for diagnostics."""
        return {ct.value: rt.value for ct, rt in _RENDER_ROUTES.items()}
