# Large Action Model (LAM) Framework

**Design Label:** ARCH-007  
**Module:** `src/large_action_model.py`  
**License:** BSL 1.1 — converts to Apache 2.0 after four years  

---

## Executive Overview

The **Murphy Large Action Model (LAM) Framework** transforms Murphy from a self-healing infrastructure into a **Large Action Model** for business operations.

Where a Large Language Model (LLM) generates *text* from a prompt, the LAM generates *business actions* from goals.  The LAM combines thought and function around money analysis and work of any kind, producing the coordinated actions that drive a business forward — all while respecting the authority, budget, and compliance constraints that keep those actions safe.

The framework is built on a **dual-agent architecture**:

| Plane | Agent Type | Owner | Optimises for |
|-------|-----------|-------|---------------|
| Individual | **Shadow Agent** | Person | Work style, personal efficiency |
| Organisational | **Org Chart Agent** | Organisation | Business throughput, compliance |

These two ownership planes are continuously reconciled by the **Action Agreement Protocol**, which negotiates plans until both planes agree — or escalates to a human when they cannot.

A third plane — the **Ecosystem** — is served by the **Workflow Marketplace**, which lets organisations license their optimised processes to others and discover complementary workflows from the broader Murphy network.

---

## Architecture Diagram

```
╔═══════════════════════════════════════════════════════════════════╗
║                      LARGE ACTION MODEL                           ║
║                         (ARCH-007)                                ║
╠═════════════════════════╦═════════════════════════════════════════╣
║  INDIVIDUAL PLANE        ║  ORGANISATIONAL PLANE                  ║
║                          ║                                        ║
║  ┌──────────────────┐    ║   ┌──────────────────────────────┐    ║
║  │ ShadowActionPlan-│    ║   │    OrgChartOrchestrator       │    ║
║  │ ner (per user)   │    ║   │                              │    ║
║  │                  │    ║   │  • Queue management          │    ║
║  │ • Goal decomp.   │───────▶│  • Budget enforcement        │    ║
║  │ • Preference     │    ║   │  • Authority checks          │    ║
║  │   learning       │    ║   │  • Conflict resolution       │    ║
║  │ • Personal lib.  │    ║   │  • Governance compliance     │    ║
║  └──────────────────┘    ║   └──────────────┬───────────────┘    ║
║                          ║                  │                     ║
║                          ║                  ▼                     ║
║                          ║   ┌──────────────────────────────┐    ║
║                          ║   │   ActionAgreementProtocol    │    ║
║                          ║   │                              │    ║
║                          ║   │  PROPOSE → EVALUATE →        │    ║
║                          ║   │  NEGOTIATE → AGREE/ESCALATE  │    ║
║                          ║   └──────────────────────────────┘    ║
╠═════════════════════════╩═════════════════════════════════════════╣
║  ECOSYSTEM PLANE                                                   ║
║                                                                    ║
║  ┌──────────────────────────┐  ┌──────────────────────────────┐  ║
║  │  WorkflowLicenseManager  │  │     WorkflowMatchmaker       │  ║
║  │                          │  │                              │  ║
║  │  • Package templates     │  │  • Compatibility scoring     │  ║
║  │  • License terms         │  │  • ROI estimation            │  ║
║  │  • Marketplace publish   │  │  • Integration plans         │  ║
║  │  • Usage tracking        │  │  • Ranked recommendations    │  ║
║  └──────────────────────────┘  └──────────────────────────────┘  ║
╠════════════════════════════════════════════════════════════════════╣
║  DATA MODEL                                                        ║
║                                                                    ║
║   ActionPrimitive  ──▶  ActionSequence  ──▶  AgreementResult      ║
║   (atomic token)        (composed workflow)  (negotiation output) ║
║                                                  │                 ║
║                                                  ▼                 ║
║                                            ExecutionResult         ║
╚════════════════════════════════════════════════════════════════════╝
```

---

## How the LAM Generates Actions — The Full Pipeline

