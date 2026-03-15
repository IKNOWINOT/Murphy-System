"""
Test Suite: Murphy System Storyline Validation

Validates that the Murphy System runtime matches the storyline documented in
docs/MURPHY_SYSTEM_STORYLINE.md.  The storyline is treated as the *expected*
outcome — these tests ensure the actual system can fulfil every chapter of
the story when configured for:

    Account: Inoni LLC
    Goal: Selling the Murphy System

The storyline covers all major subsystems:
  - How bots are used (Chapter 12)
  - The confidence engine and its base math (Chapter 13)
  - The Murphy Index formula (Chapter 14)
  - The deterministic compute plane (Chapter 15)
  - LLM integration & Rosetta state management (Chapter 20)
  - Avatar + streaming coin-join with agent calls (Chapter 21)
  - Shadow agents + org chart enforcement (Chapter 22)
  - Security plane — zero-trust, bot verification, DLP (Chapter 23)
  - Recursive stability controller (Chapter 24)
  - Supervisor system & correction loops (Chapter 25)

Each test class maps to a chapter and verifies that the corresponding module
produces the expected behaviour described in the narrative.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

import json
import os
import re
import sys
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.storyline

# ---------------------------------------------------------------------------
# Path setup — ensure the src/ and project root are importable
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SRC_DIR))

# Optional dependency flags
try:
    import textual  # noqa: F401
    HAS_TEXTUAL = True
except ImportError:
    HAS_TEXTUAL = False

try:
    import matplotlib  # noqa: F401
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False


# ===========================================================================
# Chapter 1 & 2 — Terminal & Onboarding Interview
# ===========================================================================


@pytest.mark.skipif(not HAS_TEXTUAL, reason="textual not installed")
class TestChapter1_FirstEncounter:
    """Chapter 1: A team member at Inoni LLC opens the Murphy terminal."""

    def test_terminal_app_instantiates(self):
        from murphy_terminal import MurphyTerminalApp, WELCOME_TEXT
        app = MurphyTerminalApp(api_url="http://localhost:19999")
        assert app.TITLE == "Murphy System Terminal"
        assert "Murphy" in WELCOME_TEXT

    def test_welcome_mentions_automation(self):
        from murphy_terminal import WELCOME_TEXT
        assert "automation" in WELCOME_TEXT.lower()

    def test_start_interview_intent_recognised(self):
        from murphy_terminal import detect_intent
        assert detect_intent("start interview") == "intent_start_interview"


@pytest.mark.skipif(not HAS_TEXTUAL, reason="textual not installed")
class TestChapter2_OnboardingInterview:
    """Chapter 2: The 7-step onboarding interview configured for Inoni LLC."""

    def test_interview_has_seven_steps(self):
        from murphy_terminal import DialogContext
        assert len(DialogContext.INTERVIEW_STEPS) == 7

    def test_business_goal_before_technical_details(self):
        from murphy_terminal import DialogContext
        keys = [s["key"] for s in DialogContext.INTERVIEW_STEPS]
        assert keys.index("business_goal") < keys.index("billing_tier")

    def test_full_inoni_interview(self):
        """Run the full interview with Inoni LLC answers and verify collection."""
        from murphy_terminal import DialogContext

        ctx = DialogContext()
        ctx.start()

        answers = [
            "Inoni LLC",              # name
            "sell the Murphy System", # business_goal
            "sales automation",       # use_case
            "email and CRM",          # platforms
            "pro",                    # billing_tier
            "auto",                   # integrations  → "(auto-configure)"
            "yes",                    # confirm
        ]
        for ans in answers:
            ctx.advance(ans)

        assert ctx.is_complete is True
        assert ctx.collected["name"] == "Inoni LLC"
        assert ctx.collected["business_goal"] == "sell the Murphy System"
        assert ctx.collected["use_case"] == "sales automation"
        assert ctx.collected["platforms"] == "email and CRM"
        assert ctx.collected["integrations"] == "(auto-configure)"

    def test_infer_auto_configure(self):
        from murphy_terminal import DialogContext
        assert DialogContext._infer_value("integrations", "auto") == "(auto-configure)"
        assert DialogContext._infer_value("integrations", "let murphy decide") == "(auto-configure)"


# ===========================================================================
# Chapter 3 — Setup Wizard (Inoni LLC config)
# ===========================================================================


class TestChapter3_SetupWizard:
    """Chapter 3: The Setup Wizard configures Murphy for Inoni LLC selling Murphy."""

    def _build_inoni_wizard(self):
        from src.setup_wizard import SetupWizard
        wizard = SetupWizard()
        wizard.apply_answer("q1", "Inoni LLC")
        wizard.apply_answer("q2", "technology")
        wizard.apply_answer("q3", "small")
        wizard.apply_answer("q4", ["business", "agent"])
        wizard.apply_answer("q5", "standard")
        wizard.apply_answer("q6", False)       # no robotics
        wizard.apply_answer("q7", [])           # no robotics protocols
        wizard.apply_answer("q8", False)        # no avatar
        wizard.apply_answer("q9", "local")
        wizard.apply_answer("q10", [])          # no compliance frameworks
        wizard.apply_answer("q11", "local")
        wizard.apply_answer("q12", True)        # sales automation ENABLED
        return wizard

    def test_wizard_produces_valid_config(self):
        wizard = self._build_inoni_wizard()
        config = wizard.generate_config(wizard.get_profile())
        assert config["organization"]["name"] == "Inoni LLC"
        assert config["organization"]["industry"] == "technology"
        assert config["sales_automation"]["enabled"] is True

    def test_wizard_activates_core_modules(self):
        from src.setup_wizard import CORE_MODULES
        wizard = self._build_inoni_wizard()
        config = wizard.generate_config(wizard.get_profile())
        for mod in CORE_MODULES:
            assert mod in config["modules"], f"Core module '{mod}' missing"

    def test_wizard_activates_sales_modules(self):
        from src.setup_wizard import SALES_MODULES
        wizard = self._build_inoni_wizard()
        config = wizard.generate_config(wizard.get_profile())
        for mod in SALES_MODULES:
            assert mod in config["modules"], f"Sales module '{mod}' missing"

    def test_wizard_recommends_sales_bots(self):
        from src.setup_wizard import SALES_BOTS
        wizard = self._build_inoni_wizard()
        config = wizard.generate_config(wizard.get_profile())
        for bot in SALES_BOTS:
            assert bot in config["bots"], f"Sales bot '{bot}' missing"

    def test_wizard_recommends_tech_industry_bots(self):
        wizard = self._build_inoni_wizard()
        config = wizard.generate_config(wizard.get_profile())
        # Technology industry bots per INDUSTRY_BOT_MAP
        assert "devops_bot" in config["bots"]
        assert "code_review_bot" in config["bots"]
        assert "incident_response_bot" in config["bots"]

    def test_wizard_activates_business_automation_modules(self):
        """Business automation type → trading_bot_engine, executive_planning_engine, etc."""
        from src.setup_wizard import AUTOMATION_MODULE_MAP
        wizard = self._build_inoni_wizard()
        config = wizard.generate_config(wizard.get_profile())
        for mod in AUTOMATION_MODULE_MAP["business"]:
            assert mod in config["modules"], f"Business module '{mod}' missing"

    def test_wizard_activates_agent_automation_modules(self):
        """Agent automation type → agentic_api_provisioner, swarm systems, etc."""
        from src.setup_wizard import AUTOMATION_MODULE_MAP
        wizard = self._build_inoni_wizard()
        config = wizard.generate_config(wizard.get_profile())
        for mod in AUTOMATION_MODULE_MAP["agent"]:
            assert mod in config["modules"], f"Agent module '{mod}' missing"


# ===========================================================================
# Chapter 5 & 6 — Sales Automation (the "first automation" for Inoni LLC)
# ===========================================================================


class TestChapter5_6_SalesAutomation:
    """Chapters 5-6: Inoni LLC's sales pipeline as the first automation."""

    def test_sales_config_defaults_to_inoni(self):
        from src.sales_automation import SalesAutomationConfig
        config = SalesAutomationConfig()
        assert config.company_name == "Inoni LLC"
        assert config.product_name == "Murphy System"

    def test_sales_engine_creates_with_defaults(self):
        from src.sales_automation import SalesAutomationEngine
        engine = SalesAutomationEngine()
        assert engine.config.company_name == "Inoni LLC"
        assert engine.config.product_name == "Murphy System"

    def test_register_and_score_lead(self):
        """LeadScorer agent equivalent: score based on size, industry, interests."""
        from src.sales_automation import SalesAutomationEngine, LeadProfile
        engine = SalesAutomationEngine()

        lead = LeadProfile(
            company_name="TechCorp",
            contact_name="Alice",
            contact_email="alice@techcorp.com",
            industry="technology",
            company_size="enterprise",
            interests=["CI/CD automation", "agent swarms"],
        )
        engine.register_lead(lead)
        score = engine.score_lead(lead)

        # enterprise=50, technology is target=+20, 2 interests=+10 → 80
        assert score == 80
        assert lead.score == 80

    def test_qualify_lead_above_threshold(self):
        """LeadQualifier agent: score ≥ 40 → qualified."""
        from src.sales_automation import SalesAutomationEngine, LeadProfile
        engine = SalesAutomationEngine()

        lead = LeadProfile(
            company_name="BigCo",
            contact_name="Bob",
            contact_email="bob@bigco.com",
            industry="technology",
            company_size="medium",
            interests=["code generation"],
        )
        result = engine.qualify_lead(lead)
        # medium=30 + technology=20 + 1 interest=5 → 55 → qualified
        assert result["qualified"] is True
        assert result["score"] == 55
        assert lead.status == "qualified"

    def test_qualify_lead_below_threshold(self):
        """Score 30-39 → borderline tier (Tuning #2), needs interest discovery."""
        from src.sales_automation import SalesAutomationEngine, LeadProfile
        engine = SalesAutomationEngine()

        lead = LeadProfile(
            company_name="TinyStartup",
            contact_name="Carol",
            contact_email="carol@tiny.io",
            industry="retail",       # target industry
            company_size="small",    # small=10
            interests=[],
        )
        result = engine.qualify_lead(lead)
        # small=10 + retail=20 + 0 interests → 30 → borderline (Tuning #2)
        assert result["qualified"] is False
        assert result["score"] == 30
        assert result["tier"] == "borderline"
        assert "interest discovery" in result["recommended_action"].lower()

    def test_recommend_edition_by_size(self):
        """EditionRecommender agent: enterprise→enterprise, medium→professional, small→community."""
        from src.sales_automation import SalesAutomationEngine, LeadProfile
        engine = SalesAutomationEngine()

        for size, expected in [("enterprise", "enterprise"), ("medium", "professional"), ("small", "community")]:
            lead = LeadProfile(
                company_name=f"{size}Co",
                contact_name="Test",
                contact_email="test@example.com",
                industry="technology",
                company_size=size,
            )
            assert engine.recommend_edition(lead) == expected

    def test_generate_demo_script(self):
        """DemoScriptGenerator agent: personalized demo with industry features."""
        from src.sales_automation import SalesAutomationEngine, LeadProfile
        engine = SalesAutomationEngine()

        lead = LeadProfile(
            company_name="MfgCorp",
            contact_name="Diana",
            contact_email="diana@mfg.com",
            industry="manufacturing",
            company_size="enterprise",
        )
        script = engine.generate_demo_script(lead)
        assert "Diana" in script["greeting"]
        assert "MfgCorp" in script["greeting"]
        assert "Murphy System" in script["greeting"]
        assert "manufacturing" in script["greeting"]
        assert len(script["demo_steps"]) == 4
        assert "robotics integration" in script["feature_highlights"]

    def test_generate_proposal(self):
        """ProposalGenerator agent: complete sales proposal."""
        from src.sales_automation import SalesAutomationEngine, LeadProfile
        engine = SalesAutomationEngine()

        lead = LeadProfile(
            company_name="FinServ Inc",
            contact_name="Eve",
            contact_email="eve@finserv.com",
            industry="finance",
            company_size="enterprise",
            interests=["compliance monitoring", "audit trails"],
        )
        proposal = engine.generate_proposal(lead)
        assert "FinServ Inc" in proposal["executive_summary"]
        assert "Murphy System" in proposal["executive_summary"]
        assert proposal["recommended_edition"] == "enterprise"
        assert "compliance monitoring" in proposal["features_included"]
        assert len(proposal["implementation_plan"]) == 4
        assert proposal["timeline"] == "4-8 weeks"

    def test_advance_lead_through_pipeline(self):
        """Lead lifecycle: new → qualified → demo_scheduled → proposal_sent → closed_won."""
        from src.sales_automation import SalesAutomationEngine, LeadProfile
        engine = SalesAutomationEngine()

        lead = LeadProfile(
            company_name="WinCo",
            contact_name="Frank",
            contact_email="frank@win.co",
            industry="technology",
            company_size="enterprise",
        )
        lid = engine.register_lead(lead)
        assert lead.status == "new"

        engine.qualify_lead(lead)
        assert lead.status == "qualified"

        assert engine.advance_lead(lid, "demo_scheduled") is True
        assert lead.status == "demo_scheduled"

        assert engine.advance_lead(lid, "proposal_sent") is True
        assert lead.status == "proposal_sent"

        assert engine.advance_lead(lid, "closed_won") is True
        assert lead.status == "closed_won"

    def test_pipeline_summary(self):
        """Pipeline summary groups leads by status."""
        from src.sales_automation import SalesAutomationEngine, LeadProfile
        engine = SalesAutomationEngine()

        for i in range(3):
            lead = LeadProfile(
                company_name=f"Co{i}",
                contact_name=f"Person{i}",
                contact_email=f"p{i}@co.com",
                industry="technology",
                company_size="medium",
            )
            engine.register_lead(lead)

        summary = engine.get_pipeline_summary()
        assert summary["total_leads"] == 3
        assert len(summary["by_status"]["new"]) == 3


