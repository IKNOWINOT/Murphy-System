"""
Communication channel connectors

All connectors follow the same pattern:
1. Inbound: Poll/receive messages → Create MessageArtifact
2. Outbound: Receive CommunicationPacket → Send message (if authorized)

CRITICAL: Connectors NEVER trigger execution. They only create artifacts.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any
from datetime import datetime
import smtplib
import imaplib
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
import time

from .schemas import (
    MessageArtifact,
    CommunicationPacket,
    Channel,
    IntentClassification,
    ConnectorConfig,
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
                    timestamp=datetime.utcnow(),
                    direction='inbound',
                    external_party=True,  # Assume external by default
                    source_system='email_imap',
                    triggers_execution=False  # CRITICAL: Never triggers execution
                )
                
                messages.append(artifact)
            
            imap.close()
            imap.logout()
        
        except Exception as e:
            print(f"Error receiving emails via IMAP: {e}")
        
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
            response = requests.get(url, headers=headers)
            
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
                        timestamp=datetime.fromisoformat(msg.get('receivedDateTime', datetime.utcnow().isoformat())),
                        direction='inbound',
                        external_party=True,
                        source_system='email_graph',
                        triggers_execution=False
                    )
                    
                    messages.append(artifact)
        
        except Exception as e:
            print(f"Error receiving emails via Graph: {e}")
        
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
            packet.sent_at = datetime.utcnow()
        
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
        
        except Exception as e:
            print(f"Error sending email via SMTP: {e}")
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
            response = requests.post(url, headers=headers, json=payload)
            
            return response.status_code == 202
        
        except Exception as e:
            print(f"Error sending email via Graph: {e}")
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
            
            response = requests.get(url, headers=headers, params=params)
            
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
        
        except Exception as e:
            print(f"Error receiving Slack messages: {e}")
        
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
                response = requests.post(self.webhook_url, json=payload)
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
                response = requests.post(url, headers=headers, json=payload)
                success = response.status_code == 200
            
            if success:
                self._increment_message_count()
                packet.sent_at = datetime.utcnow()
            
            return success
        
        except Exception as e:
            print(f"Error sending Slack message: {e}")
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
            response = requests.get(url, headers=headers)
            
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
                        timestamp=datetime.fromisoformat(msg.get('createdDateTime', datetime.utcnow().isoformat())),
                        direction='inbound',
                        external_party=False,
                        source_system='teams',
                        triggers_execution=False
                    )
                    
                    messages.append(artifact)
        
        except Exception as e:
            print(f"Error receiving Teams messages: {e}")
        
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
                response = requests.post(self.webhook_url, json=payload)
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
                response = requests.post(url, headers=headers, json=payload)
                success = response.status_code == 201
            
            if success:
                self._increment_message_count()
                packet.sent_at = datetime.utcnow()
            
            return success
        
        except Exception as e:
            print(f"Error sending Teams message: {e}")
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
            print(f"Unknown SMS provider: {self.provider}")
            return False
    
    def _send_via_twilio(self, packet: CommunicationPacket) -> bool:
        """Send SMS via Twilio (stub)"""
        # In production, would use Twilio SDK
        print(f"[STUB] Sending SMS via Twilio: {packet.content[:50]}...")
        self._increment_message_count()
        packet.sent_at = datetime.utcnow()
        return True
    
    def _send_via_sns(self, packet: CommunicationPacket) -> bool:
        """Send SMS via AWS SNS (stub)"""
        # In production, would use boto3
        print(f"[STUB] Sending SMS via AWS SNS: {packet.content[:50]}...")
        self._increment_message_count()
        packet.sent_at = datetime.utcnow()
        return True


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
        
        except Exception as e:
            print(f"Error receiving ticket messages: {e}")
        
        return messages
    
    def _receive_jira_comments(self) -> List[MessageArtifact]:
        """Receive Jira comments (stub)"""
        # In production, would use Jira API
        return []
    
    def _receive_servicenow_comments(self) -> List[MessageArtifact]:
        """Receive ServiceNow comments (stub)"""
        # In production, would use ServiceNow API
        return []
    
    def _receive_zendesk_comments(self) -> List[MessageArtifact]:
        """Receive Zendesk comments (stub)"""
        # In production, would use Zendesk API
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
                packet.sent_at = datetime.utcnow()
            
            return success
        
        except Exception as e:
            print(f"Error sending ticket message: {e}")
            return False
    
    def _send_jira_comment(self, packet: CommunicationPacket) -> bool:
        """Send Jira comment (stub)"""
        print(f"[STUB] Sending Jira comment: {packet.content[:50]}...")
        return True
    
    def _send_servicenow_comment(self, packet: CommunicationPacket) -> bool:
        """Send ServiceNow comment (stub)"""
        print(f"[STUB] Sending ServiceNow comment: {packet.content[:50]}...")
        return True
    
    def _send_zendesk_comment(self, packet: CommunicationPacket) -> bool:
        """Send Zendesk comment (stub)"""
        print(f"[STUB] Sending Zendesk comment: {packet.content[:50]}...")
        return True