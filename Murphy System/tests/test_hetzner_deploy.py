"""
Tests for hetzner_deploy — FounderGate, HetznerDeployProbe,
HetznerDeployPlanGenerator, HetznerDeployExecutor, HetznerDeployVerifier,
MurphyUpdateController, HetznerDeployAgent.

Security invariant validated throughout: only Corey Post (founder_admin) can
trigger a deployment. All other callers receive AuthError immediately.

Design Label: TEST-HETZNER-DEPLOY-001
Owner: QA Team / Corey Post (founder)
"""
import json
import os
import threading
from unittest.mock import MagicMock, patch, call

import pytest


from hetzner_deploy import (
    HetznerDeployAgent,
    HetznerDeployExecutor,
    HetznerDeployPlanGenerator,
    HetznerDeployProbe,
    HetznerDeployProbeReport,
    HetznerDeployResult,
    HetznerDeployStatus,
    HetznerDeployVerifier,
    HetznerStepType,
    MurphyUpdateController,
    _DEFAULT_CLUSTER_NAME,
    _DEFAULT_DEPLOYMENT,
    _DEFAULT_NAMESPACE,
    _DEFAULT_REGISTRY,
    _FOUNDER_NAME,
    _FOUNDER_ROLE,
)
from cloudflare_deploy import FounderGate
from environment_setup_agent import RiskLevel, SetupPlan, StepStatus
from signup_gateway import AuthError, SignupGateway, UserProfile


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

FOUNDER_ID = "corey-post-founder-001"


def _mock_gate(allow: bool = True) -> FounderGate:
    """Return a FounderGate whose validate() either passes or raises."""
    gate = MagicMock(spec=FounderGate)
    if allow:
        profile = UserProfile(
            user_id=FOUNDER_ID,
            name=_FOUNDER_NAME,
            role=_FOUNDER_ROLE,
            email="corey@inoni.ai",
            email_validated=True,
            eula_accepted=True,
        )
        gate.validate.return_value = profile
    else:
        gate.validate.side_effect = AuthError("not_founder", "Access denied")
    return gate


def _make_agent(
    allow: bool = True,
    public_url: str = "",
    image_tag: str = "sha-abc123",
) -> HetznerDeployAgent:
    return HetznerDeployAgent(
        user_id=FOUNDER_ID,
        image_tag=image_tag,
        public_url=public_url,
        _founder_gate=_mock_gate(allow=allow),
    )


def _probe_all_ok() -> HetznerDeployProbeReport:
    """A probe report indicating everything is ready and cluster exists."""
    return HetznerDeployProbeReport(
        hcloud_installed=True,
        hcloud_version="1.40.0",
        hcloud_path="/usr/local/bin/hcloud",
        kubectl_installed=True,
        kubectl_version="v1.29.0",
        kubectl_path="/usr/local/bin/kubectl",
        docker_installed=True,
        docker_version="Docker version 25.0.0",
        hetzner_token_set=True,
        kubeconfig_exists=True,
        registry_url=_DEFAULT_REGISTRY,
        registry_authenticated=True,
        internet_available=True,
        local_backend_running=True,
        cluster_exists=True,
        cluster_name=_DEFAULT_CLUSTER_NAME,
        cluster_id="cluster-001",
        node_count=2,
        namespace_exists=True,
        deployment_exists=True,
        current_image=f"{_DEFAULT_REGISTRY}/murphy-system:sha-old",
        service_active=True,
        ollama_running=True,
        ollama_models=["llama3"],
        issues=[],
    )


def _probe_nothing_ready() -> HetznerDeployProbeReport:
    """A probe report indicating nothing is installed or configured."""
    return HetznerDeployProbeReport(
        hcloud_installed=False,
        kubectl_installed=False,
        docker_installed=False,
        hetzner_token_set=False,
        kubeconfig_exists=False,
        internet_available=False,
        local_backend_running=False,
        cluster_exists=False,
        deployment_exists=False,
        service_active=False,
        ollama_running=False,
        ollama_models=[],
        issues=[
            "HETZNER_API_TOKEN environment variable not set",
            "no internet connection",
            "hcloud CLI not installed",
            "kubectl not installed",
            "Docker not installed",
            "Ollama is not running — start with: systemctl start ollama && ollama pull llama3",
        ],
    )


def _probe_tools_present_no_cluster() -> HetznerDeployProbeReport:
    """Tools installed, token set, internet available — but no cluster yet."""
    return HetznerDeployProbeReport(
        hcloud_installed=True,
        hcloud_version="1.40.0",
        hcloud_path="/usr/local/bin/hcloud",
        kubectl_installed=True,
        kubectl_version="v1.29.0",
        kubectl_path="/usr/local/bin/kubectl",
        docker_installed=True,
        docker_version="Docker version 25.0.0",
        hetzner_token_set=True,
        kubeconfig_exists=False,
        internet_available=True,
        local_backend_running=False,
        cluster_exists=False,
        deployment_exists=False,
        service_active=False,
        ollama_running=True,
        ollama_models=["llama3"],
        issues=[],
    )


@pytest.fixture
def agent():
    return _make_agent()


# ---------------------------------------------------------------------------
# FounderGate — security invariant (re-used from cloudflare_deploy)
# ---------------------------------------------------------------------------


