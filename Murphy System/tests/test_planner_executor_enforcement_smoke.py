from src.murphy_core.contracts import ControlExpansion, CoreRequest, GateEvaluation, RouteType
from src.murphy_core.executor import CoreExecutor
from src.murphy_core.planner import CorePlanner


def test_compile_plan_carries_family_constraints_and_allowed_actions():
    planner = CorePlanner()
    expansion = ControlExpansion(
        request_id='req-123',
        selected_route=RouteType.SWARM,
        selected_module_families=['swarm', 'operator'],
        execution_constraints={'primary_family': 'swarm'},
        allowed_actions=[{'action': 'respond'}, {'action': 'swarm_execute'}],
    )

    plan = planner.compile_plan(expansion, gate_results=[], source_message='run swarm task')

    assert plan.route == RouteType.SWARM
    assert plan.selected_module_families == ['swarm', 'operator']
    assert plan.execution_constraints['primary_family'] == 'swarm'
    assert {'action': 'swarm_execute'} in plan.allowed_actions
    assert plan.enforcement_summary['blocked'] is False


def test_compile_plan_blocks_when_primary_family_drift_exists():
    planner = CorePlanner()
    expansion = ControlExpansion(
        request_id='req-124',
        selected_route=RouteType.HYBRID,
        selected_module_families=['operator'],
        execution_constraints={'primary_family': 'swarm'},
        allowed_actions=[{'action': 'respond'}, {'action': 'execute'}],
    )

    plan = planner.compile_plan(expansion, gate_results=[], source_message='do a hybrid task')

    assert plan.blocked is True
    assert 'primary_family_missing_from_selected_module_families' in plan.enforcement_summary['reasons']


async def test_executor_blocks_swarm_route_when_allowed_actions_drift():
    executor = CoreExecutor()
    request = CoreRequest.new(message='run swarm task', mode='execute')
    planner = CorePlanner()
    expansion = ControlExpansion(
        request_id=request.request_id,
        selected_route=RouteType.SWARM,
        selected_module_families=['swarm'],
        execution_constraints={'primary_family': 'swarm'},
        allowed_actions=[{'action': 'respond'}],
    )
    plan = planner.compile_plan(expansion, gate_results=[], source_message=request.message)

    result = await executor.execute(request, plan)

    assert result['success'] is False
    assert result['status'] == 'blocked'
    assert 'swarm_route_missing_swarm_execute_action' in result['enforcement_summary']['reasons'] or 'executor_swarm_route_missing_swarm_execute_action' in result['enforcement_summary']['reasons']


async def test_executor_simulated_path_preserves_enforcement_metadata():
    executor = CoreExecutor()
    executor._murphy = None
    executor._swarm = None
    request = CoreRequest.new(message='run deterministic task', mode='execute')
    planner = CorePlanner()
    expansion = ControlExpansion(
        request_id=request.request_id,
        selected_route=RouteType.DETERMINISTIC,
        selected_module_families=['operator'],
        execution_constraints={'primary_family': 'operator'},
        allowed_actions=[{'action': 'respond'}, {'action': 'execute'}],
    )
    plan = planner.compile_plan(expansion, gate_results=[], source_message=request.message)

    result = await executor.execute(request, plan)

    assert result['success'] is True
    assert result['status'] == 'simulated'
    assert result['selected_module_families'] == ['operator']
    assert result['execution_constraints']['primary_family'] == 'operator'
    assert result['enforcement_summary']['blocked'] is False
