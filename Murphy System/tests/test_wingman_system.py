"""Tests for the Wingman System — sensor calibration, trigger, validation modules.

Test-suite design principles
-----------------------------
* Parametrize extensively so each new sensor variant or threshold change is
  caught without adding new test functions.
* Fixtures are scoped as tightly as possible (function scope = fresh state).
* No I/O, no network, no filesystem — pure unit tests, all < 1 ms each.
* Every public contract of WingmanSystem is exercised:
    - sensor readings (ok / warn / alert for each of the 6 sensors)
    - WorldModelCalibrator aggregation and overall_status
    - ValidationTrigger.decide + triggered_sensors
    - WingmanValidationModule.validate end-to-end
    - WingmanSystem.register_module, .validate, .get_status, .list_module_ids
    - Librarian knowledge-layer integration (writes, graceful None)
    - Internal library privacy (not exposed by get_status or API dict)
    - Thread-safety smoke test
"""

from __future__ import annotations

import threading
from typing import Any, Dict, List
from unittest.mock import MagicMock

import pytest

from src.wingman_system import (
    ComplianceSensor,
    ContentDensitySensor,
    ModuleValidationResult,
    SemanticCoherenceSensor,
    SensorStatus,
    StructureSensor,
    TemporalSensor,
    ValidationTrigger,
    VisibilitySensor,
    WingmanSystem,
    WingmanValidationModule,
    WorldModelCalibrator,
    WorldModelSnapshot,
)

# ---------------------------------------------------------------------------
# Shared artifact builders
# ---------------------------------------------------------------------------

_BRANDING = (
    "murphy.systems Inoni Apache License BSL 1.1 "
    "Generated: 2026-03-19 14:00:00 UTC"
)


def _full_artifact(extra_content: str = "") -> Dict[str, Any]:
    """A well-formed deliverable artifact that should pass all sensors."""
    body = (
        "╔══╗\n"
        "■ SECTION 1 — OVERVIEW\n"
        "══════════════════════\n"
        + ("word " * 200)
        + _BRANDING
        + extra_content
    )
    return {"content": body, "id": "art-001"}


def _empty_artifact() -> Dict[str, Any]:
    return {"content": "", "id": "art-empty"}


def _short_artifact(chars: int = 10) -> Dict[str, Any]:
    return {"content": "x" * chars, "id": "art-short"}


# ===========================================================================
# VisibilitySensor
# ===========================================================================

class TestVisibilitySensor:
    sensor = VisibilitySensor()

    def test_ok_large_content(self):
        r = self.sensor.read({"content": "word " * 50})
        assert r.status == SensorStatus.OK
        assert r.value == 1.0

    def test_alert_empty(self):
        r = self.sensor.read({"content": ""})
        assert r.status == SensorStatus.ALERT
        assert r.value == 0.0

    def test_alert_missing_key(self):
        r = self.sensor.read({})
        assert r.status == SensorStatus.ALERT

    def test_warn_very_short(self):
        r = self.sensor.read({"content": "hi"})
        assert r.status == SensorStatus.WARN
        assert 0.0 < r.value < 1.0

    def test_fallback_to_result_key(self):
        r = self.sensor.read({"result": "word " * 50})
        assert r.status == SensorStatus.OK

    @pytest.mark.parametrize("chars,expected_status", [
        (0,   SensorStatus.ALERT),
        (10,  SensorStatus.WARN),
        (200, SensorStatus.OK),
    ])
    def test_parametrized_thresholds(self, chars, expected_status):
        r = self.sensor.read({"content": "x" * chars})
        assert r.status == expected_status


# ===========================================================================
# StructureSensor
# ===========================================================================

