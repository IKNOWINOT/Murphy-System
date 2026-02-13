# Capability Gap Solutions (Runtime 1.0)

This document captures the best recommendations for closing the current capability gaps using the modules already present in the repository.

## Current capabilities (runtime 1.0)

The runtime currently provides:

- **Activation previews** with gate policies, swarm task planning, org chart coverage, regulatory sensor plans, and learning-loop plans.
- **Architect terminal UI** onboarding chat flow, block commands (magnify/simplify/solidify), gate updates, and preview/librarian panels.
- **Governance planning** (executive, operations, QA, HITL) and timer/trigger scheduling in previews.
- **Business automation loop outputs** (marketing, operations, QA) through the Inoni automation engine.
- **MFGC fallback execution path** that synthesizes gates and swarm candidates when the two-phase orchestrator is unavailable.
- **Capability review summaries** (execution metrics, workload balance, automation execution evaluation, competitive comparison readiness).
- **Delivery readiness checks** combining compliance gate status, HITL requirements, and 99% coverage targets.
- **Librarian context generation** with recommended conditions and approval-required guidance.
- **Org chart coverage mapping** for deliverables → positions → contract coverage gaps.
- **Regional compliance sensors** for regulatory sources tied to onboarding region data.
- **User-tested onboarding prompts** that request operating region and surface gated next steps during architect terminal sessions.
- **Gate policy edits + block commands** (magnify/simplify/solidify) that update previews in real time.

These capabilities are currently **planning/preview oriented**: the system generates gate chains, swarms, and governance plans but does not yet execute external automations without additional wiring (see completion path below).

### Learning loop status

The activation preview now includes a **learning loop plan** that:

- Identifies missing onboarding requirements before iterative automation runs.
- Lists output targets (document, email, chat, voice, API).
- Schedules repeat project variants (baseline/compliance/growth) to show multi-project iteration.
- Notes the exact wiring gaps required to move from planning to fully automated loops.

## Current goals (target state)

1. **Fully wired execution:** gate synthesis, swarm execution, compute plane, and persistence must drive live task execution.
2. **Self-service automation:** onboarding, remote access, ticketing, and patch/rollback automation must be bound to real services.
3. **Multi-channel delivery:** consistent adapters for documents, email, chat, and voice with audit trails.
4. **Autonomous learning loops:** repeated project iterations with requirements identification and updated gate policies.

## Completion path (from now → fully operational)

1. Wire gate synthesis + swarm execution into `execute_task` and form handlers.
2. Persist LivingDocument, librarian context, and gate history across sessions.
3. Add channel adapters (documents/email/chat/voice) to the integration engine.
4. Close the learning loop with iterative requirement variants and automated gate tuning.

## 1) Immediate wiring priorities (highest impact)

### A) Gate Synthesis → Execution
**Gap:** Gates are planned in previews but never generated from real requests.  
**Solution:** Wire `src/gate_synthesis` into `execute_task` and form processing so that each request produces a gate chain driven by onboarding data.

Minimal plan:
1. Instantiate `GateSynthesisEngine` in runtime init.
2. Call it during `handle_form_task_execution` and `handle_chat` to build gates.
3. Attach generated gates to the response and the LivingDocument.

### B) TrueSwarmSystem + Domain Swarms → Execution
**Gap:** Swarm systems are present but not invoked during execution.  
**Solution:** Use `TrueSwarmSystem` + `DomainSwarmGenerator` to expand onboarding flows into agent swarms.

Minimal plan:
1. Instantiate `TrueSwarmSystem` and `DomainSwarmGenerator`.
2. For each onboarding stage, generate swarm tasks and register them in the LivingDocument.
3. Expose the swarm execution plan in activation previews and task responses.

### C) Compute Plane → Deterministic Execution
**Gap:** Deterministic compute plane exists but never used.  
**Solution:** Add a compute-plane call path for tasks tagged with `calculate`, `optimize`, or symbolic processing.

Minimal plan:
1. Expose `/api/compute` endpoint or internal call to `src/compute_plane.service`.
2. Route tasks with compute keywords to the compute plane.

## 2) Executive-branch governance gates (business automation)

**Gap:** Executive oversight gates are not generated.  
**Solution:** Add an executive gate policy layer that mirrors real decision structures.

Recommendations:
- Define a **governance policy schema** (executive roles, approval thresholds, escalation rules).
- Add gate synthesis rules for each executive branch gate (finance, security, compliance).
- Bind these gates to onboarding questions so the system can enforce approvals.

## 3) Onboarding questions that must be captured

To generate gates and swarms that reflect true capability, the system must ask:

