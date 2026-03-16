# `src/agent_persona_library` — Agent Persona Library

Influence-trained agent persona definitions and selling-prompt composition for the Murphy self-selling pipeline.

![License: BSL 1.1](https://img.shields.io/badge/License-BSL%201.1-blue.svg)

## Overview

Every agent in the Murphy System is a persistent, LLM-driven character whose behaviour is shaped by an `InfluenceFramework`. This package defines the full roster of named personas, the frameworks that govern their influence style, and the `SellingPromptComposer` that assembles context-aware prompts for the self-selling engine. Persona definitions are versioned and composable, allowing new agents to inherit from existing archetypes. The roster is extensible via `_roster_data_ext.py` without touching the core data.

## Key Components

| Module | Purpose |
|--------|---------|
| `_composer.py` | `SellingPromptComposer` — assembles persuasion prompts from persona + context |
| `_frameworks.py` | `InfluenceFramework` enum and `INFLUENCE_FRAMEWORKS` registry |
| `_roster.py` | `AgentPersonaDefinition` model and `AGENT_ROSTER` builder |
| `_roster_data.py` | Core persona definitions dataset |
| `_roster_data_ext.py` | Extended persona definitions (additive, no overwrites) |

## Usage

```python
from agent_persona_library import AGENT_ROSTER, SellingPromptComposer, InfluenceFramework

persona = AGENT_ROSTER["murphy_closer"]
composer = SellingPromptComposer(persona=persona)
prompt = composer.compose(prospect_profile={"industry": "SaaS", "pain": "ops overhead"})
```

---
*Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1*
