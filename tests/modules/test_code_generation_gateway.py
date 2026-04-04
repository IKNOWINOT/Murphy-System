"""
Tests for ADV-001: CodeGenerationGateway.

Validates template-based code generation, safety validation,
forbidden pattern blocking, and EventBackbone integration.

Design Label: TEST-006 / ADV-001
Owner: QA Team
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from code_generation_gateway import (
    CodeGenerationGateway,
    CodeGenRequest,
    GenStatus,
)
from persistence_manager import PersistenceManager
from event_backbone import EventBackbone, EventType


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def pm(tmp_path):
    return PersistenceManager(persistence_dir=str(tmp_path / "test_persist"))


@pytest.fixture
def backbone():
    return EventBackbone()


@pytest.fixture
def gateway():
    return CodeGenerationGateway()


@pytest.fixture
def wired_gateway(pm, backbone):
    return CodeGenerationGateway(
        persistence_manager=pm,
        event_backbone=backbone,
    )


# ------------------------------------------------------------------
# Code generation
# ------------------------------------------------------------------

class TestCodeGeneration:
    def test_generate_python_module(self, gateway):
        req = gateway.generate(
            language="python",
            description="A data processor for CSV files",
            template_name="python_module",
            parameters={"class_name": "CsvProcessor"},
        )
        assert req.request_id.startswith("gen-")
        assert req.status == GenStatus.VALIDATED
        assert "class CsvProcessor" in req.generated_code
        assert "CsvProcessor" in req.generated_code

    def test_generate_python_function(self, gateway):
        req = gateway.generate(
            language="python",
            description="Calculate monthly revenue",
            template_name="python_function",
            parameters={
                "function_name": "calculate_revenue",
                "parameters": "data, month",
            },
        )
        assert req.status == GenStatus.VALIDATED
        assert "def calculate_revenue" in req.generated_code

    def test_generate_python_test(self, gateway):
        req = gateway.generate(
            language="python",
            description="Tests for CsvProcessor",
            template_name="python_test",
            parameters={
                "target_module": "csv_processor",
                "target_class": "CsvProcessor",
            },
        )
        assert req.status == GenStatus.VALIDATED
        assert "class TestCsvProcessor" in req.generated_code

    def test_unknown_template_fails(self, gateway):
        req = gateway.generate(
            language="python",
            description="Test",
            template_name="nonexistent_template",
        )
        assert req.status == GenStatus.FAILED_VALIDATION
        assert "Unknown template" in req.validation_errors[0]

    def test_missing_parameter_fails(self, gateway):
        req = gateway.generate(
            language="python",
            description="Test",
            template_name="python_module",
            parameters={},  # missing class_name
        )
        assert req.status == GenStatus.FAILED_VALIDATION

    def test_request_to_dict(self, gateway):
        req = gateway.generate(
            language="python",
            description="Test module",
            template_name="python_module",
            parameters={"class_name": "TestMod"},
        )
        d = req.to_dict()
        assert "request_id" in d
        assert "status" in d
        assert "generated_code" in d


# ------------------------------------------------------------------
# Safety validation
# ------------------------------------------------------------------

class TestSafetyValidation:
    def test_forbidden_eval_blocked(self, gateway):
        gateway.register_template("unsafe", 'result = eval("1+1")')
        req = gateway.generate(
            language="python",
            description="Unsafe code",
            template_name="unsafe",
        )
        assert req.status == GenStatus.FAILED_VALIDATION
        assert any("Forbidden" in e for e in req.validation_errors)

    def test_forbidden_exec_blocked(self, gateway):
        gateway.register_template("unsafe_exec", 'exec("print(1)")')
        req = gateway.generate(
            language="python",
            description="Unsafe exec",
            template_name="unsafe_exec",
        )
        assert req.status == GenStatus.FAILED_VALIDATION

    def test_forbidden_subprocess_blocked(self, gateway):
        gateway.register_template("unsafe_sub", 'import subprocess\nsubprocess.run(["ls"])')
        req = gateway.generate(
            language="python",
            description="Unsafe subprocess",
            template_name="unsafe_sub",
        )
        assert req.status == GenStatus.FAILED_VALIDATION

    def test_syntax_error_detected(self, gateway):
        gateway.register_template("bad_syntax", 'def foo(\n    pass')
        req = gateway.generate(
            language="python",
            description="Bad syntax",
            template_name="bad_syntax",
        )
        assert req.status == GenStatus.FAILED_VALIDATION
        assert any("syntax" in e.lower() for e in req.validation_errors)


# ------------------------------------------------------------------
# Template management
# ------------------------------------------------------------------

class TestTemplateManagement:
    def test_list_builtin_templates(self, gateway):
        templates = gateway.list_templates()
        assert "python_module" in templates
        assert "python_function" in templates
        assert "python_test" in templates

    def test_register_custom_template(self, gateway):
        gateway.register_template("custom", "# Custom: {description}")
        req = gateway.generate(
            language="python",
            description="My custom code",
            template_name="custom",
        )
        assert req.status == GenStatus.VALIDATED
        assert "# Custom: My custom code" in req.generated_code


# ------------------------------------------------------------------
# Persistence
# ------------------------------------------------------------------

class TestPersistence:
    def test_request_persisted(self, wired_gateway, pm):
        req = wired_gateway.generate(
            language="python",
            description="Test module",
            template_name="python_module",
            parameters={"class_name": "TestMod"},
        )
        loaded = pm.load_document(req.request_id)
        assert loaded is not None
        assert loaded["status"] == "validated"


# ------------------------------------------------------------------
# EventBackbone integration
# ------------------------------------------------------------------

class TestEventBackboneIntegration:
    def test_generation_publishes_event(self, wired_gateway, backbone):
        received = []
        backbone.subscribe(EventType.LEARNING_FEEDBACK, lambda e: received.append(e))
        wired_gateway.generate(
            language="python",
            description="Test",
            template_name="python_module",
            parameters={"class_name": "TestMod"},
        )
        backbone.process_pending()
        assert len(received) >= 1
        assert received[0].payload["source"] == "code_generation_gateway"


# ------------------------------------------------------------------
# Query / Status
# ------------------------------------------------------------------

class TestStatus:
    def test_list_requests(self, gateway):
        gateway.generate(
            language="python",
            description="A",
            template_name="python_module",
            parameters={"class_name": "ModA"},
        )
        gateway.generate(
            language="python",
            description="B",
            template_name="python_module",
            parameters={"class_name": "ModB"},
        )
        reqs = gateway.list_requests()
        assert len(reqs) == 2

    def test_status_reflects_state(self, gateway):
        gateway.generate(
            language="python",
            description="Test",
            template_name="python_module",
            parameters={"class_name": "TestMod"},
        )
        status = gateway.get_status()
        assert status["total_requests"] == 1
        assert "validated" in status["by_status"]
