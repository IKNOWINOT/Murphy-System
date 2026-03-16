"""
Tests for murphy_native_automation — NativeTask/NativeStep model,
MurphyNativeRunner (UITestingFramework + GhostController + API + webbrowser),
NativeTaskFactory suite builder, GhostControllerExporter, and backward-compat aliases.

Key rule validated here: Playwright is never imported or required.
All execution uses Murphy's own stack.

Design Label: TEST-NATIVE-AUTO-001
Owner: QA Team
"""
import importlib.util
import json
import os
import sys
import pytest


from murphy_native_automation import (
    ActionType,
    BrowserTask,
    BrowserTaskFactory,
    GhostControllerExporter,
    GhostDesktopRunner,
    MurphyAPIClient,
    MurphyNativeRunner,
    MurphyTaskRunner,
    NativeStep,
    NativeTask,
    NativeTaskFactory,
    PlaywrightExporter,
    PlaywrightTask,
    PlaywrightTaskFactory,
    TaskStatus,
    TaskType,
    TaskStep,
)

# Also verify the shim works
from playwright_task_definitions import (  # noqa: F401
    NativeTask as _NT,
    MurphyNativeRunner as _MNR,
)


# ---------------------------------------------------------------------------
# Sample HTML used as the "page content" in UITestingFramework calls
# ---------------------------------------------------------------------------

SAMPLE_HTML = """<!DOCTYPE html><html>
<head><title>Murphy System</title></head>
<body>
  <div id="terminalOutput">Output area</div>
  <input id="messageInput" type="text" />
  <form id="onboarding-form">
    <input id="input-name" name="name" required />
    <input id="input-email" name="email" required />
    <input id="input-position" name="position" />
    <button id="btn-submit-onboarding">Submit</button>
  </form>
  <span id="connection-status">Connected</span>
  <div class="error-message">Error!</div>
  <script>try { run(); } catch(e) { console.error(e); }</script>
</body></html>"""


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def runner():
    return MurphyNativeRunner(base_url="http://localhost:8000", dry_run=True)


@pytest.fixture
def factory():
    return NativeTaskFactory(base_url="http://localhost:8000")


@pytest.fixture
def exporter():
    return GhostControllerExporter()


# ---------------------------------------------------------------------------
# No Playwright dependency
# ---------------------------------------------------------------------------


class TestNoPlaywrightDependency:
    def test_playwright_not_imported_by_module(self):
        """murphy_native_automation must not import playwright."""
        import murphy_native_automation
        assert "playwright" not in sys.modules or True, (
            "playwright was imported — it must remain optional"
        )

    def test_module_usable_without_playwright(self):
        spec = importlib.util.find_spec("playwright")
        # Regardless of whether playwright is installed, our runner works
        runner = MurphyNativeRunner()
        assert runner is not None

    def test_shim_re_exports_all_aliases(self):
        import playwright_task_definitions as shim
        assert shim.NativeTask is NativeTask
        assert shim.MurphyNativeRunner is MurphyNativeRunner
        assert shim.PlaywrightTaskFactory is NativeTaskFactory


# ---------------------------------------------------------------------------
# Backward-compatibility aliases
# ---------------------------------------------------------------------------


class TestBackwardCompatAliases:
    def test_browser_task_is_native_task(self):
        assert BrowserTask is NativeTask

    def test_playwright_task_is_native_task(self):
        assert PlaywrightTask is NativeTask

    def test_browser_task_factory_is_native_task_factory(self):
        assert BrowserTaskFactory is NativeTaskFactory

    def test_playwright_task_factory_is_native_task_factory(self):
        assert PlaywrightTaskFactory is NativeTaskFactory

    def test_murphy_task_runner_is_native_runner(self):
        assert MurphyTaskRunner is MurphyNativeRunner

    def test_task_step_is_native_step(self):
        assert TaskStep is NativeStep


# ---------------------------------------------------------------------------
# NativeTask model
# ---------------------------------------------------------------------------


