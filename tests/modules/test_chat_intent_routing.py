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
        """Without env vars, LLM should use onboard mode."""
        # Clear relevant env vars for test
        old_provider = os.environ.pop("MURPHY_LLM_PROVIDER", None)
        old_key = os.environ.pop("DEEPINFRA_API_KEY", None)
        try:
            status = self.murphy._get_llm_status()
            # LLM is always enabled - uses onboard fallback when no external API configured
            self.assertTrue(status["enabled"])
            self.assertEqual(status["provider"], "onboard")
            self.assertEqual(status["mode"], "onboard")
        finally:
            if old_provider is not None:
                os.environ["MURPHY_LLM_PROVIDER"] = old_provider
            if old_key is not None:
                os.environ["DEEPINFRA_API_KEY"] = old_key

    def test_llm_status_deepinfra_no_key(self):
        """Provider set to deepinfra but no API key should fall back to onboard."""
        old_provider = os.environ.get("MURPHY_LLM_PROVIDER")
        old_key = os.environ.pop("DEEPINFRA_API_KEY", None)
        os.environ["MURPHY_LLM_PROVIDER"] = "deepinfra"
        try:
            status = self.murphy._get_llm_status()
            # LLM is always enabled - gracefully falls back to onboard when key missing
            self.assertTrue(status["enabled"])
            self.assertEqual(status["provider"], "onboard")
            self.assertEqual(status["mode"], "onboard")
        finally:
            if old_provider is not None:
                os.environ["MURPHY_LLM_PROVIDER"] = old_provider
            else:
                os.environ.pop("MURPHY_LLM_PROVIDER", None)
            if old_key is not None:
                os.environ["DEEPINFRA_API_KEY"] = old_key

    def test_llm_status_deepinfra_with_key(self):
        """Provider deepinfra + API key should report healthy."""
        old_provider = os.environ.get("MURPHY_LLM_PROVIDER")
        old_key = os.environ.get("DEEPINFRA_API_KEY")
        os.environ["MURPHY_LLM_PROVIDER"] = "deepinfra"
        os.environ["DEEPINFRA_API_KEY"] = "test-key-123"
        try:
            status = self.murphy._get_llm_status()
            self.assertTrue(status["enabled"])
            self.assertTrue(status["healthy"])
            self.assertEqual(status["provider"], "deepinfra")
            self.assertIsNotNone(status["model"])
        finally:
            if old_provider is not None:
                os.environ["MURPHY_LLM_PROVIDER"] = old_provider
            else:
                os.environ.pop("MURPHY_LLM_PROVIDER", None)
            if old_key is not None:
                os.environ["DEEPINFRA_API_KEY"] = old_key
            else:
                os.environ.pop("DEEPINFRA_API_KEY", None)

    def test_llm_status_auto_detects_deepinfra_without_provider_var(self):
        """Bug-1 regression: DEEPINFRA_API_KEY alone (no MURPHY_LLM_PROVIDER) must
        enable LLM.  Before the fix, the backend required MURPHY_LLM_PROVIDER to
        be explicitly set — users who only added DEEPINFRA_API_KEY to .env were stuck
        in deterministic mode even with a valid key."""
        old_provider = os.environ.pop("MURPHY_LLM_PROVIDER", None)
        old_key = os.environ.get("DEEPINFRA_API_KEY")
        os.environ["DEEPINFRA_API_KEY"] = "di_autodetecttest"
        try:
            status = self.murphy._get_llm_status()
            self.assertTrue(
                status["enabled"],
                "LLM must be enabled when DEEPINFRA_API_KEY is set, even without "
                "MURPHY_LLM_PROVIDER — auto-detection should kick in",
            )
            self.assertEqual(status["provider"], "deepinfra")
            self.assertTrue(status["healthy"])
        finally:
            if old_provider is not None:
                os.environ["MURPHY_LLM_PROVIDER"] = old_provider
            else:
                os.environ.pop("MURPHY_LLM_PROVIDER", None)
            if old_key is not None:
                os.environ["DEEPINFRA_API_KEY"] = old_key
            else:
                os.environ.pop("DEEPINFRA_API_KEY", None)

    def test_llm_status_auto_detects_openai_without_provider_var(self):
        """Auto-detection should work for OpenAI keys too."""
        old_provider = os.environ.pop("MURPHY_LLM_PROVIDER", None)
        old_deepinfra = os.environ.pop("DEEPINFRA_API_KEY", None)
        old_openai = os.environ.get("OPENAI_API_KEY")
        os.environ["OPENAI_API_KEY"] = "sk-autodetectopenai"
        try:
            status = self.murphy._get_llm_status()
            self.assertTrue(status["enabled"])
            self.assertEqual(status["provider"], "openai")
        finally:
            if old_provider is not None:
                os.environ["MURPHY_LLM_PROVIDER"] = old_provider
            else:
                os.environ.pop("MURPHY_LLM_PROVIDER", None)
            if old_deepinfra is not None:
                os.environ["DEEPINFRA_API_KEY"] = old_deepinfra
            if old_openai is not None:
                os.environ["OPENAI_API_KEY"] = old_openai
            else:
                os.environ.pop("OPENAI_API_KEY", None)

    def test_llm_status_deepinfra_takes_priority_over_openai_in_auto_detect(self):
        """When both DEEPINFRA_API_KEY and OPENAI_API_KEY are set but MURPHY_LLM_PROVIDER
        is absent, DeepInfra should be auto-selected (it's the recommended primary option)."""
        old_provider = os.environ.pop("MURPHY_LLM_PROVIDER", None)
        old_deepinfra = os.environ.get("DEEPINFRA_API_KEY")
        old_openai = os.environ.get("OPENAI_API_KEY")
        os.environ["DEEPINFRA_API_KEY"] = "di_prioritytest"
        os.environ["OPENAI_API_KEY"] = "sk-alsoavailable"
        try:
            status = self.murphy._get_llm_status()
            self.assertEqual(
                status["provider"],
                "deepinfra",
                "DeepInfra should take auto-detect priority over OpenAI",
            )
        finally:
            if old_provider is not None:
                os.environ["MURPHY_LLM_PROVIDER"] = old_provider
            else:
                os.environ.pop("MURPHY_LLM_PROVIDER", None)
            if old_deepinfra is not None:
                os.environ["DEEPINFRA_API_KEY"] = old_deepinfra
            else:
                os.environ.pop("DEEPINFRA_API_KEY", None)
            if old_openai is not None:
                os.environ["OPENAI_API_KEY"] = old_openai
            else:
                os.environ.pop("OPENAI_API_KEY", None)

    def test_explicit_provider_var_not_overridden_by_auto_detect(self):
        """An explicit MURPHY_LLM_PROVIDER must not be replaced by auto-detection."""
        old_provider = os.environ.get("MURPHY_LLM_PROVIDER")
        old_deepinfra = os.environ.get("DEEPINFRA_API_KEY")
        old_openai = os.environ.get("OPENAI_API_KEY")
        # Explicitly set openai as provider, but also provide deepinfra key
        os.environ["MURPHY_LLM_PROVIDER"] = "openai"
        os.environ["OPENAI_API_KEY"] = "sk-explicittestkey"
        os.environ["DEEPINFRA_API_KEY"] = "di_shouldnotoverride"
        try:
            status = self.murphy._get_llm_status()
            self.assertEqual(
                status["provider"],
                "openai",
                "Explicit MURPHY_LLM_PROVIDER=openai must be respected even if "
                "DEEPINFRA_API_KEY is also present",
            )
        finally:
            if old_provider is not None:
                os.environ["MURPHY_LLM_PROVIDER"] = old_provider
            else:
                os.environ.pop("MURPHY_LLM_PROVIDER", None)
            if old_deepinfra is not None:
                os.environ["DEEPINFRA_API_KEY"] = old_deepinfra
            else:
                os.environ.pop("DEEPINFRA_API_KEY", None)
            if old_openai is not None:
                os.environ["OPENAI_API_KEY"] = old_openai
            else:
                os.environ.pop("OPENAI_API_KEY", None)

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
        self._old_key = os.environ.pop("DEEPINFRA_API_KEY", None)

    def tearDown(self):
        if self._old_provider is not None:
            os.environ["MURPHY_LLM_PROVIDER"] = self._old_provider
        if self._old_key is not None:
            os.environ["DEEPINFRA_API_KEY"] = self._old_key

    def test_fallback_includes_deterministic_message(self):
        """When LLM is off, librarian_ask should explain onboard mode."""
        result = self.murphy.librarian_ask("hello", session_id=self.sid)
        self.assertTrue(result["success"])
        self.assertEqual(result["mode"], "onboard")
        self.assertIn("onboard", result["message"].lower())
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

    def test_nl_intent_api_setup(self):
        """_classify_nl_intent should detect api key queries."""
        self.assertEqual(self.murphy._classify_nl_intent("where do I get API keys?"), "api_setup")
        self.assertEqual(self.murphy._classify_nl_intent("how do I sign up for credentials"), "api_setup")

    def test_nl_intent_sales(self):
        """Sales-related queries should classify as plan_request."""
        self.assertEqual(self.murphy._classify_nl_intent("help me sell Murphy"), "plan_request")
        self.assertEqual(self.murphy._classify_nl_intent("I need to generate more leads"), "plan_request")


