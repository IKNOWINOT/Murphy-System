"""
Murphy CLI v2 — Tests for new command modules
===============================================

Tests for the five new command modules added in CLI v2:
- mcb (MultiCursorBrowser) — 8 commands
- split (Split-screen orchestration) — 3 commands
- automate (Native automation) — 3 commands
- diagnose (Self-diagnostics) — 3 commands
- commission (Module commissioning) — 3 commands

Test label: CLI-TEST-V2-001

Commissioning checklist:
  ☑ Does the module do what it was designed to do?
  ☑ What conditions are possible based on the module?
  ☑ Does the test profile reflect the full range of capabilities?
  ☑ What is the expected result at all points of operation?
  ☑ Has hardening been applied?

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post · License: BSL 1.1
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Test helpers  (CLI-TEST-V2-HELPERS-001)
# ---------------------------------------------------------------------------

def _make_response(
    success: bool = True,
    status_code: int = 200,
    data: Any = None,
    error_code: str = None,
    error_message: str = None,
) -> MagicMock:
    """Create a mock APIResponse.  (CLI-TEST-V2-HELPERS-001)"""
    resp = MagicMock()
    resp.success = success
    resp.status_code = status_code
    resp.data = data if data is not None else {}
    resp.error_code = error_code
    resp.error_message = error_message
    return resp


def _make_ctx(
    api_key: str = "test_key_123456789",
    api_url: str = "http://localhost:8000",
) -> dict:
    """Create a mock execution context.  (CLI-TEST-V2-HELPERS-002)"""
    from murphy_cli.client import MurphyClient
    from murphy_cli.config import CLIConfig

    tmp = tempfile.mktemp(suffix=".json")
    config = CLIConfig(config_path=Path(tmp))
    if api_key:
        config.set("api_key", api_key)

    client = MagicMock(spec=MurphyClient)
    client.api_key = api_key
    client.base_url = api_url

    return {"client": client, "config": config, "api_url": api_url}


# ===========================================================================
# 1. MCB Command Tests  (CLI-TEST-V2-MCB-001)
# ===========================================================================


class TestMCBCommands:
    """MultiCursorBrowser command handler tests.  (CLI-TEST-V2-MCB-001)"""

    def test_mcb_launch_success(self):
        """MCB launch returns session + zones.  (CLI-TEST-V2-MCB-LAUNCH-001)"""
        from murphy_cli.commands.mcb import _cmd_mcb_launch
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        ctx["client"].post.return_value = _make_response(
            success=True,
            data={
                "session_id": "ses_abc123",
                "zones": [
                    {"zone_id": "z0", "name": "Zone 0", "width": 960, "height": 1080, "label": "Left"},
                    {"zone_id": "z1", "name": "Zone 1", "width": 960, "height": 1080, "label": "Right"},
                ],
            },
        )
        parsed = parse_args(["mcb", "launch", "--layout", "dual_h"])
        result = _cmd_mcb_launch(parsed, ctx)
        assert result == 0
        ctx["client"].post.assert_called_once()
        call_args = ctx["client"].post.call_args
        assert call_args[0][0] == "/api/mcb/launch"

    def test_mcb_launch_failure(self):
        """MCB launch handles API error.  (CLI-TEST-V2-MCB-LAUNCH-ERR-001)"""
        from murphy_cli.commands.mcb import _cmd_mcb_launch
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        ctx["client"].post.return_value = _make_response(
            success=False, error_message="Browser not available"
        )
        parsed = parse_args(["mcb", "launch"])
        result = _cmd_mcb_launch(parsed, ctx)
        assert result == 1

    def test_mcb_launch_dry_run(self):
        """MCB launch dry-run doesn't call API.  (CLI-TEST-V2-MCB-LAUNCH-DRY-001)"""
        from murphy_cli.commands.mcb import _cmd_mcb_launch
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        parsed = parse_args(["--dry-run", "mcb", "launch", "--layout", "quad"])
        result = _cmd_mcb_launch(parsed, ctx)
        assert result == 0
        ctx["client"].post.assert_not_called()

    def test_mcb_launch_json_output(self):
        """MCB launch with --output json.  (CLI-TEST-V2-MCB-LAUNCH-JSON-001)"""
        from murphy_cli.commands.mcb import _cmd_mcb_launch
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        ctx["client"].post.return_value = _make_response(
            success=True,
            data={"session_id": "ses_abc123", "zones": []},
        )
        parsed = parse_args(["--output", "json", "mcb", "launch"])
        result = _cmd_mcb_launch(parsed, ctx)
        assert result == 0

    def test_mcb_zones_success(self):
        """MCB zones lists zones.  (CLI-TEST-V2-MCB-ZONES-001)"""
        from murphy_cli.commands.mcb import _cmd_mcb_zones
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        ctx["client"].get.return_value = _make_response(
            success=True,
            data=[
                {"zone_id": "z0", "name": "Left", "x": 0, "y": 0, "width": 960, "height": 1080, "cursor_id": "c0", "label": "A"},
            ],
        )
        parsed = parse_args(["mcb", "zones"])
        result = _cmd_mcb_zones(parsed, ctx)
        assert result == 0

    def test_mcb_zones_empty(self):
        """MCB zones handles empty list.  (CLI-TEST-V2-MCB-ZONES-EMPTY-001)"""
        from murphy_cli.commands.mcb import _cmd_mcb_zones
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        ctx["client"].get.return_value = _make_response(success=True, data=[])
        parsed = parse_args(["mcb", "zones"])
        result = _cmd_mcb_zones(parsed, ctx)
        assert result == 0

    def test_mcb_zones_failure(self):
        """MCB zones handles error.  (CLI-TEST-V2-MCB-ZONES-ERR-001)"""
        from murphy_cli.commands.mcb import _cmd_mcb_zones
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        ctx["client"].get.return_value = _make_response(
            success=False, error_message="Not connected"
        )
        parsed = parse_args(["mcb", "zones"])
        result = _cmd_mcb_zones(parsed, ctx)
        assert result == 1

    def test_mcb_navigate_success(self):
        """MCB navigate sends zone + url.  (CLI-TEST-V2-MCB-NAV-001)"""
        from murphy_cli.commands.mcb import _cmd_mcb_navigate
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        ctx["client"].post.return_value = _make_response(success=True)
        parsed = parse_args(["mcb", "navigate", "--zone", "z0", "--url", "https://example.com"])
        result = _cmd_mcb_navigate(parsed, ctx)
        assert result == 0

    def test_mcb_navigate_missing_params(self):
        """MCB navigate requires zone + url.  (CLI-TEST-V2-MCB-NAV-MISS-001)"""
        from murphy_cli.commands.mcb import _cmd_mcb_navigate
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        parsed = parse_args(["mcb", "navigate"])
        result = _cmd_mcb_navigate(parsed, ctx)
        assert result == 1

    def test_mcb_screenshot_success(self):
        """MCB screenshot works.  (CLI-TEST-V2-MCB-SCREEN-001)"""
        from murphy_cli.commands.mcb import _cmd_mcb_screenshot
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        ctx["client"].post.return_value = _make_response(
            success=True, data={"path": "./screenshot.png"}
        )
        parsed = parse_args(["mcb", "screenshot", "--zone", "all"])
        result = _cmd_mcb_screenshot(parsed, ctx)
        assert result == 0

    def test_mcb_run_with_task(self):
        """MCB run with --task file.  (CLI-TEST-V2-MCB-RUN-001)"""
        from murphy_cli.commands.mcb import _cmd_mcb_run
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        ctx["client"].post.return_value = _make_response(
            success=True,
            data={
                "status": "passed",
                "steps_executed": 3,
                "steps_total": 3,
                "results": [
                    {"step": 1, "action": "navigate", "status": "passed", "duration_ms": 120},
                    {"step": 2, "action": "click", "status": "passed", "duration_ms": 50},
                    {"step": 3, "action": "assert_text", "status": "passed", "duration_ms": 10},
                ],
            },
        )
        parsed = parse_args(["mcb", "run", "--task", "test.json"])
        result = _cmd_mcb_run(parsed, ctx)
        assert result == 0

    def test_mcb_run_with_steps(self):
        """MCB run with --steps inline.  (CLI-TEST-V2-MCB-RUN-STEPS-001)"""
        from murphy_cli.commands.mcb import _cmd_mcb_run
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        ctx["client"].post.return_value = _make_response(
            success=True,
            data={"status": "passed", "steps_executed": 1, "steps_total": 1, "results": []},
        )
        parsed = parse_args(["mcb", "run", "--steps", "navigate:https://example.com"])
        result = _cmd_mcb_run(parsed, ctx)
        assert result == 0

    def test_mcb_run_missing_args(self):
        """MCB run requires --task or --steps.  (CLI-TEST-V2-MCB-RUN-MISS-001)"""
        from murphy_cli.commands.mcb import _cmd_mcb_run
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        parsed = parse_args(["mcb", "run"])
        result = _cmd_mcb_run(parsed, ctx)
        assert result == 1

    def test_mcb_record_success(self):
        """MCB record starts recording.  (CLI-TEST-V2-MCB-RECORD-001)"""
        from murphy_cli.commands.mcb import _cmd_mcb_record
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        ctx["client"].post.return_value = _make_response(success=True)
        parsed = parse_args(["mcb", "record", "--zone", "0", "--out", "rec.json"])
        result = _cmd_mcb_record(parsed, ctx)
        assert result == 0

    def test_mcb_replay_success(self):
        """MCB replay runs task file.  (CLI-TEST-V2-MCB-REPLAY-001)"""
        from murphy_cli.commands.mcb import _cmd_mcb_replay
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        ctx["client"].post.return_value = _make_response(
            success=True, data={"status": "completed"}
        )
        parsed = parse_args(["mcb", "replay", "--task", "rec.json"])
        result = _cmd_mcb_replay(parsed, ctx)
        assert result == 0

    def test_mcb_replay_missing_task(self):
        """MCB replay requires --task.  (CLI-TEST-V2-MCB-REPLAY-MISS-001)"""
        from murphy_cli.commands.mcb import _cmd_mcb_replay
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        parsed = parse_args(["mcb", "replay"])
        result = _cmd_mcb_replay(parsed, ctx)
        assert result == 1

    def test_mcb_close_success(self):
        """MCB close terminates session.  (CLI-TEST-V2-MCB-CLOSE-001)"""
        from murphy_cli.commands.mcb import _cmd_mcb_close
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        ctx["client"].post.return_value = _make_response(success=True)
        parsed = parse_args(["mcb", "close"])
        result = _cmd_mcb_close(parsed, ctx)
        assert result == 0

    def test_mcb_close_failure(self):
        """MCB close handles error.  (CLI-TEST-V2-MCB-CLOSE-ERR-001)"""
        from murphy_cli.commands.mcb import _cmd_mcb_close
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        ctx["client"].post.return_value = _make_response(
            success=False, error_message="No session"
        )
        parsed = parse_args(["mcb", "close"])
        result = _cmd_mcb_close(parsed, ctx)
        assert result == 1


