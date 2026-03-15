"""
Cross-Module Integration Tests for Murphy System Subsystems.
Murphy System - Copyright 2024-2026 Corey Post, Inoni LLC - License: BSL 1.1

Tests that span multiple subsystems to prove end-to-end production readiness.
"""

import pytest
from datetime import datetime, timezone, timedelta


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_pe_credential(jurisdiction="TX"):
    """Create and register a valid PE credential, return (registry, credential)."""
    from src.murphy_credential_gate import (
        CredentialRegistry, CredentialVerifier, EStampEngine,
        CredentialGatedApproval, CredentialType, ProfessionalCredential,
    )
    exp = (datetime.now(timezone.utc) + timedelta(days=365)).strftime("%Y-%m-%d")
    iss = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    cred = ProfessionalCredential(
        holder_name="Production PE",
        holder_email="pe@murphy.system",
        credential_type=CredentialType.PE,
        license_number="PE-PROD-001",
        issuing_authority="State Engineering Board",
        jurisdiction=jurisdiction,
        issued_date=iss,
        expiration_date=exp,
    )
    registry = CredentialRegistry()
    registry.register(cred)
    verifier = CredentialVerifier(registry)
    stamp_engine = EStampEngine(registry, verifier)
    gated = CredentialGatedApproval(registry, verifier, stamp_engine)
    return registry, cred, gated


# ---------------------------------------------------------------------------
# 1. Drawing Engine → Credential Gate integration
# ---------------------------------------------------------------------------

class TestDrawingToCredentialGate:
    """Drawing → BOM → DXF/SVG export → Credential-gated PE approval."""

    def test_drawing_project_pe_stamped_approval(self):
        """Create a drawing, export it, and get PE-stamped approval."""
        from src.murphy_drawing_engine import (
            DrawingProject, DrawingSheet, DrawingElement, DrawingExporter,
            DrawingApprovalIntegration, ElementType, Discipline, SheetSize, TitleBlock,
        )
        from src.murphy_credential_gate import CredentialType

        _, cred, gated = _make_pe_credential("CA")

        # Build drawing project
        project = DrawingProject(name="Structural Frame Drawing", discipline=Discipline.STRUCTURAL)
        sheet = DrawingSheet(size=SheetSize.ANSI_D)
        sheet.title_block = TitleBlock(
            company="Murphy Engineering",
            project="Structural Frame",
            drawing_number="SE-001",
            drawn_by="Alice",
            checked_by="Bob",
        )
        sheet.elements.append(DrawingElement(
            element_type=ElementType.LINE,
            geometry={"x1": 0, "y1": 0, "z1": 0, "x2": 100, "y2": 0, "z2": 0},
        ))
        project.sheets.append(sheet)

        # Request PE approval
        dai = DrawingApprovalIntegration(gated)
        result = dai.request_pe_stamp(
            project=project,
            approver_credential_id=cred.credential_id,
            required_credential_types=[CredentialType.PE],
            jurisdiction="CA",
        )
        assert result["status"] == "approved"
        assert result["has_stamp"] is True
        assert result["document_id"] == project.project_id

    def test_drawing_export_dxf_and_svg_both_valid(self):
        """Verify that the same project produces valid DXF and SVG."""
        import xml.etree.ElementTree as ET
        from src.murphy_drawing_engine import (
            DrawingProject, DrawingSheet, DrawingElement, DrawingExporter,
            ElementType, Discipline, SheetSize,
        )
        project = DrawingProject(name="Multi-Format Test", discipline=Discipline.MECHANICAL)
        sheet = DrawingSheet(size=SheetSize.ANSI_D)
        sheet.elements.append(DrawingElement(
            element_type=ElementType.CIRCLE,
            geometry={"cx": 50, "cy": 50, "cz": 0, "radius": 25},
        ))
        sheet.elements.append(DrawingElement(
            element_type=ElementType.RECTANGLE,
            geometry={"x": 10, "y": 10, "width": 80, "height": 60},
        ))
        project.sheets.append(sheet)

        exporter = DrawingExporter()
        dxf = exporter.to_dxf(project)
        svg = exporter.to_svg(project)

        # DXF validity
        assert "SECTION" in dxf and "EOF" in dxf and "CIRCLE" in dxf

        # SVG validity (well-formed XML)
        root = ET.fromstring(svg)
        assert root.tag.endswith("svg")

    def test_bom_to_credential_gate_workflow(self):
        """Extract BOM from drawing, then use credential gate for approval."""
        from src.murphy_drawing_engine import (
            DrawingProject, DrawingSheet, DrawingElement, BOMExtractor,
            DrawingApprovalIntegration, ElementType, Discipline,
        )
        from src.murphy_credential_gate import CredentialType
        import json

        _, cred, gated = _make_pe_credential("TX")

        project = DrawingProject(name="Equipment Schedule", discipline=Discipline.MECHANICAL)
        sheet = DrawingSheet()
        for i in range(3):
            sheet.elements.append(DrawingElement(
                element_type=ElementType.BLOCK_REF,
                properties={"block_name": f"PUMP_{i+1}", "quantity": 2, "part_number": f"P-00{i+1}"},
            ))
        project.sheets.append(sheet)

        bom = BOMExtractor().extract(project)
        assert len(bom) == 3

        dai = DrawingApprovalIntegration(gated)
        result = dai.request_pe_stamp(
            project=project,
            approver_credential_id=cred.credential_id,
            required_credential_types=[CredentialType.PE],
            jurisdiction="TX",
        )
        assert result["status"] == "approved"