# ===========================================================================
# Chapter 7 — Domain Gates
# ===========================================================================


class TestChapter7_DomainGates:
    """Chapter 7: Domain gate generation for the Inoni LLC sales pipeline."""

    def test_gate_types_cover_storyline_categories(self):
        """Gates include VALIDATION, COMPLIANCE, BUSINESS, AUTHORIZATION per storyline."""
        from src.domain_gate_generator import GateType
        assert hasattr(GateType, "VALIDATION")
        assert hasattr(GateType, "COMPLIANCE")
        assert hasattr(GateType, "BUSINESS")
        assert hasattr(GateType, "AUTHORIZATION")

    def test_gate_severity_levels(self):
        from src.domain_gate_generator import GateSeverity
        assert hasattr(GateSeverity, "CRITICAL")
        assert hasattr(GateSeverity, "HIGH")
        assert hasattr(GateSeverity, "MEDIUM")

    def test_generate_gate_with_conditions(self):
        from src.domain_gate_generator import (
            DomainGateGenerator, GateType, GateSeverity,
        )
        gen = DomainGateGenerator()
        gate = gen.generate_gate(
            name="Lead Data Validation",
            description="Validates lead data before scoring",
            gate_type=GateType.VALIDATION,
            severity=GateSeverity.HIGH,
        )
        assert gate.name == "Lead Data Validation"
        assert gate.gate_type == GateType.VALIDATION
        assert gate.severity == GateSeverity.HIGH
        assert gate.gate_id is not None

    def test_generate_gates_for_system(self):
        """System-wide gate generation returns gates list and metadata."""
        from src.domain_gate_generator import DomainGateGenerator
        gen = DomainGateGenerator()
        gates, metadata = gen.generate_gates_for_system(
            {"domain": "sales", "complexity": "medium"}
        )
        assert isinstance(gates, list)
        assert isinstance(metadata, dict)
        assert "total_gates" in metadata

    def test_gate_has_pass_and_fail_actions(self):
        from src.domain_gate_generator import DomainGateGenerator, GateType
        gen = DomainGateGenerator()
        gate = gen.generate_gate(
            name="Compliance Gate",
            description="Checks CAN-SPAM compliance",
            gate_type=GateType.COMPLIANCE,
        )
        assert isinstance(gate.pass_actions, list)
        assert isinstance(gate.fail_actions, list)

    def test_gate_has_risk_reduction_score(self):
        from src.domain_gate_generator import DomainGateGenerator
        gen = DomainGateGenerator()
        gate = gen.generate_gate(
            name="Budget Gate",
            description="Checks budget",
            risk_reduction=0.7,
        )
        assert gate.risk_reduction == 0.7


