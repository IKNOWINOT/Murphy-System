"""
Tests for the SchemaRegistry module.

Covers:
1. register_from_role_template — contract has correct input/output schemas
2. validate_handoff_chain — compatible schemas (both 'code' template)
3. validate_handoff_chain — incompatible schemas (different templates)
4. generate_zod_schemas — produces valid TypeScript with z.object() wrapping
5. generate_python_schemas — produces valid Python dataclass definitions
6. get_dependency_graph — maps bot→bot dependencies through shared templates
7. _derive_schema — "quarterly financial report" matches financial/report template
"""

import tempfile
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime, timezone

import pytest

from src.schema_registry import (
    ARTIFACT_SCHEMA_TEMPLATES,
    SchemaRegistry,
)
from src.org_compiler.schemas import ArtifactType, AuthorityLevel


# ---------------------------------------------------------------------------
# Helpers — build lightweight role-template stand-ins
# ---------------------------------------------------------------------------

def _make_role(
    role_name: str,
    input_artifacts,
    output_artifacts,
    authority=AuthorityLevel.LOW,
    signoff=None,
) -> SimpleNamespace:
    """Return a minimal object that satisfies register_from_role_template."""
    return SimpleNamespace(
        role_name=role_name,
        input_artifacts=input_artifacts,
        output_artifacts=output_artifacts,
        decision_authority=authority,
        requires_human_signoff=signoff or [],
    )


def _make_artifact(artifact_type: ArtifactType, artifact_id: str = "a1") -> SimpleNamespace:
    """Return a minimal WorkArtifact-like object."""
    return SimpleNamespace(
        artifact_id=artifact_id,
        artifact_type=artifact_type,
        producer_role="test",
        consumer_roles=[],
        content_hash="abc",
    )


_FIXED_TIMESTAMP = datetime(2024, 1, 1, tzinfo=timezone.utc)


def _make_handoff(
    from_role: str,
    to_role: str,
    artifact_type: ArtifactType,
) -> SimpleNamespace:
    """Return a minimal HandoffEvent-like object."""
    return SimpleNamespace(
        event_id="e1",
        from_role=from_role,
        to_role=to_role,
        artifact=_make_artifact(artifact_type),
        timestamp=_FIXED_TIMESTAMP,
    )


# ===========================================================================
# 1. register_from_role_template
# ===========================================================================

class TestRegisterFromRoleTemplate:
    """Verify that register_from_role_template produces correct contracts."""

    def test_contract_input_and_output_schemas(self):
        """Engineer with code inputs/outputs gets contracts with correct schema counts."""
        registry = SchemaRegistry()
        role = _make_role(
            "Software Engineer",
            input_artifacts=["code_review_request"],
            output_artifacts=["code_patch", "test_suite"],
        )
        contract = registry.register_from_role_template(role, "engineer")

        assert contract.bot_name == "engineer"
        assert contract.role_name == "Software Engineer"
        assert len(contract.input_schemas) == 1
        assert len(contract.output_schemas) == 2

    def test_input_artifact_names(self):
        """Artifact names are preserved in the contract."""
        registry = SchemaRegistry()
        role = _make_role(
            "Software Engineer",
            input_artifacts=["code_review_request"],
            output_artifacts=["code_patch", "test_suite"],
        )
        contract = registry.register_from_role_template(role, "engineer")

        assert contract.input_artifact_names() == ["code_review_request"]
        assert contract.output_artifact_names() == ["code_patch", "test_suite"]

    def test_code_template_matched_for_code_artifacts(self):
        """Artifacts containing 'code' derive fields from the 'code' template."""
        registry = SchemaRegistry()
        role = _make_role(
            "Software Engineer",
            input_artifacts=["code_review_request"],
            output_artifacts=["code_patch"],
        )
        registry.register_from_role_template(role, "engineer")

        # Both code_review_request and code_patch should match the 'code' template
        code_fields = {f.name for f in ARTIFACT_SCHEMA_TEMPLATES["code"]}

        input_schema = registry.bot_contracts["engineer"].input_schemas[0]
        input_field_names = {f.name for f in input_schema.fields}
        assert code_fields.issubset(input_field_names) or code_fields == input_field_names

        output_schema = registry.bot_contracts["engineer"].output_schemas[0]
        output_field_names = {f.name for f in output_schema.fields}
        assert code_fields.issubset(output_field_names) or code_fields == output_field_names

    def test_schema_keys_stored_in_registry(self):
        """Schema keys are stored with correct format bot:direction:artifact."""
        registry = SchemaRegistry()
        role = _make_role(
            "Software Engineer",
            input_artifacts=["code_review_request"],
            output_artifacts=["code_patch"],
        )
        registry.register_from_role_template(role, "engineer")

        assert "engineer:input:code_review_request" in registry.schemas
        assert "engineer:output:code_patch" in registry.schemas

    def test_artifact_type_enum_converted_to_string(self):
        """ArtifactType enum values are converted to strings for schema keys."""
        registry = SchemaRegistry()
        role = _make_role(
            "Reviewer",
            input_artifacts=[ArtifactType.CODE],
            output_artifacts=[ArtifactType.REPORT],
        )
        contract = registry.register_from_role_template(role, "reviewer")

        # The artifact name should be the enum's .value string
        assert contract.input_artifact_names() == ["code"]
        assert contract.output_artifact_names() == ["report"]


