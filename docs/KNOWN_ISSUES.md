# Murphy System — Known Issues
<!-- Copyright © 2020 Inoni Limited Liability Company / Creator: Corey Post / License: BSL 1.1 -->

This file documents known limitations, bugs, and architectural issues in the
Murphy System 1.0 codebase. Issues are categorised by severity and include
references to the PRs or phases that resolve them.

---

## 1. Dual File Tree (Unresolved — Phase 4)

**Severity:** Medium  
**Status:** Known / Unresolved

The repository contains two parallel copies of nearly every source file:

- Root `src/` (e.g., `src/runtime/app.py`, `src/runtime/murphy_system_core.py`)
- `Murphy System/src/` (e.g., `Murphy System/src/runtime/app.py`)

Any change applied to one tree must also be applied to the other or the two
copies diverge silently. This is a maintenance hazard and a source of subtle
runtime differences depending on which working directory is used.

**Long-term fix (Phase 4):** Consolidate to a single canonical source tree.
Do NOT merge until the tiered runtime (PRs 1–2) is validated in production.

---

## 2. Monolith Runtime File Size (Unresolved — Phase 4)

**Severity:** Medium  
**Status:** Known / Managed

- `src/runtime/murphy_system_core.py` — ~662 KB (~15 000+ lines)
- `src/runtime/app.py` — ~420 KB (~10 000+ lines)

Both files are operational but unmaintainable at this scale.  The tiered
runtime (PRs 1–2) wraps them without editing them, deferring the refactor
until the tiered system is proven in production.

**Long-term fix (Phase 4):** Break each file into domain-scoped modules of
≤ 500 lines. Only after tiered runtime is validated.

---

## 3. Eager Module-Level Imports in `modular_runtime.py` (Fixed — PR 2)

**Severity:** High  
**Status:** Fixed in PR 2

`src/modular_runtime.py` instantiates `ModularRuntime()` at module scope
(line ~458). This cascades imports of 300+ sub-modules at import time,
consuming gigabytes of memory and making the system unbootable on low-RAM
machines.

**Fix (PR 2):** Replace the module-level singleton with a lazy proxy that
defers instantiation until first access.

---

## 4. `asyncio` PyPI Package in requirements (Fixed — This PR)

**Severity:** High  
**Status:** Fixed in this PR

Both `requirements_murphy_1.0.txt` files contained `asyncio>=3.4.3`. The
`asyncio` PyPI package is an ancient Python 2/3.3 backport that conflicts
with the `asyncio` stdlib module on Python 3.4+. Installing it can mask the
real stdlib asyncio and cause subtle, hard-to-diagnose breakage.

**Fix:** Removed `asyncio>=3.4.3` from both requirements files and added a
comment explaining why it must never be re-added.

---

## 5. Default `.env.example` Set to `staging` (Fixed — This PR)

**Severity:** High  
**Status:** Fixed in this PR

Both `.env.example` files defaulted to `MURPHY_ENV=staging`. Staging mode
requires `MURPHY_API_KEYS` to be set; without it, every API request returns
`401 Unauthorized`. New developers cloning the repository and running
`setup_and_start.sh` would immediately hit 401 on every endpoint.

**Fix:** Changed `MURPHY_ENV=staging` to `MURPHY_ENV=development` in both
`.env.example` files.

---

## 6. Docker Build Missing `Murphy System/` Directory (Unresolved)

**Severity:** Medium  
**Status:** Known / Unresolved

The root `Dockerfile` does not correctly copy the `Murphy System/` directory
(the space in the directory name causes issues). As a result, the Docker
image installs from a different set of requirements than the local development
environment, leading to runtime import failures inside the container.

**Workaround:** Build from the `Murphy System/` sub-directory directly or
rename the directory to remove the space.  
**Long-term fix (Phase 4):** Consolidate the dual file tree to eliminate the
space-in-path issue entirely.

---

## 7. No Automated Test Suite at the Root (Partial — Ongoing)

**Severity:** Medium  
**Status:** Partial / Ongoing

The repository has 644 test files but they are spread across both trees and
rely on optional heavy dependencies (torch, Flask, Textual). There is no
single `pytest` invocation that reliably passes on a fresh clone without
installing the full dependency stack.

**Workaround:** Use `requirements_core.txt` for a minimal install, then run
the four core test suites:

```bash
MURPHY_ENV=development MURPHY_RATE_LIMIT_RPM=6000 \
python3 -m pytest tests/test_platform_self_automation.py \
    tests/test_workflow_automation_compliance.py \
    tests/test_auth_and_route_protection.py \
    tests/test_ui_user_flow_schedule_automations.py \
    --no-cov --timeout=120
```

---

## 8. Missing `__init__.py` in Some Packages (Partial)

**Severity:** Low  
**Status:** Partial / Ongoing

Some directories that should be Python packages are missing `__init__.py`
files. This causes `ImportError` when code uses absolute package imports
into those directories.

Known affected directories:

- `src/runtime/runtime_packs/` (will be created by PR 1; stub added here)

---

## 9. `setup_and_start.sh` Python Path Assumptions (Unresolved)

**Severity:** Low  
**Status:** Known / Unresolved

`setup_and_start.sh` assumes `python3` is available in `$PATH` and does not
handle `venv` creation failures gracefully. On some systems (Windows via
WSL, certain minimal Linux images) `python3` is not aliased correctly and the
script silently falls back to the system Python, bypassing the venv.

**Workaround:** Use `python -m venv .venv` manually, then activate and install
`requirements_core.txt`.

---

## 10. Rate Limiting Requires Redis in Multi-Worker Mode (Unresolved)

**Severity:** Medium  
**Status:** Known / Unresolved

The rate-limiting middleware uses an in-process counter. When running
`uvicorn --workers 4`, each worker has its own counter, so a client can make
4× the allowed requests per minute before being throttled. A Redis-backed
counter is required for correct rate limiting in multi-worker deployments.

This is not documented prominently enough in the deployment guides.

**Workaround:** Run single-worker (`uvicorn --workers 1`) or configure a
Redis instance and set `REDIS_URL` in `.env`.

---

## 11. Onboard LLM Context Contamination (Fixed — PR 62)

**Severity:** High
**Status:** Fixed in PR 62

`LocalLLMFallback._generate_offline()` searched for knowledge-base topics in the
*entire* prompt string, including system-context prefixes injected by
`_try_llm_generate` and `_call_llm`. Since the context included strings like
`"Knowledge-base topics: murphy, murphy_setup, ..."` or `"Murphy onboarding
wizard..."`, the matcher would find `"murphy"` in the context and return the
generic Murphy System description for every query regardless of what the user
actually asked.

**Fix:** `_generate_offline` now splits the prompt on `\n\n` separators and
performs topic matching and pattern detection only against the *last segment*
(the actual user query). System context prepended to the prompt is ignored
for matching purposes.

---

## 12. Onboard LLM Missing Business-Domain Knowledge (Fixed — PR 62)

**Severity:** Medium
**Status:** Fixed in PR 62

`LocalLLMFallback` knowledge base contained only tech/programming topics
(algorithms, Python, databases, etc.) and had no content about business
automation, e-commerce, workflows, or integrations — the primary use-cases
of Murphy System. Additionally the pattern list lacked handlers for
`automation`, `integrate/connect`, `help`, `I run a business`, and
`set up / configure` phrasing.

**Fix:** Added knowledge-base entries for `automation`, `e-commerce`,
`workflow`, `integrations`, `crm`, and `reporting`. Added 8 new pattern
types with contextual response handlers that guide users toward setting up
their first Murphy automation.

---

## 13. UnifiedMFGC Offline Mode Returns Wrong Content (Fixed — PR 62)

**Severity:** High
**Status:** Fixed in PR 62

`UnifiedMFGC._process_with_context()` called `_call_llm()` (which in offline
mode delegates to `LocalLLMFallback`) with the full multi-paragraph system
prompt used for gate-resolution questioning. Because the system prompt ended
with "Make questions specific and actionable.", the pattern matcher matched
"make" and returned a generic creation-type response instead of asking the
targeted onboarding questions.

**Fix:** Gate-resolution and execution paths now check
`getattr(self, "llm_mode", "offline") != "offline"` before calling `_call_llm`.
When offline, `_process_with_context` generates structured onboarding questions
deterministically from the `remaining_unknowns` list using a keyword-to-question
mapping.

---

## 14. UnifiedMFGC None-Answer AttributeError Crash (Fixed — PR 62)

**Severity:** High
**Status:** Fixed in PR 62

`_process_with_context` recorded unanswered follow-up questions as `None`
placeholder values in the `answers` dict. On the second and subsequent turns,
the gate-satisfaction check iterated over `answers.values()` and called
`answer.lower()` on these `None` values, crashing with:
`AttributeError: 'NoneType' object has no attribute 'lower'`.

This caused `onboarding_mfgc_chat` to return `{"success": false}` for every
message after the first.

**Fix:** Added `if answer is None: continue` guard before the `.lower()` call
in the gate satisfaction loop.

---

## 15. MFGC Offline Session Never Advanced Past Turn 1 (Fixed — PR 62)

**Severity:** Critical
**Status:** Fixed in PR 62

`onboarding_mfgc_chat` only filled ONE answer slot per turn (the last None key),
`sess["context"]` never accumulated user information between turns, and
`_process_with_context` received the same empty context every turn — causing the
expansion engine to always return 4 unknowns and ask the same 3 questions forever.

**Fix:**
- Each turn now fills the **first** None slot (FIFO) so question/answer pairs map correctly
- `sess["context"]` is rebuilt after each turn from all accumulated filled answers
- `_process_with_context` incorporates filled answers into `enriched_task` so the expansion engine sees what has been provided
- Novel unknowns are computed by subtracting answered items from `remaining_unknowns`
- A turn-count safety valve fires `ready_for_plan=True` when `turn_count ≥ 3` AND `real_answer_count ≥ 2`, regardless of gate arithmetic

---

## 16. Automation Output Always "PREVIEW — Upgrade to Deploy" (Fixed — PR 62)

**Severity:** Critical
**Status:** Fixed in PR 62

`_build_automation_blueprint()` in `demo_deliverable_generator.py` always returned
a hardcoded "PREVIEW — Upgrade to deploy" string gated behind a "PAID TIER FEATURE"
header. `AIWorkflowGenerator`, `AutomationTypeRegistry`, and `AutomationEngine`
existed but were never called from the deliverable pipeline.

**Fix:**
- `_build_automation_blueprint` now calls `AIWorkflowGenerator.generate_workflow()`
- The returned workflow DAG (with real step names, types, and dependency links) is
  displayed in the deliverable
- "PREVIEW — Upgrade to deploy" language removed
- New header: "AUTOMATION BLUEPRINT — GENERATED WORKFLOW"
- Includes: Workflow ID, strategy, template used, executable steps with dependencies

---

## 17. AIWorkflowGenerator Missing Business-Domain Templates (Fixed — PR 62)

**Severity:** High
**Status:** Fixed in PR 62

Only 6 templates existed (etl, ci_cd, data_report, incident_response, customer_onboarding,
security_scan). Core business automation use-cases had no templates, so queries about
e-commerce fulfillment, invoicing, lead nurturing, employee onboarding, and content
publishing fell through to `generic_fallback` with 1–3 meaningless steps.

**Fix:**
Added 6 new pre-built templates with full dependency-wired steps:
- `order_fulfillment` — 7 steps: receive_order → validate_payment → update_inventory → create_shipping_label → notify_warehouse → send_confirmation → log_transaction
- `invoice_processing` — 7 steps: receive_invoice → extract_data → validate_invoice → route_approval → process_payment → update_ledger → notify_vendor
- `lead_nurture` — 7 steps: capture_lead → score_lead → enrich_profile → segment_lead → send_sequence → update_crm → handoff_to_sales
- `employee_onboarding` — 7 steps: create_profile → provision_accounts → assign_equipment → send_welcome_pack → schedule_orientation → assign_buddy → track_completion
- `content_publishing` — 6 steps: create_content → review_content → seo_optimise → publish_primary → syndicate_social → track_performance

Template matching threshold lowered from 60% to 50% to improve recall. 30+ new
business terms added to STEP_KEYWORDS.

---

## 18. Onboarding Chat Returns Automation Config (Fixed — PR 62)

**Severity:** High
**Status:** Fixed in PR 62

When `ready_for_plan=True`, the `/api/onboarding/mfgc-chat` response included no
actionable automation — just a boolean flag. The UI advanced to step 2 but had no
concrete workflow to show.

**Fix:** Added `_generate_automation_from_session(sess)` helper that:
1. Composes a combined description from ALL accumulated answers
2. Calls `AIWorkflowGenerator.generate_workflow()` for template matching
3. Falls back to initial_request if combined description produces < 3 steps
4. Returns the full workflow DAG (id, name, strategy, template, step count, steps)

The `automation_config` field is now included in every `ready_for_plan=True` response.

Added `/api/automations/workflows/{workflow_id}` endpoint for retrieving workflow
definitions by ID (referenced in the automation blueprint).

---

*Last updated: 2026-03-20. See [docs/PLANNED_FIXES.md](PLANNED_FIXES.md) for the resolution roadmap.*