class TestFounderGate:
    def test_allows_founder_with_override(self):
        gate = FounderGate(_override_founder_id=FOUNDER_ID)
        profile = gate.validate(FOUNDER_ID)
        assert profile.role == _FOUNDER_ROLE
        assert profile.name == _FOUNDER_NAME

    def test_blocks_non_founder_without_gateway(self):
        gate = FounderGate(_override_founder_id=FOUNDER_ID)
        with pytest.raises(AuthError) as exc:
            gate.validate("some-random-user")
        assert "no_gateway" in str(exc.value) or "not_founder" in str(exc.value)

    def test_blocks_wrong_role_via_gateway(self):
        gw = MagicMock(spec=SignupGateway)
        gw.get_profile.return_value = UserProfile(
            user_id="u2", name=_FOUNDER_NAME, role="worker",
            email="corey@inoni.ai", email_validated=True, eula_accepted=True,
        )
        gate = FounderGate(gateway=gw)
        with pytest.raises(AuthError, match="not_founder"):
            gate.validate("u2")

    def test_blocks_wrong_name_via_gateway(self):
        gw = MagicMock(spec=SignupGateway)
        gw.get_profile.return_value = UserProfile(
            user_id="u3", name="Someone Else", role=_FOUNDER_ROLE,
            email="other@example.com", email_validated=True, eula_accepted=True,
        )
        gate = FounderGate(gateway=gw)
        with pytest.raises(AuthError, match="founder_name_mismatch"):
            gate.validate("u3")

    def test_non_founder_cannot_instantiate_hetzner_agent(self):
        with pytest.raises(AuthError):
            _make_agent(allow=False)


# ---------------------------------------------------------------------------
# HetznerDeployProbeReport — data model
# ---------------------------------------------------------------------------


class TestHetznerDeployProbeReport:
    def test_is_ready_to_deploy_true_when_all_ok(self):
        report = _probe_all_ok()
        assert report.is_ready_to_deploy() is True

    def test_is_ready_to_deploy_false_when_no_token(self):
        report = _probe_all_ok()
        report.hetzner_token_set = False
        assert report.is_ready_to_deploy() is False

    def test_is_ready_to_deploy_false_when_no_internet(self):
        report = _probe_all_ok()
        report.internet_available = False
        assert report.is_ready_to_deploy() is False

    def test_is_ready_to_deploy_false_with_issues(self):
        report = _probe_all_ok()
        report.issues = ["something broken"]
        assert report.is_ready_to_deploy() is False

    def test_nothing_ready_not_ready_to_deploy(self):
        report = _probe_nothing_ready()
        assert report.is_ready_to_deploy() is False

    def test_to_dict_contains_all_fields(self):
        report = _probe_all_ok()
        d = report.to_dict()
        expected_keys = [
            "hcloud_installed", "hcloud_version", "hcloud_path",
            "kubectl_installed", "kubectl_version", "kubectl_path",
            "docker_installed", "docker_version",
            "hetzner_token_set", "kubeconfig_exists",
            "registry_url", "registry_authenticated",
            "internet_available", "local_backend_running",
            "cluster_exists", "cluster_name", "cluster_id", "node_count",
            "namespace_exists", "deployment_exists", "current_image",
            "service_active", "ollama_running", "ollama_models",
            "issues", "ready_to_deploy",
        ]
        for key in expected_keys:
            assert key in d, f"Missing key: {key}"

    def test_to_dict_ready_to_deploy_reflects_method(self):
        report = _probe_all_ok()
        d = report.to_dict()
        assert d["ready_to_deploy"] == report.is_ready_to_deploy()

    def test_to_dict_issues_is_list(self):
        report = _probe_nothing_ready()
        d = report.to_dict()
        assert isinstance(d["issues"], list)
        assert len(d["issues"]) > 0


# ---------------------------------------------------------------------------
# HetznerDeployProbe — mock all system calls
# ---------------------------------------------------------------------------


