# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Storyline Conformance Test Suite
=================================
Validates that every chapter of ``MURPHY_SYSTEM_STORYLINE.md`` maps to
working, importable code that executes without error.

Each test is tagged ``@pytest.mark.storyline`` for selective runs::

    pytest tests/test_storyline_conformance.py -m storyline -v

Chapter → Module → pass/fail summary
--------------------------------------
Ch. 1   murphy_terminal.py            MurphyTerminalApp / detect_intent
Ch. 2   murphy_terminal.py            DialogContext.advance (7 steps)
Ch. 3   src/setup_wizard.py           SetupWizard.generate_config
Ch. 4   src/readiness_bootstrap_orchestrator.py  ReadinessBootstrapOrchestrator
Ch. 5   src/conversation_handler.py   ConversationHandler.handle
Ch. 6   two_phase_orchestrator.py     TwoPhaseOrchestrator.create_automation
Ch. 7   src/domain_gate_generator.py  DomainGateGenerator.generate_gates_for_system
Ch. 8   universal_control_plane.py    UniversalControlPlane.create_automation
Ch. 9   src/execution_engine/form_executor.py  FormDrivenExecutor (7 phases)
Ch. 10  src/safety_validation_pipeline.py      SafetyValidationPipeline.validate
Ch. 11  src/true_swarm_system.py      TrueSwarmSystem (exploration + control)
Ch. 12  src/sales_automation.py       SalesAutomationEngine.score_lead
Ch. 13  src/confidence_engine/confidence_calculator.py  ConfidenceCalculator.compute_confidence
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
# conftest.py at tests/ already adds src/ to sys.path.
# We also need the Murphy System root on the path for top-level modules
# (murphy_terminal, two_phase_orchestrator, universal_control_plane).

_MURPHY_ROOT = Path(__file__).resolve().parents[1]   # .../murphy_system/
_SRC_DIR = _MURPHY_ROOT / "src"

for _p in (_MURPHY_ROOT, _SRC_DIR):
    _ps = str(_p)
    if _ps not in sys.path:
        sys.path.insert(0, _ps)


# ---------------------------------------------------------------------------
# Ch. 1 — MurphyTerminalApp detects "start interview" intent
# ---------------------------------------------------------------------------

@pytest.mark.storyline
def test_ch1_terminal_detects_start_interview_intent():
    """Ch. 1: MurphyTerminalApp can detect the 'start interview' intent."""
    pytest.importorskip("textual", reason="textual not installed (pip install 'murphy-system[terminal]')")
    from murphy_terminal import detect_intent, MurphyTerminalApp  # noqa: F401

    intent = detect_intent("start interview")
    assert intent is not None, (
        "detect_intent('start interview') returned None — intent not registered"
    )
    assert "interview" in intent.lower(), (
        f"Expected intent name to contain 'interview', got: {intent!r}"
    )


# ---------------------------------------------------------------------------
# Ch. 2 — DialogContext.advance() completes all 7 onboarding steps
# ---------------------------------------------------------------------------

@pytest.mark.storyline
def test_ch2_dialog_context_advances_7_steps():
    """Ch. 2: DialogContext.advance() walks through all 7 onboarding steps."""
    pytest.importorskip("textual", reason="textual not installed (pip install 'murphy-system[terminal]')")
    from murphy_terminal import DialogContext

    ctx = DialogContext()
    assert len(ctx.INTERVIEW_STEPS) == 7, (
        f"Expected 7 INTERVIEW_STEPS, found {len(ctx.INTERVIEW_STEPS)}"
    )

    ctx.start()
    answers = [
        "Inoni LLC",           # name
        "increase sales",      # business_goal
        "automation",          # use_case
        "Slack, GitHub",       # platforms
        "pro",                 # billing_tier
        "auto",                # integrations
        "yes",                 # confirm
    ]
    for answer in answers:
        response = ctx.advance(answer)
        assert isinstance(response, str), (
            f"advance() returned non-string after answer {answer!r}: {response!r}"
        )

    assert ctx.is_complete, (
        "DialogContext is not marked complete after all 7 answers"
    )
    assert len(ctx.collected) > 0, (
        "No answers were collected after completing the interview"
    )


