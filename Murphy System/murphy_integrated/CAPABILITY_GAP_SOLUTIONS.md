# Capability Gap Solutions (Runtime 1.0)

This document captures the best recommendations for closing the current capability gaps using the modules already present in the repository.

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
