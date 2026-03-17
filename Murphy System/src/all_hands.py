# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""All-Hands Meeting Management System — AHM-001

Owner: Platform Engineering · Dep: thread_safe_operations (capped_append)

Full-lifecycle All-Hands meeting management for the Murphy System:

- Schedule company-wide or team all-hands meetings (one-off and recurring)
- Manage attendee lists with RSVP and attendance recording
- Agenda management — items, presenters, time allocations, status
- Meeting execution lifecycle: scheduled → started → ended
- Auto-generate meeting minutes capturing decisions, notes, and action items
- Action item tracking — owner assignment, due dates, status updates
- Flask Blueprint factory ``create_all_hands_api(manager)`` for REST API

Design:
- Thread-safe via ``threading.Lock`` (consistent with Murphy System patterns)
- In-memory storage using ``Dict`` stores with ``capped_append`` list bounding
- All IDs are UUID4 hex strings
- Timestamps are ISO-8601 UTC strings

Classes: ``MeetingStatus``, ``AttendeeStatus``, ``AgendaItemStatus``,
``ActionItemStatus``, ``MeetingType``, ``RecurrenceFrequency`` (enums),
``AllHandsMeeting``, ``Attendee``, ``AgendaItem``, ``ActionItem``,
``MeetingMinutes`` (dataclasses), ``AllHandsManager`` (orchestrator).
``create_all_hands_api(manager)`` returns a Flask Blueprint.
"""
from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

try:
    from flask import Blueprint, jsonify, request
    _HAS_FLASK = True
except ImportError:
    _HAS_FLASK = False

    class _StubBlueprint:
        """No-op Blueprint stand-in when Flask is absent."""
        def __init__(self, *a: Any, **kw: Any) -> None: ...
        def route(self, *a: Any, **kw: Any) -> Any: return lambda fn: fn

    Blueprint = _StubBlueprint  # type: ignore[misc,assignment]

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

try:
    from .blueprint_auth import require_blueprint_auth
except ImportError:
    try:
        from blueprint_auth import require_blueprint_auth
    except ImportError:
        def require_blueprint_auth(bp: Any) -> None:  # type: ignore[misc]
            pass

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class MeetingStatus(str, Enum):
    """Lifecycle status of an all-hands meeting."""
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    ENDED = "ended"
    CANCELLED = "cancelled"


class AttendeeStatus(str, Enum):
    """RSVP / attendance status of a meeting attendee."""
    INVITED = "invited"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    ATTENDED = "attended"
    NO_SHOW = "no_show"


class AgendaItemStatus(str, Enum):
    """Execution status of an agenda item during a meeting."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"


class ActionItemStatus(str, Enum):
    """Lifecycle status of a post-meeting action item."""
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class MeetingType(str, Enum):
    """Classification of an all-hands meeting."""
    ALL_HANDS = "all_hands"
    TOWN_HALL = "town_hall"
    TEAM_SYNC = "team_sync"
    QUARTERLY_REVIEW = "quarterly_review"
    ANNUAL_KICKOFF = "annual_kickoff"
    EMERGENCY = "emergency"


class RecurrenceFrequency(str, Enum):
    """Recurrence frequency for scheduled meetings."""
    NONE = "none"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class Attendee:
    """A meeting attendee with RSVP and attendance tracking."""
    attendee_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    meeting_id: str = ""
    name: str = ""
    email: str = ""
    role: str = "attendee"
    status: AttendeeStatus = AttendeeStatus.INVITED
    rsvp_at: Optional[str] = None
    attended_at: Optional[str] = None
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d


@dataclass
class AgendaItem:
    """A single agenda item for an all-hands meeting."""
    item_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    meeting_id: str = ""
    title: str = ""
    description: str = ""
    presenter: str = ""
    duration_minutes: int = 5
    order: int = 0
    status: AgendaItemStatus = AgendaItemStatus.PENDING
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d


@dataclass
class ActionItem:
    """A follow-up action item generated from a meeting."""
    action_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    meeting_id: str = ""
    title: str = ""
    description: str = ""
    owner: str = ""
    due_date: Optional[str] = None
    status: ActionItemStatus = ActionItemStatus.OPEN
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: Optional[str] = None
    agenda_item_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d


@dataclass
class MeetingMinutes:
    """Auto-generated minutes for a completed all-hands meeting."""
    minutes_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    meeting_id: str = ""
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    summary: str = ""
    decisions: List[str] = field(default_factory=list)
    key_notes: List[str] = field(default_factory=list)
    attendee_count: int = 0
    action_item_count: int = 0
    agenda_items_completed: int = 0
    agenda_items_total: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AllHandsMeeting:
    """An all-hands meeting record."""
    meeting_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    title: str = ""
    description: str = ""
    meeting_type: MeetingType = MeetingType.ALL_HANDS
    status: MeetingStatus = MeetingStatus.SCHEDULED
    scheduled_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    timezone: str = "UTC"
    duration_minutes: int = 60
    location: str = ""
    video_link: str = ""
    organizer: str = ""
    recurrence: RecurrenceFrequency = RecurrenceFrequency.NONE
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    # Linked IDs — populated by AllHandsManager
    attendee_ids: List[str] = field(default_factory=list)
    agenda_item_ids: List[str] = field(default_factory=list)
    action_item_ids: List[str] = field(default_factory=list)
    minutes_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["meeting_type"] = self.meeting_type.value
        d["status"] = self.status.value
        d["recurrence"] = self.recurrence.value
        return d


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------

