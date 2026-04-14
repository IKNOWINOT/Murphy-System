# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Universal AgentOutput schema — MURPHY-SCHEMA-001

Owner: Platform Engineering
Dep: pydantic >=2.0

Every agent in the Murphy system MUST return an ``AgentOutput`` instance.
Freeform text and untyped dicts are forbidden.  This schema is the single
source of truth for inter-agent communication and is mirrored in TypeScript
(``agent_output.ts``).

Fields
------
agent_id : str
    Unique identifier of the agent that produced this output.
agent_name : str
    Human-readable agent name (e.g. "ManifestAgent", "RenderAgent").
file_path : str
    Path this agent owns or produced.  Every agent MUST declare one so the
    manifest and dependency graph are always complete.
content_type : ContentType
    Enum declaring the kind of payload in ``content``.
content : str
    The actual structured output — never freeform prose.
lang : Optional[str]
    Language of the content (python, typescript, html, svg, …).
depends_on : List[str]
    File paths this agent's output depends on.  Used by RecommissionAgent
    to know what to re-test when a file changes.
org_node_id : str
    The org chart node this agent is bound to.  Used by HITL gates for
    authority resolution.
rosetta_state_hash : str
    SHA-256 hash of the Rosetta world-state snapshot at execution time.
    Ensures every output is anchored to a known system state.
render_type : RenderType
    How the output should be rendered in the UI.
hitl_required : bool
    Whether this output requires human-in-the-loop approval before
    promotion.
hitl_authority_node_id : Optional[str]
    The org chart node that must approve.  MUST be set when
    ``hitl_required`` is True — hard error, not warning.
bat_seal_required : bool
    Whether this output must be sealed in the Blockchain Audit Trail.
error : Optional[str]
    None on success, error message on failure.  Agents MUST populate this
    on any error — silent failures are forbidden.
timestamp : datetime
    UTC timestamp of output creation.
schema_version : str
    Semver of this schema (default "1.0.0").
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# Enums  (MURPHY-SCHEMA-ENUM-001)
# ---------------------------------------------------------------------------

class ContentType(str, Enum):
    """Allowed content types for agent output."""

    SVG = "svg"
    HTML = "html"
    ZIP = "zip"
    PDF = "pdf"
    CODE = "code"
    CHART = "chart"
    COMPLIANCE_REPORT = "compliance_report"
    MATRIX_MESSAGE = "matrix_message"
    JSON_MANIFEST = "json_manifest"
    TEST_SUITE = "test_suite"
    PASS_FAIL = "pass_fail"
    AUTOMATION_PROPOSAL = "automation_proposal"
    AUDIT_ENTRY = "audit_entry"


class RenderType(str, Enum):
    """How the agent's output is rendered in the UI."""

    DIAGRAM = "diagram"
    WIDGET = "widget"
    DOWNLOAD = "download"
    DOCUMENT = "document"
    SYNTAX_HIGHLIGHT = "syntax_highlight"
    DATA_VIZ = "data_viz"
    MESSAGE = "message"


# ---------------------------------------------------------------------------
# Main schema  (MURPHY-SCHEMA-001)
# ---------------------------------------------------------------------------

