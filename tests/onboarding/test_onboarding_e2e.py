"""
End-to-end tests for the MFGC/5U conversational onboarding engine.

Tests the complete onboarding flow through the Librarian API:
- Onboard LLM mode (no API keys): adaptive deterministic responses
- DeepInfra LLM mode: when DEEPINFRA_API_KEY is set
- MFGC/5U scoring: 0% → 85% threshold → plan generation
- Reflection: user input amplified back (magnify x3)
- No duplicate responses: every reply must be unique
- Session isolation: separate conversations don't leak state
- Config generation: modules + integrations at 85%+ readiness
- Full 8-message conversation through the entire process
"""

import os
import sys
import json
import unittest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
MURPHY_DIR = os.path.join(TESTS_DIR, "..")
SRC_DIR = os.path.join(MURPHY_DIR, "src")
sys.path.insert(0, MURPHY_DIR)
sys.path.insert(0, SRC_DIR)


def _get_murphy():
    """Create a fresh MurphySystem instance for testing."""
    from src.runtime.murphy_system_core import MurphySystem
    return MurphySystem()


# ============================================================================
# 1. MFGC/5U Dimension Extraction Tests
# ============================================================================

class TestDimensionExtraction(unittest.TestCase):
    """Test that user messages correctly extract MFGC/5U dimensions."""

    def setUp(self):
        self.murphy = _get_murphy()

    def test_extracts_business_name(self):
        profile = self.murphy._get_onboarding_profile("test-name")
        dims = self.murphy._extract_dimensions_from_message(
            "My company is called Acme Corp", profile
        )
        self.assertIn("business_name", dims)
        self.assertIn("Acme Corp", dims["business_name"])

    def test_extracts_industry(self):
        profile = self.murphy._get_onboarding_profile("test-ind")
        dims = self.murphy._extract_dimensions_from_message(
            "We are a manufacturing company", profile
        )
        self.assertIn("industry", dims)
        self.assertEqual(dims["industry"], "manufacturing")

    def test_extracts_location(self):
        profile = self.murphy._get_onboarding_profile("test-loc")
        dims = self.murphy._extract_dimensions_from_message(
            "We are based in Dallas, TX", profile
        )
        self.assertIn("location", dims)
        self.assertIn("Dallas", dims["location"])

    def test_extracts_team_size(self):
        profile = self.murphy._get_onboarding_profile("test-team")
        dims = self.murphy._extract_dimensions_from_message(
            "We have 15 employees on the team", profile
        )
        self.assertIn("team_size", dims)
        self.assertEqual(dims["team_size"], "15")

    def test_extracts_email_provider(self):
        profile = self.murphy._get_onboarding_profile("test-email")
        dims = self.murphy._extract_dimensions_from_message(
            "We use Gmail for all our email", profile
        )
        self.assertIn("email_provider", dims)
        self.assertIn("gmail", dims["email_provider"])

    def test_extracts_banking(self):
        profile = self.murphy._get_onboarding_profile("test-bank")
        dims = self.murphy._extract_dimensions_from_message(
            "We bank with Chase for our business accounts", profile
        )
        self.assertIn("banking", dims)
        self.assertIn("chase", dims["banking"])

    def test_extracts_phone_carrier(self):
        profile = self.murphy._get_onboarding_profile("test-phone")
        dims = self.murphy._extract_dimensions_from_message(
            "Our company phones are on Verizon", profile
        )
        self.assertIn("phone_carrier", dims)
        self.assertIn("verizon", dims["phone_carrier"])

    def test_extracts_productivity_apps(self):
        profile = self.murphy._get_onboarding_profile("test-apps")
        dims = self.murphy._extract_dimensions_from_message(
            "The team uses Slack and Notion daily", profile
        )
        self.assertIn("productivity_apps", dims)

    def test_extracts_schedule_system(self):
        profile = self.murphy._get_onboarding_profile("test-cal")
        dims = self.murphy._extract_dimensions_from_message(
            "We manage our schedule with Google Calendar", profile
        )
        self.assertIn("schedule_system", dims)

    def test_extracts_pain_points(self):
        profile = self.murphy._get_onboarding_profile("test-pain")
        dims = self.murphy._extract_dimensions_from_message(
            "Our biggest pain point is manual data entry", profile
        )
        self.assertIn("pain_points", dims)

    def test_extracts_business_goal(self):
        profile = self.murphy._get_onboarding_profile("test-goal")
        dims = self.murphy._extract_dimensions_from_message(
            "We want to reduce customer response time by 50%", profile
        )
        self.assertIn("business_goal", dims)

    def test_extracts_automation_goal(self):
        profile = self.murphy._get_onboarding_profile("test-auto")
        dims = self.murphy._extract_dimensions_from_message(
            "We need to automate our invoice processing workflow", profile
        )
        self.assertIn("automation_goal", dims)

    def test_extracts_frequency(self):
        profile = self.murphy._get_onboarding_profile("test-freq")
        dims = self.murphy._extract_dimensions_from_message(
            "These reports need to go out daily", profile
        )
        self.assertIn("frequency", dims)
        self.assertEqual(dims["frequency"], "daily")

    def test_extracts_timezone(self):
        profile = self.murphy._get_onboarding_profile("test-tz")
        dims = self.murphy._extract_dimensions_from_message(
            "We operate in Eastern time", profile
        )
        self.assertIn("timezone", dims)

    def test_extracts_compliance(self):
        profile = self.murphy._get_onboarding_profile("test-comply")
        dims = self.murphy._extract_dimensions_from_message(
            "We need to comply with HIPAA regulations", profile
        )
        self.assertIn("compliance_needs", dims)

    def test_extracts_decision_maker(self):
        profile = self.murphy._get_onboarding_profile("test-dm")
        dims = self.murphy._extract_dimensions_from_message(
            "The CEO makes final decisions on new tools", profile
        )
        self.assertIn("decision_maker", dims)

    def test_extracts_budget(self):
        profile = self.murphy._get_onboarding_profile("test-budget")
        dims = self.murphy._extract_dimensions_from_message(
            "Budget is around $500 per month for tools", profile
        )
        self.assertIn("budget_range", dims)

    def test_extracts_timeline(self):
        profile = self.murphy._get_onboarding_profile("test-tl")
        dims = self.murphy._extract_dimensions_from_message(
            "We want this running within 2 weeks", profile
        )
        self.assertIn("timeline", dims)

    def test_extracts_data_sources(self):
        profile = self.murphy._get_onboarding_profile("test-data")
        dims = self.murphy._extract_dimensions_from_message(
            "Our main data comes from sensor readings on the production line", profile
        )
        self.assertIn("data_sources", dims)

    def test_extracts_success_metric(self):
        profile = self.murphy._get_onboarding_profile("test-success")
        dims = self.murphy._extract_dimensions_from_message(
            "Success means reducing processing time by 80%", profile
        )
        self.assertIn("success_metric", dims)

    def test_extracts_multiple_dimensions_at_once(self):
        """A single message can contain multiple dimensions."""
        profile = self.murphy._get_onboarding_profile("test-multi")
        dims = self.murphy._extract_dimensions_from_message(
            "I run a manufacturing company called Inoni LLC based in Dallas, TX with 15 employees",
            profile,
        )
        self.assertIn("business_name", dims)
        self.assertIn("industry", dims)
        self.assertIn("team_size", dims)
        self.assertIn("location", dims)

    def test_does_not_overwrite_existing(self):
        """Once a dimension is collected, it is not overwritten by later messages."""
        profile = self.murphy._get_onboarding_profile("test-no-overwrite")
        profile["collected"]["business_name"] = "Inoni LLC"
        dims = self.murphy._extract_dimensions_from_message(
            "My company is called Different Corp", profile
        )
        self.assertNotIn("business_name", dims)


