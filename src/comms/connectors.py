"""
Communication channel connectors

All connectors follow the same pattern:
1. Inbound: Poll/receive messages → Create MessageArtifact
2. Outbound: Receive CommunicationPacket → Send message (if authorized)

CRITICAL: Connectors NEVER trigger execution. They only create artifacts.
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    import requests as _requests
except ImportError:
    _requests = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)
import email
import imaplib
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests

from .schemas import (
    Channel,
    CommunicationPacket,
    ConnectorConfig,
    IntentClassification,
    MessageArtifact,
)


class BaseConnector(ABC):
    """
    Abstract base class for communication connectors

    All connectors must implement:
    - receive_messages(): Poll for inbound messages
    - send_message(): Send authorized outbound message
    """

    def __init__(self, config: ConnectorConfig):
        self.config = config
        self.channel = config.channel
        self._last_poll = None
        self._message_count = 0

    @abstractmethod
    def receive_messages(self) -> List[MessageArtifact]:
        """
        Poll for inbound messages and convert to MessageArtifacts

        CRITICAL: This method ONLY creates artifacts. It NEVER triggers execution.

        Returns:
            List of MessageArtifact objects
        """
        pass

    @abstractmethod
    def send_message(self, packet: CommunicationPacket) -> bool:
        """
        Send authorized outbound message

        CRITICAL: This method REQUIRES a CommunicationPacket with authorization.
        It CANNOT send messages without proper authorization.

        Args:
            packet: Authorized CommunicationPacket

        Returns:
            True if sent successfully, False otherwise
        """
        pass

    def _check_rate_limit(self) -> bool:
        """Check if rate limit allows sending"""
        # Simple rate limiting (production would use token bucket)
        if self._message_count >= self.config.max_messages_per_minute:
            return False
        return True

    def _increment_message_count(self):
        """Increment message count for rate limiting"""
        self._message_count += 1


class EmailConnector(BaseConnector):
    """
    Email connector supporting SMTP and Microsoft Graph

    Supports:
    - SMTP for sending
    - IMAP for receiving
    - Microsoft Graph API (optional)
    """

    def __init__(self, config: ConnectorConfig):
        super().__init__(config)

        # SMTP configuration
        self.smtp_host = config.connection_params.get('smtp_host')
        self.smtp_port = config.connection_params.get('smtp_port', 587)
        self.smtp_username = config.connection_params.get('smtp_username')
        self.smtp_password = config.connection_params.get('smtp_password')

        # IMAP configuration
        self.imap_host = config.connection_params.get('imap_host')
        self.imap_port = config.connection_params.get('imap_port', 993)
        self.imap_username = config.connection_params.get('imap_username')
        self.imap_password = config.connection_params.get('imap_password')

        # Microsoft Graph configuration (optional)
        self.use_graph = config.connection_params.get('use_graph', False)
        self.graph_token = config.connection_params.get('graph_token')
        self.graph_endpoint = config.connection_params.get('graph_endpoint', 'https://graph.microsoft.com/v1.0')

    def receive_messages(self) -> List[MessageArtifact]:
        """Receive emails via IMAP or Microsoft Graph"""
        if self.use_graph:
            return self._receive_via_graph()
        else:
            return self._receive_via_imap()

    def _receive_via_imap(self) -> List[MessageArtifact]:
        """Receive emails via IMAP"""
        messages = []

        try:
            # Connect to IMAP server
            if self.config.require_tls:
                imap = imaplib.IMAP4_SSL(self.imap_host, self.imap_port)
            else:
                imap = imaplib.IMAP4(self.imap_host, self.imap_port)

            imap.login(self.imap_username, self.imap_password)
            imap.select('INBOX')

            # Search for unread messages
            _, message_numbers = imap.search(None, 'UNSEEN')

            for num in message_numbers[0].split():
                _, msg_data = imap.fetch(num, '(RFC822)')
                email_body = msg_data[0][1]
                email_message = email.message_from_bytes(email_body)

                # Extract content
                content = self._extract_email_content(email_message)

                # Create MessageArtifact
                artifact = MessageArtifact(
                    message_id=email_message.get('Message-ID', f'email_{num}'),
                    channel=Channel.EMAIL,
                    thread_id=email_message.get('In-Reply-To', email_message.get('Message-ID')),
                    sender_hash=MessageArtifact.hash_identifier(email_message.get('From', '')),
                    recipient_hash=MessageArtifact.hash_identifier(email_message.get('To', '')),
                    content_redacted=content,  # Will be redacted by pipeline
                    content_original=content,
                    intent=IntentClassification.UNKNOWN,  # Will be classified by pipeline
                    timestamp=datetime.now(timezone.utc),
                    direction='inbound',
                    external_party=True,  # Assume external by default
                    source_system='email_imap',
                    triggers_execution=False  # CRITICAL: Never triggers execution
                )

                messages.append(artifact)

            imap.close()
            imap.logout()

        except Exception as exc:
            logger.exception("Error receiving emails via IMAP: %s", exc)

        return messages

    def _receive_via_graph(self) -> List[MessageArtifact]:
        """Receive emails via Microsoft Graph API"""
        messages = []

        try:
            headers = {
                'Authorization': f'Bearer {self.graph_token}',
                'Content-Type': 'application/json'
            }

            # Get unread messages
            url = f'{self.graph_endpoint}/me/messages?$filter=isRead eq false'
            response = requests.get(url, headers=headers, timeout=30)

            if response.status_code == 200:
                data = response.json()

                for msg in data.get('value', []):
                    # Create MessageArtifact
                    artifact = MessageArtifact(
                        message_id=msg.get('id'),
                        channel=Channel.EMAIL,
                        thread_id=msg.get('conversationId', msg.get('id')),
                        sender_hash=MessageArtifact.hash_identifier(msg.get('from', {}).get('emailAddress', {}).get('address', '')),
                        recipient_hash=MessageArtifact.hash_identifier(msg.get('toRecipients', [{}])[0].get('emailAddress', {}).get('address', '')),
                        content_redacted=msg.get('bodyPreview', ''),
                        content_original=msg.get('body', {}).get('content', ''),
                        intent=IntentClassification.UNKNOWN,
                        timestamp=datetime.fromisoformat(msg.get('receivedDateTime', datetime.now(timezone.utc).isoformat())),
                        direction='inbound',
                        external_party=True,
                        source_system='email_graph',
                        triggers_execution=False
                    )

                    messages.append(artifact)

        except Exception as exc:
            logger.exception("Error receiving emails via Graph: %s", exc)

        return messages

    def send_message(self, packet: CommunicationPacket) -> bool:
        """Send email via SMTP or Microsoft Graph"""
        # Verify packet can be sent
        if not packet.can_send():
            raise ValueError("CommunicationPacket cannot be sent (authorization or signoff missing)")

        # Check rate limit
        if not self._check_rate_limit():
            return False

        if self.use_graph:
            success = self._send_via_graph(packet)
        else:
            success = self._send_via_smtp(packet)

        if success:
            self._increment_message_count()
            packet.sent_at = datetime.now(timezone.utc)

        return success

    def _send_via_smtp(self, packet: CommunicationPacket) -> bool:
        """Send email via SMTP"""
        try:
            # Create message
            msg = MIMEMultipart()
            msg['Subject'] = f"Thread: {packet.thread_id}"
            msg['From'] = self.smtp_username
            msg['To'] = ', '.join([f'recipient_{i}@example.com' for i in range(len(packet.recipient_hashes))])

            # Add body
            msg.attach(MIMEText(packet.content, 'plain'))

            # Send via SMTP
            if self.config.require_tls:
                server = smtplib.SMTP(self.smtp_host, self.smtp_port)
                server.starttls()
            else:
                server = smtplib.SMTP(self.smtp_host, self.smtp_port)

            server.login(self.smtp_username, self.smtp_password)
            server.send_message(msg)
            server.quit()

            return True

        except Exception as exc:
            logger.exception("Error sending email via SMTP: %s", exc)
            return False

    def _send_via_graph(self, packet: CommunicationPacket) -> bool:
        """Send email via Microsoft Graph API"""
        try:
            headers = {
                'Authorization': f'Bearer {self.graph_token}',
                'Content-Type': 'application/json'
            }

            # Create message payload
            payload = {
                'message': {
                    'subject': f"Thread: {packet.thread_id}",
                    'body': {
                        'contentType': 'Text',
                        'content': packet.content
                    },
                    'toRecipients': [
                        {'emailAddress': {'address': f'recipient_{i}@example.com'}}
                        for i in range(len(packet.recipient_hashes))
                    ]
                }
            }

            url = f'{self.graph_endpoint}/me/sendMail'
            response = requests.post(url, headers=headers, json=payload, timeout=30)

            return response.status_code == 202

        except Exception as exc:
            logger.exception("Error sending email via Graph: %s", exc)
            return False

    def _extract_email_content(self, email_message) -> str:
        """Extract text content from email message"""
        if email_message.is_multipart():
            for part in email_message.walk():
                if part.get_content_type() == 'text/plain':
                    return part.get_payload(decode=True).decode()
        else:
            return email_message.get_payload(decode=True).decode()
        return ""


class SlackConnector(BaseConnector):
    """
    Slack connector supporting webhooks and polling
    """

    def __init__(self, config: ConnectorConfig):
        super().__init__(config)

        self.bot_token = config.connection_params.get('bot_token')
        self.webhook_url = config.connection_params.get('webhook_url')
        self.api_base = config.connection_params.get('api_base', 'https://slack.com/api')

    def receive_messages(self) -> List[MessageArtifact]:
        """Poll for Slack messages"""
        messages = []

        try:
            headers = {
                'Authorization': f'Bearer {self.bot_token}',
                'Content-Type': 'application/json'
            }

            # Get conversations
            url = f'{self.api_base}/conversations.history'
            params = {'limit': 100}

            response = requests.get(url, headers=headers, params=params, timeout=30)

            if response.status_code == 200:
                data = response.json()

                for msg in data.get('messages', []):
                    # Create MessageArtifact
                    artifact = MessageArtifact(
                        message_id=msg.get('ts'),
                        channel=Channel.SLACK,
                        thread_id=msg.get('thread_ts', msg.get('ts')),
                        sender_hash=MessageArtifact.hash_identifier(msg.get('user', '')),
                        recipient_hash=MessageArtifact.hash_identifier(msg.get('channel', '')),
                        content_redacted=msg.get('text', ''),
                        content_original=msg.get('text', ''),
                        intent=IntentClassification.UNKNOWN,
                        timestamp=datetime.fromtimestamp(float(msg.get('ts', 0))),
                        direction='inbound',
                        external_party=False,  # Slack is typically internal
                        source_system='slack',
                        triggers_execution=False
                    )

                    messages.append(artifact)

        except Exception as exc:
            logger.exception("Error receiving Slack messages: %s", exc)

        return messages

    def send_message(self, packet: CommunicationPacket) -> bool:
        """Send Slack message via webhook or API"""
        if not packet.can_send():
            raise ValueError("CommunicationPacket cannot be sent")

        if not self._check_rate_limit():
            return False

        try:
            if self.webhook_url:
                # Send via webhook
                payload = {'text': packet.content}
                response = requests.post(self.webhook_url, json=payload, timeout=30)
                success = response.status_code == 200
            else:
                # Send via API
                headers = {
                    'Authorization': f'Bearer {self.bot_token}',
                    'Content-Type': 'application/json'
                }

                payload = {
                    'channel': packet.thread_id,
                    'text': packet.content
                }

                url = f'{self.api_base}/chat.postMessage'
                response = requests.post(url, headers=headers, json=payload, timeout=30)
                success = response.status_code == 200

            if success:
                self._increment_message_count()
                packet.sent_at = datetime.now(timezone.utc)

            return success

        except Exception as exc:
            logger.exception("Error sending Slack message: %s", exc)
            return False


class TeamsConnector(BaseConnector):
    """
    Microsoft Teams connector supporting webhooks and polling
    """

    def __init__(self, config: ConnectorConfig):
        super().__init__(config)

        self.webhook_url = config.connection_params.get('webhook_url')
        self.graph_token = config.connection_params.get('graph_token')
        self.graph_endpoint = config.connection_params.get('graph_endpoint', 'https://graph.microsoft.com/v1.0')

    def receive_messages(self) -> List[MessageArtifact]:
        """Poll for Teams messages via Microsoft Graph"""
        messages = []

        try:
            headers = {
                'Authorization': f'Bearer {self.graph_token}',
                'Content-Type': 'application/json'
            }

            # Get chat messages
            url = f'{self.graph_endpoint}/me/chats/getAllMessages'
            response = requests.get(url, headers=headers, timeout=30)

            if response.status_code == 200:
                data = response.json()

                for msg in data.get('value', []):
                    artifact = MessageArtifact(
                        message_id=msg.get('id'),
                        channel=Channel.TEAMS,
                        thread_id=msg.get('chatId', msg.get('id')),
                        sender_hash=MessageArtifact.hash_identifier(msg.get('from', {}).get('user', {}).get('id', '')),
                        recipient_hash=MessageArtifact.hash_identifier(msg.get('chatId', '')),
                        content_redacted=msg.get('body', {}).get('content', ''),
                        content_original=msg.get('body', {}).get('content', ''),
                        intent=IntentClassification.UNKNOWN,
                        timestamp=datetime.fromisoformat(msg.get('createdDateTime', datetime.now(timezone.utc).isoformat())),
                        direction='inbound',
                        external_party=False,
                        source_system='teams',
                        triggers_execution=False
                    )

                    messages.append(artifact)

        except Exception as exc:
            logger.exception("Error receiving Teams messages: %s", exc)

        return messages

    def send_message(self, packet: CommunicationPacket) -> bool:
        """Send Teams message via webhook or Graph API"""
        if not packet.can_send():
            raise ValueError("CommunicationPacket cannot be sent")

        if not self._check_rate_limit():
            return False

        try:
            if self.webhook_url:
                # Send via webhook
                payload = {
                    'text': packet.content
                }
                response = requests.post(self.webhook_url, json=payload, timeout=30)
                success = response.status_code == 200
            else:
                # Send via Graph API
                headers = {
                    'Authorization': f'Bearer {self.graph_token}',
                    'Content-Type': 'application/json'
                }

                payload = {
                    'body': {
                        'content': packet.content
                    }
                }

                url = f'{self.graph_endpoint}/chats/{packet.thread_id}/messages'
                response = requests.post(url, headers=headers, json=payload, timeout=30)
                success = response.status_code == 201

            if success:
                self._increment_message_count()
                packet.sent_at = datetime.now(timezone.utc)

            return success

        except Exception as exc:
            logger.exception("Error sending Teams message: %s", exc)
            return False


class SMSConnector(BaseConnector):
    """
    SMS connector with pluggable provider interface

    Supports:
    - Twilio
    - AWS SNS
    - Custom providers
    """

    def __init__(self, config: ConnectorConfig):
        super().__init__(config)

        self.provider = config.connection_params.get('provider', 'twilio')
        self.api_key = config.connection_params.get('api_key')
        self.api_secret = config.connection_params.get('api_secret')
        self.from_number = config.connection_params.get('from_number')

    def receive_messages(self) -> List[MessageArtifact]:
        """
        Receive SMS messages (typically via webhook callback)

        Note: SMS is usually push-based (webhook), not poll-based.
        This method is a stub for consistency.
        """
        # In production, this would be called by webhook handler
        return []

    def send_message(self, packet: CommunicationPacket) -> bool:
        """Send SMS via configured provider"""
        if not packet.can_send():
            raise ValueError("CommunicationPacket cannot be sent")

        if not self._check_rate_limit():
            return False

        if self.provider == 'twilio':
            return self._send_via_twilio(packet)
        elif self.provider == 'aws_sns':
            return self._send_via_sns(packet)
        else:
            logger.error("Unknown SMS provider: %s", self.provider)
            return False

    def _send_via_twilio(self, packet: CommunicationPacket) -> bool:
        """Send SMS via Twilio REST API."""
        if _requests is None:
            logger.error("requests library required for Twilio integration")
            return False
        account_sid = self.config.connection_params.get("twilio_account_sid", "")
        auth_token = self.config.connection_params.get("twilio_auth_token", "")
        from_number = self.config.connection_params.get("twilio_from_number", "")
        if not all([account_sid, auth_token, from_number]):
            logger.warning("Twilio credentials not configured; SMS not sent")
            return False
        to_number = packet.metadata.get("to_number", packet.recipient)
        url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
        try:
            resp = _requests.post(
                url,
                data={"From": from_number, "To": to_number, "Body": packet.content},
                auth=(account_sid, auth_token),
                timeout=15,
            )
            if resp.status_code in (200, 201):
                self._increment_message_count()
                packet.sent_at = datetime.now(timezone.utc)
                logger.info("Twilio SMS sent (sid=%s)", resp.json().get("sid"))
                return True
            logger.error("Twilio error %s: %s", resp.status_code, resp.text[:200])
            return False
        except Exception as exc:
            logger.exception("Twilio send failed: %s", exc)
            return False

    def _send_via_sns(self, packet: CommunicationPacket) -> bool:
        """Send SMS via AWS SNS using HTTP signing."""
        try:
            import boto3
        except ImportError:
            logger.error("boto3 required for AWS SNS integration")
            return False
        region = self.config.connection_params.get("aws_region", "us-east-1")
        try:
            client = boto3.client("sns", region_name=region)
            to_number = packet.metadata.get("to_number", packet.recipient)
            response = client.publish(PhoneNumber=to_number, Message=packet.content)
            self._increment_message_count()
            packet.sent_at = datetime.now(timezone.utc)
            logger.info("AWS SNS SMS sent (MessageId=%s)", response.get("MessageId"))
            return True
        except Exception as exc:
            logger.exception("AWS SNS send failed: %s", exc)
            return False


class TicketConnector(BaseConnector):
    """
    Generic ticket system connector

    Supports:
    - Jira
    - ServiceNow
    - Zendesk
    - Custom ticket systems
    """

    def __init__(self, config: ConnectorConfig):
        super().__init__(config)

        self.system = config.connection_params.get('system', 'jira')
        self.api_base = config.connection_params.get('api_base')
        self.api_token = config.connection_params.get('api_token')
        self.username = config.connection_params.get('username')

    def receive_messages(self) -> List[MessageArtifact]:
        """Poll for ticket updates/comments"""
        messages = []

        try:
            if self.system == 'jira':
                messages = self._receive_jira_comments()
            elif self.system == 'servicenow':
                messages = self._receive_servicenow_comments()
            elif self.system == 'zendesk':
                messages = self._receive_zendesk_comments()

        except Exception as exc:
            logger.exception("Error receiving ticket messages: %s", exc)

        return messages

    def _receive_jira_comments(self) -> List[MessageArtifact]:
        """Receive recent Jira issue comments via REST API."""
        if _requests is None or not self.api_base or not self.api_token:
            return []
        project_key = self.config.connection_params.get("project_key", "")
        url = f"{self.api_base}/rest/api/3/search"
        params = {"jql": f"project={project_key} AND updated >= -1h", "maxResults": 20}
        try:
            resp = _requests.get(url, params=params, auth=(self.username or "", self.api_token), timeout=15)
            if resp.status_code != 200:
                logger.error("Jira search failed: %s", resp.status_code)
                return []
            messages: List[MessageArtifact] = []
            for issue in resp.json().get("issues", []):
                key = issue.get("key", "")
                fields = issue.get("fields", {})
                summary = fields.get("summary", "")
                messages.append(MessageArtifact(
                    message_id=key,
                    channel="jira",
                    content=summary,
                    sender=fields.get("reporter", {}).get("displayName", "unknown"),
                    timestamp=datetime.now(timezone.utc),
                    metadata={"issue_key": key},
                ))
            return messages
        except Exception as exc:
            logger.exception("Jira receive failed: %s", exc)
            return []

    def _receive_servicenow_comments(self) -> List[MessageArtifact]:
        """Receive recent ServiceNow incident comments via REST API."""
        if _requests is None or not self.api_base or not self.api_token:
            return []
        url = f"{self.api_base}/api/now/table/incident"
        params = {"sysparm_limit": 20, "sysparm_query": "sys_updated_onONLast hour@javascript:gs.beginningOfLastHour()@javascript:gs.endOfLastHour()"}
        try:
            resp = _requests.get(
                url, params=params,
                auth=(self.username or "", self.api_token),
                headers={"Accept": "application/json"},
                timeout=15,
            )
            if resp.status_code != 200:
                logger.error("ServiceNow query failed: %s", resp.status_code)
                return []
            messages: List[MessageArtifact] = []
            for record in resp.json().get("result", []):
                messages.append(MessageArtifact(
                    message_id=record.get("sys_id", ""),
                    channel="servicenow",
                    content=record.get("short_description", ""),
                    sender=record.get("opened_by", {}).get("display_value", "unknown"),
                    timestamp=datetime.now(timezone.utc),
                    metadata={"number": record.get("number", "")},
                ))
            return messages
        except Exception as exc:
            logger.exception("ServiceNow receive failed: %s", exc)
            return []

    def _receive_zendesk_comments(self) -> List[MessageArtifact]:
        """Receive recent Zendesk ticket comments via REST API."""
        if _requests is None or not self.api_base or not self.api_token:
            return []
        url = f"{self.api_base}/api/v2/tickets/recent.json"
        try:
            resp = _requests.get(
                url,
                auth=(f"{self.username}/token", self.api_token),
                timeout=15,
            )
            if resp.status_code != 200:
                logger.error("Zendesk query failed: %s", resp.status_code)
                return []
            messages: List[MessageArtifact] = []
            for ticket in resp.json().get("tickets", []):
                messages.append(MessageArtifact(
                    message_id=str(ticket.get("id", "")),
                    channel="zendesk",
                    content=ticket.get("subject", ""),
                    sender=str(ticket.get("requester_id", "unknown")),
                    timestamp=datetime.now(timezone.utc),
                    metadata={"ticket_id": ticket.get("id")},
                ))
            return messages
        except Exception as exc:
            logger.exception("Zendesk receive failed: %s", exc)
            return []

    def send_message(self, packet: CommunicationPacket) -> bool:
        """Send ticket comment/update"""
        if not packet.can_send():
            raise ValueError("CommunicationPacket cannot be sent")

        if not self._check_rate_limit():
            return False

        try:
            if self.system == 'jira':
                success = self._send_jira_comment(packet)
            elif self.system == 'servicenow':
                success = self._send_servicenow_comment(packet)
            elif self.system == 'zendesk':
                success = self._send_zendesk_comment(packet)
            else:
                success = False

            if success:
                self._increment_message_count()
                packet.sent_at = datetime.now(timezone.utc)

            return success

        except Exception as exc:
            logger.info(f"Error sending ticket message: {exc}")
            return False

    def _send_jira_comment(self, packet: CommunicationPacket) -> bool:
        """Send a comment to a Jira issue via REST API."""
        if _requests is None or not self.api_base or not self.api_token:
            logger.warning("Jira credentials not configured; comment not sent")
            return False
        issue_key = packet.metadata.get("issue_key", packet.recipient)
        url = f"{self.api_base}/rest/api/3/issue/{issue_key}/comment"
        try:
            resp = _requests.post(
                url,
                json={"body": {"type": "doc", "version": 1, "content": [{"type": "paragraph", "content": [{"type": "text", "text": packet.content}]}]}},
                auth=(self.username or "", self.api_token),
                headers={"Content-Type": "application/json"},
                timeout=15,
            )
            if resp.status_code in (200, 201):
                logger.info("Jira comment added to %s", issue_key)
                return True
            logger.error("Jira comment failed: %s %s", resp.status_code, resp.text[:200])
            return False
        except Exception as exc:
            logger.exception("Jira send failed: %s", exc)
            return False

    def _send_servicenow_comment(self, packet: CommunicationPacket) -> bool:
        """Add a work note to a ServiceNow incident via REST API."""
        if _requests is None or not self.api_base or not self.api_token:
            logger.warning("ServiceNow credentials not configured; comment not sent")
            return False
        incident_id = packet.metadata.get("sys_id", packet.recipient)
        url = f"{self.api_base}/api/now/table/incident/{incident_id}"
        try:
            resp = _requests.patch(
                url,
                json={"work_notes": packet.content},
                auth=(self.username or "", self.api_token),
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                timeout=15,
            )
            if resp.status_code == 200:
                logger.info("ServiceNow work note added to %s", incident_id)
                return True
            logger.error("ServiceNow update failed: %s %s", resp.status_code, resp.text[:200])
            return False
        except Exception as exc:
            logger.exception("ServiceNow send failed: %s", exc)
            return False

    def _send_zendesk_comment(self, packet: CommunicationPacket) -> bool:
        """Add a comment to a Zendesk ticket via REST API."""
        if _requests is None or not self.api_base or not self.api_token:
            logger.warning("Zendesk credentials not configured; comment not sent")
            return False
        ticket_id = packet.metadata.get("ticket_id", packet.recipient)
        url = f"{self.api_base}/api/v2/tickets/{ticket_id}.json"
        try:
            resp = _requests.put(
                url,
                json={"ticket": {"comment": {"body": packet.content, "public": True}}},
                auth=(f"{self.username}/token", self.api_token),
                headers={"Content-Type": "application/json"},
                timeout=15,
            )
            if resp.status_code == 200:
                logger.info("Zendesk comment added to ticket %s", ticket_id)
                return True
            logger.error("Zendesk update failed: %s %s", resp.status_code, resp.text[:200])
            return False
        except Exception as exc:
            logger.exception("Zendesk send failed: %s", exc)
            return False


# ---------------------------------------------------------------------------
# Test-friendly connector wrappers (no-arg constructors for integration tests)
# ---------------------------------------------------------------------------
# These wrappers provide simplified connectors that can be instantiated
# without a ConnectorConfig, returning deterministic results for testing.


class TestEmailConnector:
    """Test-friendly EmailConnector that works without SMTP configuration."""

    def __init__(self, config: Any = None):
        self._config = config

    def send(self, to: Any = None, subject: Any = None, body: Any = None, **kwargs: Any) -> Dict[str, Any]:
        """Send or simulate sending an email.  Accepts a notification dict."""
        if isinstance(to, dict) and subject is None:
            packet = to
            to = packet.get("recipients", [])
            subject = packet.get("message", "Notification")
            body = packet.get("message", "")
        return {"status": "sent", "to": to, "subject": subject}


class TestSlackConnector:
    """Test-friendly SlackConnector that works without Slack configuration."""

    def __init__(self, config: Any = None):
        self._config = config

    def send(self, channel: Any = None, message: Any = None, **kwargs: Any) -> Dict[str, Any]:
        """Send or simulate sending a Slack message.  Accepts a notification dict."""
        if isinstance(channel, dict) and message is None:
            packet = channel
            channels = packet.get("channels", ["general"])
            channel = channels[0] if isinstance(channels, list) else "general"
            message = packet.get("message", "")
        return {"status": "sent", "channel": channel}
