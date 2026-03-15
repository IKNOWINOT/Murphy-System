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

# Resolve the project root for file-based assertions.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Resolve the repository root (flattened — same as project root).
_REPO_ROOT = _PROJECT_ROOT


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
        """POSTGRES_PASSWORD should use :? (required) syntax, not a default."""
        content = self._content()
        assert "POSTGRES_PASSWORD:?" in content, (
            "POSTGRES_PASSWORD should use :? required-variable syntax"
        )
        # Must NOT have a default fallback like POSTGRES_PASSWORD:-
        assert "POSTGRES_PASSWORD:-" not in content, (
            "POSTGRES_PASSWORD should not have a default value (:-); use :? for required"
        )

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
        # Uses parent.parent to get project root from src/runtime/_deps.py
        assert "parent.parent" in source


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
        # After flattening, the root README is the same as the project README.
        with open(os.path.join(_PROJECT_ROOT, "README.md")) as fh:
            return fh.read()

    def test_murphy_readme_module_count_current(self):
        """README.md should not reference stale module counts."""
        content = self._murphy_readme()
        # The old counts were 922 and 753 — both should be updated
        assert "922 source modules" not in content, "Stale module count 922 found"
        assert "753 modules" not in content, "Stale module count 753 found"

    def test_murphy_readme_package_count_current(self):
        """README.md should not reference stale package counts."""
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
    """.env loading must resolve to the project root (.env),
    not to src/runtime/.env."""

    def test_deps_env_path_resolves_to_project_root(self):
        """_deps.py must load .env from three levels up (project root)."""
        with open(os.path.join(_PROJECT_ROOT, "src", "runtime", "_deps.py")) as fh:
            source = fh.read()
        # Should use parent.parent to reach project root from src/runtime/
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
        """STATUS.md should reference 644+ test files."""
        content = self._content()
        assert "644" in content, "STATUS.md should mention 644 test files"


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


# ---------------------------------------------------------------------------
# Round-3 gap closure: scripts, setup helpers, K8s manifests, compose files
# ---------------------------------------------------------------------------

class TestQuickDemoScript:
    """scripts/quick_demo.py must exist (referenced by Makefile 'demo' target)."""

    def test_quick_demo_exists(self):
        path = os.path.join(_PROJECT_ROOT, "scripts", "quick_demo.py")
        assert os.path.isfile(path), "scripts/quick_demo.py is missing"

    def test_quick_demo_is_importable(self):
        """File should be valid Python."""
        path = os.path.join(_PROJECT_ROOT, "scripts", "quick_demo.py")
        with open(path) as fh:
            compile(fh.read(), path, "exec")

    def test_makefile_demo_target_matches(self):
        with open(os.path.join(_PROJECT_ROOT, "Makefile")) as fh:
            content = fh.read()
        assert "scripts/quick_demo.py" in content


class TestSetupScriptsNoStaleDemoRef:
    """setup_murphy.sh/bat must not reference non-existent demo_murphy.py."""

    def test_setup_sh_no_demo_murphy(self):
        with open(os.path.join(_PROJECT_ROOT, "setup_murphy.sh")) as fh:
            content = fh.read()
        assert "demo_murphy.py" not in content, (
            "setup_murphy.sh still references non-existent demo_murphy.py"
        )

    def test_setup_bat_no_demo_murphy(self):
        with open(os.path.join(_PROJECT_ROOT, "setup_murphy.bat")) as fh:
            content = fh.read()
        assert "demo_murphy.py" not in content, (
            "setup_murphy.bat still references non-existent demo_murphy.py"
        )

    def test_setup_sh_references_quick_demo(self):
        with open(os.path.join(_PROJECT_ROOT, "setup_murphy.sh")) as fh:
            content = fh.read()
        assert "quick_demo" in content or "make demo" in content


class TestK8sConfigmapNoSecrets:
    """ConfigMap must not contain credential values; secrets belong in Secret."""

    def _configmap(self) -> str:
        with open(os.path.join(_PROJECT_ROOT, "k8s", "configmap.yaml")) as fh:
            return fh.read()

    def test_no_credential_master_key_value(self):
        content = self._configmap()
        # The key name may appear in a comment, but must not have an empty-string value
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            assert "MURPHY_CREDENTIAL_MASTER_KEY" not in stripped, (
                "MURPHY_CREDENTIAL_MASTER_KEY should not be in ConfigMap — use Secret"
            )

    def test_no_redis_url_value(self):
        content = self._configmap()
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            assert "MURPHY_REDIS_URL" not in stripped, (
                "MURPHY_REDIS_URL (contains password) should not be in ConfigMap — use Secret"
            )


class TestK8sSecretBillingKeys:
    """K8s secret.yaml must have PayPal/Coinbase billing secrets, not Stripe."""

    def _secret(self) -> str:
        with open(os.path.join(_PROJECT_ROOT, "k8s", "secret.yaml")) as fh:
            return fh.read()

    def test_no_stripe_api_key(self):
        content = self._secret()
        # STRIPE_API_KEY should not be present (billing uses PayPal + Coinbase)
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            assert "STRIPE_API_KEY" not in stripped, (
                "K8s secret still contains STRIPE_API_KEY — billing uses PayPal + Coinbase"
            )

    def test_has_paypal_webhook_secret(self):
        assert "PAYPAL_WEBHOOK_SECRET" in self._secret()

    def test_has_coinbase_webhook_secret(self):
        assert "COINBASE_WEBHOOK_SECRET" in self._secret()

    def test_has_paypal_client_id(self):
        assert "PAYPAL_CLIENT_ID" in self._secret()

    def test_has_paypal_client_secret(self):
        assert "PAYPAL_CLIENT_SECRET" in self._secret()

    def test_has_murphy_redis_url(self):
        assert "MURPHY_REDIS_URL" in self._secret()


