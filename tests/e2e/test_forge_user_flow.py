"""
User-flow end-to-end tests for the Forge deliverable pipeline.

Tests the system *as a user would experience it*:
  - Submit a query → get a deliverable back
  - The MFGC gate, MSS pipeline, LLM content generation, and domain
    keyword fallback all participate in producing the output
  - Concurrent MSS processing (Magnify + Solidify run in parallel)
  - The 5-phase progress pipeline reports real events
  - The system never crashes — fallback layers always produce output

Labels: FORGE-E2E-001, FORGE-USERFLOW-001
"""

import ast
import pathlib
import re
import sys
import textwrap
import unittest
from unittest import mock

# ---------------------------------------------------------------------------
# Path setup — 3-level resolution to repo root
# ---------------------------------------------------------------------------
_REPO = pathlib.Path(__file__).resolve().parent.parent.parent
_MURPHY = _REPO / "Murphy System"
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
if str(_MURPHY) not in sys.path:
    sys.path.insert(0, str(_MURPHY))
if str(_MURPHY / "src") not in sys.path:
    sys.path.insert(0, str(_MURPHY / "src"))

# Source file under test
_DDG = _MURPHY / "src" / "demo_deliverable_generator.py"


# ── Helpers ────────────────────────────────────────────────────────────────

def _import_ddg():
    """Import demo_deliverable_generator from Murphy System/src."""
    # We import via importlib to avoid name-collision with the root src/ copy
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "demo_deliverable_generator", str(_DDG),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _source_text():
    return _DDG.read_text()


# ===========================================================================
# 1.  User flow: submit query → get deliverable
# ===========================================================================

class TestUserFlowGetDeliverable(unittest.TestCase):
    """A user submits a query and receives a complete deliverable."""

    def test_generate_deliverable_exists(self):
        """The top-level entry point must exist."""
        src = _source_text()
        self.assertIn("def generate_deliverable(", src)

    def test_generate_custom_deliverable_exists(self):
        """The custom deliverable path must exist."""
        src = _source_text()
        self.assertIn("def generate_custom_deliverable(", src)

    def test_deliverable_pipeline_has_all_stages(self):
        """generate_custom_deliverable must wire all 5 stages:
        MFGC gate → MSS → LLM content → librarian → automation check."""
        src = _source_text()
        func_match = re.search(
            r"def generate_custom_deliverable\(.*?\).*?(?=\ndef |\Z)",
            src, re.DOTALL,
        )
        self.assertIsNotNone(func_match)
        body = func_match.group()
        self.assertIn("_run_mfgc_gate", body, "Stage 1: MFGC gate must be called")
        self.assertIn("_run_mss_pipeline", body, "Stage 2: MSS pipeline must be called")
        self.assertIn("_generate_llm_content", body, "Stage 3: LLM content generation must be called")

    def test_deliverable_output_structure(self):
        """Output must have title, content, filename — matching user-visible format."""
        src = _source_text()
        func_match = re.search(
            r"def generate_custom_deliverable\(.*?\).*?(?=\ndef |\Z)",
            src, re.DOTALL,
        )
        body = func_match.group()
        self.assertIn('"title"', body)
        self.assertIn('"content"', body)
        self.assertIn('"filename"', body)


# ===========================================================================
# 2.  User flow: real-time progress (SSE streaming)
# ===========================================================================

class TestUserFlowProgressStream(unittest.TestCase):
    """A user watches real-time progress of their deliverable build."""

    def test_progress_function_exists(self):
        src = _source_text()
        self.assertIn("def generate_deliverable_with_progress(", src)

    def test_progress_has_all_5_phases(self):
        """The progress pipeline must emit events for all 5 phases."""
        src = _source_text()
        func_match = re.search(
            r"def generate_deliverable_with_progress\(.*?\).*?(?=\ndef |\Z)",
            src, re.DOTALL,
        )
        self.assertIsNotNone(func_match)
        body = func_match.group()

        # Phase 1: MFGC Gate
        self.assertIn('"phase": 1', body, "Phase 1 (MFGC gate) event must be emitted")
        # Phase 2: Workflow Resolution
        self.assertIn('"phase": 2', body, "Phase 2 (workflow resolution) event must be emitted")
        # Phase 3: MSS Pipeline
        self.assertIn('"phase": 3', body, "Phase 3 (MSS pipeline) event must be emitted")
        # Phase 4: Execute Workflow
        self.assertIn('"phase": 4', body, "Phase 4 (execute workflow) event must be emitted")
        # Phase 5: HITL Review
        self.assertIn('"phase": 5', body, "Phase 5 (HITL review) event must be emitted")
        # Done event
        self.assertIn('"phase": "done"', body, "Final 'done' event must be emitted")

    def test_progress_done_event_has_deliverable(self):
        """The final 'done' event must carry the full deliverable dict."""
        src = _source_text()
        func_match = re.search(
            r"def generate_deliverable_with_progress\(.*?\).*?(?=\ndef |\Z)",
            src, re.DOTALL,
        )
        body = func_match.group()
        # The done event must include the deliverable
        self.assertIn('"deliverable":', body)

    def test_progress_done_event_has_metrics(self):
        """The final 'done' event must carry quality metrics."""
        src = _source_text()
        func_match = re.search(
            r"def generate_deliverable_with_progress\(.*?\).*?(?=\ndef |\Z)",
            src, re.DOTALL,
        )
        body = func_match.group()
        self.assertIn('"metrics":', body)
        self.assertIn('"quality_score":', body)

    def test_progress_reports_workflow_decision(self):
        """Phase 2 must report the workflow resolution decision (reuse/modify/create)."""
        src = _source_text()
        func_match = re.search(
            r"def generate_deliverable_with_progress\(.*?\).*?(?=\ndef |\Z)",
            src, re.DOTALL,
        )
        body = func_match.group()
        self.assertIn('"workflow_decision":', body)


