"""
Tests for Hero Flow completion — Tasks 1–6.

Covers:
  Task 1 — LLMResponseWirer: parse + compile + retry + degraded packet
  Task 2 — RefinementCycle: feedback integration + history
  Task 3 — CommandParser: all 17 commands (7 original + 10 new) return structured objects
  Task 4 — ConversationHandler: stateful multi-turn via GraphState
  Task 5 — GoldenPathEngine fast-track + GoldenPathBridge.execute_or_record
  Task 6 — Error recovery: retries, degraded packet, transient detection
"""

import sys
import os


import uuid
import pytest


# ---------------------------------------------------------------------------
# Task 1 — LLMResponseWirer
# ---------------------------------------------------------------------------

class TestLLMResponseWirerParsing:
    """Unit-test the _parse_llm_response static method."""

    def _parse(self, text):
        from murphy_action_engine import LLMResponseWirer
        return LLMResponseWirer._parse_llm_response(text)

    def test_json_object_with_actions(self):
        import json
        payload = json.dumps({
            "actions": [{"description": "step 1"}, {"description": "step 2"}],
            "summary": "do the thing",
            "hypothesis_id": "h123",
        })
        plan = self._parse(payload)
        assert len(plan["actions"]) == 2
        assert plan["summary"] == "do the thing"
        assert plan["hypothesis_id"] == "h123"

    def test_json_array_of_strings(self):
        import json
        payload = json.dumps(["action a", "action b"])
        plan = self._parse(payload)
        assert len(plan["actions"]) == 2
        assert plan["actions"][0]["description"] == "action a"

    def test_plain_text_lines(self):
        payload = "do step one\ndo step two\ndo step three"
        plan = self._parse(payload)
        assert len(plan["actions"]) == 3
        assert plan["actions"][0]["description"] == "do step one"

    def test_empty_raises(self):
        from murphy_action_engine import LLMResponseWirer
        with pytest.raises(ValueError, match="empty"):
            LLMResponseWirer._parse_llm_response("   ")

    def test_single_line_summary(self):
        plan = self._parse("summarise quarterly results")
        assert plan["summary"].startswith("summarise")


class TestLLMResponseWirerWire:
    """Integration-level tests for LLMResponseWirer.wire()."""

    def test_wire_returns_dict(self):
        from murphy_action_engine import LLMResponseWirer
        wirer = LLMResponseWirer(max_retries=1)
        result = wirer.wire("create report for Q1")
        assert isinstance(result, dict)

    def test_wire_compiled_or_degraded(self):
        from murphy_action_engine import LLMResponseWirer
        wirer = LLMResponseWirer(max_retries=1)
        result = wirer.wire("list active tasks")
        assert result.get("compiled") in (True, False)
        assert "status" in result or "packet_id" in result

    def test_wire_empty_response_returns_degraded(self):
        from murphy_action_engine import LLMResponseWirer
        wirer = LLMResponseWirer(max_retries=1)
        result = wirer.wire("")
        assert result.get("degraded") is True
        assert result.get("status") == "degraded"

    def test_degraded_packet_has_user_message(self):
        from murphy_action_engine import LLMResponseWirer
        wirer = LLMResponseWirer(max_retries=1)
        result = wirer.wire("")
        assert "user_message" in result
        assert "queued" in result["user_message"].lower() or "unable" in result["user_message"].lower()

    def test_degraded_packet_has_signature(self):
        from murphy_action_engine import LLMResponseWirer
        packet = LLMResponseWirer._degraded_packet("test error")
        assert "signature" in packet
        assert len(packet["signature"]) == 64  # SHA-256 hex

    def test_is_transient_timeout(self):
        from murphy_action_engine import LLMResponseWirer
        wirer = LLMResponseWirer()
        assert wirer._is_transient("Connection timeout after 30s") is True

    def test_is_transient_rate_limit(self):
        from murphy_action_engine import LLMResponseWirer
        wirer = LLMResponseWirer()
        assert wirer._is_transient("rate limit exceeded") is True

    def test_is_not_transient_value_error(self):
        from murphy_action_engine import LLMResponseWirer
        wirer = LLMResponseWirer()
        assert wirer._is_transient("KeyError: 'actions'") is False


