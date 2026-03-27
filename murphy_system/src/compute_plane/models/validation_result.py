"""
Validation Result Model

Represents the result of expression validation.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """
    Result of expression validation.

    Attributes:
        is_valid: Whether expression is valid
        errors: List of validation errors
        warnings: List of validation warnings
        suggestions: List of suggestions for fixing errors
        metadata: Additional metadata
    """

    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_error(self, error: str):
        """Add validation error"""
        self.errors.append(error)
        self.is_valid = False

    def add_warning(self, warning: str):
        """Add validation warning"""
        self.warnings.append(warning)

    def add_suggestion(self, suggestion: str):
        """Add suggestion"""
        self.suggestions.append(suggestion)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'is_valid': self.is_valid,
            'errors': self.errors,
            'warnings': self.warnings,
            'suggestions': self.suggestions,
            'metadata': self.metadata,
        }
