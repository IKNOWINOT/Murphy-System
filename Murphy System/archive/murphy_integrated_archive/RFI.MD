# Murphy System — Request for Information (RFI) Ledger

This ledger tracks decisions required to unblock architecture wiring, governance enforcement, and section 1–14 implementation closure.

## Status model

- **OPEN**: decision needed before full implementation.
- **ANSWERED**: user provided decision; implementation work is queued or in progress.
- **IMPLEMENTED**: decision has been incorporated into runtime/docs/tests.

## Response format

- Reply with: `RFI-<ID>: <decision>` for each item.
- If undecided: `RFI-<ID>: defer`.

---

## OPEN (follow-up only)

| ID | Priority | Blocking | Topic | Follow-up needed |
| --- | --- | --- | --- | --- |
| RFI-016 | Low | No | External Module Source | `universal_control_plane`, `inoni_business_automation`, `two_phase_orchestrator` exist in MODULE_CATALOG but their source packages are not in the `murphy_integrated/` tree. They import via try/except and gracefully degrade. Should they be ported into `src/` as stubs or remain external? |
| RFI-017 | Low | No | Uncatalogued Source Files | 263 Python files in `src/` are sub-modules of catalogued packages (e.g., `confidence_engine/`, `execution_engine/`, `learning_engine/` internals). These are indirectly covered by their parent catalog entry. Confirm this indirect coverage model is acceptable vs. explicit registration. |
| RFI-018 | Medium | No | Screenshot Currency | `docs/screenshots/` contains 40 screenshots from system setup (Feb 9, 2026). New modules added since then (ML strategy, content creator, digital assets, video streaming, remote access, security hardening) have no corresponding screenshots. Should new screenshots be generated? |

---

## ANSWERED

- **RFI-001** | Decision: Org design is **position-based** from onboarded org charts. If missing, system derives minimal org chart + position contracts from industry/domain/work-type intake; each org position receives a shadow agent. User accounts are separate from org profiles; role assignment is org-scoped. | Date: 2026-02-19 | Owner: @IKNOWINOT
- **RFI-002** | Decision: Collect industry + business model during onboarding; if no formal model exists, infer gating metrics from industry/work-type and current condition toward annual goal. | Date: 2026-02-19 | Owner: @IKNOWINOT
- **RFI-003** | Decision: Scope boundary is proposal/request envelope. Out-of-scope work becomes Change Order with pushback logic; HITL approvals required for production expansion decisions. | Date: 2026-02-19 | Owner: @IKNOWINOT
- **RFI-004** | Decision: Same as RFI-003; Change Orders are scope-reasonableness checks against existing proposal scope. | Date: 2026-02-19 | Owner: @IKNOWINOT
- **RFI-005** | Decision: Compliance/budget standards are established during proposal by explicitly declaring standards and tasks. | Date: 2026-02-19 | Owner: @IKNOWINOT
- **RFI-006** | Decision: Compliance/risk requirements are inferred from onboarding-selected domains that require those controls. | Date: 2026-02-19 | Owner: @IKNOWINOT
- **RFI-007** | Decision: “Source of truth” is a Rosetta-stone style production notes layer derived from onboarding (turnover information between agents/automations). | Date: 2026-02-19 | Owner: @IKNOWINOT
- **RFI-008** | Decision: Legacy orchestrator mapping is architecture-led; implement best-fit based on current code architecture. | Date: 2026-02-19 | Owner: @IKNOWINOT
- **RFI-009** | Decision: Deterministic replay/compute defaults delegated to architecture recommendation. | Date: 2026-02-19 | Owner: @IKNOWINOT
- **RFI-010** | Decision: Progress movement should reflect “actual movement based on distance to finished”; recalibrate estimates as needed. | Date: 2026-02-19 | Owner: @IKNOWINOT
- **RFI-011** | Decision: Verification strictness varies by deterministic-side risk assessment. | Date: 2026-02-19 | Owner: @IKNOWINOT
- **RFI-012** | Decision: User accounts and organization accounts are separate; users can be invited to orgs; shadow agents stay user-bound and may be licensed back. Org automations have Automator Admin role removable only by owner/board-designated authority; founder-side escalation path exists for owner credential incidents. | Date: 2026-02-19 | Owner: @IKNOWINOT

- **RFI-013** | Decision: Use industry-standard acronym expansions for UI labels: IAM = Identity & Access Management, ITSM = IT Service Management, GRC = Governance Risk & Compliance, SIEM = Security Information & Event Management, CLM = Contract Lifecycle Management. Expand on first use in UI, abbreviate thereafter. | Date: 2026-02-24 | Owner: architecture-led
- **RFI-014** | Decision: Default micro-increment precision is `0.01` (two decimal places) for per-prompt completion tracking, matching the current assessment tracker format. | Date: 2026-02-24 | Owner: architecture-led
- **RFI-015** | Decision: Use 0–1 normalized scale for distance-to-finished movement scoring. Recalibration triggers when delta exceeds 0.05 between consecutive prompts. | Date: 2026-02-24 | Owner: architecture-led

---

## IMPLEMENTED

- `RFI-001` | Reflected in section-level governance profile policies and section 14 continuity reporting; implementation ongoing for onboarding schema formalization. | Date: 2026-02-20
- `RFI-003` | Reflected in scope boundary + change-order authority policies (`section_scope_boundary_enforcement_policy`, `section_change_order_authority_policy`). | Date: 2026-02-20
- `RFI-012` | Reflected in shadow-account/user-base governance profile fields and section 14 logs. | Date: 2026-02-20
- `RFI-013` | Acronym mappings documented in architecture; UI labels use expanded form on first use. | Date: 2026-02-24
- `RFI-014` | Micro-increment precision set to 0.01 in assessment tracker (section 9). | Date: 2026-02-24
- `RFI-015` | Risk threshold scale uses 0–1 normalized with 0.05 recalibration trigger. | Date: 2026-02-24
