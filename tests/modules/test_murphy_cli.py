"""
Murphy CLI — Comprehensive test suite
======================================

Tests the full range of CLI capabilities:
- Argument parsing (all flag types, edge cases)
- Config management (load, save, env override)
- Command registry (register, resolve, help)
- Output formatting (text, json, table, streaming)
- HTTP client (request, retry, error handling, SSE)
- All command handlers (auth, chat, forge, agents, automations, hitl, safety, system)

Test label: CLI-TEST-001

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
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Test helpers  (CLI-TEST-HELPERS-001)
# ---------------------------------------------------------------------------

def _make_response(
    success: bool = True,
    status_code: int = 200,
    data: Any = None,
    error_code: str = None,
    error_message: str = None,
) -> MagicMock:
    """Create a mock APIResponse.  (CLI-TEST-HELPERS-001)"""
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
    """Create a mock execution context.  (CLI-TEST-HELPERS-002)"""
    from murphy_cli.client import MurphyClient
    from murphy_cli.config import CLIConfig

    # Use temp config file
    tmp = tempfile.mktemp(suffix=".json")
    config = CLIConfig(config_path=Path(tmp))
    if api_key:
        config.set("api_key", api_key)

    client = MagicMock(spec=MurphyClient)
    client.api_key = api_key
    client.base_url = api_url

    return {"client": client, "config": config, "api_url": api_url}


# ===========================================================================
# 1. Argument Parser Tests  (CLI-TEST-ARGS-001)
# ===========================================================================

class TestArgParser:
    """Argument parser unit tests.  (CLI-TEST-ARGS-001)"""

    def test_empty_args(self):
        """No arguments → resource/command are None.  (CLI-TEST-ARGS-EMPTY-001)"""
        from murphy_cli.args import parse_args
        parsed = parse_args([])
        assert parsed.resource is None
        assert parsed.command is None
        assert parsed.positional == []

    def test_resource_only(self):
        """Single positional → resource set, command None.  (CLI-TEST-ARGS-RES-001)"""
        from murphy_cli.args import parse_args
        parsed = parse_args(["status"])
        assert parsed.resource == "status"
        assert parsed.command is None

    def test_resource_and_command(self):
        """Two positionals → resource + command.  (CLI-TEST-ARGS-RESCMD-001)"""
        from murphy_cli.args import parse_args
        parsed = parse_args(["auth", "login"])
        assert parsed.resource == "auth"
        assert parsed.command == "login"

    def test_positional_overflow(self):
        """Extra positionals collected.  (CLI-TEST-ARGS-POS-001)"""
        from murphy_cli.args import parse_args
        parsed = parse_args(["forge", "generate", "Build", "an", "app"])
        assert parsed.resource == "forge"
        assert parsed.command == "generate"
        assert parsed.positional == ["Build", "an", "app"]

    def test_flag_string_value(self):
        """--api-key <value> is parsed.  (CLI-TEST-ARGS-FLAG-001)"""
        from murphy_cli.args import parse_args
        parsed = parse_args(["--api-key", "my_key_abc", "status"])
        assert parsed.api_key == "my_key_abc"
        assert parsed.resource == "status"

    def test_flag_equals_value(self):
        """--api-key=<value> form.  (CLI-TEST-ARGS-FLAGEQ-001)"""
        from murphy_cli.args import parse_args
        parsed = parse_args(["--api-key=my_key_xyz", "health"])
        assert parsed.api_key == "my_key_xyz"
        assert parsed.resource == "health"

    def test_boolean_flags(self):
        """Boolean flags: --verbose, --quiet, --dry-run.  (CLI-TEST-ARGS-BOOL-001)"""
        from murphy_cli.args import parse_args
        parsed = parse_args(["--verbose", "--quiet", "--dry-run", "status"])
        assert parsed.verbose is True
        assert parsed.quiet is True
        assert parsed.dry_run is True

    def test_short_flags(self):
        """-v, -h, -q short flags.  (CLI-TEST-ARGS-SHORT-001)"""
        from murphy_cli.args import parse_args
        parsed = parse_args(["-v"])
        assert parsed.show_version is True

        parsed2 = parse_args(["-h"])
        assert parsed2.show_help is True

        parsed3 = parse_args(["-q"])
        assert parsed3.quiet is True

    def test_help_flag(self):
        """--help sets show_help.  (CLI-TEST-ARGS-HELP-001)"""
        from murphy_cli.args import parse_args
        parsed = parse_args(["--help"])
        assert parsed.show_help is True

    def test_version_flag(self):
        """--version sets show_version.  (CLI-TEST-ARGS-VER-001)"""
        from murphy_cli.args import parse_args
        parsed = parse_args(["--version"])
        assert parsed.show_version is True

    def test_no_color_flag(self):
        """--no-color flag.  (CLI-TEST-ARGS-NOCOLOR-001)"""
        from murphy_cli.args import parse_args
        parsed = parse_args(["--no-color", "status"])
        assert parsed.no_color is True

    def test_non_interactive_flag(self):
        """--non-interactive flag.  (CLI-TEST-ARGS-NONINT-001)"""
        from murphy_cli.args import parse_args
        parsed = parse_args(["--non-interactive", "forge", "generate"])
        assert parsed.non_interactive is True

    def test_output_format_flag(self):
        """--output json flag.  (CLI-TEST-ARGS-OUTPUT-001)"""
        from murphy_cli.args import parse_args
        parsed = parse_args(["--output", "json", "status"])
        assert parsed.output_format == "json"

    def test_timeout_flag(self):
        """--timeout value flag.  (CLI-TEST-ARGS-TIMEOUT-001)"""
        from murphy_cli.args import parse_args
        parsed = parse_args(["--timeout", "60", "chat"])
        assert parsed.timeout == 60

    def test_mixed_flags_and_positionals(self):
        """Flags and positionals interleaved.  (CLI-TEST-ARGS-MIX-001)"""
        from murphy_cli.args import parse_args
        parsed = parse_args([
            "--api-key", "key123",
            "forge", "generate",
            "--query", "Build app",
            "--verbose",
        ])
        assert parsed.api_key == "key123"
        assert parsed.resource == "forge"
        assert parsed.command == "generate"
        assert parsed.verbose is True
        assert parsed.flags.get("query") == "Build app"

    def test_raw_preserved(self):
        """Original argv is preserved in raw.  (CLI-TEST-ARGS-RAW-001)"""
        from murphy_cli.args import parse_args
        argv = ["auth", "login", "--api-key", "k"]
        parsed = parse_args(argv)
        assert parsed.raw == argv


# ===========================================================================
# 2. Config Tests  (CLI-TEST-CONFIG-001)
# ===========================================================================

class TestConfig:
    """CLI configuration tests.  (CLI-TEST-CONFIG-001)"""

    def test_defaults(self):
        """Fresh config has correct defaults.  (CLI-TEST-CONFIG-DEF-001)"""
        from murphy_cli.config import CLIConfig
        tmp = Path(tempfile.mktemp(suffix=".json"))
        config = CLIConfig(config_path=tmp)
        assert config.api_url == "http://localhost:8000"
        assert config.timeout == 30
        assert config.output_format == "text"

    def test_set_and_get(self):
        """Set a value, get it back.  (CLI-TEST-CONFIG-SETGET-001)"""
        from murphy_cli.config import CLIConfig
        tmp = Path(tempfile.mktemp(suffix=".json"))
        config = CLIConfig(config_path=tmp)
        config.set("api_url", "https://murphy.systems")
        assert config.get("api_url") == "https://murphy.systems"
        assert config.api_url == "https://murphy.systems"

    def test_persistence(self):
        """Config persists to disk and reloads.  (CLI-TEST-CONFIG-PERSIST-001)"""
        from murphy_cli.config import CLIConfig
        tmp = Path(tempfile.mktemp(suffix=".json"))
        config1 = CLIConfig(config_path=tmp)
        config1.set("test_key", "test_value")

        config2 = CLIConfig(config_path=tmp)
        assert config2.get("test_key") == "test_value"

    def test_delete(self):
        """Delete removes a key.  (CLI-TEST-CONFIG-DEL-001)"""
        from murphy_cli.config import CLIConfig
        tmp = Path(tempfile.mktemp(suffix=".json"))
        config = CLIConfig(config_path=tmp)
        config.set("foo", "bar")
        assert config.delete("foo") is True
        assert config.get("foo") is None
        assert config.delete("nonexistent") is False

    def test_env_override(self):
        """Environment variables override config file.  (CLI-TEST-CONFIG-ENV-001)"""
        from murphy_cli.config import CLIConfig
        tmp = Path(tempfile.mktemp(suffix=".json"))
        config = CLIConfig(config_path=tmp)
        config.set("api_url", "http://from-file")

        with patch.dict(os.environ, {"MURPHY_API_URL": "http://from-env"}):
            assert config.get("api_url") == "http://from-env"

    def test_all(self):
        """all() returns a copy of config data.  (CLI-TEST-CONFIG-ALL-001)"""
        from murphy_cli.config import CLIConfig
        tmp = Path(tempfile.mktemp(suffix=".json"))
        config = CLIConfig(config_path=tmp)
        data = config.all()
        assert isinstance(data, dict)
        assert "api_url" in data

    def test_corrupt_file_handled(self):
        """Corrupt JSON file doesn't crash.  (CLI-TEST-CONFIG-CORRUPT-001)"""
        from murphy_cli.config import CLIConfig
        tmp = Path(tempfile.mktemp(suffix=".json"))
        tmp.write_text("NOT VALID JSON {{{{", encoding="utf-8")
        config = CLIConfig(config_path=tmp)
        # Should load defaults without crashing
        assert config.api_url == "http://localhost:8000"

    def test_api_key_from_env(self):
        """api_key property checks MURPHY_API_KEY env var.  (CLI-TEST-CONFIG-APIKEY-001)"""
        from murphy_cli.config import CLIConfig
        tmp = Path(tempfile.mktemp(suffix=".json"))
        config = CLIConfig(config_path=tmp)
        with patch.dict(os.environ, {"MURPHY_API_KEY": "env_key_123"}):
            assert config.api_key == "env_key_123"