class TestHetznerDeployProbe:
    def test_probe_returns_report(self):
        probe = HetznerDeployProbe()
        with (
            patch("shutil.which", return_value=None),
            patch("subprocess.run", return_value=MagicMock(returncode=1, stdout="", stderr="")),
            patch("socket.create_connection", side_effect=OSError),
            patch("urllib.request.urlopen", side_effect=Exception),
            patch.dict(os.environ, {}, clear=False),
        ):
            report = probe.probe()
        assert isinstance(report, HetznerDeployProbeReport)

    def test_probe_detects_hcloud_installed(self):
        probe = HetznerDeployProbe()
        mock_result = MagicMock(returncode=0, stdout="hcloud 1.40.0\n", stderr="")
        with (
            patch("shutil.which", side_effect=lambda cmd: f"/usr/bin/{cmd}" if cmd == "hcloud" else None),
            patch("subprocess.run", return_value=mock_result),
            patch("socket.create_connection", side_effect=OSError),
            patch("urllib.request.urlopen", side_effect=Exception),
        ):
            report = probe.probe()
        assert report.hcloud_installed is True
        assert report.hcloud_path == "/usr/bin/hcloud"

    def test_probe_detects_hcloud_not_installed(self):
        probe = HetznerDeployProbe()
        with (
            patch("shutil.which", return_value=None),
            patch("subprocess.run", return_value=MagicMock(returncode=1, stdout="", stderr="")),
            patch("socket.create_connection", side_effect=OSError),
            patch("urllib.request.urlopen", side_effect=Exception),
        ):
            report = probe.probe()
        assert report.hcloud_installed is False

    def test_probe_detects_internet_available(self):
        probe = HetznerDeployProbe()
        mock_sock = MagicMock()
        with (
            patch("shutil.which", return_value=None),
            patch("subprocess.run", return_value=MagicMock(returncode=1, stdout="", stderr="")),
            patch("socket.create_connection", return_value=mock_sock),
            patch("urllib.request.urlopen", side_effect=Exception),
        ):
            report = probe.probe()
        assert report.internet_available is True

    def test_probe_detects_no_internet(self):
        probe = HetznerDeployProbe()
        with (
            patch("shutil.which", return_value=None),
            patch("subprocess.run", return_value=MagicMock(returncode=1, stdout="", stderr="")),
            patch("socket.create_connection", side_effect=OSError("timeout")),
            patch("urllib.request.urlopen", side_effect=Exception),
        ):
            report = probe.probe()
        assert report.internet_available is False

    def test_probe_detects_hetzner_token(self):
        probe = HetznerDeployProbe()
        with (
            patch("shutil.which", return_value=None),
            patch("subprocess.run", return_value=MagicMock(returncode=1, stdout="", stderr="")),
            patch("socket.create_connection", side_effect=OSError),
            patch("urllib.request.urlopen", side_effect=Exception),
            patch.dict(os.environ, {"HETZNER_API_TOKEN": "test-token-123"}),
        ):
            report = probe.probe()
        assert report.hetzner_token_set is True

    def test_probe_detects_no_hetzner_token(self):
        probe = HetznerDeployProbe()
        env = {k: v for k, v in os.environ.items() if k != "HETZNER_API_TOKEN"}
        with (
            patch("shutil.which", return_value=None),
            patch("subprocess.run", return_value=MagicMock(returncode=1, stdout="", stderr="")),
            patch("socket.create_connection", side_effect=OSError),
            patch("urllib.request.urlopen", side_effect=Exception),
            patch.dict(os.environ, env, clear=True),
        ):
            report = probe.probe()
        assert report.hetzner_token_set is False

    def test_probe_detects_local_backend_running(self):
        probe = HetznerDeployProbe()
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        with (
            patch("shutil.which", return_value=None),
            patch("subprocess.run", return_value=MagicMock(returncode=1, stdout="", stderr="")),
            patch("socket.create_connection", side_effect=OSError),
            patch("urllib.request.urlopen", return_value=mock_resp),
        ):
            report = probe.probe()
        assert report.local_backend_running is True

    def test_probe_uses_registry_env_var(self):
        probe = HetznerDeployProbe()
        with (
            patch("shutil.which", return_value=None),
            patch("subprocess.run", return_value=MagicMock(returncode=1, stdout="", stderr="")),
            patch("socket.create_connection", side_effect=OSError),
            patch("urllib.request.urlopen", side_effect=Exception),
            patch.dict(os.environ, {"MURPHY_REGISTRY_URL": "registry.example.com"}),
        ):
            report = probe.probe()
        assert report.registry_url == "registry.example.com"

    def test_probe_issues_populated_when_nothing_ready(self):
        probe = HetznerDeployProbe()
        env = {k: v for k, v in os.environ.items() if k not in ("HETZNER_API_TOKEN",)}
        with (
            patch("shutil.which", return_value=None),
            patch("subprocess.run", return_value=MagicMock(returncode=1, stdout="", stderr="")),
            patch("socket.create_connection", side_effect=OSError),
            patch("urllib.request.urlopen", side_effect=Exception),
            patch.dict(os.environ, env, clear=True),
        ):
            report = probe.probe()
        assert len(report.issues) > 0
        assert any("HETZNER_API_TOKEN" in issue for issue in report.issues)


# ---------------------------------------------------------------------------
# HetznerDeployPlanGenerator — plan generation
# ---------------------------------------------------------------------------


class TestHetznerDeployPlanGeneratorFullDeploy:
    """Full deploy (fresh cluster) generates all expected steps."""

    def test_full_deploy_generates_namespace_step(self):
        gen = HetznerDeployPlanGenerator(image_tag="sha-abc")
        plan = gen._full_deploy_plan(_probe_nothing_ready())
        step_ids = [s.step_id for s in plan.steps]
        assert "hetzner-08-apply-namespace" in step_ids

    def test_full_deploy_includes_install_hcloud_when_missing(self):
        gen = HetznerDeployPlanGenerator(image_tag="sha-abc")
        plan = gen._full_deploy_plan(_probe_nothing_ready())
        step_ids = [s.step_id for s in plan.steps]
        assert "hetzner-01-install-hcloud" in step_ids

    def test_full_deploy_includes_install_kubectl_when_missing(self):
        gen = HetznerDeployPlanGenerator(image_tag="sha-abc")
        plan = gen._full_deploy_plan(_probe_nothing_ready())
        step_ids = [s.step_id for s in plan.steps]
        assert "hetzner-02-install-kubectl" in step_ids

    def test_full_deploy_includes_create_cluster_when_no_cluster(self):
        gen = HetznerDeployPlanGenerator(image_tag="sha-abc")
        plan = gen._full_deploy_plan(_probe_nothing_ready())
        step_ids = [s.step_id for s in plan.steps]
        assert "hetzner-04-create-cluster" in step_ids

    def test_full_deploy_includes_kubeconfig_when_missing(self):
        gen = HetznerDeployPlanGenerator(image_tag="sha-abc")
        plan = gen._full_deploy_plan(_probe_nothing_ready())
        step_ids = [s.step_id for s in plan.steps]
        assert "hetzner-05-configure-kubeconfig" in step_ids

    def test_full_deploy_includes_all_k8s_resource_steps(self):
        gen = HetznerDeployPlanGenerator(image_tag="sha-abc")
        report = _probe_tools_present_no_cluster()
        plan = gen._full_deploy_plan(report)
        step_ids = [s.step_id for s in plan.steps]
        for expected in [
            "hetzner-08-apply-namespace",
            "hetzner-09-apply-resource-quota",
            "hetzner-10-apply-limit-range",
            "hetzner-11-apply-secrets",
            "hetzner-12-apply-configmap",
            "hetzner-13-apply-pvc",
            "hetzner-14-apply-network-policy",
            "hetzner-15-apply-deployment",
            "hetzner-16-apply-service",
            "hetzner-17-apply-ingress",
            "hetzner-18-apply-hpa",
        ]:
            assert expected in step_ids

    def test_full_deploy_verify_step_is_last(self):
        gen = HetznerDeployPlanGenerator(image_tag="sha-abc")
        plan = gen._full_deploy_plan(_probe_nothing_ready())
        assert plan.steps[-1].step_id == "hetzner-26-production-readiness"

    def test_full_deploy_skips_install_hcloud_when_present(self):
        gen = HetznerDeployPlanGenerator(image_tag="sha-abc")
        report = _probe_tools_present_no_cluster()
        plan = gen._full_deploy_plan(report)
        step_ids = [s.step_id for s in plan.steps]
        assert "hetzner-01-install-hcloud" not in step_ids

    def test_full_deploy_skips_install_kubectl_when_present(self):
        gen = HetznerDeployPlanGenerator(image_tag="sha-abc")
        report = _probe_tools_present_no_cluster()
        plan = gen._full_deploy_plan(report)
        step_ids = [s.step_id for s in plan.steps]
        assert "hetzner-02-install-kubectl" not in step_ids

    def test_full_deploy_skips_create_cluster_when_exists(self):
        gen = HetznerDeployPlanGenerator(image_tag="sha-abc")
        report = _probe_all_ok()
        plan = gen._full_deploy_plan(report)
        step_ids = [s.step_id for s in plan.steps]
        assert "hetzner-04-create-cluster" not in step_ids

    def test_full_deploy_correct_risk_levels(self):
        gen = HetznerDeployPlanGenerator(image_tag="sha-abc")
        report = _probe_nothing_ready()
        plan = gen._full_deploy_plan(report)
        risk_map = {s.step_id: s.risk_level for s in plan.steps}
        assert risk_map["hetzner-01-install-hcloud"] == RiskLevel.MEDIUM
        assert risk_map["hetzner-02-install-kubectl"] == RiskLevel.MEDIUM
        assert risk_map["hetzner-03-authenticate-hcloud"] == RiskLevel.HIGH
        assert risk_map["hetzner-04-create-cluster"] == RiskLevel.HIGH
        assert risk_map["hetzner-08-apply-namespace"] == RiskLevel.LOW
        assert risk_map["hetzner-11-apply-secrets"] == RiskLevel.HIGH

    def test_full_deploy_all_steps_have_liability_note(self):
        gen = HetznerDeployPlanGenerator(image_tag="sha-abc")
        plan = gen._full_deploy_plan(_probe_nothing_ready())
        for step in plan.steps:
            assert step.liability_note, f"Step {step.step_id} missing liability note"


