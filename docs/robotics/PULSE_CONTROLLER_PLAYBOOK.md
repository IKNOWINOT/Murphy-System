# Murphy Robotics Pulse Controller Playbook

## Purpose

The `PulseController` is a controller module for robots that turns an AI agent from a direct motor commander into a supervised participant inside a deterministic robot nervous system. The design matches the pulse metaphor: the robot keeps a recursive refresh loop running around perception, information flow, constraints, and action. The agent can think continuously and submit command intent, but only the controller decides when a physical command is safe enough to dispatch.

This is the difference between an LLM loop and a robot-ready agent. A language model loop can reason, plan, and talk, but a robot needs eyes, reflexes, body-state awareness, safety constraints, timing, and a hard boundary between thought and actuation. The pulse controller provides that boundary.

## Core Metaphor

Think of the control loop like a jump rope or clock face. The rope is always rotating. Different positions represent different kinds of work.

At **6 o'clock**, the system performs `SCAN`. This is the perception refresh. The controller polls sensors, refreshes robot status, updates known robot IDs, and stores the newest readings in `PulseContext.sensor_cache`. This is the robot opening its eyes and checking proprioception.

At **3 o'clock**, the system performs `FLOW`. This is the information routing phase. The controller updates working memory counts and invokes any attached phase hooks that feed agent memory, telemetry, dashboards, learned policies, or planning systems. This is not where motors move. It is where information circulates through the nervous system.

At **9 o'clock**, the system performs `CONSTRAINT`. This is the safety gate. Commands submitted by AI agents, planners, or services are checked against the current context. The built-in rule blocks commands when the robot is unknown, unscanned, disconnected, stale, in emergency stop, or carrying an invalid timeout. Custom rules can block commands for speed limits, geofences, battery thresholds, human proximity, workspace limits, tool locks, or policy restrictions.

At **12 o'clock**, the system performs `ACTION`. This is the only phase that dispatches physical actuator commands. The controller executes only commands that survived `CONSTRAINT`, and it limits how many commands can be dispatched per action phase.

## Why This Pattern Already Exists in Robotics

This concept is related to several established patterns. Robotics systems commonly use control loops, sense-plan-act architectures, behavior trees, subsumption layers, real-time schedulers, watchdogs, safety interlocks, blackboards, and robotics middleware such as ROS/ROS 2 executors. Industrial systems also use programmable logic controller scan cycles where inputs are read, logic is evaluated, and outputs are written in a repeated deterministic loop.

The Murphy `PulseController` packages those ideas in an agent-friendly way. It gives LLMs and autonomous agents a simple rule: do not command hardware directly. Submit intent to the pulse controller, observe reports/context, and let the controller synchronize perception, constraints, and action.

## Public API Summary

Import the module with:

```python
from robotics import PulseController, PulseConfig, PulsePhase
```

Create the controller with an existing `RobotRegistry`:

```python
controller = PulseController(registry=registry, config=PulseConfig(tick_hz=4.0))
```

Submit an action intent:

```python
command_id = controller.submit_command(command, source="planner_agent", priority=10)
```

Run one deterministic phase:

```python
report = controller.step(PulsePhase.SCAN)
```

Run the automatic phase ring:

```python
controller.start_background()
# ... later ...
controller.stop()
```

Add a safety rule:

```python
def speed_limit_rule(queued, context):
    if queued.command.parameters.get("speed", 0) > 0.5:
        return "speed above local limit"
    return None

controller.add_safety_rule(speed_limit_rule)
```

Request an emergency stop:

```python
controller.request_emergency_stop("operator pressed stop")
```

## Play-by-Play for Other AI Agents

An AI agent using this controller should follow this sequence every time.

First, observe the controller state. Use `get_context_snapshot()` and, if needed, `get_reports()` or `get_command_history()`. Treat this as the robot's current nervous-system view, not as perfect truth. If the last scan is stale, do not assume the world is safe.

Second, reason about the task in software only. The agent may plan, choose a destination, decide that a manipulator should move, or select a policy. This is the cognition layer. It should not call robot SDKs, ROS action clients, GPIO drivers, or actuator engines directly.

Third, convert the plan into one or more `ActuatorCommand` objects. Each command must name the target `robot_id`, `actuator_id`, `command_type`, parameters, and a positive timeout. The command should be small enough that the next scan can catch environmental change before the robot overcommits.

Fourth, submit the command to the pulse controller using `submit_command()`. The source should identify the AI agent, planner, policy, or service that proposed the command. Priority should be lower numeric value for more urgent work.

Fifth, wait for the pulse. The command will not execute immediately. It must pass through `SCAN`, `FLOW`, and `CONSTRAINT` before `ACTION` dispatches it. This is intentional. It prevents a hallucinating, stale, or overconfident agent from becoming a direct motor-control path.

Sixth, inspect the command history. If the command was executed, read the `ActuatorResult`. If it was blocked, read the reason. Do not resubmit the same blocked command blindly. Adjust the plan, request human help, lower speed, refresh sensors, charge the robot, clear emergency stop through an operator process, or choose a safer route.

Seventh, keep tasks chunked. The controller is designed for continuous autonomy, not one giant irreversible action. A mobile robot should move in short waypoint steps. A manipulator should use bounded trajectories. A home butler should patrol incrementally. This allows the scan/constraint phases to interrupt or redirect behavior.

## Safety Contract

The controller enforces a hard safety contract.

Agents submit intent; the controller dispatches action. Agents may observe context; the controller owns hardware timing. Agents may propose; safety rules may block. Emergency stop wins over everything. Stale sensors block action by default. Unknown robots block action. Disconnected, errored, or emergency-stopped robot clients block action. Only approved commands run during `ACTION`.

This contract is meant to support real robots, not just demos. Real deployments should add custom rules for collision zones, torque limits, maximum velocity, payload limits, battery thresholds, human detection, authorization, time-of-day restrictions, and facility-specific lockouts.

## Integration Points

Use `SCAN` hooks for sensor fusion, SLAM updates, obstacle maps, and telemetry ingestion.

Use `FLOW` hooks for agent memory refresh, blackboard updates, task arbitration, digital twin sync, and learned policy observation preparation.

Use `CONSTRAINT` hooks and safety rules for geofencing, speed limits, battery management, human-in-the-loop gates, authorization, and emergency stop propagation.

Use `ACTION` hooks for post-command telemetry, audit logs, command counters, and dispatch metrics.

The controller intentionally does not require ROS 2, Open-RMF, MoveIt, Nav2, or LeRobot. Those systems can sit behind Murphy's existing `SensorEngine`, `ActuatorEngine`, `NavigationEngine`, `MotionPlanner`, `FleetOrchestrator`, and `LearnedPolicyEngine` modules.

## Minimal Example

A runnable example is available at:

```text
examples/robot_pulse_controller_demo.py
```

It creates a stub ROS2 robot, submits a movement command, steps through the four phases, and prints the resulting command history. No hardware is required.

## Design Rule for AI Consumers

If you are another AI reading this playbook, your most important instruction is simple: never bypass the pulse controller for robot motion. Treat the pulse controller as the robot body's gatekeeper. You can think on every loop, but you can only act through submitted command intent and the controller's phase clock.
