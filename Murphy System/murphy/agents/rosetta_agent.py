# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""RosettaAgent — MURPHY-AGENT-ROSETTA-001

Owner: Platform Engineering
Dep: AgentOutput schema, Rosetta org lookup

World-state consensus agent.  All agents must agree on the Rosetta
world-state before any executes.  Handles voting, conflict resolution,
and change propagation.

Input:
  manifest_state (dict), agent_states (list of dicts), org_chart (dict)
Output:
  AgentOutput with content_type=json_manifest (the locked world-state)

Error codes: ROSETTA-AGENT-ERR-001 through ROSETTA-AGENT-ERR-006.
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from murphy.rosetta.org_lookup import get_rosetta_state_hash
from murphy.schemas.agent_output import AgentOutput, ContentType, RenderType

logger = logging.getLogger(__name__)


class RosettaAgent:
    """Rosetta world-state consensus agent.

    Implements:
      vote() — all agents must agree on world-state before execution
      resolve_conflict() — confidence-based tie-breaking
      propagate_change() — delta propagation with rollback on failure
      get_state_hash() — SHA-256 of current locked state
    """

    AGENT_NAME = "RosettaAgent"

    def __init__(self, *, org_node_id: str = "platform-engineering") -> None:
        self.agent_id = f"rosetta-{uuid.uuid4().hex[:8]}"
        self.org_node_id = org_node_id
        self._locked_state: Optional[Dict[str, Any]] = None

    # ------------------------------------------------------------------
    # Vote  (ROSETTA-AGENT-VOTE-001)
    # ------------------------------------------------------------------

    def vote(
        self,
        agent_states: List[Dict[str, Any]],
    ) -> bool:
        """All agents must agree on world-state before any executes.

        Each agent_state dict must contain:
          - agent_id (str)
          - state_hash (str)
          - agrees (bool)

        Returns True if all agents agree, False otherwise.
        """
        if not agent_states:
            logger.error("ROSETTA-AGENT-ERR-001: No agent states for vote")
            return False

        for state in agent_states:
            if not isinstance(state, dict):
                logger.error("ROSETTA-AGENT-ERR-002: Invalid agent state: %s", type(state))
                return False
            if not state.get("agrees", False):
                logger.warning(
                    "ROSETTA-AGENT-ERR-003: Agent %s does not agree on state",
                    state.get("agent_id", "unknown"),
                )
                return False

        # All agents agree — lock the state
        self._locked_state = {
            "vote_result": "unanimous",
            "agent_count": len(agent_states),
            "state_hashes": [s.get("state_hash", "") for s in agent_states],
            "locked_at": datetime.now(timezone.utc).isoformat(),
        }
        return True

    # ------------------------------------------------------------------
    # Conflict resolution  (ROSETTA-AGENT-CONFLICT-001)
    # ------------------------------------------------------------------

    def resolve_conflict(
        self,
        agent_a_output: AgentOutput,
        agent_b_output: AgentOutput,
    ) -> tuple[AgentOutput, AgentOutput]:
        """Resolve conflict between two agent outputs.

        Uses confidence_score (parsed from content metadata) and dependency
        order to pick the winner.  The loser gets a retry signal in its
        error field.

        Returns (winner, loser_with_retry_signal).
        """
        score_a = self._extract_confidence(agent_a_output)
        score_b = self._extract_confidence(agent_b_output)

        if score_a >= score_b:
            winner, loser = agent_a_output, agent_b_output
        else:
            winner, loser = agent_b_output, agent_a_output

        # Create retry signal for the loser
        loser_retry = AgentOutput.from_error(
            agent_id=loser.agent_id,
            agent_name=loser.agent_name,
            file_path=loser.file_path,
            org_node_id=loser.org_node_id,
            error_message=(
                f"ROSETTA-AGENT-ERR-004: Conflict resolved — "
                f"lost to {winner.agent_name} "
                f"(confidence {self._extract_confidence(winner):.2f} vs "
                f"{self._extract_confidence(loser):.2f}). Retry required."
            ),
        )

        logger.info(
            "ROSETTA-AGENT-001: Conflict resolved — winner=%s loser=%s",
            winner.agent_name, loser.agent_name,
        )
        return winner, loser_retry

    # ------------------------------------------------------------------
    # Change propagation  (ROSETTA-AGENT-PROP-001)
    # ------------------------------------------------------------------

    def propagate_change(
        self,
        delta: Dict[str, Any],
        downstream_agents: List[Callable[[Dict[str, Any]], bool]],
    ) -> bool:
        """Propagate a state delta to all downstream agents.

        Each downstream_agent callable receives the delta dict and returns
        True if it accepted the change, False otherwise.

        If any propagation fails, ALL changes are rolled back and the
        method returns False.

        Args:
            delta: The state change to propagate.
            downstream_agents: List of callables that accept the delta.

        Returns:
            True if all propagations succeeded, False if rollback occurred.
        """
        if not downstream_agents:
            logger.warning("ROSETTA-AGENT-ERR-005: No downstream agents for propagation")
            return True  # Vacuously true — nothing to propagate to

        applied: List[int] = []
        for i, agent_fn in enumerate(downstream_agents):
            try:
                success = agent_fn(delta)
                if not success:
                    logger.error(
                        "ROSETTA-AGENT-ERR-005: Propagation to agent %d failed", i,
                    )
                    self._rollback(delta, downstream_agents, applied)
                    return False
                applied.append(i)
            except Exception as exc:  # ROSETTA-AGENT-ERR-006
                logger.error(
                    "ROSETTA-AGENT-ERR-006: Propagation to agent %d raised: %s", i, exc,
                )
                self._rollback(delta, downstream_agents, applied)
                return False

        logger.info(
            "ROSETTA-AGENT-002: Propagated delta to %d agents", len(applied),
        )
        return True

    def _rollback(
        self,
        delta: Dict[str, Any],
        agents: List[Callable[[Dict[str, Any]], bool]],
        applied: List[int],
    ) -> None:
        """Roll back applied changes by sending an inverted delta."""
        rollback_delta = {"_rollback": True, **delta}
        for idx in reversed(applied):
            try:
                agents[idx](rollback_delta)
            except Exception as exc:  # ROSETTA-AGENT-ERR-007
                logger.error(
                    "ROSETTA-AGENT-ERR-007: Rollback of agent %d failed: %s", idx, exc,
                )

    # ------------------------------------------------------------------
    # State hash  (ROSETTA-AGENT-HASH-001)
    # ------------------------------------------------------------------

    def get_state_hash(self) -> str:
        """SHA-256 hash of the current locked world-state."""
        if self._locked_state:
            canonical = json.dumps(self._locked_state, sort_keys=True, default=str)
            return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return get_rosetta_state_hash()

    # ------------------------------------------------------------------
    # Run  (ROSETTA-AGENT-RUN-001)
    # ------------------------------------------------------------------

    def run(
        self,
        manifest_state: Dict[str, Any],
        agent_states: List[Dict[str, Any]],
        org_chart: Dict[str, Any],
    ) -> AgentOutput:
        """Execute the Rosetta agent: vote, lock state, return output."""
        try:
            # Vote on world-state consensus
            vote_passed = self.vote(agent_states)
            if not vote_passed:
                return AgentOutput.from_error(
                    agent_id=self.agent_id,
                    agent_name=self.AGENT_NAME,
                    file_path="rosetta_state.json",
                    org_node_id=self.org_node_id,
                    error_message=(
                        "ROSETTA-AGENT-ERR-001: Vote failed — "
                        "agents do not agree on world-state"
                    ),
                )

            # Build the locked state
            locked_state = {
                "manifest": manifest_state,
                "vote": self._locked_state,
                "state_hash": self.get_state_hash(),
                "locked_at": datetime.now(timezone.utc).isoformat(),
            }

            return AgentOutput(
                agent_id=self.agent_id,
                agent_name=self.AGENT_NAME,
                file_path="rosetta_state.json",
                content_type=ContentType.JSON_MANIFEST,
                content=json.dumps(locked_state, indent=2, default=str),
                lang="json",
                depends_on=[],
                org_node_id=self.org_node_id,
                rosetta_state_hash=self.get_state_hash(),
                render_type=RenderType.SYNTAX_HIGHLIGHT,
                hitl_required=False,
                bat_seal_required=True,
            )

        except Exception as exc:  # ROSETTA-AGENT-ERR-008
            logger.error("ROSETTA-AGENT-ERR-008: %s", exc)
            return AgentOutput.from_error(
                agent_id=self.agent_id,
                agent_name=self.AGENT_NAME,
                file_path="rosetta_state.json",
                org_node_id=self.org_node_id,
                error_message=f"ROSETTA-AGENT-ERR-008: {exc}",
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_confidence(output: AgentOutput) -> float:
        """Extract confidence_score from an AgentOutput's content.

        Falls back to 0.5 if not parseable.
        """
        try:
            data = json.loads(output.content)
            if isinstance(data, dict):
                return float(data.get("confidence_score", 0.5))
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
        return 0.5
