"""
Tests for deliverable pipeline wiring  (label: FORGE-WIRE-TEST-001)

Validates:
1. Domain keyword engine exists and works as LLM-down fallback
2. _generate_llm_content falls through to domain engine when all LLM providers fail
3. Token limits use DeepInfra's actual model context (131 072), not arbitrary caps
4. No "64 agent" fiction in system prompts or token calculations
5. MFGC / MSS pipeline feeds into _generate_llm_content correctly
"""

import ast
import pathlib
import re
import sys
import unittest

# ---------------------------------------------------------------------------
# Path setup — 3-level resolution to repo root
# ---------------------------------------------------------------------------
_REPO = pathlib.Path(__file__).resolve().parent.parent.parent
_MURPHY = _REPO / "Murphy System"
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
if str(_MURPHY) not in sys.path:
    sys.path.insert(0, str(_MURPHY))

# Source files under test
_DDG = _MURPHY / "src" / "demo_deliverable_generator.py"
_LLP = _MURPHY / "src" / "llm_provider.py"
_LLC = _MURPHY / "src" / "llm_controller.py"


class TestDomainKeywordEngineExists(unittest.TestCase):
    """The static domain keyword engine must exist as an LLM-down fallback."""

    def setUp(self):
        self.src = _DDG.read_text()

    def test_domain_keyword_map_exists(self):
        """_DOMAIN_KEYWORD_MAP dict must be defined."""
        self.assertIn("_DOMAIN_KEYWORD_MAP", self.src,
                       "_DOMAIN_KEYWORD_MAP was deleted — restore it as LLM-down fallback")

    def test_detect_domains_exists(self):
        """_detect_domains() must be defined."""
        self.assertIn("def _detect_domains(", self.src,
                       "_detect_domains() was deleted — restore it")

    def test_build_deep_domain_content_exists(self):
        """_build_deep_domain_content() must be defined."""
        self.assertIn("def _build_deep_domain_content(", self.src,
                       "_build_deep_domain_content() was deleted — restore it")

    def test_minimal_content_uses_domain_engine(self):
        """_build_minimal_custom_content must call _build_deep_domain_content."""
        # Find the function body
        match = re.search(
            r"def _build_minimal_custom_content\(.*?\).*?(?=\ndef |\Z)",
            self.src,
            re.DOTALL,
        )
        self.assertIsNotNone(match, "_build_minimal_custom_content not found")
        body = match.group()
        self.assertIn("_build_deep_domain_content", body,
                       "_build_minimal_custom_content must delegate to the domain engine")

    def test_domain_map_covers_key_domains(self):
        """_DOMAIN_KEYWORD_MAP must cover at least the core domains."""
        required_domains = {"devops", "software", "security", "data", "content",
                            "operations", "strategy", "marketing", "compliance"}
        found = set(re.findall(r'"(\w+)":\s*"(\w+)"', self.src))
        mapped_domains = {v for _, v in found}
        missing = required_domains - mapped_domains
        self.assertFalse(missing,
                         f"Domain keyword map is missing domains: {missing}")


class TestNo64AgentFiction(unittest.TestCase):
    """The '64 agents' concept was a Cursor UI artefact — it must not appear."""

    def setUp(self):
        self.ddg_src = _DDG.read_text()
        self.llp_src = _LLP.read_text()
        self.llc_src = _LLC.read_text()

    def test_no_64_agents_in_system_prompt(self):
        """System prompt must not claim to be '64 agents'."""
        # Look specifically inside _generate_llm_content
        match = re.search(
            r"def _generate_llm_content\(.*?\).*?(?=\ndef |\Z)",
            self.ddg_src,
            re.DOTALL,
        )
        self.assertIsNotNone(match)
        body = match.group()
        self.assertNotIn("64 specialised", body)
        self.assertNotIn("64 parallel", body)
        self.assertNotIn("swarm of 64", body)

    def test_no_swarm_max_tokens_variable(self):
        """swarm_max_tokens variable must not exist — it encoded fake math."""
        self.assertNotIn("swarm_max_tokens", self.ddg_src)

    def test_no_estimate_scope_tokens(self):
        """_estimate_scope_tokens was a band-aid — MFGC/MSS handle scope."""
        self.assertNotIn("def _estimate_scope_tokens(", self.ddg_src)

    def test_no_64_in_llm_provider(self):
        """llm_provider.py must not reference '64 agents'."""
        self.assertNotIn("64 agents", self.llp_src)

    def test_no_64_in_llm_controller(self):
        """llm_controller.py must not reference '64 agents'."""
        self.assertNotIn("64 agents", self.llc_src)


