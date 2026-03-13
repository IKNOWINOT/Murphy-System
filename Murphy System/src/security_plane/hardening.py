"""
Security Plane - Phase 5: Entrance & Exit Hardening
===================================================

Comprehensive input validation, output encoding, and injection prevention.

CRITICAL PRINCIPLES:
1. Validate all inputs at system boundaries
2. Encode all outputs before rendering
3. Never trust user input
4. Use allowlists over denylists
5. Fail securely on validation errors

Author: Murphy System (MFGC-AI)
"""

import base64
import hashlib
import html
import json
import logging
import os
import re
import shlex
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set
from urllib.parse import quote, quote_plus, unquote, urlencode

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Raised when input validation fails"""
    pass


class InjectionAttemptError(Exception):
    """Raised when injection attack detected"""
    pass


class InputType(Enum):
    """Types of input data"""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    EMAIL = "email"
    URL = "url"
    PATH = "path"
    COMMAND = "command"
    JSON = "json"
    BASE64 = "base64"
    UUID = "uuid"
    IDENTIFIER = "identifier"


class OutputContext(Enum):
    """Context for output encoding"""
    HTML = "html"
    HTML_ATTRIBUTE = "html_attribute"
    JAVASCRIPT = "javascript"
    CSS = "css"
    URL = "url"
    URL_PARAMETER = "url_parameter"
    JSON = "json"
    XML = "xml"
    SHELL = "shell"
    SQL = "sql"


@dataclass
class ValidationRule:
    """Rule for validating input"""
    input_type: InputType
    required: bool = True
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    pattern: Optional[str] = None
    allowed_values: Optional[Set[str]] = None
    custom_validator: Optional[Callable[[Any], bool]] = None

    def validate(self, value: Any, field_name: str) -> Any:
        """
        Validate a value against this rule.

        Args:
            value: Value to validate
            field_name: Name of field (for error messages)

        Returns:
            Validated and sanitized value

        Raises:
            ValidationError: If validation fails
        """
        # Check required
        if value is None or value == "":
            if self.required:
                raise ValidationError(f"{field_name} is required")
            return None

        # Type-specific validation
        if self.input_type == InputType.STRING:
            return self._validate_string(value, field_name)
        elif self.input_type == InputType.INTEGER:
            return self._validate_integer(value, field_name)
        elif self.input_type == InputType.FLOAT:
            return self._validate_float(value, field_name)
        elif self.input_type == InputType.BOOLEAN:
            return self._validate_boolean(value, field_name)
        elif self.input_type == InputType.EMAIL:
            return self._validate_email(value, field_name)
        elif self.input_type == InputType.URL:
            return self._validate_url(value, field_name)
        elif self.input_type == InputType.PATH:
            return self._validate_path(value, field_name)
        elif self.input_type == InputType.COMMAND:
            return self._validate_command(value, field_name)
        elif self.input_type == InputType.JSON:
            return self._validate_json(value, field_name)
        elif self.input_type == InputType.BASE64:
            return self._validate_base64(value, field_name)
        elif self.input_type == InputType.UUID:
            return self._validate_uuid(value, field_name)
        elif self.input_type == InputType.IDENTIFIER:
            return self._validate_identifier(value, field_name)
        else:
            raise ValidationError(f"Unknown input type: {self.input_type}")

    def _validate_string(self, value: Any, field_name: str) -> str:
        """Validate string input"""
        if not isinstance(value, str):
            raise ValidationError(f"{field_name} must be a string")

        # Length checks
        if self.min_length is not None and len(value) < self.min_length:
            raise ValidationError(f"{field_name} must be at least {self.min_length} characters")
        if self.max_length is not None and len(value) > self.max_length:
            raise ValidationError(f"{field_name} must be at most {self.max_length} characters")

        # Pattern check
        if self.pattern is not None:
            if not re.match(self.pattern, value):
                raise ValidationError(f"{field_name} does not match required pattern")

        # Allowed values check
        if self.allowed_values is not None:
            if value not in self.allowed_values:
                raise ValidationError(f"{field_name} must be one of: {', '.join(self.allowed_values)}")

        # Custom validator
        if self.custom_validator is not None:
            if not self.custom_validator(value):
                raise ValidationError(f"{field_name} failed custom validation")

        return value

    def _validate_integer(self, value: Any, field_name: str) -> int:
        """Validate integer input"""
        try:
            int_value = int(value)
        except (ValueError, TypeError):
            raise ValidationError(f"{field_name} must be an integer")

        if self.min_value is not None and int_value < self.min_value:
            raise ValidationError(f"{field_name} must be at least {self.min_value}")
        if self.max_value is not None and int_value > self.max_value:
            raise ValidationError(f"{field_name} must be at most {self.max_value}")

        return int_value

    def _validate_float(self, value: Any, field_name: str) -> float:
        """Validate float input"""
        try:
            float_value = float(value)
        except (ValueError, TypeError):
            raise ValidationError(f"{field_name} must be a number")

        if self.min_value is not None and float_value < self.min_value:
            raise ValidationError(f"{field_name} must be at least {self.min_value}")
        if self.max_value is not None and float_value > self.max_value:
            raise ValidationError(f"{field_name} must be at most {self.max_value}")

        return float_value

    def _validate_boolean(self, value: Any, field_name: str) -> bool:
        """Validate boolean input"""
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            if value.lower() in ("true", "yes", "1", "on"):
                return True
            if value.lower() in ("false", "no", "0", "off"):
                return False
        raise ValidationError(f"{field_name} must be a boolean")

    def _validate_email(self, value: Any, field_name: str) -> str:
        """Validate email address"""
        if not isinstance(value, str):
            raise ValidationError(f"{field_name} must be a string")

        # Simple email regex (RFC 5322 simplified)
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, value):
            raise ValidationError(f"{field_name} must be a valid email address")

        if len(value) > 254:  # RFC 5321
            raise ValidationError(f"{field_name} email address too long")

        return value.lower()

    def _validate_url(self, value: Any, field_name: str) -> str:
        """Validate URL"""
        if not isinstance(value, str):
            raise ValidationError(f"{field_name} must be a string")

        # URL pattern (http/https only for security)
        url_pattern = r'^https?://[a-zA-Z0-9.-]+(?:\.[a-zA-Z]{2,})?(?:/[^\s]*)?$'
        if not re.match(url_pattern, value):
            raise ValidationError(f"{field_name} must be a valid HTTP/HTTPS URL")

        if len(value) > 2048:  # Common URL length limit
            raise ValidationError(f"{field_name} URL too long")

        return value

    def _validate_path(self, value: Any, field_name: str) -> str:
        """Validate file path (prevent path traversal)"""
        if not isinstance(value, str):
            raise ValidationError(f"{field_name} must be a string")

        # Decode URL-encoded sequences recursively to prevent bypasses
        # via %2e%2e%2f or double-encoding (%252e%252e%252f)
        decoded = value
        prev = ""
        _max_decode_rounds = 10
        for _ in range(_max_decode_rounds):
            if prev == decoded:
                break
            prev = decoded
            decoded = unquote(decoded)

        # Check for path traversal attempts (on decoded value)
        if ".." in decoded:
            raise InjectionAttemptError(f"{field_name} contains path traversal attempt")

        # Check for absolute paths (only allow relative)
        if os.path.isabs(decoded):
            raise ValidationError(f"{field_name} must be a relative path")

        # Normalize path
        normalized = os.path.normpath(decoded)

        # Check again after normalization
        if ".." in normalized or normalized.startswith("/"):
            raise InjectionAttemptError(f"{field_name} contains path traversal attempt")

        return normalized

    def _validate_command(self, value: Any, field_name: str) -> str:
        """Validate shell command (prevent command injection)"""
        if not isinstance(value, str):
            raise ValidationError(f"{field_name} must be a string")

        # Dangerous characters/patterns
        dangerous_patterns = [
            r'[;&|`$()]',  # Shell metacharacters
            r'>\s*/',      # Output redirection to absolute path
            r'<\s*/',      # Input redirection from absolute path
            r'\$\(',       # Command substitution
            r'`',          # Backtick command substitution
        ]

        for pattern in dangerous_patterns:
            if re.search(pattern, value):
                raise InjectionAttemptError(f"{field_name} contains dangerous shell characters")

        # Use shlex to safely parse
        try:
            shlex.split(value)
        except ValueError as exc:
            raise ValidationError(f"{field_name} is not a valid command: {exc}")

        return value

    def _validate_json(self, value: Any, field_name: str) -> Dict:
        """Validate JSON input"""
        if isinstance(value, dict):
            return value

        if not isinstance(value, str):
            raise ValidationError(f"{field_name} must be a JSON string or dict")

        try:
            return json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValidationError(f"{field_name} is not valid JSON: {exc}")

    def _validate_base64(self, value: Any, field_name: str) -> bytes:
        """Validate base64 input"""
        if not isinstance(value, str):
            raise ValidationError(f"{field_name} must be a string")

        try:
            return base64.b64decode(value, validate=True)
        except Exception as exc:
            logger.debug("Caught exception: %s", exc)
            raise ValidationError(f"{field_name} is not valid base64: {exc}")

    def _validate_uuid(self, value: Any, field_name: str) -> str:
        """Validate UUID"""
        if not isinstance(value, str):
            raise ValidationError(f"{field_name} must be a string")

        uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        if not re.match(uuid_pattern, value.lower()):
            raise ValidationError(f"{field_name} must be a valid UUID")

        return value.lower()

    def _validate_identifier(self, value: Any, field_name: str) -> str:
        """Validate identifier (alphanumeric + underscore only)"""
        if not isinstance(value, str):
            raise ValidationError(f"{field_name} must be a string")

        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', value):
            raise ValidationError(f"{field_name} must be a valid identifier (alphanumeric + underscore)")

        if len(value) > 255:
            raise ValidationError(f"{field_name} identifier too long")

        return value


class InputValidator:
    """
    Validates input data against defined rules.

    PRINCIPLE: Validate all inputs at system boundaries.
    """

    def __init__(self):
        """Initialize input validator"""
        self.rules: Dict[str, ValidationRule] = {}
        self.validation_log: List[Dict] = []

    def add_rule(self, field_name: str, rule: ValidationRule):
        """
        Add validation rule for a field.

        Args:
            field_name: Name of field
            rule: Validation rule
        """
        self.rules[field_name] = rule

    def validate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate input data.

        Args:
            data: Input data dictionary

        Returns:
            Validated and sanitized data

        Raises:
            ValidationError: If validation fails
        """
        validated = {}
        errors = []

        # Validate each field
        for field_name, rule in self.rules.items():
            try:
                value = data.get(field_name)
                validated[field_name] = rule.validate(value, field_name)
            except (ValidationError, InjectionAttemptError) as exc:
                errors.append(str(exc))

        # Check for unexpected fields
        unexpected = set(data.keys()) - set(self.rules.keys())
        if unexpected:
            errors.append(f"Unexpected fields: {', '.join(unexpected)}")

        # Log validation attempt
        self.validation_log.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "success": len(errors) == 0,
            "errors": errors,
            "field_count": len(data)
        })

        if errors:
            raise ValidationError("; ".join(errors))

        return validated

    def validate_single(self, field_name: str, value: Any) -> Any:
        """
        Validate a single field.

        Args:
            field_name: Name of field
            value: Value to validate

        Returns:
            Validated value

        Raises:
            ValidationError: If validation fails
        """
        if field_name not in self.rules:
            raise ValidationError(f"No validation rule for field: {field_name}")

        return self.rules[field_name].validate(value, field_name)