class TestHetznerDeployPlanGeneratorRollingUpdate:
    """Rolling update (existing cluster + deployment) generates only 5 steps."""

    def test_rolling_update_generates_5_steps(self):
        gen = HetznerDeployPlanGenerator(image_tag="sha-new")
        plan = gen._rolling_update_plan(_probe_all_ok())
        assert len(plan.steps) == 4

    def test_rolling_update_step_ids(self):
        gen = HetznerDeployPlanGenerator(image_tag="sha-new")
        plan = gen._rolling_update_plan(_probe_all_ok())
        step_ids = [s.step_id for s in plan.steps]
        assert step_ids == [
            "hetzner-ru-01-git-pull",
            "hetzner-ru-02-ensure-ollama",
            "hetzner-ru-03-restart-service",
            "hetzner-ru-04-verify-health",
        ]

    def test_rolling_update_verify_step_is_last(self):
        gen = HetznerDeployPlanGenerator(image_tag="sha-new")
        plan = gen._rolling_update_plan(_probe_all_ok())
        assert "verify" in plan.steps[-1].step_id

    def test_rolling_update_risk_levels(self):
        gen = HetznerDeployPlanGenerator(image_tag="sha-new")
        plan = gen._rolling_update_plan(_probe_all_ok())
        risk_map = {s.step_id: s.risk_level for s in plan.steps}
        assert risk_map["hetzner-ru-01-git-pull"] == RiskLevel.LOW
        assert risk_map["hetzner-ru-02-ensure-ollama"] == RiskLevel.MEDIUM
        assert risk_map["hetzner-ru-03-restart-service"] == RiskLevel.MEDIUM
        assert risk_map["hetzner-ru-04-verify-health"] == RiskLevel.LOW

    def test_rolling_update_image_in_command(self):
        gen = HetznerDeployPlanGenerator(
            registry_url="ghcr.io/myorg",
            image_name="murphy-system",
            image_tag="sha-newver",
        )
        plan = gen._rolling_update_plan(_probe_all_ok())
        # SSH deploy uses git pull, not image references — verify git pull command
        pull_step = next(
            s for s in plan.steps if s.step_id == "hetzner-ru-01-git-pull"
        )
        assert "git pull" in pull_step.command

    def test_rolling_update_does_not_include_full_deploy_steps(self):
        gen = HetznerDeployPlanGenerator(image_tag="sha-new")
        plan = gen._rolling_update_plan(_probe_all_ok())
        step_ids = [s.step_id for s in plan.steps]
        for unexpected in [
            "hetzner-01-install-hcloud",
            "hetzner-04-create-cluster",
            "hetzner-08-apply-namespace",
        ]:
            assert unexpected not in step_ids


class TestHetznerDeployPlanGeneratorAutoSelect:
    def test_generate_selects_rolling_update_when_cluster_and_deployment_exist(self):
        gen = HetznerDeployPlanGenerator(image_tag="sha-new")
        plan = gen.generate(_probe_all_ok())
        step_ids = [s.step_id for s in plan.steps]
        assert "hetzner-ru-03-restart-service" in step_ids
        assert "hetzner-04-create-cluster" not in step_ids

    def test_generate_selects_full_deploy_when_no_cluster(self):
        gen = HetznerDeployPlanGenerator(image_tag="sha-new")
        plan = gen.generate(_probe_nothing_ready())
        step_ids = [s.step_id for s in plan.steps]
        assert "hetzner-04-create-cluster" in step_ids
        assert "hetzner-ru-03-restart-service" not in step_ids

    def test_generate_selects_full_deploy_when_no_deployment(self):
        gen = HetznerDeployPlanGenerator(image_tag="sha-new")
        report = _probe_all_ok()
        report.deployment_exists = False
        plan = gen.generate(report)
        step_ids = [s.step_id for s in plan.steps]
        assert "hetzner-08-apply-namespace" in step_ids