# ===========================================================================
# 2. Split-Screen Command Tests  (CLI-TEST-V2-SPLIT-001)
# ===========================================================================


class TestSplitCommands:
    """Split-screen command handler tests.  (CLI-TEST-V2-SPLIT-001)"""

    def test_split_run_with_zone_tasks(self):
        """Split run with --left and --right flags.  (CLI-TEST-V2-SPLIT-RUN-001)"""
        from murphy_cli.commands.split import _cmd_split_run
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        ctx["client"].post.return_value = _make_response(
            success=True,
            data={
                "session_id": "split_001",
                "zone_count": 2,
                "results": {
                    "left": {"status": "passed", "tasks_run": 1, "duration_ms": 200},
                    "right": {"status": "passed", "tasks_run": 1, "duration_ms": 150},
                },
            },
        )
        parsed = parse_args([
            "split", "run", "--layout", "dual_h",
            "--left", "api health check",
            "--right", "form test",
        ])
        result = _cmd_split_run(parsed, ctx)
        assert result == 0

    def test_split_run_with_config(self):
        """Split run with --config file.  (CLI-TEST-V2-SPLIT-RUN-CFG-001)"""
        from murphy_cli.commands.split import _cmd_split_run
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        ctx["client"].post.return_value = _make_response(
            success=True,
            data={"session_id": "s2", "zone_count": 4, "results": {}},
        )
        parsed = parse_args(["split", "run", "--config", "zones.json"])
        result = _cmd_split_run(parsed, ctx)
        assert result == 0

    def test_split_run_missing_args(self):
        """Split run requires zone tasks or config.  (CLI-TEST-V2-SPLIT-RUN-MISS-001)"""
        from murphy_cli.commands.split import _cmd_split_run
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        parsed = parse_args(["split", "run"])
        result = _cmd_split_run(parsed, ctx)
        assert result == 1

    def test_split_run_dry_run(self):
        """Split run dry-run.  (CLI-TEST-V2-SPLIT-RUN-DRY-001)"""
        from murphy_cli.commands.split import _cmd_split_run
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        parsed = parse_args(["--dry-run", "split", "run", "--left", "test"])
        result = _cmd_split_run(parsed, ctx)
        assert result == 0
        ctx["client"].post.assert_not_called()

    def test_split_run_failure(self):
        """Split run handles API error.  (CLI-TEST-V2-SPLIT-RUN-ERR-001)"""
        from murphy_cli.commands.split import _cmd_split_run
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        ctx["client"].post.return_value = _make_response(
            success=False, error_message="Zone allocation failed"
        )
        parsed = parse_args(["split", "run", "--left", "test"])
        result = _cmd_split_run(parsed, ctx)
        assert result == 1

    def test_split_status_success(self):
        """Split status shows zones.  (CLI-TEST-V2-SPLIT-STATUS-001)"""
        from murphy_cli.commands.split import _cmd_split_status
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        ctx["client"].get.return_value = _make_response(
            success=True,
            data={
                "state": "active",
                "layout": "dual_h",
                "zones": [
                    {"zone_id": "z0", "state": "running", "cursor_id": "c0", "tasks_queued": 2, "tasks_completed": 1},
                ],
            },
        )
        parsed = parse_args(["split", "status"])
        result = _cmd_split_status(parsed, ctx)
        assert result == 0

    def test_split_status_empty(self):
        """Split status no zones.  (CLI-TEST-V2-SPLIT-STATUS-EMPTY-001)"""
        from murphy_cli.commands.split import _cmd_split_status
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        ctx["client"].get.return_value = _make_response(
            success=True,
            data={"state": "idle", "layout": "—", "zones": []},
        )
        parsed = parse_args(["split", "status"])
        result = _cmd_split_status(parsed, ctx)
        assert result == 0

    def test_split_coordinate_success(self):
        """Split coordinate runs full pipeline.  (CLI-TEST-V2-SPLIT-COORD-001)"""
        from murphy_cli.commands.split import _cmd_split_coordinate
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        ctx["client"].post.return_value = _make_response(
            success=True,
            data={
                "triage": {"z0": {"severity": "high", "confidence": 0.9}},
                "evidence": {"z0": {"verdict": "pass", "detail": "Monte Carlo OK"}},
                "summary": "All zones dispatched successfully.",
            },
        )
        parsed = parse_args(["split", "coordinate", "--config", "multi.json"])
        result = _cmd_split_coordinate(parsed, ctx)
        assert result == 0

    def test_split_coordinate_missing_config(self):
        """Split coordinate requires --config.  (CLI-TEST-V2-SPLIT-COORD-MISS-001)"""
        from murphy_cli.commands.split import _cmd_split_coordinate
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        parsed = parse_args(["split", "coordinate"])
        result = _cmd_split_coordinate(parsed, ctx)
        assert result == 1

    def test_split_coordinate_failure(self):
        """Split coordinate handles error.  (CLI-TEST-V2-SPLIT-COORD-ERR-001)"""
        from murphy_cli.commands.split import _cmd_split_coordinate
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        ctx["client"].post.return_value = _make_response(
            success=False, error_message="Triage engine unavailable"
        )
        parsed = parse_args(["split", "coordinate", "--config", "x.json"])
        result = _cmd_split_coordinate(parsed, ctx)
        assert result == 1


