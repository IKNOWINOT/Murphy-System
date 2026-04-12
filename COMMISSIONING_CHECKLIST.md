# Commissioning Checklist

**Purpose:** Every module touched during production hardening MUST have this
checklist completed before the change is considered done. This is the
as-built record that proves the module was properly commissioned.

Copy this template into your PR description for each module changed.

---

## Module: [name]

**File(s):** `src/[path]`  
**Subsystem:** [subsystem name]  
**Commissioned by:** [author]  
**Date:** [YYYY-MM-DD]

### Commissioning Questions

| # | Question | Answer |
|---|----------|--------|
| 1 | **Does the module do what it was designed to do?** | [ ] Yes / [ ] No — [evidence] |
| 2 | **What exactly is the module supposed to do?** | [clear statement of purpose, may evolve with design decisions] |
| 3 | **What conditions are possible based on the module?** | [list: normal operation, edge cases, error states, concurrency, resource exhaustion] |
| 4 | **Does the test profile reflect the full range of capabilities and conditions?** | [ ] Yes / [ ] No — [list tests, identify gaps] |
| 5 | **What is the expected result at all points of operation?** | [per-condition expected outcomes] |
| 6 | **What is the actual result?** | [test run output, manual verification notes] |
| 7 | **If problems remain, how do we restart from symptoms?** | [N/A if all passing, otherwise describe restart procedure] |
| 8 | **Has all ancillary code and documentation been updated?** | [ ] Docstrings [ ] API docs [ ] README [ ] CHANGELOG [ ] as-builts |
| 9 | **Has hardening been applied?** | [ ] Error handling [ ] Input validation [ ] Logging [ ] Rate limiting [ ] Type hints |
| 10 | **Has the module been re-commissioned after changes?** | [ ] Yes — [date, test results summary] |

### Test Evidence

```
# Paste pytest output here
pytest tests/test_[module].py -v --tb=short
```

### MCB Commission Harness Evidence (if applicable)

```python
# Paste ProbeResult / CommissionSpec evidence here
CommissionSpec(page="...", element="...", expected="...")
ProbeResult(spec_id="...", passed=True, actual="...")
```

---

## Automated Commissioning Validator

The commissioning questions above can be validated automatically using the
`ProductionCommissioningValidator` module (Design Label: `COMMISSION-VAL-001`):

```python
from src.production_commissioning_validator import ProductionCommissioningValidator

validator = ProductionCommissioningValidator()
report = validator.commission_module(
    module_path="src/llm_provider.py",
    test_dir="tests/llm",
    commissioned_by="engineering-team",
)
print(validator.generate_report_markdown(report))
```

The validator performs static analysis (via `ast`) on each module to check:
- **Q1/Q2:** Module imports cleanly and has a purpose docstring
- **Q3:** Error handling exists (try/except blocks)
- **Q4/Q5/Q6:** Corresponding test files exist, contain assertions, and are pytest-discoverable
- **Q7:** Error recovery patterns present (try/except with logging)
- **Q8:** All public functions/classes have docstrings
- **Q9:** Hardening indicators (type hints, error codes, logging, input validation)
- **Q10:** Module file and test file modification timestamps are consistent

Run `validator.generate_report_markdown(report)` to produce a markdown report
suitable for embedding in PR descriptions.

---

## Quick Reference

**Severity levels for gaps:**
- **P0 — Blocker:** Module does not function at all
- **P1 — Critical:** Core functionality broken or missing
- **P2 — Major:** Important feature incomplete or unreliable
- **P3 — Minor:** Edge case or polish issue
- **P4 — Cosmetic:** Documentation or naming only

**"No new features" rule:**
- ✅ Complete a function with docstring but empty body
- ✅ Wire an existing endpoint that's defined but not registered
- ✅ Add error handling to an existing flow
- ✅ Fix a bug discovered during commissioning
- ❌ Add a new endpoint not in existing documentation
- ❌ Add a new module not referenced anywhere
- ❌ Change the architecture of an existing module