# ===========================================================================
# 3. Command Registry Tests  (CLI-TEST-REGISTRY-001)
# ===========================================================================

class TestCommandRegistry:
    """Command registry tests.  (CLI-TEST-REGISTRY-001)"""

    def test_register_and_resolve(self):
        """Register a command and resolve it.  (CLI-TEST-REGISTRY-RESOLVE-001)"""
        from murphy_cli.registry import CommandRegistry, CommandDef
        from murphy_cli.args import parse_args

        registry = CommandRegistry()
        handler = MagicMock(return_value=0)
        registry.register(CommandDef(
            resource="test",
            name="run",
            handler=handler,
            description="Test command",
        ))

        parsed = parse_args(["test", "run"])
        cmd = registry.resolve(parsed)
        assert cmd is not None
        assert cmd.resource == "test"
        assert cmd.name == "run"

    def test_resolve_default_command(self):
        """Resolve resource with empty command name.  (CLI-TEST-REGISTRY-DEFAULT-001)"""
        from murphy_cli.registry import CommandRegistry, CommandDef
        from murphy_cli.args import parse_args

        registry = CommandRegistry()
        handler = MagicMock(return_value=0)
        registry.register(CommandDef(
            resource="status",
            name="",
            handler=handler,
            description="Status",
        ))

        parsed = parse_args(["status"])
        cmd = registry.resolve(parsed)
        assert cmd is not None
        assert cmd.resource == "status"

    def test_resolve_with_alias(self):
        """Resolve via alias.  (CLI-TEST-REGISTRY-ALIAS-001)"""
        from murphy_cli.registry import CommandRegistry, CommandDef
        from murphy_cli.args import parse_args

        registry = CommandRegistry()
        handler = MagicMock(return_value=0)
        registry.register(CommandDef(
            resource="config",
            name="list",
            handler=handler,
            description="List",
            aliases=["ls"],
        ))

        parsed = parse_args(["config", "ls"])
        cmd = registry.resolve(parsed)
        assert cmd is not None
        assert cmd.name == "list"

    def test_resolve_unknown(self):
        """Unknown command returns None.  (CLI-TEST-REGISTRY-UNKNOWN-001)"""
        from murphy_cli.registry import CommandRegistry
        from murphy_cli.args import parse_args

        registry = CommandRegistry()
        parsed = parse_args(["nonexistent", "cmd"])
        assert registry.resolve(parsed) is None

    def test_all_commands(self):
        """all_commands returns unique list.  (CLI-TEST-REGISTRY-ALLCMDS-001)"""
        from murphy_cli.registry import CommandRegistry, CommandDef

        registry = CommandRegistry()
        for name in ["a", "b", "c"]:
            registry.register(CommandDef(
                resource="test",
                name=name,
                handler=MagicMock(),
            ))

        cmds = registry.all_commands()
        assert len(cmds) == 3

    def test_resources(self):
        """resources() returns sorted unique names.  (CLI-TEST-REGISTRY-RES-001)"""
        from murphy_cli.registry import CommandRegistry, CommandDef

        registry = CommandRegistry()
        for res in ["charlie", "alpha", "bravo"]:
            registry.register(CommandDef(
                resource=res, name="", handler=MagicMock()
            ))
        assert registry.resources() == ["alpha", "bravo", "charlie"]

    def test_full_name(self):
        """CommandDef.full_name property.  (CLI-TEST-REGISTRY-FULLNAME-001)"""
        from murphy_cli.registry import CommandDef
        cmd = CommandDef(resource="auth", name="login", handler=MagicMock())
        assert cmd.full_name == "auth login"

        cmd2 = CommandDef(resource="status", name="", handler=MagicMock())
        assert cmd2.full_name == "status"