1. **Business structure** (org chart, executive authority levels)
2. **Compliance scope** (SOC2, PCI, HIPAA, regional regulations)
3. **Automation targets** (primary workflows, triggers, escalation)
4. **Data authority** (systems of record, audit logs, access controls)
5. **Service expectations** (SLA, support tiers, human override triggers)

## 4) Capability alignment enforcement

**Gap:** Activation preview shows gaps but does not enforce closure.  
**Solution:** Require a “gap closure plan” for any subsystem marked `not_wired` or `not_initialized`.

Implementation:
- Add a “gap resolution checklist” field in activation previews.
- Block production mode until gaps are resolved.

## 5) Recommended test plan (prove capability)

1. **Gate generation test**
   - Provide onboarding data with compliance + risk context.
   - Expect gate chain with policy/approval gates.
2. **Swarm expansion test**
   - Provide onboarding data with automation scope.
   - Expect swarm tasks per onboarding stage.
3. **Executive branch test**
   - Include executive approval thresholds.
   - Expect approval gates in activation preview and in execution.
4. **Compute plane test**
   - Provide a numeric/symbolic request.
   - Expect deterministic compute plane output.

## 6) What to do next

1. Wire Gate Synthesis + Swarm systems into execution.
2. Add executive branch gate policies and onboarding schema.
3. Re-run activation preview and confirm `capability_alignment` = ready.

## 7) Customer operations & self-service automation (commercial readiness)

**Gap:** Remote access invitations, ticket management, update/rollback automation, and self-service onboarding are not wired to production services.  
**Solution:** Bind these workflows to the integration engine + governance scheduler, with explicit gates and audit trails.

Recommendations:
- **Remote access invites:** Integrate secure access provisioning (SSO/VPN) and log approvals via HITL gates.
- **Ticket management (Delphi AI):** Add a ticketing adapter to the integration engine and sync with librarian transcripts.
- **Update/rollback automation:** Register patch playbooks with the governance scheduler and require executive gates.
- **Self-service onboarding:** Expand onboarding prompts into templates that auto-generate gates, org charts, and contracts.

> **Competitive readiness note:** compare capability coverage only after `capability_review.automation_execution.status` is `validated`; until then, `capability_review.competitive_comparison` is advisory and should be validated through external benchmarks.

## 8) Capability rating & dynamic comparison (current vs. target)

**Current capability rating (Runtime 1.0):** **5/10**  
This reflects that previews, governance gates, and automation planning are present, but full execution wiring is still partial (gate synthesis, swarms, compute plane, and persistence require further integration).

**Dynamicity vs. full agentic runtime:**
- **Current system:** predictable, policy-driven, and structured around deterministic gates with limited dynamic task execution (runtime previews are richer than execution paths).
- **Target agentic runtime:** autonomous, event-driven, with self-updating memory and robust multi-channel execution (LLM + deterministic side are fully orchestrated).

**Design changes I would make if building the agentic runtime end-to-end:**
1. **Event-driven execution backbone:** move from request-response handlers to an event bus with durable queues.
2. **Persistent task memory:** unify LivingDocument, librarian transcripts, and gate state into a single persistent store.
3. **Runtime policy compiler:** compile governance rules into enforceable runtime constraints (not just previews).
4. **Deterministic + LLM routing:** standardize skill routing (compute plane vs. LLM) based on task schema, not heuristics.
5. **Multi-channel delivery adapters:** native adapters for email, chat, voice, and documents with uniform auditing.

## 9) Multi-channel output gap assessment (text, email, voice, chat, docs)

**Gap:** output is primarily JSON and HTML previews. There are no production adapters for email, chat, voice, or document generation.

**Closure plan:**
- **Document adapter:** add a report renderer (PDF/Markdown) tied to LivingDocument snapshots.
- **Email adapter:** integrate an email sending service with approval gates + audit logs.
- **Chat adapter:** publish to chat systems (Slack/Teams) with trigger hooks and escalation.
- **Voice adapter:** add text-to-speech integration for alerts or operational summaries.
- **Uniform dispatch layer:** register all adapters in the integration engine so each task can target multiple channels.

## 10) Updated gap assessment to reach fully operational status

1. **Execution wiring:** connect gate synthesis, TrueSwarmSystem, and compute plane to live execution.
2. **Persistence:** ensure LivingDocument, librarian context, and gate history are stored and replayable.
3. **Automation loop closure:** enable automated re-planning based on gate outcomes and HITL decisions.
4. **Channel readiness:** complete multi-channel adapters with deterministic auditing.
5. **Operational telemetry:** add system health + success metrics to validate real-world execution quality.