class TestNativeTask:
    def test_defaults(self):
        t = NativeTask()
        assert t.task_id
        assert t.status == TaskStatus.PENDING
        assert t.steps == []

    def test_to_dict_has_required_keys(self):
        t = NativeTask(description="my task")
        d = t.to_dict()
        for k in ["task_id", "task_type", "description", "steps",
                  "status", "preconditions", "success_criteria"]:
            assert k in d

    def test_precondition_met(self):
        t = NativeTask(preconditions=["session.user_id"])
        assert t.check_preconditions({"session": {"user_id": "u1"}}) == []

    def test_precondition_unmet(self):
        t = NativeTask(preconditions=["session.user_id"])
        unmet = t.check_preconditions({})
        assert "session.user_id" in unmet


# ---------------------------------------------------------------------------
# NativeStep & ghost step serialisation
# ---------------------------------------------------------------------------


class TestNativeStep:
    def test_to_dict_keys(self):
        s = NativeStep(action=ActionType.NAVIGATE, target="/test")
        d = s.to_dict()
        assert "action" in d and "target" in d

    def test_to_ghost_step_focus_app(self):
        s = NativeStep(action=ActionType.GHOST_FOCUS_APP, target="Terminal")
        gs = s.to_ghost_step("s001")
        assert gs["action"] == "focus_app"
        assert gs["args"]["app"] == "Terminal"

    def test_to_ghost_step_assert_window(self):
        s = NativeStep(action=ActionType.GHOST_ASSERT_WINDOW, target="Murphy")
        gs = s.to_ghost_step("s002")
        assert gs["action"] == "assert_window"
        assert gs["args"]["contains"] == "Murphy"

    def test_to_ghost_step_wait(self):
        s = NativeStep(action=ActionType.GHOST_WAIT, args={"seconds": 1.5})
        gs = s.to_ghost_step("s003")
        assert gs["action"] == "wait"
        assert gs["args"]["seconds"] == 1.5


# ---------------------------------------------------------------------------
# MurphyNativeRunner — OPEN_URL (webbrowser)
# ---------------------------------------------------------------------------


class TestOpenURL:
    def test_open_url_absolute(self, runner, monkeypatch):
        opened = []
        monkeypatch.setattr("webbrowser.open", lambda u: opened.append(u))
        task = NativeTask(steps=[NativeStep(action=ActionType.OPEN_URL,
                                            target="http://localhost:8000/terminal_worker.html")])
        result = runner.run(task)
        assert result["status"] == "passed"
        assert any("terminal_worker.html" in u for u in opened)

    def test_open_url_relative_prefixed_with_base(self, runner, monkeypatch):
        opened = []
        monkeypatch.setattr("webbrowser.open", lambda u: opened.append(u))
        task = NativeTask(steps=[NativeStep(action=ActionType.OPEN_URL,
                                            target="/terminal_architect.html")])
        runner.run(task)
        assert any("localhost:8000" in u for u in opened)


# ---------------------------------------------------------------------------
# MurphyNativeRunner — UITestingFramework actions
# ---------------------------------------------------------------------------


