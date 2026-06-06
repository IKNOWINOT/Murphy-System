# AionMind salvage — 2026-06-01

## What's here
Code from R421-R427b that welded AionMind planning into /api/chat.
Rolled back from the live runtime per founder direction:
"the existing ops was perfect the new aionmind is what we want"

## When to use this
When building the standalone AionMind personal-assistant surface as
its own file (not welded into /api/chat). Reuse:

- `r427_op_canvas.html` — 3-column canvas (identity / plan / timelines).
  Was at /op. Repurpose as the AionMind main surface OR strip for parts.

- `r426c_match_capabilities.py` — reasoning-engine filter that uses
  Rosetta task_config to bound the candidate capability pool by role.
  This is the role-bounded dispatch logic. Reuse in AionMind's
  planning layer.

- `r427b_graph_in_result.py` — adds `graph` + `state.node_states` to
  the kernel result so a UI can render which nodes executed.
  Drop into AionMind's kernel-call wrapper.

- `app_py_welds.py` — the big chat-side handler block. Don't paste back
  into app.py; instead, refactor as the body of AionMind's own
  /api/aionmind/converse endpoint.

## Architecture intent (per founder)
ONE entry point: AionMind personal assistant.
- AionMind interprets in org-chart context, spawns role-agents
- Each agent gets Rosetta soul + DLF + MCP tools at spawn
- Ambient capture: email/SMS/call/meeting → attributed to right agent
- ROI clock: human-time-estimate × labor-rate vs computer-work
- Teaching loop: input junctions become future generation templates

AionMind is its OWN surface (own page, own endpoints).
OS pages (/founder, /tenant, /os) untouched — they keep their own /api/chat.
