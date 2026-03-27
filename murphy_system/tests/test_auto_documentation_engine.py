"""
Tests for DEV-003: AutoDocumentationEngine.

Validates file analysis, directory scanning, design label extraction,
persistence integration, and EventBackbone event publishing.

Design Label: TEST-010 / DEV-003
Owner: QA Team
"""

import os
import pytest


from auto_documentation_engine import (
    AutoDocumentationEngine,
    ModuleDoc,
    ClassDoc,
    FunctionDoc,
    DesignLabelEntry,
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
def engine():
    return AutoDocumentationEngine()


@pytest.fixture
def wired_engine(pm, backbone):
    return AutoDocumentationEngine(
        persistence_manager=pm,
        event_backbone=backbone,
    )


@pytest.fixture
def sample_py(tmp_path):
    """Create a sample Python file for testing."""
    code = '''"""
Sample module.

Design Label: TEST-999 — Test Module
Owner: QA Team
"""

class MyClass:
    """A test class."""

    def my_method(self, x, y):
        """A test method."""
        return x + y


def top_level(a, b, c):
    """A top-level function."""
    pass
'''
    p = tmp_path / "sample_module.py"
    p.write_text(code)
    return str(p)


@pytest.fixture
def sample_dir(tmp_path):
    """Create a directory with sample Python files."""
    for i in range(3):
        code = f'"""Module {i}. Design Label: M-{i:03d}"""\ndef func_{i}(): pass\n'
        (tmp_path / f"mod_{i}.py").write_text(code)
    return str(tmp_path)


# ------------------------------------------------------------------
# File analysis
# ------------------------------------------------------------------

class TestFileAnalysis:
    def test_analyse_file(self, engine, sample_py):
        doc = engine.analyse_file(sample_py)
        assert doc is not None
        assert doc.module_name == "sample_module"
        assert doc.design_label == "TEST-999"
        assert "QA Team" in doc.owner

    def test_classes_extracted(self, engine, sample_py):
        doc = engine.analyse_file(sample_py)
        assert len(doc.classes) == 1
        assert doc.classes[0].name == "MyClass"
        assert len(doc.classes[0].methods) == 1
        assert doc.classes[0].methods[0].name == "my_method"

    def test_functions_extracted(self, engine, sample_py):
        doc = engine.analyse_file(sample_py)
        assert len(doc.functions) == 1
        assert doc.functions[0].name == "top_level"

    def test_doc_to_dict(self, engine, sample_py):
        doc = engine.analyse_file(sample_py)
        d = doc.to_dict()
        assert "doc_id" in d
        assert "module_name" in d
        assert "classes" in d
        assert "functions" in d

    def test_nonexistent_file(self, engine):
        result = engine.analyse_file("/nonexistent/file.py")
        assert result is None

    def test_invalid_syntax(self, engine, tmp_path):
        bad = tmp_path / "bad.py"
        bad.write_text("def broken(:\n  pass\n")
        result = engine.analyse_file(str(bad))
        assert result is None


# ------------------------------------------------------------------
# Directory scanning
# ------------------------------------------------------------------

class TestDirectoryScanning:
    def test_scan_directory(self, engine, sample_dir):
        docs = engine.scan_directory(sample_dir)
        assert len(docs) == 3

    def test_scan_nonexistent_dir(self, engine):
        docs = engine.scan_directory("/nonexistent/dir")
        assert docs == []


# ------------------------------------------------------------------
# Design label inventory
# ------------------------------------------------------------------

class TestDesignLabels:
    def test_label_extracted(self, engine, sample_py):
        engine.analyse_file(sample_py)
        labels = engine.get_label_inventory()
        assert len(labels) >= 1
        assert labels[0]["label"] == "TEST-999"

    def test_labels_from_directory(self, engine, sample_dir):
        engine.scan_directory(sample_dir)
        labels = engine.get_label_inventory()
        assert len(labels) == 3


# ------------------------------------------------------------------
# Query
# ------------------------------------------------------------------

class TestQuery:
    def test_get_artifacts(self, engine, sample_py):
        engine.analyse_file(sample_py)
        artifacts = engine.get_artifacts()
        assert len(artifacts) == 1

    def test_get_artifact_by_id(self, engine, sample_py):
        doc = engine.analyse_file(sample_py)
        result = engine.get_artifact(doc.doc_id)
        assert result is not None
        assert result["module_name"] == "sample_module"

    def test_get_artifact_not_found(self, engine):
        assert engine.get_artifact("nonexistent") is None


# ------------------------------------------------------------------
# Persistence
# ------------------------------------------------------------------

class TestPersistence:
    def test_doc_persisted(self, wired_engine, pm, sample_py):
        doc = wired_engine.analyse_file(sample_py)
        loaded = pm.load_document(doc.doc_id)
        assert loaded is not None
        assert loaded["module_name"] == "sample_module"


# ------------------------------------------------------------------
# EventBackbone integration
# ------------------------------------------------------------------

class TestEventBackboneIntegration:
    def test_analyse_publishes_event(self, wired_engine, backbone, sample_py):
        received = []
        backbone.subscribe(EventType.LEARNING_FEEDBACK, lambda e: received.append(e))
        wired_engine.analyse_file(sample_py)
        backbone.process_pending()
        assert len(received) >= 1
        assert received[0].payload["source"] == "auto_documentation_engine"


# ------------------------------------------------------------------
# Status
# ------------------------------------------------------------------

class TestStatus:
    def test_status(self, engine, sample_py):
        engine.analyse_file(sample_py)
        status = engine.get_status()
        assert status["total_artifacts"] == 1
        assert status["total_labels"] >= 1
        assert status["persistence_attached"] is False