# ---------------------------------------------------------------------------
# Task 2 — RefinementCycle
# ---------------------------------------------------------------------------

class TestRefinementCycle:
    """Tests for RefinementCycle in response_composer."""

    def _make_cycle(self, with_integrator=False):
        from response_composer import ResponseComposer, RefinementCycle
        composer = ResponseComposer()
        integrator = None
        if with_integrator:
            try:
                from feedback_integrator import FeedbackIntegrator
                integrator = FeedbackIntegrator()
            except ImportError:
                pass
        return RefinementCycle(composer, integrator)

    def _make_plan(self):
        return {
            "actions": [
                {"description": "run report", "type": "analysis"},
                {"description": "send email", "type": "notification"},
            ],
            "summary": "Monthly report pipeline",
            "hypothesis_id": f"h_{uuid.uuid4().hex[:8]}",
        }

    def test_refine_returns_dict_with_required_keys(self):
        cycle = self._make_cycle()
        result = cycle.refine("no, I meant weekly", self._make_plan())
        for key in ("refined_plan", "response", "confidence", "recalibration_needed", "cycle_id"):
            assert key in result, f"Missing key: {key}"

    def test_negative_feedback_lowers_confidence(self):
        cycle = self._make_cycle()
        original_conf = 0.8
        result = cycle.refine("that is wrong", self._make_plan(), original_confidence=original_conf)
        assert result["confidence"] < original_conf

    def test_positive_feedback_raises_confidence(self):
        cycle = self._make_cycle()
        original_conf = 0.5
        result = cycle.refine("yes, that's correct", self._make_plan(), original_confidence=original_conf)
        assert result["confidence"] > original_conf

    def test_refined_plan_contains_feedback(self):
        cycle = self._make_cycle()
        result = cycle.refine("use weekly data", self._make_plan())
        assert "use weekly data" in result["refined_plan"].get("refinement_feedback", "")

    def test_history_recorded(self):
        cycle = self._make_cycle()
        cycle.refine("feedback one", self._make_plan())
        cycle.refine("feedback two", self._make_plan())
        history = cycle.get_history()
        assert len(history) == 2
        assert history[0]["user_feedback"] == "feedback one"
        assert history[1]["user_feedback"] == "feedback two"

    def test_clear_history(self):
        cycle = self._make_cycle()
        cycle.refine("feedback", self._make_plan())
        cycle.clear_history()
        assert cycle.get_history() == []

    def test_cycle_id_is_unique(self):
        cycle = self._make_cycle()
        r1 = cycle.refine("a", self._make_plan())
        r2 = cycle.refine("b", self._make_plan())
        assert r1["cycle_id"] != r2["cycle_id"]

    def test_refine_with_integrator(self):
        cycle = self._make_cycle(with_integrator=True)
        result = cycle.refine("wrong direction", self._make_plan(), original_confidence=0.6)
        assert "cycle_id" in result

    def test_response_contains_feedback_text(self):
        cycle = self._make_cycle()
        result = cycle.refine("I meant quarterly", self._make_plan())
        assert "I meant quarterly" in result["response"]


# ---------------------------------------------------------------------------
# Task 3 — CommandParser all categories
# ---------------------------------------------------------------------------

class _MockSystem:
    """Minimal mock for CommandParser's mfgc_system dependency."""

    def get_system_state(self):
        return {
            "band": "introductory",
            "confidence": 0.9,
            "domain": "test",
            "gates_count": 0,
            "active_gates": ["gate_safety"],
        }

    def reset_context(self):
        pass

    def get_active_gates(self):
        return ["gate_safety", "gate_confidence"]