# ===========================================================================
# Chapter 9 — Phase Thresholds (MurphyGate)
# ===========================================================================


class TestChapter9_PhaseExecution:
    """Chapter 9: The 7-phase execution pipeline with confidence gating."""

    def test_murphy_gate_phase_thresholds(self):
        """Phase thresholds: EXPAND=0.5 rising to EXECUTE=0.85."""
        from src.confidence_engine.murphy_gate import MurphyGate

        gate = MurphyGate()
        # phase_thresholds uses Phase enum keys; verify the values are present
        threshold_values = list(gate.phase_thresholds.values())
        assert 0.5 in threshold_values   # EXPAND
        assert 0.85 in threshold_values  # EXECUTE

    def test_murphy_gate_evaluate_pass(self):
        """High confidence passes the gate."""
        from src.confidence_engine.murphy_gate import MurphyGate

        gate = MurphyGate()
        result = gate.evaluate(confidence=0.95)
        assert result.allowed is True

    def test_murphy_gate_evaluate_block(self):
        """Very low confidence blocks execution."""
        from src.confidence_engine.murphy_gate import MurphyGate

        gate = MurphyGate()
        result = gate.evaluate(confidence=0.1)
        assert result.allowed is False


# ===========================================================================
# Chapter 12 — Bot System
# ===========================================================================


