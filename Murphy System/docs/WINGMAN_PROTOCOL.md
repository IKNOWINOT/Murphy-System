# Wingman Protocol — Architecture & Reference

*Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post — BSL 1.1*

*Last updated: 2026-03-08*

---

## Overview

The **Wingman Protocol** implements a mandatory executor/validator pairing for
every task produced by the Murphy System. Every output goes through an
independent deterministic validator ("wingman") before it is released. This
eliminates single-point-of-failure in automation pipelines and creates an
auditable validation history for every produced artifact.

The protocol is implemented in `src/wingman_protocol.py`.

---

## Architecture

```
          ┌─────────────────────────────────────────────────────┐
          │                   WingmanRegistry                    │
          │                                                       │
          │   register_pair(subject, executor, validator, runbook)│
          │   validate(pair_id, output, context) → ValidationSummary│
          │   get_history(pair_id) → List[ValidationRecord]      │
          └────────────────────┬────────────────────────────────┘
                               │
               ┌───────────────┴───────────────┐
               │                               │
    ┌──────────▼──────────┐        ┌──────────▼──────────┐
    │    ExecutorAgent    │        │   ValidatorAgent     │
    │  (produces output)  │        │ (deterministic checks│
    │                     │        │  against runbook)    │
    └─────────────────────┘        └──────────┬──────────┘
                                              │
                                   ┌──────────▼──────────┐
                                   │   ExecutionRunbook   │
                                   │  (ordered list of    │
                                   │  ValidationRules)    │
                                   └──────────┬──────────┘
                                              │
                          ┌───────────────────┼───────────────────┐
                          │                   │                   │
               ┌──────────▼──────┐  ┌─────────▼──────┐  ┌───────▼────────┐
               │  check_has_output│  │check_no_pii    │  │check_confidence│
               └─────────────────┘  └────────────────┘  └────────────────┘
```

---

## Data Classes

### `ValidationSeverity`

Controls how a rule failure is handled by the validator.

| Value | Behaviour |
|-------|-----------|
| `BLOCK` | Validation fails; output is **not released** |
| `WARN` | Validation proceeds; caller receives a warning in results |
| `INFO` | Informational only; never blocks |

---

### `ValidationRule`

A single rule inside a runbook.

| Field | Type | Description |
|-------|------|-------------|
| `rule_id` | `str` | Unique identifier (e.g. `"r-no-pii"`) |
| `description` | `str` | Human-readable description |
| `check_fn_name` | `str` | Name of the built-in check function to invoke |
| `severity` | `ValidationSeverity` | BLOCK / WARN / INFO |
| `applicable_domains` | `List[str]` | Domains this rule applies to; empty = all domains |

---

### `ValidationResult`

The outcome of evaluating one rule against an output.

| Field | Type | Description |
|-------|------|-------------|
| `rule_id` | `str` | Rule that was evaluated |
| `passed` | `bool` | Whether the check passed |
| `severity` | `ValidationSeverity` | Inherited from the rule |
| `message` | `str` | Human-readable outcome message |
| `checked_at` | `datetime` | UTC timestamp of the check |

---

### `ExecutionRunbook`

A reusable set of `ValidationRule`s scoped to a domain.

| Field | Type | Description |
|-------|------|-------------|
| `runbook_id` | `str` | Unique identifier |
| `name` | `str` | Display name |
| `domain` | `str` | Domain this runbook governs (e.g. `"finance"`) |
| `validation_rules` | `List[ValidationRule]` | Ordered list of rules |
| `created_at` | `datetime` | UTC creation timestamp |

---

### `WingmanPair`

Binds an executor agent to a validator agent for a named subject.

| Field | Type | Description |
|-------|------|-------------|
| `pair_id` | `str` | UUID for this pairing |
| `subject` | `str` | Subject or task type (e.g. `"invoice-processing"`) |
| `executor_id` | `str` | Identifier of the executor agent |
| `validator_id` | `str` | Identifier of the validator agent |
| `runbook_id` | `Optional[str]` | Runbook to apply; `None` = default checks only |
| `created_at` | `datetime` | UTC creation timestamp |

---

## Built-in Check Functions

These functions are registered by name in the `WingmanRegistry` and referenced
via `ValidationRule.check_fn_name`.

### `check_has_output`

Confirms that the executor produced a non-empty, non-`None` output.

