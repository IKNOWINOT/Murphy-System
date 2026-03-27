"""
Schema Registry Data Models

Data models for bot I/O schema contracts derived from org chart artifacts.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


@dataclass
class SchemaField:
    """A single field in an artifact schema."""

    name: str
    field_type: str  # 'string', 'number', 'boolean', 'object', 'array'
    required: bool = True
    description: str = ""
    constraints: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ArtifactSchema:
    """Schema definition for a single artifact (input or output)."""

    artifact_name: str
    direction: str  # 'input' or 'output'
    fields: List[SchemaField]
    description: str = ""
    format_hint: str = ""  # 'json', 'csv', 'pdf', 'markdown'


@dataclass
class BotContract:
    """Full I/O contract for a single bot, derived from its RoleTemplate."""

    bot_name: str
    role_name: str
    input_schemas: List[ArtifactSchema]
    output_schemas: List[ArtifactSchema]
    authority_level: Any  # AuthorityLevel enum from org_compiler
    requires_human_signoff: Any  # list of action strings
    registered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def input_artifact_names(self) -> List[str]:
        """Return names of all input artifacts."""
        return [s.artifact_name for s in self.input_schemas]

    def output_artifact_names(self) -> List[str]:
        """Return names of all output artifacts."""
        return [s.artifact_name for s in self.output_schemas]


@dataclass
class SchemaCompatibility:
    """Result of a schema compatibility check."""

    is_compatible: bool
    mismatches: List[str]


@dataclass
class HandoffValidation:
    """Validation result for a single handoff event."""

    from_role: str
    to_role: str
    artifact: Any  # WorkArtifact or compatible object
    compatible: bool
    mismatches: List[str]