class TestIntegrationInference(unittest.TestCase):
    """Test that infer_needed_integrations correctly deduces services from answers."""

    def setUp(self):
        self.murphy = MurphySystem()

    def test_email_mention_suggests_sendgrid(self):
        recs = self.murphy.infer_needed_integrations({"platforms": "email, slack"})
        names = [r["service"] for r in recs]
        self.assertIn("sendgrid", names)
        self.assertIn("slack", names)

    def test_crm_mention_suggests_hubspot(self):
        recs = self.murphy.infer_needed_integrations({"platforms": "CRM"})
        names = [r["service"] for r in recs]
        self.assertIn("hubspot", names)

    def test_sales_goal_suggests_relevant_integrations(self):
        recs = self.murphy.infer_needed_integrations({
            "business_goal": "sell Murphy System online",
            "platforms": "Shopify, email marketing",
        })
        names = [r["service"] for r in recs]
        self.assertIn("shopify", names)
        self.assertIn("stripe", names)

    def test_always_recommends_llm_if_not_configured(self):
        """Without LLM env vars, deepinfra should always be recommended."""
        old_provider = os.environ.pop("MURPHY_LLM_PROVIDER", None)
        old_key = os.environ.pop("DEEPINFRA_API_KEY", None)
        try:
            recs = self.murphy.infer_needed_integrations({"name": "Test Co"})
            names = [r["service"] for r in recs]
            self.assertIn("deepinfra", names)
        finally:
            if old_provider is not None:
                os.environ["MURPHY_LLM_PROVIDER"] = old_provider
            if old_key is not None:
                os.environ["DEEPINFRA_API_KEY"] = old_key

    def test_recommendations_include_signup_url(self):
        recs = self.murphy.infer_needed_integrations({"platforms": "GitHub"})
        for rec in recs:
            if rec["service"] == "github":
                self.assertIn("signup_url", rec)
                self.assertIn("github.com", rec["signup_url"])
                self.assertIn("env_var", rec)
                self.assertEqual(rec["env_var"], "GITHUB_TOKEN")

    def test_empty_answers_recommends_llm(self):
        """Even with empty answers, LLM should be recommended."""
        old_provider = os.environ.pop("MURPHY_LLM_PROVIDER", None)
        try:
            recs = self.murphy.infer_needed_integrations({})
            names = [r["service"] for r in recs]
            self.assertIn("deepinfra", names)
        finally:
            if old_provider is not None:
                os.environ["MURPHY_LLM_PROVIDER"] = old_provider

    def test_recommendations_have_reason(self):
        recs = self.murphy.infer_needed_integrations({"platforms": "Slack"})
        for rec in recs:
            if rec["service"] == "slack":
                self.assertIn("reason", rec)


