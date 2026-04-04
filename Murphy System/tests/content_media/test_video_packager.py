"""
Tests for video_packager.py

Coverage:
  - _detect_mode returns valid mode
  - _confidence_bar formatting
  - _generate_chapters creates correct chapter structure
  - VideoPackager.package (all modes, static fallback)
  - VideoPackage.to_dict round-trip
  - History tracking + bounded
  - Mode detection helpers

Copyright © 2020 Inoni Limited Liability Company
License: BSL 1.1
"""

from __future__ import annotations

import os
import sys
import tempfile
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from video_packager import (
    VideoChapter,
    VideoMode,
    VideoPackage,
    VideoPackager,
    _confidence_bar,
    _detect_mode,
    _ffmpeg_available,
    _generate_chapters,
    _pillow_available,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_recording(**kwargs):
    defaults = dict(
        run_id="run-vid-001",
        task_description="Automate CI pipeline",
        task_type="devops",
        status="SUCCESS_COMPLETED",
        confidence_score=0.87,
        confidence_progression=[
            {"timestamp": "t0", "confidence": 0.60},
            {"timestamp": "t1", "confidence": 0.80},
            {"timestamp": "t2", "confidence": 0.87},
        ],
        steps=[
            {"step_id": f"s{i}", "success": True}
            for i in range(6)
        ],
        hitl_decisions=[{"decision": "approved"}],
        modules_used=["mod_a", "mod_b"],
        gates_passed=["RISK_GATE"],
        duration_seconds=95.0,
        system_version="1.0",
        started_at="2024-01-01T00:00:00Z",
        completed_at="2024-01-01T00:01:35Z",
        terminal_output=["Done."],
        metadata={},
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class TestConfidenceBar:
    def test_full_bar(self):
        bar = _confidence_bar(1.0, width=10)
        assert "100%" in bar
        assert "█" * 10 in bar

    def test_zero_bar(self):
        bar = _confidence_bar(0.0, width=10)
        assert "0%" in bar
        assert "░" * 10 in bar

    def test_half_bar(self):
        bar = _confidence_bar(0.5, width=10)
        assert "50%" in bar
        assert "█" * 5 in bar


class TestGenerateChapters:
    def test_returns_list(self):
        rec = _make_recording()
        chapters = _generate_chapters(rec, 120.0)
        assert isinstance(chapters, list)
        assert len(chapters) >= 2

    def test_first_chapter_zero(self):
        rec = _make_recording()
        chapters = _generate_chapters(rec, 120.0)
        assert chapters[0].timestamp_seconds == 0

    def test_chapters_sorted(self):
        rec = _make_recording()
        chapters = _generate_chapters(rec, 120.0)
        timestamps = [c.timestamp_seconds for c in chapters]
        assert timestamps == sorted(timestamps)

    def test_chapters_no_duplicates(self):
        rec = _make_recording()
        chapters = _generate_chapters(rec, 120.0)
        timestamps = [c.timestamp_seconds for c in chapters]
        assert len(timestamps) == len(set(timestamps))

    def test_chapter_format_timestamp(self):
        ch = VideoChapter(125, "Test")
        assert ch.format_timestamp() == "02:05"

    def test_chapter_to_description_line(self):
        ch = VideoChapter(65, "My Chapter")
        line = ch.to_description_line()
        assert "01:05" in line
        assert "My Chapter" in line


# ---------------------------------------------------------------------------
# Mode detection
# ---------------------------------------------------------------------------

class TestModeDetection:
    def test_detect_mode_returns_valid_mode(self):
        mode = _detect_mode()
        assert mode in (VideoMode.FFMPEG, VideoMode.PILLOW, VideoMode.STATIC)

    def test_pillow_available_bool(self):
        result = _pillow_available()
        assert isinstance(result, bool)

    def test_ffmpeg_available_bool(self):
        result = _ffmpeg_available()
        assert isinstance(result, bool)


# ---------------------------------------------------------------------------
# VideoPackager
# ---------------------------------------------------------------------------

class TestVideoPackager:
    def test_package_returns_video_package(self, tmp_path):
        packager = VideoPackager(output_dir=str(tmp_path))
        rec = _make_recording()
        pkg = packager.package(rec)
        assert isinstance(pkg, VideoPackage)
        assert pkg.run_id == rec.run_id

    def test_package_static_mode_always_works(self, tmp_path):
        packager = VideoPackager(output_dir=str(tmp_path))
        rec = _make_recording()
        pkg = packager.package(rec, force_mode=VideoMode.STATIC)
        assert pkg.mode == VideoMode.STATIC
        assert pkg.summary_path is not None
        assert os.path.exists(pkg.summary_path)

    def test_package_creates_summary_json(self, tmp_path):
        packager = VideoPackager(output_dir=str(tmp_path))
        rec = _make_recording()
        pkg = packager.package(rec, force_mode=VideoMode.STATIC)
        assert os.path.exists(pkg.summary_path)
        import json
        with open(pkg.summary_path, encoding="utf-8") as fh:
            data = json.load(fh)
        assert data["run_id"] == rec.run_id
        assert "confidence_score" in data

    def test_package_creates_output_dir(self, tmp_path):
        packager = VideoPackager(output_dir=str(tmp_path))
        rec = _make_recording()
        pkg = packager.package(rec)
        assert os.path.isdir(pkg.output_dir)

    def test_package_has_chapters(self, tmp_path):
        packager = VideoPackager(output_dir=str(tmp_path))
        rec = _make_recording()
        pkg = packager.package(rec)
        assert isinstance(pkg.chapters, list)
        assert len(pkg.chapters) >= 2

    def test_package_to_dict(self, tmp_path):
        packager = VideoPackager(output_dir=str(tmp_path))
        rec = _make_recording()
        pkg = packager.package(rec, force_mode=VideoMode.STATIC)
        d = pkg.to_dict()
        assert d["run_id"] == rec.run_id
        assert "mode" in d
        assert "chapters" in d

    def test_history_tracks_packages(self, tmp_path):
        packager = VideoPackager(output_dir=str(tmp_path))
        rec = _make_recording()
        packager.package(rec, force_mode=VideoMode.STATIC)
        packager.package(rec, force_mode=VideoMode.STATIC)
        history = packager.get_history(limit=10)
        assert len(history) == 2

    def test_pillow_mode_if_available(self, tmp_path):
        if not _pillow_available():
            pytest.skip("Pillow not available")
        packager = VideoPackager(output_dir=str(tmp_path))
        rec = _make_recording()
        pkg = packager.package(rec, force_mode=VideoMode.PILLOW)
        assert pkg.mode in (VideoMode.PILLOW, VideoMode.STATIC)

    def test_get_mode_returns_string(self, tmp_path):
        packager = VideoPackager(output_dir=str(tmp_path))
        mode = packager.get_mode()
        assert isinstance(mode, str)
