"""
Tests for cloudflare_deploy — FounderGate, CloudflareDeployProbe,
DeployPlanGenerator, DeployExecutor, DeployVerifier, CloudflareDeployAgent.

Security invariant validated throughout: only Corey Post (founder_admin) can
trigger a deployment.  All other callers receive AuthError immediately.

Design Label: TEST-CLOUDFLARE-DEPLOY-001
Owner: QA Team / Corey Post (founder)
"""
import json
import os
import threading
from unittest.mock import MagicMock, patch

import pytest


from cloudflare_deploy import (
    CloudflareDeployAgent,
    CloudflareDeployProbe,
    DeployExecutor,
    DeployPlanGenerator,
    DeployProbeReport,
    DeployResult,
    DeployStatus,
    DeployVerifier,
    FounderGate,
    _FOUNDER_NAME,
    _FOUNDER_ROLE,
)
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
    domain: str = "",
    backend_port: int = 8000,
) -> CloudflareDeployAgent:
    return CloudflareDeployAgent(
        user_id=FOUNDER_ID,
        domain=domain,
        backend_port=backend_port,
        _founder_gate=_mock_gate(allow=allow),
    )


def _probe_all_ok() -> DeployProbeReport:
    """A probe report that indicates everything is ready."""
    return DeployProbeReport(
        cloudflared_installed=True,
        cloudflared_version="2024.1.0",
        cf_credentials_found=True,
        cf_credentials_path=os.path.expanduser("~/.cloudflared/cert.pem"),
        tunnel_exists=True,
        tunnel_name="murphy-system",
        internet_available=True,
        local_backend_running=True,
        local_backend_port=8000,
        os_name="linux",
        python_ok=True,
        pip_ok=True,
        requirements_installed=True,
        dotenv_present=True,
        issues=[],
    )


def _probe_nothing_ready() -> DeployProbeReport:
    return DeployProbeReport(
        cloudflared_installed=False,
        cf_credentials_found=False,
        tunnel_exists=False,
        internet_available=False,
        local_backend_running=False,
        os_name="linux",
        python_ok=True,
        pip_ok=True,
        issues=[
            "cloudflared not installed",
            "no internet connection",
            "Murphy backend not running on localhost",
            "Cloudflare credentials not found",
            ".env file missing",
        ],
    )


@pytest.fixture
def agent():
    return _make_agent()


# ---------------------------------------------------------------------------
# FounderGate — security invariant
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
            email_validated=True, eula_accepted=True,
        )
        gate = FounderGate(gateway=gw)
        with pytest.raises(AuthError, match="not_founder"):
            gate.validate("u2")

    def test_blocks_wrong_name_via_gateway(self):
        gw = MagicMock(spec=SignupGateway)
        gw.get_profile.return_value = UserProfile(
            user_id="u3", name="Someone Else", role=_FOUNDER_ROLE,
            email_validated=True, eula_accepted=True,
        )
        gate = FounderGate(gateway=gw)
        with pytest.raises(AuthError, match="founder_name_mismatch"):
            gate.validate("u3")

    def test_blocks_unvalidated_email(self):
        gw = MagicMock(spec=SignupGateway)
        gw.get_profile.return_value = UserProfile(
            user_id="u4", name=_FOUNDER_NAME, role=_FOUNDER_ROLE,
            email_validated=False, eula_accepted=True,
        )
        gate = FounderGate(gateway=gw)
        with pytest.raises(AuthError, match="not_fully_onboarded"):
            gate.validate("u4")

    def test_blocks_unsigned_eula(self):
        gw = MagicMock(spec=SignupGateway)
        gw.get_profile.return_value = UserProfile(
            user_id="u5", name=_FOUNDER_NAME, role=_FOUNDER_ROLE,
            email_validated=True, eula_accepted=False,
        )
        gate = FounderGate(gateway=gw)
        with pytest.raises(AuthError, match="not_fully_onboarded"):
            gate.validate("u5")

    def test_blocks_nonexistent_user(self):
        gw = MagicMock(spec=SignupGateway)
        gw.get_profile.side_effect = Exception("not found")
        gate = FounderGate(gateway=gw)
        with pytest.raises(AuthError):
            gate.validate("nouser")

    def test_non_founder_cannot_instantiate_agent(self):
        with pytest.raises(AuthError):
            _make_agent(allow=False)


# ---------------------------------------------------------------------------
# CloudflareDeployAgent construction
# ---------------------------------------------------------------------------


