"""
Test Suite for Phase 2: Viewport Integration & Content Resolver

Tests:
- ViewportContentResolver with MAS, Persistence, and Librarian backends
- Viewport endpoints mounted on execution orchestrator
- conftest.py PYTHONPATH setup
"""

import os
import json
import tempfile
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


# ============================================================================
# conftest.py VERIFICATION
# ============================================================================


class TestConftest:
    """Verify conftest.py correctly adds src/ to sys.path"""

    def test_src_on_sys_path(self):
        """src/ should be on sys.path via conftest.py"""
        import sys
        src_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), '..', 'src')
        )
        assert src_dir in sys.path

    def test_can_import_flask_security_without_pythonpath(self):
        """flask_security should be importable via conftest.py"""
        import flask_security
        assert hasattr(flask_security, 'configure_secure_app')

    def test_can_import_artifact_viewport(self):
        """artifact_viewport should be importable via conftest.py"""
        import artifact_viewport
        assert hasattr(artifact_viewport, 'ArtifactViewport')


# ============================================================================
# VIEWPORT CONTENT RESOLVER TESTS
# ============================================================================


@dataclass
class _FakeArtifact:
    """Minimal artifact for testing"""
    id: str
    content: Any
    def to_dict(self):
        return {'id': self.id, 'content': self.content}


class _FakeMemoryPlane:
    """Fake memory plane for testing"""
    def __init__(self, artifacts=None):
        self._store = {a.id: a for a in (artifacts or [])}
    def read(self, artifact_id):
        return self._store.get(artifact_id)


class _FakeMAS:
    """Fake Memory Artifact System"""
    def __init__(self):
        self.sandbox = _FakeMemoryPlane([
            _FakeArtifact("sb-1", "sandbox content line 1\nline 2"),
        ])
        self.working = _FakeMemoryPlane([
            _FakeArtifact("wk-1", {"key": "working value", "steps": [1, 2]}),
        ])
        self.control = _FakeMemoryPlane()
        self.execution = _FakeMemoryPlane([
            _FakeArtifact("ex-1", "executed content"),
        ])


class _FakePersistence:
    """Fake Persistence Manager"""
    def __init__(self):
        self._docs = {
            "doc-1": {"title": "Test Document", "body": "Hello world"},
            "doc-2": {"title": "Gate Log", "events": [{"gate": "g1"}]},
        }
    def load_document(self, doc_id):
        return self._docs.get(doc_id)


class _FakeLibrarian:
    """Fake System Librarian"""
    def __init__(self):
        self._transcripts = {
            "tx-1": "Librarian transcript line 1\nline 2\nline 3",
        }
    def get_transcript(self, artifact_id):
        return self._transcripts.get(artifact_id)


class TestViewportContentResolver:
    """Test ViewportContentResolver across data stores"""

    @pytest.fixture
    def resolver(self):
        from viewport_content_resolver import ViewportContentResolver
        return ViewportContentResolver(
            memory_system=_FakeMAS(),
            persistence_manager=_FakePersistence(),
            system_librarian=_FakeLibrarian(),
        )

    def test_resolve_from_sandbox(self, resolver):
        from artifact_viewport import ViewportOrigin
        content = resolver.resolve("sb-1", "tenant-a", ViewportOrigin.SANDBOX)
        assert content is not None
        assert "sandbox content" in str(content)

    def test_resolve_from_working(self, resolver):
        from artifact_viewport import ViewportOrigin
        content = resolver.resolve("wk-1", "tenant-a", ViewportOrigin.WORKING)
        assert content is not None
        assert content['key'] == 'working value'

    def test_resolve_from_execution(self, resolver):
        from artifact_viewport import ViewportOrigin
        content = resolver.resolve("ex-1", "tenant-a", ViewportOrigin.EXECUTION)
        assert content == "executed content"

    def test_resolve_from_persistence(self, resolver):
        from artifact_viewport import ViewportOrigin
        content = resolver.resolve("doc-1", "tenant-a", ViewportOrigin.PERSISTENCE)
        assert content is not None
        assert content['title'] == 'Test Document'

    def test_resolve_from_librarian(self, resolver):
        from artifact_viewport import ViewportOrigin
        content = resolver.resolve("tx-1", "tenant-a", ViewportOrigin.LIBRARIAN)
        assert content is not None
        assert "Librarian transcript" in content

    def test_resolve_not_found(self, resolver):
        from artifact_viewport import ViewportOrigin
        content = resolver.resolve("nonexistent", "tenant-a", ViewportOrigin.WORKING)
        assert content is None

    def test_resolve_any_searches_all_stores(self, resolver):
        """When origin doesn't match a specific store, search all"""
        from viewport_content_resolver import ViewportContentResolver
        from artifact_viewport import ViewportOrigin

        # Resolve with fallback search — should find in persistence
        r = ViewportContentResolver(
            persistence_manager=_FakePersistence(),
        )
        content = r._resolve_any("doc-2")
        assert content is not None
        assert content['title'] == 'Gate Log'

    def test_resolve_without_backends(self):
        """Resolver with no backends should return None gracefully"""
        from viewport_content_resolver import ViewportContentResolver
        from artifact_viewport import ViewportOrigin
        r = ViewportContentResolver()
        assert r.resolve("any-id", "t", ViewportOrigin.SANDBOX) is None
        assert r.resolve("any-id", "t", ViewportOrigin.PERSISTENCE) is None
        assert r.resolve("any-id", "t", ViewportOrigin.LIBRARIAN) is None