# ===========================================================================
# 3. Automate Command Tests  (CLI-TEST-V2-AUTOMATE-001)
# ===========================================================================


class TestAutomateCommands:
    """Native automation command handler tests.  (CLI-TEST-V2-AUTOMATE-001)"""

    def test_automate_api_success(self):
        """Automate API call works.  (CLI-TEST-V2-AUTOMATE-API-001)"""
        from murphy_cli.commands.automate import _cmd_automate_api
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        ctx["client"].post.return_value = _make_response(
            success=True,
            data={"status_code": 200, "duration_ms": 45, "response_body": '{"status":"ok"}'},
        )
        parsed = parse_args(["automate", "api", "--method", "GET", "--url", "/api/health"])
        result = _cmd_automate_api(parsed, ctx)
        assert result == 0

    def test_automate_api_missing_url(self):
        """Automate API requires --url.  (CLI-TEST-V2-AUTOMATE-API-MISS-001)"""
        from murphy_cli.commands.automate import _cmd_automate_api
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        parsed = parse_args(["automate", "api"])
        result = _cmd_automate_api(parsed, ctx)
        assert result == 1

    def test_automate_api_dry_run(self):
        """Automate API dry-run.  (CLI-TEST-V2-AUTOMATE-API-DRY-001)"""
        from murphy_cli.commands.automate import _cmd_automate_api
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        parsed = parse_args(["--dry-run", "automate", "api", "--url", "/api/health"])
        result = _cmd_automate_api(parsed, ctx)
        assert result == 0
        ctx["client"].post.assert_not_called()

    def test_automate_api_json_output(self):
        """Automate API JSON output.  (CLI-TEST-V2-AUTOMATE-API-JSON-001)"""
        from murphy_cli.commands.automate import _cmd_automate_api
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        ctx["client"].post.return_value = _make_response(
            success=True, data={"status_code": 200, "duration_ms": 30}
        )
        parsed = parse_args(["--output", "json", "automate", "api", "--url", "/api/test"])
        result = _cmd_automate_api(parsed, ctx)
        assert result == 0

    def test_automate_api_failure(self):
        """Automate API handles error.  (CLI-TEST-V2-AUTOMATE-API-ERR-001)"""
        from murphy_cli.commands.automate import _cmd_automate_api
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        ctx["client"].post.return_value = _make_response(
            success=False, error_message="Connection refused"
        )
        parsed = parse_args(["automate", "api", "--url", "/api/health"])
        result = _cmd_automate_api(parsed, ctx)
        assert result == 1

    def test_automate_desktop_success(self):
        """Automate desktop action works.  (CLI-TEST-V2-AUTOMATE-DESK-001)"""
        from murphy_cli.commands.automate import _cmd_automate_desktop
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        ctx["client"].post.return_value = _make_response(
            success=True,
            data={"status": "completed"},
        )
        parsed = parse_args(["automate", "desktop", "--action", "click", "--target", "Submit"])
        result = _cmd_automate_desktop(parsed, ctx)
        assert result == 0

    def test_automate_desktop_missing_action(self):
        """Automate desktop requires --action.  (CLI-TEST-V2-AUTOMATE-DESK-MISS-001)"""
        from murphy_cli.commands.automate import _cmd_automate_desktop
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        parsed = parse_args(["automate", "desktop"])
        result = _cmd_automate_desktop(parsed, ctx)
        assert result == 1

    def test_automate_batch_success(self):
        """Automate batch runs tasks.  (CLI-TEST-V2-AUTOMATE-BATCH-001)"""
        from murphy_cli.commands.automate import _cmd_automate_batch
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        ctx["client"].post.return_value = _make_response(
            success=True,
            data={
                "total": 3,
                "passed": 2,
                "failed": 1,
                "results": [
                    {"description": "Check health", "status": "passed", "duration_ms": 50},
                    {"description": "Submit form", "status": "passed", "duration_ms": 120},
                    {"description": "OCR verify", "status": "failed", "duration_ms": 300},
                ],
            },
        )
        parsed = parse_args(["automate", "batch", "--tasks", "batch.json"])
        result = _cmd_automate_batch(parsed, ctx)
        assert result == 0

    def test_automate_batch_missing_file(self):
        """Automate batch requires --tasks.  (CLI-TEST-V2-AUTOMATE-BATCH-MISS-001)"""
        from murphy_cli.commands.automate import _cmd_automate_batch
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        parsed = parse_args(["automate", "batch"])
        result = _cmd_automate_batch(parsed, ctx)
        assert result == 1