# ============================================================================
# 2. MFGC/5U Scoring Tests
# ============================================================================

class TestMFGCScoring(unittest.TestCase):
    """Test the MFGC/5U readiness scoring system."""

    def setUp(self):
        self.murphy = _get_murphy()

    def test_empty_profile_scores_zero(self):
        profile = {"collected": {}}
        score = self.murphy._score_mfgc_readiness(profile)
        self.assertEqual(score, 0.0)

    def test_partial_profile_scores_proportionally(self):
        profile = {"collected": {"business_name": "Acme", "industry": "tech"}}
        score = self.murphy._score_mfgc_readiness(profile)
        self.assertGreater(score, 0)
        self.assertLess(score, 50)

    def test_full_profile_scores_100(self):
        """Filling all 21 dimensions scores 100%."""
        profile = {"collected": {dim: "test" for dim in self.murphy._ONBOARDING_DIMENSIONS}}
        score = self.murphy._score_mfgc_readiness(profile)
        self.assertEqual(score, 100.0)

    def test_threshold_at_85_percent(self):
        """Config is generated only when score >= 85%."""
        session = "test-threshold"
        murphy = self.murphy

        # Fill dimensions until we hit 85%
        high_weight = sorted(
            murphy._ONBOARDING_DIMENSIONS.items(),
            key=lambda x: x[1]["weight"],
            reverse=True,
        )
        profile = murphy._get_onboarding_profile(session)
        total_weight = sum(d["weight"] for d in murphy._ONBOARDING_DIMENSIONS.values())

        earned = 0
        for dim, info in high_weight:
            profile["collected"][dim] = "test_value"
            earned += info["weight"]
            score = murphy._score_mfgc_readiness(profile)
            if score >= 85:
                break

        self.assertGreaterEqual(score, 85.0)


# ============================================================================
# 3. Conversational Flow Tests (Onboard LLM)
# ============================================================================

