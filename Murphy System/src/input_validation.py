"""
Input Validation Layer
Validates and sanitizes all user inputs using Pydantic schemas
"""

import logging
import re
from typing import List, Optional
from urllib.parse import unquote

from pydantic import BaseModel, Field, field_validator, validator

logger = logging.getLogger(__name__)


class ConstraintInput(BaseModel):
    """
    Validation schema for constraint proposals.

    Constraints are formal rules that the system must obey.
    Strict validation prevents injection attacks and ensures constraint integrity.
    """
    target: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="What the constraint applies to (e.g., 'execution', 'data_access')"
    )
    rule: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="The constraint rule in formal or natural language"
    )
    justification: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Why this constraint is necessary"
    )

    @field_validator('target', 'rule', 'justification')
    @classmethod
    def sanitize_input(cls, v: str) -> str:
        """
        Sanitize input by removing dangerous characters.

        Blocks:
        - Script tags and HTML
        - SQL injection patterns
        - Command injection characters
        - Path traversal attempts
        """
        if not v:
            return v

        # Remove dangerous characters
        dangerous_chars = ['<', '>', ';', '&', '|', '$', '`', '\\', '\x00']
        for char in dangerous_chars:
            v = v.replace(char, '')

        # Remove SQL injection patterns
        sql_patterns = [
            r'--',
            r'/\*',
            r'\*/',
            r'xp_',
            r'sp_',
            r'exec\s*\(',
            r'execute\s*\(',
            r'drop\s+table',
            r'drop\s+database',
            r'union\s+select',
            r'insert\s+into',
            r'delete\s+from',
            r'update\s+\w+\s+set',
            r'alter\s+table',
            r';\s*(?:drop|insert|update|delete|alter)\s',
            r'waitfor\s+delay',
            r'sleep\s*\(',
            r'benchmark\s*\(',
        ]
        for pattern in sql_patterns:
            v = re.sub(pattern, '', v, flags=re.IGNORECASE)

        # Decode URL-encoded sequences before path traversal check to prevent
        # bypasses via %2e%2e%2f or double-encoding (%252e%252e%252f)
        decoded = v
        prev = ""
        _max_decode_rounds = 10
        for _ in range(_max_decode_rounds):
            if prev == decoded:
                break
            prev = decoded
            decoded = unquote(decoded)

        # Remove path traversal sequences iteratively until stable
        # to prevent double-encoding bypasses like '....//'' → '../'
        for _ in range(_max_decode_rounds):
            if '../' not in decoded and '..\\' not in decoded:
                break
            decoded = decoded.replace('../', '').replace('..\\', '')

        # If decoding changed the value, use the decoded/sanitized version
        if decoded != v:
            v = decoded

        return v.strip()

    @field_validator('rule')
    @classmethod
    def validate_rule_format(cls, v: str) -> str:
        """Ensure rule is not empty after sanitization"""
        if not v or len(v.strip()) == 0:
            raise ValueError("Rule cannot be empty after sanitization")
        return v


class VerificationInput(BaseModel):
    """
    Validation schema for verification evidence.

    Verification evidence is used to satisfy gates.
    """
    gate_id: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="ID of the gate being verified"
    )
    evidence: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="Evidence that satisfies the gate"
    )
    evidence_type: Optional[str] = Field(
        default="manual",
        max_length=50,
        description="Type of evidence (manual, automated, test_result, etc.)"
    )

    @field_validator('gate_id', 'evidence', 'evidence_type')
    @classmethod
    def sanitize_input(cls, v: str) -> str:
        """Sanitize input"""
        if not v:
            return v

        dangerous_chars = ['<', '>', ';', '&', '|', '$', '`', '\\', '\x00']
        for char in dangerous_chars:
            v = v.replace(char, '')

        return v.strip()


class PhaseApprovalInput(BaseModel):
    """
    Validation schema for phase transition approvals.

    Note: Approval does NOT force execution - it only records human acknowledgment.
    System still checks confidence thresholds.
    """
    phase: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Phase being approved"
    )
    approver: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Name or ID of approver"
    )
    signature: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Digital signature or approval token"
    )
    notes: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Additional notes about the approval"
    )

    @field_validator('phase')
    @classmethod
    def validate_phase(cls, v: str) -> str:
        """Validate phase name"""
        valid_phases = ['intake', 'expansion', 'synthesis', 'execute', 'verify']
        v_lower = v.lower().strip()

        if v_lower not in valid_phases:
            raise ValueError(f"Invalid phase. Must be one of: {', '.join(valid_phases)}")

        return v_lower

    @field_validator('approver', 'signature', 'notes')
    @classmethod
    def sanitize_input(cls, v: Optional[str]) -> Optional[str]:
        """Sanitize input"""
        if not v:
            return v

        dangerous_chars = ['<', '>', ';', '&', '|', '$', '`', '\\']
        for char in dangerous_chars:
            v = v.replace(char, '')

        return v.strip()


