from robotics import (
    ActuatorCommand,
    CommandStatus,
    ConnectionConfig,
    PulseConfig,
    PulseController,
    PulsePhase,
    RobotConfig,
    RobotRegistry,
    RobotType,
)


def make_registry() -> RobotRegistry:
    registry = RobotRegistry()
    registry.register(
        RobotConfig(
            robot_id="bot-1",
            name="Test Robot",
            robot_type=RobotType.ROS2,
            connection=ConnectionConfig(hostname="localhost"),
            capabilities=["sense_distance", "sense_battery"],
        )
    )
    return registry


def make_command(robot_id: str = "bot-1") -> ActuatorCommand:
    return ActuatorCommand(
        robot_id=robot_id,
        actuator_id="base",
        command_type="move_forward",
        parameters={"speed": 0.1, "duration_seconds": 0.1},
        timeout_seconds=1.0,
    )


def test_pulse_controller_executes_command_after_scan_constraint_and_action() -> None:
    controller = PulseController(
        registry=make_registry(),
        config=PulseConfig(tick_hz=10.0, stale_sensor_seconds=5.0),
    )
    command_id = controller.submit_command(make_command(), source="unit_test", priority=1)

    scan_report = controller.step(PulsePhase.SCAN)
    flow_report = controller.step(PulsePhase.FLOW)
    constraint_report = controller.step(PulsePhase.CONSTRAINT)
    action_report = controller.step(PulsePhase.ACTION)

    assert scan_report.phase == PulsePhase.SCAN
    assert flow_report.phase == PulsePhase.FLOW
    assert constraint_report.approved_commands == 1
    assert action_report.executed_commands == 1

    history = controller.get_command_history()
    assert len(history) == 1
    assert history[0]["command_id"] == command_id
    assert history[0]["status"] == CommandStatus.EXECUTED.value
    assert history[0]["robot_id"] == "bot-1"


def test_pulse_controller_blocks_unknown_robot_command() -> None:
    controller = PulseController(registry=make_registry(), config=PulseConfig(stale_sensor_seconds=5.0))
    controller.submit_command(make_command(robot_id="missing-bot"), source="unit_test")

    controller.step(PulsePhase.SCAN)
    report = controller.step(PulsePhase.CONSTRAINT)

    assert report.blocked_commands == 1
    history = controller.get_command_history()
    assert history[0]["status"] == CommandStatus.BLOCKED.value
    assert "unknown or unscanned robot" in history[0]["reason"]


def test_pulse_controller_emergency_stop_blocks_pending_commands() -> None:
    controller = PulseController(registry=make_registry(), config=PulseConfig(stale_sensor_seconds=5.0))
    controller.step(PulsePhase.SCAN)
    controller.submit_command(make_command(), source="unit_test")

    stop_results = controller.request_emergency_stop("test stop")

    assert stop_results == {"bot-1": True}
    snapshot = controller.get_context_snapshot()
    assert snapshot["emergency_stop"] is True
    history = controller.get_command_history()
    assert history[0]["status"] == CommandStatus.BLOCKED.value
    assert history[0]["reason"] == "test stop"


def test_custom_safety_rule_can_block_high_speed_command() -> None:
    controller = PulseController(registry=make_registry(), config=PulseConfig(stale_sensor_seconds=5.0))

    def speed_limit_rule(queued, context):
        if queued.command.parameters.get("speed", 0) > 0.5:
            return "speed above local limit"
        return None

    controller.add_safety_rule(speed_limit_rule)
    controller.submit_command(
        ActuatorCommand(
            robot_id="bot-1",
            actuator_id="base",
            command_type="move_forward",
            parameters={"speed": 0.9},
            timeout_seconds=1.0,
        )
    )

    controller.step(PulsePhase.SCAN)
    report = controller.step(PulsePhase.CONSTRAINT)

    assert report.blocked_commands == 1
    assert controller.get_command_history()[0]["reason"] == "speed above local limit"