# ===========================================================================
# 4. Diagnose Command Tests  (CLI-TEST-V2-DIAGNOSE-001)
# ===========================================================================


class TestDiagnoseCommands:
    """Self-diagnostics command handler tests.  (CLI-TEST-V2-DIAGNOSE-001)"""

    def test_diagnose_symptom_success(self):
        """Diagnose symptom traces root cause.  (CLI-TEST-V2-DIAGNOSE-SYM-001)"""
        from murphy_cli.commands.diagnose import _cmd_diagnose_symptom
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        ctx["client"].post.return_value = _make_response(
            success=True,
            data={
                "root_causes": [
                    {"module": "llm_provider", "description": "API key not set", "confidence": "high"},
                ],
                "affected_modules": ["llm_provider", "demo_deliverable_generator"],
                "validation_chain": [
                    {"check": "API key present", "expected": "set", "actual": "empty", "passed": False},
                    {"check": "LLM reachable", "expected": "200", "actual": "timeout", "passed": False},
                ],
                "remediation": [
                    "Set DEEPINFRA_API_KEY in .env or environment",
                    "Run: murphy diagnose drift to confirm config",
                ],
            },
        )
        parsed = parse_args(["diagnose", "symptom", "--symptom", "forge returns empty deliverable"])
        result = _cmd_diagnose_symptom(parsed, ctx)
        assert result == 0

    def test_diagnose_symptom_positional(self):
        """Diagnose symptom from positional args.  (CLI-TEST-V2-DIAGNOSE-SYM-POS-001)"""
        from murphy_cli.commands.diagnose import _cmd_diagnose_symptom
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        ctx["client"].post.return_value = _make_response(
            success=True, data={"root_causes": [], "validation_chain": []}
        )
        parsed = parse_args(["diagnose", "symptom", "login", "fails", "500"])
        result = _cmd_diagnose_symptom(parsed, ctx)
        assert result == 0

    def test_diagnose_symptom_missing(self):
        """Diagnose symptom requires description.  (CLI-TEST-V2-DIAGNOSE-SYM-MISS-001)"""
        from murphy_cli.commands.diagnose import _cmd_diagnose_symptom
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        parsed = parse_args(["diagnose", "symptom"])
        result = _cmd_diagnose_symptom(parsed, ctx)
        assert result == 1

    def test_diagnose_symptom_dry_run(self):
        """Diagnose symptom dry-run.  (CLI-TEST-V2-DIAGNOSE-SYM-DRY-001)"""
        from murphy_cli.commands.diagnose import _cmd_diagnose_symptom
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        parsed = parse_args(["--dry-run", "diagnose", "symptom", "--symptom", "test issue"])
        result = _cmd_diagnose_symptom(parsed, ctx)
        assert result == 0
        ctx["client"].post.assert_not_called()

    def test_diagnose_pipeline_success(self):
        """Diagnose pipeline shows error tracker output.  (CLI-TEST-V2-DIAGNOSE-PIPE-001)"""
        from murphy_cli.commands.diagnose import _cmd_diagnose_pipeline
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        ctx["client"].get.return_value = _make_response(
            success=True,
            data={
                "errors": [
                    {"code": "FORGE-SWARM-ERR-003", "stage": "swarm_execution", "message": "Agent timeout", "fallback": "role_fallback"},
                ],
                "summary": "1 error, 1 fallback used. Deliverable generated.",
            },
        )
        parsed = parse_args(["diagnose", "pipeline", "--run-id", "run_abc123"])
        result = _cmd_diagnose_pipeline(parsed, ctx)
        assert result == 0

    def test_diagnose_pipeline_no_errors(self):
        """Diagnose pipeline with clean run.  (CLI-TEST-V2-DIAGNOSE-PIPE-CLEAN-001)"""
        from murphy_cli.commands.diagnose import _cmd_diagnose_pipeline
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        ctx["client"].get.return_value = _make_response(
            success=True, data={"errors": [], "summary": "Clean run."}
        )
        parsed = parse_args(["diagnose", "pipeline", "--run-id", "run_xyz"])
        result = _cmd_diagnose_pipeline(parsed, ctx)
        assert result == 0

    def test_diagnose_pipeline_missing_id(self):
        """Diagnose pipeline requires --run-id.  (CLI-TEST-V2-DIAGNOSE-PIPE-MISS-001)"""
        from murphy_cli.commands.diagnose import _cmd_diagnose_pipeline
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        parsed = parse_args(["diagnose", "pipeline"])
        result = _cmd_diagnose_pipeline(parsed, ctx)
        assert result == 1

    def test_diagnose_drift_all_pass(self):
        """Diagnose drift all checks pass.  (CLI-TEST-V2-DIAGNOSE-DRIFT-OK-001)"""
        from murphy_cli.commands.diagnose import _cmd_diagnose_drift
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        ctx["client"].get.return_value = _make_response(
            success=True,
            data={"tree_divergence_ok": True, "source_drift_ok": True},
        )
        parsed = parse_args(["diagnose", "drift"])
        result = _cmd_diagnose_drift(parsed, ctx)
        assert result == 0

    def test_diagnose_drift_with_issues(self):
        """Diagnose drift detects problems.  (CLI-TEST-V2-DIAGNOSE-DRIFT-FAIL-001)"""
        from murphy_cli.commands.diagnose import _cmd_diagnose_drift
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        ctx["client"].get.return_value = _make_response(
            success=True,
            data={
                "tree_divergence_ok": False,
                "source_drift_ok": True,
                "tree_divergence_files": ["src/new_module.py"],
            },
        )
        parsed = parse_args(["diagnose", "drift"])
        result = _cmd_diagnose_drift(parsed, ctx)
        assert result == 1

    def test_diagnose_drift_failure(self):
        """Diagnose drift handles API error.  (CLI-TEST-V2-DIAGNOSE-DRIFT-ERR-001)"""
        from murphy_cli.commands.diagnose import _cmd_diagnose_drift
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        ctx["client"].get.return_value = _make_response(
            success=False, error_message="Server error"
        )
        parsed = parse_args(["diagnose", "drift"])
        result = _cmd_diagnose_drift(parsed, ctx)
        assert result == 1


# ===========================================================================
# 5. Commission Command Tests  (CLI-TEST-V2-COMMISSION-001)
# ===========================================================================


class TestCommissionCommands:
    """Module commissioning command handler tests.  (CLI-TEST-V2-COMMISSION-001)"""

    def test_commission_run_pass(self):
        """Commission run passes a module.  (CLI-TEST-V2-COMMISSION-RUN-001)"""
        from murphy_cli.commands.commission import _cmd_commission_run
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        ctx["client"].post.return_value = _make_response(
            success=True,
            data={
                "status": "pass",
                "module": "forge",
                "checks": [
                    {"name": "Purpose verification", "passed": True, "detail": "All endpoints respond"},
                    {"name": "Error labeling", "passed": True, "detail": "98 codes found"},
                    {"name": "Test coverage", "passed": True, "detail": "94 tests"},
                ],
                "warnings": [],
            },
        )
        parsed = parse_args(["commission", "run", "--module", "forge"])
        result = _cmd_commission_run(parsed, ctx)
        assert result == 0

    def test_commission_run_warn(self):
        """Commission run with warnings.  (CLI-TEST-V2-COMMISSION-RUN-WARN-001)"""
        from murphy_cli.commands.commission import _cmd_commission_run
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        ctx["client"].post.return_value = _make_response(
            success=True,
            data={
                "status": "warn",
                "module": "llm",
                "checks": [
                    {"name": "Purpose", "passed": True, "detail": "OK"},
                    {"name": "Docs", "passed": False, "detail": "Missing changelog entry"},
                ],
                "warnings": ["Changelog not updated"],
            },
        )
        parsed = parse_args(["commission", "run", "--module", "llm"])
        result = _cmd_commission_run(parsed, ctx)
        assert result == 0  # warn still returns 0

    def test_commission_run_fail(self):
        """Commission run fails a module.  (CLI-TEST-V2-COMMISSION-RUN-FAIL-001)"""
        from murphy_cli.commands.commission import _cmd_commission_run
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        ctx["client"].post.return_value = _make_response(
            success=True,
            data={"status": "fail", "module": "broken", "checks": [], "warnings": []},
        )
        parsed = parse_args(["commission", "run", "--module", "broken"])
        result = _cmd_commission_run(parsed, ctx)
        assert result == 1

    def test_commission_run_missing_module(self):
        """Commission run requires --module.  (CLI-TEST-V2-COMMISSION-RUN-MISS-001)"""
        from murphy_cli.commands.commission import _cmd_commission_run
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        parsed = parse_args(["commission", "run"])
        result = _cmd_commission_run(parsed, ctx)
        assert result == 1

    def test_commission_run_dry_run(self):
        """Commission run dry-run.  (CLI-TEST-V2-COMMISSION-RUN-DRY-001)"""
        from murphy_cli.commands.commission import _cmd_commission_run
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        parsed = parse_args(["--dry-run", "commission", "run", "--module", "forge"])
        result = _cmd_commission_run(parsed, ctx)
        assert result == 0
        ctx["client"].post.assert_not_called()

    def test_commission_checklist_success(self):
        """Commission checklist shows items.  (CLI-TEST-V2-COMMISSION-CHECKLIST-001)"""
        from murphy_cli.commands.commission import _cmd_commission_checklist
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        ctx["client"].get.return_value = _make_response(
            success=True,
            data={
                "module": "forge",
                "items": [
                    {"description": "Does it do what it was designed to do?", "done": True},
                    {"description": "Test profile reflects full range?", "done": True},
                    {"description": "Hardening applied?", "done": False},
                ],
            },
        )
        parsed = parse_args(["commission", "checklist", "--module", "forge"])
        result = _cmd_commission_checklist(parsed, ctx)
        assert result == 0

    def test_commission_checklist_missing_module(self):
        """Commission checklist requires --module.  (CLI-TEST-V2-COMMISSION-CL-MISS-001)"""
        from murphy_cli.commands.commission import _cmd_commission_checklist
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        parsed = parse_args(["commission", "checklist"])
        result = _cmd_commission_checklist(parsed, ctx)
        assert result == 1

    def test_commission_verify_all(self):
        """Commission verify --all shows all modules.  (CLI-TEST-V2-COMMISSION-VER-001)"""
        from murphy_cli.commands.commission import _cmd_commission_verify
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        ctx["client"].get.return_value = _make_response(
            success=True,
            data={
                "modules": [
                    {"name": "forge", "status": "pass", "last_commissioned": "2026-04-11", "issue_count": 0},
                    {"name": "llm", "status": "pass", "last_commissioned": "2026-04-10", "issue_count": 0},
                    {"name": "auth", "status": "pass", "last_commissioned": "2026-04-09", "issue_count": 0},
                ],
            },
        )
        parsed = parse_args(["commission", "verify", "--all"])
        result = _cmd_commission_verify(parsed, ctx)
        assert result == 0

    def test_commission_verify_partial_fail(self):
        """Commission verify --all with failures returns 1.  (CLI-TEST-V2-COMMISSION-VER-FAIL-001)"""
        from murphy_cli.commands.commission import _cmd_commission_verify
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        ctx["client"].get.return_value = _make_response(
            success=True,
            data={
                "modules": [
                    {"name": "forge", "status": "pass", "last_commissioned": "2026-04-11", "issue_count": 0},
                    {"name": "broken", "status": "fail", "last_commissioned": "never", "issue_count": 5},
                ],
            },
        )
        parsed = parse_args(["commission", "verify", "--all"])
        result = _cmd_commission_verify(parsed, ctx)
        assert result == 1

    def test_commission_verify_missing_args(self):
        """Commission verify requires --all or --module.  (CLI-TEST-V2-COMMISSION-VER-MISS-001)"""
        from murphy_cli.commands.commission import _cmd_commission_verify
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        parsed = parse_args(["commission", "verify"])
        result = _cmd_commission_verify(parsed, ctx)
        assert result == 1

    def test_commission_verify_single_module(self):
        """Commission verify --module <name>.  (CLI-TEST-V2-COMMISSION-VER-SINGLE-001)"""
        from murphy_cli.commands.commission import _cmd_commission_verify
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        ctx["client"].get.return_value = _make_response(
            success=True,
            data={
                "modules": [
                    {"name": "forge", "status": "pass", "last_commissioned": "2026-04-11", "issue_count": 0},
                ],
            },
        )
        parsed = parse_args(["commission", "verify", "--module", "forge"])
        result = _cmd_commission_verify(parsed, ctx)
        assert result == 0


