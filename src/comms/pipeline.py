"""
Message Artifact Pipeline

Processes inbound messages:
1. Ingestion - Convert to MessageArtifact
2. Classification - Determine intent
3. Redaction - Remove PII
4. Storage - Store with retention policy
5. Threading - Track conversations

CRITICAL: Pipeline NEVER triggers execution. Only creates artifacts.
"""

import logging
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from .schemas import (
    Channel,
    IntentClassification,
    MessageArtifact,
    RedactionRule,
    RetentionPolicy,
    ThreadContext,
)

logger = logging.getLogger(__name__)


class MessageIngestor:
    """
    Ingests messages from connectors and creates MessageArtifacts

    CRITICAL: Ingestion NEVER triggers execution.
    """

    def __init__(self):
        self.ingested_count = 0

    def ingest(self, messages: List[MessageArtifact]) -> List[MessageArtifact]:
        """
        Ingest messages and prepare for processing

        Args:
            messages: List of MessageArtifacts from connectors

        Returns:
            List of ingested MessageArtifacts
        """
        ingested = []

        for message in messages:
            # Verify message is safe (cannot trigger execution)
            if message.triggers_execution:
                raise ValueError(f"Message {message.message_id} has triggers_execution=True")

            # Add to ingested list
            ingested.append(message)
            self.ingested_count += 1

        return ingested


class IntentClassifier:
    """
    Classifies message intent using pattern matching and keywords

    Intent types:
    - QUESTION: Asking for information
    - APPROVAL_REQUEST: Requesting approval
    - APPROVAL_GRANT: Granting approval (BLOCKED for execution)
    - DENIAL: Denying request
    - CLARIFICATION: Seeking clarification
    - INFORMATION: Providing information
    - ESCALATION: Escalating issue
    - REPORT: Status report
    """

    def __init__(self):
        # Intent patterns (keyword-based)
        self.patterns = {
            IntentClassification.QUESTION: [
                r'\?',
                r'\bwhat\b',
                r'\bwhy\b',
                r'\bhow\b',
                r'\bwhen\b',
                r'\bwhere\b',
                r'\bwho\b',
                r'\bcan you\b',
                r'\bcould you\b',
            ],
            IntentClassification.APPROVAL_REQUEST: [
                r'\bplease approve\b',
                r'\brequest approval\b',
                r'\bneed approval\b',
                r'\bcan you approve\b',
                r'\bapproval needed\b',
            ],
            IntentClassification.APPROVAL_GRANT: [
                r'\bi approve\b',
                r'\bapproved\b',
                r'\bgo ahead\b',
                r'\bauthorized\b',
                r'\bsign off\b',
            ],
            IntentClassification.DENIAL: [
                r'\bdenied\b',
                r'\breject\b',
                r'\bcannot approve\b',
                r'\bdo not approve\b',
                r'\bnot approved\b',
            ],
            IntentClassification.CLARIFICATION: [
                r'\bcan you clarify\b',
                r'\bneed clarification\b',
                r'\bplease explain\b',
                r'\bnot clear\b',
                r'\bconfused\b',
            ],
            IntentClassification.ESCALATION: [
                r'\bescalate\b',
                r'\bneed help\b',
                r'\bmanager\b',
                r'\bsupervisor\b',
                r'\burgent\b',
            ],
            IntentClassification.REPORT: [
                r'\bstatus\b',
                r'\bupdate\b',
                r'\breport\b',
                r'\bprogress\b',
                r'\bsummary\b',
            ],
        }

    def classify(self, message: MessageArtifact) -> IntentClassification:
        """
        Classify message intent

        Args:
            message: MessageArtifact to classify

        Returns:
            IntentClassification
        """
        content = message.content_redacted.lower()

        # Check each intent pattern
        for intent, patterns in self.patterns.items():
            for pattern in patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    return intent

        # Default to INFORMATION if no pattern matches
        return IntentClassification.INFORMATION

    def classify_batch(self, messages: List[MessageArtifact]) -> List[MessageArtifact]:
        """Classify a batch of messages"""
        for message in messages:
            if message.intent == IntentClassification.UNKNOWN:
                message.intent = self.classify(message)

        return messages


class RedactionPipeline:
    """
    Redacts PII from message content

    Supports:
    - Email addresses
    - Phone numbers
    - SSN
    - Credit card numbers
    - Custom patterns
    """

    def __init__(self):
        # Default redaction rules
        self.rules = [
            RedactionRule(
                rule_id='email',
                pattern=r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
                replacement='[EMAIL_REDACTED]',
                pii_type='email'
            ),
            RedactionRule(
                rule_id='phone',
                pattern=r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',
                replacement='[PHONE_REDACTED]',
                pii_type='phone'
            ),
            RedactionRule(
                rule_id='ssn',
                pattern=r'\b\d{3}-\d{2}-\d{4}\b',
                replacement='[SSN_REDACTED]',
                pii_type='ssn'
            ),
            RedactionRule(
                rule_id='credit_card',
                pattern=r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b',
                replacement='[CC_REDACTED]',
                pii_type='credit_card'
            ),
        ]

    def add_rule(self, rule: RedactionRule):
        """Add custom redaction rule"""
        self.rules.append(rule)

    def redact(self, text: str) -> str:
        """
        Redact PII from text

        Args:
            text: Text to redact

        Returns:
            Redacted text
        """
        redacted = text

        for rule in self.rules:
            if rule.enabled:
                redacted = rule.apply(redacted)

        return redacted

    def redact_message(self, message: MessageArtifact) -> MessageArtifact:
        """Redact PII from message"""
        if message.content_original:
            message.content_redacted = self.redact(message.content_original)

        return message

    def redact_batch(self, messages: List[MessageArtifact]) -> List[MessageArtifact]:
        """Redact a batch of messages"""
        for message in messages:
            self.redact_message(message)

        return messages


