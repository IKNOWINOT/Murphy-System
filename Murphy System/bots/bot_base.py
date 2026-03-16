"""Base classes for asynchronous bots."""
from __future__ import annotations

from dataclasses import dataclass
from abc import ABC, abstractmethod


@dataclass
class Message:
    sender: str
    content: str


class AsyncBot:
    async def handle(self, message: Message) -> str:
        """Handle an incoming message."""
        raise NotImplementedError


class HiveBot(ABC):
    """Interface for dynamically loaded bot plugins."""

    @abstractmethod
    def init(self) -> None:
        """Initialize resources for the bot."""

    @abstractmethod
    def register_handlers(self) -> None:
        """Register any message handlers with the orchestrator."""