# ============================================================================
# EXECUTION ORCHESTRATOR VIEWPORT INTEGRATION TESTS
# ============================================================================


class TestExecutionOrchestratorViewport:
    """Test that viewport endpoints are mounted on the execution orchestrator"""

    @pytest.fixture
    def client(self):
        pytest.importorskip("flask", reason="Flask not installed")
        from execution_orchestrator.api import app
        app.config['TESTING'] = True
        with app.test_client() as c:
            yield c

    def test_viewport_health_mounted(self, client):
        """GET /viewport/health should be available on execution orchestrator"""
        resp = client.get('/viewport/health')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['status'] == 'healthy'
        assert data['service'] == 'artifact_viewport'

    def test_viewport_manifest_requires_content(self, client):
        """GET /viewport/manifest/<id> should return 404 when resolver has no data"""
        resp = client.get('/viewport/manifest/nonexistent-doc')
        assert resp.status_code == 404

    def test_viewport_project_via_post_with_content(self, client):
        """POST /viewport/project/<id> with content body should work"""
        test_content = "line one\nline two\nline three"
        resp = client.post(
            '/viewport/project/inline-doc',
            json={'content': test_content},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        proj = data['projection']
        assert proj['total_lines'] == 3

    def test_viewport_search_via_post_with_content(self, client):
        """POST /viewport/search/<id>?q=... with content body should find matches"""
        test_content = "alpha\nbeta\ngamma\nbeta again"
        resp = client.post(
            '/viewport/search/inline-doc?q=beta',
            json={'content': test_content},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['match_count'] == 2


# ============================================================================
# END-TO-END: VIEWPORT + RESOLVER + PROJECTION
# ============================================================================


class TestViewportEndToEnd:
    """End-to-end test of viewport with content resolver"""

    def test_manifest_then_project_section(self):
        """Full flow: get manifest → find section → project section"""
        from artifact_viewport import ArtifactViewport, ViewportRange

        vp = ArtifactViewport()
        content = (
            "# Introduction\n"
            "This is the intro.\n"
            "\n"
            "# Architecture\n"
            "Murphy System is modular.\n"
            "It uses memory planes.\n"
            "\n"
            "# Security\n"
            "All endpoints are authenticated.\n"
        )

        # Get manifest
        manifest = vp.get_manifest("doc-e2e", content, "tenant-e2e")
        assert manifest.total_lines > 0
        assert len(manifest.section_index) >= 3

        # Find the Architecture section
        arch_section = next(
            (s for s in manifest.section_index if 'Architecture' in s['name']),
            None,
        )
        assert arch_section is not None

        # Project it
        proj = vp.project(
            "doc-e2e", content, "tenant-e2e",
            ViewportRange(
                start_line=arch_section['start_line'],
                end_line=arch_section['end_line'],
            ),
        )
        rendered = "\n".join(proj.lines)
        assert "modular" in rendered
        assert "Introduction" not in rendered  # should not include intro

    def test_structured_content_drill_down(self):
        """Drill into structured content via key_path"""
        from artifact_viewport import ArtifactViewport, ViewportRange

        vp = ArtifactViewport()
        content = {
            "metadata": {"version": "1.0", "author": "Murphy"},
            "execution_graph": {
                "steps": [
                    {"id": "s1", "action": "verify"},
                    {"id": "s2", "action": "compile"},
                    {"id": "s3", "action": "execute"},
                ]
            },
            "audit_trail": [
                {"event": "created", "timestamp": "2026-01-01"},
            ],
        }

        # Drill into execution_graph.steps
        proj = vp.project(
            "pkt-e2e", content, "tenant-e2e",
            ViewportRange(key_path="execution_graph.steps"),
        )
        rendered = "\n".join(proj.lines)
        assert "verify" in rendered
        assert "compile" in rendered
        assert "execute" in rendered
        # metadata and audit should not appear
        assert "author" not in rendered
        assert "created" not in rendered

    def test_persistence_document_viewport(self):
        """Test viewing a persisted document through the resolver"""
        from viewport_content_resolver import ViewportContentResolver
        from artifact_viewport import ArtifactViewport, ViewportOrigin

        vp = ArtifactViewport()
        resolver = ViewportContentResolver(
            persistence_manager=_FakePersistence(),
        )

        content = resolver.resolve("doc-1", "t1", ViewportOrigin.PERSISTENCE)
        assert content is not None

        manifest = vp.get_manifest("doc-1", content, "t1", ViewportOrigin.PERSISTENCE)
        assert manifest.total_lines > 0
        assert manifest.origin == ViewportOrigin.PERSISTENCE

        proj = vp.project("doc-1", content, "t1", origin=ViewportOrigin.PERSISTENCE)
        assert len(proj.lines) > 0