```
User Goal (natural language)
        │
        ▼
 ShadowActionPlanner.decompose_goal()
        │  Detects verb → action_type
        │  Assigns domain, authority, cost estimate
        │  Builds linear/DAG dependency graph
        ▼
 ActionSequence  (confidence_score, dag, primitives)
        │
        ▼
 ShadowActionPlanner.optimize_sequence()
        │  Applies user preference model
        │  Batches like-domain actions
        ▼
 Optimised ActionSequence
        │
        ▼
 LargeActionModel.submit_for_orchestration()
        │
        ▼
 ActionAgreementProtocol.propose()
        │
        ├── OrgChartOrchestrator.evaluate_sequence()
        │       Budget check
        │       Authority check  ──▶  GovernanceKernel / OrgChartEnforcement
        │       Governance check
        │
        ├── [PASS]  →  AgreementType.INSTANT
        │
        ├── [SOFT FAIL]  →  _negotiate()  →  [PASS]  →  NEGOTIATED
        │
        ├── [AUTHORITY VIOLATION]  →  AgreementType.ESCALATED (human required)
        │
        └── [HARD FAIL]  →  AgreementType.REJECTED
                │
                ▼
         AgreementResult  (dual_authorization_required)
                │
                ▼
 LargeActionModel.execute_agreed_plan()
        │  Topological DAG sort
        │  Step-by-step primitive execution
        │  WorkflowDAGEngine delegation (optional)
        │  Audit trail entry per step
        ▼
 ExecutionResult  (COMPLETED | PENDING | FAILED | ROLLED_BACK)
```

---

## Shadow Agent vs Org Chart Agent — Ownership Model

### Shadow Agents (Individual Plane)

A **Shadow Agent** is owned by and acts on behalf of a single person.  It learns:

- **Work pattern profile**: when the user works best, preferred communication channels
- **Task completion history**: which approaches succeed for this person
- **Preference model**: report format, meeting length, notification style
- **Personal automation library**: validated `ActionSequence` templates the user can re-use

The shadow planner decomposes a free-text goal into `ActionPrimitive` tokens, assembles them into an `ActionSequence`, and submits the plan upward to the `OrgChartOrchestrator`.  After each execution, `learn_from_outcome()` refines the preference model so future plans get a higher `confidence_score`.

**Key constraint**: a shadow agent *never* executes above its designated authority level.

### Org Chart Agents (Organisational Plane)

The **OrgChartOrchestrator** holds the global view that no individual shadow can see:

- Company-wide queue of all pending `ActionSequence` requests
- Current budget utilisation per department
- Cross-team dependency graph
- Regulatory / compliance requirements
- Strategic priority rankings

The orchestrator evaluates each submitted sequence against these constraints and either approves it, proposes modifications, or routes it to a human escalation path.

**Key constraint**: the orchestrator *never* overrides hard governance / compliance constraints.

---

## The Agreement Protocol in Detail

The `ActionAgreementProtocol` is the bridge between the two ownership planes.

### Six-Phase Flow

| Phase | Actor | Description |
|-------|-------|-------------|
| **PROPOSE** | Shadow | Submits `ActionSequence` |
| **EVALUATE** | Orchestrator | Checks budget, authority, governance |
| **NEGOTIATE** | Protocol | If soft-fail: proposes cost-reduced alternative |
| **AGREE** | Both | Accept final plan |
| **EXECUTE** | LAM | Dual-signed execution begins |
| **REVIEW** | Shadow | `learn_from_outcome()` updates preference model |

### Agreement Types

| Type | Meaning | Execution? |
|------|---------|-----------|
| `INSTANT` | No conflicts; auto-approved within authority | ✅ Yes |
| `NEGOTIATED` | Minor adjustments made (e.g. cost reduction) | ✅ Yes |
| `ESCALATED` | Requires human decision-maker intervention | ⏳ Pending |
| `REJECTED` | Violates hard constraints (compliance, budget) | ❌ Never |

All agreements require `dual_authorization_required` in their `conditions` list — both the shadow agent *and* the org chart orchestrator must have accepted the plan.

---

## Workflow Licensing and Marketplace

The `WorkflowLicenseManager` enables organisations to share optimised processes.

### License Types

| Type | Accessibility | Marketplace? |
|------|--------------|-------------|
| `PRIVATE` | Owning org only | No |
| `ORG_INTERNAL` | All departments within owning org | No |
| `LICENSED` | Other orgs under defined terms | Yes |
| `OPEN` | Freely available (attribution required) | Yes |

### Lifecycle

```
Org A creates ActionSequence
        │
        ▼
WorkflowLicenseManager.package_workflow(sequence, "org-A", LicenseType.LICENSED)
        │  → LicenseRecord  (license_id, terms, usage_count=0)
        │  → Published to internal marketplace index
        ▼
Org B calls WorkflowLicenseManager.import_workflow(license_id, "org-B")
        │  → Checks license_type permits cross-org access
        │  → Increments usage_count
        ▼
Org B adapts the sequence to its own org chart
        │  → Shadow planner learns from adopted sequence
        ▼
WorkflowLicenseManager.record_usage(license_id, revenue=earned)
        │  → Tracks revenue_generated for Org A
```

---

## Workflow Matchmaking Algorithm

