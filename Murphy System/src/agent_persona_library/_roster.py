"""Agent persona roster for the self-selling pipeline.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Agent Persona Definition
# ---------------------------------------------------------------------------


@dataclass
class AgentPersonaDefinition:
    """Complete agent persona for the self-selling pipeline.

    Each agent is a persistent character — a virtual employee with:
    - Identity (name, title, department)
    - Personality traits and communication style
    - Influence frameworks they're trained on
    - System prompt (the LLM instructions)
    - Information API connections (live data feeds that drive their reasoning)
    - Gate/trigger definitions (what events activate this agent)
    - Rosetta contract fields (maps to EmployeeContract in rosetta_models.py)
    """

    agent_id: str
    name: str
    title: str
    department: str
    personality: str
    communication_style: str
    influence_frameworks: List[str]  # framework_ids this agent uses
    system_prompt: str  # The full LLM system prompt
    information_apis: List[Dict[str, Any]]  # API connections for live data
    trigger_conditions: List[Dict[str, Any]]  # Events that activate this agent
    gate_definitions: List[Dict[str, Any]]  # Quality/safety gates this agent enforces
    action_capabilities: List[str]  # What actions this agent can take
    reports_to: str  # Who this agent reports to in the org chart
    direct_reports: List[str]  # Who reports to this agent
    rosetta_fields: Dict[str, Any]  # Fields that map to EmployeeContract/RosettaDocument
    kaia_mix: Dict[str, float] = field(default_factory=dict)  # Kaia personality mix weights


# ---------------------------------------------------------------------------
# Agent roster — nine self-selling personas
# ---------------------------------------------------------------------------


from agent_persona_library._roster_data import (  # noqa: F401, E402
    AGENT_ROSTER,
    _build_agent_roster,
)