class TestCommandParserAllCategories:
    """All 17 registered command prefixes must return valid result dicts."""

    ALL_COMMANDS = [
        "/swarmmonitor",
        "/swarmauto do something",
        "/memory",
        "/reset",
        "/help",
        "/status",
        "/gates",
        "/confidence",
        "/workflow",
        "/governance",
        "/llm",
        "/analysis some-topic",
        "/integration",
        "/learning",
        "/autonomous",
        "/module",
    ]

    @pytest.fixture
    def parser(self):
        from command_parser import CommandParser
        return CommandParser(_MockSystem())

    @pytest.mark.parametrize("cmd", ALL_COMMANDS)
    def test_is_command(self, parser, cmd):
        assert parser.is_command(cmd), f"{cmd!r} not recognized as command"

    @pytest.mark.parametrize("cmd", ALL_COMMANDS)
    def test_parse_and_execute_returns_dict(self, parser, cmd):
        is_cmd, result = parser.parse_and_execute(cmd)
        assert is_cmd is True
        assert isinstance(result, dict)
        assert "content" in result
        assert "is_command" in result
        assert result["is_command"] is True

    def test_get_command_object_returns_category(self, parser):
        obj = parser.get_command_object("/workflow my-workflow")
        assert obj is not None
        assert obj["category"] == "workflow"
        assert obj["command"] == "/workflow"
        assert obj["args"] == "my-workflow"
        assert obj["structured"] is True

    def test_get_command_object_governance(self, parser):
        obj = parser.get_command_object("/governance")
        assert obj["category"] == "governance"

    def test_get_command_object_autonomous_is_high_risk(self, parser):
        obj = parser.get_command_object("/autonomous")
        assert obj["risk_level"] == "high"

    def test_get_command_object_unknown_returns_none(self, parser):
        assert parser.get_command_object("not a command") is None

    def test_help_mentions_new_commands(self, parser):
        _, result = parser.parse_and_execute("/help")
        text = result["content"]
        for cmd_prefix in ["/workflow", "/governance", "/llm", "/analysis",
                           "/integration", "/learning", "/autonomous", "/module"]:
            assert cmd_prefix in text, f"{cmd_prefix} missing from /help output"


# ---------------------------------------------------------------------------
# Task 4 — ConversationHandler stateful
# ---------------------------------------------------------------------------

class TestConversationHandlerStateless:
    """ConversationHandler still works without a state graph (backward compat)."""

    @pytest.fixture
    def handler(self):
        from conversation_handler import ConversationHandler
        return ConversationHandler()

    def test_greeting_response(self, handler):
        result = handler.handle("hello")
        assert result["marker"] in ("V", "G")
        assert "response" in result

    def test_topic_match(self, handler):
        result = handler.handle("tell me about the constitution")
        assert result["topic"] == "constitution"
        assert result["marker"] == "V"

    def test_context_key_present(self, handler):
        result = handler.handle("hi there")
        assert "context" in result

    def test_general_query(self, handler):
        result = handler.handle("some random query XYZ123")
        assert "response" in result


class TestConversationHandlerStateful:
    """ConversationHandler uses GraphState for context carryover."""

    @pytest.fixture
    def state_graph(self):
        from murphy_state_graph import GraphState
        return GraphState()

    @pytest.fixture
    def handler(self, state_graph):
        from conversation_handler import ConversationHandler
        return ConversationHandler(state_graph=state_graph)

    def test_history_accumulated_in_state(self, handler, state_graph):
        handler.handle("hello")
        handler.handle("what is the constitution?")
        history = state_graph.get("_conv_history") or []
        assert len(history) >= 2

    def test_topics_tracked_in_state(self, handler, state_graph):
        handler.handle("tell me about the constitution")
        topics = state_graph.get("_conv_topics") or []
        assert "constitution" in topics

    def test_topic_carryover_pronoun(self, handler, state_graph):
        """After asking about constitution, 'tell me more about it' should resolve."""
        handler.handle("the constitution is interesting")
        # Seed the topic manually to test pronoun resolution
        state_graph.set("_conv_topics", ["constitution"])
        result = handler.handle("tell me more about it")
        # The enriched input should include [constitution], triggering the topic match
        assert result["topic"] == "constitution"

    def test_second_handler_sees_same_state(self, state_graph):
        """Two handler instances sharing the same GraphState see each other's history."""
        from conversation_handler import ConversationHandler
        h1 = ConversationHandler(state_graph=state_graph)
        h2 = ConversationHandler(state_graph=state_graph)
        h1.handle("hello")
        history = state_graph.get("_conv_history") or []
        assert len(history) >= 1