class OutputEncoder:
    """
    Encodes output data for safe rendering in different contexts.

    PRINCIPLE: Encode all outputs before rendering to prevent injection.
    """

    @staticmethod
    def encode(value: str, context: OutputContext) -> str:
        """
        Encode value for specific output context.

        Args:
            value: Value to encode
            context: Output context

        Returns:
            Encoded value
        """
        if context == OutputContext.HTML:
            return OutputEncoder.encode_html(value)
        elif context == OutputContext.HTML_ATTRIBUTE:
            return OutputEncoder.encode_html_attribute(value)
        elif context == OutputContext.JAVASCRIPT:
            return OutputEncoder.encode_javascript(value)
        elif context == OutputContext.CSS:
            return OutputEncoder.encode_css(value)
        elif context == OutputContext.URL:
            return OutputEncoder.encode_url(value)
        elif context == OutputContext.URL_PARAMETER:
            return OutputEncoder.encode_url_parameter(value)
        elif context == OutputContext.JSON:
            return OutputEncoder.encode_json(value)
        elif context == OutputContext.XML:
            return OutputEncoder.encode_xml(value)
        elif context == OutputContext.SHELL:
            return OutputEncoder.encode_shell(value)
        elif context == OutputContext.SQL:
            return OutputEncoder.encode_sql(value)
        else:
            raise ValueError(f"Unknown output context: {context}")

    @staticmethod
    def encode_html(value: str) -> str:
        """Encode for HTML content"""
        return html.escape(value, quote=True)

    @staticmethod
    def encode_html_attribute(value: str) -> str:
        """Encode for HTML attribute"""
        # More aggressive encoding for attributes
        encoded = html.escape(value, quote=True)
        # Also encode single quotes
        encoded = encoded.replace("'", "&#x27;")
        return encoded

    @staticmethod
    def encode_javascript(value: str) -> str:
        """Encode for JavaScript string"""
        # Escape special characters
        replacements = {
            '\\': '\\\\',
            '"': '\\"',
            "'": "\\'",
            '\n': '\\n',
            '\r': '\\r',
            '\t': '\\t',
            '<': '\\x3C',  # Prevent </script> injection
            '>': '\\x3E',
        }
        for old, new in replacements.items():
            value = value.replace(old, new)
        return value

    @staticmethod
    def encode_css(value: str) -> str:
        """Encode for CSS"""
        # Only allow alphanumeric and safe characters
        safe_chars = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_')
        return ''.join(c if c in safe_chars else f'\\{ord(c):x}' for c in value)

    @staticmethod
    def encode_url(value: str) -> str:
        """Encode for URL"""
        return quote(value, safe='')

    @staticmethod
    def encode_url_parameter(value: str) -> str:
        """Encode for URL parameter"""
        return quote_plus(value)

    @staticmethod
    def encode_json(value: Any) -> str:
        """Encode for JSON"""
        return json.dumps(value, ensure_ascii=True)

    @staticmethod
    def encode_xml(value: str) -> str:
        """Encode for XML"""
        replacements = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': r'&quot;',
            "'": r'&apos;',
        }
        for old, new in replacements.items():
            value = value.replace(old, new)
        return value

    @staticmethod
    def encode_shell(value: str) -> str:
        """Encode for shell command"""
        # Use shlex.quote for safe shell escaping
        return shlex.quote(value)

    @staticmethod
    def encode_sql(value: str) -> str:
        """Encode for SQL (basic escaping, prefer parameterized queries)"""
        # Escape single quotes
        return value.replace("'", "''")


