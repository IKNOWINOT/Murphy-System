# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Voice Command Interface — VCI-001

Owner: Platform Engineering · Dep: thread_safe_operations (capped_append)

Speech-to-text adapter and command parser for the Murphy terminal.  Accepts
audio input (raw PCM / WAV / base64), runs it through a pluggable STT
provider (local or cloud), parses recognised text into structured Murphy
commands, and returns execution-ready command payloads.

Classes: AudioFormat/CommandCategory/ParseStatus/STTProviderKind (enums),
AudioChunk/STTResult/ParsedCommand/CommandMatch/VoiceSession/VoiceStats
(dataclasses), VoiceCommandInterface (thread-safe engine).
``create_vci_api(engine)`` returns a Flask Blueprint (JSON error envelope).

Safety: all mutable state under threading.Lock; bounded lists via
capped_append; no external dependencies beyond stdlib + Flask.  Actual STT
providers are optional — the engine ships with a built-in keyword recogniser
so that all logic is testable without network access.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

try:
    from flask import Blueprint, jsonify, request

    _HAS_FLASK = True
except ImportError:
    _HAS_FLASK = False
    Blueprint = type("Blueprint", (), {"route": lambda *a, **k: lambda f: f})  # type: ignore[assignment,misc]

    def jsonify(*_a: Any, **_k: Any) -> dict:  # type: ignore[misc]
        return {}

    class _FakeReq:  # type: ignore[no-redef]
        args: dict = {}

        @staticmethod
        def get_json(silent: bool = True) -> dict:
            return {}

    request = _FakeReq()  # type: ignore[assignment]

try:
    from .blueprint_auth import require_blueprint_auth
except ImportError:
    from blueprint_auth import require_blueprint_auth
try:
    from thread_safe_operations import capped_append
