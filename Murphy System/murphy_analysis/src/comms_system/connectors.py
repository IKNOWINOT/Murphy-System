"""
Communications Connectors (Email/Slack)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class EmailConnector:
    sender: str = "murphy@local"

    def send(self, recipient: str, subject: str, body: str) -> Dict[str, Any]:
        return {"status": "sent", "recipient": recipient, "subject": subject}


@dataclass
class SlackConnector:
    workspace: str = "murphy"

    def post(self, channel: str, message: str) -> Dict[str, Any]:
        return {"status": "sent", "channel": channel, "message": message}