class CommandInjectionPreventer:
    """
    Prevents command injection attacks.

    PRINCIPLE: Never execute user input directly as shell commands.
    """

    # Allowed commands (allowlist approach)
    ALLOWED_COMMANDS = {
        'ls', 'cat', 'grep', 'find', 'echo', 'pwd', 'date',
        'python', 'node', 'npm', 'git'
    }

    # Dangerous patterns
    DANGEROUS_PATTERNS = [
        r'[;&|`$()]',  # Shell metacharacters
        r'>\s*/',      # Output redirection
        r'<\s*/',      # Input redirection
        r'\$\(',       # Command substitution
        r'`',          # Backtick substitution
        r'\|\s*\w+',   # Pipe to command
    ]

    @staticmethod
    def is_safe_command(command: str) -> bool:
        """
        Check if command is safe to execute.

        Args:
            command: Command string

        Returns:
            True if safe, False otherwise
        """
        # Check for dangerous patterns
        for pattern in CommandInjectionPreventer.DANGEROUS_PATTERNS:
            if re.search(pattern, command):
                return False

        # Parse command
        try:
            parts = shlex.split(command)
        except ValueError:
            return False

        if not parts:
            return False

        # Check if base command is allowed
        base_command = parts[0]
        if base_command not in CommandInjectionPreventer.ALLOWED_COMMANDS:
            return False

        return True

    @staticmethod
    def sanitize_command(command: str) -> List[str]:
        """
        Sanitize command into safe argument list.

        Args:
            command: Command string

        Returns:
            List of command arguments

        Raises:
            InjectionAttemptError: If command is unsafe
        """
        if not CommandInjectionPreventer.is_safe_command(command):
            raise InjectionAttemptError(f"Unsafe command detected: {command}")

        return shlex.split(command)


