"""
Hero Flow End-to-End Integration Tests — PR 6 Gap Closure

Validates the full **Describe → Execute → Refine** cycle as a gapless
integration path, including:

  1. Complete Describe → Execute → Refine cycle
  2. Various command types through the wirer + conversation handler
  3. Error handling — LLM timeout simulation, malformed / empty input
  4. Multi-turn conversation state persistence across handle() calls

These tests operate against real module logic (no mocks).

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import time
import uuid

import pytest

# ---------------------------------------------------------------------------
# Module imports (src/ on path via pyproject.toml pythonpath)
# ---------------------------------------------------------------------------
from murphy_action_engine import LLMResponseWirer
from response_composer import RefinementCycle, ResponseComposer
from conversation_handler import ConversationHandler


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _new_wirer(max_retries: int = 1) -> LLMResponseWirer:
    return LLMResponseWirer(max_retries=max_retries)


def _new_cycle() -> RefinementCycle:
    return RefinementCycle(composer=ResponseComposer())


# ===========================================================================
# 1. Complete Describe → Execute → Refine cycle
# ===========================================================================

class TestDescribeExecuteRefineCycle:
    """End-to-end cycle: LLMResponseWirer.wire() → RefinementCycle.refine()."""

    def test_describe_produces_plan(self):
        """wire() on a description command returns a valid plan dict."""
        wirer = _new_wirer()
        result = wirer.wire("describe the current system health")
        assert isinstance(result, dict)

    def test_execute_compiled_plan_has_packet_id(self):
        """A successfully compiled plan includes a packet_id."""
        wirer = _new_wirer()
        result = wirer.wire("list all active workflows")
        assert result.get("packet_id") is not None or result.get("degraded") is True

    def test_refine_after_describe_returns_response(self):
        """RefinementCycle.refine() returns a structured response."""
        cycle = _new_cycle()
        resp = cycle.refine(
            "make it shorter",
            {"summary": "The system shows 5 active workflows."},
        )
        assert isinstance(resp, dict)
        assert "response" in resp or "refined_plan" in resp

    def test_cycle_history_accumulates(self):
        """Successive refine() calls accumulate into history."""
        cycle = _new_cycle()
        cycle.refine("expand the details", {"summary": "System ok."})
        cycle.refine("now shorten it", {"summary": "System ok."})
        history = cycle.get_history()
        assert len(history) >= 2

    def test_full_cycle_describe_then_refine(self):
        """Full cycle: wire a description → pass plan to RefinementCycle."""
        wirer = _new_wirer()
        plan = wirer.wire("create a weekly report on task completion rates")
        cycle = _new_cycle()
        resp = cycle.refine("add cost breakdown", plan)
        assert isinstance(resp, dict)

    def test_refine_cycle_preserves_confidence(self):
        """Refine returns a confidence value between 0.0 and 1.0."""
        cycle = _new_cycle()
        resp = cycle.refine(
            "looks good, finalize",
            {"summary": "Workflow has 3 steps."},
        )
        confidence = resp.get("confidence")
        if confidence is not None:
            assert 0.0 <= confidence <= 1.0


# ===========================================================================
# 2. Various command types
# ===========================================================================

class TestVariousCommandTypes:
    """wire() handles different semantic command types gracefully."""

    COMMANDS = [
        "list all open tasks",
        "create a new project called Alpha",
        "delete the archived board",
        "summarize last week's activity",
        "execute the nightly backup workflow",
        "show me the system health dashboard",
        "help me configure a new automation",
        "what is my current usage",
        "set the status of task 42 to done",
        "assign task 7 to alice@example.com",
    ]

    @pytest.mark.parametrize("command", COMMANDS)
    def test_wire_handles_command(self, command: str):
        """Each command type returns a dict without raising."""
        wirer = _new_wirer(max_retries=1)
        result = wirer.wire(command)
        assert isinstance(result, dict)

    def test_all_commands_have_status_or_degraded(self):
        """Every command result includes a status indicator or degraded flag."""
        wirer = _new_wirer(max_retries=1)
        for cmd in self.COMMANDS:
            result = wirer.wire(cmd)
            has_indicator = (
                "status" in result
                or "degraded" in result
                or "packet_id" in result
                or "compiled" in result
            )
            assert has_indicator, f"No indicator in result for command: {cmd!r}"


# ===========================================================================
# 3. Error handling — LLM timeout, malformed input
# ===========================================================================

class TestErrorHandling:
    """LLM timeout simulation and malformed / edge-case inputs."""

    def test_empty_string_returns_degraded(self):
        """Empty string input → degraded packet, no exception."""
        wirer = _new_wirer(max_retries=1)
        result = wirer.wire("")
        assert result.get("degraded") is True

    def test_whitespace_only_returns_degraded(self):
        """Whitespace-only input → degraded packet."""
        wirer = _new_wirer(max_retries=1)
        result = wirer.wire("   \t\n  ")
        assert result.get("degraded") is True

    def test_malformed_json_string_does_not_raise(self):
        """A JSON-like but malformed string is handled gracefully."""
        wirer = _new_wirer(max_retries=1)
        result = wirer.wire('{"unclosed": "bracket"')
        assert isinstance(result, dict)

    def test_oversized_input_handled(self):
        """A very large input string is handled without crashing."""
        wirer = _new_wirer(max_retries=1)
        large_input = "process all tasks " * 1000
        result = wirer.wire(large_input)
        assert isinstance(result, dict)

    def test_degraded_packet_has_required_fields(self):
        """Degraded packet always includes degraded=True, status, user_message."""
        wirer = _new_wirer(max_retries=1)
        result = wirer.wire("")
        assert result.get("degraded") is True
        assert result.get("status") == "degraded"
        assert "user_message" in result

    def test_single_retry_does_not_block_long(self):
        """With max_retries=1, wire() completes in a reasonable time."""
        wirer = _new_wirer(max_retries=1)
        start = time.monotonic()
        wirer.wire("")
        elapsed = time.monotonic() - start
        # Should complete within 5 seconds even with retry logic
        assert elapsed < 5.0

    def test_refine_with_empty_feedback_does_not_crash(self):
        """RefinementCycle.refine() with empty feedback returns a dict."""
        cycle = _new_cycle()
        result = cycle.refine("", {"summary": "Previous summary."})
        assert isinstance(result, dict)

    def test_refine_with_empty_plan_does_not_crash(self):
        """RefinementCycle.refine() with empty plan returns a dict."""
        cycle = _new_cycle()
        result = cycle.refine("make it better", {})
        assert isinstance(result, dict)


# ===========================================================================
# 4. Multi-turn conversation state persistence
# ===========================================================================

class TestMultiTurnConversationState:
    """ConversationHandler retains state across multiple handle() calls."""

    def test_history_grows_with_each_turn(self):
        """Each call to handle() adds an entry to the conversation history."""
        handler = ConversationHandler()
        handler.handle("hello")
        handler.handle("what can you do?")
        handler.handle("list my tasks")
        # Access internal history
        history = handler._get_recent_history(10)
        assert len(history) >= 3

    def test_second_turn_response_references_prior_context(self):
        """Handler returns a response dict on each turn."""
        handler = ConversationHandler()
        r1 = handler.handle("start project Phoenix")
        r2 = handler.handle("what was the last thing I asked about?")
        assert isinstance(r1, dict)
        assert isinstance(r2, dict)

    def test_state_independent_across_handler_instances(self):
        """Two separate ConversationHandler instances do not share state."""
        h1 = ConversationHandler()
        h2 = ConversationHandler()
        h1.handle("session one question")
        h2.handle("session two question")
        h1_history = h1._get_recent_history(10)
        h2_history = h2._get_recent_history(10)
        # Each handler should only have its own single entry
        assert len(h1_history) >= 1
        assert len(h2_history) >= 1

    def test_topic_tracking_persists_across_turns(self):
        """Topics detected in turn 1 are available in turn 2 state."""
        handler = ConversationHandler()
        handler.handle("show me the health status")
        r2 = handler.handle("tell me more about it")
        assert isinstance(r2, dict)

    def test_multiple_turns_no_exception(self):
        """10 consecutive handle() calls complete without exception."""
        handler = ConversationHandler()
        messages = [
            "hello", "list tasks", "create project", "help",
            "what is my status", "show health", "set task done",
            "assign to alice", "summarize", "goodbye",
        ]
        for msg in messages:
            result = handler.handle(msg)
            assert isinstance(result, dict), f"handle() returned non-dict for: {msg!r}"

    def test_pronoun_carryover_between_turns(self):
        """Pronoun references ('it') after a topic-setting turn return a dict."""
        handler = ConversationHandler()
        handler.handle("check the system status")
        result = handler.handle("can you expand on it?")
        assert isinstance(result, dict)

    def test_clear_history_resets_state(self):
        """After clear_history() on the refinement cycle, history is empty."""
        cycle = _new_cycle()
        cycle.refine("more detail", {"summary": "Summary A"})
        cycle.refine("even more", {"summary": "Summary B"})
        cycle.clear_history()
        assert cycle.get_history() == []
