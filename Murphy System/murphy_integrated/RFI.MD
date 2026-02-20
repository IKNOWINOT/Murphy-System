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
| RFI-013 | Medium | No | Acronym mapping | Confirm your preferred names for source systems that previously used acronyms (IAM, ITSM, GRC, SIEM, CLM) so UI labels match your terminology. |
| RFI-014 | Medium | No | Micro-increment precision | Confirm default decimal precision for per-prompt micro-build display (`0.10`, `0.01`, `0.001`, etc.). |
| RFI-015 | Medium | No | Risk threshold tuning | Confirm preferred default threshold scale for “distance to finished” movement scoring used in recalibration prompts (e.g., 0–1 normalized). |

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

---

## IMPLEMENTED

- `RFI-001` | Reflected in section-level governance profile policies and section 14 continuity reporting; implementation ongoing for onboarding schema formalization. | Date: 2026-02-20
- `RFI-003` | Reflected in scope boundary + change-order authority policies (`section_scope_boundary_enforcement_policy`, `section_change_order_authority_policy`). | Date: 2026-02-20
- `RFI-012` | Reflected in shadow-account/user-base governance profile fields and section 14 logs. | Date: 2026-02-20
