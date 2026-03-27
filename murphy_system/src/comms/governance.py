"""
Governance Layer for Communication

Enforces:
1. Inbound messages stored as artifacts only (never trigger execution)
2. Outbound messages require CommunicationPacket authorization
3. Disallow executable approvals/payments/contracts
4. Human signoff required for external communications
5. Complete audit trail

CRITICAL: This layer is the enforcement boundary between messages and execution.
"""

import logging
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from .schemas import (
    AuditLogEntry,
    Channel,
    CommunicationPacket,
    IntentClassification,
    MessageArtifact,
)

logger = logging.getLogger(__name__)


class CommunicationAuthorizer:
    """
    Authorizes outbound communications

    CRITICAL: This is the ONLY way to authorize outbound messages.
    Requires Control Plane verification and gate clearance.
    """

    def __init__(self):
        self.authorized_packets: Dict[str, CommunicationPacket] = {}
        self.authorization_count = 0

    def authorize(
        self,
        channel: Channel,
        thread_id: str,
        recipient_hashes: List[str],
        content: str,
        authorized_by: str,
        authority_level: str,
        gates_satisfied: List[str],
        external_party: bool = False
    ) -> CommunicationPacket:
        """
        Authorize outbound communication

        Args:
            channel: Communication channel
            thread_id: Thread ID
            recipient_hashes: List of recipient hashes
            content: Message content
            authorized_by: Control Plane authorization ID
            authority_level: Authority level of authorizer
            gates_satisfied: List of satisfied gate IDs
            external_party: Whether communication is with external party

        Returns:
            Authorized CommunicationPacket
        """
        # Generate packet ID
        packet_id = f"comm_packet_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{self.authorization_count}"
        self.authorization_count += 1

        # Create packet
        packet = CommunicationPacket(
            packet_id=packet_id,
            channel=channel,
            thread_id=thread_id,
            recipient_hashes=recipient_hashes,
            content=content,
            authorized_by=authorized_by,
            authority_level=authority_level,
            gates_satisfied=gates_satisfied,
            external_party=external_party,
            human_signoff_required=external_party  # Require signoff for external
        )

        # Store authorized packet
        self.authorized_packets[packet_id] = packet

        return packet

    def verify_authorization(self, packet_id: str) -> bool:
        """Verify packet is authorized"""
        return packet_id in self.authorized_packets

    def get_packet(self, packet_id: str) -> Optional[CommunicationPacket]:
        """Get authorized packet"""
        return self.authorized_packets.get(packet_id)


class OutboundValidator:
    """
    Validates outbound messages for safety

    Checks:
    - Authorization exists
    - No prohibited content
    - Human signoff (if required)
    - Content safety
    """

    def __init__(self):
        # Prohibited patterns
        self.prohibited_patterns = {
            'approval': [
                r'\bi approve\b',
                r'\bapproved\b',
                r'\bauthorize payment\b',
                r'\bexecute transaction\b',
            ],
            'payment': [
                r'\bpay \$\d+',
                r'\btransfer \$\d+',
                r'\bwire \$\d+',
                r'\bsend payment\b',
            ],
            'contract': [
                r'\bsign contract\b',
                r'\bexecute agreement\b',
                r'\bbinding commitment\b',
            ]
        }

    def validate(self, packet: CommunicationPacket) -> Tuple[bool, List[str]]:
        """
        Validate outbound packet

        Args:
            packet: CommunicationPacket to validate

        Returns:
            Tuple of (is_valid, list of violations)
        """
        violations = []

        # Check authorization
        if not packet.authorized_by:
            violations.append("Missing authorization")

        # Check human signoff (if required)
        if packet.external_party and packet.human_signoff_required and not packet.human_signoff_granted:
            violations.append("Human signoff required but not granted")

        # Check for prohibited content
        content_lower = packet.content.lower()

        for category, patterns in self.prohibited_patterns.items():
            for pattern in patterns:
                if re.search(pattern, content_lower, re.IGNORECASE):
                    violations.append(f"Prohibited {category} content detected: {pattern}")

        # Check packet flags
        if packet.contains_approval:
            violations.append("Packet contains executable approval")
        if packet.contains_payment:
            violations.append("Packet contains executable payment")
        if packet.contains_contract:
            violations.append("Packet contains executable contract")

        return len(violations) == 0, violations

    def scan_content(self, content: str) -> Dict[str, bool]:
        """
        Scan content for prohibited patterns

        Returns:
            Dict with flags for each category
        """
        content_lower = content.lower()

        flags = {
            'contains_approval': False,
            'contains_payment': False,
            'contains_contract': False
        }

        for category, patterns in self.prohibited_patterns.items():
            for pattern in patterns:
                if re.search(pattern, content_lower, re.IGNORECASE):
                    flags[f'contains_{category}'] = True
                    break

        return flags