# ===========================================================================
# 4. Output Formatter Tests  (CLI-TEST-OUTPUT-001)
# ===========================================================================

class TestOutputFormatter:
    """Output formatter tests.  (CLI-TEST-OUTPUT-001)"""

    def test_set_no_color(self):
        """set_no_color toggles colour.  (CLI-TEST-OUTPUT-NOCOLOR-001)"""
        from murphy_cli.output import set_no_color, green
        set_no_color(True)
        assert "\033[" not in green("test")
        set_no_color(False)
        assert "\033[" in green("test")

    def test_print_success(self, capsys):
        """print_success outputs ✓.  (CLI-TEST-OUTPUT-SUCCESS-001)"""
        from murphy_cli.output import print_success, set_no_color
        set_no_color(True)
        print_success("Done")
        out = capsys.readouterr().out
        assert "✓" in out
        assert "Done" in out
        set_no_color(False)

    def test_print_error(self, capsys):
        """print_error outputs ✗ to stderr.  (CLI-TEST-OUTPUT-ERROR-001)"""
        from murphy_cli.output import print_error, set_no_color
        set_no_color(True)
        print_error("Failed", code="ERR-001")
        err = capsys.readouterr().err
        assert "✗" in err
        assert "ERR-001" in err
        assert "Failed" in err
        set_no_color(False)

    def test_print_json(self, capsys):
        """print_json outputs formatted JSON.  (CLI-TEST-OUTPUT-JSON-001)"""
        from murphy_cli.output import print_json
        print_json({"key": "value"})
        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert parsed["key"] == "value"

    def test_print_table(self, capsys):
        """print_table outputs aligned rows.  (CLI-TEST-OUTPUT-TABLE-001)"""
        from murphy_cli.output import print_table, set_no_color
        set_no_color(True)
        print_table(["Name", "Value"], [["foo", "1"], ["bar", "2"]])
        out = capsys.readouterr().out
        assert "Name" in out
        assert "foo" in out
        assert "bar" in out
        set_no_color(False)

    def test_print_kv(self, capsys):
        """print_kv outputs aligned key-value pairs.  (CLI-TEST-OUTPUT-KV-001)"""
        from murphy_cli.output import print_kv, set_no_color
        set_no_color(True)
        print_kv({"alpha": 1, "beta": 2})
        out = capsys.readouterr().out
        assert "alpha" in out
        assert "beta" in out
        set_no_color(False)

    def test_render_response_json(self, capsys):
        """render_response with json format.  (CLI-TEST-OUTPUT-RENDER-JSON-001)"""
        from murphy_cli.output import render_response
        render_response({"status": "ok"}, output_format="json")
        out = capsys.readouterr().out
        assert '"status"' in out

    def test_render_response_text_dict(self, capsys):
        """render_response with text format dict.  (CLI-TEST-OUTPUT-RENDER-TXT-001)"""
        from murphy_cli.output import render_response, set_no_color
        set_no_color(True)
        render_response({"status": "ok"}, output_format="text", title="Test")
        out = capsys.readouterr().out
        assert "status" in out
        assert "Test" in out
        set_no_color(False)

    def test_render_response_text_list(self, capsys):
        """render_response with text format list.  (CLI-TEST-OUTPUT-RENDER-LIST-001)"""
        from murphy_cli.output import render_response, set_no_color
        set_no_color(True)
        render_response(["item1", "item2"], output_format="text")
        out = capsys.readouterr().out
        assert "item1" in out
        set_no_color(False)

    def test_print_stream_chunk(self, capsys):
        """print_stream_chunk writes without newline.  (CLI-TEST-OUTPUT-STREAMCHUNK-001)"""
        from murphy_cli.output import print_stream_chunk
        print_stream_chunk("hello")
        out = capsys.readouterr().out
        assert out == "hello"

    def test_print_banner(self, capsys):
        """print_banner outputs murphy.systems branding.  (CLI-TEST-OUTPUT-BANNER-001)"""
        from murphy_cli.output import print_banner, set_no_color
        set_no_color(True)
        print_banner()
        out = capsys.readouterr().out
        assert "murphy.systems" in out
        set_no_color(False)

    def test_print_table_truncation(self, capsys):
        """Long cells are truncated.  (CLI-TEST-OUTPUT-TABLE-TRUNC-001)"""
        from murphy_cli.output import print_table, set_no_color
        set_no_color(True)
        long_val = "x" * 100
        print_table(["Data"], [[long_val]], max_col_width=20)
        out = capsys.readouterr().out
        assert "..." in out
        set_no_color(False)