class TestTokenLimitsMatchDeepInfra(unittest.TestCase):
    """Token limits must reflect DeepInfra's actual model capability."""

    def test_llm_provider_constant_exists(self):
        """DEEPINFRA_MODEL_CONTEXT constant must be defined."""
        src = _LLP.read_text()
        self.assertIn("DEEPINFRA_MODEL_CONTEXT", src)

    def test_llm_provider_context_is_131072(self):
        """DEEPINFRA_MODEL_CONTEXT must be 131072 (Llama-3.1-70B full context)."""
        src = _LLP.read_text()
        match = re.search(r"DEEPINFRA_MODEL_CONTEXT\s*=\s*(\d+)", src)
        self.assertIsNotNone(match, "DEEPINFRA_MODEL_CONTEXT not found")
        self.assertEqual(int(match.group(1)), 131072)

    def test_complete_messages_default_uses_constant(self):
        """complete_messages() default max_tokens must reference DEEPINFRA_MODEL_CONTEXT."""
        src = _LLP.read_text()
        # Find complete_messages signature
        match = re.search(r"def complete_messages\(.*?\).*?:", src, re.DOTALL)
        self.assertIsNotNone(match)
        sig = match.group()
        self.assertIn("DEEPINFRA_MODEL_CONTEXT", sig,
                       "complete_messages default must use DEEPINFRA_MODEL_CONTEXT, not a hardcoded number")

    def test_llm_controller_default_is_131072(self):
        """LLMRequest.max_tokens default must be 131072."""
        src = _LLC.read_text()
        match = re.search(r"max_tokens:\s*int\s*=\s*(\d+)", src)
        self.assertIsNotNone(match, "LLMRequest.max_tokens not found")
        self.assertEqual(int(match.group(1)), 131072)

    def test_generate_llm_content_uses_full_context(self):
        """_generate_llm_content must pass 131072 (or DEEPINFRA_MODEL_CONTEXT) to providers."""
        src = _DDG.read_text()
        match = re.search(
            r"def _generate_llm_content\(.*?\).*?(?=\ndef |\Z)",
            src,
            re.DOTALL,
        )
        self.assertIsNotNone(match)
        body = match.group()
        # Must contain 131072 somewhere — either as literal or via the constant
        self.assertTrue(
            "131072" in body or "DEEPINFRA_MODEL_CONTEXT" in body,
            "_generate_llm_content must use DeepInfra's full context window (131072)"
        )
        # Must NOT contain the old hardcoded 16384
        self.assertNotIn("swarm_max_tokens = 16384", body)


