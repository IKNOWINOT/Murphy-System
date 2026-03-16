"""
Gap Closure Tests — Multi-Cursor Split-Screen Desktop Automation.

Validates the split-screen desktop automation subsystem (INC-06):

  Gap 1 (Critical): No multi-zone desktop layout system existed; all
                    automation was single-cursor, single-viewport.
  Gap 2 (High):     No coordinator existed to lifecycle-manage multiple
                    concurrent split-screen sessions.

Gaps addressed:
 1. SplitScreenLayout enum (7 values)
 2. ScreenZone dataclass — normalised coords, point-in-zone, centre
 3. CursorContext dataclass — cursor state per zone
 4. MultiCursorDesktop — thread-safe cursor pool
 5. SplitScreenManager — builds / queries zones for each layout
 6. SplitScreenSession — full session lifecycle (PENDING → ACTIVE → COMPLETED)
 7. SplitScreenCoordinator — multi-session lifecycle manager
 8. Session pause / resume / fail paths
 9. Custom zone layout support
10. Thread safety under concurrent access
"""

import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pytest


# ===========================================================================
# Helpers
# ===========================================================================

def _get_classes():
    from murphy_native_automation import (
        SplitScreenLayout,
        ScreenZone,
        CursorContext,
        MultiCursorDesktop,
        SplitScreenManager,
    )
    return SplitScreenLayout, ScreenZone, CursorContext, MultiCursorDesktop, SplitScreenManager


def _get_coordinator_classes():
    from split_screen_coordinator import (
        SplitScreenCoordinator,
        SplitScreenSession,
        SessionState,
    )
    return SplitScreenCoordinator, SplitScreenSession, SessionState


# ===========================================================================
# Gap 1 — SplitScreenLayout enum
# ===========================================================================

class TestGap1_SplitScreenLayout:
    def test_enum_values_present(self):
        SplitScreenLayout, *_ = _get_classes()
        assert SplitScreenLayout.SINGLE.value == "single"
        assert SplitScreenLayout.DUAL_H.value == "dual_horizontal"
        assert SplitScreenLayout.DUAL_V.value == "dual_vertical"
        assert SplitScreenLayout.TRIPLE_H.value == "triple_horizontal"
        assert SplitScreenLayout.QUAD.value == "quad"
        assert SplitScreenLayout.HEXA.value == "hexa"
        assert SplitScreenLayout.CUSTOM.value == "custom"

    def test_enum_has_seven_values(self):
        SplitScreenLayout, *_ = _get_classes()
        assert len(list(SplitScreenLayout)) == 7

    def test_enum_is_string(self):
        SplitScreenLayout, *_ = _get_classes()
        assert isinstance(SplitScreenLayout.QUAD, str)

    def test_enum_comparison(self):
        SplitScreenLayout, *_ = _get_classes()
        assert SplitScreenLayout.QUAD == "quad"


# ===========================================================================
# Gap 2 — ScreenZone dataclass
# ===========================================================================

class TestGap2_ScreenZone:
    def _make_zone(self, x=0.0, y=0.0, w=0.5, h=0.5, zid="z0", label="test"):
        _, ScreenZone, *_ = _get_classes()
        return ScreenZone(zid, x, y, w, h, label=label)

    def test_zone_creation(self):
        z = self._make_zone()
        assert z.zone_id == "z0"
        assert z.x == 0.0
        assert z.y == 0.0
        assert z.width == 0.5
        assert z.height == 0.5

    def test_zone_default_label(self):
        _, ScreenZone, *_ = _get_classes()
        z = ScreenZone("z1", 0.0, 0.0, 1.0, 1.0)
        assert z.label == ""

    def test_zone_invalid_x_raises(self):
        _, ScreenZone, *_ = _get_classes()
        with pytest.raises(ValueError):
            ScreenZone("z0", 1.5, 0.0, 0.5, 0.5)

    def test_zone_invalid_y_raises(self):
        _, ScreenZone, *_ = _get_classes()
        with pytest.raises(ValueError):
            ScreenZone("z0", 0.0, -0.1, 0.5, 0.5)

    def test_zone_zero_width_raises(self):
        _, ScreenZone, *_ = _get_classes()
        with pytest.raises(ValueError):
            ScreenZone("z0", 0.0, 0.0, 0.0, 0.5)

    def test_zone_contains_point_true(self):
        z = self._make_zone(x=0.0, y=0.0, w=0.5, h=0.5)
        assert z.contains_point(0.25, 0.25)

    def test_zone_contains_point_false(self):
        z = self._make_zone(x=0.0, y=0.0, w=0.5, h=0.5)
        assert not z.contains_point(0.75, 0.75)

    def test_zone_contains_boundary_point(self):
        z = self._make_zone(x=0.0, y=0.0, w=0.5, h=0.5)
        assert z.contains_point(0.0, 0.0)
        assert z.contains_point(0.5, 0.5)

    def test_zone_centre(self):
        z = self._make_zone(x=0.0, y=0.0, w=1.0, h=1.0)
        cx, cy = z.centre()
        assert abs(cx - 0.5) < 1e-9
        assert abs(cy - 0.5) < 1e-9

    def test_zone_centre_offset(self):
        z = self._make_zone(x=0.5, y=0.5, w=0.5, h=0.5)
        cx, cy = z.centre()
        assert abs(cx - 0.75) < 1e-9
        assert abs(cy - 0.75) < 1e-9

    def test_zone_to_dict(self):
        z = self._make_zone(x=0.1, y=0.2, w=0.3, h=0.4, zid="zx", label="lbl")
        d = z.to_dict()
        assert d["zone_id"] == "zx"
        assert d["label"] == "lbl"
        assert d["x"] == 0.1
        assert d["width"] == 0.3


# ===========================================================================
# Gap 3 — CursorContext
# ===========================================================================

