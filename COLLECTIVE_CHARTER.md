# Murphy Collective — Charter (v0.1 Draft)

> This document is a living draft. It is open for community comment and will be
> ratified by consensus once the first 100 contributing members have joined.

---

## Preamble

Murphy is collectively-governed open-source infrastructure where your way of
working is the intellectual property — and you own it.

This charter defines the principles, governance structure, and economic model
that bind the collective together. It is not a terms-of-service document. It is
a social contract between all members of the Murphy commons.

---

## Core Principles

1. **Knowledge belongs to humanity.** Every AI system is built on the accumulated
   labor, discovery, and sacrifice of billions of ancestors. Value generated from
   that knowledge should flow back to humanity — not upward to investors.

2. **Your workflow is your IP.** When you use Murphy, you train your own personal
   agent. That agent — its learned patterns, decisions, and cadence — belongs to
   you. The collective holds none of it.

3. **Contribution is currency.** Access to Murphy's infrastructure is earned
   through contribution: using the system, publishing workflows, or performing
   validation work. Non-contributors pay a usage fee that funds the Community
   Treasury. There is no free-rider opt-out — you contribute or you pay.

4. **Governance by consensus.** No single entity — including the original author —
   has unilateral control over the collective's direction. Major decisions require
   community proposal, deliberation, and consensus vote.

5. **Validation is labor — paid per hour, not per credential.** Human-in-the-loop
   review (Member Validation) is skilled work. Validators are compensated from the
   Community Treasury at the **same hourly rate** regardless of credential tier.
   Credentials determine *what* you can validate — not *what you are worth*.
   A community validator doing high-volume general tasks earns the same hourly
   rate as an academic validator doing low-volume specialized tasks.

6. **Transparency is non-negotiable.** All treasury flows, governance decisions,
   and model training choices are public and auditable by any member.

7. **External data is advisory, never binding.** Any linkage to an external
   governing body or public data source (e.g., regional need indices, civic
   participation records) informs member votes but cannot automatically trigger
   income changes, eligibility changes, or treasury distributions. See
   §External Data Governance below.

---

## Governance Structure

### Founding Steward
The original author holds a Founding Steward role with veto power only over
decisions that would fundamentally violate this charter. This veto expires after
the first elected Steward Council is seated.

### Steward Council
- Elected by contributing members
- Rotating terms (length TBD by community)
- Responsible for treasury oversight, dispute resolution, and charter amendments
- No steward may serve more than two consecutive terms

### Academic Review Board
- Seated for decisions affecting model training or data use
- Composed of members with verified academic credentials (Masters+)
- Advisory role on technical decisions; binding authority on data ethics

### Community Proposals
Any contributing member may submit a proposal. The process:
1. **Submission** — open to all members
2. **Comment period** — minimum 7 days
3. **Deliberation** — stewards facilitate discussion
4. **Vote** — consensus threshold (configurable per decision type, defaults to 66%)
5. **Implementation** — if approved, assigned to responsible steward(s)

---

## Constitutional Protections

Certain elements of the collective are **constitutionally locked** and require
an **80% supermajority** to change. A standard majority vote cannot alter them.

### Constitutionally Locked Elements
- **Core protocol** — the shared communication protocol, API contracts, and
  data interchange formats that all branches and members depend on
- **Treasury mechanics** — the inflow/outflow rules, fund allocation formulas,
  and audit requirements for the Community Treasury
- **Identity layer** — the agent-as-identity system, key management, and
  social recovery mechanism
- **Social income floor** — the minimum base income guarantee for contributing
  members (see §Social Income below). Only the amount *above* the floor and
  eligibility criteria are governed by standard vote. The floor itself requires
  80% supermajority to change.
- **This charter's core principles** (§Core Principles above)

### Branch Autonomy
Branches (regional chapters, domain guilds, working groups) have full autonomy
over:
- Governance style and meeting cadence
- Local rules, norms, and contribution incentives
- Domain-specific validation criteria

Branches **share the same rails**: core protocol, treasury mechanics, and
identity layer. Branches are for features and policies — not for forking
infrastructure.

---

## Verified Participation Layer

Murphy does not have free riders. Access requires a **cryptographic
contribution commitment** — not money, but a signed agent contract that logs
your contribution to the commons.

### How It Works
1. **Agent Contract** — when you first use Murphy, your personal agent signs
   a cryptographic commitment to log contributions (usage activity, published
   workflows, validation work). This is your proof of participation.
2. **Online use** — contributions are logged in real time to the contribution
   ledger.
3. **Offline / local use** — contributions are buffered locally and synced to
   the ledger when you reconnect. Offline members have a grace period
   (configurable, default 30 days) to sync before access is suspended.