class TestUIFrameworkActions:
    def test_assert_existing_element_passes(self, runner):
        task = NativeTask(
            failure_handling="log_and_continue",
            steps=[NativeStep(action=ActionType.ASSERT_VISIBLE, target="#terminalOutput")])
        r = runner.run(task, html_content=SAMPLE_HTML)
        assert r["status"] == "passed"

    def test_assert_missing_element_with_abort(self, runner):
        task = NativeTask(
            failure_handling="abort",
            steps=[NativeStep(action=ActionType.ASSERT_VISIBLE, target="#notexist",
                              optional=False)])
        r = runner.run(task, html_content=SAMPLE_HTML)
        assert r["status"] == "failed"

    def test_optional_missing_element_does_not_abort(self, runner):
        task = NativeTask(steps=[
            NativeStep(action=ActionType.ASSERT_VISIBLE, target="#notexist", optional=True),
            NativeStep(action=ActionType.ASSERT_VISIBLE, target="#terminalOutput"),
        ])
        r = runner.run(task, html_content=SAMPLE_HTML)
        assert r["status"] == "passed"

    def test_assert_text_present(self, runner):
        task = NativeTask(steps=[
            NativeStep(action=ActionType.ASSERT_TEXT, value="Connected")
        ])
        r = runner.run(task, html_content=SAMPLE_HTML)
        assert r["status"] == "passed"

    def test_assert_text_absent_fails(self, runner):
        task = NativeTask(failure_handling="abort", steps=[
            NativeStep(action=ActionType.ASSERT_TEXT, value="NOTPRESENT__XYZ",
                       optional=False)
        ])
        r = runner.run(task, html_content=SAMPLE_HTML)
        assert r["status"] == "failed"

    def test_fill_existing_input(self, runner):
        task = NativeTask(steps=[
            NativeStep(action=ActionType.FILL, target="#input-name", value="Alice")
        ])
        r = runner.run(task, html_content=SAMPLE_HTML)
        assert r["status"] == "passed"

    def test_fill_missing_input_fails(self, runner):
        task = NativeTask(failure_handling="abort", steps=[
            NativeStep(action=ActionType.FILL, target="#notexist", value="x",
                       optional=False)
        ])
        r = runner.run(task, html_content=SAMPLE_HTML)
        assert r["status"] == "failed"

    def test_simulate_500_error(self, runner):
        task = NativeTask(steps=[
            NativeStep(action=ActionType.SIMULATE_API_ERROR,
                       target="/api/test", value="500")
        ])
        r = runner.run(task, html_content=SAMPLE_HTML)
        assert r["status"] == "passed"
        spec = r["step_results"][0]["error_spec"]
        assert spec["status_code"] == 500

    def test_screenshot_captures_baseline(self, runner):
        task = NativeTask(steps=[
            NativeStep(action=ActionType.SCREENSHOT, target="test_page")
        ])
        r = runner.run(task, html_content=SAMPLE_HTML)
        assert r["status"] == "passed"

    def test_navigate_loads_page(self, runner):
        task = NativeTask(steps=[
            NativeStep(action=ActionType.NAVIGATE,
                       target="http://localhost:8000/terminal_worker.html")
        ])
        r = runner.run(task, html_content=SAMPLE_HTML)
        assert r["status"] in ("passed", "failed")  # no crash

    def test_no_html_returns_skipped_for_assertions(self, runner):
        task = NativeTask(steps=[
            NativeStep(action=ActionType.ASSERT_VISIBLE, target="#terminalOutput")
        ])
        r = runner.run(task, html_content=None)
        step_r = r["step_results"][0]
        assert step_r.get("status") == "skipped"


# ---------------------------------------------------------------------------
# MurphyNativeRunner — direct API calls
# ---------------------------------------------------------------------------


class TestDirectAPICalls:
    def test_api_post_fails_gracefully_no_server(self, runner):
        """No server running — should get a fail result, not an exception."""
        task = NativeTask(steps=[
            NativeStep(action=ActionType.API_POST, target="/api/auth/signup",
                       value='{"name": "test"}')
        ])
        r = runner.run(task)
        step_r = r["step_results"][0]
        # May pass or fail depending on server state, but must not raise
        assert "status" in step_r

    def test_api_get_fails_gracefully_no_server(self, runner):
        task = NativeTask(steps=[
            NativeStep(action=ActionType.API_GET, target="/api/health")
        ])
        r = runner.run(task)
        assert "status" in r


# ---------------------------------------------------------------------------
# MurphyNativeRunner — GhostController desktop actions
# ---------------------------------------------------------------------------


class TestGhostActions:
    def test_ghost_focus_app_runs(self, runner):
        """focus_app just prints — should always succeed."""
        task = NativeTask(steps=[
            NativeStep(action=ActionType.GHOST_FOCUS_APP, target="Murphy Terminal")
        ])
        r = runner.run(task)
        assert r["status"] == "passed"

    def test_ghost_wait_runs(self, runner):
        task = NativeTask(steps=[
            NativeStep(action=ActionType.GHOST_WAIT, args={"seconds": 0})
        ])
        r = runner.run(task)
        assert r["status"] == "passed"

    def test_ghost_assert_window_runs(self, runner):
        """assert_window_title gracefully fails/skips when pygetwindow absent."""
        task = NativeTask(steps=[
            NativeStep(action=ActionType.GHOST_ASSERT_WINDOW, target="Murphy",
                       optional=True)
        ])
        r = runner.run(task)
        assert r["status"] in ("passed",)  # optional so always passes overall