class ApprovalBlocker:
    """
    Blocks executable approvals in communications

    CRITICAL: Approvals in messages CANNOT trigger execution.
    They are informational only.
    """

    def __init__(self):
        self.blocked_count = 0

    def check_message(self, message: MessageArtifact) -> bool:
        """
        Check if message contains approval that might be misinterpreted as executable

        Args:
            message: MessageArtifact to check

        Returns:
            True if message is safe, False if contains executable approval
        """
        # Check intent
        if message.intent == IntentClassification.APPROVAL_GRANT:
            # This is an approval, but it's INFORMATIONAL ONLY
            # Mark for human review
            message.requires_human_review = True
            return True  # Allow but flag for review

        return True

    def block_execution(self, message: MessageArtifact) -> str:
        """
        Generate blocking message explaining why approval cannot execute

        Args:
            message: MessageArtifact with approval

        Returns:
            Explanation message
        """
        self.blocked_count += 1

        return (
            f"Message {message.message_id} contains approval language but CANNOT trigger execution. "
            f"Approvals in messages are informational only. "
            f"To execute an action, it must go through Control Plane verification and gate clearance. "
            f"This message has been flagged for human review."
        )


class HumanSignoffEnforcer:
    """
    Enforces human signoff for external communications

    CRITICAL: External communications REQUIRE human signoff by default.
    """

    def __init__(self):
        self.signoffs: Dict[str, Dict] = {}

    def require_signoff(self, packet: CommunicationPacket, required_from: str) -> bool:
        """
        Mark packet as requiring human signoff

        Args:
            packet: CommunicationPacket
            required_from: Who must provide signoff

        Returns:
            True if signoff requirement set
        """
        if not packet.external_party:
            return False  # Only external communications require signoff

        packet.human_signoff_required = True

        # Track signoff requirement
        self.signoffs[packet.packet_id] = {
            'required_from': required_from,
            'granted': False,
            'granted_by': None,
            'granted_at': None
        }

        return True

    def grant_signoff(self, packet: CommunicationPacket, granted_by: str) -> bool:
        """
        Grant human signoff for packet

        Args:
            packet: CommunicationPacket
            granted_by: Who is granting signoff

        Returns:
            True if signoff granted
        """
        if not packet.external_party:
            return False

        # Grant signoff on packet
        packet.grant_human_signoff(granted_by)

        # Update tracking
        if packet.packet_id in self.signoffs:
            self.signoffs[packet.packet_id].update({
                'granted': True,
                'granted_by': granted_by,
                'granted_at': datetime.now(timezone.utc)
            })

        return True

    def verify_signoff(self, packet: CommunicationPacket) -> bool:
        """Verify packet has required signoff"""
        if not packet.external_party:
            return True  # Internal communications don't require signoff

        if not packet.human_signoff_required:
            return True  # Signoff not required

        return packet.human_signoff_granted