class TestAgentConstruction:
    def test_founder_can_instantiate(self, agent):
        assert agent is not None
        assert agent.status == DeployStatus.NOT_STARTED

    def test_non_founder_raises_on_construction(self):
        with pytest.raises(AuthError):
            _make_agent(allow=False)

    def test_initial_plan_is_none(self, agent):
        assert agent.get_plan() is None

    def test_initial_probe_is_none(self, agent):
        assert agent.get_probe_report() is None


# ---------------------------------------------------------------------------
# probe_and_plan
# ---------------------------------------------------------------------------


class TestProbeAndPlan:
    def test_probe_and_plan_returns_setup_plan(self, agent):
        with patch.object(CloudflareDeployProbe, "probe", return_value=_probe_all_ok()):
            plan = agent.probe_and_plan()
        assert isinstance(plan, SetupPlan)

    def test_all_ok_probe_still_has_run_tunnel_step(self, agent):
        with patch.object(CloudflareDeployProbe, "probe", return_value=_probe_all_ok()):
            plan = agent.probe_and_plan()
        step_ids = [s.step_id for s in plan.steps]
        assert "deploy-08-run-tunnel" in step_ids

    def test_nothing_ready_probe_includes_all_steps(self, agent):
        with patch.object(CloudflareDeployProbe, "probe", return_value=_probe_nothing_ready()):
            plan = agent.probe_and_plan()
        step_ids = [s.step_id for s in plan.steps]
        assert "deploy-01-install-cloudflared" in step_ids
        assert "deploy-03-login-cloudflare" in step_ids
        assert "deploy-07-start-backend" in step_ids

    def test_all_ok_probe_skips_install_cloudflared(self, agent):
        with patch.object(CloudflareDeployProbe, "probe", return_value=_probe_all_ok()):
            plan = agent.probe_and_plan()
        step_ids = [s.step_id for s in plan.steps]
        assert "deploy-01-install-cloudflared" not in step_ids

    def test_status_becomes_awaiting_approval_after_plan(self, agent):
        with patch.object(CloudflareDeployProbe, "probe", return_value=_probe_all_ok()):
            agent.probe_and_plan()
        assert agent.status == DeployStatus.AWAITING_APPROVAL

    def test_plan_stored_on_agent(self, agent):
        with patch.object(CloudflareDeployProbe, "probe", return_value=_probe_all_ok()):
            plan = agent.probe_and_plan()
        assert agent.get_plan() is plan

    def test_probe_report_stored_on_agent(self, agent):
        report = _probe_all_ok()
        with patch.object(CloudflareDeployProbe, "probe", return_value=report):
            agent.probe_and_plan()
        assert agent.get_probe_report() is report


# ---------------------------------------------------------------------------
# HITL: approve / reject
# ---------------------------------------------------------------------------


class TestHITLApproval:
    def test_approve_all_marks_steps_approved(self, agent):
        with patch.object(CloudflareDeployProbe, "probe", return_value=_probe_all_ok()):
            plan = agent.probe_and_plan()
        agent.approve_all()
        assert all(s.status == StepStatus.APPROVED for s in plan.steps)

    def test_approve_step_by_id(self, agent):
        with patch.object(CloudflareDeployProbe, "probe", return_value=_probe_all_ok()):
            plan = agent.probe_and_plan()
        step_id = plan.steps[0].step_id
        result = agent.approve_step(step_id)
        assert result is True
        assert plan.steps[0].status == StepStatus.APPROVED

    def test_reject_step_by_id(self, agent):
        with patch.object(CloudflareDeployProbe, "probe", return_value=_probe_all_ok()):
            plan = agent.probe_and_plan()
        step_id = plan.steps[0].step_id
        result = agent.reject_step(step_id)
        assert result is True
        assert plan.steps[0].status == StepStatus.REJECTED

    def test_approve_all_before_plan_raises(self, agent):
        with pytest.raises(RuntimeError, match="probe_and_plan"):
            agent.approve_all()

    def test_hitl_log_populated_after_approval(self, agent):
        with patch.object(CloudflareDeployProbe, "probe", return_value=_probe_all_ok()):
            agent.probe_and_plan()
        agent.approve_all()
        log = agent.get_hitl_log()
        assert len(log) >= 1
        assert all("approved" in e for e in log)

    def test_each_step_has_liability_note(self, agent):
        with patch.object(CloudflareDeployProbe, "probe", return_value=_probe_all_ok()):
            plan = agent.probe_and_plan()
        for step in plan.steps:
            assert step.liability_note, f"Step {step.step_id} has empty liability_note"


# ---------------------------------------------------------------------------
# DeployPlanGenerator
# ---------------------------------------------------------------------------


