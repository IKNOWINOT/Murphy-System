"""
Input Validation Layer
Validates and sanitizes all user inputs using Pydantic schemas.
Covers: text fields, file uploads, webhook payloads, API parameters.
"""

import hashlib
import hmac
import logging
import re
from typing import Any, Dict, List, Optional
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


# ── File Upload Validation ──────────────────────────────────────────

# MIME-type signatures (magic bytes) for common upload types.
# Maps allowed extension → (magic_hex_prefix, human_readable_name).
_FILE_MAGIC: Dict[str, tuple] = {
    ".pdf":  ("255044462d", "PDF"),
    ".png":  ("89504e47",  "PNG"),
    ".jpg":  ("ffd8ff",    "JPEG"),
    ".jpeg": ("ffd8ff",    "JPEG"),
    ".gif":  ("47494638",  "GIF"),
    ".webp": ("52494646",  "WebP"),
    ".zip":  ("504b0304",  "ZIP"),
    ".docx": ("504b0304",  "DOCX (ZIP)"),
    ".xlsx": ("504b0304",  "XLSX (ZIP)"),
    ".txt":  (None,        "Plain text"),  # no magic bytes check
    ".md":   (None,        "Markdown"),
    ".csv":  (None,        "CSV"),
    ".json": (None,        "JSON"),
}

# Maximum upload sizes by tier
_MAX_UPLOAD_BYTES_DEFAULT = 5 * 1024 * 1024   # 5 MB
_MAX_UPLOAD_BYTES_DOCUMENT = 50 * 1024 * 1024  # 50 MB

# Characters / patterns that must never appear in uploaded filenames
_DANGEROUS_FILENAME_RE = re.compile(r'[/\\<>:"|?*\x00-\x1f]|\.\.', re.IGNORECASE)


class FileUploadInput(BaseModel):
    """Validation schema for file upload requests.

    Validates:
    - Filename safety (path traversal, dangerous chars)
    - Allowed extension (allowlist)
    - File size (configurable limit)
    - Content type header plausibility
    - Magic bytes (file signature) when content bytes are provided

    Usage::

        upload = FileUploadInput(
            filename="report.pdf",
            content_type="application/pdf",
            size_bytes=102400,
            allowed_extensions=[".pdf", ".docx"],
        )
    """

    filename: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Original filename from the upload",
    )
    content_type: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="MIME content-type header provided by the client",
    )
    size_bytes: int = Field(
        ...,
        ge=1,
        description="File size in bytes",
    )
    allowed_extensions: Optional[List[str]] = Field(
        default=None,
        description="Allowlist of extensions (e.g. ['.pdf', '.png']). None = use defaults.",
    )
    max_size_bytes: int = Field(
        default=_MAX_UPLOAD_BYTES_DEFAULT,
        description="Maximum allowed upload size in bytes",
    )
    content_preview: Optional[bytes] = Field(
        default=None,
        description="First 16 bytes of the file for magic-byte validation (optional)",
    )

    model_config = {"arbitrary_types_allowed": True}

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, v: str) -> str:
        """Block path traversal, null bytes, and dangerous characters."""
        # Null bytes
        if "\x00" in v:
            raise ValueError("Filename contains null bytes")
        # Dangerous characters / traversal
        if _DANGEROUS_FILENAME_RE.search(v):
            raise ValueError(f"Filename contains disallowed characters or traversal patterns: {v!r}")
        # Ensure there's at least a name component
        v = v.strip()
        if not v:
            raise ValueError("Filename is empty after stripping whitespace")
        return v

    @field_validator("content_type")
    @classmethod
    def validate_content_type(cls, v: str) -> str:
        """Normalise and sanity-check the content-type value."""
        v = v.strip().lower().split(";")[0]  # strip parameters like charset
        if not v or "/" not in v:
            raise ValueError(f"content_type does not look like a MIME type: {v!r}")
        return v

    def validate_extension(self) -> None:
        """Raise ValueError if the filename extension is not in the allowlist."""
        ext = "." + self.filename.rsplit(".", 1)[-1].lower() if "." in self.filename else ""
        allowlist = self.allowed_extensions or list(_FILE_MAGIC.keys())
        if ext not in allowlist:
            raise ValueError(
                f"File extension '{ext}' is not allowed. "
                f"Allowed: {', '.join(sorted(allowlist))}"
            )

    def validate_size(self) -> None:
        """Raise ValueError if the file exceeds the configured size limit."""
        if self.size_bytes > self.max_size_bytes:
            raise ValueError(
                f"File size {self.size_bytes} bytes exceeds maximum "
                f"{self.max_size_bytes} bytes"
            )

    def validate_magic_bytes(self) -> None:
        """Raise ValueError if magic bytes mismatch the declared extension.

        Only checked when *content_preview* is provided.
        """
        if not self.content_preview:
            return
        ext = "." + self.filename.rsplit(".", 1)[-1].lower() if "." in self.filename else ""
        magic_entry = _FILE_MAGIC.get(ext)
        if magic_entry is None:
            return  # Unknown extension — skip magic check
        expected_magic, file_type = magic_entry
        if expected_magic is None:
            return  # Text-based format — no magic bytes to check
        preview_hex = self.content_preview[:8].hex()
        if not preview_hex.startswith(expected_magic):
            raise ValueError(
                f"File content does not match declared type '{file_type}' "
                f"(expected magic {expected_magic!r}, got {preview_hex!r})"
            )

    def full_validate(self) -> None:
        """Run all validation checks (extension + size + magic bytes)."""
        self.validate_extension()
        self.validate_size()
        self.validate_magic_bytes()