class TestGap3_CursorContext:
    def _make_cursor(self):
        _, _, CursorContext, *_ = _get_classes()
        return CursorContext(cursor_id="c0", zone_id="z0")

    def test_cursor_defaults(self):
        c = self._make_cursor()
        assert c.cursor_id == "c0"
        assert c.zone_id == "z0"
        assert c.is_active is True
        assert c.position == (0.5, 0.5)

    def test_cursor_move_to(self):
        c = self._make_cursor()
        c.move_to(0.1, 0.9)
        assert c.position == (0.1, 0.9)

    def test_cursor_move_out_of_range_raises(self):
        c = self._make_cursor()
        with pytest.raises(ValueError):
            c.move_to(1.5, 0.5)

    def test_cursor_assign_zone(self):
        c = self._make_cursor()
        c.assign_zone("z1")
        assert c.zone_id == "z1"

    def test_cursor_assign_empty_zone_raises(self):
        c = self._make_cursor()
        with pytest.raises(ValueError):
            c.assign_zone("")

    def test_cursor_to_dict(self):
        c = self._make_cursor()
        d = c.to_dict()
        assert d["cursor_id"] == "c0"
        assert d["zone_id"] == "z0"
        assert d["is_active"] is True

    def test_cursor_metadata(self):
        _, _, CursorContext, *_ = _get_classes()
        c = CursorContext("c1", "z0", metadata={"task": "click"})
        assert c.metadata["task"] == "click"


# ===========================================================================
# Gap 4 — MultiCursorDesktop
# ===========================================================================

class TestGap4_MultiCursorDesktop:
    def _make_desktop(self):
        _, _, _, MultiCursorDesktop, _ = _get_classes()
        return MultiCursorDesktop()

    def test_add_cursor(self):
        desk = self._make_desktop()
        ctx = desk.add_cursor("c0", "z0")
        assert ctx.cursor_id == "c0"

    def test_add_duplicate_raises(self):
        desk = self._make_desktop()
        desk.add_cursor("c0", "z0")
        with pytest.raises(ValueError):
            desk.add_cursor("c0", "z1")

    def test_remove_cursor(self):
        desk = self._make_desktop()
        desk.add_cursor("c0", "z0")
        desk.remove_cursor("c0")
        assert desk.cursor_count() == 0

    def test_remove_nonexistent_raises(self):
        desk = self._make_desktop()
        with pytest.raises(KeyError):
            desk.remove_cursor("ghost")

    def test_get_cursor(self):
        desk = self._make_desktop()
        desk.add_cursor("c0", "z0")
        ctx = desk.get_cursor("c0")
        assert ctx.zone_id == "z0"

    def test_get_nonexistent_raises(self):
        desk = self._make_desktop()
        with pytest.raises(KeyError):
            desk.get_cursor("nope")

    def test_cursors_in_zone(self):
        desk = self._make_desktop()
        desk.add_cursor("c0", "z0")
        desk.add_cursor("c1", "z1")
        desk.add_cursor("c2", "z0")
        assert len(desk.cursors_in_zone("z0")) == 2

    def test_active_cursor_ids(self):
        desk = self._make_desktop()
        desk.add_cursor("c0", "z0")
        ctx = desk.add_cursor("c1", "z0")
        ctx.is_active = False
        assert desk.active_cursor_ids() == ["c0"]

    def test_cursor_count(self):
        desk = self._make_desktop()
        desk.add_cursor("c0", "z0")
        desk.add_cursor("c1", "z1")
        assert desk.cursor_count() == 2

    def test_snapshot(self):
        desk = self._make_desktop()
        desk.add_cursor("c0", "z0")
        snap = desk.snapshot()
        assert isinstance(snap, list)
        assert len(snap) == 1
        assert snap[0]["cursor_id"] == "c0"


# ===========================================================================
# Gap 5 — SplitScreenManager layouts
# ===========================================================================

class TestGap5_SplitScreenManager:
    def _make_manager(self, layout):
        *_, SplitScreenManager = _get_classes()
        SplitScreenLayout, *_ = _get_classes()
        return SplitScreenManager(SplitScreenLayout[layout])

    def test_single_one_zone(self):
        m = self._make_manager("SINGLE")
        assert m.zone_count() == 1

    def test_dual_h_two_zones(self):
        m = self._make_manager("DUAL_H")
        assert m.zone_count() == 2

    def test_dual_v_two_zones(self):
        m = self._make_manager("DUAL_V")
        assert m.zone_count() == 2

    def test_triple_h_three_zones(self):
        m = self._make_manager("TRIPLE_H")
        assert m.zone_count() == 3

    def test_quad_four_zones(self):
        m = self._make_manager("QUAD")
        assert m.zone_count() == 4

    def test_hexa_six_zones(self):
        m = self._make_manager("HEXA")
        assert m.zone_count() == 6

    def test_zone_ids_returned(self):
        m = self._make_manager("DUAL_V")
        ids = m.zone_ids()
        assert set(ids) == {"z0", "z1"}

    def test_get_zone_valid(self):
        m = self._make_manager("QUAD")
        z = m.get_zone("z0")
        assert z is not None

    def test_get_zone_invalid_raises(self):
        m = self._make_manager("QUAD")
        with pytest.raises(KeyError):
            m.get_zone("z99")

    def test_find_zone_at_centre(self):
        m = self._make_manager("DUAL_V")
        z = m.find_zone_at(0.25, 0.5)
        assert z is not None
        assert z.label == "left"

    def test_find_zone_at_right(self):
        m = self._make_manager("DUAL_V")
        z = m.find_zone_at(0.75, 0.5)
        assert z is not None
        assert z.label == "right"

    def test_find_zone_outside_returns_none(self):
        m = self._make_manager("SINGLE")
        assert m.find_zone_at(1.5, 0.5) is None

    def test_custom_layout_requires_zones(self):
        _, _, _, _, SplitScreenManager = _get_classes()
        SplitScreenLayout, *_ = _get_classes()
        with pytest.raises(ValueError):
            SplitScreenManager(SplitScreenLayout.CUSTOM, custom_zones=[])

    def test_custom_layout_with_zones(self):
        SplitScreenLayout, ScreenZone, _, _, SplitScreenManager = _get_classes()
        zones = [
            ScreenZone("a", 0.0, 0.0, 0.3, 1.0, label="left"),
            ScreenZone("b", 0.3, 0.0, 0.7, 1.0, label="right"),
        ]
        m = SplitScreenManager(SplitScreenLayout.CUSTOM, custom_zones=zones)
        assert m.zone_count() == 2

    def test_snapshot_structure(self):
        m = self._make_manager("QUAD")
        snap = m.snapshot()
        assert len(snap) == 4
        assert all("zone_id" in z for z in snap)