# ===========================================================================
# 6. Registration Tests  (CLI-TEST-V2-REGISTRATION-001)
# ===========================================================================


class TestV2Registration:
    """Verify all v2 modules register correctly.  (CLI-TEST-V2-REGISTRATION-001)"""

    def test_all_v2_resources_registered(self):
        """All five new resources appear in help.  (CLI-TEST-V2-REG-ALL-001)"""
        from murphy_cli.registry import CommandRegistry
        from murphy_cli.commands import register_all_commands

        registry = CommandRegistry()
        register_all_commands(registry)
        resources = registry.resources()

        assert "mcb" in resources, "mcb resource missing"
        assert "split" in resources, "split resource missing"
        assert "automate" in resources, "automate resource missing"
        assert "diagnose" in resources, "diagnose resource missing"
        assert "commission" in resources, "commission resource missing"

    def test_mcb_commands_registered(self):
        """MCB has 8 commands.  (CLI-TEST-V2-REG-MCB-001)"""
        from murphy_cli.registry import CommandRegistry
        from murphy_cli.commands import register_all_commands

        registry = CommandRegistry()
        register_all_commands(registry)
        mcb_cmds = [c for c in registry.all_commands() if c.resource == "mcb"]
        mcb_names = {c.name for c in mcb_cmds}
        assert mcb_names >= {"launch", "zones", "navigate", "screenshot", "run", "record", "replay", "close"}

    def test_split_commands_registered(self):
        """Split has 3 commands.  (CLI-TEST-V2-REG-SPLIT-001)"""
        from murphy_cli.registry import CommandRegistry
        from murphy_cli.commands import register_all_commands

        registry = CommandRegistry()
        register_all_commands(registry)
        split_cmds = [c for c in registry.all_commands() if c.resource == "split"]
        names = {c.name for c in split_cmds}
        assert names >= {"run", "status", "coordinate"}

    def test_automate_commands_registered(self):
        """Automate has 3 commands.  (CLI-TEST-V2-REG-AUTO-001)"""
        from murphy_cli.registry import CommandRegistry
        from murphy_cli.commands import register_all_commands

        registry = CommandRegistry()
        register_all_commands(registry)
        cmds = [c for c in registry.all_commands() if c.resource == "automate"]
        names = {c.name for c in cmds}
        assert names >= {"api", "desktop", "batch"}

    def test_diagnose_commands_registered(self):
        """Diagnose has 3 commands.  (CLI-TEST-V2-REG-DIAG-001)"""
        from murphy_cli.registry import CommandRegistry
        from murphy_cli.commands import register_all_commands

        registry = CommandRegistry()
        register_all_commands(registry)
        cmds = [c for c in registry.all_commands() if c.resource == "diagnose"]
        names = {c.name for c in cmds}
        assert names >= {"symptom", "pipeline", "drift"}

    def test_commission_commands_registered(self):
        """Commission has 3 commands.  (CLI-TEST-V2-REG-COMM-001)"""
        from murphy_cli.registry import CommandRegistry
        from murphy_cli.commands import register_all_commands

        registry = CommandRegistry()
        register_all_commands(registry)
        cmds = [c for c in registry.all_commands() if c.resource == "commission"]
        names = {c.name for c in cmds}
        assert names >= {"run", "checklist", "verify"}

    def test_v1_commands_still_present(self):
        """Original v1 commands still registered.  (CLI-TEST-V2-REG-V1-001)"""
        from murphy_cli.registry import CommandRegistry
        from murphy_cli.commands import register_all_commands

        registry = CommandRegistry()
        register_all_commands(registry)
        resources = registry.resources()
        for v1_res in ("auth", "chat", "forge", "agents", "automations", "hitl", "safety"):
            assert v1_res in resources, f"v1 resource '{v1_res}' missing after v2 registration"