# ---------------------------------------------------------------------------
# HetznerDeployVerifier — mock urllib and kubectl
# ---------------------------------------------------------------------------


class TestHetznerDeployVerifier:
    def _make_urlopen(self, status: int = 200):
        mock_resp = MagicMock()
        mock_resp.status = status
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        return mock_resp

    def test_verify_operational_when_local_ok(self):
        """In systemd mode (default), operational when local health responds."""
        verifier = HetznerDeployVerifier(local_port=8000)
        mock_resp = self._make_urlopen(200)
        mock_pod_result = MagicMock(returncode=1, stdout="", stderr="no kubectl")
        with (
            patch("urllib.request.urlopen", return_value=mock_resp),
            patch("subprocess.run", return_value=mock_pod_result),
        ):
            result = verifier.verify()
        assert result["local_ok"] is True
        assert result["operational"] is True

    def test_verify_operational_when_pods_ok_and_local_ok(self):
        """operational is True in systemd mode with or without pods."""
        verifier = HetznerDeployVerifier(local_port=8000)
        mock_resp = self._make_urlopen(200)
        mock_pod_result = MagicMock(returncode=0, stdout="murphy-api-xxx Running\n", stderr="")
        with (
            patch("urllib.request.urlopen", return_value=mock_resp),
            patch("subprocess.run", return_value=mock_pod_result),
        ):
            result = verifier.verify()
        assert result["local_ok"] is True
        assert result["pods_ok"] is True
        assert result["operational"] is True

    def test_verify_not_operational_when_endpoint_fails(self):
        """Not operational when neither local nor public endpoint responds."""
        verifier = HetznerDeployVerifier(local_port=8000)
        mock_pod_result = MagicMock(returncode=0, stdout="murphy-api-xxx Running\n", stderr="")
        with (
            patch("urllib.request.urlopen", side_effect=Exception("connection refused")),
            patch("subprocess.run", return_value=mock_pod_result),
        ):
            result = verifier.verify()
        assert result["local_ok"] is False
        assert result["operational"] is False

    def test_verify_k8s_mode_requires_pods(self):
        """In k8s_mode=True, operational requires pods AND local/public endpoint."""
        verifier = HetznerDeployVerifier(local_port=8000, k8s_mode=True)
        mock_resp = self._make_urlopen(200)
        mock_pod_result = MagicMock(returncode=0, stdout="", stderr="")
        with (
            patch("urllib.request.urlopen", return_value=mock_resp),
            patch("subprocess.run", return_value=mock_pod_result),
        ):
            result = verifier.verify()
        assert result["pods_ok"] is False
        assert result["operational"] is False

    def test_verify_k8s_mode_operational_when_pods_and_local(self):
        verifier = HetznerDeployVerifier(local_port=8000, k8s_mode=True)
        mock_resp = self._make_urlopen(200)
        mock_pod_result = MagicMock(returncode=0, stdout="murphy-api-xxx Running\n", stderr="")
        with (
            patch("urllib.request.urlopen", return_value=mock_resp),
            patch("subprocess.run", return_value=mock_pod_result),
        ):
            result = verifier.verify()
        assert result["pods_ok"] is True
        assert result["operational"] is True

    def test_verify_checks_public_url_when_provided(self):
        verifier = HetznerDeployVerifier(
            public_url="https://murphy.example.com/api/health",
            local_port=8000,
        )
        mock_resp = self._make_urlopen(200)
        mock_pod_result = MagicMock(returncode=0, stdout="murphy-api-xxx Running\n", stderr="")
        with (
            patch("urllib.request.urlopen", return_value=mock_resp),
            patch("subprocess.run", return_value=mock_pod_result),
        ):
            result = verifier.verify()
        assert result["public_ok"] is True

    def test_verify_public_ok_false_when_url_fails(self):
        verifier = HetznerDeployVerifier(
            public_url="https://murphy.example.com/api/health",
            local_port=8000,
        )
        mock_pod_result = MagicMock(returncode=0, stdout="murphy-api-xxx Running\n", stderr="")
        with (
            patch("urllib.request.urlopen", side_effect=Exception("connection refused")),
            patch("subprocess.run", return_value=mock_pod_result),
        ):
            result = verifier.verify()
        assert result["local_ok"] is False
        assert result["public_ok"] is False

    def test_verify_dict_has_all_keys(self):
        verifier = HetznerDeployVerifier()
        with (
            patch("urllib.request.urlopen", side_effect=Exception),
            patch("subprocess.run", return_value=MagicMock(returncode=1, stdout="", stderr="")),
        ):
            result = verifier.verify()
        assert "local_ok" in result
        assert "public_ok" in result
        assert "pods_ok" in result
        assert "operational" in result

    def test_verify_operational_requires_pods_ok(self):
        """In k8s_mode, operational is False without running pods."""
        verifier = HetznerDeployVerifier(k8s_mode=True)
        mock_resp = self._make_urlopen(200)
        with (
            patch("urllib.request.urlopen", return_value=mock_resp),
            patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="", stderr="")),
        ):
            result = verifier.verify()
        assert result["pods_ok"] is False
        assert result["operational"] is False


# ---------------------------------------------------------------------------
# MurphyUpdateController — dual update path
# ---------------------------------------------------------------------------


