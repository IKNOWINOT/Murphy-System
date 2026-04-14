# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""ManifestAgent — MURPHY-AGENT-MANIFEST-001

Owner: Platform Engineering
Dep: AgentOutput schema, Rosetta org lookup

Declares every file BEFORE any swarm agent spawns.  The manifest is the
single source of truth for what the build will contain.

Input:
  normalized_request (dict), deliverable_type (str), tech_stack (list), org_chart (dict)
Output:
  AgentOutput with content_type=json_manifest

Error codes: MANIFEST-ERR-001 through MANIFEST-ERR-004.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Dict, List

from murphy.rosetta.org_lookup import get_rosetta_state_hash
from murphy.schemas.agent_output import AgentOutput, ContentType, RenderType

logger = logging.getLogger(__name__)

_REQUIRED_ENTRY_FIELDS = frozenset({
    "file_path", "owner_agent", "lang", "depends_on",
    "render_type", "hitl_required", "org_node_id",
})


class ManifestAgent:
    """Build file manifest before swarm execution.

    Every file that will be produced MUST be declared here.
    If any manifest entry is missing a required field, the agent
    returns FAIL — swarm MUST NOT proceed.
    """

    AGENT_NAME = "ManifestAgent"

    def __init__(self, *, org_node_id: str = "platform-engineering") -> None:
        self.agent_id = f"manifest-{uuid.uuid4().hex[:8]}"
        self.org_node_id = org_node_id

    def run(
        self,
        normalized_request: Dict[str, Any],
        deliverable_type: str,
        tech_stack: List[str],
        org_chart: Dict[str, Any],
    ) -> AgentOutput:
        """Execute the manifest agent.

        Returns AgentOutput with a JSON manifest or FAIL on error.
        """
        try:
            manifest_entries = self._build_manifest(
                normalized_request, deliverable_type, tech_stack, org_chart,
            )

            # Validate every entry has required fields
            for i, entry in enumerate(manifest_entries):
                missing = _REQUIRED_ENTRY_FIELDS - set(entry.keys())
                if missing:
                    return AgentOutput.from_error(
                        agent_id=self.agent_id,
                        agent_name=self.AGENT_NAME,
                        file_path="manifest.json",
                        org_node_id=self.org_node_id,
                        error_message=(
                            f"MANIFEST-ERR-002: Entry {i} missing fields: "
                            f"{sorted(missing)}"
                        ),
                    )

            manifest_json = json.dumps(manifest_entries, indent=2, default=str)
            state_hash = get_rosetta_state_hash()

            logger.info(
                "MANIFEST-001: Manifest built — %d entries, hash=%s",
                len(manifest_entries), state_hash[:12],
            )

            return AgentOutput(
                agent_id=self.agent_id,
                agent_name=self.AGENT_NAME,
                file_path="manifest.json",
                content_type=ContentType.JSON_MANIFEST,
                content=manifest_json,
                lang="json",
                depends_on=[],
                org_node_id=self.org_node_id,
                rosetta_state_hash=state_hash,
                render_type=RenderType.SYNTAX_HIGHLIGHT,
                hitl_required=False,
                bat_seal_required=True,
            )

        except Exception as exc:  # MANIFEST-ERR-001
            logger.error("MANIFEST-ERR-001: %s", exc)
            return AgentOutput.from_error(
                agent_id=self.agent_id,
                agent_name=self.AGENT_NAME,
                file_path="manifest.json",
                org_node_id=self.org_node_id,
                error_message=f"MANIFEST-ERR-001: {exc}",
            )

    def _build_manifest(
        self,
        request: Dict[str, Any],
        deliverable_type: str,
        tech_stack: List[str],
        org_chart: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Build manifest entries from the request.

        Each entry declares a file that will be produced by the swarm.
        """
        entries: List[Dict[str, Any]] = []

        # Core deliverable file
        lang = tech_stack[0] if tech_stack else "python"
        ext = {"python": ".py", "typescript": ".ts", "html": ".html",
               "svg": ".svg"}.get(lang, ".txt")

        entries.append({
            "file_path": f"output/main{ext}",
            "owner_agent": "SwarmCoordinator",
            "lang": lang,
            "depends_on": [],
            "render_type": "syntax_highlight",
            "hitl_required": False,
            "org_node_id": self.org_node_id,
        })

        # README
        entries.append({
            "file_path": "output/README.md",
            "owner_agent": "DocumentationAgent",
            "lang": "markdown",
            "depends_on": [f"output/main{ext}"],
            "render_type": "document",
            "hitl_required": False,
            "org_node_id": self.org_node_id,
        })

        # Test file
        entries.append({
            "file_path": f"output/test_main{ext}",
            "owner_agent": "TestAgent",
            "lang": lang,
            "depends_on": [f"output/main{ext}"],
            "render_type": "syntax_highlight",
            "hitl_required": False,
            "org_node_id": self.org_node_id,
        })

        # Start scripts
        entries.append({
            "file_path": "output/start.sh",
            "owner_agent": "PackageAgent",
            "lang": "bash",
            "depends_on": [f"output/main{ext}"],
            "render_type": "syntax_highlight",
            "hitl_required": False,
            "org_node_id": self.org_node_id,
        })

        entries.append({
            "file_path": "output/start.bat",
            "owner_agent": "PackageAgent",
            "lang": "batch",
            "depends_on": [f"output/main{ext}"],
            "render_type": "syntax_highlight",
            "hitl_required": False,
            "org_node_id": self.org_node_id,
        })

        # Smoke test
        entries.append({
            "file_path": "output/smoke_test.py",
            "owner_agent": "PackageAgent",
            "lang": "python",
            "depends_on": [f"output/main{ext}", "output/start.sh"],
            "render_type": "syntax_highlight",
            "hitl_required": False,
            "org_node_id": self.org_node_id,
        })

        return entries