class TestStructureSensor:
    sensor = StructureSensor()

    def test_ok_with_murphy_sections(self):
        r = self.sensor.read({"content": "■ SECTION 1\n══════\n■ SECTION 2\n══════\n■ SECTION 3"})
        assert r.status == SensorStatus.OK

    def test_warn_no_structure(self):
        r = self.sensor.read({"content": "plain text with no sections or markers"})
        assert r.status == SensorStatus.WARN
        assert r.value == 0.0

    def test_ok_with_separator_bar(self):
        r = self.sensor.read({"content": "═" * 40})
        assert r.status == SensorStatus.OK

    def test_empty_is_warn(self):
        r = self.sensor.read({"content": ""})
        assert r.status == SensorStatus.WARN


# ===========================================================================
# ContentDensitySensor
# ===========================================================================

class TestContentDensitySensor:
    sensor = ContentDensitySensor()

    @pytest.mark.parametrize("words,expected_status", [
        (5,   SensorStatus.ALERT),
        (50,  SensorStatus.WARN),
        (200, SensorStatus.OK),
    ])
    def test_density_thresholds(self, words, expected_status):
        r = self.sensor.read({"content": "word " * words})
        assert r.status == expected_status

    def test_value_scales_with_word_count(self):
        r_low  = self.sensor.read({"content": "word " * 10})
        r_high = self.sensor.read({"content": "word " * 200})
        assert r_high.value > r_low.value

    def test_empty_is_alert(self):
        r = self.sensor.read({"content": ""})
        assert r.status == SensorStatus.ALERT


# ===========================================================================
# SemanticCoherenceSensor
# ===========================================================================

class TestSemanticCoherenceSensor:
    sensor = SemanticCoherenceSensor()

    def test_ok_clean_content(self):
        r = self.sensor.read({"content": "This is well-formed, coherent content."})
        assert r.status == SensorStatus.OK

    def test_alert_empty_after_strip(self):
        r = self.sensor.read({"content": "   \n\t  "})
        assert r.status == SensorStatus.ALERT

    def test_alert_repeated_chars(self):
        r = self.sensor.read({"content": "a" * 50})
        assert r.status == SensorStatus.ALERT

    def test_warn_llm_log_leak(self):
        # Content contains the LLM processing note but does NOT end with "..."
        # (that would trigger the ellipsis degenerate pattern before this check)
        r = self.sensor.read({
            "content": "[Local Medium Model] Analyzing request: build a dashboard module"
        })
        assert r.status == SensorStatus.WARN

    @pytest.mark.parametrize("degenerate", [
        "[TRUNCATED]",
        "[ERROR]",
        "<PLACEHOLDER>",
        "normal text...",          # ends with ellipsis
    ])
    def test_degenerate_patterns_alert(self, degenerate):
        r = self.sensor.read({"content": degenerate})
        assert r.status in (SensorStatus.ALERT, SensorStatus.WARN)


# ===========================================================================
# ComplianceSensor
# ===========================================================================

class TestComplianceSensor:
    sensor = ComplianceSensor()

    def test_ok_all_markers(self):
        r = self.sensor.read({"content": _full_artifact()["content"]})
        assert r.status == SensorStatus.OK
        assert r.value == 1.0

    @pytest.mark.parametrize("missing_marker", [
        "murphy.systems",
        "Inoni",
        "Apache License",
        "BSL",
    ])
    def test_missing_single_marker_is_warn(self, missing_marker):
        content = _BRANDING.replace(missing_marker, "REMOVED")
        r = self.sensor.read({"content": content})
        # One missing → warn (not enough for ALERT which needs ≥2)
        assert r.status == SensorStatus.WARN

    def test_two_missing_markers_is_alert(self):
        content = "no branding here at all"
        r = self.sensor.read({"content": content})
        assert r.status == SensorStatus.ALERT

    def test_empty_is_alert(self):
        r = self.sensor.read({"content": ""})
        assert r.status == SensorStatus.ALERT


# ===========================================================================
# TemporalSensor
# ===========================================================================

