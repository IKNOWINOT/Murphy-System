"""
LLM Output Schema Validation (GAP-3).

Defines Pydantic models for each structured LLM output type and provides
an :class:`LLMOutputValidator` that validates raw dicts against these schemas,
returning ``(is_valid, parsed_model_or_None, list_of_errors)``.
"""

from typing import Any, Dict, List, Optional, Tuple

try:
    from pydantic import BaseModel, Field, ValidationError, field_validator

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
    from dataclasses import dataclass, field as dc_field

    _PYDANTIC_AVAILABLE = False

    class BaseModel:  # type: ignore[no-redef]
        pass

    class ValidationError(Exception):  # type: ignore[no-redef]
        pass

    @dataclass
    class LLMGeneratedExpert(BaseModel):  # type: ignore[no-redef]
        name: str = ""
        domain: str = ""
        capabilities: List[str] = dc_field(default_factory=list)
        confidence: float = 0.5

    @dataclass
    class LLMGeneratedGate(BaseModel):  # type: ignore[no-redef]
        gate_type: str = ""
        target: str = ""
        trigger_condition: str = ""
        risk_reduction: float = 0.0

    @dataclass
    class LLMGeneratedConstraint(BaseModel):  # type: ignore[no-redef]
        parameter: str = ""
        operator: str = ""
        threshold: float = 0.0
        severity: str = "medium"


class LLMOutputValidator:
    """Validates raw LLM output dicts against structured schemas.

    Each ``validate_*`` method returns a tuple::

        (is_valid: bool, parsed_model | None, errors: List[str])
    """

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
    ) -> Tuple[bool, Optional[BaseModel], List[str]]:
        """Validate a raw dict against the named schema type.

        *schema_type* must be one of ``"expert"``, ``"gate"``, or
        ``"constraint"`` (case-insensitive).
        """
        mapping = {
            "expert": LLMGeneratedExpert,
            "gate": LLMGeneratedGate,
            "constraint": LLMGeneratedConstraint,
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
                return False, None, [str(exc)]


__all__ = [
    "LLMGeneratedExpert",
    "LLMGeneratedGate",
    "LLMGeneratedConstraint",
    "LLMOutputValidator",
]