_MAX_MEETINGS = 10_000
_MAX_ATTENDEES = 100_000
_MAX_AGENDA_ITEMS = 100_000
_MAX_ACTION_ITEMS = 100_000


def _advance_by_frequency(base_dt: datetime, freq: RecurrenceFrequency) -> datetime:
    """Return a new ``datetime`` advanced by the given recurrence frequency.

    Uses calendar-accurate month arithmetic (no fixed 30/91-day drift):
    - ``WEEKLY`` → +7 days
    - ``BIWEEKLY`` → +14 days
    - ``MONTHLY`` → +1 calendar month (day clamped to last day of month)
    - ``QUARTERLY`` → +3 calendar months (day clamped to last day of month)

    Args:
        base_dt: The base datetime to advance from.
        freq:    The recurrence frequency.

    Returns:
        A new timezone-aware ``datetime`` object.
    """
    import calendar as _calendar

    if freq == RecurrenceFrequency.WEEKLY:
        return base_dt + timedelta(days=7)
    if freq == RecurrenceFrequency.BIWEEKLY:
        return base_dt + timedelta(days=14)

    months = 1 if freq == RecurrenceFrequency.MONTHLY else 3
    total_months = base_dt.month - 1 + months
    new_year = base_dt.year + total_months // 12
    new_month = total_months % 12 + 1
    # Clamp day to the last valid day of the target month (e.g., Jan 31 → Feb 28)
    max_day = _calendar.monthrange(new_year, new_month)[1]
    new_day = min(base_dt.day, max_day)
    return base_dt.replace(year=new_year, month=new_month, day=new_day)


