# Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
"""Tests for EnergyAuditEngine (EAE-001) — Layer 4 test coverage."""

import sys
import os
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from energy_audit_engine import (
    AuditLevel,
    AuditStatus,
    ECMCategory,
    ECMPriority,
    ComplianceFramework,
    FindingSeverity,
    EnergyReading,
    EnergyCostSummary,
    EnergyConservationMeasure,
    AuditFinding,
    EnergyAudit,
    EnergyAuditEngine,
    get_status,
)


class TestEnergyAuditEngineCreation(unittest.TestCase):
    """Test audit creation and lifecycle."""

    def setUp(self):
        self.engine = EnergyAuditEngine()

    def test_create_audit_level_i(self):
        audit = self.engine.create_audit(
            facility_id="FAC-001", facility_name="Test Office",
            sqft=50000, audit_level=AuditLevel.LEVEL_I,
            auditor_name="Murphy AI",
        )
        self.assertIsNotNone(audit)
        self.assertEqual(audit.facility_id, "FAC-001")
        self.assertEqual(audit.audit_level, AuditLevel.LEVEL_I)
        self.assertEqual(audit.status, AuditStatus.DRAFT)

    def test_create_audit_level_ii(self):
        audit = self.engine.create_audit(
            facility_id="FAC-002", facility_name="Test School",
            sqft=100000, audit_level=AuditLevel.LEVEL_II,
            auditor_name="Murphy AI",
        )
        self.assertEqual(audit.audit_level, AuditLevel.LEVEL_II)

    def test_create_audit_level_iii(self):
        audit = self.engine.create_audit(
            facility_id="FAC-003", facility_name="Hospital",
            sqft=200000, audit_level=AuditLevel.LEVEL_III,
            auditor_name="Murphy AI",
        )
        self.assertEqual(audit.audit_level, AuditLevel.LEVEL_III)

    def test_create_audit_with_compliance(self):
        audit = self.engine.create_audit(
            facility_id="FAC-004", facility_name="Office",
            sqft=30000, audit_level=AuditLevel.LEVEL_II,
            auditor_name="Murphy AI",
            compliance_frameworks=[ComplianceFramework.ISO_50001, ComplianceFramework.ASHRAE_90_1],
        )
        self.assertIn(ComplianceFramework.ISO_50001, audit.compliance_frameworks)

    def test_get_audit(self):
        audit = self.engine.create_audit(
            facility_id="FAC-005", facility_name="Warehouse",
            sqft=80000, audit_level=AuditLevel.LEVEL_I,
            auditor_name="Murphy AI",
        )
        retrieved = self.engine.get_audit(audit.audit_id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.audit_id, audit.audit_id)

    def test_get_nonexistent_audit(self):
        result = self.engine.get_audit("nonexistent-0001")
        self.assertIsNone(result)

    def test_list_audits(self):
        self.engine.create_audit("F1", "Office1", 10000, AuditLevel.LEVEL_I, "AI")
        self.engine.create_audit("F2", "Office2", 20000, AuditLevel.LEVEL_II, "AI")
        audits = self.engine.list_audits()
        self.assertGreaterEqual(len(audits), 2)

    def test_list_audits_by_facility(self):
        self.engine.create_audit("F-filter", "Specific", 10000, AuditLevel.LEVEL_I, "AI")
        self.engine.create_audit("F-other", "Other", 20000, AuditLevel.LEVEL_I, "AI")
        audits = self.engine.list_audits(facility_id="F-filter")
        # list_audits returns dicts
        self.assertTrue(all(a["facility_id"] == "F-filter" for a in audits))

    def test_list_audits_by_status(self):
        self.engine.create_audit("FS1", "S1", 10000, AuditLevel.LEVEL_I, "AI")
        audits = self.engine.list_audits(status=AuditStatus.DRAFT)
        self.assertTrue(all(a["status"] == "draft" for a in audits))


