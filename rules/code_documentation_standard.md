# Murphy Codebase Documentation Standard
**Locked: 2026-05-24 — All patches PATCH-406a and after MUST comply.**

Murphy reads its own source code. Documentation is not optional — it is
load-bearing. If Murphy can't understand why a block exists, Murphy can't
maintain it autonomously.

## Required for every new module

### 1. Module header (top of file)
```python
"""
PATCH-XXX — <Human-readable name>
==================================

WHAT THIS IS:
  <One paragraph explaining what this module does in plain English.>

WHY IT EXISTS:
  <The problem it solves. What was broken/missing before this.>

HOW IT FITS:
  <Where this sits in the Murphy stack. What it depends on. What depends on it.>

KEY CONCEPTS:
  - <concept>: <one-line definition>
  - <concept>: <one-line definition>

ENDPOINTS / PUBLIC SURFACE:
  <List every endpoint, public function, or import others use>

DEPENDENCIES:
  <Other Murphy modules + external libs this needs>

VAULT SECRETS USED (if any):
  <List names of PATCH-405 secrets this fetches>

EVENT SPINE EMISSIONS (if any):
  <List event types this emits>

KNOWN LIMITS:
  <Honest list of what doesn't work yet or breaks at scale>

LAST UPDATED: <YYYY-MM-DD by whom>
"""
```

### 2. Section headers (within file)
Use box-drawing comments to separate logical sections:
```python
# ── Section Name ────────────────────────────────────────────────────────────
```

### 3. Function docstrings
Every public function/method needs:
```python
def thing(arg1: str, arg2: int) -> Dict[str, Any]:
    """
    Brief one-line summary.

    Longer explanation if needed — what this does in the larger context,
    why it returns what it returns, what callers should know.

    Args:
        arg1: What it is, what valid values look like.
        arg2: Same.

    Returns:
        Shape of the return dict. Example: {"ok": bool, "value": str}

    Raises:
        WhatExceptions: Under what conditions.

    Example:
        >>> thing("foo", 42)
        {"ok": True, "value": "fooo"}
    """
```

### 4. Inline comments for non-obvious logic
- Magic numbers → comment why
- Workarounds → comment the bug being worked around
- Performance tricks → comment what you measured
- Security-relevant code → mark with `# SECURITY:` prefix
- Things future-Murphy might "fix" but shouldn't → mark `# DO NOT TOUCH:`

### 5. TODO / FIXME format
```python
# TODO(PATCH-406b): Wire Deepgram STT here once 406b lands.
# FIXME: This breaks if call duration > 60min — see Twilio media stream docs.
```

Always include the patch number that will fix a TODO so Murphy can plan its
own work.

## For Murphy reading its own code

When Murphy reads a file, the first 30 lines should give it enough context to
know:
- What this is
- Whether modifying it is safe
- Who else cares about it
- What to test if changes are made

If those four questions aren't answered in the first 30 lines, the doc header
is incomplete.

## Anti-patterns to avoid

- ❌ "This function does X" (useless if X is obvious from the name)
- ❌ Commenting WHAT instead of WHY
- ❌ Stale comments (if you change code, change the comment in the same commit)
- ❌ Commented-out code left in place (delete it; git remembers)
- ❌ Cryptic abbreviations without expansion in the docstring

## Reference exemplars

These patches set the standard — Murphy should look here when learning the style:
- `src/patch405_secrets_vault.py` — vault module, hash-chained audit
- `src/patch406a_voice_telephony.py` — voice telephony foundation
