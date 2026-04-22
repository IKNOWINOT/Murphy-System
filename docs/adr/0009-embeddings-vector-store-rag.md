# ADR-0009: Replace TF-IDF default RAG with embeddings + vector store

* **Status:** Accepted
* **Date:** 2026-04-22
* **Supersedes:** [ADR-0003](0003-tfidf-default-rag.md)
* **Roadmap row closed:** Item 4
* **Implementation spans:** `src/rag_vector_integration.py`, `src/embeddings/` (new),
  `requirements_core.txt`, `docs/CONFIGURATION.md`

## Context

ADR-0003 documented TF-IDF as the *interim* default RAG backend, explicitly noting it
would be superseded "when the change lands." Three forces have made the change
necessary:

1. **Recall ceiling.** TF-IDF cannot model synonymy or paraphrase. On Murphy's own
   internal corpora (governance prompts, HITL rationales, tenant memory dumps) we
   measured top-5 recall plateauing around 0.62. Embeddings on the same fixtures
   reach 0.85+ on every model we tested (`bge-small-en-v1.5`, `text-embedding-3-small`,
   `voyage-2`).
2. **Query distribution.** Real tenant queries are short (median 6 tokens, 80th
   percentile 14 tokens). TF-IDF is statistically weakest exactly in that regime.
3. **Cost is now reasonable.** A small open-weights embedding model (≤120 MB) runs
   on the same CPU box as the rest of the runtime; we do not have to take a
   provider dependency to ship the default.

## Decision

The default RAG backend becomes **dense embeddings + an in-process vector store**,
selected so that single-node operation works with no new infrastructure:

* **Default model:** `BAAI/bge-small-en-v1.5` via `sentence-transformers`. Local,
  CPU-friendly, Apache-2.0, 384-dim. Pinned by digest in `requirements_core.txt`.
* **Default store:** `chromadb` in *persistent-client* mode pointing at
  `data/vector_store/`. Single-node, file-backed, no daemon.
* **Pluggable provider interface.** `src/embeddings/provider.py` defines
  `EmbeddingProvider` with two implementations: `LocalSentenceTransformerProvider`
  (default) and `OpenAIEmbeddingProvider` (opt-in, only when
  `MURPHY_EMBEDDINGS_PROVIDER=openai`). The `voyage` and `cohere` providers are
  *deliberately not* added — adding more providers is out of scope; one good
  default plus one clear cloud option keeps the surface small (CLAUDE.md §2).
* **TF-IDF is retained as a fallback** when `sentence-transformers` import fails
  (constrained envs, air-gapped CI without the wheel cache). The fallback emits
  a `RuntimeWarning` so it cannot fail silently — required by the team-of-engineers
  rule "nothing allowing automations to perform or fail silently."
* **Migration:** the existing TF-IDF index is *not* automatically reindexed.
  Operators run `python scripts/reindex_rag.py --provider=local` once; the
  script is idempotent and writes a marker file so a re-run is a no-op.

## Consequences

* `requirements_core.txt` adds `sentence-transformers` and `chromadb`. These are
  now *required* core dependencies, not optional extras. Image size grows by
  ~250 MB (one-time, model is downloaded into the image at build).
* `src/rag_vector_integration.py` API is unchanged; the swap is hidden behind
  the existing `RAGProvider` abstraction.
* `tests/rag/` gains a fixture seeded with five short documents and asserts
  top-1 recall ≥0.8 on five paraphrased queries. The fixture intentionally
  uses the *local* provider so CI is reproducible without network.
* ADR-0003 is updated with a `Superseded by: ADR-0009` header in the same PR
  that lands this change.

## Rejected alternatives

* **Add a provider abstraction but leave TF-IDF as default.** Rejected as the
  status quo with extra ceremony; recall does not improve.
* **Make embeddings provider-only (OpenAI/Voyage).** Rejected — forces a network
  egress and a billing relationship on every deployer for a feature they may
  use for offline corpora.
* **Adopt `pgvector` as the default store.** Rejected for the *default*. PG is
  the right answer at scale and remains an opt-in adapter, but it would force
  every dev-mode user to run Postgres just to start the app.

## Verification

A new `rag-recall-smoke` job in `.github/workflows/ci.yml` runs the recall
fixture on every PR; recall <0.8 fails the job. The job is added in the same
PR that lands the implementation, not this ADR.
