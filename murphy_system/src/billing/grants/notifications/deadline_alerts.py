# © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional

ALERT_THRESHOLDS_DAYS = [30, 14, 7, 3, 1]


@dataclass
class DeadlineAlert:
    alert_id: str
    grant_id: str
    grant_title: str
    deadline: datetime
    days_before: int
    alert_level: str
    created_at: datetime
    dismissed: bool = False


# In-memory alert store
_alerts: Dict[str, DeadlineAlert] = {}
# Tracks which (grant_id, days_before) alerts have been sent
_sent_alerts: Dict[str, set] = {}


class DeadlineAlertSystem:
    def check_deadlines(self, grants: List[Dict]) -> List[DeadlineAlert]:
        """Check grants for upcoming deadlines and create alerts as needed."""
        new_alerts = []
        now = datetime.utcnow()

        for grant in grants:
            grant_id = grant.get("grant_id", "")
            grant_title = grant.get("title", "")
            deadline_str = grant.get("deadline")
            if not deadline_str or not grant_id:
                continue

            if isinstance(deadline_str, str):
                try:
                    deadline = datetime.fromisoformat(deadline_str)
                except ValueError:
                    continue
            elif isinstance(deadline_str, datetime):
                deadline = deadline_str
            else:
                continue

            days_until = (deadline - now).days
            sent = _sent_alerts.setdefault(grant_id, set())

            for threshold in ALERT_THRESHOLDS_DAYS:
                if days_until <= threshold and threshold not in sent:
                    alert = DeadlineAlert(
                        alert_id=str(uuid.uuid4()),
                        grant_id=grant_id,
                        grant_title=grant_title,
                        deadline=deadline,
                        days_before=threshold,
                        alert_level=self._level(threshold),
                        created_at=now,
                    )
                    _alerts[alert.alert_id] = alert
                    sent.add(threshold)
                    new_alerts.append(alert)

        return new_alerts

    def get_active_alerts(self) -> List[DeadlineAlert]:
        return [a for a in _alerts.values() if not a.dismissed]

    def dismiss_alert(self, alert_id: str) -> Optional[DeadlineAlert]:
        alert = _alerts.get(alert_id)
        if alert:
            alert.dismissed = True
        return alert

    def get_all_alerts(self) -> List[DeadlineAlert]:
        return list(_alerts.values())

    def _level(self, days: int) -> str:
        if days <= 1:
            return "critical"
        if days <= 3:
            return "urgent"
        if days <= 7:
            return "high"
        if days <= 14:
            return "medium"
        return "low"