class TestPipelineWiring(unittest.TestCase):
    """The deliverable pipeline must wire MFGC → MSS → LLM correctly."""

    def setUp(self):
        self.src = _DDG.read_text()

    def test_generate_custom_deliverable_calls_mfgc(self):
        """generate_custom_deliverable must call _run_mfgc_gate."""
        match = re.search(
            r"def generate_custom_deliverable\(.*?\).*?(?=\ndef |\Z)",
            self.src,
            re.DOTALL,
        )
        self.assertIsNotNone(match)
        body = match.group()
        self.assertIn("_run_mfgc_gate", body)

    def test_generate_custom_deliverable_calls_mss(self):
        """generate_custom_deliverable must call _run_mss_pipeline."""
        match = re.search(
            r"def generate_custom_deliverable\(.*?\).*?(?=\ndef |\Z)",
            self.src,
            re.DOTALL,
        )
        self.assertIsNotNone(match)
        body = match.group()
        self.assertIn("_run_mss_pipeline", body)

    def test_generate_custom_deliverable_calls_llm_content(self):
        """generate_custom_deliverable must call _generate_llm_content."""
        match = re.search(
            r"def generate_custom_deliverable\(.*?\).*?(?=\ndef |\Z)",
            self.src,
            re.DOTALL,
        )
        self.assertIsNotNone(match)
        body = match.group()
        self.assertIn("_generate_llm_content", body)

    def test_llm_content_accepts_mfgc_and_mss(self):
        """_generate_llm_content signature must accept mfgc_result and mss_result."""
        match = re.search(
            r"def _generate_llm_content\((.*?)\)",
            self.src,
            re.DOTALL,
        )
        self.assertIsNotNone(match)
        sig = match.group(1)
        self.assertIn("mfgc_result", sig)
        self.assertIn("mss_result", sig)

    def test_llm_content_feeds_domain_content_to_llm(self):
        """_generate_llm_content must feed domain engine output into the LLM prompt."""
        match = re.search(
            r"def _generate_llm_content\(.*?\).*?(?=\ndef |\Z)",
            self.src,
            re.DOTALL,
        )
        self.assertIsNotNone(match)
        body = match.group()
        self.assertIn("_build_deep_domain_content", body,
                       "Domain engine output should enrich the LLM prompt context")

    def test_fallback_chain_ends_at_domain_engine(self):
        """When all LLM providers fail, _build_minimal_custom_content is the final fallback."""
        match = re.search(
            r"def _generate_llm_content\(.*?\).*?(?=\ndef |\Z)",
            self.src,
            re.DOTALL,
        )
        self.assertIsNotNone(match)
        body = match.group()
        self.assertIn("_build_minimal_custom_content", body)


class TestSyntaxValid(unittest.TestCase):
    """All modified source files must be valid Python."""

    def test_demo_deliverable_generator_syntax(self):
        ast.parse(_DDG.read_text())

    def test_llm_provider_syntax(self):
        ast.parse(_LLP.read_text())

    def test_llm_controller_syntax(self):
        ast.parse(_LLC.read_text())


# ═══════════════════════════════════════════════════════════════════════════
# Regression guards for wire reconnection  (label: TEST-WIRE-002)
# ═══════════════════════════════════════════════════════════════════════════

