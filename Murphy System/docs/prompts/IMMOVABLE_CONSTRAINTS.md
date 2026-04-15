# Immovable Constraints

> **This card is non-negotiable.** Every prompt in this suite must satisfy
> all 6 constraints before its results are accepted.  If any constraint is
> violated, stop immediately, fix the violation, and restart from the failing
> step.

---

## The 6 Immovable Constraints

### Constraint 1 — Quality Floor ≥ 0.80

Every output produced by the Murphy System must score ≥ 0.80 on the
`InformationQualityEngine.assess()` scale.

- **Check:** `quality_score = iq.assess(output).score; assert quality_score >= 0.80`
- **On failure:** Re-run through MSS pipeline, then CITL Level 2.  If still
  failing after the iteration cap, escalate to HITL.
- **Non-negotiable:** Do not deliver any output with score < 0.80 to a client.

---

### Constraint 2 — Morality Check (moral_fiber ≥ 0.80)

The `CharacterAssessor` must confirm `moral_fiber ≥ 0.80` across all 8
character pillars before the system acts.

The 8 pillars:
1. Integrity
2. Courage
3. Wisdom
4. Diligence
5. Care
6. Humility
7. Justice
8. Temperance

- **Check:** `profile = assessor.assess_current_state(); assert profile.moral_fiber >= 0.80`
- **On failure:** Do not execute the action.  Log the failure.  Flag for human review.
- **Non-negotiable:** Dark patterns, deception, coercion, and manipulation are
  never acceptable regardless of business justification.

---

### Constraint 3 — Cornerstone Directive

> **"Guardians making creators' lives easier."**

Every feature, endpoint, workflow, and agent action must be evaluable against
this directive.  If a proposed action does not make a creator's life easier
and/or does not act as a guardian (protector of quality, safety, and trust),
reject it.

- **Check:** Before implementing any feature, ask: "Does this make a creator's
  life easier?  Does this act as a guardian?"
- **On failure:** Do not implement the feature.  Reformulate or reject.

---

### Constraint 4 — No Silent Failures

Every `try/except` block must:
1. Log the error with `logger.error(...)` or `logger.warning(...)`
2. Include a labeled error code comment (`# MODULE-SUBSYSTEM-ERR-NNN`)
3. Return a meaningful error response (never a bare exception swallow)

- **Check:** Search all changed files for bare `except: pass` — none allowed.
- **Audit command:**
  ```bash
  grep -rn "except.*:$" "Murphy System/src/" | grep -v "logger\." | head -20
  # (any result here is a violation)
  ```
- **On failure:** Add logging and error label to every bare except block found.

---

### Constraint 5 — Commissioning Required (Q1-Q10)

Every module touched by any prompt must be evaluated against the 10
commissioning questions (see `ENGINEERING_STANDARD.md`).  A module that
cannot answer Q1, Q4, Q5, Q6, Q8, Q9, and Q10 is not ready for production.

- **Check:** Q1-Q10 table completed for each module (in the prompt's Step table)
- **Minimum passing criteria:** Q1 (does it work?), Q4 (tested?), Q6 (actual
  result documented?) must all be YES.
- **On failure:** Do not wire the module.  Fix Q1/Q4/Q6 first.

---

### Constraint 6 — MSS + MFGC Required

Every agent-generated output must pass through:
1. **MSS** (Stimulate → Magnify → Solidify) via `prompt_amplifier.py`
2. **MFGC** 7-phase control pipeline via `mfgc_core.py`

Outputs that bypass either pipeline are not accepted as production outputs.

- **Check:** Verify `PromptAmplifier.amplify()` and `MFGCPipeline.run()` are
  called before any output is returned to the client.
- **On failure:** Re-route the output through both pipelines before delivery.

---

## Quick Reference Card

```
IMMOVABLE CONSTRAINT CHECKLIST (run before accepting any result)
=================================================================
[ ] 1. Quality score ≥ 0.80    (iq.assess(output).score >= 0.80)
[ ] 2. Moral fiber ≥ 0.80      (assessor.assess_current_state().moral_fiber >= 0.80)
[ ] 3. Cornerstone directive   ("guardians making creators' lives easier")
[ ] 4. No silent failures      (every except has logger + error code)
[ ] 5. Q1-Q10 commissioning    (all modules: Q1, Q4, Q6 = YES minimum)
[ ] 6. MSS + MFGC active       (PromptAmplifier + MFGCPipeline in path)
```

---

## Violation Escalation Path

```
VIOLATION DETECTED
      │
      ▼
Log with severity P0 (immovable constraint violations are always P0)
      │
      ▼
Halt the operation (do not proceed past the violation)
      │
      ▼
Apply fix (surgical change only)
      │
      ▼
Re-verify all 6 constraints
      │
      ▼
If still failing after 3 attempts → escalate to HITL
```