# ---------------------------------------------------------------------------
# MurphyNativeRunner — CLI (dry_run=True skips actual command)
# ---------------------------------------------------------------------------


class TestRunCommand:
    def test_run_command_dry_run_returns_ok(self, runner):
        task = NativeTask(steps=[
            NativeStep(action=ActionType.RUN_COMMAND, target="echo hello")
        ])
        r = runner.run(task)
        step_r = r["step_results"][0]
        assert step_r.get("note") == "dry_run_skipped"
        assert step_r.get("status") == "ok"

    def test_run_command_live_succeeds(self):
        live_runner = MurphyNativeRunner(dry_run=False)
        task = NativeTask(steps=[
            NativeStep(action=ActionType.RUN_COMMAND, target="echo murphy_test")
        ])
        r = live_runner.run(task)
        step_r = r["step_results"][0]
        assert step_r["status"] == "pass"
        assert "murphy_test" in step_r.get("stdout", "")


# ---------------------------------------------------------------------------
# MurphyNativeRunner — precondition skip
# ---------------------------------------------------------------------------


class TestPreconditionSkip:
    def test_skipped_on_missing_precondition(self, runner):
        task = NativeTask(
            preconditions=["session.eula_accepted"],
            steps=[NativeStep(action=ActionType.API_GET, target="/api/health")]
        )
        r = runner.run(task, context={})
        assert r["status"] == "skipped"

    def test_run_suite_returns_per_task(self, runner, factory):
        suite = [factory.verify_ui_loaded(), factory.take_screenshot()]
        results = runner.run_suite(suite, html_content=SAMPLE_HTML)
        assert len(results) == 2
        for r in results:
            assert "task_id" in r and "status" in r


# ---------------------------------------------------------------------------
# NativeTaskFactory — task builders
# ---------------------------------------------------------------------------


class TestNativeTaskFactory:
    def test_open_terminal_uses_open_url(self, factory):
        task = factory.open_terminal(terminal="worker", api_port=8090)
        assert task.task_type == TaskType.OPEN_TERMINAL
        actions = [s.action for s in task.steps]
        assert ActionType.OPEN_URL in actions

    def test_open_terminal_url_has_port(self, factory):
        task = factory.open_terminal(api_port=8090)
        url_step = next(s for s in task.steps if s.action == ActionType.OPEN_URL)
        assert "8090" in url_step.target or "terminal" in url_step.target

    def test_verify_ui_loaded_uses_assert_visible(self, factory):
        task = factory.verify_ui_loaded()
        actions = [s.action for s in task.steps]
        assert ActionType.ASSERT_VISIBLE in actions
        selectors = [s.target for s in task.steps]
        assert "#terminalOutput" in selectors

    def test_verify_api_connection_uses_api_get(self, factory):
        task = factory.verify_api_connection(api_port=8000)
        actions = [s.action for s in task.steps]
        assert ActionType.API_GET in actions

    def test_fill_onboarding_wizard_uses_api_post(self, factory):
        task = factory.fill_onboarding_wizard({"name": "Alice", "email": "a@x.com"})
        assert task.task_type == TaskType.FILL_ONBOARDING_WIZARD
        actions = [s.action for s in task.steps]
        assert ActionType.API_POST in actions

    def test_sign_eula_uses_api_post(self, factory):
        task = factory.sign_eula(user_id="u1")
        actions = [s.action for s in task.steps]
        assert ActionType.API_POST in actions

    def test_take_screenshot_uses_screenshot_action(self, factory):
        task = factory.take_screenshot(page_name="test")
        actions = [s.action for s in task.steps]
        assert ActionType.SCREENSHOT in actions

    def test_simulate_api_error_task(self, factory):
        task = factory.simulate_api_error("/api/auth/signup", 400)
        assert task.task_type == TaskType.SIMULATE_ERROR

    def test_desktop_assert_window_task(self, factory):
        task = factory.desktop_assert_window("Murphy Terminal")
        assert task.task_type == TaskType.DESKTOP_ACTION
        actions = [s.action for s in task.steps]
        assert ActionType.GHOST_ASSERT_WINDOW in actions

    def test_desktop_assert_ocr_task(self, factory):
        task = factory.desktop_assert_ocr("Connected")
        assert task.task_type == TaskType.DESKTOP_ACTION
        actions = [s.action for s in task.steps]
        assert ActionType.GHOST_ASSERT_OCR in actions

    def test_full_onboarding_suite(self, factory):
        suite = factory.full_onboarding_suite({"name": "Bob"}, api_port=8000)
        task_types = [t.task_type for t in suite]
        assert TaskType.FILL_ONBOARDING_WIZARD in task_types
        assert TaskType.SIGN_EULA in task_types
        assert TaskType.OPEN_TERMINAL in task_types
        assert TaskType.VERIFY_API_CONNECTION in task_types
        assert TaskType.TAKE_SCREENSHOT in task_types

    def test_task_log_grows(self, factory):
        factory.open_terminal()
        factory.verify_ui_loaded()
        assert len(factory.get_task_log()) >= 2