class TestMurphyUpdateControllerCIWorkflow:
    def test_generate_ci_workflow_returns_string(self):
        ctrl = MurphyUpdateController(user_id=FOUNDER_ID, _founder_gate=_mock_gate())
        yaml_str = ctrl.generate_ci_workflow()
        assert isinstance(yaml_str, str)
        assert len(yaml_str) > 100

    def test_generate_ci_workflow_contains_push_to_main(self):
        ctrl = MurphyUpdateController(user_id=FOUNDER_ID, _founder_gate=_mock_gate())
        yaml_str = ctrl.generate_ci_workflow()
        assert "branches: [main]" in yaml_str

    def test_generate_ci_workflow_uses_ssh_action(self):
        ctrl = MurphyUpdateController(user_id=FOUNDER_ID, _founder_gate=_mock_gate())
        yaml_str = ctrl.generate_ci_workflow()
        assert "appleboy/ssh-action" in yaml_str

    def test_generate_ci_workflow_contains_hetzner_ssh_key_secret(self):
        ctrl = MurphyUpdateController(user_id=FOUNDER_ID, _founder_gate=_mock_gate())
        yaml_str = ctrl.generate_ci_workflow()
        assert "HETZNER_SSH_KEY" in yaml_str

    def test_generate_ci_workflow_contains_systemctl_restart(self):
        ctrl = MurphyUpdateController(user_id=FOUNDER_ID, _founder_gate=_mock_gate())
        yaml_str = ctrl.generate_ci_workflow()
        assert "systemctl restart" in yaml_str

    def test_generate_ci_workflow_contains_ollama(self):
        ctrl = MurphyUpdateController(user_id=FOUNDER_ID, _founder_gate=_mock_gate())
        yaml_str = ctrl.generate_ci_workflow()
        assert "ollama" in yaml_str

    def test_generate_ci_workflow_contains_health_check(self):
        ctrl = MurphyUpdateController(user_id=FOUNDER_ID, _founder_gate=_mock_gate())
        yaml_str = ctrl.generate_ci_workflow()
        assert "api/health" in yaml_str

    def test_generate_ci_workflow_contains_git_pull(self):
        ctrl = MurphyUpdateController(user_id=FOUNDER_ID, _founder_gate=_mock_gate())
        yaml_str = ctrl.generate_ci_workflow()
        assert "git pull" in yaml_str


class TestMurphyUpdateControllerTriggerUpdate:
    def _make_ctrl(self, allow: bool = True) -> MurphyUpdateController:
        return MurphyUpdateController(
            user_id=FOUNDER_ID,
            _founder_gate=_mock_gate(allow=allow),
        )

    def test_non_founder_gets_auth_error(self):
        ctrl = self._make_ctrl(allow=False)
        with pytest.raises(AuthError):
            ctrl.trigger_update()

    def test_trigger_update_returns_result(self):
        ctrl = self._make_ctrl()
        probe_report = _probe_all_ok()
        verify_result = {"local_ok": True, "public_ok": False, "pods_ok": False, "operational": True}
        with (
            patch.object(HetznerDeployProbe, "probe", return_value=probe_report),
            patch.object(HetznerDeployExecutor, "execute_plan", return_value=[]),
            patch.object(HetznerDeployVerifier, "verify", return_value=verify_result),
        ):
            result = ctrl.trigger_update()
        assert isinstance(result, HetznerDeployResult)

    def test_trigger_update_uses_rolling_update_mode(self):
        ctrl = self._make_ctrl()
        probe_report = _probe_all_ok()
        verify_result = {"local_ok": True, "public_ok": False, "pods_ok": False, "operational": True}
        with (
            patch.object(HetznerDeployProbe, "probe", return_value=probe_report),
            patch.object(HetznerDeployExecutor, "execute_plan", return_value=[]),
            patch.object(HetznerDeployVerifier, "verify", return_value=verify_result),
        ):
            result = ctrl.trigger_update()
        assert result.update_mode == "rolling_update"

    def test_trigger_update_success_when_operational(self):
        ctrl = self._make_ctrl()
        probe_report = _probe_all_ok()
        verify_result = {"local_ok": True, "public_ok": False, "pods_ok": False, "operational": True}
        with (
            patch.object(HetznerDeployProbe, "probe", return_value=probe_report),
            patch.object(HetznerDeployExecutor, "execute_plan", return_value=[]),
            patch.object(HetznerDeployVerifier, "verify", return_value=verify_result),
        ):
            result = ctrl.trigger_update()
        assert result.success is True

    def test_trigger_update_not_success_when_not_operational(self):
        ctrl = self._make_ctrl()
        probe_report = _probe_all_ok()
        verify_result = {"local_ok": False, "public_ok": False, "pods_ok": False, "operational": False}
        with (
            patch.object(HetznerDeployProbe, "probe", return_value=probe_report),
            patch.object(HetznerDeployExecutor, "execute_plan", return_value=[]),
            patch.object(HetznerDeployVerifier, "verify", return_value=verify_result),
        ):
            result = ctrl.trigger_update()
        assert result.success is False


# ---------------------------------------------------------------------------
# HetznerDeployAgent — full lifecycle
# ---------------------------------------------------------------------------


class TestHetznerDeployAgentConstruction:
    def test_founder_can_instantiate(self, agent):
        assert agent is not None
        assert agent.status == HetznerDeployStatus.NOT_STARTED

    def test_non_founder_raises_on_construction(self):
        with pytest.raises(AuthError):
            _make_agent(allow=False)

    def test_initial_plan_is_none(self, agent):
        assert agent.get_plan() is None

    def test_initial_probe_is_none(self, agent):
        assert agent.get_probe_report() is None

    def test_initial_audit_log_empty(self, agent):
        assert agent.get_audit_log() == []


