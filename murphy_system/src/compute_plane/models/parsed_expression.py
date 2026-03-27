"""
Parsed Expression Models

Represents parsed and normalized mathematical expressions.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


@dataclass
class ParsedExpression:
    """
    Parsed mathematical expression with uncertainty tracking.

    Attributes:
        original: Original expression string
        parsed: Parsed expression object
        language: Language used for parsing
        uncertainty: Transformation uncertainty (0.0 to 1.0)
        warnings: Parsing warnings
        metadata: Additional metadata
    """

    original: str
    parsed: Any
    language: str
    uncertainty: float = 0.0
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate parsed expression"""
        if self.uncertainty < 0.0 or self.uncertainty > 1.0:
            raise ValueError("Uncertainty must be between 0.0 and 1.0")


@dataclass
class NormalizedExpression:
    """
    Normalized mathematical expression in canonical form.

    Attributes:
        parsed_expr: Original parsed expression
        normalized: Normalized expression object
        canonical_form: Canonical string representation
        variables: Set of variables in expression
        constants: Set of constants in expression
        operations: List of operations used
        complexity: Expression complexity score
        metadata: Additional metadata
    """

    parsed_expr: ParsedExpression
    normalized: Any
    canonical_form: str
    variables: set = field(default_factory=set)
    constants: set = field(default_factory=set)
    operations: List[str] = field(default_factory=list)
    complexity: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate normalized expression"""
        if self.complexity < 0.0:
            raise ValueError("Complexity must be non-negative")
