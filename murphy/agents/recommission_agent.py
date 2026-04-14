# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""RecommissionAgent — MURPHY-AGENT-RECOMMISSION-001

Owner: Platform Engineering
Dep: AgentOutput schema, Rosetta org lookup, BAT sealing

Re-tests changed files and their dependents.  Never silently passes.
Every result (pass or fail) is sealed to the BAT audit trail.

Input:
  changed_file_path (str), dependent_files (list), previous_test_results (dict)
Output:
  AgentOutput with content_type=test_suite

Error codes: RECOMMISSION-ERR-001 through RECOMMISSION-ERR-005.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from murphy.rosetta.org_lookup import (
    get_rosetta_state_hash,
    _seal_to_bat,
    BATSealError,
)
from murphy.schemas.agent_output import AgentOutput, ContentType, RenderType

logger = logging.getLogger(__name__)

# Default test runner — replaced via set_test_runner() in production
_test_runner: Optional[Callable[[str], Dict[str, Any]]] = None


def set_test_runner(runner: Callable[[str], Dict[str, Any]]) -> None:
    """Wire the test runner at startup.

    Signature: runner(file_path) -> {"passed": bool, "details": str, ...}
    """
    global _test_runner
    _test_runner = runner


class RecommissionAgent:
    """Re-test changed files and all their dependents.

    Hard rules:
      - If the test runner cannot be invoked: return FAIL
      - If any test fails: return FAIL listing which tests failed
      - Every result is sealed to BAT — no exceptions
      - Never silently pass
    """

    AGENT_NAME = "RecommissionAgent"

    def __init__(self, *, org_node_id: str = "platform-engineering") -> None:
        self.agent_id = f"recommission-{uuid.uuid4().hex[:8]}"
        self.org_node_id = org_node_id

    def run(
        self,
        changed_file_path: str,
        dependent_files: List[str],
        previous_test_results: Dict[str, Any],
        *,
        test_runner: Optional[Callable[[str], Dict[str, Any]]] = None,
    ) -> AgentOutput:
        """Execute re-commissioning tests.

        Args:
            changed_file_path: The file that was changed.
            dependent_files: Files that depend on the changed file.
            previous_test_results: Previous test results for comparison.
            test_runner: Override the global test runner for this invocation.

        Returns:
            AgentOutput with test_suite content.
        """
        runner = test_runner or _test_runner
        if runner is None:
            return self._fail_and_seal(
                "RECOMMISSION-ERR-001: No test runner wired — "
                "call set_test_runner() at startup or pass test_runner kwarg"
            )

        all_files = [changed_file_path] + list(dependent_files)
        results: List[Dict[str, Any]] = []
        failures: List[str] = []

        for file_path in all_files:
            try:
                result = runner(file_path)
                result["file_path"] = file_path
                results.append(result)
                if not result.get("passed", False):
                    failures.append(file_path)
            except Exception as exc:  # RECOMMISSION-ERR-002
                logger.error("RECOMMISSION-ERR-002: Test runner failed for %s: %s", file_path, exc)
                results.append({
                    "file_path": file_path,
                    "passed": False,
                    "details": f"RECOMMISSION-ERR-002: {exc}",
                })
                failures.append(file_path)

        # Seal every result to BAT
        report = {
            "changed_file": changed_file_path,
            "total_files": len(all_files),
            "total_passed": len(all_files) - len(failures),
            "total_failed": len(failures),
            "failures": failures,
            "results": results,
            "recommissioned_at": datetime.now(timezone.utc).isoformat(),
        }

        try:
            _seal_to_bat(
                action="recommission_test",
                resource=changed_file_path,
                metadata=report,
            )
        except BATSealError as exc:  # RECOMMISSION-ERR-003
            logger.error("RECOMMISSION-ERR-003: BAT seal failed — %s", exc)
            # Still return the result — but note the seal failure

        state_hash = get_rosetta_state_hash()

        if failures:
            return AgentOutput(
                agent_id=self.agent_id,
                agent_name=self.AGENT_NAME,
                file_path=changed_file_path,
                content_type=ContentType.PASS_FAIL,
                content="FAIL",
                lang="json",
                depends_on=dependent_files,
                org_node_id=self.org_node_id,
                rosetta_state_hash=state_hash,
                render_type=RenderType.SYNTAX_HIGHLIGHT,
                hitl_required=False,
                bat_seal_required=True,
                error=(
                    f"RECOMMISSION-ERR-004: {len(failures)} test(s) failed: "
                    f"{', '.join(failures)}"
                ),
            )

        return AgentOutput(
            agent_id=self.agent_id,
            agent_name=self.AGENT_NAME,
            file_path=changed_file_path,
            content_type=ContentType.TEST_SUITE,
            content=json.dumps(report, indent=2, default=str),
            lang="json",
            depends_on=dependent_files,
            org_node_id=self.org_node_id,
            rosetta_state_hash=state_hash,
            render_type=RenderType.SYNTAX_HIGHLIGHT,
            hitl_required=False,
            bat_seal_required=True,
        )

    def _fail_and_seal(self, error_message: str) -> AgentOutput:
        """Return FAIL and attempt to seal the failure to BAT."""
        try:
            _seal_to_bat(
                action="recommission_failure",
                resource="test_runner",
                metadata={"error": error_message},
            )
        except BATSealError:  # RECOMMISSION-ERR-005
            logger.error("RECOMMISSION-ERR-005: BAT seal also failed")

        return AgentOutput.from_error(
            agent_id=self.agent_id,
            agent_name=self.AGENT_NAME,
            file_path="recommission.json",
            org_node_id=self.org_node_id,
            error_message=error_message,
        )
