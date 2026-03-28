"""
Tests for announcer_voice_engine.py (MercyAnnouncer persona)

Coverage:
  - MercyAnnouncer all script builders (hook, confidence, hitl, module, step, close, cta)
  - Script content reacts to run data (confidence score, status, hitl count)
  - AnnouncerVoiceEngine.generate_script_only (no TTS required)
  - AnnouncerVoiceEngine.narrate (produces AudioPackage)
  - AnnouncerScript.to_dict / AudioPackage.to_dict
  - TTS backend detection returns valid backend
  - Text fallback always produces a file
  - History tracking
  - get_stats structure

Copyright © 2020 Inoni Limited Liability Company
License: BSL 1.1
"""

from __future__ import annotations

import os
from types import SimpleNamespace

import pytest


from announcer_voice_engine import (
    TTSBackend,
    AnnouncerScript,
    AnnouncerVoiceEngine,
    AudioPackage,
    MercyAnnouncer,
    _detect_tts_backend,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_recording(confidence: float = 0.88, status: str = "SUCCESS_COMPLETED", **kwargs):
    defaults = dict(
        run_id="run-announce-001",
        task_description="Deploy microservice to production cluster",
        task_type="devops",
        status=status,
        confidence_score=confidence,
        confidence_progression=[{"timestamp": "t0", "confidence": confidence}],
        steps=[{"step_id": f"s{i}", "success": True} for i in range(4)],
        hitl_decisions=[{"decision": "approved"}, {"decision": "approved"}],
        modules_used=["deploy_engine", "health_check", "rollback"],
        gates_passed=["RISK_GATE"],
        duration_seconds=55.0,
        system_version="1.0",
        started_at="2024-01-01T00:00:00Z",
        completed_at="2024-01-01T00:00:55Z",
        terminal_output=["Deploying...", "Done."],
        metadata={},
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


# ---------------------------------------------------------------------------
# MercyAnnouncer persona
# ---------------------------------------------------------------------------

class TestMercyAnnouncer:
    def test_build_hook_returns_non_empty(self):
        persona = MercyAnnouncer()
        rec = _make_recording()
        hook = persona.build_hook(rec, seed=42)
        assert isinstance(hook, str)
        assert len(hook) > 20

    def test_build_hook_contains_task_name(self):
        persona = MercyAnnouncer()
        rec = _make_recording(task_description="Deploy payment service")
        hook = persona.build_hook(rec, seed=42)
        assert "Deploy payment service" in hook or "Deploy payment" in hook

    def test_high_confidence_line(self):
        persona = MercyAnnouncer()
        rec = _make_recording(confidence=0.92)
        line = persona.build_confidence_line(rec, seed=1)
        assert "92" in line or "%" in line

    def test_medium_confidence_line(self):
        persona = MercyAnnouncer()
        rec = _make_recording(confidence=0.65)
        line = persona.build_confidence_line(rec, seed=1)
        assert isinstance(line, str)
        assert len(line) > 10

    def test_low_confidence_line(self):
        persona = MercyAnnouncer()
        rec = _make_recording(confidence=0.35)
        line = persona.build_confidence_line(rec, seed=1)
        assert isinstance(line, str)
        assert "35" in line or "%" in line

    def test_hitl_commentary_with_decisions(self):
        persona = MercyAnnouncer()
        line = persona.build_hitl_commentary(decision_count=3, seed=5)
        assert "3" in line or "decision" in line.lower()

    def test_hitl_commentary_zero_decisions(self):
        persona = MercyAnnouncer()
        line = persona.build_hitl_commentary(decision_count=0, seed=5)
        assert "Zero" in line or "zero" in line or "autonomous" in line.lower()

    def test_module_hype_with_count(self):
        persona = MercyAnnouncer()
        line = persona.build_module_hype(module_count=7, seed=3)
        assert "7" in line

    def test_step_transition_contains_step_number(self):
        persona = MercyAnnouncer()
        line = persona.build_step_transition(step_idx=2, total=5, seed=0)
        assert "3" in line or "Step" in line

    def test_success_close_contains_confidence(self):
        persona = MercyAnnouncer()
        rec = _make_recording(confidence=0.88)
        line = persona.build_success_close(rec, seed=7)
        assert "88" in line or "%" in line

    def test_failure_open_contains_task(self):
        persona = MercyAnnouncer()
        rec = _make_recording(task_description="Fix the database migration")
        line = persona.build_failure_open(rec, seed=7)
        assert "Fix the database" in line or "database" in line.lower()

    def test_subscribe_cta_non_empty(self):
        persona = MercyAnnouncer()
        cta = persona.build_subscribe_cta(seed=0)
        assert len(cta) > 10
        assert "subscribe" in cta.lower() or "Subscribe" in cta

    def test_catchphrase_non_empty(self):
        persona = MercyAnnouncer()
        cp = persona.build_catchphrase(seed=0)
        assert isinstance(cp, str)
        assert len(cp) > 10

    def test_different_seeds_give_variety(self):
        persona = MercyAnnouncer()
        catchphrases = {persona.build_catchphrase(seed=i) for i in range(len(persona._CATCHPHRASES))}
        assert len(catchphrases) > 1


# ---------------------------------------------------------------------------
# AnnouncerVoiceEngine
# ---------------------------------------------------------------------------

class TestAnnouncerVoiceEngine:
    def test_generate_script_only(self, tmp_path):
        engine = AnnouncerVoiceEngine(output_dir=str(tmp_path))
        rec = _make_recording()
        script = engine.generate_script_only(rec)
        assert isinstance(script, AnnouncerScript)
        assert len(script.full_script) > 50
        assert script.run_id == rec.run_id

    def test_narrate_returns_audio_package(self, tmp_path):
        engine = AnnouncerVoiceEngine(output_dir=str(tmp_path))
        rec = _make_recording()
        pkg = engine.narrate(rec)
        assert isinstance(pkg, AudioPackage)
        assert pkg.run_id == rec.run_id

    def test_narrate_creates_output_dir(self, tmp_path):
        engine = AnnouncerVoiceEngine(output_dir=str(tmp_path))
        rec = _make_recording()
        pkg = engine.narrate(rec)
        assert os.path.isdir(pkg.output_dir)

    def test_narrate_produces_audio_or_text_file(self, tmp_path):
        engine = AnnouncerVoiceEngine(output_dir=str(tmp_path))
        rec = _make_recording()
        pkg = engine.narrate(rec)
        assert pkg.audio_path is not None
        assert os.path.exists(pkg.audio_path)

    def test_text_fallback_always_works(self, tmp_path):
        engine = AnnouncerVoiceEngine(output_dir=str(tmp_path))
        engine._tts_backend = TTSBackend.TEXT
        rec = _make_recording()
        pkg = engine.narrate(rec)
        assert pkg.audio_path is not None
        assert pkg.audio_path.endswith(".txt")
        assert os.path.exists(pkg.audio_path)

    def test_text_file_contains_script(self, tmp_path):
        engine = AnnouncerVoiceEngine(output_dir=str(tmp_path))
        engine._tts_backend = TTSBackend.TEXT
        rec = _make_recording()
        pkg = engine.narrate(rec)
        with open(pkg.audio_path, encoding="utf-8") as fh:
            content = fh.read()
        assert len(content) > 100
        assert "HOOK" in content or "Murphy" in content

    def test_history_tracked(self, tmp_path):
        engine = AnnouncerVoiceEngine(output_dir=str(tmp_path))
        rec = _make_recording()
        engine.narrate(rec)
        engine.narrate(rec)
        history = engine.get_history()
        assert len(history) == 2

    def test_get_stats(self, tmp_path):
        engine = AnnouncerVoiceEngine(output_dir=str(tmp_path))
        rec = _make_recording()
        engine.narrate(rec)
        stats = engine.get_stats()
        assert "total_narrations" in stats
        assert stats["total_narrations"] == 1
        assert stats["persona"] == "MercyAnnouncer"


# ---------------------------------------------------------------------------
# AnnouncerScript data model
# ---------------------------------------------------------------------------

class TestAnnouncerScript:
    def test_to_dict_has_required_keys(self, tmp_path):
        engine = AnnouncerVoiceEngine(output_dir=str(tmp_path))
        rec = _make_recording()
        script = engine.generate_script_only(rec)
        d = script.to_dict()
        for key in (
            "script_id", "run_id", "hook", "confidence_line",
            "hitl_commentary", "module_hype", "step_narrations",
            "success_or_failure_close", "subscribe_cta", "catchphrase",
            "full_script",
        ):
            assert key in d, f"Missing key: {key}"

    def test_full_script_has_all_sections(self, tmp_path):
        engine = AnnouncerVoiceEngine(output_dir=str(tmp_path))
        rec = _make_recording()
        script = engine.generate_script_only(rec)
        assert "HOOK" in script.full_script
        assert "RESULT" in script.full_script
        assert "CALL TO ACTION" in script.full_script


# ---------------------------------------------------------------------------
# TTS backend detection
# ---------------------------------------------------------------------------

class TestTTSBackendDetection:
    def test_detect_tts_backend_returns_valid(self):
        backend = _detect_tts_backend()
        assert backend in (TTSBackend.PYTTSX3, TTSBackend.ESPEAK, TTSBackend.TEXT)

    def test_engine_reports_backend(self, tmp_path):
        engine = AnnouncerVoiceEngine(output_dir=str(tmp_path))
        backend = engine.get_tts_backend()
        assert backend in (TTSBackend.PYTTSX3, TTSBackend.ESPEAK, TTSBackend.TEXT)