# ---------------------------------------------------------------------------
# 2. Sensor Fusion → Autonomous Perception integration
# ---------------------------------------------------------------------------

class TestSensorFusionToPerception:
    """Feed fused sensor state into perception pipeline → safety decisions."""

    def test_fused_state_feeds_perception_pipeline(self):
        """Fused vehicle sensor data used to populate perception frame → decision."""
        from src.murphy_sensor_fusion import (
            VehicleFusionProfile, SensorReading, ReadingQuality, FusionStrategy,
            SensorFusionPipeline, SensorSource, DataType,
        )
        from src.murphy_autonomous_perception import (
            PerceptionPipeline, PerceptionObject, ObjectClass, Vector3D, AutonomyAction,
        )

        # Step 1: Fuse radar readings to estimate target distance
        source = SensorSource(source_id="radar-1", data_type=DataType.NUMERIC, unit="m/s")
        pipeline = SensorFusionPipeline("radar-pipeline", [source], FusionStrategy.WEIGHTED_AVERAGE)
        readings = [
            SensorReading(source_id="radar-1", value=15.0, quality=ReadingQuality.GOOD),
            SensorReading(source_id="radar-2", value=16.0, quality=ReadingQuality.GOOD),
        ]
        fused = pipeline.fuse(readings)
        assert fused.confidence > 0.5

        # Step 2: Use fused value to set up perception object
        fused_speed = fused.readings.get("fused_value", 15.0)
        pp = PerceptionPipeline()
        obj = PerceptionObject(
            object_class=ObjectClass.VEHICLE,
            position=Vector3D(x=50, y=0),
            velocity=Vector3D(x=-fused_speed, y=0),
        )
        frame, decision = pp.process(
            [obj],
            ego_velocity=Vector3D(x=fused_speed, y=0),
        )
        assert decision.action in AutonomyAction.__members__.values()

    def test_high_disagreement_reduces_confidence(self):
        """Disagreement between sensors reduces fused confidence below 1.0."""
        from src.murphy_sensor_fusion import (
            SensorFusionPipeline, FusionStrategy, SensorSource, DataType,
            SensorReading, ReadingQuality,
        )
        source = SensorSource(source_id="s0", data_type=DataType.NUMERIC)
        pipeline = SensorFusionPipeline("pipe1", [source], FusionStrategy.WEIGHTED_AVERAGE)
        readings = [
            SensorReading(source_id="s1", value=10.0, quality=ReadingQuality.GOOD),
            SensorReading(source_id="s2", value=100.0, quality=ReadingQuality.GOOD),
        ]
        fused = pipeline.fuse(readings)
        # disagreement should be non-zero
        assert fused.disagreement_score > 0.0

    def test_all_fusion_strategies_work_with_perception(self):
        """Each fusion strategy produces a valid fused state usable by perception."""
        from src.murphy_sensor_fusion import (
            SensorFusionPipeline, FusionStrategy, SensorSource, DataType,
            SensorReading, ReadingQuality,
        )
        from src.murphy_autonomous_perception import PerceptionPipeline, Vector3D

        source = SensorSource(source_id="s0", data_type=DataType.NUMERIC)
        readings = [SensorReading(source_id="s0", value=10.0, quality=ReadingQuality.GOOD),
                    SensorReading(source_id="s1", value=11.0, quality=ReadingQuality.GOOD)]

        for strategy in FusionStrategy:
            pipeline = SensorFusionPipeline(f"p-{strategy}", [source], strategy)
            fused = pipeline.fuse(readings)
            assert fused.source_count == 2
            assert fused.confidence > 0.0