class TestDockerComposeMurphyPinned:
    """docker-compose.murphy.yml must use pinned image versions, not :latest."""

    def _content(self) -> str:
        with open(os.path.join(_PROJECT_ROOT, "docker-compose.murphy.yml")) as fh:
            return fh.read()

    def test_prometheus_pinned(self):
        content = self._content()
        assert "prom/prometheus:latest" not in content, (
            "docker-compose.murphy.yml should pin Prometheus version"
        )
        assert "prom/prometheus:v" in content

    def test_grafana_pinned(self):
        content = self._content()
        assert "grafana/grafana:latest" not in content, (
            "docker-compose.murphy.yml should pin Grafana version"
        )
        assert "grafana/grafana:1" in content


class TestEnvExampleWebhookSecrets:
    """.env.example must document PayPal and Coinbase webhook secrets."""

    def _content(self) -> str:
        with open(os.path.join(_PROJECT_ROOT, ".env.example")) as fh:
            return fh.read()

    def test_paypal_webhook_secret_documented(self):
        assert "PAYPAL_WEBHOOK_SECRET" in self._content()

    def test_coinbase_webhook_secret_documented(self):
        assert "COINBASE_WEBHOOK_SECRET" in self._content()

    def test_paypal_labeled_primary(self):
        """PayPal should be labeled as primary, not 'alternative'."""
        assert "primary payment" in self._content().lower() or "PayPal (primary" in self._content()


# ---------------------------------------------------------------------------
# Round 4: Image pinning, lock file, CONTRIBUTING, .vscode stale refs
# ---------------------------------------------------------------------------

class TestK8sImagePinning:
    """K8s manifests must not use :latest in production."""

    def test_deployment_image_pinned(self):
        path = os.path.join(_PROJECT_ROOT, "k8s", "deployment.yaml")
        with open(path) as fh:
            content = fh.read()
        assert ":latest" not in content, "k8s/deployment.yaml still uses :latest"
        assert ":v1.0.0" in content or ":v" in content, (
            "k8s/deployment.yaml should use a versioned tag like :v1.0.0"
        )

    def test_deployment_pull_policy_not_always(self):
        path = os.path.join(_PROJECT_ROOT, "k8s", "deployment.yaml")
        with open(path) as fh:
            content = fh.read()
        assert "imagePullPolicy: Always" not in content, (
            "imagePullPolicy should be IfNotPresent with pinned images"
        )

    def test_backup_cronjob_image_pinned(self):
        path = os.path.join(_PROJECT_ROOT, "k8s", "backup-cronjob.yaml")
        with open(path) as fh:
            content = fh.read()
        assert ":latest" not in content, "k8s/backup-cronjob.yaml still uses :latest"
        assert ":v1.0.0" in content or ":v" in content


class TestContributingRequirements:
    """CONTRIBUTING.md must reference the correct requirements file."""

    def test_no_requirements_lock_install(self):
        path = os.path.join(_PROJECT_ROOT, "CONTRIBUTING.md")
        with open(path) as fh:
            content = fh.read()
        assert "pip install -r requirements.lock" not in content, (
            "CONTRIBUTING.md still tells contributors to install from incomplete lock file"
        )

    def test_uses_murphy_requirements(self):
        path = os.path.join(_PROJECT_ROOT, "CONTRIBUTING.md")
        with open(path) as fh:
            content = fh.read()
        assert "requirements_murphy_1.0.txt" in content


class TestRequirementsLockCompleteness:
    """requirements.lock must cover all packages from requirements_murphy_1.0.txt."""

    def _pkg_count(self, filename: str) -> int:
        path = os.path.join(_PROJECT_ROOT, filename)
        with open(path) as fh:
            lines = fh.readlines()
        return len([
            l for l in lines
            if l.strip() and not l.strip().startswith("#")
        ])

    def test_lock_has_at_least_80_packages(self):
        count = self._pkg_count("requirements.lock")
        assert count >= 80, f"requirements.lock has only {count} packages, expected >= 80"

    def test_lock_uses_exact_pins(self):
        path = os.path.join(_PROJECT_ROOT, "requirements.lock")
        with open(path) as fh:
            lines = fh.readlines()
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if ">=" in stripped:
                assert False, f"Lock file should use ==, not >=: {stripped}"

    def test_lock_references_murphy_source(self):
        path = os.path.join(_PROJECT_ROOT, "requirements.lock")
        with open(path) as fh:
            content = fh.read()
        assert "requirements_murphy_1.0.txt" in content, (
            "Lock file should reference its authoritative source"
        )