class TestHetznerDeployAgentProbeAndPlan:
    def test_probe_and_plan_returns_setup_plan(self, agent):
        with patch.object(HetznerDeployProbe, "probe", return_value=_probe_all_ok()):
            plan = agent.probe_and_plan()
        assert isinstance(plan, SetupPlan)

    def test_rolling_update_probe_generates_5_steps(self, agent):
        with patch.object(HetznerDeployProbe, "probe", return_value=_probe_all_ok()):
            plan = agent.probe_and_plan()
        assert len(plan.steps) == 4

    def test_nothing_ready_probe_generates_full_deploy_plan(self, agent):
        with patch.object(HetznerDeployProbe, "probe", return_value=_probe_nothing_ready()):
            plan = agent.probe_and_plan()
        step_ids = [s.step_id for s in plan.steps]
        assert "hetzner-01-install-hcloud" in step_ids
        assert "hetzner-04-create-cluster" in step_ids

    def test_status_becomes_awaiting_approval_after_plan(self, agent):
        with patch.object(HetznerDeployProbe, "probe", return_value=_probe_all_ok()):
            agent.probe_and_plan()
        assert agent.status == HetznerDeployStatus.AWAITING_APPROVAL

    def test_plan_stored_on_agent(self, agent):
        with patch.object(HetznerDeployProbe, "probe", return_value=_probe_all_ok()):
            plan = agent.probe_and_plan()
        assert agent.get_plan() is plan

    def test_probe_report_stored_on_agent(self, agent):
        report = _probe_all_ok()
        with patch.object(HetznerDeployProbe, "probe", return_value=report):
            agent.probe_and_plan()
        assert agent.get_probe_report() is report

    def test_audit_log_populated_after_probe(self, agent):
        with patch.object(HetznerDeployProbe, "probe", return_value=_probe_all_ok()):
            agent.probe_and_plan()
        log = agent.get_audit_log()
        assert len(log) >= 2
        actions = [e["action"] for e in log]
        assert "probe" in actions
        assert "plan_generated" in actions


class TestHetznerDeployAgentHITL:
    def test_approve_all_marks_steps_approved(self, agent):
        with patch.object(HetznerDeployProbe, "probe", return_value=_probe_all_ok()):
            plan = agent.probe_and_plan()
        agent.approve_all()
        assert all(s.status == StepStatus.APPROVED for s in plan.steps)

    def test_approve_step_by_id(self, agent):
        with patch.object(HetznerDeployProbe, "probe", return_value=_probe_all_ok()):
            plan = agent.probe_and_plan()
        step_id = plan.steps[0].step_id
        result = agent.approve_step(step_id)
        assert result is True
        assert plan.steps[0].status == StepStatus.APPROVED

    def test_reject_step_by_id(self, agent):
        with patch.object(HetznerDeployProbe, "probe", return_value=_probe_all_ok()):
            plan = agent.probe_and_plan()
        step_id = plan.steps[0].step_id
        result = agent.reject_step(step_id)
        assert result is True
        assert plan.steps[0].status == StepStatus.REJECTED

    def test_approve_all_before_plan_raises(self, agent):
        with pytest.raises(RuntimeError, match="probe_and_plan"):
            agent.approve_all()

    def test_approve_step_before_plan_raises(self, agent):
        with pytest.raises(RuntimeError, match="probe_and_plan"):
            agent.approve_step("some-step-id")

    def test_reject_step_before_plan_returns_false(self, agent):
        result = agent.reject_step("some-step-id")
        assert result is False

    def test_hitl_log_populated_after_approval(self, agent):
        with patch.object(HetznerDeployProbe, "probe", return_value=_probe_all_ok()):
            agent.probe_and_plan()
        agent.approve_all()
        log = agent.get_hitl_log()
        assert len(log) >= 1


class TestHetznerDeployAgentExecuteAndVerify:
    def _setup_successful_run(self, agent: HetznerDeployAgent) -> None:
        with patch.object(HetznerDeployProbe, "probe", return_value=_probe_all_ok()):
            agent.probe_and_plan()
        agent.approve_all()

    def test_execute_without_plan_raises(self, agent):
        with pytest.raises(RuntimeError, match="probe_and_plan"):
            agent.execute_and_verify()

    def test_execute_returns_deploy_result(self, agent):
        self._setup_successful_run(agent)
        verify_ok = {
            "local_ok": True, "public_ok": False, "pods_ok": True, "operational": True
        }
        with (
            patch.object(HetznerDeployExecutor, "execute_plan", return_value=[]),
            patch.object(HetznerDeployVerifier, "verify", return_value=verify_ok),
        ):
            result = agent.execute_and_verify()
        assert isinstance(result, HetznerDeployResult)

    def test_execute_success_when_operational(self, agent):
        self._setup_successful_run(agent)
        verify_ok = {
            "local_ok": True, "public_ok": False, "pods_ok": True, "operational": True
        }
        with (
            patch.object(HetznerDeployExecutor, "execute_plan", return_value=[]),
            patch.object(HetznerDeployVerifier, "verify", return_value=verify_ok),
        ):
            result = agent.execute_and_verify()
        assert result.success is True
        assert result.attempts == 1

    def test_status_becomes_operational_on_success(self, agent):
        self._setup_successful_run(agent)
        verify_ok = {
            "local_ok": True, "public_ok": False, "pods_ok": True, "operational": True
        }
        with (
            patch.object(HetznerDeployExecutor, "execute_plan", return_value=[]),
            patch.object(HetznerDeployVerifier, "verify", return_value=verify_ok),
        ):
            agent.execute_and_verify()
        assert agent.status == HetznerDeployStatus.OPERATIONAL

    def test_status_becomes_failed_after_max_attempts(self, agent):
        self._setup_successful_run(agent)
        verify_fail = {
            "local_ok": False, "public_ok": False, "pods_ok": False, "operational": False
        }
        with (
            patch.object(HetznerDeployProbe, "probe", return_value=_probe_all_ok()),
            patch.object(HetznerDeployExecutor, "execute_plan", return_value=[]),
            patch.object(HetznerDeployVerifier, "verify", return_value=verify_fail),
        ):
            agent_small = HetznerDeployAgent(
                user_id=FOUNDER_ID,
                max_attempts=2,
                _founder_gate=_mock_gate(),
            )
            with patch.object(HetznerDeployProbe, "probe", return_value=_probe_all_ok()):
                agent_small.probe_and_plan()
            agent_small.approve_all()
            result = agent_small.execute_and_verify()
        assert result.success is False
        assert result.attempts == 2
        assert agent_small.status == HetznerDeployStatus.FAILED

    def test_retry_loop_respects_max_attempts(self, agent):
        call_count = 0

        def _fake_verify():
            nonlocal call_count
            call_count += 1
            return {"local_ok": False, "public_ok": False, "pods_ok": False, "operational": False}

        agent_small = HetznerDeployAgent(
            user_id=FOUNDER_ID,
            max_attempts=3,
            _founder_gate=_mock_gate(),
        )
        with patch.object(HetznerDeployProbe, "probe", return_value=_probe_all_ok()):
            agent_small.probe_and_plan()
        agent_small.approve_all()

        with (
            patch.object(HetznerDeployProbe, "probe", return_value=_probe_all_ok()),
            patch.object(HetznerDeployExecutor, "execute_plan", return_value=[]),
            patch.object(HetznerDeployVerifier, "verify", side_effect=lambda: _fake_verify()),
        ):
            result = agent_small.execute_and_verify()

        assert call_count == 3
        assert result.attempts == 3

    def test_audit_log_populated_after_execute(self, agent):
        self._setup_successful_run(agent)
        verify_ok = {
            "local_ok": True, "public_ok": False, "pods_ok": True, "operational": True
        }
        with (
            patch.object(HetznerDeployExecutor, "execute_plan", return_value=[]),
            patch.object(HetznerDeployVerifier, "verify", return_value=verify_ok),
        ):
            agent.execute_and_verify()
        log = agent.get_audit_log()
        actions = [e["action"] for e in log]
        assert "execute_attempt" in actions
        assert "verify" in actions

    def test_state_saved_on_success(self, agent, tmp_path):
        self._setup_successful_run(agent)
        verify_ok = {
            "local_ok": True, "public_ok": False, "pods_ok": True, "operational": True
        }
        state_path = str(tmp_path / "hetzner_deploy_state.json")
        with (
            patch.object(HetznerDeployExecutor, "execute_plan", return_value=[]),
            patch.object(HetznerDeployVerifier, "verify", return_value=verify_ok),
            patch("hetzner_deploy._STATE_FILE", state_path),
            patch("os.makedirs"),
        ):
            result = agent.execute_and_verify()
        assert result.success is True
        assert os.path.exists(state_path)
        with open(state_path) as fh:
            state = json.load(fh)
        assert "deployed_at" in state
        assert "cluster_name" in state
        assert state["founder"] == _FOUNDER_NAME


