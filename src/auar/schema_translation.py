"""
AUAR Layer 4 — Schema Translation Layer
=========================================

Dynamic schema mapping and data transformation between the AUAR
canonical format and individual provider-specific schemas.

Supports bidirectional translation (request → provider, provider →
response), type coercion, default injection, and field renaming.

Copyright 2024 Inoni LLC – BSL-1.1
"""

import copy
import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple
from uuid import uuid4

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class FieldMapping:
    """Maps a source field to a target field with optional transform."""
    source_field: str
    target_field: str
    transform: Optional[str] = None  # e.g. "to_upper", "to_int", "iso_date"
    default_value: Any = None
    required: bool = False


@dataclass
class SchemaMapping:
    """Complete mapping between canonical schema and provider schema."""
    mapping_id: str = field(default_factory=lambda: str(uuid4()))
    capability_name: str = ""
    provider_id: str = ""
    direction: str = "request"  # "request" or "response"
    field_mappings: List[FieldMapping] = field(default_factory=list)
    static_fields: Dict[str, Any] = field(default_factory=dict)
    version: str = "1.0.0"


@dataclass
class TranslationResult:
    """Result of a schema translation operation."""
    success: bool = True
    translated_data: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    fields_mapped: int = 0
    fields_defaulted: int = 0


# ---------------------------------------------------------------------------
# Built-in transforms
# ---------------------------------------------------------------------------

_BUILTIN_TRANSFORMS: Dict[str, Callable[[Any], Any]] = {
    "to_str": lambda v: str(v) if v is not None else "",
    "to_int": lambda v: int(v) if v is not None else 0,
    "to_float": lambda v: float(v) if v is not None else 0.0,
    "to_bool": lambda v: bool(v),
    "to_upper": lambda v: str(v).upper(),
    "to_lower": lambda v: str(v).lower(),
    "strip": lambda v: str(v).strip(),
    "identity": lambda v: v,
}


# ---------------------------------------------------------------------------
# Schema Translator
# ---------------------------------------------------------------------------

class SchemaTranslator:
    """Bidirectional schema translation engine.

    Register ``SchemaMapping`` objects for capability-provider pairs,
    then call ``translate_request`` / ``translate_response`` to convert
    data between canonical and provider formats.
    """

    def __init__(self):
        # Key: (capability, provider_id, direction) → SchemaMapping
        self._mappings: Dict[Tuple[str, str, str], SchemaMapping] = {}
        self._custom_transforms: Dict[str, Callable[[Any], Any]] = {}
        self._lock = threading.Lock()
        self._stats = {"translations": 0, "errors": 0}

    # -- Mapping registration -----------------------------------------------

    def register_mapping(self, mapping: SchemaMapping) -> str:
        """Register a schema mapping and return its id."""
        key = (mapping.capability_name, mapping.provider_id, mapping.direction)
        with self._lock:
            self._mappings[key] = mapping
        logger.info(
            "Registered schema mapping: %s / %s (%s)",
            mapping.capability_name,
            mapping.provider_id,
            mapping.direction,
        )
        return mapping.mapping_id

    def register_transform(self, name: str, fn: Callable[[Any], Any]) -> None:
        """Register a custom field transform function."""
        with self._lock:
            self._custom_transforms[name] = fn

    def deregister_provider_mappings(self, provider_id: str) -> int:
        """Remove all schema mappings for a given provider. Returns count removed."""
        removed = 0
        with self._lock:
            keys_to_remove = [
                k for k in self._mappings if k[1] == provider_id
            ]
            for key in keys_to_remove:
                del self._mappings[key]
                removed += 1
        return removed

    def deregister_capability_mappings(self, capability_name: str) -> int:
        """Remove all schema mappings for a given capability. Returns count removed."""
        removed = 0
        with self._lock:
            keys_to_remove = [
                k for k in self._mappings if k[0] == capability_name
            ]
            for key in keys_to_remove:
                del self._mappings[key]
                removed += 1
        return removed

    # -- Translation --------------------------------------------------------

    def translate_request(
        self,
        capability_name: str,
        provider_id: str,
        canonical_data: Dict[str, Any],
    ) -> TranslationResult:
        """Translate canonical request data to provider format."""
        return self._translate(capability_name, provider_id, "request", canonical_data)

    def translate_response(
        self,
        capability_name: str,
        provider_id: str,
        provider_data: Dict[str, Any],
    ) -> TranslationResult:
        """Translate provider response data back to canonical format."""
        return self._translate(capability_name, provider_id, "response", provider_data)

    def _translate(
        self,
        capability_name: str,
        provider_id: str,
        direction: str,
        source_data: Dict[str, Any],
    ) -> TranslationResult:
        key = (capability_name, provider_id, direction)
        with self._lock:
            mapping = self._mappings.get(key)

        result = TranslationResult()

        if not mapping:
            # No mapping registered – pass through unchanged
            result.translated_data = copy.deepcopy(source_data)
            result.warnings.append(
                f"No mapping for {capability_name}/{provider_id}/{direction}; data passed through"
            )
            return result

        translated: Dict[str, Any] = {}
        errors: List[str] = []
        warnings: List[str] = []
        fields_mapped = 0
        fields_defaulted = 0

        for fm in mapping.field_mappings:
            value = self._get_nested(source_data, fm.source_field)

            if value is None and fm.default_value is not None:
                value = fm.default_value
                fields_defaulted += 1
            elif value is None and fm.required:
                errors.append(f"Required field missing: {fm.source_field}")
                continue
            elif value is None:
                continue

            # Apply transform
            if fm.transform:
                value = self._apply_transform(fm.transform, value, errors)

            self._set_nested(translated, fm.target_field, value)
            fields_mapped += 1

        # Inject static fields
        for k, v in mapping.static_fields.items():
            self._set_nested(translated, k, v)

        result.translated_data = translated
        result.errors = errors
        result.warnings = warnings
        result.fields_mapped = fields_mapped
        result.fields_defaulted = fields_defaulted
        result.success = len(errors) == 0

        with self._lock:
            self._stats["translations"] += 1
            if errors:
                self._stats["errors"] += 1

        return result

    # -- Helpers ------------------------------------------------------------

    def _apply_transform(self, name: str, value: Any, errors: List[str]) -> Any:
        fn = _BUILTIN_TRANSFORMS.get(name)
        if not fn:
            with self._lock:
                fn = self._custom_transforms.get(name)
        if not fn:
            errors.append(f"Unknown transform: {name}")
            return value
        try:
            return fn(value)
        except Exception as exc:
            logger.debug("Caught exception: %s", exc)
            errors.append(f"Transform {name} failed: {exc}")
            return value

    @staticmethod
    def _get_nested(data: Dict[str, Any], path: str) -> Any:
        """Retrieve a value from *data* using a dotted path."""
        parts = path.split(".")
        current: Any = data
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None
        return current

    @staticmethod
    def _set_nested(data: Dict[str, Any], path: str, value: Any) -> None:
        """Set a value in *data* using a dotted path."""
        parts = path.split(".")
        current = data
        for part in parts[:-1]:
            current = current.setdefault(part, {})
        current[parts[-1]] = value

    def get_stats(self) -> Dict[str, int]:
        with self._lock:
            return dict(self._stats)
