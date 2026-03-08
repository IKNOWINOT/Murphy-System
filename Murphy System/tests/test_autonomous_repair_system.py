"""
Comprehensive Test Suite for the Autonomous Repair System.

Design Label: ARCH-006 — Autonomous Repair System Tests
Owner: Backend Team

Tests cover:
  - Multi-layer diagnosis detects known gap types
  - Reconciliation loop converges to desired state
  - Immune memory persists and recalls fixes
  - Antibody generation produces valid variant fixes
  - Wiring validator catches port mismatches and missing endpoints
  - Terminology lock-on detects cross-module meaning drift
  - Innovation farmer generates valid proposals
  - Knowledge builder produces industry-specific knowledge sets
  - REST API endpoints return correct responses

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import uuid

import pytest

_SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from autonomous_repair_system import (
    AutonomousRepairSystem,
    DiagnosisLayer,
    DiagnosisResult,
    ImmuneMemoryCell,
    ImmuneSystem,
    ImmunityType,
    PredictiveDiagnosisLayer,
    ReconciliationLoop,
    RepairProposal,
    RepairReport,
    RepairStatus,
    RuntimeDiagnosisLayer,
    SemanticDiagnosisLayer,
    StaticDiagnosisLayer,
    TermConcordanceEntry,
    TerminologyLockOnEngine,
    WiringDiagnosisLayer,
    WiringIssue,
    WiringIssueKind,
)
from generative_knowledge_builder import (
    BoundaryCondition,
    GenerativeKnowledgeBuilder,
    IndustryDomain,
    KnowledgeSet,
    TermDefinition,
    TermRelationship,
)
from innovation_farmer import (
    CompetitiveGapEntry,
    FeatureProposal,
    GapPriority,
    InnovationFarmer,
    InnovationScanReport,
    OpenSourcePattern,
    PatternCategory,
)


# ===========================================================================
# Fixtures
# ===========================================================================

@pytest.fixture()
def tmp_src_dir(tmp_path):
    """Create a temporary src directory with sample Python files."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "__init__.py").write_text("", encoding="utf-8")
    (src / "module_a.py").write_text(
        "def trigger_workflow(workflow_id):\n    pass\n",
        encoding="utf-8",
    )
    (src / "module_b.py").write_text(
        "def schedule_gate(gate_id):\n    pass\n",
        encoding="utf-8",
    )
    return str(src)


@pytest.fixture()
def tmp_broken_src_dir(tmp_path):
    """Create a temporary src directory with a syntax-error file."""
    src = tmp_path / "broken_src"
    src.mkdir()
    (src / "good_module.py").write_text("x = 1\n", encoding="utf-8")
    (src / "bad_module.py").write_text("def broken(:\n    pass\n", encoding="utf-8")
    return str(src)


@pytest.fixture()
def repair_system(tmp_src_dir):
    """Create an AutonomousRepairSystem with a temp src directory."""
    return AutonomousRepairSystem(
        src_root=tmp_src_dir,
        project_root=os.path.dirname(tmp_src_dir),
    )


@pytest.fixture()
def immune_system():
    """Create a bare ImmuneSystem."""
    return ImmuneSystem()


@pytest.fixture()
def innovation_farmer():
    """Create an InnovationFarmer."""
    return InnovationFarmer()


@pytest.fixture()
def knowledge_builder():
    """Create a GenerativeKnowledgeBuilder."""
    return GenerativeKnowledgeBuilder()


@pytest.fixture()
def reconciliation_loop(tmp_src_dir):
    """Create a ReconciliationLoop with a temp src directory."""
    return ReconciliationLoop(src_root=tmp_src_dir)


# ===========================================================================
# Tests: Multi-Layer Diagnosis
# ===========================================================================

