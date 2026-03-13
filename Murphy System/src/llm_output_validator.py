"""
LLM Output Schema Validation (GAP-3 / CFP-6).

Defines Pydantic models for each structured LLM output type and provides
an :class:`LLMOutputValidator` that validates raw dicts against these schemas,
returning ``(is_valid, parsed_model_or_None, list_of_errors)``.

Also exposes :class:`LLMOutputEnvelope` and :class:`ValidationResult` for
envelope-level validation workflows (Gap CFP-6).
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Type

logger = logging.getLogger(__name__)

try:
    from pydantic import BaseModel, Field, ValidationError, field_validator

    # ------------------------------------------------------------------
    # Envelope-level models (CFP-6)
    # ------------------------------------------------------------------

    class ValidationResult(BaseModel):
        """Result of validating an LLM output envelope."""

        valid: bool
        errors: List[str] = Field(default_factory=list)
        warnings: List[str] = Field(default_factory=list)
        confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    class LLMOutputEnvelope(BaseModel):
        """Envelope wrapping a raw LLM output with metadata for validation."""

        output_type: str
        raw_output: str = ""
        parsed_output: Dict[str, Any] = Field(default_factory=dict)
        schema_version: str = "1.0"
        validation_result: Optional[ValidationResult] = None
        timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # ------------------------------------------------------------------
    # Pre-registered output schemas
    # ------------------------------------------------------------------

    class LLMExpansionResult(BaseModel):
        """Schema for an LLM-generated state-expansion result."""

        new_dimension: str
        initial_value: float = Field(default=0.0)
        uncertainty: float = Field(default=0.5, ge=0.0, le=1.0)
        rationale: str = ""

    class LLMGeneratedExpert(BaseModel):
        """Schema for an LLM-generated domain expert."""

        name: str
        domain: str
        capabilities: List[str]
        confidence: float = Field(default=0.5, ge=0.0, le=1.0)

        @field_validator("capabilities", mode="before")
        @classmethod
        def ensure_list(cls, v: Any) -> List[str]:
            if isinstance(v, str):
                return [v]
            return list(v)

    class LLMGeneratedGate(BaseModel):
        """Schema for an LLM-generated control gate."""

        gate_type: str
        target: str
        trigger_condition: str
        risk_reduction: float = Field(default=0.0, ge=0.0, le=1.0)

    class LLMGeneratedConstraint(BaseModel):
        """Schema for an LLM-generated system constraint."""

        parameter: str
        operator: str
        threshold: float
        severity: str = "medium"

        @field_validator("severity", mode="before")
        @classmethod
        def validate_severity(cls, v: str) -> str:
            allowed = {"low", "medium", "high", "critical"}
            if str(v).lower() not in allowed:
                raise ValueError(f"severity must be one of {allowed}")
            return str(v).lower()

    _PYDANTIC_AVAILABLE = True

except ImportError:
    # Minimal fallback stubs when pydantic is not installed
    from dataclasses import dataclass
    from dataclasses import field as dc_field

    _PYDANTIC_AVAILABLE = False

    class BaseModel:  # type: ignore[no-redef]
        """Base model."""
        pass

    class ValidationError(Exception):  # type: ignore[no-redef]
        """Validation error (Exception subclass)."""
        pass

    @dataclass
    class ValidationResult(BaseModel):  # type: ignore[no-redef]
        """Validation result."""
        valid: bool = True
        errors: List[str] = dc_field(default_factory=list)
        warnings: List[str] = dc_field(default_factory=list)
        confidence: float = 1.0

    @dataclass
    class LLMOutputEnvelope(BaseModel):  # type: ignore[no-redef]
        """LLM output envelope."""
        output_type: str = ""
        raw_output: str = ""
        parsed_output: Dict[str, Any] = dc_field(default_factory=dict)
        schema_version: str = "1.0"
        validation_result: Optional["ValidationResult"] = None
        timestamp: datetime = dc_field(default_factory=lambda: datetime.now(timezone.utc))

    @dataclass
    class LLMExpansionResult(BaseModel):  # type: ignore[no-redef]
        """LLM expansion result."""
        new_dimension: str = ""
        initial_value: float = 0.0
        uncertainty: float = 0.5
        rationale: str = ""

    @dataclass
    class LLMGeneratedExpert(BaseModel):  # type: ignore[no-redef]
        """LLM generated expert."""
        name: str = ""
        domain: str = ""
        capabilities: List[str] = dc_field(default_factory=list)
        confidence: float = 0.5

    @dataclass
    class LLMGeneratedGate(BaseModel):  # type: ignore[no-redef]
        """LLM generated gate."""
        gate_type: str = ""
        target: str = ""
        trigger_condition: str = ""
        risk_reduction: float = 0.0

    @dataclass
    class LLMGeneratedConstraint(BaseModel):  # type: ignore[no-redef]
        """LLM generated constraint."""
        parameter: str = ""
        operator: str = ""
        threshold: float = 0.0
        severity: str = "medium"


class LLMOutputValidator:
    """Validates raw LLM output dicts against structured schemas.

    Each ``validate_*`` method returns a tuple::

        (is_valid: bool, parsed_model | None, errors: List[str])

    The envelope-level API (``register_schema``, ``validate``,
    ``validate_and_reject``) handles :class:`LLMOutputEnvelope` objects and
    uses schemas registered via :meth:`register_schema`.
    """

    # Pre-registered output-type → schema class mapping
    _BUILTIN_SCHEMAS: Dict[str, type] = {}

    def __init__(self) -> None:
        # Start with the built-in schemas; callers can add more.
        self._schemas: Dict[str, type] = dict(self._BUILTIN_SCHEMAS)

    # ------------------------------------------------------------------
    # Envelope-level API (CFP-6)
    # ------------------------------------------------------------------

    def register_schema(self, output_type: str, schema: Type[BaseModel]) -> None:  # type: ignore[valid-type]
        """Register *schema* for *output_type* for envelope-level validation."""
        self._schemas[output_type.lower()] = schema

    def validate(self, envelope: LLMOutputEnvelope) -> ValidationResult:  # type: ignore[valid-type]
        """Validate *envelope.parsed_output* against the registered schema.

        Returns a :class:`ValidationResult` (always; never raises).
        """
        output_type = envelope.output_type.lower()
        schema_cls = self._schemas.get(output_type)
        if schema_cls is None:
            return ValidationResult(  # type: ignore[call-arg]
                valid=False,
                errors=[f"No schema registered for output_type {output_type!r}"],
                confidence=0.0,
            )
        ok, _, errors = self._validate(envelope.parsed_output, schema_cls)
        return ValidationResult(  # type: ignore[call-arg]
            valid=ok,
            errors=errors,
            confidence=1.0 if ok else 0.0,
        )

    def validate_and_reject(
        self, envelope: LLMOutputEnvelope  # type: ignore[valid-type]
    ) -> Tuple[bool, Optional[Any]]:
        """Validate envelope and return ``(True, parsed_model)`` or ``(False, None)``."""
        output_type = envelope.output_type.lower()
        schema_cls = self._schemas.get(output_type)
        if schema_cls is None:
            return False, None
        ok, obj, _ = self._validate(envelope.parsed_output, schema_cls)
        return ok, obj if ok else None

    def validate_expert(
        self, raw_output: Dict[str, Any]
    ) -> Tuple[bool, Optional[LLMGeneratedExpert], List[str]]:
        """Validate a raw dict as a :class:`LLMGeneratedExpert`."""
        return self._validate(raw_output, LLMGeneratedExpert)

    def validate_gate(
        self, raw_output: Dict[str, Any]
    ) -> Tuple[bool, Optional[LLMGeneratedGate], List[str]]:
        """Validate a raw dict as a :class:`LLMGeneratedGate`."""
        return self._validate(raw_output, LLMGeneratedGate)

    def validate_constraint(
        self, raw_output: Dict[str, Any]
    ) -> Tuple[bool, Optional[LLMGeneratedConstraint], List[str]]:
        """Validate a raw dict as a :class:`LLMGeneratedConstraint`."""
        return self._validate(raw_output, LLMGeneratedConstraint)

    def validate_any(
        self, raw_output: Dict[str, Any], schema_type: str
    ) -> Tuple[bool, Optional[BaseModel], List[str]]:  # type: ignore[valid-type]
        """Validate a raw dict against the named schema type.

        *schema_type* must be one of ``"expert"``, ``"gate"``,
        ``"constraint"``, or ``"expansion_result"`` (case-insensitive).
        """
        mapping: Dict[str, type] = {
            "expert": LLMGeneratedExpert,
            "generated_expert": LLMGeneratedExpert,
            "gate": LLMGeneratedGate,
            "domain_gate": LLMGeneratedGate,
            "constraint": LLMGeneratedConstraint,
            "expansion_result": LLMExpansionResult,
        }
        cls = mapping.get(schema_type.lower())
        if cls is None:
            return False, None, [f"Unknown schema_type: {schema_type!r}"]
        return self._validate(raw_output, cls)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate(
        raw_output: Dict[str, Any], model_cls: type
    ) -> Tuple[bool, Optional[Any], List[str]]:
        if not isinstance(raw_output, dict):
            return False, None, ["Input must be a dict"]
        if _PYDANTIC_AVAILABLE:
            try:
                obj = model_cls(**raw_output)
                return True, obj, []
            except ValidationError as exc:
                errors = [str(e["msg"]) for e in exc.errors()]
                return False, None, errors
            except TypeError as exc:
                return False, None, [str(exc)]
        else:
            # Fallback: basic key-presence check
            errors: List[str] = []
            required = {
                LLMGeneratedExpert: ["name", "domain", "capabilities"],
                LLMGeneratedGate: ["gate_type", "target", "trigger_condition"],
                LLMGeneratedConstraint: ["parameter", "operator", "threshold"],
            }.get(model_cls, [])
            for key in required:
                if key not in raw_output:
                    errors.append(f"Missing required field: {key!r}")
            if errors:
                return False, None, errors
            try:
                obj = model_cls(**{k: raw_output.get(k, getattr(model_cls, k, None)) for k in required})
                return True, obj, []
            except Exception as exc:
                logger.debug("Caught exception: %s", exc)
                return False, None, [str(exc)]


__all__ = [
    "LLMGeneratedExpert",
    "LLMGeneratedGate",
    "LLMGeneratedConstraint",
    "LLMExpansionResult",
    "LLMOutputEnvelope",
    "ValidationResult",
    "LLMOutputValidator",
]


# ------------------------------------------------------------------
# Pre-register built-in schemas so all instances share them
# ------------------------------------------------------------------
LLMOutputValidator._BUILTIN_SCHEMAS = {
    "generated_expert": LLMGeneratedExpert,
    "domain_gate": LLMGeneratedGate,
    "constraint": LLMGeneratedConstraint,
    "expansion_result": LLMExpansionResult,
}
