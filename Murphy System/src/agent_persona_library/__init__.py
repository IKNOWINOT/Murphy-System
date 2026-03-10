"""Influence-trained agent persona definitions for the self-selling pipeline.

Every agent in Murphy System is a persistent LLM-driven character.
This package defines InfluenceFramework, AgentPersonaDefinition, and
SellingPromptComposer.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from agent_persona_library._frameworks import (  # noqa: F401
    InfluenceFramework,
    INFLUENCE_FRAMEWORKS,
    _build_influence_frameworks,
)
from agent_persona_library._roster import (  # noqa: F401
    AgentPersonaDefinition,
    AGENT_ROSTER,
    _build_agent_roster,
)
from agent_persona_library._composer import (  # noqa: F401
    SellingPromptComposer,
)

__all__ = [
    "InfluenceFramework",
    "INFLUENCE_FRAMEWORKS",
    "_build_influence_frameworks",
    "AgentPersonaDefinition",
    "AGENT_ROSTER",
    "_build_agent_roster",
    "SellingPromptComposer",
]