class TestEnergyAuditLifecycle(unittest.TestCase):
    """Test status transitions."""

    def setUp(self):
        self.engine = EnergyAuditEngine()
        self.audit = self.engine.create_audit(
            "FAC-LC", "Lifecycle Test", 50000, AuditLevel.LEVEL_II, "AI",
        )

    def test_advance_to_in_progress(self):
        result = self.engine.advance_audit_status(self.audit.audit_id, AuditStatus.IN_PROGRESS)
        self.assertIsInstance(result, dict)
        a = self.engine.get_audit(self.audit.audit_id)
        self.assertEqual(a.status, AuditStatus.IN_PROGRESS)

    def test_advance_to_review(self):
        self.engine.advance_audit_status(self.audit.audit_id, AuditStatus.IN_PROGRESS)
        result = self.engine.advance_audit_status(self.audit.audit_id, AuditStatus.REVIEW)
        self.assertIsInstance(result, dict)

    def test_advance_to_complete(self):
        self.engine.advance_audit_status(self.audit.audit_id, AuditStatus.IN_PROGRESS)
        self.engine.advance_audit_status(self.audit.audit_id, AuditStatus.REVIEW)
        result = self.engine.advance_audit_status(self.audit.audit_id, AuditStatus.COMPLETE)
        self.assertIsInstance(result, dict)


class TestEnergyReadings(unittest.TestCase):
    """Test energy reading ingestion."""

    def setUp(self):
        self.engine = EnergyAuditEngine()
        self.audit = self.engine.create_audit(
            "FAC-RD", "Readings Test", 50000, AuditLevel.LEVEL_II, "AI",
        )

    def test_ingest_readings(self):
        readings = [
            {
                "reading_id": f"R{i}",
                "facility_id": "FAC-RD",
                "meter_id": "M1",
                "energy_type": "electricity",
                "value_kwh": float(1000 + i * 10),
                "timestamp": time.time() - i * 86400,
                "period_days": 30,
                "unit_cost_usd": 0.12,
            }
            for i in range(12)
        ]
        result = self.engine.ingest_energy_readings(self.audit.audit_id, readings)
        self.assertTrue(result.get("success"))
        self.assertEqual(result["ingested"], 12)

    def test_compute_cost_summary(self):
        readings = [
            {
                "reading_id": f"R{i}",
                "facility_id": "FAC-RD",
                "meter_id": "M1",
                "energy_type": "electricity",
                "value_kwh": 10000.0,
                "timestamp": time.time() - i * 2_592_000,
                "period_days": 30,
                "unit_cost_usd": 0.12,
                "demand_kw": 200.0,
            }
            for i in range(12)
        ]
        self.engine.ingest_energy_readings(self.audit.audit_id, readings)
        summary = self.engine.compute_cost_summary(self.audit.audit_id)
        self.assertIsNotNone(summary)
        self.assertGreater(summary.total_kwh, 0)