class TestOnboardConversation(unittest.TestCase):
    """Test the full onboarding conversation with onboard (no API key) LLM."""

    def setUp(self):
        self.murphy = _get_murphy()
        # Ensure no LLM keys are set
        for key in ("DEEPINFRA_API_KEY", "OPENAI_API_KEY", "MURPHY_LLM_PROVIDER"):
            os.environ.pop(key, None)

    def test_first_message_gets_personalized_response(self):
        """First message should NOT return a canned response."""
        r = self.murphy.librarian_ask(
            "I run a manufacturing company called Inoni LLC",
            session_id="test-first",
        )
        self.assertEqual(r["mode"], "onboard")
        # Should mention the business name
        self.assertIn("Inoni LLC", r["message"])
        # Should mention manufacturing
        self.assertIn("manufacturing", r["message"].lower())
        # Should have MFGC score
        self.assertIn("mfgc_score", r)

    def test_responses_are_never_identical(self):
        """Each response in a conversation must be unique."""
        session = "test-unique"
        messages = [
            "I run a manufacturing company called Inoni LLC",
            "We make custom parts and need to automate QC",
            "We use Gmail, Slack, and bank with Chase",
            "Our team is 15 people in Dallas, Texas",
        ]
        responses = []
        for msg in messages:
            r = self.murphy.librarian_ask(msg, session_id=session)
            responses.append(r["message"])

        # All responses must be different
        for i in range(len(responses)):
            for j in range(i + 1, len(responses)):
                self.assertNotEqual(
                    responses[i], responses[j],
                    f"Response {i+1} and {j+1} are identical!",
                )

    def test_score_increases_with_each_message(self):
        """MFGC/5U score must increase as user provides more info."""
        session = "test-increasing"
        messages = [
            "I run a manufacturing company called Inoni LLC",
            "We need to automate quality control inspections",
            "We use Gmail, Slack, and bank with Chase. 15 people, Dallas TX",
        ]
        scores = []
        for msg in messages:
            r = self.murphy.librarian_ask(msg, session_id=session)
            scores.append(r["mfgc_score"])

        # Each score should be >= previous
        for i in range(1, len(scores)):
            self.assertGreaterEqual(
                scores[i], scores[i - 1],
                f"Score decreased from {scores[i-1]} to {scores[i]}",
            )

    def test_full_8_message_conversation(self):
        """Full conversation from 0% to 85%+ with config generation."""
        session = "test-full-8"
        messages = [
            "I run a manufacturing company called Inoni LLC",
            "We make custom parts and need to automate quality control inspections",
            "We use Gmail, Slack, and bank with Chase. Our team is 15 people in Dallas, Texas",
            "Our biggest pain point is manual QC reports that take hours every day",
            "We want to automate the entire QC pipeline from sensor data to final reports",
            "We use Google Calendar for scheduling and want daily automated reports",
            "We need to comply with ISO 9001 and the CEO makes final decisions",
            "Budget is around $500 per month and we want this within 2 weeks. Success is 80% time reduction",
        ]

        final_response = None
        for msg in messages:
            r = self.murphy.librarian_ask(msg, session_id=session)
            final_response = r

        # Final score should be well above 85%
        self.assertGreaterEqual(final_response["mfgc_score"], 85.0)
        # Config should be generated
        self.assertIn("config", final_response)
        config = final_response["config"]
        self.assertIn("modules", config)
        self.assertIn("integrations", config)
        self.assertGreater(len(config["modules"]), 0)

    def test_reflection_amplifies_user_input(self):
        """When user shares info, it should be reflected back expanded."""
        r = self.murphy.librarian_ask(
            "I run a manufacturing company called Inoni LLC",
            session_id="test-reflect",
        )
        msg = r["message"]
        # Should mention Inoni LLC at least twice (reflection amplification)
        count = msg.lower().count("inoni llc")
        self.assertGreaterEqual(count, 2, f"Business name mentioned only {count} time(s)")

    def test_asks_next_important_question(self):
        """Each response should ask a follow-up question."""
        r = self.murphy.librarian_ask(
            "I run a manufacturing company called Inoni LLC",
            session_id="test-question",
        )
        # Should contain a question mark (asking next question)
        self.assertIn("?", r["message"])

    def test_readiness_check_phrase(self):
        """Response should ask 'does this sound close' or offer to solidify."""
        r = self.murphy.librarian_ask(
            "I run a manufacturing company called Inoni LLC",
            session_id="test-check",
        )
        msg = r["message"].lower()
        self.assertTrue(
            "sound close" in msg or "solidify" in msg or "adjust" in msg,
            "Missing HITL confirmation check (sound close / solidify / adjust)",
        )

    def test_session_isolation(self):
        """Two different sessions should not share state."""
        r1 = self.murphy.librarian_ask("I own a bakery", session_id="session-a")
        r2 = self.murphy.librarian_ask("I'm a software developer", session_id="session-b")

        # Session A should mention bakery-related content
        self.assertNotIn("software", r1["message"].lower())
        # Session B should NOT mention bakery
        self.assertNotIn("bakery", r2["message"].lower())