class TestApiSetupGuidance(unittest.TestCase):
    """Test the API setup guidance method."""

    def setUp(self):
        self.murphy = MurphySystem()

    def test_all_services_returned(self):
        result = self.murphy.get_api_setup_guidance()
        self.assertTrue(result["success"])
        self.assertGreater(result["count"], 10)

    def test_filtered_services(self):
        result = self.murphy.get_api_setup_guidance(["deepinfra", "github"])
        self.assertEqual(result["count"], 2)
        names = [s["service"] for s in result["services"]]
        self.assertIn("deepinfra", names)
        self.assertIn("github", names)

    def test_entries_have_required_fields(self):
        result = self.murphy.get_api_setup_guidance()
        for svc in result["services"]:
            self.assertIn("service", svc)
            self.assertIn("name", svc)
            self.assertIn("signup_url", svc)
            self.assertIn("env_var", svc)
            self.assertIn("description", svc)


class TestApiLinksReply(unittest.TestCase):
    """Test the deterministic API links reply."""

    def setUp(self):
        self.murphy = MurphySystem()
        self.sid = "test-api-links"
        self._old_provider = os.environ.pop("MURPHY_LLM_PROVIDER", None)
        self._old_key = os.environ.pop("DEEPINFRA_API_KEY", None)

    def tearDown(self):
        if self._old_provider is not None:
            os.environ["MURPHY_LLM_PROVIDER"] = self._old_provider
        if self._old_key is not None:
            os.environ["DEEPINFRA_API_KEY"] = self._old_key

    def test_api_key_query_returns_links(self):
        result = self.murphy.librarian_ask("where do I get API keys?", session_id=self.sid)
        self.assertTrue(result["success"])
        self.assertIn("Signup", result["message"])
        self.assertIn("console.deepinfra.com", result["message"])

    def test_api_key_query_suggests_api_keys_command(self):
        result = self.murphy.librarian_ask("how to get credentials?", session_id=self.sid)
        self.assertIn("api keys", result["suggested_commands"])


