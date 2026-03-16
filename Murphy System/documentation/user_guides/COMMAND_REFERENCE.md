# Command Reference

Reference for all Murphy System CLI commands available in the REPL and chat interface.

---

## Overview

Murphy System provides slash-commands that can be entered in the REPL or chat interface.
Commands are parsed by `CommandParser` (`src/command_parser.py`) and executed in the
`SafeREPL` environment (`src/murphy_repl.py`).

---

## Available Commands

### `/help`

Display a list of all available commands and their descriptions.

```
/help
```

### `/status`

Show the current system state, including active phase, confidence level, and loaded engines.

```
/status
```

### `/swarmmonitor`

Display swarm system status — active swarms, total atoms, artifacts generated, and
whether exploration/control modes are running.

```
/swarmmonitor
```

**Example output:**

```
## Swarm System Status
Active Swarms: 3
Total Atoms: 42
Artifacts Generated: 7
Swarm Modes:
  • Exploration: True
  • Control: False
```

### `/swarmauto <task>`

Initiate a swarm automation task. The system enters the exploratory band and
delegates the task description to the swarm engine.

```
/swarmauto Analyze customer churn data and propose retention strategies
```

> The command triggers the exploratory confidence band (threshold 0.1), meaning
> results will be presented for human review before execution.

### `/memory`

Show the 4-plane memory artifact system — sandbox, working, control, and
execution planes with artifact counts.

```
/memory
```

**Example output:**

```
## Memory Artifact System
Sandbox Plane:  12 artifacts  — Unverified hypotheses
Working Plane:   8 artifacts  — Verified and active
Control Plane:   3 artifacts  — High-confidence patterns
Execution Plane: 1 artifact   — Production-ready
Total Artifacts: 24
```

### `/reset`

Reset the system state, clearing session data and returning to the initial phase.

```
/reset
```

### `/docs`

Open or display links to the Murphy System documentation.

```
/docs
```

---

## REPL Environment

The `SafeREPL` class provides a sandboxed Python execution environment with:

- **Isolated context** — user code runs in a restricted `exec` environment.
- **Safe builtins** — only non-destructive builtins (`print`, `len`, `str`, `sorted`, etc.) are exposed.
- **Variable tracking** — created/modified variables are logged per execution.
- **Output capture** — stdout/stderr are redirected and returned in the result.
- **Resource limits** — 30-second execution timeout, 100 MB memory cap.
- **LLM callback** — optional `llm_query` function injected for AI-assisted code.

### Executing Code in the REPL

```python
repl = SafeREPL()
result = repl.execute("x = sum(range(10))\nprint(x)")
# result.success == True, result.output == "45\n"
```

---

## See Also

- [User Guide](USER_GUIDE.md)
- [Quick Start](../getting_started/QUICK_START.md)
- [API Reference](API_REFERENCE.md)
