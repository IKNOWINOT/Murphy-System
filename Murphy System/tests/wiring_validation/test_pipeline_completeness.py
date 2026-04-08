# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post | License: BSL-1.1
"""Pipeline completeness tests  (label: TEST-WIRE-001).

Validates that every enrichment wire in the Forge deliverable pipeline is
connected end-to-end.  Each test maps 1:1 to a WIRE-* label in the
Production Commissioning Plan.

Run:  pytest -m wiring_validation -k test_pipeline_completeness
"""
from __future__ import annotations

import inspect
import sys
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Path setup — ensure Murphy System/src is importable
# ---------------------------------------------------------------------------
_ROOT = Path(__file__).resolve().parent.parent.parent          # Murphy System/
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
if str(_ROOT.parent) not in sys.path:
    sys.path.insert(0, str(_ROOT.parent))


# ═══════════════════════════════════════════════════════════════════════════
# WIRE-LLM-001 — Async LLM defaults match sync defaults
# ═══════════════════════════════════════════════════════════════════════════

class TestWireLLM001:
    """Verify that async LLM methods share the same max_tokens default
    as the sync methods (DEEPINFRA_MODEL_CONTEXT = 131072)."""

    def test_deepinfra_model_context_constant_exists(self):
        from src.llm_provider import DEEPINFRA_MODEL_CONTEXT
        assert DEEPINFRA_MODEL_CONTEXT == 131_072

    def test_sync_complete_uses_model_context(self):
        from src.llm_provider import MurphyLLMProvider, DEEPINFRA_MODEL_CONTEXT
        sig = inspect.signature(MurphyLLMProvider.complete)
        default = sig.parameters["max_tokens"].default
        assert default == DEEPINFRA_MODEL_CONTEXT, (
            f"complete() max_tokens default is {default}, expected {DEEPINFRA_MODEL_CONTEXT}"
        )

    def test_async_acomplete_uses_model_context(self):
        from src.llm_provider import MurphyLLMProvider, DEEPINFRA_MODEL_CONTEXT
        sig = inspect.signature(MurphyLLMProvider.acomplete)
        default = sig.parameters["max_tokens"].default
        assert default == DEEPINFRA_MODEL_CONTEXT, (
            f"acomplete() max_tokens default is {default}, expected {DEEPINFRA_MODEL_CONTEXT}"
        )

    def test_async_acomplete_messages_uses_model_context(self):
        from src.llm_provider import MurphyLLMProvider, DEEPINFRA_MODEL_CONTEXT
        sig = inspect.signature(MurphyLLMProvider.acomplete_messages)
        default = sig.parameters["max_tokens"].default
        assert default == DEEPINFRA_MODEL_CONTEXT

    def test_async_acomplete_with_fallback_uses_model_context(self):
        from src.llm_provider import MurphyLLMProvider, DEEPINFRA_MODEL_CONTEXT
        sig = inspect.signature(MurphyLLMProvider._acomplete_with_fallback)
        default = sig.parameters["max_tokens"].default
        assert default == DEEPINFRA_MODEL_CONTEXT

    def test_module_level_complete_uses_model_context(self):
        import src.llm_provider as llm
        sig = inspect.signature(llm.complete)
        default = sig.parameters["max_tokens"].default
        assert default == llm.DEEPINFRA_MODEL_CONTEXT

    def test_module_level_acomplete_uses_model_context(self):
        import src.llm_provider as llm
        sig = inspect.signature(llm.acomplete)
        default = sig.parameters["max_tokens"].default
        assert default == llm.DEEPINFRA_MODEL_CONTEXT


# ═══════════════════════════════════════════════════════════════════════════
# WIRE-MSS-001 — MSS quality & simulation metadata captured
# ═══════════════════════════════════════════════════════════════════════════

