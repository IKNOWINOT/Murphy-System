"""
Test Suite for Conversation Manager
Tests bounded history, cleanup, and state persistence
"""

import pytest
import time
from datetime import datetime, timedelta, timezone
from collections import deque
import os

# Add src to path

from conversation_manager import (
    ConversationManager, Conversation, ConversationMessage,
    get_conversation_manager
)


class TestConversationMessage:
    """Test ConversationMessage dataclass"""

    def test_message_creation(self):
        """Test creating a conversation message"""
        msg = ConversationMessage(
            user_message="Hello",
            bot_response="Hi there!",
            timestamp=datetime.now(timezone.utc),
            metadata={'confidence': 0.9}
        )

        assert msg.user_message == "Hello"
        assert msg.bot_response == "Hi there!"
        assert msg.metadata['confidence'] == 0.9


class TestConversation:
    """Test Conversation dataclass"""

    def test_conversation_creation(self):
        """Test creating a conversation"""
        conv = Conversation(
            conversation_id="test-123",
            messages=deque(maxlen=10),
            created_at=datetime.now(timezone.utc),
            last_activity=datetime.now(timezone.utc)
        )

        assert conv.conversation_id == "test-123"
        assert len(conv.messages) == 0
        assert conv.messages.maxlen == 10

    def test_add_message(self):
        """Test adding messages to conversation"""
        conv = Conversation(
            conversation_id="test-123",
            messages=deque(maxlen=10),
            created_at=datetime.now(timezone.utc),
            last_activity=datetime.now(timezone.utc)
        )

        conv.add_message("Hello", "Hi", {'confidence': 0.9})

        assert len(conv.messages) == 1
        assert conv.messages[0].user_message == "Hello"
        assert conv.messages[0].bot_response == "Hi"

    def test_bounded_messages(self):
        """Test that messages are bounded by maxlen"""
        conv = Conversation(
            conversation_id="test-123",
            messages=deque(maxlen=5),
            created_at=datetime.now(timezone.utc),
            last_activity=datetime.now(timezone.utc)
        )

        # Add 10 messages (more than maxlen)
        for i in range(10):
            conv.add_message(f"Message {i}", f"Response {i}")

        # Should only keep last 5
        assert len(conv.messages) == 5
        assert conv.messages[0].user_message == "Message 5"
        assert conv.messages[-1].user_message == "Message 9"

    def test_get_recent_messages(self):
        """Test getting recent messages"""
        conv = Conversation(
            conversation_id="test-123",
            messages=deque(maxlen=100),
            created_at=datetime.now(timezone.utc),
            last_activity=datetime.now(timezone.utc)
        )

        # Add 20 messages
        for i in range(20):
            conv.add_message(f"Message {i}", f"Response {i}")

        # Get last 10
        recent = conv.get_recent_messages(10)

        assert len(recent) == 10
        assert recent[0].user_message == "Message 10"
        assert recent[-1].user_message == "Message 19"