class TestOnboardingCompletionIntegrations(unittest.TestCase):
    """Test that onboarding completion shows integration recommendations."""

    def setUp(self):
        self.murphy = MurphySystem()
        self.sid = "test-onboard-complete"

    def test_completion_includes_integration_recs(self):
        """After onboarding with email/slack, completion should recommend integrations."""
        # Start the onboarding flow
        self.murphy.handle_chat("start interview", session_id=self.sid, use_mfgc=False)
        # Advance through all steps with answers mentioning integrations
        # Flow has 6 steps; the 6th answer triggers completion (stage_index reaches last)
        answers = [
            "Inoni LLC",          # signup (step 0)
            "US",                 # region (step 1)
            "email, Slack, CRM",  # setup (step 2)
            "sales automation",   # automation_design (step 3)
            "yes",                # automation_production (step 4)
        ]
        result = None
        for ans in answers:
            result = self.murphy.handle_chat(ans, session_id=self.sid, use_mfgc=False)
        # After 5 answers, stage_index=5 which is last step → completion
        msg = result["message"]
        self.assertIn("Onboarding complete", msg)
        # Should recommend integrations based on "email", "Slack", "CRM"
        self.assertIn("Recommended integrations", msg)
        self.assertIn("Get your API key", msg)


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


class TestApiKeysIntentRouting(unittest.TestCase):
    """Test that 'api keys' is a recognised intent in the runtime."""

    def setUp(self):
        self.murphy = MurphySystem()
        self.sid = "test-api-keys-intent"

    def test_api_keys_intent_detected(self):
        """'api keys' should be detected as the 'api_keys' intent."""
        intent = self.murphy._detect_intent("api keys")
        self.assertEqual(intent, "api_keys")

    def test_api_key_singular_detected(self):
        intent = self.murphy._detect_intent("api key")
        self.assertEqual(intent, "api_keys")

    def test_get_api_detected(self):
        intent = self.murphy._detect_intent("get api")
        self.assertEqual(intent, "api_keys")

    def test_signup_links_detected(self):
        intent = self.murphy._detect_intent("signup links")
        self.assertEqual(intent, "api_keys")

    def test_api_keys_returns_response(self):
        """Typing 'api keys' should return a response with signup links."""
        result = self.murphy.handle_chat("api keys", session_id=self.sid, use_mfgc=False)
        self.assertTrue(result["success"])
        self.assertIn("Signup", result["message"])
        self.assertIn("DeepInfra", result["message"])

    def test_api_keys_after_onboarding_shows_tailored_recs(self):
        """After onboarding with context, 'api keys' should show tailored recs."""
        # Run onboarding
        self.murphy.handle_chat("start interview", session_id=self.sid, use_mfgc=False)
        self.murphy.handle_chat("Acme Corp, email marketing", session_id=self.sid, use_mfgc=False)
        self.murphy.handle_chat("US", session_id=self.sid, use_mfgc=False)
        self.murphy.handle_chat("email, Slack", session_id=self.sid, use_mfgc=False)
        self.murphy.handle_chat("send email campaigns", session_id=self.sid, use_mfgc=False)
        result = self.murphy.handle_chat("yes", session_id=self.sid, use_mfgc=False)
        # Now ask for api keys
        result = self.murphy.handle_chat("api keys", session_id=self.sid, use_mfgc=False)
        self.assertTrue(result["success"])
        # Should include tailored recs based on "email" and "Slack"
        self.assertIn("Recommended", result["message"])