class TestChapter12_BotSystem:
    """Chapter 12: How bots do the work — base classes and plugin loading."""

    @pytest.mark.skipif(not HAS_MATPLOTLIB, reason="matplotlib not installed")
    def test_async_bot_base_exists(self):
        from bots.bot_base import AsyncBot
        assert hasattr(AsyncBot, "handle")

    @pytest.mark.skipif(not HAS_MATPLOTLIB, reason="matplotlib not installed")
    def test_hive_bot_base_exists(self):
        from bots.bot_base import HiveBot
        assert hasattr(HiveBot, "init")
        assert hasattr(HiveBot, "register_handlers")

    @pytest.mark.skipif(not HAS_MATPLOTLIB, reason="matplotlib not installed")
    def test_message_dataclass(self):
        from bots.bot_base import Message
        msg = Message(sender="test_user", content="hello")
        assert msg.sender == "test_user"
        assert msg.content == "hello"

    def test_sales_bots_exist_in_setup_wizard(self):
        """Setup wizard defines SALES_BOTS for Inoni LLC config."""
        from src.setup_wizard import SALES_BOTS
        assert "sales_outreach_bot" in SALES_BOTS
        assert "lead_scoring_bot" in SALES_BOTS
        assert "marketing_automation_bot" in SALES_BOTS


# ===========================================================================
# Chapter 13 — Confidence Engine Math
# ===========================================================================


class TestChapter13_ConfidenceEngine:
    """Chapter 13: The confidence equation c_t = w_g×G + w_d×D."""

    def test_confidence_calculator_exists(self):
        from src.confidence_engine.confidence_calculator import ConfidenceCalculator
        calc = ConfidenceCalculator()
        assert hasattr(calc, "compute_confidence")

    def test_confidence_has_generative_adequacy(self):
        from src.confidence_engine.confidence_calculator import ConfidenceCalculator
        calc = ConfidenceCalculator()
        assert hasattr(calc, "calculate_generative_adequacy")

    def test_confidence_has_deterministic_grounding(self):
        from src.confidence_engine.confidence_calculator import ConfidenceCalculator
        calc = ConfidenceCalculator()
        assert hasattr(calc, "calculate_deterministic_grounding")

    def test_confidence_has_epistemic_instability(self):
        from src.confidence_engine.confidence_calculator import ConfidenceCalculator
        calc = ConfidenceCalculator()
        assert hasattr(calc, "calculate_epistemic_instability")


# ===========================================================================
# Chapter 14 — Murphy Index
# ===========================================================================


class TestChapter14_MurphyIndex:
    """Chapter 14: The Murphy Index M_t = Σ(L_k × p_k)."""

    def test_murphy_calculator_exists(self):
        from src.confidence_engine.murphy_calculator import MurphyCalculator
        calc = MurphyCalculator()
        assert hasattr(calc, "calculate_murphy_index")

    def test_murphy_calculator_sigmoid_weights(self):
        """Verify the sigmoid weights match the storyline specification."""
        from src.confidence_engine.murphy_calculator import MurphyCalculator
        calc = MurphyCalculator()
        assert calc.alpha == 2.0   # epistemic instability
        assert calc.beta == 1.5    # lack of grounding
        assert calc.gamma == 1.0   # exposure
        assert calc.delta == 1.2   # authority risk


# ===========================================================================
# Chapter 15 — Deterministic Compute Plane
# ===========================================================================