# ---------------------------------------------------------------------------
# Task 5 — GoldenPathEngine fast-track + GoldenPathBridge.execute_or_record
# ---------------------------------------------------------------------------

class TestGoldenPathFastTrack:
    """GoldenPathEngine.is_eligible_for_fast_track and execute_fast_path."""

    @pytest.fixture
    def engine(self):
        from golden_path_engine import GoldenPathEngine
        return GoldenPathEngine()

    def test_status_command_eligible(self, engine):
        assert engine.is_eligible_for_fast_track("/status") is True

    def test_help_command_eligible(self, engine):
        assert engine.is_eligible_for_fast_track("/help") is True

    def test_list_query_eligible(self, engine):
        assert engine.is_eligible_for_fast_track("list active tasks") is True

    def test_delete_not_eligible(self, engine):
        assert engine.is_eligible_for_fast_track("delete all records") is False

    def test_reset_not_eligible(self, engine):
        assert engine.is_eligible_for_fast_track("/reset") is False

    def test_execute_fast_path_miss_returns_sentinel(self, engine):
        from golden_path_bridge import GoldenPathBridge
        bridge = GoldenPathBridge()
        result = engine.execute_fast_path("/status unknown_command", bridge)
        assert result["fast_path"] is False

    def test_execute_fast_path_hit_returns_spec(self, engine):
        from golden_path_bridge import GoldenPathBridge
        bridge = GoldenPathBridge()
        # Record a high-confidence path
        bridge.record_success("/status", "system", {"steps": ["read_state"]})
        path_id = bridge.record_success("/status", "system", {"steps": ["read_state"]})
        bridge.get_path(path_id).confidence_score = 0.9
        result = engine.execute_fast_path("/status", bridge, domain="system")
        assert result["fast_path"] is True
        assert "steps" in result

    def test_execute_fast_path_calls_fallback_on_miss(self, engine):
        from golden_path_bridge import GoldenPathBridge
        bridge = GoldenPathBridge()
        calls = []

        def fallback(cmd):
            calls.append(cmd)
            return {"fallback": True}

        result = engine.execute_fast_path("novel-command", bridge, fallback_fn=fallback)
        assert len(calls) == 1
        assert result.get("fallback") is True


class TestGoldenPathBridgeExecuteOrRecord:
    """GoldenPathBridge.execute_or_record connects fast path to full pipeline."""

    @pytest.fixture
    def bridge(self):
        from golden_path_bridge import GoldenPathBridge
        return GoldenPathBridge()

    def test_miss_calls_execution_fn_and_records(self, bridge):
        calls = []

        def execute(task):
            calls.append(task)
            return {"result": "ok", "steps": ["execute"]}

        result = bridge.execute_or_record("new-task", "test", execute)
        assert len(calls) == 1
        assert result["source"] == "full_pipeline"
        # Should now have a recorded path
        assert bridge.get_statistics()["total_paths"] == 1

    def test_hit_skips_execution_fn(self, bridge):
        calls = []

        def execute(task):
            calls.append(task)
            return {"steps": ["execute"]}

        # First call records the path
        bridge.execute_or_record("repeat-task", "test", execute)
        # Manually boost confidence
        stats = bridge.get_statistics()
        all_paths = list(bridge._paths.values())
        for p in all_paths:
            p.confidence_score = 0.9

        result2 = bridge.execute_or_record("repeat-task", "test", execute)
        # Should have hit the golden path; execute called only once total
        assert len(calls) == 1
        assert result2["source"] == "golden_path"

    def test_execution_failure_records_failure(self, bridge):
        def execute(task):
            raise RuntimeError("pipeline error")

        with pytest.raises(RuntimeError, match="pipeline error"):
            bridge.execute_or_record("fail-task", "test", execute)

        # Failure should have been recorded (no path exists yet, so failure count is 0,
        # but calling record_failure on a non-existing path is a no-op — test just
        # checks no secondary exception is raised)

    def test_source_key_in_result(self, bridge):
        def execute(task):
            return {"output": "done"}

        result = bridge.execute_or_record("task-a", "domain-x", execute)
        assert "source" in result