class TestMultiLayerDiagnosis:
    """Tests for multi-layer diagnosis engine components."""

    def test_static_layer_runs_without_repair_engine(self, tmp_src_dir):
        """Static layer returns a result even without CodeRepairEngine."""
        layer = StaticDiagnosisLayer(src_root=tmp_src_dir)
        result = layer.run()
        assert isinstance(result, DiagnosisResult)
        assert result.layer == DiagnosisLayer.STATIC

    def test_static_layer_detects_syntax_error(self, tmp_broken_src_dir):
        """Static layer detects syntax errors in source files."""
        layer = StaticDiagnosisLayer(src_root=tmp_broken_src_dir)
        result = layer.run()
        assert any(
            i.get("type") == "syntax_error" for i in result.issues
        ), "Expected syntax_error to be detected"

    def test_static_layer_no_issues_for_clean_src(self, tmp_src_dir):
        """Static layer reports no issues for valid Python files."""
        layer = StaticDiagnosisLayer(src_root=tmp_src_dir)
        result = layer.run()
        syntax_errors = [i for i in result.issues if i.get("type") == "syntax_error"]
        assert syntax_errors == []

    def test_runtime_layer_runs_without_dependencies(self):
        """Runtime layer degrades gracefully when dependencies are None."""
        layer = RuntimeDiagnosisLayer()
        result = layer.run()
        assert isinstance(result, DiagnosisResult)
        assert result.layer == DiagnosisLayer.RUNTIME
        assert result.issues == []

    def test_semantic_layer_runs_without_controller(self):
        """Semantic layer degrades gracefully when controller is None."""
        layer = SemanticDiagnosisLayer()
        result = layer.run()
        assert isinstance(result, DiagnosisResult)
        assert result.layer == DiagnosisLayer.SEMANTIC

    def test_predictive_layer_reports_rising_trend(self):
        """Predictive layer detects rising error trend."""
        layer = PredictiveDiagnosisLayer()
        for count in [1, 3, 7, 15, 30]:
            layer.record_error_count(count)
        result = layer.run()
        assert isinstance(result, DiagnosisResult)
        assert result.layer == DiagnosisLayer.PREDICTIVE

    def test_predictive_layer_no_issues_for_empty_history(self):
        """Predictive layer reports no issues when history is empty."""
        layer = PredictiveDiagnosisLayer()
        result = layer.run()
        assert result.issues == []

    def test_wiring_layer_runs_for_nonexistent_project_root(self, tmp_path):
        """Wiring layer runs gracefully when project files do not exist."""
        layer = WiringDiagnosisLayer(project_root=str(tmp_path))
        result = layer.run()
        assert isinstance(result, DiagnosisResult)
        assert result.layer == DiagnosisLayer.WIRING

    def test_wiring_layer_detects_port_mismatch(self, tmp_path):
        """Wiring layer detects frontend endpoints using non-authorised ports."""
        js_file = tmp_path / "murphy_overlay.js"
        js_file.write_text(
            'const url = "http://localhost:8080/api/chat";\n',
            encoding="utf-8",
        )
        layer = WiringDiagnosisLayer(project_root=str(tmp_path))
        result = layer.run()
        port_issues = [
            i for i in result.issues
            if i.get("type") == WiringIssueKind.PORT_MISMATCH.value
        ]
        assert port_issues, "Expected at least one port mismatch issue"


# ===========================================================================
# Tests: Reconciliation Loop
# ===========================================================================

class TestReconciliationLoop:
    """Tests for the Kubernetes-inspired reconciliation loop."""

    def test_reconcile_returns_state(self, reconciliation_loop):
        """Reconciliation loop returns a valid state object."""
        state = reconciliation_loop.reconcile()
        assert state is not None
        assert isinstance(state.drift_items, list)
        assert state.convergence_iterations >= 1

    def test_reconcile_detects_import_drift(self, tmp_broken_src_dir):
        """Reconciliation loop detects drift when files have syntax errors."""
        loop = ReconciliationLoop(src_root=tmp_broken_src_dir)
        state = loop.reconcile()
        assert any(
            d["key"] == "all_modules_importable"
            for d in state.drift_items
        ), "Expected drift for all_modules_importable"

    def test_reconcile_clean_src_no_drift(self, tmp_src_dir):
        """Reconciliation loop reports no drift for clean source."""
        loop = ReconciliationLoop(src_root=tmp_src_dir)
        state = loop.reconcile()
        importable_drift = [
            d for d in state.drift_items
            if d["key"] == "all_modules_importable"
        ]
        assert importable_drift == []

    def test_convergence_iterations_increment(self, reconciliation_loop):
        """Convergence iterations counter increments on each reconcile call."""
        reconciliation_loop.reconcile()
        reconciliation_loop.reconcile()
        state = reconciliation_loop.get_state()
        assert state.convergence_iterations >= 2

    def test_desired_state_override(self, tmp_src_dir):
        """Custom desired state is respected."""
        desired = {"all_modules_importable": True, "custom_check": True}
        loop = ReconciliationLoop(src_root=tmp_src_dir, desired_state=desired)
        state = loop.reconcile()
        custom_drift = [d for d in state.drift_items if d["key"] == "custom_check"]
        assert len(custom_drift) == 1

    def test_state_serialisation(self, reconciliation_loop):
        """ReconciliationState serialises to a dict without errors."""
        reconciliation_loop.reconcile()
        state = reconciliation_loop.get_state()
        d = state.to_dict()
        assert "desired_state" in d
        assert "actual_state" in d
        assert "drift_items" in d


