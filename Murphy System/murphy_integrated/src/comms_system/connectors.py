"""
Communications Connectors (Email/Slack)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class EmailConnector:
    sender: str = "murphy@local"

    def send(self, recipient: str | Dict[str, Any], subject: str = "", body: str = "") -> Dict[str, Any]:
        if isinstance(recipient, dict):
            packet = recipient
            recipient = ",".join(packet.get("recipients", []))
            subject = packet.get("subject", "notification")
            body = packet.get("message", "")
        return {"status": "sent", "recipient": recipient, "subject": subject}


@dataclass
class SlackConnector:
    workspace: str = "murphy"

    def post(self, channel: str | Dict[str, Any], message: str = "") -> Dict[str, Any]:
        if isinstance(channel, dict):
            packet = channel
            channel = ",".join(packet.get("channels", [])) or "general"
            message = packet.get("message", "")
        return {"status": "sent", "channel": channel, "message": message}

    def send(self, packet: Dict[str, Any]) -> Dict[str, Any]:
        return self.post(packet)