# ===========================================================================
# Gap 6 — SplitScreenSession lifecycle
# ===========================================================================

class TestGap6_SplitScreenSession:
    def _make_session(self):
        SplitScreenCoordinator, SplitScreenSession, SessionState = _get_coordinator_classes()
        SplitScreenLayout, *_ = _get_classes()
        coord = SplitScreenCoordinator()
        return coord.create_session(SplitScreenLayout.QUAD), SessionState

    def test_session_starts_pending(self):
        session, SessionState = self._make_session()
        assert session.state == SessionState.PENDING

    def test_session_start(self):
        session, SessionState = self._make_session()
        session.start()
        assert session.state == SessionState.ACTIVE

    def test_session_complete(self):
        session, SessionState = self._make_session()
        session.start()
        session.complete()
        assert session.state == SessionState.COMPLETED

    def test_session_has_zone_count(self):
        session, _ = self._make_session()
        assert session.manager.zone_count() == 4

    def test_session_add_cursor(self):
        session, _ = self._make_session()
        session.start()
        ctx = session.add_cursor("c0", "z0")
        assert ctx.cursor_id == "c0"

    def test_session_add_cursor_invalid_zone_raises(self):
        session, _ = self._make_session()
        session.start()
        with pytest.raises(KeyError):
            session.add_cursor("c0", "z99")

    def test_session_add_cursor_completed_raises(self):
        session, _ = self._make_session()
        session.start()
        session.complete()
        with pytest.raises(RuntimeError):
            session.add_cursor("c0", "z0")

    def test_session_to_dict(self):
        session, _ = self._make_session()
        d = session.to_dict()
        assert "session_id" in d
        assert "state" in d
        assert "zone_count" in d

    def test_session_started_at_set(self):
        session, _ = self._make_session()
        assert session.started_at is None
        session.start()
        assert session.started_at is not None

    def test_session_finished_at_set(self):
        session, _ = self._make_session()
        session.start()
        session.complete()
        assert session.finished_at is not None


# ===========================================================================
# Gap 7 — SplitScreenCoordinator
# ===========================================================================

class TestGap7_SplitScreenCoordinator:
    def _make_coord(self):
        SplitScreenCoordinator, _, _ = _get_coordinator_classes()
        return SplitScreenCoordinator()

    def test_create_session(self):
        SplitScreenLayout, *_ = _get_classes()
        coord = self._make_coord()
        s = coord.create_session(SplitScreenLayout.QUAD)
        assert s is not None

    def test_get_session(self):
        SplitScreenLayout, *_ = _get_classes()
        coord = self._make_coord()
        s = coord.create_session(SplitScreenLayout.DUAL_V)
        s2 = coord.get_session(s.session_id)
        assert s.session_id == s2.session_id

    def test_get_nonexistent_raises(self):
        coord = self._make_coord()
        with pytest.raises(KeyError):
            coord.get_session("fake-id")

    def test_remove_session(self):
        SplitScreenLayout, *_ = _get_classes()
        coord = self._make_coord()
        s = coord.create_session(SplitScreenLayout.SINGLE)
        coord.remove_session(s.session_id)
        assert coord.session_count() == 0

    def test_remove_nonexistent_raises(self):
        coord = self._make_coord()
        with pytest.raises(KeyError):
            coord.remove_session("nope")

    def test_duplicate_session_id_raises(self):
        SplitScreenLayout, *_ = _get_classes()
        coord = self._make_coord()
        coord.create_session(SplitScreenLayout.SINGLE, session_id="abc")
        with pytest.raises(ValueError):
            coord.create_session(SplitScreenLayout.SINGLE, session_id="abc")

    def test_session_count(self):
        SplitScreenLayout, *_ = _get_classes()
        coord = self._make_coord()
        coord.create_session(SplitScreenLayout.DUAL_V)
        coord.create_session(SplitScreenLayout.QUAD)
        assert coord.session_count() == 2

    def test_active_sessions(self):
        SplitScreenLayout, *_ = _get_classes()
        coord = self._make_coord()
        s = coord.create_session(SplitScreenLayout.DUAL_V)
        s.start()
        assert len(coord.active_sessions()) == 1

    def test_sessions_by_state(self):
        SplitScreenLayout, *_ = _get_classes()
        _, _, SessionState = _get_coordinator_classes()
        coord = self._make_coord()
        s1 = coord.create_session(SplitScreenLayout.DUAL_V)
        s2 = coord.create_session(SplitScreenLayout.QUAD)
        s1.start()
        active = coord.sessions_by_state(SessionState.ACTIVE)
        pending = coord.sessions_by_state(SessionState.PENDING)
        assert len(active) == 1
        assert len(pending) == 1

    def test_snapshot(self):
        SplitScreenLayout, *_ = _get_classes()
        coord = self._make_coord()
        coord.create_session(SplitScreenLayout.SINGLE)
        snap = coord.snapshot()
        assert len(snap) == 1
        assert "session_id" in snap[0]


# ===========================================================================
# Gap 8 — Pause / Resume / Fail paths
# ===========================================================================

class TestGap8_SessionStateTransitions:
    def _make_session(self):
        SplitScreenCoordinator, SplitScreenSession, SessionState = _get_coordinator_classes()
        SplitScreenLayout, *_ = _get_classes()
        coord = SplitScreenCoordinator()
        session = coord.create_session(SplitScreenLayout.QUAD)
        return session, SessionState

    def test_pause_active(self):
        session, SessionState = self._make_session()
        session.start()
        session.pause()
        assert session.state == SessionState.PAUSED

    def test_pause_non_active_raises(self):
        session, _ = self._make_session()
        with pytest.raises(RuntimeError):
            session.pause()

    def test_resume_paused(self):
        session, SessionState = self._make_session()
        session.start()
        session.pause()
        session.resume()
        assert session.state == SessionState.ACTIVE

    def test_resume_non_paused_raises(self):
        session, _ = self._make_session()
        session.start()
        with pytest.raises(RuntimeError):
            session.resume()

    def test_fail_active_session(self):
        session, SessionState = self._make_session()
        session.start()
        session.fail("disk full")
        assert session.state == SessionState.FAILED
        assert "disk full" in session.errors

    def test_fail_appends_reason(self):
        session, _ = self._make_session()
        session.start()
        session.fail("error A")
        session.fail("error B")
        assert len(session.errors) == 2

    def test_start_already_active_raises(self):
        session, _ = self._make_session()
        session.start()
        with pytest.raises(RuntimeError):
            session.start()

    def test_complete_paused_session(self):
        session, SessionState = self._make_session()
        session.start()
        session.pause()
        session.complete()
        assert session.state == SessionState.COMPLETED


