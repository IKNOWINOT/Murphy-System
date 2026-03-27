"""
Announcer Voice Engine — Open-source TTS narration with the MercyAnnouncer persona.

Design Label: YT-008 — Agent Run Announcer & Viral Audio Narrator
Owner: Platform Engineering / Content Team
Dependencies:
  - agent_run_recorder (AgentRunRecording)
  - thread_safe_operations (capped_append)
  - TTS backends (pyttsx3 → espeak → text fallback, all open-source)

Magnify×2 → Solidify:
  M1 — MercyAnnouncer: situation-aware, comedic-female-energy personality
       that reacts to actual run data. High confidence = triumphant screaming.
       Low confidence = suspicious side-eye. HITL decisions = dramatic pause.
  M2 — Dynamic script system with hook, tension, payoff structure.
       Viral best-practices baked in: 5-second hook, callbacks, catchphrases,
       audience engagement lines, cliffhanger at each chapter transition.
  Solidify — Single engine: script generator + TTS backends + audio packaging.

TTS backend priority (all open-source, no API keys):
  1. pyttsx3  — cross-platform, offline, zero cost
  2. espeak   — system TTS via subprocess
  3. text     — always available, writes script to file

Voice persona: MercyAnnouncer
  Energy: Melissa McCarthy-level unhinged enthusiasm. Sarcastic when things
  go sideways. Genuinely losing her mind when Murphy succeeds. Fourth-wall
  breaks. Self-aware. Loud. Warm. Never boring. Catchphrases that rotate.

Safety invariants:
  - Thread-safe: all shared state guarded by Lock
  - Bounded: max 500 audio packages in history
  - No external API calls for TTS
  - All generated scripts are PG-13 safe

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import os
import random
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

_MAX_AUDIO_HISTORY = 500


# ---------------------------------------------------------------------------
# TTS backend detection
# ---------------------------------------------------------------------------

class TTSBackend:
    """Available text-to-speech backend identifiers."""
    PYTTSX3 = "pyttsx3"
    ESPEAK = "espeak"
    TEXT = "text"


def _detect_tts_backend() -> str:
    try:
        import pyttsx3  # noqa: F401
        return TTSBackend.PYTTSX3
    except ImportError:
        pass
    if shutil.which("espeak") or shutil.which("espeak-ng"):
        return TTSBackend.ESPEAK
    return TTSBackend.TEXT


# ---------------------------------------------------------------------------
# MercyAnnouncer — Personality Engine
# ---------------------------------------------------------------------------

class MercyAnnouncer:
    """
    The voice of Murphy System agent runs.

    Mercy is a former competitive esports announcer who pivoted to AI coverage
    because, quote, "at least the robots have GOALS." She is enthusiastic to
    a medically concerning degree, brutally honest about failure, and somehow
    makes infrastructure automation sound like the Super Bowl.

    She has strong opinions. She will share them. You cannot stop her.
    At least the robots have goals, she says. Often."""

    _CATCHPHRASES = [
        "MURPHY IS COOKING AND THE KITCHEN IS ON FIRE — IN THE BEST WAY!",
        "Did the algorithm just— yes. Yes it did. BEAUTIFUL.",
        "I've seen a lot of agent runs in my career and THIS one is a whole MOOD.",
        "Oh my goodness gracious, Murphy just casually fixed that like it was NOTHING.",
        "I'm not crying, you're crying. Actually I'm definitely crying.",
        "THAT'S WHAT I'M TALKING ABOUT! Well, technically I'm talking about everything, always.",
        "Smooth. Surgical. Slightly terrifying. Ten out of ten.",
        "Murphy went full send and it absolutely WORKED and I'm not okay.",
        "That confidence score just went UP and so did my blood pressure — for GOOD reasons!",
        "Somebody call a doctor because this run just gave me PALPITATIONS.",
    ]

    _HOOK_OPENERS = [
        "OH. OH WE ARE STARTING. Welcome, welcome, WELCOME to what is about to be an absolute JOURNEY.",
        "STOP whatever you are doing. I need five minutes of your life and I promise you will not regret it.",
        "Hello and GOOD DAY. Mercy here. Murphy System just did something and you need to witness it.",
        "Buckle UP, buttercup. Agent run incoming. Confidence scores loading. DRAMA IS IMMINENT.",
        "You clicked the right video. I'm not saying that to be nice. I'm saying it because what you're about to see is REAL.",
        "Right. Okay. Here we go. I have been WAITING for this run to finish so I could tell you about it.",
    ]

    _LOW_CONFIDENCE_LINES = [
        "Okay so... confidence is at {pct}%. Which is... fine. Totally fine. I'm fine. WE'RE FINE.",
        "I'm not panicking but I'm making the face I make when I'm panicking. {pct}% confidence. Deep breaths.",
        "{pct}% confidence right now. Murphy is giving it a shot and I respect the hustle even if my hands are shaking.",
        "Look. {pct}% is a number. Numbers go up. Let's all believe in that right now. Together.",
    ]

    _MED_CONFIDENCE_LINES = [
        "We're sitting at {pct}% confidence and Murphy is handling it with the calm of someone who has seen things.",
        "{pct}% confidence. Not sweating yet. Lightly perspiring. There's a difference.",
        "Solid {pct}%. Murphy is methodical. Murphy is focused. Murphy is not taking questions at this time.",
        "At {pct}% we're in control. Cool. Collected. Absolutely not going to suddenly explode. Probably.",
    ]

    _HIGH_CONFIDENCE_LINES = [
        "NINETY. THREE. PERCENT. Do you understand what that MEANS?! I'M GOING TO NEED A MOMENT.",
        "{pct}%! THAT IS {pct} PERCENT! I need everyone to understand how hard that is to do!",
        "Okay {pct}% confidence and I have OFFICIALLY lost my composure. I had composure. It's gone now. No regrets.",
        "At {pct}% Murphy is not just running — Murphy is PERFORMING ART right now.",
    ]

    _HITL_LINES = [
        "And HERE is where Murphy stops and says — hey, human? Little help? I love a good check-in moment.",
        "HITL decision incoming! This is the handshake between human wisdom and machine power and I get GOOSEBUMPS every time.",
        "Murphy just rang the human bell. Ding ding ding! Decision required. This is the feature. This IS the system working.",
        "Human in the loop! Because Murphy is smart enough to know when to ask. That's not a weakness. That is EXCELLENCE.",
    ]

    _STEP_TRANSITION_LINES = [
        "Moving to the next step and I can feel the MOMENTUM.",
        "NEXT STEP. Clean. Crisp. Murphy is not playing games. Well, metaphorically.",
        "Onward! The run continues! The energy is immaculate!",
        "Step transition. Smooth. Like butter. Like extremely competent butter.",
    ]

    _MODULE_HYPE_LINES = [
        "And look at the MODULE LIST on this run! {count} modules! That's a TEAM effort right there!",
        "{count} modules fired up and none of them quit! Reliability! Teamwork! I'm emotional!",
        "We've got {count} modules in play and they are all pulling their weight like CHAMPIONS.",
    ]

    _SUCCESS_CLOSERS = [
        "AND THAT IS A WRAP! STATUS: SUCCESS COMPLETED! CONFIDENCE: {pct}%! DURATION: {dur}! Murphy did THAT!",
        "COMPLETE! We are DONE! In {dur} Murphy solved it, {pct}% confidence, and I need to go lie down!",
        "SUCCESS COMPLETED. {pct}% confidence. {steps} steps executed. {dur} total. Murphy. Is. A. MACHINE. An excellent machine!",
        "AND WE ARE DONE HERE! {pct}%! {steps} steps! {dur}! I have witnessed GREATNESS and I want everyone to know!",
    ]

    _FAILURE_OPENERS = [
        "Okay. So. We're going to talk about what happened. And we're going to do it with GRACE.",
        "Look. Not every run completes. That's real. That's life. Murphy is going to try again and I believe in that.",
        "Status: not a success. But status: LEARNED SOMETHING. And that's what Murphy does.",
    ]

    _SUBSCRIBE_CTA = [
        "If you want to watch Murphy do this AGAIN — which, why wouldn't you — subscribe. Do it. I'll wait.",
        "Subscribe to the channel. Murphy's not done. I'm not done. NONE OF US ARE DONE.",
        "Hit subscribe. Seriously. You're going to want to see what comes next. I've seen the roadmap. IT'S A LOT.",
    ]

    def _pick(self, pool: List[str], seed: int = 0) -> str:
        rng = random.Random(seed)
        return rng.choice(pool)

    def build_hook(self, recording: Any, seed: int = 0) -> str:
        """Generate the opening hook (first 5 seconds of video)."""
        opener = self._pick(self._HOOK_OPENERS, seed)
        task = recording.task_description[:50]
        pct = int(recording.confidence_score * 100)
        return (
            f"{opener} "
            f"Murphy System just tackled {task!r}. "
            f"End result? {pct}% confidence. "
            f"We're going to walk through every single step. "
            f"Together. Right now. Let's GO."
        )

    def build_confidence_line(self, recording: Any, seed: int = 0) -> str:
        """Generate a confidence-level-specific commentary line."""
        pct = int(recording.confidence_score * 100)
        if pct >= 80:
            pool = self._HIGH_CONFIDENCE_LINES
        elif pct >= 55:
            pool = self._MED_CONFIDENCE_LINES
        else:
            pool = self._LOW_CONFIDENCE_LINES
        template = self._pick(pool, seed)
        return template.format(pct=pct)

    def build_hitl_commentary(self, decision_count: int, seed: int = 0) -> str:
        """Commentary on HITL decisions."""
        if decision_count == 0:
            return "Zero HITL decisions on this one. Murphy handled it autonomously. Gutsy. Correct. Impressive."
        base = self._pick(self._HITL_LINES, seed)
        return f"{base} {decision_count} decision{'s' if decision_count != 1 else ''} made by a human in this run."

    def build_module_hype(self, module_count: int, seed: int = 0) -> str:
        """Hype about the number of modules used."""
        template = self._pick(self._MODULE_HYPE_LINES, seed)
        return template.format(count=module_count)

    def build_step_transition(self, step_idx: int, total: int, seed: int = 0) -> str:
        """Short transition line between steps."""
        base = self._pick(self._STEP_TRANSITION_LINES, seed + step_idx)
        return f"{base} Step {step_idx + 1} of {total}."

    def build_success_close(self, recording: Any, seed: int = 0) -> str:
        """Triumphant closing line for successful runs."""
        pct = int(recording.confidence_score * 100)
        dur_s = int(recording.duration_seconds)
        dur_str = f"{dur_s // 60}m {dur_s % 60}s"
        template = self._pick(self._SUCCESS_CLOSERS, seed)
        return template.format(
            pct=pct,
            steps=len(recording.steps),
            dur=dur_str,
        )

    def build_failure_open(self, recording: Any, seed: int = 0) -> str:
        """Compassionate but honest opener for failed runs."""
        opener = self._pick(self._FAILURE_OPENERS, seed)
        return f"{opener} Task was: {recording.task_description[:60]}."

    def build_subscribe_cta(self, seed: int = 0) -> str:
        """End-of-video call-to-action."""
        return self._pick(self._SUBSCRIBE_CTA, seed)

    def build_catchphrase(self, seed: int = 0) -> str:
        """Return a random Mercy catchphrase."""
        return self._pick(self._CATCHPHRASES, seed)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class AnnouncerScript:
    """Full narration script for a video package."""

    script_id: str
    run_id: str
    hook: str
    confidence_line: str
    hitl_commentary: str
    module_hype: str
    step_narrations: List[str]
    success_or_failure_close: str
    subscribe_cta: str
    catchphrase: str
    full_script: str
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "script_id": self.script_id,
            "run_id": self.run_id,
            "hook": self.hook,
            "confidence_line": self.confidence_line,
            "hitl_commentary": self.hitl_commentary,
            "module_hype": self.module_hype,
            "step_narrations": list(self.step_narrations),
            "success_or_failure_close": self.success_or_failure_close,
            "subscribe_cta": self.subscribe_cta,
            "catchphrase": self.catchphrase,
            "full_script": self.full_script,
            "created_at": self.created_at,
        }


@dataclass
class AudioPackage:
    """Output of the voice engine — script + optional audio files."""

    audio_id: str
    run_id: str
    script: AnnouncerScript
    audio_path: Optional[str]
    tts_backend: str
    output_dir: str
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "audio_id": self.audio_id,
            "run_id": self.run_id,
            "script": self.script.to_dict(),
            "audio_path": self.audio_path,
            "tts_backend": self.tts_backend,
            "output_dir": self.output_dir,
            "created_at": self.created_at,
        }


# ---------------------------------------------------------------------------
# TTS Synthesis helpers
# ---------------------------------------------------------------------------

def _synthesize_pyttsx3(text: str, output_path: str) -> bool:
    """Synthesize speech with pyttsx3. Returns True on success."""
    try:
        import pyttsx3  # noqa: F401

        engine = pyttsx3.init()
        voices = engine.getProperty("voices")
        if voices:
            female_voice = next(
                (v for v in voices if "female" in v.name.lower() or "zira" in v.name.lower() or "samantha" in v.name.lower()),
                None,
            )
            if female_voice:
                engine.setProperty("voice", female_voice.id)
        engine.setProperty("rate", 165)
        engine.setProperty("volume", 0.95)
        engine.save_to_file(text, output_path)
        engine.runAndWait()
        engine.stop()
        return os.path.exists(output_path)
    except Exception as exc:
        logger.warning("pyttsx3 synthesis failed: %s", exc)
        return False


def _synthesize_espeak(text: str, output_path: str) -> bool:
    """Synthesize speech with espeak/espeak-ng. Returns True on success."""
    binary = shutil.which("espeak-ng") or shutil.which("espeak")
    if not binary:
        return False
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tmp:
            tmp.write(text)
            tmp_path = tmp.name

        cmd = [
            binary,
            "-v", "en+f3",
            "-s", "155",
            "-a", "200",
            "-f", tmp_path,
            "-w", output_path,
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )
        try:
            os.unlink(tmp_path)
        except OSError as exc:
            logger.debug("Could not delete temp script file: %s", exc)

        if result.returncode == 0 and os.path.exists(output_path):
            return True
        logger.warning("espeak exited %d: %s", result.returncode, result.stderr[:100])
        return False
    except Exception as exc:
        logger.warning("espeak synthesis failed: %s", exc)
        return False


def _write_text_script(text: str, output_path: str) -> bool:
    """Fallback: write plain-text script to file. Always succeeds."""
    try:
        with open(output_path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return True
    except Exception as exc:
        logger.warning("Text script write failed: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Main engine
# ---------------------------------------------------------------------------

class AnnouncerVoiceEngine:
    """
    Generates entertaining, Mercy-voiced narration for Murphy System agent runs.

    Automatically selects the best available open-source TTS backend:
      1. pyttsx3  (cross-platform, offline)
      2. espeak   (system TTS)
      3. text     (always available — writes script to .txt)

    Usage::

        engine = AnnouncerVoiceEngine()
        pkg = engine.narrate(recording)
        logger.info("Audio ready: %s (backend=%s)", pkg.audio_path, pkg.tts_backend)
        logger.info("Script hook: %s", pkg.script.hook)
    """

    def __init__(self, output_dir: Optional[str] = None) -> None:
        self._lock = threading.Lock()
        self._output_dir = Path(output_dir or ".murphy_persistence/announcer_audio")
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._persona = MercyAnnouncer()
        self._tts_backend = _detect_tts_backend()
        self._history: List[Dict[str, Any]] = []
        logger.info(
            "AnnouncerVoiceEngine initialised (persona=MercyAnnouncer, tts_backend=%s)",
            self._tts_backend,
        )

    def narrate(self, recording: Any) -> AudioPackage:
        """
        Generate a complete narration package for an agent run recording.

        Builds the MercyAnnouncer script from actual run data, then
        synthesizes audio with the best available TTS backend.
        """
        seed = hash(recording.run_id) % (2 ** 31)
        script = self._build_script(recording, seed)

        audio_id = str(uuid.uuid4())
        pkg_dir = self._output_dir / audio_id
        pkg_dir.mkdir(parents=True, exist_ok=True)

        audio_path = self._synthesize(script.full_script, pkg_dir, audio_id)

        pkg = AudioPackage(
            audio_id=audio_id,
            run_id=recording.run_id,
            script=script,
            audio_path=audio_path,
            tts_backend=self._tts_backend,
            output_dir=str(pkg_dir),
        )

        with self._lock:
            capped_append(self._history, pkg.to_dict(), max_size=_MAX_AUDIO_HISTORY)

        logger.info(
            "Narration generated audio_id=%s run_id=%s backend=%s",
            audio_id,
            recording.run_id,
            self._tts_backend,
        )
        return pkg

    def generate_script_only(self, recording: Any) -> AnnouncerScript:
        """Generate the narration script without synthesizing audio."""
        seed = hash(recording.run_id) % (2 ** 31)
        return self._build_script(recording, seed)

    def _build_script(self, recording: Any, seed: int) -> AnnouncerScript:
        """Assemble the full MercyAnnouncer script from recording data."""
        persona = self._persona

        hook = persona.build_hook(recording, seed)
        confidence_line = persona.build_confidence_line(recording, seed + 1)

        hitl_count = len(getattr(recording, "hitl_decisions", []))
        hitl_commentary = persona.build_hitl_commentary(hitl_count, seed + 2)

        module_count = len(getattr(recording, "modules_used", []))
        module_hype = persona.build_module_hype(module_count, seed + 3)

        steps = getattr(recording, "steps", [])
        step_narrations: List[str] = []
        sample_steps = steps[::max(1, len(steps) // 5)] if len(steps) > 5 else steps
        for idx, step in enumerate(sample_steps):
            step_label = str(step.get("step_id", f"step {idx + 1}"))[:40] if isinstance(step, dict) else f"step {idx + 1}"
            transition = persona.build_step_transition(idx, len(sample_steps), seed + 10 + idx)
            narration = f"{transition} {step_label}."
            step_narrations.append(narration)

        is_success = getattr(recording, "status", "") == "SUCCESS_COMPLETED"
        if is_success:
            close = persona.build_success_close(recording, seed + 20)
        else:
            close = persona.build_failure_open(recording, seed + 20)

        subscribe_cta = persona.build_subscribe_cta(seed + 30)
        catchphrase = persona.build_catchphrase(seed + 40)

        sections = [
            "=== HOOK ===",
            hook,
            "",
            "=== TASK OVERVIEW ===",
            f"Today's task: {recording.task_description}. "
            f"Task type: {recording.task_type}. "
            f"Running on Murphy System version {recording.system_version}.",
            "",
            "=== CONFIDENCE UPDATE ===",
            confidence_line,
            "",
            "=== MODULE LINEUP ===",
            module_hype,
            "",
            "=== EXECUTION STEPS ===",
        ]
        sections.extend(step_narrations)
        sections += [
            "",
            "=== HUMAN IN THE LOOP ===",
            hitl_commentary,
            "",
            "=== RESULT ===",
            close,
            "",
            "=== MERCY'S TAKE ===",
            catchphrase,
            "",
            "=== CALL TO ACTION ===",
            subscribe_cta,
        ]

        full_script = "\n".join(sections)

        return AnnouncerScript(
            script_id=str(uuid.uuid4()),
            run_id=recording.run_id,
            hook=hook,
            confidence_line=confidence_line,
            hitl_commentary=hitl_commentary,
            module_hype=module_hype,
            step_narrations=step_narrations,
            success_or_failure_close=close,
            subscribe_cta=subscribe_cta,
            catchphrase=catchphrase,
            full_script=full_script,
        )

    def _synthesize(self, text: str, pkg_dir: Path, audio_id: str) -> Optional[str]:
        """Synthesize text to audio using the best available backend."""
        if self._tts_backend == TTSBackend.PYTTSX3:
            wav_path = str(pkg_dir / f"{audio_id}.wav")
            if _synthesize_pyttsx3(text, wav_path):
                return wav_path
            logger.warning("pyttsx3 failed, falling back to espeak")

        if self._tts_backend in (TTSBackend.PYTTSX3, TTSBackend.ESPEAK):
            wav_path = str(pkg_dir / f"{audio_id}.wav")
            if _synthesize_espeak(text, wav_path):
                return wav_path
            logger.warning("espeak failed, falling back to text")

        txt_path = str(pkg_dir / f"{audio_id}_script.txt")
        _write_text_script(text, txt_path)
        return txt_path

    def get_tts_backend(self) -> str:
        """Return the currently active TTS backend name."""
        return self._tts_backend

    def get_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Return recent narration history."""
        with self._lock:
            return list(self._history[-limit:])

    def get_stats(self) -> Dict[str, Any]:
        """Return engine statistics."""
        with self._lock:
            total = len(self._history)
        return {
            "total_narrations": total,
            "tts_backend": self._tts_backend,
            "persona": "MercyAnnouncer",
            "output_dir": str(self._output_dir),
        }
