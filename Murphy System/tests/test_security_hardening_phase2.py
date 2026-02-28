"""
Test Suite for Security Hardening Phase 1.6-1.9 & Artifact Viewport

Tests:
- debug=True removal (environment-based debug control)
- Input validation on execution orchestrator endpoints
- Artifact Viewport: manifest, projection, search, section, head/tail
- Viewport tenant isolation and edge cases
"""

import os
import re
import json
import pytest
import threading
from datetime import datetime
from unittest.mock import patch

# ============================================================================
# PHASE 1.6: DEBUG MODE TESTS
# ============================================================================


class TestDebugModeRemoval:
    """Verify that no API server uses hardcoded debug=True"""

    def test_no_hardcoded_debug_true_in_src(self):
        """No source file in src/ should contain 'debug=True' in app.run()"""
        src_dir = os.path.join(
            os.path.dirname(__file__), '..', 'src'
        )
        violations = []
        for root, _dirs, files in os.walk(src_dir):
            for fname in files:
                if not fname.endswith('.py'):
                    continue
                fpath = os.path.join(root, fname)
                with open(fpath, 'r', errors='ignore') as f:
                    for lineno, line in enumerate(f, 1):
                        if 'debug=True' in line and 'app.run' in line:
                            violations.append(f"{fpath}:{lineno}")
        assert violations == [], f"Hardcoded debug=True found in: {violations}"

    def test_environment_based_debug_uses_murphy_env(self):
        """Debug should read from MURPHY_ENV environment variable"""
        src_dir = os.path.join(
            os.path.dirname(__file__), '..', 'src'
        )
        # Check that files with app.run() use MURPHY_ENV pattern
        app_run_files = []
        for root, _dirs, files in os.walk(src_dir):
            for fname in files:
                if not fname.endswith('.py'):
                    continue
                fpath = os.path.join(root, fname)
                with open(fpath, 'r', errors='ignore') as f:
                    content = f.read()
                    if 'app.run(' in content and 'debug=' in content:
                        app_run_files.append(fpath)
        # All files with debug= should use is_debug_mode(), MURPHY_ENV, or debug=False
        for fpath in app_run_files:
            with open(fpath, 'r') as f:
                content = f.read()
                has_env_check = (
                    'MURPHY_ENV' in content
                    or 'debug=False' in content
                    or 'is_debug_mode' in content
                )
                assert has_env_check, f"{fpath} uses debug= without environment check"


# ============================================================================
# PHASE 1.9: INPUT VALIDATION TESTS
# ============================================================================


