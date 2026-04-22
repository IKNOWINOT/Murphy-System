# ADR-0006: Blockchain-style append-only audit ledger for self-modification

* **Status:** Accepted
* **Date:** 2026-04-22 (retroactive)
* **Implementation:** `src/blockchain_audit_trail.py`,
  `src/platform_self_modification/`, `src/founder_self_modification_engine.py`

## Context

Murphy can modify its own code, configuration, and policy: the platform
self-modification pipeline lets agents propose patches that, after passing
the HITL gate (ADR-0004), are applied to the running system. This is the
single highest-risk capability in the codebase.

If a malicious or compromised actor — internal, external, or an agent
prompt-injected — submitted a self-modification, our forensic position must
be unambiguous: we must be able to say *exactly* what changed, *who or what*
proposed it, *who* approved it, and prove that no one has since rewritten
the record. Conventional database tables fail this test because anyone with
write access (including a compromised process) can edit history.

## Decision

Every self-modification event is committed to an **append-only,
hash-chained** ledger:

* Each record includes the modification payload, the proposer identity,
  the approver identity, the HITL ticket reference, and the hash of the
  previous record.
* Records are sealed with the previous record's hash, so any rewrite of a
  past entry invalidates every subsequent hash.
* The ledger head is periodically anchored to durable storage (and, for
  high-trust deployments, to an external timestamping service).
* The ledger is **read-only** to application code by default; writes go
  through a single audited entry point in `blockchain_audit_trail.py`.

We deliberately did **not** adopt a distributed/proof-of-work blockchain.
The cost (latency, energy, complexity, governance) does not match the
benefit at our deployment scale. What we need is *tamper-evident history*,
not *trustless consensus among mutually distrustful parties*. A single-writer
hash chain is the right tool.

## Consequences

* **Positive:** any post-incident forensics on self-modification has an
  authoritative, tamper-evident timeline.
* **Positive:** the ledger doubles as a regulatory artifact — useful for
  EU AI Act conformity assessments and SOC 2 change-management evidence.
* **Positive:** simple to operate: a single Postgres table plus a small
  amount of cryptographic discipline at the writer. No external
  blockchain dependency.
* **Negative:** if the ledger is corrupted (catastrophic disk failure
  between snapshots), it cannot be silently repaired — the chain breaks
  visibly. We treat this as a feature: backup discipline must be real.
* **Negative:** operators must understand that "blockchain" here does not
  mean what the consumer-press "blockchain" means. We have repeatedly had
  to disambiguate this in security reviews.