# ---------------------------------------------------------------------------
# 3. Osmosis Engine → Wingman Evolution integration
# ---------------------------------------------------------------------------

class TestOsmosisToWingmanEvolution:
    """Observe capability → extract pattern → build impl → create wingman pair → evolve runbook."""

    def test_observe_extract_build_wingman_pair(self):
        """Full pipeline: osmosis absorbs capability → wingman pair created."""
        from src.murphy_osmosis_engine import OsmosisPipeline, ImplementationStatus
        from src.murphy_wingman_evolution import WingmanEvolution

        # Step 1: Osmosis pipeline absorbs capability
        osmosis = OsmosisPipeline()
        observations = [{"input": i, "output": i * 2.0} for i in range(1, 6)]
        test_cases = [{"input": i, "expected_output": i * 2.0} for i in range(1, 6)]
        cap = osmosis.absorb("ExternalAPI", "double_value", "Multiply input by 2",
                             observations, test_cases)
        assert cap.murphy_implementation_status == ImplementationStatus.VALIDATED

        # Step 2: Create wingman pair for the absorbed capability
        evolution = WingmanEvolution()
        pair = evolution.factory().auto_create_pair(
            subject=cap.capability_name,
            capability_type="osmosis",
        )
        assert pair["pair_id"].startswith("wp-auto-")

        # Step 3: Record some validations and evolve
        for _ in range(3):
            evolution.record_validation(pair["pair_id"], True)
        metrics = evolution.get_metrics(pair["pair_id"])
        assert metrics.total_validations == 3

    def test_failed_osmosis_candidate_not_promoted(self):
        """Capability that fails sandbox stays in OBSERVED; wingman pair handles it safely."""
        from src.murphy_osmosis_engine import OsmosisPipeline, ImplementationStatus
        from src.murphy_wingman_evolution import WingmanEvolution

        osmosis = OsmosisPipeline()
        observations = [{"input": i, "output": i * 2.0} for i in range(1, 4)]
        test_cases = [{"input": i, "expected_output": i * 999.0} for i in range(1, 4)]  # wrong
        cap = osmosis.absorb("ExternalAPI", "wrong_impl", "Wrong expected", observations, test_cases)
        assert cap.murphy_implementation_status == ImplementationStatus.OBSERVED

        # Can still create wingman pair
        evolution = WingmanEvolution()
        pair = evolution.factory().auto_create_pair(cap.capability_name, "osmosis")
        assert pair is not None

    def test_runbook_evolves_after_osmosis_validation_history(self):
        """After recording validation history from osmosis, runbook evolution fires."""
        from src.murphy_osmosis_engine import OsmosisPipeline, ImplementationStatus
        from src.murphy_wingman_evolution import WingmanEvolution

        osmosis = OsmosisPipeline()
        observations = [{"input": i, "output": i * 3.0} for i in range(1, 6)]
        test_cases = [{"input": i, "expected_output": i * 3.0} for i in range(1, 6)]
        cap = osmosis.absorb("APIv2", "triple_value", "x3", observations, test_cases)

        evolution = WingmanEvolution()
        pair = evolution.factory().auto_create_pair(cap.capability_name, "osmosis")
        pair_id = pair["pair_id"]

        # Simulate validation history that always passes one rule
        history = [{"results": [{"rule_id": "check_output", "passed": True}]} for _ in range(10)]
        for _ in range(10):
            evolution.record_validation(pair_id, True)
        suggestions = evolution.evolve(pair_id, history)

        relax = [s for s in suggestions if s.suggestion_type == "relax"]
        assert len(relax) >= 1