# ============================================================================
# 3b. Magnify x3 + Solidify Integration Tests
# ============================================================================

class TestMagnifySolidifyFlow(unittest.TestCase):
    """Test the Magnify x3 → HITL agreement → Solidify pipeline."""

    def setUp(self):
        self.murphy = _get_murphy()
        for key in ("DEEPINFRA_API_KEY", "OPENAI_API_KEY", "MURPHY_LLM_PROVIDER"):
            os.environ.pop(key, None)

    def test_magnify_creates_living_document(self):
        """First user message should create a LivingDocument via Magnify."""
        session = "test-magnify-doc"
        r = self.murphy.librarian_ask(
            "I run a manufacturing company called Inoni LLC",
            session_id=session,
        )
        profile = self.murphy._get_onboarding_profile(session)
        doc_id = profile.get("_pending_magnified_doc_id")
        self.assertIsNotNone(doc_id, "Magnify should create a LivingDocument")
        doc = self.murphy.living_documents.get(doc_id)
        self.assertIsNotNone(doc, "Document should be in living_documents")
        self.assertEqual(doc.doc_type, "onboarding_plan")

    def test_magnify_increases_domain_depth(self):
        """Each Magnify operation increases domain_depth by 15."""
        session = "test-magnify-depth"
        self.murphy.librarian_ask(
            "I run a manufacturing company called Inoni LLC",
            session_id=session,
        )
        profile = self.murphy._get_onboarding_profile(session)
        doc = self.murphy.living_documents.get(profile["_pending_magnified_doc_id"])
        self.assertEqual(doc.domain_depth, 15)

        self.murphy.librarian_ask(
            "We need to automate quality control with 15 people in Dallas",
            session_id=session,
        )
        self.assertEqual(doc.domain_depth, 30)

    def test_magnify_count_shown_in_response(self):
        """Response should show 'Magnify x1', 'Magnify x2', etc."""
        session = "test-magnify-count"
        r1 = self.murphy.librarian_ask(
            "I run a manufacturing company called Inoni LLC",
            session_id=session,
        )
        self.assertIn("Magnify x1", r1["message"])

        r2 = self.murphy.librarian_ask(
            "We need to automate QC inspections daily",
            session_id=session,
        )
        self.assertIn("Magnify x2", r2["message"])

    def test_hitl_agreement_triggers_solidify(self):
        """Saying 'yes' after magnify should solidify the document."""
        session = "test-solidify"
        self.murphy.librarian_ask(
            "I run a manufacturing company called Inoni LLC",
            session_id=session,
        )
        r = self.murphy.librarian_ask("Yes, that sounds close!", session_id=session)
        self.assertIn("Solidified", r["message"])
        self.assertIn("SOLIDIFIED", r["message"])

        # Document state should be SOLIDIFIED
        profile = self.murphy._get_onboarding_profile(session)
        doc = self.murphy.living_documents.get(profile["_pending_magnified_doc_id"])
        self.assertEqual(doc.state, "SOLIDIFIED")

    def test_solidify_shows_confidence(self):
        """Solidify response should include confidence percentage."""
        session = "test-solidify-conf"
        self.murphy.librarian_ask(
            "I run a manufacturing company",
            session_id=session,
        )
        r = self.murphy.librarian_ask("Yes, go ahead", session_id=session)
        self.assertIn("Confidence:", r["message"])

    def test_agreement_detection(self):
        """Test various agreement phrases are detected."""
        for phrase in ["yes", "sounds good", "that's right", "perfect", "go ahead",
                       "confirm", "absolutely", "let's go"]:
            self.assertTrue(
                self.murphy._is_hitl_agreement(phrase),
                f"'{phrase}' should be detected as agreement",
            )

    def test_non_agreement_not_detected(self):
        """Test that non-agreement phrases are NOT detected."""
        for phrase in ["no", "I don't think so", "change the plan",
                       "my company is in manufacturing", "tell me more"]:
            self.assertFalse(
                self.murphy._is_hitl_agreement(phrase),
                f"'{phrase}' should NOT be detected as agreement",
            )

    def test_full_magnify_solidify_cycle(self):
        """Complete cycle: info → Magnify x3 → agree → Solidify → continue."""
        session = "test-full-cycle"

        # Step 1: Provide info → Magnify x1
        r1 = self.murphy.librarian_ask(
            "I run a manufacturing company called Inoni LLC",
            session_id=session,
        )
        self.assertIn("Magnify x1", r1["message"])

        # Step 2: More info → Magnify x2
        r2 = self.murphy.librarian_ask(
            "We make custom parts and need to automate QC inspections",
            session_id=session,
        )
        self.assertIn("Magnify x2", r2["message"])

        # Step 3: Even more → Magnify x3
        r3 = self.murphy.librarian_ask(
            "We use Gmail and Slack, team of 15 in Dallas, banking with Chase",
            session_id=session,
        )
        self.assertIn("Magnify x3", r3["message"])

        # Step 4: User agrees → Solidify
        r4 = self.murphy.librarian_ask("Yes, that sounds close!", session_id=session)
        self.assertIn("Solidified", r4["message"])
        self.assertIn("Magnify x3", r4["message"])

        # Verify document state
        profile = self.murphy._get_onboarding_profile(session)
        doc = self.murphy.living_documents.get(profile["_pending_magnified_doc_id"])
        self.assertEqual(doc.state, "SOLIDIFIED")
        self.assertEqual(doc.domain_depth, 45)  # 3 magnify x 15 each