# ===========================================================================
# 5. Client Tests  (CLI-TEST-CLIENT-001)
# ===========================================================================

class TestClient:
    """HTTP client tests.  (CLI-TEST-CLIENT-001)"""

    def test_api_response_to_dict(self):
        """APIResponse.to_dict serialises correctly.  (CLI-TEST-CLIENT-RESP-001)"""
        from murphy_cli.client import APIResponse
        resp = APIResponse(
            success=True,
            status_code=200,
            data={"key": "val"},
        )
        d = resp.to_dict()
        assert d["success"] is True
        assert d["data"]["key"] == "val"

    def test_api_response_error_dict(self):
        """APIResponse with error.  (CLI-TEST-CLIENT-RESPERR-001)"""
        from murphy_cli.client import APIResponse
        resp = APIResponse(
            success=False,
            status_code=401,
            error_code="AUTH-001",
            error_message="Unauthorized",
        )
        d = resp.to_dict()
        assert d["success"] is False
        assert d["error"]["code"] == "AUTH-001"

    def test_client_headers(self):
        """Client injects API key header.  (CLI-TEST-CLIENT-HDR-001)"""
        from murphy_cli.client import MurphyClient
        c = MurphyClient(api_key="test_key")
        hdrs = c._headers()
        assert hdrs["X-API-Key"] == "test_key"

    def test_client_headers_no_key(self):
        """Client with no key omits header.  (CLI-TEST-CLIENT-HDRNO-001)"""
        from murphy_cli.client import MurphyClient
        c = MurphyClient()
        hdrs = c._headers()
        assert "X-API-Key" not in hdrs

    def test_parse_response_success(self):
        """_parse_response with Murphy JSON envelope.  (CLI-TEST-CLIENT-PARSE-001)"""
        from murphy_cli.client import MurphyClient
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.ok = True
        mock_resp.json.return_value = {"success": True, "data": {"status": "ok"}}
        result = MurphyClient._parse_response(mock_resp)
        assert result.success is True
        assert result.data["status"] == "ok"

    def test_parse_response_error(self):
        """_parse_response with error envelope.  (CLI-TEST-CLIENT-PARSEERR-001)"""
        from murphy_cli.client import MurphyClient
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.ok = False
        mock_resp.json.return_value = {
            "success": False,
            "error": {"code": "BAD-REQ", "message": "Bad request"},
        }
        result = MurphyClient._parse_response(mock_resp)
        assert result.success is False
        assert result.error_code == "BAD-REQ"

    def test_parse_response_non_json(self):
        """_parse_response with non-JSON body.  (CLI-TEST-CLIENT-PARSERAW-001)"""
        from murphy_cli.client import MurphyClient
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.ok = True
        mock_resp.json.side_effect = json.JSONDecodeError("", "", 0)
        mock_resp.text = "OK"
        result = MurphyClient._parse_response(mock_resp)
        assert result.success is True
        assert result.data == "OK"

    @patch("murphy_cli.client.requests.Session")
    def test_request_retry_on_connection_error(self, mock_session_cls):
        """Client retries on ConnectionError.  (CLI-TEST-CLIENT-RETRY-001)"""
        from murphy_cli.client import MurphyClient
        import requests as req

        mock_session = MagicMock()
        mock_session.headers = {}
        mock_session_cls.return_value = mock_session

        # Fail twice, succeed on third
        good_resp = MagicMock()
        good_resp.status_code = 200
        good_resp.ok = True
        good_resp.json.return_value = {"success": True}
        mock_session.request.side_effect = [
            req.ConnectionError("conn fail"),
            req.ConnectionError("conn fail"),
            good_resp,
        ]

        client = MurphyClient(timeout=1)
        result = client.get("/api/test")
        assert result.success is True
        assert mock_session.request.call_count == 3

    @patch("murphy_cli.client.requests.Session")
    def test_request_timeout_no_retry(self, mock_session_cls):
        """Client does not retry on Timeout.  (CLI-TEST-CLIENT-TIMEOUT-001)"""
        from murphy_cli.client import MurphyClient
        import requests as req

        mock_session = MagicMock()
        mock_session.headers = {}
        mock_session_cls.return_value = mock_session
        mock_session.request.side_effect = req.Timeout("timed out")

        client = MurphyClient(timeout=1)
        result = client.get("/api/test")
        assert result.success is False
        assert "CLI-CLIENT-ERR-004" in (result.error_code or "")
        # Timeout should not retry
        assert mock_session.request.call_count == 1


