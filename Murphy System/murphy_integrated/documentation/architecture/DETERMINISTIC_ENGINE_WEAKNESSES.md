# Deterministic Engine – Weaknesses & Faulty Assumptions

This document enumerates inherent weaknesses and faulty assumptions in the deterministic engine so mitigations can be tracked and audited.

## 1) Assumption: Inputs Are Complete and Accurate
- **Weakness:** Deterministic pipelines assume required inputs are present and correct. Missing or inconsistent data can produce confident but wrong outputs.
- **Mitigation:** Enforce required-field gates; halt generation when required inputs are missing; log evidence lineage in the ledger.

## 2) Assumption: Rules Capture Real‑World Exceptions
- **Weakness:** Static rules miss edge cases or regulatory exceptions, leading to brittle outputs.
- **Mitigation:** Add exception taxonomy and HITL override paths; audit false positives/negatives and update rules.

## 3) Assumption: Thresholds Are Universally Valid
- **Weakness:** Single confidence thresholds can misrepresent risk across domains or jurisdictions.
- **Mitigation:** Use domain‑specific thresholds (policy packs) and track threshold tuning history in the ledger.

## 4) Assumption: Deterministic Outputs Are Always Safe to Execute
- **Weakness:** Even deterministic outputs can violate business intent if upstream inputs drift.
- **Mitigation:** Drift detection + periodic revalidation; require approvals for high‑impact actions.

## 5) Assumption: Domain Packs Are Stable Over Time
- **Weakness:** Domain knowledge and regulations change, invalidating old rules.
- **Mitigation:** Version domain packs, expire stale rules, and enforce scheduled reviews.

## 6) Assumption: Taxonomies Are Sufficiently Granular
- **Weakness:** Over‑general taxonomies hide nuance, leading to incorrect mappings.
- **Mitigation:** Maintain hierarchical taxonomies with “unknown/other” capture and escalation.

## 7) Assumption: Determinism Equals Auditability
- **Weakness:** Deterministic outcomes are only auditable if full lineage is logged.
- **Mitigation:** Always log inputs, transformations, model/rule versions, and approvals.

## 8) Assumption: Inferred Data Can Be Treated Like Provided Data
- **Weakness:** Mixing inferred and provided data collapses accountability.
- **Mitigation:** Tag data by source type and gate inferred‑data usage.

---

## Immediate Control Checklist
- [ ] Required‑field gates enforced
- [ ] Policy/threshold packs versioned
- [ ] Ledger captures input lineage
- [ ] HITL overrides logged
- [ ] Drift detectors enabled
