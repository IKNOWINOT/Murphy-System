"""
Tests for the onboard LLM fixes:

- FIX-1: LocalLLMFallback._generate_offline — no context contamination
- FIX-2: LocalLLMFallback — business-domain knowledge (e-commerce, automation, etc.)
- FIX-3: UnifiedMFGC._process_with_context — None-answer crash fixed
- FIX-4: UnifiedMFGC._process_with_context — offline mode uses structured questions
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


# ---------------------------------------------------------------------------
# FIX-1: LocalLLMFallback context contamination
# ---------------------------------------------------------------------------

class TestLocalLLMFallbackContextContamination:
    """FIX-1: system context injected before the user query must not hijack topic matching."""

    def _make_llm(self):
        from local_llm_fallback import LocalLLMFallback
        return LocalLLMFallback()

    def test_murphy_in_context_does_not_match_murphy_topic(self):
        """When context contains 'murphy' but the user query is about e-commerce,
        the response must NOT be the murphy setup/info content."""
        llm = self._make_llm()
        context = "Knowledge-base topics: murphy, murphy_setup, murphy_troubleshooting"
        user_msg = "I run a small e-commerce business and want to automate order fulfillment."
        full_prompt = f"{context}\n\n{user_msg}"
        result = llm.generate(full_prompt, max_tokens=200)
        # Must NOT return the generic murphy-system description
        assert "Murphy System is an AI-powered automation assistant" not in result, (
            "Context contamination: 'murphy' in system context should not match 'murphy' "
            "knowledge-base topic and hijack the response"
        )

    def test_user_query_topic_match_still_works(self):
        """Direct murphy query (no context prefix) still returns murphy content."""
        llm = self._make_llm()
        result = llm.generate("What is Murphy System?", max_tokens=200)
        assert "Murphy" in result or "automation" in result.lower()

    def test_context_prefix_e_commerce_returns_ecommerce_content(self):
        """E-commerce query with context prefix returns e-commerce content, not murphy setup."""
        llm = self._make_llm()
        full_prompt = "Knowledge-base topics: murphy\n\nI want to automate my e-commerce store."
        result = llm.generate(full_prompt, max_tokens=200)
        # Should match e-commerce knowledge base entry
        ecom_keywords = ["e-commerce", "order", "fulfillment", "shopify", "automation", "store"]
        assert any(kw in result.lower() for kw in ecom_keywords), (
            f"Expected e-commerce content, got: {result[:200]}"
        )


# ---------------------------------------------------------------------------
# FIX-2: LocalLLMFallback business-domain knowledge
# ---------------------------------------------------------------------------

class TestLocalLLMFallbackBusinessDomain:
    """FIX-2: Knowledge base has entries for business/automation domain queries."""

    def _make_llm(self):
        from local_llm_fallback import LocalLLMFallback
        return LocalLLMFallback()

    def test_ecommerce_topic_in_knowledge_base(self):
        from local_llm_fallback import LocalLLMFallback
        llm = LocalLLMFallback()
        assert "e-commerce" in llm.knowledge_base or "ecommerce" in llm.knowledge_base or \
               any("ecommerce" in k or "e-commerce" in k for k in llm.knowledge_base), \
               "e-commerce topic missing from knowledge base"

    def test_automation_topic_in_knowledge_base(self):
        from local_llm_fallback import LocalLLMFallback
        llm = LocalLLMFallback()
        assert "automation" in llm.knowledge_base, "automation topic missing from knowledge base"

    def test_workflow_topic_in_knowledge_base(self):
        from local_llm_fallback import LocalLLMFallback
        llm = LocalLLMFallback()
        assert "workflow" in llm.knowledge_base, "workflow topic missing from knowledge base"

    def test_automation_query_gives_relevant_response(self):
        """A query mentioning 'automation' returns automation-relevant content."""
        llm = self._make_llm()
        result = llm.generate("I want to automate my business workflows", max_tokens=200)
        auto_keywords = ["automat", "trigger", "workflow", "task", "integration"]
        assert any(kw in result.lower() for kw in auto_keywords), (
            f"Automation query did not return relevant response: {result[:200]}"
        )

    def test_business_pattern_match(self):
        """'I run a business...' matches the business pattern and returns onboarding questions."""
        llm = self._make_llm()
        result = llm.generate("I run a small bakery and need to automate", max_tokens=200)
        # Should use business or automation response type
        assert len(result) > 20, "Response too short for a business query"

    def test_integration_pattern_match(self):
        """'I want to connect Shopify...' uses integration pattern."""
        llm = self._make_llm()
        result = llm.generate("I want to integrate Shopify with my accounting software", max_tokens=200)
        assert len(result) > 20, "Response too short for an integration query"


# ---------------------------------------------------------------------------
# FIX-3: UnifiedMFGC None-answer crash fix
# ---------------------------------------------------------------------------

class TestUnifiedMFGCNoneAnswerCrash:
    """FIX-3: _process_with_context must not crash when answers dict has None values."""

    def test_none_answer_values_do_not_crash(self):
        """When answers dict has None values (unanswered question placeholders),
        _process_with_context must not raise AttributeError."""
        from unified_mfgc import UnifiedMFGC
        mfgc = UnifiedMFGC()
        answers = {
            "initial_request": "I want to build a website",
            "What is your timeline?": None,   # unanswered question placeholder
            "What is your budget?": None,
        }
        # This must not raise AttributeError: 'NoneType' has no attribute 'lower'
        result = mfgc._process_with_context(
            message="I have 3 months and $5000 budget",
            answers=answers,
            context_summary="Murphy onboarding wizard.",
        )
        assert isinstance(result, dict), "Result should be a dict"
        assert "content" in result, "Result should have 'content' key"

    def test_empty_answers_dict_does_not_crash(self):
        """Empty answers dict must not crash _process_with_context."""
        from unified_mfgc import UnifiedMFGC
        mfgc = UnifiedMFGC()
        result = mfgc._process_with_context(
            message="I want to automate my business",
            answers={},
            context_summary="Murphy onboarding wizard.",
        )
        assert isinstance(result, dict)

    def test_all_none_answers_does_not_crash(self):
        """All-None answers dict must not crash _process_with_context."""
        from unified_mfgc import UnifiedMFGC
        mfgc = UnifiedMFGC()
        answers = {"q1": None, "q2": None, "q3": None}
        result = mfgc._process_with_context(
            message="I have 3 months and $5000",
            answers=answers,
            context_summary="Murphy onboarding wizard.",
        )
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# FIX-4: UnifiedMFGC offline mode structured questions
# ---------------------------------------------------------------------------

class TestUnifiedMFGCOfflineStructuredQuestions:
    """FIX-4: In offline mode, _process_with_context generates structured questions."""

    def test_offline_mode_generates_questions_not_generic_murphy_info(self):
        """When LLM mode is offline, response should be structured questions,
        NOT the generic Murphy System description."""
        from unified_mfgc import UnifiedMFGC
        mfgc = UnifiedMFGC()
        assert mfgc.llm_mode == "offline", "Test requires offline mode (no Groq key set)"
        result = mfgc._process_with_context(
            message="I run a small e-commerce business selling handmade crafts.",
            answers={"initial_request": "I run a small e-commerce business selling handmade crafts."},
            context_summary="Murphy onboarding wizard: helping a new user describe their business.",
        )
        content = result.get("content", "")
        # Must NOT be the murphy system description
        assert "Murphy System is an AI-powered automation assistant" not in content, (
            "Offline mode should not return generic murphy info"
        )
        # Must contain targeted questions
        assert "?" in content, f"Expected questions in offline response, got: {content[:200]}"

    def test_offline_mode_sets_questioning_mode(self):
        """In offline mode, response sets questioning_mode=True."""
        from unified_mfgc import UnifiedMFGC
        mfgc = UnifiedMFGC()
        if mfgc.llm_mode != "offline":
            pytest.skip("Test requires offline mode")
        result = mfgc._process_with_context(
            message="I want to automate my small business",
            answers={"initial_request": "I want to automate my small business"},
            context_summary="Murphy onboarding wizard.",
        )
        assert result.get("questioning_mode") is True, (
            "Offline mode should set questioning_mode=True"
        )
