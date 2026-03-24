"""
tests/test_documentation_gaps.py

Programmatic verification that documentation-code gaps cataloged in
docs/DOC_CODE_GAP_ANALYSIS.md remain closed after Phase 4 gap closure.
"""
import os
import re
import glob
import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestEntryPointExists:
    """Verify documented entry points actually exist."""

    def test_runtime_entry_point_exists(self):
        """murphy_system_1.0_runtime.py must exist (the actual runtime entry point)."""
        path = os.path.join(REPO_ROOT, "murphy_system_1.0_runtime.py")
        assert os.path.exists(path), f"Runtime entry point missing: {path}"

    def test_no_phantom_entry_point_in_architecture_docs(self):
        """ARCHITECTURE_MAP.md must not reference the non-existent murphy_complete_backend_extended.py."""
        arch_map = os.path.join(REPO_ROOT, "ARCHITECTURE_MAP.md")
        if os.path.exists(arch_map):
            content = open(arch_map).read()
            assert "murphy_complete_backend_extended.py" not in content, (
                "ARCHITECTURE_MAP.md references non-existent murphy_complete_backend_extended.py"
            )

    def test_no_phantom_entry_point_in_dependency_graph(self):
        """DEPENDENCY_GRAPH.md must not reference the non-existent murphy_complete_backend_extended.py."""
        dep_graph = os.path.join(REPO_ROOT, "DEPENDENCY_GRAPH.md")
        if os.path.exists(dep_graph):
            content = open(dep_graph).read()
            assert "murphy_complete_backend_extended.py" not in content, (
                "DEPENDENCY_GRAPH.md references non-existent murphy_complete_backend_extended.py"
            )


class TestAPIKeyCanonicalName:
    """Verify MURPHY_API_KEY is the canonical env var name."""

    def test_env_example_uses_canonical_api_key(self):
        """The canonical API key var in .env.example should be MURPHY_API_KEY."""
        env_example = os.path.join(REPO_ROOT, ".env.example")
        assert os.path.exists(env_example), ".env.example must exist"
        content = open(env_example).read()
        assert "MURPHY_API_KEY" in content, (
            ".env.example must document MURPHY_API_KEY as the canonical API key variable"
        )

    def test_runtime_app_accepts_canonical_api_key(self):
        """src/runtime/app.py must check MURPHY_API_KEY (the canonical name)."""
        app_py = os.path.join(REPO_ROOT, "src", "runtime", "app.py")
        assert os.path.exists(app_py), "src/runtime/app.py must exist"
        content = open(app_py).read()
        assert 'MURPHY_API_KEY' in content, (
            "src/runtime/app.py must reference MURPHY_API_KEY (the canonical API key variable)"
        )


class TestNoRelativeLinksBroken:
    """Verify no broken relative links exist in markdown files."""

    def _get_all_md_files(self):
        root_mds = glob.glob(os.path.join(REPO_ROOT, "*.md"))
        docs_mds = glob.glob(os.path.join(REPO_ROOT, "docs", "*.md"))
        return root_mds + docs_mds

    def _check_links_in_file(self, filepath):
        """Return list of broken relative links in a markdown file."""
        broken = []
        dir_ = os.path.dirname(filepath)
        try:
            content = open(filepath, encoding="utf-8", errors="replace").read()
        except Exception:
            return broken
        link_pattern = re.compile(r'\[([^\]]*)\]\(([^)#]+)(?:#[^)]*)?\)')
        for m in link_pattern.finditer(content):
            href = m.group(2).strip()
            if href.startswith(('http://', 'https://', 'mailto:', 'ftp://')):
                continue
            if href.startswith('#'):
                continue
            target = os.path.normpath(os.path.join(dir_, href))
            if not os.path.exists(target):
                broken.append((href, target))
        return broken

    def test_no_broken_links_in_root_markdown(self):
        """Root-level markdown files must not have broken relative links."""
        root_mds = glob.glob(os.path.join(REPO_ROOT, "*.md"))
        all_broken = {}
        for mf in root_mds:
            broken = self._check_links_in_file(mf)
            if broken:
                all_broken[os.path.basename(mf)] = broken
        assert not all_broken, (
            f"Broken relative links found in markdown files:\n"
            + "\n".join(f"  {f}: {links}" for f, links in all_broken.items())
        )

    def test_no_broken_links_in_docs_markdown(self):
        """docs/ markdown files must not have broken relative links."""
        docs_mds = glob.glob(os.path.join(REPO_ROOT, "docs", "*.md"))
        all_broken = {}
        for mf in docs_mds:
            broken = self._check_links_in_file(mf)
            if broken:
                all_broken[os.path.relpath(mf, REPO_ROOT)] = broken
        assert not all_broken, (
            f"Broken relative links found in docs/ markdown files:\n"
            + "\n".join(f"  {f}: {links}" for f, links in all_broken.items())
        )


class TestEnvExampleCompleteness:
    """Verify .env.example documents the key env vars."""

    def _load_env_example_keys(self):
        env_example = os.path.join(REPO_ROOT, ".env.example")
        keys = set()
        if not os.path.exists(env_example):
            return keys
        for line in open(env_example):
            line = line.strip()
            if line.startswith('#'):
                m = re.match(r'#\s*([A-Z][A-Z0-9_]+)\s*=', line)
                if m:
                    keys.add(m.group(1))
            elif '=' in line and not line.startswith(' '):
                key = line.split('=', 1)[0].strip()
                if key and re.match(r'^[A-Z][A-Z0-9_]+$', key):
                    keys.add(key)
        return keys

    def test_canonical_api_key_documented(self):
        """MURPHY_API_KEY must be documented in .env.example."""
        keys = self._load_env_example_keys()
        assert 'MURPHY_API_KEY' in keys, (
            "MURPHY_API_KEY must be documented in .env.example"
        )

    def test_postgres_password_documented(self):
        """POSTGRES_PASSWORD must be documented in .env.example."""
        keys = self._load_env_example_keys()
        assert 'POSTGRES_PASSWORD' in keys, (
            "POSTGRES_PASSWORD must be documented in .env.example (required for production)"
        )


class TestAPIRoutesDocumented:
    """Verify API_ROUTES.md documents the major route groups."""

    def test_admin_routes_documented(self):
        """Admin routes (/api/admin/*) must be in API_ROUTES.md."""
        routes_file = os.path.join(REPO_ROOT, "API_ROUTES.md")
        if not os.path.exists(routes_file):
            pytest.skip("API_ROUTES.md not found")
        content = open(routes_file).read()
        assert '/api/admin' in content, "Admin routes (/api/admin/*) must be documented in API_ROUTES.md"

    def test_auth_routes_documented(self):
        """Auth routes (/api/auth/*) must be in API_ROUTES.md."""
        routes_file = os.path.join(REPO_ROOT, "API_ROUTES.md")
        if not os.path.exists(routes_file):
            pytest.skip("API_ROUTES.md not found")
        content = open(routes_file).read()
        assert '/api/auth' in content, "Auth routes (/api/auth/*) must be documented in API_ROUTES.md"

    def test_security_docs_exist(self):
        """SECURITY.md must exist and document key security features."""
        security_file = os.path.join(REPO_ROOT, "SECURITY.md")
        assert os.path.exists(security_file), "SECURITY.md must exist"
        content = open(security_file).read()
        assert 'CSRF' in content or 'csrf' in content.lower(), (
            "SECURITY.md must document CSRF protection"
        )
        assert 'rate limit' in content.lower() or 'ratelimit' in content.lower(), (
            "SECURITY.md must document rate limiting"
        )