class TestChapter15_DeterministicCompute:
    """Chapter 15: The deterministic routing engine and its policies."""

    def test_routing_engine_exists(self):
        from src.deterministic_routing_engine import DeterministicRoutingEngine
        engine = DeterministicRoutingEngine()
        assert hasattr(engine, "route_task")
        assert hasattr(engine, "evaluate_guardrails")

    def test_routing_engine_has_policies(self):
        from src.deterministic_routing_engine import DeterministicRoutingEngine
        engine = DeterministicRoutingEngine()
        policies = engine.list_policies() if hasattr(engine, "list_policies") else engine._policies
        assert len(policies) > 0, "Engine should have default policies"

    def test_routing_policy_dataclass(self):
        from src.deterministic_routing_engine import RoutingPolicy
        policy = RoutingPolicy(
            policy_id="test-001",
            name="Test Policy",
            task_tags=["math"],
            route_type="deterministic",
        )
        assert policy.route_type == "deterministic"
        assert "math" in policy.task_tags

    def test_routing_decision_dataclass(self):
        from src.deterministic_routing_engine import RoutingDecision
        decision = RoutingDecision(
            decision_id="d-001",
            task_type="scoring",
            matched_policy="math_policy",
            route_type="deterministic",
            confidence=0.95,
            reason="Math task",
            guardrails_applied=["output_validation"],
            timestamp="2024-01-01T00:00:00Z",
        )
        assert decision.route_type == "deterministic"
        assert decision.confidence == 0.95


# ===========================================================================
# Chapter 10 — Safety Net
# ===========================================================================


class TestChapter10_SafetyNet:
    """Chapter 10: Safety systems — emergency stop, governance kernel."""

    def test_emergency_stop_controller_exists(self):
        from src.emergency_stop_controller import EmergencyStopController
        ctrl = EmergencyStopController()
        assert hasattr(ctrl, "activate_global") or hasattr(ctrl, "activate")
        assert hasattr(ctrl, "is_stopped") or hasattr(ctrl, "check")

    def test_governance_kernel_exists(self):
        from src.governance_kernel import GovernanceKernel
        kernel = GovernanceKernel()
        assert hasattr(kernel, "enforce") or hasattr(kernel, "evaluate")


# ===========================================================================
# Chapter 16 — Learning Engine
# ===========================================================================


class TestChapter16_LearningEngine:
    """Chapter 16: Murphy learns from execution."""

    def test_learning_engine_exists(self):
        from src.learning_engine.learning_engine import PerformanceTracker
        tracker = PerformanceTracker()
        assert hasattr(tracker, "record_metric") or hasattr(tracker, "record") or hasattr(tracker, "add_metric")

    def test_feedback_system_exists(self):
        from src.learning_engine.feedback_system import HumanFeedbackSystem
        fs = HumanFeedbackSystem()
        assert hasattr(fs, "collect_feedback") or hasattr(fs, "submit_feedback")

    def test_adaptive_decision_engine_exists(self):
        from src.learning_engine.adaptive_decision_engine import AdaptiveDecisionEngine
        engine = AdaptiveDecisionEngine()
        assert hasattr(engine, "decide") or hasattr(engine, "make_decision")


# ===========================================================================
# Chapter 4 — System Bootstrap
# ===========================================================================


class TestChapter4_Bootstrap:
    """Chapter 4: System bootstraps with KPI baselines and readiness checks."""

    def test_readiness_bootstrap_exists(self):
        from src.readiness_bootstrap_orchestrator import ReadinessBootstrapOrchestrator
        orch = ReadinessBootstrapOrchestrator()
        assert orch is not None

    def test_capability_map_exists(self):
        from src.capability_map import CapabilityMap
        cm = CapabilityMap()
        assert hasattr(cm, "scan") or hasattr(cm, "get_capabilities")


# ===========================================================================
# Storyline Document Structural Validation
# ===========================================================================


class TestStorylineDocumentStructure:
    """Validate the MURPHY_SYSTEM_STORYLINE.md document itself is correct."""

    @pytest.fixture
    def storyline_text(self):
        doc_path = PROJECT_ROOT / "docs" / "MURPHY_SYSTEM_STORYLINE.md"
        return doc_path.read_text(encoding="utf-8")

    def test_storyline_exists(self, storyline_text):
        assert len(storyline_text) > 1000

    def test_storyline_uses_inoni_llc(self, storyline_text):
        """The story should be about Inoni LLC, not a generic user."""
        assert "Inoni LLC" in storyline_text

    def test_storyline_goal_is_selling_murphy(self, storyline_text):
        """The business goal should be selling the Murphy System."""
        assert "sell" in storyline_text.lower() and "Murphy System" in storyline_text

    def test_storyline_has_25_chapters(self, storyline_text):
        """25 chapters covering all subsystems."""
        chapters = re.findall(r"^## Chapter \d+:", storyline_text, re.MULTILINE)
        assert len(chapters) == 25, f"Expected 25 chapters, found {len(chapters)}: {chapters}"

    def test_storyline_covers_bots(self, storyline_text):
        """Chapter 12 should explain how bots work."""
        assert "How Bots Do the Work" in storyline_text
        assert "AsyncBot" in storyline_text
        assert "HiveBot" in storyline_text

    def test_storyline_covers_confidence_math(self, storyline_text):
        """Chapter 13 should explain the confidence equation."""
        assert "Confidence Engine" in storyline_text
        assert "c_t = w_g" in storyline_text
        assert "G(x)" in storyline_text
        assert "D(x)" in storyline_text

    def test_storyline_covers_murphy_index(self, storyline_text):
        """Chapter 14 should explain the Murphy Index formula."""
        assert "Murphy Index" in storyline_text
        assert "M_t = " in storyline_text or "M_t =" in storyline_text
        assert "sigmoid" in storyline_text.lower()

    def test_storyline_covers_deterministic(self, storyline_text):
        """Chapter 15 should explain deterministic vs LLM routing."""
        assert "Deterministic" in storyline_text
        assert "DeterministicRoutingEngine" in storyline_text
        assert "RoutingPolicy" in storyline_text

    def test_storyline_has_prologue_and_epilogue(self, storyline_text):
        assert "Prologue" in storyline_text
        assert "Epilogue" in storyline_text

    def test_storyline_has_appendix(self, storyline_text):
        assert "Appendix: Module-to-Story Mapping" in storyline_text

    def test_storyline_sales_automation_in_appendix(self, storyline_text):
        """Appendix should reference sales automation modules."""
        assert "SalesAutomationEngine" in storyline_text
        assert "sales_automation.py" in storyline_text

    def test_storyline_lead_scoring_formula(self, storyline_text):
        """Storyline should explain lead scoring math: size + industry + interests."""
        assert "score" in storyline_text.lower()
        assert "small=10" in storyline_text or "small = 10" in storyline_text

    def test_storyline_chapter_order(self, storyline_text):
        """Chapters should be in sequential order 1-25."""
        chapter_nums = [
            int(m.group(1))
            for m in re.finditer(r"^## Chapter (\d+):", storyline_text, re.MULTILINE)
        ]
        assert chapter_nums == list(range(1, 26))


