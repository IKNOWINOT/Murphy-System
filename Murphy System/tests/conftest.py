"""
Test configuration for Murphy System.

Adds src/ to sys.path so modules can be imported without
manual PYTHONPATH manipulation.

Also provides:
  - ``textual_available`` session fixture: skips any test that requires the
    optional ``textual`` TUI dependency when it is not installed.
  - ``pytest_terminal_summary`` hook: after a test run that includes any
    ``@pytest.mark.storyline`` tests, prints a chapter → module → pass/fail
    table so stakeholders can see at a glance which storyline promises hold.
"""

import importlib.util
import os
import sys
from typing import Dict

import pytest

# ---------------------------------------------------------------------------
# sys.path bootstrap
# ---------------------------------------------------------------------------
# Add src/ to the Python path
_src_dir = os.path.join(os.path.dirname(__file__), '..', 'src')
_src_dir = os.path.abspath(_src_dir)
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)


# ---------------------------------------------------------------------------
# Storyline chapter map
# ---------------------------------------------------------------------------
# Authoritative mapping used by both the fixture and the summary hook.
# Keys are the *exact* test function names in test_storyline_conformance.py.

_STORYLINE_MAP: Dict[str, Dict[str, str]] = {
    "test_ch1_terminal_detects_start_interview_intent": {
        "chapter": "Ch. 1",
        "module": "murphy_terminal.py",
        "description": "MurphyTerminalApp detects 'start interview' intent",
    },
    "test_ch2_dialog_context_advances_7_steps": {
        "chapter": "Ch. 2",
        "module": "murphy_terminal.py",
        "description": "DialogContext.advance() completes 7 onboarding steps",
    },
    "test_ch3_setup_wizard_generates_valid_config": {
        "chapter": "Ch. 3",
        "module": "src/setup_wizard.py",
        "description": "SetupWizard.generate_config() produces valid config",
    },
    "test_ch4_readiness_bootstrap_seeds_subsystems": {
        "chapter": "Ch. 4",
        "module": "src/readiness_bootstrap_orchestrator.py",
        "description": "ReadinessBootstrapOrchestrator seeds KPIs, RBAC, tenants",
    },
    "test_ch5_conversation_handler_routes_natural_language": {
        "chapter": "Ch. 5",
        "module": "src/conversation_handler.py",
        "description": "ConversationHandler.handle() routes to DomainEngine",
    },
    "test_ch6_two_phase_orchestrator_completes_phase1": {
        "chapter": "Ch. 6",
        "module": "two_phase_orchestrator.py",
        "description": "TwoPhaseOrchestrator.create_automation() completes Phase 1",
    },
    "test_ch7_domain_gate_generator_produces_gates": {
        "chapter": "Ch. 7",
        "module": "src/domain_gate_generator.py",
        "description": "DomainGateGenerator.generate_gates_for_system() produces gates",
    },
    "test_ch8_universal_control_plane_selects_engines": {
        "chapter": "Ch. 8",
        "module": "universal_control_plane.py",
        "description": "UniversalControlPlane.create_automation() selects engines",
    },
    "test_ch9_form_driven_executor_runs_7_phases": {
        "chapter": "Ch. 9",
        "module": "src/execution_engine/form_executor.py",
        "description": "FormDrivenExecutor runs 7-phase pipeline",
    },
    "test_ch10_safety_validation_pipeline_runs_all_3_stages": {
        "chapter": "Ch. 10",
        "module": "src/safety_validation_pipeline.py",
        "description": "SafetyValidationPipeline.validate() runs all 3 stages",
    },
    "test_ch11_true_swarm_system_creates_both_swarms": {
        "chapter": "Ch. 11",
        "module": "src/true_swarm_system.py",
        "description": "TrueSwarmSystem creates exploration + control swarms",
    },
    "test_ch12_sales_automation_engine_scores_lead": {
        "chapter": "Ch. 12",
        "module": "src/sales_automation.py",
        "description": "SalesAutomationEngine.score_lead() returns valid score",
    },
    "test_ch13_confidence_calculator_returns_valid_ct": {
        "chapter": "Ch. 13",
        "module": "src/confidence_engine/confidence_calculator.py",
        "description": "ConfidenceCalculator.compute_confidence() returns valid c_t",
    },
}


# ---------------------------------------------------------------------------
# Fixture: textual_available
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def textual_available() -> bool:
    """Session-scoped fixture that skips the requesting test when the optional
    ``textual`` TUI package is not installed.

    Usage in a test::

        def test_something(textual_available):
            from murphy_terminal import MurphyTerminalApp
            ...

    If ``textual`` is absent the test is skipped with a clear message rather
    than failing with an ``ImportError``.
    """
    if importlib.util.find_spec("textual") is None:
        pytest.skip("textual not installed — install with: pip install 'murphy-system[terminal]'")
    return True


# ---------------------------------------------------------------------------
# Hook: storyline chapter → module → pass/fail summary table
# ---------------------------------------------------------------------------

def pytest_terminal_summary(terminalreporter) -> None:
    """Print a chapter → module → pass/fail summary after any storyline run.

    The table is emitted only when at least one ``@pytest.mark.storyline``
    test was collected during the session, so normal (non-storyline) runs are
    unaffected.
    """
    # Gather all storyline test results from the reporter's stats.
    passed_ids = {
        _nodeid_to_func(r.nodeid)
        for r in terminalreporter.stats.get("passed", [])
    }
    failed_ids = {
        _nodeid_to_func(r.nodeid)
        for r in terminalreporter.stats.get("failed", [])
    }
    skipped_ids = {
        _nodeid_to_func(r.nodeid)
        for r in terminalreporter.stats.get("skipped", [])
    }

    # Only print the table if at least one storyline test appeared.
    storyline_ran = (passed_ids | failed_ids | skipped_ids) & _STORYLINE_MAP.keys()
    if not storyline_ran:
        return

    terminalreporter.write_sep("=", "Storyline Conformance Summary")

    col_ch = 6
    col_mod = 44
    col_desc = 50
    col_status = 6
    header = (
        f"{'Ch.':<{col_ch}} {'Module':<{col_mod}} {'Description':<{col_desc}} {'Status':>{col_status}}"
    )
    separator = "-" * len(header)

    terminalreporter.write_line(header)
    terminalreporter.write_line(separator)

    all_passed = True
    for func_name, info in _STORYLINE_MAP.items():
        if func_name in passed_ids:
            status = "PASS"
            markup = {"green": True}
        elif func_name in failed_ids:
            status = "FAIL"
            markup = {"red": True}
            all_passed = False
        elif func_name in skipped_ids:
            status = "SKIP"
            markup = {"yellow": True}
        else:
            # Test was not collected in this run — skip from table.
            continue

        row = (
            f"{info['chapter']:<{col_ch}} "
            f"{info['module']:<{col_mod}} "
            f"{info['description']:<{col_desc}} "
            f"{status:>{col_status}}"
        )
        terminalreporter.write_line(row, **markup)

    terminalreporter.write_line(separator)
    verdict = "ALL CHAPTERS PASS ✓" if all_passed else "ONE OR MORE CHAPTERS FAILED ✗"
    terminalreporter.write_line(
        verdict,
        **({"green": True} if all_passed else {"red": True}),
    )


def _nodeid_to_func(nodeid: str) -> str:
    """Extract the bare test function name from a pytest node id.

    E.g. ``tests/test_storyline_conformance.py::test_ch1_…`` → ``test_ch1_…``
    """
    return nodeid.split("::")[-1]