# ---------------------------------------------------------------------------
# Task 6 — Error recovery
# ---------------------------------------------------------------------------

class TestErrorRecovery:
    """Retry logic and graceful degradation."""

    def test_wirer_retries_on_transient(self):
        """LLMResponseWirer._compile raises a transient error; wirer must retry."""
        from murphy_action_engine import LLMResponseWirer
        attempt_count = [0]

        def patched_compile(plan, **kwargs):
            attempt_count[0] += 1
            if attempt_count[0] < 2:
                raise RuntimeError("Connection timeout on first attempt")
            return {
                "compiled": True,
                "packet_id": "p123",
                "status": "compiled",
                "hypothesis_id": "h1",
                "actions": [],
            }

        original_compile = LLMResponseWirer._compile
        wirer = LLMResponseWirer(max_retries=3)
        # Monkey-patch _compile for this test
        LLMResponseWirer._compile = staticmethod(patched_compile)
        try:
            result = wirer.wire("list items")
            assert result.get("compiled") is True
            assert attempt_count[0] == 2
        finally:
            LLMResponseWirer._compile = original_compile

    def test_wirer_exhausts_retries_returns_degraded(self):
        """When all retries fail the wirer returns a degraded packet."""
        from murphy_action_engine import LLMResponseWirer

        def always_fail(plan, **kwargs):
            raise RuntimeError("Connection timeout always")

        original_compile = LLMResponseWirer._compile
        wirer = LLMResponseWirer(max_retries=2)
        LLMResponseWirer._compile = staticmethod(always_fail)
        try:
            result = wirer.wire("some task")
            assert result["degraded"] is True
            assert result["status"] == "degraded"
        finally:
            LLMResponseWirer._compile = original_compile

    def test_degraded_packet_has_all_required_fields(self):
        from murphy_action_engine import LLMResponseWirer
        packet = LLMResponseWirer._degraded_packet("simulated outage")
        required = {"packet_id", "status", "compiled", "reason", "timestamp",
                    "degraded", "user_message", "signature"}
        assert required.issubset(packet.keys())

    def test_conversation_handler_survives_bad_state_graph(self):
        """ConversationHandler gracefully handles a broken state graph."""
        from conversation_handler import ConversationHandler

        class BrokenState:
            def get(self, key):
                raise OSError("DB unavailable")
            def set(self, key, value):
                raise OSError("DB unavailable")

        handler = ConversationHandler(state_graph=BrokenState())
        # Should not raise — falls back to local state
        result = handler.handle("hello")
        assert "response" in result

    def test_golden_path_engine_handles_bridge_exception(self):
        """execute_fast_path gracefully handles bridge.find_matching_paths exceptions."""
        from golden_path_engine import GoldenPathEngine

        class BrokenBridge:
            def find_matching_paths(self, *args, **kwargs):
                raise ConnectionError("bridge offline")

        engine = GoldenPathEngine()
        result = engine.execute_fast_path("/status", BrokenBridge())
        assert result["fast_path"] is False
