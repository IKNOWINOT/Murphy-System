"""
Tests for youtube_metadata_generator.py

Coverage:
  - Title generation (format, length limits, special chars)
  - Description generation (required sections, length)
  - Tag generation (standard tags, deduplication, task-derived)
  - Chapters text formatting
  - Thumbnail generation (when Pillow available)
  - YouTubeMetadata.to_dict
  - History tracking

Copyright © 2020 Inoni Limited Liability Company
License: BSL 1.1
"""

from __future__ import annotations

import os
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from youtube_metadata_generator import (
    CATEGORY_SCIENCE_TECH,
    PRIVACY_UNLISTED,
    YouTubeMetadata,
    YouTubeMetadataGenerator,
    _ALPHA_DISCLAIMER,
    _GITHUB_REPO,
    _MAX_TITLE_LEN,
    generate_thumbnail,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_recording(**kwargs):
    defaults = dict(
        run_id="run-yt-meta-001",
        task_description="Automate invoice processing pipeline",
        task_type="finance",
        status="SUCCESS_COMPLETED",
        confidence_score=0.92,
        confidence_progression=[{"timestamp": "t0", "confidence": 0.92}],
        steps=[{"step_id": f"s{i}", "success": True} for i in range(4)],
        hitl_decisions=[],
        modules_used=["invoice_engine", "pdf_parser", "email_notifier"],
        gates_passed=["RISK_GATE", "CONFIDENCE_GATE"],
        duration_seconds=67.0,
        system_version="1.0",
        started_at="2024-01-01T00:00:00Z",
        completed_at="2024-01-01T00:01:07Z",
        terminal_output=[],
        metadata={},
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _make_chapter(ts: int, title: str):
    class _Ch:
        def __init__(self, timestamp: int, ttl: str):
            self.timestamp_seconds = timestamp
            self.title = ttl
            self._ts = timestamp
            self._ttl = ttl

        def to_description_line(self) -> str:
            m = self._ts // 60
            s = self._ts % 60
            return f"{m:02d}:{s:02d} {self._ttl}"
    return _Ch(ts, title)


# ---------------------------------------------------------------------------
# Title generation
# ---------------------------------------------------------------------------

class TestTitleGeneration:
    def test_title_contains_murphy_system(self):
        gen = YouTubeMetadataGenerator()
        rec = _make_recording()
        meta = gen.generate(rec)
        assert "[Murphy System]" in meta.title

    def test_title_contains_task_type(self):
        gen = YouTubeMetadataGenerator()
        rec = _make_recording(task_type="devops")
        meta = gen.generate(rec)
        assert "devops" in meta.title

    def test_title_contains_confidence_pct(self):
        gen = YouTubeMetadataGenerator()
        rec = _make_recording(confidence_score=0.92)
        meta = gen.generate(rec)
        assert "92%" in meta.title

    def test_title_max_length(self):
        gen = YouTubeMetadataGenerator()
        rec = _make_recording(task_description="A" * 200)
        meta = gen.generate(rec)
        assert len(meta.title) <= _MAX_TITLE_LEN

    def test_title_very_long_task_name_truncated(self):
        gen = YouTubeMetadataGenerator()
        rec = _make_recording(task_description="x" * 150)
        meta = gen.generate(rec)
        assert len(meta.title) <= _MAX_TITLE_LEN

    def test_title_special_chars_handled(self):
        gen = YouTubeMetadataGenerator()
        rec = _make_recording(task_description="Deploy <service> & fix 100% issues!")
        meta = gen.generate(rec)
        assert meta.title is not None
        assert len(meta.title) > 0


# ---------------------------------------------------------------------------
# Description generation
# ---------------------------------------------------------------------------

class TestDescriptionGeneration:
    def test_description_contains_github_link(self):
        gen = YouTubeMetadataGenerator()
        rec = _make_recording()
        meta = gen.generate(rec)
        assert _GITHUB_REPO in meta.description

    def test_description_contains_alpha_disclaimer(self):
        gen = YouTubeMetadataGenerator()
        rec = _make_recording()
        meta = gen.generate(rec)
        assert "ALPHA SOFTWARE" in meta.description.upper() or "alpha" in meta.description.lower()

    def test_description_contains_inoni_attribution(self):
        gen = YouTubeMetadataGenerator()
        rec = _make_recording()
        meta = gen.generate(rec)
        assert "Inoni" in meta.description

    def test_description_has_run_details(self):
        gen = YouTubeMetadataGenerator()
        rec = _make_recording(task_type="finance", confidence_score=0.92)
        meta = gen.generate(rec)
        assert "finance" in meta.description
        assert "92%" in meta.description

    def test_description_with_chapters(self):
        gen = YouTubeMetadataGenerator()
        rec = _make_recording()
        chapters = [_make_chapter(0, "Intro"), _make_chapter(30, "Main")]
        meta = gen.generate(rec, chapters=chapters)
        assert "00:00" in meta.description or "CHAPTERS" in meta.description

    def test_description_max_length(self):
        gen = YouTubeMetadataGenerator()
        rec = _make_recording(task_description="x" * 500, modules_used=["m"] * 50)
        meta = gen.generate(rec)
        assert len(meta.description) <= 5000


# ---------------------------------------------------------------------------
# Tag generation
# ---------------------------------------------------------------------------

class TestTagGeneration:
    def test_standard_tags_present(self):
        gen = YouTubeMetadataGenerator()
        rec = _make_recording()
        meta = gen.generate(rec)
        assert "murphy system" in meta.tags
        assert "ai automation" in meta.tags

    def test_task_type_in_tags(self):
        gen = YouTubeMetadataGenerator()
        rec = _make_recording(task_type="robotics")
        meta = gen.generate(rec)
        assert "robotics" in meta.tags

    def test_no_duplicate_tags(self):
        gen = YouTubeMetadataGenerator()
        rec = _make_recording()
        meta = gen.generate(rec)
        assert len(meta.tags) == len(set(meta.tags))

    def test_high_confidence_tag(self):
        gen = YouTubeMetadataGenerator()
        rec = _make_recording(confidence_score=0.90)
        meta = gen.generate(rec)
        assert "high confidence" in meta.tags

    def test_med_confidence_tag(self):
        gen = YouTubeMetadataGenerator()
        rec = _make_recording(confidence_score=0.65)
        meta = gen.generate(rec)
        assert "medium confidence" in meta.tags

    def test_low_confidence_tag(self):
        gen = YouTubeMetadataGenerator()
        rec = _make_recording(confidence_score=0.30)
        meta = gen.generate(rec)
        assert "low confidence" in meta.tags


# ---------------------------------------------------------------------------
# Metadata structure
# ---------------------------------------------------------------------------

class TestYouTubeMetadata:
    def test_category_is_science_tech(self):
        gen = YouTubeMetadataGenerator()
        rec = _make_recording()
        meta = gen.generate(rec)
        assert meta.category_id == CATEGORY_SCIENCE_TECH

    def test_default_privacy_unlisted(self):
        gen = YouTubeMetadataGenerator()
        rec = _make_recording()
        meta = gen.generate(rec)
        assert meta.privacy == PRIVACY_UNLISTED

    def test_custom_privacy(self):
        gen = YouTubeMetadataGenerator()
        rec = _make_recording()
        meta = gen.generate(rec, privacy="public")
        assert meta.privacy == "public"

    def test_to_dict_has_required_keys(self):
        gen = YouTubeMetadataGenerator()
        rec = _make_recording()
        meta = gen.generate(rec)
        d = meta.to_dict()
        for key in ("metadata_id", "run_id", "title", "description", "tags", "category_id", "privacy"):
            assert key in d, f"Missing key: {key}"

    def test_history_tracked(self, tmp_path):
        gen = YouTubeMetadataGenerator(thumbnail_dir=str(tmp_path))
        rec = _make_recording()
        gen.generate(rec)
        gen.generate(rec)
        history = gen.get_history()
        assert len(history) >= 2


# ---------------------------------------------------------------------------
# Thumbnail
# ---------------------------------------------------------------------------

class TestThumbnailGeneration:
    def test_thumbnail_generation_when_pillow_available(self, tmp_path):
        try:
            from PIL import Image  # noqa: F401
        except ImportError:
            pytest.skip("Pillow not available")

        rec = _make_recording()
        out_path = str(tmp_path / "thumb.png")
        result = generate_thumbnail(rec, out_path)
        assert result is True
        assert os.path.exists(out_path)
        assert os.path.getsize(out_path) > 0

    def test_thumbnail_returns_false_without_pillow(self, tmp_path, monkeypatch):
        import youtube_metadata_generator as mod

        def _no_pillow():
            return False

        monkeypatch.setattr(mod, "_pillow_available", _no_pillow)
        rec = _make_recording()
        out_path = str(tmp_path / "thumb.png")
        result = mod.generate_thumbnail(rec, out_path)
        assert result is False
