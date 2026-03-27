# Murphy Grant Strategy — Track A (Inoni LLC)

**"We are the first use case always."**

Murphy System (Inoni LLC) applies for grants using the same system it ships to
customers. If the grant engine cannot help Murphy win funding, it cannot help
customers. Track A is the proving ground.

---

## Why Grants Matter for Murphy

Murphy System is an R&D-intensive platform — BAS/BMS, EMS, SCADA, agentic AI,
industrial IoT, workflow automation. This maps directly to the highest-value
federal grant categories:

| Grant Family | Relevance | Potential Value |
|-------------|-----------|-----------------|
| **SBIR/STTR** | AI-driven automation platform = qualifying R&D | $50K–$30M |
| **ARPA-E / DOE AMO** | Energy efficiency modules (EMS, BAS) | $500K–$10M+ |
| **NSF Convergence** | AI + manufacturing + sustainability | up to $5M |
| **EDA Build to Scale** | Platform company scaling | $500K–$2M |
| **§41 R&D Tax Credit** | Qualifying research expenses | 6.5–20% of QRE |
| **State R&D Credits** | Oregon, California, NY, NJ offsets | varies |

---

## The 4 Murphy Grant Profiles

Each profile in `murphy_profiles.py` represents a different "hat" Inoni wears
when applying. Matching the right profile to the right grant is critical.

### Profile 1 — `murphy_ai_platform` (AI/Automation SaaS)
- **Best for:** SBIR/STTR, NSF, EDA, NIH SBIR
- **Pitch:** Murphy is an AI-powered universal automation platform enabling any
  organization to automate business processes, IoT systems, and industrial
  controls without custom code
- **Key evidence:** 750+ automation modules, agentic workflow engine, inference
  gate with industry classification

### Profile 2 — `murphy_energy_tech` (Clean Energy Technology)
- **Best for:** DOE ARPA-E, DOE AMO, DOE BTO, DOE GRIP, CESMII
- **Pitch:** Murphy's EMS and BAS/BMS modules optimize energy consumption in
  commercial and industrial facilities, directly reducing carbon emissions
- **Key evidence:** Real-time energy monitoring, HVAC automation, demand
  response integration, §179D/§48 project tracking

### Profile 3 — `murphy_manufacturing` (Smart Manufacturing)
- **Best for:** CESMII, NIST MEP, ARPA-E, Manufacturing USA institutes
- **Pitch:** Murphy integrates with SCADA and industrial IoT to create
  AI-driven smart manufacturing workflows that reduce waste and improve OEE
- **Key evidence:** SCADA connectors, predictive maintenance modules, OEE
  dashboards, manufacturing workflow templates

### Profile 4 — `murphy_infrastructure` (Critical Infrastructure Resilience)
- **Best for:** EDA Tech Hubs, DHS S&T, NSF, FEMA BRIC
- **Pitch:** Murphy's multi-protocol IoT platform enables resilient, AI-supervised
  control of critical infrastructure including water, energy, and transport
- **Key evidence:** Multi-protocol support (BACnet, Modbus, MQTT, OPC-UA),
  autonomous fault detection, HITL escalation system

---

## Priority Grant Targets (FY 2025–2026)

### Tier 1 — Apply Now (Phase I feasibility)

| Grant | Profile | Deadline Cadence | Notes |
|-------|---------|-----------------|-------|
| **SBIR Phase I** (DOE) | `murphy_energy_tech` | Rolling (3 solicitations/yr) | EMS + BAS modules qualify |
| **SBIR Phase I** (NSF) | `murphy_ai_platform` | Fall/Spring solicitations | AI automation platform |
| **§41 R&D Tax Credit** | all | Annual (tax filing) | Immediate — file with taxes |
| **State R&D Credits** (OR) | all | Annual | Oregon HQ; 15% of QRE |

### Tier 2 — Phase II / Scale (after Phase I award)

| Grant | Profile | Notes |
|-------|---------|-------|
| **SBIR Phase II** (DOE/NSF) | energy_tech / ai_platform | $750K–$1.75M; requires Phase I |
| **ARPA-E** | `murphy_energy_tech` | Requires strong Phase I results |
| **NSF Convergence** | `murphy_ai_platform` | 2-year program; $3–5M |

### Tier 3 — Long-term (18–36 months)

| Grant | Profile | Notes |
|-------|---------|-------|
| **EDA Tech Hubs** | all | Regional consortium required |
| **SBIR Strategic Breakthrough** | all | Up to $30M; requires Phase II |
| **CESMII** | `murphy_manufacturing` | Membership + project required |

---

## Prerequisites Checklist

Before any federal grant application can be submitted, Inoni LLC must complete
the following registration chain (tracked in `prerequisites.py`):

1. **[ ] SAM.gov Registration** — mandatory for all federal awards  
   ↳ URL: https://sam.gov/  
   ↳ Renewal: annually  

2. **[ ] Unique Entity Identifier (UEI)** — auto-assigned at SAM.gov  
   ↳ Set `INONI_SAM_UEI` in `.env` once obtained  

3. **[ ] CAGE Code** — auto-assigned by DLA at SAM.gov  
   ↳ Set `INONI_CAGE_CODE` in `.env` once obtained  

4. **[ ] EIN (Employer ID Number)** — file SS-4 with IRS  
   ↳ Set `INONI_EIN` in `.env`  

5. **[ ] Grants.gov Account** — for NIH/NSF/DOT submissions  
   ↳ Set `INONI_GRANTS_GOV_USERNAME` in `.env`  

6. **[ ] SBA SBIR/STTR Registration** — required for SBIR applications  
   ↳ URL: https://www.sbir.gov/registration  

7. **[ ] Research.gov / NSF FastLane** — for NSF submissions  

---

## R&D Tax Credit Strategy (§41)

The §41 R&D tax credit is the fastest path to non-dilutive funding:

- **Rate:** 20% of qualified research expenses (QRE) above base amount  
  (startups: 6% credit against payroll taxes, up to $250K/yr — no revenue needed)
- **QREs include:** Employee wages for R&D, contractor R&D, cloud computing for
  R&D (AWS/GCP/Azure), prototype costs
- **Documentation:** Time-tracking logs, git commit history, sprint records,
  architecture documents — Murphy's own workflows can generate this automatically
- **State credits:** Oregon (15%), California (15% over threshold), New York (9%)

**Action:** Engage an R&D tax credit specialist for FY 2024 filing.  
Murphy should generate documentation artifacts automatically from git + sprint data.

---

## Tracking Applications

All Track A applications are tracked in `GrantSession` records with
`track=TRACK_A`. The grant wizard UI (PR 3) provides a dashboard showing:

- Prerequisites status
- Active applications by status (draft / in_review / submitted / awarded)
- HITL tasks pending human action
- Upcoming deadlines

---

## Key Contacts

| Organization | Contact Role | Purpose |
|-------------|-------------|---------|
| SBA SBIR | Program manager | Phase I/II guidance |
| DOE ARPA-E | Program director (varies) | Technology-specific |
| NSF | Program officer (varies) | Convergence/PFI |
| PTAC (Procurement Technical Assistance Center) | Regional advisor | Free SAM.gov + bid help |
| SBDC (Small Business Development Center) | Business advisor | Free business planning help |

---

*This document is updated as Inoni LLC progresses through the grant lifecycle.  
See `docs/GRANT_DATABASE_SCHEMA.md` for the full data model reference.*