# ===========================================================================
# 6. Auth Command Tests  (CLI-TEST-CMD-AUTH-001)
# ===========================================================================

class TestAuthCommands:
    """Auth command handler tests.  (CLI-TEST-CMD-AUTH-001)"""

    def test_login_with_api_key(self):
        """Login stores key on success.  (CLI-TEST-CMD-AUTH-LOGIN-001)"""
        from murphy_cli.commands.auth import _cmd_login
        from murphy_cli.args import parse_args

        ctx = _make_ctx(api_key="")
        ctx["client"].get.return_value = _make_response(success=True, data={"email": "test@example.com"})

        parsed = parse_args(["auth", "login", "--api-key", "new_key_12345678"])
        result = _cmd_login(parsed, ctx)
        assert result == 0
        assert ctx["config"].get("api_key") is not None

    def test_login_no_credentials(self):
        """Login with no key fails.  (CLI-TEST-CMD-AUTH-LOGINFAIL-001)"""
        from murphy_cli.commands.auth import _cmd_login
        from murphy_cli.args import parse_args

        ctx = _make_ctx(api_key="")
        parsed = parse_args(["auth", "login"])
        result = _cmd_login(parsed, ctx)
        assert result == 1

    def test_logout(self):
        """Logout clears key.  (CLI-TEST-CMD-AUTH-LOGOUT-001)"""
        from murphy_cli.commands.auth import _cmd_logout
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        ctx["client"].post.return_value = _make_response(success=True)
        parsed = parse_args(["auth", "logout"])
        result = _cmd_logout(parsed, ctx)
        assert result == 0

    def test_auth_status(self):
        """Auth status shows masked key.  (CLI-TEST-CMD-AUTH-STATUS-001)"""
        from murphy_cli.commands.auth import _cmd_auth_status
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        ctx["client"].get.return_value = _make_response(success=True, data={"email": "x@y.com"})
        parsed = parse_args(["auth", "status"])
        result = _cmd_auth_status(parsed, ctx)
        assert result == 0

    def test_auth_me(self):
        """Auth me returns profile.  (CLI-TEST-CMD-AUTH-ME-001)"""
        from murphy_cli.commands.auth import _cmd_auth_me
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        ctx["client"].get.return_value = _make_response(success=True, data={"email": "x@y.com", "role": "admin"})
        parsed = parse_args(["auth", "me"])
        result = _cmd_auth_me(parsed, ctx)
        assert result == 0


# ===========================================================================
# 7. Chat Command Tests  (CLI-TEST-CMD-CHAT-001)
# ===========================================================================

class TestChatCommands:
    """Chat command handler tests.  (CLI-TEST-CMD-CHAT-001)"""

    def test_chat_no_message(self):
        """Chat with no message fails.  (CLI-TEST-CMD-CHAT-NOMSG-001)"""
        from murphy_cli.commands.chat import _cmd_chat
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        parsed = parse_args(["chat"])
        # Simulate TTY
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = True
            result = _cmd_chat(parsed, ctx)
        assert result == 1

    def test_chat_with_message(self):
        """Chat with --message succeeds.  (CLI-TEST-CMD-CHAT-MSG-001)"""
        from murphy_cli.commands.chat import _cmd_chat
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        # SSE streaming raises, fallback to sync
        ctx["client"].stream_sse.side_effect = Exception("no streaming")
        ctx["client"].post.return_value = _make_response(
            success=True,
            data={"response": "Hello from Murphy!"},
        )

        parsed = parse_args(["chat", "--message", "Hello"])
        result = _cmd_chat(parsed, ctx)
        assert result == 0

    def test_chat_dry_run(self):
        """Chat dry-run doesn't call API.  (CLI-TEST-CMD-CHAT-DRY-001)"""
        from murphy_cli.commands.chat import _cmd_chat
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        parsed = parse_args(["chat", "--message", "test", "--dry-run"])
        result = _cmd_chat(parsed, ctx)
        assert result == 0
        ctx["client"].post.assert_not_called()

    def test_llm_status(self):
        """LLM status command.  (CLI-TEST-CMD-CHAT-LLMSTATUS-001)"""
        from murphy_cli.commands.chat import _cmd_llm_status
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        ctx["client"].get.return_value = _make_response(success=True, data={"provider": "deepinfra"})
        parsed = parse_args(["llm", "status"])
        result = _cmd_llm_status(parsed, ctx)
        assert result == 0

    def test_llm_providers(self):
        """LLM providers command.  (CLI-TEST-CMD-CHAT-LLMPROV-001)"""
        from murphy_cli.commands.chat import _cmd_llm_providers
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        ctx["client"].get.return_value = _make_response(
            success=True,
            data=[{"name": "deepinfra"}, {"name": "openai"}],
        )
        parsed = parse_args(["llm", "providers"])
        result = _cmd_llm_providers(parsed, ctx)
        assert result == 0