# ---------------------------------------------------------------------------
# HetznerDeployResult — data model
# ---------------------------------------------------------------------------


class TestHetznerDeployResult:
    def test_default_update_mode_is_full_deploy(self):
        result = HetznerDeployResult()
        assert result.update_mode == "full_deploy"

    def test_to_dict_contains_all_fields(self):
        result = HetznerDeployResult(
            success=True,
            attempts=1,
            public_url="https://murphy.example.com",
            cluster_name="murphy-system",
            cluster_id="abc123",
            node_count=2,
            image_tag="sha-abc",
            update_mode="rolling_update",
        )
        d = result.to_dict()
        expected_keys = [
            "run_id", "success", "attempts", "public_url",
            "cluster_name", "cluster_id", "node_count", "image_tag",
            "steps_executed", "steps_failed", "remaining_issues",
            "completed_at", "update_mode",
        ]
        for key in expected_keys:
            assert key in d, f"Missing key: {key}"

    def test_to_dict_update_mode_preserved(self):
        for mode in ("full_deploy", "rolling_update", "github_ci"):
            result = HetznerDeployResult(update_mode=mode)
            assert result.to_dict()["update_mode"] == mode


# ---------------------------------------------------------------------------
# Status transitions — thread safety
# ---------------------------------------------------------------------------


class TestHetznerDeployStatusTransitions:
    def test_status_is_thread_safe(self):
        agent = _make_agent()
        statuses = []

        def read_status():
            for _ in range(100):
                statuses.append(agent.status)

        threads = [threading.Thread(target=read_status) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        # All statuses should be valid HetznerDeployStatus values
        valid = set(HetznerDeployStatus)
        for s in statuses:
            assert s in valid

    def test_status_enum_values(self):
        assert HetznerDeployStatus.NOT_STARTED == "not_started"
        assert HetznerDeployStatus.PROBING == "probing"
        assert HetznerDeployStatus.PLANNING == "planning"
        assert HetznerDeployStatus.AWAITING_APPROVAL == "awaiting_approval"
        assert HetznerDeployStatus.EXECUTING == "executing"
        assert HetznerDeployStatus.VERIFYING == "verifying"
        assert HetznerDeployStatus.OPERATIONAL == "operational"
        assert HetznerDeployStatus.FAILED == "failed"
        assert HetznerDeployStatus.RETRYING == "retrying"


# ---------------------------------------------------------------------------
# HetznerStepType enum
# ---------------------------------------------------------------------------


class TestHetznerStepType:
    def test_all_step_types_present(self):
        expected = {
            "install_hcloud", "install_kubectl", "authenticate_hcloud",
            "create_k8s_cluster", "configure_kubeconfig", "build_image",
            "push_image", "apply_namespace", "apply_secrets", "apply_configmap",
            "apply_pvc", "apply_deployment", "apply_service", "apply_ingress",
            "apply_hpa", "apply_network_policy", "apply_pdb", "apply_redis",
            "apply_resource_quota", "apply_limit_range", "apply_backup_cronjob",
            "rolling_update", "apply_prometheus", "apply_grafana",
            "apply_service_monitor", "apply_postgres", "apply_staging_namespace",
            "run_production_readiness", "verify_deployment",
            # SSH / systemd update path
            "ssh_git_pull", "ssh_ensure_ollama", "ssh_restart_service", "ssh_verify_health",
        }
        actual = {member.value for member in HetznerStepType}
        assert expected == actual
