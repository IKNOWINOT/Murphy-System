# Rosetta Architecture — LOCKED 2026-06-04 (founder spec)

## What Rosetta IS

Rosetta is **how an agent becomes itself**. It is the org-chart-driven
mechanism for injecting skills + knowledge + perspective into a fresh
agent instance at dispatch time, based on its position (title) in the
org chart.

Rosetta is **NOT** a router, **NOT** a persona-roleplay layer for the
LLM, and **NOT** a vibe/tone configurator.

## The mechanism (verbatim from founder)

1. **Org chart defines the role.** Every role is a node in the chart.
   The node has a **title**. Title is canonical.

2. **Title → injection bundle.** Each title maps to a deterministic
   bundle of: (a) skills (typed callables), (b) knowledge (docs/RAG/
   facts), (c) perspective (decision frames, what-matters weights).
   The agent doesn't have personality baked in. It gets **equipped**
   at runtime from its position.

3. **Executor is the dispatcher.** When a plan needs work done:
     - Executor reads the plan.
     - Maps each task → role (by title).
     - Spawns a fresh agent for that role.
     - Injects the role's bundle into the agent.
     - Routes the task into the equipped agent.

4. **Professions in action, not professions in conversation.** A
   "sales engineer" agent does NOT roleplay being a sales engineer
   in a prompt. It IS one because its action space contains the
   sales-engineer skills/modules/functions. The verbs come from the
   equipped skillset, not from LLM roleplay.

5. **Inputs are typed commands.** Between LLM communicative steps,
   the actual work happens via **typed inputs into the skill / module
   / function library**. The LLM is the glue between typed steps,
   not the doer of the steps. A skill call looks like:
       `dispatch("send_quote", customer_id=X, line_items=Y)`
   — typed args, not free-text prompt.

6. **Row title is the contract.** The org-chart row's **title** is
   what determines what gets injected. Skills are queryable by the
   typed inputs they accept.

## The flow

```
plan
  → executor
  → for each task:
      resolve(task.role) → org_chart_row
      inject(row.title) → skills + knowledge + perspective bundle
      spawn agent equipped with bundle
      agent.execute(typed_input)
          → uses skills (deterministic) + LLM (communicative glue)
      return result
```

## Hard rules

- **Title is canonical.** No two role definitions with the same title.
- **Skills are typed.** Every skill declares its input types. If you
  can't dispatch with typed args, it's not a skill — it's a prompt.
- **LLM is glue.** Communication = LLM. Action = skill. Never invert.
- **No persona prompts.** "You are a sales engineer" in a system
  prompt is a Rosetta failure. The agent IS one because of what was
  injected, not because the LLM was told to pretend.
- **One bundle per dispatch.** Each task gets a fresh injection.
  Bundles don't persist across tasks unless the role explicitly says so.

## What's in the codebase (audited 2026-06-04)

The pattern is half-built and almost entirely unwired:

| File | Purpose | Wired? |
|---|---|---|
| `org_compiler/compiler.py` (RoleTemplateCompiler) | title → role template | **NO** — only used inside org_compiler |
| `org_compiler/schemas.py` (RoleTemplate, OrgChartNode) | typed shapes | yes (used by compiler) |
| `dynamic_rosetta_planner.py` (TaskProfile, AgentBlueprint, DispatchPacket) | executor → dispatch | **partial** — app.py touches it (2 refs) |
| `rosetta_subsystem_wiring.py` (bootstrap_rosetta_wiring) | the harness that connects everything | **NO** — never called outside its own file |
| `rosetta_core.py` (RosettaSoul, AgentCharacter, SoulVerdict) | conscience/gate layer (proceed/block/defer_hitl) | **NO** — orphan |
| `agent_employment_bridge.py` | hires agents into roles | unknown — needs audit |
| `rosetta_selling_bridge.py` | self-selling agent personas | orphan |

The biggest finding: **`bootstrap_rosetta_wiring()` is the spinal cord
that never got connected.** Wiring it from `app.py` startup is the
single highest-leverage action.

## What "wiring Rosetta" actually means

The next-session work plan (Tier 0):

1. AUDIT each file above against this spec — what claims to do what.
2. Locate or define the org chart (DB? YAML? JSON?). If absent,
   founder defines the starter chart.
3. Run `RoleTemplateCompiler` against the chart → `role_templates.db`.
4. Build the typed-dispatch table: `skill_name → callable + typed_args`.
5. Call `bootstrap_rosetta_wiring()` from app.py startup.
6. Add journey test J11 `rosetta_dispatches_to_role` — fake task with
   role="sales_engineer", verify DispatchPacket produced with correct
   bundle, verify agent executes typed command (not a free-text prompt).
7. Snapshot before/after. PSM-logged.

## Anti-patterns (refuse these)

❌ "You are a sales engineer named Murphy who…" in any system prompt
❌ Untyped skill calls (free-text dispatch)
❌ Persona vibes injected as character traits instead of skills
❌ Reusing an agent's bundle across unrelated tasks
❌ Title collisions in the org chart
❌ Adding a new orchestration layer instead of calling bootstrap_rosetta_wiring()

## The deeper principle

An agent is not what it says it is. An agent is what it can do.
Equip it correctly, and it acts the role. Equip it wrong, and no
amount of prompt engineering will make it competent.
