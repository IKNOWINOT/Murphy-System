import importlib.util
from pathlib import Path


def load_runtime_module():
    runtime_dir = Path(__file__).resolve().parent.parent
    candidates = list(runtime_dir.glob("murphy_system_*_runtime.py"))
    if not candidates:
        raise RuntimeError("Unable to locate Murphy runtime module")
    module_path = candidates[0]
    spec = importlib.util.spec_from_file_location("murphy_system_runtime", module_path)
    module = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        raise RuntimeError("Unable to load Murphy runtime module")
    spec.loader.exec_module(module)
    return module


class DummyOrchestrator:
    async def phase1_generative_setup(self):
        return {}

    async def phase2_production_execution(self):
        return {}


def test_dynamic_implementation_plan_requires_requirements():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    doc = runtime.LivingDocument("doc-1", "Test", "content", "request")
    doc.gates = [{"status": "blocked"}]
    doc.generated_tasks = [{"stage": "automation_design", "description": "Design automation"}]
    operations_plan = murphy._build_operations_plan(doc)
    learning_loop = murphy._build_learning_loop_plan("Test request", {}, {})
    trigger_plan = {"status": "unavailable"}
    org_chart_plan = {"coverage_summary": {"status": "partial"}}
    sensor_plan = {"region": "global", "primary_regulatory_source": {"id": "regulatory_source"}}
    delivery_readiness = murphy._build_delivery_readiness(doc, org_chart_plan, learning_loop, sensor_plan, [])

    plan = murphy._build_dynamic_implementation_plan(
        doc,
        "Test request",
        [],
        learning_loop,
        operations_plan,
        delivery_readiness,
        [],
        sensor_plan,
        org_chart_plan,
        trigger_plan
    )

    assert plan["status"] == "needs_info"
    assert plan["execution_strategy"] == "simulation"
    policy = murphy._build_execution_policy(plan, {})
    assert policy["enforced"] is True
    assert policy["status"] == "needs_wiring"
    assert policy["approval_required"] is False
    assert policy["execution_blocked"] is True
    relaxed_policy = murphy._build_execution_policy(plan, {"enforce_policy": False})
    assert relaxed_policy["enforced"] is False
    stages = {stage["id"]: stage for stage in plan["stages"]}
    assert stages["requirements_identification"]["status"] == "needs_info"
    assert stages["confidence_approval"]["status"] == "needs_info"
    assert stages["gate_alignment"]["status"] == "blocked"
    assert stages["gate_sequencing"]["status"] == "blocked"
    assert stages["compliance_review"]["status"] == "blocked"
    assert stages["swarm_generation"]["status"] == "needs_wiring"
    assert stages["integration_wiring"]["status"] == "needs_wiring"
    assert stages["automation_loop"]["status"] == "needs_info"
    assert stages["multi_loop_schedule"]["status"] == "needs_info"
    assert stages["trigger_schedule"]["status"] == "needs_wiring"
    assert stages["monitoring_feedback"]["status"] == "ready"
    assert stages["output_delivery"]["status"] == "needs_info"
    assert stages["rollback_plan"]["status"] == "needs_wiring"
    assert plan["chain_plan"]["mode"] == "adaptive"
    assert "requirements_identification" in plan["chain_plan"]["control_points"]
    wiring_ids = {gap["id"] for gap in plan["wiring_gaps"]}
    assert {"execution_plan", "swarm_generation", "integration_wiring", "trigger_schedule", "rollback_plan"}.issubset(
        wiring_ids
    )
    execution_gap = next(gap for gap in plan["wiring_gaps"] if gap["id"] == "execution_plan")
    assert execution_gap["label"] == "Execution planning"
    assert execution_gap["owner"] == "automation_engine"
    assert execution_gap["reason"] == "Wire the orchestrator or MFGC adapter for live execution."
    info_ids = {gap["id"] for gap in plan["information_gaps"]}
    assert {"requirements_identification", "output_delivery"}.issubset(info_ids)
    assert "confidence_approval" in info_ids
    requirements_gap = next(gap for gap in plan["information_gaps"] if gap["id"] == "requirements_identification")
    assert requirements_gap["label"] == "Requirements identification"
    assert requirements_gap["owner"] == "executive_branch"
    assert requirements_gap["reason"] == "Collect onboarding answers to finalize requirements."
    training = plan["chain_plan"]["training_patterns"]
    assert training["threshold"] == murphy.HIGH_CONFIDENCE_THRESHOLD
    assert len(training["patterns"]) == len(plan["chain_plan"]["links"])
    assert all(
        pattern["confidence"] >= training["threshold"]
        for pattern in training["high_confidence_paths"]
    )
    wingman = training["wingman_protocol"]
    assert wingman["status"] in {"needs_info", "ready"}
    assert wingman["action_side"]["role"] == "primary_executor"
    assert wingman["validator_side"]["role"] == "deterministic_validator"
    assert "compute_plane_validation" in wingman["deterministic_checks"]
    execution_routes = plan["chain_plan"]["execution_routes"]
    assert len(execution_routes["priority_sequence"]) == len(plan["stages"])
    assert execution_routes["summary"]["blocked"] > 0
    assert len(execution_routes["adaptive_routes"]) == len(plan["chain_plan"]["links"])
    graphing = training["graphing"]
    assert "executive_branch" in graphing["subjects"]
    subject_summary = {entry["subject"]: entry for entry in graphing["subject_summary"]}
    assert subject_summary["executive_branch"]["paths"] >= 1
    graph_ids = [graph["id"] for graph in graphing["graphs"]]
    assert graph_ids == ["all_paths", "high_confidence", "fastest_paths", "subject_condensation"]
    assert graphing["graphs"][0]["paths"] == training["patterns"]
    condensation = graphing["graphs"][3]
    assert condensation["axes"]["humidity"] == "load_index"
    assert len(condensation["points"]) == len(training["patterns"])
    assert "subject matter" in condensation["purpose"].lower()
    subjects = {point["subject"] for point in condensation["points"]}
    assert subjects.issubset(set(graphing["subjects"]))