# ── Webhook Payload Validation ──────────────────────────────────────

class WebhookPayloadInput(BaseModel):
    """Validation schema for inbound webhook payloads.

    Validates:
    - HMAC-SHA256 signature verification (constant-time comparison)
    - Payload size limit
    - Timestamp freshness (replay attack prevention)
    - Schema/structure assertions via required_fields

    Usage::

        webhook = WebhookPayloadInput(
            payload=b'{"event": "push"}',
            signature_header="sha256=abc123...",
            secret="my-webhook-secret",
        )
        webhook.verify_signature()  # raises ValueError on mismatch
    """

    payload: bytes = Field(..., description="Raw webhook payload bytes")
    signature_header: str = Field(
        ...,
        description="Signature header value, e.g. 'sha256=hexdigest' or 'sha1=hexdigest'",
    )
    secret: str = Field(..., description="Shared webhook secret used to compute HMAC")
    max_payload_bytes: int = Field(
        default=1 * 1024 * 1024,
        description="Maximum accepted payload size in bytes (default 1 MB)",
    )
    timestamp_header: Optional[str] = Field(
        default=None,
        description="Optional Unix timestamp header value for replay prevention",
    )
    max_age_seconds: int = Field(
        default=300,
        description="Maximum allowed age of the webhook request in seconds",
    )
    required_fields: Optional[List[str]] = Field(
        default=None,
        description="JSON top-level keys that must be present in the payload",
    )

    model_config = {"arbitrary_types_allowed": True}

    @field_validator("signature_header")
    @classmethod
    def normalise_signature(cls, v: str) -> str:
        return v.strip()

    def verify_signature(self) -> None:
        """Verify HMAC signature using constant-time comparison.

        Supports ``sha256=<hex>`` and ``sha1=<hex>`` header formats.
        Raises ``ValueError`` on mismatch.
        """
        header = self.signature_header
        if "=" in header:
            algo, _, sig_hex = header.partition("=")
        else:
            raise ValueError(
                f"Signature header must be 'algo=hexdigest', got: {header!r}"
            )

        algo = algo.lower()
        if algo == "sha256":
            digest_fn = hashlib.sha256
        elif algo == "sha1":
            logger.warning(
                "WebhookPayloadInput: SHA1 signature algorithm is deprecated; "
                "upgrade webhook source to SHA256."
            )
            digest_fn = hashlib.sha1
        else:
            raise ValueError(f"Unsupported signature algorithm: {algo!r}")

        expected = hmac.new(
            self.secret.encode(),
            self.payload,
            digest_fn,
        ).hexdigest()

        if not hmac.compare_digest(expected, sig_hex):
            raise ValueError("Webhook signature verification failed")

    def verify_size(self) -> None:
        """Raise ValueError if payload exceeds the size limit."""
        if len(self.payload) > self.max_payload_bytes:
            raise ValueError(
                f"Webhook payload size {len(self.payload)} bytes exceeds "
                f"maximum {self.max_payload_bytes} bytes"
            )

    def verify_timestamp(self) -> None:
        """Raise ValueError if the timestamp is missing or too old (replay prevention).

        Only checked when *timestamp_header* is provided.
        """
        if not self.timestamp_header:
            return
        import time as _time
        try:
            ts = float(self.timestamp_header)
        except ValueError:
            raise ValueError(
                f"Timestamp header is not a valid Unix epoch: {self.timestamp_header!r}"
            )
        age = abs(_time.time() - ts)
        if age > self.max_age_seconds:
            raise ValueError(
                f"Webhook timestamp is {int(age)}s old; maximum allowed: "
                f"{self.max_age_seconds}s (replay attack prevention)"
            )

    def verify_required_fields(self) -> None:
        """Raise ValueError if any required JSON fields are absent from the payload."""
        if not self.required_fields:
            return
        import json as _json
        try:
            data = _json.loads(self.payload.decode("utf-8", errors="replace"))
        except _json.JSONDecodeError as exc:
            raise ValueError(f"Webhook payload is not valid JSON: {exc}")
        if not isinstance(data, dict):
            raise ValueError("Webhook payload JSON root must be an object (dict)")
        missing = [f for f in self.required_fields if f not in data]
        if missing:
            raise ValueError(
                f"Webhook payload is missing required fields: {', '.join(missing)}"
            )

    def full_validate(self) -> None:
        """Run all validation checks."""
        self.verify_size()
        self.verify_signature()
        self.verify_timestamp()
        self.verify_required_fields()