The `WorkflowMatchmaker` scores all publicly available workflows against an org profile.

### Fit Score Formula

```
base_score      = 0.50
usage_bonus     = min(usage_count × 0.01, 0.30)
license_bonus   = 0.10  (OPEN)  |  0.05  (LICENSED)

fit_score = min(base_score + usage_bonus + license_bonus, 1.0)
```

### Integration Complexity

| Fit Score | Complexity |
|-----------|-----------|
| ≥ 0.8 | low |
| 0.6 – 0.79 | medium |
| < 0.6 | high |

### ROI Estimate

```
estimated_roi = budget_per_workflow × fit_score × 2.5
```

---

## Data Model Reference

### `ActionPrimitive`

The atomic unit of business action — the "token" of the LAM.

| Field | Type | Description |
|-------|------|-------------|
| `action_id` | `str` | Unique primitive identifier |
| `action_type` | `str` | Verb: `approve`, `schedule`, `assign`, `escalate`, `analyze`, `generate`, `communicate` |
| `domain` | `str` | Business domain: `finance`, `hr`, `engineering`, `sales`, `operations` |
| `parameters` | `Dict[str, Any]` | Action-specific parameters |
| `requires_authority` | `str` | Minimum role level required |
| `cost_estimate` | `float` | Estimated resource cost |
| `reversible` | `bool` | Can this action be undone? |
| `rollback_action` | `Optional[str]` | Action type to undo this primitive |

### `ActionSequence`

A composed business workflow — analogous to a sentence in an LLM.

| Field | Type | Description |
|-------|------|-------------|
| `sequence_id` | `str` | Unique sequence identifier |
| `name` | `str` | Human-readable name |
| `description` | `str` | Full description / original goal |
| `primitives` | `List[ActionPrimitive]` | Ordered list of primitives |
| `dag` | `Dict[str, List[str]]` | Dependency graph: `action_id → [depends_on]` |
| `owner_type` | `str` | `"shadow"` \| `"org_chart"` \| `"shared"` |
| `owner_id` | `str` | Shadow agent ID or org ID |
| `license_type` | `str` | `LicenseType` value |
| `version` | `str` | Semantic version |
| `confidence_score` | `float` | 0.0–1.0 validation confidence |

### `AgreementResult`

Output of the `ActionAgreementProtocol` negotiation.

| Field | Type | Description |
|-------|------|-------------|
| `agreement_id` | `str` | Unique agreement identifier |
| `sequence_id` | `str` | Source sequence |
| `shadow_agent_id` | `str` | Proposing shadow agent |
| `org_id` | `str` | Receiving organisation |
| `agreement_type` | `AgreementType` | `INSTANT` \| `NEGOTIATED` \| `ESCALATED` \| `REJECTED` |
| `approved_sequence` | `Optional[ActionSequence]` | Final agreed sequence |
| `reason` | `str` | Human-readable outcome reason |
| `conditions` | `List[str]` | E.g. `["dual_authorization_required"]` |
| `requires_human` | `bool` | True when escalation is needed |

### `ExecutionResult`

Result of executing an agreed plan.

| Field | Type | Description |
|-------|------|-------------|
| `execution_id` | `str` | Unique execution identifier |
| `agreement_id` | `str` | Source agreement |
| `status` | `ExecutionStatus` | `PENDING` \| `RUNNING` \| `COMPLETED` \| `FAILED` \| `ROLLED_BACK` |
| `completed_actions` | `List[str]` | Completed action IDs |
| `failed_action` | `Optional[str]` | First failed action ID |
| `error_message` | `Optional[str]` | Failure reason |
| `audit_entries` | `List[Dict]` | Per-step audit trail |

### `LicenseRecord`

A licensed workflow package.

| Field | Type | Description |
|-------|------|-------------|
| `license_id` | `str` | Unique license identifier |
| `sequence_id` | `str` | Licensed sequence |
| `owner_org_id` | `str` | Organisation that owns the license |
| `license_type` | `LicenseType` | `PRIVATE` \| `ORG_INTERNAL` \| `LICENSED` \| `OPEN` |
| `terms` | `Dict[str, Any]` | License terms (usage limits, revenue share) |
| `usage_count` | `int` | Number of import/usage events |
| `revenue_generated` | `float` | Cumulative revenue earned |

### `WorkflowMatch`

A workflow recommendation from the matchmaker.