class TestWireMSS001:
    """Verify that _run_mss_pipeline() returns quality & simulation fields
    when MSS runs successfully."""

    def _make_mock_transformation(
        self,
        *,
        output: Dict[str, Any],
        governance: str = "approved",
        cqi: float = 4.5,
        recommendation: str = "proceed",
        risk_indicators: list = None,
        simulation: Any = None,
    ):
        """Build a mock TransformationResult."""
        mock = MagicMock()
        mock.output = output
        mock.governance_status = governance
        mock.output_quality = MagicMock()
        mock.output_quality.cqi = cqi
        mock.output_quality.iqs = 3.8
        mock.output_quality.resolution_level = "RM3"
        mock.output_quality.recommendation = recommendation
        mock.output_quality.risk_indicators = risk_indicators or []
        mock.simulation = simulation
        return mock

    def _make_mock_simulation(self):
        sim = MagicMock()
        sim.cost_impact = 2.1
        sim.complexity_impact = 3.0
        sim.compliance_impact = 1.5
        sim.performance_impact = 2.0
        sim.overall_score = 2.15
        sim.risk_level = "moderate"
        sim.recommended = True
        sim.warnings = ["Watch cost"]
        sim.estimated_engineering_hours = 40.0
        sim.regulatory_implications = ["GDPR"]
        return sim

    @patch("src.demo_deliverable_generator._build_mss_controller")
    def test_pipeline_returns_quality_metadata(self, mock_build):
        from src.demo_deliverable_generator import _run_mss_pipeline

        sim = self._make_mock_simulation()
        mag = self._make_mock_transformation(
            output={"functional_requirements": ["req1"]},
        )
        sol = self._make_mock_transformation(
            output={"implementation_steps": ["step1"]},
            simulation=sim,
        )
        mock_ctrl = MagicMock()
        mock_ctrl.magnify.return_value = mag
        mock_ctrl.solidify.return_value = sol
        mock_build.return_value = mock_ctrl

        result = _run_mss_pipeline("test query", {"confidence": 0.8})

        assert result["fallback"] is False
        # Quality metadata present
        assert "magnify_quality" in result
        assert result["magnify_quality"]["cqi"] == 4.5
        assert result["magnify_quality"]["recommendation"] == "proceed"
        # Simulation metadata present
        assert "simulation" in result
        assert result["simulation"]["risk_level"] == "moderate"
        assert result["simulation"]["estimated_engineering_hours"] == 40.0
        assert result["simulation"]["warnings"] == ["Watch cost"]
        assert result["simulation"]["regulatory_implications"] == ["GDPR"]

    @patch("src.demo_deliverable_generator._build_mss_controller")
    def test_pipeline_fallback_has_no_quality_metadata(self, mock_build):
        from src.demo_deliverable_generator import _run_mss_pipeline

        mock_build.side_effect = ImportError("test")
        result = _run_mss_pipeline("test query", {})

        assert result["fallback"] is True
        assert "magnify_quality" not in result
        assert "simulation" not in result


# ═══════════════════════════════════════════════════════════════════════════
# WIRE-MSS-002/003/004 — MSS enrichment fields rendered
# ═══════════════════════════════════════════════════════════════════════════