class TestWireRegressionGuards(unittest.TestCase):
    """Regression guards ensuring enrichment wires stay connected."""

    def setUp(self):
        self.ddg_src = _DDG.read_text()
        self.llp_src = _LLP.read_text()

    def test_run_mss_pipeline_captures_magnify_quality(self):
        """_run_mss_pipeline must populate 'magnify_quality' key."""
        match = re.search(
            r"def _run_mss_pipeline\(.*?\).*?(?=\ndef |\Z)",
            self.ddg_src, re.DOTALL,
        )
        self.assertIsNotNone(match)
        body = match.group()
        self.assertIn("magnify_quality", body,
                       "WIRE-MSS-001: _run_mss_pipeline must capture magnify_quality")

    def test_run_mss_pipeline_captures_simulation(self):
        """_run_mss_pipeline must populate 'simulation' key."""
        match = re.search(
            r"def _run_mss_pipeline\(.*?\).*?(?=\ndef |\Z)",
            self.ddg_src, re.DOTALL,
        )
        self.assertIsNotNone(match)
        body = match.group()
        self.assertIn('"simulation"', body,
                       "WIRE-MSS-001: _run_mss_pipeline must capture simulation data")

    def test_build_content_from_mss_renders_architecture_mapping(self):
        """_build_content_from_mss must render architecture_mapping."""
        match = re.search(
            r"def _build_content_from_mss\(.*?\).*?(?=\ndef |\Z)",
            self.ddg_src, re.DOTALL,
        )
        self.assertIsNotNone(match)
        body = match.group()
        self.assertIn("architecture_mapping", body,
                       "WIRE-MSS-002: architecture_mapping must be rendered")

    def test_build_content_from_mss_renders_module_specification(self):
        """_build_content_from_mss must render module_specification."""
        match = re.search(
            r"def _build_content_from_mss\(.*?\).*?(?=\ndef |\Z)",
            self.ddg_src, re.DOTALL,
        )
        self.assertIsNotNone(match)
        body = match.group()
        self.assertIn("module_specification", body,
                       "WIRE-MSS-003: module_specification must be rendered")

    def test_build_content_from_mss_renders_resolution_progression(self):
        """_build_content_from_mss must render resolution_progression."""
        match = re.search(
            r"def _build_content_from_mss\(.*?\).*?(?=\ndef |\Z)",
            self.ddg_src, re.DOTALL,
        )
        self.assertIsNotNone(match)
        body = match.group()
        self.assertIn("resolution_progression", body,
                       "WIRE-MSS-004: resolution_progression must be rendered")

    def test_build_content_from_mss_accepts_mfgc_result(self):
        """_build_content_from_mss must accept mfgc_result parameter."""
        match = re.search(
            r"def _build_content_from_mss\((.*?)\)",
            self.ddg_src, re.DOTALL,
        )
        self.assertIsNotNone(match)
        sig = match.group(1)
        self.assertIn("mfgc_result", sig,
                       "WIRE-MFGC-001: _build_content_from_mss must accept mfgc_result")

    def test_acomplete_defaults_match_sync(self):
        """All async LLM methods must default to DEEPINFRA_MODEL_CONTEXT."""
        # Check acomplete method signature
        for method_name in ("acomplete", "acomplete_messages", "_acomplete_with_fallback"):
            match = re.search(
                rf"def {re.escape(method_name)}\(.*?\).*?:",
                self.llp_src, re.DOTALL,
            )
            self.assertIsNotNone(match, f"{method_name} not found")
            sig = match.group()
            self.assertIn("DEEPINFRA_MODEL_CONTEXT", sig,
                           f"WIRE-LLM-001: {method_name} must default to DEEPINFRA_MODEL_CONTEXT")

    def test_generate_llm_content_accepts_expert_result(self):
        """_generate_llm_content must accept expert_result parameter."""
        match = re.search(
            r"def _generate_llm_content\((.*?)\)",
            self.ddg_src, re.DOTALL,
        )
        self.assertIsNotNone(match)
        sig = match.group(1)
        self.assertIn("expert_result", sig,
                       "WIRE-EXPERT-001: _generate_llm_content must accept expert_result")

    def test_production_workflow_registry_wire_wf_001_label(self):
        """production_workflow_registry.py must have WIRE-WF-001 documentation."""
        pwr = (_MURPHY / "src" / "production_workflow_registry.py").read_text()
        self.assertIn("WIRE-WF-001", pwr,
                       "WIRE-WF-001: workflow step dispatch must be documented as intentional metadata")

    def test_generate_deliverable_with_progress_includes_automation_spec(self):
        """generate_deliverable_with_progress must call generate_automation_spec."""
        match = re.search(
            r"def generate_deliverable_with_progress\(.*?\).*?(?=\ndef |\Z)",
            self.ddg_src, re.DOTALL,
        )
        self.assertIsNotNone(match)
        body = match.group()
        self.assertIn("generate_automation_spec", body,
                       "WIRE-SPEC-001: streaming pipeline must generate automation spec")


if __name__ == "__main__":
    unittest.main()
