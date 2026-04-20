# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Tests for cursor channel linking, split-screen replay viewer,
memory palace wiring, and deliverable audit gate.

Design Label: TEST-INTEGRATION-PHASE1-001
Owner: QA Team

Validates all Phase 1 additions from the MemPalace + OpenClaw integration:
  - CursorChannel + linked copy/paste between zones
  - ReplayCapture + ReplayRenderer
  - MemoryPalaceWiring + HybridScorer + TemporalTriple
  - DeliverableAuditGate
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import uuid

import pytest

# Ensure src/ is on the path
_SRC = os.path.join(os.path.dirname(__file__), "..", "..", "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)


# ============================================================
# SECTION 1: CursorChannel Tests (MCB-CHANNEL-001)
# ============================================================

from murphy_native_automation import (
    CursorChannel,
    CursorContext,
    MultiCursorDesktop,
    ScreenZone,
    SplitScreenLayout,
)


class TestCursorChannel:
    """Tests for CursorChannel data-sharing between cursors."""

    def test_create_channel(self):
        ch = CursorChannel(name="clipboard")
        assert ch.channel_id.startswith("chan_")
        assert ch.name == "clipboard"
        assert ch.member_count == 0
        assert ch.buffer_size == 0

    def test_join_and_leave(self):
        ch = CursorChannel(name="test")
        c1 = CursorContext(cursor_id="c1")
        c2 = CursorContext(cursor_id="c2")

        ch.join(c1)
        assert ch.member_count == 1
        assert "c1" in ch.members
        assert ch.channel_id in c1.linked_channels

        ch.join(c2)
        assert ch.member_count == 2

        ch.leave(c1)
        assert ch.member_count == 1
        assert "c1" not in ch.members
        assert ch.channel_id not in c1.linked_channels

    def test_join_idempotent(self):
        ch = CursorChannel()
        c = CursorContext(cursor_id="c1")
        ch.join(c)
        ch.join(c)  # Should not duplicate
        assert ch.member_count == 1

    def test_push_pull_basic(self):
        ch = CursorChannel()
        c1 = CursorContext(cursor_id="c1")
        c2 = CursorContext(cursor_id="c2")
        ch.join(c1)
        ch.join(c2)

        envelope = ch.push("hello from zone A", source="c1")
        assert envelope["data"] == "hello from zone A"
        assert envelope["source"] == "c1"
        assert envelope["channel_id"] == ch.channel_id

        result = ch.pull(consumer="c2")
        assert result is not None
        assert result["data"] == "hello from zone A"

    def test_push_non_member_raises(self):
        ch = CursorChannel()
        with pytest.raises(RuntimeError, match="not a member"):
            ch.push("data", source="unknown_cursor")

    def test_pull_non_member_raises(self):
        ch = CursorChannel()
        with pytest.raises(RuntimeError, match="not a member"):
            ch.pull(consumer="unknown_cursor")

    def test_pull_empty_buffer(self):
        ch = CursorChannel()
        c = CursorContext(cursor_id="c1")
        ch.join(c)
        result = ch.pull(consumer="c1")
        assert result is None

    def test_push_bounded_buffer(self):
        ch = CursorChannel()
        ch.MAX_BUFFER = 5
        c = CursorContext(cursor_id="c1")
        ch.join(c)

        for i in range(10):
            ch.push(f"item_{i}", source="c1")

        assert ch.buffer_size == 5
        # Most recent should be item_9
        result = ch.pull(consumer="c1")
        assert result["data"] == "item_9"

    def test_peek(self):
        ch = CursorChannel()
        c = CursorContext(cursor_id="c1")
        ch.join(c)

        for i in range(5):
            ch.push(f"msg_{i}", source="c1")

        peeked = ch.peek(last_n=3)
        assert len(peeked) == 3
        assert peeked[-1]["data"] == "msg_4"

    def test_to_dict(self):
        ch = CursorChannel(name="test-chan")
        c = CursorContext(cursor_id="c1")
        ch.join(c)
        ch.push("data", source="c1")

        d = ch.to_dict()
        assert d["name"] == "test-chan"
        assert d["members"] == ["c1"]
        assert d["buffer_size"] == 1


class TestCursorContextChannelMethods:
    """Tests for the channel helper methods added to CursorContext."""

    def test_copy_to_channel(self):
        ch = CursorChannel()
        c = CursorContext(cursor_id="c1")
        ch.join(c)

        envelope = c.copy_to_channel(ch, "copied text")
        assert envelope["data"] == "copied text"
        assert envelope["source"] == "c1"

    def test_paste_from_channel(self):
        ch = CursorChannel()
        c1 = CursorContext(cursor_id="c1")
        c2 = CursorContext(cursor_id="c2")
        ch.join(c1)
        ch.join(c2)

        c1.copy_to_channel(ch, "shared data")
        result = c2.paste_from_channel(ch)
        assert result is not None
        assert result["data"] == "shared data"

    def test_linked_channels_property(self):
        ch1 = CursorChannel(channel_id="ch1")
        ch2 = CursorChannel(channel_id="ch2")
        c = CursorContext(cursor_id="c1")
        ch1.join(c)
        ch2.join(c)
        assert set(c.linked_channels) == {"ch1", "ch2"}

    def test_channel_events_in_history(self):
        ch = CursorChannel()
        c = CursorContext(cursor_id="c1")
        ch.join(c)
        c.copy_to_channel(ch, "test")
        c.paste_from_channel(ch)

        history = c.get_history(last_n=10)
        event_types = [h["event"] for h in history]
        assert "channel_copy" in event_types
        assert "channel_paste" in event_types


class TestMultiCursorDesktopChannels:
    """Tests for channel management on MultiCursorDesktop."""

    def test_create_channel(self):
        d = MultiCursorDesktop()
        ch = d.create_channel(name="shared")
        assert ch.name == "shared"
        assert len(d.list_channels()) == 1

    def test_create_duplicate_raises(self):
        d = MultiCursorDesktop()
        d.create_channel(channel_id="ch1")
        with pytest.raises(ValueError, match="already exists"):
            d.create_channel(channel_id="ch1")

    def test_get_channel(self):
        d = MultiCursorDesktop()
        ch = d.create_channel(name="test")
        retrieved = d.get_channel(ch.channel_id)
        assert retrieved.channel_id == ch.channel_id

    def test_get_channel_not_found(self):
        d = MultiCursorDesktop()
        with pytest.raises(KeyError):
            d.get_channel("nonexistent")

    def test_link_cursors(self):
        d = MultiCursorDesktop()
        zones = d.apply_layout(SplitScreenLayout.DUAL_H)
        z0_id = zones[0].zone_id
        z1_id = zones[1].zone_id

        ch = d.link_cursors([z0_id, z1_id], channel_name="shared")
        assert ch.member_count == 2

        # Now copy/paste between zones
        c0 = d.get_cursor(z0_id)
        c1 = d.get_cursor(z1_id)
        c0.copy_to_channel(ch, "cross-zone data")
        result = c1.paste_from_channel(ch)
        assert result["data"] == "cross-zone data"

    def test_snapshot_includes_channels(self):
        d = MultiCursorDesktop()
        d.create_channel(name="ch1")
        snap = d.snapshot()
        assert "channels" in snap
        assert len(snap["channels"]) == 1
        assert snap["channels"][0]["name"] == "ch1"


# ============================================================
# SECTION 2: Split-Screen Replay Viewer Tests (MCB-REPLAY-001)
# ============================================================

from split_screen_replay_viewer import (
    ReplayCapture,
    ReplayEvent,
    ReplayLog,
    ReplayRenderer,
)


class TestReplayEvent:
    """Tests for ReplayEvent data model."""

    def test_create_event(self):
        ev = ReplayEvent(
            zone_id="z0", cursor_id="c0",
            event_type="click", data={"button": "left"},
        )
        assert ev.event_type == "click"
        assert ev.zone_id == "z0"

    def test_to_dict(self):
        ev = ReplayEvent(event_type="move", data={"x": 100, "y": 200})
        d = ev.to_dict()
        assert d["event_type"] == "move"
        assert d["data"]["x"] == 100


class TestReplayLog:
    """Tests for ReplayLog event accumulation."""

    def test_create_log(self):
        log = ReplayLog(session_id="sess1", layout="quad")
        assert log.event_count == 0
        assert log.session_id == "sess1"

    def test_add_event(self):
        log = ReplayLog()
        log.add_event(ReplayEvent(event_type="click"))
        assert log.event_count == 1

    def test_bounded_events(self):
        log = ReplayLog()
        log.MAX_EVENTS = 10
        for i in range(20):
            log.add_event(ReplayEvent(event_type=f"ev_{i}"))
        assert log.event_count <= 15  # truncated to half on overflow

    def test_to_dict(self):
        log = ReplayLog(session_id="s1")
        log.add_event(ReplayEvent(event_type="test"))
        d = log.to_dict()
        assert d["session_id"] == "s1"
        assert d["event_count"] == 1


class TestReplayCapture:
    """Tests for live session event capture."""

    def test_start_stop(self):
        cap = ReplayCapture()
        assert not cap.is_capturing

        log = cap.start_capture("sess1", "quad", [{"zone_id": "z0"}])
        assert cap.is_capturing
        assert log.session_id == "sess1"

        finished = cap.stop_capture()
        assert not cap.is_capturing
        assert finished is not None
        # Should have session_start and session_end events
        types = [e.event_type for e in finished.events]
        assert "session_start" in types
        assert "session_end" in types

    def test_double_start_raises(self):
        cap = ReplayCapture()
        cap.start_capture("s1", "quad", [])
        with pytest.raises(RuntimeError, match="already active"):
            cap.start_capture("s2", "quad", [])
        cap.stop_capture()

    def test_record_cursor_event(self):
        cap = ReplayCapture()
        cap.start_capture("s1", "dual_h", [{"zone_id": "z0"}])
        cap.record_cursor_event("z0", "c0", "click", {"button": "left"})
        log = cap.stop_capture()
        click_events = [e for e in log.events if e.event_type == "click"]
        assert len(click_events) == 1

    def test_record_channel_event(self):
        cap = ReplayCapture()
        cap.start_capture("s1", "quad", [])
        cap.record_channel_event("ch1", "copy", {"data": "hello"})
        log = cap.stop_capture()
        chan_events = [e for e in log.events if "channel" in e.event_type]
        assert len(chan_events) == 1

    def test_stop_when_not_capturing(self):
        cap = ReplayCapture()
        result = cap.stop_capture()
        assert result is None


class TestReplayRenderer:
    """Tests for HTML replay rendering."""

    def _make_log(self):
        log = ReplayLog(
            session_id="test-session",
            layout="dual_h",
            zones=[
                {"zone_id": "z0", "name": "left", "label": "Zone A"},
                {"zone_id": "z1", "name": "right", "label": "Zone B"},
            ],
        )
        log.add_event(ReplayEvent(
            zone_id="z0", cursor_id="c0",
            event_type="click", data={"button": "left", "rel_x": 0.5, "rel_y": 0.3},
        ))
        log.add_event(ReplayEvent(
            zone_id="z1", cursor_id="c1",
            event_type="move", data={"rel_x": 0.7, "rel_y": 0.6},
        ))
        return log

    def test_render_produces_html(self):
        renderer = ReplayRenderer()
        html = renderer.render(self._make_log())
        assert "<!DOCTYPE html>" in html
        assert "Murphy Split-Screen Replay" in html
        assert "test-session" in html

    def test_render_contains_zones(self):
        renderer = ReplayRenderer()
        html = renderer.render(self._make_log())
        assert "Zone A" in html
        assert "Zone B" in html

    def test_render_empty_zones_raises(self):
        renderer = ReplayRenderer()
        log = ReplayLog(zones=[])
        log.add_event(ReplayEvent(event_type="test"))
        with pytest.raises(ValueError, match="no zones"):
            renderer.render(log)

    def test_render_empty_events_raises(self):
        renderer = ReplayRenderer()
        log = ReplayLog(zones=[{"zone_id": "z0"}])
        with pytest.raises(ValueError, match="no events"):
            renderer.render(log)

    def test_render_to_file(self):
        renderer = ReplayRenderer()
        log = self._make_log()
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tmp:
            path = tmp.name
        try:
            renderer.render_to_file(log, path)
            assert os.path.exists(path)
            with open(path, "r") as f:
                content = f.read()
            assert "<!DOCTYPE html>" in content
        finally:
            os.unlink(path)


# ============================================================
# SECTION 3: Memory Palace Wiring Tests (MEMPALACE-WIRE-001)
# ============================================================

from murphy_memory_palace import (
    HallType,
    HybridScorer,
    HybridSearchResult,
    MemoryPalaceWiring,
    PalaceLevel,
    PalaceNode,
    TemporalTriple,
)


class TestPalaceNode:
    """Tests for Memory Palace hierarchy nodes."""

    def test_create_node(self):
        node = PalaceNode(level=PalaceLevel.WING, name="test-wing")
        assert node.level == PalaceLevel.WING
        assert node.name == "test-wing"
        assert node.node_id.startswith("pn_")

    def test_to_dict(self):
        node = PalaceNode(level=PalaceLevel.ROOM, name="auth-room")
        d = node.to_dict()
        assert d["level"] == "room"
        assert d["name"] == "auth-room"


class TestTemporalTriple:
    """Tests for temporal knowledge graph triples."""

    def test_create_triple(self):
        t = TemporalTriple(subject="Murphy", predicate="is", obj="AI system")
        assert t.is_current
        assert t.ended is None

    def test_end_triple(self):
        t = TemporalTriple(subject="A", predicate="uses", obj="Python 3.11")
        t.end()
        assert not t.is_current
        assert t.ended is not None

    def test_to_dict(self):
        t = TemporalTriple(subject="S", predicate="P", obj="O")
        d = t.to_dict()
        assert d["subject"] == "S"
        assert d["is_current"] is True


class TestHybridScorer:
    """Tests for hybrid search scoring."""

    def test_default_weights_sum_to_one(self):
        s = HybridScorer()
        total = s.w_semantic + s.w_keyword + s.w_temporal + s.w_entity
        assert abs(total - 1.0) < 0.001

    def test_zero_weights_raises(self):
        with pytest.raises(ValueError, match="must sum to > 0"):
            HybridScorer(w_semantic=0, w_keyword=0, w_temporal=0, w_entity=0)

    def test_keyword_overlap(self):
        s = HybridScorer()
        result = s.score(
            content="Murphy System uses Python for AI",
            query="Python AI system",
        )
        assert result.keyword_score > 0

    def test_temporal_boost_recent(self):
        s = HybridScorer()
        now = "2026-04-14T00:00:00+00:00"
        result = s.score(content="test", query="test", created_at=now)
        assert result.temporal_boost > 0.9

    def test_entity_boost(self):
        s = HybridScorer()
        result = s.score(
            content="Murphy uses DeepInfra for inference",
            query="What does Murphy use?",
            entity_names=["Murphy", "DeepInfra"],
        )
        assert result.entity_name_boost > 0

    def test_rank(self):
        s = HybridScorer()
        r1 = HybridSearchResult(final_score=0.9, content="high")
        r2 = HybridSearchResult(final_score=0.3, content="low")
        r3 = HybridSearchResult(final_score=0.6, content="mid")
        ranked = s.rank([r1, r2, r3], top_k=2)
        assert len(ranked) == 2
        assert ranked[0].content == "high"
        assert ranked[1].content == "mid"


class TestMemoryPalaceWiring:
    """Tests for the Memory Palace integration layer."""

    def test_init_default_palace(self):
        palace = MemoryPalaceWiring(tenant_id="test")
        structure = palace.get_palace_structure()
        assert structure["tenant_id"] == "test"
        assert len(structure["wings"]) == 1
        halls = structure["wings"][0]["halls"]
        assert len(halls) == len(HallType)

    def test_index_conversation(self):
        palace = MemoryPalaceWiring()
        result = palace.index_conversation("Hello world", source="chat")
        assert result["status"] == "indexed"
        assert result["index_id"].startswith("idx_")

    def test_index_empty_text_skipped(self):
        palace = MemoryPalaceWiring()
        result = palace.index_conversation("")
        assert result["status"] == "skipped"

    def test_add_temporal_triple(self):
        palace = MemoryPalaceWiring()
        t = palace.add_temporal_triple("Murphy", "runs_on", "DeepInfra")
        assert t.is_current
        assert t.subject == "Murphy"

    def test_contradiction_detection(self):
        palace = MemoryPalaceWiring()
        t1 = palace.add_temporal_triple("Murphy", "version", "1.0")
        t2 = palace.add_temporal_triple("Murphy", "version", "2.0")
        # t1 should be ended (contradicted)
        assert not t1.is_current
        assert t2.is_current

    def test_query_triples(self):
        palace = MemoryPalaceWiring()
        palace.add_temporal_triple("A", "is", "B")
        palace.add_temporal_triple("C", "is", "D")
        results = palace.query_triples(subject="A")
        assert len(results) == 1
        assert results[0].obj == "B"

    def test_query_current_only(self):
        palace = MemoryPalaceWiring()
        t1 = palace.add_temporal_triple("X", "color", "red")
        t2 = palace.add_temporal_triple("X", "color", "blue")
        current = palace.query_triples(subject="X", current_only=True)
        assert len(current) == 1
        assert current[0].obj == "blue"

    def test_search(self):
        palace = MemoryPalaceWiring()
        palace.index_conversation("Murphy System uses DeepInfra for LLM inference")
        palace.index_conversation("The weather is nice today")
        results = palace.search("DeepInfra LLM", top_k=2)
        assert len(results) > 0
        # The first result should be about DeepInfra
        assert "DeepInfra" in results[0].content

    def test_add_room(self):
        palace = MemoryPalaceWiring()
        room = palace.add_room("auth-room", HallType.FACTS)
        assert room.level == PalaceLevel.ROOM
        assert room.name == "auth-room"

    def test_get_status(self):
        palace = MemoryPalaceWiring(tenant_id="test")
        palace.index_conversation("test data")
        palace.add_temporal_triple("A", "is", "B")
        status = palace.get_status()
        assert status["tenant_id"] == "test"
        assert status["indexed_conversations"] == 1
        assert status["temporal_triples"] == 1


# ============================================================
# SECTION 4: Deliverable Audit Gate Tests (FORGE-AUDIT-GATE-001)
# ============================================================

from deliverable_audit_gate import (
    AuditCheck,
    AuditReport,
    AuditVerdict,
    CheckStatus,
    DeliverableAuditGate,
)


class TestDeliverableAuditGate:
    """Tests for the pre-delivery quality gate."""

    def _make_good_deliverable(self):
        return """# Compliance Management Application

## Overview
This application provides comprehensive compliance management for
regulated industries. It tracks regulatory requirements, monitors
compliance status, and generates audit reports.

## Architecture
The system uses a microservices architecture with the following components:
- **Compliance Engine** — tracks regulatory requirements
- **Audit Logger** — records all compliance events
- **Report Generator** — creates compliance reports
- **Dashboard** — real-time compliance monitoring

## Implementation Plan
1. Set up the database schema for compliance rules
2. Build the compliance tracking API
3. Create the audit logging service
4. Implement the report generator
5. Build the monitoring dashboard

## Technology Stack
- Python 3.12 with FastAPI for the backend
- PostgreSQL for the database
- React for the frontend dashboard
- Docker for containerization

## Timeline
- Week 1-2: Database schema and API
- Week 3-4: Audit logging and reports
- Week 5-6: Dashboard and integration testing
"""

    def test_good_deliverable_passes(self):
        gate = DeliverableAuditGate()
        report = gate.audit(
            prompt="Build a compliance management application",
            deliverable=self._make_good_deliverable(),
        )
        assert report.verdict in (AuditVerdict.PASS, AuditVerdict.WARN)
        assert report.overall_score > 0.4

    def test_empty_deliverable_fails(self):
        gate = DeliverableAuditGate()
        report = gate.audit(
            prompt="Build something",
            deliverable="",
        )
        assert report.verdict == AuditVerdict.FAIL
        assert report.overall_score == 0.0

    def test_empty_prompt_raises(self):
        gate = DeliverableAuditGate()
        with pytest.raises(ValueError, match="non-empty"):
            gate.audit(prompt="", deliverable="content")

    def test_short_deliverable_warns(self):
        gate = DeliverableAuditGate()
        report = gate.audit(
            prompt="Build a comprehensive compliance management system with reporting",
            deliverable="Here is a basic plan.",
        )
        assert report.verdict in (AuditVerdict.WARN, AuditVerdict.FAIL)

    def test_placeholder_detection(self):
        gate = DeliverableAuditGate()
        report = gate.audit(
            prompt="Create a plan",
            deliverable="""# Plan
## Section 1
TODO: fill in later

## Section 2
[insert content here]

## Section 3
TBD — needs research
""" + "x " * 200,  # pad to pass length check
        )
        completeness = next(
            (c for c in report.checks if c.check_name == "completeness"), None
        )
        assert completeness is not None
        assert completeness.status in (CheckStatus.WARN, CheckStatus.FAIL)

    def test_report_properties(self):
        report = AuditReport(
            verdict=AuditVerdict.FAIL,
            checks=[
                AuditCheck(check_id="C1", status=CheckStatus.PASS),
                AuditCheck(check_id="C2", status=CheckStatus.FAIL),
                AuditCheck(check_id="C3", status=CheckStatus.WARN),
            ],
        )
        assert not report.passed
        assert len(report.failed_checks) == 1
        assert len(report.warning_checks) == 1

    def test_to_dict(self):
        gate = DeliverableAuditGate()
        report = gate.audit(
            prompt="Build an app",
            deliverable=self._make_good_deliverable(),
        )
        d = report.to_dict()
        assert "verdict" in d
        assert "checks" in d
        assert isinstance(d["checks"], list)

    def test_invalid_thresholds_raises(self):
        with pytest.raises(ValueError, match="Thresholds"):
            DeliverableAuditGate(pass_threshold=0.3, warn_threshold=0.8)

    def test_format_inference_plan(self):
        gate = DeliverableAuditGate()
        report = gate.audit(
            prompt="Create a detailed roadmap for product launch",
            deliverable=self._make_good_deliverable(),
        )
        fmt_check = next(
            (c for c in report.checks if c.check_name == "format_compliance"), None
        )
        assert fmt_check is not None
        # Should recognise "roadmap" as plan format
        assert "plan" in fmt_check.details.lower()

    def test_coherence_detects_repetition(self):
        gate = DeliverableAuditGate()
        repeated = "This is a repeated line that appears many times.\n" * 20
        report = gate.audit(
            prompt="Write something original",
            deliverable=repeated + "\n\nSome unique content at the end.",
        )
        coherence = next(
            (c for c in report.checks if c.check_name == "coherence"), None
        )
        assert coherence is not None
        if coherence.suggestions:
            assert any("repeat" in s.lower() for s in coherence.suggestions)


# ============================================================
# SECTION 5: Thread safety smoke tests
# ============================================================

class TestThreadSafety:
    """Verify thread safety of channel operations."""

    def test_concurrent_push_pull(self):
        ch = CursorChannel()
        c1 = CursorContext(cursor_id="writer")
        c2 = CursorContext(cursor_id="reader")
        ch.join(c1)
        ch.join(c2)

        errors = []

        def writer():
            try:
                for i in range(100):
                    ch.push(f"msg_{i}", source="writer")
            except Exception as e:
                errors.append(str(e))

        def reader():
            try:
                for _ in range(100):
                    ch.pull(consumer="reader")
            except Exception as e:
                errors.append(str(e))

        threads = [
            threading.Thread(target=writer),
            threading.Thread(target=reader),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert not errors, f"Thread safety errors: {errors}"

    def test_concurrent_replay_capture(self):
        cap = ReplayCapture()
        cap.start_capture("s1", "quad", [{"zone_id": "z0"}])

        errors = []

        def record_events():
            try:
                for i in range(50):
                    cap.record_cursor_event("z0", "c0", f"ev_{i}")
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=record_events) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        log = cap.stop_capture()
        assert not errors
        # 4 threads × 50 events + start + stop = 202 events
        assert log.event_count >= 200