class TestVscodeReadmeNoStaleDemo:
    """.vscode/README.md must not reference non-existent demo_murphy.py."""

    def test_no_demo_murphy_reference(self):
        path = os.path.join(_REPO_ROOT, ".vscode", "README.md")
        with open(path) as fh:
            content = fh.read()
        assert "demo_murphy" not in content, (
            ".vscode/README.md still references non-existent demo_murphy.py"
        )

    def test_references_quick_demo(self):
        path = os.path.join(_REPO_ROOT, ".vscode", "README.md")
        with open(path) as fh:
            content = fh.read()
        assert "quick_demo" in content, (
            ".vscode/README.md should reference scripts/quick_demo.py"
        )


class TestDockerComposeMurphyRedis:
    """docker-compose.murphy.yml Redis should be version-pinned."""

    def test_redis_version_pinned(self):
        path = os.path.join(_PROJECT_ROOT, "docker-compose.murphy.yml")
        with open(path) as fh:
            content = fh.read()
        assert "redis:7-alpine" not in content, (
            "Redis should be pinned to specific version, not redis:7-alpine"
        )
        assert "redis:7." in content, "Redis version should be pinned (e.g., redis:7.2-alpine)"


class TestScalingGuideImageTag:
    """SCALING_GUIDE.md should use versioned image tags, not :latest."""

    def test_no_latest_tag(self):
        path = os.path.join(
            _PROJECT_ROOT, "documentation", "enterprise", "SCALING_GUIDE.md"
        )
        with open(path) as fh:
            content = fh.read()
        assert "murphy-system:latest" not in content, (
            "SCALING_GUIDE.md still uses :latest — production guides should use version tags"
        )


# ===================================================================
# Round 5: Deeper cross-file consistency checks
# ===================================================================

# ---------------------------------------------------------------------------
# 28. docker-compose.yml Redis version pinning
# ---------------------------------------------------------------------------

class TestDockerComposeMainRedis:
    """docker-compose.yml Redis must be pinned to match docker-compose.murphy.yml."""

    def test_redis_version_pinned(self):
        path = os.path.join(_PROJECT_ROOT, "docker-compose.yml")
        with open(path) as fh:
            content = fh.read()
        assert "redis:7-alpine" not in content, (
            "docker-compose.yml Redis should be pinned to specific version (e.g., 7.2-alpine)"
        )
        assert "redis:7." in content, "Redis version should be pinned"


# ---------------------------------------------------------------------------
# 29. docker-compose.scale.yml image consistency
# ---------------------------------------------------------------------------

class TestDockerComposeScaleImages:
    """docker-compose.scale.yml images must be consistent with main compose files."""

    def _content(self) -> str:
        path = os.path.join(
            _PROJECT_ROOT, "strategic", "gap_closure", "launch",
            "docker-compose.scale.yml"
        )
        with open(path) as fh:
            return fh.read()

    def test_no_latest_murphy_image(self):
        """Murphy image should not use :latest tag."""
        content = self._content()
        assert "murphy-system:latest" not in content, (
            "docker-compose.scale.yml uses :latest — must use versioned tag"
        )

    def test_redis_version_pinned(self):
        content = self._content()
        assert "redis:7-alpine" not in content, (
            "docker-compose.scale.yml Redis should be pinned (e.g., redis:7.2-alpine)"
        )

    def test_prometheus_version_current(self):
        content = self._content()
        assert "v2.50.0" not in content, (
            "docker-compose.scale.yml Prometheus is outdated (v2.50.0)"
        )
        assert "v2.53.0" in content, "Prometheus should be v2.53.0"

    def test_grafana_version_current(self):
        content = self._content()
        assert "grafana:10." not in content, (
            "docker-compose.scale.yml Grafana is outdated (10.x)"
        )
        assert "grafana:11.1.0" in content, "Grafana should be 11.1.0"


# ---------------------------------------------------------------------------
# 30. start_murphy_1.0.sh Python version consistency
# ---------------------------------------------------------------------------

class TestStartMurphyPythonVersion:
    """start_murphy_1.0.sh Python requirement must match pyproject.toml (>=3.10)."""

    def test_requires_python_3_10(self):
        path = os.path.join(_PROJECT_ROOT, "start_murphy_1.0.sh")
        with open(path) as fh:
            content = fh.read()
        assert 'REQUIRED_VERSION="3.10"' in content, (
            "start_murphy_1.0.sh should require Python 3.10 (matching pyproject.toml)"
        )

    def test_not_requiring_3_11(self):
        path = os.path.join(_PROJECT_ROOT, "start_murphy_1.0.sh")
        with open(path) as fh:
            content = fh.read()
        assert 'REQUIRED_VERSION="3.11"' not in content, (
            "start_murphy_1.0.sh should not require 3.11 — pyproject.toml allows 3.10+"
        )


# ---------------------------------------------------------------------------
# 31. Root README stale module/test counts
# ---------------------------------------------------------------------------

class TestRootReadmeStatsCurrent:
    """Root README.md stats section must reflect current module/test counts."""

    def _content(self) -> str:
        path = os.path.join(_REPO_ROOT, "README.md")
        with open(path) as fh:
            return fh.read()

    def test_no_stale_625_module_count(self):
        content = self._content()
        assert "625+" not in content and "625 Python" not in content, (
            "Root README.md still has stale '625+' module count"
        )

    def test_source_files_shows_978(self):
        content = self._content()
        assert "978" in content, (
            "Root README.md stats section should show 978 Python modules"
        )

    def test_test_files_updated(self):
        content = self._content()
        assert "627 test files" not in content, (
            "Root README.md still shows stale 627 test file count"
        )