# ===========================================================================
# 7. Main Entry Point Integration Tests  (CLI-TEST-V2-MAIN-001)
# ===========================================================================


class TestV2MainIntegration:
    """Verify new resources show in global help.  (CLI-TEST-V2-MAIN-001)"""

    def test_global_help_shows_v2_resources(self, capsys):
        """Global --help lists new resources.  (CLI-TEST-V2-MAIN-HELP-001)"""
        from murphy_cli.main import main
        from murphy_cli.output import set_no_color
        set_no_color(True)
        exit_code = main(["--help"])
        assert exit_code == 0
        out = capsys.readouterr().out
        assert "mcb" in out
        assert "split" in out
        assert "automate" in out
        assert "diagnose" in out
        assert "commission" in out
        set_no_color(False)

    def test_mcb_resource_help(self, capsys):
        """murphy mcb --help works.  (CLI-TEST-V2-MAIN-MCB-001)"""
        from murphy_cli.main import main
        from murphy_cli.output import set_no_color
        set_no_color(True)
        exit_code = main(["mcb", "--help"])
        assert exit_code == 0
        out = capsys.readouterr().out
        assert "launch" in out
        assert "zones" in out
        set_no_color(False)

    def test_split_resource_help(self, capsys):
        """murphy split --help works.  (CLI-TEST-V2-MAIN-SPLIT-001)"""
        from murphy_cli.main import main
        from murphy_cli.output import set_no_color
        set_no_color(True)
        exit_code = main(["split", "--help"])
        assert exit_code == 0
        out = capsys.readouterr().out
        assert "coordinate" in out
        set_no_color(False)

    def test_diagnose_resource_help(self, capsys):
        """murphy diagnose --help works.  (CLI-TEST-V2-MAIN-DIAG-001)"""
        from murphy_cli.main import main
        from murphy_cli.output import set_no_color
        set_no_color(True)
        exit_code = main(["diagnose", "--help"])
        assert exit_code == 0
        out = capsys.readouterr().out
        assert "symptom" in out
        set_no_color(False)