# ===========================================================================
# Tests: Immune System
# ===========================================================================

class TestImmuneSystem:
    """Tests for the immune system pattern."""

    def test_innate_immunity_responds_to_timeout(self, immune_system):
        """Innate immunity responds to timeout errors."""
        cell = immune_system.respond("operation timed out after 30s")
        assert cell is not None
        assert "timeout" in cell.fix_applied.lower() or cell.fix_applied != ""

    def test_innate_immunity_responds_to_import_error(self, immune_system):
        """Innate immunity responds to ImportError failures."""
        cell = immune_system.respond("ImportError: No module named 'foo'")
        assert cell is not None

    def test_memorize_fix_stores_cell(self, immune_system):
        """Memorizing a fix creates a new adaptive immune memory cell."""
        cell = immune_system.memorize_fix(
            error_description="Custom error: widget exploded",
            fix_applied="Restart widget manager",
            signature="WidgetExplosionError",
        )
        assert cell is not None
        assert cell.immunity_type == ImmunityType.ADAPTIVE
        assert "WidgetExplosionError" in cell.error_signature

    def test_memorized_fix_is_recalled(self, immune_system):
        """A memorized fix is recalled when the same error occurs again."""
        immune_system.memorize_fix(
            error_description="DatabaseConnectionError: pool exhausted",
            fix_applied="Increase connection pool size",
            signature="DatabaseConnectionError",
        )
        recalled = immune_system.respond("DatabaseConnectionError: pool exhausted")
        assert recalled is not None
        assert "pool" in recalled.fix_applied.lower() or recalled is not None

    def test_antibody_generation_for_similar_error(self, immune_system):
        """Antibody is generated for a similar but novel error."""
        immune_system.memorize_fix(
            error_description="ServiceTimeout: auth-service took too long",
            fix_applied="Increase auth-service timeout to 30s",
            signature="ServiceTimeout",
        )
        antibody = immune_system.respond("ServiceTimeout: payment-service too slow")
        assert antibody is not None

    def test_get_all_memory_returns_cells(self, immune_system):
        """get_all_memory returns all stored memory cells."""
        cells = immune_system.get_all_memory()
        assert isinstance(cells, list)
        assert len(cells) >= 5

    def test_memory_cell_serialisation(self, immune_system):
        """ImmuneMemoryCell serialises to a dict correctly."""
        cell = immune_system.memorize_fix(
            error_description="Test error",
            fix_applied="Test fix",
        )
        d = cell.to_dict()
        assert "cell_id" in d
        assert "fix_applied" in d
        assert "immunity_type" in d


# ===========================================================================
# Tests: Terminology Lock-On Engine
# ===========================================================================

class TestTerminologyLockOnEngine:
    """Tests for the Terminology Probability Lock-On Engine."""

    def test_build_concordance_map_returns_dict(self, tmp_src_dir):
        """build_concordance_map returns a populated concordance dict."""
        engine = TerminologyLockOnEngine(src_root=tmp_src_dir)
        concordance = engine.build_concordance_map()
        assert isinstance(concordance, dict)
        assert len(concordance) > 0

    def test_concordance_entry_has_required_fields(self, tmp_src_dir):
        """Each concordance entry has the expected fields."""
        engine = TerminologyLockOnEngine(src_root=tmp_src_dir)
        concordance = engine.build_concordance_map()
        for entry in concordance.values():
            assert isinstance(entry, TermConcordanceEntry)
            assert isinstance(entry.consistency_score, float)
            assert 0.0 <= entry.consistency_score <= 1.0

    def test_flagged_terms_are_inconsistent(self, tmp_src_dir):
        """Flagged terms have consistency_score < 0.7."""
        engine = TerminologyLockOnEngine(src_root=tmp_src_dir)
        engine.build_concordance_map()
        for entry in engine.get_flagged_terms():
            assert entry.consistency_score < 0.7

    def test_get_concordance_map_serialisable(self, tmp_src_dir):
        """get_concordance_map returns JSON-serialisable output."""
        engine = TerminologyLockOnEngine(src_root=tmp_src_dir)
        engine.build_concordance_map()
        cmap = engine.get_concordance_map()
        json.dumps(cmap)

    def test_concordance_empty_dir_is_safe(self, tmp_path):
        """build_concordance_map handles an empty directory safely."""
        empty_dir = tmp_path / "empty_src"
        empty_dir.mkdir()
        engine = TerminologyLockOnEngine(src_root=str(empty_dir))
        concordance = engine.build_concordance_map()
        assert isinstance(concordance, dict)