# ---------------------------------------------------------------------------
# 32. K8s redis.yaml image pinning
# ---------------------------------------------------------------------------

class TestK8sRedisImagePinning:
    """k8s/redis.yaml must use a pinned Redis image version."""

    def test_redis_version_pinned(self):
        path = os.path.join(_PROJECT_ROOT, "k8s", "redis.yaml")
        with open(path) as fh:
            content = fh.read()
        assert "redis:7-alpine" not in content, (
            "k8s/redis.yaml Redis should be pinned (e.g., redis:7.2-alpine)"
        )
        assert "redis:7." in content, "Redis version should be pinned"


# ===================================================================
# Round 6: VS Code, docker-compose.murphy.yml, CONTRIBUTING.md
# ===================================================================

# ---------------------------------------------------------------------------
# 33. .vscode/launch.json — no stale murphy_integrated paths
# ---------------------------------------------------------------------------

class TestVscodeLaunchJsonNoBrokenPaths:
    """launch.json must not reference the non-existent murphy_integrated/ dir."""

    def _content(self) -> str:
        path = os.path.join(_REPO_ROOT, ".vscode", "launch.json")
        with open(path) as fh:
            return fh.read()

    def test_no_murphy_integrated_reference(self):
        content = self._content()
        assert "murphy_integrated" not in content, (
            "launch.json still references non-existent murphy_integrated/ directory"
        )

    def test_no_demo_murphy_reference(self):
        content = self._content()
        assert "demo_murphy" not in content, (
            "launch.json still references non-existent demo_murphy.py"
        )

    def test_references_quick_demo(self):
        content = self._content()
        assert "scripts/quick_demo.py" in content, (
            "launch.json should reference scripts/quick_demo.py for demos"
        )

    def test_references_runtime_entry_point(self):
        content = self._content()
        assert "murphy_system_1.0_runtime.py" in content, (
            "launch.json should reference murphy_system_1.0_runtime.py for server"
        )


# ---------------------------------------------------------------------------
# 34. .vscode/tasks.json — no stale murphy_integrated paths
# ---------------------------------------------------------------------------

class TestVscodeTasksJsonNoBrokenPaths:
    """tasks.json must not reference the non-existent murphy_integrated/ dir."""

    def _content(self) -> str:
        path = os.path.join(_REPO_ROOT, ".vscode", "tasks.json")
        with open(path) as fh:
            return fh.read()

    def test_no_murphy_integrated_reference(self):
        content = self._content()
        assert "murphy_integrated" not in content, (
            "tasks.json still references non-existent murphy_integrated/ directory"
        )

    def test_no_demo_murphy_reference(self):
        content = self._content()
        assert "demo_murphy" not in content, (
            "tasks.json still references non-existent demo_murphy.py"
        )

    def test_references_quick_demo(self):
        content = self._content()
        assert "scripts/quick_demo.py" in content, (
            "tasks.json should reference scripts/quick_demo.py for demos"
        )


# ---------------------------------------------------------------------------
# 35. docker-compose.murphy.yml Grafana credential enforcement
# ---------------------------------------------------------------------------

class TestDockerComposeMurphyGrafanaCredentials:
    """docker-compose.murphy.yml must enforce Grafana credentials."""

    def _content(self) -> str:
        path = os.path.join(_PROJECT_ROOT, "docker-compose.murphy.yml")
        with open(path) as fh:
            return fh.read()

    def test_grafana_admin_password_enforced(self):
        content = self._content()
        assert "GRAFANA_ADMIN_PASSWORD" in content, (
            "docker-compose.murphy.yml must wire GRAFANA_ADMIN_PASSWORD to Grafana"
        )

    def test_grafana_admin_user_enforced(self):
        content = self._content()
        assert "GRAFANA_ADMIN_USER" in content, (
            "docker-compose.murphy.yml must wire GRAFANA_ADMIN_USER to Grafana"
        )

    def test_grafana_uses_required_var_syntax(self):
        content = self._content()
        assert ":?" in content or "GRAFANA_ADMIN_PASSWORD" in content, (
            "docker-compose.murphy.yml should enforce Grafana credentials"
        )


# ---------------------------------------------------------------------------
# 36. CONTRIBUTING.md module counts
# ---------------------------------------------------------------------------

class TestContributingModuleCounts:
    """Root CONTRIBUTING.md must reflect current module/package counts."""

    def _content(self) -> str:
        path = os.path.join(_REPO_ROOT, "CONTRIBUTING.md")
        with open(path) as fh:
            return fh.read()

    def test_no_stale_650_count(self):
        content = self._content()
        assert "650+" not in content, (
            "CONTRIBUTING.md still uses stale '650+' module count"
        )

    def test_no_stale_56_packages(self):
        content = self._content()
        assert "56 packages" not in content, (
            "CONTRIBUTING.md still uses stale '56 packages' count"
        )

    def test_current_module_count(self):
        content = self._content()
        assert "978" in content, (
            "CONTRIBUTING.md should reflect 978 source modules"
        )

    def test_current_package_count(self):
        content = self._content()
        assert "81 packages" in content, (
            "CONTRIBUTING.md should reflect 81 packages"
        )


