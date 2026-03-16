# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Tests that validate Dockerfile syntax and .dockerignore coverage.

These are static-analysis tests — no Docker daemon required.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent  # Murphy System/

DOCKERFILE = PROJECT_ROOT / "Dockerfile"
DOCKERIGNORE = PROJECT_ROOT / ".dockerignore"
COMPOSE_MAIN = PROJECT_ROOT / "docker-compose.yml"
COMPOSE_PROD = PROJECT_ROOT / "docker-compose.prod.yml"
ENTRYPOINT = PROJECT_ROOT / "scripts" / "docker-entrypoint.sh"


# ---------------------------------------------------------------------------
# Dockerfile tests
# ---------------------------------------------------------------------------


class TestDockerfileSyntax:
    def test_dockerfile_exists(self):
        assert DOCKERFILE.exists(), "Dockerfile must exist"

    def test_multistage_build(self):
        text = DOCKERFILE.read_text()
        from_lines = [ln for ln in text.splitlines() if ln.strip().upper().startswith("FROM")]
        assert len(from_lines) >= 2, (
            "Dockerfile must use a multi-stage build (at least 2 FROM lines)"
        )

    def test_non_root_user(self):
        text = DOCKERFILE.read_text()
        assert re.search(r"^USER\s+\S+", text, re.MULTILINE), (
            "Dockerfile must switch to a non-root USER before CMD/ENTRYPOINT"
        )

    def test_healthcheck_present(self):
        text = DOCKERFILE.read_text()
        assert "HEALTHCHECK" in text, "Dockerfile must contain a HEALTHCHECK instruction"

    def test_healthcheck_interval(self):
        text = DOCKERFILE.read_text()
        assert "--interval=30s" in text, "HEALTHCHECK --interval must be 30s"

    def test_healthcheck_timeout(self):
        text = DOCKERFILE.read_text()
        assert "--timeout=5s" in text, "HEALTHCHECK --timeout must be 5s"

    def test_healthcheck_uses_health_endpoint(self):
        text = DOCKERFILE.read_text()
        assert "/api/health" in text, "HEALTHCHECK must probe /api/health"

    def test_entrypoint_script_copied(self):
        text = DOCKERFILE.read_text()
        assert "docker-entrypoint.sh" in text, (
            "Dockerfile must COPY docker-entrypoint.sh"
        )

    def test_cmd_uses_entrypoint(self):
        text = DOCKERFILE.read_text()
        assert "docker-entrypoint.sh" in text, (
            "Dockerfile CMD must reference docker-entrypoint.sh"
        )

    def test_expose_port_8000(self):
        text = DOCKERFILE.read_text()
        assert "EXPOSE 8000" in text, "Dockerfile must EXPOSE 8000"

    def test_pythonunbuffered_set(self):
        text = DOCKERFILE.read_text()
        assert "PYTHONUNBUFFERED=1" in text, "PYTHONUNBUFFERED must be set to 1"

    def test_no_sudo_in_dockerfile(self):
        text = DOCKERFILE.read_text()
        assert "sudo" not in text.lower(), "Dockerfile must not use sudo"


# ---------------------------------------------------------------------------
# .dockerignore tests
# ---------------------------------------------------------------------------


