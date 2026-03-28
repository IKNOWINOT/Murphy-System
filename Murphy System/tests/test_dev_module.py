"""Tests for Phase 9 – Dev Module."""

import sys, os

import pytest
from dev_module.models import (
    Bug, BugSeverity, BugStatus, BugPriority, GitActivity,
    Release, ReleaseStatus, RoadmapItem, RoadmapItemStatus,
    Sprint, SprintItem, SprintStatus,
)
from dev_module.dev_manager import DevManager


class TestModels:
    def test_sprint_to_dict(self):
        s = Sprint(name="S1", board_id="b1")
        d = s.to_dict()
        assert d["name"] == "S1"
        assert d["status"] == "planning"

    def test_sprint_velocity(self):
        s = Sprint(status=SprintStatus.COMPLETED, items=[
            SprintItem(story_points=5, completed=True),
            SprintItem(story_points=3, completed=False),
        ])
        assert s.velocity == 5
        assert s.total_points == 8
        assert s.completed_points == 5

    def test_bug_to_dict(self):
        b = Bug(title="Crash", severity=BugSeverity.CRITICAL)
        d = b.to_dict()
        assert d["severity"] == "critical"

    def test_release_to_dict(self):
        r = Release(version="1.0.0", name="Launch")
        d = r.to_dict()
        assert d["version"] == "1.0.0"

    def test_git_activity_to_dict(self):
        a = GitActivity(event_type="commit", author="alice")
        assert a.to_dict()["event_type"] == "commit"

    def test_roadmap_item_to_dict(self):
        i = RoadmapItem(title="Feature X", quarter="Q2")
        assert i.to_dict()["quarter"] == "Q2"


class TestDevManager:
    def test_create_sprint(self):
        mgr = DevManager()
        s = mgr.create_sprint("S1", "b1", start_date="2025-01-01")
        assert s.name == "S1"
        assert mgr.get_sprint(s.id) is s

    def test_list_sprints(self):
        mgr = DevManager()
        mgr.create_sprint("S1", "b1")
        mgr.create_sprint("S2", "b2")
        assert len(mgr.list_sprints()) == 2
        assert len(mgr.list_sprints("b1")) == 1

    def test_start_and_complete_sprint(self):
        mgr = DevManager()
        s = mgr.create_sprint("S1", "b1")
        mgr.start_sprint(s.id)
        assert s.status == SprintStatus.ACTIVE
        mgr.complete_sprint(s.id)
        assert s.status == SprintStatus.COMPLETED

    def test_add_sprint_item(self):
        mgr = DevManager()
        s = mgr.create_sprint("S1", "b1")
        si = mgr.add_sprint_item(s.id, "item1", 5)
        assert si.story_points == 5
        assert len(s.items) == 1

    def test_complete_sprint_item(self):
        mgr = DevManager()
        s = mgr.create_sprint("S1", "b1")
        mgr.add_sprint_item(s.id, "item1", 3)
        assert mgr.complete_sprint_item(s.id, "item1")
        assert not mgr.complete_sprint_item(s.id, "nonexistent")

    def test_velocity_history(self):
        mgr = DevManager()
        s = mgr.create_sprint("S1", "b1")
        mgr.add_sprint_item(s.id, "i1", 5)
        mgr.complete_sprint_item(s.id, "i1")
        mgr.complete_sprint(s.id)
        hist = mgr.velocity_history("b1")
        assert len(hist) == 1
        assert hist[0]["velocity"] == 5

    def test_burndown(self):
        mgr = DevManager()
        s = mgr.create_sprint("S1", "b1")
        mgr.add_sprint_item(s.id, "i1", 5)
        mgr.add_sprint_item(s.id, "i2", 3)
        mgr.complete_sprint_item(s.id, "i1")
        bd = mgr.burndown(s.id)
        assert bd["total_points"] == 8
        assert bd["completed_points"] == 5
        assert bd["remaining_points"] == 3

    def test_create_bug(self):
        mgr = DevManager()
        b = mgr.create_bug("Crash", board_id="b1", severity=BugSeverity.HIGH)
        assert b.severity == BugSeverity.HIGH
        assert mgr.get_bug(b.id) is b

    def test_list_bugs(self):
        mgr = DevManager()
        mgr.create_bug("A", board_id="b1", severity=BugSeverity.HIGH)
        mgr.create_bug("B", board_id="b1", severity=BugSeverity.LOW)
        mgr.create_bug("C", board_id="b2")
        assert len(mgr.list_bugs(board_id="b1")) == 2
        assert len(mgr.list_bugs(severity=BugSeverity.HIGH)) == 1

    def test_resolve_and_close_bug(self):
        mgr = DevManager()
        b = mgr.create_bug("X")
        mgr.resolve_bug(b.id)
        assert b.status == BugStatus.RESOLVED
        assert b.resolved_at != ""
        mgr.close_bug(b.id)
        assert b.status == BugStatus.CLOSED

    def test_create_release(self):
        mgr = DevManager()
        r = mgr.create_release("1.0.0", "Launch")
        assert r.version == "1.0.0"
        assert mgr.get_release(r.id) is r

    def test_release_checklist(self):
        mgr = DevManager()
        r = mgr.create_release("1.0.0")
        ci = mgr.add_checklist_item(r.id, "Run tests")
        assert mgr.check_checklist_item(r.id, ci.id)
        assert r.checklist[0].checked

    def test_publish_release(self):
        mgr = DevManager()
        r = mgr.create_release("1.0.0")
        mgr.publish_release(r.id)
        assert r.status == ReleaseStatus.RELEASED
        assert r.released_at != ""

    def test_git_activity(self):
        mgr = DevManager()
        a = mgr.log_git_activity("b1", "commit", author="alice", message="Fix bug")
        feed = mgr.git_feed("b1")
        assert len(feed) == 1
        assert feed[0].author == "alice"

    def test_roadmap_crud(self):
        mgr = DevManager()
        i = mgr.create_roadmap_item("Feature X", quarter="Q2")
        assert i.quarter == "Q2"
        assert len(mgr.list_roadmap("Q2")) == 1
        mgr.update_roadmap_item(i.id, status=RoadmapItemStatus.IN_PROGRESS)
        assert i.status == RoadmapItemStatus.IN_PROGRESS

    def test_sprint_not_found(self):
        mgr = DevManager()
        with pytest.raises(KeyError):
            mgr.start_sprint("bad")

    def test_bug_not_found(self):
        mgr = DevManager()
        with pytest.raises(KeyError):
            mgr.resolve_bug("bad")


class TestAPIRouter:
    def test_create_router(self):
        from dev_module.api import create_dev_router
        router = create_dev_router()
        assert router is not None