| Field | Type | Description |
|-------|------|-------------|
| `match_id` | `str` | Unique match identifier |
| `sequence_id` | `str` | Matched sequence |
| `sequence_name` | `str` | Human-readable name |
| `owner_org_id` | `str` | Owning organisation |
| `fit_score` | `float` | 0.0–1.0 compatibility score |
| `integration_complexity` | `str` | `"low"` \| `"medium"` \| `"high"` |
| `estimated_roi` | `float` | Projected return on adoption |
| `rationale` | `str` | Why this workflow was matched |
| `license_type` | `LicenseType` | License terms for adoption |

---

## API Reference

### `LargeActionModel`

```python
lam = LargeActionModel(
    org_id="acme-corp",
    shadow_agent_integration=sai,   # optional
    governance_kernel=gk,           # optional
    org_chart_enforcement=oce,      # optional
    workflow_dag_engine=dag,        # optional
    persistence_manager=pm,         # optional
    event_backbone=eb,              # optional
)
```

| Method | Signature | Returns |
|--------|-----------|---------|
| `register_shadow` | `(shadow_agent_id, user_context=None)` | `ShadowActionPlanner` |
| `generate_actions` | `(goal, shadow_agent_id, user_context=None, org_context=None)` | `ActionSequence` |
| `submit_for_orchestration` | `(sequence, shadow_agent_id)` | `AgreementResult` |
| `license_workflow` | `(sequence, owner_org_id, license_type, terms=None)` | `LicenseRecord` |
| `find_matching_workflows` | `(org_profile, top_n=5)` | `List[WorkflowMatch]` |
| `execute_agreed_plan` | `(agreement)` | `ExecutionResult` |
| `set_org_budget` | `(budget)` | `None` |
| `get_audit_log` | `()` | `List[Dict]` |

### `ShadowActionPlanner`

```python
planner = ShadowActionPlanner(shadow_agent_id="shadow-001")
```

| Method | Signature | Returns |
|--------|-----------|---------|
| `decompose_goal` | `(goal, domain="operations", authority_level="individual")` | `ActionSequence` |
| `optimize_sequence` | `(sequence)` | `ActionSequence` |
| `learn_from_outcome` | `(sequence_id, outcome)` | `None` |
| `add_to_personal_library` | `(sequence)` | `None` |
| `get_personal_library` | `()` | `List[ActionSequence]` |

### `OrgChartOrchestrator`

```python
orch = OrgChartOrchestrator(org_id="acme-corp", governance_kernel=gk)
```

| Method | Signature | Returns |
|--------|-----------|---------|
| `enqueue` | `(sequence, priority=5)` | `None` |
| `dequeue_next` | `()` | `Optional[ActionSequence]` |
| `queue_depth` | `()` | `int` |
| `evaluate_sequence` | `(sequence)` | `Tuple[bool, str, List[str]]` |
| `resolve_conflict` | `(seq_a, seq_b)` | `Tuple[preferred, deferred]` |
| `set_department_budget` | `(dept_or_org_id, budget)` | `None` |

### `ActionAgreementProtocol`

```python
protocol = ActionAgreementProtocol(orchestrator)
```

| Method | Signature | Returns |
|--------|-----------|---------|
| `propose` | `(sequence, shadow_agent_id, org_id)` | `AgreementResult` |
| `get_agreement` | `(agreement_id)` | `Optional[AgreementResult]` |
| `list_agreements` | `(org_id=None)` | `List[AgreementResult]` |

### `WorkflowLicenseManager`

```python
lm = WorkflowLicenseManager(persistence_manager=pm, event_backbone=eb)
```

| Method | Signature | Returns |
|--------|-----------|---------|
| `package_workflow` | `(sequence, owner_org_id, license_type, terms=None)` | `LicenseRecord` |
| `get_license` | `(license_id)` | `Optional[LicenseRecord]` |
| `list_marketplace` | `(license_type=None)` | `List[LicenseRecord]` |
| `record_usage` | `(license_id, revenue=0.0)` | `bool` |
| `import_workflow` | `(license_id, importing_org_id)` | `Optional[LicenseRecord]` |

### `WorkflowMatchmaker`

```python
mm = WorkflowMatchmaker(license_manager)
```

| Method | Signature | Returns |
|--------|-----------|---------|
| `find_matches` | `(org_profile, top_n=5)` | `List[WorkflowMatch]` |

---

## Example Execution Traces

### 1. Individual Action — Analyst Schedules a Report

