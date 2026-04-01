"""
Skill System — first-class composable and shareable skills.

Design Label: SK-001
Module ID:    src.skill_system

Elevates workflow templates into a first-class Skill system where:
  • Users can save any executed workflow as a named skill
  • Skills can compose other skills (nested DAGs)
  • Skills are shareable between tenants
  • Describe → Execute pipeline matches against skills first

Commissioning answers
─────────────────────
Q: Does the module do what it was designed to do?
A: Provides a skill registry, skill composition (nested DAGs),
   inter-tenant sharing, and priority matching for the D→E pipeline.

Q: What conditions are possible?
A: Create / compose / share / execute / search skills.  Nested skills
   resolved via DAG traversal.  Circular deps detected.  Tenant isolation.

Q: Has hardening been applied?
A: Thread-safe, bounded collections, cycle detection, tenant isolation,
   Pydantic validation, no bare except.
"""

from __future__ import annotations

from src.skill_system.models import (
    SkillAccess,
    SkillComposition,
    SkillExecutionRecord,
    SkillMetadata,
    SkillSpec,
    SkillStep,
    SkillStepStatus,
)
from src.skill_system.skill_manager import SkillManager

__all__ = [
    "SkillAccess",
    "SkillComposition",
    "SkillExecutionRecord",
    "SkillManager",
    "SkillMetadata",
    "SkillSpec",
    "SkillStep",
    "SkillStepStatus",
]