class MessageStorage:
    """
    Stores messages with retention policy

    Storage tiers:
    - Hot: Recent messages (fast access)
    - Warm: Archived messages (slower access)
    - Cold: Long-term storage (slowest access)
    """

    def __init__(self):
        self.hot_storage: Dict[str, MessageArtifact] = {}
        self.warm_storage: Dict[str, MessageArtifact] = {}
        self.retention_policies: Dict[Channel, RetentionPolicy] = {}

    def set_retention_policy(self, channel: Channel, policy: RetentionPolicy):
        """Set retention policy for channel"""
        self.retention_policies[channel] = policy

    def store(self, message: MessageArtifact):
        """Store message in hot storage"""
        self.hot_storage[message.message_id] = message

    def store_batch(self, messages: List[MessageArtifact]):
        """Store batch of messages"""
        for message in messages:
            self.store(message)

    def get(self, message_id: str) -> Optional[MessageArtifact]:
        """Retrieve message by ID"""
        # Check hot storage first
        if message_id in self.hot_storage:
            return self.hot_storage[message_id]

        # Check warm storage
        if message_id in self.warm_storage:
            return self.warm_storage[message_id]

        return None

    def apply_retention_policies(self):
        """Apply retention policies to stored messages"""
        now = datetime.now(timezone.utc)

        for message_id, message in list(self.hot_storage.items()):
            policy = self.retention_policies.get(message.channel)
            if not policy:
                continue

            age_days = (now - message.created_at).days

            # Archive to warm storage
            if age_days >= policy.archive_after_days:
                self.warm_storage[message_id] = message
                del self.hot_storage[message_id]

            # Delete from warm storage
            if age_days >= policy.delete_after_days:
                if message_id in self.warm_storage:
                    del self.warm_storage[message_id]

    def get_messages_by_thread(self, thread_id: str) -> List[MessageArtifact]:
        """Get all messages in a thread"""
        messages = []

        # Search hot storage
        for message in self.hot_storage.values():
            if message.thread_id == thread_id:
                messages.append(message)

        # Search warm storage
        for message in self.warm_storage.values():
            if message.thread_id == thread_id:
                messages.append(message)

        # Sort by timestamp
        messages.sort(key=lambda m: m.timestamp)

        return messages


class ThreadManager:
    """
    Manages conversation threads

    Tracks:
    - Thread participants
    - Message history
    - Thread intent
    - Response requirements
    """

    def __init__(self):
        self.threads: Dict[str, ThreadContext] = {}

    def get_or_create_thread(self, thread_id: str, channel: Channel) -> ThreadContext:
        """Get existing thread or create new one"""
        if thread_id not in self.threads:
            self.threads[thread_id] = ThreadContext(
                thread_id=thread_id,
                channel=channel,
                participants=[]
            )

        return self.threads[thread_id]

    def add_message_to_thread(self, message: MessageArtifact):
        """Add message to thread"""
        thread = self.get_or_create_thread(message.thread_id, message.channel)

        # Add participants
        if message.sender_hash not in thread.participants:
            thread.participants.append(message.sender_hash)
        if message.recipient_hash not in thread.participants:
            thread.participants.append(message.recipient_hash)

        # Add message
        thread.add_message(message)

        # Update response requirement
        if message.intent in [
            IntentClassification.QUESTION,
            IntentClassification.APPROVAL_REQUEST,
            IntentClassification.CLARIFICATION,
            IntentClassification.ESCALATION
        ]:
            thread.requires_response = True

    def get_thread(self, thread_id: str) -> Optional[ThreadContext]:
        """Get thread by ID"""
        return self.threads.get(thread_id)

    def get_threads_requiring_response(self) -> List[ThreadContext]:
        """Get all threads requiring response"""
        return [t for t in self.threads.values() if t.requires_response]

    def get_threads_by_channel(self, channel: Channel) -> List[ThreadContext]:
        """Get all threads for a channel"""
        return [t for t in self.threads.values() if t.channel == channel]


class MessagePipeline:
    """
    Complete message processing pipeline

    Pipeline stages:
    1. Ingestion
    2. Classification
    3. Redaction
    4. Storage
    5. Threading
    """

    def __init__(self):
        self.ingestor = MessageIngestor()
        self.classifier = IntentClassifier()
        self.redactor = RedactionPipeline()
        self.storage = MessageStorage()
        self.thread_manager = ThreadManager()

    def process(self, messages: List[MessageArtifact]) -> List[MessageArtifact]:
        """
        Process messages through complete pipeline

        Args:
            messages: Raw messages from connectors

        Returns:
            Processed messages
        """
        # 1. Ingest
        messages = self.ingestor.ingest(messages)

        # 2. Classify intent
        messages = self.classifier.classify_batch(messages)

        # 3. Redact PII
        messages = self.redactor.redact_batch(messages)

        # 4. Store
        self.storage.store_batch(messages)

        # 5. Add to threads
        for message in messages:
            self.thread_manager.add_message_to_thread(message)

        return messages

    def get_thread_context(self, thread_id: str) -> Optional[ThreadContext]:
        """Get thread context"""
        return self.thread_manager.get_thread(thread_id)

    def get_pending_threads(self) -> List[ThreadContext]:
        """Get threads requiring response"""
        return self.thread_manager.get_threads_requiring_response()
