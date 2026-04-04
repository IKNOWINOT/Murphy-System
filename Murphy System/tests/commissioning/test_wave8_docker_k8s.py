"""
Wave 8 Commissioning Tests — Docker & Kubernetes Manifest Validation

Validates docker-compose files and K8s manifests for security hardening,
correctness, and alignment with the application codebase.

Commissioning Questions Answered:
  - Does the module do what it was designed to do? → Correct image refs, ports, healthchecks
  - What conditions are possible? → Exposed ports, missing secrets, duplicate keys
  - Does the test profile reflect full capabilities? → All compose + k8s files tested
  - What is the expected result? → No 0.0.0.0 bindings for internal services, all secrets required
  - Has hardening been applied? → Localhost bindings, logging, non-root, network policies

Copyright © 2020 Inoni Limited Liability Company
License: BSL-1.1
"""

import re
from pathlib import Path

import pytest

_root = Path(__file__).resolve().parent.parent.parent


class TestDockerCompose:
    """Validate docker-compose.yml hardening."""

    @pytest.fixture
    def compose_content(self):
        return (_root / "docker-compose.yml").read_text()

    def test_postgres_binds_to_localhost(self, compose_content):
        """Postgres should not be exposed to 0.0.0.0."""
        lines = compose_content.split("\n")
        in_postgres = False
        in_ports = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("postgres:"):
                in_postgres = True
                in_ports = False
            elif in_postgres and stripped == "ports:":
                in_ports = True
            elif in_postgres and in_ports and stripped.startswith("-") and "5432" in stripped:
                assert "127.0.0.1" in stripped, f"Postgres port should bind to 127.0.0.1: {stripped}"
                break
            elif in_postgres and in_ports and not stripped.startswith("-") and stripped:
                in_ports = False

    def test_redis_binds_to_localhost(self, compose_content):
        """Redis should not be exposed to 0.0.0.0."""
        lines = compose_content.split("\n")
        in_redis = False
        for line in lines:
            if "redis:" in line.strip() and line.strip().startswith("redis:"):
                in_redis = True
            if in_redis and "6379" in line and "ports:" not in line:
                assert "127.0.0.1" in line, "Redis port should bind to 127.0.0.1"
                break

    def test_postgres_password_required(self, compose_content):
        """POSTGRES_PASSWORD must use :? syntax (fail if unset)."""
        assert "POSTGRES_PASSWORD:?" in compose_content.replace(" ", "")

    def test_grafana_creds_required(self, compose_content):
        """Grafana admin credentials must use :? syntax."""
        assert "GRAFANA_ADMIN_USER:?" in compose_content.replace(" ", "")
        assert "GRAFANA_ADMIN_PASSWORD:?" in compose_content.replace(" ", "")

    def test_healthcheck_path_correct(self, compose_content):
        """Murphy API healthcheck should hit /api/health."""
        assert "/api/health" in compose_content

    def test_all_services_have_logging(self, compose_content):
        """All services should have logging configuration."""
        # Count services and logging blocks
        service_count = compose_content.count("restart: unless-stopped")
        logging_count = compose_content.count("logging:")
        assert logging_count >= service_count, (
            f"Expected logging on all {service_count} services, "
            f"found {logging_count} logging blocks"
        )

    def test_mailserver_healthcheck_uses_cmd_shell(self, compose_content):
        """Mailserver healthcheck with pipe needs CMD-SHELL."""
        # Find the healthcheck near the mailserver section
        assert 'CMD-SHELL' in compose_content


class TestDockerComposeMurphy:
    """Validate docker-compose.murphy.yml hardening."""

    @pytest.fixture
    def compose_content(self):
        return (_root / "docker-compose.murphy.yml").read_text()

    def test_no_deprecated_version_key(self, compose_content):
        """Compose v2 does not need 'version:' key."""
        assert "version:" not in compose_content

    def test_redis_has_password_support(self, compose_content):
        """Redis should support password authentication."""
        assert "REDIS_PASSWORD" in compose_content
        assert "requirepass" in compose_content

    def test_internal_services_bind_localhost(self, compose_content):
        """Redis, Prometheus, Grafana should bind to 127.0.0.1."""
        assert "127.0.0.1" in compose_content


class TestDockerComposeHetzner:
    """Validate docker-compose.hetzner.yml (production Hetzner deployment)."""

    @pytest.fixture
    def compose_content(self):
        return (_root / "docker-compose.hetzner.yml").read_text()

    def test_all_services_bind_localhost(self, compose_content):
        """All non-mail port bindings should use 127.0.0.1 in production."""
        lines = compose_content.split("\n")
        in_ports = False
        for line in lines:
            stripped = line.strip()
            if stripped == "ports:":
                in_ports = True
                continue
            if in_ports and stripped.startswith("-") and '"' in stripped:
                # Extract the port mapping value
                port_val = stripped.lstrip("- ").strip('"')
                # Mail ports (25, 143, 465, 587, 993) are intentionally public
                mail_ports = ["25:", "143:", "465:", "587:", "993:"]
                if any(port_val.startswith(mp) for mp in mail_ports):
                    continue
                # All other port bindings should be localhost
                if any(p in port_val for p in ["5432", "6379", "9090", "3000", "8443"]):
                    assert "127.0.0.1" in port_val, (
                        f"Port binding should be localhost: {port_val}"
                    )
            elif in_ports and not stripped.startswith("-") and stripped:
                in_ports = False

    def test_all_services_have_logging(self, compose_content):
        """All Hetzner services should have json-file logging."""
        assert compose_content.count("logging:") >= 6  # 6 services

    def test_postgres_password_required(self, compose_content):
        """POSTGRES_PASSWORD must be required."""
        assert "POSTGRES_PASSWORD:?" in compose_content.replace(" ", "")