# ── API Parameter Validation ────────────────────────────────────────

class APIParameterInput(BaseModel):
    """Validation schema for generic API query/path parameters.

    Validates type coercion and bounds checking.  Intended for use with
    endpoints that accept numeric IDs, pagination parameters, and enum strings.

    Usage::

        params = APIParameterInput(
            page=request.args.get("page"),
            per_page=request.args.get("per_page"),
            sort_by=request.args.get("sort_by"),
            allowed_sort_fields=["created_at", "name"],
        )
    """

    page: Optional[int] = Field(default=1, ge=1, le=10_000, description="Page number (1-based)")
    per_page: Optional[int] = Field(default=20, ge=1, le=100, description="Results per page")
    sort_by: Optional[str] = Field(default=None, max_length=64, description="Sort field name")
    sort_order: Optional[str] = Field(default="asc", description="Sort direction: asc or desc")
    allowed_sort_fields: Optional[List[str]] = Field(
        default=None,
        description="Allowlist of accepted sort_by values",
    )

    @field_validator("sort_order")
    @classmethod
    def validate_sort_order(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return "asc"
        v = v.lower().strip()
        if v not in ("asc", "desc"):
            raise ValueError("sort_order must be 'asc' or 'desc'")
        return v

    @field_validator("sort_by")
    @classmethod
    def sanitize_sort_by(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        # Only allow alphanumeric, underscores, and hyphens
        if not re.match(r'^[a-zA-Z0-9_\-]+$', v):
            raise ValueError(f"sort_by contains disallowed characters: {v!r}")
        return v

    def validate_sort_field(self) -> None:
        """Raise ValueError if sort_by is not in the allowed fields list."""
        if self.sort_by and self.allowed_sort_fields is not None:
            if self.sort_by not in self.allowed_sort_fields:
                raise ValueError(
                    f"sort_by '{self.sort_by}' is not allowed. "
                    f"Valid fields: {', '.join(self.allowed_sort_fields)}"
                )


# Export all schemas
__all__ = [
    'ConstraintInput',
    'VerificationInput',
    'PhaseApprovalInput',
    'HaltInput',
    'ChatMessageInput',
    'PacketCompilationInput',
    'FileUploadInput',
    'WebhookPayloadInput',
    'APIParameterInput',
    'validate_input',
]
