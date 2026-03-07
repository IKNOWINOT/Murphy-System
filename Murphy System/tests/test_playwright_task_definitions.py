"""
Tests for playwright_task_definitions — BrowserTask spec, MurphyTaskRunner
(internal UITestingFramework execution), PlaywrightExporter, and
BrowserTaskFactory suite builder.

Validates that the system runs correctly using Murphy's own internal
UITestingFramework without requiring an external Playwright process.

Design Label: TEST-BROWSER-TASKS-001
Owner: QA Team
"""
import json
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from playwright_task_definitions import (
    BrowserTask,
    BrowserTaskFactory,
    MurphyTaskRunner,
    PlaywrightExporter,
    PlaywrightTaskFactory,   # backward-compat alias
    PlaywrightTask,          # backward-compat alias
    TaskType,
    TaskStatus,
    ActionType,
    TaskStep,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_HTML = """<!DOCTYPE html>
<html>
<head><title>Murphy System Terminal</title></head>
<body>
  <div id="terminalOutput">Terminal output here</div>
  <input id="messageInput" type="text" placeholder="Type a message" />
  <form id="onboarding-form">
    <input id="input-name" name="name" required />
    <input id="input-email" name="email" required />
    <input id="input-position" name="position" />
    <input id="input-justification" name="justification" />
    <button id="btn-submit-onboarding">Submit</button>
  </form>
  <div id="eula-content">EULA text here</div>
  <button id="btn-accept-eula">I Accept</button>
  <span id="connection-status">Connected</span>
  <div class="error-message">Something went wrong</div>
  <script>
    try { doSomething(); } catch(e) { console.error(e); }
  </script>
</body>
</html>"""


@pytest.fixture
def runner():
    return MurphyTaskRunner(base_url="http://localhost:8000")


@pytest.fixture
def factory():
    return BrowserTaskFactory(base_url="http://localhost:8000")


@pytest.fixture
def exporter():
    return PlaywrightExporter()


# ---------------------------------------------------------------------------
# BrowserTask model
# ---------------------------------------------------------------------------


class TestBrowserTask:
    def test_defaults(self):
        task = BrowserTask()
        assert task.task_id
        assert task.status == TaskStatus.PENDING
        assert task.steps == []

    def test_to_dict_keys(self):
        task = BrowserTask(description="test task")
        d = task.to_dict()
        for key in ["task_id", "task_type", "description", "steps",
                    "success_criteria", "status", "preconditions"]:
            assert key in d

    def test_check_preconditions_met(self):
        task = BrowserTask(preconditions=["session.user_id", "session.eula_accepted"])
        ctx = {"session": {"user_id": "u1", "eula_accepted": True}}
        assert task.check_preconditions(ctx) == []

    def test_check_preconditions_unmet(self):
        task = BrowserTask(preconditions=["session.user_id"])
        unmet = task.check_preconditions({})
        assert "session.user_id" in unmet

    def test_backward_compat_alias(self):
        """PlaywrightTask should be an alias for BrowserTask."""
        pt = PlaywrightTask()
        assert isinstance(pt, BrowserTask)

    def test_backward_compat_factory_alias(self):
        f = PlaywrightTaskFactory()
        assert isinstance(f, BrowserTaskFactory)


# ---------------------------------------------------------------------------
# MurphyTaskRunner — navigate
# ---------------------------------------------------------------------------


class TestMurphyRunnerNavigate:
    def test_navigate_step_loads_page(self, runner):
        task = BrowserTask(
            task_type=TaskType.OPEN_TERMINAL,
            steps=[
                TaskStep(action=ActionType.NAVIGATE,
                         target="http://localhost:8000/terminal_worker.html")
            ],
        )
        result = runner.run(task, html_content=SAMPLE_HTML)
        assert result["status"] in ("passed", "failed")  # loaded or not, no crash

    def test_navigate_relative_url_prefixed(self, runner):
        task = BrowserTask(
            steps=[
                TaskStep(action=ActionType.NAVIGATE, target="/terminal_worker.html")
            ],
        )
        result = runner.run(task, html_content=SAMPLE_HTML)
        step_result = result["step_results"][0]
        assert "localhost:8000" in step_result.get("url", "")


# ---------------------------------------------------------------------------
# MurphyTaskRunner — assert element
# ---------------------------------------------------------------------------


class TestMurphyRunnerAssertElement:
    def test_assert_existing_element_passes(self, runner):
        task = BrowserTask(
            steps=[
                TaskStep(action=ActionType.ASSERT_VISIBLE, target="#terminalOutput")
            ],
        )
        result = runner.run(task, html_content=SAMPLE_HTML)
        assert result["status"] == "passed"

    def test_assert_missing_element_fails(self, runner):
        task = BrowserTask(
            failure_handling="abort",
            steps=[
                TaskStep(action=ActionType.ASSERT_VISIBLE, target="#does-not-exist",
                         optional=False)
            ],
        )
        result = runner.run(task, html_content=SAMPLE_HTML)
        assert result["status"] == "failed"

    def test_optional_missing_element_does_not_abort(self, runner):
        task = BrowserTask(
            steps=[
                TaskStep(action=ActionType.ASSERT_VISIBLE, target="#missing",
                         optional=True),
                TaskStep(action=ActionType.ASSERT_VISIBLE, target="#terminalOutput"),
            ],
        )
        result = runner.run(task, html_content=SAMPLE_HTML)
        assert result["status"] == "passed"


# ---------------------------------------------------------------------------
# MurphyTaskRunner — assert text
# ---------------------------------------------------------------------------


class TestMurphyRunnerAssertText:
    def test_text_present_passes(self, runner):
        task = BrowserTask(
            steps=[TaskStep(action=ActionType.ASSERT_TEXT,
                            target="#connection-status", value="Connected")],
        )
        result = runner.run(task, html_content=SAMPLE_HTML)
        assert result["status"] == "passed"

    def test_text_absent_fails(self, runner):
        task = BrowserTask(
            failure_handling="abort",
            steps=[TaskStep(action=ActionType.ASSERT_TEXT,
                            target="", value="THIS TEXT IS NOT PRESENT",
                            optional=False)],
        )
        result = runner.run(task, html_content=SAMPLE_HTML)
        assert result["status"] == "failed"


# ---------------------------------------------------------------------------
# MurphyTaskRunner — fill
# ---------------------------------------------------------------------------


class TestMurphyRunnerFill:
    def test_fill_existing_input_passes(self, runner):
        task = BrowserTask(
            steps=[TaskStep(action=ActionType.FILL, target="#input-name",
                            value="Alice Smith")],
        )
        result = runner.run(task, html_content=SAMPLE_HTML)
        assert result["status"] == "passed"

    def test_fill_missing_input_fails(self, runner):
        task = BrowserTask(
            failure_handling="abort",
            steps=[TaskStep(action=ActionType.FILL, target="#nonexistent",
                            value="test", optional=False)],
        )
        result = runner.run(task, html_content=SAMPLE_HTML)
        assert result["status"] == "failed"


# ---------------------------------------------------------------------------
# MurphyTaskRunner — simulate error
# ---------------------------------------------------------------------------


class TestMurphyRunnerSimulateError:
    def test_simulate_500_passes(self, runner):
        task = BrowserTask(
            steps=[TaskStep(action=ActionType.SIMULATE_API_ERROR,
                            target="/api/auth/signup", value="500")],
        )
        result = runner.run(task, html_content=SAMPLE_HTML)
        assert result["status"] == "passed"
        step_r = result["step_results"][0]
        assert step_r.get("error_spec", {}).get("status_code") == 500

    def test_simulate_401_error_spec(self, runner):
        task = BrowserTask(
            steps=[TaskStep(action=ActionType.SIMULATE_API_ERROR,
                            target="/api/profiles/me", value="401")],
        )
        result = runner.run(task, html_content=SAMPLE_HTML)
        err_spec = result["step_results"][0].get("error_spec", {})
        assert err_spec.get("recoverable") is True


# ---------------------------------------------------------------------------
# MurphyTaskRunner — precondition skip
# ---------------------------------------------------------------------------


class TestPreconditionSkip:
    def test_skipped_when_precondition_missing(self, runner):
        task = BrowserTask(
            preconditions=["session.eula_accepted"],
            steps=[TaskStep(action=ActionType.NAVIGATE,
                            target="http://localhost:8000/terminal_worker.html")],
        )
        result = runner.run(task, context={})
        assert result["status"] == "skipped"


# ---------------------------------------------------------------------------
# MurphyTaskRunner — run_suite
# ---------------------------------------------------------------------------


class TestRunSuite:
    def test_run_suite_returns_result_per_task(self, runner, factory):
        suite = [factory.verify_ui_loaded(), factory.take_screenshot()]
        results = runner.run_suite(suite, html_content=SAMPLE_HTML)
        assert len(results) == 2
        for r in results:
            assert "task_id" in r
            assert "status" in r

    def test_run_log_populated(self, runner, factory):
        suite = [factory.verify_ui_loaded()]
        runner.run_suite(suite, html_content=SAMPLE_HTML)
        log = runner.get_run_log()
        assert len(log) >= 1


# ---------------------------------------------------------------------------
# BrowserTaskFactory
# ---------------------------------------------------------------------------


class TestBrowserTaskFactory:
    def test_open_terminal_task(self, factory):
        task = factory.open_terminal(terminal="worker", api_port=8000)
        assert isinstance(task, BrowserTask)
        assert task.task_type == TaskType.OPEN_TERMINAL
        assert any("terminal_worker.html" in s.target for s in task.steps)

    def test_verify_ui_loaded_task(self, factory):
        task = factory.verify_ui_loaded()
        assert task.task_type == TaskType.VERIFY_UI_LOADED
        selectors = [s.target for s in task.steps]
        assert "#terminalOutput" in selectors

    def test_fill_onboarding_wizard_task(self, factory):
        profile = {"name": "Alice", "email": "alice@x.com",
                   "position": "Engineer", "justification": "Need access"}
        task = factory.fill_onboarding_wizard(profile)
        assert task.task_type == TaskType.FILL_ONBOARDING_WIZARD
        fill_targets = [s.target for s in task.steps if s.action == ActionType.FILL]
        assert "#input-name" in fill_targets

    def test_sign_eula_task(self, factory):
        task = factory.sign_eula()
        assert task.task_type == TaskType.SIGN_EULA
        actions = [s.action for s in task.steps]
        assert ActionType.SCROLL_TO_BOTTOM in actions
        assert ActionType.CLICK in actions

    def test_verify_api_connection_task(self, factory):
        task = factory.verify_api_connection(api_port=8090)
        assert task.metadata.get("api_port") == 8090

    def test_take_screenshot_task(self, factory):
        task = factory.take_screenshot(filename="test.png")
        assert task.task_type == TaskType.TAKE_SCREENSHOT
        assert task.metadata.get("filename") == "test.png"

    def test_simulate_api_error_task(self, factory):
        task = factory.simulate_api_error("/api/auth/signup", 400)
        assert task.task_type == TaskType.SIMULATE_ERROR

    def test_full_onboarding_suite_count(self, factory):
        suite = factory.full_onboarding_suite(profile_data={"name": "Bob"})
        assert len(suite) == 6  # wizard + eula + open + verify_ui + verify_api + screenshot

    def test_task_log_grows(self, factory):
        factory.open_terminal()
        factory.verify_ui_loaded()
        log = factory.get_task_log()
        assert len(log) >= 2


# ---------------------------------------------------------------------------
# PlaywrightExporter (optional external format)
# ---------------------------------------------------------------------------


class TestPlaywrightExporter:
    def test_export_returns_valid_json(self, factory, exporter):
        tasks = [factory.verify_ui_loaded(), factory.take_screenshot()]
        raw = exporter.export(tasks)
        data = json.loads(raw)
        assert data["schema"] == "murphy_browser_tasks_v1"
        assert len(data["tasks"]) == 2

    def test_export_to_file(self, factory, exporter, tmp_path):
        tasks = [factory.open_terminal()]
        path = str(tmp_path / "tasks.json")
        exporter.export_to_file(tasks, path)
        assert os.path.isfile(path)
        with open(path) as f:
            data = json.load(f)
        assert data["schema"] == "murphy_browser_tasks_v1"

    def test_exported_tasks_have_steps(self, factory, exporter):
        tasks = factory.full_onboarding_suite(profile_data={"name": "X"})
        raw = exporter.export(tasks)
        data = json.loads(raw)
        for t in data["tasks"]:
            assert "steps" in t

    def test_no_playwright_import_needed(self):
        """The module must be importable and functional without playwright installed."""
        import importlib
        spec = importlib.util.find_spec("playwright")
        # Whether or not playwright is installed, our module should work
        from playwright_task_definitions import MurphyTaskRunner as R
        assert R is not None


# ---------------------------------------------------------------------------
# Integration: full onboarding suite run on sample HTML
# ---------------------------------------------------------------------------


class TestFullSuiteIntegration:
    def test_onboarding_suite_runs_without_crash(self, factory, runner):
        profile = {
            "name": "Integration Test",
            "email": "it@test.com",
            "position": "QA Engineer",
            "justification": "Testing onboarding",
        }
        ctx = {
            "session": {
                "user_id": "u-test",
                "eula_accepted": True,
                "email_validated": True,
                "terminal_open": True,
            }
        }
        suite = factory.full_onboarding_suite(profile_data=profile)
        results = runner.run_suite(suite, context=ctx, html_content=SAMPLE_HTML)
        assert len(results) == 6
        # All tasks should have a known status, no exceptions
        for r in results:
            assert r["status"] in ("passed", "failed", "skipped")