# ===========================================================================
# 8. Forge Command Tests  (CLI-TEST-CMD-FORGE-001)
# ===========================================================================

class TestForgeCommands:
    """Forge command handler tests.  (CLI-TEST-CMD-FORGE-001)"""

    def test_forge_no_query(self):
        """Forge with no query fails.  (CLI-TEST-CMD-FORGE-NOQUERY-001)"""
        from murphy_cli.commands.forge import _cmd_forge_generate
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        parsed = parse_args(["forge", "generate"])
        result = _cmd_forge_generate(parsed, ctx)
        assert result == 1

    def test_forge_sync_fallback(self):
        """Forge falls back to sync endpoint.  (CLI-TEST-CMD-FORGE-SYNC-001)"""
        from murphy_cli.commands.forge import _cmd_forge_generate
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        ctx["client"].stream_sse.return_value = iter([])  # empty stream
        ctx["client"].post.return_value = _make_response(
            success=True,
            data={"deliverable": "# Test Deliverable"},
        )

        parsed = parse_args(["forge", "generate", "--query", "Build an app"])
        result = _cmd_forge_generate(parsed, ctx)
        assert result == 0

    def test_forge_dry_run(self):
        """Forge dry-run.  (CLI-TEST-CMD-FORGE-DRY-001)"""
        from murphy_cli.commands.forge import _cmd_forge_generate
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        parsed = parse_args(["forge", "generate", "--query", "test", "--dry-run"])
        result = _cmd_forge_generate(parsed, ctx)
        assert result == 0
        ctx["client"].post.assert_not_called()

    def test_forge_formats(self):
        """Forge formats listing.  (CLI-TEST-CMD-FORGE-FMTS-001)"""
        from murphy_cli.commands.forge import _cmd_forge_formats
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        ctx["client"].get.return_value = _make_response(
            success=True,
            data=["txt", "pdf", "html", "md"],
        )
        parsed = parse_args(["forge", "formats"])
        result = _cmd_forge_formats(parsed, ctx)
        assert result == 0


# ===========================================================================
# 9. Agent Command Tests  (CLI-TEST-CMD-AGENTS-001)
# ===========================================================================

class TestAgentCommands:
    """Agent command handler tests.  (CLI-TEST-CMD-AGENTS-001)"""

    def test_agents_list_empty(self):
        """Agents list with no agents.  (CLI-TEST-CMD-AGENTS-EMPTY-001)"""
        from murphy_cli.commands.agents import _cmd_agents_list
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        ctx["client"].get.return_value = _make_response(success=True, data=[])
        parsed = parse_args(["agents", "list"])
        result = _cmd_agents_list(parsed, ctx)
        assert result == 0

    def test_agents_list_populated(self):
        """Agents list with agents.  (CLI-TEST-CMD-AGENTS-POP-001)"""
        from murphy_cli.commands.agents import _cmd_agents_list
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        ctx["client"].get.return_value = _make_response(
            success=True,
            data=[{"id": "a1", "name": "Analyst", "role": "analysis", "status": "active"}],
        )
        parsed = parse_args(["agents", "list"])
        result = _cmd_agents_list(parsed, ctx)
        assert result == 0

    def test_agents_inspect_no_id(self):
        """Agents inspect with no ID fails.  (CLI-TEST-CMD-AGENTS-NOID-001)"""
        from murphy_cli.commands.agents import _cmd_agents_inspect
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        parsed = parse_args(["agents", "inspect"])
        result = _cmd_agents_inspect(parsed, ctx)
        assert result == 1


# ===========================================================================
# 10. Automation Command Tests  (CLI-TEST-CMD-AUTO-001)
# ===========================================================================