# ============================================================================
# 4. DeepInfra LLM Integration Tests
# ============================================================================

class TestDeepInfraIntegration(unittest.TestCase):
    """Test with DeepInfra API key (if available and network accessible)."""

    def setUp(self):
        self.murphy = _get_murphy()
        self.deepinfra_key = os.environ.get("DEEPINFRA_API_KEY", "")
        if not self.deepinfra_key:
            self.skipTest("DEEPINFRA_API_KEY not set — skipping DeepInfra tests")
        # Check if DeepInfra API is reachable (sandbox may not have network)
        try:
            import socket
            socket.create_connection(("api.deepinfra.com", 443), timeout=3)
        except (OSError, socket.timeout):
            self.skipTest("api.deepinfra.com not reachable — no network access")

    def test_deepinfra_responds_in_llm_mode(self):
        """With DeepInfra key, responses should be in 'llm' mode."""
        os.environ["MURPHY_LLM_PROVIDER"] = "deepinfra"
        r = self.murphy.librarian_ask(
            "I run a manufacturing company called Inoni LLC",
            session_id="deepinfra-test-1",
        )
        self.assertEqual(r["mode"], "llm")
        self.assertGreater(len(r["message"]), 50)

    def test_deepinfra_maintains_context(self):
        """DeepInfra LLM should receive context about previously collected dimensions."""
        os.environ["MURPHY_LLM_PROVIDER"] = "deepinfra"
        session = "deepinfra-context"
        # First message
        self.murphy.librarian_ask(
            "I run a manufacturing company called Inoni LLC",
            session_id=session,
        )
        # Second message — LLM should have context from first
        r2 = self.murphy.librarian_ask(
            "What integrations would you recommend for my setup?",
            session_id=session,
        )
        self.assertEqual(r2["mode"], "llm")
        # Response should reference manufacturing or Inoni (from context)
        msg_lower = r2["message"].lower()
        has_context = "manufactur" in msg_lower or "inoni" in msg_lower or "integrat" in msg_lower
        self.assertTrue(has_context, "DeepInfra response lacks context from prior message")

    def test_deepinfra_score_still_tracked(self):
        """MFGC/5U score should be tracked even in LLM mode."""
        os.environ["MURPHY_LLM_PROVIDER"] = "deepinfra"
        r = self.murphy.librarian_ask(
            "I run a manufacturing company called Inoni LLC with 15 people in Dallas",
            session_id="deepinfra-score",
        )
        self.assertIn("mfgc_score", r)
        self.assertGreater(r["mfgc_score"], 0)


# ============================================================================
# 5. Intent Classification Tests
# ============================================================================

class TestIntentClassification(unittest.TestCase):
    """Test the NL intent classifier handles edge cases."""

    def setUp(self):
        self.murphy = _get_murphy()

    def test_i_run_a_company_not_execution(self):
        """'I run a company' should NOT match execution_request."""
        intent = self.murphy._classify_nl_intent("I run a manufacturing company")
        self.assertNotEqual(intent, "execution_request")

    def test_run_command_is_execution(self):
        """'run my pipeline' at start of sentence IS execution_request."""
        intent = self.murphy._classify_nl_intent("run my pipeline")
        self.assertEqual(intent, "execution_request")

    def test_execute_is_execution(self):
        intent = self.murphy._classify_nl_intent("execute the report generation")
        self.assertEqual(intent, "execution_request")

    def test_automate_is_plan_request(self):
        intent = self.murphy._classify_nl_intent("I want to automate my sales pipeline")
        self.assertEqual(intent, "plan_request")

    def test_api_keys_is_api_setup(self):
        intent = self.murphy._classify_nl_intent("where do I get API keys?")
        self.assertEqual(intent, "api_setup")

    def test_status_inquiry(self):
        intent = self.murphy._classify_nl_intent("how is the system doing?")
        self.assertEqual(intent, "status_inquiry")

    def test_general_message(self):
        intent = self.murphy._classify_nl_intent("hello there")
        self.assertEqual(intent, "general")


# ============================================================================
# 6. API Response Format Tests
# ============================================================================

