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

    def send(self, to, subject, body):
        return {"status": "sent", "to": to, "subject": subject}


class SlackConnector:
    """Test-friendly SlackConnector wrapper."""

    def __init__(self, config=None):
        self._config = config

    def send(self, channel, message):
        return {"status": "sent", "channel": channel}


__all__ = ['EmailConnector', 'SlackConnector', 'BaseConnector']
