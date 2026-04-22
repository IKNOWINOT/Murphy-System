# Architecture Decision Records (ADRs)

This directory captures the **why** behind the major architectural choices
in the Murphy System. The rest of `docs/` describes *what* the system does;
ADRs explain *why* it was built that way and *what alternatives were rejected*.

ADRs are immutable once accepted: when a decision changes, a new ADR is
written that references and supersedes the old one. The old ADR remains in
place so that the historical reasoning is preserved.

Format
------

Each ADR uses the lightweight [Michael Nygard format](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions):

* **Status** — Proposed / Accepted / Superseded by ADR-NNNN
* **Context** — what forced the decision, what constraints applied
* **Decision** — what we chose
* **Consequences** — what follows, including the trade-offs we accepted

Index
-----

| ADR  | Title                                                           | Status   |
|------|-----------------------------------------------------------------|----------|
| 0001 | Use Architecture Decision Records                               | Accepted |
| 0002 | DeepInfra is the primary LLM provider                           | Accepted |
| 0003 | TF-IDF is the default RAG backend until embeddings ship         | Accepted |
| 0004 | Human-in-the-loop (HITL) gate is mandatory for all agent action | Accepted |
| 0005 | Canonical source layout: `Murphy System/` mirrored to root      | Accepted |
| 0006 | Blockchain-style append-only audit ledger for self-modification | Accepted |
| 0007 | OpenTelemetry tracing is opt-in, not on-by-default              | Accepted |

Adding a new ADR
----------------

1. Copy the next number (e.g. `0007-my-decision.md`).
2. Fill in Status / Context / Decision / Consequences.
3. Add a row to the Index above.
4. Open a PR — the ADR is reviewed alongside the code change it justifies.