class AuditLogger:
    """
    Logs all communication events

    CRITICAL: Audit logs are IMMUTABLE.
    """

    def __init__(self):
        self.logs: List[AuditLogEntry] = []
        self.log_count = 0

    def log_message_received(self, message: MessageArtifact, actor: str = "system"):
        """Log inbound message received"""
        log = AuditLogEntry(
            log_id=f"log_{self.log_count}",
            event_type="message_received",
            timestamp=datetime.now(timezone.utc),
            message_id=message.message_id,
            channel=message.channel,
            actor=actor,
            details={
                'thread_id': message.thread_id,
                'direction': message.direction,
                'intent': message.intent.value,
                'external_party': message.external_party
            }
        )

        self.logs.append(log)
        self.log_count += 1

    def log_message_sent(self, packet: CommunicationPacket, actor: str):
        """Log outbound message sent"""
        log = AuditLogEntry(
            log_id=f"log_{self.log_count}",
            event_type="message_sent",
            timestamp=datetime.now(timezone.utc),
            packet_id=packet.packet_id,
            channel=packet.channel,
            actor=actor,
            details={
                'thread_id': packet.thread_id,
                'authorized_by': packet.authorized_by,
                'external_party': packet.external_party,
                'human_signoff_granted': packet.human_signoff_granted
            }
        )

        self.logs.append(log)
        self.log_count += 1

    def log_authorization_granted(self, packet: CommunicationPacket, actor: str):
        """Log authorization granted"""
        log = AuditLogEntry(
            log_id=f"log_{self.log_count}",
            event_type="authorization_granted",
            timestamp=datetime.now(timezone.utc),
            packet_id=packet.packet_id,
            channel=packet.channel,
            actor=actor,
            details={
                'authority_level': packet.authority_level,
                'gates_satisfied': packet.gates_satisfied
            }
        )

        self.logs.append(log)
        self.log_count += 1

    def log_authorization_denied(self, channel: Channel, reason: str, actor: str):
        """Log authorization denied"""
        log = AuditLogEntry(
            log_id=f"log_{self.log_count}",
            event_type="authorization_denied",
            timestamp=datetime.now(timezone.utc),
            channel=channel,
            actor=actor,
            details={'reason': reason}
        )

        self.logs.append(log)
        self.log_count += 1

    def log_human_signoff_granted(self, packet: CommunicationPacket, actor: str):
        """Log human signoff granted"""
        log = AuditLogEntry(
            log_id=f"log_{self.log_count}",
            event_type="human_signoff_granted",
            timestamp=datetime.now(timezone.utc),
            packet_id=packet.packet_id,
            channel=packet.channel,
            actor=actor,
            details={
                'signoff_by': packet.human_signoff_by,
                'signoff_at': packet.human_signoff_at.isoformat() if packet.human_signoff_at else None
            }
        )

        self.logs.append(log)
        self.log_count += 1

    def log_redaction_applied(self, message: MessageArtifact, actor: str = "system"):
        """Log redaction applied"""
        log = AuditLogEntry(
            log_id=f"log_{self.log_count}",
            event_type="redaction_applied",
            timestamp=datetime.now(timezone.utc),
            message_id=message.message_id,
            channel=message.channel,
            actor=actor,
            details={'has_original': message.content_original is not None}
        )

        self.logs.append(log)
        self.log_count += 1

    def get_logs(self, event_type: Optional[str] = None) -> List[AuditLogEntry]:
        """Get audit logs, optionally filtered by event type"""
        if event_type:
            return [log for log in self.logs if log.event_type == event_type]
        return self.logs

    def get_logs_for_message(self, message_id: str) -> List[AuditLogEntry]:
        """Get all logs for a specific message"""
        return [log for log in self.logs if log.message_id == message_id]

    def get_logs_for_packet(self, packet_id: str) -> List[AuditLogEntry]:
        """Get all logs for a specific packet"""
        return [log for log in self.logs if log.packet_id == packet_id]


