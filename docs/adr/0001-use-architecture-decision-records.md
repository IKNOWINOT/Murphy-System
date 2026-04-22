# ADR-0001: Use Architecture Decision Records

* **Status:** Accepted
* **Date:** 2026-04-22

## Context

Murphy System has accumulated 80+ design documents in `docs/` describing what
each subsystem does. Newcomers to the codebase repeatedly ask the same
questions — "why did we pick DeepInfra?", "why is TF-IDF the default RAG?",
"why do we keep two copies of every config file?" — because the *rationale*
for these choices is scattered across PR threads, Slack messages, and tribal
knowledge. The descriptive docs answer *what* but not *why*.

Class S Roadmap, Item 16 explicitly calls for ADRs.

## Decision

We adopt the Michael Nygard ADR format and keep ADRs in `docs/adr/`. Each
significant architectural choice gets one ADR. ADRs are:

* numbered sequentially starting from 0001;
* **immutable** once accepted — when a decision changes, a new ADR
  supersedes the old one and the old one is marked `Superseded by ADR-NNNN`;
* short (one page is the target, two pages is the maximum);
* reviewed in the same PR as the code change that justifies them.

`docs/adr/README.md` maintains the index table.

## Consequences

* **Positive:** new contributors can answer "why" questions by reading
  five short documents instead of archaeology across years of PRs.
* **Positive:** changing a foundational decision becomes an explicit,
  reviewable act (a new ADR) rather than an invisible drift.
* **Negative:** small overhead per significant PR — one extra markdown file.
  We accept this; the cost is negligible compared to the cost of forgetting
  the rationale.
* **Negative:** pre-2026 decisions are unrecorded. We will write retroactive
  ADRs (0002–0006 in this initial batch) for the most consequential ones
  rather than leaving them undocumented.
