"""
YouTube Metadata Generator — Produces YouTube-ready metadata from agent run recordings.

Design Label: YT-003 — YouTube Metadata & Thumbnail Generator
Owner: Platform Engineering / Content Team
Dependencies:
  - agent_run_recorder (AgentRunRecording)
  - video_packager (VideoChapter list)

Generates:
  - Title (viral-optimised format with confidence score)
  - Description (system info, chapters, attribution, alpha disclaimer)
  - Tags (auto-generated from task type, modules, standard set)
  - Thumbnail (Pillow-branded PNG, 1280×720)
  - Category, privacy, playlist hints

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import os
import tempfile
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
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

# YouTube category IDs
CATEGORY_SCIENCE_TECH = "28"
CATEGORY_EDUCATION = "27"

# Privacy options
PRIVACY_UNLISTED = "unlisted"
PRIVACY_PUBLIC = "public"
PRIVACY_PRIVATE = "private"

_GITHUB_REPO = "https://github.com/IKNOWINOT/Murphy-System"
_MURPHY_VERSION_TAG = "Murphy System 1.0"
_ALPHA_DISCLAIMER = (
    "⚠️ ALPHA SOFTWARE — NO WARRANTY. This is pre-production software. "
    "Results may vary. Not for use in production environments without additional validation."
)
_INONI_ATTRIBUTION = "Built by Inoni LLC — https://github.com/IKNOWINOT/Murphy-System"

_STANDARD_TAGS = [
    "murphy system",
    "ai automation",
    "agent run",
    "HITL",
    "human in the loop",
    "agentic ai",
    "autonomous agent",
    "inoni",
    "open source ai",
]

_MAX_METADATA_HISTORY = 500

# Confidence buckets for tags
_CONF_BUCKET_HIGH = "high confidence"
_CONF_BUCKET_MED = "medium confidence"
_CONF_BUCKET_LOW = "low confidence"

# Max lengths per YouTube spec
_MAX_TITLE_LEN = 100
_MAX_DESCRIPTION_LEN = 5000
_MAX_TAGS_COUNT = 500


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class YouTubeMetadata:
    """All fields needed for a YouTube video upload."""

    metadata_id: str
    run_id: str
    title: str
    description: str
    tags: List[str]
    thumbnail_path: Optional[str]
    category_id: str
    privacy: str
    chapters_text: str
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metadata_id": self.metadata_id,
            "run_id": self.run_id,
            "title": self.title,
            "description": self.description,
            "tags": list(self.tags),
            "thumbnail_path": self.thumbnail_path,
            "category_id": self.category_id,
            "privacy": self.privacy,
            "chapters_text": self.chapters_text,
            "created_at": self.created_at,
            "extra": dict(self.extra),
        }


# ---------------------------------------------------------------------------
# Thumbnail helpers
# ---------------------------------------------------------------------------

_BG_COLOR = (18, 18, 24)
_ACCENT_CYAN = (0, 212, 212)
_ACCENT_GREEN = (0, 230, 118)
_ACCENT_AMBER = (255, 193, 7)
_TEXT_WHITE = (230, 230, 235)
_TEXT_DIM = (120, 120, 135)
_RED = (220, 50, 50)


def _pillow_available() -> bool:
    try:
        from PIL import Image, ImageDraw  # noqa: F401
        return True
    except ImportError:
        return False


def generate_thumbnail(
    recording: Any,
    output_path: str,
    chapters: Optional[List[Any]] = None,
) -> bool:
    """
    Generate a branded YouTube thumbnail (1280×720) using Pillow.
    Returns True on success, False on failure.
    """
    if not _pillow_available():
        return False
    try:
        from PIL import Image, ImageDraw, ImageFont  # noqa: F401

        img = Image.new("RGB", (1280, 720), _BG_COLOR)
        draw = ImageDraw.Draw(img)

        for yy in range(720):
            ratio = yy / 720
            r = int(_BG_COLOR[0] + ratio * 15)
            g = int(_BG_COLOR[1] + ratio * 10)
            b = int(_BG_COLOR[2] + ratio * 25)
            draw.line([(0, yy), (1280, yy)], fill=(r, g, b))

        font = ImageFont.load_default()

        # Left accent bar (viral design element)
        draw.rectangle([0, 0, 6, 720], fill=_ACCENT_CYAN)

        # Brand header
        draw.text((30, 28), "☠  MURPHY SYSTEM", fill=_ACCENT_CYAN, font=font)
        draw.text((30, 46), "Agent Run Complete", fill=_TEXT_DIM, font=font)

        # Task name — large, high contrast
        task = recording.task_description
        lines_out: List[str] = []
        words = task.split()
        current = ""
        for word in words:
            if len(current) + len(word) + 1 <= 40:
                current = (current + " " + word).strip()
            else:
                if current:
                    lines_out.append(current)
                current = word
        if current:
            lines_out.append(current)

        for ln_idx, ln in enumerate(lines_out[:3]):
            draw.text((30, 110 + ln_idx * 24), ln, fill=_TEXT_WHITE, font=font)

        # Confidence badge (right panel)
        pct = int(recording.confidence_score * 100)
        conf_color = _ACCENT_GREEN if pct >= 70 else (_ACCENT_AMBER if pct >= 50 else _RED)

        draw.rectangle([920, 100, 1240, 200], fill=(28, 28, 38))
        draw.rectangle([920, 100, 1240, 110], fill=conf_color)
        draw.text((930, 120), f"{pct}%", fill=conf_color, font=font)
        draw.text((930, 138), "CONFIDENCE", fill=_TEXT_DIM, font=font)

        # Confidence bar
        bar_w = int(300 * recording.confidence_score)
        draw.rectangle([920, 165, 1240, 180], fill=(40, 40, 55))
        draw.rectangle([920, 165, 920 + bar_w, 180], fill=conf_color)

        # SUCCESS banner
        draw.rectangle([30, 580, 360, 630], fill=_ACCENT_GREEN)
        draw.text((44, 596), "✓  SUCCESS_COMPLETED", fill=_BG_COLOR, font=font)

        # Stats row
        draw.text((30, 650), f"Steps: {len(recording.steps)}", fill=_TEXT_DIM, font=font)
        draw.text((180, 650), f"Modules: {len(recording.modules_used)}", fill=_TEXT_DIM, font=font)
        dur = recording.duration_seconds
        draw.text((360, 650), f"Duration: {int(dur // 60)}m {int(dur % 60)}s", fill=_TEXT_DIM, font=font)

        # Bottom bar
        draw.rectangle([0, 696, 1280, 720], fill=(10, 10, 16))
        draw.text((30, 703), "Alpha Software — No Warranty  |  Inoni LLC  |  BSL 1.1", fill=_TEXT_DIM, font=font)

        img.save(output_path, format="PNG")
        return True
    except Exception as exc:
        logger.warning("Thumbnail generation failed: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------

class YouTubeMetadataGenerator:
    """
    Generates YouTube-ready metadata from an AgentRunRecording.

    Usage::

        gen = YouTubeMetadataGenerator()
        meta = gen.generate(recording, chapters=package.chapters)
        logger.info("Title: %s", meta.title)
    """

    def __init__(
        self,
        default_privacy: str = PRIVACY_UNLISTED,
        thumbnail_dir: Optional[str] = None,
    ) -> None:
        self._lock = threading.Lock()
        self._default_privacy = default_privacy
        self._thumbnail_dir = thumbnail_dir or ".murphy_persistence/thumbnails"
        os.makedirs(self._thumbnail_dir, exist_ok=True)
        self._history: List[Dict[str, Any]] = []

    def generate(
        self,
        recording: Any,
        chapters: Optional[List[Any]] = None,
        privacy: Optional[str] = None,
    ) -> YouTubeMetadata:
        """Generate complete YouTube metadata for a recording."""
        title = self._build_title(recording)
        description = self._build_description(recording, chapters or [])
        tags = self._build_tags(recording)
        chapters_text = self._build_chapters_text(chapters or [])

        thumbnail_path = self._generate_thumbnail(recording, chapters)

        metadata = YouTubeMetadata(
            metadata_id=str(uuid.uuid4()),
            run_id=recording.run_id,
            title=title,
            description=description,
            tags=tags,
            thumbnail_path=thumbnail_path,
            category_id=CATEGORY_SCIENCE_TECH,
            privacy=privacy or self._default_privacy,
            chapters_text=chapters_text,
        )

        with self._lock:
            capped_append(self._history, metadata.to_dict(), max_size=_MAX_METADATA_HISTORY)

        logger.info("Generated metadata metadata_id=%s title='%s'", metadata.metadata_id, title)
        return metadata

    def _build_title(self, recording: Any) -> str:
        """Build viral-optimised YouTube title."""
        pct = int(recording.confidence_score * 100)
        date = datetime.now(timezone.utc).strftime("%b %d")
        task = recording.task_description[:40].strip()
        if len(recording.task_description) > 40:
            task += "…"

        title = f"[Murphy System] {recording.task_type}: {task} — {pct}% confidence ({date})"
        if len(title) > _MAX_TITLE_LEN:
            overflow = len(title) - _MAX_TITLE_LEN
            task = task[: max(5, len(task) - overflow)]
            title = f"[Murphy System] {recording.task_type}: {task} — {pct}% confidence ({date})"
        return title[:_MAX_TITLE_LEN]

    def _build_description(self, recording: Any, chapters: List[Any]) -> str:
        """Build full YouTube description with chapters, attribution, disclaimer."""
        pct = int(recording.confidence_score * 100)
        dur_m = int(recording.duration_seconds // 60)
        dur_s = int(recording.duration_seconds % 60)
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        modules_str = ", ".join(recording.modules_used[:10]) or "none"
        gates_str = ", ".join(recording.gates_passed[:10]) or "none"

        sections = [
            f"Murphy System autonomously completed a {recording.task_type} task "
            f"with {pct}% confidence — fully logged, gated, and reviewed.",
            "",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "📋 RUN DETAILS",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            f"Task: {recording.task_description}",
            f"Type: {recording.task_type}",
            f"Status: {recording.status}",
            f"Confidence: {pct}%",
            f"Duration: {dur_m}m {dur_s}s",
            f"Steps Executed: {len(recording.steps)}",
            f"HITL Decisions: {len(recording.hitl_decisions)}",
            f"System Version: {recording.system_version}",
            f"Run Date: {date}",
            "",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "⚙️ MODULES USED",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            modules_str,
            "",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "🔒 GATES PASSED",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            gates_str,
        ]

        if chapters:
            sections += [
                "",
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                "⏱ CHAPTERS",
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            ]
            for ch in chapters:
                if hasattr(ch, "to_description_line"):
                    sections.append(ch.to_description_line())
                else:
                    ts = ch.get("timestamp", 0) if isinstance(ch, dict) else 0
                    title_val = ch.get("title", "") if isinstance(ch, dict) else str(ch)
                    mins = ts // 60
                    secs = ts % 60
                    sections.append(f"{mins:02d}:{secs:02d} {title_val}")

        sections += [
            "",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "🔗 LINKS",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            f"GitHub: {_GITHUB_REPO}",
            "",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "🏢 ABOUT",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            _INONI_ATTRIBUTION,
            "",
            _ALPHA_DISCLAIMER,
        ]

        full = "\n".join(sections)
        return full[:_MAX_DESCRIPTION_LEN]

    def _build_tags(self, recording: Any) -> List[str]:
        """Build tag list from task context + standard set."""
        tags: List[str] = []
        tags.extend(_STANDARD_TAGS)

        task_type_clean = recording.task_type.lower().replace("_", " ")
        if task_type_clean not in tags:
            tags.append(task_type_clean)

        for mod in recording.modules_used[:8]:
            tag = mod.lower().replace("_", " ").replace(".", " ").strip()
            if tag and tag not in tags:
                tags.append(tag)

        pct = int(recording.confidence_score * 100)
        if pct >= 85:
            tags.append(_CONF_BUCKET_HIGH)
        elif pct >= 60:
            tags.append(_CONF_BUCKET_MED)
        else:
            tags.append(_CONF_BUCKET_LOW)

        task_words = recording.task_description.lower().split()
        for word in task_words[:6]:
            clean = word.strip(".,;:!?\"'()")
            if len(clean) > 3 and clean not in tags:
                tags.append(clean)

        seen: set = set()
        deduped: List[str] = []
        for tag in tags:
            if tag not in seen:
                seen.add(tag)
                deduped.append(tag)

        return deduped[:_MAX_TAGS_COUNT]

    def _build_chapters_text(self, chapters: List[Any]) -> str:
        """Build chapter timestamps block for copy-paste into description."""
        if not chapters:
            return ""
        lines = []
        for ch in chapters:
            if hasattr(ch, "to_description_line"):
                lines.append(ch.to_description_line())
            elif isinstance(ch, dict):
                ts = ch.get("timestamp", 0)
                title_val = ch.get("title", "")
                mins = ts // 60
                secs = ts % 60
                lines.append(f"{mins:02d}:{secs:02d} {title_val}")
        return "\n".join(lines)

    def _generate_thumbnail(self, recording: Any, chapters: Optional[List[Any]]) -> Optional[str]:
        """Generate and save thumbnail. Returns path or None."""
        thumb_name = f"thumb_{recording.run_id[:12]}_{uuid.uuid4().hex[:6]}.png"
        thumb_path = os.path.join(self._thumbnail_dir, thumb_name)
        success = generate_thumbnail(recording, thumb_path, chapters)
        if success:
            return thumb_path
        return None

    def get_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Return recent metadata generation history."""
        with self._lock:
            return list(self._history[-limit:])