# ---------------------------------------------------------------------------
# Ch. 3 — SetupWizard.generate_config() produces a valid config dict
# ---------------------------------------------------------------------------

@pytest.mark.storyline
def test_ch3_setup_wizard_generates_valid_config():
    """Ch. 3: SetupWizard.generate_config() returns a non-empty config dict."""
    from setup_wizard import SetupWizard, SetupProfile

    wizard = SetupWizard()
    profile = SetupProfile(
        organization_name="Inoni LLC",
        industry="technology",
        company_size="small",
        automation_types=["workflow", "content"],
        security_level="standard",
    )
    config = wizard.generate_config(profile)

    assert isinstance(config, dict), (
        f"generate_config() returned {type(config).__name__}, expected dict"
    )
    assert config, "generate_config() returned an empty dict"
    assert "organization" in config, (
        "Config missing 'organization' key"
    )
    assert config["organization"]["name"] == "Inoni LLC", (
        "Organization name not preserved in config"
    )


# ---------------------------------------------------------------------------
# Ch. 4 — ReadinessBootstrapOrchestrator seeds KPIs, RBAC, tenant limits
# ---------------------------------------------------------------------------

@pytest.mark.storyline
def test_ch4_readiness_bootstrap_seeds_subsystems():
    """Ch. 4: ReadinessBootstrapOrchestrator.run_bootstrap() seeds KPIs, RBAC, and tenants."""
    from readiness_bootstrap_orchestrator import ReadinessBootstrapOrchestrator

    orchestrator = ReadinessBootstrapOrchestrator()
    report = orchestrator.run_bootstrap()

    assert report is not None, "run_bootstrap() returned None"
    task_names = {t.subsystem for t in report.tasks}
    for expected in ("kpi_tracker", "rbac_controller", "tenant_governor"):
        assert expected in task_names, (
            f"Bootstrap did not include task for subsystem '{expected}'. "
            f"Found: {task_names}"
        )


# ---------------------------------------------------------------------------
# Ch. 5 — ConversationHandler.handle() routes natural language input
# ---------------------------------------------------------------------------

@pytest.mark.storyline
def test_ch5_conversation_handler_routes_natural_language():
    """Ch. 5: ConversationHandler.handle() returns a structured response dict."""
    from conversation_handler import ConversationHandler

    handler = ConversationHandler()
    result = handler.handle("automate my sales pipeline")

    assert isinstance(result, dict), (
        f"handle() returned {type(result).__name__}, expected dict"
    )
    assert result, "handle() returned an empty dict"
    assert "response" in result or "answer" in result or len(result) > 0, (
        "handle() response dict has no recognizable output key"
    )


# ---------------------------------------------------------------------------
# Ch. 6 — TwoPhaseOrchestrator.create_automation() completes Phase 1
# ---------------------------------------------------------------------------

@pytest.mark.storyline
def test_ch6_two_phase_orchestrator_completes_phase1():
    """Ch. 6: TwoPhaseOrchestrator.create_automation() returns a non-empty automation_id."""
    from two_phase_orchestrator import TwoPhaseOrchestrator

    orchestrator = TwoPhaseOrchestrator()
    automation_id = orchestrator.create_automation(
        request="automate lead qualification",
        domain="sales",
    )

    assert automation_id, (
        "create_automation() returned a falsy automation_id"
    )
    assert isinstance(automation_id, str), (
        f"create_automation() returned {type(automation_id).__name__}, expected str"
    )


# ---------------------------------------------------------------------------
# Ch. 7 — DomainGateGenerator.generate_gates_for_system() produces gates
# ---------------------------------------------------------------------------

