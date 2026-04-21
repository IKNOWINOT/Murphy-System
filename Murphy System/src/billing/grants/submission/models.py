# © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional


@dataclass
class SubmissionFile:
    file_id: str
    filename: str
    format: str
    content_type: str
    size_bytes: int
    description: str


@dataclass
class SubmissionStep:
    step_number: int
    instruction: str
    url: Optional[str] = None
    screenshot_hint: Optional[str] = None
    data_to_enter: Dict[str, str] = field(default_factory=dict)
    is_upload: bool = False
    upload_file_id: Optional[str] = None


@dataclass
class SubmissionPackage:
    package_id: str
    application_id: str
    session_id: str
    portal: str
    format: str
    files: List[SubmissionFile]
    instructions: List[SubmissionStep]
    status: str
    created_at: datetime
    submitted_at: Optional[datetime] = None
    confirmation_number: Optional[str] = None


@dataclass
class StatusChange:
    changed_at: datetime
    old_status: str
    new_status: str
    notes: str = ""


@dataclass
class SubmissionStatus:
    submission_id: str
    status: str
    portal: str
    submitted_at: Optional[datetime] = None
    confirmation_number: Optional[str] = None
    last_checked: Optional[datetime] = None
    notes: str = ""
    history: List[StatusChange] = field(default_factory=list)

    def transition(self, new_status: str, notes: str = "") -> None:
        change = StatusChange(
            changed_at=datetime.now(timezone.utc).replace(tzinfo=None),
            old_status=self.status,
            new_status=new_status,
            notes=notes,
        )
        self.history.append(change)
        self.status = new_status
        self.last_checked = datetime.now(timezone.utc).replace(tzinfo=None)