def test_dynamic_implementation_plan_ready_with_orchestrator():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()

    murphy.orchestrator = DummyOrchestrator()
    # Keep flow steps empty so requirements status is driven by explicit answers
    # instead of default onboarding prompts.
    murphy.flow_steps = []
    murphy.swarm_system = object()
    murphy.integration_engine = object()
    doc = runtime.LivingDocument("doc-2", "Test", "content", "request")
    doc.confidence = 0.9
    doc.gates = [{"status": "open"}]
    doc.generated_tasks = [{"stage": "automation_design", "description": "Design automation"}]
    operations_plan = murphy._build_operations_plan(doc)
    learning_loop = murphy._build_learning_loop_plan("Automation", {"answers": {}}, {})
    trigger_plan = {"status": "scheduled"}
    org_chart_plan = {"coverage_summary": {"total_deliverables": 100, "uncovered_deliverables": 0}}
    sensor_plan = {"region": "global", "primary_regulatory_source": {"id": "regulatory_source"}}
    delivery_readiness = murphy._build_delivery_readiness(doc, org_chart_plan, learning_loop, sensor_plan, [])

    plan = murphy._build_dynamic_implementation_plan(
        doc,
        "Automation",
        [{"id": "compute_plane"}],
        learning_loop,
        operations_plan,
        delivery_readiness,
        [],
        sensor_plan,
        org_chart_plan,
        trigger_plan
    )

    assert plan["execution_strategy"] == "orchestrator"
    # Plan status depends on delivery adapter wiring
    assert plan["status"] in {"ready", "needs_wiring"}
    policy = murphy._build_execution_policy(plan, {})
    assert policy["status"] in {"ready", "needs_wiring"}
    assert policy["approval_required"] is False
    stage_map = {stage["id"]: stage for stage in plan["stages"]}
    assert stage_map["gate_alignment"]["status"] == "ready"
    assert stage_map["gate_sequencing"]["status"] == "ready"
    assert stage_map["compliance_review"]["status"] == "ready"
    assert stage_map["confidence_approval"]["status"] == "ready"
    assert stage_map["swarm_generation"]["status"] == "ready"
    assert stage_map["integration_wiring"]["status"] == "ready"
    assert stage_map["automation_loop"]["status"] == "ready"
    assert stage_map["multi_loop_schedule"]["status"] == "ready"
    assert stage_map["trigger_schedule"]["status"] == "ready"
    assert stage_map["monitoring_feedback"]["status"] == "ready"
    assert plan["chain_plan"]["mode"] == "adaptive"
    training = plan["chain_plan"]["training_patterns"]
    assert training["threshold"] == murphy.HIGH_CONFIDENCE_THRESHOLD
    assert len(training["patterns"]) == len(plan["chain_plan"]["links"])
    wingman = training["wingman_protocol"]
    assert wingman["status"] == "ready"
    assert wingman["action_side"]["subjects"]
    assert wingman["validator_side"]["subjects"]
    graphing = training["graphing"]
    execution_routes = plan["chain_plan"]["execution_routes"]
    summary = {entry["subject"]: entry for entry in graphing["subject_summary"]}
    assert summary["automation_engine"]["average_seconds"] >= 0


def test_dynamic_implementation_plan_partial_wiring():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()

    murphy.orchestrator = DummyOrchestrator()
    murphy.flow_steps = []
    # Simulate partial wiring: orchestrator is available, swarm/integration are not.
    murphy.swarm_system = None
    murphy.integration_engine = None
    doc = runtime.LivingDocument("doc-3", "Test", "content", "request")
    doc.confidence = 0.92
    doc.gates = [{"status": "open"}]
    doc.generated_tasks = [{"stage": "automation_design", "description": "Design automation"}]
    operations_plan = murphy._build_operations_plan(doc)
    learning_loop = murphy._build_learning_loop_plan("Automation", {"answers": {"goal": "automate"}}, {})
    trigger_plan = {"status": "scheduled"}
    org_chart_plan = {"coverage_summary": {"total_deliverables": 2, "uncovered_deliverables": 0}}
    sensor_plan = {"region": "global", "primary_regulatory_source": {"id": "regulatory_source"}}
    delivery_readiness = murphy._build_delivery_readiness(doc, org_chart_plan, learning_loop, sensor_plan, [])

    plan = murphy._build_dynamic_implementation_plan(
        doc,
        "Automation",
        [{"id": "compute_plane"}],
        learning_loop,
        operations_plan,
        delivery_readiness,
        [],
        sensor_plan,
        org_chart_plan,
        trigger_plan
    )

    assert plan["execution_strategy"] == "orchestrator"
    assert plan["status"] == "needs_wiring"
    stage_map = {stage["id"]: stage for stage in plan["stages"]}
    assert stage_map["execution_plan"]["status"] == "ready"
    assert stage_map["swarm_generation"]["status"] == "needs_wiring"
    assert stage_map["integration_wiring"]["status"] == "needs_wiring"
    wiring_ids = {gap["id"] for gap in plan["wiring_gaps"]}
    assert {"swarm_generation", "integration_wiring"}.issubset(wiring_ids)
    swarm_gap = next(gap for gap in plan["wiring_gaps"] if gap["id"] == "swarm_generation")
    integration_gap = next(gap for gap in plan["wiring_gaps"] if gap["id"] == "integration_wiring")
    assert "swarm" in swarm_gap["reason"].lower()
    assert "integration" in integration_gap["reason"].lower()
