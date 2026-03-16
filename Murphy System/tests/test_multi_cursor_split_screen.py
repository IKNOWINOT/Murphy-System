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