# ===========================================================================
# End-to-End: Inoni LLC storyline flow validation
# ===========================================================================


class TestInoniLLCEndToEnd:
    """Validates the complete Inoni LLC storyline flow:
    Interview → Setup → Sales Automation → Gate Generation → Results.
    """

    @pytest.mark.skipif(not HAS_TEXTUAL, reason="textual not installed")
    def test_full_flow_interview_to_config(self):
        """Steps 1-3: Interview → Wizard → Config for Inoni LLC."""
        from murphy_terminal import DialogContext
        from src.setup_wizard import SetupWizard

        # Chapter 2: Interview
        ctx = DialogContext()
        ctx.start()
        for ans in ["Inoni LLC", "sell the Murphy System", "sales automation",
                     "email and CRM", "pro", "auto", "yes"]:
            ctx.advance(ans)
        assert ctx.is_complete is True

        # Chapter 3: Wizard
        wizard = SetupWizard()
        wizard.apply_answer("q1", ctx.collected["name"])
        wizard.apply_answer("q2", "technology")
        wizard.apply_answer("q3", "small")
        wizard.apply_answer("q4", ["business", "agent"])
        wizard.apply_answer("q5", "standard")
        wizard.apply_answer("q6", False)
        wizard.apply_answer("q7", [])
        wizard.apply_answer("q8", False)
        wizard.apply_answer("q9", "local")
        wizard.apply_answer("q10", [])
        wizard.apply_answer("q11", "local")
        wizard.apply_answer("q12", True)

        config = wizard.generate_config(wizard.get_profile())
        assert config["organization"]["name"] == "Inoni LLC"
        assert config["sales_automation"]["enabled"] is True
        assert "workflow_template_marketplace" in config["modules"]
        assert "sales_outreach_bot" in config["bots"]

    def test_full_flow_config_to_sales_pipeline(self):
        """Steps 5-6: Config → Sales Automation → Lead Pipeline."""
        from src.sales_automation import SalesAutomationEngine, SalesAutomationConfig, LeadProfile

        # Sales engine configured for Inoni LLC
        config = SalesAutomationConfig(
            company_name="Inoni LLC",
            product_name="Murphy System",
        )
        engine = SalesAutomationEngine(config=config)

        # Simulate 3 leads through pipeline
        leads = [
            LeadProfile(
                company_name="EnterpriseCo",
                contact_name="Alice",
                contact_email="alice@enterprise.com",
                industry="technology",
                company_size="enterprise",
                interests=["CI/CD automation", "agent swarms", "API integration"],
            ),
            LeadProfile(
                company_name="MidMarket Inc",
                contact_name="Bob",
                contact_email="bob@midmarket.com",
                industry="finance",
                company_size="medium",
                interests=["compliance monitoring"],
            ),
            LeadProfile(
                company_name="SmallShop",
                contact_name="Carol",
                contact_email="carol@small.io",
                industry="other",
                company_size="small",
                interests=[],
            ),
        ]

        results = []
        for lead in leads:
            engine.register_lead(lead)
            qual = engine.qualify_lead(lead)
            results.append(qual)

        # Enterprise: 50+20+15=85 → qualified
        assert results[0]["qualified"] is True
        assert results[0]["score"] == 85
        # Medium finance: 30+20+5=55 → qualified
        assert results[1]["qualified"] is True
        # Small other: 10+0+0=10 → not qualified
        assert results[2]["qualified"] is False

        # Generate proposals for qualified leads
        for lead, qual in zip(leads, results):
            if qual["qualified"]:
                proposal = engine.generate_proposal(lead)
                assert "Murphy System" in proposal["executive_summary"]
                assert proposal["recommended_edition"] in ["enterprise", "professional", "community"]

        summary = engine.get_pipeline_summary()
        assert summary["total_leads"] == 3
        assert len(summary["by_status"]["qualified"]) == 2

    def test_full_flow_gates_for_sales(self):
        """Chapter 7: Generate domain gates for the sales automation."""
        from src.domain_gate_generator import DomainGateGenerator, GateType, GateSeverity

        gen = DomainGateGenerator()

        # Generate gates for sales domain
        gates, metadata = gen.generate_gates_for_system(
            {"domain": "sales", "complexity": "medium"}
        )
        assert isinstance(gates, list)
        assert isinstance(metadata, dict)

        # Also generate specific gates matching storyline
        validation_gate = gen.generate_gate(
            name="Lead Data Validation",
            description="Validates lead has email, company name, and recognized industry",
            gate_type=GateType.VALIDATION,
            severity=GateSeverity.HIGH,
            risk_reduction=0.6,
        )
        compliance_gate = gen.generate_gate(
            name="CAN-SPAM Compliance",
            description="Ensures outreach complies with CAN-SPAM and GDPR",
            gate_type=GateType.COMPLIANCE,
            severity=GateSeverity.CRITICAL,
            risk_reduction=0.9,
        )
        assert validation_gate.severity == GateSeverity.HIGH
        assert compliance_gate.severity == GateSeverity.CRITICAL
        assert compliance_gate.risk_reduction == 0.9


