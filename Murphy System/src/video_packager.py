"""
Video Packager — Converts AgentRunRecording into publishable video content.

Design Label: YT-002 — Video Package Generator
Owner: Platform Engineering / Content Team
Dependencies:
  - agent_run_recorder (AgentRunRecording)
  - ImageGenerationEngine (Pillow-based frame generation)

Three modes (auto-detected):
  A — ffmpeg composition: compose MP4 from generated frames + audio overlay
  B — Pillow frame-stitching: animated GIF or image sequence
  C — Static package: branded thumbnail + markdown/JSON summary (always available)

Safety invariants:
  - Thread-safe: all shared state guarded by Lock
  - Bounded: max 500 packages in history
  - Graceful degradation: always falls back to Mode C

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import tempfile
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)

# Murphy System brand palette
_BG_COLOR = (18, 18, 24)
_ACCENT_CYAN = (0, 212, 212)
_ACCENT_GREEN = (0, 230, 118)
_ACCENT_AMBER = (255, 193, 7)
_TEXT_WHITE = (230, 230, 235)
_TEXT_DIM = (120, 120, 135)
_RED = (220, 50, 50)

_MAX_PACKAGE_HISTORY = 500

# Viral video best-practice constants
_HOOK_DURATION_SECONDS = 5   # Opening hook must land in first 5 seconds
_CHAPTER_INTERVAL_SECONDS = 60  # Chapter marker every ~60 seconds
_IDEAL_DURATION_SECONDS = 480   # 8-minute sweet spot for retention
_FRAME_RATE = 30


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class VideoMode:
    """Output rendering mode identifiers for the video packager."""
    FFMPEG = "ffmpeg_render"
    PILLOW = "pillow_frame_stitch"
    STATIC = "static_package"


@dataclass
class VideoChapter:
    """A single chapter/timestamp marker for YouTube description."""
    timestamp_seconds: int
    title: str

    def format_timestamp(self) -> str:
        """Return MM:SS string."""
        minutes = self.timestamp_seconds // 60
        seconds = self.timestamp_seconds % 60
        return f"{minutes:02d}:{seconds:02d}"

    def to_description_line(self) -> str:
        return f"{self.format_timestamp()} {self.title}"


@dataclass
class VideoPackage:
    """Output of the video packager — all files needed for upload."""

    package_id: str
    run_id: str
    mode: str
    thumbnail_path: Optional[str]
    video_path: Optional[str]
    summary_path: Optional[str]
    chapters: List[VideoChapter]
    duration_seconds: float
    output_dir: str
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "package_id": self.package_id,
            "run_id": self.run_id,
            "mode": self.mode,
            "thumbnail_path": self.thumbnail_path,
            "video_path": self.video_path,
            "summary_path": self.summary_path,
            "chapters": [
                {"timestamp": c.timestamp_seconds, "title": c.title}
                for c in self.chapters
            ],
            "duration_seconds": self.duration_seconds,
            "output_dir": self.output_dir,
            "created_at": self.created_at,
            "metadata": dict(self.metadata),
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _pillow_available() -> bool:
    try:
        from PIL import Image, ImageDraw  # noqa: F401
        return True
    except ImportError:
        return False


def _ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def _detect_mode() -> str:
    if _ffmpeg_available() and _pillow_available():
        return VideoMode.FFMPEG
    if _pillow_available():
        return VideoMode.PILLOW
    return VideoMode.STATIC


def _confidence_bar(score: float, width: int = 30) -> str:
    """Return ASCII progress bar for confidence score."""
    filled = int(score * width)
    bar = "█" * filled + "░" * (width - filled)
    pct = int(score * 100)
    return f"[{bar}] {pct}%"


def _draw_confidence_chart(draw: Any, recording: Any, x: int, y: int, w: int, h: int) -> None:
    """Draw a simple bar chart of confidence progression using Pillow."""
    prog = recording.confidence_progression
    if not prog:
        return
    bar_w = max(1, w // (len(prog) or 1))
    for idx, point in enumerate(prog):
        conf = float(point.get("confidence", 0.0))
        bar_h = int(conf * h)
        bx = x + idx * bar_w
        by = y + h - bar_h
        color = _ACCENT_GREEN if conf >= 0.70 else _ACCENT_AMBER
        draw.rectangle([bx, by, bx + bar_w - 2, y + h], fill=color)


def _generate_thumbnail(recording: Any, output_path: str) -> bool:
    """Generate branded PNG thumbnail. Returns True on success."""
    if not _pillow_available():
        return False
    try:
        from PIL import Image, ImageDraw, ImageFont  # noqa: F401

        img = Image.new("RGB", (1280, 720), _BG_COLOR)
        draw = ImageDraw.Draw(img)

        # Gradient background
        for yy in range(720):
            ratio = yy / 720
            r = int(_BG_COLOR[0] + ratio * 12)
            g = int(_BG_COLOR[1] + ratio * 8)
            b = int(_BG_COLOR[2] + ratio * 20)
            draw.line([(0, yy), (1280, yy)], fill=(r, g, b))

        font = ImageFont.load_default()

        # Murphy skull / brand mark (text-based)
        draw.text((40, 30), "☠  MURPHY SYSTEM", fill=_ACCENT_CYAN, font=font)
        draw.text((40, 50), "─" * 60, fill=_ACCENT_CYAN, font=font)

        # Task name (large, truncated)
        task = recording.task_description[:55] + ("…" if len(recording.task_description) > 55 else "")
        draw.text((40, 120), task, fill=_TEXT_WHITE, font=font)

        # Task type badge
        badge_text = f"  {recording.task_type.upper()}  "
        draw.rectangle([40, 200, 40 + len(badge_text) * 7, 224], fill=_ACCENT_CYAN)
        draw.text((44, 203), badge_text, fill=_BG_COLOR, font=font)

        # Confidence badge
        pct = int(recording.confidence_score * 100)
        conf_color = _ACCENT_GREEN if pct >= 70 else (_ACCENT_AMBER if pct >= 50 else _RED)
        draw.text((40, 260), f"Confidence: {pct}%", fill=conf_color, font=font)
        bar_text = _confidence_bar(recording.confidence_score, width=40)
        draw.text((40, 278), bar_text, fill=conf_color, font=font)

        # Confidence chart
        _draw_confidence_chart(draw, recording, 40, 320, 500, 120)

        # SUCCESS banner
        draw.rectangle([900, 580, 1240, 650], fill=_ACCENT_GREEN)
        draw.text((920, 600), "✓  SUCCESS", fill=_BG_COLOR, font=font)

        # Duration badge
        mins = int(recording.duration_seconds // 60)
        secs = int(recording.duration_seconds % 60)
        draw.text((40, 480), f"Duration: {mins}m {secs}s", fill=_TEXT_DIM, font=font)

        # Step count
        draw.text((40, 498), f"Steps: {len(recording.steps)}", fill=_TEXT_DIM, font=font)

        # Inoni watermark
        draw.text((40, 690), "Inoni LLC — Alpha Software — No Warranty", fill=_TEXT_DIM, font=font)

        img.save(output_path, format="PNG")
        return True
    except Exception as exc:
        logger.warning("Thumbnail generation failed: %s", exc)
        return False


def _generate_frame(
    recording: Any,
    frame_idx: int,
    total_frames: int,
    output_path: str,
) -> bool:
    """Generate a single branded video frame. Returns True on success."""
    if not _pillow_available():
        return False
    try:
        from PIL import Image, ImageDraw, ImageFont  # noqa: F401

        img = Image.new("RGB", (1920, 1080), _BG_COLOR)
        draw = ImageDraw.Draw(img)

        font = ImageFont.load_default()
        progress = frame_idx / (total_frames or 1)

        # Header bar
        draw.rectangle([0, 0, 1920, 60], fill=(10, 10, 20))
        draw.text((20, 18), "☠  MURPHY SYSTEM  |  AGENT RUN REPLAY", fill=_ACCENT_CYAN, font=font)
        draw.text((1700, 18), f"{int(progress * 100)}%", fill=_TEXT_DIM, font=font)

        # Title area
        draw.text((60, 100), recording.task_description[:80], fill=_TEXT_WHITE, font=font)
        draw.text((60, 125), f"Type: {recording.task_type}  |  Status: {recording.status}", fill=_ACCENT_GREEN, font=font)

        # Progress bar (viral retention hook — shows how far into the run we are)
        bar_filled = int(1760 * progress)
        draw.rectangle([80, 170, 1840, 182], fill=(40, 40, 50))
        draw.rectangle([80, 170, 80 + bar_filled, 182], fill=_ACCENT_CYAN)

        # Steps completed so far
        steps_so_far = int(len(recording.steps) * progress)
        for idx in range(min(steps_so_far, 12)):
            step = recording.steps[idx]
            step_label = str(step.get("step_id", f"step_{idx}"))[:40]
            yy = 210 + idx * 22
            check = "✓" if step.get("success", True) else "✗"
            color = _ACCENT_GREEN if step.get("success", True) else _RED
            draw.text((80, yy), f"{check}  {step_label}", fill=color, font=font)

        # Confidence chart
        _draw_confidence_chart(draw, recording, 1100, 200, 700, 300)
        draw.text((1100, 195), "Confidence Progression", fill=_TEXT_DIM, font=font)

        # Confidence badge
        pct = int(recording.confidence_score * 100)
        conf_color = _ACCENT_GREEN if pct >= 70 else (_ACCENT_AMBER if pct >= 50 else _RED)
        draw.text((1100, 520), f"Final Confidence: {pct}%", fill=conf_color, font=font)

        # Footer
        draw.rectangle([0, 1040, 1920, 1080], fill=(10, 10, 20))
        draw.text((20, 1052), f"Murphy System {recording.system_version}  |  Alpha Software  |  Inoni LLC", fill=_TEXT_DIM, font=font)
        draw.text((1700, 1052), recording.run_id[:16], fill=_TEXT_DIM, font=font)

        img.save(output_path, format="PNG")
        return True
    except Exception as exc:
        logger.warning("Frame %d generation failed: %s", frame_idx, exc)
        return False


def _generate_chapters(recording: Any, duration_seconds: float) -> List[VideoChapter]:
    """Generate YouTube chapter markers for the recording."""
    chapters: List[VideoChapter] = []
    chapters.append(VideoChapter(0, "🎯 Hook — What Murphy Just Did"))
    chapters.append(VideoChapter(min(10, int(duration_seconds * 0.05)), f"📋 Task: {recording.task_description[:40]}"))

    step_count = len(recording.steps)
    if step_count > 0 and duration_seconds > 30:
        per_step = duration_seconds / (step_count or 1)
        for idx in range(0, step_count, max(1, step_count // 5)):
            ts = int(per_step * idx + 15)
            if ts < int(duration_seconds * 0.9):
                step = recording.steps[idx]
                label = str(step.get("step_id", f"Step {idx + 1}"))[:30]
                chapters.append(VideoChapter(ts, f"⚡ {label}"))

    result_ts = max(0, int(duration_seconds * 0.85))
    chapters.append(VideoChapter(result_ts, f"🏆 Result — {int(recording.confidence_score * 100)}% Confidence"))
    if duration_seconds > 60:
        chapters.append(VideoChapter(max(0, int(duration_seconds) - 15), "🔗 What's Next / Subscribe"))

    seen: set = set()
    deduped: List[VideoChapter] = []
    for ch in sorted(chapters, key=lambda c: c.timestamp_seconds):
        if ch.timestamp_seconds not in seen:
            seen.add(ch.timestamp_seconds)
            deduped.append(ch)
    return deduped


# ---------------------------------------------------------------------------
# Main packager
# ---------------------------------------------------------------------------

class VideoPackager:
    """
    Converts AgentRunRecording objects into publishable video packages.

    Auto-detects the best available mode:
      A (ffmpeg)  → real MP4 with audio overlay
      B (Pillow)  → animated GIF or PNG sequence
      C (static)  → thumbnail + JSON/markdown summary

    Usage::

        packager = VideoPackager(output_dir="/tmp/murphy_packages")
        package = packager.package(recording)
        logger.info("Package ready: %s (mode=%s)", package.output_dir, package.mode)
    """

    def __init__(self, output_dir: Optional[str] = None) -> None:
        self._lock = threading.Lock()
        self._output_dir = Path(output_dir or ".murphy_persistence/video_packages")
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._history: List[Dict[str, Any]] = []
        self._mode = _detect_mode()
        logger.info("VideoPackager initialised (mode=%s)", self._mode)

    def package(self, recording: Any, force_mode: Optional[str] = None) -> VideoPackage:
        """Package a recording. Gracefully degrades through A→B→C."""
        mode = force_mode or self._mode
        pkg_id = str(uuid.uuid4())
        pkg_dir = self._output_dir / pkg_id
        pkg_dir.mkdir(parents=True, exist_ok=True)

        duration = max(recording.duration_seconds, float(len(recording.steps) * 3))
        chapters = _generate_chapters(recording, duration)

        thumbnail_path = str(pkg_dir / "thumbnail.png")
        has_thumbnail = _generate_thumbnail(recording, thumbnail_path)
        if not has_thumbnail:
            thumbnail_path = None

        video_path: Optional[str] = None
        actual_mode = VideoMode.STATIC

        if mode == VideoMode.FFMPEG:
            result = self._package_ffmpeg(recording, pkg_dir, duration)
            if result:
                video_path = result
                actual_mode = VideoMode.FFMPEG
            else:
                logger.warning("ffmpeg packaging failed, falling back to Pillow mode")
                mode = VideoMode.PILLOW

        if mode == VideoMode.PILLOW and video_path is None:
            result = self._package_pillow(recording, pkg_dir, duration)
            if result:
                video_path = result
                actual_mode = VideoMode.PILLOW
            else:
                logger.warning("Pillow packaging failed, falling back to static mode")

        summary_path = self._write_summary(recording, pkg_dir, chapters)

        package = VideoPackage(
            package_id=pkg_id,
            run_id=recording.run_id,
            mode=actual_mode,
            thumbnail_path=thumbnail_path,
            video_path=video_path,
            summary_path=summary_path,
            chapters=chapters,
            duration_seconds=duration,
            output_dir=str(pkg_dir),
        )

        with self._lock:
            capped_append(self._history, package.to_dict(), max_size=_MAX_PACKAGE_HISTORY)

        logger.info(
            "Packaged run_id=%s pkg_id=%s mode=%s",
            recording.run_id,
            pkg_id,
            actual_mode,
        )
        return package

    def _package_ffmpeg(self, recording: Any, pkg_dir: Path, duration: float) -> Optional[str]:
        """Mode A: compose MP4 via ffmpeg from generated frames."""
        try:
            frames_dir = pkg_dir / "frames"
            frames_dir.mkdir(exist_ok=True)

            total_frames = max(1, int(duration * _FRAME_RATE))
            sample_frames = min(total_frames, 30)

            for idx in range(sample_frames):
                fpath = str(frames_dir / f"frame_{idx:06d}.png")
                _generate_frame(recording, idx, sample_frames, fpath)

            pattern = str(frames_dir / "frame_%06d.png")
            output_mp4 = str(pkg_dir / "agent_run.mp4")

            frame_count = len(list(frames_dir.glob("*.png")))
            if frame_count == 0:
                return None

            fps = max(1, frame_count // max(1, int(duration)))
            cmd = [
                "ffmpeg", "-y",
                "-framerate", str(fps),
                "-i", pattern,
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                output_mp4,
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode == 0 and os.path.exists(output_mp4):
                return output_mp4
            logger.warning("ffmpeg exited %d: %s", result.returncode, result.stderr[:200])
            return None
        except Exception as exc:
            logger.warning("ffmpeg packaging exception: %s", exc)
            return None

    def _package_pillow(self, recording: Any, pkg_dir: Path, duration: float) -> Optional[str]:
        """Mode B: animated GIF from generated frames."""
        if not _pillow_available():
            return None
        try:
            from PIL import Image  # noqa: F401

            total_frames = min(20, max(5, len(recording.steps)))
            frames = []
            tmp_paths = []

            for idx in range(total_frames):
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                    tmp_path = tmp.name
                tmp_paths.append(tmp_path)
                _generate_frame(recording, idx, total_frames, tmp_path)
                try:
                    frames.append(Image.open(tmp_path).copy())
                except Exception as exc:
                    logger.debug("Failed to open frame %d: %s", idx, exc)

            for tmp_path in tmp_paths:
                try:
                    os.unlink(tmp_path)
                except OSError as exc:
                    logger.debug("Could not delete temp file %s: %s", tmp_path, exc)

            if not frames:
                return None

            gif_path = str(pkg_dir / "agent_run.gif")
            frame_duration = max(100, int(duration * 1000 / (len(frames) or 1)))
            frames[0].save(
                gif_path,
                save_all=True,
                append_images=frames[1:],
                duration=frame_duration,
                loop=0,
            )
            return gif_path
        except Exception as exc:
            logger.warning("Pillow GIF packaging exception: %s", exc)
            return None

    def _write_summary(
        self, recording: Any, pkg_dir: Path, chapters: List[VideoChapter]
    ) -> str:
        """Always-available: write JSON + markdown summary."""
        summary_data = {
            "run_id": recording.run_id,
            "task_description": recording.task_description,
            "task_type": recording.task_type,
            "status": recording.status,
            "confidence_score": recording.confidence_score,
            "duration_seconds": recording.duration_seconds,
            "steps_count": len(recording.steps),
            "modules_used": list(recording.modules_used),
            "gates_passed": list(recording.gates_passed),
            "system_version": recording.system_version,
            "started_at": recording.started_at,
            "completed_at": recording.completed_at,
            "chapters": [{"timestamp": c.timestamp_seconds, "title": c.title} for c in chapters],
        }
        json_path = pkg_dir / "summary.json"
        with open(str(json_path), "w", encoding="utf-8") as fh:
            json.dump(summary_data, fh, indent=2)

        md_lines = [
            "# Murphy System Agent Run Summary",
            "",
            f"**Run ID:** `{recording.run_id}`",
            f"**Task:** {recording.task_description}",
            f"**Type:** {recording.task_type}",
            f"**Status:** {recording.status}",
            f"**Confidence:** {int(recording.confidence_score * 100)}%",
            f"**Duration:** {recording.duration_seconds:.1f}s",
            f"**System Version:** {recording.system_version}",
            "",
            "## Chapters",
            "",
        ]
        for ch in chapters:
            md_lines.append(f"- `{ch.format_timestamp()}` — {ch.title}")

        md_lines += [
            "",
            "## Modules Used",
            "",
        ]
        for mod in recording.modules_used:
            md_lines.append(f"- {mod}")

        md_lines += [
            "",
            "## Gates Passed",
            "",
        ]
        for gate in recording.gates_passed:
            md_lines.append(f"- {gate}")

        md_lines += [
            "",
            "---",
            "*Alpha Software — No Warranty. © Inoni LLC. License: BSL 1.1*",
        ]

        md_path = pkg_dir / "summary.md"
        with open(str(md_path), "w", encoding="utf-8") as fh:
            fh.write("\n".join(md_lines))

        return str(json_path)

    def get_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Return recent package history."""
        with self._lock:
            return list(self._history[-limit:])

    def get_mode(self) -> str:
        """Return the detected packaging mode."""
        return self._mode