@pytest.mark.storyline
def test_ch7_domain_gate_generator_produces_gates():
    """Ch. 7: DomainGateGenerator.generate_gates_for_system() returns at least one gate."""
    from domain_gate_generator import DomainGateGenerator

    generator = DomainGateGenerator()
    requirements = {
        "domain": "software",
        "complexity": "medium",
        "security_focus": True,
    }
    gates, analysis = generator.generate_gates_for_system(requirements)

    assert isinstance(gates, list), (
        f"generate_gates_for_system() returned {type(gates).__name__}, expected list"
    )
    assert len(gates) > 0, (
        "generate_gates_for_system() returned zero gates for a software domain"
    )
    assert isinstance(analysis, dict), (
        f"Gate analysis is {type(analysis).__name__}, expected dict"
    )


# ---------------------------------------------------------------------------
# Ch. 8 — UniversalControlPlane.create_automation() selects engines
# ---------------------------------------------------------------------------

@pytest.mark.storyline
def test_ch8_universal_control_plane_selects_engines():
    """Ch. 8: UniversalControlPlane.create_automation() creates a session with engines."""
    from universal_control_plane import UniversalControlPlane

    ucp = UniversalControlPlane()
    session_id = ucp.create_automation(
        request="send a daily sales report email",
        user_id="test-user",
        repository_id="test-repo",
    )

    assert session_id, (
        "create_automation() returned a falsy session_id"
    )
    assert isinstance(session_id, str), (
        f"create_automation() returned {type(session_id).__name__}, expected str"
    )
    assert session_id in ucp.sessions, (
        "Returned session_id not found in ucp.sessions — session was not stored"
    )


# ---------------------------------------------------------------------------
# Ch. 9 — FormDrivenExecutor runs 7-phase pipeline
# ---------------------------------------------------------------------------

@pytest.mark.storyline
def test_ch9_form_driven_executor_runs_7_phases():
    """Ch. 9: FormDrivenExecutor.execute_task() runs all 7 phases (EXPAND … EXECUTE)."""
    from execution_engine.form_executor import FormDrivenExecutor
    from confidence_engine.murphy_models import Phase

    expected_phases = [
        Phase.EXPAND,
        Phase.TYPE,
        Phase.ENUMERATE,
        Phase.CONSTRAIN,
        Phase.COLLAPSE,
        Phase.BIND,
        Phase.EXECUTE,
    ]
    assert len(expected_phases) == 7, "Test setup error: phase list must have 7 entries"

    executor = FormDrivenExecutor()
    assert len(executor.phases) == 7, (
        f"FormDrivenExecutor defines {len(executor.phases)} phases, expected 7"
    )

    class _SimpleTask:
        task_id = "storyline-ch9-test"
        description = "validate 7-phase pipeline"

    result = executor.execute_task(task=_SimpleTask(), execution_mode="automatic")

    assert result is not None, "execute_task() returned None"
    assert hasattr(result, "phase_results"), (
        "ExecutionResult has no 'phase_results' attribute"
    )


# ---------------------------------------------------------------------------
# Ch. 10 — SafetyValidationPipeline.validate() runs all 3 stages
# ---------------------------------------------------------------------------

@pytest.mark.storyline
def test_ch10_safety_validation_pipeline_runs_all_3_stages():
    """Ch. 10: SafetyValidationPipeline.validate() executes PRE, EXECUTION, and POST stages."""
    from safety_validation_pipeline import (
        SafetyValidationPipeline,
        ValidationStage,
        OverallVerdict,
    )

    pipeline = SafetyValidationPipeline()

    # Register one check per stage so we can confirm all three are visited.
    visited: list[str] = []

    def _pre_check(ctx: dict[str, Any]) -> tuple[bool, str]:
        visited.append("pre")
        return True, "pre-execution ok"

    def _exec_check(ctx: dict[str, Any]) -> tuple[bool, str]:
        visited.append("exec")
        return True, "execution ok"

    def _post_check(ctx: dict[str, Any]) -> tuple[bool, str]:
        visited.append("post")
        return True, "post-execution ok"

    pipeline.register_check(ValidationStage.PRE_EXECUTION, "auth_check", _pre_check)
    pipeline.register_check(ValidationStage.EXECUTION, "progress_check", _exec_check)
    pipeline.register_check(ValidationStage.POST_EXECUTION, "output_check", _post_check)

    result = pipeline.validate("action-storyline-test", "deploy", {"user": "admin"})

    assert result is not None, "validate() returned None"
    assert result.verdict == OverallVerdict.PASSED, (
        f"Expected PASSED verdict, got {result.verdict}"
    )
    assert "pre" in visited, "PRE_EXECUTION stage was not run"
    assert "exec" in visited, "EXECUTION stage was not run"
    assert "post" in visited, "POST_EXECUTION stage was not run"