# ===========================================================================
# Chapter 20 — LLM Integration & Rosetta State Management
# ===========================================================================


class TestChapter20_LLMAndRosetta:
    """Chapter 20: LLM dual-write (user-facing + internal Rosetta) and state management."""

    def test_llm_integration_layer_exists(self):
        from src.llm_integration_layer import LLMIntegrationLayer
        layer = LLMIntegrationLayer()
        assert hasattr(layer, "route_request")
        assert hasattr(layer, "domain_routing")

    def test_safe_llm_wrapper_exists(self):
        from src.safe_llm_wrapper import SafeLLMWrapper
        wrapper = SafeLLMWrapper()
        assert hasattr(wrapper, "safe_generate")
        assert hasattr(wrapper, "verify_against_sources")

    def test_rosetta_manager_state_ops(self):
        from src.rosetta.rosetta_manager import RosettaManager
        mgr = RosettaManager()
        assert hasattr(mgr, "save_state")
        assert hasattr(mgr, "load_state")
        assert hasattr(mgr, "update_state")
        assert hasattr(mgr, "list_agents")

    def test_rosetta_archive_classifier(self):
        from src.rosetta.archive_classifier import ArchiveClassifier
        assert hasattr(ArchiveClassifier, "classify")
        assert hasattr(ArchiveClassifier, "archive_item")

    def test_rosetta_heartbeat_exists(self):
        from src.rosetta_stone_heartbeat import RosettaStoneHeartbeat
        hb = RosettaStoneHeartbeat()
        assert hasattr(hb, "emit_pulse")
        assert hasattr(hb, "sync_check")
        assert hasattr(hb, "register_translator")

    def test_rosetta_recalibration_scheduler(self):
        from src.rosetta.recalibration_scheduler import RecalibrationScheduler
        from src.rosetta.rosetta_manager import RosettaManager
        mgr = RosettaManager()
        sched = RecalibrationScheduler(manager=mgr)
        assert hasattr(sched, "run_recalibration")
        assert hasattr(sched, "get_status")


# ===========================================================================
# Chapter 21 — Avatar + Streaming
# ===========================================================================


class TestChapter21_AvatarStreaming:
    """Chapter 21: Avatar sessions coin-join with agent calls via streaming."""

    def test_avatar_session_manager_exists(self):
        from src.avatar.avatar_session_manager import AvatarSessionManager
        mgr = AvatarSessionManager()
        assert hasattr(mgr, "start_session")
        assert hasattr(mgr, "end_session")
        assert hasattr(mgr, "record_message")

    def test_avatar_persona_injector(self):
        from src.avatar.persona_injector import PersonaInjector
        assert PersonaInjector is not None

    def test_avatar_sentiment_classifier(self):
        from src.avatar.sentiment_classifier import SentimentClassifier
        assert SentimentClassifier is not None

    def test_video_streaming_registry(self):
        from src.video_streaming_connector import VideoStreamingRegistry
        assert hasattr(VideoStreamingRegistry, "create_simulcast")
        assert hasattr(VideoStreamingRegistry, "list_platforms")


# ===========================================================================
# Chapter 22 — Shadow Agents & Org Chart
# ===========================================================================


class TestChapter22_ShadowAgentsOrgChart:
    """Chapter 22: Shadow agents bind to org chart roles and learn passively."""

    def test_shadow_agent_integration_exists(self):
        from src.shadow_agent_integration import ShadowAgentIntegration
        sai = ShadowAgentIntegration()
        assert hasattr(sai, "create_shadow_agent")
        assert hasattr(sai, "bind_shadow_to_role")
        assert hasattr(sai, "get_shadows_for_org")

    def test_shadow_governance_boundary(self):
        from src.shadow_agent_integration import ShadowAgentIntegration
        sai = ShadowAgentIntegration()
        assert hasattr(sai, "get_shadow_governance_boundary")
        assert hasattr(sai, "suspend_shadow")
        assert hasattr(sai, "revoke_shadow")

    def test_org_compiler_role_template(self):
        from src.org_compiler.compiler import RoleTemplateCompiler
        assert hasattr(RoleTemplateCompiler, "compile_role_template")
        assert hasattr(RoleTemplateCompiler, "add_org_chart")

    def test_org_chart_enforcement_exists(self):
        from src.org_chart_enforcement import OrgChartEnforcement
        assert OrgChartEnforcement is not None

    def test_shadow_learning_module(self):
        from src.org_compiler.shadow_learning import ShadowLearningAgent
        assert ShadowLearningAgent is not None