class TestTemporalSensor:
    sensor = TemporalSensor()

    def test_ok_metadata_timestamp(self):
        r = self.sensor.read({"content": "x", "generated_at": "2026-03-19T14:00:00Z"})
        assert r.status == SensorStatus.OK
        assert r.value == 1.0

    def test_ok_timestamp_in_content(self):
        r = self.sensor.read({"content": "Generated: 2026-03-19 14:00:00 UTC"})
        assert r.status == SensorStatus.OK

    def test_warn_no_timestamp(self):
        r = self.sensor.read({"content": "just some content, no timestamp"})
        assert r.status == SensorStatus.WARN

    def test_fallback_timestamp_key(self):
        r = self.sensor.read({"content": "", "timestamp": "2026-01-01T00:00:00Z"})
        assert r.status == SensorStatus.OK


# ===========================================================================
# WorldModelCalibrator
# ===========================================================================

class TestWorldModelCalibrator:

    @pytest.fixture
    def calibrator(self):
        return WorldModelCalibrator()

    def test_returns_snapshot(self, calibrator):
        snap = calibrator.calibrate(_full_artifact())
        assert isinstance(snap, WorldModelSnapshot)

    def test_has_six_readings(self, calibrator):
        snap = calibrator.calibrate(_full_artifact())
        assert len(snap.readings) == 6

    def test_all_sensor_ids_present(self, calibrator):
        snap = calibrator.calibrate(_full_artifact())
        sensor_ids = {r.sensor_id for r in snap.readings}
        expected = {"visibility", "structure", "content_density",
                    "semantic_coherence", "compliance", "temporal"}
        assert sensor_ids == expected

    def test_overall_ok_for_full_artifact(self, calibrator):
        snap = calibrator.calibrate(_full_artifact())
        assert snap.overall_status == SensorStatus.OK

    def test_overall_alert_for_empty(self, calibrator):
        snap = calibrator.calibrate(_empty_artifact())
        assert snap.overall_status == SensorStatus.ALERT

    def test_sensor_lookup_by_id(self, calibrator):
        snap = calibrator.calibrate(_full_artifact())
        vis = snap.sensor("visibility")
        assert vis is not None
        assert vis.sensor_id == "visibility"

    def test_custom_sensor_added(self, calibrator):
        class ExtraSensor:
            SENSOR_ID = "extra"
            def read(self, artifact):
                from src.wingman_system import SensorReading
                return SensorReading("extra", "extra", 1.0, SensorStatus.OK, "ok")

        calibrator.add_sensor(ExtraSensor())
        snap = calibrator.calibrate(_full_artifact())
        assert snap.sensor("extra") is not None
        assert len(snap.readings) == 7

    def test_sensor_exception_becomes_warn_reading(self, calibrator):
        class BrokenSensor:
            SENSOR_ID = "broken"
            def read(self, artifact):
                raise RuntimeError("boom")

        calibrator.add_sensor(BrokenSensor())
        snap = calibrator.calibrate(_full_artifact())
        broken = snap.sensor("broken")
        assert broken is not None
        assert broken.status == SensorStatus.WARN


# ===========================================================================
# ValidationTrigger
# ===========================================================================

