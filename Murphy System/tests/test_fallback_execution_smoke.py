import asyncio

from src.murphy_core.contracts import ControlExpansion, CoreRequest, GateDecision, GateEvaluation, RouteType
from src.murphy_core.executor import CoreExecutor
from src.murphy_core.planner import CorePlanner


def test_compile_plan_defaults_fallback_policy_to_explicit_opt_in():
    planner = CorePlanner()
    expansion = ControlExpansion(
        request_id='req-fallback-defaults',
        selected_route=RouteType.DETERMINISTIC,
        selected_module_families=['operator'],
        execution_constraints={'primary_family': 'operator'},
        allowed_actions=[{'action': 'respond'}, {'action': 'execute'}],
        fallback_policy={
            'fallback_route': 'legacy_adapter',
            'allow_automatic_fallback': False,
            'fallback_on_block': True,
            'fallback_on_review': False,
            'fallback_on_hitl': False,
        },
    )
    gate_results = [
        GateEvaluation(gate_name='security', decision=GateDecision.BLOCK, rationale=['blocked'])
    ]

    plan = planner.compile_plan(expansion, gate_results=gate_results, source_message='blocked task')

    assert plan.gate_enforcement_summary['fallback_policy']['allow_automatic_fallback'] is False
    assert plan.gate_enforcement_summary['fallback_available'] is True


def test_executor_performs_legacy_adapter_fallback_when_explicitly_allowed():
    executor = CoreExecutor()
    executor._murphy = None
    executor._swarm = None
    planner = CorePlanner()
    request = CoreRequest.new(message='blocked task', mode='execute')
    expansion = ControlExpansion(
        request_id=request.request_id,
        selected_route=RouteType.DETERMINISTIC,
        selected_module_families=['operator'],
        execution_constraints={'primary_family': 'operator'},
        allowed_actions=[{'action': 'respond'}, {'action': 'execute'}],
        fallback_policy={
            'fallback_route': 'legacy_adapter',
            'allow_automatic_fallback': True,
            'fallback_on_block': True,
            'fallback_on_review': False,
            'fallback_on_hitl': False,
        },
    )
    gate_results = [
        GateEvaluation(gate_name='security', decision=GateDecision.BLOCK, rationale=['blocked'])
    ]
    plan = planner.compile_plan(expansion, gate_results=gate_results, source_message=request.message)

    result = asyncio.run(executor.execute(request, plan))

    assert result['success'] is True
    assert result['status'] == 'fallback_completed'
    assert result['fallback_route'] == 'legacy_adapter'
    assert result['fallback_result']['adapter'] == 'legacy_adapter'


def test_executor_does_not_fallback_for_review_even_if_route_exists():
    executor = CoreExecutor()
    executor._murphy = None
    executor._swarm = None
    planner = CorePlanner()
    request = CoreRequest.new(message='review task', mode='execute')
    expansion = ControlExpansion(
        request_id=request.request_id,
        selected_route=RouteType.DETERMINISTIC,
        selected_module_families=['operator'],
        execution_constraints={'primary_family': 'operator'},
        allowed_actions=[{'action': 'respond'}, {'action': 'execute'}],
        fallback_policy={
            'fallback_route': 'legacy_adapter',
            'allow_automatic_fallback': True,
            'fallback_on_block': True,
            'fallback_on_review': False,
            'fallback_on_hitl': False,
        },
    )
    gate_results = [
        GateEvaluation(gate_name='security', decision=GateDecision.REVIEW, rationale=['review needed'])
    ]
    plan = planner.compile_plan(expansion, gate_results=gate_results, source_message=request.message)

    result = asyncio.run(executor.execute(request, plan))

    assert result['success'] is False
    assert result['status'] == 'review_required'
    assert 'fallback_result' not in result


def test_executor_does_not_fallback_for_hitl_even_if_route_exists():
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
        fallback_policy={
            'fallback_route': 'legacy_adapter',
            'allow_automatic_fallback': True,
            'fallback_on_block': True,
            'fallback_on_review': False,
            'fallback_on_hitl': False,
        },
    )
    gate_results = [
        GateEvaluation(gate_name='hitl', decision=GateDecision.REQUIRES_HITL, rationale=['hitl needed'])
    ]
    plan = planner.compile_plan(expansion, gate_results=gate_results, source_message=request.message)

    result = asyncio.run(executor.execute(request, plan))

    assert result['success'] is False
    assert result['status'] == 'hitl_required'
    assert 'fallback_result' not in result


def test_executor_does_not_fallback_for_planner_drift_without_blocking_gate():
    executor = CoreExecutor()
    executor._murphy = None
    executor._swarm = None
    planner = CorePlanner()
    request = CoreRequest.new(message='drift task', mode='execute')
    expansion = ControlExpansion(
        request_id=request.request_id,
        selected_route=RouteType.DETERMINISTIC,
        selected_module_families=['operator'],
        execution_constraints={'primary_family': 'swarm'},
        allowed_actions=[{'action': 'respond'}, {'action': 'execute'}],
        fallback_policy={
            'fallback_route': 'legacy_adapter',
            'allow_automatic_fallback': True,
            'fallback_on_block': True,
            'fallback_on_review': False,
            'fallback_on_hitl': False,
        },
    )
    plan = planner.compile_plan(expansion, gate_results=[], source_message=request.message)

    result = asyncio.run(executor.execute(request, plan))

    assert result['success'] is False
    assert result['status'] == 'blocked'
    assert 'fallback_result' not in result
