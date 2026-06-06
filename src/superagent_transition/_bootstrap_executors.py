"""Bootstrap: load every cap module and register its executors.

Strategy (R31 v2 — corrected after honest debugging):
  Walk every superagent_transition.cap_*.py module. For each
  callable named `execute_<something>`, register `<something>` as
  a skill executor in the local SkillManager singleton.

This is the local-singleton mitigation for BL-R14. It guarantees that
any process which imports superagent_transition can call run_skill()
on any registered cap, even though no cross-process executor
persistence exists yet.
"""
from __future__ import annotations
import importlib
import inspect
import logging
import pkgutil
from typing import List

log = logging.getLogger(__name__)

_BOOTSTRAPPED = False


def bootstrap_all() -> List[str]:
    """Import every cap_*.py in this package. Returns module names loaded."""
    global _BOOTSTRAPPED
    if _BOOTSTRAPPED:
        return []
    loaded: List[str] = []
    import superagent_transition as pkg
    for finder, name, ispkg in pkgutil.iter_modules(pkg.__path__):
        if not name.startswith("cap_"):
            continue
        full = f"superagent_transition.{name}"
        try:
            importlib.import_module(full)
            loaded.append(full)
        except Exception as e:
            log.warning("cap bootstrap import failed: %s: %s", full, e)
    _BOOTSTRAPPED = True
    return loaded


def reregister_executors_from_cube() -> int:
    """Walk every cap_*.py and register every `execute_<x>` function as <x>.

    Returns count of executors registered.
    """
    from .migration import get_skill_manager
    sm = get_skill_manager()
    bootstrap_all()

    registered = 0
    import superagent_transition as pkg
    for _, modname, _ in pkgutil.iter_modules(pkg.__path__):
        if not modname.startswith("cap_"):
            continue
        try:
            mod = importlib.import_module(f"superagent_transition.{modname}")
        except Exception:
            continue
        for attr_name, fn in inspect.getmembers(mod, inspect.isfunction):
            if not attr_name.startswith("execute_"):
                continue
            skill_name = attr_name[len("execute_"):]
            if skill_name in sm._tool_executors:
                continue  # already there
            sm.register_tool_executor(skill_name, fn)
            registered += 1
    return registered
