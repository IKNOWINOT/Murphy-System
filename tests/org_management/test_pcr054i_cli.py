"""PCR-054i — engagement_inbound_cli.py regression suite."""
import json
import subprocess
import sys
from pathlib import Path

import pytest


CLI_PATH = "/opt/Murphy-System/src/engagement_inbound_cli.py"


class TestCli:
    def test_cli_runs_and_emits_json(self, tmp_path, monkeypatch):
        # Just verify the script executes cleanly with --limit 0 and prints valid JSON.
        # process_pending_replies will scan 0 rows because limit=0.
        result = subprocess.run(
            [sys.executable, CLI_PATH, "--limit", "1", "--quiet"],
            capture_output=True, text=True, timeout=15,
        )
        # Exit code 0 on success (even when 0 rows scanned)
        assert result.returncode == 0, f"stderr: {result.stderr}"
        # Last line is JSON
        last_line = [l for l in result.stdout.strip().split("\n") if l.strip()][-1]
        parsed = json.loads(last_line)
        assert parsed.get("ok") is True
        assert "scanned" in parsed
        assert "started_at" in parsed
        assert "finished_at" in parsed

    def test_cli_summary_line_when_not_quiet(self):
        result = subprocess.run(
            [sys.executable, CLI_PATH, "--limit", "1"],
            capture_output=True, text=True, timeout=15,
        )
        assert result.returncode == 0
        assert "[PCR-054i]" in result.stdout
        assert "scanned=" in result.stdout
        assert "finalized=" in result.stdout

    def test_cli_help(self):
        result = subprocess.run(
            [sys.executable, CLI_PATH, "--help"],
            capture_output=True, text=True, timeout=5,
        )
        assert result.returncode == 0
        assert "--limit" in result.stdout
        assert "--since" in result.stdout
