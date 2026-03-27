"""
Formal State Vector Schema (Gap CFP-1).

Provides a Pydantic-backed typed state vector with per-dimension uncertainty
tracking, schema versioning, and a registry for domain-scoped schemas.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Type

logger = logging.getLogger(__name__)

try:
    from pydantic import BaseModel, Field, field_validator

    class StateVariable(BaseModel):
        """A single named dimension in the state vector."""

        name: str
        value: Any
        dtype: str = "float"
        uncertainty: float = Field(default=0.0, ge=0.0, le=1.0)
        source: str = ""
        updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
        domain: str = ""

        @field_validator("dtype", mode="before")
        @classmethod
        def _validate_dtype(cls, v: str) -> str:
            allowed = {"float", "bool", "str", "int"}
            if str(v) not in allowed:
                raise ValueError(f"dtype must be one of {allowed}, got {v!r}")
            return str(v)

    class StateVectorSchema(BaseModel):
        """Schema descriptor for a typed state vector in a given domain."""

        schema_version: str = "1.0"
        domain: str
        dimensions: List[StateVariable] = Field(default_factory=list)
        created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
        updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    _PYDANTIC_AVAILABLE = True

except ImportError:
    from dataclasses import dataclass  # type: ignore[no-redef]
    from dataclasses import field as dc_field

    _PYDANTIC_AVAILABLE = False

    class BaseModel:  # type: ignore[no-redef]
        """Base model."""
        pass

    @dataclass
    class StateVariable(BaseModel):  # type: ignore[no-redef]
        """State variable."""
        name: str = ""
        value: Any = None
        dtype: str = "float"
        uncertainty: float = 0.0
        source: str = ""
        updated_at: datetime = dc_field(default_factory=lambda: datetime.now(timezone.utc))
        domain: str = ""

    @dataclass
    class StateVectorSchema(BaseModel):  # type: ignore[no-redef]
        """State vector schema."""
        domain: str = ""
        schema_version: str = "1.0"
        dimensions: List[StateVariable] = dc_field(default_factory=list)
        created_at: datetime = dc_field(default_factory=lambda: datetime.now(timezone.utc))
        updated_at: datetime = dc_field(default_factory=lambda: datetime.now(timezone.utc))


class TypedStateVector:
    """Wraps ``Dict[str, Any]`` and enforces a :class:`StateVectorSchema`.

    Each dimension is stored as a :class:`StateVariable` so that per-variable
    uncertainty, dtype, and provenance are always available.
    """

    def __init__(self, schema: Optional[StateVectorSchema] = None) -> None:
        self._schema = schema or StateVectorSchema(domain="default")
        self._dimensions: Dict[str, StateVariable] = {
            v.name: v for v in self._schema.dimensions
        }

    # ------------------------------------------------------------------
    # Core accessors
    # ------------------------------------------------------------------

    def get(self, name: str) -> Optional[StateVariable]:
        """Return the :class:`StateVariable` for *name*, or ``None``."""
        return self._dimensions.get(name)

    def set(
        self,
        name: str,
        value: Any,
        uncertainty: float = 0.0,
        source: str = "",
        dtype: str = "float",
        domain: str = "",
    ) -> None:
        """Create or update the dimension *name*."""
        if name in self._dimensions:
            existing = self._dimensions[name]
            updated = StateVariable(
                name=name,
                value=value,
                dtype=existing.dtype,
                uncertainty=uncertainty,
                source=source or existing.source,
                domain=existing.domain if existing.domain else domain,
            )
        else:
            updated = StateVariable(
                name=name,
                value=value,
                dtype=dtype,
                uncertainty=uncertainty,
                source=source,
                domain=domain,
            )
        self._dimensions[name] = updated

    # ------------------------------------------------------------------
    # Schema-level helpers
    # ------------------------------------------------------------------

    def dimensionality(self) -> int:
        """Return the number of tracked dimensions."""
        return len(self._dimensions)

    def uncertainty_vector(self) -> List[float]:
        """Return a list of per-dimension uncertainties in insertion order."""
        return [v.uncertainty for v in self._dimensions.values()]

    # Alias used in the problem statement
    def to_uncertainty_vector(self) -> List[float]:
        """Alias for :meth:`uncertainty_vector`."""
        return self.uncertainty_vector()

    def expand(self, new_variable: StateVariable) -> None:
        """Add *new_variable* as a new dimension (schema migration).

        If a dimension with the same name already exists it is overwritten.
        The schema's *updated_at* timestamp is refreshed.
        """
        self._dimensions[new_variable.name] = new_variable
        self._schema.updated_at = datetime.now(timezone.utc)
        # Rebuild schema.dimensions to stay in sync
        self._schema.dimensions = list(self._dimensions.values())

    def expand_state(self, new_variable: StateVariable) -> None:
        """Convenience alias for :meth:`expand`."""
        self.expand(new_variable)

    def validate(self) -> bool:
        """Return ``True`` when all dimensions have valid uncertainty in [0, 1].

        Returns ``False`` if any dimension has an uncertainty outside [0, 1] or
        a missing/empty name.
        """
        for name, var in self._dimensions.items():
            if not name:
                return False
            if not (0.0 <= var.uncertainty <= 1.0):
                return False
        return True

    # ------------------------------------------------------------------
    # Dict-like helpers for backward compatibility
    # ------------------------------------------------------------------

    def __contains__(self, name: str) -> bool:
        return name in self._dimensions

    def keys(self) -> List[str]:
        return list(self._dimensions.keys())

    def values(self) -> List[StateVariable]:
        return list(self._dimensions.values())


class StateVectorRegistry:
    """Tracks :class:`StateVectorSchema` instances per domain with versioning."""

    def __init__(self) -> None:
        # domain -> list of schemas (newest last)
        self._schemas: Dict[str, List[StateVectorSchema]] = {}

    def register(self, schema: StateVectorSchema) -> None:
        """Register *schema* for its domain, incrementing the version."""
        domain = schema.domain
        if domain not in self._schemas:
            self._schemas[domain] = []
        self._schemas[domain].append(schema)

    def get_latest(self, domain: str) -> Optional[StateVectorSchema]:
        """Return the most recently registered schema for *domain*."""
        versions = self._schemas.get(domain)
        if not versions:
            return None
        return versions[-1]

    def get_version(self, domain: str, schema_version: str) -> Optional[StateVectorSchema]:
        """Return a specific version of the schema for *domain*."""
        for s in self._schemas.get(domain, []):
            if s.schema_version == schema_version:
                return s
        return None

    def list_domains(self) -> List[str]:
        """Return all registered domain names."""
        return list(self._schemas.keys())

    def migrate(self, state: TypedStateVector, target_schema: StateVectorSchema) -> TypedStateVector:
        """Migrate *state* to *target_schema* by adding missing dimensions."""
        new_sv = TypedStateVector(schema=target_schema)
        # Carry over existing values
        for name, var in state._dimensions.items():
            new_sv._dimensions[name] = var
        # Add dimensions present in target but not in source
        for dim in target_schema.dimensions:
            if dim.name not in new_sv._dimensions:
                new_sv._dimensions[dim.name] = dim
        return new_sv


__all__ = [
    "StateVariable",
    "StateVectorSchema",
    "TypedStateVector",
    "StateVectorRegistry",
]
