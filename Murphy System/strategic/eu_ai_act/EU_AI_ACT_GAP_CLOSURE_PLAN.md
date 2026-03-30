# EU AI Act — Gap Closure Plan

## Document Purpose
Actionable plan to close all identified gaps in Murphy System's EU AI Act (2024/1689) conformity assessment.

## Current Status
- Articles assessed: 8
- Compliant: 3 (Article 9, Article 13, Article 14)
- Partial: 5 (Article 6, Article 15, Article 17, Annex III §5, Annex III §8)
- Target: 100% compliance for all applicable articles by 2027-Q1

## Gap Closure Roadmap

### GAP-1: Article 6 — Annex III Legal Review
- **Current status:** Classification logic implemented; legal review not scheduled
- **Action items:**
  1. Engage EU AI Act specialist counsel for Annex III mapping review
  2. Document all deployment contexts and map to Annex III categories
  3. Produce formal legal opinion on risk classification
  4. Update classification engine with counsel's findings
- **Owner:** Legal / Compliance
- **Target date:** 2026-06-01
- **Acceptance criteria:** Written legal opinion confirming Annex III mapping accuracy

### GAP-2: Article 15 — Cryptographic Integrity (HMAC-SHA256)
- **Current status:** Patent #3 in progress; implementation pending
- **Action items:**
  1. Complete HMAC-SHA256 integrity module implementation
  2. Integrate with confidence engine output signing
  3. Add integrity verification to all audit-logged decisions
  4. Penetration test the integrity chain
- **Owner:** Platform Engineering
- **Target date:** 2026-08-01
- **Acceptance criteria:** All confidence decisions cryptographically signed and verifiable

### GAP-3: Article 17 — Quality Management System (QMS)
- **Current status:** Planned; no ISO 9001-aligned documentation exists
- **Action items:**
  1. Draft QMS policy document aligned with ISO 9001:2015 structure
  2. Document development lifecycle, change management, and release processes
  3. Establish internal audit schedule
  4. Create corrective action procedure
  5. Prepare for third-party QMS audit (target: 2027-Q1)
- **Owner:** Engineering Leadership
- **Target date:** 2026-09-01
- **Acceptance criteria:** QMS documentation passes internal review; audit scheduled

### GAP-4: Annex III §5 — HR/Employment Domain Model
- **Current status:** HITL gate exists but no HR-specific domain model or dedicated workflow
- **Action items:**
  1. Design HR-specific confidence thresholds (recruitment, performance review, task allocation)
  2. Implement dedicated HITL workflow requiring human review for all employment-affecting decisions
  3. Add HR domain-specific bias detection and fairness metrics
  4. Create deployment guide with EU AI Act compliance checklist for HR use cases
  5. Engage employment law counsel for review
- **Owner:** Platform Engineering + Legal
- **Target date:** 2026-Q4
- **Acceptance criteria:** HR deployment guide with legal sign-off; dedicated HITL workflow tested

### GAP-5: Annex III §8 — Critical Infrastructure (IEC 61508/62443)
- **Current status:** Manufacturing IoT demo exists; formal gap analysis not completed
- **Action items:**
  1. Commission formal IEC 61508 SIL-2 gap analysis
  2. Commission IEC 62443 cybersecurity gap analysis
  3. Document safety-critical gate behavior against IEC 61508 requirements
  4. Implement any required safety instrumented function (SIF) patterns
  5. Create critical infrastructure deployment guide
- **Owner:** Platform Engineering + External Safety Consultant
- **Target date:** 2026-10-01
- **Acceptance criteria:** Gap analysis complete; remediation items scheduled

## Tracking
Each gap will be tracked as a GitHub issue with the label `eu-ai-act`. Progress reviews monthly.

## Verification
- Corey Post — Murphy Collective
- Date: 2026-03-08
