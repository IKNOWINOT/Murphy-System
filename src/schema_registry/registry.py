"""
Schema Registry

Central registry of bot I/O schemas derived from org chart artifacts.

Each role in the org chart has input_artifacts and output_artifacts.
The SchemaRegistry:
1. Converts artifact definitions into schema contracts.
2. Tracks which bot consumes/produces which artifacts.
3. Validates that handoff chains have matching schemas.
4. Generates Zod TypeScript schemas for bots.
5. Generates Python dataclass schemas for the Python-side runtime.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .schemas import (
    ArtifactSchema,
    BotContract,
    HandoffValidation,
    SchemaCompatibility,
    SchemaField,
)

logger = logging.getLogger("schema_registry")

# ---------------------------------------------------------------------------
# Template definitions — common artifact type patterns and their default fields
# ---------------------------------------------------------------------------

ARTIFACT_SCHEMA_TEMPLATES: Dict[str, List[SchemaField]] = {
    "report": [
        SchemaField("title", "string"),
        SchemaField("content", "string"),
        SchemaField("sections", "array"),
        SchemaField("metadata", "object", required=False),
    ],
    "code": [
        SchemaField("language", "string"),
        SchemaField("source", "string"),
        SchemaField("tests", "array", required=False),
        SchemaField("dependencies", "array", required=False),
    ],
    "plan": [
        SchemaField("goal", "string"),
        SchemaField("steps", "array"),
        SchemaField("dependencies", "array"),
        SchemaField("timeline", "object", required=False),
        SchemaField("acceptance_tests", "array", required=False),
    ],
    "approval": [
        SchemaField(
            "decision",
            "string",
            constraints={"enum": ["approved", "rejected", "deferred"]},
        ),
        SchemaField("approver", "string"),
        SchemaField("conditions", "array", required=False),
        SchemaField("reason", "string", required=False),
    ],
    "financial": [
        SchemaField("amount", "number"),
        SchemaField("currency", "string"),
        SchemaField("category", "string"),
        SchemaField("period", "string", required=False),
    ],
    "design": [
        SchemaField("format", "string"),
        SchemaField("specifications", "object"),
        SchemaField("revisions", "array", required=False),
    ],
}

_DEFAULT_FIELDS: List[SchemaField] = [
    SchemaField("data", "object"),
    SchemaField("metadata", "object", required=False),
]


class SchemaRegistry:
    """Central registry of bot I/O schemas derived from org chart artifacts."""

    def __init__(self) -> None:
        self.schemas: Dict[str, ArtifactSchema] = {}
        self.bot_contracts: Dict[str, BotContract] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_from_role_template(
        self, role_template: Any, bot_name: str
    ) -> BotContract:
        """Derive and register I/O schemas from a compiled RoleTemplate.

        Args:
            role_template: A RoleTemplate (or compatible object) with
                ``role_name``, ``input_artifacts``, ``output_artifacts``,
                ``decision_authority``, and ``requires_human_signoff``.
            bot_name: Unique identifier for the bot being registered.

        Returns:
            The newly created BotContract.
        """
        input_schemas = []
        for artifact in role_template.input_artifacts:
            artifact_name = self._artifact_to_str(artifact)
            schema = self._derive_schema(artifact_name, "input")
            self.schemas[f"{bot_name}:input:{artifact_name}"] = schema
            input_schemas.append(schema)

        output_schemas = []
        for artifact in role_template.output_artifacts:
            artifact_name = self._artifact_to_str(artifact)
            schema = self._derive_schema(artifact_name, "output")
            self.schemas[f"{bot_name}:output:{artifact_name}"] = schema
            output_schemas.append(schema)

        contract = BotContract(
            bot_name=bot_name,
            role_name=role_template.role_name,
            input_schemas=input_schemas,
            output_schemas=output_schemas,
            authority_level=role_template.decision_authority,
            requires_human_signoff=role_template.requires_human_signoff,
        )
        self.bot_contracts[bot_name] = contract
        return contract

    # ------------------------------------------------------------------
    # Handoff validation
    # ------------------------------------------------------------------

    def validate_handoff_chain(
        self, handoff_events: List[Any]
    ) -> List[HandoffValidation]:
        """Validate that each handoff's output schema matches the receiver's.

        Args:
            handoff_events: List of HandoffEvent (or compatible) objects with
                ``from_role``, ``to_role``, and ``artifact`` attributes.

        Returns:
            List of HandoffValidation results, one per event where both sides
            have a registered contract.
        """
        validations = []
        for event in handoff_events:
            from_contract = self.bot_contracts.get(event.from_role)
            to_contract = self.bot_contracts.get(event.to_role)
            if from_contract and to_contract:
                compatible = self._check_schema_compatibility(
                    from_contract.output_schemas,
                    to_contract.input_schemas,
                    event.artifact,
                )
                validations.append(
                    HandoffValidation(
                        from_role=event.from_role,
                        to_role=event.to_role,
                        artifact=event.artifact,
                        compatible=compatible.is_compatible,
                        mismatches=compatible.mismatches,
                    )
                )
        return validations

    # ------------------------------------------------------------------
    # Code generation — Zod (TypeScript)
    # ------------------------------------------------------------------

    def generate_zod_schemas(self, bot_name: str, output_path: Path) -> Path:
        """Generate a Zod TypeScript schema file for a bot's I/O contract.

        Args:
            bot_name: Name of the registered bot.
            output_path: Directory (or file path) to write the schema file to.
                If a directory is given the file is named ``{bot_name}.schema.ts``.

        Returns:
            Path to the written file.

        Raises:
            ValueError: If no contract is registered for bot_name.
        """
        contract = self.bot_contracts.get(bot_name)
        if not contract:
            raise ValueError(f"No contract registered for {bot_name}")

        output_path = Path(output_path)
        if output_path.is_dir() or not output_path.suffix:
            output_path.mkdir(parents=True, exist_ok=True)
            file_path = output_path / f"{bot_name}.schema.ts"
        else:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            file_path = output_path

        bot_class = self._to_pascal_case(bot_name)
        lines: List[str] = [
            "// Auto-generated by Murphy System SchemaRegistry",
            f"// Bot: {bot_name}",
            'import { z } from "zod";',
            "",
        ]

        lines += self._zod_object_block(
            f"{bot_class}InputSchema", contract.input_schemas
        )
        lines.append("")
        lines += self._zod_object_block(
            f"{bot_class}OutputSchema", contract.output_schemas
        )
        lines.append("")

        file_path.write_text("\n".join(lines), encoding="utf-8")
        return file_path

    def _zod_object_block(
        self, export_name: str, schemas: List[ArtifactSchema]
    ) -> List[str]:
        """Build the lines for a single exported z.object() block."""
        lines = [f"export const {export_name} = z.object({{"]
        for schema in schemas:
            safe_name = schema.artifact_name.replace(" ", "_").replace("-", "_")
            lines.append(f"  {safe_name}: z.object({{")
            for fld in schema.fields:
                zod_expr = self._field_to_zod(fld)
                lines.append(f"    {fld.name}: {zod_expr},")
            lines.append("  }),")
        lines.append("});")
        return lines

    def _field_to_zod(self, fld: SchemaField) -> str:
        """Convert a SchemaField to a Zod type expression string."""
        type_map = {
            "string": "z.string()",
            "number": "z.number()",
            "boolean": "z.boolean()",
            "object": "z.record(z.any())",
            "array": "z.array(z.any())",
        }
        zod_type = type_map.get(fld.field_type, "z.any()")

        if fld.constraints.get("enum"):
            values = fld.constraints["enum"]
            zod_type = f"z.enum({json.dumps(values)})"
        if fld.constraints.get("min") is not None:
            zod_type += f".min({fld.constraints['min']})"

        if not fld.required:
            zod_type += ".optional()"

        return zod_type

    # ------------------------------------------------------------------
    # Code generation — Python dataclasses
    # ------------------------------------------------------------------

    def generate_python_schemas(self, bot_name: str, output_path: Path) -> Path:
        """Generate Python dataclass schemas for a bot's I/O contract.

        Args:
            bot_name: Name of the registered bot.
            output_path: Directory (or file path) to write the schema file to.
                If a directory is given the file is named ``{bot_name}_schemas.py``.

        Returns:
            Path to the written file.

        Raises:
            ValueError: If no contract is registered for bot_name.
        """
        contract = self.bot_contracts.get(bot_name)
        if not contract:
            raise ValueError(f"No contract registered for {bot_name}")

        output_path = Path(output_path)
        if output_path.is_dir() or not output_path.suffix:
            output_path.mkdir(parents=True, exist_ok=True)
            file_path = output_path / f"{bot_name}_schemas.py"
        else:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            file_path = output_path

        lines: List[str] = [
            "# Auto-generated by Murphy System SchemaRegistry",
            f"# Bot: {bot_name}",
            "from dataclasses import dataclass",
            "from typing import Any, List, Optional",
            "",
        ]

        all_schemas = (
            [(s, "Input") for s in contract.input_schemas]
            + [(s, "Output") for s in contract.output_schemas]
        )
        for schema, suffix in all_schemas:
            class_name = (
                self._to_pascal_case(schema.artifact_name.replace(" ", "_")) + suffix
            )
            lines.append("")
            lines.append("@dataclass")
            lines.append(f"class {class_name}:")
            for fld in schema.fields:
                py_type = self._field_to_python_type(fld)
                lines.append(f"    {fld.name}: {py_type}")

        lines.append("")

        file_path.write_text("\n".join(lines), encoding="utf-8")
        return file_path

    def _field_to_python_type(self, fld: SchemaField) -> str:
        """Convert a SchemaField to a Python type annotation string."""
        type_map = {
            "string": "str",
            "number": "float",
            "boolean": "bool",
            "object": "Any",
            "array": "List[Any]",
        }
        py_type = type_map.get(fld.field_type, "Any")

        if fld.constraints.get("enum"):
            py_type = "str"

        if not fld.required:
            py_type = f"Optional[{py_type}] = None"

        return py_type

    # ------------------------------------------------------------------
    # Dependency graph
    # ------------------------------------------------------------------

    def get_dependency_graph(self) -> Dict[str, List[str]]:
        """Build a dependency graph: bot → list of bots its inputs depend on.

        A bot A depends on bot B when A has an input artifact that matches the
        same template pattern as one of B's output artifacts.

        Returns:
            Dict mapping each registered bot name to a list of bot names whose
            outputs feed into it.
        """
        graph: Dict[str, List[str]] = {}

        for bot_name, contract in self.bot_contracts.items():
            dependencies: List[str] = []

            for input_schema in contract.input_schemas:
                input_template = self._get_template_name(input_schema.artifact_name)

                for other_bot, other_contract in self.bot_contracts.items():
                    if other_bot == bot_name:
                        continue
                    if other_bot in dependencies:
                        continue

                    for output_schema in other_contract.output_schemas:
                        output_template = self._get_template_name(
                            output_schema.artifact_name
                        )
                        if input_template is not None and input_template == output_template:
                            dependencies.append(other_bot)
                            break

            graph[bot_name] = dependencies

        return graph

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _artifact_to_str(self, artifact: Any) -> str:
        """Convert an artifact (enum or string) to its string name."""
        if hasattr(artifact, "value"):
            return str(artifact.value)
        return str(artifact)

    def _derive_schema(self, artifact_name: str, direction: str) -> ArtifactSchema:
        """Derive an ArtifactSchema from an artifact name using template matching.

        Iterates through ARTIFACT_SCHEMA_TEMPLATES and returns the fields of the
        first pattern found in the artifact name (case-insensitive).  Falls back
        to a generic two-field schema when no pattern matches.
        """
        artifact_lower = artifact_name.lower()
        matched_fields: Optional[List[SchemaField]] = None

        for pattern, template_fields in ARTIFACT_SCHEMA_TEMPLATES.items():
            if pattern in artifact_lower:
                matched_fields = template_fields
                break

        if matched_fields is None:
            matched_fields = _DEFAULT_FIELDS

        return ArtifactSchema(
            artifact_name=artifact_name,
            direction=direction,
            fields=matched_fields,
        )

    def _get_template_name(self, artifact_name: str) -> Optional[str]:
        """Return the name of the first template pattern matched by artifact_name."""
        artifact_lower = artifact_name.lower()
        for pattern in ARTIFACT_SCHEMA_TEMPLATES:
            if pattern in artifact_lower:
                return pattern
        return None

    def _check_schema_compatibility(
        self,
        output_schemas: List[ArtifactSchema],
        input_schemas: List[ArtifactSchema],
        artifact: Any,
    ) -> SchemaCompatibility:
        """Check whether sender output schemas are compatible with receiver inputs.

        Compatibility is determined by comparing the set of required field names
        of the best-matching output schema against those of the best-matching
        input schema.  Two schemas are compatible when their required field sets
        are identical.

        The "best matching" schema for a side is the one whose artifact_name
        contains the artifact_type string; if none match, the first schema is
        used.
        """
        # Resolve artifact type string
        if hasattr(artifact, "artifact_type"):
            art_type = artifact.artifact_type
            art_type_str = art_type.value if hasattr(art_type, "value") else str(art_type)
        else:
            art_type_str = str(artifact)

        sender_schema = self._best_matching_schema(output_schemas, art_type_str)
        receiver_schema = self._best_matching_schema(input_schemas, art_type_str)

        if sender_schema is None:
            return SchemaCompatibility(
                is_compatible=False,
                mismatches=["No output schema found for artifact"],
            )
        if receiver_schema is None:
            return SchemaCompatibility(
                is_compatible=False,
                mismatches=["No input schema found for receiver"],
            )

        output_required = {f.name for f in sender_schema.fields if f.required}
        input_required = {f.name for f in receiver_schema.fields if f.required}

        mismatches: List[str] = []
        missing_in_input = output_required - input_required
        if missing_in_input:
            mismatches.append(
                f"Input schema missing required fields: {sorted(missing_in_input)}"
            )
        extra_in_input = input_required - output_required
        if extra_in_input:
            mismatches.append(
                f"Output schema missing required fields: {sorted(extra_in_input)}"
            )

        return SchemaCompatibility(
            is_compatible=len(mismatches) == 0,
            mismatches=mismatches,
        )

    def _best_matching_schema(
        self, schemas: List[ArtifactSchema], art_type_str: str
    ) -> Optional[ArtifactSchema]:
        """Return the schema whose artifact_name contains art_type_str, or the first."""
        for schema in schemas:
            if art_type_str in schema.artifact_name.lower():
                return schema
        if schemas:
            return schemas[0]
        return None

    @staticmethod
    def _to_pascal_case(name: str) -> str:
        """Convert snake_case or space-separated name to PascalCase."""
        return "".join(word.capitalize() for word in name.replace("-", "_").split("_"))