# ===========================================================================
# 2. validate_handoff_chain — compatible
# ===========================================================================

class TestHandoffChainCompatible:
    """validate_handoff_chain detects compatible handoffs."""

    def test_same_template_schemas_are_compatible(self):
        """Engineer (code_patch output) → QA (code_review input) is compatible."""
        registry = SchemaRegistry()
        engineer = _make_role(
            "Software Engineer",
            input_artifacts=[],
            output_artifacts=["code_patch"],
        )
        qa = _make_role(
            "QA Engineer",
            input_artifacts=["code_review"],
            output_artifacts=[],
        )
        registry.register_from_role_template(engineer, "engineer")
        registry.register_from_role_template(qa, "qa")

        handoff = _make_handoff("engineer", "qa", ArtifactType.CODE)
        results = registry.validate_handoff_chain([handoff])

        assert len(results) == 1
        assert results[0].from_role == "engineer"
        assert results[0].to_role == "qa"
        assert results[0].compatible is True
        assert results[0].mismatches == []


# ===========================================================================
# 3. validate_handoff_chain — incompatible
# ===========================================================================

class TestHandoffChainIncompatible:
    """validate_handoff_chain detects incompatible handoffs."""

    def test_different_template_schemas_are_incompatible(self):
        """Engineer (code_patch) → Finance (financial_report) is incompatible."""
        registry = SchemaRegistry()
        engineer = _make_role(
            "Software Engineer",
            input_artifacts=[],
            output_artifacts=["code_patch"],
        )
        finance = _make_role(
            "Finance Analyst",
            input_artifacts=["financial_report"],
            output_artifacts=[],
        )
        registry.register_from_role_template(engineer, "engineer")
        registry.register_from_role_template(finance, "finance")

        handoff = _make_handoff("engineer", "finance", ArtifactType.CODE)
        results = registry.validate_handoff_chain([handoff])

        assert len(results) == 1
        assert results[0].compatible is False
        assert len(results[0].mismatches) > 0

    def test_missing_contract_skips_validation(self):
        """Handoffs where one side has no contract are silently skipped."""
        registry = SchemaRegistry()
        handoff = _make_handoff("unknown_sender", "unknown_receiver", ArtifactType.CODE)
        results = registry.validate_handoff_chain([handoff])
        assert results == []


# ===========================================================================
# 4. generate_zod_schemas
# ===========================================================================

