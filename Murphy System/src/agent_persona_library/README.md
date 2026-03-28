# Agent Persona Library

The `agent_persona_library` package maintains a roster of named AI agent
personas.  Each persona encodes a role, communication style, capability
set, and behavioural constraints.

## Key Modules

| Module | Purpose |
|--------|---------|
| `_roster.py` | `PERSONA_ROSTER` — the canonical list of persona definitions |
| `_roster_data.py` | Core persona data (Part 1) |
| `_roster_data_ext.py` | Extended persona data (Part 2) |
| `_frameworks.py` | Reasoning and communication frameworks applied per persona |
| `_composer.py` | Composes final system prompts from persona + task context |

## Usage

```python
from agent_persona_library._roster import PERSONA_ROSTER
murphy = next(p for p in PERSONA_ROSTER if p.name == "Murphy")
prompt = murphy.compose_system_prompt(task="Summarise the board report")
```
