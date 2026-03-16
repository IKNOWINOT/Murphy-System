"""
Schema Registry Package

Central registry of bot I/O schemas auto-derived from org chart RoleTemplate
artifacts.  Provides:
- SchemaRegistry: registration, validation, and code-generation
- Data models: ArtifactSchema, BotContract, SchemaField, etc.
"""

from .registry import ARTIFACT_SCHEMA_TEMPLATES, SchemaRegistry
from .schemas import (
    ArtifactSchema,
    BotContract,
    HandoffValidation,
    SchemaCompatibility,
    SchemaField,
)

__all__ = [
    "SchemaRegistry",
    "ARTIFACT_SCHEMA_TEMPLATES",
    "ArtifactSchema",
    "BotContract",
    "HandoffValidation",
    "SchemaCompatibility",
    "SchemaField",
]