class TestDockerignoreCoverage:
    def test_dockerignore_exists(self):
        assert DOCKERIGNORE.exists(), ".dockerignore must exist in Murphy System/"

    def _lines(self) -> list[str]:
        return DOCKERIGNORE.read_text().splitlines()

    def _covers(self, pattern: str) -> bool:
        """Return True if any non-comment line in .dockerignore contains the pattern."""
        for ln in self._lines():
            stripped = ln.strip()
            if stripped.startswith("#") or not stripped:
                continue
            if pattern in stripped:
                return True
        return False

    def test_excludes_git(self):
        assert self._covers(".git"), ".dockerignore must exclude .git"

    def test_excludes_docs(self):
        assert self._covers("docs"), ".dockerignore must exclude docs/"

    def test_excludes_tests(self):
        assert self._covers("tests"), ".dockerignore must exclude tests/"

    def test_excludes_markdown(self):
        assert self._covers(".md"), ".dockerignore must exclude *.md files"

    def test_excludes_pycache(self):
        assert self._covers("__pycache__"), ".dockerignore must exclude __pycache__"

    def test_excludes_dotenv(self):
        assert self._covers(".env"), ".dockerignore must exclude .env"

    def test_excludes_telemetry_evidence(self):
        assert self._covers("telemetry_evidence"), (
            ".dockerignore must exclude telemetry_evidence/"
        )

    def test_excludes_strategic(self):
        assert self._covers("strategic"), ".dockerignore must exclude strategic/"

    def test_excludes_pyc(self):
        assert self._covers(".pyc"), ".dockerignore must exclude *.pyc files"


# ---------------------------------------------------------------------------
# Entrypoint script tests
# ---------------------------------------------------------------------------


class TestEntrypointScript:
    def test_entrypoint_exists(self):
        assert ENTRYPOINT.exists(), "scripts/docker-entrypoint.sh must exist"

    def test_entrypoint_shebang(self):
        text = ENTRYPOINT.read_text()
        assert text.startswith("#!/"), "entrypoint must have a shebang line"

    def test_entrypoint_set_e(self):
        text = ENTRYPOINT.read_text()
        assert "set -e" in text, "entrypoint must use 'set -e' for error safety"

    def test_entrypoint_worker_count(self):
        text = ENTRYPOINT.read_text()
        assert "nproc" in text, (
            "entrypoint must derive worker count from nproc"
        )

    def test_entrypoint_auto_migrate(self):
        text = ENTRYPOINT.read_text()
        assert "MURPHY_AUTO_MIGRATE" in text, (
            "entrypoint must honour MURPHY_AUTO_MIGRATE for migrations"
        )

    def test_entrypoint_uvicorn(self):
        text = ENTRYPOINT.read_text()
        assert "uvicorn" in text, "entrypoint must start the server with uvicorn"

    def test_entrypoint_host_binding(self):
        text = ENTRYPOINT.read_text()
        assert "0.0.0.0" in text, "entrypoint must bind to 0.0.0.0"


# ---------------------------------------------------------------------------
# docker-compose tests
# ---------------------------------------------------------------------------


class TestDockerCompose:
    def test_compose_main_exists(self):
        assert COMPOSE_MAIN.exists(), "docker-compose.yml must exist"

    def test_compose_prod_exists(self):
        assert COMPOSE_PROD.exists(), "docker-compose.prod.yml must exist"

    def test_compose_main_has_healthcheck(self):
        text = COMPOSE_MAIN.read_text()
        assert "healthcheck" in text, "docker-compose.yml must define healthchecks"

    def test_compose_main_has_resource_limits(self):
        text = COMPOSE_MAIN.read_text()
        assert "limits" in text, (
            "docker-compose.yml must define resource limits for murphy-api"
        )

    def test_compose_main_restart_policy(self):
        text = COMPOSE_MAIN.read_text()
        assert "restart" in text, "docker-compose.yml must set a restart policy"

    def test_compose_prod_has_replicas(self):
        text = COMPOSE_PROD.read_text()
        assert "replicas" in text, "docker-compose.prod.yml must set replica count"

    def test_compose_prod_has_logging_driver(self):
        text = COMPOSE_PROD.read_text()
        assert "logging" in text, (
            "docker-compose.prod.yml must configure a logging driver"
        )

    def test_compose_prod_auto_migrate_enabled(self):
        text = COMPOSE_PROD.read_text()
        assert "MURPHY_AUTO_MIGRATE" in text, (
            "docker-compose.prod.yml must set MURPHY_AUTO_MIGRATE"
        )