# ===================================================================
# Round 7: Cross-system consistency (K8s monitoring, compose parity,
#          root README stats, start-script permissions)
# ===================================================================

# ---------------------------------------------------------------------------
# 37. K8s Grafana image version matches Docker Compose
# ---------------------------------------------------------------------------

class TestK8sGrafanaVersionPinned:
    """K8s grafana-deployment.yaml must match the pinned Grafana version used
    in docker-compose.yml (11.1.0)."""

    def _content(self) -> str:
        path = os.path.join(
            _PROJECT_ROOT, "k8s", "monitoring", "grafana-deployment.yaml"
        )
        with open(path) as fh:
            return fh.read()

    def test_grafana_version_matches_compose(self):
        content = self._content()
        assert "grafana/grafana:11.1.0" in content, (
            "K8s grafana-deployment.yaml must use grafana:11.1.0 "
            "(matching docker-compose.yml)"
        )

    def test_no_stale_11_0_0(self):
        content = self._content()
        assert "grafana:11.0.0" not in content, (
            "K8s grafana-deployment.yaml still uses stale 11.0.0"
        )


# ---------------------------------------------------------------------------
# 38. docker-compose.murphy.yml prometheus-rules volume
# ---------------------------------------------------------------------------

class TestDockerComposeMurphyPrometheusRules:
    """docker-compose.murphy.yml must mount prometheus-rules like
    docker-compose.yml does."""

    def _content(self) -> str:
        path = os.path.join(_PROJECT_ROOT, "docker-compose.murphy.yml")
        with open(path) as fh:
            return fh.read()

    def test_prometheus_rules_mounted(self):
        content = self._content()
        assert "prometheus-rules" in content, (
            "docker-compose.murphy.yml must mount ./prometheus-rules "
            "to enable alert rules (matching docker-compose.yml)"
        )


# ---------------------------------------------------------------------------
# 39. Root README.md stats table accuracy
# ---------------------------------------------------------------------------

class TestRootReadmeStatsTableAccurate:
    """Root README.md stats table must reflect actual file counts."""

    def _content(self) -> str:
        path = os.path.join(_REPO_ROOT, "README.md")
        with open(path) as fh:
            return fh.read()

    def test_no_stale_585_test_count(self):
        content = self._content()
        assert "585+" not in content, (
            "Root README.md still uses stale '585+' test file count; "
            "actual is 644"
        )

    def test_no_stale_54_packages(self):
        content = self._content()
        assert "54 subsystem" not in content, (
            "Root README.md stats table still uses stale '54 subsystem "
            "directories'; actual is 81"
        )

    def test_stats_show_644_tests(self):
        content = self._content()
        assert "644" in content, (
            "Root README.md should show 644 test files"
        )

    def test_stats_show_81_packages(self):
        content = self._content()
        assert "81 subsystem" in content, (
            "Root README.md stats should show 81 subsystem directories"
        )


# ---------------------------------------------------------------------------
# 40. start_murphy_1.0.sh is executable
# ---------------------------------------------------------------------------

class TestStartScriptExecutable:
    """start_murphy_1.0.sh must have the executable permission bit set."""

    def test_start_script_is_executable(self):
        path = os.path.join(_PROJECT_ROOT, "start_murphy_1.0.sh")
        assert os.path.isfile(path), "start_murphy_1.0.sh not found"
        assert os.access(path, os.X_OK), (
            "start_murphy_1.0.sh is not executable; run chmod +x"
        )


# ===================================================================
# Round 8: Deployment workflow, scale compose, setup.py, CI, docs
# ===================================================================

# ---------------------------------------------------------------------------
# 41. hetzner-deploy.yml health-check if-block properly closed
# ---------------------------------------------------------------------------

class TestHetznerDeployHealthCheckSyntax:
    """The Verify health step must have a properly closed if-block with fi."""

    def _content(self) -> str:
        path = os.path.join(_REPO_ROOT, ".github", "workflows",
                            "hetzner-deploy.yml")
        with open(path) as fh:
            return fh.read()

    def test_if_block_has_fi(self):
        content = self._content()
        assert "exit 1\n          fi" in content or "exit 1\n            fi" in content, (
            "hetzner-deploy.yml health-check if-block missing closing 'fi'"
        )

    def test_no_unreachable_echo_after_exit(self):
        lines = self._content().splitlines()
        for i, line in enumerate(lines):
            if "exit 1" in line and i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                assert not next_line.startswith("echo"), (
                    f"Unreachable echo after exit 1 at line {i + 2}"
                )


# ---------------------------------------------------------------------------
# 42. docker-compose.scale.yml Grafana credentials enforced
# ---------------------------------------------------------------------------

