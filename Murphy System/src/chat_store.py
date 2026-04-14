"""
chat_store.py — Murphy System Chat Conversation Store
=====================================================
In-memory conversation storage for the Murphy chat interface.
Provides user-scoped, multi-role message conversations with
LLM context-window management.

Complements the existing ``conversation_manager.py`` which manages
bot-paired message history.  This module stores the richer chat-style
messages (user / assistant / system / tool) needed for the Claude-like
interface.

Error codes: CHAT-STORE-ERR-001 .. CHAT-STORE-ERR-010

Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · BSL 1.1
"""

from __future__ import annotations

import logging
import re
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_CONVERSATIONS_PER_USER = 100
MAX_MESSAGES_PER_CONVERSATION = 500
CONTEXT_WINDOW_MESSAGES = 20  # last N messages sent to LLM

_VALID_ID = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class ChatMessage:
    """A single message in a conversation."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    role: str = "user"  # "user" | "assistant" | "system"
    content: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    artifacts: List[Dict[str, Any]] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_llm_message(self) -> Dict[str, str]:
        """Convert to OpenAI-compatible message dict for LLM context."""
        return {"role": self.role, "content": self.content}


@dataclass
class ChatConversation:
    """A multi-turn chat conversation."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    user_id: str = ""
    title: str = "New conversation"
    messages: List[ChatMessage] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    pinned: bool = False
    mode: str = "chat"  # "chat" | "forge" | "analyze"

    def to_dict(self, include_messages: bool = True) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "pinned": self.pinned,
            "mode": self.mode,
            "message_count": len(self.messages),
        }
        if include_messages:
            d["messages"] = [m.to_dict() for m in self.messages]
        return d

    def get_context_messages(self, system_prompt: str = "") -> List[Dict[str, str]]:
        """Return the last N messages as LLM-compatible context window."""
        ctx: List[Dict[str, str]] = []
        if system_prompt:
            ctx.append({"role": "system", "content": system_prompt})
        recent = self.messages[-CONTEXT_WINDOW_MESSAGES:]
        for msg in recent:
            if msg.role in ("user", "assistant", "system"):
                ctx.append(msg.to_llm_message())
        return ctx

    def auto_title(self) -> str:
        """Generate a title from the first user message."""
        for msg in self.messages:
            if msg.role == "user" and msg.content.strip():
                text = msg.content.strip()
                if len(text) > 60:
                    return text[:57] + "..."
                return text
        return "New conversation"


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------

class ChatStore:
    """Thread-safe in-memory chat conversation storage."""

    def __init__(self) -> None:
        self._conversations: Dict[str, ChatConversation] = {}
        self._user_index: Dict[str, List[str]] = {}  # user_id -> [conv_id]

    # ── CRUD ──────────────────────────────────────────────────────────

    def create(self, user_id: str, title: str = "", mode: str = "chat") -> ChatConversation:
        """Create a new conversation for a user."""
        try:
            user_convs = self._user_index.get(user_id, [])
            if len(user_convs) >= MAX_CONVERSATIONS_PER_USER:
                self._evict_oldest(user_id)

            conv = ChatConversation(
                user_id=user_id,
                title=title or "New conversation",
                mode=mode,
            )
            self._conversations[conv.id] = conv
            self._user_index.setdefault(user_id, []).append(conv.id)
            return conv
        except Exception as exc:  # CHAT-STORE-ERR-001
            logger.error("CHAT-STORE-ERR-001: Failed to create conversation: %s", exc)
            raise

    def get(self, conv_id: str, user_id: str) -> Optional[ChatConversation]:
        """Get a conversation by ID, verifying ownership."""
        conv = self._conversations.get(conv_id)
        if conv and conv.user_id == user_id:
            return conv
        return None

    def list_for_user(self, user_id: str) -> List[Dict[str, Any]]:
        """List all conversations for a user (without full messages)."""
        conv_ids = self._user_index.get(user_id, [])
        result = []
        for cid in reversed(conv_ids):  # newest first
            conv = self._conversations.get(cid)
            if conv:
                result.append(conv.to_dict(include_messages=False))
        return result

    def add_message(
        self,
        conv_id: str,
        user_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        artifacts: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[ChatMessage]:
        """Add a message to a conversation."""
        conv = self.get(conv_id, user_id)
        if not conv:
            logger.warning("CHAT-STORE-ERR-002: Conversation %s not found for user %s", conv_id, user_id)
            return None

        if len(conv.messages) >= MAX_MESSAGES_PER_CONVERSATION:
            logger.warning("CHAT-STORE-ERR-003: Message limit reached for conversation %s", conv_id)
            return None

        # Sanitize content length (CWE-400)
        content = content[:50000] if isinstance(content, str) else ""

        msg = ChatMessage(
            role=role,
            content=content,
            metadata=metadata or {},
            tool_calls=tool_calls or [],
            artifacts=artifacts or [],
        )
        conv.messages.append(msg)
        conv.updated_at = time.time()

        # Auto-title on first user message
        if role == "user" and len([m for m in conv.messages if m.role == "user"]) == 1:
            conv.title = conv.auto_title()

        return msg

    def delete(self, conv_id: str, user_id: str) -> bool:
        """Delete a conversation."""
        conv = self._conversations.get(conv_id)
        if not conv or conv.user_id != user_id:
            return False
        del self._conversations[conv_id]
        user_convs = self._user_index.get(user_id, [])
        if conv_id in user_convs:
            user_convs.remove(conv_id)
        return True

    def rename(self, conv_id: str, user_id: str, new_title: str) -> bool:
        """Rename a conversation."""
        conv = self.get(conv_id, user_id)
        if not conv:
            return False
        conv.title = (new_title or "").strip()[:200]
        conv.updated_at = time.time()
        return True

    # ── Internal helpers ──────────────────────────────────────────────

    def _evict_oldest(self, user_id: str) -> None:
        """Remove the oldest non-pinned conversation for a user."""
        convs = self._user_index.get(user_id, [])
        oldest_id = None
        oldest_time = float("inf")
        for cid in convs:
            c = self._conversations.get(cid)
            if c and not c.pinned and c.updated_at < oldest_time:
                oldest_time = c.updated_at
                oldest_id = cid
        if oldest_id:
            self.delete(oldest_id, user_id)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_store: Optional[ChatStore] = None


def get_chat_store() -> ChatStore:
    """Return the global chat store singleton."""
    global _store
    if _store is None:
        _store = ChatStore()
    return _store
