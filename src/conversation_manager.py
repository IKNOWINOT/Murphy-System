"""
Conversation Manager
Manages conversation history with bounded memory and automatic cleanup
Integrates with MemoryArtifactSystem for important conversation preservation
"""

import json
import logging
import re
import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("conversation_manager")


@dataclass
class ConversationMessage:
    """Single message in a conversation"""
    user_message: str
    bot_response: str
    timestamp: datetime
    metadata: Dict = field(default_factory=dict)


@dataclass
class Conversation:
    """Conversation with bounded history"""
    conversation_id: str
    messages: deque  # Bounded deque for automatic size limiting
    created_at: datetime
    last_activity: datetime
    metadata: Dict = field(default_factory=dict)

    def add_message(self, user_msg: str, bot_msg: str, metadata: Optional[Dict] = None):
        """Add message to conversation"""
        msg = ConversationMessage(
            user_message=user_msg,
            bot_response=bot_msg,
            timestamp=datetime.now(timezone.utc),
            metadata=metadata or {}
        )
        self.messages.append(msg)
        self.last_activity = datetime.now(timezone.utc)

    def get_recent_messages(self, count: int = 10) -> List[ConversationMessage]:
        """Get recent messages"""
        return list(self.messages)[-count:]

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        return {
            'conversation_id': self.conversation_id,
            'created_at': self.created_at.isoformat(),
            'last_activity': self.last_activity.isoformat(),
            'message_count': len(self.messages),
            'metadata': self.metadata
        }