class HaltInput(BaseModel):
    """
    Validation schema for system halt requests.

    Halt requests are treated as high-priority constraints.
    """
    reason: str = Field(
        ...,
        min_length=10,
        max_length=2000,
        description="Detailed reason for halting the system"
    )
    severity: Optional[str] = Field(
        default="high",
        max_length=20,
        description="Severity level (low, medium, high, critical)"
    )
    requester: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Name or ID of person requesting halt"
    )

    @field_validator('severity')
    @classmethod
    def validate_severity(cls, v: str) -> str:
        """Validate severity level"""
        valid_severities = ['low', 'medium', 'high', 'critical']
        v_lower = v.lower().strip()

        if v_lower not in valid_severities:
            raise ValueError(f"Invalid severity. Must be one of: {', '.join(valid_severities)}")

        return v_lower

    @field_validator('reason', 'requester')
    @classmethod
    def sanitize_input(cls, v: Optional[str]) -> Optional[str]:
        """Sanitize input"""
        if not v:
            return v

        dangerous_chars = ['<', '>', ';', '&', '|', '$', '`', '\\']
        for char in dangerous_chars:
            v = v.replace(char, '')

        return v.strip()


class ChatMessageInput(BaseModel):
    """
    Validation schema for chat messages.

    More permissive than governance inputs, but still sanitized.
    """
    message: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="User message"
    )
    conversation_id: Optional[str] = Field(
        default="default",
        max_length=100,
        description="Conversation identifier"
    )

    @field_validator('message')
    @classmethod
    def sanitize_message(cls, v: str) -> str:
        """
        Sanitize message while preserving natural language.

        Less strict than governance inputs - allows punctuation and common symbols.
        """
        if not v:
            raise ValueError("Message cannot be empty")

        # Remove only the most dangerous characters
        dangerous_chars = [
            '<script', '</script', '<iframe', '</iframe',
            'javascript:', 'onerror=', 'onload=', 'onmouseover=',
            'onfocus=', 'onblur=', 'onclick=',
        ]
        v_lower = v.lower()

        for pattern in dangerous_chars:
            if pattern in v_lower:
                raise ValueError(f"Message contains potentially dangerous content: {pattern}")

        # Remove null bytes
        v = v.replace('\x00', '')

        return v.strip()

    @field_validator('conversation_id')
    @classmethod
    def sanitize_conversation_id(cls, v: str) -> str:
        """Sanitize conversation ID"""
        if not v:
            return "default"

        # Only allow alphanumeric, hyphens, and underscores
        v = re.sub(r'[^a-zA-Z0-9_-]', '', v)

        if not v:
            return "default"

        return v[:100]  # Enforce max length


class PacketCompilationInput(BaseModel):
    """
    Validation schema for execution packet compilation requests.
    """
    task_description: str = Field(
        ...,
        min_length=10,
        max_length=5000,
        description="Description of task to compile into execution packet"
    )
    force_compile: Optional[bool] = Field(
        default=False,
        description="Attempt compilation even if conditions not met (will still fail if unsafe)"
    )

    @field_validator('task_description')
    @classmethod
    def sanitize_task(cls, v: str) -> str:
        """Sanitize task description"""
        if not v:
            raise ValueError("Task description cannot be empty")

        # Remove dangerous characters
        dangerous_chars = ['<', '>', ';', '&', '|', '$', '`', '\\']
        for char in dangerous_chars:
            v = v.replace(char, '')

        return v.strip()


def validate_input(data: dict, schema_class: type[BaseModel]) -> tuple[bool, Optional[BaseModel], Optional[str]]:
    """
    Validate input data against a Pydantic schema.

    Args:
        data: Input data dictionary
        schema_class: Pydantic model class to validate against

    Returns:
        Tuple of (is_valid, validated_data, error_message)
    """
    try:
        validated = schema_class(**data)
        return (True, validated, None)

    except Exception as exc:
        logger.debug("Caught exception: %s", exc)
        error_msg = str(exc)
        return (False, None, error_msg)


# Export all schemas
__all__ = [
    'ConstraintInput',
    'VerificationInput',
    'PhaseApprovalInput',
    'HaltInput',
    'ChatMessageInput',
    'PacketCompilationInput',
    'validate_input'
]
