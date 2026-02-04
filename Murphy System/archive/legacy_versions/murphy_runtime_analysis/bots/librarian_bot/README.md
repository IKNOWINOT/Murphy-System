
# librarian_bot v1.1 — Hybrid rerank, safe remote fetch, ANN stub, GP auto-promotion, facets

**Additions**
- **Hybrid rerank** (configurable blend of lexical/semantic/freshness); semantic via RP-based proxy (no external SDK). If your system exposes a `MODEL_PROXY_URL`, swap in your true embedding/rerank.
- **Safe remote fetch** (allowlist, timeout, max bytes) → ingest as doc.
- **ANN/vector stub**: random projections per chunk stored in D1; fast cosine proxy.
- **Golden Path auto-promotion** (helper): `internal/gp/auto.ts` prepares frequent query keys; hook to your golden_paths recorder.
- **Facets**: tag buckets (`result.facets`) for UI filters.

**SLOs** (unchanged): lexical P50 < 150 ms; hybrid target < 500 ms; ingest ~300 ms; avg cost/run ≈ $0.0004.

**Register**
- run: `src/clockwork/bots/librarian_bot/librarian_bot.ts::run`
- ping: `src/clockwork/bots/librarian_bot/rollcall.ts::ping`

**Env**
- `LIBRARIAN_ALLOWLIST="example.com,docs.example.org"` for safe remote fetch.
- (Optional) add a true `model_proxy` bridge and replace RP semantic in `rank/hybrid.ts`.
