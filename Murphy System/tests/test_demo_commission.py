"""
Demo Commission Tests — Murphy System

Verifies that the complete demo pipeline is wired and produces real output
for all 6 canonical demo scenarios and custom queries.

Commission criteria:
  - Every scenario completes without raising an exception
  - Every scenario produces at least 4 terminal steps
  - Every scenario has a non-empty ROI message
  - Every scenario produces an automation spec with workflow_id
  - The automation spec has positive ROI calculations
  - The DemoRunner.commission_all() report passes with 0 errors

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from demo_runner import DemoRunner, _SCENARIOS


PILOT_QUERIES = {
    "onboarding": "Onboard a new client",
    "finance":    "Generate Q3 finance report",
    "hr":         "Screen candidates for PM role",
    "compliance": "Run compliance audit",
    "project":    "Create project plan",
    "invoice":    "Process invoice batch",
}


@pytest.fixture(scope="module")
def runner():
    return DemoRunner()


class TestDemoRunnerInstantiation:
    def test_instantiates(self):
        r = DemoRunner()
        assert r is not None

    def test_has_detect_scenario(self):
        r = DemoRunner()
        assert hasattr(r, "_detect_scenario")

    def test_has_run_scenario(self):
        r = DemoRunner()
        assert hasattr(r, "run_scenario")

    def test_has_commission_all(self):
        r = DemoRunner()
        assert hasattr(r, "commission_all")


class TestScenarioDetection:
    def setup_method(self):
        self.r = DemoRunner()

    def test_detects_onboarding(self):
        assert self.r._detect_scenario("Onboard a new client") == "onboarding"

    def test_detects_finance(self):
        assert self.r._detect_scenario("Generate Q3 finance report") == "finance"

    def test_detects_hr(self):
        assert self.r._detect_scenario("Screen candidates for PM role") == "hr"

    def test_detects_compliance(self):
        assert self.r._detect_scenario("Run compliance audit") == "compliance"

    def test_detects_project(self):
        assert self.r._detect_scenario("Create project plan") == "project"

    def test_detects_invoice(self):
        assert self.r._detect_scenario("Process invoice batch") == "invoice"

    def test_unknown_returns_custom(self):
        assert self.r._detect_scenario("Something totally unknown xyz123") == "custom"


class TestRunScenarioStructure:
    """Verify run_scenario returns correct structure for each scenario."""

    @pytest.mark.parametrize("scenario_key,query", list(PILOT_QUERIES.items()))
    def test_returns_dict(self, runner, scenario_key, query):
        result = runner.run_scenario(query)
        assert isinstance(result, dict)

    @pytest.mark.parametrize("scenario_key,query", list(PILOT_QUERIES.items()))
    def test_has_required_keys(self, runner, scenario_key, query):
        result = runner.run_scenario(query)
        for key in ("steps", "roi_message", "scenario_key", "duration_ms", "mfgc", "mss", "workflow", "spec"):
            assert key in result, f"Scenario {scenario_key} missing key: {key}"

    @pytest.mark.parametrize("scenario_key,query", list(PILOT_QUERIES.items()))
    def test_scenario_key_matches(self, runner, scenario_key, query):
        result = runner.run_scenario(query)
        assert result["scenario_key"] == scenario_key

    @pytest.mark.parametrize("scenario_key,query", list(PILOT_QUERIES.items()))
    def test_steps_is_list(self, runner, scenario_key, query):
        result = runner.run_scenario(query)
        assert isinstance(result["steps"], list)

    @pytest.mark.parametrize("scenario_key,query", list(PILOT_QUERIES.items()))
    def test_minimum_four_steps(self, runner, scenario_key, query):
        result = runner.run_scenario(query)
        assert len(result["steps"]) >= 4, \
            f"Scenario {scenario_key} produced only {len(result['steps'])} steps"

    @pytest.mark.parametrize("scenario_key,query", list(PILOT_QUERIES.items()))
    def test_roi_message_non_empty(self, runner, scenario_key, query):
        result = runner.run_scenario(query)
        assert result["roi_message"] and len(result["roi_message"]) > 10

    @pytest.mark.parametrize("scenario_key,query", list(PILOT_QUERIES.items()))
    def test_duration_positive(self, runner, scenario_key, query):
        result = runner.run_scenario(query)
        assert result["duration_ms"] > 0


class TestStepStructure:
    """Verify individual step dicts have required fields."""

    @pytest.mark.parametrize("scenario_key,query", list(PILOT_QUERIES.items()))
    def test_steps_have_label(self, runner, scenario_key, query):
        result = runner.run_scenario(query)
        for step in result["steps"]:
            assert "label" in step, f"Step in {scenario_key} missing 'label'"

    @pytest.mark.parametrize("scenario_key,query", list(PILOT_QUERIES.items()))
    def test_steps_have_cls(self, runner, scenario_key, query):
        result = runner.run_scenario(query)
        valid_classes = {"green", "cyan", "teal", "roi", "done"}
        for step in result["steps"]:
            assert step.get("cls") in valid_classes, \
                f"Step cls '{step.get('cls')}' not in valid set"

    @pytest.mark.parametrize("scenario_key,query", list(PILOT_QUERIES.items()))
    def test_first_step_is_cli_command(self, runner, scenario_key, query):
        result = runner.run_scenario(query)
        first = result["steps"][0]
        assert first["cls"] == "green"
        assert "murphy" in first["label"].lower() or "$" in first["label"]


class TestAutomationSpec:
    """Verify the automation spec is a usable schematic."""

    @pytest.mark.parametrize("scenario_key,query", list(PILOT_QUERIES.items()))
    def test_spec_has_required_fields(self, runner, scenario_key, query):
        result = runner.run_scenario(query)
        spec = result["spec"]
        for field in ("spec_id", "query", "scenario_key", "integrations",
                      "monthly_savings_usd", "roi_multiple", "workflow_id"):
            assert field in spec, f"Spec for {scenario_key} missing: {field}"

    @pytest.mark.parametrize("scenario_key,query", list(PILOT_QUERIES.items()))
    def test_spec_id_format(self, runner, scenario_key, query):
        spec = runner.run_scenario(query)["spec"]
        assert spec["spec_id"].startswith("SPEC-")

    @pytest.mark.parametrize("scenario_key,query", list(PILOT_QUERIES.items()))
    def test_positive_monthly_savings(self, runner, scenario_key, query):
        spec = runner.run_scenario(query)["spec"]
        assert spec["monthly_savings_usd"] > 0

    @pytest.mark.parametrize("scenario_key,query", list(PILOT_QUERIES.items()))
    def test_positive_roi_multiple(self, runner, scenario_key, query):
        spec = runner.run_scenario(query)["spec"]
        assert spec["roi_multiple"] > 1.0, \
            f"ROI should exceed 1x; got {spec['roi_multiple']}x"

    @pytest.mark.parametrize("scenario_key,query", list(PILOT_QUERIES.items()))
    def test_has_integrations_list(self, runner, scenario_key, query):
        spec = runner.run_scenario(query)["spec"]
        assert isinstance(spec["integrations"], list)
        assert len(spec["integrations"]) > 0

    @pytest.mark.parametrize("scenario_key,query", list(PILOT_QUERIES.items()))
    def test_workflow_id_non_empty(self, runner, scenario_key, query):
        result = runner.run_scenario(query)
        assert result["workflow"].get("workflow_id") or result["spec"].get("workflow_id")


class TestCustomQuery:
    def test_custom_query_runs(self, runner):
        result = runner.run_scenario("Build a customer feedback automation pipeline")
        assert isinstance(result, dict)
        assert len(result["steps"]) >= 3

    def test_custom_scenario_key(self, runner):
        result = runner.run_scenario("Something completely unique xyz987")
        assert result["scenario_key"] == "custom"

    def test_custom_has_spec(self, runner):
        result = runner.run_scenario("Automate my inventory management")
        assert "spec" in result
        assert result["spec"]["spec_id"].startswith("SPEC-")


class TestCommissionAll:
    """Full commissioning test — proves all gaps are closed."""

    def test_commission_all_passes(self, runner):
        report = runner.commission_all()
        assert report["passed"] is True, \
            f"Commission FAILED. Errors: {report['errors']}"

    def test_commission_all_runs_all_scenarios(self, runner):
        report = runner.commission_all()
        assert report["scenarios_run"] == len(_SCENARIOS)

    def test_commission_all_zero_errors(self, runner):
        report = runner.commission_all()
        assert report["scenarios_failed"] == 0, \
            f"Failed scenarios: {report['errors']}"

    def test_commission_report_has_timestamp(self, runner):
        report = runner.commission_all()
        assert "generated_at" in report
        assert len(report["generated_at"]) > 0

    def test_commission_results_keyed_by_scenario(self, runner):
        report = runner.commission_all()
        for key in _SCENARIOS:
            assert key in report["results"], f"Missing result for scenario: {key}"
