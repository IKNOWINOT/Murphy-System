# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Comprehensive test suite for voice_command_interface — VCI-001.

Uses the storyline-actuals ``record()`` pattern to capture every check
as an auditable VCIRecord with cause / effect / lesson annotations.
"""
from __future__ import annotations

import datetime
import json
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"

from voice_command_interface import (  # noqa: E402
    AudioChunk,
    AudioFormat,
    CommandCategory,
    CommandMatch,
    ParsedCommand,
    ParseStatus,
    STTProviderKind,
    STTResult,
    VoiceCommandInterface,
    VoiceSession,
    VoiceStats,
    create_vci_api,
    gate_vci_in_sandbox,
    validate_wingman_pair,
)

# -- Record pattern --------------------------------------------------------


@dataclass
class VCIRecord:
    """One VCI check record."""

    check_id: str
    description: str
    expected: Any
    actual: Any
    passed: bool
    cause: str = ""
    effect: str = ""
    lesson: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat()
    )


_RESULTS: List[VCIRecord] = []


def record(
    check_id: str,
    description: str,
    expected: Any,
    actual: Any,
    *,
    cause: str = "",
    effect: str = "",
    lesson: str = "",
) -> None:
    passed = expected == actual
    _RESULTS.append(
        VCIRecord(
            check_id=check_id,
            description=description,
            expected=expected,
            actual=actual,
            passed=passed,
            cause=cause,
            effect=effect,
            lesson=lesson,
        )
    )
    assert passed, (
        f"[{check_id}] {description}: expected={expected!r}, got={actual!r}"
    )


# -- Tests -----------------------------------------------------------------


class TestVCIDataclasses:
    """Tests for VCI dataclass models."""

    def test_vci_001_audio_chunk_defaults(self) -> None:
        c = AudioChunk()
        record("VCI-001", "AudioChunk has chunk_id",
               True, bool(c.chunk_id),
               cause="dataclass field factory",
               effect="unique id assigned",
               lesson="uuid generates non-empty ids")

    def test_vci_002_audio_chunk_to_dict(self) -> None:
        c = AudioChunk(sample_rate=44100, channels=2)
        d = c.to_dict()
        record("VCI-002", "AudioChunk.to_dict returns sample_rate",
               44100, d["sample_rate"],
               cause="explicit constructor arg",
               effect="serialised correctly",
               lesson="asdict preserves int fields")

    def test_vci_003_stt_result_defaults(self) -> None:
        r = STTResult()
        record("VCI-003", "STTResult default confidence is 0",
               0.0, r.confidence,
               cause="no input",
               effect="confidence stays zero",
               lesson="default float is 0.0")

    def test_vci_004_stt_result_to_dict(self) -> None:
        r = STTResult(transcript="hello murphy", confidence=0.95)
        d = r.to_dict()
        record("VCI-004", "STTResult.to_dict transcript",
               "hello murphy", d["transcript"])

    def test_vci_005_parsed_command_defaults(self) -> None:
        c = ParsedCommand()
        record("VCI-005", "ParsedCommand default status is unrecognised",
               "unrecognised", c.status,
               cause="no parsing done",
               effect="status shows unrecognised",
               lesson="safe default for parse results")

    def test_vci_006_command_match_to_dict(self) -> None:
        m = CommandMatch(pattern=r"\bstatus\b", command="status",
                         category="system")
        d = m.to_dict()
        record("VCI-006", "CommandMatch.to_dict command",
               "status", d["command"])

    def test_vci_007_voice_session_active(self) -> None:
        s = VoiceSession()
        record("VCI-007", "VoiceSession starts active",
               True, s.active,
               cause="new session",
               effect="active flag True",
               lesson="sessions start as active")

    def test_vci_008_voice_stats_defaults(self) -> None:
        st = VoiceStats()
        record("VCI-008", "VoiceStats all zeros by default",
               0, st.total_sessions)


class TestVCIEnums:
    """Tests for VCI enum types."""

    def test_vci_009_audio_format_values(self) -> None:
        record("VCI-009", "AudioFormat.wav value",
               "wav", AudioFormat.wav.value)

    def test_vci_010_command_category_system(self) -> None:
        record("VCI-010", "CommandCategory.system value",
               "system", CommandCategory.system.value)

    def test_vci_011_parse_status_matched(self) -> None:
        record("VCI-011", "ParseStatus.matched value",
               "matched", ParseStatus.matched.value)

    def test_vci_012_stt_provider_builtin(self) -> None:
        record("VCI-012", "STTProviderKind.builtin_keyword value",
               "builtin_keyword", STTProviderKind.builtin_keyword.value)


class TestVCIEngineRecognise:
    """Tests for the STT recognise pipeline."""

    def test_vci_013_recognise_simple(self) -> None:
        eng = VoiceCommandInterface()
        r = eng.recognise("Hello Murphy")
        record("VCI-013", "Recognise returns lowercase transcript",
               "hello murphy", r.transcript,
               cause="builtin STT lowercases",
               effect="normalised transcript",
               lesson="consistent lowercase for matching")

    def test_vci_014_recognise_empty(self) -> None:
        eng = VoiceCommandInterface()
        r = eng.recognise("")
        record("VCI-014", "Empty input gives zero confidence",
               0.0, r.confidence)

    def test_vci_015_recognise_whitespace(self) -> None:
        eng = VoiceCommandInterface()
        r = eng.recognise("   ")
        record("VCI-015", "Whitespace-only input gets trimmed to empty",
               "", r.transcript)

    def test_vci_016_recognise_increments_chunks(self) -> None:
        eng = VoiceCommandInterface()
        eng.recognise("test")
        eng.recognise("test2")
        st = eng.get_stats()
        record("VCI-016", "Two recognise calls → 2 chunks",
               2, st.total_chunks)


class TestVCIEngineParse:
    """Tests for command parsing logic."""

    def test_vci_017_parse_status_command(self) -> None:
        eng = VoiceCommandInterface()
        cmd = eng.parse_command("show status")
        record("VCI-017", "show status → status command",
               "status", cmd.command,
               cause="matches default status pattern",
               effect="correct command extracted",
               lesson="regex patterns match voice triggers")

    def test_vci_018_parse_help_command(self) -> None:
        eng = VoiceCommandInterface()
        cmd = eng.parse_command("help")
        record("VCI-018", "help → help command",
               "help", cmd.command)

    def test_vci_019_parse_deploy_command(self) -> None:
        eng = VoiceCommandInterface()
        cmd = eng.parse_command("deploy the new version")
        record("VCI-019", "deploy ... → deploy command",
               "deploy", cmd.command)

    def test_vci_020_parse_unrecognised(self) -> None:
        eng = VoiceCommandInterface()
        cmd = eng.parse_command("xyzzy foobar nonsense")
        record("VCI-020", "Nonsense input → unrecognised",
               "unrecognised", cmd.status)

    def test_vci_021_parse_empty(self) -> None:
        eng = VoiceCommandInterface()
        cmd = eng.parse_command("")
        record("VCI-021", "Empty input → empty status",
               "empty", cmd.status)

    def test_vci_022_parse_args_extraction(self) -> None:
        eng = VoiceCommandInterface()
        cmd = eng.parse_command("query the last 10 logs")
        record("VCI-022", "query has args extracted",
               True, len(cmd.args) > 0,
               cause="text after command keyword becomes args",
               effect="args list populated",
               lesson="args let terminal receive parameters")

    def test_vci_023_parse_alias_match(self) -> None:
        eng = VoiceCommandInterface()
        cmd = eng.parse_command("check health")
        record("VCI-023", "check health alias → health command",
               "health", cmd.command,
               cause="alias in default patterns",
               effect="matched via alias",
               lesson="aliases broaden voice coverage")

    def test_vci_024_parse_security_scan(self) -> None:
        eng = VoiceCommandInterface()
        cmd = eng.parse_command("security scan please")
        record("VCI-024", "security scan → security_scan command",
               "security_scan", cmd.command)

    def test_vci_025_parse_list_modules(self) -> None:
        eng = VoiceCommandInterface()
        cmd = eng.parse_command("list modules")
        record("VCI-025", "list modules → list_modules command",
               "list_modules", cmd.command)

    def test_vci_026_parse_version(self) -> None:
        eng = VoiceCommandInterface()
        cmd = eng.parse_command("version")
        record("VCI-026", "version → version command",
               "version", cmd.command)

    def test_vci_027_parse_logs(self) -> None:
        eng = VoiceCommandInterface()
        cmd = eng.parse_command("show logs")
        record("VCI-027", "show logs → logs command",
               "logs", cmd.command)

    def test_vci_028_parse_configure(self) -> None:
        eng = VoiceCommandInterface()
        cmd = eng.parse_command("configure something")
        record("VCI-028", "configure → configure command",
               "configure", cmd.command)

    def test_vci_029_parse_stop(self) -> None:
        eng = VoiceCommandInterface()
        cmd = eng.parse_command("stop the system")
        record("VCI-029", "stop → stop command",
               "stop", cmd.command)

    def test_vci_030_parse_restart(self) -> None:
        eng = VoiceCommandInterface()
        cmd = eng.parse_command("restart now")
        record("VCI-030", "restart → restart command",
               "restart", cmd.command)

    def test_vci_031_matched_confidence_is_1(self) -> None:
        eng = VoiceCommandInterface()
        cmd = eng.parse_command("help")
        record("VCI-031", "Single match confidence is 1.0",
               1.0, cmd.confidence)


class TestVCIEngineProcessVoice:
    """Tests for end-to-end process_voice pipeline."""

    def test_vci_032_process_voice_basic(self) -> None:
        eng = VoiceCommandInterface()
        result = eng.process_voice("show status")
        record("VCI-032", "process_voice returns stt key",
               True, "stt" in result)

    def test_vci_033_process_voice_command_key(self) -> None:
        eng = VoiceCommandInterface()
        result = eng.process_voice("help")
        record("VCI-033", "process_voice returns command key",
               True, "command" in result)

    def test_vci_034_process_with_session(self) -> None:
        eng = VoiceCommandInterface()
        s = eng.start_session()
        result = eng.process_voice("deploy", session_id=s.session_id)
        s2 = eng.get_session(s.session_id)
        record("VCI-034", "Session chunks incremented after process",
               1, s2.chunks_received if s2 else -1,
               cause="process_voice with session_id",
               effect="session tracks chunks",
               lesson="sessions aggregate usage stats")


class TestVCISessionManagement:
    """Tests for session lifecycle."""

    def test_vci_035_start_session(self) -> None:
        eng = VoiceCommandInterface()
        s = eng.start_session()
        record("VCI-035", "start_session returns active session",
               True, s.active)

    def test_vci_036_end_session(self) -> None:
        eng = VoiceCommandInterface()
        s = eng.start_session()
        ended = eng.end_session(s.session_id)
        record("VCI-036", "end_session deactivates session",
               False, ended.active if ended else None)

    def test_vci_037_end_nonexistent_session(self) -> None:
        eng = VoiceCommandInterface()
        result = eng.end_session("nonexistent")
        record("VCI-037", "end_session for missing id returns None",
               None, result)

    def test_vci_038_list_sessions_active_only(self) -> None:
        eng = VoiceCommandInterface()
        s1 = eng.start_session()
        s2 = eng.start_session()
        eng.end_session(s1.session_id)
        active = eng.list_sessions(active_only=True)
        record("VCI-038", "Active filter returns only active sessions",
               1, len(active))

    def test_vci_039_list_sessions_all(self) -> None:
        eng = VoiceCommandInterface()
        eng.start_session()
        eng.start_session()
        all_s = eng.list_sessions()
        record("VCI-039", "list_sessions returns all 2 sessions",
               2, len(all_s))


class TestVCIPatternManagement:
    """Tests for command pattern registration."""

    def test_vci_040_register_custom_pattern(self) -> None:
        eng = VoiceCommandInterface()
        initial = len(eng.list_patterns())
        eng.register_pattern(r"\bbackup\b", "backup", "system", "Run backup")
        record("VCI-040", "register_pattern adds one pattern",
               initial + 1, len(eng.list_patterns()))

    def test_vci_041_custom_pattern_matches(self) -> None:
        eng = VoiceCommandInterface()
        eng.register_pattern(r"\bbackup\b", "backup", "system")
        cmd = eng.parse_command("run backup now")
        record("VCI-041", "Custom pattern matches input",
               "backup", cmd.command)

    def test_vci_042_remove_pattern(self) -> None:
        eng = VoiceCommandInterface()
        eng.register_pattern(r"\bbackup\b", "backup_cmd")
        removed = eng.remove_pattern("backup_cmd")
        record("VCI-042", "remove_pattern returns True",
               True, removed)

    def test_vci_043_remove_nonexistent_pattern(self) -> None:
        eng = VoiceCommandInterface()
        removed = eng.remove_pattern("no_such_cmd")
        record("VCI-043", "remove nonexistent pattern returns False",
               False, removed)

    def test_vci_044_register_with_enum_category(self) -> None:
        eng = VoiceCommandInterface()
        m = eng.register_pattern(r"\btest\b", "test_cmd",
                                 CommandCategory.monitor)
        record("VCI-044", "Enum category stored as string",
               "monitor", m.category)


class TestVCIHistoryAndStats:
    """Tests for history and statistics tracking."""

    def test_vci_045_history_records_commands(self) -> None:
        eng = VoiceCommandInterface()
        eng.parse_command("status")
        eng.parse_command("help")
        h = eng.get_history()
        record("VCI-045", "History has 2 entries after 2 parses",
               2, len(h))

    def test_vci_046_history_filter_by_category(self) -> None:
        eng = VoiceCommandInterface()
        eng.parse_command("status")    # system
        eng.parse_command("help")      # help
        eng.parse_command("deploy")    # deploy
        h = eng.get_history(category="system")
        record("VCI-046", "Category filter returns system commands only",
               True, all(c["category"] == "system" for c in h))

    def test_vci_047_history_limit(self) -> None:
        eng = VoiceCommandInterface()
        for _ in range(10):
            eng.parse_command("status")
        h = eng.get_history(limit=3)
        record("VCI-047", "History limit caps at 3",
               3, len(h))

    def test_vci_048_clear_history(self) -> None:
        eng = VoiceCommandInterface()
        eng.parse_command("status")
        eng.parse_command("help")
        n = eng.clear_history()
        record("VCI-048", "clear_history returns count of cleared",
               2, n)

    def test_vci_049_stats_after_commands(self) -> None:
        eng = VoiceCommandInterface()
        eng.parse_command("status")
        eng.parse_command("xyzzy")
        st = eng.get_stats()
        record("VCI-049", "Stats total_commands is 2",
               2, st.total_commands,
               cause="one matched + one unrecognised",
               effect="both counted",
               lesson="stats track all attempts")

    def test_vci_050_stats_recognised_count(self) -> None:
        eng = VoiceCommandInterface()
        eng.parse_command("status")
        eng.parse_command("help")
        eng.parse_command("xyzzy")
        st = eng.get_stats()
        record("VCI-050", "Stats recognised_commands is 2",
               2, st.recognised_commands)

    def test_vci_051_stats_unrecognised_count(self) -> None:
        eng = VoiceCommandInterface()
        eng.parse_command("xyzzy")
        st = eng.get_stats()
        record("VCI-051", "Stats unrecognised_commands is 1",
               1, st.unrecognised_commands)

    def test_vci_052_stats_avg_confidence(self) -> None:
        eng = VoiceCommandInterface()
        eng.parse_command("status")   # 1.0
        eng.parse_command("xyzzy")    # 0.0
        st = eng.get_stats()
        record("VCI-052", "Avg confidence is 0.5",
               0.5, st.avg_confidence)


class TestVCIWingmanAndSandbox:
    """Tests for Wingman pair validation and Sandbox gating."""

    def test_vci_053_wingman_pass(self) -> None:
        r = validate_wingman_pair(["a", "b"], ["a", "b"])
        record("VCI-053", "Wingman pass with matching pairs",
               True, r["passed"])

    def test_vci_054_wingman_empty_storyline(self) -> None:
        r = validate_wingman_pair([], ["a"])
        record("VCI-054", "Wingman fail on empty storyline",
               False, r["passed"])

    def test_vci_055_wingman_empty_actuals(self) -> None:
        r = validate_wingman_pair(["a"], [])
        record("VCI-055", "Wingman fail on empty actuals",
               False, r["passed"])

    def test_vci_056_wingman_length_mismatch(self) -> None:
        r = validate_wingman_pair(["a", "b"], ["a"])
        record("VCI-056", "Wingman fail on length mismatch",
               False, r["passed"])

    def test_vci_057_wingman_value_mismatch(self) -> None:
        r = validate_wingman_pair(["a", "b"], ["a", "c"])
        record("VCI-057", "Wingman fail on value mismatch",
               False, r["passed"])

    def test_vci_058_sandbox_pass(self) -> None:
        ctx = {"text_input": "hello", "session_id": "s1"}
        r = gate_vci_in_sandbox(ctx)
        record("VCI-058", "Sandbox pass with valid context",
               True, r["passed"])

    def test_vci_059_sandbox_missing_keys(self) -> None:
        r = gate_vci_in_sandbox({})
        record("VCI-059", "Sandbox fail on missing keys",
               False, r["passed"])

    def test_vci_060_sandbox_empty_text(self) -> None:
        r = gate_vci_in_sandbox({"text_input": "", "session_id": "s1"})
        record("VCI-060", "Sandbox fail on empty text_input",
               False, r["passed"])

    def test_vci_061_sandbox_empty_session(self) -> None:
        r = gate_vci_in_sandbox({"text_input": "hi", "session_id": ""})
        record("VCI-061", "Sandbox fail on empty session_id",
               False, r["passed"])


class TestVCIThreadSafety:
    """Thread-safety tests for the VCI engine."""

    def test_vci_062_concurrent_parse(self) -> None:
        eng = VoiceCommandInterface()
        errors: List[str] = []

        def worker(text: str) -> None:
            try:
                for _ in range(50):
                    eng.parse_command(text)
            except Exception as exc:
                errors.append(str(exc))

        threads = [
            threading.Thread(target=worker, args=("status",)),
            threading.Thread(target=worker, args=("help",)),
            threading.Thread(target=worker, args=("deploy",)),
            threading.Thread(target=worker, args=("xyzzy",)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        st = eng.get_stats()
        record("VCI-062", "200 concurrent commands without errors",
               True, len(errors) == 0 and st.total_commands == 200,
               cause="4 threads × 50 commands",
               effect="all recorded, no exceptions",
               lesson="Lock protects shared state")

    def test_vci_063_concurrent_sessions(self) -> None:
        eng = VoiceCommandInterface()
        sessions: List[str] = []
        lock = threading.Lock()

        def creator() -> None:
            for _ in range(20):
                s = eng.start_session()
                with lock:
                    sessions.append(s.session_id)

        threads = [threading.Thread(target=creator) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        record("VCI-063", "80 concurrent session creates",
               80, len(sessions))


class TestVCIFlaskBlueprint:
    """Tests for the Flask Blueprint API layer."""

    def _make_client(self) -> Any:
        from flask import Flask
        eng = VoiceCommandInterface()
        app = Flask(__name__)
        app.register_blueprint(create_vci_api(eng))
        app.config["TESTING"] = True
        return app.test_client(), eng

    def test_vci_064_recognise_endpoint(self) -> None:
        client, _ = self._make_client()
        resp = client.post("/api/vci/recognise",
                           json={"text_input": "hello murphy"})
        record("VCI-064", "POST /api/vci/recognise returns 200",
               200, resp.status_code)

    def test_vci_065_recognise_missing_field(self) -> None:
        client, _ = self._make_client()
        resp = client.post("/api/vci/recognise", json={})
        record("VCI-065", "POST /api/vci/recognise missing field → 400",
               400, resp.status_code)

    def test_vci_066_parse_endpoint(self) -> None:
        client, _ = self._make_client()
        resp = client.post("/api/vci/parse",
                           json={"transcript": "status"})
        data = resp.get_json()
        record("VCI-066", "POST /api/vci/parse returns command",
               "status", data.get("command"))

    def test_vci_067_process_endpoint(self) -> None:
        client, _ = self._make_client()
        resp = client.post("/api/vci/process",
                           json={"text_input": "help"})
        data = resp.get_json()
        record("VCI-067", "POST /api/vci/process returns stt + command",
               True, "stt" in data and "command" in data)

    def test_vci_068_sessions_create(self) -> None:
        client, _ = self._make_client()
        resp = client.post("/api/vci/sessions")
        record("VCI-068", "POST /api/vci/sessions → 201",
               201, resp.status_code)

    def test_vci_069_sessions_list(self) -> None:
        client, _ = self._make_client()
        client.post("/api/vci/sessions")
        resp = client.get("/api/vci/sessions")
        data = resp.get_json()
        record("VCI-069", "GET /api/vci/sessions returns list",
               True, isinstance(data, list) and len(data) >= 1)

    def test_vci_070_session_get(self) -> None:
        client, _ = self._make_client()
        resp = client.post("/api/vci/sessions")
        sid = resp.get_json()["session_id"]
        resp2 = client.get(f"/api/vci/sessions/{sid}")
        record("VCI-070", "GET /api/vci/sessions/<id> returns session",
               200, resp2.status_code)

    def test_vci_071_session_delete(self) -> None:
        client, _ = self._make_client()
        resp = client.post("/api/vci/sessions")
        sid = resp.get_json()["session_id"]
        resp2 = client.delete(f"/api/vci/sessions/{sid}")
        data = resp2.get_json()
        record("VCI-071", "DELETE /api/vci/sessions/<id> deactivates",
               False, data.get("active"))

    def test_vci_072_session_not_found(self) -> None:
        client, _ = self._make_client()
        resp = client.get("/api/vci/sessions/no_such_id")
        record("VCI-072", "GET nonexistent session → 404",
               404, resp.status_code)

    def test_vci_073_patterns_list(self) -> None:
        client, _ = self._make_client()
        resp = client.get("/api/vci/patterns")
        data = resp.get_json()
        record("VCI-073", "GET /api/vci/patterns returns list ≥ 12",
               True, isinstance(data, list) and len(data) >= 12)

    def test_vci_074_patterns_register(self) -> None:
        client, _ = self._make_client()
        resp = client.post("/api/vci/patterns",
                           json={"pattern": r"\bbackup\b",
                                 "command": "backup",
                                 "category": "system"})
        record("VCI-074", "POST /api/vci/patterns → 201",
               201, resp.status_code)

    def test_vci_075_patterns_delete(self) -> None:
        client, _ = self._make_client()
        client.post("/api/vci/patterns",
                    json={"pattern": r"\bmy_cmd\b", "command": "my_cmd"})
        resp = client.delete("/api/vci/patterns/my_cmd")
        record("VCI-075", "DELETE /api/vci/patterns/my_cmd → 200",
               200, resp.status_code)

    def test_vci_076_patterns_delete_not_found(self) -> None:
        client, _ = self._make_client()
        resp = client.delete("/api/vci/patterns/nope")
        record("VCI-076", "DELETE nonexistent pattern → 404",
               404, resp.status_code)

    def test_vci_077_history_endpoint(self) -> None:
        client, eng = self._make_client()
        eng.parse_command("status")
        resp = client.get("/api/vci/history")
        data = resp.get_json()
        record("VCI-077", "GET /api/vci/history returns list",
               True, isinstance(data, list) and len(data) >= 1)

    def test_vci_078_history_clear(self) -> None:
        client, eng = self._make_client()
        eng.parse_command("status")
        resp = client.delete("/api/vci/history")
        data = resp.get_json()
        record("VCI-078", "DELETE /api/vci/history returns cleared count",
               True, data.get("cleared", 0) >= 1)

    def test_vci_079_stats_endpoint(self) -> None:
        client, _ = self._make_client()
        resp = client.get("/api/vci/stats")
        data = resp.get_json()
        record("VCI-079", "GET /api/vci/stats returns total_sessions",
               True, "total_sessions" in data)

    def test_vci_080_health_endpoint(self) -> None:
        client, _ = self._make_client()
        resp = client.get("/api/vci/health")
        data = resp.get_json()
        record("VCI-080", "GET /api/vci/health returns healthy",
               "healthy", data.get("status"))


class TestVCICustomSTT:
    """Tests for pluggable STT provider."""

    def test_vci_081_custom_stt_provider(self) -> None:
        def my_stt(text: str) -> STTResult:
            return STTResult(transcript=text.upper(), confidence=0.8,
                             provider="custom")

        eng = VoiceCommandInterface(stt_fn=my_stt)
        r = eng.recognise("hello")
        record("VCI-081", "Custom STT provider produces uppercase",
               "HELLO", r.transcript,
               cause="custom stt_fn uppercases",
               effect="transcript is HELLO",
               lesson="pluggable STT allows any provider")

    def test_vci_082_custom_stt_confidence(self) -> None:
        def my_stt(text: str) -> STTResult:
            return STTResult(transcript=text, confidence=0.42,
                             provider="mock")

        eng = VoiceCommandInterface(stt_fn=my_stt)
        r = eng.recognise("test")
        record("VCI-082", "Custom STT confidence propagates",
               0.42, r.confidence)


class TestVCIEdgeCases:
    """Edge case and boundary tests."""

    def test_vci_083_very_long_input(self) -> None:
        eng = VoiceCommandInterface()
        long_text = "status " * 500
        cmd = eng.parse_command(long_text)
        record("VCI-083", "Very long input doesn't crash",
               True, cmd.command == "status")

    def test_vci_084_special_characters(self) -> None:
        eng = VoiceCommandInterface()
        cmd = eng.parse_command("!@#$%^&*()")
        record("VCI-084", "Special chars → unrecognised",
               "unrecognised", cmd.status)

    def test_vci_085_unicode_input(self) -> None:
        eng = VoiceCommandInterface()
        cmd = eng.parse_command("状态 status 检查")
        record("VCI-085", "Unicode + status keyword → matched",
               "status", cmd.command)

    def test_vci_086_case_insensitive_match(self) -> None:
        eng = VoiceCommandInterface()
        cmd = eng.parse_command("DEPLOY NOW")
        record("VCI-086", "Uppercase DEPLOY matches",
               "deploy", cmd.command,
               cause="normalised to lowercase before matching",
               effect="case-insensitive",
               lesson="voice input may come in any case")

    def test_vci_087_max_history_boundary(self) -> None:
        eng = VoiceCommandInterface(max_history=20)
        for _ in range(30):
            eng.parse_command("status")
        h = eng.get_history(limit=100)
        record("VCI-087", "History capped at max_history",
               True, len(h) <= 20)

    def test_vci_088_process_voice_no_session(self) -> None:
        eng = VoiceCommandInterface()
        result = eng.process_voice("help")
        record("VCI-088", "process_voice without session_id works",
               "", result["session_id"])