class TestGenerateZodSchemas:
    """generate_zod_schemas produces valid TypeScript."""

    def test_output_file_contains_z_object(self):
        """Generated file wraps schemas in z.object()."""
        registry = SchemaRegistry()
        role = _make_role(
            "Software Engineer",
            input_artifacts=["code_review_request"],
            output_artifacts=["code_patch"],
        )
        registry.register_from_role_template(role, "engineer")

        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            file_path = registry.generate_zod_schemas("engineer", out_dir)

            assert file_path.exists()
            content = file_path.read_text(encoding="utf-8")

            assert "z.object(" in content
            assert "import { z } from" in content

    def test_output_contains_input_and_output_schemas(self):
        """Generated file has both InputSchema and OutputSchema exports."""
        registry = SchemaRegistry()
        role = _make_role(
            "Software Engineer",
            input_artifacts=["code_review_request"],
            output_artifacts=["code_patch"],
        )
        registry.register_from_role_template(role, "engineer")

        with tempfile.TemporaryDirectory() as tmp:
            file_path = registry.generate_zod_schemas("engineer", Path(tmp))
            content = file_path.read_text(encoding="utf-8")

            assert "EngineerInputSchema" in content
            assert "EngineerOutputSchema" in content

    def test_enum_constraint_produces_z_enum(self):
        """Approval artifact with enum constraint generates z.enum()."""
        registry = SchemaRegistry()
        role = _make_role(
            "Approver",
            input_artifacts=[],
            output_artifacts=["approval_decision"],
        )
        registry.register_from_role_template(role, "approver")

        with tempfile.TemporaryDirectory() as tmp:
            file_path = registry.generate_zod_schemas("approver", Path(tmp))
            content = file_path.read_text(encoding="utf-8")
            assert "z.enum(" in content

    def test_raises_for_unregistered_bot(self):
        """ValueError is raised when bot has no registered contract."""
        registry = SchemaRegistry()
        with pytest.raises(ValueError, match="No contract registered"):
            registry.generate_zod_schemas("ghost_bot", Path("/tmp"))


# ===========================================================================
# 5. generate_python_schemas
# ===========================================================================

class TestGeneratePythonSchemas:
    """generate_python_schemas produces valid Python dataclass definitions."""

    def test_output_file_contains_dataclass_decorator(self):
        """Generated file includes @dataclass decorator."""
        registry = SchemaRegistry()
        role = _make_role(
            "Software Engineer",
            input_artifacts=["code_review_request"],
            output_artifacts=["code_patch"],
        )
        registry.register_from_role_template(role, "engineer")

        with tempfile.TemporaryDirectory() as tmp:
            file_path = registry.generate_python_schemas("engineer", Path(tmp))
            assert file_path.exists()
            content = file_path.read_text(encoding="utf-8")
            assert "@dataclass" in content
            assert "class " in content

    def test_output_file_imports_dataclass(self):
        """Generated file imports dataclass from stdlib."""
        registry = SchemaRegistry()
        role = _make_role(
            "Software Engineer",
            input_artifacts=["code_review_request"],
            output_artifacts=["code_patch"],
        )
        registry.register_from_role_template(role, "engineer")

        with tempfile.TemporaryDirectory() as tmp:
            file_path = registry.generate_python_schemas("engineer", Path(tmp))
            content = file_path.read_text(encoding="utf-8")
            assert "from dataclasses import dataclass" in content

    def test_raises_for_unregistered_bot(self):
        """ValueError is raised when bot has no registered contract."""
        registry = SchemaRegistry()
        with pytest.raises(ValueError, match="No contract registered"):
            registry.generate_python_schemas("ghost_bot", Path("/tmp"))


# ===========================================================================
# 6. get_dependency_graph
# ===========================================================================

class TestGetDependencyGraph:
    """get_dependency_graph maps bot→bot dependencies."""

    def test_qa_depends_on_engineer_via_code_template(self):
        """QA has code input → depends on Engineer who produces code output."""
        registry = SchemaRegistry()
        engineer = _make_role(
            "Software Engineer",
            input_artifacts=[],
            output_artifacts=["code_patch"],
        )
        qa = _make_role(
            "QA Engineer",
            input_artifacts=["code_review"],
            output_artifacts=[],
        )
        registry.register_from_role_template(engineer, "engineer")
        registry.register_from_role_template(qa, "qa")

        graph = registry.get_dependency_graph()

        assert "engineer" in graph
        assert "qa" in graph
        assert "engineer" in graph["qa"]
        assert graph["engineer"] == []

    def test_no_dependency_for_unrelated_templates(self):
        """Finance and Engineer have no shared template → no dependency."""
        registry = SchemaRegistry()
        engineer = _make_role(
            "Software Engineer",
            input_artifacts=[],
            output_artifacts=["code_patch"],
        )
        finance = _make_role(
            "Finance Analyst",
            input_artifacts=["financial_report"],
            output_artifacts=[],
        )
        registry.register_from_role_template(engineer, "engineer")
        registry.register_from_role_template(finance, "finance")

        graph = registry.get_dependency_graph()

        assert graph["finance"] == []
        assert graph["engineer"] == []