class TestDeployPlanGenerator:
    def test_generates_dns_step_when_domain_provided(self):
        gen = DeployPlanGenerator(domain="example.com", subdomain="murphy")
        plan = gen.generate(_probe_all_ok())
        step_ids = [s.step_id for s in plan.steps]
        assert "deploy-06-route-dns" in step_ids

    def test_no_dns_step_without_domain(self):
        gen = DeployPlanGenerator(domain="", subdomain="murphy")
        plan = gen.generate(_probe_all_ok())
        step_ids = [s.step_id for s in plan.steps]
        assert "deploy-06-route-dns" not in step_ids

    def test_run_tunnel_always_included(self):
        gen = DeployPlanGenerator()
        plan = gen.generate(_probe_all_ok())
        step_ids = [s.step_id for s in plan.steps]
        assert "deploy-08-run-tunnel" in step_ids

    def test_verify_always_last(self):
        gen = DeployPlanGenerator()
        plan = gen.generate(_probe_all_ok())
        assert plan.steps[-1].step_id == "deploy-09-verify"

    def test_install_step_risk_is_medium(self):
        gen = DeployPlanGenerator()
        plan = gen.generate(_probe_nothing_ready())
        install = next(s for s in plan.steps if s.step_id == "deploy-01-install-cloudflared")
        assert install.risk_level == RiskLevel.MEDIUM

    def test_login_step_risk_is_high(self):
        gen = DeployPlanGenerator()
        plan = gen.generate(_probe_nothing_ready())
        login = next(s for s in plan.steps if s.step_id == "deploy-03-login-cloudflare")
        assert login.risk_level == RiskLevel.HIGH

    def test_tunnel_run_risk_is_high(self):
        gen = DeployPlanGenerator()
        plan = gen.generate(_probe_all_ok())
        run = next(s for s in plan.steps if s.step_id == "deploy-08-run-tunnel")
        assert run.risk_level == RiskLevel.HIGH

    def test_tunnel_config_written_as_file_op(self):
        gen = DeployPlanGenerator()
        plan = gen.generate(_probe_all_ok())
        cfg = next(s for s in plan.steps if s.step_id == "deploy-05-write-tunnel-config")
        assert cfg.file_op is not None
        assert cfg.file_op["type"] == "file"

    def test_config_content_has_tunnel_name(self):
        gen = DeployPlanGenerator(tunnel_name="my-tunnel")
        content = gen._tunnel_config_content()
        assert "my-tunnel" in content

    def test_config_content_has_ingress_section(self):
        gen = DeployPlanGenerator()
        content = gen._tunnel_config_content()
        assert "ingress:" in content

    def test_public_url_with_domain(self):
        gen = DeployPlanGenerator(subdomain="murphy", domain="example.com")
        assert gen._public_url() == "https://murphy.example.com/api/health"

    def test_public_url_without_domain_falls_back_to_localhost(self):
        gen = DeployPlanGenerator(domain="", backend_port=8000)
        url = gen._public_url()
        assert url == "" or "localhost" in url


# ---------------------------------------------------------------------------
# DeployVerifier
# ---------------------------------------------------------------------------


class TestDeployVerifier:
    def test_local_ok_when_backend_responds(self):
        verifier = DeployVerifier(local_port=8000)
        with patch("urllib.request.urlopen") as mock_open:
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_open.return_value = mock_resp
            result = verifier.verify()
        assert result["local_ok"] is True

    def test_local_fail_when_backend_down(self):
        verifier = DeployVerifier(local_port=19999)
        result = verifier.verify()
        assert result["local_ok"] is False

    def test_operational_requires_local_ok_when_no_domain(self):
        verifier = DeployVerifier(public_url="", local_port=19999)
        result = verifier.verify()
        assert result["operational"] is False

    def test_operational_requires_both_when_domain_set(self):
        verifier = DeployVerifier(
            public_url="https://murphy.example.com/api/health",
            local_port=19999,
        )
        result = verifier.verify()
        assert result["operational"] is False


# ---------------------------------------------------------------------------
# CloudflareDeployProbe
# ---------------------------------------------------------------------------


class TestCloudflareDeployProbe:
    def test_probe_returns_report(self):
        probe = CloudflareDeployProbe()
        report = probe.probe()
        assert isinstance(report, DeployProbeReport)
        assert report.os_name  # non-empty

    def test_no_cloudflared_marked_in_issues(self):
        probe = CloudflareDeployProbe()
        with patch("shutil.which", return_value=None):
            report = probe.probe()
        assert "cloudflared not installed" in report.issues

    def test_to_dict_has_ready_to_deploy_key(self):
        report = DeployProbeReport()
        d = report.to_dict()
        assert "ready_to_deploy" in d

    def test_all_ok_report_is_ready(self):
        assert _probe_all_ok().is_ready_to_deploy() is True

    def test_nothing_ready_is_not_ready(self):
        assert _probe_nothing_ready().is_ready_to_deploy() is False


