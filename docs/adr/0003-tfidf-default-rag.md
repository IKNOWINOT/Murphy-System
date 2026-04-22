# ADR-0003: TF-IDF is the default RAG backend until embeddings ship

* **Status:** Accepted (interim)
* **Date:** 2026-04-22 (retroactive)
* **Will be superseded by:** the ADR that lands real embeddings + a vector
  store as the default RAG backend (Class S Roadmap, Item 4).

## Context

`src/rag_vector_integration.py` exposes a uniform retrieval interface used by
the agent reasoning loop, the knowledge base manager, and several
domain-specific subsystems. It supports four backends:

1. **TF-IDF** (scikit-learn) — pure Python, no model download, no network.
2. **ChromaDB** — local vector store with persisted collections.
3. **pgvector** — vectors stored in the existing Postgres deployment.
4. **Hosted embeddings** — through `MurphyLLMProvider`.

The non-TF-IDF backends require either (a) downloading a 80–400 MB
embedding model, (b) running an extra service, or (c) a network round-trip
per indexed chunk. None of those are acceptable defaults during local
development, CI, or the cold-start of a fresh tenant.

## Decision

TF-IDF is the **default** RAG backend. The other backends are opt-in,
selected by environment variable (`MURPHY_RAG_BACKEND=tfidf|chroma|pgvector|embeddings`).

This is an **interim** decision. The Class S roadmap commits to flipping the
default to a real embedding backend (Item 4). When that work lands, this ADR
will be marked `Superseded by ADR-NNNN`.

## Consequences

* **Positive:** zero-setup RAG works out of the box for new contributors and
  CI runs.
* **Positive:** retrieval works for every tenant on day one, even before
  embedding infrastructure is provisioned.
* **Negative:** TF-IDF retrieval quality is meaningfully worse than dense
  embeddings on paraphrase-heavy queries, which is a substantial fraction of
  what users actually ask. We accept the quality gap until Item 4 lands.
* **Negative:** users who deploy without changing the env var get a
  degraded experience and may not realize there is a better default. The
  startup banner in `startup_feature_summary.py` explicitly logs the active
  RAG backend so this is at least observable.