# ===========================================================================
# 7. Artifact name template matching
# ===========================================================================

class TestArtifactTemplateMatching:
    """_derive_schema resolves the correct template from artifact names."""

    def test_quarterly_financial_report_matches_template(self):
        """'quarterly financial report' matches a known template (not default)."""
        registry = SchemaRegistry()
        schema = registry._derive_schema("quarterly financial report", "input")

        default_field_names = {"data", "metadata"}
        actual_field_names = {f.name for f in schema.fields}
        # Should NOT be the default fallback schema
        assert actual_field_names != default_field_names

    def test_quarterly_financial_report_has_known_template_fields(self):
        """'quarterly financial report' fields come from 'report' or 'financial' template."""
        registry = SchemaRegistry()
        schema = registry._derive_schema("quarterly financial report", "input")

        actual_field_names = {f.name for f in schema.fields}
        report_fields = {f.name for f in ARTIFACT_SCHEMA_TEMPLATES["report"]}
        financial_fields = {f.name for f in ARTIFACT_SCHEMA_TEMPLATES["financial"]}

        matched = (
            actual_field_names == report_fields
            or actual_field_names == financial_fields
        )
        assert matched, (
            f"Expected fields from 'report' or 'financial' template, "
            f"got {actual_field_names}"
        )

    def test_code_artifact_matches_code_template(self):
        """Artifact name containing 'code' matches the 'code' template."""
        registry = SchemaRegistry()
        schema = registry._derive_schema("source_code_artifact", "output")
        expected = {f.name for f in ARTIFACT_SCHEMA_TEMPLATES["code"]}
        assert {f.name for f in schema.fields} == expected

    def test_unknown_artifact_uses_default_schema(self):
        """Artifact with no recognisable pattern gets the default schema."""
        registry = SchemaRegistry()
        schema = registry._derive_schema("xyz_unknown_blob", "output")
        assert {f.name for f in schema.fields} == {"data", "metadata"}


# ===========================================================================
# 8. SystemLibrarian integration
# ===========================================================================

class TestSystemLibrarianIntegration:
    """register_schema_knowledge indexes schemas into the knowledge base."""

    def test_register_schema_knowledge_returns_count(self):
        """Returns the number of knowledge entries added."""
        from src.system_librarian import SystemLibrarian

        registry = SchemaRegistry()
        role = _make_role(
            "Software Engineer",
            input_artifacts=["code_review_request"],
            output_artifacts=["code_patch", "test_suite"],
        )
        registry.register_from_role_template(role, "engineer")

        librarian = SystemLibrarian()
        before = len(librarian.knowledge_base)
        count = librarian.register_schema_knowledge(registry)

        assert count == 3  # 1 input + 2 outputs
        assert len(librarian.knowledge_base) == before + 3

    def test_registered_entries_have_schema_contract_category(self):
        """Knowledge entries added by register_schema_knowledge have correct category."""
        from src.system_librarian import SystemLibrarian

        registry = SchemaRegistry()
        role = _make_role(
            "Software Engineer",
            input_artifacts=["code_patch"],
            output_artifacts=[],
        )
        registry.register_from_role_template(role, "engineer")

        librarian = SystemLibrarian()
        librarian.register_schema_knowledge(registry)

        schema_entries = [
            k for k in librarian.knowledge_base.values()
            if k.category == "schema_contract"
        ]
        assert len(schema_entries) >= 1
        entry = schema_entries[0]
        assert "Schema:" in entry.topic
        assert "engineer" in entry.related_modules