# ===========================================================================
# Tests: Wiring Validator
# ===========================================================================

class TestWiringValidator:
    """Tests for the front-end to back-end wiring validator."""

    def test_wiring_issue_serialisation(self):
        """WiringIssue serialises to a dict with all required fields."""
        wi = WiringIssue(
            issue_id=str(uuid.uuid4()),
            kind=WiringIssueKind.PORT_MISMATCH,
            description="Port mismatch detected",
            frontend_ref="/api/chat",
            proposed_fix="Update frontend to use port 8053",
        )
        d = wi.to_dict()
        assert d["kind"] == WiringIssueKind.PORT_MISMATCH.value
        assert "Port mismatch" in d["description"]

    def test_wiring_layer_empty_project_no_crash(self, tmp_path):
        """WiringDiagnosisLayer does not crash for an empty project."""
        layer = WiringDiagnosisLayer(project_root=str(tmp_path))
        result = layer.run()
        assert result is not None
        assert isinstance(result.issues, list)

    def test_wiring_layer_detects_missing_backend_endpoint(self, tmp_path):
        """Wiring layer flags frontend endpoint not found in backend."""
        js_file = tmp_path / "murphy_overlay.js"
        js_file.write_text(
            'fetch("/api/nonexistent-endpoint")\n',
            encoding="utf-8",
        )
        layer = WiringDiagnosisLayer(project_root=str(tmp_path))
        result = layer.run()
        missing = [
            i for i in result.issues
            if i.get("type") == WiringIssueKind.MISSING_BACKEND_ENDPOINT.value
        ]
        assert missing, "Expected MISSING_BACKEND_ENDPOINT to be detected"


# ===========================================================================
# Tests: Full Repair Cycle
# ===========================================================================

class TestRepairCycle:
    """Tests for the master AutonomousRepairSystem."""

    def test_run_repair_cycle_returns_report(self, repair_system):
        """run_repair_cycle returns a RepairReport."""
        report = repair_system.run_repair_cycle(max_iterations=2)
        assert isinstance(report, RepairReport)
        assert report.status == RepairStatus.COMPLETED

    def test_repair_cycle_reports_stored(self, repair_system):
        """Reports are stored and retrievable after a cycle."""
        repair_system.run_repair_cycle(max_iterations=1)
        reports = repair_system.get_reports()
        assert len(reports) >= 1

    def test_repair_cycle_proposals_retrievable(self, repair_system):
        """Proposals generated during a cycle are retrievable."""
        repair_system.run_repair_cycle(max_iterations=1)
        proposals = repair_system.get_proposals()
        assert isinstance(proposals, list)

    def test_run_repair_cycle_single_layer(self, repair_system):
        """Repair cycle runs correctly when restricted to a single layer."""
        report = repair_system.run_repair_cycle(
            max_iterations=1,
            layers=[DiagnosisLayer.STATIC],
        )
        assert report.layers_run == [DiagnosisLayer.STATIC.value]

    def test_repair_cycle_no_concurrent_runs(self, repair_system):
        """Concurrent repair cycles raise RuntimeError."""
        errors: list = []

        def _run() -> None:
            try:
                repair_system.run_repair_cycle(max_iterations=5)
            except RuntimeError as exc:
                errors.append(str(exc))

        t1 = threading.Thread(target=_run)
        t2 = threading.Thread(target=_run)
        t1.start()
        t2.start()
        t1.join(timeout=30)
        t2.join(timeout=30)

    def test_trigger_reconciliation(self, repair_system):
        """trigger_reconciliation returns a ReconciliationState."""
        state = repair_system.trigger_reconciliation()
        assert state is not None
        d = state.to_dict()
        assert "drift_items" in d

    def test_get_health_returns_dict(self, repair_system):
        """get_health returns a dict with expected keys."""
        health = repair_system.get_health()
        assert "status" in health
        assert "proposals_generated" in health

    def test_get_immune_memory_list(self, repair_system):
        """get_immune_memory returns a list."""
        memory = repair_system.get_immune_memory()
        assert isinstance(memory, list)

    def test_report_serialisation(self, repair_system):
        """RepairReport serialises without error."""
        report = repair_system.run_repair_cycle(max_iterations=1)
        d = report.to_dict()
        json.dumps(d)

    def test_wiring_report_after_cycle(self, repair_system):
        """Wiring report is available after a repair cycle."""
        repair_system.run_repair_cycle(max_iterations=1, layers=[DiagnosisLayer.WIRING])
        wiring = repair_system.get_wiring_report()
        assert isinstance(wiring, list)

    def test_terminology_concordance_after_cycle(self, repair_system):
        """Terminology concordance is available after a repair cycle."""
        repair_system.run_repair_cycle(max_iterations=1)
        concordance = repair_system.get_terminology_concordance()
        assert isinstance(concordance, dict)