# ===========================================================================
# Chapter 23 — Security Plane
# ===========================================================================


class TestChapter23_SecurityPlane:
    """Chapter 23: Zero-trust access control, bot verification, and DLP."""

    def test_zero_trust_access_controller(self):
        from src.security_plane.access_control import ZeroTrustAccessController
        assert ZeroTrustAccessController is not None

    def test_bot_identity_verifier(self):
        from src.security_plane.bot_identity_verifier import BotIdentityVerifier
        assert BotIdentityVerifier is not None

    def test_bot_anomaly_detector(self):
        from src.security_plane.bot_anomaly_detector import BotAnomalyDetector
        assert BotAnomalyDetector is not None

    def test_data_leak_prevention(self):
        from src.security_plane.data_leak_prevention import DataLeakPreventionSystem
        assert DataLeakPreventionSystem is not None

    def test_packet_protection(self):
        from src.security_plane.packet_protection import PacketProtectionSystem
        assert PacketProtectionSystem is not None


# ===========================================================================
# Chapter 24 — Recursive Stability Controller
# ===========================================================================


class TestChapter24_RecursiveStabilityController:
    """Chapter 24: Lyapunov-based stability monitoring and gate damping."""

    def test_lyapunov_monitor_exists(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "lyapunov_monitor",
            str(SRC_DIR / "recursive_stability_controller" / "lyapunov_monitor.py"),
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert hasattr(mod, "LyapunovMonitor")

    def test_gate_damping_exists(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "gate_damping",
            str(SRC_DIR / "recursive_stability_controller" / "gate_damping.py"),
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert hasattr(mod, "GateDampingController")

    def test_spawn_controller_exists(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "spawn_controller",
            str(SRC_DIR / "recursive_stability_controller" / "spawn_controller.py"),
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert hasattr(mod, "SpawnRateController")

    def test_stability_score_exists(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "stability_score",
            str(SRC_DIR / "recursive_stability_controller" / "stability_score.py"),
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert hasattr(mod, "StabilityScoreCalculator")


# ===========================================================================
# Chapter 25 — Supervisor System & Correction Loops
# ===========================================================================


class TestChapter25_SupervisorSystem:
    """Chapter 25: Supervisor assumption management and correction loops."""

    def test_supervisor_interface_exists(self):
        from src.supervisor_system.supervisor_loop import SupervisorInterface
        assert hasattr(SupervisorInterface, "submit_feedback")
        assert hasattr(SupervisorInterface, "process_feedback")

    def test_assumption_management(self):
        from src.supervisor_system.assumption_management import AssumptionRegistry
        assert AssumptionRegistry is not None

    def test_correction_loop(self):
        from src.supervisor_system.correction_loop import InvalidationDetector
        assert InvalidationDetector is not None

    def test_anti_recursion_exists(self):
        from src.supervisor_system.anti_recursion import AntiRecursionSystem
        assert AntiRecursionSystem is not None


# ===========================================================================
# New Storyline Chapter Structural Tests
# ===========================================================================


class TestNewStorylineChapters:
    """Validate the new chapters exist and mention key modules."""

    @pytest.fixture
    def storyline_text(self):
        doc_path = PROJECT_ROOT / "docs" / "MURPHY_SYSTEM_STORYLINE.md"
        return doc_path.read_text(encoding="utf-8")

    def test_storyline_covers_llm_rosetta(self, storyline_text):
        """Chapter 20 should explain LLM dual-write and Rosetta state."""
        assert "LLM" in storyline_text
        assert "Rosetta" in storyline_text
        assert "rosetta_manager" in storyline_text or "RosettaManager" in storyline_text

    def test_storyline_covers_avatar_streaming(self, storyline_text):
        """Chapter 21 should explain avatar + streaming coin-join."""
        assert "Avatar" in storyline_text or "avatar" in storyline_text
        assert "streaming" in storyline_text.lower() or "VideoStreaming" in storyline_text

    def test_storyline_covers_shadow_agents(self, storyline_text):
        """Chapter 22 should explain shadow agents and org chart."""
        assert "shadow" in storyline_text.lower()
        assert "org_compiler" in storyline_text or "OrgCompiler" in storyline_text or "org chart" in storyline_text.lower()

    def test_storyline_covers_security_plane(self, storyline_text):
        """Chapter 23 should explain zero-trust security."""
        assert "security" in storyline_text.lower()
        assert "ZeroTrust" in storyline_text or "zero-trust" in storyline_text.lower() or "zero trust" in storyline_text.lower()

    def test_storyline_covers_recursive_stability(self, storyline_text):
        """Chapter 24 should explain recursive stability controller."""
        assert "Lyapunov" in storyline_text or "stability" in storyline_text.lower()
        assert "recursive" in storyline_text.lower()

    def test_storyline_covers_supervisor_system(self, storyline_text):
        """Chapter 25 should explain supervisor and correction loops."""
        assert "Supervisor" in storyline_text or "supervisor" in storyline_text
        assert "correction" in storyline_text.lower() or "assumption" in storyline_text.lower()