# ===========================================================================
# Gap 9 — Custom zone layout
# ===========================================================================

class TestGap9_CustomLayout:
    def test_custom_zones_wired(self):
        SplitScreenLayout, ScreenZone, _, _, _ = _get_classes()
        SplitScreenCoordinator, _, _ = _get_coordinator_classes()
        coord = SplitScreenCoordinator()
        zones = [
            ScreenZone("z0", 0.0, 0.0, 0.4, 1.0, label="sidebar"),
            ScreenZone("z1", 0.4, 0.0, 0.6, 1.0, label="main"),
        ]
        session = coord.create_session(
            SplitScreenLayout.CUSTOM, custom_zones=zones
        )
        assert session.manager.zone_count() == 2
        z = session.manager.get_zone("z1")
        assert z.label == "main"

    def test_custom_cursor_in_correct_zone(self):
        SplitScreenLayout, ScreenZone, _, _, _ = _get_classes()
        SplitScreenCoordinator, _, _ = _get_coordinator_classes()
        coord = SplitScreenCoordinator()
        zones = [ScreenZone("only", 0.0, 0.0, 1.0, 1.0, label="full")]
        session = coord.create_session(SplitScreenLayout.CUSTOM, custom_zones=zones)
        session.start()
        ctx = session.add_cursor("c0", "only")
        assert ctx.zone_id == "only"

    def test_custom_no_zones_raises(self):
        SplitScreenLayout, ScreenZone, _, _, _ = _get_classes()
        SplitScreenCoordinator, _, _ = _get_coordinator_classes()
        coord = SplitScreenCoordinator()
        with pytest.raises(ValueError):
            coord.create_session(SplitScreenLayout.CUSTOM, custom_zones=[])


# ===========================================================================
# Gap 10 — Thread safety
# ===========================================================================

class TestGap10_ThreadSafety:
    def test_concurrent_cursor_add(self):
        SplitScreenLayout, *_ = _get_classes()
        SplitScreenCoordinator, _, SessionState = _get_coordinator_classes()
        coord = SplitScreenCoordinator()
        session = coord.create_session(SplitScreenLayout.QUAD)
        session.start()

        errors = []

        def add_cursors(offset):
            try:
                for i in range(5):
                    session.add_cursor(f"c{offset}_{i}", "z0")
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=add_cursors, args=(t,)) for t in range(4)]
Multi-Cursor Split-Screen Tests — Murphy System

Verifies that every CursorContext is tested:
  1. Individually — each cursor's own state, movement, clicks, drag,
     scroll, history, zone clamping, and independence.
  2. As a whole — all cursors in a MultiCursorDesktop together, proving
     they are fully isolated from each other and that parallel dispatch works.

Also covers:
  - ScreenZone geometry helpers
  - SplitScreenLayout presets (SINGLE, DUAL_H, DUAL_V, TRIPLE_H, QUAD, HEXA, CUSTOM)
  - SplitScreenManager enqueue/run_all (serial + parallel)
  - SplitScreenCoordinator triage+evidence+dispatch pipeline
  - playback_runner multi-cursor state registry