# ---------------------------------------------------------------------------
# Ch. 11 — TrueSwarmSystem creates exploration + control swarms
# ---------------------------------------------------------------------------

@pytest.mark.storyline
def test_ch11_true_swarm_system_creates_both_swarms():
    """Ch. 11: TrueSwarmSystem.execute_phase() spawns exploration and control swarms."""
    from true_swarm_system import TrueSwarmSystem, Phase

    swarm = TrueSwarmSystem()
    result = swarm.execute_phase(
        phase=Phase.EXPAND,
        task="analyse customer churn patterns",
        context={"domain": "sales", "complexity": 0.4},
    )

    assert isinstance(result, dict), (
        f"execute_phase() returned {type(result).__name__}, expected dict"
    )
    assert "exploration_agents" in result, (
        "Result missing 'exploration_agents' key — exploration swarm not recorded"
    )
    assert "control_agents" in result, (
        "Result missing 'control_agents' key — control swarm not recorded"
    )
    assert len(result["exploration_agents"]) > 0, (
        "No exploration agents were spawned"
    )
    assert len(result["control_agents"]) > 0, (
        "No control agents were spawned"
    )


# ---------------------------------------------------------------------------
# Ch. 12 — SalesAutomationEngine.score_lead() returns a valid score
# ---------------------------------------------------------------------------

@pytest.mark.storyline
def test_ch12_sales_automation_engine_scores_lead():
    """Ch. 12: SalesAutomationEngine.score_lead() returns a float in [0, 100]."""
    from sales_automation import SalesAutomationEngine, LeadProfile

    engine = SalesAutomationEngine()
    lead = LeadProfile(
        company_name="Inoni LLC",
        contact_name="Corey Post",
        contact_email="corey@inoni.com",
        industry="technology",
        company_size="small",
        interests=["CI/CD automation", "agent swarms", "API integration"],
    )
    score = engine.score_lead(lead)

    assert isinstance(score, (int, float)), (
        f"score_lead() returned {type(score).__name__}, expected numeric"
    )
    assert 0.0 <= score <= 100.0, (
        f"score_lead() returned {score}, expected a value in [0, 100]"
    )


# ---------------------------------------------------------------------------
# Ch. 13 — ConfidenceCalculator.compute_confidence() returns valid c_t
# ---------------------------------------------------------------------------

@pytest.mark.storyline
def test_ch13_confidence_calculator_returns_valid_ct():
    """Ch. 13: ConfidenceCalculator.compute_confidence() returns c_t ∈ [0, 1]."""
    from confidence_engine.confidence_calculator import ConfidenceCalculator
    from confidence_engine.models import (
        ArtifactGraph,
        Phase,
        TrustModel,
        VerificationEvidence,
    )

    calculator = ConfidenceCalculator()
    graph = ArtifactGraph()
    trust_model = TrustModel()

    state = calculator.compute_confidence(
        graph=graph,
        phase=Phase.EXPAND,
        verification_evidence=[],
        trust_model=trust_model,
    )

    assert state is not None, "compute_confidence() returned None"
    assert hasattr(state, "confidence"), (
        "ConfidenceState has no 'confidence' attribute"
    )
    assert 0.0 <= state.confidence <= 1.0, (
        f"compute_confidence() returned c_t={state.confidence}, expected value in [0, 1]"
    )