except ImportError:

    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max(1, max_size // 10)]
        target_list.append(item)

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _enum_val(v: Any) -> str:
    """Return the string value whether *v* is an Enum or already a str."""
    return v.value if hasattr(v, "value") else str(v)


# -- Enums ------------------------------------------------------------------

class AudioFormat(str, Enum):
    """Supported audio input formats."""
    pcm_16k = "pcm_16k"
    wav = "wav"
    base64_wav = "base64_wav"
    raw_bytes = "raw_bytes"


class CommandCategory(str, Enum):
    """Murphy terminal command categories."""
    system = "system"
    query = "query"
    config = "config"
    deploy = "deploy"
    monitor = "monitor"
    security = "security"
    help = "help"
    unknown = "unknown"


class ParseStatus(str, Enum):
    """Result status of command parsing."""
    matched = "matched"
    ambiguous = "ambiguous"
    unrecognised = "unrecognised"
    empty = "empty"


class STTProviderKind(str, Enum):
    """Kind of speech-to-text provider."""
    builtin_keyword = "builtin_keyword"
    local_model = "local_model"
    cloud_api = "cloud_api"


# -- Dataclasses ------------------------------------------------------------

@dataclass
class AudioChunk:
    """A chunk of audio data submitted for recognition."""
    chunk_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    audio_format: str = AudioFormat.pcm_16k.value
    sample_rate: int = 16000
    channels: int = 1
    duration_ms: int = 0
    byte_length: int = 0
    checksum: str = ""
    timestamp: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to plain dict."""
        return asdict(self)


@dataclass
class STTResult:
    """Result from the speech-to-text engine."""
    result_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    transcript: str = ""
    confidence: float = 0.0
    provider: str = STTProviderKind.builtin_keyword.value
    language: str = "en"
    duration_ms: int = 0
    alternatives: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to plain dict."""
        d = asdict(self)
        return d


@dataclass
class ParsedCommand:
    """A Murphy terminal command extracted from voice input."""
    command_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    raw_text: str = ""
    normalised_text: str = ""
    command: str = ""
    args: List[str] = field(default_factory=list)
    category: str = CommandCategory.unknown.value
    confidence: float = 0.0
    status: str = ParseStatus.unrecognised.value
    timestamp: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to plain dict."""
        return asdict(self)


@dataclass
class CommandMatch:
    """A registered command pattern for voice matching."""
    pattern: str = ""
    command: str = ""
    category: str = CommandCategory.system.value
    description: str = ""
    aliases: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to plain dict."""
        return asdict(self)


@dataclass
class VoiceSession:
    """An active voice input session."""
    session_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    started_at: str = field(default_factory=_now)
    chunks_received: int = 0
    commands_parsed: int = 0
    last_transcript: str = ""
    active: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to plain dict."""
        return asdict(self)


@dataclass
class VoiceStats:
    """Aggregate statistics for the voice command engine."""
    total_sessions: int = 0
    active_sessions: int = 0
    total_chunks: int = 0
    total_commands: int = 0
    recognised_commands: int = 0
    unrecognised_commands: int = 0
    avg_confidence: float = 0.0
    registered_patterns: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to plain dict."""
        return asdict(self)


# -- Built-in keyword recogniser --------------------------------------------

_DEFAULT_PATTERNS: List[Dict[str, Any]] = [
    {"pattern": r"\b(?:status|show\s+status)\b", "command": "status",
     "category": "system", "description": "Show system status",
     "aliases": ["system status", "current status"]},
    {"pattern": r"\b(?:health|health\s+check)\b", "command": "health",
     "category": "monitor", "description": "Run health check",
     "aliases": ["check health"]},
    {"pattern": r"\b(?:deploy)\b", "command": "deploy",
     "category": "deploy", "description": "Trigger deployment",
     "aliases": ["start deploy", "run deploy"]},
    {"pattern": r"\b(?:help|what\s+can\s+you\s+do)\b", "command": "help",
     "category": "help", "description": "Show help information",
     "aliases": ["commands", "available commands"]},
    {"pattern": r"\b(?:stop|halt|shutdown)\b", "command": "stop",
     "category": "system", "description": "Stop the system",
     "aliases": ["shut down", "power off"]},
    {"pattern": r"\b(?:restart|reboot)\b", "command": "restart",
     "category": "system", "description": "Restart the system",
     "aliases": ["reboot system"]},
    {"pattern": r"\b(?:configure|config|set)\b", "command": "configure",
     "category": "config", "description": "Open configuration",
     "aliases": ["settings", "preferences"]},
    {"pattern": r"\b(?:query|search|find|look\s+up)\b", "command": "query",
     "category": "query", "description": "Run a query",
     "aliases": ["search for", "look up"]},
    {"pattern": r"\b(?:logs?|show\s+logs?)\b", "command": "logs",
     "category": "monitor", "description": "Show system logs",
     "aliases": ["display logs", "view logs"]},
    {"pattern": r"\b(?:security\s+scan|audit)\b", "command": "security_scan",
     "category": "security", "description": "Run security scan",
     "aliases": ["run audit", "check security"]},
    {"pattern": r"\b(?:list\s+modules?|modules?)\b", "command": "list_modules",
     "category": "query", "description": "List loaded modules",
     "aliases": ["show modules"]},
    {"pattern": r"\b(?:version)\b", "command": "version",
     "category": "system", "description": "Show system version",
     "aliases": ["what version"]},
]


def _builtin_stt(text_input: str) -> STTResult:
    """Built-in keyword recogniser — deterministic, no network needed."""
    transcript = text_input.strip().lower()
    confidence = 1.0 if transcript else 0.0
    return STTResult(
        transcript=transcript,
        confidence=confidence,
        provider=STTProviderKind.builtin_keyword.value,
        language="en",
        duration_ms=0,
    )


# -- Engine -----------------------------------------------------------------

class VoiceCommandInterface:
    """Thread-safe voice command interface engine.

    Provides speech-to-text processing, command pattern registration,
    voice-to-command parsing, session management, and aggregate statistics.
    """

    def __init__(
        self,
        *,
        stt_fn: Optional[Callable[[str], STTResult]] = None,
        max_history: int = 10_000,
    ) -> None:
        self._lock = threading.Lock()
        self._stt_fn: Callable[[str], STTResult] = stt_fn or _builtin_stt
        self._max_history = max_history
        self._patterns: List[CommandMatch] = []
        self._sessions: Dict[str, VoiceSession] = {}
        self._history: List[ParsedCommand] = []
        self._total_chunks = 0
        self._total_commands = 0
        self._recognised = 0
        self._unrecognised = 0
        self._confidence_sum = 0.0
        self._register_defaults()

    # -- Pattern registration -----------------------------------------------

    def _register_defaults(self) -> None:
        """Load built-in command patterns."""
        for p in _DEFAULT_PATTERNS:
            self._patterns.append(CommandMatch(
                pattern=p["pattern"],
                command=p["command"],
                category=p["category"],
                description=p.get("description", ""),
                aliases=p.get("aliases", []),
            ))

    def register_pattern(
        self,
        pattern: str,
        command: str,
        category: Union[str, CommandCategory] = CommandCategory.unknown,
        description: str = "",
        aliases: Optional[List[str]] = None,
    ) -> CommandMatch:
        """Register a new voice command pattern.

        Args:
            pattern: Regex pattern to match against transcripts.
            command: Murphy terminal command to emit.
            category: Command category enum or string.
            description: Human-readable description.
            aliases: Alternative trigger phrases.

        Returns:
            The registered CommandMatch.
        """
        m = CommandMatch(
            pattern=pattern,
            command=command,
            category=_enum_val(category),
            description=description,
            aliases=aliases or [],
        )
        with self._lock:
            capped_append(self._patterns, m, max_size=1000)
        return m

    def list_patterns(self) -> List[Dict[str, Any]]:
        """Return all registered command patterns."""
        with self._lock:
            return [p.to_dict() for p in self._patterns]

    def remove_pattern(self, command: str) -> bool:
        """Remove all patterns matching *command*. Returns True if any removed."""
        with self._lock:
            before = len(self._patterns)
            self._patterns = [p for p in self._patterns if p.command != command]
            return len(self._patterns) < before

    # -- Session management -------------------------------------------------

    def start_session(self) -> VoiceSession:
        """Start a new voice input session."""
        s = VoiceSession()
        with self._lock:
            self._sessions[s.session_id] = s
        return s

    def end_session(self, session_id: str) -> Optional[VoiceSession]:
        """End a session. Returns the session or None if not found."""
        with self._lock:
            s = self._sessions.get(session_id)
            if s:
                s.active = False
            return s

    def get_session(self, session_id: str) -> Optional[VoiceSession]:
        """Retrieve a session by id."""
        with self._lock:
            return self._sessions.get(session_id)

    def list_sessions(self, active_only: bool = False) -> List[Dict[str, Any]]:
        """List sessions, optionally filtering to active only."""
        with self._lock:
            sessions = list(self._sessions.values())
        if active_only:
            sessions = [s for s in sessions if s.active]
        return [s.to_dict() for s in sessions]

    # -- Core recognition + parsing -----------------------------------------

    def recognise(self, text_input: str) -> STTResult:
        """Run speech-to-text on the given input.

        For the built-in provider *text_input* is the raw text to parse.
        A real STT provider would accept audio bytes instead.
        """
        with self._lock:
            self._total_chunks += 1
        result = self._stt_fn(text_input)
        return result

    def parse_command(self, transcript: str) -> ParsedCommand:
        """Parse a transcript string into a structured Murphy command.

        Matches against all registered patterns, picks the best match
        (highest confidence / first match), and returns a ParsedCommand.
        """
        normalised = transcript.strip().lower()
        if not normalised:
            cmd = ParsedCommand(
                raw_text=transcript,
                normalised_text=normalised,
                status=ParseStatus.empty.value,
            )
            self._record_command(cmd)
            return cmd

        matches = self._find_matches(normalised)
        if not matches:
            cmd = ParsedCommand(
                raw_text=transcript,
                normalised_text=normalised,
                status=ParseStatus.unrecognised.value,
            )
            self._record_command(cmd)
            return cmd

        if len(matches) == 1:
            best = matches[0]
            cmd = ParsedCommand(
                raw_text=transcript,
                normalised_text=normalised,
                command=best.command,
                category=best.category,
                confidence=1.0,
                status=ParseStatus.matched.value,
                args=self._extract_args(normalised, best),
            )
        else:
            best = matches[0]
            cmd = ParsedCommand(
                raw_text=transcript,
                normalised_text=normalised,
                command=best.command,
                category=best.category,
                confidence=0.7,
                status=ParseStatus.ambiguous.value,
                args=self._extract_args(normalised, best),
            )
        self._record_command(cmd)
        return cmd

    def process_voice(
        self,
        text_input: str,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """End-to-end pipeline: recognise → parse → return result dict.

        Args:
            text_input: Raw text (or audio placeholder for real STT).
            session_id: Optional session to associate with this input.

        Returns:
            Dict with ``stt``, ``command``, and ``session_id`` keys.
        """
        stt = self.recognise(text_input)
        cmd = self.parse_command(stt.transcript)

        if session_id:
            with self._lock:
                s = self._sessions.get(session_id)
                if s and s.active:
                    s.chunks_received += 1
                    s.commands_parsed += 1
                    s.last_transcript = stt.transcript

        return {
            "stt": stt.to_dict(),
            "command": cmd.to_dict(),
            "session_id": session_id or "",
        }

    # -- History & stats ----------------------------------------------------

    def get_history(
        self,
        limit: int = 50,
        category: Optional[Union[str, CommandCategory]] = None,
    ) -> List[Dict[str, Any]]:
        """Return recent parsed commands, optionally filtered by category."""
        with self._lock:
            cmds = list(self._history)
        if category:
            cat_val = _enum_val(category)
            cmds = [c for c in cmds if c.category == cat_val]
        return [c.to_dict() for c in cmds[-limit:]]

    def get_stats(self) -> VoiceStats:
        """Return aggregate statistics."""
        with self._lock:
            total_cmds = self._total_commands
            avg_conf = (
                self._confidence_sum / total_cmds if total_cmds else 0.0
            )
            return VoiceStats(
                total_sessions=len(self._sessions),
                active_sessions=sum(
                    1 for s in self._sessions.values() if s.active
                ),
                total_chunks=self._total_chunks,
                total_commands=total_cmds,
                recognised_commands=self._recognised,
                unrecognised_commands=self._unrecognised,
                avg_confidence=round(avg_conf, 4),
                registered_patterns=len(self._patterns),
            )

    def clear_history(self) -> int:
        """Clear command history. Returns number of entries cleared."""
        with self._lock:
            n = len(self._history)
            self._history.clear()
            return n

    # -- Internal helpers ---------------------------------------------------

    def _find_matches(self, text: str) -> List[CommandMatch]:
        """Find all CommandMatch patterns that match *text*."""
        hits: List[CommandMatch] = []
        with self._lock:
            patterns = list(self._patterns)
        for p in patterns:
            if re.search(p.pattern, text, re.IGNORECASE):
                hits.append(p)
                continue
            for alias in p.aliases:
                if alias.lower() in text:
                    hits.append(p)
                    break
        return hits

    def _extract_args(self, text: str, match: CommandMatch) -> List[str]:
        """Extract arguments from text after removing the command keyword."""
        cleaned = re.sub(match.pattern, "", text, flags=re.IGNORECASE).strip()
        parts = cleaned.split()
        return [w for w in parts if w]

    def _record_command(self, cmd: ParsedCommand) -> None:
        """Record a parsed command in history and update counters."""
        with self._lock:
            capped_append(self._history, cmd, max_size=self._max_history)
            self._total_commands += 1
            self._confidence_sum += cmd.confidence
            if cmd.status in (ParseStatus.matched.value, ParseStatus.ambiguous.value):
                self._recognised += 1
            else:
                self._unrecognised += 1


# -- Wingman pair validation ------------------------------------------------

def validate_wingman_pair(storyline: List[str], actuals: List[str]) -> dict:
    """VCI-001 Wingman gate.

    Validate that storyline and actuals lists are non-empty, equal-length,
    and each pair matches.  Returns a pass/fail dict with diagnostics.
    """
    if not storyline:
        return {"passed": False, "message": "Storyline list is empty"}
    if not actuals:
        return {"passed": False, "message": "Actuals list is empty"}
    if len(storyline) != len(actuals):
        return {"passed": False,
                "message": f"Length mismatch: storyline={len(storyline)} "
                           f"actuals={len(actuals)}"}
    mismatches: List[int] = []
    for i, (s, a) in enumerate(zip(storyline, actuals)):
        if s != a:
            mismatches.append(i)
    if mismatches:
        return {"passed": False,
                "message": f"Pair mismatches at indices {mismatches}"}
    return {"passed": True, "message": "Wingman pair validated",
            "pair_count": len(storyline)}


# -- Causality Sandbox gating -----------------------------------------------

def gate_vci_in_sandbox(context: dict) -> dict:
    """VCI-001 Causality Sandbox gate.

    Verify that the provided context contains the required keys for a
    VCI action and that the values are acceptable within the sandbox.
    """
    required_keys = {"text_input", "session_id"}
    missing = required_keys - set(context.keys())
    if missing:
        return {"passed": False,
                "message": f"Missing context keys: {sorted(missing)}"}
    if not context.get("text_input"):
        return {"passed": False, "message": "text_input must be non-empty"}
    if not context.get("session_id"):
        return {"passed": False, "message": "session_id must be non-empty"}
    return {"passed": True, "message": "Sandbox gate passed",
            "text_input_len": len(str(context["text_input"]))}


# -- Flask helpers ----------------------------------------------------------

def _api_body() -> Dict[str, Any]:
    """Extract JSON body from the current request."""
    return request.get_json(silent=True) or {}


def _api_need(body: Dict[str, Any], *keys: str) -> Optional[Any]:
    """Return an error tuple if any *keys* are missing from *body*."""
    for k in keys:
        if not body.get(k):
            return jsonify({"error": f"Missing required field: {k}",
                            "code": "MISSING_FIELD"}), 400
    return None


def _not_found(msg: str) -> Any:
    return jsonify({"error": msg, "code": "NOT_FOUND"}), 404


# -- Blueprint factory ------------------------------------------------------

def create_vci_api(engine: VoiceCommandInterface) -> Any:
    """Create a Flask Blueprint with VCI REST endpoints.

    Endpoints:
        POST /vci/recognise          — Run STT on text input
        POST /vci/parse              — Parse transcript to command
        POST /vci/process            — End-to-end voice pipeline
        POST /vci/sessions           — Start a new session
        DELETE /vci/sessions/<id>    — End a session
        GET  /vci/sessions           — List sessions
        GET  /vci/sessions/<id>      — Get session detail
        GET  /vci/patterns           — List command patterns
        POST /vci/patterns           — Register a pattern
        DELETE /vci/patterns/<cmd>   — Remove a pattern
        GET  /vci/history            — Command history
        DELETE /vci/history          — Clear history
        GET  /vci/stats              — Engine statistics
        GET  /vci/health             — Health check
    """
    bp = Blueprint("vci", __name__, url_prefix="/api")
    _register_stt_routes(bp, engine)
    _register_session_routes(bp, engine)
    _register_pattern_routes(bp, engine)
    _register_history_routes(bp, engine)
    _register_stats_routes(bp, engine)
    require_blueprint_auth(bp)
    return bp


def _register_stt_routes(bp: Any, eng: VoiceCommandInterface) -> None:
    """Register STT and parse endpoints."""

    @bp.route("/vci/recognise", methods=["POST"])
    def recognise() -> Any:
        body = _api_body()
        err = _api_need(body, "text_input")
        if err:
            return err
        result = eng.recognise(body["text_input"])
        return jsonify(result.to_dict()), 200

    @bp.route("/vci/parse", methods=["POST"])
    def parse() -> Any:
        body = _api_body()
        err = _api_need(body, "transcript")
        if err:
            return err
        result = eng.parse_command(body["transcript"])
        return jsonify(result.to_dict()), 200

    @bp.route("/vci/process", methods=["POST"])
    def process() -> Any:
        body = _api_body()
        err = _api_need(body, "text_input")
        if err:
            return err
        result = eng.process_voice(
            body["text_input"],
            session_id=body.get("session_id"),
        )
        return jsonify(result), 200


def _register_session_routes(bp: Any, eng: VoiceCommandInterface) -> None:
    """Register session management endpoints."""

    @bp.route("/vci/sessions", methods=["POST"])
    def start_session() -> Any:
        s = eng.start_session()
        return jsonify(s.to_dict()), 201

    @bp.route("/vci/sessions", methods=["GET"])
    def list_sessions() -> Any:
        active = request.args.get("active", "").lower() == "true"
        return jsonify(eng.list_sessions(active_only=active)), 200

    @bp.route("/vci/sessions/<session_id>", methods=["GET"])
    def get_session(session_id: str) -> Any:
        s = eng.get_session(session_id)
        if not s:
            return _not_found("Session not found")
        return jsonify(s.to_dict()), 200

    @bp.route("/vci/sessions/<session_id>", methods=["DELETE"])
    def end_session(session_id: str) -> Any:
        s = eng.end_session(session_id)
        if not s:
            return _not_found("Session not found")
        return jsonify(s.to_dict()), 200


def _register_pattern_routes(bp: Any, eng: VoiceCommandInterface) -> None:
    """Register pattern CRUD endpoints."""

    @bp.route("/vci/patterns", methods=["GET"])
    def list_patterns() -> Any:
        return jsonify(eng.list_patterns()), 200

    @bp.route("/vci/patterns", methods=["POST"])
    def register_pattern() -> Any:
        body = _api_body()
        err = _api_need(body, "pattern", "command")
        if err:
            return err
        m = eng.register_pattern(
            pattern=body["pattern"],
            command=body["command"],
            category=body.get("category", "unknown"),
            description=body.get("description", ""),
            aliases=body.get("aliases", []),
        )
        return jsonify(m.to_dict()), 201

    @bp.route("/vci/patterns/<cmd>", methods=["DELETE"])
    def remove_pattern(cmd: str) -> Any:
        removed = eng.remove_pattern(cmd)
        if not removed:
            return _not_found("Pattern not found")
        return jsonify({"removed": cmd}), 200


def _register_history_routes(bp: Any, eng: VoiceCommandInterface) -> None:
    """Register history and clear endpoints."""

    @bp.route("/vci/history", methods=["GET"])
    def get_history() -> Any:
        limit = int(request.args.get("limit", 50))
        cat = request.args.get("category")
        return jsonify(eng.get_history(limit=limit, category=cat)), 200

    @bp.route("/vci/history", methods=["DELETE"])
    def clear_history() -> Any:
        n = eng.clear_history()
        return jsonify({"cleared": n}), 200


def _register_stats_routes(bp: Any, eng: VoiceCommandInterface) -> None:
    """Register stats and health endpoints."""

    @bp.route("/vci/stats", methods=["GET"])
    def stats() -> Any:
        return jsonify(eng.get_stats().to_dict()), 200

    @bp.route("/vci/health", methods=["GET"])
    def health() -> Any:
        st = eng.get_stats()
        return jsonify({
            "status": "healthy",
            "module": "VCI-001",
            "patterns": st.registered_patterns,
            "sessions_active": st.active_sessions,
        }), 200
