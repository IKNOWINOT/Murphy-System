"""Minimal demo for the Murphy robotics PulseController.

Run from the repository root with:

    python examples/robot_pulse_controller_demo.py

The demo uses stub protocol clients, so no robot hardware is required.
"""

from robotics import (
    ActuatorCommand,
    ConnectionConfig,
    PulseConfig,
    PulseController,
    RobotConfig,
    RobotRegistry,
    RobotType,
)


def main() -> None:
    registry = RobotRegistry()
    registry.register(
        RobotConfig(
            robot_id="reason-sim-01",
            name="Reason Simulation",
            robot_type=RobotType.ROS2,
            connection=ConnectionConfig(hostname="localhost"),
            capabilities=["sense_distance", "sense_battery"],
        )
    )

    controller = PulseController(
        registry=registry,
        config=PulseConfig(tick_hz=4.0, max_commands_per_action_phase=1),
    )

    controller.submit_command(
        ActuatorCommand(
            robot_id="reason-sim-01",
            actuator_id="base",
            command_type="move_forward",
            parameters={"speed": 0.2, "duration_seconds": 0.5},
            timeout_seconds=2.0,
        ),
        source="demo_agent",
        priority=10,
    )

    for _ in range(4):
        report = controller.step()
        print(f"tick={report.tick} phase={report.phase.value} queued={report.queued_commands} "
              f"approved={report.approved_commands} executed={report.executed_commands} "
              f"blocked={report.blocked_commands}")

    print("history:", controller.get_command_history())


if __name__ == "__main__":
    main()