class TestExecutionOrchestratorInputValidation:
    """Test input validation on execution orchestrator endpoints"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        pytest.importorskip("flask", reason="Flask not installed")
        from src.execution_orchestrator.api import app
        app.config['TESTING'] = True
        with app.test_client() as c:
            yield c

    def test_execute_rejects_empty_body(self, client):
        """POST /execute with empty body should return 400"""
        resp = client.post('/execute', json={})
        assert resp.status_code == 400

    def test_execute_rejects_invalid_authority_level(self, client):
        """POST /execute with invalid authority_level should return 400"""
        resp = client.post('/execute', json={
            'packet': {'packet_id': 'test-123', 'signature': 'sig'},
            'authority_level': 'SUPER_ADMIN'
        })
        assert resp.status_code == 400
        data = resp.get_json()
        assert 'valid_values' in data

    def test_execute_rejects_missing_packet_id(self, client):
        """POST /execute with missing packet_id should return 400"""
        resp = client.post('/execute', json={
            'packet': {'signature': 'sig'},
            'authority_level': 'standard'
        })
        assert resp.status_code == 400

    def test_execute_rejects_injection_in_packet_id(self, client):
        """POST /execute with injection chars in packet_id should return 400"""
        resp = client.post('/execute', json={
            'packet': {'packet_id': '<script>alert(1)</script>', 'signature': 'sig'},
            'authority_level': 'standard'
        })
        assert resp.status_code == 400

    def test_execute_rejects_overlong_packet_id(self, client):
        """POST /execute with very long packet_id should return 400"""
        resp = client.post('/execute', json={
            'packet': {'packet_id': 'a' * 300, 'signature': 'sig'},
            'authority_level': 'standard'
        })
        assert resp.status_code == 400

    def test_execute_accepts_valid_authority_levels(self, client):
        """POST /execute should accept all valid authority levels"""
        valid_levels = ['none', 'low', 'medium', 'standard', 'high', 'full']
        for level in valid_levels:
            resp = client.post('/execute', json={
                'packet': {'packet_id': f'test-{level}', 'signature': 'sig'},
                'authority_level': level
            })
            # Valid authority level should pass input validation (400 for authority means rejection)
            if resp.status_code == 400:
                error_msg = resp.get_json().get('error', '')
                assert 'authority' not in error_msg.lower(), (
                    f"Valid authority level '{level}' was rejected: {error_msg}"
                )

    def test_register_interface_rejects_empty_id(self, client):
        """POST /interfaces/register with empty interface_id should return 400"""
        resp = client.post('/interfaces/register', json={
            'interface_id': '',
            'is_available': True
        })
        assert resp.status_code == 400

    def test_register_interface_rejects_injection(self, client):
        """POST /interfaces/register with injection in interface_id should return 400"""
        resp = client.post('/interfaces/register', json={
            'interface_id': '; DROP TABLE interfaces;--',
            'is_available': True
        })
        assert resp.status_code == 400

    def test_register_interface_accepts_valid_id(self, client):
        """POST /interfaces/register with valid ID should succeed"""
        resp = client.post('/interfaces/register', json={
            'interface_id': 'confidence-engine-v1',
            'is_available': True,
            'response_time_ms': 15.5,
            'error_rate': 0.01
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['status'] == 'registered'


# ============================================================================
# ARTIFACT VIEWPORT TESTS
# ============================================================================


class TestArtifactViewportManifest:
    """Test ContentManifest generation"""

    def test_text_manifest(self):
        """Manifest for text content should have correct line count"""
        from src.artifact_viewport import ArtifactViewport, ViewportOrigin
        vp = ArtifactViewport()
        content = "line one\nline two\nline three\nline four\nline five"
        manifest = vp.get_manifest("art-1", content, "tenant-a", ViewportOrigin.SANDBOX)
        assert manifest.total_lines == 5
        assert manifest.tenant_id == "tenant-a"
        assert manifest.artifact_id == "art-1"
        assert manifest.checksum  # Non-empty SHA-256
        assert len(manifest.checksum) == 64

    def test_structured_manifest(self):
        """Manifest for dict content should detect structured type"""
        from src.artifact_viewport import ArtifactViewport, ContentType
        vp = ArtifactViewport()
        content = {"key1": "value1", "key2": {"nested": True}, "key3": [1, 2, 3]}
        manifest = vp.get_manifest("art-2", content, "tenant-b")
        assert manifest.content_type == ContentType.STRUCTURED
        assert manifest.total_lines > 0
        assert manifest.total_bytes > 0

    def test_manifest_caching(self):
        """Same content should return cached manifest"""
        from src.artifact_viewport import ArtifactViewport
        vp = ArtifactViewport()
        content = "hello world"
        m1 = vp.get_manifest("art-3", content, "tenant-c")
        m2 = vp.get_manifest("art-3", content, "tenant-c")
        assert m1.checksum == m2.checksum

    def test_manifest_invalidation_on_change(self):
        """Changed content should produce new manifest"""
        from src.artifact_viewport import ArtifactViewport
        vp = ArtifactViewport()
        m1 = vp.get_manifest("art-4", "version 1", "tenant-d")
        m2 = vp.get_manifest("art-4", "version 2", "tenant-d")
        assert m1.checksum != m2.checksum


class TestArtifactViewportProjection:
    """Test range-based content projection"""

    def _make_content(self, num_lines=100):
        return "\n".join(f"Line {i+1}: content here" for i in range(num_lines))

    def test_default_viewport(self):
        """Default projection should return first 50 lines"""
        from src.artifact_viewport import ArtifactViewport
        vp = ArtifactViewport()
        content = self._make_content(100)
        proj = vp.project("art-5", content, "tenant-e")
        assert proj.range_start == 1
        assert proj.range_end == 50
        assert proj.total_lines == 100
        assert len(proj.lines) == 50

    def test_custom_range(self):
        """Custom range should return exact lines"""
        from src.artifact_viewport import ArtifactViewport, ViewportRange
        vp = ArtifactViewport()
        content = self._make_content(100)
        proj = vp.project("art-6", content, "tenant-f",
                          ViewportRange(start_line=10, end_line=20))
        assert proj.range_start == 10
        assert proj.range_end == 20
        assert len(proj.lines) == 11  # inclusive

    def test_numbered_lines_format(self):
        """Lines should be formatted as 'N. content'"""
        from src.artifact_viewport import ArtifactViewport, ViewportRange
        vp = ArtifactViewport()
        content = "alpha\nbeta\ngamma"
        proj = vp.project("art-7", content, "tenant-g",
                          ViewportRange(start_line=2, end_line=3))
        assert proj.lines[0].startswith("2. ")
        assert proj.lines[1].startswith("3. ")

    def test_head_projection(self):
        """Head mode should return first N lines"""
        from src.artifact_viewport import ArtifactViewport
        vp = ArtifactViewport()
        content = self._make_content(100)
        proj = vp.project_head("art-8", content, "tenant-h", num_lines=10)
        assert proj.range_start == 1
        assert proj.range_end == 10

    def test_tail_projection(self):
        """Tail mode should return last N lines"""
        from src.artifact_viewport import ArtifactViewport
        vp = ArtifactViewport()
        content = self._make_content(100)
        proj = vp.project_tail("art-9", content, "tenant-i", num_lines=10)
        assert proj.range_start == 91
        assert proj.range_end == 100

    def test_end_marker_negative_one(self):
        """end_line=-1 should mean 'to end of content'"""
        from src.artifact_viewport import ArtifactViewport, ViewportRange
        vp = ArtifactViewport()
        content = self._make_content(25)
        proj = vp.project("art-10", content, "tenant-j",
                          ViewportRange(start_line=20, end_line=-1))
        assert proj.range_end == 25
        assert len(proj.lines) == 6  # 20..25 inclusive

    def test_truncation_on_large_range(self):
        """Viewport exceeding MAX_VIEWPORT_LINES should be truncated"""
        from src.artifact_viewport import ArtifactViewport, ViewportRange, MAX_VIEWPORT_LINES
        vp = ArtifactViewport()
        content = self._make_content(1000)
        proj = vp.project("art-11", content, "tenant-k",
                          ViewportRange(start_line=1, end_line=1000))
        assert proj.truncated is True
        assert len(proj.lines) == MAX_VIEWPORT_LINES

    def test_out_of_bounds_clamped(self):
        """Out-of-bounds ranges should be clamped"""
        from src.artifact_viewport import ArtifactViewport, ViewportRange
        vp = ArtifactViewport()
        content = "one\ntwo\nthree"
        proj = vp.project("art-12", content, "tenant-l",
                          ViewportRange(start_line=0, end_line=999))
        assert proj.range_start == 1
        assert proj.range_end == 3


class TestArtifactViewportStructured:
    """Test viewport on structured (dict/list) content"""

    def test_dict_content_as_json_lines(self):
        """Dict content should be rendered as pretty-printed JSON lines"""
        from src.artifact_viewport import ArtifactViewport, ContentType
        vp = ArtifactViewport()
        content = {"name": "test", "steps": [1, 2, 3]}
        proj = vp.project("art-13", content, "tenant-m")
        assert proj.content_type == ContentType.STRUCTURED
        assert any("name" in line for line in proj.lines)

    def test_key_path_extraction(self):
        """key_path should drill into nested structures"""
        from src.artifact_viewport import ArtifactViewport, ViewportRange
        vp = ArtifactViewport()
        content = {
            "execution_graph": {
                "steps": [
                    {"id": "step-1", "action": "analyze"},
                    {"id": "step-2", "action": "compile"},
                ]
            },
            "metadata": {"version": "1.0"}
        }
        proj = vp.project("art-14", content, "tenant-n",
                          ViewportRange(key_path="execution_graph.steps"))
        # Should show only the steps array, not the full content
        rendered = "\n".join(proj.lines)
        assert "step-1" in rendered
        assert "version" not in rendered  # metadata should not appear

    def test_depth_truncation(self):
        """Deep structures should be truncated at specified depth when using key_path"""
        from src.artifact_viewport import ArtifactViewport, ViewportRange
        vp = ArtifactViewport()
        content = {"a": {"b": {"c": {"d": {"e": "deep"}}}}}
        proj = vp.project("art-15", content, "tenant-o",
                          ViewportRange(key_path="a", depth=1))
        rendered = "\n".join(proj.lines)
        # At depth 1 from key "a", "c" should be truncated
        assert "<dict>" in rendered or "<str>" in rendered


class TestArtifactViewportSearch:
    """Test content search functionality"""

    def test_search_finds_matches(self):
        """Search should find matching lines"""
        from src.artifact_viewport import ArtifactViewport
        vp = ArtifactViewport()
        content = "line alpha\nline beta\nline gamma\nline beta again"
        results = vp.search_content("art-16", content, "tenant-p", "beta")
        assert len(results) == 2
        assert results[0]['match_line'] == 2
        assert results[1]['match_line'] == 4

    def test_search_case_insensitive(self):
        """Search should be case-insensitive"""
        from src.artifact_viewport import ArtifactViewport
        vp = ArtifactViewport()
        content = "Hello World\nhello world\nHELLO WORLD"
        results = vp.search_content("art-17", content, "tenant-q", "hello")
        assert len(results) == 3

    def test_search_with_context(self):
        """Search results should include context lines"""
        from src.artifact_viewport import ArtifactViewport
        vp = ArtifactViewport()
        content = "\n".join(f"Line {i}" for i in range(20))
        results = vp.search_content("art-18", content, "tenant-r", "Line 10",
                                     context_lines=2)
        assert len(results) == 1
        # Context should include lines before and after
        assert len(results[0]['context']) >= 3

    def test_search_no_results(self):
        """Search with no matches should return empty list"""
        from src.artifact_viewport import ArtifactViewport
        vp = ArtifactViewport()
        results = vp.search_content("art-19", "hello world", "tenant-s", "zzzzz")
        assert results == []


class TestArtifactViewportTenantIsolation:
    """Test that viewport respects tenant boundaries"""

    def test_different_tenants_get_different_manifests(self):
        """Manifests should be keyed by tenant"""
        from src.artifact_viewport import ArtifactViewport
        vp = ArtifactViewport()
        content = "same content"
        m1 = vp.get_manifest("art-20", content, "tenant-t1")
        m2 = vp.get_manifest("art-20", content, "tenant-t2")
        assert m1.tenant_id == "tenant-t1"
        assert m2.tenant_id == "tenant-t2"

    def test_access_log_filtered_by_tenant(self):
        """Access log should filter by tenant"""
        from src.artifact_viewport import ArtifactViewport
        vp = ArtifactViewport()
        vp.project_head("art-21", "content-a", "tenant-u1")
        vp.project_head("art-22", "content-b", "tenant-u2")
        vp.project_head("art-23", "content-c", "tenant-u1")

        log_u1 = vp.get_access_log(tenant_id="tenant-u1")
        log_u2 = vp.get_access_log(tenant_id="tenant-u2")
        assert len(log_u1) == 2
        assert len(log_u2) == 1

    def test_thread_safe_access(self):
        """Concurrent viewport access should not raise errors"""
        from src.artifact_viewport import ArtifactViewport
        vp = ArtifactViewport()
        content = "\n".join(f"line {i}" for i in range(50))
        errors = []

        def access(tid):
            try:
                vp.get_manifest(f"art-{tid}", content, tid)
                vp.project_head(f"art-{tid}", content, tid)
                vp.search_content(f"art-{tid}", content, tid, "line")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=access, args=(f"t-{i}",)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []


class TestArtifactViewportAPI:
    """Test the Flask REST API blueprint"""

    @pytest.fixture
    def client(self):
        """Create test client with viewport API mounted"""
        pytest.importorskip("flask", reason="Flask not installed")
        from flask import Flask
        from src.artifact_viewport import ArtifactViewport
        from src.artifact_viewport_api import mount_viewport_api

        app = Flask(__name__)
        app.config['TESTING'] = True
        viewport = ArtifactViewport()

        # Simple content resolver for testing
        test_store = {
            'doc-1': "# Title\n\nParagraph one.\n\n## Section Two\n\nParagraph two.\nMore content.\n",
            'doc-2': json.dumps({
                "execution_graph": {"steps": [{"id": "s1"}, {"id": "s2"}]},
                "confidence": 0.85,
            }),
            'doc-3': "\n".join(f"Line {i+1}" for i in range(200)),
        }

        def resolver(artifact_id, tenant_id, origin):
            return test_store.get(artifact_id)

        mount_viewport_api(app, viewport, resolver)

        with app.test_client() as c:
            yield c

    def test_health_endpoint(self, client):
        resp = client.get('/viewport/health')
        assert resp.status_code == 200
        assert resp.get_json()['status'] == 'healthy'

    def test_manifest_endpoint(self, client):
        resp = client.get('/viewport/manifest/doc-1')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert data['manifest']['total_lines'] > 0

    def test_project_default(self, client):
        resp = client.get('/viewport/project/doc-3')
        assert resp.status_code == 200
        data = resp.get_json()
        proj = data['projection']
        assert proj['range_start'] == 1
        assert len(proj['lines']) == 50  # default viewport size

    def test_project_custom_range(self, client):
        resp = client.get('/viewport/project/doc-3?start_line=10&end_line=20')
        assert resp.status_code == 200
        proj = resp.get_json()['projection']
        assert proj['range_start'] == 10
        assert proj['range_end'] == 20

    def test_project_head_mode(self, client):
        resp = client.get('/viewport/project/doc-3?mode=head&num_lines=5')
        assert resp.status_code == 200
        proj = resp.get_json()['projection']
        assert proj['range_start'] == 1
        assert proj['range_end'] == 5

    def test_project_tail_mode(self, client):
        resp = client.get('/viewport/project/doc-3?mode=tail&num_lines=5')
        assert resp.status_code == 200
        proj = resp.get_json()['projection']
        assert proj['range_end'] == 200

    def test_search_endpoint(self, client):
        resp = client.get('/viewport/search/doc-3?q=Line+100')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['match_count'] >= 1

    def test_search_missing_query(self, client):
        resp = client.get('/viewport/search/doc-3')
        assert resp.status_code == 400

    def test_invalid_artifact_id(self, client):
        # Overlong ID (Flask route accepts it, our validation rejects it)
        long_id = "a" * 300
        # Use POST method which accepts any path argument
        resp = client.post(f'/viewport/manifest/{long_id}',
                           json={'content': 'test'})
        assert resp.status_code == 400

    def test_not_found_artifact(self, client):
        resp = client.get('/viewport/manifest/nonexistent')
        assert resp.status_code == 404

    def test_project_section_mode(self, client):
        resp = client.get('/viewport/project/doc-1?section=Section+Two')
        assert resp.status_code == 200
        proj = resp.get_json()['projection']
        rendered = "\n".join(proj['lines'])
        assert "Paragraph two" in rendered