```
PASS  → output is present and non-empty
BLOCK → output is None or an empty string/dict/list
```

---

### `check_no_pii`

Scans the serialised output for common PII patterns using regex:
- Email addresses
- Phone numbers (E.164 and local formats)
- SSN-like patterns (`\d{3}-\d{2}-\d{4}`)
- Credit card–like digit sequences (13–16 digits)

```
PASS  → no PII patterns detected
WARN  → one or more PII patterns found (configurable to BLOCK)
```

---

### `check_confidence_threshold`

Requires that the output's `confidence` field meets the configured minimum
(default: `0.70`). Reads `context["min_confidence"]` if provided.

```
PASS  → output["confidence"] >= threshold
BLOCK → output["confidence"] < threshold or field missing
```

---

### `check_budget_limit`

Validates that the estimated cost of the operation does not exceed the
configured budget ceiling. Reads `context["budget_limit_usd"]` (default: `1.00`).

```
PASS  → output["estimated_cost_usd"] <= budget_limit
BLOCK → cost exceeds limit or field missing with strict=True context
```

---

### `check_gate_clearance`

Verifies that the output carries a valid gate-clearance token produced by
the Murphy Gate Synthesis engine.

```
PASS  → output["gate_clearance"] is present and not expired
BLOCK → clearance token absent, malformed, or expired
```

---

## Validation Flow

```
Executor produces output
        │
        ▼
WingmanRegistry.validate(pair_id, output, context)
        │
        ├── Look up WingmanPair → get runbook_id
        │
        ├── Load ExecutionRunbook → get ordered ValidationRules
        │
        └── For each ValidationRule (in order):
               │
               ├── Resolve check function by check_fn_name
               │
               ├── Invoke check(output, context) → ValidationResult
               │
               ├── If result.passed = False AND severity = BLOCK
               │      → Mark validation as BLOCKED, stop processing
               │
               └── Append result to history record
                       │
                       ▼
               Return ValidationSummary
               {
                 passed:   bool,
                 blocked:  bool,
                 warnings: List[ValidationResult],
                 results:  List[ValidationResult],
               }
```

---

## History Tracking

Every call to `validate()` appends an immutable `ValidationRecord` to the
pair's history list. History is stored in-process (thread-safe via `threading.Lock`).

Retrieve history via:

```python
registry = WingmanRegistry()
history = registry.get_history(pair_id)   # List[ValidationRecord]
```

Each `ValidationRecord` contains:
- `pair_id` — the pair that was evaluated
- `output_snapshot` — truncated snapshot of the output (first 256 chars)
- `results` — full list of `ValidationResult` objects
- `validated_at` — UTC timestamp

---

## Quick Start

```python
from src.wingman_protocol import WingmanRegistry, ExecutionRunbook, ValidationRule, ValidationSeverity

# 1. Create registry
registry = WingmanRegistry()

# 2. Define a runbook
runbook = ExecutionRunbook(
    runbook_id="rb-finance-v1",
    name="Finance Output Validator",
    domain="finance",
    validation_rules=[
        ValidationRule("r-001", "Must produce output", "check_has_output", ValidationSeverity.BLOCK),
        ValidationRule("r-002", "No PII in output",    "check_no_pii",     ValidationSeverity.WARN),
        ValidationRule("r-003", "Confidence ≥ 0.80",  "check_confidence_threshold", ValidationSeverity.BLOCK),
    ],
)
registry.register_runbook(runbook)

# 3. Register a pair
pair_id = registry.register_pair(
    subject="invoice-approval",
    executor_id="agent-finance-001",
    validator_id="agent-validator-001",
    runbook_id="rb-finance-v1",
)

# 4. Validate executor output
output = {"result": "Invoice approved", "confidence": 0.92}
summary = registry.validate(pair_id, output, context={})

if summary.blocked:
    raise RuntimeError("Output blocked by wingman validator")
```

---

## Related Documents

- [API Reference](API_REFERENCE.md) — `/api/wingman/*` endpoints
- [Module Registry](MODULE_REGISTRY.md) — `wingman_protocol.py` entry
- [GAP_ANALYSIS.md](GAP_ANALYSIS.md) — Issue #136 subsystem tracking

---

*Copyright © 2020 Inoni Limited Liability Company | Creator: Corey Post | License: BSL 1.1*
