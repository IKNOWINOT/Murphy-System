"""Influence-trained agent persona definitions for the self-selling pipeline.

Every agent in Murphy System is a persistent LLM-driven character.
This package defines InfluenceFramework, AgentPersonaDefinition, and
SellingPromptComposer.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from agent_persona_library._composer import (  # noqa: F401
    SellingPromptComposer,
)
from agent_persona_library._frameworks import (  # noqa: F401
    INFLUENCE_FRAMEWORKS,
    InfluenceFramework,
    _build_influence_frameworks,
)
from agent_persona_library._roster import (  # noqa: F401
    AGENT_ROSTER,
    AgentPersonaDefinition,
    _build_agent_roster,
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