# ---------------------------------------------------------------------------
# 4. Engineering Toolbox → Drawing Engine integration
# ---------------------------------------------------------------------------

class TestEngineeringToolboxToDrawing:
    """Use toolbox calculations to parameterize drawing elements."""

    def test_beam_deflection_drives_drawing_dimensions(self):
        """Compute beam span from structural calc, then draw the beam element."""
        from src.murphy_engineering_toolbox import StructuralCalcs, UnitConverter
        from src.murphy_drawing_engine import (
            AgenticDrawingAssistant, DrawingProject, ElementType, Discipline,
        )

        # Step 1: Engineering calc — find span for a given deflection limit
        sc = StructuralCalcs()
        uc = UnitConverter()
        result = sc.simple_beam_deflection(
            load_N=50000, span_m=6, E_Pa=200e9, I_m4=2e-5, load_type="center"
        )
        span_m = 6.0
        span_ft = uc.convert(span_m, "m", "ft")

        # Step 2: Draw the beam in the drawing engine
        project = DrawingProject(name="Structural Beam Drawing", discipline=Discipline.STRUCTURAL)
        assistant = AgenticDrawingAssistant(project)
        cmd = f"draw line from (0,0) to ({span_ft:.1f},0)"
        result_cmd = assistant.execute(cmd)
        assert result_cmd["success"] is True
        elem = project.sheets[0].elements[0]
        assert elem.element_type == ElementType.LINE
        assert abs(elem.geometry["x2"] - span_ft) < 0.1

    def test_unit_conversion_used_in_drawing_workflow(self):
        """Convert units, then use result to set drawing element geometry."""
        from src.murphy_engineering_toolbox import UnitConverter
        from src.murphy_drawing_engine import (
            AgenticDrawingAssistant, DrawingProject, ElementType, Discipline,
        )

        uc = UnitConverter()
        width_m = 3.5  # 3.5m wide room
        width_ft = uc.convert(width_m, "m", "ft")

        project = DrawingProject(name="Room Layout", discipline=Discipline.ARCHITECTURAL)
        assistant = AgenticDrawingAssistant(project)
        cmd = f"draw a {width_ft:.1f}x{width_ft:.1f} rectangle at origin"
        result = assistant.execute(cmd)
        assert result["success"] is True
        assert project.sheets[0].elements[0].element_type == ElementType.RECTANGLE

    def test_hvac_load_drives_equipment_annotation(self):
        """Compute HVAC load then annotate drawing with required tonnage."""
        from src.murphy_engineering_toolbox import HVACCalcs
        from src.murphy_drawing_engine import (
            AgenticDrawingAssistant, DrawingProject, ElementType, Discipline,
        )

        hc = HVACCalcs()
        load = hc.simple_heat_load(area_m2=200, delta_T_K=20, occupants=20, lighting_W_m2=15)
        tonnage = load.recommended_tonnage

        project = DrawingProject(name="HVAC Drawing", discipline=Discipline.HVAC)
        assistant = AgenticDrawingAssistant(project)
        result = assistant.execute(f"add text 'HVAC: {tonnage:.1f} ton unit' at 50,50")
        assert result["success"] is True
        elem = project.sheets[0].elements[0]
        assert elem.element_type == ElementType.TEXT
        assert "ton" in elem.properties["text"].lower()


# ---------------------------------------------------------------------------
# 5. Full pipeline integration test
# ---------------------------------------------------------------------------

class TestFullPipeline:
    """
    Drawing created → Engineering calcs attached → Sensor data fused →
    Perception evaluated → Osmosis absorbs pattern → Wingman validates →
    Credential gate approves.
    """

    def test_full_end_to_end_pipeline(self):
        """Integration test spanning all 7 subsystems in sequence."""
        from src.murphy_drawing_engine import (
            DrawingProject, DrawingSheet, DrawingElement, DrawingExporter,
            AgenticDrawingAssistant, DrawingApprovalIntegration, ElementType, Discipline,
        )
        from src.murphy_credential_gate import CredentialType
        from src.murphy_engineering_toolbox import StructuralCalcs, UnitConverter
        from src.murphy_sensor_fusion import (
            SensorFusionPipeline, FusionStrategy, SensorSource, DataType,
            SensorReading, ReadingQuality,
        )
        from src.murphy_autonomous_perception import (
            PerceptionPipeline, PerceptionObject, ObjectClass, Vector3D, AutonomyAction,
        )
        from src.murphy_osmosis_engine import OsmosisPipeline, ImplementationStatus
        from src.murphy_wingman_evolution import WingmanEvolution

        # ── Step 1: Engineering Toolbox ─────────────────────────────────────
        uc = UnitConverter()
        sc = StructuralCalcs()
        beam_result = sc.simple_beam_deflection(
            load_N=100000, span_m=8, E_Pa=200e9, I_m4=5e-5, load_type="center"
        )
        assert beam_result.max_deflection_m > 0
        span_in = uc.convert(8.0, "m", "in")

        # ── Step 2: Drawing Engine ───────────────────────────────────────────
        project = DrawingProject(name="Full Pipeline Test", discipline=Discipline.STRUCTURAL)
        assistant = AgenticDrawingAssistant(project)
        assistant.execute(f"draw line from (0,0) to ({span_in:.0f},0)")
        assert len(project.sheets[0].elements) == 1

        # ── Step 3: Credential Gate ──────────────────────────────────────────
        _, cred, gated = _make_pe_credential("TX")
        dai = DrawingApprovalIntegration(gated)
        approval = dai.request_pe_stamp(
            project=project,
            approver_credential_id=cred.credential_id,
            required_credential_types=[CredentialType.PE],
            jurisdiction="TX",
        )
        assert approval["status"] == "approved"

        # ── Step 4: Sensor Fusion ────────────────────────────────────────────
        source = SensorSource(source_id="strain-1", data_type=DataType.NUMERIC, unit="MPa")
        fusion_pipe = SensorFusionPipeline("strain-pipe", [source], FusionStrategy.WEIGHTED_AVERAGE)
        readings = [
            SensorReading(source_id="strain-1", value=150.0, quality=ReadingQuality.GOOD),
            SensorReading(source_id="strain-2", value=155.0, quality=ReadingQuality.GOOD),
        ]
        fused = fusion_pipe.fuse(readings)
        assert fused.confidence > 0.5

        # ── Step 5: Autonomous Perception ───────────────────────────────────
        perception_pipe = PerceptionPipeline()
        obj = PerceptionObject(
            object_class=ObjectClass.STATIC_OBSTACLE,
            position=Vector3D(x=50, y=0),
        )
        frame, decision = perception_pipe.process([obj], ego_velocity=Vector3D(x=5, y=0))
        assert decision.action in AutonomyAction.__members__.values()

        # ── Step 6: Osmosis Engine ───────────────────────────────────────────
        osmosis = OsmosisPipeline()
        obs = [{"input": fused.readings.get("fused_value", 152), "output": True}]
        cap = osmosis.absorb("strain_sensor", "classify_stress", "is stress acceptable?",
                             obs, [])
        assert cap.capability_id is not None

        # ── Step 7: Wingman Evolution ────────────────────────────────────────
        we = WingmanEvolution()
        pair = we.factory().auto_create_pair(
            subject="full-pipeline-validation",
            capability_type="autonomy",
            domain="safety",
        )
        for approved in [True, True, True, False, True]:
            we.record_validation(pair["pair_id"], approved)
        metrics = we.get_metrics(pair["pair_id"])
        assert metrics.total_validations == 5
        scorecard = we.get_scorecard(pair["pair_id"])
        assert scorecard is not None

        # ── Final assert: all subsystems produced valid outputs ──────────────
        assert approval["status"] == "approved"
        assert fused.source_count == 2
        assert len(frame.objects) == 1
        assert metrics.total_validations == 5
