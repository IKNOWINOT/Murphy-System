"""
Expression Parser

Parses natural language math into formal expressions with uncertainty tracking.
"""

import logging
import re
from typing import Any, Dict

from ..models.parsed_expression import NormalizedExpression, ParsedExpression
from ..models.validation_result import ValidationResult

logger = logging.getLogger(__name__)


class ExpressionParser:
    """
    Parse natural language math into formal expressions.

    Supports:
    - SymPy expressions
    - Wolfram Language (basic)
    - Linear programming
    - SAT expressions
    """

    def __init__(self):
        """Initialize parser"""
        self.sympy_available = False
        try:
            import sympy
            self.sympy = sympy
            self.sympy_available = True
        except ImportError:
            pass

    def parse(self, expression: str, language: str, assumptions: Dict[str, Any] = None) -> ParsedExpression:
        """
        Parse expression with uncertainty tracking.

        Args:
            expression: Expression string
            language: Language to parse (sympy, wolfram, lp, sat)
            assumptions: Assumptions about variables

        Returns:
            ParsedExpression with parsed object and uncertainty
        """
        assumptions = assumptions or {}

        if language == "sympy":
            return self._parse_sympy(expression, assumptions)
        elif language == "wolfram":
            return self._parse_wolfram(expression, assumptions)
        elif language == "lp":
            return self._parse_lp(expression, assumptions)
        elif language == "sat":
            return self._parse_sat(expression, assumptions)
        else:
            raise ValueError(f"Unsupported language: {language}")

    def _parse_sympy(self, expression: str, assumptions: Dict[str, Any]) -> ParsedExpression:
        """Parse SymPy expression"""
        if not self.sympy_available:
            raise RuntimeError("SymPy not available. Install with: pip install sympy")

        warnings = []
        uncertainty = 0.0

        try:
            # Clean expression
            cleaned = self._clean_expression(expression)
            if cleaned != expression:
                warnings.append(f"Expression cleaned: {expression} -> {cleaned}")
                uncertainty += 0.1

            # Parse with SymPy
            parsed = self.sympy.sympify(cleaned, evaluate=False)

            # Check for undefined symbols
            free_symbols = parsed.free_symbols
            for symbol in free_symbols:
                if str(symbol) not in assumptions:
                    warnings.append(f"Undefined symbol: {symbol}")
                    uncertainty += 0.05

            return ParsedExpression(
                original=expression,
                parsed=parsed,
                language="sympy",
                uncertainty=min(uncertainty, 1.0),
                warnings=warnings,
                metadata={'free_symbols': [str(s) for s in free_symbols]}
            )

        except Exception as exc:
            logger.debug("Caught exception: %s", exc)
            raise ValueError(f"Failed to parse SymPy expression: {exc}")

    def _parse_wolfram(self, expression: str, assumptions: Dict[str, Any]) -> ParsedExpression:
        """Parse Wolfram Language expression (basic support)"""
        warnings = ["Wolfram parsing is basic - full Wolfram Engine not integrated"]

        # For now, store as string (would need Wolfram Engine for full parsing)
        return ParsedExpression(
            original=expression,
            parsed=expression,
            language="wolfram",
            uncertainty=0.3,  # Higher uncertainty without full Wolfram Engine
            warnings=warnings,
            metadata={'note': 'Basic Wolfram support - full engine not integrated'}
        )

    def _parse_lp(self, expression: str, assumptions: Dict[str, Any]) -> ParsedExpression:
        """Parse linear programming expression"""
        warnings = []

        # Basic LP parsing (would need proper LP parser for production)
        # Format: "minimize: c1*x1 + c2*x2 subject to: a1*x1 + a2*x2 <= b"

        if "minimize" not in expression.lower() and "maximize" not in expression.lower():
            warnings.append("No objective function found (minimize/maximize)")

        if "subject to" not in expression.lower():
            warnings.append("No constraints found (subject to)")

        return ParsedExpression(
            original=expression,
            parsed=expression,
            language="lp",
            uncertainty=0.2,
            warnings=warnings,
            metadata={'note': 'Basic LP support'}
        )

    def _parse_sat(self, expression: str, assumptions: Dict[str, Any]) -> ParsedExpression:
        """Parse SAT expression"""
        warnings = []

        # Basic SAT parsing (would need proper SAT parser for production)
        # Format: "(x1 OR x2) AND (NOT x3 OR x4)"

        if not any(op in expression.upper() for op in ['AND', 'OR', 'NOT']):
            warnings.append("No boolean operators found (AND/OR/NOT)")

        return ParsedExpression(
            original=expression,
            parsed=expression,
            language="sat",
            uncertainty=0.2,
            warnings=warnings,
            metadata={'note': 'Basic SAT support'}
        )

    def normalize(self, parsed_expr: ParsedExpression) -> NormalizedExpression:
        """
        Normalize parsed expression to canonical form.

        Args:
            parsed_expr: Parsed expression

        Returns:
            NormalizedExpression in canonical form
        """
        if parsed_expr.language == "sympy" and self.sympy_available:
            return self._normalize_sympy(parsed_expr)
        else:
            # For other languages, return as-is
            return NormalizedExpression(
                parsed_expr=parsed_expr,
                normalized=parsed_expr.parsed,
                canonical_form=str(parsed_expr.parsed),
                complexity=self._estimate_complexity(str(parsed_expr.parsed))
            )

    def _normalize_sympy(self, parsed_expr: ParsedExpression) -> NormalizedExpression:
        """Normalize SymPy expression"""
        expr = parsed_expr.parsed

        # Simplify expression
        normalized = self.sympy.simplify(expr)

        # Extract variables and constants
        variables = {str(s) for s in normalized.free_symbols}
        constants = set()

        # Extract operations
        operations = []
        if hasattr(normalized, 'func'):
            operations.append(str(normalized.func))

        # Compute complexity (number of operations)
        complexity = len(str(normalized))

        return NormalizedExpression(
            parsed_expr=parsed_expr,
            normalized=normalized,
            canonical_form=str(normalized),
            variables=variables,
            constants=constants,
            operations=operations,
            complexity=complexity
        )

    def validate_syntax(self, expression: str, language: str) -> ValidationResult:
        """
        Validate expression syntax.

        Args:
            expression: Expression string
            language: Language to validate

        Returns:
            ValidationResult with errors and warnings
        """
        result = ValidationResult(is_valid=True)

        # Check for empty expression
        if not expression or not expression.strip():
            result.add_error("Expression is empty")
            return result

        # Try to parse
        try:
            parsed = self.parse(expression, language)

            # Add warnings from parsing
            for warning in parsed.warnings:
                result.add_warning(warning)

            # Check uncertainty
            if parsed.uncertainty > 0.5:
                result.add_warning(f"High parsing uncertainty: {parsed.uncertainty:.2f}")

        except Exception as exc:
            logger.debug("Caught exception: %s", exc)
            result.add_error(f"Syntax error: {exc}")
            result.add_suggestion("Check expression syntax and try again")

        return result

    def _clean_expression(self, expression: str) -> str:
        """Clean expression string"""
        # Remove extra whitespace
        cleaned = ' '.join(expression.split())

        # Replace common natural language patterns
        replacements = {
            ' times ': '*',
            ' plus ': '+',
            ' minus ': '-',
            ' divided by ': '/',
            ' to the power of ': '**',
            '^': '**',  # Convert ^ to **
        }

        for old, new in replacements.items():
            cleaned = cleaned.replace(old, new)

        return cleaned

    def _estimate_complexity(self, expression: str) -> float:
        """Estimate expression complexity"""
        # Simple heuristic: length + number of operators
        operators = ['+', '-', '*', '/', '**', '(', ')']
        complexity = len(expression)
        complexity += sum(expression.count(op) for op in operators)
        return complexity
