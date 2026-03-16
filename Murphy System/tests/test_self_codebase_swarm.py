"""
Tests for Self-Codebase Swarm (SCS-001).

Covers:
  - propose_change / execute_change HITL gating
  - build_package in autonomous and document modes
  - parse_rfp BMS document parsing
  - ingest_cutsheet / generate_drawings / generate_device_code /
    verify_commissioning_from_cutsheets (cut sheet integration)
  - get_recommendations / swarm_on_project / list_agents
  - Input validation, thread safety, audit log

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""
from __future__ import annotations

import os
import threading

import pytest


from self_codebase_swarm import (
    AgentRole,
    BuildMode,
    DeliverablePackage,
    ProposalStatus,
    RFPParseResult,
    SelfCodebaseSwarm,
    SwarmExecutionResult,
    SwarmProposal,
    SwarmSession,
    _detect_compliance,
    _detect_protocols,
    _detect_systems,
    _generate_point_schedule,
    _generate_sequences,
)


# ---------------------------------------------------------------------------
# Stub HITL controller
# ---------------------------------------------------------------------------

class _PermissiveHITL:
    """Always returns autonomous=True (disarmed HITL for testing)."""
    def evaluate_autonomy(self, task_type, confidence, risk_level, policy_id=None):
        return {
            "autonomous": True,
            "reason": "test_permissive",
            "requires_hitl": False,
            "confidence": confidence,
            "risk_level": risk_level,
        }
    def record_action(self, **kwargs):
        pass


class _BlockingHITL:
    """Always requires HITL (armed for testing)."""
    def evaluate_autonomy(self, task_type, confidence, risk_level, policy_id=None):
        return {
            "autonomous": False,
            "reason": "hitl_required",
            "requires_hitl": True,
            "confidence": confidence,
            "risk_level": risk_level,
        }
    def record_action(self, **kwargs):
        pass


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def swarm_permissive():
    return SelfCodebaseSwarm(hitl_controller=_PermissiveHITL())


@pytest.fixture
def swarm_blocking():
    return SelfCodebaseSwarm(hitl_controller=_BlockingHITL())


# ---------------------------------------------------------------------------
# propose_change
# ---------------------------------------------------------------------------

class TestProposeChange:
    def test_returns_proposal(self, swarm_permissive):
        p = swarm_permissive.propose_change("Add logging to the auth module")
        assert isinstance(p, SwarmProposal)
        assert p.proposal_id != ""

    def test_confidence_score_populated(self, swarm_permissive):
        p = swarm_permissive.propose_change("Refactor billing engine")
        assert 0.0 <= p.confidence_score <= 1.0

    def test_agent_votes_cast(self, swarm_permissive):
        p = swarm_permissive.propose_change("Add tests for onboarding")
        assert len(p.agent_votes) >= 3

    def test_hitl_hold_when_blocking(self, swarm_blocking):
        p = swarm_blocking.propose_change("Dangerous refactor")
        assert p.status == ProposalStatus.HITL_HOLD

    def test_approved_when_permissive(self, swarm_permissive):
        p = swarm_permissive.propose_change("Safe change")
        assert p.status in (ProposalStatus.APPROVED, ProposalStatus.HITL_HOLD)

    def test_stored_and_retrievable(self, swarm_permissive):
        p = swarm_permissive.propose_change("Something")
        retrieved = swarm_permissive.get_proposal(p.proposal_id)
        assert retrieved is not None
        assert retrieved.proposal_id == p.proposal_id

    def test_invalid_id_retrieve_returns_none(self, swarm_permissive):
        assert swarm_permissive.get_proposal("nonexistentid123") is None

    def test_to_dict(self, swarm_permissive):
        p = swarm_permissive.propose_change("x")
        d = p.to_dict()
        assert "proposal_id" in d
        assert "confidence_score" in d
        assert "status" in d


# ---------------------------------------------------------------------------
# execute_change
# ---------------------------------------------------------------------------

class TestExecuteChange:
    def test_blocked_when_hitl_required(self, swarm_blocking):
        p = swarm_blocking.propose_change("Some change")
        result = swarm_blocking.execute_change(p.proposal_id)
        assert isinstance(result, SwarmExecutionResult)
        assert result.success is False
        assert result.hitl_required is True

    def test_succeeds_when_permissive(self, swarm_permissive):
        p = swarm_permissive.propose_change("Safe change")
        # Force to APPROVED so execution gate doesn't block
        p.status = ProposalStatus.APPROVED
        result = swarm_permissive.execute_change(p.proposal_id)
        assert result.success is True

    def test_unknown_proposal_returns_error(self, swarm_permissive):
        result = swarm_permissive.execute_change("unknownidhere000")
        assert result.success is False
        assert result.errors

    def test_to_dict(self, swarm_permissive):
        p = swarm_permissive.propose_change("x")
        r = swarm_permissive.execute_change(p.proposal_id)
        d = r.to_dict()
        assert "execution_id" in d
        assert "success" in d
        assert "hitl_required" in d


# ---------------------------------------------------------------------------
# parse_rfp
# ---------------------------------------------------------------------------

RFP_TEXT = """
PROJECT NAME: Northgate Office Complex BMS Upgrade
LOCATION: Seattle, WA
OWNER: Northgate Properties LLC
BUILDING TYPE: Commercial Office
FLOORS: 5

