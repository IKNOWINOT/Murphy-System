from __future__ import annotations

from .utils.typed_event import HiveEvent


class MessageValidatorBot:
    def validate(self, data: dict) -> HiveEvent:
        return HiveEvent(**data)
