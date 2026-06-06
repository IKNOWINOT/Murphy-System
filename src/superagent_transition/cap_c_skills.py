"""Caps C.1 + C.2 + C.3 — skill management.

C.1 run_skill(skill_name, arguments) — execute a registered executor
C.2 suggest_skill_installation(query) — match query to skill catalog
C.3 activate_platform_skill(skill_name) — lazy-load detailed spec

Reuses Murphy's SkillManager singleton (from R13 migration utility),
augmented with a bootstrap path that re-registers cap executors when
called from a fresh Python process.

Honest scope note: full BL-R14 (cross-process executor persistence)
is NOT solved here. We give run_skill a best-effort lookup by
re-importing every cap_*.py at first call, which works because cap
modules expose execute_<name> functions. For truly stateless callers
that don't have the cap modules importable, executors are still
unavailable — that needs the R615.7p-equivalent persistence layer.
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional

from .migration import get_skill_manager, list_migrated
from . import _skill_catalog
from . import _platform_skill_specs
from . import _bootstrap_executors


def run_skill(skill_name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """C.1 — execute a registered skill / cap executor by name."""
    out: Dict[str, Any] = {"ok": False, "skill_name": skill_name, "error": None}
    try:
        if not skill_name or not skill_name.strip():
            out["error"] = "empty skill_name"; return out
        args = arguments or {}
        if not isinstance(args, dict):
            out["error"] = "arguments must be a dict"; return out

        sm = get_skill_manager()

        # Strip "superagent." prefix if present (registration uses bare name)
        lookup_name = skill_name.strip()
        if lookup_name.startswith("superagent."):
            lookup_name = lookup_name[len("superagent."):]

        # If executor not present, bootstrap from cap modules
        if lookup_name not in sm._tool_executors:
            _bootstrap_executors.reregister_executors_from_cube()

        executor = sm._tool_executors.get(lookup_name)
        if not executor:
            out["error"] = f"no executor for skill '{lookup_name}' (bootstrap exhausted)"
            out["available_executors"] = sorted(list(sm._tool_executors.keys()))[:20]
            return out

        result = executor(**args)
        out["ok"] = True
        out["result"] = result
        out["executor_count_after_bootstrap"] = len(sm._tool_executors)
        return out
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"; return out


def suggest_skill_installation(query: str, *, limit: int = 5) -> Dict[str, Any]:
    """C.2 — match a free-text query to known skills (third-party + platform)."""
    out: Dict[str, Any] = {"ok": False, "query": query, "matches": [], "error": None}
    try:
        if not query or not query.strip():
            out["error"] = "empty query"; return out
        matches = _skill_catalog.search(query, limit=int(limit))
        out["matches"] = matches
        out["count"] = len(matches)
        out["ok"] = True
        return out
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"; return out


def activate_platform_skill(skill_name: str) -> Dict[str, Any]:
    """C.3 — lazy-load detailed instructions for a platform skill."""
    return _platform_skill_specs.get(skill_name)


def list_platform_skills() -> Dict[str, Any]:
    """Companion: show all platform skills available to activate."""
    return _platform_skill_specs.list_available()


# ── Executor wrappers ─────────────────────────────────────────────────────

def execute_run_skill(**kwargs) -> Dict[str, Any]:
    return run_skill(
        skill_name=kwargs.get("skill_name", ""),
        arguments=kwargs.get("arguments"),
    )


def execute_suggest_skill_installation(**kwargs) -> Dict[str, Any]:
    return suggest_skill_installation(
        query=kwargs.get("query", ""),
        limit=int(kwargs.get("limit", 5)),
    )


def execute_activate_platform_skill(**kwargs) -> Dict[str, Any]:
    return activate_platform_skill(skill_name=kwargs.get("skill_name", ""))


def execute_list_platform_skills(**kwargs) -> Dict[str, Any]:
    return list_platform_skills()
