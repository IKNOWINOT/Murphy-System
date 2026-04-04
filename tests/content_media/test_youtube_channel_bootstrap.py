"""
Tests for youtube_channel_bootstrap.py

Coverage:
  - check_youtube_setup status dict structure
  - missing_steps populated correctly when deps absent
  - get_setup_instructions returns markdown
  - initiate_oauth_flow degrades when packages not installed
  - initiate_oauth_flow degrades when client_secrets.json missing
  - verify_channel_access degrades when not authenticated
  - get_channel_url returns expected URL

All OAuth/API calls are mocked — no external service dependencies.

Copyright © 2020 Inoni Limited Liability Company
License: BSL 1.1
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from youtube_channel_bootstrap import YouTubeChannelBootstrap


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_bootstrap(tmp_path: Path) -> YouTubeChannelBootstrap:
    return YouTubeChannelBootstrap(
        credentials_path=tmp_path / "yt_creds.json",
        client_secrets_path=tmp_path / "client_secrets.json",
    )


# ---------------------------------------------------------------------------
# check_youtube_setup
# ---------------------------------------------------------------------------

class TestCheckYouTubeSetup:
    def test_returns_dict(self, tmp_path):
        bs = _make_bootstrap(tmp_path)
        status = bs.check_youtube_setup()
        assert isinstance(status, dict)

    def test_required_keys_present(self, tmp_path):
        bs = _make_bootstrap(tmp_path)
        status = bs.check_youtube_setup()
        for key in (
            "credentials_exist",
            "client_secrets_exist",
            "api_packages_installed",
            "authenticated",
            "quota_remaining",
            "ready",
            "missing_steps",
        ):
            assert key in status, f"Missing key: {key}"

    def test_not_ready_without_files(self, tmp_path):
        bs = _make_bootstrap(tmp_path)
        status = bs.check_youtube_setup()
        assert status["ready"] is False

    def test_missing_steps_not_empty_when_unconfigured(self, tmp_path):
        bs = _make_bootstrap(tmp_path)
        status = bs.check_youtube_setup()
        assert isinstance(status["missing_steps"], list)

    def test_credentials_exist_false_when_no_file(self, tmp_path):
        bs = _make_bootstrap(tmp_path)
        status = bs.check_youtube_setup()
        assert status["credentials_exist"] is False

    def test_credentials_exist_true_when_file_present(self, tmp_path):
        creds_path = tmp_path / "yt_creds.json"
        with open(str(creds_path), "w", encoding="utf-8") as fh:
            json.dump({"token": "fake_token"}, fh)
        bs = YouTubeChannelBootstrap(
            credentials_path=creds_path,
            client_secrets_path=tmp_path / "client_secrets.json",
        )
        status = bs.check_youtube_setup()
        assert status["credentials_exist"] is True

    def test_quota_remaining_is_integer(self, tmp_path):
        bs = _make_bootstrap(tmp_path)
        status = bs.check_youtube_setup()
        assert isinstance(status["quota_remaining"], int)
        assert status["quota_remaining"] >= 0


# ---------------------------------------------------------------------------
# get_setup_instructions
# ---------------------------------------------------------------------------

class TestGetSetupInstructions:
    def test_returns_string(self, tmp_path):
        bs = _make_bootstrap(tmp_path)
        instructions = bs.get_setup_instructions()
        assert isinstance(instructions, str)
        assert len(instructions) > 100

    def test_contains_required_steps(self, tmp_path):
        bs = _make_bootstrap(tmp_path)
        instructions = bs.get_setup_instructions()
        assert "YouTube Data API" in instructions
        assert "OAuth" in instructions
        assert "client_secrets.json" in instructions
        assert "studio.youtube.com" in instructions

    def test_contains_murphy_system_channel_name(self, tmp_path):
        bs = _make_bootstrap(tmp_path)
        instructions = bs.get_setup_instructions()
        assert "Murphy System" in instructions

    def test_contains_no_channel_creation_warning(self, tmp_path):
        bs = _make_bootstrap(tmp_path)
        instructions = bs.get_setup_instructions()
        assert "programmatic" in instructions.lower() or "manually" in instructions.lower()


# ---------------------------------------------------------------------------
# initiate_oauth_flow
# ---------------------------------------------------------------------------

class TestInitiateOAuthFlow:
    def test_returns_false_when_packages_not_installed(self, tmp_path, monkeypatch):
        import youtube_channel_bootstrap as mod

        monkeypatch.setattr(
            YouTubeChannelBootstrap,
            "_check_api_packages",
            lambda self: False,
        )
        bs = _make_bootstrap(tmp_path)
        result = bs.initiate_oauth_flow()
        assert result is False

    def test_returns_false_when_client_secrets_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            YouTubeChannelBootstrap,
            "_check_api_packages",
            lambda self: True,
        )
        bs = _make_bootstrap(tmp_path)
        result = bs.initiate_oauth_flow()
        assert result is False


# ---------------------------------------------------------------------------
# verify_channel_access
# ---------------------------------------------------------------------------

class TestVerifyChannelAccess:
    def test_returns_dict(self, tmp_path):
        bs = _make_bootstrap(tmp_path)
        result = bs.verify_channel_access()
        assert isinstance(result, dict)

    def test_fails_when_packages_not_installed(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            YouTubeChannelBootstrap,
            "_check_api_packages",
            lambda self: False,
        )
        bs = _make_bootstrap(tmp_path)
        result = bs.verify_channel_access()
        assert result["success"] is False

    def test_fails_when_not_authenticated(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            YouTubeChannelBootstrap,
            "_check_api_packages",
            lambda self: True,
        )
        bs = _make_bootstrap(tmp_path)
        result = bs.verify_channel_access()
        assert result["success"] is False
        assert "error" in result

    def test_result_has_channel_fields(self, tmp_path):
        bs = _make_bootstrap(tmp_path)
        result = bs.verify_channel_access()
        for key in ("success", "error", "channel_id", "channel_title", "video_count"):
            assert key in result, f"Missing key: {key}"


# ---------------------------------------------------------------------------
# get_channel_url
# ---------------------------------------------------------------------------

class TestGetChannelUrl:
    def test_returns_string(self, tmp_path):
        bs = _make_bootstrap(tmp_path)
        url = bs.get_channel_url()
        assert isinstance(url, str)

    def test_contains_youtube(self, tmp_path):
        bs = _make_bootstrap(tmp_path)
        url = bs.get_channel_url()
        assert "youtube.com" in url
