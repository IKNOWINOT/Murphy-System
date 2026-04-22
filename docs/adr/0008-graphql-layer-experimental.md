# ADR-0008: Mark the custom GraphQL layer experimental, slate for removal

* **Status:** Accepted
* **Date:** 2026-04-22
* **Implementation:** `src/graphql_api_layer.py` (731 LOC),
  `tests/integration_connector/test_graphql_api_layer.py` (976 LOC)

## Context

`src/graphql_api_layer.py` is a 731-line stdlib-only GraphQL execution
engine — schema dataclasses, query parser, AST executor, introspection
support — written from scratch rather than depending on `graphql-core` or
`strawberry`. The roadmap (`docs/ROADMAP_TO_CLASS_S.md` Item 13) flagged
it for a graduate-vs-delete decision.

A direct survey of the codebase confirms the situation:

* **Not wired into the production HTTP surface.** `src/runtime/app.py`
  contains zero references to `graphql_api_layer` or to a `/graphql`
  route. The subsystem registry has docstring examples that mention it
  but no live registration.
* **No external client uses it.** The GraphQL mentions in
  `src/universal_integration_adapter.py` are *outbound* URLs to Linear,
  Railway, and ProductHunt's GraphQL APIs — completely unrelated.
* **One internal touchpoint:** `src/murphy_terminal/command_registry.py`
  registers a `!murphy graphql` terminal command, but it is a thin shell
  that has no production traffic.
* **Test surface is large:** the dedicated test file is 976 lines and
  passes today. Deleting blindly throws away that signal.

The competing pressures are:

1. **Surface-area discipline** (Class S grading rubric, Item 20): every
   line of code that compiles is a line that has to be maintained, audited
   for security, and proven not to break on every refactor. 1 700 LOC of
   unused engine + tests is real cost.
2. **Optionality**: a previous owner saw value in this layer. Outright
   deletion in one PR forecloses the option of bringing GraphQL back
   later if a real consumer materialises.
3. **Reversibility cost asymmetry**: deletion is irreversible without git
   archaeology; deferred deletion is cheap. Keeping the code without a
   plan is the worst of both worlds — it accumulates rot indefinitely.

## Decision

The custom GraphQL layer is **marked experimental** and **slated for
removal** on a defined schedule:

1. The module gains an explicit `__experimental__ = True` marker and a
   `DeprecationWarning` at import time naming this ADR.
2. The roadmap row (Item 13) is updated to point at this ADR, with a
   removal target of **the next major version bump** (or 90 days from
   this ADR's date, whichever comes first).
3. If between now and the removal date a production consumer is
   identified, the path forward is to **replace** the custom engine with
   `strawberry` (mature, typed, FastAPI-native, ~1/3 the LOC) and write
   a superseding ADR. We do not graduate the bespoke implementation.
4. If no consumer materialises by the removal date, the module and its
   tests are deleted in a single PR that cites this ADR.

We deliberately do **not** delete it in this PR because:

* The 976 lines of passing tests are non-trivial signal that someone
  may still depend on the surface in a way the static survey missed.
* A 90-day cooling-off window is cheap insurance against that risk and
  forces an explicit "yes, we still want this" or "no, delete it" call
  from a future maintainer rather than letting the question linger.

## Consequences

* The module continues to import cleanly so any out-of-tree caller does
  not break overnight; the `DeprecationWarning` makes them visible.
* The Item 20 surface-area heatmap (`scripts/find_unused_modules.py`)
  will keep flagging this module — that is the desired behaviour, not
  noise to suppress. The allowlist is reserved for *runtime-loaded*
  modules, not for deprecated ones.
* The Class S Roadmap row for Item 13 is updated from `⏳ Decision required`
  to `🟡 Decided — experimental, removal scheduled` so the audit trail
  reflects the call.
* No ADR rewrite is required when the module is finally deleted; that
  PR cites this ADR as its justification.

## Rejected alternatives

* **Graduate as-is (mark stable, write public docs).** Rejected. The
  bespoke parser does not implement the full GraphQL spec, has no
  subscription support, and would compete with the FastAPI/REST surface
  that all current clients already use. Promoting it would entrench
  ~700 LOC of duplicated routing logic.
* **Replace with `strawberry` immediately.** Rejected as premature.
  Adding a real GraphQL dependency (and the operational surface that
  comes with it — N+1 query risks, schema versioning, dataloader
  patterns) for zero current consumers fails the "boring is good" test
  and would itself need an ADR documenting the consumer it serves.
* **Delete in this PR.** Rejected for the reasons in Decision §
  above — the cooling-off window costs nothing and protects against the
  one failure mode (an undiscovered consumer) that the static survey
  cannot rule out with full confidence.
