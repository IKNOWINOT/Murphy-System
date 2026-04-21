# © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional


@dataclass
class StatusUpdateEvent:
    event_id: str
    submission_id: str
    old_status: str
    new_status: str
    message: str
    created_at: datetime
    read: bool = False


_events: Dict[str, StatusUpdateEvent] = {}


class StatusUpdateNotifier:
    def notify(self, submission_id: str, old_status: str, new_status: str, message: str = "") -> StatusUpdateEvent:
        event = StatusUpdateEvent(
            event_id=str(uuid.uuid4()),
            submission_id=submission_id,
            old_status=old_status,
            new_status=new_status,
            message=message or f"Status changed from {old_status} to {new_status}",
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        _events[event.event_id] = event
        return event

    def get_unread(self, submission_id: str) -> List[StatusUpdateEvent]:
        return [e for e in _events.values() if e.submission_id == submission_id and not e.read]

    def mark_read(self, event_id: str) -> Optional[StatusUpdateEvent]:
        e = _events.get(event_id)
        if e:
            e.read = True
        return e