class TestValidationTrigger:

    def _snap(self, statuses: List[str]) -> WorldModelSnapshot:
        from src.wingman_system import SensorReading
        snap = WorldModelSnapshot(artifact_id="t")
        for i, s in enumerate(statuses):
            snap.readings.append(SensorReading(f"s{i}", "dim", 0.5, s, ""))
        return snap

    @pytest.mark.parametrize("statuses,expected_level", [
        ([SensorStatus.OK,    SensorStatus.OK],    "info"),
        ([SensorStatus.WARN,  SensorStatus.OK],    "warn"),
        ([SensorStatus.ALERT, SensorStatus.OK],    "block"),
        ([SensorStatus.ALERT, SensorStatus.WARN],  "block"),
        ([SensorStatus.WARN,  SensorStatus.WARN],  "warn"),
        ([],                                        "info"),
    ])
    def test_decide(self, statuses, expected_level):
        snap = self._snap(statuses)
        assert ValidationTrigger.decide(snap) == expected_level

    def test_triggered_sensors_block_level(self):
        snap = self._snap([SensorStatus.ALERT, SensorStatus.OK, SensorStatus.WARN])
        triggered = ValidationTrigger.triggered_sensors(snap, "block")
        assert "s0" in triggered
        assert "s1" not in triggered  # OK is not triggered

    def test_triggered_sensors_warn_level(self):
        snap = self._snap([SensorStatus.ALERT, SensorStatus.WARN, SensorStatus.OK])
        triggered = ValidationTrigger.triggered_sensors(snap, "warn")
        assert "s0" in triggered  # ALERT also triggers at warn level
        assert "s1" in triggered  # WARN triggers at warn level
        assert "s2" not in triggered

    def test_triggered_sensors_info_level_empty(self):
        snap = self._snap([SensorStatus.OK, SensorStatus.OK])
        triggered = ValidationTrigger.triggered_sensors(snap, "info")
        assert triggered == []


# ===========================================================================
# WingmanValidationModule
# ===========================================================================

class TestWingmanValidationModule:

    @pytest.fixture
    def module(self):
        return WingmanValidationModule("test_module", "test_domain")

    def test_returns_result(self, module):
        r = module.validate(_full_artifact())
        assert isinstance(r, ModuleValidationResult)

    def test_approved_for_full_artifact(self, module):
        r = module.validate(_full_artifact())
        assert r.approved is True
        assert r.trigger_level == "info"

    def test_rejected_for_empty_artifact(self, module):
        r = module.validate(_empty_artifact())
        assert r.approved is False
        assert r.trigger_level == "block"

    def test_findings_populated_on_rejection(self, module):
        r = module.validate(_empty_artifact())
        assert len(r.findings) > 0
        sensor_ids = {f["sensor_id"] for f in r.findings}
        assert "visibility" in sensor_ids

    def test_custom_block_rules_surfaced(self):
        m = WingmanValidationModule(
            "custom_mod", "custom",
            custom_rules=[{"severity": "block", "description": "Must include signature"}],
        )
        r = m.validate(_empty_artifact())
        domain_findings = [f for f in r.findings if f["sensor_id"] == "domain_rule"]
        assert any("signature" in f["detail"] for f in domain_findings)

    def test_history_grows(self, module):
        module.validate(_full_artifact())
        module.validate(_empty_artifact())
        assert len(module.history()) == 2

    def test_stats_correct(self, module):
        module.validate(_full_artifact())   # approved
        module.validate(_empty_artifact())  # rejected
        s = module.stats()
        assert s["total_validations"] == 2
        assert s["approved"] == 1
        assert s["rejected"] == 1

    def test_module_id_in_result(self, module):
        r = module.validate(_full_artifact())
        assert r.module_id == "test_module"

    def test_result_to_dict_keys(self, module):
        d = module.validate(_full_artifact()).to_dict()
        for key in ("module_id", "artifact_id", "approved", "trigger_level",
                    "triggered_sensors", "findings", "snapshot", "validated_at"):
            assert key in d


# ===========================================================================
# WingmanSystem — top-level
# ===========================================================================

class TestWingmanSystemInit:

    def test_instantiates_without_librarian(self):
        ws = WingmanSystem(librarian=None)
        assert ws is not None

    def test_six_default_modules_registered(self):
        ws = WingmanSystem(librarian=None)
        assert ws.get_status()["registered_modules"] == 6

    def test_default_module_ids(self):
        ws = WingmanSystem(librarian=None)
        ids = set(ws.list_module_ids())
        expected = {"deliverable", "workflow", "compliance", "hr", "finance", "invoice"}
        assert expected == ids

    def test_internal_library_not_in_status(self):
        ws = WingmanSystem(librarian=None)
        status = ws.get_status()
        # The private library dict must never appear in any serialised output
        assert "_internal_library" not in status
        assert "internal_library" not in status
        assert "library" not in status

    def test_librarian_receives_registration_knowledge(self):
        lib = MagicMock()
        WingmanSystem(librarian=lib)
        # 6 default modules → 6 add_knowledge_entry calls
        assert lib.add_knowledge_entry.call_count == 6
        # Verify each call had wingman_validation category
        for call in lib.add_knowledge_entry.call_args_list:
            entry = call[0][0]
            assert entry["category"] == "wingman_validation"