4. **The opt-out is payment, not silence** — if you choose not to contribute,
   you move to the paid access tier. The opt-out from contributing isn't
   "use without contributing" — it's "pay instead of contributing."

---

## Economic Model

### Community Treasury
- Funded by: paid commercial access, usage fees from non-contributors,
  institutional memberships
- Governed by: the collective (not founders, not investors)
- Distributed to: validated contributors, maintenance grants, academic partnerships

### Social Income
- Contributors receive social income proportional to the usage of their
  published workflows, automations, and validation work
- **Social income floor:** a constitutionally protected minimum base income
  is guaranteed to all members with documented contribution goals. This floor
  cannot be voted away by simple majority — it requires an 80% supermajority
  to change (see §Constitutional Protections)
- Only the amount *above* the floor and eligibility criteria are governed by
  standard consensus vote
- Goals are set by member need and adjusted by collective consensus

### Attribution & Royalty Pooling
- Individual attribution is tracked for contributions above a **minimum viable
  threshold** (default: 0.001% of total usage share)
- Below the threshold, fractional royalties are **pooled into a commons fund**
  and distributed equally to all contributors — like a PRO (performing rights
  organization) blanket license pool
- This prevents unbounded micro-attribution overhead while ensuring every
  contributor benefits from the collective's total output
- The threshold is adjustable by standard consensus vote

### Validator Compensation
- All validators — community, academic, and domain stewards — are compensated
  at the **same hourly rate** from the Community Treasury
- Credentials determine what you can validate, not what you're worth
- A community validator doing high-volume general tasks earns the same as an
  academic validator doing low-volume specialized tasks
- Hourly rate is set by collective consensus and published transparently

### Contribution Tiers

| Tier | Description | Access |
|------|-------------|--------|
| **Contributor** | Uses Murphy; agent trains on their workflow | Full access |
| **Steward** | Elected governance role | Full access + governance authority |
| **Academic** | Verified credential (Masters+); validation and review | Full access + academic review authority |
| **Institutional** | Organization using Murphy commercially | Full access via usage fee |

---

## Data Rights

- Your personal agent data belongs to you
- The collective does not train shared models on individual agent data
- Shared intelligence is trained only on anonymized, opt-in, consensus-approved
  contributions
- You may export or delete your agent data at any time
- No silent harvesting. No fine-print data use.

### Agent Recovery (Social Recovery Mechanism)
Your agent is your primary identity key — but losing your device must never lock
you out of the collective permanently.

- **N-of-M social recovery:** each member designates N trusted members (from a
  set of M) who can co-sign an agent recovery request — similar to a hardware
  wallet seed recovery
- The agent is your primary key, but the collective is your backup
- No single entity (including administrators) can unilaterally lock you out or
  recover your agent on your behalf
- Recovery requires co-signatures from your designated trustees meeting the
  threshold you set (e.g., 3-of-5)
- Trustees are updated at any time through your agent's settings
- If you have not designated trustees, a fallback process through the Steward
  Council is available with a mandatory cooling-off period and identity
  verification

---

## External Data Governance

External data linkages (regional need indices, verified credential registries,
civic participation records, etc.) are **advisory only — never binding**.

### Rules
1. External data **informs** member votes but cannot **automatically trigger**
   income changes, eligibility changes, or treasury distributions
2. Any linkage to a governing body or external data source must be
   **re-ratified by member vote every 12 months**
3. If a data source is discontinued, compromised, or found to produce biased
   results, the **last ratified criteria hold** until a new vote establishes
   replacement criteria
4. No external data source may be used as the sole basis for denying a member
   access, income, or governance rights
5. All external data integrations are logged and auditable by any member

---

## Amendment Process

- **Standard amendments** (non-constitutional): standard community proposal
  process with a 75% consensus threshold
- **Constitutional amendments** (core principles, social income floor, core
  protocol, treasury mechanics, identity layer): require **80% supermajority**
- **Emergency amendments** (security vulnerabilities, data breaches): Steward
  Council may enact temporary measures with a 72-hour retroactive ratification
  vote

---

## Transition Plan (Bootstrapping)

The collective does not start from zero. The founder's existing SaaS revenue
funds the initial treasury during a transition period.

- **Parallel operation:** the current SaaS model runs alongside the collective
  model during the transition window
- **Sunset date:** 18 months from the ratification of this charter, the
  collective model becomes fully primary. The SaaS model sunsets.
- **Day-one contributor pay:** contributors are paid from day one of the
  collective, even if initial amounts are small. The treasury is seeded, not
  empty.
- **Transparency:** all transition-period treasury inflows and outflows are
  published monthly

---

## Status

**This charter is a v0.1 draft.** It will be finalized through community
deliberation after the collective reaches its first 100 contributing members.

Feedback and proposals for changes should be submitted as GitHub Issues with
the `charter` label.