class TestAPIResponseFormat(unittest.TestCase):
    """Test that API responses have the correct structure."""

    def setUp(self):
        self.murphy = _get_murphy()

    def test_response_has_required_fields(self):
        r = self.murphy.librarian_ask("hello", session_id="test-format")
        self.assertIn("success", r)
        self.assertIn("session_id", r)
        self.assertIn("reply_text", r)
        self.assertIn("response", r)
        self.assertIn("message", r)
        self.assertIn("intent", r)
        self.assertIn("mode", r)
        self.assertIn("mfgc_score", r)
        self.assertIn("suggested_commands", r)

    def test_response_aliases_match(self):
        """reply_text, response, and message should all be the same."""
        r = self.murphy.librarian_ask("hello", session_id="test-aliases")
        self.assertEqual(r["reply_text"], r["response"])
        self.assertEqual(r["reply_text"], r["message"])

    def test_config_generated_at_85_percent(self):
        """Config should appear when score hits 85%+."""
        session = "test-config-gen"
        profile = self.murphy._get_onboarding_profile(session)
        # Fill enough dimensions to hit 85%
        for dim in list(self.murphy._ONBOARDING_DIMENSIONS.keys())[:17]:
            profile["collected"][dim] = "test_value"

        r = self.murphy.librarian_ask("What's next?", session_id=session)
        self.assertGreaterEqual(r["mfgc_score"], 85.0)
        self.assertIn("config", r)
        self.assertIn("modules", r["config"])
        self.assertIn("integrations", r["config"])

    def test_config_has_business_profile(self):
        """Config should include the collected business profile."""
        session = "test-config-profile"
        profile = self.murphy._get_onboarding_profile(session)
        profile["collected"] = {
            dim: "test" for dim in self.murphy._ONBOARDING_DIMENSIONS
        }
        profile["collected"]["business_name"] = "Acme Corp"

        r = self.murphy.librarian_ask("ready", session_id=session)
        self.assertIn("config", r)
        self.assertEqual(r["config"]["business_profile"]["business_name"], "Acme Corp")


# ============================================================================
# 7. Onboarding Wizard UI + API Integration Tests
# ============================================================================

class TestOnboardingWizardIntegration(unittest.TestCase):
    """Test the onboarding wizard HTML + API contract."""

    def test_wizard_html_posts_question_field(self):
        """Wizard posts 'question' field — API must accept it."""
        import re
        html_path = os.path.join(MURPHY_DIR, "onboarding_wizard.html")
        with open(html_path) as f:
            content = f.read()
        # The wizard should post to /librarian/ask
        self.assertIn("/librarian/ask", content)

    def test_wizard_reads_response_aliases(self):
        """Wizard reads answer/response/message fields from API response."""
        html_path = os.path.join(MURPHY_DIR, "onboarding_wizard.html")
        with open(html_path) as f:
            content = f.read()
        # Should handle multiple field names
        has_answer = "answer" in content
        has_response = "response" in content
        has_message = "message" in content
        self.assertTrue(
            has_answer or has_response or has_message,
            "Wizard doesn't read any response alias",
        )

    def test_wizard_shows_continue_after_exchanges(self):
        """Wizard shows 'Continue to Plan' after 3+ exchanges."""
        html_path = os.path.join(MURPHY_DIR, "onboarding_wizard.html")
        with open(html_path) as f:
            content = f.read()
        # Should have exchange counting logic
        self.assertIn("exchangeCount", content)

    def test_wizard_has_five_steps(self):
        """Wizard must have all 5 steps."""
        html_path = os.path.join(MURPHY_DIR, "onboarding_wizard.html")
        with open(html_path) as f:
            content = f.read()
        for step in ["Step 1", "Step 2", "Step 3", "Step 4", "Step 5"]:
            self.assertIn(step, content, f"Missing {step} in wizard")

    def test_wizard_reads_config_from_api(self):
        """Wizard should read config.modules and config.integrations from API."""
        html_path = os.path.join(MURPHY_DIR, "onboarding_wizard.html")
        with open(html_path) as f:
            content = f.read()
        self.assertIn("config", content)


# ============================================================================
# 8. Workflow Canvas Integration Tests
# ============================================================================

class TestWorkflowCanvasIntegration(unittest.TestCase):
    """Test the workflow canvas UI + API contract."""

    def test_canvas_has_terminal_output_alias(self):
        """Canvas should have terminal.output alias for appendOutput."""
        html_path = os.path.join(MURPHY_DIR, "workflow_canvas.html")
        with open(html_path) as f:
            content = f.read()
        self.assertIn("appendOutput", content)

    def test_canvas_has_save_load(self):
        """Canvas must have save and load functionality."""
        html_path = os.path.join(MURPHY_DIR, "workflow_canvas.html")
        with open(html_path) as f:
            content = f.read()
        self.assertIn("save", content.lower())
        self.assertIn("load", content.lower())

    def test_canvas_has_nl_input(self):
        """Canvas must have natural language workflow input."""
        html_path = os.path.join(MURPHY_DIR, "workflow_canvas.html")
        with open(html_path) as f:
            content = f.read()
        has_nl = "plain english" in content.lower() or "describe" in content.lower()
        self.assertTrue(has_nl, "Canvas missing NL input")