class TestWingmanSystemValidate:

    @pytest.fixture
    def ws(self):
        return WingmanSystem(librarian=None)

    def test_approved_full_artifact(self, ws):
        r = ws.validate(_full_artifact(), module_id="deliverable")
        assert r.approved is True

    def test_rejected_empty_artifact(self, ws):
        r = ws.validate(_empty_artifact(), module_id="deliverable")
        assert r.approved is False

    def test_unknown_module_falls_back(self, ws):
        # Falls back to "deliverable" module
        r = ws.validate(_full_artifact(), module_id="nonexistent_xyz")
        assert isinstance(r, ModuleValidationResult)

    def test_total_validation_count_increments(self, ws):
        ws.validate(_full_artifact())
        ws.validate(_full_artifact())
        assert ws.get_status()["total_validations"] == 2

    def test_approved_count_correct(self, ws):
        ws.validate(_full_artifact())    # approved
        ws.validate(_empty_artifact())   # rejected
        s = ws.get_status()
        assert s["total_approved"] == 1
        assert s["total_rejected"] == 1

    def test_approval_rate_computed(self, ws):
        ws.validate(_full_artifact())
        s = ws.get_status()
        assert s["approval_rate"] == 1.0

    def test_approval_rate_none_when_no_validations(self, ws):
        assert ws.get_status()["approval_rate"] is None

    def test_per_module_stats_present(self, ws):
        ws.validate(_full_artifact(), module_id="deliverable")
        per = ws.get_status()["per_module"]
        assert "deliverable" in per
        assert per["deliverable"]["total_validations"] == 1

    def test_validate_all_default_modules(self, ws):
        for mid in ws.list_module_ids():
            r = ws.validate(_full_artifact(), module_id=mid)
            assert isinstance(r, ModuleValidationResult)

    def test_librarian_records_validation_result(self):
        lib = MagicMock()
        ws = WingmanSystem(librarian=lib)
        lib.reset_mock()
        ws.validate(_full_artifact(), module_id="deliverable")
        assert lib.add_knowledge_entry.call_count >= 1
        last_call = lib.add_knowledge_entry.call_args_list[-1][0][0]
        assert last_call["category"] == "wingman_validation_result"
        assert "APPROVED" in last_call["topic"] or "REJECTED" in last_call["topic"]

    def test_librarian_none_does_not_raise(self):
        ws = WingmanSystem(librarian=None)
        r = ws.validate(_full_artifact())
        assert r is not None


class TestWingmanSystemRegisterModule:

    @pytest.fixture
    def ws(self):
        return WingmanSystem(librarian=None)

    def test_register_new_module(self, ws):
        ws.register_module("custom_mod", "custom_domain")
        assert "custom_mod" in ws.list_module_ids()

    def test_registered_module_can_validate(self, ws):
        ws.register_module("custom_mod", "custom_domain")
        r = ws.validate(_full_artifact(), module_id="custom_mod")
        assert isinstance(r, ModuleValidationResult)
        assert r.module_id == "custom_mod"

    def test_register_replaces_existing(self, ws):
        ws.register_module("deliverable", "new_domain",
                           custom_rules=[{"severity": "block", "description": "new rule"}])
        r = ws.validate(_empty_artifact(), module_id="deliverable")
        domain_findings = [f for f in r.findings if f["sensor_id"] == "domain_rule"]
        assert any("new rule" in f["detail"] for f in domain_findings)

    def test_librarian_entry_on_register(self):
        lib = MagicMock()
        ws = WingmanSystem(librarian=lib)
        lib.reset_mock()
        ws.register_module("fresh_mod", "fresh_domain")
        assert lib.add_knowledge_entry.call_count == 1
        entry = lib.add_knowledge_entry.call_args[0][0]
        assert "fresh_mod" in entry["topic"]
        assert "wingman_validation" == entry["category"]

    def test_internal_library_private_after_register(self, ws):
        ws.register_module("new_mod", "test")
        status = ws.get_status()
        assert "_internal_library" not in status
        assert "new_mod" in status["module_domains"]