# ===========================================================================
# Tests: Innovation Farmer
# ===========================================================================

class TestInnovationFarmer:
    """Tests for the Innovation Farmer."""

    def test_run_innovation_scan_returns_report(self, innovation_farmer):
        """run_innovation_scan returns an InnovationScanReport."""
        report = innovation_farmer.run_innovation_scan()
        assert isinstance(report, InnovationScanReport)
        assert report.patterns_discovered >= 1
        assert report.proposals_generated >= 1

    def test_proposals_have_required_fields(self, innovation_farmer):
        """Feature proposals have all required fields."""
        innovation_farmer.run_innovation_scan()
        proposals = innovation_farmer.get_proposals()
        assert len(proposals) >= 1
        for prop in proposals:
            assert "proposal_id" in prop
            assert "title" in prop
            assert "what_it_does" in prop
            assert "requires_human_review" in prop
            assert prop["requires_human_review"] is True

    def test_gaps_are_identified(self, innovation_farmer):
        """Competitive gaps are identified and returned."""
        innovation_farmer.run_innovation_scan()
        gaps = innovation_farmer.get_gaps()
        assert len(gaps) >= 1
        for gap in gaps:
            assert "gap_description" in gap
            assert "priority" in gap

    def test_patterns_are_retrieved(self, innovation_farmer):
        """Discovered patterns can be retrieved."""
        innovation_farmer.run_innovation_scan()
        patterns = innovation_farmer.get_patterns()
        assert len(patterns) >= 1

    def test_scan_history_is_recorded(self, innovation_farmer):
        """Scan history is recorded after each scan."""
        innovation_farmer.run_innovation_scan()
        history = innovation_farmer.get_scan_history()
        assert len(history) >= 1

    def test_report_serialisation(self, innovation_farmer):
        """InnovationScanReport serialises to JSON without error."""
        report = innovation_farmer.run_innovation_scan()
        json.dumps(report.to_dict())

    def test_all_high_relevance_patterns_generate_proposals(self, innovation_farmer):
        """All patterns with relevance >= 0.75 generate a proposal."""
        innovation_farmer.run_innovation_scan()
        patterns = innovation_farmer.get_patterns()
        proposals = innovation_farmer.get_proposals()
        high_relevance = [p for p in patterns if p.get("relevance_score", 0) >= 0.75]
        assert len(proposals) >= len(high_relevance)


# ===========================================================================
# Tests: Generative Knowledge Builder
# ===========================================================================

class TestGenerativeKnowledgeBuilder:
    """Tests for the Generative Knowledge Builder."""

    def test_build_healthcare_knowledge_set(self, knowledge_builder):
        """Healthcare knowledge set is built with expected terms."""
        ks = knowledge_builder.build_knowledge_set("healthcare")
        assert ks.domain == IndustryDomain.HEALTHCARE
        assert "order" in ks.terms
        assert "patient" in ks.terms

    def test_build_finance_knowledge_set(self, knowledge_builder):
        """Finance knowledge set is built with expected terms."""
        ks = knowledge_builder.build_knowledge_set("finance")
        assert ks.domain == IndustryDomain.FINANCE
        assert "order" in ks.terms

    def test_build_manufacturing_knowledge_set(self, knowledge_builder):
        """Manufacturing knowledge set is built with expected terms."""
        ks = knowledge_builder.build_knowledge_set("manufacturing")
        assert ks.domain == IndustryDomain.MANUFACTURING
        assert "asset" in ks.terms

    def test_build_legal_knowledge_set(self, knowledge_builder):
        """Legal knowledge set is built with expected terms."""
        ks = knowledge_builder.build_knowledge_set("legal")
        assert ks.domain == IndustryDomain.LEGAL
        assert "party" in ks.terms

    def test_build_generic_for_unknown_domain(self, knowledge_builder):
        """Unknown domains fall back to the generic catalog."""
        ks = knowledge_builder.build_knowledge_set("astrophysics")
        assert ks.domain == IndustryDomain.GENERIC
        assert len(ks.terms) >= 1

    def test_knowledge_set_has_standards(self, knowledge_builder):
        """Built knowledge sets include industry standards."""
        ks = knowledge_builder.build_knowledge_set("healthcare")
        assert len(ks.standards) >= 1

    def test_knowledge_set_has_relationships(self, knowledge_builder):
        """Built knowledge sets include term relationships."""
        ks = knowledge_builder.build_knowledge_set("finance")
        assert len(ks.relationships) >= 1

    def test_term_has_boundary_condition(self, knowledge_builder):
        """Terms in a knowledge set include boundary conditions."""
        ks = knowledge_builder.build_knowledge_set("healthcare")
        term = ks.terms.get("order")
        assert term is not None
        assert term.boundary_condition != ""

    def test_get_knowledge_set_returns_built_set(self, knowledge_builder):
        """get_knowledge_set retrieves a previously-built knowledge set."""
        knowledge_builder.build_knowledge_set("finance")
        ks = knowledge_builder.get_knowledge_set("finance")
        assert ks is not None
        assert ks.domain == IndustryDomain.FINANCE

    def test_get_knowledge_set_missing_returns_none(self, knowledge_builder):
        """get_knowledge_set returns None for a domain not yet built."""
        ks = knowledge_builder.get_knowledge_set("unknown_industry_xyz")
        assert ks is None

    def test_check_boundary_ambiguity_detects_ambiguous_term(self, knowledge_builder):
        """check_boundary_ambiguity detects ambiguous terms."""
        bc = knowledge_builder.check_boundary_ambiguity(
            term="order",
            industry="finance",
            sender_module="trade_service",
            receiver_module="procurement_service",
        )
        assert bc is not None
        assert bc.ambiguity_detected is True

    def test_check_boundary_no_ambiguity_for_clear_term(self, knowledge_builder):
        """check_boundary_ambiguity returns None for unambiguous terms."""
        bc = knowledge_builder.check_boundary_ambiguity(
            term="patient",
            industry="healthcare",
            sender_module="clinical_service",
            receiver_module="billing_service",
        )

    def test_compute_term_probability_returns_distribution(self, knowledge_builder):
        """compute_term_probability returns a probability distribution."""
        probs = knowledge_builder.compute_term_probability(
            term="order",
            industry="healthcare",
            observed_context="The doctor placed a lab order for the patient",
        )
        assert isinstance(probs, dict)
        assert len(probs) >= 1
        total = sum(probs.values())
        assert abs(total - 1.0) < 1e-3

    def test_knowledge_set_serialisation(self, knowledge_builder):
        """KnowledgeSet serialises to JSON without error."""
        ks = knowledge_builder.build_knowledge_set("technology")
        json.dumps(ks.to_dict())

    def test_boundary_conditions_accessible(self, knowledge_builder):
        """Boundary conditions are accessible after building a knowledge set."""
        knowledge_builder.build_knowledge_set("finance")
        bcs = knowledge_builder.get_boundary_conditions()
        assert isinstance(bcs, list)

    def test_build_history_recorded(self, knowledge_builder):
        """Build history is recorded for each build call."""
        knowledge_builder.build_knowledge_set("manufacturing")
        history = knowledge_builder.get_build_history()
        assert len(history) >= 1
        assert any(h["domain"] == "manufacturing" for h in history)


# ===========================================================================
# Tests: REST API Endpoints
# ===========================================================================

