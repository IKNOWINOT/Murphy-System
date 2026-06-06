"""Caps I.1 + I.2 + I.3 + I.4 + I.5 — meta-rules registry.

I.1-I.4 are soul-level behaviors codified as Standing Decisions
64-67 in the registry. I.5 is the registry itself: ship a queryable
canonical store at /var/lib/murphy-production/standing_decisions/
registry.json plus three caps to read/append/quote any SD by number.

Surfaces:
  I.5  list_standing_decisions(category=None)
  I.5  get_standing_decision(decision_id)
  I.5  add_standing_decision(title, rule, category)
       (returns the next id; appends to registry)

I.1/I.2/I.3/I.4 don't get their own caps — they're behaviors,
not commands. The registry IS the executable artifact.
"""
from __future__ import annotations
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

REGISTRY = Path("/var/lib/murphy-production/standing_decisions/registry.json")
VALID_CATEGORIES = {
    "engineering", "governance", "audit", "memory", "ux",
    "phase_1", "soul", "external", "operations",
}


def _read_registry() -> List[Dict[str, Any]]:
    if not REGISTRY.exists():
        return []
    try:
        return json.loads(REGISTRY.read_text())
    except Exception:
        return []


def _write_registry(entries: List[Dict[str, Any]]) -> None:
    REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY.write_text(json.dumps(entries, indent=2))


def list_standing_decisions(category: Optional[str] = None) -> Dict[str, Any]:
    out: Dict[str, Any] = {"ok": False, "decisions": [], "error": None}
    try:
        regs = _read_registry()
        if category:
            cat = category.lower().strip()
            if cat not in VALID_CATEGORIES:
                out["error"] = f"unknown category: {cat} (valid: {sorted(VALID_CATEGORIES)})"
                return out
            regs = [r for r in regs if r.get("category") == cat]
        out["decisions"] = regs
        out["count"] = len(regs)
        out["latest_id"] = max((r["id"] for r in _read_registry()), default=0)
        out["ok"] = True
        return out
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"; return out


def get_standing_decision(decision_id: int) -> Dict[str, Any]:
    out: Dict[str, Any] = {"ok": False, "decision": None, "error": None}
    try:
        decision_id = int(decision_id)
        for r in _read_registry():
            if r.get("id") == decision_id:
                out["decision"] = r
                out["ok"] = True
                return out
        out["error"] = f"no standing decision with id={decision_id}"
        return out
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"; return out


def add_standing_decision(title: str, rule: str,
                          *, category: str = "engineering") -> Dict[str, Any]:
    out: Dict[str, Any] = {"ok": False, "decision_id": None, "error": None}
    try:
        if not title or not title.strip(): out["error"] = "title required"; return out
        if not rule or not rule.strip(): out["error"] = "rule required"; return out
        if len(title) > 80: out["error"] = "title too long (>80 chars)"; return out
        if len(rule) > 800: out["error"] = "rule too long (>800 chars)"; return out
        cat = category.lower().strip()
        if cat not in VALID_CATEGORIES:
            out["error"] = f"invalid category: {cat} (valid: {sorted(VALID_CATEGORIES)})"
            return out

        regs = _read_registry()
        next_id = max((r["id"] for r in regs), default=0) + 1
        entry = {
            "id": next_id, "title": title.strip(), "rule": rule.strip(),
            "established": time.strftime("%Y-%m-%d", time.gmtime()),
            "category": cat,
        }
        regs.append(entry)
        _write_registry(regs)
        out["decision_id"] = next_id
        out["decision"] = entry
        out["registry_count"] = len(regs)
        out["ok"] = True
        return out
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"; return out


# ── Executor wrappers ─────────────────────────────────────────────────────

def execute_list_standing_decisions(**kwargs) -> Dict[str, Any]:
    return list_standing_decisions(category=kwargs.get("category"))

def execute_get_standing_decision(**kwargs) -> Dict[str, Any]:
    return get_standing_decision(decision_id=kwargs.get("decision_id", 0))

def execute_add_standing_decision(**kwargs) -> Dict[str, Any]:
    return add_standing_decision(
        title=kwargs.get("title", ""),
        rule=kwargs.get("rule", ""),
        category=kwargs.get("category", "engineering"),
    )