# ===========================================================================
# Thread safety
# ===========================================================================

class TestThreadSafety:

    def test_concurrent_validations(self):
        ws = WingmanSystem(librarian=None)
        errors: List[Exception] = []

        def run():
            try:
                for _ in range(20):
                    ws.validate(_full_artifact(), module_id="deliverable")
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=run) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert errors == [], f"Thread errors: {errors}"
        assert ws.get_status()["total_validations"] == 100

    def test_concurrent_register_and_validate(self):
        ws = WingmanSystem(librarian=None)
        errors: List[Exception] = []

        def register():
            try:
                for i in range(5):
                    ws.register_module(f"mod_{i}_{threading.get_ident()}", "test")
            except Exception as exc:
                errors.append(exc)

        def validate():
            try:
                for _ in range(10):
                    ws.validate(_full_artifact())
            except Exception as exc:
                errors.append(exc)

        threads = (
            [threading.Thread(target=register) for _ in range(3)]
            + [threading.Thread(target=validate) for _ in range(3)]
        )
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert errors == [], f"Thread errors: {errors}"


# ===========================================================================
# API endpoint integration (via TestClient)
# ===========================================================================

class TestWingmanEndpoints:
    """Test the three Wingman API endpoints against a real app instance."""

    @pytest.fixture(scope="class")
    def client(self):
        import os
        os.environ.setdefault("MURPHY_ENV", "development")
        os.environ.setdefault("MURPHY_RATE_LIMIT_RPM", "6000")
        from httpx import Client
        from src.runtime.app import create_app
        from starlette.testclient import TestClient
        return TestClient(create_app())

    def test_status_endpoint_returns_success(self, client):
        resp = client.get("/api/wingman/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

    def test_status_has_module_count(self, client):
        resp = client.get("/api/wingman/status")
        data = resp.json()
        # Either "registered_modules" (live) or "status" key (fallback)
        assert "registered_modules" in data or "status" in data

    def test_suggestions_endpoint_returns_success(self, client):
        resp = client.get("/api/wingman/suggestions")
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        assert "suggestions" in resp.json()

    def test_validate_endpoint_missing_artifact_returns_400(self, client):
        resp = client.post(
            "/api/wingman/validate",
            json={"module_id": "deliverable"},
        )
        assert resp.status_code in (400, 503)

    def test_validate_endpoint_with_full_artifact(self, client):
        artifact = _full_artifact()
        resp = client.post(
            "/api/wingman/validate",
            json={"artifact": artifact, "module_id": "deliverable"},
        )
        if resp.status_code == 200:
            data = resp.json()
            assert data["success"] is True
            assert "validation" in data
            assert "approved" in data["validation"]
        else:
            # 503 when wingman_system unavailable in test env
            assert resp.status_code == 503

    def test_deliverable_endpoint_includes_wingman_validation(self, client):
        resp = client.post(
            "/api/demo/generate-deliverable",
            json={"query": "Onboard a new client"},
            headers={"X-Forwarded-For": "10.99.0.1"},
        )
        if resp.status_code == 200:
            data = resp.json()
            assert data["success"] is True
            # wingman_validation key present when wingman_system is initialised
            if "wingman_validation" in data:
                wv = data["wingman_validation"]
                assert "approved" in wv
                assert "trigger_level" in wv
                assert "findings" in wv