SCOPE OF WORK
The contractor shall furnish and install a complete BMS for HVAC and lighting systems.

SYSTEMS
This project includes HVAC, VAV control, lighting control, energy metering, and
fire safety integration.

PROTOCOLS
All controllers shall be native BACnet/IP with BACnet MS/TP field buses.
Modbus RTU shall be used for energy meters.

STANDARDS
The system shall comply with ASHRAE 135, ASHRAE 90.1, NFPA 72.

QUALIFICATIONS
The controls engineer must hold a PE stamp.
A certified commissioning agent (CxA) is required for functional testing.
"""


class TestParseRFP:
    def test_returns_rfp_result(self, swarm_permissive):
        result = swarm_permissive.parse_rfp(RFP_TEXT)
        assert isinstance(result, RFPParseResult)

    def test_detects_systems(self, swarm_permissive):
        result = swarm_permissive.parse_rfp(RFP_TEXT)
        assert "hvac" in result.systems_required

    def test_detects_protocols(self, swarm_permissive):
        result = swarm_permissive.parse_rfp(RFP_TEXT)
        assert any("BACnet" in p for p in result.protocols_required)

    def test_detects_compliance(self, swarm_permissive):
        result = swarm_permissive.parse_rfp(RFP_TEXT)
        assert len(result.compliance_standards) >= 1

    def test_detects_hitl_disciplines(self, swarm_permissive):
        result = swarm_permissive.parse_rfp(RFP_TEXT)
        assert len(result.hitl_disciplines) >= 1

    def test_generates_point_schedule(self, swarm_permissive):
        result = swarm_permissive.parse_rfp(RFP_TEXT)
        assert len(result.point_schedule) > 0

    def test_generates_sequences(self, swarm_permissive):
        result = swarm_permissive.parse_rfp(RFP_TEXT)
        assert len(result.sequences) > 0

    def test_confidence_positive(self, swarm_permissive):
        result = swarm_permissive.parse_rfp(RFP_TEXT)
        assert result.parse_confidence > 0.0

    def test_bad_input_raises(self, swarm_permissive):
        with pytest.raises(ValueError):
            swarm_permissive.parse_rfp(None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# build_package — autonomous mode
# ---------------------------------------------------------------------------

class TestBuildPackageAutonomous:
    def test_returns_package(self, swarm_permissive):
        pkg = swarm_permissive.build_package(
            mode=BuildMode.AUTONOMOUS,
            project_name="Test Office Building",
            systems=["hvac", "lighting"],
            floors=3,
        )
        assert isinstance(pkg, DeliverablePackage)
        assert pkg.package_id != ""

    def test_sections_populated(self, swarm_permissive):
        pkg = swarm_permissive.build_package(
            mode=BuildMode.AUTONOMOUS,
            systems=["hvac"],
        )
        assert "03_scope_of_work" in pkg.sections
        assert "06_point_schedule" in pkg.sections
        assert "07_alarm_matrix" in pkg.sections

    def test_files_generated(self, swarm_permissive):
        pkg = swarm_permissive.build_package(mode=BuildMode.AUTONOMOUS)
        assert "COVER_SHEET.md" in pkg.files
        assert "POINT_SCHEDULE.json" in pkg.files
        assert "SEQUENCE_OF_OPERATIONS.md" in pkg.files
        assert "COMMISSIONING_CHECKLIST.md" in pkg.files

    def test_compliance_matrix_populated(self, swarm_permissive):
        pkg = swarm_permissive.build_package(mode=BuildMode.AUTONOMOUS)
        assert len(pkg.compliance_matrix) > 0

    def test_hitl_sign_offs_required(self, swarm_permissive):
        pkg = swarm_permissive.build_package(mode=BuildMode.AUTONOMOUS)
        assert len(pkg.hitl_sign_offs) >= 1

    def test_to_dict(self, swarm_permissive):
        pkg = swarm_permissive.build_package(mode=BuildMode.AUTONOMOUS)
        d = pkg.to_dict()
        assert "package_id" in d
        assert "sections" in d
        assert "compliance_matrix" in d

    def test_stored_and_retrievable(self, swarm_permissive):
        pkg = swarm_permissive.build_package(mode=BuildMode.AUTONOMOUS)
        retrieved = swarm_permissive.get_package(pkg.package_id)
        assert retrieved is not None


class TestBuildPackageDocumentMode:
    def test_builds_from_rfp(self, swarm_permissive):
        rfp = swarm_permissive.parse_rfp(RFP_TEXT)
        pkg = swarm_permissive.build_package(
            mode=BuildMode.DOCUMENT,
            rfp_result=rfp,
            project_name="Northgate BMS",
        )
        assert isinstance(pkg, DeliverablePackage)
        assert pkg.project_name == "Northgate BMS"

    def test_document_mode_requires_rfp(self, swarm_permissive):
        with pytest.raises(ValueError):
            swarm_permissive.build_package(mode=BuildMode.DOCUMENT)


# ---------------------------------------------------------------------------
# Cut sheet integration
# ---------------------------------------------------------------------------

DDC_TEXT = """
Manufacturer: Siemens
Model Number: PXC100-E.D
Product Name: Modular Building Controller
Supply Voltage: 24 VAC
AI: 8
AO: 4
BI: 8
BO: 4
Protocols: BACnet/IP, BACnet MS/TP
BACnet Device Profile: B-AAC
Certifications: BTL, UL 916
"""

SENSOR_TEXT = """
Manufacturer: Vaisala
Model Number: HMD60Y
Product Name: Humidity and Temperature Transmitter
Range: 0°F to 160°F
Accuracy: ±0.3°F
Output: 4-20mA
Units: °F
Supply Voltage: 24 VAC
Certifications: CE
"""


class TestCutSheetIntegration:
    def test_ingest_cutsheet_returns_spec(self, swarm_permissive):
        spec = swarm_permissive.ingest_cutsheet(DDC_TEXT, "Siemens", "PXC100-E.D")
        assert spec.manufacturer == "Siemens"
        assert spec.model_number == "PXC100-E.D"

    def test_list_cutsheets_after_ingest(self, swarm_permissive):
        swarm_permissive.ingest_cutsheet(DDC_TEXT)
        swarm_permissive.ingest_cutsheet(SENSOR_TEXT)
        listing = swarm_permissive.list_cutsheets()
        assert len(listing) == 2

    def test_generate_drawings_returns_files(self, swarm_permissive):
        spec1 = swarm_permissive.ingest_cutsheet(DDC_TEXT)
        spec2 = swarm_permissive.ingest_cutsheet(SENSOR_TEXT)
        result = swarm_permissive.generate_drawings_from_cutsheets(
            [spec1.cutsheet_id, spec2.cutsheet_id],
            project_name="Swarm Test",
        )
        assert "wiring_diagram" in result
        assert "control_diagram" in result
        assert "WIRING_DIAGRAM.md" in result["files"]
        assert "WIRE_LIST.csv" in result["files"]
        assert "CONTROL_DIAGRAM.md" in result["files"]

    def test_generate_device_code_returns_configs(self, swarm_permissive):
        spec = swarm_permissive.ingest_cutsheet(DDC_TEXT)
        result = swarm_permissive.generate_device_code_from_cutsheets(
            [spec.cutsheet_id], project_name="CODE-TEST"
        )
        assert "device_configs" in result
        assert "json_export" in result
        assert "program_stubs" in result

    def test_verify_commissioning_returns_report(self, swarm_permissive):
        spec = swarm_permissive.ingest_cutsheet(SENSOR_TEXT)
        result = swarm_permissive.verify_commissioning_from_cutsheets(
            [spec.cutsheet_id], project_name="CX-TEST"
        )
        assert "verification_result" in result
        assert "report_markdown" in result
        assert "hitl_eval" in result

    def test_verify_commissioning_hitl_blocked_on_failure(self, swarm_blocking):
        spec = swarm_blocking.ingest_cutsheet(SENSOR_TEXT)
        result = swarm_blocking.verify_commissioning_from_cutsheets(
            [spec.cutsheet_id]
        )
        assert result["acceptance_blocked"] is True

    def test_drawings_invalid_ids(self, swarm_permissive):
        result = swarm_permissive.generate_drawings_from_cutsheets(
            ["nonexistent-id"]
        )
        assert "error" in result

    def test_get_cutsheet_by_id(self, swarm_permissive):
        spec = swarm_permissive.ingest_cutsheet(DDC_TEXT)
        retrieved = swarm_permissive.get_cutsheet(spec.cutsheet_id)
        assert retrieved is not None
        assert retrieved.cutsheet_id == spec.cutsheet_id


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------

class TestGetRecommendations:
    def test_returns_list(self, swarm_permissive):
        recs = swarm_permissive.get_recommendations()
        assert isinstance(recs, list)

    def test_hitl_recommendation_present(self, swarm_permissive):
        recs = swarm_permissive.get_recommendations()
        titles = " ".join(r.title for r in recs).lower()
        assert "hitl" in titles or "human" in titles


# ---------------------------------------------------------------------------
# swarm_on_project
# ---------------------------------------------------------------------------

class TestSwarmOnProject:
    def test_returns_session(self, swarm_permissive):
        session = swarm_permissive.swarm_on_project({"repo": "https://github.com/test/repo"})
        assert isinstance(session, SwarmSession)
        assert session.session_id != ""

    def test_bad_config_raises(self, swarm_permissive):
        with pytest.raises(ValueError):
            swarm_permissive.swarm_on_project("not a dict")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Agents and audit log
# ---------------------------------------------------------------------------

class TestAgents:
    def test_lists_agents(self, swarm_permissive):
        agents = swarm_permissive.list_agents()
        assert len(agents) >= 5
        roles = {a["role"] for a in agents}
        assert "architect" in roles
        assert "code_gen" in roles
        assert "bms_domain" in roles


class TestAuditLog:
    def test_audit_log_grows(self, swarm_permissive):
        swarm_permissive.propose_change("test change")
        log = swarm_permissive.get_audit_log()
        assert len(log) >= 1

    def test_audit_entries_have_action(self, swarm_permissive):
        swarm_permissive.propose_change("test")
        log = swarm_permissive.get_audit_log()
        assert all("action" in e for e in log)


# ---------------------------------------------------------------------------
# BMS domain helpers
# ---------------------------------------------------------------------------

class TestBMSHelpers:
    def test_detect_systems_hvac(self):
        assert "hvac" in _detect_systems("HVAC and air handling unit control")

    def test_detect_systems_lighting(self):
        assert "lighting" in _detect_systems("lighting dimming control")

    def test_detect_protocols_bacnet(self):
        assert "BACnet" in _detect_protocols("BACnet MS/TP and BACnet/IP")

    def test_detect_compliance_ashrae(self):
        standards = _detect_compliance("ASHRAE 135 BACnet standard compliance required")
        assert "ASHRAE_135" in standards

    def test_generate_point_schedule_hvac(self):
        pts = _generate_point_schedule(["hvac"], floors=2)
        assert len(pts) > 0
        types = {p.point_type for p in pts}
        assert len(types) > 1

    def test_generate_sequences_hvac(self):
        seqs = _generate_sequences(["hvac"])
        assert len(seqs) >= 1
        assert "hvac" in seqs[0].system

    def test_generate_sequences_lighting(self):
        seqs = _generate_sequences(["lighting"])
        lighting_seqs = [s for s in seqs if s.system == "lighting"]
        assert len(lighting_seqs) >= 1


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_propose(self, swarm_permissive):
        errors = []
        proposals = []

        def propose():
            try:
                p = swarm_permissive.propose_change("concurrent change")
                proposals.append(p.proposal_id)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=propose) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []
        assert len(proposals) == 10

    def test_concurrent_build_package(self, swarm_permissive):
        errors = []

        def build():
            try:
                swarm_permissive.build_package(
                    mode=BuildMode.AUTONOMOUS,
                    systems=["hvac"],
                )
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=build) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []
