# Osmosis Bot (Cloud)

**Purpose:** Learn software behavior from attention over observations (Ghost profile, UI/log events) and reproduce it **by inference** (intent/interaction plan) — no code copying.

## Input
```json
{
  "task": "learn the workflow to open a project and run it",
  "software_signature": {"name":"JetBrains","os":"win","hints":["Ctrl+P","Run"]},
  "observations": [{"kind":"ui","value":"menu:file"}, {"kind":"key","value":"Ctrl+P"}],
  "ghost_profile": {"task_description":"Open project, run tests","active_window":"IDE"},
  "constraints": {"safety":"strict","budget_hint_usd":0.002,"time_s":10}
}