class AllHandsManager:
    """Thread-safe All-Hands meeting lifecycle manager.

    Provides full CRUD for meetings, attendees, agenda items, and action
    items.  Auto-generates ``MeetingMinutes`` when a meeting is ended.

    All public methods are safe to call concurrently.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._meetings: Dict[str, AllHandsMeeting] = {}
        self._attendees: Dict[str, Attendee] = {}
        self._agenda_items: Dict[str, AgendaItem] = {}
        self._action_items: Dict[str, ActionItem] = {}
        self._minutes: Dict[str, MeetingMinutes] = {}

    # -- Meetings ------------------------------------------------------------

    def schedule_meeting(
        self,
        title: str,
        scheduled_at: str,
        *,
        description: str = "",
        meeting_type: MeetingType = MeetingType.ALL_HANDS,
        duration_minutes: int = 60,
        timezone: str = "UTC",
        location: str = "",
        video_link: str = "",
        organizer: str = "",
        recurrence: RecurrenceFrequency = RecurrenceFrequency.NONE,
    ) -> AllHandsMeeting:
        """Create and schedule a new all-hands meeting.

        Args:
            title:            Human-readable meeting title.
            scheduled_at:     ISO-8601 UTC string for the planned start time.
            description:      Optional description / agenda overview.
            meeting_type:     Classification (default: ALL_HANDS).
            duration_minutes: Expected duration in minutes (default: 60).
            timezone:         Display timezone label (default: "UTC").
            location:         Physical or virtual location description.
            video_link:       URL for the video-call link.
            organizer:        Name or ID of the meeting organizer.
            recurrence:       Recurrence frequency (default: NONE).

        Returns:
            The created ``AllHandsMeeting``.

        Raises:
            ValueError: if *title* is empty or *scheduled_at* is blank.
        """
        if not title or not title.strip():
            raise ValueError("Meeting title must not be empty")
        if not scheduled_at:
            raise ValueError("scheduled_at must be a non-empty ISO-8601 string")

        with self._lock:
            if len(self._meetings) >= _MAX_MEETINGS:
                raise ValueError("Maximum meeting limit reached")

        meeting = AllHandsMeeting(
            title=title.strip(),
            description=description,
            meeting_type=meeting_type,
            scheduled_at=scheduled_at,
            timezone=timezone,
            duration_minutes=max(1, duration_minutes),
            location=location,
            video_link=video_link,
            organizer=organizer,
            recurrence=recurrence,
        )

        with self._lock:
            self._meetings[meeting.meeting_id] = meeting

        logger.info("Meeting scheduled: %s (%s)", meeting.meeting_id, title)
        return meeting

    def get_meeting(self, meeting_id: str) -> Optional[AllHandsMeeting]:
        """Retrieve a meeting by ID."""
        with self._lock:
            return self._meetings.get(meeting_id)

    def list_meetings(
        self,
        status: Optional[MeetingStatus] = None,
        meeting_type: Optional[MeetingType] = None,
    ) -> List[AllHandsMeeting]:
        """List meetings, optionally filtered by status and/or type."""
        with self._lock:
            meetings = list(self._meetings.values())
        if status is not None:
            meetings = [m for m in meetings if m.status == status]
        if meeting_type is not None:
            meetings = [m for m in meetings if m.meeting_type == meeting_type]
        return meetings

    def update_meeting(
        self,
        meeting_id: str,
        *,
        title: Optional[str] = None,
        description: Optional[str] = None,
        scheduled_at: Optional[str] = None,
        duration_minutes: Optional[int] = None,
        location: Optional[str] = None,
        video_link: Optional[str] = None,
        organizer: Optional[str] = None,
        recurrence: Optional[RecurrenceFrequency] = None,
    ) -> Optional[AllHandsMeeting]:
        """Update mutable fields on a scheduled or in-progress meeting.

        Returns the updated meeting, or ``None`` if not found.
        Raises ``ValueError`` if the meeting has ended or been cancelled.
        """
        with self._lock:
            meeting = self._meetings.get(meeting_id)
        if meeting is None:
            return None
        if meeting.status in (MeetingStatus.ENDED, MeetingStatus.CANCELLED):
            raise ValueError(
                f"Cannot update meeting {meeting_id} with status {meeting.status.value}"
            )

        if title is not None:
            meeting.title = title.strip()
        if description is not None:
            meeting.description = description
        if scheduled_at is not None:
            meeting.scheduled_at = scheduled_at
        if duration_minutes is not None:
            meeting.duration_minutes = max(1, duration_minutes)
        if location is not None:
            meeting.location = location
        if video_link is not None:
            meeting.video_link = video_link
        if organizer is not None:
            meeting.organizer = organizer
        if recurrence is not None:
            meeting.recurrence = recurrence

        meeting.updated_at = datetime.now(timezone.utc).isoformat()
        return meeting

    def cancel_meeting(self, meeting_id: str) -> bool:
        """Cancel a scheduled meeting.

        Returns ``True`` if cancelled, ``False`` if not found.
        Raises ``ValueError`` if the meeting is already in progress or ended.
        """
        with self._lock:
            meeting = self._meetings.get(meeting_id)
        if meeting is None:
            return False
        if meeting.status == MeetingStatus.IN_PROGRESS:
            raise ValueError("Cannot cancel a meeting that is already in progress")
        if meeting.status == MeetingStatus.ENDED:
            raise ValueError("Cannot cancel a meeting that has already ended")
        meeting.status = MeetingStatus.CANCELLED
        meeting.updated_at = datetime.now(timezone.utc).isoformat()
        logger.info("Meeting cancelled: %s", meeting_id)
        return True

    def start_meeting(self, meeting_id: str) -> Optional[AllHandsMeeting]:
        """Transition a meeting from SCHEDULED to IN_PROGRESS.

        Returns the updated meeting, or ``None`` if not found.
        Raises ``ValueError`` if the meeting cannot be started.
        """
        with self._lock:
            meeting = self._meetings.get(meeting_id)
        if meeting is None:
            return None
        if meeting.status != MeetingStatus.SCHEDULED:
            raise ValueError(
                f"Only SCHEDULED meetings can be started (current: {meeting.status.value})"
            )
        meeting.status = MeetingStatus.IN_PROGRESS
        meeting.started_at = datetime.now(timezone.utc).isoformat()
        meeting.updated_at = meeting.started_at
        logger.info("Meeting started: %s", meeting_id)
        return meeting

    def end_meeting(
        self,
        meeting_id: str,
        summary: str = "",
        decisions: Optional[List[str]] = None,
        key_notes: Optional[List[str]] = None,
    ) -> Optional[MeetingMinutes]:
        """End an in-progress meeting and auto-generate meeting minutes.

        Args:
            meeting_id: ID of the meeting to end.
            summary:    Executive summary for the minutes.
            decisions:  List of decisions made during the meeting.
            key_notes:  List of key discussion notes.

        Returns:
            The generated ``MeetingMinutes``, or ``None`` if meeting not found.
        Raises:
            ValueError: if the meeting is not IN_PROGRESS.
        """
        with self._lock:
            meeting = self._meetings.get(meeting_id)
        if meeting is None:
            return None
        if meeting.status != MeetingStatus.IN_PROGRESS:
            raise ValueError(
                f"Only IN_PROGRESS meetings can be ended (current: {meeting.status.value})"
            )

        now = datetime.now(timezone.utc).isoformat()
        meeting.status = MeetingStatus.ENDED
        meeting.ended_at = now
        meeting.updated_at = now

        # Mark any still-pending agenda items as skipped
        with self._lock:
            agenda_items = [
                self._agenda_items[iid]
                for iid in meeting.agenda_item_ids
                if iid in self._agenda_items
            ]
            attendees = [
                self._attendees[aid]
                for aid in meeting.attendee_ids
                if aid in self._attendees
            ]
            action_items = [
                self._action_items[acid]
                for acid in meeting.action_item_ids
                if acid in self._action_items
            ]

        for item in agenda_items:
            if item.status == AgendaItemStatus.PENDING:
                item.status = AgendaItemStatus.SKIPPED

        completed = sum(1 for i in agenda_items if i.status == AgendaItemStatus.COMPLETED)

        minutes = MeetingMinutes(
            meeting_id=meeting_id,
            summary=summary or f"All-hands meeting: {meeting.title}",
            decisions=decisions or [],
            key_notes=key_notes or [],
            attendee_count=sum(
                1 for a in attendees if a.status == AttendeeStatus.ATTENDED
            ),
            action_item_count=len(action_items),
            agenda_items_completed=completed,
            agenda_items_total=len(agenda_items),
        )

        with self._lock:
            self._minutes[minutes.minutes_id] = minutes
            meeting.minutes_id = minutes.minutes_id

        logger.info(
            "Meeting ended: %s — minutes generated: %s",
            meeting_id,
            minutes.minutes_id,
        )
        return minutes

    # -- Attendees -----------------------------------------------------------

    def add_attendee(
        self,
        meeting_id: str,
        name: str,
        email: str,
        role: str = "attendee",
    ) -> Attendee:
        """Add an attendee to a meeting.

        Returns the created ``Attendee``.
        Raises ``ValueError`` if the meeting is not found or is ended/cancelled.
        """
        with self._lock:
            meeting = self._meetings.get(meeting_id)
        if meeting is None:
            raise ValueError(f"Meeting {meeting_id} not found")
        if meeting.status in (MeetingStatus.ENDED, MeetingStatus.CANCELLED):
            raise ValueError(
                f"Cannot add attendees to a {meeting.status.value} meeting"
            )
        if not name or not email:
            raise ValueError("Attendee name and email are required")

        with self._lock:
            if len(self._attendees) >= _MAX_ATTENDEES:
                raise ValueError("Maximum attendee limit reached")

        attendee = Attendee(
            meeting_id=meeting_id,
            name=name.strip(),
            email=email.strip().lower(),
            role=role,
        )

        with self._lock:
            self._attendees[attendee.attendee_id] = attendee
            capped_append(meeting.attendee_ids, attendee.attendee_id, 10_000)

        logger.debug("Attendee added: %s → meeting %s", attendee.attendee_id, meeting_id)
        return attendee

    def update_attendee_status(
        self,
        attendee_id: str,
        status: AttendeeStatus,
    ) -> Optional[Attendee]:
        """Update RSVP or attendance status for an attendee.

        Returns the updated ``Attendee``, or ``None`` if not found.
        """
        with self._lock:
            attendee = self._attendees.get(attendee_id)
        if attendee is None:
            return None

        now = datetime.now(timezone.utc).isoformat()
        attendee.status = status
        if status in (AttendeeStatus.ACCEPTED, AttendeeStatus.DECLINED):
            attendee.rsvp_at = now
        if status == AttendeeStatus.ATTENDED:
            attendee.attended_at = now
        return attendee

    def list_attendees(self, meeting_id: str) -> List[Attendee]:
        """List all attendees for a meeting."""
        with self._lock:
            meeting = self._meetings.get(meeting_id)
        if meeting is None:
            return []
        with self._lock:
            return [
                self._attendees[aid]
                for aid in meeting.attendee_ids
                if aid in self._attendees
            ]

    def remove_attendee(self, meeting_id: str, attendee_id: str) -> bool:
        """Remove an attendee from a meeting.

        Returns ``True`` if removed, ``False`` if not found.
        """
        with self._lock:
            meeting = self._meetings.get(meeting_id)
            if meeting is None:
                return False
            if attendee_id not in meeting.attendee_ids:
                return False
            meeting.attendee_ids.remove(attendee_id)
            self._attendees.pop(attendee_id, None)
        return True

    # -- Agenda items --------------------------------------------------------

    def add_agenda_item(
        self,
        meeting_id: str,
        title: str,
        *,
        description: str = "",
        presenter: str = "",
        duration_minutes: int = 5,
        order: int = 0,
    ) -> AgendaItem:
        """Add an agenda item to a meeting.

        Returns the created ``AgendaItem``.
        Raises ``ValueError`` if the meeting is not found or is ended/cancelled.
        """
        with self._lock:
            meeting = self._meetings.get(meeting_id)
        if meeting is None:
            raise ValueError(f"Meeting {meeting_id} not found")
        if meeting.status in (MeetingStatus.ENDED, MeetingStatus.CANCELLED):
            raise ValueError(
                f"Cannot add agenda items to a {meeting.status.value} meeting"
            )
        if not title or not title.strip():
            raise ValueError("Agenda item title must not be empty")

        with self._lock:
            if len(self._agenda_items) >= _MAX_AGENDA_ITEMS:
                raise ValueError("Maximum agenda item limit reached")

        # Default order = current count + 1 if not provided explicitly
        if order == 0:
            with self._lock:
                order = len(meeting.agenda_item_ids) + 1

        item = AgendaItem(
            meeting_id=meeting_id,
            title=title.strip(),
            description=description,
            presenter=presenter,
            duration_minutes=max(1, duration_minutes),
            order=order,
        )

        with self._lock:
            self._agenda_items[item.item_id] = item
            capped_append(meeting.agenda_item_ids, item.item_id, 10_000)

        return item

    def update_agenda_item_status(
        self,
        item_id: str,
        status: AgendaItemStatus,
    ) -> Optional[AgendaItem]:
        """Update execution status of an agenda item.

        Returns the updated ``AgendaItem``, or ``None`` if not found.
        """
        with self._lock:
            item = self._agenda_items.get(item_id)
        if item is None:
            return None

        now = datetime.now(timezone.utc).isoformat()
        item.status = status
        if status == AgendaItemStatus.IN_PROGRESS:
            item.started_at = now
        elif status in (AgendaItemStatus.COMPLETED, AgendaItemStatus.SKIPPED):
            item.completed_at = now
        return item

    def list_agenda_items(self, meeting_id: str) -> List[AgendaItem]:
        """List all agenda items for a meeting, ordered by ``order``."""
        with self._lock:
            meeting = self._meetings.get(meeting_id)
        if meeting is None:
            return []
        with self._lock:
            items = [
                self._agenda_items[iid]
                for iid in meeting.agenda_item_ids
                if iid in self._agenda_items
            ]
        return sorted(items, key=lambda i: i.order)

    # -- Action items --------------------------------------------------------

    def add_action_item(
        self,
        meeting_id: str,
        title: str,
        *,
        description: str = "",
        owner: str = "",
        due_date: Optional[str] = None,
        agenda_item_id: Optional[str] = None,
    ) -> ActionItem:
        """Add a follow-up action item to a meeting.

        Returns the created ``ActionItem``.
        Raises ``ValueError`` if the meeting is not found.
        """
        with self._lock:
            meeting = self._meetings.get(meeting_id)
        if meeting is None:
            raise ValueError(f"Meeting {meeting_id} not found")
        if not title or not title.strip():
            raise ValueError("Action item title must not be empty")

        with self._lock:
            if len(self._action_items) >= _MAX_ACTION_ITEMS:
                raise ValueError("Maximum action item limit reached")

        action = ActionItem(
            meeting_id=meeting_id,
            title=title.strip(),
            description=description,
            owner=owner,
            due_date=due_date,
            agenda_item_id=agenda_item_id,
        )

        with self._lock:
            self._action_items[action.action_id] = action
            capped_append(meeting.action_item_ids, action.action_id, 10_000)

        logger.debug("Action item created: %s → meeting %s", action.action_id, meeting_id)
        return action

    def update_action_item(
        self,
        action_id: str,
        *,
        title: Optional[str] = None,
        description: Optional[str] = None,
        owner: Optional[str] = None,
        due_date: Optional[str] = None,
        status: Optional[ActionItemStatus] = None,
    ) -> Optional[ActionItem]:
        """Update an action item.

        Returns the updated ``ActionItem``, or ``None`` if not found.
        """
        with self._lock:
            action = self._action_items.get(action_id)
        if action is None:
            return None

        if title is not None:
            action.title = title.strip()
        if description is not None:
            action.description = description
        if owner is not None:
            action.owner = owner
        if due_date is not None:
            action.due_date = due_date
        if status is not None:
            action.status = status
            if status == ActionItemStatus.COMPLETED:
                action.completed_at = datetime.now(timezone.utc).isoformat()
        return action

    def list_action_items(
        self,
        meeting_id: Optional[str] = None,
        status: Optional[ActionItemStatus] = None,
        owner: Optional[str] = None,
    ) -> List[ActionItem]:
        """List action items with optional filters.

        Args:
            meeting_id: Filter to a specific meeting.
            status:     Filter by status.
            owner:      Filter by owner name/ID.
        """
        with self._lock:
            items = list(self._action_items.values())
        if meeting_id is not None:
            items = [a for a in items if a.meeting_id == meeting_id]
        if status is not None:
            items = [a for a in items if a.status == status]
        if owner is not None:
            items = [a for a in items if a.owner == owner]
        return items

    # -- Minutes -------------------------------------------------------------

    def get_minutes(self, meeting_id: str) -> Optional[MeetingMinutes]:
        """Retrieve the meeting minutes for a completed meeting."""
        with self._lock:
            meeting = self._meetings.get(meeting_id)
        if meeting is None or meeting.minutes_id is None:
            return None
        with self._lock:
            return self._minutes.get(meeting.minutes_id)

    # -- Recurring meetings --------------------------------------------------

    def create_next_occurrence(self, meeting_id: str) -> Optional[AllHandsMeeting]:
        """Create the next occurrence of a recurring meeting.

        Computes the next ``scheduled_at`` based on the meeting's
        ``recurrence`` frequency and creates a new meeting record with the
        same metadata but a fresh ID.

        Calendar-accurate arithmetic is used for monthly and quarterly
        recurrences (no drift from fixed 30/91 day offsets).  Weekly and
        biweekly use exact day offsets.

        Returns the new ``AllHandsMeeting``, or ``None`` if the meeting is
        not found or has ``RecurrenceFrequency.NONE``.
        """
        with self._lock:
            template = self._meetings.get(meeting_id)
        if template is None or template.recurrence == RecurrenceFrequency.NONE:
            return None

        try:
            base_dt = datetime.fromisoformat(template.scheduled_at)
        except (ValueError, TypeError):
            base_dt = datetime.now(timezone.utc)

        next_dt = _advance_by_frequency(base_dt, template.recurrence)
        next_scheduled_at = next_dt.isoformat()

        return self.schedule_meeting(
            title=template.title,
            scheduled_at=next_scheduled_at,
            description=template.description,
            meeting_type=template.meeting_type,
            duration_minutes=template.duration_minutes,
            timezone=template.timezone,
            location=template.location,
            video_link=template.video_link,
            organizer=template.organizer,
            recurrence=template.recurrence,
        )

    # -- Stats ---------------------------------------------------------------

    def stats(self) -> Dict[str, Any]:
        """Return summary statistics for the All-Hands manager."""
        with self._lock:
            return {
                "total_meetings": len(self._meetings),
                "scheduled": sum(
                    1 for m in self._meetings.values()
                    if m.status == MeetingStatus.SCHEDULED
                ),
                "in_progress": sum(
                    1 for m in self._meetings.values()
                    if m.status == MeetingStatus.IN_PROGRESS
                ),
                "ended": sum(
                    1 for m in self._meetings.values()
                    if m.status == MeetingStatus.ENDED
                ),
                "cancelled": sum(
                    1 for m in self._meetings.values()
                    if m.status == MeetingStatus.CANCELLED
                ),
                "total_attendees": len(self._attendees),
                "total_agenda_items": len(self._agenda_items),
                "total_action_items": len(self._action_items),
                "open_action_items": sum(
                    1 for a in self._action_items.values()
                    if a.status == ActionItemStatus.OPEN
                ),
                "total_minutes": len(self._minutes),
            }


# ---------------------------------------------------------------------------
# Flask Blueprint factory
# ---------------------------------------------------------------------------


def create_all_hands_api(mgr: AllHandsManager) -> Any:
    """Create a Flask Blueprint exposing All-Hands meeting management endpoints.

    Endpoint summary::

        POST   /api/all-hands/meetings                              Schedule meeting
        GET    /api/all-hands/meetings                              List meetings
        GET    /api/all-hands/meetings/<id>                         Get meeting
        PUT    /api/all-hands/meetings/<id>                         Update meeting
        POST   /api/all-hands/meetings/<id>/start                   Start meeting
        POST   /api/all-hands/meetings/<id>/end                     End meeting + generate minutes
        DELETE /api/all-hands/meetings/<id>                         Cancel meeting
        POST   /api/all-hands/meetings/<id>/next-occurrence         Create next recurrence

        POST   /api/all-hands/meetings/<id>/attendees               Add attendee
        GET    /api/all-hands/meetings/<id>/attendees               List attendees
        PUT    /api/all-hands/attendees/<id>/status                 Update RSVP/attendance
        DELETE /api/all-hands/meetings/<id>/attendees/<aid>         Remove attendee

        POST   /api/all-hands/meetings/<id>/agenda                  Add agenda item
        GET    /api/all-hands/meetings/<id>/agenda                  List agenda items
        PUT    /api/all-hands/agenda/<id>/status                    Update item status

        POST   /api/all-hands/meetings/<id>/action-items            Add action item
        GET    /api/all-hands/meetings/<id>/action-items            List meeting action items
        GET    /api/all-hands/action-items                          List all action items (filterable)
        PUT    /api/all-hands/action-items/<id>                     Update action item

        GET    /api/all-hands/meetings/<id>/minutes                 Get meeting minutes
        GET    /api/all-hands/stats                                 Statistics
    """
    if not _HAS_FLASK:
        return Blueprint("all_hands", __name__)  # type: ignore[arg-type]

    bp = Blueprint("all_hands", __name__, url_prefix="/api/all-hands")

    def _body() -> Dict[str, Any]:
        return request.get_json(silent=True) or {}

    def _need(body: Dict[str, Any], *keys: str) -> Optional[Any]:
        for k in keys:
            if not body.get(k):
                return jsonify({"error": f"{k} required", "code": "MISSING_FIELDS"}), 400
        return None

    def _404(resource: str = "Resource") -> Any:
        return jsonify({"error": f"{resource} not found", "code": "NOT_FOUND"}), 404

    # -- Meetings ------------------------------------------------------------

    @bp.route("/meetings", methods=["POST"])
    def create_meeting() -> Any:
        """Schedule a new all-hands meeting."""
        b = _body()
        err = _need(b, "title", "scheduled_at")
        if err:
            return err
        try:
            rec = RecurrenceFrequency(b.get("recurrence", "none"))
            mtype = MeetingType(b.get("meeting_type", "all_hands"))
            meeting = mgr.schedule_meeting(
                title=b["title"],
                scheduled_at=b["scheduled_at"],
                description=b.get("description", ""),
                meeting_type=mtype,
                duration_minutes=int(b.get("duration_minutes", 60)),
                timezone=b.get("timezone", "UTC"),
                location=b.get("location", ""),
                video_link=b.get("video_link", ""),
                organizer=b.get("organizer", ""),
                recurrence=rec,
            )
        except (ValueError, KeyError) as exc:
            return jsonify({"error": str(exc), "code": "INVALID_INPUT"}), 400
        return jsonify(meeting.to_dict()), 201

    @bp.route("/meetings", methods=["GET"])
    def list_meetings() -> Any:
        """List meetings with optional ?status= and ?meeting_type= filters."""
        status_str = request.args.get("status")
        type_str = request.args.get("meeting_type")
        status = MeetingStatus(status_str) if status_str else None
        mtype = MeetingType(type_str) if type_str else None
        return jsonify([m.to_dict() for m in mgr.list_meetings(status, mtype)])

    @bp.route("/meetings/<meeting_id>", methods=["GET"])
    def get_meeting(meeting_id: str) -> Any:
        """Get a single meeting by ID."""
        m = mgr.get_meeting(meeting_id)
        return jsonify(m.to_dict()) if m else _404("Meeting")

    @bp.route("/meetings/<meeting_id>", methods=["PUT"])
    def update_meeting(meeting_id: str) -> Any:
        """Update a scheduled or in-progress meeting."""
        b = _body()
        try:
            rec = RecurrenceFrequency(b["recurrence"]) if "recurrence" in b else None
            m = mgr.update_meeting(
                meeting_id,
                title=b.get("title"),
                description=b.get("description"),
                scheduled_at=b.get("scheduled_at"),
                duration_minutes=int(b["duration_minutes"]) if "duration_minutes" in b else None,
                location=b.get("location"),
                video_link=b.get("video_link"),
                organizer=b.get("organizer"),
                recurrence=rec,
            )
        except ValueError as exc:
            return jsonify({"error": str(exc), "code": "INVALID_STATE"}), 409
        return jsonify(m.to_dict()) if m else _404("Meeting")

    @bp.route("/meetings/<meeting_id>", methods=["DELETE"])
    def cancel_meeting(meeting_id: str) -> Any:
        """Cancel a scheduled meeting."""
        try:
            ok = mgr.cancel_meeting(meeting_id)
        except ValueError as exc:
            return jsonify({"error": str(exc), "code": "INVALID_STATE"}), 409
        return jsonify({"status": "cancelled"}) if ok else _404("Meeting")

    @bp.route("/meetings/<meeting_id>/start", methods=["POST"])
    def start_meeting(meeting_id: str) -> Any:
        """Start an in-progress meeting."""
        try:
            m = mgr.start_meeting(meeting_id)
        except ValueError as exc:
            return jsonify({"error": str(exc), "code": "INVALID_STATE"}), 409
        return jsonify(m.to_dict()) if m else _404("Meeting")

    @bp.route("/meetings/<meeting_id>/end", methods=["POST"])
    def end_meeting(meeting_id: str) -> Any:
        """End a meeting and generate minutes."""
        b = _body()
        try:
            minutes = mgr.end_meeting(
                meeting_id,
                summary=b.get("summary", ""),
                decisions=b.get("decisions") or [],
                key_notes=b.get("key_notes") or [],
            )
        except ValueError as exc:
            return jsonify({"error": str(exc), "code": "INVALID_STATE"}), 409
        return jsonify(minutes.to_dict()) if minutes else _404("Meeting")

    @bp.route("/meetings/<meeting_id>/next-occurrence", methods=["POST"])
    def next_occurrence(meeting_id: str) -> Any:
        """Create the next recurrence of a recurring meeting."""
        m = mgr.create_next_occurrence(meeting_id)
        if m is None:
            return jsonify({
                "error": "Meeting not found or not recurring",
                "code": "NOT_RECURRING",
            }), 404
        return jsonify(m.to_dict()), 201

    # -- Attendees -----------------------------------------------------------

    @bp.route("/meetings/<meeting_id>/attendees", methods=["POST"])
    def add_attendee(meeting_id: str) -> Any:
        """Add an attendee to a meeting."""
        b = _body()
        err = _need(b, "name", "email")
        if err:
            return err
        try:
            attendee = mgr.add_attendee(
                meeting_id, b["name"], b["email"], b.get("role", "attendee")
            )
        except ValueError as exc:
            return jsonify({"error": str(exc), "code": "INVALID_INPUT"}), 400
        return jsonify(attendee.to_dict()), 201

    @bp.route("/meetings/<meeting_id>/attendees", methods=["GET"])
    def list_attendees(meeting_id: str) -> Any:
        """List attendees for a meeting."""
        return jsonify([a.to_dict() for a in mgr.list_attendees(meeting_id)])

    @bp.route("/attendees/<attendee_id>/status", methods=["PUT"])
    def update_attendee_status(attendee_id: str) -> Any:
        """Update RSVP or attendance status."""
        b = _body()
        err = _need(b, "status")
        if err:
            return err
        try:
            status = AttendeeStatus(b["status"])
        except ValueError:
            return jsonify({"error": "Invalid status value", "code": "INVALID_INPUT"}), 400
        a = mgr.update_attendee_status(attendee_id, status)
        return jsonify(a.to_dict()) if a else _404("Attendee")

    @bp.route("/meetings/<meeting_id>/attendees/<attendee_id>", methods=["DELETE"])
    def remove_attendee(meeting_id: str, attendee_id: str) -> Any:
        """Remove an attendee from a meeting."""
        ok = mgr.remove_attendee(meeting_id, attendee_id)
        return jsonify({"status": "removed"}) if ok else _404("Attendee")

    # -- Agenda items --------------------------------------------------------

    @bp.route("/meetings/<meeting_id>/agenda", methods=["POST"])
    def add_agenda_item(meeting_id: str) -> Any:
        """Add an agenda item to a meeting."""
        b = _body()
        err = _need(b, "title")
        if err:
            return err
        try:
            item = mgr.add_agenda_item(
                meeting_id,
                b["title"],
                description=b.get("description", ""),
                presenter=b.get("presenter", ""),
                duration_minutes=int(b.get("duration_minutes", 5)),
                order=int(b.get("order", 0)),
            )
        except ValueError as exc:
            return jsonify({"error": str(exc), "code": "INVALID_INPUT"}), 400
        return jsonify(item.to_dict()), 201

    @bp.route("/meetings/<meeting_id>/agenda", methods=["GET"])
    def list_agenda_items(meeting_id: str) -> Any:
        """List agenda items for a meeting (ordered)."""
        return jsonify([i.to_dict() for i in mgr.list_agenda_items(meeting_id)])

    @bp.route("/agenda/<item_id>/status", methods=["PUT"])
    def update_agenda_item_status(item_id: str) -> Any:
        """Update execution status of an agenda item."""
        b = _body()
        err = _need(b, "status")
        if err:
            return err
        try:
            status = AgendaItemStatus(b["status"])
        except ValueError:
            return jsonify({"error": "Invalid status value", "code": "INVALID_INPUT"}), 400
        item = mgr.update_agenda_item_status(item_id, status)
        return jsonify(item.to_dict()) if item else _404("Agenda item")

    # -- Action items --------------------------------------------------------

    @bp.route("/meetings/<meeting_id>/action-items", methods=["POST"])
    def add_action_item(meeting_id: str) -> Any:
        """Add an action item to a meeting."""
        b = _body()
        err = _need(b, "title")
        if err:
            return err
        try:
            action = mgr.add_action_item(
                meeting_id,
                b["title"],
                description=b.get("description", ""),
                owner=b.get("owner", ""),
                due_date=b.get("due_date"),
                agenda_item_id=b.get("agenda_item_id"),
            )
        except ValueError as exc:
            return jsonify({"error": str(exc), "code": "INVALID_INPUT"}), 400
        return jsonify(action.to_dict()), 201

    @bp.route("/meetings/<meeting_id>/action-items", methods=["GET"])
    def list_meeting_action_items(meeting_id: str) -> Any:
        """List action items for a specific meeting."""
        return jsonify([a.to_dict() for a in mgr.list_action_items(meeting_id=meeting_id)])

    @bp.route("/action-items", methods=["GET"])
    def list_action_items_global() -> Any:
        """List all action items with optional ?status= and ?owner= filters."""
        status_str = request.args.get("status")
        owner = request.args.get("owner")
        status = ActionItemStatus(status_str) if status_str else None
        return jsonify([a.to_dict() for a in mgr.list_action_items(status=status, owner=owner)])

    @bp.route("/action-items/<action_id>", methods=["PUT"])
    def update_action_item(action_id: str) -> Any:
        """Update an action item (title, owner, due_date, status)."""
        b = _body()
        status = None
        if "status" in b:
            try:
                status = ActionItemStatus(b["status"])
            except ValueError:
                return jsonify({"error": "Invalid status value", "code": "INVALID_INPUT"}), 400
        action = mgr.update_action_item(
            action_id,
            title=b.get("title"),
            description=b.get("description"),
            owner=b.get("owner"),
            due_date=b.get("due_date"),
            status=status,
        )
        return jsonify(action.to_dict()) if action else _404("Action item")

    # -- Minutes -------------------------------------------------------------

    @bp.route("/meetings/<meeting_id>/minutes", methods=["GET"])
    def get_minutes(meeting_id: str) -> Any:
        """Get meeting minutes for a completed meeting."""
        mins = mgr.get_minutes(meeting_id)
        return jsonify(mins.to_dict()) if mins else _404("Minutes")

    # -- Stats ---------------------------------------------------------------

    @bp.route("/stats", methods=["GET"])
    def all_hands_stats() -> Any:
        """Return All-Hands system statistics."""
        return jsonify(mgr.stats())

    require_blueprint_auth(bp)
    return bp
