# `src/murphy_terminal` — Murphy Terminal

Universal command registry and category definitions for the Murphy System terminal interface.

![License: BSL 1.1](https://img.shields.io/badge/License-BSL%201.1-blue.svg)

## Overview

The murphy terminal package provides the canonical registry of all commands available in the Murphy interactive terminal. `CommandRegistry` holds `CommandDefinition` objects organised into `CommandCategory` groups — covering system management, orchestration, agent operations, and developer utilities. The `build_registry` factory function bootstraps the full `MURPHY_COMMANDS` dictionary on first call, making the registry available to terminal frontends, the Matrix bridge command router, and the REST API.

## Key Components

| Module | Purpose |
|--------|---------|
| `command_registry.py` | `CommandRegistry`, `CommandDefinition`, `CommandCategory`, `MURPHY_COMMANDS`, `build_registry` |

## Usage

```python
from murphy_terminal import CommandRegistry, build_registry, CommandCategory

registry = build_registry()
system_commands = registry.by_category(CommandCategory.SYSTEM)
for cmd in system_commands:
    print(cmd.name, cmd.description)
```

---
*Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1*
