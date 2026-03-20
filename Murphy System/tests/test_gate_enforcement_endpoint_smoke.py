import asyncio

from src.murphy_core.contracts import ControlExpansion, CoreRequest, GateDecision, GateEvaluation, RouteType
from src.murphy_core.executor import CoreExecutor
from src.murphy_core.planner import CorePlanner


def test_compile_plan_marks_review_gate_as_enforced_pause():
    planner = CorePlanner()
    expansion = ControlExpansion(
        request_id='req-review',
        selected_route=RouteType.DETERMINISTIC,
        selected_module_families=['operator'],
        execution_constraints={'primary_family': 'operator'},
        allowed_actions=[{'action': 'respond'}, {'action': 'execute'}],
        fallback_policy={'fallback_route': 'legacy_adapter'},
    )
    gate_results = [
        GateEvaluation(gate_name='security', decision=GateDecision.REVIEW, rationale=['review needed'])
    ]

    plan = planner.compile_plan(expansion, gate_results=gate_results, source_message='reviewed task')

    assert plan.blocked is True
    assert plan.gate_enforcement_summary['requires_review'] is True
    assert plan.gate_enforcement_summary['fallback_route'] == 'legacy_adapter'


def test_compile_plan_marks_hitl_gate_as_enforced_pause():
    planner = CorePlanner()
    expansion = ControlExpansion(
        request_id='req-hitl',
        selected_route=RouteType.DETERMINISTIC,
        selected_module_families=['operator'],
        execution_constraints={'primary_family': 'operator'},
        allowed_actions=[{'action': 'respond'}, {'action': 'execute'}],
        fallback_policy={'fallback_route': 'legacy_adapter'},
    )
    gate_results = [
        GateEvaluation(gate_name='hitl', decision=GateDecision.REQUIRES_HITL, rationale=['hitl needed'])
    ]

    plan = planner.compile_plan(expansion, gate_results=gate_results, source_message='hitl task')

    assert plan.blocked is True
    assert plan.gate_enforcement_summary['requires_hitl'] is True
    assert plan.gate_enforcement_summary['fallback_available'] is True


def test_executor_returns_review_required_without_executing():
    executor = CoreExecutor()
    executor._murphy = None
    executor._swarm = None
    planner = CorePlanner()
    request = CoreRequest.new(message='reviewed task', mode='execute')
    expansion = ControlExpansion(
        request_id=request.request_id,
        selected_route=RouteType.DETERMINISTIC,
        selected_module_families=['operator'],
        execution_constraints={'primary_family': 'operator'},
        allowed_actions=[{'action': 'respond'}, {'action': 'execute'}],
        fallback_policy={'fallback_route': 'legacy_adapter'},
    )
    gate_results = [
        GateEvaluation(gate_name='security', decision=GateDecision.REVIEW, rationale=['review needed'])
    ]
    plan = planner.compile_plan(expansion, gate_results=gate_results, source_message=request.message)

    result = asyncio.run(executor.execute(request, plan))

    assert result['success'] is False
    assert result['status'] == 'review_required'
    assert result['gate_enforcement_summary']['requires_review'] is True
    assert result['fallback_policy']['fallback_route'] == 'legacy_adapter'


def test_executor_returns_hitl_required_without_executing():
    executor = CoreExecutor()
    executor._murphy = None
    executor._swarm = None
    planner = CorePlanner()
    request = CoreRequest.new(message='hitl task', mode='execute')
    expansion = ControlExpansion(
        request_id=request.request_id,
        selected_route=RouteType.DETERMINISTIC,
        selected_module_families=['operator'],
        execution_constraints={'primary_family': 'operator'},
        allowed_actions=[{'action': 'respond'}, {'action': 'execute'}],
        fallback_policy={'fallback_route': 'legacy_adapter'},
    )
    gate_results = [
        GateEvaluation(gate_name='hitl', decision=GateDecision.REQUIRES_HITL, rationale=['hitl needed'])
    ]
    plan = planner.compile_plan(expansion, gate_results=gate_results, source_message=request.message)

    result = asyncio.run(executor.execute(request, plan))

    assert result['success'] is False
    assert result['status'] == 'hitl_required'
    assert result['gate_enforcement_summary']['requires_hitl'] is True
    assert result['fallback_policy']['fallback_route'] == 'legacy_adapter'
