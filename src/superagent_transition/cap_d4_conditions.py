"""Cap D.4 — trigger_conditions evaluator.

When an automation fires, optionally evaluate {conditions, logic}
against the trigger payload and decide whether to proceed.

Contract matches Base44 exactly:
  {
    "logic": "and" | "or",   (default "and")
    "conditions": [
      {"field": "data.status", "operator": "equals", "value": "Active"},
      ...
    ]
  }

Operators: equals, not_equals, gt, gte, lt, lte, contains,
not_contains, starts_with, ends_with, in_list, not_in_list,
exists, not_exists, is_empty, is_not_empty
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple

ALLOWED_OPS = {
    "equals", "not_equals", "gt", "gte", "lt", "lte",
    "contains", "not_contains", "starts_with", "ends_with",
    "in_list", "not_in_list", "exists", "not_exists",
    "is_empty", "is_not_empty",
}


def _resolve(payload: Dict[str, Any], path: str) -> Tuple[bool, Any]:
    """Walk dot-path; return (found, value)."""
    if not path: return True, payload
    cur: Any = payload
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return False, None
    return True, cur


def _check(op: str, found: bool, lhs: Any, rhs: Any) -> bool:
    if op == "exists":     return found
    if op == "not_exists": return not found
    if op == "is_empty":   return found and (lhs is None or lhs == "" or lhs == [] or lhs == {})
    if op == "is_not_empty":
        return found and not (lhs is None or lhs == "" or lhs == [] or lhs == {})
    if not found: return False
    if op == "equals":     return lhs == rhs
    if op == "not_equals": return lhs != rhs
    if op in ("gt","gte","lt","lte"):
        try:
            l, r = float(lhs), float(rhs)
            return {"gt":l>r,"gte":l>=r,"lt":l<r,"lte":l<=r}[op]
        except Exception: return False
    if op == "contains":
        try: return rhs in lhs
        except TypeError: return False
    if op == "not_contains":
        try: return rhs not in lhs
        except TypeError: return True
    if op == "starts_with": return isinstance(lhs,str) and lhs.startswith(str(rhs))
    if op == "ends_with":   return isinstance(lhs,str) and lhs.endswith(str(rhs))
    if op == "in_list":     return isinstance(rhs,list) and lhs in rhs
    if op == "not_in_list": return isinstance(rhs,list) and lhs not in rhs
    return False


def evaluate_trigger_conditions(payload: Dict[str, Any],
                                 trigger_conditions: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {"ok": False, "should_fire": False, "results": [], "error": None}
    try:
        if not isinstance(payload, dict):
            out["error"] = "payload must be dict"; return out
        if not isinstance(trigger_conditions, dict):
            out["error"] = "trigger_conditions must be dict {logic, conditions}"; return out

        conditions = trigger_conditions.get("conditions") or []
        logic = (trigger_conditions.get("logic") or "and").lower()
        if logic not in ("and", "or"):
            out["error"] = f"logic must be 'and' or 'or', got {logic!r}"; return out
        if not isinstance(conditions, list):
            out["error"] = "conditions must be a list"; return out

        # Empty conditions → fire (no filter)
        if not conditions:
            out["should_fire"] = True
            out["reason"] = "no conditions — fires unconditionally"
            out["ok"] = True
            return out

        results: List[Dict[str, Any]] = []
        for i, cond in enumerate(conditions):
            if not isinstance(cond, dict):
                out["error"] = f"conditions[{i}]: must be dict"; return out
            field = cond.get("field", "")
            op    = cond.get("operator", "")
            value = cond.get("value")
            if not field:
                out["error"] = f"conditions[{i}]: field required"; return out
            if op not in ALLOWED_OPS:
                out["error"] = f"conditions[{i}]: invalid operator {op!r} (allowed: {sorted(ALLOWED_OPS)})"
                return out
            found, lhs = _resolve(payload, field)
            passed = _check(op, found, lhs, value)
            results.append({"field": field, "operator": op, "value": value,
                            "resolved": lhs if found else None, "found": found,
                            "passed": passed})

        if logic == "and":
            should_fire = all(r["passed"] for r in results)
        else:
            should_fire = any(r["passed"] for r in results)

        out["results"] = results
        out["logic"] = logic
        out["should_fire"] = should_fire
        out["reason"] = f"{logic} of {len(results)} condition(s): {sum(r['passed'] for r in results)} passed"
        out["ok"] = True
        return out
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"; return out


def execute_evaluate_trigger_conditions(**kwargs) -> Dict[str, Any]:
    return evaluate_trigger_conditions(
        payload=kwargs.get("payload") or {},
        trigger_conditions=kwargs.get("trigger_conditions") or {},
    )
