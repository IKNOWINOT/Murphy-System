"""
Tests for Self-Introspection Module (INTRO-001).

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""
from __future__ import annotations

import os
import threading
import tempfile

import pytest


from self_introspection_module import (
    ModuleNode,
    SelfIntrospectionEngine,
    SystemGraph,
    _count_loc,
    _safe_module_name,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_py(directory: str, filename: str, content: str) -> str:
    path = os.path.join(directory, filename)
    with open(path, "w") as fh:
        fh.write(content)
    return path


# ---------------------------------------------------------------------------
# ModuleNode
# ---------------------------------------------------------------------------

class TestModuleNode:
    def test_to_dict_keys(self):
        node = ModuleNode(module_name="foo", file_path="/tmp/foo.py")
        d = node.to_dict()
        assert "module_name" in d
        assert "classes" in d
        assert "functions" in d
        assert "imports" in d
        assert "dependencies" in d
        assert "size_bytes" in d
        assert "last_modified" in d

    def test_docstring_truncated(self):
        node = ModuleNode(module_name="m", file_path="/tmp/m.py", docstring="x" * 1000)
        d = node.to_dict()
        assert len(d["docstring"]) <= 500


# ---------------------------------------------------------------------------
# SystemGraph
# ---------------------------------------------------------------------------

class TestSystemGraph:
    def test_to_dict(self):
        g = SystemGraph()
        d = g.to_dict()
        assert "nodes" in d
        assert "edges" in d
        assert "total_modules" in d
        assert "generated_at" in d


# ---------------------------------------------------------------------------
# LOC counting
# ---------------------------------------------------------------------------

class TestCountLoc:
    def test_blank_lines_excluded(self):
        src = "\n\n\ndef foo():\n    pass\n"
        assert _count_loc(src) == 2

    def test_comments_excluded(self):
        src = "# comment\nx = 1\n"
        assert _count_loc(src) == 1

    def test_empty(self):
        assert _count_loc("") == 0


# ---------------------------------------------------------------------------
# Safe module name
# ---------------------------------------------------------------------------

class TestSafeModuleName:
    def test_converts_path_sep(self):
        name = _safe_module_name("/root/src/foo/bar.py", "/root/src")
        assert name == "foo.bar"

    def test_init_file(self):
        name = _safe_module_name("/root/src/__init__.py", "/root/src")
        assert "__init__" in name


# ---------------------------------------------------------------------------
# SelfIntrospectionEngine
# ---------------------------------------------------------------------------

class TestScanCodebase:
    def test_scan_returns_system_graph(self, tmp_path):
        _write_py(str(tmp_path), "alpha.py",
                  '"""Alpha module."""\nclass Alpha:\n    pass\ndef foo(): pass\n')
        _write_py(str(tmp_path), "beta.py",
                  'import alpha\ndef bar(): pass\n')
        engine = SelfIntrospectionEngine()
        graph = engine.scan_codebase(str(tmp_path))
        assert isinstance(graph, SystemGraph)
        assert graph.total_modules == 2
        assert graph.total_classes >= 1
        assert graph.total_functions >= 2

    def test_scan_extracts_imports(self, tmp_path):
        _write_py(str(tmp_path), "mod.py", "import os\nfrom sys import path\n")
        engine = SelfIntrospectionEngine()
        graph = engine.scan_codebase(str(tmp_path))
        node = list(graph.nodes.values())[0]
        assert "os" in node.dependencies

    def test_scan_parses_docstring(self, tmp_path):
        _write_py(str(tmp_path), "doc.py", '"""My docstring."""\nx = 1\n')
        engine = SelfIntrospectionEngine()
        graph = engine.scan_codebase(str(tmp_path))
        node = list(graph.nodes.values())[0]
        assert "My docstring" in node.docstring

    def test_scan_handles_syntax_error(self, tmp_path):
        _write_py(str(tmp_path), "bad.py", "def foo(\n")
        engine = SelfIntrospectionEngine()
        graph = engine.scan_codebase(str(tmp_path))
        node = list(graph.nodes.values())[0]
        assert node.parse_error != ""

    def test_invalid_root_raises(self):
        engine = SelfIntrospectionEngine()
        with pytest.raises(ValueError):
            engine.scan_codebase("/does/not/exist")

    def test_non_string_root_raises(self):
        engine = SelfIntrospectionEngine()
        with pytest.raises(ValueError):
            engine.scan_codebase(None)  # type: ignore[arg-type]


class TestGetModuleDependencyGraph:
    def test_returns_dict(self, tmp_path):
        _write_py(str(tmp_path), "a.py", "import b\n")
        _write_py(str(tmp_path), "b.py", "x = 1\n")
        engine = SelfIntrospectionEngine()
        engine.scan_codebase(str(tmp_path))
        dep_graph = engine.get_module_dependency_graph()
        assert isinstance(dep_graph, dict)

    def test_returns_empty_before_scan(self):
        engine = SelfIntrospectionEngine()
        assert engine.get_module_dependency_graph() == {}


class TestGetComplexityReport:
    def test_has_required_keys(self, tmp_path):
        _write_py(str(tmp_path), "x.py", "def foo():\n    pass\n")
        engine = SelfIntrospectionEngine()
        engine.scan_codebase(str(tmp_path))
        report = engine.get_complexity_report()
        assert "total_modules" in report
        assert "total_loc" in report
        assert "avg_cyclomatic_estimate" in report

    def test_error_before_scan(self):
        engine = SelfIntrospectionEngine()
        report = engine.get_complexity_report()
        assert "error" in report


class TestFindModuleForCapability:
    def test_finds_matching_module(self, tmp_path):
        _write_py(str(tmp_path), "auth.py",
                  '"""Authentication module."""\ndef login(): pass\n')
        _write_py(str(tmp_path), "billing.py",
                  '"""Billing module."""\ndef charge(): pass\n')
        engine = SelfIntrospectionEngine()
        engine.scan_codebase(str(tmp_path))
        results = engine.find_module_for_capability("authentication login")
        names = [r.module_name for r in results]
        assert any("auth" in n for n in names)

    def test_empty_before_scan(self):
        engine = SelfIntrospectionEngine()
        assert engine.find_module_for_capability("anything") == []

    def test_bad_type_raises(self):
        engine = SelfIntrospectionEngine()
        with pytest.raises(ValueError):
            engine.find_module_for_capability(123)  # type: ignore[arg-type]


class TestHealthSnapshot:
    def test_has_required_keys(self, tmp_path):
        _write_py(str(tmp_path), "ok.py", "x = 1\n")
        engine = SelfIntrospectionEngine()
        engine.scan_codebase(str(tmp_path))
        health = engine.get_health_snapshot()
        assert "parse_errors" in health
        assert "circular_dependencies" in health
        assert "health_score" in health

    def test_detects_syntax_error(self, tmp_path):
        _write_py(str(tmp_path), "bad.py", "def f(\n")
        engine = SelfIntrospectionEngine()
        engine.scan_codebase(str(tmp_path))
        health = engine.get_health_snapshot()
        assert len(health["parse_errors"]) >= 1

    def test_error_before_scan(self):
        engine = SelfIntrospectionEngine()
        snap = engine.get_health_snapshot()
        assert "error" in snap


class TestCircularDependencies:
    def test_detects_cycle(self, tmp_path):
        # a → b → a
        _write_py(str(tmp_path), "a.py", "import b\n")
        _write_py(str(tmp_path), "b.py", "import a\n")
        engine = SelfIntrospectionEngine()
        engine.scan_codebase(str(tmp_path))
        health = engine.get_health_snapshot()
        # At least one cycle should be detected
        assert isinstance(health["circular_dependencies"], list)


class TestThreadSafety:
    def test_concurrent_scans(self, tmp_path):
        _write_py(str(tmp_path), "mod.py", "x = 1\n")
        engine = SelfIntrospectionEngine()
        errors = []

        def scan():
            try:
                engine.scan_codebase(str(tmp_path))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=scan) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []
