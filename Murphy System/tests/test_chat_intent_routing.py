"""
Tests for chat intent routing in the Murphy System runtime.

Validates that the /api/chat endpoint correctly:
1. Detects known intents (help, status, modules, etc.)
2. Routes them to the appropriate handler
3. Does NOT blindly advance the onboarding flow for recognized commands
4. Advances the onboarding flow only for unrecognized input during an active flow
5. Returns to intent routing after the onboarding flow completes
"""

import unittest
import importlib.util
import sys
import os

# Load the runtime module (filename contains dots)
_spec = importlib.util.spec_from_file_location(
    "murphy_runtime",
    os.path.join(os.path.dirname(__file__), "..", "murphy_system_1.0_runtime.py"),
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
MurphySystem = _mod.MurphySystem


class TestIntentDetection(unittest.TestCase):
    """Test that _detect_intent returns the correct intent for various inputs."""

    def setUp(self):
        self.murphy = MurphySystem()

    def test_greeting_intents(self):
        for msg in ["hello", "hi", "hey", "greetings", "good morning"]:
            self.assertEqual(
                self.murphy._detect_intent(msg),
                "greeting",
                f"Expected 'greeting' for '{msg}'",
            )

    def test_help_intent(self):
        self.assertEqual(self.murphy._detect_intent("help"), "help")
        self.assertEqual(self.murphy._detect_intent("commands"), "help")

    def test_modules_intent(self):
        self.assertEqual(self.murphy._detect_intent("show modules"), "modules")
        self.assertEqual(self.murphy._detect_intent("modules"), "modules")

    def test_status_intent(self):
        self.assertEqual(self.murphy._detect_intent("status"), "status")
        self.assertEqual(self.murphy._detect_intent("dashboard"), "status")

    def test_sales_report_intent(self):
        self.assertEqual(self.murphy._detect_intent("sales report"), "sales_report")

    def test_compliance_before_status(self):
        """compliance status should match 'compliance', not 'status'."""
        self.assertEqual(self.murphy._detect_intent("compliance status"), "compliance")

    def test_onboarding_intent(self):
        self.assertEqual(self.murphy._detect_intent("start interview"), "onboarding")

    def test_unrecognized_returns_none(self):
        self.assertIsNone(self.murphy._detect_intent("configure the flux capacitor"))

    def test_billing_intent(self):
        self.assertEqual(self.murphy._detect_intent("billing"), "billing")
        self.assertEqual(self.murphy._detect_intent("subscription"), "billing")

    def test_corrections_intent(self):
        self.assertEqual(self.murphy._detect_intent("corrections"), "corrections")

    def test_hitl_intent(self):
        self.assertEqual(self.murphy._detect_intent("hitl"), "hitl")

    def test_plan_intent(self):
        self.assertEqual(self.murphy._detect_intent("plan"), "plan")

    def test_info_intent(self):
        self.assertEqual(self.murphy._detect_intent("info"), "info")

    def test_integrations_intent(self):
        self.assertEqual(self.murphy._detect_intent("integrations"), "integrations")

    def test_librarian_intent(self):
        self.assertEqual(self.murphy._detect_intent("librarian"), "librarian")


class TestChatRouting(unittest.TestCase):
    """Test that handle_chat routes intents correctly without advancing the flow."""

    def setUp(self):
        self.murphy = MurphySystem()

    def test_help_returns_command_list(self):
        result = self.murphy.handle_chat("help", session_id="test-help", use_mfgc=False)
        self.assertTrue(result["success"])
        self.assertEqual(result.get("intent"), "help")
        self.assertIn("start interview", result["message"])

    def test_greeting_returns_welcome(self):
        result = self.murphy.handle_chat("hello", session_id="test-greet", use_mfgc=False)
        self.assertTrue(result["success"])
        self.assertEqual(result.get("intent"), "greeting")
        self.assertIn("Murphy", result["message"])

    def test_status_returns_system_status(self):
        result = self.murphy.handle_chat("status", session_id="test-status", use_mfgc=False)
        self.assertTrue(result["success"])
        self.assertEqual(result.get("intent"), "status")
        self.assertIn("running", result["message"])

    def test_modules_returns_module_list(self):
        result = self.murphy.handle_chat("show modules", session_id="test-mods", use_mfgc=False)
        self.assertTrue(result["success"])
        self.assertEqual(result.get("intent"), "modules")
        self.assertIn("Loaded Modules", result["message"])

    def test_help_does_not_advance_flow(self):
        """Sending 'help' should not increment the flow stage."""
        result1 = self.murphy.handle_chat("help", session_id="test-no-adv", use_mfgc=False)
        result2 = self.murphy.handle_chat("help", session_id="test-no-adv", use_mfgc=False)
        self.assertEqual(result1.get("intent"), "help")
        self.assertEqual(result2.get("intent"), "help")
        # No flow_stage in intent responses
        self.assertNotIn("flow_stage", result1)

    def test_compliance_status_routes_to_compliance(self):
        result = self.murphy.handle_chat("compliance status", session_id="test-comp", use_mfgc=False)
        self.assertTrue(result["success"])
        self.assertEqual(result.get("intent"), "compliance")
        self.assertIn("Compliance", result["message"])


class TestOnboardingFlow(unittest.TestCase):
    """Test that the onboarding flow works correctly."""

    def setUp(self):
        self.murphy = MurphySystem()
        self.sid = "test-onboard"

    def test_start_interview_begins_flow(self):
        result = self.murphy.handle_chat("start interview", session_id=self.sid, use_mfgc=False)
        self.assertTrue(result["success"])
        self.assertEqual(result.get("intent"), "onboarding")
        self.assertIn("Step 1", result["message"])

    def test_flow_advances_with_answers(self):
        self.murphy.handle_chat("start interview", session_id=self.sid, use_mfgc=False)
        result = self.murphy.handle_chat("Inoni LLC", session_id=self.sid, use_mfgc=False)
        self.assertTrue(result["success"])
        self.assertIn("Captured signup", result["message"])

    def test_flow_completes_after_all_steps(self):
        answers = [
            "start interview",
            "Inoni LLC",
            "United States",
            "email, CRM",
            "sales pipeline",
            "weekly review",
            "Professional",
        ]
        for ans in answers:
            result = self.murphy.handle_chat(ans, session_id=self.sid, use_mfgc=False)
        # After completion, intent routing should resume
        result = self.murphy.handle_chat("status", session_id=self.sid, use_mfgc=False)
        self.assertEqual(result.get("intent"), "status")

    def test_reset_restarts_flow(self):
        self.murphy.handle_chat("start interview", session_id=self.sid, use_mfgc=False)
        self.murphy.handle_chat("Inoni LLC", session_id=self.sid, use_mfgc=False)
        result = self.murphy.handle_chat("reset", session_id=self.sid, use_mfgc=False)
        # After reset, intent detection should be active again
        # (reset triggers the flow reset, then advances one step)
        self.assertTrue(result["success"])


class TestNaturalLanguageRouting(unittest.TestCase):
    """Test that unrecognized input routes through Librarian, not the wizard."""

    def setUp(self):
        self.murphy = MurphySystem()
        self.sid = "test-nl"

    def test_freeform_text_does_not_advance_wizard(self):
        """Sending freeform text (no recognised intent) should NOT advance the
        onboarding wizard when not in an active flow."""
        result = self.murphy.handle_chat(
            "hello there, help me automate selling widgets",
            session_id=self.sid,
            use_mfgc=False,
        )
        self.assertTrue(result["success"])
        # Should have a reply_text (librarian path), not flow_stage
        self.assertNotIn("flow_stage", result)
        self.assertIn("message", result)

    def test_freeform_text_returns_librarian_response(self):
        """Freeform NL should route through librarian_ask."""
        result = self.murphy.handle_chat(
            "how do I connect my CRM to Murphy?",
            session_id=self.sid,
            use_mfgc=False,
        )
        self.assertTrue(result["success"])
        self.assertIn("intent", result)
        self.assertIn("message", result)
        # Should return suggested commands
        self.assertIn("suggested_commands", result)

    def test_freeform_hello_produces_helpful_response(self):
        """Typing 'tell me a joke' (no intent match) should give a librarian
        response rather than a wizard step."""
        result = self.murphy.handle_chat(
            "tell me a joke",
            session_id=self.sid,
            use_mfgc=False,
        )
        self.assertTrue(result["success"])
        self.assertNotIn("flow_stage", result)
        self.assertIn("message", result)
        # Should not contain onboarding step language
        self.assertNotIn("Captured signup", result.get("message", ""))

    def test_wizard_only_advances_when_in_flow(self):
        """Verify the wizard only advances when in_flow is True."""
        # Start the onboarding flow
        self.murphy.handle_chat("start interview", session_id=self.sid, use_mfgc=False)
        # This should advance the wizard (we're in_flow)
        result = self.murphy.handle_chat("Inoni LLC", session_id=self.sid, use_mfgc=False)
        self.assertIn("Captured", result["message"])

    def test_repeated_freeform_does_not_loop_wizard(self):
        """Sending multiple freeform messages should not create a wizard loop."""
        for msg in ["hello", "what can you do?", "integrate my email"]:
            result = self.murphy.handle_chat(msg, session_id=self.sid, use_mfgc=False)
            self.assertTrue(result["success"])
            self.assertNotIn("flow_stage", result)


class TestLLMStatus(unittest.TestCase):
    """Test LLM status reporting."""

    def setUp(self):
        self.murphy = MurphySystem()

    def test_llm_status_not_configured_by_default(self):
        """Without env vars, LLM should report as not configured."""
        # Clear relevant env vars for test
        old_provider = os.environ.pop("MURPHY_LLM_PROVIDER", None)
        old_key = os.environ.pop("GROQ_API_KEY", None)
        try:
            status = self.murphy._get_llm_status()
            self.assertFalse(status["enabled"])
            self.assertFalse(status["healthy"])
            self.assertIn("error", status)
        finally:
            if old_provider is not None:
                os.environ["MURPHY_LLM_PROVIDER"] = old_provider
            if old_key is not None:
                os.environ["GROQ_API_KEY"] = old_key

    def test_llm_status_groq_no_key(self):
        """Provider set to groq but no API key should be unhealthy."""
        old_provider = os.environ.get("MURPHY_LLM_PROVIDER")
        old_key = os.environ.pop("GROQ_API_KEY", None)
        os.environ["MURPHY_LLM_PROVIDER"] = "groq"
        try:
            status = self.murphy._get_llm_status()
            self.assertFalse(status["enabled"])
            self.assertEqual(status["provider"], "groq")
            self.assertIn("GROQ_API_KEY", status.get("error", ""))
        finally:
            if old_provider is not None:
                os.environ["MURPHY_LLM_PROVIDER"] = old_provider
            else:
                os.environ.pop("MURPHY_LLM_PROVIDER", None)
            if old_key is not None:
                os.environ["GROQ_API_KEY"] = old_key

    def test_llm_status_groq_with_key(self):
        """Provider groq + API key should report healthy."""
        old_provider = os.environ.get("MURPHY_LLM_PROVIDER")
        old_key = os.environ.get("GROQ_API_KEY")
        os.environ["MURPHY_LLM_PROVIDER"] = "groq"
        os.environ["GROQ_API_KEY"] = "test-key-123"
        try:
            status = self.murphy._get_llm_status()
            self.assertTrue(status["enabled"])
            self.assertTrue(status["healthy"])
            self.assertEqual(status["provider"], "groq")
            self.assertIsNotNone(status["model"])
        finally:
            if old_provider is not None:
                os.environ["MURPHY_LLM_PROVIDER"] = old_provider
            else:
                os.environ.pop("MURPHY_LLM_PROVIDER", None)
            if old_key is not None:
                os.environ["GROQ_API_KEY"] = old_key
            else:
                os.environ.pop("GROQ_API_KEY", None)

    def test_librarian_status(self):
        """Librarian status should report enabled/healthy."""
        status = self.murphy._get_librarian_status()
        self.assertIn("enabled", status)
        self.assertIn("healthy", status)

    def test_system_status_includes_llm_and_librarian(self):
        """get_system_status must include llm and librarian keys."""
        status = self.murphy.get_system_status()
        self.assertIn("llm", status)
        self.assertIn("librarian", status)
        self.assertIn("enabled", status["llm"])
        self.assertIn("enabled", status["librarian"])


class TestDeterministicFallback(unittest.TestCase):
    """Test fallback messaging when LLM is not configured."""

    def setUp(self):
        self.murphy = MurphySystem()
        self.sid = "test-fallback"
        # Ensure LLM is not configured
        self._old_provider = os.environ.pop("MURPHY_LLM_PROVIDER", None)
        self._old_key = os.environ.pop("GROQ_API_KEY", None)

    def tearDown(self):
        if self._old_provider is not None:
            os.environ["MURPHY_LLM_PROVIDER"] = self._old_provider
        if self._old_key is not None:
            os.environ["GROQ_API_KEY"] = self._old_key

    def test_fallback_includes_deterministic_message(self):
        """When LLM is off, librarian_ask should explain deterministic mode."""
        result = self.murphy.librarian_ask("hello", session_id=self.sid)
        self.assertTrue(result["success"])
        self.assertEqual(result["mode"], "deterministic")
        self.assertIn("deterministic mode", result["message"])
        self.assertIn("MURPHY_LLM_PROVIDER", result["message"])

    def test_fallback_still_suggests_commands(self):
        """Deterministic mode should still suggest useful commands."""
        result = self.murphy.librarian_ask("I want to automate my pipeline", session_id=self.sid)
        self.assertTrue(result["success"])
        self.assertIn("suggested_commands", result)
        self.assertTrue(len(result["suggested_commands"]) > 0)

    def test_fallback_onboarding_suggestion(self):
        """Asking about onboarding should get a helpful response."""
        result = self.murphy.librarian_ask("help me get started", session_id=self.sid)
        self.assertIn("start interview", result["message"].lower())

    def test_nl_intent_classification(self):
        """_classify_nl_intent should return correct categories."""
        self.assertEqual(self.murphy._classify_nl_intent("how is the system running?"), "status_inquiry")
        self.assertEqual(self.murphy._classify_nl_intent("help me get started with onboarding"), "onboarding")
        self.assertEqual(self.murphy._classify_nl_intent("connect my CRM"), "integration_discovery")
        self.assertEqual(self.murphy._classify_nl_intent("automate my workflow"), "plan_request")
        self.assertEqual(self.murphy._classify_nl_intent("run the deployment"), "execution_request")
        self.assertEqual(self.murphy._classify_nl_intent("tell me a joke"), "general")


class TestMurphyGateStringPhase(unittest.TestCase):
    """Test that MurphyGate accepts string phase names."""

    def test_string_phase_execute(self):
        from src.confidence_engine.murphy_gate import MurphyGate

        mg = MurphyGate()
        result = mg.evaluate(confidence=0.9, phase="EXECUTE")
        self.assertTrue(result.allowed)

    def test_string_phase_expand(self):
        from src.confidence_engine.murphy_gate import MurphyGate

        mg = MurphyGate()
        result = mg.evaluate(confidence=0.6, phase="expand")
        self.assertTrue(result.allowed)

    def test_string_phase_block(self):
        from src.confidence_engine.murphy_gate import MurphyGate

        mg = MurphyGate()
        result = mg.evaluate(confidence=0.3, phase="EXECUTE")
        self.assertFalse(result.allowed)

    def test_enum_phase_still_works(self):
        from src.confidence_engine.murphy_gate import MurphyGate
        from src.confidence_engine.murphy_models import Phase

        mg = MurphyGate()
        result = mg.evaluate(confidence=0.9, phase=Phase.EXECUTE)
        self.assertTrue(result.allowed)

    def test_invalid_string_phase_uses_default_threshold(self):
        from src.confidence_engine.murphy_gate import MurphyGate

        mg = MurphyGate()
        result = mg.evaluate(confidence=0.8, phase="INVALID_PHASE")
        # Should use default threshold (0.7), so 0.8 passes
        self.assertTrue(result.allowed)


if __name__ == "__main__":
    unittest.main()
