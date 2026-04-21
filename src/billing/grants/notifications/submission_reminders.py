# © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional


@dataclass
class SubmissionReminder:
    reminder_id: str
    session_id: str
    application_id: str
    message: str
    created_at: datetime
    dismissed: bool = False


_reminders: Dict[str, SubmissionReminder] = {}


class SubmissionReminderSystem:
    def create_reminder(self, session_id: str, application_id: str, message: str) -> SubmissionReminder:
        reminder = SubmissionReminder(
            reminder_id=str(uuid.uuid4()),
            session_id=session_id,
            application_id=application_id,
            message=message,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        _reminders[reminder.reminder_id] = reminder
        return reminder

    def get_pending(self, session_id: str) -> List[SubmissionReminder]:
        return [r for r in _reminders.values() if r.session_id == session_id and not r.dismissed]

    def dismiss(self, reminder_id: str) -> Optional[SubmissionReminder]:
        r = _reminders.get(reminder_id)
        if r:
            r.dismissed = True
        return r