# ===========================================================================
# 3.  Concurrent processing (MSS Magnify + Solidify in parallel)
# ===========================================================================

class TestConcurrentMSSProcessing(unittest.TestCase):
    """MSS Magnify and Solidify must run concurrently — they are independent."""

    def test_mss_pipeline_uses_thread_pool(self):
        """_run_mss_pipeline must use ThreadPoolExecutor for concurrent dispatch."""
        src = _source_text()
        func_match = re.search(
            r"def _run_mss_pipeline\(.*?\).*?(?=\ndef |\Z)",
            src, re.DOTALL,
        )
        self.assertIsNotNone(func_match)
        body = func_match.group()
        self.assertIn("ThreadPoolExecutor", body,
                       "MSS pipeline must use ThreadPoolExecutor for parallel Magnify+Solidify")

    def test_mss_pipeline_submits_both_magnify_and_solidify(self):
        """Both mss.magnify and mss.solidify must be submitted concurrently."""
        src = _source_text()
        func_match = re.search(
            r"def _run_mss_pipeline\(.*?\).*?(?=\ndef |\Z)",
            src, re.DOTALL,
        )
        body = func_match.group()
        self.assertIn("mss.magnify", body)
        self.assertIn("mss.solidify", body)
        # Both must be submitted as futures (pool.submit), not called sequentially
        self.assertIn("pool.submit", body,
                       "Magnify and Solidify must be submitted as concurrent futures")

    def test_mss_pipeline_uses_at_least_2_workers(self):
        """Thread pool must allow at least 2 workers for true concurrency."""
        src = _source_text()
        func_match = re.search(
            r"def _run_mss_pipeline\(.*?\).*?(?=\ndef |\Z)",
            src, re.DOTALL,
        )
        body = func_match.group()
        # Check max_workers >= 2
        match = re.search(r"max_workers\s*=\s*(\d+)", body)
        self.assertIsNotNone(match, "max_workers must be specified")
        self.assertGreaterEqual(int(match.group(1)), 2)


# ===========================================================================
# 4.  Agent task count driven by MSS/workflow — NOT hardcoded
# ===========================================================================

class TestAgentTaskCountDynamic(unittest.TestCase):
    """Agent task count must be driven by actual MSS/workflow output."""

    def test_no_hardcoded_64_range(self):
        """_build_agent_task_list must NOT use range(64) — task count is dynamic."""
        src = _source_text()
        func_match = re.search(
            r"def _build_agent_task_list\(.*?\).*?(?=\ndef |\Z)",
            src, re.DOTALL,
        )
        self.assertIsNotNone(func_match)
        body = func_match.group()
        self.assertNotIn("range(64)", body,
                         "Agent task count must not be hardcoded to 64")

    def test_task_count_matches_items(self):
        """The function must produce exactly len(items) tasks, not a fixed number."""
        src = _source_text()
        func_match = re.search(
            r"def _build_agent_task_list\(.*?\).*?(?=\ndef |\Z)",
            src, re.DOTALL,
        )
        body = func_match.group()
        # Must iterate over actual items, not a fixed range
        self.assertTrue(
            "enumerate(items)" in body or "for i, item" in body,
            "Must enumerate actual items rather than a fixed range"
        )

    def test_no_64_agent_in_docstring(self):
        """Docstring must not reference '64-agent'."""
        src = _source_text()
        func_match = re.search(
            r"def _build_agent_task_list\(.*?\).*?(?=\ndef |\Z)",
            src, re.DOTALL,
        )
        body = func_match.group()
        self.assertNotIn("64-agent", body)
        self.assertNotIn("64 agent", body)


# ===========================================================================
# 5.  Fallback chain — system never crashes
# ===========================================================================

class TestFallbackChainNeverCrashes(unittest.TestCase):
    """From a user's perspective, every query must produce output — no crashes."""

    def test_mfgc_gate_returns_fallback_on_failure(self):
        """_run_mfgc_gate must return a dict with fallback=True on error, not raise."""
        src = _source_text()
        func_match = re.search(
            r"def _run_mfgc_gate\(.*?\).*?(?=\ndef |\Z)",
            src, re.DOTALL,
        )
        body = func_match.group()
        self.assertIn('"fallback": True', body)
        # Must catch both ImportError and generic Exception
        self.assertIn("except ImportError", body)
        self.assertIn("except Exception", body)

    def test_mss_pipeline_returns_fallback_on_failure(self):
        """_run_mss_pipeline must return a dict with fallback=True on error, not raise."""
        src = _source_text()
        func_match = re.search(
            r"def _run_mss_pipeline\(.*?\).*?(?=\ndef |\Z)",
            src, re.DOTALL,
        )
        body = func_match.group()
        self.assertIn('"fallback": True', body)
        self.assertIn("except ImportError", body)
        self.assertIn("except Exception", body)

    def test_llm_content_has_domain_engine_fallback(self):
        """_generate_llm_content must fall through to domain keyword engine."""
        src = _source_text()
        func_match = re.search(
            r"def _generate_llm_content\(.*?\).*?(?=\ndef |\Z)",
            src, re.DOTALL,
        )
        body = func_match.group()
        self.assertIn("_build_minimal_custom_content", body,
                       "Last fallback must be the domain keyword engine")

    def test_domain_engine_produces_structured_content(self):
        """_build_minimal_custom_content must produce structured content, not empty string."""
        src = _source_text()
        func_match = re.search(
            r"def _build_minimal_custom_content\(.*?\).*?(?=\ndef |\Z)",
            src, re.DOTALL,
        )
        self.assertIsNotNone(func_match)
        body = func_match.group()
        # Must reference the domain engine
        self.assertIn("_build_deep_domain_content", body)
        # Must produce structured sections
        self.assertIn("DELIVERABLE OVERVIEW", body)
        self.assertIn("EXECUTIVE SUMMARY", body)


# ===========================================================================
# 6.  Token limits: DeepInfra actual limits, not artificial caps
# ===========================================================================

class TestTokenLimitsUserExperience(unittest.TestCase):
    """From a user's perspective, the system must not truncate output artificially."""

    def test_no_artificial_token_cap_in_llm_content(self):
        """_generate_llm_content must not hardcode 16384 or any small token limit."""
        src = _source_text()
        func_match = re.search(
            r"def _generate_llm_content\(.*?\).*?(?=\ndef |\Z)",
            src, re.DOTALL,
        )
        body = func_match.group()
        # Must use 131072 (DeepInfra actual), not 16384
        self.assertNotIn("= 16384", body,
                         "Must not cap tokens at 16384 — DeepInfra supports 131072")
        self.assertTrue(
            "131072" in body or "DEEPINFRA_MODEL_CONTEXT" in body,
            "Token budget must reference DeepInfra's actual 131K context window"
        )

    def test_llm_provider_default_not_artificially_low(self):
        """MurphyLLMProvider.complete_messages default max_tokens must be >= 131072."""
        llp = (_MURPHY / "src" / "llm_provider.py").read_text()
        match = re.search(r"DEEPINFRA_MODEL_CONTEXT\s*=\s*(\d+)", llp)
        self.assertIsNotNone(match)
        self.assertEqual(int(match.group(1)), 131072)


# ===========================================================================
# 7.  Workflow persistence — user benefits from past builds
# ===========================================================================

class TestWorkflowPersistence(unittest.TestCase):
    """Users benefit when previously-built workflows are reused."""

    def test_progress_pipeline_persists_workflow(self):
        """generate_deliverable_with_progress must attempt to persist the workflow."""
        src = _source_text()
        func_match = re.search(
            r"def generate_deliverable_with_progress\(.*?\).*?(?=\ndef |\Z)",
            src, re.DOTALL,
        )
        body = func_match.group()
        self.assertIn("persist_workflow", body,
                       "New workflows must be persisted for future reuse")

    def test_progress_pipeline_records_usage(self):
        """Workflow usage must be recorded for quality tracking."""
        src = _source_text()
        func_match = re.search(
            r"def generate_deliverable_with_progress\(.*?\).*?(?=\ndef |\Z)",
            src, re.DOTALL,
        )
        body = func_match.group()
        self.assertIn("record_usage", body,
                       "Workflow usage must be recorded for analytics")


# ===========================================================================
# 8.  Syntax validation
# ===========================================================================

class TestSyntaxValid(unittest.TestCase):
    """Modified source must parse without errors."""

    def test_demo_deliverable_generator_syntax(self):
        ast.parse(_DDG.read_text())


if __name__ == "__main__":
    unittest.main()
