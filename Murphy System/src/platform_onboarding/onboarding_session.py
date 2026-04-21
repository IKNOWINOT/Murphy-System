# © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
"""Onboarding session: persists task states, collected data, and wait states."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Optional


@dataclass
class OnboardingSession:
    session_id: str
    account_id: str
    created_at: datetime
    updated_at: datetime
    # task_id -> "not_started"|"in_progress"|"completed"|"skipped"|"waiting_on_external"
    task_states: Dict[str, str]
    task_data: Dict[str, Dict]          # task_id -> collected data
    wait_states: Dict[str, datetime]    # task_id -> expected_completion date
    session_data: Dict[str, str]        # prefill data: ein, company_name, address, etc.
    checkpoint: Optional[Dict] = None

    # ------------------------------------------------------------------ #
    # State accessors                                                       #
    # ------------------------------------------------------------------ #

    def get_task_state(self, task_id: str) -> str:
        return self.task_states.get(task_id, "not_started")

    def set_task_state(
        self,
        task_id: str,
        state: str,
        data: Optional[Dict] = None,
    ) -> None:
        self.task_states[task_id] = state
        if data:
            self.task_data[task_id] = data
        self.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

    # ------------------------------------------------------------------ #
    # Serialization                                                         #
    # ------------------------------------------------------------------ #

    def to_dict(self) -> Dict:
        return {
            "session_id": self.session_id,
            "account_id": self.account_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "task_states": self.task_states,
            "task_data": self.task_data,
            "wait_states": {k: v.isoformat() for k, v in self.wait_states.items()},
            "session_data": self.session_data,
            "checkpoint": self.checkpoint,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "OnboardingSession":
        wait_states = {
            k: datetime.fromisoformat(v)
            for k, v in data.get("wait_states", {}).items()
        }
        return cls(
            session_id=data["session_id"],
            account_id=data["account_id"],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            task_states=data.get("task_states", {}),
            task_data=data.get("task_data", {}),
            wait_states=wait_states,
            session_data=data.get("session_data", {}),
            checkpoint=data.get("checkpoint"),
        )

    @classmethod
    def create_new(cls, account_id: str) -> "OnboardingSession":
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        return cls(
            session_id=str(uuid.uuid4()),
            account_id=account_id,
            created_at=now,
            updated_at=now,
            task_states={},
            task_data={},
            wait_states={},
            session_data={},
            checkpoint=None,
        )