class TestECMs(unittest.TestCase):
    """Test Energy Conservation Measures."""

    def setUp(self):
        self.engine = EnergyAuditEngine()
        self.audit = self.engine.create_audit(
            "FAC-ECM", "ECM Test", 50000, AuditLevel.LEVEL_II, "AI",
        )

    def test_add_ecm(self):
        result = self.engine.add_ecm(
            audit_id=self.audit.audit_id,
            title="LED Retrofit",
            description="Replace T8 with LED",
            category=ECMCategory.LIGHTING,
            priority=ECMPriority.HIGH,
            annual_savings_kwh=50000.0,
            unit_cost_usd=0.12,
            impl_cost_usd=24000.0,
        )
        self.assertTrue(result.get("success"))

    def test_get_ecm(self):
        result = self.engine.add_ecm(
            audit_id=self.audit.audit_id,
            title="VFD Install",
            description="Add VFDs to AHU fans",
            category=ECMCategory.HVAC,
            priority=ECMPriority.MEDIUM,
            annual_savings_kwh=80000.0,
            unit_cost_usd=0.12,
            impl_cost_usd=35000.0,
        )
        ecm_id = result["ecm"].ecm_id
        retrieved = self.engine.get_ecm(self.audit.audit_id, ecm_id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.title, "VFD Install")

    def test_list_ecms(self):
        for i in range(3):
            self.engine.add_ecm(
                self.audit.audit_id,
                title=f"Measure {i}", description=f"Desc {i}",
                category=ECMCategory.HVAC, priority=ECMPriority.LOW,
                annual_savings_kwh=10000.0, unit_cost_usd=0.12,
                impl_cost_usd=5000.0,
            )
        ecms = self.engine.list_ecms(self.audit.audit_id)
        self.assertGreaterEqual(len(ecms), 3)

    def test_prioritize_ecms(self):
        for i in range(3):
            self.engine.add_ecm(
                self.audit.audit_id,
                title=f"Prioritize {i}", description=f"Desc {i}",
                category=ECMCategory.HVAC, priority=ECMPriority.MEDIUM,
                annual_savings_kwh=float(20000 + i * 10000),
                unit_cost_usd=0.12,
                impl_cost_usd=float(10000 + i * 5000),
            )
        result = self.engine.prioritize_ecms(self.audit.audit_id, budget_usd=20000.0)
        self.assertIsInstance(result, list)


class TestFindings(unittest.TestCase):
    """Test audit findings."""

    def setUp(self):
        self.engine = EnergyAuditEngine()
        self.audit = self.engine.create_audit(
            "FAC-FND", "Findings Test", 50000, AuditLevel.LEVEL_II, "AI",
        )

    def test_add_finding(self):
        result = self.engine.add_finding(
            audit_id=self.audit.audit_id,
            area="HVAC Zone 1",
            observation="Simultaneous heating and cooling observed",
            baseline_kwh=120000.0,
            savings_pct=15.0,
            severity=FindingSeverity.HIGH,
        )
        self.assertTrue(result.get("success"))


class TestReporting(unittest.TestCase):
    """Test summary and compliance reporting."""

    def setUp(self):
        self.engine = EnergyAuditEngine()
        self.audit = self.engine.create_audit(
            "FAC-RPT", "Report Test", 50000, AuditLevel.LEVEL_II, "AI",
            compliance_frameworks=[ComplianceFramework.ISO_50001],
        )

    def test_executive_summary(self):
        summary = self.engine.generate_executive_summary(self.audit.audit_id)
        self.assertIsInstance(summary, str)
        self.assertGreater(len(summary), 0)

    def test_compliance_report(self):
        report = self.engine.generate_compliance_report(
            self.audit.audit_id, ComplianceFramework.ISO_50001,
        )
        self.assertIsInstance(report, dict)

    def test_export_audit(self):
        export = self.engine.export_audit(self.audit.audit_id)
        self.assertIsInstance(export, dict)
        self.assertIn("audit_id", export)


class TestBenchmarking(unittest.TestCase):
    """Test EUI benchmarking."""

    def setUp(self):
        self.engine = EnergyAuditEngine()

    def test_benchmark_eui_office(self):
        # EUI for 50k sqft office using 500k kWh/yr ≈ 34 kBtu/sqft/yr
        eui = 500000 * 3.412 / 50000  # ~34.12 kBtu/sqft/yr
        result = self.engine.benchmark_eui("office", eui)
        self.assertIsInstance(result, dict)

    def test_benchmark_eui_hospital(self):
        eui = 5000000 * 3.412 / 200000  # ~85.3 kBtu/sqft/yr
        result = self.engine.benchmark_eui("hospital", eui)
        self.assertIsInstance(result, dict)

    def test_benchmark_unknown_type(self):
        result = self.engine.benchmark_eui("unknown_building_type", 100.0)
        self.assertIsInstance(result, dict)


class TestGetStatus(unittest.TestCase):
    """Test module status function."""

    def test_status(self):
        status = get_status()
        self.assertIsInstance(status, dict)
        self.assertIn("module", status)


if __name__ == "__main__":
    unittest.main()