class TestDockerComposeScaleGrafanaCredentials:
    """docker-compose.scale.yml must enforce Grafana credentials with :? syntax."""

    def _content(self) -> str:
        path = os.path.join(
            _PROJECT_ROOT, "strategic", "gap_closure", "launch",
            "docker-compose.scale.yml",
        )
        with open(path) as fh:
            return fh.read()

    def test_no_hardcoded_grafana_password(self):
        content = self._content()
        assert "GF_SECURITY_ADMIN_PASSWORD=murphy_admin" not in content, (
            "docker-compose.scale.yml has hardcoded Grafana password"
        )

    def test_grafana_password_uses_required_var(self):
        content = self._content()
        assert "GRAFANA_ADMIN_PASSWORD:?" in content, (
            "docker-compose.scale.yml must use :? syntax for Grafana password"
        )

    def test_grafana_user_uses_required_var(self):
        content = self._content()
        assert "GRAFANA_ADMIN_USER:?" in content, (
            "docker-compose.scale.yml must use :? syntax for Grafana admin user"
        )


# ---------------------------------------------------------------------------
# 43. setup.py references README.md (not non-existent README_INSTALL.md)
# ---------------------------------------------------------------------------

class TestSetupPyReadmeReference:
    """setup.py must reference README.md (which exists), not README_INSTALL.md."""

    def _content(self) -> str:
        path = os.path.join(_PROJECT_ROOT, "setup.py")
        with open(path) as fh:
            return fh.read()

    def test_no_readme_install_reference(self):
        content = self._content()
        assert "README_INSTALL.md" not in content, (
            "setup.py still references non-existent README_INSTALL.md"
        )

    def test_references_readme_md(self):
        content = self._content()
        assert '"README.md"' in content or "'README.md'" in content, (
            "setup.py should reference README.md for long_description"
        )


# ---------------------------------------------------------------------------
# 44. benchmarks.yml PYTHONPATH is quoted
# ---------------------------------------------------------------------------

class TestBenchmarksYmlPythonpathQuoted:
    """benchmarks.yml PYTHONPATH must be quoted to handle spaces in path."""

    def _content(self) -> str:
        path = os.path.join(_REPO_ROOT, ".github", "workflows",
                            "benchmarks.yml")
        with open(path) as fh:
            return fh.read()

    def test_pythonpath_is_quoted(self):
        for line in self._content().splitlines():
            stripped = line.strip()
            if stripped.startswith("PYTHONPATH:"):
                value_part = stripped.split(":", 1)[1].strip()
                assert (
                    (value_part.startswith('"') and value_part.endswith('"'))
                    or (value_part.startswith("'") and value_part.endswith("'"))
                ), (
                    f"benchmarks.yml PYTHONPATH not properly quoted: {stripped}"
                )


# ---------------------------------------------------------------------------
# 45. TROUBLESHOOTING.md has no stale api_server process references
# ---------------------------------------------------------------------------

class TestTroubleshootingNoStaleProcessName:
    """TROUBLESHOOTING.md must use murphy_system_1.0_runtime, not api_server."""

    def _content(self) -> str:
        path = os.path.join(
            _PROJECT_ROOT, "documentation", "user_guides",
            "TROUBLESHOOTING.md",
        )
        with open(path) as fh:
            return fh.read()

    def test_no_grep_api_server(self):
        content = self._content()
        assert "grep api_server" not in content, (
            "TROUBLESHOOTING.md still references 'grep api_server'"
        )

    def test_no_pgrep_api_server(self):
        content = self._content()
        assert "pgrep api_server" not in content, (
            "TROUBLESHOOTING.md still references 'pgrep api_server'"
        )

    def test_uses_correct_runtime_name(self):
        content = self._content()
        assert "murphy_system_1.0_runtime" in content, (
            "TROUBLESHOOTING.md should reference murphy_system_1.0_runtime"
        )


# ---------------------------------------------------------------------------
# 46. INSTALLATION.md has no :latest Docker tags
# ---------------------------------------------------------------------------

class TestInstallationDocNoLatestTag:
    """INSTALLATION.md must use pinned image tags, not :latest."""

    def _content(self) -> str:
        path = os.path.join(
            _PROJECT_ROOT, "documentation", "getting_started",
            "INSTALLATION.md",
        )
        with open(path) as fh:
            return fh.read()

    def test_no_latest_tag(self):
        content = self._content()
        assert ":latest" not in content, (
            "INSTALLATION.md still uses :latest Docker tag"
        )


# ---------------------------------------------------------------------------
# 47. DEPLOYMENT_GUIDE.md has no :latest Docker tags
# ---------------------------------------------------------------------------

class TestDeploymentGuideNoLatestTag:
    """DEPLOYMENT_GUIDE.md must use pinned image tags, not :latest."""

    def _content(self) -> str:
        path = os.path.join(
            _PROJECT_ROOT, "documentation", "deployment",
            "DEPLOYMENT_GUIDE.md",
        )
        with open(path) as fh:
            return fh.read()

    def test_no_latest_tag(self):
        content = self._content()
        assert ":latest" not in content, (
            "DEPLOYMENT_GUIDE.md still uses :latest Docker tag"
        )


# ---------------------------------------------------------------------------
# 48. docker-compose.scale.yml must not contain hardcoded database credentials
# ---------------------------------------------------------------------------