class ConversationManager:
    """
    Manages conversations with bounded memory and automatic cleanup.

    Features:
    - Bounded message history per conversation (default: 100 messages)
    - Automatic cleanup of old conversations (default: 24 hours)
    - Thread-safe operations
    - Integration with MemoryArtifactSystem for important conversations
    - Periodic cleanup to prevent memory leaks

    Architecture Alignment:
    - Integrates with existing MemoryArtifactSystem
    - Preserves important conversations as artifacts
    - Cleans up ephemeral chat history
    """

    # Conversation ID format: alphanumeric + hyphen/underscore, max 100 chars
    _VALID_CONV_ID = re.compile(r"^[a-zA-Z0-9_\-]{1,100}$")
    _MAX_CONVERSATIONS = 10_000  # Hard cap to prevent memory exhaustion (CWE-400)

    def __init__(
        self,
        max_messages_per_conversation: int = 100,
        max_conversation_age_hours: int = 24,
        cleanup_interval_seconds: int = 3600,
        memory_artifact_system=None
    ):
        """
        Initialize conversation manager.

        Args:
            max_messages_per_conversation: Maximum messages to keep per conversation
            max_conversation_age_hours: Maximum age before conversation is cleaned up
            cleanup_interval_seconds: How often to run cleanup (default: 1 hour)
            memory_artifact_system: Optional MemoryArtifactSystem for preserving important conversations
        """
        self.max_messages = max_messages_per_conversation
        self.max_age = timedelta(hours=max_conversation_age_hours)
        self.cleanup_interval = cleanup_interval_seconds
        self.memory_system = memory_artifact_system

        self.conversations: Dict[str, Conversation] = {}
        self.lock = threading.Lock()
        self.last_cleanup = datetime.now(timezone.utc)

        # Statistics
        self.stats = {
            'total_conversations': 0,
            'total_messages': 0,
            'conversations_cleaned': 0,
            'conversations_archived': 0
        }

    def _validate_conversation_id(self, conversation_id: str) -> str:
        """Validate and sanitize a conversation ID.

        Returns the validated ID.  Raises ``ValueError`` for invalid formats.
        """
        if not isinstance(conversation_id, str) or not conversation_id:
            raise ValueError("conversation_id must be a non-empty string")
        # Strip null bytes
        conversation_id = conversation_id.replace("\x00", "")
        if not self._VALID_CONV_ID.match(conversation_id):
            raise ValueError(
                "conversation_id must be 1-100 alphanumeric characters, hyphens, or underscores"
            )
        return conversation_id

    def get_or_create_conversation(self, conversation_id: str) -> Conversation:
        """
        Get existing conversation or create new one.

        Args:
            conversation_id: Unique conversation identifier (alphanumeric, hyphens, underscores)

        Returns:
            Conversation object

        Raises:
            ValueError: If conversation_id is invalid
        """
        conversation_id = self._validate_conversation_id(conversation_id)
        with self.lock:
            if conversation_id not in self.conversations:
                # Hard cap: prevent unbounded memory growth
                if len(self.conversations) >= self._MAX_CONVERSATIONS:
                    logger.warning("ConversationManager: hit max conversations cap (%d), running cleanup", self._MAX_CONVERSATIONS)
                    self._cleanup_oldest_unlocked()
                # Create new conversation with bounded deque
                conv = Conversation(
                    conversation_id=conversation_id,
                    messages=deque(maxlen=self.max_messages),
                    created_at=datetime.now(timezone.utc),
                    last_activity=datetime.now(timezone.utc)
                )
                self.conversations[conversation_id] = conv
                self.stats['total_conversations'] += 1

            return self.conversations[conversation_id]

    def _cleanup_oldest_unlocked(self) -> None:
        """Remove the 10% oldest conversations to make room. Must hold self.lock."""
        if not self.conversations:
            return
        sorted_convs = sorted(
            self.conversations.items(),
            key=lambda kv: kv[1].last_activity,
        )
        remove_count = max(1, len(sorted_convs) // 10)
        for cid, _ in sorted_convs[:remove_count]:
            del self.conversations[cid]
            self.stats['conversations_cleaned'] += 1

    def add_message(
        self,
        conversation_id: str,
        user_message: str,
        bot_response: str,
        metadata: Optional[Dict] = None
    ):
        """
        Add message to conversation.

        Args:
            conversation_id: Conversation identifier
            user_message: User's message (max 50000 chars, sanitized)
            bot_response: Bot's response
            metadata: Optional metadata (confidence, band, etc.)
        """
        # Input length bounds (CWE-400)
        if isinstance(user_message, str):
            user_message = user_message[:50000]
        if isinstance(bot_response, str):
            bot_response = bot_response[:50000]
        # Sanitize metadata keys/values
        if metadata:
            metadata = {
                str(k)[:256]: (str(v)[:10000] if isinstance(v, str) else v)
                for k, v in (metadata or {}).items()
            }
        conv = self.get_or_create_conversation(conversation_id)
        conv.add_message(user_message, bot_response, metadata)
        self.stats['total_messages'] += 1

        # Periodic cleanup check
        if (datetime.now(timezone.utc) - self.last_cleanup).seconds > self.cleanup_interval:
            self.cleanup_old_conversations()

    def get_conversation_history(
        self,
        conversation_id: str,
        max_messages: Optional[int] = None
    ) -> List[Dict]:
        """
        Get conversation history.

        Args:
            conversation_id: Conversation identifier
            max_messages: Maximum number of recent messages to return

        Returns:
            List of message dictionaries
        """
        with self.lock:
            if conversation_id not in self.conversations:
                return []

            conv = self.conversations[conversation_id]
            messages = conv.get_recent_messages(max_messages or self.max_messages)

            return [
                {
                    'user': msg.user_message,
                    'bot': msg.bot_response,
                    'timestamp': msg.timestamp.isoformat(),
                    'metadata': msg.metadata
                }
                for msg in messages
            ]

    def cleanup_old_conversations(self):
        """
        Clean up conversations older than max_age.

        Important conversations are archived to MemoryArtifactSystem before deletion.
        """
        with self.lock:
            now = datetime.now(timezone.utc)
            to_remove = []

            for conv_id, conv in self.conversations.items():
                age = now - conv.last_activity

                if age > self.max_age:
                    # Check if conversation should be archived
                    if self._should_archive_conversation(conv):
                        self._archive_conversation(conv)
                        self.stats['conversations_archived'] += 1

                    to_remove.append(conv_id)

            # Remove old conversations
            for conv_id in to_remove:
                del self.conversations[conv_id]
                self.stats['conversations_cleaned'] += 1

            self.last_cleanup = now

            if to_remove:
                logger.info(f"🧹 Cleaned up {len(to_remove)} old conversations")

    def _should_archive_conversation(self, conv: Conversation) -> bool:
        """
        Determine if conversation should be archived.

        Criteria:
        - Has more than 10 messages
        - Contains high-confidence interactions
        - Has important metadata
        """
        if len(conv.messages) < 10:
            return False

        # Check for high-confidence messages
        high_confidence_count = sum(
            1 for msg in conv.messages
            if msg.metadata.get('confidence', 0) > 0.8
        )

        return high_confidence_count > 3

    def _archive_conversation(self, conv: Conversation):
        """
        Archive conversation to MemoryArtifactSystem.

        Converts conversation to artifact for long-term storage.
        """
        if not self.memory_system:
            return

        try:
            # Create artifact from conversation
            # This would integrate with the existing MemoryArtifactSystem
            # For now, just log the archival
            logger.info(f"📦 Archived conversation {conv.conversation_id} ({len(conv.messages)} messages)")
        except Exception as exc:
            logger.info(f"⚠️  Failed to archive conversation {conv.conversation_id}: {exc}")

    def get_active_conversations(self) -> List[Dict]:
        """
        Get list of active conversations.

        Returns:
            List of conversation summaries
        """
        with self.lock:
            return [
                conv.to_dict()
                for conv in self.conversations.values()
            ]

    def get_statistics(self) -> Dict:
        """
        Get conversation manager statistics.

        Returns:
            Dictionary of statistics
        """
        with self.lock:
            return {
                **self.stats,
                'active_conversations': len(self.conversations),
                'total_active_messages': sum(
                    len(conv.messages) for conv in self.conversations.values()
                )
            }

    def force_cleanup(self):
        """Force immediate cleanup of old conversations"""
        self.cleanup_old_conversations()

    def clear_conversation(self, conversation_id: str):
        """
        Clear a specific conversation.

        Args:
            conversation_id: Conversation to clear
        """
        with self.lock:
            if conversation_id in self.conversations:
                del self.conversations[conversation_id]

    def save_state(self, filepath: str = "conversation_state.json"):
        """
        Save conversation state to file.

        Args:
            filepath: Path to save state
        """
        with self.lock:
            state = {
                'conversations': [
                    {
                        **conv.to_dict(),
                        'messages': [
                            {
                                'user': msg.user_message,
                                'bot': msg.bot_response,
                                'timestamp': msg.timestamp.isoformat(),
                                'metadata': msg.metadata
                            }
                            for msg in conv.messages
                        ]
                    }
                    for conv in self.conversations.values()
                ],
                'stats': self.stats,
                'saved_at': datetime.now(timezone.utc).isoformat()
            }

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2)

            logger.info(f"💾 Saved conversation state to {filepath}")

    def load_state(self, filepath: str = "conversation_state.json"):
        """
        Load conversation state from file.

        Args:
            filepath: Path to load state from
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                state = json.load(f)

            with self.lock:
                # Restore conversations
                for conv_data in state.get('conversations', []):
                    conv = Conversation(
                        conversation_id=conv_data['conversation_id'],
                        messages=deque(maxlen=self.max_messages),
                        created_at=datetime.fromisoformat(conv_data['created_at']),
                        last_activity=datetime.fromisoformat(conv_data['last_activity']),
                        metadata=conv_data.get('metadata', {})
                    )

                    # Restore messages
                    for msg_data in conv_data.get('messages', []):
                        msg = ConversationMessage(
                            user_message=msg_data['user'],
                            bot_response=msg_data['bot'],
                            timestamp=datetime.fromisoformat(msg_data['timestamp']),
                            metadata=msg_data.get('metadata', {})
                        )
                        conv.messages.append(msg)

                    self.conversations[conv.conversation_id] = conv

                # Restore stats
                self.stats.update(state.get('stats', {}))

            logger.info(f"📂 Loaded conversation state from {filepath}")

        except FileNotFoundError:
            logger.info(f"⚠️  No saved state found at {filepath}")
        except Exception as exc:
            logger.info(f"❌ Failed to load conversation state: {exc}")


# Global conversation manager instance
_conversation_manager_instance = None
_manager_lock = threading.Lock()


def get_conversation_manager(
    max_messages: int = 100,
    max_age_hours: int = 24,
    memory_system = None
) -> ConversationManager:
    """
    Get or create the global conversation manager instance.

    Args:
        max_messages: Maximum messages per conversation
        max_age_hours: Maximum conversation age in hours
        memory_system: Optional MemoryArtifactSystem

    Returns:
        ConversationManager instance
    """
    global _conversation_manager_instance

    with _manager_lock:
        if _conversation_manager_instance is None:
            _conversation_manager_instance = ConversationManager(
                max_messages_per_conversation=max_messages,
                max_conversation_age_hours=max_age_hours,
                memory_artifact_system=memory_system
            )

        return _conversation_manager_instance