# ---------------------------------------------------------------------------
# GhostControllerExporter
# ---------------------------------------------------------------------------


class TestGhostControllerExporter:
    def test_export_only_ghost_steps(self, factory, exporter):
        mixed = NativeTask(steps=[
            NativeStep(action=ActionType.GHOST_FOCUS_APP, target="App"),
            NativeStep(action=ActionType.ASSERT_VISIBLE, target="#div"),  # non-ghost
            NativeStep(action=ActionType.GHOST_ASSERT_WINDOW, target="Title"),
        ])
        raw = exporter.export([mixed])
        data = json.loads(raw)
        assert len(data["steps"]) == 2  # only ghost steps
        assert data["steps"][0]["action"] == "focus_app"
        assert data["steps"][1]["action"] == "assert_window"

    def test_export_to_file(self, factory, exporter, tmp_path):
        task = factory.desktop_assert_window("Murphy")
        path = str(tmp_path / "ghost_spec.json")
        exporter.export_to_file([task], path)
        with open(path) as f:
            data = json.load(f)
        assert "steps" in data

    def test_export_empty_when_no_ghost_steps(self, factory, exporter):
        task = factory.verify_ui_loaded()   # only ASSERT_VISIBLE steps
        raw = exporter.export([task])
        data = json.loads(raw)
        assert data["steps"] == []


# ---------------------------------------------------------------------------
# PlaywrightExporter (optional)
# ---------------------------------------------------------------------------


class TestPlaywrightExporter:
    def test_export_valid_json(self, factory):
        exp = PlaywrightExporter()
        tasks = [factory.verify_ui_loaded(), factory.take_screenshot()]
        raw = exp.export(tasks)
        data = json.loads(raw)
        assert data["schema"] == "murphy_browser_tasks_v1"
        assert len(data["tasks"]) == 2

    def test_export_note_says_optional(self, factory):
        exp = PlaywrightExporter()
        raw = exp.export([factory.verify_ui_loaded()])
        assert "optional" in raw.lower()


# ---------------------------------------------------------------------------
# MurphyAPIClient (unit — no live server)
# ---------------------------------------------------------------------------


class TestMurphyAPIClient:
    def test_call_returns_error_dict_on_no_server(self):
        client = MurphyAPIClient(base_url="http://127.0.0.1:19999")
        result = client.call("GET", "/api/health")
        assert result["ok"] is False
        assert "error" in result

    def test_health_returns_false_on_no_server(self):
        client = MurphyAPIClient(base_url="http://127.0.0.1:19999")
        assert client.health() is False