class PathTraversalPreventer:
    """
    Prevents path traversal attacks.

    PRINCIPLE: Validate all file paths and restrict to allowed directories.
    """

    def __init__(self, allowed_base_paths: List[str]):
        """
        Initialize path traversal preventer.

        Args:
            allowed_base_paths: List of allowed base directory paths
        """
        self.allowed_base_paths = [Path(p).resolve() for p in allowed_base_paths]

    def is_safe_path(self, path: str) -> bool:
        """
        Check if path is safe (no traversal, within allowed directories).

        Args:
            path: File path to check

        Returns:
            True if safe, False otherwise
        """
        try:
            # Resolve path
            resolved = Path(path).resolve()

            # Check if within any allowed base path
            for base_path in self.allowed_base_paths:
                try:
                    resolved.relative_to(base_path)
                    return True
                except ValueError:
                    continue

            return False
        except Exception as exc:
            logger.debug("Suppressed exception: %s", exc)
            return False

    def sanitize_path(self, path: str) -> Path:
        """
        Sanitize path and ensure it's safe.

        Args:
            path: File path

        Returns:
            Sanitized Path object

        Raises:
            InjectionAttemptError: If path is unsafe
        """
        if not self.is_safe_path(path):
            raise InjectionAttemptError(f"Unsafe path detected: {path}")

        return Path(path).resolve()


@dataclass
class HardeningStatistics:
    """Statistics for hardening operations"""
    total_validations: int = 0
    successful_validations: int = 0
    failed_validations: int = 0
    injection_attempts_blocked: int = 0
    path_traversal_attempts_blocked: int = 0
    command_injection_attempts_blocked: int = 0

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "total_validations": self.total_validations,
            "successful_validations": self.successful_validations,
            "failed_validations": self.failed_validations,
            "injection_attempts_blocked": self.injection_attempts_blocked,
            "path_traversal_attempts_blocked": self.path_traversal_attempts_blocked,
            "command_injection_attempts_blocked": self.command_injection_attempts_blocked
        }