class TestWireMSSEnrichment:
    """Verify that _build_content_from_mss() renders all enrichment fields."""

    def test_architecture_mapping_rendered(self):
        from src.demo_deliverable_generator import _build_content_from_mss

        mss_result = {
            "magnify": {
                "architecture_mapping": {
                    "components": ["API Gateway", "Database"],
                    "data_flows": ["client→gateway→db"],
                    "control_logic": ["auth middleware"],
                    "validation_methods": ["schema validation"],
                },
            },
            "solidify": {},
        }
        content = _build_content_from_mss("test", mss_result)
        assert "ARCHITECTURE MAPPING" in content
        assert "API Gateway" in content
        assert "schema validation" in content

    def test_module_specification_rendered(self):
        from src.demo_deliverable_generator import _build_content_from_mss

        mss_result = {
            "magnify": {},
            "solidify": {
                "module_specification": {
                    "name": "AuthModule",
                    "purpose": "Handle authentication",
                    "dependencies": ["jwt", "bcrypt"],
                    "interfaces": ["IAuthProvider"],
                },
            },
        }
        content = _build_content_from_mss("test", mss_result)
        assert "MODULE SPECIFICATION" in content
        assert "AuthModule" in content
        assert "jwt, bcrypt" in content

    def test_existing_module_analysis_rendered(self):
        from src.demo_deliverable_generator import _build_content_from_mss

        mss_result = {
            "magnify": {},
            "solidify": {
                "existing_module_analysis": "Current auth module uses session cookies",
            },
        }
        content = _build_content_from_mss("test", mss_result)
        assert "EXISTING MODULE ANALYSIS" in content
        assert "session cookies" in content

    def test_resolution_progression_rendered(self):
        from src.demo_deliverable_generator import _build_content_from_mss

        mss_result = {
            "magnify": {"resolution_progression": "RM0 → RM2"},
            "solidify": {"resolution_progression": "RM0 → RM5"},
        }
        content = _build_content_from_mss("test", mss_result)
        assert "Resolution:" in content
        assert "RM0 → RM2" in content
        assert "RM0 → RM5" in content

    def test_quality_metrics_rendered(self):
        from src.demo_deliverable_generator import _build_content_from_mss

        mss_result = {
            "magnify": {},
            "solidify": {},
            "magnify_quality": {
                "cqi": 4.5,
                "resolution_level": "RM3",
                "recommendation": "proceed",
                "risk_indicators": [],
            },
            "solidify_quality": {
                "cqi": 5.0,
                "resolution_level": "RM5",
                "recommendation": "proceed",
                "risk_indicators": ["complex"],
            },
        }
        content = _build_content_from_mss("test", mss_result)
        assert "QUALITY METRICS" in content
        assert "4.50" in content
        assert "5.00" in content

    def test_simulation_impact_rendered(self):
        from src.demo_deliverable_generator import _build_content_from_mss

        mss_result = {
            "magnify": {},
            "solidify": {},
            "simulation": {
                "overall_score": 2.5,
                "risk_level": "moderate",
                "cost_impact": 2.1,
                "complexity_impact": 3.0,
                "compliance_impact": 1.5,
                "performance_impact": 2.0,
                "estimated_engineering_hours": 40.0,
                "regulatory_implications": ["GDPR"],
                "warnings": ["Watch cost"],
            },
        }
        content = _build_content_from_mss("test", mss_result)
        assert "SIMULATION IMPACT ANALYSIS" in content
        assert "moderate" in content
        assert "40" in content
        assert "GDPR" in content


# ═══════════════════════════════════════════════════════════════════════════
# WIRE-MFGC-001 — MFGC quality assurance section rendered
# ═══════════════════════════════════════════════════════════════════════════

class TestWireMFGC001:
    """Verify that _build_content_from_mss includes MFGC QA section."""

    def test_mfgc_qa_section_rendered(self):
        from src.demo_deliverable_generator import _build_content_from_mss

        mss_result = {"magnify": {}, "solidify": {}}
        mfgc_result = {
            "confidence": 0.92,
            "murphy_index": 87,
            "gates": ["gate_001", "gate_002"],
            "phases": ["scope", "analysis", "scoring"],
            "success": True,
            "fallback": False,
        }
        content = _build_content_from_mss("test", mss_result, mfgc_result=mfgc_result)
        assert "QUALITY ASSURANCE" in content
        assert "MFGC" in content
        assert "92%" in content
        assert "87" in content
        assert "gate_001" in content

    def test_mfgc_note_includes_murphy_index(self):
        """_generate_llm_content should build MFGC note with murphy_index
        when MSS data is available."""
        from src.demo_deliverable_generator import _generate_llm_content

        mfgc_result = {
            "confidence": 0.85,
            "phases": ["intake", "analysis"],
            "murphy_index": 73,
            "gates": ["g1", "g2", "g3"],
        }
        mss_result = {
            "magnify": {"functional_requirements": ["req1"]},
            "solidify": {"implementation_steps": ["step1"]},
            "fallback": False,
        }
        # Patch the LLM call to avoid network — we just verify prompt context
        with patch("src.llm_provider.get_llm") as mock_llm:
            mock_provider = MagicMock()
            mock_provider.complete_messages.return_value = MagicMock(content="test output")
            mock_llm.return_value = mock_provider

            _generate_llm_content("test query", mfgc_result=mfgc_result, mss_result=mss_result)

            # Verify the messages passed to complete_messages contain murphy_index
            call_args = mock_provider.complete_messages.call_args
            assert call_args is not None, "complete_messages was never called"
            messages = call_args[0][0] if call_args[0] else call_args[1].get("messages", [])
            user_msg = next((m["content"] for m in messages if m["role"] == "user"), "")
            assert "murphy_index=73" in user_msg, (
                f"murphy_index=73 not found in user prompt"
            )