class AgentOutput(BaseModel):
    """Universal output schema for every Murphy agent.

    Hard rules:
      • If ``hitl_required`` is True, ``hitl_authority_node_id`` MUST be set.
      • If ``content_type`` is ``pass_fail``, ``content`` MUST be "PASS" or
        "FAIL" — any other value is a hard error.
      • ``error`` must be populated on failure — silent failures are forbidden.
    """

    agent_id: str = Field(..., min_length=1, description="Unique agent identifier")
    agent_name: str = Field(..., min_length=1, description="Human-readable agent name")
    file_path: str = Field(..., min_length=1, description="Path this agent owns or produced")
    content_type: ContentType = Field(..., description="Kind of payload in content")
    content: str = Field(..., description="Structured output — never freeform prose")
    lang: Optional[str] = Field(default=None, description="Language: python, typescript, html, svg, …")
    depends_on: List[str] = Field(default_factory=list, description="File paths this output depends on")
    org_node_id: str = Field(..., min_length=1, description="Org chart node this agent is bound to")
    rosetta_state_hash: str = Field(..., min_length=1, description="SHA-256 of Rosetta state at execution")
    render_type: RenderType = Field(..., description="How to render in UI")
    hitl_required: bool = Field(default=False, description="Requires human approval?")
    hitl_authority_node_id: Optional[str] = Field(
        default=None,
        description="Org chart node that must approve — MUST be set if hitl_required",
    )
    bat_seal_required: bool = Field(default=False, description="Must be sealed in BAT?")
    error: Optional[str] = Field(default=None, description="None on success, error message on failure")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of creation",
    )
    schema_version: str = Field(default="1.0.0", description="Semver of this schema")

    # ------------------------------------------------------------------
    # Validators  (MURPHY-SCHEMA-VAL-001)
    # ------------------------------------------------------------------

    @model_validator(mode="after")
    def _hitl_authority_required(self) -> "AgentOutput":
        """If hitl_required is True, hitl_authority_node_id MUST be set."""
        if self.hitl_required and not self.hitl_authority_node_id:
            raise ValueError(
                "MURPHY-SCHEMA-ERR-001: hitl_authority_node_id must be set "
                "when hitl_required is True — hard error, not warning"
            )
        return self

    @model_validator(mode="after")
    def _pass_fail_content(self) -> "AgentOutput":
        """If content_type is pass_fail, content must be PASS or FAIL."""
        if self.content_type == ContentType.PASS_FAIL and self.content not in ("PASS", "FAIL"):
            raise ValueError(
                "MURPHY-SCHEMA-ERR-002: content must be 'PASS' or 'FAIL' "
                f"when content_type is pass_fail — got '{self.content}'"
            )
        return self

    # ------------------------------------------------------------------
    # Factories  (MURPHY-SCHEMA-FACTORY-001)
    # ------------------------------------------------------------------

    @classmethod
    def from_error(
        cls,
        agent_id: str,
        agent_name: str,
        file_path: str,
        org_node_id: str,
        error_message: str,
        *,
        rosetta_state_hash: str = "error-state",
    ) -> "AgentOutput":
        """Create a valid FAIL AgentOutput for error reporting.

        Use this factory whenever an agent encounters an error it cannot
        recover from.  The returned output has content_type=pass_fail,
        content="FAIL", and error populated — ensuring errors are never
        silent.

        Args:
            agent_id: The agent's unique id.
            agent_name: Human-readable agent name.
            file_path: Path the agent was working on.
            org_node_id: Org chart node the agent is bound to.
            error_message: Description of what went wrong.
            rosetta_state_hash: Rosetta state hash (defaults to "error-state").

        Returns:
            A valid ``AgentOutput`` with content="FAIL" and error set.
        """
        return cls(
            agent_id=agent_id,
            agent_name=agent_name,
            file_path=file_path,
            content_type=ContentType.PASS_FAIL,
            content="FAIL",
            org_node_id=org_node_id,
            rosetta_state_hash=rosetta_state_hash,
            render_type=RenderType.SYNTAX_HIGHLIGHT,
            hitl_required=False,
            bat_seal_required=True,
            error=error_message,
        )

    def to_json(self) -> str:
        """Serialize to JSON string for inter-agent transport."""
        return self.model_dump_json()

    @classmethod
    def from_json(cls, raw: str) -> "AgentOutput":
        """Deserialize from JSON string."""
        return cls.model_validate_json(raw)

    def content_hash(self) -> str:
        """SHA-256 hash of the content for dedup / integrity checks."""
        return hashlib.sha256(self.content.encode("utf-8")).hexdigest()
