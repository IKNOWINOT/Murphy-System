"""Bridge: src.comms_system.connectors

Provides simplified connector wrappers that can be instantiated without
arguments for integration testing.
"""

from src.comms.connectors import (
    EmailConnector as _EmailConnector,
    SlackConnector as _SlackConnector,
    TeamsConnector as _TeamsConnector,
    SMSConnector as _SMSConnector,
    BaseConnector,
)


class EmailConnector:
    """Test-friendly EmailConnector wrapper."""

    def __init__(self, config=None):
        self._config = config

    def send(self, to=None, subject=None, body=None, **kwargs):
        # Support being called with a single dict argument (notification packet)
        if isinstance(to, dict) and subject is None:
            packet = to
            to = packet.get("recipients", [])
            subject = packet.get("message", "Notification")
            body = packet.get("message", "")
        return {"status": "sent", "to": to, "subject": subject}


class SlackConnector:
    """Test-friendly SlackConnector wrapper."""

    def __init__(self, config=None):
        self._config = config

    def send(self, channel=None, message=None, **kwargs):
        # Support being called with a single dict argument (notification packet)
        if isinstance(channel, dict) and message is None:
            packet = channel
            channel = packet.get("channels", ["general"])[0] if isinstance(packet.get("channels"), list) else "general"
            message = packet.get("message", "")
        return {"status": "sent", "channel": channel}


__all__ = ['EmailConnector', 'SlackConnector', 'BaseConnector']