# ═══════════════════════════════════════════════════════════════════════════
# WIRE-SPEC-001 — Automation spec in streaming pipeline
# ═══════════════════════════════════════════════════════════════════════════

class TestWireSPEC001:
    """Verify that generate_deliverable_with_progress includes automation_spec."""

    @patch("src.demo_deliverable_generator.generate_automation_spec")
    @patch("src.demo_deliverable_generator.generate_deliverable")
    @patch("src.demo_deliverable_generator._run_mss_pipeline")
    @patch("src.demo_deliverable_generator._run_mfgc_gate")
    def test_streaming_pipeline_includes_automation_spec(
        self, mock_mfgc, mock_mss, mock_gen, mock_spec
    ):
        from src.demo_deliverable_generator import generate_deliverable_with_progress

        mock_mfgc.return_value = {"success": True, "fallback": False, "confidence": 0.9, "phases": []}
        mock_mss.return_value = {"fallback": True}
        mock_gen.return_value = {"title": "Test", "content": "Test content here " * 50, "filename": "test.txt"}
        mock_spec.return_value = {"spec_id": "SPEC-TEST", "title": "Test Spec"}

        events = generate_deliverable_with_progress("build automation for invoicing")
        done_event = next(e for e in events if e.get("phase") == "done")

        assert "automation_spec" in done_event
        assert done_event["automation_spec"]["spec_id"] == "SPEC-TEST"


# ═══════════════════════════════════════════════════════════════════════════
# WIRE-EXPERT-001 — Domain expert integration
# ═══════════════════════════════════════════════════════════════════════════

class TestWireEXPERT001:
    """Verify domain expert analysis wrapper and rendering."""

    def test_run_domain_expert_analysis_returns_on_import_error(self):
        from src.demo_deliverable_generator import _run_domain_expert_analysis

        # domain_expert_integration may not be importable — should return fallback
        result = _run_domain_expert_analysis("test query")
        # Either real result or graceful fallback
        assert isinstance(result, dict)
        if result.get("fallback"):
            assert "error" in result

    def test_format_expert_context_empty_on_fallback(self):
        from src.demo_deliverable_generator import _format_expert_context

        assert _format_expert_context({}) == ""
        assert _format_expert_context({"fallback": True, "error": "import error"}) == ""

    def test_format_expert_context_renders_summary(self):
        from src.demo_deliverable_generator import _format_expert_context

        result = {
            "summary": "Build an invoicing automation system",
            "team": "Project Manager\nBackend Developer",
            "time_and_cost": "40 hours, $2,000",
            "questions_we_will_ask": ["What invoicing software?", "Volume?"],
            "artifacts_we_will_create": "API spec\nDeployment guide",
            "fallback": False,
        }
        content = _format_expert_context(result)
        assert "DOMAIN EXPERT ANALYSIS" in content
        assert "invoicing automation" in content
        assert "Project Manager" in content
        assert "What invoicing software?" in content


# ═══════════════════════════════════════════════════════════════════════════
# WIRE-WF-001 — Workflow steps documented as intentional metadata
# ═══════════════════════════════════════════════════════════════════════════

class TestWireWF001:
    """Verify the WIRE-WF-001 documentation label exists in the registry."""

    def test_wire_wf_001_label_in_registry(self):
        registry_path = Path(__file__).resolve().parent.parent.parent / "src" / "production_workflow_registry.py"
        content = registry_path.read_text()
        assert "WIRE-WF-001" in content, "WIRE-WF-001 label must be present in production_workflow_registry.py"