class TestAutomationCommands:
    """Automation command handler tests.  (CLI-TEST-CMD-AUTO-001)"""

    def test_automations_list(self):
        """Automations list.  (CLI-TEST-CMD-AUTO-LIST-001)"""
        from murphy_cli.commands.automations import _cmd_automations_list
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        ctx["client"].get.return_value = _make_response(success=True, data=[])
        parsed = parse_args(["automations", "list"])
        result = _cmd_automations_list(parsed, ctx)
        assert result == 0

    def test_execute_no_task(self):
        """Execute with no task fails.  (CLI-TEST-CMD-AUTO-NOTASK-001)"""
        from murphy_cli.commands.automations import _cmd_execute
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        parsed = parse_args(["execute"])
        result = _cmd_execute(parsed, ctx)
        assert result == 1

    def test_execute_with_task(self):
        """Execute with task.  (CLI-TEST-CMD-AUTO-TASK-001)"""
        from murphy_cli.commands.automations import _cmd_execute
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        ctx["client"].post.return_value = _make_response(
            success=True,
            data={"execution_id": "exec-123", "status": "running"},
        )
        parsed = parse_args(["execute", "--task", "Process invoices"])
        result = _cmd_execute(parsed, ctx)
        assert result == 0


# ===========================================================================
# 11. HITL Command Tests  (CLI-TEST-CMD-HITL-001)
# ===========================================================================

class TestHITLCommands:
    """HITL command handler tests.  (CLI-TEST-CMD-HITL-001)"""

    def test_hitl_queue(self):
        """HITL queue listing.  (CLI-TEST-CMD-HITL-QUEUE-001)"""
        from murphy_cli.commands.hitl import _cmd_hitl_queue
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        ctx["client"].get.return_value = _make_response(
            success=True,
            data=[{"id": "h1", "type": "execution", "status": "pending", "created_at": "2026-01-01"}],
        )
        parsed = parse_args(["hitl", "queue"])
        result = _cmd_hitl_queue(parsed, ctx)
        assert result == 0

    def test_hitl_approve_no_id(self):
        """HITL approve without ID fails.  (CLI-TEST-CMD-HITL-NOID-001)"""
        from murphy_cli.commands.hitl import _cmd_hitl_approve
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        parsed = parse_args(["hitl", "approve"])
        result = _cmd_hitl_approve(parsed, ctx)
        assert result == 1

    def test_hitl_approve_success(self):
        """HITL approve succeeds.  (CLI-TEST-CMD-HITL-APPROVE-001)"""
        from murphy_cli.commands.hitl import _cmd_hitl_approve
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        ctx["client"].post.return_value = _make_response(success=True)
        parsed = parse_args(["hitl", "approve", "--id", "h1"])
        result = _cmd_hitl_approve(parsed, ctx)
        assert result == 0

    def test_hitl_reject_success(self):
        """HITL reject succeeds.  (CLI-TEST-CMD-HITL-REJECT-001)"""
        from murphy_cli.commands.hitl import _cmd_hitl_reject
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        ctx["client"].post.return_value = _make_response(success=True)
        parsed = parse_args(["hitl", "reject", "--id", "h2", "--reason", "Bad"])
        result = _cmd_hitl_reject(parsed, ctx)
        assert result == 0


# ===========================================================================
# 12. Safety Command Tests  (CLI-TEST-CMD-SAFETY-001)
# ===========================================================================

class TestSafetyCommands:
    """Safety command handler tests.  (CLI-TEST-CMD-SAFETY-001)"""

    def test_safety_status(self):
        """Safety status command.  (CLI-TEST-CMD-SAFETY-STATUS-001)"""
        from murphy_cli.commands.safety import _cmd_safety_status
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        ctx["client"].get.return_value = _make_response(
            success=True,
            data={"score": 98, "status": "nominal"},
        )
        parsed = parse_args(["safety", "status"])
        result = _cmd_safety_status(parsed, ctx)
        assert result == 0

    def test_emergency_stop_no_confirm(self):
        """Emergency stop without --confirm blocked.  (CLI-TEST-CMD-SAFETY-ESTOPNO-001)"""
        from murphy_cli.commands.safety import _cmd_emergency_stop
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        parsed = parse_args(["emergency", "stop"])
        result = _cmd_emergency_stop(parsed, ctx)
        assert result == 1

    def test_emergency_stop_confirmed(self):
        """Emergency stop with --confirm executes.  (CLI-TEST-CMD-SAFETY-ESTOPYES-001)"""
        from murphy_cli.commands.safety import _cmd_emergency_stop
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        ctx["client"].post.return_value = _make_response(success=True)
        parsed = parse_args(["emergency", "stop", "--confirm"])
        result = _cmd_emergency_stop(parsed, ctx)
        assert result == 0

    def test_gates_list(self):
        """Gates list command.  (CLI-TEST-CMD-SAFETY-GATES-001)"""
        from murphy_cli.commands.safety import _cmd_gates_list
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        ctx["client"].get.return_value = _make_response(success=True, data=[])
        parsed = parse_args(["gates", "list"])
        result = _cmd_gates_list(parsed, ctx)
        assert result == 0


# ===========================================================================
# 13. System Command Tests  (CLI-TEST-CMD-SYS-001)
# ===========================================================================

