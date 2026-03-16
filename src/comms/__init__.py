"""
Communication Connectors & Governance Layer

This module provides safe communication handling where:
- ALL inbound messages are stored as artifacts (never trigger execution)
- ALL outbound messages require Control Plane authorization
- PII is redacted and audit trails are maintained
- Human signoff required for external communications

Components:
- schemas: Core data models (MessageArtifact, CommunicationPacket, etc.)
- connectors: Communication channel connectors (Email, Slack, Teams, SMS, Tickets)
- pipeline: Message processing pipeline (ingestion, classification, redaction)
- governance: Authorization and safety enforcement
- compliance: Privacy, retention, and audit
"""

from .schemas import (
    Channel,
    CommunicationPacket,
    IntentClassification,
    MessageArtifact,
    RedactionRule,
    RetentionPolicy,
)

__all__ = [
    "MessageArtifact",
    "CommunicationPacket",
    "IntentClassification",
    "Channel",
    "RedactionRule",
    "RetentionPolicy",
]