# ============================================================================
# 9. Terminal UI Integration Tests
# ============================================================================

class TestTerminalIntegration(unittest.TestCase):
    """Test terminal UIs have Librarian chat integration."""

    TERMINAL_FILES = [
        "terminal_unified.html",
        "terminal_integrated.html",
        "terminal_architect.html",
        "terminal_enhanced.html",
        "terminal_costs.html",
        "terminal_orgchart.html",
        "terminal_integrations.html",
        "terminal_worker.html",
    ]

    def test_terminals_have_librarian_chat(self):
        """All terminal UIs must have MurphyLibrarianChat component."""
        for fname in self.TERMINAL_FILES:
            path = os.path.join(MURPHY_DIR, fname)
            if not os.path.isfile(path):
                continue
            with open(path) as f:
                content = f.read()
            self.assertIn(
                "MurphyLibrarianChat",
                content,
                f"{fname} missing MurphyLibrarianChat",
            )

    def test_terminals_have_murphy_api(self):
        """All terminal UIs must instantiate MurphyAPI."""
        for fname in self.TERMINAL_FILES:
            path = os.path.join(MURPHY_DIR, fname)
            if not os.path.isfile(path):
                continue
            with open(path) as f:
                content = f.read()
            self.assertIn("MurphyAPI", content, f"{fname} missing MurphyAPI")


# ============================================================================
# 10. Landing Page Integration Tests
# ============================================================================

class TestLandingPageIntegration(unittest.TestCase):
    """Test landing page UI."""

    def test_landing_links_to_onboarding(self):
        """Landing page should link to onboarding or getting started."""
        path = os.path.join(MURPHY_DIR, "murphy_landing_page.html")
        with open(path) as f:
            content = f.read()
        has_onboarding = "onboarding" in content.lower() or "get started" in content.lower()
        self.assertTrue(has_onboarding, "Landing page missing onboarding link")

    def test_landing_has_terminal_links(self):
        """Landing page should link to terminal views."""
        path = os.path.join(MURPHY_DIR, "murphy_landing_page.html")
        with open(path) as f:
            content = f.read()
        self.assertIn("terminal_unified", content)


# ============================================================================
# 11. Infinite Loop Regression Tests (Bug Fix Validation)
# ============================================================================