Design Label: TEST-MULTICURSOR-001
Owner: QA Team
"""
from __future__ import annotations

import os
import sys
import threading
import uuid

import pytest

# Ensure src/ is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from murphy_native_automation import (
    ActionType,
    CursorContext,
    MultiCursorDesktop,
    NativeStep,
    NativeTask,
    ScreenZone,
    SplitScreenLayout,
    SplitScreenManager,
    TaskType,
)

# ============================================================
# Fixtures
# ============================================================

SCREEN_W = 1920
SCREEN_H = 1080


@pytest.fixture
def desktop():
    return MultiCursorDesktop(screen_width=SCREEN_W, screen_height=SCREEN_H)


@pytest.fixture
def dual_h_desktop():
    d = MultiCursorDesktop(screen_width=SCREEN_W, screen_height=SCREEN_H)
    d.apply_layout(SplitScreenLayout.DUAL_H)
    return d


@pytest.fixture
def quad_desktop():
    d = MultiCursorDesktop(screen_width=SCREEN_W, screen_height=SCREEN_H)
    d.apply_layout(SplitScreenLayout.QUAD)
    return d


@pytest.fixture
def zone():
    return ScreenZone(name="test", x=100, y=200, width=800, height=600, label="Test Zone")


@pytest.fixture
def cursor(zone):
    c = CursorContext(label="TestCursor")
    c.attach_zone(zone)
    return c


# ============================================================
# Part 1 — ScreenZone geometry
# ============================================================

class TestScreenZone:
    """ScreenZone coordinate helpers and properties."""

    def test_center(self):
        z = ScreenZone(x=0, y=0, width=100, height=80)
        assert z.center == (50, 40)

    def test_center_offset(self):
        z = ScreenZone(x=200, y=100, width=400, height=300)
        assert z.center == (400, 250)

    def test_bounds(self):
        z = ScreenZone(x=10, y=20, width=100, height=50)
        assert z.bounds == (10, 20, 110, 70)

    def test_contains_inside(self):
        z = ScreenZone(x=0, y=0, width=100, height=100)
        assert z.contains(50, 50)

    def test_contains_boundary(self):
        z = ScreenZone(x=0, y=0, width=100, height=100)
        assert z.contains(0, 0)
        assert not z.contains(100, 100)   # exclusive upper bound

    def test_contains_outside(self):
        z = ScreenZone(x=100, y=100, width=200, height=200)
        assert not z.contains(50, 50)

    def test_to_absolute(self):
        z = ScreenZone(x=0, y=0, width=1000, height=1000)
        assert z.to_absolute(0.5, 0.5) == (500, 500)

    def test_to_absolute_origin(self):
        z = ScreenZone(x=500, y=200, width=400, height=300)
        assert z.to_absolute(0.0, 0.0) == (500, 200)

    def test_to_relative(self):
        z = ScreenZone(x=0, y=0, width=1000, height=500)
        rel_x, rel_y = z.to_relative(500, 250)
        assert abs(rel_x - 0.5) < 0.001
        assert abs(rel_y - 0.5) < 0.001

    def test_to_dict(self):
        z = ScreenZone(name="a", x=1, y=2, width=3, height=4, label="L")
        d = z.to_dict()
        assert d["name"] == "a"
        assert d["width"] == 3

    def test_zone_id_unique(self):
        z1 = ScreenZone()
        z2 = ScreenZone()
        assert z1.zone_id != z2.zone_id


# ============================================================
# Part 2 — CursorContext individually
# ============================================================

class TestCursorContextIndividual:
    """Each cursor tested on its own — state, movement, actions, history."""

    def test_initial_position(self, zone):
        c = CursorContext()
        c.attach_zone(zone)
        # Should be at zone center after attach
        cx, cy = zone.center
        assert c.abs_x == cx
        assert c.abs_y == cy

    def test_warp_absolute(self, cursor, zone):
        cursor.warp(zone.x + 10, zone.y + 10)
        assert cursor.abs_x == zone.x + 10
        assert cursor.abs_y == zone.y + 10

    def test_warp_clamps_to_zone(self, cursor, zone):
        cursor.warp(zone.x - 100, zone.y - 100)
        assert cursor.abs_x == zone.x
        assert cursor.abs_y == zone.y

    def test_warp_clamps_upper(self, cursor, zone):
        cursor.warp(zone.x + zone.width + 500, zone.y + zone.height + 500)
        assert cursor.abs_x < zone.x + zone.width
        assert cursor.abs_y < zone.y + zone.height

    def test_move_by_delta(self, cursor, zone):
        cursor.warp(zone.x + 100, zone.y + 100)
        cursor.move_by(10, 20)
        assert cursor.abs_x == zone.x + 110
        assert cursor.abs_y == zone.y + 120

    def test_move_by_updates_velocity(self, cursor):
        cursor.move_by(5, -3)
        assert cursor.velocity_x == 5.0
        assert cursor.velocity_y == -3.0

    def test_rel_position_synced(self, cursor, zone):
        target_x = zone.x + zone.width // 4
        target_y = zone.y + zone.height // 4
        cursor.warp(target_x, target_y)
        assert 0.0 <= cursor.rel_x <= 1.0
        assert 0.0 <= cursor.rel_y <= 1.0

    def test_press_button(self, cursor):
        cursor.press_button("left")
        assert "left" in cursor.buttons_down

    def test_release_button(self, cursor):
        cursor.press_button("right")
        cursor.release_button("right")
        assert "right" not in cursor.buttons_down

    def test_click_returns_event(self, cursor, zone):
        ev = cursor.click("left")
        assert ev["event"] == "click"
        assert ev["button"] == "left"
        assert ev["cursor_id"] == cursor.cursor_id
        assert ev["zone_id"] == zone.zone_id

    def test_click_clears_button(self, cursor):
        ev = cursor.click("left")
        assert "left" not in cursor.buttons_down  # released after click

    def test_double_click_event(self, cursor):
        ev = cursor.double_click()
        assert ev["event"] == "double_click"

    def test_drag_updates_position(self, cursor, zone):
        cursor.warp(zone.x + 50, zone.y + 50)
        target_x = zone.x + 200
        target_y = zone.y + 200
        ev = cursor.drag(target_x, target_y)
        assert ev["event"] == "drag"
        assert cursor.abs_x == target_x
        assert cursor.abs_y == target_y

    def test_drag_records_from_to(self, cursor, zone):
        cursor.warp(zone.x + 10, zone.y + 10)
        ev = cursor.drag(zone.x + 100, zone.y + 100)
        assert ev["from"] == (zone.x + 10, zone.y + 10)
        assert ev["to"][0] == zone.x + 100

    def test_scroll_event(self, cursor, zone):
        ev = cursor.scroll(delta_x=0, delta_y=-120)
        assert ev["event"] == "scroll"
        assert ev["delta_y"] == -120
        assert ev["zone_id"] == zone.zone_id

    def test_position_snapshot(self, cursor, zone):
        pos = cursor.position()
        assert "cursor_id" in pos
        assert "abs_x" in pos
        assert "rel_x" in pos
        assert "zone_id" in pos
        assert pos["zone_id"] == zone.zone_id

    def test_history_recorded(self, cursor):
        cursor.click()
        cursor.move_by(5, 5)
        hist = cursor.get_history()
        events = [e["event"] for e in hist]
        assert "click" in events
        assert "move_by" in events

    def test_history_last_n(self, cursor):
        for _ in range(30):
            cursor.move_by(1, 1)
        hist = cursor.get_history(last_n=10)
        assert len(hist) <= 10

    def test_cursor_label(self, zone):
        c = CursorContext(label="Agent-007")
        c.attach_zone(zone)
        assert c.position()["label"] == "Agent-007"

    def test_cursor_id_unique(self):
        ids = {CursorContext().cursor_id for _ in range(50)}
        assert len(ids) == 50

    def test_no_zone_warp(self):
        c = CursorContext()
        c.warp(500, 400)   # no zone — should not clamp
        assert c.abs_x == 500
        assert c.abs_y == 400

    def test_is_active_default(self, cursor):
        assert cursor.is_active is True


# ============================================================
# Part 3 — All cursors together (MultiCursorDesktop)
# ============================================================

class TestAllCursorsTogether:
    """Verify all cursors in a MultiCursorDesktop are independent and correct."""

    def test_dual_h_two_cursors(self, dual_h_desktop):
        cursors = dual_h_desktop.list_cursors()
        assert len(cursors) == 2

    def test_dual_h_cursor_zones_distinct(self, dual_h_desktop):
        zones = dual_h_desktop.list_zones()
        zone_ids = [z.zone_id for z in zones]
        assert len(set(zone_ids)) == 2

    def test_quad_four_cursors(self, quad_desktop):
        assert len(quad_desktop.list_cursors()) == 4

    def test_each_cursor_in_own_zone(self, quad_desktop):
        zones = quad_desktop.list_zones()
        for zone in zones:
            cursor = quad_desktop.get_cursor(zone.zone_id)
            # Cursor should be at zone center
            cx, cy = zone.center
            assert cursor.abs_x == cx
            assert cursor.abs_y == cy

    def test_moving_one_cursor_does_not_affect_others(self, dual_h_desktop):
        zones = dual_h_desktop.list_zones()
        c0 = dual_h_desktop.get_cursor(zones[0].zone_id)
        c1 = dual_h_desktop.get_cursor(zones[1].zone_id)

        pos_c1_before = (c1.abs_x, c1.abs_y)
        c0.move_by(50, 50)
        pos_c1_after = (c1.abs_x, c1.abs_y)

        assert pos_c1_before == pos_c1_after, (
            "Moving cursor-0 must not affect cursor-1"
        )

    def test_clicking_one_cursor_does_not_affect_others(self, dual_h_desktop):
        zones = dual_h_desktop.list_zones()
        c0 = dual_h_desktop.get_cursor(zones[0].zone_id)
        c1 = dual_h_desktop.get_cursor(zones[1].zone_id)

        hist_before = len(c1.get_history())
        c0.click()
        hist_after = len(c1.get_history())
        assert hist_before == hist_after, (
            "Clicking cursor-0 must not add events to cursor-1's history"
        )

    def test_all_cursors_unique_ids(self, quad_desktop):
        ids = [c.cursor_id for c in quad_desktop.list_cursors()]
        assert len(ids) == len(set(ids))

    def test_dispatch_click_on_each_zone(self, quad_desktop):
        zones = quad_desktop.list_zones()
        for zone in zones:
            ev = quad_desktop.dispatch_click(zone.zone_id)
            assert ev["cursor_id"] is not None
            assert ev["zone_id"] == zone.zone_id

    def test_dispatch_move_on_each_zone(self, quad_desktop):
        zones = quad_desktop.list_zones()
        for zone in zones:
            pos = quad_desktop.dispatch_move(zone.zone_id, 0.25, 0.75)
            assert pos["zone_id"] == zone.zone_id
            assert 0.2 <= pos["rel_x"] <= 0.3
            assert 0.7 <= pos["rel_y"] <= 0.8

    def test_dispatch_drag_on_each_zone(self, quad_desktop):
        zones = quad_desktop.list_zones()
        for zone in zones:
            ev = quad_desktop.dispatch_drag(zone.zone_id, 0.1, 0.1, 0.9, 0.9)
            assert ev["event"] == "drag"

    def test_all_cursor_positions_snapshot(self, quad_desktop):
        snap = quad_desktop.snapshot()
        assert len(snap["cursors"]) == 4
        for pos in snap["cursors"]:
            assert "cursor_id" in pos
            assert "abs_x" in pos
            assert "zone_id" in pos

    def test_parallel_moves_thread_safe(self, quad_desktop):
        """All four cursors can be moved concurrently without corruption."""
        zones = quad_desktop.list_zones()
        errors = []

        def move_cursor(zone_id: str) -> None:
            try:
                c = quad_desktop.get_cursor(zone_id)
                for _ in range(20):
                    c.move_by(1, 1)
                    c.click()
            except Exception as exc:
                errors.append(str(exc))

        threads = [
            threading.Thread(target=move_cursor, args=(z.zone_id,))
            for z in zones
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors
        assert session.desktop.cursor_count() == 20

    def test_concurrent_session_create(self):
        SplitScreenLayout, *_ = _get_classes()
        SplitScreenCoordinator, _, _ = _get_coordinator_classes()
        coord = SplitScreenCoordinator()
        errors = []

        def create_session(i):
            try:
                coord.create_session(SplitScreenLayout.DUAL_V, session_id=f"s{i}")
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=create_session, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors
        assert coord.session_count() == 10

    def test_concurrent_zone_lookup(self):
        SplitScreenLayout, _, _, _, SplitScreenManager = _get_classes()
        manager = SplitScreenManager(SplitScreenLayout.HEXA)
        results = []

        def find_zone():
            for _ in range(50):
                z = manager.find_zone_at(0.5, 0.3)
                results.append(z is not None)

        threads = [threading.Thread(target=find_zone) for _ in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert all(results)

        assert not errors, f"Thread-safety errors: {errors}"

    def test_extra_cursor_per_zone(self, dual_h_desktop):
        zones = dual_h_desktop.list_zones()
        extra = dual_h_desktop.add_extra_cursor(zones[0].zone_id, label="Agent-2")
        assert extra.cursor_id in [c.cursor_id for c in dual_h_desktop.list_cursors()]

    def test_extra_cursor_independent(self, dual_h_desktop):
        zones = dual_h_desktop.list_zones()
        primary = dual_h_desktop.get_cursor(zones[0].zone_id)
        extra = dual_h_desktop.add_extra_cursor(zones[0].zone_id)
        primary.warp(zones[0].x + 10, zones[0].y + 10)
        # Extra cursor should NOT have moved
        assert extra.abs_x != primary.abs_x or extra.abs_y != primary.abs_y

    def test_apply_layout_resets_cursors(self, desktop):
        desktop.apply_layout(SplitScreenLayout.QUAD)
        assert len(desktop.list_cursors()) == 4
        desktop.apply_layout(SplitScreenLayout.DUAL_H)
        assert len(desktop.list_cursors()) == 2

    def test_parallel_task_dispatch(self, dual_h_desktop):
        """run_parallel_tasks with two tasks returns results for both zones."""
        zones = dual_h_desktop.list_zones()
        task_a = NativeTask(
            task_type=TaskType.VERIFY_API_CONNECTION,
            steps=[NativeStep(action=ActionType.API_GET, target="/api/health")],
        )
        task_b = NativeTask(
            task_type=TaskType.VERIFY_API_CONNECTION,
            steps=[NativeStep(action=ActionType.API_GET, target="/api/health")],
        )
        result = dual_h_desktop.run_parallel_tasks(
            {zones[0].zone_id: task_a, zones[1].zone_id: task_b}
        )
        assert "zone_results" in result
        assert len(result["zone_results"]) == 2
        assert result["layout"] == SplitScreenLayout.DUAL_H.value

    def test_max_cursors_guard(self, desktop):
        desktop.apply_layout(SplitScreenLayout.SINGLE)
        zones = desktop.list_zones()
        # Add cursors up to limit
        added = 0
        try:
            for _ in range(MultiCursorDesktop.MAX_CURSORS + 5):
                desktop.add_extra_cursor(zones[0].zone_id)
                added += 1
        except RuntimeError as exc:
            assert "limit" in str(exc).lower() or "Cursor limit" in str(exc)
        else:
            pytest.fail("Should have raised RuntimeError at MAX_CURSORS")


# ============================================================
# Part 4 — SplitScreenLayout presets
# ============================================================

class TestSplitScreenLayouts:
    """Every layout creates the correct number/position of zones."""

    @pytest.mark.parametrize("layout,expected_zones", [
        (SplitScreenLayout.SINGLE, 1),
        (SplitScreenLayout.DUAL_H, 2),
        (SplitScreenLayout.DUAL_V, 2),
        (SplitScreenLayout.TRIPLE_H, 3),
        (SplitScreenLayout.QUAD, 4),
        (SplitScreenLayout.HEXA, 6),
    ])
    def test_zone_count(self, layout, expected_zones, desktop):
        zones = desktop.apply_layout(layout)
        assert len(zones) == expected_zones

    def test_dual_h_zones_side_by_side(self, desktop):
        zones = desktop.apply_layout(SplitScreenLayout.DUAL_H)
        left, right = zones[0], zones[1]
        assert left.x == 0
        assert right.x == left.width    # right starts where left ends
        assert left.height == right.height == SCREEN_H

    def test_dual_v_zones_stacked(self, desktop):
        zones = desktop.apply_layout(SplitScreenLayout.DUAL_V)
        top, bottom = zones[0], zones[1]
        assert top.y == 0
        assert bottom.y == top.height
        assert top.width == bottom.width == SCREEN_W

    def test_quad_covers_full_screen(self, desktop):
        zones = desktop.apply_layout(SplitScreenLayout.QUAD)
        total_area = sum(z.width * z.height for z in zones)
        assert total_area == SCREEN_W * SCREEN_H

    def test_hexa_six_zones(self, desktop):
        zones = desktop.apply_layout(SplitScreenLayout.HEXA)
        assert len(zones) == 6

    def test_custom_layout(self, desktop):
        custom = [
            ScreenZone(name="a", x=0,    y=0, width=600,  height=1080),
            ScreenZone(name="b", x=600,  y=0, width=600,  height=1080),
            ScreenZone(name="c", x=1200, y=0, width=720,  height=1080),
        ]
        zones = desktop.apply_layout(SplitScreenLayout.CUSTOM, custom_zones=custom)
        assert len(zones) == 3
        assert zones[0].name == "a"

    def test_custom_too_many_zones_raises(self, desktop):
        oversized = [ScreenZone() for _ in range(MultiCursorDesktop.MAX_CURSORS + 1)]
        with pytest.raises(ValueError, match="Too many"):
            desktop.apply_layout(SplitScreenLayout.CUSTOM, custom_zones=oversized)

    def test_each_zone_gets_cursor(self, desktop):
        desktop.apply_layout(SplitScreenLayout.TRIPLE_H)
        zones = desktop.list_zones()
        cursors = desktop.list_cursors()
        assert len(zones) == len(cursors) == 3


# ============================================================
# Part 5 — SplitScreenManager
# ============================================================

class TestSplitScreenManager:
    """SplitScreenManager enqueue, run_zone, run_all."""

    @pytest.fixture
    def mgr(self):
        return SplitScreenManager(
            layout=SplitScreenLayout.DUAL_H,
            screen_width=SCREEN_W,
            screen_height=SCREEN_H,
        )

    def _health_task(self) -> NativeTask:
        return NativeTask(steps=[NativeStep(action=ActionType.API_GET, target="/api/health")])

    def test_zones_created(self, mgr):
        assert len(mgr.zones) == 2

    def test_enqueue_task(self, mgr):
        zone_id = mgr.zones[0].zone_id
        mgr.enqueue(zone_id, self._health_task())
        # No error = enqueue succeeded

    def test_enqueue_invalid_zone_raises(self, mgr):
        with pytest.raises(KeyError):
            mgr.enqueue("nonexistent_zone_id", self._health_task())

    def test_enqueue_to_all(self, mgr):
        mgr.enqueue_to_all(self._health_task())
        # Tasks enqueued to both zones — verified by run_all returning 2 zones

    def test_run_all_parallel(self, mgr):
        for zone in mgr.zones:
            mgr.enqueue(zone.zone_id, self._health_task())
        result = mgr.run_all(parallel=True)
        assert result["zone_count"] == 2
        assert "results" in result
        assert len(result["results"]) == 2

    def test_run_all_serial(self, mgr):
        for zone in mgr.zones:
            mgr.enqueue(zone.zone_id, self._health_task())
        result = mgr.run_all(parallel=False)
        assert result["zone_count"] == 2

    def test_run_zone_returns_list(self, mgr):
        zone_id = mgr.zones[0].zone_id
        mgr.enqueue(zone_id, self._health_task())
        results = mgr.run_zone(zone_id)
        assert isinstance(results, list)

    def test_summary_text(self, mgr):
        for zone in mgr.zones:
            mgr.enqueue(zone.zone_id, self._health_task())
        mgr.run_all()
        text = mgr.summary()
        assert isinstance(text, str)
        assert "tasks passed" in text

    def test_cursors_in_result(self, mgr):
        for zone in mgr.zones:
            mgr.enqueue(zone.zone_id, self._health_task())
        result = mgr.run_all()
        assert "cursors" in result
        assert len(result["cursors"]) == 2


# ============================================================
# Part 6 — SplitScreenCoordinator (Rubix + Triage + Dispatch)
# ============================================================

class TestSplitScreenCoordinator:
    """Coordinator pipeline: triage → evidence → dispatch for each zone."""

    @pytest.fixture
    def coord(self):
        from split_screen_coordinator import SplitScreenCoordinator
        return SplitScreenCoordinator(
            layout=SplitScreenLayout.DUAL_H,
            screen_width=SCREEN_W,
            screen_height=SCREEN_H,
        )

    def _task_with_desc(self, desc: str):
        return (
            NativeTask(steps=[NativeStep(action=ActionType.API_GET, target="/api/health")]),
            desc,
        )

    def test_coordinate_returns_report(self, coord):
        from split_screen_coordinator import CoordinationReport
        zones = coord.zones
        result = coord.coordinate({
            zones[0].zone_id: self._task_with_desc("API health check"),
            zones[1].zone_id: self._task_with_desc("System status check"),
        })
        assert isinstance(result, CoordinationReport)

    def test_report_has_all_zones(self, coord):
        zones = coord.zones
        result = coord.coordinate({
            zones[0].zone_id: self._task_with_desc("task alpha"),
            zones[1].zone_id: self._task_with_desc("task beta"),
        })
        assert len(result.zone_results) == 2

    def test_each_zone_has_triage(self, coord):
        zones = coord.zones
        result = coord.coordinate({
            zones[0].zone_id: self._task_with_desc("production outage"),
            zones[1].zone_id: self._task_with_desc("minor cosmetic fix"),
        })
        severities = {zr.triage_severity for zr in result.zone_results}
        assert all(s in ("critical", "high", "medium", "low", "unknown")
                   for s in severities)

    def test_each_zone_has_evidence_verdict(self, coord):
        zones = coord.zones
        result = coord.coordinate({
            zones[0].zone_id: self._task_with_desc("check health"),
            zones[1].zone_id: self._task_with_desc("verify status"),
        })
        for zr in result.zone_results:
            assert zr.evidence_verdict in ("pass", "fail", "inconclusive", "skipped")

    def test_all_zones_have_task_result(self, coord):
        zones = coord.zones
        result = coord.coordinate({
            z.zone_id: self._task_with_desc(f"task for {z.name}")
            for z in zones
        })
        for zr in result.zone_results:
            assert zr.task_result is not None
            assert "status" in zr.task_result

    def test_report_run_id_unique(self, coord):
        zones = coord.zones
        r1 = coord.coordinate({
            z.zone_id: self._task_with_desc("t") for z in zones
        })
        r2 = coord.coordinate({
            z.zone_id: self._task_with_desc("t") for z in zones
        })
        assert r1.run_id != r2.run_id

    def test_summary_contains_zone_names(self, coord):
        zones = coord.zones
        result = coord.coordinate({
            z.zone_id: self._task_with_desc("check") for z in zones
        })
        text = coord.summary(result)
        assert isinstance(text, str)
        assert len(text) > 0

    def test_get_status(self, coord):
        status = coord.get_status()
        assert "layout" in status
        assert "zone_count" in status
        assert status["zone_count"] == 2

    def test_history_recorded(self, coord):
        zones = coord.zones
        coord.coordinate({z.zone_id: self._task_with_desc("t") for z in zones})
        history = coord.get_history()
        assert len(history) >= 1
        assert "run_id" in history[-1]

    def test_strict_mode_skips_failing_zones(self):
        """In strict_mode, zones whose evidence fails are skipped."""
        from split_screen_coordinator import SplitScreenCoordinator
        coord = SplitScreenCoordinator(
            layout=SplitScreenLayout.DUAL_H,
            strict_mode=True,
        )
        # Monkeypatch evidence to always fail
        coord._evidence_check = lambda zone_id, conf: {
            "verdict": "fail", "score": 0.1, "artifact_id": None
        }
        zones = coord.zones
        result = coord.coordinate({
            z.zone_id: (
                NativeTask(steps=[NativeStep(action=ActionType.API_GET, target="/api/health")]),
                "test task",
            )
            for z in zones
        })
        for zr in result.zone_results:
            assert zr.flagged or zr.task_result.get("status") == "skipped"

    def test_quad_coordinator(self):
        from split_screen_coordinator import SplitScreenCoordinator
        coord = SplitScreenCoordinator(layout=SplitScreenLayout.QUAD)
        assert len(coord.zones) == 4
        result = coord.coordinate({
            z.zone_id: (
                NativeTask(steps=[NativeStep(action=ActionType.API_GET, target="/api/health")]),
                f"health check for {z.name}",
            )
            for z in coord.zones
        })
        assert len(result.zone_results) == 4
        assert result.zone_count == 4


# ============================================================
# Part 7 — playback_runner multi-cursor registry
# ============================================================

class TestPlaybackRunnerMultiCursor:
    """playback_runner.py cursor registry tested directly."""

    @pytest.fixture
    def runner_module(self):
        import importlib.util, os
        spec_path = os.path.abspath(os.path.join(
            os.path.dirname(__file__), "..",
            "bots", "ghost_controller_bot", "desktop", "playback_runner.py",
        ))
        spec = importlib.util.spec_from_file_location("playback_runner", spec_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_register_cursor(self, runner_module):
        runner_module.register_cursor("agent_a", x=100, y=200)
        pos = runner_module._cursor_pos("agent_a")
        assert pos == (100, 200)

    def test_cursor_move_updates_state(self, runner_module):
        runner_module._cursor_move("agent_b", 300, 400)
        assert runner_module._cursor_pos("agent_b") == (300, 400)

    def test_list_cursors_includes_registered(self, runner_module):
        runner_module.register_cursor("agent_c", x=0, y=0)
        cursors = runner_module.list_cursors()
        ids = [c["cursor_id"] for c in cursors]
        assert "agent_c" in ids

    def test_default_cursor_position(self, runner_module):
        pos = runner_module._cursor_pos("nonexistent_cursor")
        assert pos == (0, 0)   # default to (0,0) when not registered

    def test_click_updates_cursor_state(self, runner_module):
        runner_module.register_cursor("click_test", x=50, y=60)
        runner_module.click(x=150, y=170, cursor_id="click_test")
        # After click, position should update to click target
        pos = runner_module._cursor_pos("click_test")
        assert pos == (150, 170)

    def test_independent_cursors_do_not_interfere(self, runner_module):
        runner_module.register_cursor("p1", x=10, y=10)
        runner_module.register_cursor("p2", x=900, y=500)
        runner_module._cursor_move("p1", 20, 20)
        # p2 should be unchanged
        assert runner_module._cursor_pos("p2") == (900, 500)

    def test_multiple_cursors_in_list(self, runner_module):
        runner_module.register_cursor("multi_a", x=0, y=0)
        runner_module.register_cursor("multi_b", x=0, y=0)
        runner_module.register_cursor("multi_c", x=0, y=0)
        ids = {c["cursor_id"] for c in runner_module.list_cursors()}
        assert {"multi_a", "multi_b", "multi_c"}.issubset(ids)
