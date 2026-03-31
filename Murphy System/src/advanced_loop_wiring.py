"""
Advanced Loop Wiring for Murphy System.

Design Label: WIRE-004 — Advanced Self-Improvement Loop Integration
Owner: Platform Engineering
Dependencies:
  - SelfFixLoop (ARCH-005)
  - AutomationLoopConnector (DEV-001)
  - SelfAutomationOrchestrator (ARCH-002)
  - GateBypassController (GATE-001)
  - SelfFixLoopConnector (WIRE-002)
  - TaskExecutionBridge (WIRE-003)
  - EventBackbone (optional)

Extends the core self-improvement wiring (self_loop_wiring.py, Steps 1–3)
with Steps 4–5:
  Step 4 — Wire SelfFixLoop diagnosis into AutomationLoopConnector via
            SelfFixLoopConnector
  Step 5 — Wire prompt chain execution via TaskExecutionBridge

If self_loop_wiring.py exists (PR 1), wire_advanced_loop() accepts its
component dict and adds the two new components.  Otherwise it constructs
all required dependencies from scratch with graceful degradation.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def wire_advanced_loop(
    base_components: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Instantiate and cross-wire SelfFixLoopConnector and TaskExecutionBridge.

    Parameters
    ----------
    base_components:
        Optional dict returned by ``wire_self_improvement_loop()`` from
        ``self_loop_wiring.py`` (PR 1).  If provided, the existing
        instances are reused.  If None, all components are created fresh
        with graceful degradation.

    Returns
    -------
    dict
        Component registry with keys:
        ``fix_loop_connector``, ``task_execution_bridge``, and all
        base components passed in (or freshly created).
    """
    components: Dict[str, Any] = dict(base_components or {})

    # ------------------------------------------------------------------
    # Resolve / create base dependencies
    # ------------------------------------------------------------------

    event_backbone = components.get("event_backbone")
    if event_backbone is None:
        try:
            from event_backbone import EventBackbone
            event_backbone = EventBackbone()
            components["event_backbone"] = event_backbone
            logger.info("wire_advanced_loop: created new EventBackbone")
        except Exception as exc:
            logger.warning("wire_advanced_loop: EventBackbone unavailable: %s", exc)

    improvement_engine = components.get("improvement_engine")
    if improvement_engine is None:
        try:
            from self_improvement_engine import SelfImprovementEngine
            improvement_engine = SelfImprovementEngine()
            components["improvement_engine"] = improvement_engine
            logger.info("wire_advanced_loop: created new SelfImprovementEngine")
        except Exception as exc:
            logger.warning("wire_advanced_loop: SelfImprovementEngine unavailable: %s", exc)

    orchestrator = components.get("orchestrator")
    if orchestrator is None:
        try:
            from self_automation_orchestrator import SelfAutomationOrchestrator
            orchestrator = SelfAutomationOrchestrator()
            components["orchestrator"] = orchestrator
            logger.info("wire_advanced_loop: created new SelfAutomationOrchestrator")
        except Exception as exc:
            logger.warning("wire_advanced_loop: SelfAutomationOrchestrator unavailable: %s", exc)

    automation_connector = components.get("automation_connector") or components.get("connector")
    if automation_connector is None:
        try:
            from automation_loop_connector import AutomationLoopConnector
            automation_connector = AutomationLoopConnector(
                improvement_engine=improvement_engine,
                orchestrator=orchestrator,
                event_backbone=event_backbone,
            )
            components["automation_connector"] = automation_connector
            logger.info("wire_advanced_loop: created new AutomationLoopConnector")
        except Exception as exc:
            logger.warning("wire_advanced_loop: AutomationLoopConnector unavailable: %s", exc)

    fix_loop = components.get("fix_loop") or components.get("self_fix_loop")
    if fix_loop is None:
        try:
            from self_fix_loop import SelfFixLoop
            fix_loop = SelfFixLoop(
                improvement_engine=improvement_engine,
                event_backbone=event_backbone,
            )
            components["fix_loop"] = fix_loop
            logger.info("wire_advanced_loop: created new SelfFixLoop")
        except Exception as exc:
            logger.warning("wire_advanced_loop: SelfFixLoop unavailable: %s", exc)

    gate_ctrl = components.get("gate_bypass_controller") or components.get("gate_ctrl")
    if gate_ctrl is None:
        try:
            from gate_bypass_controller import GateBypassController
            gate_ctrl = GateBypassController()
            components["gate_bypass_controller"] = gate_ctrl
            logger.info("wire_advanced_loop: created new GateBypassController")
        except Exception as exc:
            logger.warning("wire_advanced_loop: GateBypassController unavailable: %s", exc)

    # ------------------------------------------------------------------
    # Step 4 — SelfFixLoopConnector
    # ------------------------------------------------------------------
    fix_loop_connector = None
    try:
        from self_fix_loop_connector import SelfFixLoopConnector
        fix_loop_connector = SelfFixLoopConnector(
            self_fix_loop=fix_loop,
            automation_connector=automation_connector,
            event_backbone=event_backbone,
        )
        components["fix_loop_connector"] = fix_loop_connector
        logger.info("wire_advanced_loop: SelfFixLoopConnector wired (Step 4)")
    except Exception as exc:
        logger.warning("wire_advanced_loop: SelfFixLoopConnector failed: %s", exc)

    # ------------------------------------------------------------------
    # Step 5 — TaskExecutionBridge
    # ------------------------------------------------------------------
    task_bridge = None
    try:
        from task_execution_bridge import TaskExecutionBridge
        task_bridge = TaskExecutionBridge(
            orchestrator=orchestrator,
            event_backbone=event_backbone,
            gate_bypass_controller=gate_ctrl,
        )
        components["task_execution_bridge"] = task_bridge
        logger.info("wire_advanced_loop: TaskExecutionBridge wired (Step 5)")
    except Exception as exc:
        logger.warning("wire_advanced_loop: TaskExecutionBridge failed: %s", exc)

    logger.info(
        "wire_advanced_loop complete: fix_loop_connector=%s task_bridge=%s",
        fix_loop_connector is not None,
        task_bridge is not None,
    )
    return components
