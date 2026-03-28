"""Integration tests: run all 10 industry simulation scripts as a user would."""
import pytest, sys, os, subprocess

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "../examples/scripts")
SRC_DIR = os.path.join(os.path.dirname(__file__), "../src")

SCRIPTS = [
    "bas_energy_management_simulation.py",
    "manufacturing_automation_simulation.py",
    "healthcare_automation_simulation.py",
    "energy_audit_simulation.py",
    "org_chart_simulation.py",
    "system_configuration_simulation.py",
    "retail_automation_simulation.py",
    "climate_resilience_simulation.py",
    "decision_engine_simulation.py",
    "synthetic_interview_simulation.py",
]


def _run_script(name):
    path = os.path.join(SCRIPTS_DIR, name)
    env = os.environ.copy()
    env["PYTHONPATH"] = SRC_DIR
    result = subprocess.run(
        [sys.executable, path],
        capture_output=True, text=True, timeout=30, env=env,
    )
    return result


@pytest.mark.parametrize("script_name", SCRIPTS)
def test_script_completes(script_name):
    result = _run_script(script_name)
    assert result.returncode == 0, f"{script_name} exited {result.returncode}:\n{result.stderr[-500:]}"
    assert "SIMULATION COMPLETE" in result.stdout, \
        f"{script_name} did not print SIMULATION COMPLETE.\nstdout: {result.stdout[-500:]}"


@pytest.mark.parametrize("script_name", SCRIPTS)
def test_script_no_traceback(script_name):
    result = _run_script(script_name)
    assert "Traceback" not in result.stderr, \
        f"{script_name} produced a Traceback:\n{result.stderr[-500:]}"
