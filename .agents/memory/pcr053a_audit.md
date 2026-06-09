# PCR-053a — Org Compiler Reality Audit
**Date:** 2026-06-09  **Auditor:** Murphy (Cyborg)  **Status:** COMPLETE

## TL;DR
The `src/org_compiler/` module is **fully built and fully tested** (3,965 LoC,
26/26 pytest passes, all 8 files import cleanly). It is **almost entirely
unwired** — only `onboarding_team_pipeline.py` imports `ShadowLearningAgent`
and `schema_registry/schemas.py` references the `AuthorityLevel` enum.

This is not a build problem. It is a wiring problem.

## Live demo result (no patches applied)

```
STEP 1 ✓ Parse org chart       3 nodes (CEO, Sales Rep, Engineer)
STEP 2 ✓ Compile RoleTemplates 3 templates with responsibilities + authority
STEP 3 ✓ Shadow-observe        10 send_quote tasks recorded with metadata
STEP 4 ✓ Pattern + risk        1 repetitive pattern, risk={compliance:low,...}
STEP 5 ✓ 4-gate evaluation     gates correctly block premature automation
```

## Multi-dim N model coverage (Corey's spec)

| Dimension                  | Field on existing schema                | Status |
|----------------------------|-----------------------------------------|--------|
| TIME       (window_days)   | `TemplateProposalArtifact.observation_window_days` | ✅ exists |
| QUALITY    (success rate)  | `TemplateProposalArtifact.success_rate`            | ✅ exists |
| RISK       (compliance/auth)| `RiskAnalyzer.analyze_risks` returns dict        | ✅ exists |
| MONEY      (ceiling_usd)   | only AuthorityLevel enum (NONE→EXECUTIVE)          | ❌ missing |
| OPERATORS  (distinct)      | nothing                                            | ❌ missing |
| JURISDICTION               | `ComplianceConstraint.regulation` (no geo)         | ❌ missing |
| REGULATORY_FLOOR lookup    | nothing                                            | ❌ missing |

## Wiring gap (independent of N model)

- ❌ no `/api/org/*` HTTP surface in `src/runtime/app.py`
- ❌ no heartbeat-driven shadow tick (agent has no continuous loop)
- ❌ no one-line `register_org_compiler(app)` wiring call

## Proposed PCR-053 series

| PCR    | Scope                                                           | Risk |
|--------|-----------------------------------------------------------------|------|
| 053a   | This audit (DONE)                                               | none |
| 053b   | Add `jurisdiction`, `decision_ceiling_usd`, `distinct_operators_required` to schemas + migrate tests | low |
| 053c   | New file: `regulatory_floor.py` — lookup table seeded for US-CA/saas | low |
| 053d   | New file: `org_compiler_routes.py` — `/api/org/compile`, `/api/org/shadow/observe`, `/api/org/proposals` | low |
| 053e   | Wire register_org_compiler(app) into runtime/app.py             | low |
| 053f   | Heartbeat tick: every 10min, shadow agent processes pending events | medium |
| 053g   | Inoni seed: feed real Inoni org chart + first 7 days of observation | low |

## Key insight
Past-you put `observation_window_days` and `success_rate` directly on the
proposal artifact. That means **3 of 4 N-dimensions are first-class data
already**. The patch is much smaller than I originally framed.