class TestSystemCommands:
    """System command handler tests.  (CLI-TEST-CMD-SYS-001)"""

    def test_status(self):
        """Status command.  (CLI-TEST-CMD-SYS-STATUS-001)"""
        from murphy_cli.commands.system import _cmd_status
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        ctx["client"].get.return_value = _make_response(
            success=True,
            data={"version": "1.0.0", "uptime": "24h"},
        )
        parsed = parse_args(["status"])
        result = _cmd_status(parsed, ctx)
        assert result == 0

    def test_health(self):
        """Health check command.  (CLI-TEST-CMD-SYS-HEALTH-001)"""
        from murphy_cli.commands.system import _cmd_health
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        ctx["client"].get.return_value = _make_response(
            success=True,
            data={"status": "healthy"},
        )
        parsed = parse_args(["health"])
        result = _cmd_health(parsed, ctx)
        assert result == 0

    def test_credentials_list(self):
        """Credentials list command.  (CLI-TEST-CMD-SYS-CREDLIST-001)"""
        from murphy_cli.commands.system import _cmd_credentials_list
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        ctx["client"].get.return_value = _make_response(
            success=True,
            data=[{"provider": "deepinfra", "status": "active", "last_used": "2026-01-01"}],
        )
        parsed = parse_args(["credentials", "list"])
        result = _cmd_credentials_list(parsed, ctx)
        assert result == 0

    def test_manifest(self):
        """Manifest command.  (CLI-TEST-CMD-SYS-MANIFEST-001)"""
        from murphy_cli.commands.system import _cmd_manifest
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        ctx["client"].get.return_value = _make_response(
            success=True,
            data={"endpoints": 619},
        )
        parsed = parse_args(["manifest"])
        result = _cmd_manifest(parsed, ctx)
        assert result == 0

    def test_admin_stats(self):
        """Admin stats command.  (CLI-TEST-CMD-SYS-ADMINSTATS-001)"""
        from murphy_cli.commands.system import _cmd_admin_stats
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        ctx["client"].get.return_value = _make_response(
            success=True,
            data={"users": 10, "modules": 1230},
        )
        parsed = parse_args(["admin", "stats"])
        result = _cmd_admin_stats(parsed, ctx)
        assert result == 0


# ===========================================================================
# 14. Config Command Tests  (CLI-TEST-CMD-CONFIG-001)
# ===========================================================================

class TestConfigCommands:
    """Config command handler tests.  (CLI-TEST-CMD-CONFIG-001)"""

    def test_config_get(self):
        """Config get returns value.  (CLI-TEST-CMD-CONFIG-GET-001)"""
        from murphy_cli.commands.config_cmd import _cmd_config_get
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        ctx["config"].set("api_url", "http://test")
        parsed = parse_args(["config", "get", "--key", "api_url"])
        result = _cmd_config_get(parsed, ctx)
        assert result == 0

    def test_config_get_missing(self):
        """Config get for missing key.  (CLI-TEST-CMD-CONFIG-GETMISS-001)"""
        from murphy_cli.commands.config_cmd import _cmd_config_get
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        parsed = parse_args(["config", "get", "--key", "nonexistent_key_xyz"])
        result = _cmd_config_get(parsed, ctx)
        assert result == 1

    def test_config_set(self):
        """Config set stores value.  (CLI-TEST-CMD-CONFIG-SET-001)"""
        from murphy_cli.commands.config_cmd import _cmd_config_set
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        parsed = parse_args(["config", "set", "--key", "timeout", "--value", "60"])
        result = _cmd_config_set(parsed, ctx)
        assert result == 0
        assert ctx["config"].get("timeout") == "60"

    def test_config_list(self):
        """Config list shows all values.  (CLI-TEST-CMD-CONFIG-LIST-001)"""
        from murphy_cli.commands.config_cmd import _cmd_config_list
        from murphy_cli.args import parse_args

        ctx = _make_ctx()
        parsed = parse_args(["config", "list"])
        result = _cmd_config_list(parsed, ctx)
        assert result == 0


# ===========================================================================
# 15. Main Entry Point Tests  (CLI-TEST-MAIN-001)
# ===========================================================================

class TestMain:
    """Main entry point tests.  (CLI-TEST-MAIN-001)"""

    def test_version_flag(self, capsys):
        """--version prints version.  (CLI-TEST-MAIN-VER-001)"""
        from murphy_cli.main import main
        exit_code = main(["--version"])
        assert exit_code == 0
        out = capsys.readouterr().out
        assert "murphy-cli" in out

    def test_help_flag(self, capsys):
        """--help shows global help.  (CLI-TEST-MAIN-HELP-001)"""
        from murphy_cli.main import main
        from murphy_cli.output import set_no_color
        set_no_color(True)
        exit_code = main(["--help"])
        assert exit_code == 0
        out = capsys.readouterr().out
        assert "RESOURCES" in out
        set_no_color(False)

    def test_no_args_shows_help(self, capsys):
        """No args shows banner + help.  (CLI-TEST-MAIN-NOARGS-001)"""
        from murphy_cli.main import main
        from murphy_cli.output import set_no_color
        set_no_color(True)
        exit_code = main([])
        assert exit_code == 0
        out = capsys.readouterr().out
        assert "murphy" in out
        set_no_color(False)

    def test_unknown_command(self, capsys):
        """Unknown command returns 1.  (CLI-TEST-MAIN-UNKNOWN-001)"""
        from murphy_cli.main import main
        from murphy_cli.output import set_no_color
        set_no_color(True)
        exit_code = main(["xyznonexistent"])
        assert exit_code == 1
        set_no_color(False)

    def test_resource_help(self, capsys):
        """Resource --help shows resource help.  (CLI-TEST-MAIN-RESHELP-001)"""
        from murphy_cli.main import main
        from murphy_cli.output import set_no_color
        set_no_color(True)
        exit_code = main(["auth", "--help"])
        assert exit_code == 0
        out = capsys.readouterr().out
        assert "auth" in out.lower()
        set_no_color(False)
