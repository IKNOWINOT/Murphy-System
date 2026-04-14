"""Tests for murphy_cli — command-line interface."""

import argparse
import json
import sys
from io import StringIO
from unittest import mock

import pytest

from murphy_cli import (
    __version__,
    _build_parser,
    cmd_status,
    cmd_version,
    cmd_confidence,
    cmd_engine_list,
    main,
    _error,
    _output,
)


# ── parser ────────────────────────────────────────────────────────────────
class TestParser:
    def test_parser_builds(self):
        parser = _build_parser()
        assert isinstance(parser, argparse.ArgumentParser)

    def test_version_subcommand_parsed(self):
        parser = _build_parser()
        args = parser.parse_args(["version"])
        assert args.command == "version"


# ── status command ────────────────────────────────────────────────────────
class TestStatusCommand:
    @mock.patch("murphy_cli._api_get", return_value={"status": "ok"})
    @mock.patch("murphy_cli._read_live", return_value=None)
    @mock.patch("murphy_cli._dbus_call", return_value=None)
    def test_status_returns_int(self, *_):
        args = argparse.Namespace(json=True)
        rc = cmd_status(args)
        assert isinstance(rc, int)

    @mock.patch("murphy_cli._api_get", return_value=None)
    @mock.patch("murphy_cli._read_live", return_value=None)
    @mock.patch("murphy_cli._dbus_call", return_value=None)
    def test_status_no_data(self, *_):
        args = argparse.Namespace(json=False)
        rc = cmd_status(args)
        assert isinstance(rc, int)


# ── exit codes ────────────────────────────────────────────────────────────
class TestExitCodes:
    def test_version_returns_zero(self):
        args = argparse.Namespace()
        rc = cmd_version(args)
        assert rc == 0

    @mock.patch("murphy_cli._api_get", return_value={"score": 88})
    @mock.patch("murphy_cli._read_live", return_value=None)
    @mock.patch("murphy_cli._dbus_call", return_value=None)
    def test_confidence_returns_int(self, *_):
        args = argparse.Namespace(json=False)
        rc = cmd_confidence(args)
        assert isinstance(rc, int)

    @mock.patch("murphy_cli._api_get", return_value=None)
    @mock.patch("murphy_cli._read_live", return_value=None)
    @mock.patch("murphy_cli._dbus_call", return_value=None)
    def test_engine_list_returns_int(self, *_):
        args = argparse.Namespace(json=False)
        rc = cmd_engine_list(args)
        assert isinstance(rc, int)


# ── error handling when data sources fail ─────────────────────────────────
class TestErrorHandling:
    @mock.patch("murphy_cli._api_get", return_value=None)
    @mock.patch("murphy_cli._read_live", return_value=None)
    @mock.patch("murphy_cli._dbus_call", return_value=None)
    def test_get_all_sources_fail(self, *_):
        from murphy_cli import _get
        result = _get("/api/status", "status")
        assert result is None

    def test_main_no_args_shows_help(self):
        with pytest.raises(SystemExit) as exc:
            main(["--help"])
        assert exc.value.code == 0

    def test_main_version(self):
        rc = main(["version"])
        assert rc == 0

    @mock.patch("murphy_cli._api_get", return_value=None)
    @mock.patch("murphy_cli._read_live", return_value=None)
    @mock.patch("murphy_cli._dbus_call", return_value=None)
    def test_main_status_graceful(self, *_):
        rc = main(["status"])
        assert isinstance(rc, int)


# ── output helpers ────────────────────────────────────────────────────────
class TestOutputHelpers:
    def test_version_string(self):
        assert isinstance(__version__, str)
        assert "." in __version__

    def test_error_does_not_raise(self, capsys):
        _error("test error message")
        captured = capsys.readouterr()
        assert "error" in captured.err.lower() or len(captured.err) > 0