# ---------------------------------------------------------------------------
# execute_and_verify — mocked for CI (no live server)
# ---------------------------------------------------------------------------


class TestExecuteAndVerify:
    def _make_operational_agent(self) -> CloudflareDeployAgent:
        agent = _make_agent()
        with patch.object(CloudflareDeployProbe, "probe", return_value=_probe_all_ok()):
            agent.probe_and_plan()
        agent.approve_all()
        return agent

    def test_success_when_verifier_says_operational(self):
        agent = self._make_operational_agent()
        with patch.object(DeployVerifier, "verify", return_value={
            "local_ok": True, "public_ok": False, "operational": True
        }):
            with patch.object(DeployExecutor, "execute_plan", return_value=[]):
                result = agent.execute_and_verify()
        assert result.success is True
        assert agent.status == DeployStatus.OPERATIONAL

    def test_failure_after_max_attempts(self):
        agent = self._make_operational_agent()
        agent.max_attempts = 2
        with patch.object(DeployVerifier, "verify", return_value={
            "local_ok": False, "public_ok": False, "operational": False
        }):
            with patch.object(DeployExecutor, "execute_plan", return_value=[]):
                with patch.object(CloudflareDeployProbe, "probe", return_value=_probe_all_ok()):
                    result = agent.execute_and_verify()
        assert result.success is False
        assert result.attempts == 2
        assert agent.status == DeployStatus.FAILED

    def test_result_has_run_id(self):
        agent = self._make_operational_agent()
        with patch.object(DeployVerifier, "verify", return_value={
            "local_ok": True, "public_ok": False, "operational": True
        }):
            with patch.object(DeployExecutor, "execute_plan", return_value=[]):
                result = agent.execute_and_verify()
        assert result.run_id

    def test_execute_before_plan_raises(self, agent):
        with pytest.raises(RuntimeError, match="probe_and_plan"):
            agent.execute_and_verify()


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------


class TestAuditLog:
    def test_probe_and_plan_adds_entries(self, agent):
        with patch.object(CloudflareDeployProbe, "probe", return_value=_probe_all_ok()):
            agent.probe_and_plan()
        log = agent.get_audit_log()
        actions = [e["action"] for e in log]
        assert "probe" in actions
        assert "plan_generated" in actions

    def test_approve_all_adds_entry(self, agent):
        with patch.object(CloudflareDeployProbe, "probe", return_value=_probe_all_ok()):
            agent.probe_and_plan()
        agent.approve_all()
        actions = [e["action"] for e in agent.get_audit_log()]
        assert "approve_all" in actions

    def test_audit_entries_have_timestamp_and_user_id(self, agent):
        with patch.object(CloudflareDeployProbe, "probe", return_value=_probe_all_ok()):
            agent.probe_and_plan()
        for entry in agent.get_audit_log():
            assert "timestamp" in entry
            assert "user_id" in entry

    def test_successful_deploy_adds_verify_entry(self):
        agent = _make_agent()
        with patch.object(CloudflareDeployProbe, "probe", return_value=_probe_all_ok()):
            agent.probe_and_plan()
        agent.approve_all()
        with patch.object(DeployVerifier, "verify", return_value={
            "local_ok": True, "public_ok": False, "operational": True
        }):
            with patch.object(DeployExecutor, "execute_plan", return_value=[]):
                agent.execute_and_verify()
        actions = [e["action"] for e in agent.get_audit_log()]
        assert "verify" in actions


# ---------------------------------------------------------------------------
# DeployResult model
# ---------------------------------------------------------------------------


class TestDeployResult:
    def test_to_dict_keys(self):
        r = DeployResult()
        d = r.to_dict()
        for k in ["run_id", "success", "attempts", "public_url",
                  "tunnel_name", "steps_executed", "steps_failed"]:
            assert k in d

    def test_initial_success_is_false(self):
        assert DeployResult().success is False


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------


class TestThreadSafety:
    def test_status_read_from_multiple_threads(self, agent):
        statuses = []

        def read_status():
            statuses.append(agent.status)

        threads = [threading.Thread(target=read_status) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(statuses) == 20
        assert all(s == DeployStatus.NOT_STARTED for s in statuses)