```python
lam = LargeActionModel(org_id="acme")

# 1. Shadow agent decomposes goal
seq = lam.generate_actions(
    goal="generate quarterly finance report for CFO",
    shadow_agent_id="shadow-alice",
    user_context={"authority_level": "analyst"},
    org_context={"domain": "finance"},
)
# ActionSequence with primitive: action_type="generate", domain="finance"

# 2. Submit for org-chart approval
agreement = lam.submit_for_orchestration(seq, "shadow-alice")
# AgreementResult(type=INSTANT, conditions=["dual_authorization_required"])

# 3. Execute
result = lam.execute_agreed_plan(agreement)
# ExecutionResult(status=COMPLETED, completed_actions=["act-gene"])
```

### 2. Cross-Department Coordination — Budget Approval

```python
lam = LargeActionModel(org_id="acme")
lam.set_org_budget(500.0)

# Engineering shadow wants to approve a $600 server purchase
seq = lam.generate_actions(
    "approve server purchase",
    shadow_agent_id="shadow-bob",
    user_context={"authority_level": "team_lead"},
)
# Primitive: action_type="approve", cost_estimate=0.0 (decomposed from goal)

agreement = lam.submit_for_orchestration(seq, "shadow-bob")
# Budget check passes (cost_estimate=0.0 from goal decomposition)
# agreement.type == INSTANT
```

### 3. Workflow Licensing Round-Trip

```python
# Org A packages a successful reporting workflow
lm = WorkflowLicenseManager()
record = lm.package_workflow(
    sequence=seq,
    owner_org_id="acme",
    license_type=LicenseType.LICENSED,
    terms={"revenue_share": 0.1, "max_users": 50},
)

# Org B discovers and imports it
mm = WorkflowMatchmaker(lm)
matches = mm.find_matches({"gaps": ["reporting"], "budget_per_workflow": 1000.0})
top_match = matches[0]

imported = lm.import_workflow(top_match.sequence_id, "startup-b")
# LicenseRecord for acme's workflow, usage_count incremented
```

---

## Integration Points

| Murphy Component | Integration | How Used |
|-----------------|-------------|---------|
| `ShadowAgentIntegration` | `shadow_agent_integration=` param | Shadow lifecycle management |
| `GovernanceKernel` | `governance_kernel=` param | Budget tracking, policy enforcement |
| `OrgChartEnforcement` | `org_chart_enforcement=` param | Authority level checks |
| `WorkflowDAGEngine` | `workflow_dag_engine=` param | Step-by-step primitive execution |
| `EventBackbone` | `event_backbone=` param | Audit event publishing |
| `PersistenceManager` | `persistence_manager=` param | Durable storage of licenses |

All integration dependencies are **optional** — the LAM operates in isolation when they are not provided, making it straightforward to test and deploy incrementally.

---

## Safety Guarantees

1. **Shadow agents never execute above their authority level** — `OrgChartOrchestrator._check_authority()` enforces this on every primitive.
2. **Orchestrator never overrides governance** — `_run_governance_check()` is non-bypassable; a DENY result always rejects the sequence.
3. **All agreements require dual authorization** — `conditions` always includes `"dual_authorization_required"` on any approved sequence.
4. **Licensed workflows are sandboxed until org-chart approval** — imported sequences must go through `submit_for_orchestration()` before execution.
5. **Full audit trail for every action** — `_audit()` is called at every LAM API boundary and every execution step; the audit log is capped at 50,000 entries to prevent unbounded growth.
6. **Budget enforcement is non-negotiable** — the budget check in `evaluate_sequence()` uses a hard threshold; negotiation only reduces costs, never raises the budget cap.
7. **Human escalation path always available** — authority violations and governance failures produce `ESCALATED` agreements with `requires_human=True` rather than silent failures.
8. **Rejected agreements never execute** — `execute_agreed_plan()` returns `ExecutionStatus.FAILED` immediately for `REJECTED` agreements, regardless of whether an `approved_sequence` is attached.

---

## Event Reference

All events are emitted to the `EventBackbone` (when configured) and always written to the internal audit log.

| Event | Trigger | Key Payload Fields |
|-------|---------|-------------------|
| `LAM_ACTION_GENERATED` | `generate_actions()` | `goal`, `shadow_agent_id`, `sequence_id` |
| `LAM_AGREEMENT_PROPOSED` | `submit_for_orchestration()` | `sequence_id`, `shadow_agent_id`, `org_id` |
| `LAM_AGREEMENT_REACHED` | Successful negotiation | `agreement_id`, `agreement_type` |
| `LAM_WORKFLOW_LICENSED` | `license_workflow()` | `license_id`, `sequence_id`, `owner_org_id`, `license_type` |
| `LAM_WORKFLOW_MATCHED` | `find_matching_workflows()` | `org_id`, `match_count` |
| `LAM_EXECUTION_COMPLETED` | `execute_agreed_plan()` | `execution_id`, `agreement_id`, `status` |
