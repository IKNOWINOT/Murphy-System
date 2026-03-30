# Open Source Strategy — Murphy System

**Prepared by:** Corey Post, Murphy Collective  
**Last Updated:** 2026-03-05  
**Status:** APPROVED — Internal Strategic Document

---

## Objective

Establish a dual-license open-source strategy that drives community adoption
and ecosystem growth while protecting proprietary IP and enabling commercial
revenue.

---

## Module Classification

### Open Source (Apache 2.0 — Community Tier)

| Module | Rationale |
|--------|-----------|
| `murphy_confidence` — types, engine, gates, compiler | Core algorithm — community validation of MFGC formula accelerates trust |
| `murphy_confidence` test suites | Transparency builds confidence in safety claims |
| LangChain safety layer (duck-typed) | Drives ecosystem integrations |
| Demo scripts (healthcare, financial, manufacturing) | Showcases capabilities, generates leads |
| EU AI Act compliance mapping utilities | Positions Murphy as compliance partner |

### Proprietary (Commercial License — Enterprise Tier)

| Module | Rationale |
|--------|-----------|
| Full Murphy System orchestrator | Core product differentiator |
| Production-grade HITL workflow engine | Enterprise revenue driver |
| Real-time SIEM / audit log integration | Regulated-industry premium feature |
| Cryptographic integrity module (Patent #3) | Patent-protected; enterprise tier only |
| Trained domain models (healthcare, finance, manufacturing) | Data-derived IP |
| Multi-tenant SaaS platform | Hosted service |
| Compliance report generation (SOC 2 / ISO / HIPAA) | Professional services upsell |

---

## Dual-License Model

### Community Edition (Apache 2.0)
- **Who:** Researchers, startups, individual developers, non-profits
- **What:** `murphy_confidence` library + demos + integrations
- **Cost:** Free
- **Restrictions:** Must retain copyright notices; cannot use Inoni trademarks

### Enterprise Edition (Commercial License)
- **Who:** Companies deploying in production regulated environments
- **What:** Full Murphy System + proprietary modules + SLA + audit support
- **Cost:** Negotiated — see LICENSE_ENTERPRISE
- **Includes:** 
  - All Community Edition components
  - Proprietary orchestrator and HITL workflow
  - Dedicated support (SLA: 99.9% uptime, 4-hour response)
  - Compliance report generation
  - Patent license for all three Murphy System patents

---

## Migration Plan & Timeline

### Q2 2026 — Community Launch

- [ ] Publish `murphy_confidence` on PyPI under Apache 2.0
- [ ] Create public GitHub repository: `github.com/inoni/murphy-confidence`
- [ ] Publish README_OPENSOURCE.md as the public README
- [ ] Submit to Awesome-LangChain and Awesome-AI-Safety lists
- [ ] Post launch blog on Inoni website and LinkedIn

### Q3 2026 — Ecosystem Growth

- [ ] Submit Murphy System paper to arXiv (MFGC formula)
- [ ] Conference presentation: AI safety track (NeurIPS / ICLR workshop)
- [ ] Publish LangChain integration to LangChain Hub
- [ ] Grow GitHub stars to 500+

### Q4 2026 — Enterprise GA

- [ ] Launch Enterprise Edition with commercial license
- [ ] Publish healthcare and financial compliance case studies
- [ ] Target first 3 enterprise design partnerships

### 2027 — Scale

- [ ] SaaS platform launch
- [ ] Partner program for system integrators
- [ ] EU AI Act certification support offering

---

## IP Protection During Open Source

1. All open-source code retains copyright header
2. ATTRIBUTION.md in every release
3. Patents filed before open-source release
4. Contributor License Agreement (CLA) required for all PRs
5. Proprietary modules never published in public repository

---

## VERIFIED BY: Corey Post — Murphy Collective

© 2020-2026 Inoni Limited Liability Company. All rights reserved.
