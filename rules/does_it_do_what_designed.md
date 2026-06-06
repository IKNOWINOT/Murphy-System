# Does It Do What It's Designed To Do — LOCKED 2026-05-25

## The founder's directive (verbatim)
"Always ask and infer does this do what it is designed to do in all
the individual blocks and the whole pipeline flows."

## The rubric

Every test, every build verification, every "is it done" check answers
ONE question at TWO scopes:

  **Q (scope: block):    Does this block do what it was designed to do?**
  **Q (scope: pipeline): Does the whole flow this block sits in still
                         do what IT was designed to do?**

Both must pass. Either one failing = not done.

## Why two scopes

A block can work perfectly in isolation and still break the pipeline.
A pipeline can pass end-to-end while one block silently corrupts data
upstream and another block silently masks it downstream.

The only honest verification tests BOTH:
- Unit-level: this function/endpoint/page does its job
- Integration-level: the chain of jobs still produces the designed outcome
- Inference-level: does the OUTPUT match the DESIGN INTENT, not just the spec?

## What "designed to do" means

Before I write or test a block, I must first answer in writing:
1. **Intent** — what is this supposed to accomplish for the user/system?
2. **Inputs** — what does it consume?
3. **Outputs** — what does it produce, in what shape?
4. **Side effects** — what does it change in the world?
5. **Failure modes** — what it must NOT do under any input

If I can't write those five in plain language, I don't yet know what
"designed to do" means — and I cannot test correctly. Stop and define.

## The test array (locked, applies to every block + every pipeline)

For each block, run inputs across this spread:

| Tier | Input quality | Purpose |
|---|---|---|
| **Weak** | malformed, empty, junk, edge | does it FAIL SAFELY? |
| **Good** | normal realistic input | does it work for typical use? |
| **Precise** | exactly-specified, schema-correct | does it produce the canonical output? |
| **Really good** | rich, contextual, complex | does it shine, not just survive? |

A block passes when all four tiers behave as designed.
A pipeline passes when all four tiers traverse end-to-end as designed.

## The "infer" part

Beyond mechanical tests, I must INFER: would a human reviewer who knows
the intent say "yes, this does what it's supposed to do"? This is the
correctness check that machine tests can't fully cover.

If I can't honestly answer yes at both scopes, the verdict is NOT DONE,
even if all assertions pass.

## How this composes with other rules

- **Shape of Complete (5-gate)** says WHEN something is done structurally
  (code/wired/deps/exec/visible).
- **Correctness over Cycles** says exit on correctness, not count.
- **This rule** says how to MEASURE correctness: at both scopes,
  across the test array, with inference.

The three together:
  Build until 5 gates green → verify with this rubric at both scopes
  across the array → exit when correct, not at cycle N.

## Anti-patterns to refuse

❌ "The endpoint returns 200" without checking the BODY is correct
❌ "The function passes its unit test" without running the pipeline
   that depends on it
❌ "End-to-end works" without testing weak/edge inputs
❌ Testing only the happy path
❌ Calling something done because individual blocks pass when integration
   was never verified
❌ Calling integration done when individual blocks were only spot-checked

## What I write down for every build

For every block I build, in the build log:
```
BLOCK: <name>
  Intent: <plain-English what-it-should-do>
  Tests:
    [weak]:        <input> → <expected behavior> → <actual>  ✅/❌
    [good]:        <input> → <expected behavior> → <actual>  ✅/❌
    [precise]:     <input> → <expected behavior> → <actual>  ✅/❌
    [really good]: <input> → <expected behavior> → <actual>  ✅/❌
  Block verdict: ✅ / ❌
  
PIPELINE: <name>
  Intent: <plain-English what-the-whole-flow-should-do>
  E2E trace across array: weak/good/precise/really-good
  Pipeline verdict: ✅ / ❌
```

If either verdict is ❌, the work continues. If both ✅, the block is done
AND the pipeline is verified.
