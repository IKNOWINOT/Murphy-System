# Compliance Roadmap — Murphy System

**Prepared by:** Corey Post, Inoni LLC  
**Last Updated:** 2026-03-05  
**Status:** DRAFT — Internal Strategic Document

---

## Overview

This document outlines the timeline, cost estimates, and resource requirements
for achieving SOC 2 Type II, ISO 27001, and HIPAA compliance certifications
for the Murphy System.

---

## Phase 1 — Foundation (Q2 2026)  *Target: May–June 2026*

| Work Item | Owner | Estimated Cost | Target Date |
|-----------|-------|----------------|-------------|
| Appoint Data Protection Officer (DPO) | Inoni LLC | $0 (internal) | 2026-05-01 |
| Complete Annex III legal review (EU AI Act) | External counsel | $8,000–$15,000 | 2026-05-01 |
| Deploy append-only gate event store (SOC 2 CC6.1) | Engineering | $2,000 (infra) | 2026-06-01 |
| Implement RBAC middleware for gate endpoints (ISO A.9.4.1) | Engineering | $5,000 | 2026-06-15 |
| Route audit logs to HIPAA-compliant backend (164.312(b)) | Engineering | $3,000 | 2026-05-30 |
| Forward ConfidenceResult to SIEM (ISO A.12.4.1) | Engineering | $2,500 | 2026-06-01 |

**Phase 1 Total Estimate:** $20,500–$27,500

---

## Phase 2 — Certification Prep (Q3 2026)  *Target: July–September 2026*

| Work Item | Owner | Estimated Cost | Target Date |
|-----------|-------|----------------|-------------|
| Implement HMAC-SHA256 integrity module (Patent #3, Art. 15) | Engineering | $6,000 | 2026-07-01 |
| Integrate PII scanner with COMPLIANCE gate (ISO A.18.1.4) | Engineering | $4,000 | 2026-07-15 |
| Draft ISO 9001-aligned QMS documentation (Art. 17) | Legal + Eng | $10,000 | 2026-08-01 |
| SOC 2 auditor engagement — scope definition | External auditor | $15,000–$25,000 | 2026-07-01 |
| ISO 27001 gap assessment with certified auditor | External auditor | $12,000–$20,000 | 2026-08-01 |
| Deploy Prometheus + Grafana SLO dashboards (SOC 2 A1.2) | Engineering | $1,500 | 2026-07-01 |
| IEC 61508 / IEC 62443 gap analysis for IoT deployment | Engineering + Legal | $8,000 | 2026-09-01 |

**Phase 2 Total Estimate:** $56,500–$74,500

---

## Phase 3 — Certification (Q4 2026–Q1 2027)

| Work Item | Owner | Estimated Cost | Target Date |
|-----------|-------|----------------|-------------|
| SOC 2 Type II examination (12-month audit window) | External auditor | $25,000–$40,000 | 2027-Q1 |
| ISO 27001 certification audit | Certification body | $15,000–$25,000 | 2026-Q4 |
| HIPAA third-party assessment | External assessor | $10,000–$18,000 | 2026-Q4 |
| HR-specific HITL workflow for employment AI (Annex III §5) | Engineering | $8,000 | 2026-Q4 |
| Staff HIPAA / privacy training | HR | $3,000 | 2026-Q4 |

**Phase 3 Total Estimate:** $61,000–$94,000

---

## Total Cost Estimate

| Phase | Low | High |
|-------|-----|------|
| Phase 1 — Foundation | $20,500 | $27,500 |
| Phase 2 — Cert Prep | $56,500 | $74,500 |
| Phase 3 — Certification | $61,000 | $94,000 |
| **TOTAL** | **$138,000** | **$196,000** |

*Estimates exclude ongoing annual renewal fees (~$20,000–$35,000/year).*

---

## Key Risks

1. **Legal review delay** — Annex III classification requires external counsel; budget for 6–8 week lead time.
2. **SIEM integration complexity** — Log pipeline architecture may require vendor selection.
3. **SOC 2 audit window** — Type II requires 12 months of operating evidence; start date governs certification date.
4. **IEC 61508 SIL-2** — Manufacturing certification path may require third-party testing laboratory.

---

## VERIFIED BY: Corey Post — Inoni LLC

© 2020-2026 Inoni Limited Liability Company. All rights reserved.
