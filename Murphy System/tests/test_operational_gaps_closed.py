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


# ===================================================================
# Round 2: Additional gap-closure tests
# ===================================================================

# ---------------------------------------------------------------------------
# 15. .env path resolution — _deps.py and app.py must point to project root
# ---------------------------------------------------------------------------

class TestEnvPathResolution:
    """.env loading must resolve to the project root (Murphy System/.env),
    not to src/runtime/.env."""

    def test_deps_env_path_resolves_to_project_root(self):
        """_deps.py must load .env from three levels up (project root)."""
        with open(os.path.join(_PROJECT_ROOT, "src", "runtime", "_deps.py")) as fh:
            source = fh.read()
        # Should use parent.parent.parent to reach Murphy System/ from src/runtime/
        assert 'parent.parent.parent / ".env"' in source, (
            "_deps.py .env path should resolve to project root via parent.parent.parent"
        )
        # Must NOT use the old broken path
        lines = source.splitlines()
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if '_load_dotenv' in stripped and '".env"' in stripped:
                assert "parent.parent.parent" in stripped, (
                    f"Active dotenv line uses wrong path: {stripped!r}"
                )

    def test_app_env_path_resolves_to_project_root(self):
        """app.py must load .env from three levels up (project root)."""
        with open(os.path.join(_PROJECT_ROOT, "src", "runtime", "app.py")) as fh:
            source = fh.read()
        # Every _env_path assignment should use parent.parent.parent
        for i, line in enumerate(source.splitlines(), 1):
            if "_env_path" in line and "parent" in line and "==" not in line:
                assert "parent.parent.parent" in line, (
                    f"app.py line {i} has wrong .env path: {line.strip()!r}"
                )

    def test_no_src_runtime_env_path(self):
        """Neither file should resolve .env to src/runtime/."""
        for rel in ("src/runtime/_deps.py", "src/runtime/app.py"):
            with open(os.path.join(_PROJECT_ROOT, rel)) as fh:
                source = fh.read()
            # The old broken pattern was: .parent / ".env" (resolves to src/runtime/.env)
            lines = source.splitlines()
            for lineno, line in enumerate(lines, 1):
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                if '".env"' in stripped and "parent /" in stripped:
                    # This line sets an .env path — must not be single .parent
                    assert "parent.parent.parent" in stripped, (
                        f"{rel}:{lineno} still uses single-parent .env path: {stripped!r}"
                    )


# ---------------------------------------------------------------------------
# 16. setup.py consistency with pyproject.toml
# ---------------------------------------------------------------------------

class TestSetupPyConsistency:
    """setup.py must be aligned with pyproject.toml."""

    def _setup(self) -> str:
        with open(os.path.join(_PROJECT_ROOT, "setup.py")) as fh:
            return fh.read()

    def _pyproject(self) -> str:
        with open(os.path.join(_PROJECT_ROOT, "pyproject.toml")) as fh:
            return fh.read()

    def test_package_name_matches(self):
        """setup.py name= must match pyproject.toml [project] name."""
        setup = self._setup()
        pyproject = self._pyproject()
        assert 'name="murphy-system"' in setup or "name='murphy-system'" in setup, (
            "setup.py package name should be 'murphy-system' to match pyproject.toml"
        )

    def test_no_mfgc_ai_name(self):
        """The legacy 'mfgc-ai' name should be removed from setup.py."""
        setup = self._setup()
        assert 'name="mfgc-ai"' not in setup and "name='mfgc-ai'" not in setup, (
            "setup.py still uses legacy 'mfgc-ai' name"
        )

    def test_description_matches_project(self):
        """setup.py description should reference 'Murphy System'."""
        setup = self._setup()
        assert "Murphy System" in setup, (
            "setup.py description should reference 'Murphy System'"
        )

    def test_no_stale_entry_point(self):
        """setup.py should not reference the non-existent mfgc_ai module."""
        setup = self._setup()
        assert "mfgc_ai" not in setup, (
            "setup.py entry_points still references non-existent mfgc_ai module"
        )

    def test_fastapi_in_install_requires(self):
        """setup.py must include fastapi in install_requires (runtime dependency)."""
        setup = self._setup()
        assert "fastapi" in setup, "setup.py missing fastapi in install_requires"

    def test_uvicorn_in_install_requires(self):
        """setup.py must include uvicorn in install_requires (runtime dependency)."""
        setup = self._setup()
        assert "uvicorn" in setup, "setup.py missing uvicorn in install_requires"

    def test_pydantic_in_install_requires(self):
        """setup.py must include pydantic in install_requires (runtime dependency)."""
        setup = self._setup()
        assert "pydantic" in setup, "setup.py missing pydantic in install_requires"

    def test_readme_read_is_safe(self):
        """setup.py should not crash if README_INSTALL.md is missing."""
        setup = self._setup()
        pre_setup = setup.split("setup(")[0]
        has_bare_open = "open(" in pre_setup
        has_exists_guard = "exists()" in pre_setup
        has_conditional = "if" in pre_setup
        assert not has_bare_open or has_exists_guard or has_conditional, (
            "setup.py should safely handle missing README_INSTALL.md"
        )


# ---------------------------------------------------------------------------
# 17. Makefile uses correct requirements file
# ---------------------------------------------------------------------------

class TestMakefileCorrectness:
    """Makefile should reference the right requirements file."""

    def _content(self) -> str:
        with open(os.path.join(_PROJECT_ROOT, "Makefile")) as fh:
            return fh.read()

    def test_makefile_uses_murphy_requirements(self):
        """Makefile setup target should use requirements_murphy_1.0.txt."""
        content = self._content()
        assert "requirements_murphy_1.0.txt" in content, (
            "Makefile should reference requirements_murphy_1.0.txt"
        )

    def test_makefile_not_using_bare_requirements(self):
        """Makefile should not use bare 'requirements.txt' for install."""
        content = self._content()
        lines = content.splitlines()
        for line in lines:
            stripped = line.strip()
            if "pip install" in stripped and "requirements.txt" in stripped:
                assert "requirements_murphy_1.0.txt" in stripped, (
                    f"Makefile pip install uses wrong requirements file: {stripped!r}"
                )


# ---------------------------------------------------------------------------
# 18. start.sh uses correct requirements file
# ---------------------------------------------------------------------------

class TestStartShCorrectness:
    """start.sh should use the correct requirements file."""

    def _content(self) -> str:
        with open(os.path.join(_PROJECT_ROOT, "start.sh")) as fh:
            return fh.read()

    def test_start_sh_uses_murphy_requirements(self):
        """start.sh should install from requirements_murphy_1.0.txt, not requirements.lock."""
        content = self._content()
        assert "requirements_murphy_1.0.txt" in content, (
            "start.sh should reference requirements_murphy_1.0.txt"
        )

    def test_start_sh_not_using_lock_file(self):
        """start.sh should not reference the incomplete requirements.lock."""
        content = self._content()
        assert "requirements.lock" not in content, (
            "start.sh still references incomplete requirements.lock"
        )


# ---------------------------------------------------------------------------
# 19. GETTING_STARTED.md module counts accuracy
# ---------------------------------------------------------------------------

class TestGettingStartedCounts:
    """GETTING_STARTED.md should have accurate module counts."""

    def _content(self) -> str:
        with open(os.path.join(_PROJECT_ROOT, "GETTING_STARTED.md")) as fh:
            return fh.read()

    def test_no_stale_753_count(self):
        """GETTING_STARTED.md should not reference old 753 module count."""
        content = self._content()
        assert "753" not in content, "Stale module count '753' found in GETTING_STARTED.md"

    def test_no_stale_60_packages(self):
        """GETTING_STARTED.md should not reference old '60 packages'."""
        content = self._content()
        assert "60 packages" not in content, "Stale package count '60 packages' found"

    def test_updated_module_count_present(self):
        """GETTING_STARTED.md should reference 978 modules."""
        content = self._content()
        assert "978" in content, "GETTING_STARTED.md should mention 978 modules"


# ---------------------------------------------------------------------------
# 20. STATUS.md test count accuracy
# ---------------------------------------------------------------------------

class TestStatusMdCounts:
    """STATUS.md should reflect current test file counts."""

    def _content(self) -> str:
        with open(os.path.join(_PROJECT_ROOT, "STATUS.md")) as fh:
            return fh.read()

    def test_no_stale_585_count(self):
        """STATUS.md should not reference old '585+' test count."""
        content = self._content()
        assert "585+" not in content, "Stale test count '585+' found in STATUS.md"

    def test_updated_test_count_present(self):
        """STATUS.md should reference 627+ test files."""
        content = self._content()
        assert "627" in content, "STATUS.md should mention 627 test files"


# ---------------------------------------------------------------------------
# 21. Documentation — no stale demo/api_server_v2.py references
# ---------------------------------------------------------------------------

class TestDeploymentGuideEntryPoint:
    """Documentation files should reference the correct entry point."""

    def _content(self) -> str:
        path = os.path.join(_PROJECT_ROOT, "documentation", "deployment", "DEPLOYMENT_GUIDE.md")
        with open(path) as fh:
            return fh.read()

    def test_no_stale_api_server_v2_reference(self):
        """Deployment guide should not reference non-existent demo/api_server_v2.py."""
        content = self._content()
        assert "api_server_v2" not in content, (
            "DEPLOYMENT_GUIDE.md still references non-existent demo/api_server_v2.py"
        )

    def test_uses_current_runtime_entry_point(self):
        """Deployment guide should reference murphy_system_1.0_runtime.py."""
        content = self._content()
        assert "murphy_system_1.0_runtime.py" in content, (
            "DEPLOYMENT_GUIDE.md should reference murphy_system_1.0_runtime.py"
        )

    def test_systemd_services_use_correct_entry_point(self):
        """Systemd ExecStart lines in deployment guide should use the current runtime."""
        content = self._content()
        import re as _re
        exec_lines = _re.findall(r"ExecStart=.*", content)
        for line in exec_lines:
            assert "murphy_system_1.0_runtime.py" in line, (
                f"Systemd ExecStart still uses old entry point: {line!r}"
            )

    def test_no_stale_entry_point_in_any_doc(self):
        """No documentation file should reference demo/api_server_v2.py."""
        doc_dir = os.path.join(_PROJECT_ROOT, "documentation")
        stale = []
        for root, _dirs, files in os.walk(doc_dir):
            for fn in files:
                if not fn.endswith(".md"):
                    continue
                path = os.path.join(root, fn)
                with open(path) as fh:
                    content = fh.read()
                if "api_server_v2" in content:
                    rel = os.path.relpath(path, _PROJECT_ROOT)
                    stale.append(rel)
        assert not stale, (
            f"Stale demo/api_server_v2.py reference found in: {stale}"
        )
