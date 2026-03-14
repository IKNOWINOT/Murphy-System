# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Tests verifying that the operational and security gaps identified during the
system scan have been closed.

Gap categories covered:
  1. Version consistency (setup.py ↔ pyproject.toml)
  2. Duplicate dependency removal (requirements.txt)
  3. Default credential elimination (docker-compose.yml)
  4. Production secret enforcement (deployment_readiness.py)
  5. Webhook secret enforcement in production (deployment_readiness.py)
  6. Pytest config consolidation (pyproject.toml only, no pytest.ini)
  7. Alembic env-var comment (alembic.ini)
  8. Deployment guide security checklist
  9. .env.example Docker Compose credentials section
"""

import os
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Resolve the project root (Murphy System/) for file-based assertions.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ---------------------------------------------------------------------------
# 1. Version consistency
# ---------------------------------------------------------------------------

class TestVersionConsistency:
    """setup.py and pyproject.toml must agree on version."""

    def _read(self, rel_path: str) -> str:
        with open(os.path.join(_PROJECT_ROOT, rel_path)) as fh:
            return fh.read()

    def test_setup_py_version_is_1_0_0(self):
        content = self._read("setup.py")
        assert 'version="1.0.0"' in content or "version='1.0.0'" in content

    def test_pyproject_version_is_1_0_0(self):
        content = self._read("pyproject.toml")
        assert 'version = "1.0.0"' in content

    def test_versions_match(self):
        setup = self._read("setup.py")
        pyproject = self._read("pyproject.toml")
        # Extract versions with simple regex
        setup_ver = re.search(r'version\s*=\s*["\'](\d+\.\d+\.\d+)["\']', setup)
        pyproject_ver = re.search(r'version\s*=\s*"(\d+\.\d+\.\d+)"', pyproject)
        assert setup_ver and pyproject_ver
        assert setup_ver.group(1) == pyproject_ver.group(1), (
            f"setup.py ({setup_ver.group(1)}) != pyproject.toml ({pyproject_ver.group(1)})"
        )

    def test_setup_py_dependency_pins_match_requirements(self):
        """setup.py install_requires should not have weaker pins than requirements.txt."""
        setup = self._read("setup.py")
        # The critical ones: transformers, torch, cryptography
        assert "transformers>=4.48.0" in setup
        assert "torch>=2.6.0" in setup
        assert "cryptography>=46.0.5" in setup


# ---------------------------------------------------------------------------
# 2. Duplicate dependency removal
# ---------------------------------------------------------------------------

class TestRequirements:
    """requirements.txt should not contain duplicate entries."""

    def _lines(self) -> list:
        with open(os.path.join(_PROJECT_ROOT, "requirements.txt")) as fh:
            return [
                line.strip()
                for line in fh
                if line.strip() and not line.strip().startswith("#")
            ]

    def test_no_duplicate_matrix_nio(self):
        lines = self._lines()
        nio_lines = [l for l in lines if "matrix-nio" in l]
        assert len(nio_lines) == 1, f"Expected 1 matrix-nio entry, found {len(nio_lines)}: {nio_lines}"

    def test_no_duplicate_packages(self):
        """No package name should appear more than once."""
        lines = self._lines()
        seen: dict = {}
        for line in lines:
            name = re.split(r"[><=\[]", line)[0].strip().lower()
            seen.setdefault(name, []).append(line)
        dupes = {k: v for k, v in seen.items() if len(v) > 1}
        assert not dupes, f"Duplicate packages: {dupes}"


# ---------------------------------------------------------------------------
# 3. Default credential elimination (docker-compose.yml)
# ---------------------------------------------------------------------------

class TestDockerComposeCredentials:
    """docker-compose.yml must not contain fallback default passwords."""

    def _content(self) -> str:
        with open(os.path.join(_PROJECT_ROOT, "docker-compose.yml")) as fh:
            return fh.read()

    def test_no_default_postgres_password(self):
        content = self._content()
        assert "POSTGRES_PASSWORD:-murphy" not in content, (
            "docker-compose.yml still uses default PostgreSQL password"
        )

    def test_no_default_grafana_password(self):
        content = self._content()
        assert "GRAFANA_ADMIN_PASSWORD:-admin" not in content, (
            "docker-compose.yml still uses default Grafana password"
        )

    def test_no_default_grafana_user(self):
        content = self._content()
        assert "GRAFANA_ADMIN_USER:-admin" not in content, (
            "docker-compose.yml still uses default Grafana user"
        )

    def test_postgres_password_required(self):
        """POSTGRES_PASSWORD should use :? (required) syntax."""
        content = self._content()
        assert "POSTGRES_PASSWORD:?" in content or "POSTGRES_PASSWORD}" not in content

    def test_redis_password_supported(self):
        """docker-compose.yml should support REDIS_PASSWORD."""
        content = self._content()
        assert "REDIS_PASSWORD" in content

    def test_security_notes_present(self):
        """docker-compose.yml should contain production security notes."""
        content = self._content()
        assert "PRODUCTION SECURITY NOTES" in content or "security" in content.lower()


# ---------------------------------------------------------------------------
# 4. Production secret enforcement (deployment_readiness.py)
# ---------------------------------------------------------------------------

class TestProductionSecretEnforcement:
    """DeploymentReadinessChecker must fail when critical secrets are missing
    in production/staging."""

    def test_production_secrets_check_exists(self):
        from src.deployment_readiness import DeploymentReadinessChecker
        checker = DeploymentReadinessChecker()
        check_names = [c.name for c in checker._checks]
        assert "production_secrets" in check_names

    def test_production_secrets_fail_when_missing(self):
        """In production env, missing secrets should cause a failure."""
        # Temporarily set MURPHY_ENV to production
        old_env = os.environ.get("MURPHY_ENV")
        old_keys = {
            k: os.environ.pop(k, None)
            for k in ["MURPHY_API_KEYS", "MURPHY_CREDENTIAL_MASTER_KEY",
                       "JWT_SECRET_KEY", "POSTGRES_PASSWORD"]
        }
        try:
            os.environ["MURPHY_ENV"] = "production"
            from src.deployment_readiness import _check_production_secrets
            ok, detail = _check_production_secrets()()
            assert not ok, f"Expected failure, got: {detail}"
            assert "Missing required secrets" in detail
        finally:
            if old_env is not None:
                os.environ["MURPHY_ENV"] = old_env
            else:
                os.environ.pop("MURPHY_ENV", None)
            for k, v in old_keys.items():
                if v is not None:
                    os.environ[k] = v

    def test_production_secrets_pass_when_set(self):
        old_env = os.environ.get("MURPHY_ENV")
        old_keys = {}
        required = {
            "MURPHY_API_KEYS": "test-key",
            "MURPHY_CREDENTIAL_MASTER_KEY": "test-master",
            "JWT_SECRET_KEY": "a" * 32,
            "POSTGRES_PASSWORD": "strong-password",
        }
        try:
            for k, v in required.items():
                old_keys[k] = os.environ.get(k)
                os.environ[k] = v
            os.environ["MURPHY_ENV"] = "production"
            from src.deployment_readiness import _check_production_secrets
            ok, detail = _check_production_secrets()()
            assert ok, f"Expected pass, got: {detail}"
        finally:
            if old_env is not None:
                os.environ["MURPHY_ENV"] = old_env
            else:
                os.environ.pop("MURPHY_ENV", None)
            for k, v in old_keys.items():
                if v is not None:
                    os.environ[k] = v
                else:
                    os.environ.pop(k, None)

    def test_development_skips_secret_check(self):
        old_env = os.environ.get("MURPHY_ENV")
        try:
            os.environ["MURPHY_ENV"] = "development"
            from src.deployment_readiness import _check_production_secrets
            ok, detail = _check_production_secrets()()
            assert ok, f"Expected skip, got: {detail}"
            assert "skipped" in detail.lower()
        finally:
            if old_env is not None:
                os.environ["MURPHY_ENV"] = old_env
            else:
                os.environ.pop("MURPHY_ENV", None)


# ---------------------------------------------------------------------------
# 5. Webhook secret enforcement in production
# ---------------------------------------------------------------------------

class TestWebhookSecretEnforcement:
    """Webhook secrets should be enforced in production."""

    def test_webhook_secrets_check_exists(self):
        from src.deployment_readiness import DeploymentReadinessChecker
        checker = DeploymentReadinessChecker()
        check_names = [c.name for c in checker._checks]
        assert "webhook_secrets" in check_names

    def test_webhook_secrets_fail_in_production(self):
        old_env = os.environ.get("MURPHY_ENV")
        old_paypal = os.environ.pop("PAYPAL_WEBHOOK_SECRET", None)
        old_coinbase = os.environ.pop("COINBASE_WEBHOOK_SECRET", None)
        try:
            os.environ["MURPHY_ENV"] = "production"
            from src.deployment_readiness import _check_webhook_secrets_in_production
            ok, detail = _check_webhook_secrets_in_production()()
            assert not ok
            assert "missing" in detail.lower()
        finally:
            if old_env is not None:
                os.environ["MURPHY_ENV"] = old_env
            else:
                os.environ.pop("MURPHY_ENV", None)
            if old_paypal is not None:
                os.environ["PAYPAL_WEBHOOK_SECRET"] = old_paypal
            if old_coinbase is not None:
                os.environ["COINBASE_WEBHOOK_SECRET"] = old_coinbase

    def test_webhook_secrets_skip_in_development(self):
        old_env = os.environ.get("MURPHY_ENV")
        try:
            os.environ["MURPHY_ENV"] = "development"
            from src.deployment_readiness import _check_webhook_secrets_in_production
            ok, detail = _check_webhook_secrets_in_production()()
            assert ok
            assert "skipped" in detail.lower()
        finally:
            if old_env is not None:
                os.environ["MURPHY_ENV"] = old_env
            else:
                os.environ.pop("MURPHY_ENV", None)


# ---------------------------------------------------------------------------
# 6. Pytest config consolidation
# ---------------------------------------------------------------------------

class TestPytestConfigConsolidation:
    """pytest.ini should not exist; all config should be in pyproject.toml."""

    def test_no_pytest_ini(self):
        assert not os.path.exists(os.path.join(_PROJECT_ROOT, "pytest.ini")), (
            "pytest.ini should be removed — config is in pyproject.toml"
        )

    def test_pyproject_has_collection_warning_filter(self):
        with open(os.path.join(_PROJECT_ROOT, "pyproject.toml")) as fh:
            content = fh.read()
        assert "PytestCollectionWarning" in content, (
            "pyproject.toml should include PytestCollectionWarning filter "
            "(was previously in pytest.ini)"
        )

    def test_pyproject_has_testpaths(self):
        with open(os.path.join(_PROJECT_ROOT, "pyproject.toml")) as fh:
            content = fh.read()
        assert "testpaths" in content

    def test_pyproject_has_asyncio_mode(self):
        with open(os.path.join(_PROJECT_ROOT, "pyproject.toml")) as fh:
            content = fh.read()
        assert "asyncio_mode" in content


# ---------------------------------------------------------------------------
# 7. Alembic env-var comment
# ---------------------------------------------------------------------------

class TestAlembicConfig:
    """alembic.ini should document the env-var override."""

    def test_alembic_ini_mentions_env_override(self):
        with open(os.path.join(_PROJECT_ROOT, "alembic.ini")) as fh:
            content = fh.read()
        assert "DATABASE_URL" in content or "environment" in content.lower(), (
            "alembic.ini should document the environment variable override"
        )


# ---------------------------------------------------------------------------
# 8. Deployment guide security checklist
# ---------------------------------------------------------------------------

class TestDeploymentGuide:
    """DEPLOYMENT_GUIDE.md should contain a security hardening checklist."""

    def _content(self) -> str:
        path = os.path.join(_PROJECT_ROOT, "documentation", "deployment", "DEPLOYMENT_GUIDE.md")
        with open(path) as fh:
            return fh.read()

    def test_security_checklist_exists(self):
        content = self._content()
        assert "Security Hardening Checklist" in content

    def test_checklist_covers_postgres_password(self):
        content = self._content()
        assert "POSTGRES_PASSWORD" in content

    def test_checklist_covers_grafana(self):
        content = self._content()
        assert "GRAFANA" in content or "Grafana" in content

    def test_checklist_covers_redis(self):
        content = self._content()
        assert "REDIS" in content or "Redis" in content

    def test_checklist_covers_cors(self):
        content = self._content()
        assert "CORS" in content

    def test_checklist_covers_tls(self):
        content = self._content()
        assert "TLS" in content


# ---------------------------------------------------------------------------
# 9. .env.example Docker Compose section
# ---------------------------------------------------------------------------

class TestEnvExample:
    """.env.example should document required Docker Compose credentials."""

    def _content(self) -> str:
        with open(os.path.join(_PROJECT_ROOT, ".env.example")) as fh:
            return fh.read()

    def test_documents_postgres_password(self):
        content = self._content()
        assert "POSTGRES_PASSWORD" in content

    def test_documents_grafana_credentials(self):
        content = self._content()
        assert "GRAFANA_ADMIN_USER" in content
        assert "GRAFANA_ADMIN_PASSWORD" in content

    def test_documents_redis_password(self):
        content = self._content()
        assert "REDIS_PASSWORD" in content

    def test_documents_docker_compose_section(self):
        content = self._content()
        assert "DOCKER COMPOSE" in content.upper() or "docker compose" in content.lower()


# ---------------------------------------------------------------------------
# 10. Billing module import paths (CRITICAL fix)
# ---------------------------------------------------------------------------

class TestBillingImportPaths:
    """src/billing/api.py must use fully-qualified import paths."""

    def _billing_api_source(self) -> str:
        with open(os.path.join(_PROJECT_ROOT, "src", "billing", "api.py")) as fh:
            return fh.read()

    def test_currency_import_uses_src_prefix(self):
        """billing/api.py should import from src.billing.currency, not billing.currency."""
        source = self._billing_api_source()
        assert "from src.billing.currency import" in source
        assert "from billing.currency import" not in source

    def test_subscription_manager_uses_src_prefix(self):
        """billing/api.py should import from src.subscription_manager, not bare subscription_manager."""
        source = self._billing_api_source()
        assert "from src.subscription_manager import" in source
        # Ensure no bare import (unqualified) is used
        lines = source.splitlines()
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("from subscription_manager import"):
                pytest.fail(
                    f"Found bare import: {stripped!r} — should use 'from src.subscription_manager import'"
                )

    def test_billing_api_importable(self):
        """Verify src.billing.api can actually be imported."""
        from src.billing.api import create_billing_router
        assert callable(create_billing_router)


# ---------------------------------------------------------------------------
# 11. Runtime app.py billing import path
# ---------------------------------------------------------------------------

class TestRuntimeBillingImport:
    """src/runtime/app.py must import billing through src.billing."""

    def test_app_imports_src_billing(self):
        with open(os.path.join(_PROJECT_ROOT, "src", "runtime", "app.py")) as fh:
            source = fh.read()
        assert "from src.billing.api import" in source
        assert "from billing.api import" not in source


# ---------------------------------------------------------------------------
# 12. _deps.py sys.path points to project root
# ---------------------------------------------------------------------------

class TestDepsPathSetup:
    """src/runtime/_deps.py must add the project root to sys.path."""

    def test_deps_adds_project_root_to_path(self):
        with open(os.path.join(_PROJECT_ROOT, "src", "runtime", "_deps.py")) as fh:
            source = fh.read()
        # Must use parent.parent.parent to get Murphy System/ from src/runtime/_deps.py
        assert "parent.parent.parent" in source


# ---------------------------------------------------------------------------
# 13. Config description accuracy
# ---------------------------------------------------------------------------

class TestConfigDescriptions:
    """src/config.py field descriptions should not reference stale frameworks."""

    def test_no_flask_reference_in_api_debug(self):
        with open(os.path.join(_PROJECT_ROOT, "src", "config.py")) as fh:
            source = fh.read()
        assert "Flask debug" not in source, (
            "config.py api_debug description still references Flask — should say 'debug mode'"
        )


# ---------------------------------------------------------------------------
# 14. README module count accuracy
# ---------------------------------------------------------------------------

class TestReadmeModuleCounts:
    """README files should reflect actual module and test file counts."""

    def _murphy_readme(self) -> str:
        with open(os.path.join(_PROJECT_ROOT, "README.md")) as fh:
            return fh.read()

    def _root_readme(self) -> str:
        root = os.path.dirname(_PROJECT_ROOT)
        with open(os.path.join(root, "README.md")) as fh:
            return fh.read()

    def test_murphy_readme_module_count_current(self):
        """Murphy System/README.md should not reference stale module counts."""
        content = self._murphy_readme()
        # The old counts were 922 and 753 — both should be updated
        assert "922 source modules" not in content, "Stale module count 922 found"
        assert "753 modules" not in content, "Stale module count 753 found"

    def test_murphy_readme_package_count_current(self):
        """Murphy System/README.md should not reference stale package counts."""
        content = self._murphy_readme()
        assert "77 packages" not in content, "Stale package count 77 found"
        assert "60 packages" not in content, "Stale package count 60 found"

    def test_root_readme_module_count_current(self):
        """Root README.md should not reference stale module counts."""
        content = self._root_readme()
        assert "920+ production modules" not in content, "Stale module count '920+' found"

    def test_root_readme_test_file_count_current(self):
        """Root README.md should not reference stale test file counts."""
        content = self._root_readme()
        assert "371 test files" not in content, "Stale test file count 371 found"
        assert "603 test files" not in content, "Stale test file count 603 found"