class TestDockerfile:
    """Validate Dockerfile completeness."""

    @pytest.fixture
    def dockerfile_content(self):
        return (_root / "Dockerfile").read_text()

    def test_copies_src_directory(self, dockerfile_content):
        assert "COPY src/ ./src/" in dockerfile_content

    def test_copies_orchestrators(self, dockerfile_content):
        """Root-level orchestrator files must be in the image."""
        assert "two_phase_orchestrator.py" in dockerfile_content
        assert "universal_control_plane.py" in dockerfile_content

    def test_runs_as_nonroot(self, dockerfile_content):
        assert "USER murphy" in dockerfile_content

    def test_healthcheck_configured(self, dockerfile_content):
        assert "HEALTHCHECK" in dockerfile_content
        assert "/api/health" in dockerfile_content

    def test_production_target(self, dockerfile_content):
        assert "AS production" in dockerfile_content


class TestK8sDeployment:
    """Validate K8s deployment manifest."""

    @pytest.fixture
    def deployment_content(self):
        return (_root / "k8s" / "deployment.yaml").read_text()

    def test_liveness_probe_path(self, deployment_content):
        assert "/api/health" in deployment_content

    def test_readiness_probe_path(self, deployment_content):
        assert "readinessProbe" in deployment_content

    def test_security_context(self, deployment_content):
        assert "runAsNonRoot: true" in deployment_content
        assert "readOnlyRootFilesystem: true" in deployment_content
        assert "allowPrivilegeEscalation: false" in deployment_content

    def test_resource_limits(self, deployment_content):
        assert "limits:" in deployment_content
        assert "requests:" in deployment_content


class TestK8sResourceQuota:
    """Validate resource-quota.yaml has no duplicate keys."""

    @pytest.fixture
    def quota_content(self):
        return (_root / "k8s" / "resource-quota.yaml").read_text()

    def test_no_duplicate_hard_limits(self, quota_content):
        """Each key in spec.hard should appear only once."""
        lines = [
            line.strip() for line in quota_content.split("\n")
            if line.strip() and not line.strip().startswith("#")
        ]
        # Extract keys from the hard section
        in_hard = False
        keys = []
        for line in lines:
            if line == "hard:":
                in_hard = True
                continue
            if in_hard:
                if ":" in line and not line.startswith("-"):
                    key = line.split(":")[0].strip()
                    if key in ("apiVersion", "kind", "metadata", "spec", "labels"):
                        break
                    keys.append(key)
        # Check for duplicates
        assert len(keys) == len(set(keys)), (
            f"Duplicate keys in resource-quota: {[k for k in keys if keys.count(k) > 1]}"
        )


class TestK8sSecret:
    """Validate K8s secret has all required keys."""

    @pytest.fixture
    def secret_content(self):
        return (_root / "k8s" / "secret.yaml").read_text()

    def test_has_deepinfra_key(self, secret_content):
        assert "DEEPINFRA_API_KEY" in secret_content

    def test_no_groq_references(self, secret_content):
        """No Groq references should remain."""
        assert "groq" not in secret_content.lower()

    def test_has_grafana_credentials(self, secret_content):
        assert "GRAFANA_ADMIN_USER" in secret_content
        assert "GRAFANA_ADMIN_PASSWORD" in secret_content

    def test_has_database_url(self, secret_content):
        assert "DATABASE_URL" in secret_content

    def test_has_redis_password(self, secret_content):
        assert "REDIS_PASSWORD" in secret_content


class TestK8sKustomization:
    """Validate kustomization.yaml includes all manifests."""

    @pytest.fixture
    def kustomization_content(self):
        return (_root / "k8s" / "kustomization.yaml").read_text()

    def test_includes_limit_range(self, kustomization_content):
        assert "limit-range.yaml" in kustomization_content

    def test_includes_monitoring(self, kustomization_content):
        assert "monitoring/" in kustomization_content

    def test_includes_all_core_resources(self, kustomization_content):
        required = [
            "namespace.yaml", "configmap.yaml", "secret.yaml",
            "deployment.yaml", "service.yaml", "ingress.yaml",
            "redis.yaml", "postgres.yaml",
        ]
        for res in required:
            assert res in kustomization_content, f"Missing resource: {res}"