class TestDockerComposeScaleCredentials:
    """docker-compose.scale.yml must not contain hardcoded database passwords."""

    def _content(self) -> str:
        path = os.path.join(
            _PROJECT_ROOT, "strategic", "gap_closure", "launch",
            "docker-compose.scale.yml",
        )
        with open(path) as fh:
            return fh.read()

    def test_no_hardcoded_postgres_password(self):
        content = self._content()
        assert "POSTGRES_PASSWORD=murphy_pass" not in content, (
            "docker-compose.scale.yml has hardcoded POSTGRES_PASSWORD"
        )

    def test_postgres_password_uses_required_var(self):
        content = self._content()
        assert "POSTGRES_PASSWORD:?" in content, (
            "docker-compose.scale.yml must use :? syntax for POSTGRES_PASSWORD"
        )

    def test_no_hardcoded_database_url(self):
        content = self._content()
        assert "murphy_pass" not in content, (
            "docker-compose.scale.yml still contains hardcoded password 'murphy_pass'"
        )

    def test_database_url_uses_required_var(self):
        content = self._content()
        assert "DATABASE_URL:?" in content or "DATABASE_URL=${DATABASE_URL:?" in content, (
            "docker-compose.scale.yml must use :? syntax for DATABASE_URL"
        )


# ---------------------------------------------------------------------------
# 49. K8s manifests must have imagePullPolicy on all containers
# ---------------------------------------------------------------------------

class TestK8sImagePullPolicyPresent:
    """All K8s manifests with container images must specify imagePullPolicy."""

    def test_postgres_has_pull_policy(self):
        path = os.path.join(_PROJECT_ROOT, "k8s", "postgres.yaml")
        with open(path) as fh:
            content = fh.read()
        assert "imagePullPolicy:" in content, (
            "k8s/postgres.yaml missing imagePullPolicy"
        )

    def test_redis_has_pull_policy(self):
        path = os.path.join(_PROJECT_ROOT, "k8s", "redis.yaml")
        with open(path) as fh:
            content = fh.read()
        assert "imagePullPolicy:" in content, (
            "k8s/redis.yaml missing imagePullPolicy"
        )

    def test_grafana_has_pull_policy(self):
        path = os.path.join(
            _PROJECT_ROOT, "k8s", "monitoring", "grafana-deployment.yaml",
        )
        with open(path) as fh:
            content = fh.read()
        assert "imagePullPolicy:" in content, (
            "k8s/monitoring/grafana-deployment.yaml missing imagePullPolicy"
        )

    def test_prometheus_has_pull_policy(self):
        path = os.path.join(
            _PROJECT_ROOT, "k8s", "monitoring", "prometheus-deployment.yaml",
        )
        with open(path) as fh:
            content = fh.read()
        assert "imagePullPolicy:" in content, (
            "k8s/monitoring/prometheus-deployment.yaml missing imagePullPolicy"
        )


# ---------------------------------------------------------------------------
# 50. All terminal HTML pages must have a topbar with sidebar toggle
# ---------------------------------------------------------------------------

class TestTerminalTopbarsPresent:
    """Terminal HTML pages with sidebar JS must have btn-sidebar-toggle element."""

    @staticmethod
    def _discover_terminals():
        """Dynamically discover terminal_*.html files in the project root."""
        import glob as _glob
        return [
            os.path.basename(f)
            for f in _glob.glob(os.path.join(_PROJECT_ROOT, "terminal_*.html"))
        ]

    def test_topbar_element_exists(self):
        for fname in self._discover_terminals():
            path = os.path.join(_PROJECT_ROOT, fname)
            with open(path) as fh:
                content = fh.read()
            assert 'class="murphy-topbar"' in content or '<murphy-header' in content, (
                f"{fname} missing topbar header element"
            )

    def test_sidebar_toggle_wired(self):
        for fname in self._discover_terminals():
            path = os.path.join(_PROJECT_ROOT, fname)
            with open(path) as fh:
                content = fh.read()
            if 'btn-sidebar-toggle' in content:
                assert 'id="btn-sidebar-toggle"' in content, (
                    f"{fname} references btn-sidebar-toggle in JS but has no HTML element"
                )


# ---------------------------------------------------------------------------
# 51. Static file serving must be configured in create_app()
# ---------------------------------------------------------------------------

class TestStaticFilesAndHTMLRoutes:
    """create_app() must mount static files and HTML UI routes."""

    def _app_content(self) -> str:
        path = os.path.join(_PROJECT_ROOT, "src", "runtime", "app.py")
        with open(path) as fh:
            return fh.read()

    def test_static_files_mounted(self):
        content = self._app_content()
        assert "StaticFiles" in content, (
            "app.py must mount StaticFiles for static/ directory"
        )
        assert "/ui/static" in content, (
            "app.py must mount static files at /ui/static for relative asset paths"
        )

    def test_html_routes_defined(self):
        content = self._app_content()
        assert "murphy_landing_page.html" in content, (
            "app.py must register the landing page HTML route"
        )
        assert "terminal_architect.html" in content, (
            "app.py must register the architect terminal HTML route"
        )

    def test_matrix_api_endpoints_exist(self):
        content = self._app_content()
        for endpoint in ["/api/matrix/status", "/api/matrix/rooms",
                         "/api/matrix/send", "/api/matrix/stats"]:
            assert endpoint in content, (
                f"app.py missing Matrix bridge endpoint: {endpoint}"
            )

    def test_librarian_commands_endpoint_exists(self):
        content = self._app_content()
        assert "/api/librarian/commands" in content, (
            "app.py must have /api/librarian/commands endpoint for command catalog"
        )


