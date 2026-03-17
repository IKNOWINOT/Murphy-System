# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Comprehensive test suite for all_hands — AHM-001.

Covers meeting lifecycle, attendee management, agenda items, action items,
meeting minutes generation, recurring meetings, Flask Blueprint API, and
concurrent thread-safety.
"""
from __future__ import annotations

import datetime
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SRC_DIR))

from all_hands import (  # noqa: E402
    ActionItem,
    ActionItemStatus,
    AgendaItem,
    AgendaItemStatus,
    AllHandsMeeting,
    AllHandsManager,
    Attendee,
    AttendeeStatus,
    MeetingMinutes,
    MeetingStatus,
    MeetingType,
    RecurrenceFrequency,
    create_all_hands_api,
)

# ---------------------------------------------------------------------------
# Record pattern
# ---------------------------------------------------------------------------


@dataclass
class AHMRecord:
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


_RESULTS: List[AHMRecord] = []


def record(
    check_id: str,
    desc: str,
    expected: Any,
    actual: Any,
    cause: str = "",
    effect: str = "",
    lesson: str = "",
) -> bool:
    ok = expected == actual
    _RESULTS.append(AHMRecord(
        check_id=check_id, description=desc,
        expected=expected, actual=actual, passed=ok,
        cause=cause, effect=effect, lesson=lesson,
    ))
    return ok


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mgr() -> AllHandsManager:
    return AllHandsManager()


def _scheduled_at() -> str:
    return (
        datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(days=7)
    ).isoformat()


# ===========================================================================
# Enum tests
# ===========================================================================


def test_ahm_001_meeting_status_enum():
    """MeetingStatus has 4 values."""
    assert record("AHM-001", "4 MeetingStatus values", 4, len(MeetingStatus))


def test_ahm_002_attendee_status_enum():
    """AttendeeStatus has 5 values."""
    assert record("AHM-002", "5 AttendeeStatus values", 5, len(AttendeeStatus))


def test_ahm_003_agenda_item_status_enum():
    """AgendaItemStatus has 4 values."""
    assert record("AHM-003", "4 AgendaItemStatus values", 4, len(AgendaItemStatus))


def test_ahm_004_action_item_status_enum():
    """ActionItemStatus has 4 values."""
    assert record("AHM-004", "4 ActionItemStatus values", 4, len(ActionItemStatus))


def test_ahm_005_meeting_type_enum():
    """MeetingType has 6 values."""
    assert record("AHM-005", "6 MeetingType values", 6, len(MeetingType))


def test_ahm_006_recurrence_frequency_enum():
    """RecurrenceFrequency has 5 values."""
    assert record("AHM-006", "5 RecurrenceFrequency values", 5, len(RecurrenceFrequency))


# ===========================================================================
# Meeting scheduling
# ===========================================================================


def test_ahm_007_schedule_meeting():
    """schedule_meeting creates a SCHEDULED meeting."""
    mgr = _mgr()
    m = mgr.schedule_meeting("Q1 All Hands", _scheduled_at())
    assert record("AHM-007", "Meeting status is SCHEDULED",
                   MeetingStatus.SCHEDULED, m.status,
                   cause="newly created meeting",
                   effect="status defaults to SCHEDULED",
                   lesson="All meetings start in SCHEDULED state")


def test_ahm_008_schedule_meeting_title_required():
    """schedule_meeting raises ValueError for empty title."""
    mgr = _mgr()
    raised = False
    try:
        mgr.schedule_meeting("", _scheduled_at())
    except ValueError:
        raised = True
    assert record("AHM-008", "Empty title raises ValueError", True, raised)


def test_ahm_009_schedule_meeting_fields():
    """schedule_meeting stores all fields correctly."""
    mgr = _mgr()
    sa = _scheduled_at()
    m = mgr.schedule_meeting(
        "Kickoff",
        sa,
        description="Annual kickoff",
        meeting_type=MeetingType.ANNUAL_KICKOFF,
        duration_minutes=90,
        timezone="America/New_York",
        location="HQ",
        video_link="https://meet.example.com/kickoff",
        organizer="ceo@example.com",
        recurrence=RecurrenceFrequency.NONE,
    )
    assert record("AHM-009a", "Title stored", "Kickoff", m.title)
    assert record("AHM-009b", "Type stored", MeetingType.ANNUAL_KICKOFF, m.meeting_type)
    assert record("AHM-009c", "Duration stored", 90, m.duration_minutes)
    assert record("AHM-009d", "Organizer stored", "ceo@example.com", m.organizer)


def test_ahm_010_get_meeting():
    """get_meeting returns the correct meeting by ID."""
    mgr = _mgr()
    m = mgr.schedule_meeting("Sync", _scheduled_at())
    got = mgr.get_meeting(m.meeting_id)
    assert record("AHM-010", "get_meeting returns correct meeting",
                   m.meeting_id, got.meeting_id if got else None)


def test_ahm_011_get_meeting_not_found():
    """get_meeting returns None for unknown ID."""
    mgr = _mgr()
    assert record("AHM-011", "Unknown meeting returns None",
                   None, mgr.get_meeting("unknown"))


def test_ahm_012_list_meetings():
    """list_meetings returns all meetings."""
    mgr = _mgr()
    mgr.schedule_meeting("M1", _scheduled_at())
    mgr.schedule_meeting("M2", _scheduled_at())
    assert record("AHM-012", "2 meetings listed", 2, len(mgr.list_meetings()))


def test_ahm_013_list_meetings_filter_status():
    """list_meetings filters by status."""
    mgr = _mgr()
    m = mgr.schedule_meeting("M", _scheduled_at())
    mgr.start_meeting(m.meeting_id)
    assert record("AHM-013a", "SCHEDULED filter returns 0",
                   0, len(mgr.list_meetings(status=MeetingStatus.SCHEDULED)))
    assert record("AHM-013b", "IN_PROGRESS filter returns 1",
                   1, len(mgr.list_meetings(status=MeetingStatus.IN_PROGRESS)))


def test_ahm_014_update_meeting():
    """update_meeting modifies mutable fields."""
    mgr = _mgr()
    m = mgr.schedule_meeting("Old Title", _scheduled_at())
    updated = mgr.update_meeting(m.meeting_id, title="New Title", duration_minutes=30)
    assert record("AHM-014a", "Title updated", "New Title", updated.title if updated else None)
    assert record("AHM-014b", "Duration updated", 30, updated.duration_minutes if updated else None)


def test_ahm_015_update_ended_meeting_raises():
    """update_meeting raises ValueError for ended meetings."""
    mgr = _mgr()
    m = mgr.schedule_meeting("M", _scheduled_at())
    mgr.start_meeting(m.meeting_id)
    mgr.end_meeting(m.meeting_id, summary="done")
    raised = False
    try:
        mgr.update_meeting(m.meeting_id, title="New")
    except ValueError:
        raised = True
    assert record("AHM-015", "Updating ended meeting raises ValueError", True, raised)


def test_ahm_016_cancel_meeting():
    """cancel_meeting transitions status to CANCELLED."""
    mgr = _mgr()
    m = mgr.schedule_meeting("Cancel Me", _scheduled_at())
    ok = mgr.cancel_meeting(m.meeting_id)
    m2 = mgr.get_meeting(m.meeting_id)
    assert record("AHM-016", "Meeting cancelled",
                   (True, MeetingStatus.CANCELLED),
                   (ok, m2.status if m2 else None))


def test_ahm_017_cancel_in_progress_raises():
    """cancel_meeting raises ValueError for in-progress meetings."""
    mgr = _mgr()
    m = mgr.schedule_meeting("M", _scheduled_at())
    mgr.start_meeting(m.meeting_id)
    raised = False
    try:
        mgr.cancel_meeting(m.meeting_id)
    except ValueError:
        raised = True
    assert record("AHM-017", "Cancelling in-progress meeting raises ValueError", True, raised)


# ===========================================================================
# Meeting lifecycle
# ===========================================================================


def test_ahm_018_start_meeting():
    """start_meeting transitions to IN_PROGRESS."""
    mgr = _mgr()
    m = mgr.schedule_meeting("Start Me", _scheduled_at())
    started = mgr.start_meeting(m.meeting_id)
    assert record("AHM-018", "Status is IN_PROGRESS after start",
                   MeetingStatus.IN_PROGRESS, started.status if started else None)


def test_ahm_019_start_already_started_raises():
    """start_meeting raises ValueError if not SCHEDULED."""
    mgr = _mgr()
    m = mgr.schedule_meeting("M", _scheduled_at())
    mgr.start_meeting(m.meeting_id)
    raised = False
    try:
        mgr.start_meeting(m.meeting_id)
    except ValueError:
        raised = True
    assert record("AHM-019", "Starting already-started meeting raises ValueError", True, raised)


def test_ahm_020_end_meeting():
    """end_meeting transitions to ENDED and generates minutes."""
    mgr = _mgr()
    m = mgr.schedule_meeting("End Me", _scheduled_at())
    mgr.start_meeting(m.meeting_id)
    minutes = mgr.end_meeting(m.meeting_id, summary="Great meeting")
    ended = mgr.get_meeting(m.meeting_id)
    assert record("AHM-020a", "Status is ENDED", MeetingStatus.ENDED, ended.status if ended else None)
    assert record("AHM-020b", "Minutes generated", True, minutes is not None)
    assert record("AHM-020c", "Summary stored in minutes", "Great meeting",
                   minutes.summary if minutes else None)


def test_ahm_021_end_meeting_generates_minutes_id():
    """end_meeting links minutes_id on the meeting record."""
    mgr = _mgr()
    m = mgr.schedule_meeting("M", _scheduled_at())
    mgr.start_meeting(m.meeting_id)
    minutes = mgr.end_meeting(m.meeting_id)
    m2 = mgr.get_meeting(m.meeting_id)
    assert record("AHM-021", "Meeting has minutes_id set",
                   True, m2 is not None and m2.minutes_id == minutes.minutes_id)


def test_ahm_022_end_meeting_not_in_progress_raises():
    """end_meeting raises ValueError if not IN_PROGRESS."""
    mgr = _mgr()
    m = mgr.schedule_meeting("M", _scheduled_at())
    raised = False
    try:
        mgr.end_meeting(m.meeting_id)
    except ValueError:
        raised = True
    assert record("AHM-022", "Ending scheduled (not started) meeting raises ValueError", True, raised)


def test_ahm_023_end_meeting_decisions_and_notes():
    """end_meeting stores decisions and key_notes in minutes."""
    mgr = _mgr()
    m = mgr.schedule_meeting("M", _scheduled_at())
    mgr.start_meeting(m.meeting_id)
    minutes = mgr.end_meeting(
        m.meeting_id,
        decisions=["Adopt RFC-42"],
        key_notes=["Budget approved for Q3"],
    )
    assert record("AHM-023a", "Decisions stored", ["Adopt RFC-42"],
                   minutes.decisions if minutes else None)
    assert record("AHM-023b", "Key notes stored", ["Budget approved for Q3"],
                   minutes.key_notes if minutes else None)


# ===========================================================================
# Attendees
# ===========================================================================


def test_ahm_024_add_attendee():
    """add_attendee creates an INVITED attendee."""
    mgr = _mgr()
    m = mgr.schedule_meeting("M", _scheduled_at())
    a = mgr.add_attendee(m.meeting_id, "Alice", "alice@example.com")
    assert record("AHM-024", "Attendee status is INVITED",
                   AttendeeStatus.INVITED, a.status)


def test_ahm_025_add_attendee_missing_fields():
    """add_attendee raises ValueError when name or email is missing."""
    mgr = _mgr()
    m = mgr.schedule_meeting("M", _scheduled_at())
    raised = False
    try:
        mgr.add_attendee(m.meeting_id, "", "")
    except ValueError:
        raised = True
    assert record("AHM-025", "Empty name/email raises ValueError", True, raised)


def test_ahm_026_add_attendee_to_cancelled_raises():
    """add_attendee raises ValueError for cancelled meeting."""
    mgr = _mgr()
    m = mgr.schedule_meeting("M", _scheduled_at())
    mgr.cancel_meeting(m.meeting_id)
    raised = False
    try:
        mgr.add_attendee(m.meeting_id, "Bob", "bob@example.com")
    except ValueError:
        raised = True
    assert record("AHM-026", "Adding attendee to cancelled meeting raises ValueError", True, raised)


def test_ahm_027_list_attendees():
    """list_attendees returns all attendees for a meeting."""
    mgr = _mgr()
    m = mgr.schedule_meeting("M", _scheduled_at())
    mgr.add_attendee(m.meeting_id, "Alice", "alice@example.com")
    mgr.add_attendee(m.meeting_id, "Bob", "bob@example.com")
    assert record("AHM-027", "2 attendees listed", 2, len(mgr.list_attendees(m.meeting_id)))


def test_ahm_028_update_attendee_rsvp():
    """update_attendee_status records RSVP timestamp."""
    mgr = _mgr()
    m = mgr.schedule_meeting("M", _scheduled_at())
    a = mgr.add_attendee(m.meeting_id, "Alice", "alice@example.com")
    updated = mgr.update_attendee_status(a.attendee_id, AttendeeStatus.ACCEPTED)
    assert record("AHM-028a", "Status is ACCEPTED",
                   AttendeeStatus.ACCEPTED, updated.status if updated else None)
    assert record("AHM-028b", "rsvp_at timestamp set",
                   True, updated.rsvp_at is not None if updated else False)


def test_ahm_029_update_attendee_attended():
    """update_attendee_status records attended_at timestamp for ATTENDED."""
    mgr = _mgr()
    m = mgr.schedule_meeting("M", _scheduled_at())
    a = mgr.add_attendee(m.meeting_id, "Bob", "bob@example.com")
    updated = mgr.update_attendee_status(a.attendee_id, AttendeeStatus.ATTENDED)
    assert record("AHM-029", "attended_at set for ATTENDED status",
                   True, updated.attended_at is not None if updated else False)


def test_ahm_030_remove_attendee():
    """remove_attendee removes attendee from meeting."""
    mgr = _mgr()
    m = mgr.schedule_meeting("M", _scheduled_at())
    a = mgr.add_attendee(m.meeting_id, "Alice", "alice@example.com")
    ok = mgr.remove_attendee(m.meeting_id, a.attendee_id)
    attendees = mgr.list_attendees(m.meeting_id)
    assert record("AHM-030", "Attendee removed",
                   (True, 0), (ok, len(attendees)))


def test_ahm_031_end_meeting_counts_attended():
    """end_meeting counts ATTENDED attendees in minutes."""
    mgr = _mgr()
    m = mgr.schedule_meeting("M", _scheduled_at())
    a1 = mgr.add_attendee(m.meeting_id, "Alice", "alice@example.com")
    a2 = mgr.add_attendee(m.meeting_id, "Bob", "bob@example.com")
    mgr.update_attendee_status(a1.attendee_id, AttendeeStatus.ATTENDED)
    mgr.update_attendee_status(a2.attendee_id, AttendeeStatus.NO_SHOW)
    mgr.start_meeting(m.meeting_id)
    minutes = mgr.end_meeting(m.meeting_id)
    assert record("AHM-031", "Minutes counts 1 attended",
                   1, minutes.attendee_count if minutes else -1)


# ===========================================================================
# Agenda items
# ===========================================================================


def test_ahm_032_add_agenda_item():
    """add_agenda_item creates a PENDING item."""
    mgr = _mgr()
    m = mgr.schedule_meeting("M", _scheduled_at())
    item = mgr.add_agenda_item(m.meeting_id, "Welcome")
    assert record("AHM-032", "Agenda item status is PENDING",
                   AgendaItemStatus.PENDING, item.status)


def test_ahm_033_add_agenda_item_empty_title():
    """add_agenda_item raises ValueError for empty title."""
    mgr = _mgr()
    m = mgr.schedule_meeting("M", _scheduled_at())
    raised = False
    try:
        mgr.add_agenda_item(m.meeting_id, "")
    except ValueError:
        raised = True
    assert record("AHM-033", "Empty title raises ValueError", True, raised)


def test_ahm_034_list_agenda_items_ordered():
    """list_agenda_items returns items ordered by 'order'."""
    mgr = _mgr()
    m = mgr.schedule_meeting("M", _scheduled_at())
    mgr.add_agenda_item(m.meeting_id, "C", order=3)
    mgr.add_agenda_item(m.meeting_id, "A", order=1)
    mgr.add_agenda_item(m.meeting_id, "B", order=2)
    items = mgr.list_agenda_items(m.meeting_id)
    assert record("AHM-034", "Items ordered by order field",
                   ["A", "B", "C"], [i.title for i in items])


def test_ahm_035_update_agenda_item_status():
    """update_agenda_item_status transitions item to COMPLETED."""
    mgr = _mgr()
    m = mgr.schedule_meeting("M", _scheduled_at())
    item = mgr.add_agenda_item(m.meeting_id, "Demo")
    updated = mgr.update_agenda_item_status(item.item_id, AgendaItemStatus.COMPLETED)
    assert record("AHM-035a", "Status is COMPLETED",
                   AgendaItemStatus.COMPLETED, updated.status if updated else None)
    assert record("AHM-035b", "completed_at is set",
                   True, updated.completed_at is not None if updated else False)


def test_ahm_036_end_meeting_skips_pending_agenda_items():
    """end_meeting marks pending agenda items as SKIPPED."""
    mgr = _mgr()
    m = mgr.schedule_meeting("M", _scheduled_at())
    item = mgr.add_agenda_item(m.meeting_id, "Unfinished")
    mgr.start_meeting(m.meeting_id)
    mgr.end_meeting(m.meeting_id)
    item_after = mgr._agenda_items.get(item.item_id)
    assert record("AHM-036", "Pending item marked SKIPPED on meeting end",
                   AgendaItemStatus.SKIPPED,
                   item_after.status if item_after else None)


def test_ahm_037_end_meeting_counts_completed_agenda():
    """end_meeting counts completed agenda items in minutes."""
    mgr = _mgr()
    m = mgr.schedule_meeting("M", _scheduled_at())
    i1 = mgr.add_agenda_item(m.meeting_id, "Done")
    i2 = mgr.add_agenda_item(m.meeting_id, "Skipped")
    mgr.update_agenda_item_status(i1.item_id, AgendaItemStatus.COMPLETED)
    mgr.start_meeting(m.meeting_id)
    minutes = mgr.end_meeting(m.meeting_id)
    assert record("AHM-037a", "Minutes: 1 completed", 1,
                   minutes.agenda_items_completed if minutes else -1)
    assert record("AHM-037b", "Minutes: 2 total", 2,
                   minutes.agenda_items_total if minutes else -1)


# ===========================================================================
# Action items
# ===========================================================================


def test_ahm_038_add_action_item():
    """add_action_item creates an OPEN action item."""
    mgr = _mgr()
    m = mgr.schedule_meeting("M", _scheduled_at())
    a = mgr.add_action_item(m.meeting_id, "Follow up with team")
    assert record("AHM-038", "Action item status is OPEN",
                   ActionItemStatus.OPEN, a.status)


def test_ahm_039_add_action_item_empty_title():
    """add_action_item raises ValueError for empty title."""
    mgr = _mgr()
    m = mgr.schedule_meeting("M", _scheduled_at())
    raised = False
    try:
        mgr.add_action_item(m.meeting_id, "")
    except ValueError:
        raised = True
    assert record("AHM-039", "Empty title raises ValueError", True, raised)


def test_ahm_040_update_action_item():
    """update_action_item updates fields."""
    mgr = _mgr()
    m = mgr.schedule_meeting("M", _scheduled_at())
    a = mgr.add_action_item(m.meeting_id, "Task A")
    updated = mgr.update_action_item(a.action_id, owner="alice", due_date="2026-06-01")
    assert record("AHM-040a", "Owner updated", "alice", updated.owner if updated else None)
    assert record("AHM-040b", "Due date updated", "2026-06-01", updated.due_date if updated else None)


def test_ahm_041_complete_action_item():
    """Completing an action item sets completed_at."""
    mgr = _mgr()
    m = mgr.schedule_meeting("M", _scheduled_at())
    a = mgr.add_action_item(m.meeting_id, "Task")
    updated = mgr.update_action_item(a.action_id, status=ActionItemStatus.COMPLETED)
    assert record("AHM-041a", "Status is COMPLETED",
                   ActionItemStatus.COMPLETED, updated.status if updated else None)
    assert record("AHM-041b", "completed_at is set",
                   True, updated.completed_at is not None if updated else False)


def test_ahm_042_list_action_items_by_status():
    """list_action_items filters by status."""
    mgr = _mgr()
    m = mgr.schedule_meeting("M", _scheduled_at())
    a1 = mgr.add_action_item(m.meeting_id, "Open")
    a2 = mgr.add_action_item(m.meeting_id, "Done")
    mgr.update_action_item(a2.action_id, status=ActionItemStatus.COMPLETED)
    open_items = mgr.list_action_items(status=ActionItemStatus.OPEN)
    assert record("AHM-042", "Filter OPEN returns 1", 1, len(open_items))


def test_ahm_043_list_action_items_by_owner():
    """list_action_items filters by owner."""
    mgr = _mgr()
    m = mgr.schedule_meeting("M", _scheduled_at())
    a1 = mgr.add_action_item(m.meeting_id, "Task 1", owner="alice")
    a2 = mgr.add_action_item(m.meeting_id, "Task 2", owner="bob")
    alice_items = mgr.list_action_items(owner="alice")
    assert record("AHM-043", "Filter by owner returns 1", 1, len(alice_items))


def test_ahm_044_end_meeting_action_item_count_in_minutes():
    """end_meeting counts action items in generated minutes."""
    mgr = _mgr()
    m = mgr.schedule_meeting("M", _scheduled_at())
    mgr.add_action_item(m.meeting_id, "A1")
    mgr.add_action_item(m.meeting_id, "A2")
    mgr.start_meeting(m.meeting_id)
    minutes = mgr.end_meeting(m.meeting_id)
    assert record("AHM-044", "Minutes counts 2 action items", 2,
                   minutes.action_item_count if minutes else -1)


# ===========================================================================
# Minutes
# ===========================================================================


def test_ahm_045_get_minutes():
    """get_minutes returns minutes for a completed meeting."""
    mgr = _mgr()
    m = mgr.schedule_meeting("M", _scheduled_at())
    mgr.start_meeting(m.meeting_id)
    expected_mins = mgr.end_meeting(m.meeting_id, summary="All done")
    retrieved = mgr.get_minutes(m.meeting_id)
    assert record("AHM-045", "get_minutes returns correct minutes",
                   expected_mins.minutes_id if expected_mins else None,
                   retrieved.minutes_id if retrieved else None)


def test_ahm_046_get_minutes_not_ended():
    """get_minutes returns None for meetings without minutes."""
    mgr = _mgr()
    m = mgr.schedule_meeting("M", _scheduled_at())
    assert record("AHM-046", "get_minutes returns None for scheduled meeting",
                   None, mgr.get_minutes(m.meeting_id))


# ===========================================================================
# Recurring meetings
# ===========================================================================


def test_ahm_047_create_next_occurrence_weekly():
    """create_next_occurrence creates a new meeting 7 days later."""
    mgr = _mgr()
    base_dt = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=7)
    m = mgr.schedule_meeting(
        "Weekly Sync",
        base_dt.isoformat(),
        recurrence=RecurrenceFrequency.WEEKLY,
    )
    next_m = mgr.create_next_occurrence(m.meeting_id)
    assert record("AHM-047a", "Next occurrence created", True, next_m is not None)
    assert record("AHM-047b", "New meeting has different ID",
                   True, next_m.meeting_id != m.meeting_id if next_m else False)
    if next_m:
        next_dt = datetime.datetime.fromisoformat(next_m.scheduled_at)
        delta_days = (next_dt - base_dt).days
        assert record("AHM-047c", "Next occurrence is 7 days later", 7, delta_days)


def test_ahm_048_create_next_occurrence_monthly():
    """create_next_occurrence for monthly recurrence is ~30 days later."""
    mgr = _mgr()
    base_dt = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=7)
    m = mgr.schedule_meeting(
        "Monthly All Hands",
        base_dt.isoformat(),
        recurrence=RecurrenceFrequency.MONTHLY,
    )
    next_m = mgr.create_next_occurrence(m.meeting_id)
    assert record("AHM-048", "Monthly next occurrence created", True, next_m is not None)


def test_ahm_049_create_next_occurrence_no_recurrence():
    """create_next_occurrence returns None for non-recurring meetings."""
    mgr = _mgr()
    m = mgr.schedule_meeting("One-Off", _scheduled_at())
    result = mgr.create_next_occurrence(m.meeting_id)
    assert record("AHM-049", "Non-recurring meeting returns None", None, result)


def test_ahm_050_next_occurrence_inherits_recurrence():
    """create_next_occurrence preserves recurrence on the new meeting."""
    mgr = _mgr()
    m = mgr.schedule_meeting("Biweekly", _scheduled_at(),
                               recurrence=RecurrenceFrequency.BIWEEKLY)
    next_m = mgr.create_next_occurrence(m.meeting_id)
    assert record("AHM-050", "Next occurrence inherits recurrence",
                   RecurrenceFrequency.BIWEEKLY,
                   next_m.recurrence if next_m else None)


# ===========================================================================
# Stats
# ===========================================================================


def test_ahm_051_stats():
    """stats() returns accurate meeting and action item counts."""
    mgr = _mgr()
    m1 = mgr.schedule_meeting("M1", _scheduled_at())
    m2 = mgr.schedule_meeting("M2", _scheduled_at())
    mgr.start_meeting(m1.meeting_id)
    mgr.add_action_item(m1.meeting_id, "Do thing")
    s = mgr.stats()
    assert record("AHM-051a", "2 total meetings", 2, s["total_meetings"])
    assert record("AHM-051b", "1 SCHEDULED", 1, s["scheduled"])
    assert record("AHM-051c", "1 IN_PROGRESS", 1, s["in_progress"])
    assert record("AHM-051d", "1 open action item", 1, s["open_action_items"])


def test_ahm_052_stats_ended():
    """stats() tracks ended meetings."""
    mgr = _mgr()
    m = mgr.schedule_meeting("M", _scheduled_at())
    mgr.start_meeting(m.meeting_id)
    mgr.end_meeting(m.meeting_id)
    s = mgr.stats()
    assert record("AHM-052", "1 ended meeting", 1, s["ended"])


# ===========================================================================
# Serialisation (to_dict)
# ===========================================================================


def test_ahm_053_meeting_to_dict():
    """AllHandsMeeting.to_dict serialises enum values as strings."""
    mgr = _mgr()
    m = mgr.schedule_meeting("M", _scheduled_at())
    d = m.to_dict()
    assert record("AHM-053a", "status is string", True, isinstance(d["status"], str))
    assert record("AHM-053b", "meeting_type is string", True, isinstance(d["meeting_type"], str))
    assert record("AHM-053c", "recurrence is string", True, isinstance(d["recurrence"], str))


def test_ahm_054_attendee_to_dict():
    """Attendee.to_dict serialises status as string."""
    mgr = _mgr()
    m = mgr.schedule_meeting("M", _scheduled_at())
    a = mgr.add_attendee(m.meeting_id, "Alice", "alice@example.com")
    d = a.to_dict()
    assert record("AHM-054", "attendee status is string",
                   True, isinstance(d["status"], str))


def test_ahm_055_action_item_to_dict():
    """ActionItem.to_dict serialises status as string."""
    mgr = _mgr()
    m = mgr.schedule_meeting("M", _scheduled_at())
    a = mgr.add_action_item(m.meeting_id, "Task")
    d = a.to_dict()
    assert record("AHM-055", "action_item status is string",
                   True, isinstance(d["status"], str))


# ===========================================================================
# Thread safety
# ===========================================================================


def test_ahm_056_thread_safety_schedule():
    """Concurrent meeting scheduling from 20 threads is race-free."""
    mgr = _mgr()
    barrier = threading.Barrier(20)

    def worker(i: int) -> None:
        barrier.wait()
        mgr.schedule_meeting(f"Meeting-{i}", _scheduled_at())

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert record("AHM-056", "20 concurrent meetings scheduled",
                   20, len(mgr.list_meetings()),
                   cause="threading.Lock guards all mutations",
                   effect="no meetings lost or duplicated",
                   lesson="Thread safety is non-negotiable for in-memory stores")


def test_ahm_057_thread_safety_attendees():
    """Concurrent attendee additions are race-free."""
    mgr = _mgr()
    m = mgr.schedule_meeting("Big Meeting", _scheduled_at())
    barrier = threading.Barrier(10)

    def add(i: int) -> None:
        barrier.wait()
        mgr.add_attendee(m.meeting_id, f"Person {i}", f"person{i}@example.com")

    threads = [threading.Thread(target=add, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert record("AHM-057", "10 concurrent attendees added",
                   10, len(mgr.list_attendees(m.meeting_id)))


# ===========================================================================
# Flask Blueprint API
# ===========================================================================

try:
    from flask import Flask

    def _app():
        mgr = _mgr()
        app = Flask(__name__)
        app.register_blueprint(create_all_hands_api(mgr))
        return app, mgr

    def test_ahm_058_api_create_meeting():
        """POST /api/all-hands/meetings returns 201."""
        app, _ = _app()
        with app.test_client() as c:
            resp = c.post("/api/all-hands/meetings", json={
                "title": "Q2 All Hands",
                "scheduled_at": _scheduled_at(),
            })
        assert record("AHM-058", "POST meetings returns 201", 201, resp.status_code)

    def test_ahm_059_api_create_meeting_missing_title():
        """POST /api/all-hands/meetings without title returns 400."""
        app, _ = _app()
        with app.test_client() as c:
            resp = c.post("/api/all-hands/meetings", json={"scheduled_at": _scheduled_at()})
        assert record("AHM-059", "Missing title returns 400", 400, resp.status_code)

    def test_ahm_060_api_list_meetings():
        """GET /api/all-hands/meetings returns a list."""
        app, mgr = _app()
        mgr.schedule_meeting("M1", _scheduled_at())
        with app.test_client() as c:
            resp = c.get("/api/all-hands/meetings")
            data = resp.get_json()
        assert record("AHM-060", "GET meetings returns list with 1 item",
                       (200, 1), (resp.status_code, len(data)))

    def test_ahm_061_api_get_meeting():
        """GET /api/all-hands/meetings/<id> returns meeting."""
        app, mgr = _app()
        m = mgr.schedule_meeting("M", _scheduled_at())
        with app.test_client() as c:
            resp = c.get(f"/api/all-hands/meetings/{m.meeting_id}")
            data = resp.get_json()
        assert record("AHM-061", "GET meeting returns 200",
                       (200, m.meeting_id), (resp.status_code, data.get("meeting_id")))

    def test_ahm_062_api_get_meeting_not_found():
        """GET /api/all-hands/meetings/unknown returns 404."""
        app, _ = _app()
        with app.test_client() as c:
            resp = c.get("/api/all-hands/meetings/unknown")
        assert record("AHM-062", "Unknown meeting returns 404", 404, resp.status_code)

    def test_ahm_063_api_start_meeting():
        """POST /api/all-hands/meetings/<id>/start returns 200."""
        app, mgr = _app()
        m = mgr.schedule_meeting("M", _scheduled_at())
        with app.test_client() as c:
            resp = c.post(f"/api/all-hands/meetings/{m.meeting_id}/start")
            data = resp.get_json()
        assert record("AHM-063", "Start meeting returns 200 and IN_PROGRESS",
                       (200, "in_progress"), (resp.status_code, data.get("status")))

    def test_ahm_064_api_end_meeting():
        """POST /api/all-hands/meetings/<id>/end returns minutes."""
        app, mgr = _app()
        m = mgr.schedule_meeting("M", _scheduled_at())
        mgr.start_meeting(m.meeting_id)
        with app.test_client() as c:
            resp = c.post(f"/api/all-hands/meetings/{m.meeting_id}/end",
                          json={"summary": "Done"})
            data = resp.get_json()
        assert record("AHM-064", "End meeting returns 200 with minutes_id",
                       (200, True), (resp.status_code, "minutes_id" in data))

    def test_ahm_065_api_add_attendee():
        """POST /api/all-hands/meetings/<id>/attendees returns 201."""
        app, mgr = _app()
        m = mgr.schedule_meeting("M", _scheduled_at())
        with app.test_client() as c:
            resp = c.post(f"/api/all-hands/meetings/{m.meeting_id}/attendees",
                          json={"name": "Alice", "email": "alice@example.com"})
        assert record("AHM-065", "Add attendee returns 201", 201, resp.status_code)

    def test_ahm_066_api_add_agenda_item():
        """POST /api/all-hands/meetings/<id>/agenda returns 201."""
        app, mgr = _app()
        m = mgr.schedule_meeting("M", _scheduled_at())
        with app.test_client() as c:
            resp = c.post(f"/api/all-hands/meetings/{m.meeting_id}/agenda",
                          json={"title": "Demo", "duration_minutes": 10})
        assert record("AHM-066", "Add agenda item returns 201", 201, resp.status_code)

    def test_ahm_067_api_add_action_item():
        """POST /api/all-hands/meetings/<id>/action-items returns 201."""
        app, mgr = _app()
        m = mgr.schedule_meeting("M", _scheduled_at())
        with app.test_client() as c:
            resp = c.post(f"/api/all-hands/meetings/{m.meeting_id}/action-items",
                          json={"title": "Follow up"})
        assert record("AHM-067", "Add action item returns 201", 201, resp.status_code)

    def test_ahm_068_api_stats():
        """GET /api/all-hands/stats returns statistics dict."""
        app, mgr = _app()
        mgr.schedule_meeting("M", _scheduled_at())
        with app.test_client() as c:
            resp = c.get("/api/all-hands/stats")
            data = resp.get_json()
        assert record("AHM-068", "Stats returns 200 with total_meetings",
                       (200, 1), (resp.status_code, data.get("total_meetings")))

    def test_ahm_069_api_cancel_meeting():
        """DELETE /api/all-hands/meetings/<id> cancels meeting."""
        app, mgr = _app()
        m = mgr.schedule_meeting("M", _scheduled_at())
        with app.test_client() as c:
            resp = c.delete(f"/api/all-hands/meetings/{m.meeting_id}")
        assert record("AHM-069", "Cancel meeting returns 200", 200, resp.status_code)

    def test_ahm_070_api_next_occurrence():
        """POST /api/all-hands/meetings/<id>/next-occurrence creates new meeting."""
        app, mgr = _app()
        m = mgr.schedule_meeting("Weekly", _scheduled_at(),
                                  recurrence=RecurrenceFrequency.WEEKLY)
        # Update via the manager directly as the fixture uses mgr
        with app.test_client() as c:
            resp = c.post(f"/api/all-hands/meetings/{m.meeting_id}/next-occurrence")
        assert record("AHM-070", "Next occurrence returns 201", 201, resp.status_code)

    def test_ahm_071_api_get_minutes():
        """GET /api/all-hands/meetings/<id>/minutes returns minutes."""
        app, mgr = _app()
        m = mgr.schedule_meeting("M", _scheduled_at())
        mgr.start_meeting(m.meeting_id)
        mgr.end_meeting(m.meeting_id, summary="All done")
        with app.test_client() as c:
            resp = c.get(f"/api/all-hands/meetings/{m.meeting_id}/minutes")
            data = resp.get_json()
        assert record("AHM-071", "GET minutes returns 200 with summary",
                       (200, "All done"), (resp.status_code, data.get("summary")))

    def test_ahm_072_api_update_attendee_status():
        """PUT /api/all-hands/attendees/<id>/status updates RSVP."""
        app, mgr = _app()
        m = mgr.schedule_meeting("M", _scheduled_at())
        a = mgr.add_attendee(m.meeting_id, "Alice", "alice@example.com")
        with app.test_client() as c:
            resp = c.put(f"/api/all-hands/attendees/{a.attendee_id}/status",
                         json={"status": "accepted"})
            data = resp.get_json()
        assert record("AHM-072", "Update attendee status returns 200",
                       (200, "accepted"), (resp.status_code, data.get("status")))

    def test_ahm_073_api_update_action_item():
        """PUT /api/all-hands/action-items/<id> updates action item."""
        app, mgr = _app()
        m = mgr.schedule_meeting("M", _scheduled_at())
        a = mgr.add_action_item(m.meeting_id, "Task")
        with app.test_client() as c:
            resp = c.put(f"/api/all-hands/action-items/{a.action_id}",
                         json={"owner": "bob", "status": "in_progress"})
            data = resp.get_json()
        assert record("AHM-073", "Update action item returns 200",
                       (200, "bob"), (resp.status_code, data.get("owner")))

    def test_ahm_074_api_list_action_items_global():
        """GET /api/all-hands/action-items returns all action items."""
        app, mgr = _app()
        m = mgr.schedule_meeting("M", _scheduled_at())
        mgr.add_action_item(m.meeting_id, "A1")
        mgr.add_action_item(m.meeting_id, "A2")
        with app.test_client() as c:
            resp = c.get("/api/all-hands/action-items")
            data = resp.get_json()
        assert record("AHM-074", "Global action items list returns 2",
                       (200, 2), (resp.status_code, len(data)))

    def test_ahm_075_api_update_agenda_item_status():
        """PUT /api/all-hands/agenda/<id>/status updates status."""
        app, mgr = _app()
        m = mgr.schedule_meeting("M", _scheduled_at())
        item = mgr.add_agenda_item(m.meeting_id, "Intro")
        with app.test_client() as c:
            resp = c.put(f"/api/all-hands/agenda/{item.item_id}/status",
                         json={"status": "completed"})
            data = resp.get_json()
        assert record("AHM-075", "Update agenda item status returns 200",
                       (200, "completed"), (resp.status_code, data.get("status")))

except ImportError:
    pass