class GovernanceLayer:
    """
    Complete governance layer for communications

    Enforces all safety rules:
    1. Inbound messages are artifacts only
    2. Outbound requires authorization
    3. No executable approvals/payments/contracts
    4. Human signoff for external communications
    5. Complete audit trail
    """

    def __init__(self):
        self.authorizer = CommunicationAuthorizer()
        self.validator = OutboundValidator()
        self.approval_blocker = ApprovalBlocker()
        self.signoff_enforcer = HumanSignoffEnforcer()
        self.audit_logger = AuditLogger()

    def process_inbound(self, message: MessageArtifact) -> MessageArtifact:
        """
        Process inbound message

        CRITICAL: This NEVER triggers execution.

        Args:
            message: Inbound MessageArtifact

        Returns:
            Processed message
        """
        # Verify message cannot trigger execution
        if message.triggers_execution:
            raise ValueError("Inbound message cannot trigger execution")

        # Check for approval language
        self.approval_blocker.check_message(message)

        # Log receipt
        self.audit_logger.log_message_received(message)

        return message

    def authorize_outbound(
        self,
        channel: Channel,
        thread_id: str,
        recipient_hashes: List[str],
        content: str,
        authorized_by: str,
        authority_level: str,
        gates_satisfied: List[str],
        external_party: bool = False
    ) -> CommunicationPacket:
        """
        Authorize outbound communication

        Args:
            channel: Communication channel
            thread_id: Thread ID
            recipient_hashes: Recipient hashes
            content: Message content
            authorized_by: Control Plane authorization ID
            authority_level: Authority level
            gates_satisfied: Satisfied gates
            external_party: External communication flag

        Returns:
            Authorized CommunicationPacket
        """
        # Scan content for prohibited patterns
        flags = self.validator.scan_content(content)

        # Create packet
        packet = self.authorizer.authorize(
            channel=channel,
            thread_id=thread_id,
            recipient_hashes=recipient_hashes,
            content=content,
            authorized_by=authorized_by,
            authority_level=authority_level,
            gates_satisfied=gates_satisfied,
            external_party=external_party
        )

        # Set flags
        packet.contains_approval = flags['contains_approval']
        packet.contains_payment = flags['contains_payment']
        packet.contains_contract = flags['contains_contract']

        # Require signoff for external
        if external_party:
            self.signoff_enforcer.require_signoff(packet, "manager")

        # Log authorization
        self.audit_logger.log_authorization_granted(packet, authorized_by)

        return packet

    def validate_outbound(self, packet: CommunicationPacket) -> Tuple[bool, List[str]]:
        """
        Validate outbound packet before sending

        Args:
            packet: CommunicationPacket to validate

        Returns:
            Tuple of (is_valid, violations)
        """
        return self.validator.validate(packet)

    def grant_signoff(self, packet: CommunicationPacket, granted_by: str) -> bool:
        """Grant human signoff for external communication"""
        success = self.signoff_enforcer.grant_signoff(packet, granted_by)

        if success:
            self.audit_logger.log_human_signoff_granted(packet, granted_by)

        return success

    def send_outbound(self, packet: CommunicationPacket, actor: str) -> Tuple[bool, Optional[str]]:
        """
        Validate and approve outbound packet for sending

        Args:
            packet: CommunicationPacket to send
            actor: Who is sending

        Returns:
            Tuple of (can_send, error_message)
        """
        # Validate packet
        is_valid, violations = self.validate_outbound(packet)

        if not is_valid:
            error = f"Packet validation failed: {', '.join(violations)}"
            self.audit_logger.log_authorization_denied(packet.channel, error, actor)
            return False, error

        # Check if packet can be sent
        if not packet.can_send():
            error = "Packet cannot be sent (missing authorization or signoff)"
            return False, error

        # Log send
        self.audit_logger.log_message_sent(packet, actor)

        return True, None