# ---------------------------------------------------------------------------
# 52. Compliance API endpoints must exist
# ---------------------------------------------------------------------------

class TestComplianceEndpoints:
    """Compliance dashboard requires backend API endpoints."""

    def _app_content(self) -> str:
        path = os.path.join(_PROJECT_ROOT, "src", "runtime", "app.py")
        with open(path) as fh:
            return fh.read()

    def test_compliance_toggles_endpoint(self):
        content = self._app_content()
        assert "/api/compliance/toggles" in content, (
            "app.py must have /api/compliance/toggles endpoint"
        )

    def test_compliance_recommended_endpoint(self):
        content = self._app_content()
        assert "/api/compliance/recommended" in content, (
            "app.py must have /api/compliance/recommended endpoint"
        )

    def test_compliance_report_endpoint(self):
        content = self._app_content()
        assert "/api/compliance/report" in content, (
            "app.py must have /api/compliance/report endpoint"
        )


# ---------------------------------------------------------------------------
# 53. No hardcoded localhost API URLs in HTML pages
# ---------------------------------------------------------------------------

class TestNoHardcodedLocalhostURLs:
    """HTML pages must use relative URLs or window.location.origin, not hardcoded localhost."""

    def test_matrix_integration_no_hardcoded_port(self):
        path = os.path.join(_PROJECT_ROOT, "matrix_integration.html")
        with open(path) as fh:
            content = fh.read()
        assert "http://localhost:" not in content and "http://127.0.0.1:" not in content, (
            "matrix_integration.html must not use hardcoded localhost API URLs"
        )

    def test_production_wizard_no_hardcoded_port(self):
        path = os.path.join(_PROJECT_ROOT, "production_wizard.html")
        with open(path) as fh:
            content = fh.read()
        assert "http://localhost:" not in content and "http://127.0.0.1:" not in content, (
            "production_wizard.html must not use hardcoded localhost API URLs"
        )

    def test_murphy_auth_no_hardcoded_base(self):
        path = os.path.join(_PROJECT_ROOT, "murphy_auth.js")
        with open(path) as fh:
            content = fh.read()
        assert "http://127.0.0.1:" not in content and "http://localhost:" not in content, (
            "murphy_auth.js must not use hardcoded localhost API URLs"
        )


# ---------------------------------------------------------------------------
# 54. CSP headers must allow Google Fonts
# ---------------------------------------------------------------------------

class TestCSPGoogleFonts:
    """CSP headers must include Google Fonts domains for proper font loading."""

    def test_fastapi_csp_allows_google_fonts(self):
        path = os.path.join(_PROJECT_ROOT, "src", "fastapi_security.py")
        with open(path) as fh:
            content = fh.read()
        assert "fonts.googleapis.com" in content, (
            "fastapi_security.py CSP must allow fonts.googleapis.com in style-src"
        )
        assert "fonts.gstatic.com" in content, (
            "fastapi_security.py CSP must allow fonts.gstatic.com in font-src"
        )

    def test_flask_csp_allows_google_fonts(self):
        path = os.path.join(_PROJECT_ROOT, "src", "flask_security.py")
        with open(path) as fh:
            content = fh.read()
        assert "fonts.googleapis.com" in content, (
            "flask_security.py CSP must allow fonts.googleapis.com in style-src"
        )
        assert "fonts.gstatic.com" in content, (
            "flask_security.py CSP must allow fonts.gstatic.com in font-src"
        )


# ---------------------------------------------------------------------------
# 55. Events/SSE endpoints must exist for workspace
# ---------------------------------------------------------------------------

class TestEventsEndpoints:
    """Workspace requires events API endpoints."""

    def _app_content(self) -> str:
        path = os.path.join(_PROJECT_ROOT, "src", "runtime", "app.py")
        with open(path) as fh:
            return fh.read()

    def test_events_subscribe_endpoint(self):
        content = self._app_content()
        assert "/api/events/subscribe" in content, (
            "app.py must have /api/events/subscribe endpoint"
        )

    def test_events_stream_endpoint(self):
        content = self._app_content()
        assert "/api/events/stream/" in content, (
            "app.py must have /api/events/stream/{subscriber_id} endpoint"
        )

    def test_events_history_endpoint(self):
        content = self._app_content()
        assert "/api/events/history/" in content, (
            "app.py must have /api/events/history/{subscriber_id} endpoint"
        )

    def test_security_events_endpoint(self):
        content = self._app_content()
        assert "/api/security/events" in content, (
            "app.py must have /api/security/events endpoint"
        )


# ---------------------------------------------------------------------------
# 56. JS files at project root must be served under /ui/ path
# ---------------------------------------------------------------------------

class TestJSFileServing:
    """Root-level JS files must be served under /ui/ for relative path resolution."""

    def _app_content(self) -> str:
        path = os.path.join(_PROJECT_ROOT, "src", "runtime", "app.py")
        with open(path) as fh:
            return fh.read()

    def test_js_files_served_under_ui(self):
        content = self._app_content()
        assert '*.js' in content or 'glob("*.js")' in content, (
            "app.py must serve root-level .js files under /ui/ for relative path resolution"
        )
