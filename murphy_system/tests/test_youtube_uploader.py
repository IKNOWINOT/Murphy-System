"""
Tests for youtube_uploader.py

Coverage:
  - UploadResult dataclass
  - YouTubeUploader graceful degradation (api_unavailable → save locally)
  - Quota tracking (get_remaining, consume, overflow)
  - is_authenticated (no file, invalid file, valid file)
  - upload_video (api unavailable → saved_locally)
  - History tracking
  - Quota status dict structure

All YouTube API calls are mocked — no external service dependencies.

Copyright © 2020 Inoni Limited Liability Company
License: BSL 1.1
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


from youtube_uploader import (
    _DAILY_QUOTA_LIMIT,
    _UPLOAD_QUOTA_COST,
    _QuotaTracker,
    UploadResult,
    YouTubeUploader,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_metadata(**kwargs):
    defaults = dict(
        metadata_id="meta-001",
        run_id="run-yt-001",
        title="[Murphy System] test: Deploy — 88% confidence (Jan 01)",
        description="A great run.",
        tags=["murphy system"],
        thumbnail_path=None,
        category_id="28",
        privacy="unlisted",
        chapters_text="00:00 Intro",
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _make_uploader(tmp_path: Path) -> YouTubeUploader:
    creds_path = tmp_path / "yt_creds.json"
    secrets_path = tmp_path / "client_secrets.json"
    quota_path = tmp_path / "quota.json"
    return YouTubeUploader(
        credentials_path=creds_path,
        client_secrets_path=secrets_path,
        quota_path=quota_path,
    )


# ---------------------------------------------------------------------------
# UploadResult
# ---------------------------------------------------------------------------

class TestUploadResult:
    def test_to_dict_has_required_keys(self):
        result = UploadResult(
            upload_id="uid-001",
            run_id="run-001",
            video_id=None,
            video_url=None,
            upload_status="saved_locally",
            quota_used=0,
            manual_package_path="/tmp/pkg.json",
            message="saved",
        )
        d = result.to_dict()
        for key in ("upload_id", "run_id", "upload_status", "quota_used", "message"):
            assert key in d


# ---------------------------------------------------------------------------
# Quota tracker
# ---------------------------------------------------------------------------

class TestQuotaTracker:
    def test_get_remaining_no_file(self, tmp_path):
        tracker = _QuotaTracker(tmp_path / "quota.json")
        assert tracker.get_remaining() == _DAILY_QUOTA_LIMIT

    def test_consume_reduces_remaining(self, tmp_path):
        tracker = _QuotaTracker(tmp_path / "quota.json")
        remaining = tracker.consume(1000)
        assert remaining == _DAILY_QUOTA_LIMIT - 1000

    def test_consume_overflow_returns_minus_one(self, tmp_path):
        tracker = _QuotaTracker(tmp_path / "quota.json")
        tracker.consume(_DAILY_QUOTA_LIMIT - 100)
        result = tracker.consume(500)
        assert result == -1

    def test_resets_on_new_day(self, tmp_path):
        quota_path = tmp_path / "quota.json"
        yesterday = {"date": "2000-01-01", "used": 9000}
        with open(str(quota_path), "w", encoding="utf-8") as fh:
            json.dump(yesterday, fh)
        tracker = _QuotaTracker(quota_path)
        assert tracker.get_remaining() == _DAILY_QUOTA_LIMIT


# ---------------------------------------------------------------------------
# YouTubeUploader — graceful degradation
# ---------------------------------------------------------------------------

class TestYouTubeUploaderDegradation:
    def test_api_unavailable_saves_locally(self, tmp_path):
        uploader = _make_uploader(tmp_path)
        uploader._api_available = False
        meta = _make_metadata()
        result = uploader.upload_video("/tmp/fake_video.mp4", meta)
        assert result.upload_status == "saved_locally"
        assert result.video_id is None
        assert result.video_url is None

    def test_not_authenticated_saves_locally(self, tmp_path):
        uploader = _make_uploader(tmp_path)
        uploader._api_available = True
        meta = _make_metadata()
        result = uploader.upload_video("/tmp/fake_video.mp4", meta)
        assert result.upload_status == "saved_locally"

    def test_quota_exhausted_saves_locally(self, tmp_path):
        uploader = _make_uploader(tmp_path)
        uploader._api_available = True
        uploader._quota.consume(_DAILY_QUOTA_LIMIT)
        meta = _make_metadata()
        result = uploader.upload_video("/tmp/fake_video.mp4", meta)
        assert result.upload_status == "saved_locally"

    def test_saved_locally_creates_manifest(self, tmp_path):
        uploader = _make_uploader(tmp_path)
        uploader._api_available = False
        meta = _make_metadata()
        result = uploader.upload_video("/tmp/fake_video.mp4", meta)
        assert result.manual_package_path is not None

    def test_history_tracked_after_local_save(self, tmp_path):
        uploader = _make_uploader(tmp_path)
        uploader._api_available = False
        meta = _make_metadata()
        uploader.upload_video("/tmp/fake_video.mp4", meta)
        uploader.upload_video("/tmp/fake_video.mp4", meta)
        history = uploader.get_history()
        assert len(history) == 2

    def test_quota_status_structure(self, tmp_path):
        uploader = _make_uploader(tmp_path)
        status = uploader.get_quota_status()
        assert "daily_limit" in status
        assert "remaining" in status
        assert "used" in status
        assert "upload_cost" in status
        assert status["daily_limit"] == _DAILY_QUOTA_LIMIT


# ---------------------------------------------------------------------------
# is_authenticated
# ---------------------------------------------------------------------------

class TestIsAuthenticated:
    def test_no_credentials_file(self, tmp_path):
        uploader = _make_uploader(tmp_path)
        assert uploader.is_authenticated() is False

    def test_empty_credentials_file(self, tmp_path):
        uploader = _make_uploader(tmp_path)
        creds_path = tmp_path / "yt_creds.json"
        with open(str(creds_path), "w", encoding="utf-8") as fh:
            json.dump({}, fh)
        assert uploader.is_authenticated() is False

    def test_valid_token_in_credentials(self, tmp_path):
        uploader = _make_uploader(tmp_path)
        creds_path = tmp_path / "yt_creds.json"
        creds_path.parent.mkdir(parents=True, exist_ok=True)
        with open(str(creds_path), "w", encoding="utf-8") as fh:
            json.dump({"token": "some_token_value", "refresh_token": "some_refresh"}, fh)
        assert uploader.is_authenticated() is True
