"""Cap A.9 — transcribe_audio.

Reuses Murphy's existing faster-whisper installation (already used by
voice_bridge.py for the Twilio voice loop). No new dependency, no API
key required, no per-call cost.

Supported formats: anything ffmpeg can demux (mp3, wav, ogg, m4a, mp4,
flac, webm) — faster-whisper handles via ffmpeg internally.

Hard caps:
  - 25 MB max file size (matches Base44 superagent surface)
  - 600s (10 min) max audio duration (sanity guard)
  - English-only by default (tiny.en model); larger model swap point
    documented inline for future cap.
"""
from __future__ import annotations
import os
from pathlib import Path
from typing import Any, Dict, Optional
from ._path_guard import is_allowed, canonicalize

# Reuse the SAME loaded model voice_bridge uses (process-global singleton)
_WHISPER = None
MAX_AUDIO_BYTES = 25 * 1024 * 1024
MAX_AUDIO_SECONDS = 600
SUPPORTED_EXTS = {".wav", ".mp3", ".ogg", ".m4a", ".mp4", ".flac", ".webm", ".aac"}


def _get_whisper():
    """Lazy-init faster-whisper tiny.en — same model voice_bridge uses."""
    global _WHISPER
    if _WHISPER is None:
        from faster_whisper import WhisperModel
        _WHISPER = WhisperModel("tiny.en", device="cpu", compute_type="int8")
    return _WHISPER


def transcribe_audio(file_path: str, *, language: Optional[str] = None) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "ok": False, "file_path": file_path, "text": "",
        "segments": [], "duration_s": 0.0, "language": None,
        "model": "faster-whisper:tiny.en", "error": None,
    }
    try:
        if not file_path:
            out["error"] = "empty path"; return out
        if not is_allowed(file_path):
            out["error"] = "path not under allowed roots"; return out
        canon = canonicalize(file_path)
        if not os.path.exists(canon):
            out["error"] = "file does not exist"; return out
        if not os.path.isfile(canon):
            out["error"] = "not a regular file"; return out
        size = os.path.getsize(canon)
        if size > MAX_AUDIO_BYTES:
            out["error"] = f"file too large: {size} > {MAX_AUDIO_BYTES}"
            return out
        ext = Path(canon).suffix.lower()
        if ext not in SUPPORTED_EXTS:
            out["error"] = f"unsupported extension: {ext} (supported: {sorted(SUPPORTED_EXTS)})"
            return out

        model = _get_whisper()
        segments, info = model.transcribe(
            canon,
            language=language or "en",
            vad_filter=True,
        )
        if info.duration > MAX_AUDIO_SECONDS:
            out["error"] = f"audio too long: {info.duration:.1f}s > {MAX_AUDIO_SECONDS}s"
            return out

        seg_list = []
        full_text_parts = []
        for s in segments:
            seg_list.append({
                "start": round(s.start, 2),
                "end": round(s.end, 2),
                "text": s.text.strip(),
            })
            full_text_parts.append(s.text.strip())

        out["text"] = " ".join(full_text_parts)
        out["segments"] = seg_list
        out["duration_s"] = round(info.duration, 2)
        out["language"] = info.language
        out["language_probability"] = round(info.language_probability, 3)
        out["ok"] = True
        return out
    except FileNotFoundError as e:
        out["error"] = f"missing: {e}"; return out
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"; return out


def execute_transcribe_audio(**kwargs) -> Dict[str, Any]:
    return transcribe_audio(
        file_path=kwargs.get("file_path", "") or kwargs.get("path", ""),
        language=kwargs.get("language"),
    )