class TestWorkflowAwareInference(unittest.TestCase):
    """Test that inference picks up workflow ACTIONS, not just keyword mentions."""

    def setUp(self):
        self.murphy = MurphySystem()

    def test_send_email_action_infers_sendgrid(self):
        """'send email' workflow action should trigger SendGrid recommendation."""
        recs = self.murphy.infer_needed_integrations({
            "automation_design": "When a new lead comes in, send email to the sales team"
        })
        services = [r["service"] for r in recs]
        self.assertIn("sendgrid", services)

    def test_post_to_channel_infers_slack(self):
        """'post to channel' action should trigger Slack recommendation."""
        recs = self.murphy.infer_needed_integrations({
            "automation_design": "Post to channel when build fails"
        })
        services = [r["service"] for r in recs]
        self.assertIn("slack", services)

    def test_create_issue_infers_github_or_jira(self):
        """'create issue' action should trigger GitHub/Jira recommendation."""
        recs = self.murphy.infer_needed_integrations({
            "automation_design": "Create issue when a critical bug is detected"
        })
        services = [r["service"] for r in recs]
        self.assertTrue("github" in services or "jira" in services)

    def test_process_payment_infers_stripe(self):
        recs = self.murphy.infer_needed_integrations({
            "automation_design": "Process payment when order confirmed"
        })
        services = [r["service"] for r in recs]
        self.assertIn("stripe", services)

    def test_goal_increase_sales_infers_crm(self):
        """Business goal 'increase sales' should trigger CRM/email recs."""
        recs = self.murphy.infer_needed_integrations({
            "signup": "We want to increase sales by 30%"
        })
        services = [r["service"] for r in recs]
        self.assertIn("hubspot", services)
        self.assertIn("sendgrid", services)

    def test_goal_devops_infers_github_slack(self):
        """Business goal 'devops' should trigger GitHub/Slack recs."""
        recs = self.murphy.infer_needed_integrations({
            "signup": "We need a devops automation solution"
        })
        services = [r["service"] for r in recs]
        self.assertIn("github", services)
        self.assertIn("slack", services)

    def test_recommendations_have_reason_field(self):
        """Every recommendation should explain WHY it was recommended."""
        recs = self.murphy.infer_needed_integrations({
            "automation_design": "Send email to notify team when build completes"
        })
        for rec in recs:
            self.assertIn("reason", rec)
            self.assertTrue(len(rec["reason"]) > 0)


class TestLibrarianFlowEnrichment(unittest.TestCase):
    """Test that the Librarian provides enrichment hints during onboarding."""

    def setUp(self):
        self.murphy = MurphySystem()
        self.sid = "test-librarian-enrich"

    def test_setup_stage_triggers_librarian_hint(self):
        """After providing setup info mentioning services, librarian should hint."""
        self.murphy.handle_chat("start interview", session_id=self.sid, use_mfgc=False)
        self.murphy.handle_chat("Acme Corp, email@acme.com, increase sales", session_id=self.sid, use_mfgc=False)
        self.murphy.handle_chat("US", session_id=self.sid, use_mfgc=False)
        result = self.murphy.handle_chat("email, Slack, GitHub", session_id=self.sid, use_mfgc=False)
        # After setup stage, librarian should provide a hint
        msg = result["message"]
        self.assertIn("Librarian note", msg)

    def test_onboarding_completion_has_next_steps(self):
        """Onboarding completion should include numbered next steps."""
        self.murphy.handle_chat("start interview", session_id=self.sid, use_mfgc=False)
        self.murphy.handle_chat("Acme Corp", session_id=self.sid, use_mfgc=False)
        self.murphy.handle_chat("US", session_id=self.sid, use_mfgc=False)
        self.murphy.handle_chat("email, Slack", session_id=self.sid, use_mfgc=False)
        self.murphy.handle_chat("send notifications", session_id=self.sid, use_mfgc=False)
        result = self.murphy.handle_chat("yes", session_id=self.sid, use_mfgc=False)
        msg = result["message"]
        self.assertIn("What to do next", msg)
        self.assertIn("Restart Murphy", msg)

    def test_onboarding_completion_has_integration_recommendations(self):
        """Completion with email/Slack mentions should recommend those APIs."""
        self.murphy.handle_chat("start interview", session_id=self.sid, use_mfgc=False)
        self.murphy.handle_chat("Company with email marketing", session_id=self.sid, use_mfgc=False)
        self.murphy.handle_chat("US", session_id=self.sid, use_mfgc=False)
        self.murphy.handle_chat("email, GitHub", session_id=self.sid, use_mfgc=False)
        self.murphy.handle_chat("automate deployments", session_id=self.sid, use_mfgc=False)
        result = self.murphy.handle_chat("yes", session_id=self.sid, use_mfgc=False)
        msg = result["message"]
        self.assertIn("Onboarding complete", msg)
        # Should recommend email and GitHub services
        self.assertTrue("SendGrid" in msg or "Google" in msg)
        self.assertIn("GitHub", msg)


if __name__ == "__main__":
    unittest.main()
