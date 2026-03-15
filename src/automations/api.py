"""
Automations – REST API
========================

FastAPI router for automation rule CRUD, trigger firing, and execution log.

All endpoints live under ``/api/automations``.

Copyright 2024 Inoni LLC – BSL-1.1
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

try:
    from fastapi import APIRouter, HTTPException, Query
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel, Field
except ImportError:  # pragma: no cover
    APIRouter = None  # type: ignore[assignment,misc]

from .engine import AutomationEngine
from .models import ActionType, ConditionOperator, TriggerType

logger = logging.getLogger(__name__)

if APIRouter is not None:

    class CreateRuleRequest(BaseModel):
        """Create Rule Request."""
        name: str
        board_id: str
        trigger_type: str
        trigger_config: Dict[str, Any] = Field(default_factory=dict)
        conditions: List[Dict[str, Any]] = Field(default_factory=list)
        actions: List[Dict[str, Any]] = Field(default_factory=list)

    class UpdateRuleRequest(BaseModel):
        """Update Rule Request."""
        name: Optional[str] = None
        enabled: Optional[bool] = None

    class FireTriggerRequest(BaseModel):
        """Fire Trigger Request."""
        board_id: str
        trigger_type: str
        context: Dict[str, Any] = Field(default_factory=dict)


def create_automations_router(
    engine: Optional[AutomationEngine] = None,
) -> "APIRouter":
    if APIRouter is None:
        raise RuntimeError("FastAPI is required for the automations API")
    if engine is None:
        engine = AutomationEngine()

    router = APIRouter(prefix="/api/automations", tags=["automations"])

    @router.post("/rules")
    async def create_rule(req: CreateRuleRequest):
        try:
            tt = TriggerType(req.trigger_type)
        except ValueError:
            raise HTTPException(400, f"Invalid trigger type: {req.trigger_type!r}")

        from .models import ActionType, AutomationAction, Condition, ConditionOperator
        conditions = []
        for c in req.conditions:
            try:
                op = ConditionOperator(c.get("operator", "equals"))
            except ValueError:
                raise HTTPException(400, f"Invalid operator: {c.get('operator')!r}")
            conditions.append(Condition(
                column_id=c.get("column_id", ""),
                operator=op,
                value=c.get("value"),
            ))
        actions = []
        for a in req.actions:
            try:
                at = ActionType(a.get("action_type", "notify"))
            except ValueError:
                raise HTTPException(400, f"Invalid action type: {a.get('action_type')!r}")
            actions.append(AutomationAction(action_type=at, config=a.get("config", {})))

        rule = engine.create_rule(
            req.name, req.board_id, tt, actions,
            trigger_config=req.trigger_config,
            conditions=conditions,
        )
        return JSONResponse(rule.to_dict(), status_code=201)

    @router.get("/rules")
    async def list_rules(board_id: str = Query("")):
        rules = engine.list_rules(board_id)
        return JSONResponse([r.to_dict() for r in rules])

    @router.get("/rules/{rule_id}")
    async def get_rule(rule_id: str):
        rule = engine.get_rule(rule_id)
        if rule is None:
            raise HTTPException(404, "Rule not found")
        return JSONResponse(rule.to_dict())

    @router.patch("/rules/{rule_id}")
    async def update_rule(rule_id: str, req: UpdateRuleRequest):
        try:
            rule = engine.update_rule(rule_id, name=req.name, enabled=req.enabled)
            return JSONResponse(rule.to_dict())
        except KeyError as exc:
            raise HTTPException(404, str(exc))

    @router.delete("/rules/{rule_id}")
    async def delete_rule(rule_id: str):
        if not engine.delete_rule(rule_id):
            raise HTTPException(404, "Rule not found")
        return JSONResponse({"deleted": True})

    @router.post("/trigger")
    async def fire_trigger(req: FireTriggerRequest):
        try:
            tt = TriggerType(req.trigger_type)
        except ValueError:
            raise HTTPException(400, f"Invalid trigger type: {req.trigger_type!r}")
        results = engine.fire_trigger(req.board_id, tt, req.context)
        return JSONResponse({"triggered": len(results), "results": results})

    @router.get("/log")
    async def execution_log(limit: int = Query(50, ge=1, le=500)):
        log = engine.get_execution_log(limit)
        return JSONResponse(log)

    return router