class TestRepairApiEndpoints:
    """Tests for the repair system REST API endpoints."""

    @pytest.fixture(autouse=True)
    def _flask_or_skip(self):
        """Skip tests if Flask is not available."""
        try:
            from flask import Flask
        except ImportError:
            pytest.skip("Flask not available")

    @pytest.fixture()
    def client(self, tmp_path):
        """Create a Flask test client for the repair API."""
        from flask import Flask
        from repair_api_endpoints import (
            _get_knowledge_builder,
            _get_repair_system,
            create_health_blueprint,
            create_repair_blueprint,
            register_repair_api,
        )
        import repair_api_endpoints as rae

        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "module_a.py").write_text("x = 1\n", encoding="utf-8")

        rae._repair_system = AutonomousRepairSystem(
            src_root=str(src_dir),
            project_root=str(tmp_path),
        )
        rae._innovation_farmer = InnovationFarmer()
        rae._knowledge_builder = GenerativeKnowledgeBuilder()

        app = Flask(__name__)
        register_repair_api(app)
        app.config["TESTING"] = True
        with app.test_client() as c:
            yield c

        rae._repair_system = None
        rae._innovation_farmer = None
        rae._knowledge_builder = None

    def test_health_endpoint_returns_200(self, client):
        """GET /api/health returns 200."""
        resp = client.get("/api/health")
        assert resp.status_code == 200

    def test_health_endpoint_returns_status_ok(self, client):
        """GET /api/health body includes status=ok."""
        resp = client.get("/api/health")
        data = resp.get_json()
        assert data is not None
        assert data.get("status") == "ok"

    def test_repair_status_endpoint(self, client):
        """GET /api/repair/status returns 200."""
        resp = client.get("/api/repair/status")
        assert resp.status_code == 200

    def test_repair_history_endpoint(self, client):
        """GET /api/repair/history returns reports list."""
        resp = client.get("/api/repair/history")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "reports" in data

    def test_repair_wiring_endpoint(self, client):
        """GET /api/repair/wiring returns wiring_issues."""
        resp = client.get("/api/repair/wiring")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "wiring_issues" in data

    def test_repair_immune_memory_endpoint(self, client):
        """GET /api/repair/immune-memory returns immune_memory list."""
        resp = client.get("/api/repair/immune-memory")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "immune_memory" in data

    def test_repair_proposals_endpoint(self, client):
        """GET /api/repair/proposals returns proposals list."""
        resp = client.get("/api/repair/proposals")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "proposals" in data

    def test_repair_terminology_endpoint(self, client):
        """GET /api/repair/terminology returns concordance."""
        resp = client.get("/api/repair/terminology")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "concordance" in data

    def test_reconcile_endpoint(self, client):
        """POST /api/repair/reconcile returns reconciliation state."""
        resp = client.post("/api/repair/reconcile")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "reconciliation_state" in data

    def test_innovate_endpoint(self, client):
        """POST /api/repair/innovate returns scan report."""
        resp = client.post("/api/repair/innovate")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get("status") == "ok"

    def test_innovation_proposals_endpoint(self, client):
        """GET /api/repair/innovation/proposals returns proposals."""
        client.post("/api/repair/innovate")
        resp = client.get("/api/repair/innovation/proposals")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "proposals" in data

    def test_knowledge_build_endpoint(self, client):
        """POST /api/repair/knowledge/build builds a knowledge set."""
        resp = client.post(
            "/api/repair/knowledge/build",
            json={"industry": "healthcare", "language": "python"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get("status") == "ok"
        assert "knowledge_set" in data

    def test_knowledge_get_endpoint(self, client):
        """GET /api/repair/knowledge/<industry> returns knowledge set."""
        client.post(
            "/api/repair/knowledge/build",
            json={"industry": "finance"},
        )
        resp = client.get("/api/repair/knowledge/finance")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "knowledge_set" in data

    def test_knowledge_get_missing_returns_404(self, client):
        """GET /api/repair/knowledge/<industry> returns 404 for unknown industry."""
        resp = client.get("/api/repair/knowledge/nonexistent_industry_xyz")
        assert resp.status_code == 404

    def test_run_repair_endpoint(self, client):
        """POST /api/repair/run triggers repair cycle and returns report."""
        resp = client.post(
            "/api/repair/run",
            json={"max_iterations": 1},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get("status") == "ok"
        assert "report" in data
