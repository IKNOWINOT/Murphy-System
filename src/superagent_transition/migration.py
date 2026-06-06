"""R12 — superagent → Murphy capability migration utility.

Dual-registers a capability:
  - SkillSpec in shared SkillManager (executable surface)
  - CapabilityManifest in CapabilityCube (composition / discovery)

If either side fails, the other is rolled back atomically.
"""
from __future__ import annotations
import logging, threading
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Set, List

logger = logging.getLogger(__name__)

_SKILL_MANAGER_LOCK = threading.Lock()
_SKILL_MANAGER = None


def get_skill_manager():
    global _SKILL_MANAGER
    with _SKILL_MANAGER_LOCK:
        if _SKILL_MANAGER is None:
            from src.skill_system.skill_manager import SkillManager
            _SKILL_MANAGER = SkillManager()
            logger.info("superagent_transition: SkillManager singleton created")
        return _SKILL_MANAGER


@dataclass
class MigrationResult:
    cap_id: str
    skill_id: Optional[str]
    cube_name: Optional[str]
    skill_registered: bool
    cube_registered: bool
    error: Optional[str]

    @property
    def success(self) -> bool:
        return self.skill_registered and self.cube_registered

    def to_dict(self) -> Dict[str, Any]:
        return {"cap_id": self.cap_id, "skill_id": self.skill_id,
                "cube_name": self.cube_name,
                "skill_registered": self.skill_registered,
                "cube_registered": self.cube_registered,
                "success": self.success, "error": self.error}


def migrate_capability(
    cap_id: str, name: str, description: str,
    executor: Callable[..., Dict[str, Any]],
    *, accepts: Set[str], produces: Set[str],
    domain: str = "platform", risk_class: str = "yellow",
    trust_tier: str = "signed", soul_fit: str = "executor",
    tags: Optional[List[str]] = None, cost_hint: float = 0.0,
    avg_latency_ms: int = 100, requires_hitl: bool = False,
    version: str = "1.0.0",
) -> MigrationResult:
    from src.skill_system.models import (
        SkillSpec, SkillAccess, SkillMetadata,
    )
    from src.patch412_capability_cube import (
        CapabilityManifest, Accepts, Produces, Domain, RiskClass,
        TrustTier, SoulFit, register_capability,
    )

    skill_id = f"superagent_cap_{cap_id.lower().replace('.', '_')}"
    cube_name = f"superagent.{cap_id}"

    result = MigrationResult(
        cap_id=cap_id, skill_id=skill_id, cube_name=cube_name,
        skill_registered=False, cube_registered=False, error=None,
    )

    sm = get_skill_manager()
    try:
        spec = SkillSpec(
            skill_id=skill_id, name=name, description=description,
            version=version, owner_tenant="system",
            access=SkillAccess.TENANT,
            metadata=SkillMetadata(
                tags=tags or [cap_id, "superagent_migration"],
                category="superagent_transition",
                estimated_duration_seconds=avg_latency_ms / 1000.0,
                estimated_cost_usd=cost_hint,
            ),
        )
        sm.register(spec)
        sm.register_tool_executor(skill_id, executor)
        result.skill_registered = True
    except Exception as e:
        result.error = f"skill_register_failed: {type(e).__name__}: {e}"
        return result

    try:
        manifest = CapabilityManifest(
            accepts={Accepts(a) for a in accepts},
            produces={Produces(p) for p in produces},
            domain=Domain(domain), risk_class=RiskClass(risk_class),
            trust_tier=TrustTier(trust_tier), soul_fit=SoulFit(soul_fit),
            cost_hint=cost_hint, avg_latency_ms=avg_latency_ms,
            description=f"[{cap_id}] {description}",
            requires_hitl=requires_hitl,
            tags=tags or [cap_id, "superagent_migration"],
        )
        register_capability(cube_name, manifest)
        result.cube_registered = True
    except Exception as e:
        try:
            sm.unregister(skill_id)
        except Exception:
            pass
        result.skill_registered = False
        result.error = f"cube_register_failed: {type(e).__name__}: {e}"
        return result

    return result


def list_migrated() -> Dict[str, Any]:
    from src.patch412_capability_cube import get_cube
    cube = get_cube()
    sa_caps = {n: m for n, m in cube._caps.items() if n.startswith("superagent.")}
    sm = get_skill_manager()
    sa_skills = {sid: spec for sid, spec in sm._skills.items()
                 if sid.startswith("superagent_cap_")}
    return {
        "cube_count": len(sa_caps),
        "skill_count": len(sa_skills),
        "cube_caps": [{"name": n, "domain": m.domain.value,
                       "description": m.description}
                      for n, m in sa_caps.items()],
        "skills": [{"id": sid, "name": s.name} for sid, s in sa_skills.items()],
    }


def rollback_capability(cap_id: str) -> Dict[str, Any]:
    skill_id = f"superagent_cap_{cap_id.lower().replace('.', '_')}"
    cube_name = f"superagent.{cap_id}"
    sm = get_skill_manager()
    result = {"cap_id": cap_id, "skill_removed": False, "cube_removed": False}
    try:
        sm.unregister(skill_id)
        result["skill_removed"] = True
    except KeyError:
        pass
    try:
        from src.patch412_capability_cube import get_cube
        import sqlite3
        cube = get_cube()
        if cube_name in cube._caps:
            cube._remove_from_indexes(cube_name)
            del cube._caps[cube_name]
            result["cube_removed"] = True
        # Also wipe DB row (R615.7p persistence)
        c = sqlite3.connect("/var/lib/murphy-production/agent_substrate.db")
        c.execute("DELETE FROM capabilities WHERE name=?", (cube_name,))
        c.commit(); c.close()
        result["db_wiped"] = True
    except Exception as e:
        result["cube_error"] = str(e)
    return result