class TestConversationManager:
    """Test ConversationManager class"""

    @pytest.fixture
    def manager(self):
        """Create a fresh conversation manager for each test"""
        return ConversationManager(
            max_messages_per_conversation=10,
            max_conversation_age_hours=1,
            cleanup_interval_seconds=3600
        )

    def test_manager_initialization(self, manager):
        """Test manager initialization"""
        assert manager.max_messages == 10
        assert manager.max_age == timedelta(hours=1)
        assert len(manager.conversations) == 0
        assert manager.stats['total_conversations'] == 0

    def test_get_or_create_conversation(self, manager):
        """Test getting or creating conversations"""
        conv1 = manager.get_or_create_conversation("test-1")

        assert conv1.conversation_id == "test-1"
        assert len(manager.conversations) == 1
        assert manager.stats['total_conversations'] == 1

        # Get same conversation again
        conv2 = manager.get_or_create_conversation("test-1")

        assert conv1 is conv2
        assert len(manager.conversations) == 1
        assert manager.stats['total_conversations'] == 1

    def test_add_message(self, manager):
        """Test adding messages"""
        manager.add_message(
            "test-1",
            "Hello",
            "Hi there!",
            {'confidence': 0.9}
        )

        assert len(manager.conversations) == 1
        assert manager.stats['total_messages'] == 1

        conv = manager.conversations["test-1"]
        assert len(conv.messages) == 1
        assert conv.messages[0].user_message == "Hello"

    def test_bounded_history(self, manager):
        """Test that history is bounded"""
        # Add 20 messages (more than max_messages=10)
        for i in range(20):
            manager.add_message(
                "test-1",
                f"Message {i}",
                f"Response {i}"
            )

        conv = manager.conversations["test-1"]

        # Should only keep last 10
        assert len(conv.messages) == 10
        assert conv.messages[0].user_message == "Message 10"
        assert conv.messages[-1].user_message == "Message 19"

    def test_get_conversation_history(self, manager):
        """Test getting conversation history"""
        # Add messages
        for i in range(5):
            manager.add_message("test-1", f"Message {i}", f"Response {i}")

        history = manager.get_conversation_history("test-1")

        assert len(history) == 5
        assert history[0]['user'] == "Message 0"
        assert history[-1]['user'] == "Message 4"

    def test_get_conversation_history_with_limit(self, manager):
        """Test getting limited conversation history"""
        # Add 10 messages
        for i in range(10):
            manager.add_message("test-1", f"Message {i}", f"Response {i}")

        # Get only last 3
        history = manager.get_conversation_history("test-1", max_messages=3)

        assert len(history) == 3
        assert history[0]['user'] == "Message 7"
        assert history[-1]['user'] == "Message 9"

    def test_cleanup_old_conversations(self, manager):
        """Test cleanup of old conversations"""
        # Create old conversation
        old_conv = Conversation(
            conversation_id="old",
            messages=deque(maxlen=10),
            created_at=datetime.now(timezone.utc) - timedelta(hours=2),
            last_activity=datetime.now(timezone.utc) - timedelta(hours=2)
        )
        manager.conversations["old"] = old_conv

        # Create recent conversation
        manager.add_message("recent", "Hello", "Hi")

        # Run cleanup
        manager.cleanup_old_conversations()

        # Old conversation should be removed
        assert "old" not in manager.conversations
        assert "recent" in manager.conversations
        assert manager.stats['conversations_cleaned'] == 1

    def test_clear_conversation(self, manager):
        """Test clearing a specific conversation"""
        manager.add_message("test-1", "Hello", "Hi")
        manager.add_message("test-2", "Hello", "Hi")

        assert len(manager.conversations) == 2

        manager.clear_conversation("test-1")

        assert len(manager.conversations) == 1
        assert "test-1" not in manager.conversations
        assert "test-2" in manager.conversations

    def test_get_active_conversations(self, manager):
        """Test getting active conversations"""
        manager.add_message("test-1", "Hello", "Hi")
        manager.add_message("test-2", "Hello", "Hi")

        active = manager.get_active_conversations()

        assert len(active) == 2
        assert any(c['conversation_id'] == 'test-1' for c in active)
        assert any(c['conversation_id'] == 'test-2' for c in active)

    def test_get_statistics(self, manager):
        """Test getting statistics"""
        manager.add_message("test-1", "Hello", "Hi")
        manager.add_message("test-1", "How are you?", "Good!")
        manager.add_message("test-2", "Hello", "Hi")

        stats = manager.get_statistics()

        assert stats['active_conversations'] == 2
        assert stats['total_active_messages'] == 3
        assert stats['total_messages'] == 3

    def test_force_cleanup(self, manager):
        """Test forcing cleanup"""
        # Create old conversation
        old_conv = Conversation(
            conversation_id="old",
            messages=deque(maxlen=10),
            created_at=datetime.now(timezone.utc) - timedelta(hours=2),
            last_activity=datetime.now(timezone.utc) - timedelta(hours=2)
        )
        manager.conversations["old"] = old_conv

        manager.force_cleanup()

        assert "old" not in manager.conversations

    def test_state_persistence(self, manager, tmp_path):
        """Test saving and loading state"""
        # Add conversations
        manager.add_message("test-1", "Hello", "Hi")
        manager.add_message("test-2", "Goodbye", "Bye")

        # Save state
        state_file = tmp_path / "test_state.json"
        manager.save_state(str(state_file))

        assert state_file.exists()

        # Create new manager and load state
        new_manager = ConversationManager(
            max_messages_per_conversation=10,
            max_conversation_age_hours=1
        )
        new_manager.load_state(str(state_file))

        # Verify conversations restored
        assert len(new_manager.conversations) == 2
        assert "test-1" in new_manager.conversations
        assert "test-2" in new_manager.conversations

        # Verify messages restored
        conv1 = new_manager.conversations["test-1"]
        assert len(conv1.messages) == 1
        assert conv1.messages[0].user_message == "Hello"


class TestGlobalConversationManager:
    """Test global conversation manager singleton"""

    def test_get_conversation_manager(self):
        """Test getting global manager"""
        manager1 = get_conversation_manager()
        manager2 = get_conversation_manager()

        # Should be same instance
        assert manager1 is manager2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
