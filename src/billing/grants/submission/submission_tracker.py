# © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Optional

from src.billing.grants.submission.models import StatusChange, SubmissionStatus

# In-memory store: submission_id -> SubmissionStatus
_statuses: Dict[str, SubmissionStatus] = {}


class SubmissionTracker:
    def create(self, submission_id: str, portal: str, initial_status: str = "generated") -> SubmissionStatus:
        status = SubmissionStatus(
            submission_id=submission_id,
            status=initial_status,
            portal=portal,
        )
        _statuses[submission_id] = status
        return status

    def get(self, submission_id: str) -> Optional[SubmissionStatus]:
        return _statuses.get(submission_id)

    def update_status(self, submission_id: str, new_status: str, notes: str = "") -> Optional[SubmissionStatus]:
        status = _statuses.get(submission_id)
        if status:
            status.transition(new_status, notes)
        return status

    def mark_submitted(self, submission_id: str, confirmation_number: Optional[str] = None) -> Optional[SubmissionStatus]:
        status = _statuses.get(submission_id)
        if status:
            status.transition("submitted")
            status.submitted_at = datetime.now(timezone.utc).replace(tzinfo=None)
            if confirmation_number:
                status.confirmation_number = confirmation_number
        return status