class TestOnboardingLoopFixes(unittest.TestCase):
    """Regression tests for the onboarding infinite-loop bugs.

    These tests verify that:
    1. The profile summary is shown at most once and then the session
       transitions to normal chat routing (Bug 1 fix).
    2. Escape commands break out of the onboarding loop (Bug 3 fix).
    3. Bot/system responses are never fed into the dimension extractor
       as user data (Bug 2 fix).
    4. Post-summary messages are routed to the normal intent handler
       rather than re-rendering the profile summary (Bug 1 & 4 fix).
    5. A second call with an unchanged score and unchanged dimensions
       does NOT re-display the full profile summary (Bug 4 fix).
    """

    def setUp(self):
        self.murphy = _get_murphy()

    # ------------------------------------------------------------------
    # Helper: force profile to >=85% readiness
    # ------------------------------------------------------------------
    def _fill_profile_to_85(self, session: str) -> None:
        """Manually fill enough dimensions to reach 85% readiness."""
        profile = self.murphy._get_onboarding_profile(session)
        high_weight = sorted(
            self.murphy._ONBOARDING_DIMENSIONS.items(),
            key=lambda x: x[1]["weight"],
            reverse=True,
        )
        earned = 0
        total_weight = sum(d["weight"] for d in self.murphy._ONBOARDING_DIMENSIONS.values())
        for dim, info in high_weight:
            profile["collected"][dim] = "test_value"
            earned += info["weight"]
            if (earned / total_weight) * 100 >= 85:
                break

    # ------------------------------------------------------------------
    # Test 1 — Profile summary not repeated
    # ------------------------------------------------------------------
    def test_profile_summary_not_repeated(self):
        """After the profile summary is shown once, the next 3 messages
        should NOT contain the full profile summary again.  They should
        be routed to normal chat (Bug 1 regression)."""
        session = "regression-no-repeat"
        self._fill_profile_to_85(session)

        # First message — should trigger the profile summary
        r1 = self.murphy.librarian_ask("what else?", session_id=session)
        self.assertIn("MFGC/5U Readiness", r1["message"],
                      "First message at 85%+ should show the profile summary")

        # Subsequent messages must NOT re-display the full summary
        for i, msg in enumerate(["what else?", "no way!", "are you?"], start=2):
            r = self.murphy.librarian_ask(msg, session_id=session)
            self.assertNotIn(
                "Your profile summary",
                r["message"],
                f"Message {i} should NOT contain 'Your profile summary' (got: {r['message'][:200]})",
            )
            self.assertNotIn(
                "MFGC/5U Readiness",
                r["message"],
                f"Message {i} should NOT contain the readiness score header (got: {r['message'][:200]})",
            )

    # ------------------------------------------------------------------
    # Test 2 — Escape commands break the onboarding loop
    # ------------------------------------------------------------------
    def test_escape_commands_break_onboarding_loop(self):
        """Sending 'done', 'stop', 'cancel', or 'exit' during onboarding
        should transition the session to normal chat and NOT re-enter
        the dimension-extraction loop (Bug 3 regression)."""
        escape_words = ["done", "stop", "cancel", "exit", "skip"]
        for cmd in escape_words:
            with self.subTest(command=cmd):
                session = f"regression-escape-{cmd}"
                # Partially fill the profile so we are in onboarding state
                profile = self.murphy._get_onboarding_profile(session)
                profile["collected"]["business_name"] = "Escape Corp"
                profile["state"] = "onboarding"

                r = self.murphy.librarian_ask(cmd, session_id=session)

                # The response should acknowledge the escape
                self.assertIn(
                    "Onboarding paused",
                    r["message"],
                    f"'{cmd}' should trigger escape message, got: {r['message'][:200]}",
                )
                # State must be updated
                updated_profile = self.murphy._get_onboarding_profile(session)
                self.assertNotEqual(
                    updated_profile.get("state"), "onboarding",
                    f"After '{cmd}', state should not be 'onboarding'",
                )

    # ------------------------------------------------------------------
    # Test 3 — Bot responses not extracted as dimensions
    # ------------------------------------------------------------------
    def test_bot_responses_not_extracted_as_dimensions(self):
        """Messages that look like bot/system output must not be parsed
        as user-provided dimension values (Bug 2 regression)."""
        murphy = self.murphy
        bot_like_messages = [
            "Copilot said: Got it. Now I understand what you're doing",
            "📊 MFGC/5U Readiness: 88% ✅",
            "Murphy: I can help you with that",
            "📐 Magnify x3 applied — domain depth: 45",
            "✅ Ready to generate your plan!",
            "Excellent! I have enough information to build a tailored automation plan",
            "Your profile summary:\n• Business Name: Acme Corp",
            "Click Continue to Plan → to see your recommended modules",
            "Got it — \"some input\". Thanks for that information!",
        ]
        for msg in bot_like_messages:
            with self.subTest(msg=msg[:60]):
                profile = murphy._get_onboarding_profile(f"regression-bot-{abs(hash(msg))}")
                dims = murphy._extract_dimensions_from_message(msg, profile)
                self.assertEqual(
                    dims, {},
                    f"Bot-like message should extract NO dimensions, got {dims}: '{msg[:80]}'",
                )

    # ------------------------------------------------------------------
    # Test 4 — Post-summary messages route to intent handler
    # ------------------------------------------------------------------
    def test_post_summary_messages_route_to_intent_handler(self):
        """After the profile summary is shown, follow-up messages like
        'help' or 'status' should return meaningful, non-summary responses
        (Bug 1 & 4 regression)."""
        session = "regression-post-summary"
        self._fill_profile_to_85(session)

        # Trigger the initial summary
        self.murphy.librarian_ask("show me the plan", session_id=session)

        # Now subsequent messages must NOT contain the profile summary
        for follow_up in ["help", "what can you do", "are you?", "no way!"]:
            r = self.murphy.librarian_ask(follow_up, session_id=session)
            self.assertNotIn(
                "Your profile summary",
                r["message"],
                f"Post-summary message '{follow_up}' re-displayed profile summary",
            )

    # ------------------------------------------------------------------
    # Test 5 — Summary only shown when score / dimensions change
    # ------------------------------------------------------------------
    def test_summary_only_shown_when_score_changes(self):
        """If the score has not changed and no new dimensions were added,
        re-entering the onboarding handler must NOT re-display the full
        profile summary (Bug 4 regression)."""
        session = "regression-no-rehash"
        self._fill_profile_to_85(session)

        # First call — shows the summary and marks summary_shown=True
        r1 = self.murphy.librarian_ask("what else?", session_id=session)
        self.assertIn("MFGC/5U Readiness", r1["message"])

        # Verify state was properly updated after the first render
        profile = self.murphy._get_onboarding_profile(session)
        self.assertTrue(profile.get("summary_shown"),
                        "summary_shown should be True after first render")
        self.assertEqual(profile.get("state"), "plan_offered",
                         "state should be 'plan_offered' after first render")

        # A second direct call to _build_readiness_reply with unchanged data
        # should return the short "already ready" message instead of the full summary
        score = self.murphy._score_mfgc_readiness(profile)
        reply2 = self.murphy._build_readiness_reply(profile, score)
        self.assertNotIn(
            "Your profile summary",
            reply2,
            "Second _build_readiness_reply call with unchanged data should NOT re-render full summary",
        )



if __name__ == '__main__':
    unittest.main()
