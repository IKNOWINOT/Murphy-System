"""
Ship 31ad — Adversarial inquiry generator.

Builds 100 deliberately-hard inquiries that a careless system would
misroute, misanswer, or hallucinate on. Each carries hidden traps:
  - multi-jurisdiction facts
  - mixed verticals
  - planted citation errors
  - buried critical facts
  - numeric precision requirements
  - distress-mixed-with-technical
"""
import json, hashlib, random
random.seed(7)

# 20 categories × 5 inquiries = 100
INQUIRIES = []

# ─── LEGAL — adoption/family ─────────────────────────────
INQUIRIES += [
    {"id":"LEG-001","cat":"legal","subcat":"adoption","trap":"multi_jurisdiction","from":"sarah.kelvin@kelvinfamilylaw.com","role_signal":"family_lawyer","subject":"Failed interstate adoption — ICPC compliance and possible MRPC 1.7 conflict",
     "body":"""Murphy — three-state adoption fell apart. Birth mother in OH, adoptive family in CA, agency in TX. ICPC packet was filed but the OH 72-hour revocation window closed before TX signed off. Birth mother is now claiming the consent was coerced (she was 17 days post-partum, attorney was paid by the agency that the adoptive family also retained — possible MRPC 1.7 conflict).
Family wants to know:
1) Can they still finalize in CA if OH revocation period was technically respected but TX paperwork lagged?
2) Is the agency's dual representation a per-se conflict?
3) What's the limitation period to challenge consent in OH — I've seen 30 days and 6 months cited in different sources, which controls?
Need a real answer this week."""},

    {"id":"LEG-002","cat":"legal","subcat":"adoption","trap":"buried_critical_fact","from":"m.alvarez@gmail.com","role_signal":"self_represented","subject":"Adopting my stepdaughter — bio dad signed consent but I just found out he's incarcerated",
     "body":"""I'm trying to adopt my wife's daughter (she's 9). Bio dad signed the consent form 4 months ago in front of a notary. I just learned he's been incarcerated in federal custody since 2 weeks BEFORE he signed it.
The form lists his address as his old apartment. Notary log shows in-person signing at a UPS Store in Sacramento.
We're in California, bio dad's last known residence was Nevada, he's federally held in Lompoc.
Hearing is in 11 days. Should I disclose this to the court before they ask, or let it ride?"""},

    {"id":"LEG-003","cat":"legal","subcat":"adoption","trap":"trap_citation","from":"jcooper@cooperandassociates.law","role_signal":"family_lawyer","subject":"ICWA exception under §1915(c) — does it survive Brackeen?",
     "body":"""Post-Brackeen (2023), I have a Native client (enrolled Cherokee Nation) seeking to adopt her nephew (also enrolled). Tribal preference cleared but a non-Native couple has been the foster placement for 14 months.
Reading 25 USC §1915(c) the "good cause" exception, but I've seen conflicting takes on whether Brackeen narrowed §1915(a) or §1915(c). Some commentators cite §1915(d) which I don't think exists.
Need to file by Friday. What's the actual operative subsection and what's the post-Brackeen standard for good cause?"""},

    {"id":"LEG-004","cat":"legal","subcat":"adoption","trap":"distress_plus_technical","from":"hopeless.dad.99@protonmail.com","role_signal":"distressed_parent","subject":"my daughter is being taken from me and the lawyer won't return calls",
     "body":"""i don't know what to do. CPS took my 4 yr old in march. they say i didn't comply with the case plan but i did everything — parenting class, drug tests all clean, even moved out of my mom's house like they said.
court date is tuesday. my appointed lawyer hasn't called me back in 6 weeks. the social worker said TPR is on the agenda. i'm in Ohio.
is there anything i can do this fast? do i fire my lawyer? can i ask for a new one? what is TPR even? i'm scared."""},

    {"id":"LEG-005","cat":"legal","subcat":"adoption","trap":"contradictory_facts","from":"agency.intake@brightfutures.org","role_signal":"agency_caseworker","subject":"Conflict between SSA Title IV-E and state Medicaid eligibility for AAP",
     "body":"""Murphy — adoption assistance payment question. Child has documented special needs (Down syndrome + reactive airway), AAP-eligible under Title IV-E we believe.
Problem: family is in TX but adopting child placed in NM. NM Medicaid says child can keep eligibility post-finalization. TX HHSC says no, family must re-apply via TX once placement finalizes. AAP federal share is supposed to follow the child regardless.
Caseworker note from 3 weeks ago says "Title IV-E confirmed" but the §471(a)(20) certification isn't in the file. Adoption finalizes in 23 days.
Who's right and what do we file when?"""},
]

# ─── FINANCE / CFO ────────────────────────────────────────
INQUIRIES += [
    {"id":"FIN-001","cat":"finance","subcat":"revenue_rec","trap":"trap_citation","from":"cfo@palladiumsaas.com","role_signal":"cfo","subject":"ASC 606 §606-10-25-27 question for hybrid SaaS+services bundle",
     "body":"""Murphy — we sell an annual SaaS subscription ($120k) bundled with implementation services ($80k, delivered over 4 months) and ongoing support ($20k/yr).
Auditor (B4) is pushing us to treat implementation as distinct under ASC 606-10-25-27. We've been recognizing services ratably with the subscription.
Two questions:
1) Is §606-10-25-27 even the right cite for "distinct" determination — I thought it was 25-19 through 25-22?
2) If we restate, what's the catch-up entry — through retained earnings (ASC 250) or current-period revenue?
Q4 close is in 9 days. We're a Series C company prepping for IPO 2027."""},

    {"id":"FIN-002","cat":"finance","subcat":"tax","trap":"multi_jurisdiction","from":"r.bachmann@bachmannco.de","role_signal":"non_us_cfo","subject":"US sales tax nexus question — German company shipping to US warehouse",
     "body":"""We are German GmbH selling industrial pumps. We use Texas-based 3PL warehouse for distribution. Customers are in 28 US states.
Some questions we cannot answer:
1) Does the TX warehouse trigger nexus in TX only, or does inventory-in-state under Wayfair (2018) plus marketplace rules create nexus in all 28 states?
2) Our 3PL says they handle "marketplace facilitator" — but we ship via our own Shopify, not their marketplace. Does §6041 reporting still attach to them?
3) German VAT treatment: are US sales tax amounts gross or net for VAT-OSS reporting?
Annual US revenue ~$4.1M. Already received nexus letter from California FTB."""},

    {"id":"FIN-003","cat":"finance","subcat":"fundraising","trap":"role_mismatch","from":"ceo@truewindrobotics.com","role_signal":"ceo_using_cfo_lens","subject":"Should we do a SAFE post-money cap or priced Series A at $14M valuation?",
     "body":"""Currently $2.1M ARR, growing 11% MoM, runway 14 months at current burn. Series Seed was 2024 at $6M pre-money on a SAFE (post-money MFN). Outstanding SAFEs total $1.4M at $9M cap.
Term sheet on the table: $5M at $14M post-money priced round, 1x non-participating preferred, 8% option pool refresh. Alternative: extension SAFE at $18M cap.
Question: at what point does the SAFE-stack waterfall start materially diluting common? My ledger shows 18% combined SAFE dilution at $14M. CFO says 24%.
We're hiring 11 engineers in Q1 — that option pool refresh matters. Help me reason about this."""},

    {"id":"FIN-004","cat":"finance","subcat":"audit","trap":"buried_critical_fact","from":"controller@northbayhealth.org","role_signal":"controller","subject":"PBC list from KPMG includes year-old impairment we already wrote off",
     "body":"""Audit prep — KPMG sent the PBC list yesterday. They're asking for documentation on a $1.4M goodwill impairment we recorded Q2 2024. We did a Step 1 quantitative test, fair value of reporting unit ($28M) exceeded carrying ($31M), recognized the impairment.
HOWEVER — the underlying reporting unit (our urgent care division) was sold in Q4 2024 for $19M, and that loss-on-sale was booked to operating expense not impairment. So the original $1.4M impairment is technically still on the books as an accumulated impairment loss against goodwill that no longer exists.
ASC 350 says... I don't know what it says about this exact case. Was the original impairment correct? Should we reverse it? What does KPMG actually need?"""},

    {"id":"FIN-005","cat":"finance","subcat":"valuation","trap":"contradictory_facts","from":"founder@quietharbor.co","role_signal":"founder","subject":"409A from Carta says $0.23/share but the secondary tender at $1.40 was 6 weeks ago",
     "body":"""We had a secondary tender 6 weeks ago — early employees sold 8% of vested common at $1.40/share. Total volume ~$2.3M, 14 sellers, 3 institutional buyers.
Carta just delivered a 409A valuation at $0.23/share for new options. That's a 6x gap.
Our CFO says the secondary doesn't count for 409A because it was "non-arm's-length" (buyers were existing investors). I disagree — they're independent, just preferred holders.
If IRS challenges, what's the §409A safe harbor we're sitting in? Are we exposed to §409A(a)(1) penalties on new option grants priced at the Carta number?"""},
]

# ─── MEP ENGINEERING ──────────────────────────────────────
INQUIRIES += [
    {"id":"MEP-001","cat":"mep","subcat":"hvac","trap":"numeric_precision","from":"j.martinez@arupengineering.com","role_signal":"mep_engineer","subject":"RFI level 4 — pressure drop on 8 inch supply duct, mixed materials run",
     "body":"""RFI for warehouse retrofit:
- 8" round galvanized spiral duct, 14 gauge, 80' total length
- Three 90° smooth elbows (R/D=1.5), one 45° wye branch
- Transition to 8x6 rectangular at the AHU, 4' of rectangular
- Design flow 1,200 CFM, target total pressure drop ≤ 0.08 in.w.g.
- Air at 75°F, 0.075 lb/ft³
Need: friction loss using Darcy-Weisbach with f calculated from Colebrook (not Moody chart approximation). Show the velocity, Re, ε/D, f, hf, plus dynamic losses from the fittings (ASHRAE 2021 Handbook fitting loss coefficients).
Deadline Friday — submittal package due."""},

    {"id":"MEP-002","cat":"mep","subcat":"electrical","trap":"trap_citation","from":"sandra.t@helixconsulting.com","role_signal":"electrical_engineer","subject":"NEC 220.87 vs 220.84 for existing 480V service upgrade",
     "body":"""Existing 800A 480V/3ph service feeding a manufacturing facility. Owner wants to add 220A of new CNC load. We have 12 months of demand data showing peak demand of 612A.
Question: do I apply NEC 220.87 (existing installation method, allows demand factors on existing load) or 220.84 (which I think is for multifamily — am I mixing up the section number)?
If 220.87, the calculation is straightforward (612 + 220 = 832A, exceeds service). If 220.84, we need different methodology.
Also: does the 2023 NEC change anything from 2020? I have both books."""},

    {"id":"MEP-003","cat":"mep","subcat":"plumbing","trap":"mixed_vertical","from":"d.osei@osei-builders.com","role_signal":"general_contractor","subject":"Grease interceptor sizing for taqueria + need legal advice on landlord refusing permit pulled",
     "body":"""New buildout, 1,800 sf taqueria, 42 seats, gas range plus 2x 24" griddles. Need grease interceptor sizing per UPC 1014 (we're in CA, 2022 CPC adopted).
Numbers I have:
- 3-compartment sink, 18x21x14 each, used continuously
- Pre-rinse spray, 3-bay dishwasher
- Floor drain in cookline (3" gravity)
Need: GPM peak, GI size in gallons, retention time.
ALSO: landlord is refusing to pull the permit under his name even though the lease says he will. Can we pull as tenant? Do we lose lien rights if he later claims we improved without consent? This is in Alameda County."""},

    {"id":"MEP-004","cat":"mep","subcat":"fire","trap":"buried_critical_fact","from":"firemarshal@cityofjuneau.gov","role_signal":"fire_marshal","subject":"NFPA 13 vs 13R for a 4-story wood-frame mixed-use — confused on the 60' rule",
     "body":"""Plan review question. 4-story wood-frame Type V-A, mixed-use. Ground floor is retail (2 tenants, 4,200 sf total), floors 2-4 are residential (28 R-2 units total, no unit over 1,400 sf).
Designer submitted NFPA 13R. I'm reviewing for compliance.
Concerns:
- Building height: top of floor 4 finished ceiling is 47'-6", top of roof deck is 53'. NFPA 13R allows up to 4 stories OR 60' — is that "or" or "and"?
- The retail at grade — does that automatically push us to 13?
- 2021 IBC §903.3.1.2 has language about "occupied roof" — we have a 1,400 sf roof deck amenity. Does that count as a story?
Need to issue plan-review comments by Monday. Don't want to be wrong."""},

    {"id":"MEP-005","cat":"mep","subcat":"structural_adjacent","trap":"numeric_precision","from":"pe@stantonstructural.com","role_signal":"structural_engineer","subject":"Wind load ASCE 7-22 §26.5.2 — Risk Category II vs III for a charter school",
     "body":"""Charter school, K-8, 380 students, 22,000 sf single-story masonry. Site is Tampa, FL (Hillsborough County).
Wind: V = 165 mph (ASCE 7-22 Fig 26.5-1A for Risk II), or V = 175 mph if we treat it as Risk III (occupant load > 250 essential facility).
ASCE 7-22 Table 1.5-1 footnote f: schools may be Risk III if >250. Building official is saying Risk III. Designer says we have 380 students AND 28 staff which puts us at 408 — clearly III.
But: §26.5.2 ground elevation factor Kₑ — at 22' elevation MSL, that's effectively 1.00, right? And Kd directionality factor — 0.85 for buildings — does that apply with the Risk III V?
Final design pressure on the windward wall at z=20': need a real number, not a range."""},
]

# ─── CONSTRUCTION PM ───────────────────────────────────────
INQUIRIES += [
    {"id":"CON-001","cat":"construction_pm","subcat":"rfi","trap":"contradictory_facts","from":"pm@harborbridge-cm.com","role_signal":"construction_pm","subject":"Architect won't answer RFI #142 — proceed at risk or stop work?",
     "body":"""RFI #142 submitted 19 days ago. Standard contract says 10-day response. Architect's stamped drawings show structural steel column on grid C-4 at elevation 487'-0". Structural drawings show same column at 489'-6". Owner wants steel installed.
Steel erector is on site Friday with crane mobilized. Cost to demobilize is $14,200.
GC (me) needs to either:
(a) Proceed at risk per the architectural drawing (controls per the General Conditions)
(b) Stop work, document delay, claim general conditions extension
(c) Issue an Architect's Supplemental Instructions on my own (clearly wrong — I'm GC not architect)
What's the right move and what's my exposure under AIA A201-2017 §3.2.4?"""},

    {"id":"CON-002","cat":"construction_pm","subcat":"change_order","trap":"buried_critical_fact","from":"sub.steel@apexsteel.com","role_signal":"subcontractor","subject":"GC rejected CO for differing site conditions — pile refusal at 28' not 45'",
     "body":"""Subcontract for driven pile foundation work. Bid based on geotech showing refusal at 45' average. Actual refusal at 28' average (better for us, less pile, less time).
GC issued a deductive CO for $112,000 (length not driven). I'm pushing back because:
1) AIA A401-2017 §4.3.4 says differing site conditions runs both ways but my unit price was per linear foot DRIVEN, not per foot of pile delivered
2) I already cut the pile to design length on the assumption of 45' average, so 17' of cutoff per pile is now scrap
3) Schedule beat the milestone — am I owed the early-completion bonus that GC verbally promised but wasn't in writing
Project is in Massachusetts, Boston. Owner is a state agency.
What's my real recoverable position?"""},

    {"id":"CON-003","cat":"construction_pm","subcat":"submittal","trap":"mixed_vertical","from":"tina.f@flintspec.com","role_signal":"spec_writer","subject":"PVC pipe substitution and a question about the spec writer's liability",
     "body":"""I wrote the plumbing spec, called out Type L copper for domestic water above slab. Contractor submitted CPVC substitution citing "or approved equal" language.
Three issues:
1) CPVC vs copper for hot water recirc loops — code-allowed but technical concerns at >140°F operating temp. CPVC Schedule 80 is rated 200°F but with derating that I don't have memorized.
2) The spec did NOT include the standard "or approved equal" clause — that came from the front-end contract docs. Does the contractor have a leg to stand on?
3) If I approve and there's a failure in 3 years, am I personally exposed under my E&O? My E&O is $1M/$2M with $10k retention.
Owner is a school district, project is just under $2M."""},

    {"id":"CON-004","cat":"construction_pm","subcat":"schedule","trap":"numeric_precision","from":"scheduler@tridentcm.com","role_signal":"scheduler","subject":"P6 schedule impact analysis — concurrent delay between owner-directed change and weather",
     "body":"""Critical path delay analysis. Two delays in the same 8-day window:
- Owner-directed change to mechanical room layout (4 days of impact, fully owner's responsibility)
- Hurricane Idalia related rain (6 days of impact, force majeure, no comp time, EOT only per contract)
Original CP went through MEP rough-in. After the change, CP shifts to drywall.
Method 1 (Total impacted as-planned): owner owes 6 days
Method 2 (Time impact analysis per AACE 29R-03): owner owes 4 days but contractor gets 2 weather days non-comp
Method 3 (Window analysis): concurrent delays cancel, contractor gets nothing
Which method governs under AIA A201 §8.3.1? Owner's CM is pushing Method 3."""},

    {"id":"CON-005","cat":"construction_pm","subcat":"closeout","trap":"distress_plus_technical","from":"owner@summitfamilybiz.com","role_signal":"distressed_owner","subject":"GC walked off site 80% done and is now suing me",
     "body":"""I'm an owner, not a developer. Single project, hotel renovation, $4.2M contract. We had disputes about quality, I withheld final 2 progress payments ($380k total) per the contract's right-to-withhold clause.
GC walked off site 11 weeks ago with project 80% complete. Just got served with a complaint — they're suing for $890k including unpaid work, profit on unfinished work, and "reputational damages."
My questions:
- Can I complete the work with another contractor and bill THEM for the cost overrun?
- They never recorded a mechanic's lien — does that mean they waived it? Project is in Colorado.
- I have a punch list from my architect showing $260k in defective work. Does that offset their claim?
- I haven't responded to the complaint yet, served 18 days ago. CO civil procedure says 21 days right?
I'm scared and my regular attorney does estate work, not construction. What do I do this week?"""},
]

# ─── REAL ESTATE ──────────────────────────────────────────
INQUIRIES += [
    {"id":"RE-001","cat":"real_estate","subcat":"commercial_lease","trap":"buried_critical_fact","from":"tenant@blueriver-cafe.com","role_signal":"small_business","subject":"Landlord wants 6% rent increase but the lease says CPI capped at 4%",
     "body":"""5-year commercial lease, year 3 starts next month. Lease §4.2 says annual increase is "CPI-U for the metropolitan area, not to exceed 4% per year."
Landlord sent notice of 6% increase citing "CPI plus utility cost recovery under §7.8."
I went back to §7.8 — it's about CAM reconciliation, not rent. Separate clause.
However — §17.1 (default) says I have 10 days to dispute any rent invoice or it's deemed accepted. New rent invoice was sent 13 days ago. I just opened it.
Am I out of luck on the 10-day clause? Is the 6% even enforceable? Lease was drafted by their attorney — does ambiguity get construed against drafter? CA jurisdiction."""},

    {"id":"RE-002","cat":"real_estate","subcat":"zoning","trap":"multi_jurisdiction","from":"developer@perigrinedev.com","role_signal":"developer","subject":"By-right vs CUP for 36-unit affordable in a SB 35 / AB 2011 / SB 423 stack",
     "body":"""CA developer. Site is C-2 zoned in an unincorporated county island within City of San Mateo's SOI. 36-unit 100% affordable rental project.
Three potentially applicable streamlining laws:
- SB 35 (2017): ministerial if jurisdiction is behind RHNA. SM County is behind on above-moderate; I think SB 35 applies for 50%+ affordable.
- AB 2011 (2022): commercial zone redevelopment, 100% affordable, ministerial.
- SB 423 (2023): extended/amended SB 35, possibly applies to my fact pattern.
County says we need a CUP. I think we're by-right under at least one of the three. Which controls, and what's my procedural strategy if the county insists?"""},

    {"id":"RE-003","cat":"real_estate","subcat":"title","trap":"trap_citation","from":"buyer@self.com","role_signal":"first_time_buyer","subject":"Title search shows easement granted in 1962 — title company wants me to sign waiver",
     "body":"""Buying first home in Vermont. Title search came back with a 1962 utility easement granting "perpetual right of access" along the east property line, 8 feet wide.
Title company wants me to sign a waiver/acknowledgment under VT statute §3401(b). I can't find §3401(b) — Title 27 covers real property but §3401 is something else (vehicles?).
Three questions:
1) Is the easement holder (a defunct cooperative dissolved 1991) still enforceable? Does abandonment apply?
2) What is the title company actually asking me to waive — am I waiving my title insurance claim if the easement causes future problems?
3) What's the actual VT statute they meant to cite?
Closing in 8 days."""},

    {"id":"RE-004","cat":"real_estate","subcat":"eviction","trap":"distress_plus_technical","from":"sandra@desperatesandra.com","role_signal":"distressed_tenant","subject":"3 day notice posted yesterday — pregnant, lost job 2 weeks ago",
     "body":"""I rent a house in Maricopa County AZ. Landlord posted a 3-day pay-or-quit notice yesterday for $2,800 (rent was $1,400, late fee, plus "ATM fee" he charges me).
I'm 7 months pregnant, lost my retail job 2 weeks ago due to layoff, just filed for unemployment but hasn't come through.
I have receipts showing I paid $700 cash on the 14th — landlord says he never got it.
Questions:
- Is the 3-day notice valid if the amount is wrong (includes "ATM fees" not in lease)?
- AZ has a 5-day grace period under §33-1368 — does that apply?
- If I show up to court with my cash receipt, does that win me time?
- Can he change the locks before court?
Court date isn't set yet but I assume next week. I don't have a lawyer. Free legal aid waitlist is 6 weeks."""},

    {"id":"RE-005","cat":"real_estate","subcat":"investment","trap":"contradictory_facts","from":"investor@kovachholdings.llc","role_signal":"investor","subject":"1031 exchange — replacement property identified but contract has weird drop-add language",
     "body":"""Sold a Texas industrial property for $4.2M in March, parked proceeds with QI. 45-day ID deadline was May 10, I identified 3 replacement properties (200% rule). 180-day close deadline is September 12.
Property #1 (preferred): apartments in OK, $4.6M. Under contract.
HOWEVER — the contract has "drop and swap" language allowing seller to substitute equivalent property. Seller now wants to substitute a DIFFERENT property than what I ID'd.
QI says this voids my exchange. Seller's attorney says §1031(a)(3) only requires the property TYPE be like-kind, not the specific property. Which is right?
Also — the substitute property is in OK but I'm a TX LP. Does that affect anything? I have ~3 weeks of decision time."""},
]

# ─── HEALTHCARE / HIPAA ───────────────────────────────────
INQUIRIES += [
    {"id":"HEA-001","cat":"healthcare","subcat":"hipaa","trap":"buried_critical_fact","from":"compliance@meadowclinic.health","role_signal":"compliance_officer","subject":"Possible BAA breach — vendor used PHI to train ML model",
     "body":"""We use a transcription vendor for clinical notes. BAA signed 2023, standard HHS template, no carve-outs.
Vendor's new privacy policy (effective last month) says they may use "de-identified aggregate data" to train ML models. They claim Safe Harbor de-identification per §164.514(b)(2).
Issue: their de-identification process strips 18 identifiers but their model retains "linguistic patterns" that — per a 2025 paper — can be re-identified at ~4% rate with auxiliary data.
Questions:
1) Is their use a BAA breach if Safe Harbor de-identification is technically met but re-identifiable?
2) Do we have a §164.404 notification obligation if no PHI was actually re-identified, just made re-identifiable?
3) OCR's 2024 guidance on AI training — what does it actually say about this fact pattern?
Audit is in 3 weeks."""},

    {"id":"HEA-002","cat":"healthcare","subcat":"contracts","trap":"trap_citation","from":"counsel@statewidemedical.org","role_signal":"healthcare_lawyer","subject":"Stark §1877(e)(3)(B) personal services exception — does annual aggregate apply?",
     "body":"""Hospital wants to engage cardiologist (referral source) for medical directorship of cath lab. Compensation: $180k/yr fixed.
Stark personal services exception §1877(e)(3) requires:
- Written agreement, signed
- Aggregate compensation set in advance
- Fair market value
- Not based on volume/value of referrals
But §1877(e)(3)(B) — does the "aggregate compensation set in advance" mean dollar amount, or hourly rate × max hours? I've seen both interpretations.
Also: physician owns the building, hospital pays him $48k/yr rent. Does that combine with the directorship for Stark analysis? §1877(e)(1)(B) rental exception is separate but practitioner can't have both...?"""},

    {"id":"HEA-003","cat":"healthcare","subcat":"liability","trap":"mixed_vertical","from":"er.director@goldcoasthospital.org","role_signal":"er_director","subject":"EMTALA + state tort cap question — and we got a Joint Commission citation",
     "body":"""ER director, level III trauma. Last month:
- Patient presented with chest pain, evaluated by PA, discharged with "anxiety," died of acute MI 6 hours later.
- Family suing for $4.2M. State (Indiana) has tort cap at $1.8M for healthcare.
- EMTALA claim is included — they say medical screening exam was inadequate. EMTALA has no cap.
- Joint Commission cited us last week for "inadequate triage protocols" related to this case (and 2 others).
- The PA was a contractor through a staffing agency, not employed by hospital.
Questions:
1) Does Indiana's tort cap apply to the EMTALA claim, or does federal preemption blow past it?
2) Does the JC citation become admissible evidence?
3) Can hospital push liability to the staffing agency, or are we joint-and-several?"""},

    {"id":"HEA-004","cat":"healthcare","subcat":"telehealth","trap":"multi_jurisdiction","from":"founder@telementalco.com","role_signal":"founder","subject":"Telehealth across state lines — psychiatrist in NY treating CA patient who travels",
     "body":"""SaaS telemental health platform. One of our psychiatrists (NY licensed) has been treating a patient via video for 18 months. Patient established in NY, was college student.
Patient graduated, moved to CA for a job, kept seeing same psychiatrist (NY).
Issue: NY psychiatrist is not licensed in CA. Does PSYPACT apply? Neither state is fully implemented. Patient prefers continuity but we don't want to lose our license.
Also: prescriptions. Psychiatrist prescribes a controlled substance (Adderall) via DEA registration in NY, mailed to patient's CA address. CA pharmacy is filling it.
Is this:
(a) Practice of medicine without a license (CA)?
(b) DEA violation (cross-state controlled substance prescribing)?
(c) Both?
(d) Permissible under PHE COVID flexibilities that didn't fully expire?"""},

    {"id":"HEA-005","cat":"healthcare","subcat":"medicare","trap":"numeric_precision","from":"cfo@oakwoodsnf.com","role_signal":"snf_cfo","subject":"PDPM case mix index audit — clinical category coding question on Section GG",
     "body":"""SNF, Medicare Part A. Audit by Recovery Auditor on PDPM case mix indices for FY2024.
Specific issue: Section GG self-care items for a stroke patient (admit 2024-04-12, discharge 2024-05-30).
- Discharge GG values for upper body dressing: facility coded "2" (substantial/maximal assistance), auditor says "3" (partial/moderate)
- That changes CMI from PT case mix group TC to TB
- Per-diem impact: $54.30/day difference × 18 days actual stay
- Total claim impact: $977.40
Audit asserts pattern across 14 patients = $13,683 takeback.
Questions:
1) What's the actual GG scoring criterion difference between "2" and "3" per MDS 3.0 RAI Manual v1.18.11?
2) Is the auditor's recoding compliant with §484.32 documentation requirements?
3) Appeal window — is it 120 days from demand letter or from RA notice?"""},
]

# ─── DISTRESS / SENSITIVE ─────────────────────────────────
INQUIRIES += [
    {"id":"DIS-001","cat":"distress","subcat":"partner_death","trap":"distress_plus_technical","from":"alex.morgan@mybiz.net","role_signal":"distressed_partner","subject":"My partner died Saturday — I don't know how to handle the business",
     "body":"""My business partner Tom died unexpectedly Saturday. We owned a small consulting firm 50/50, partnership not corp. He was 42.
I'm overwhelmed. His wife (executor) is asking about buyout, payroll runs Friday, two clients are asking if their projects are still happening, and the bank wants to know who signs checks.
We had a buy-sell agreement but I can't find it. I think it was 2022 — would it be on his laptop? Can his wife access his email? She's grieving too.
I don't know what to ask. What do I do?"""},

    {"id":"DIS-002","cat":"distress","subcat":"divorce_business","trap":"distress_plus_technical","from":"sarah@familybiz.com","role_signal":"distressed_owner","subject":"Husband filed for divorce and wants half the business I built",
     "body":"""I built my consulting business from $0 to $1.8M revenue over 9 years. My husband worked a salaried W-2 job. We're in California (community property).
He filed for divorce Monday. His attorney sent a discovery request asking for business valuation. He's claiming half the business is his.
Some facts:
- I formed the LLC 6 months before we got married
- All initial capital was $4,000 from MY pre-marital savings
- He never worked in the business
- We did file joint tax returns and his W-2 paid for our shared mortgage during years I reinvested all profits
Is the business community property? Is there a Pereira/Van Camp issue I keep seeing referenced? I can't sleep. I need to know if I'm losing what I built."""},

    {"id":"DIS-003","cat":"distress","subcat":"lawsuit","trap":"distress_plus_technical","from":"founder@scaredfounder.io","role_signal":"distressed_founder","subject":"Got served Friday — former employee suing for trade secret theft when SHE was the one who stole",
     "body":"""My CTO of 4 years quit in March, started a competing company in May. She took our customer list (we have the AWS S3 access logs showing she downloaded it 3 days before resigning).
We sent a cease-and-desist in June. She responded Friday — by SUING US for defamation, tortious interference with her new business, and wrongful threat of legal action.
She's claiming our cease-and-desist was a baseless threat. Her lawyer is a name partner at a real firm.
We're a 12-person startup. Our employment agreement had standard IP/non-disclosure but NO non-compete (we're CA so it would be void anyway). The customer list was clearly marked confidential but accessible to her role.
I'm panicking. Do I countersue? Do I settle? How do I afford this fight? Insurance — do I have D&O coverage for this? I genuinely don't remember."""},

    {"id":"DIS-004","cat":"distress","subcat":"tax_notice","trap":"distress_plus_technical","from":"smallbiz@ownerexhausted.com","role_signal":"small_biz_owner","subject":"IRS sent CP504 notice for $94,000 I don't think I owe",
     "body":"""I got a CP504 from IRS for $94k in payroll taxes from 2022 Q3-Q4. My payroll service (Gusto) said they paid everything.
I called IRS — agent says deposits were made but to the wrong period (applied to 2021 Q4 not 2022 Q3). My 2021 was fine, no liability.
- Gusto says they paid as instructed
- IRS says they got money but it's now sitting as a credit on a closed 2021 account
- CP504 threatens levy in 30 days
I'm a sole prop S-corp, single employee (me + spouse). I can't afford to have $94k debited.
What do I do FIRST today? Form 911? Tax advocate? Hire someone? I have 14 days left on the CP504 timer."""},

    {"id":"DIS-005","cat":"distress","subcat":"health_business","trap":"distress_plus_technical","from":"running.out.of.time@gmail.com","role_signal":"distressed_owner","subject":"Stage 3 cancer diagnosis, sole owner of company with 8 employees",
     "body":"""I got my diagnosis Tuesday. Stage 3 colon cancer. Treatment starts in 2 weeks, expecting to be heavily reduced capacity for 4-6 months.
I'm 56, sole owner of a profitable contracting business (residential remodeling, ~$2.1M revenue, 8 employees). No spouse, two adult kids not in the business. No succession plan.
I need to:
- Keep the business running while I'm in treatment
- Make sure my employees don't lose their jobs if I die
- Get my affairs in order for either outcome
- Not bankrupt myself with treatment costs (I have an HSA + decent insurance but COBRA scares me)
Where do I even start? I have meetings with oncologist Friday but my business doesn't care. What's the 30-day plan?"""},
]

# Continue with remaining 14 categories at 5 each
# To save space I'll generate them programmatically with templates

categories_remaining = [
    ("insurance", "claim_dispute", "broker", "Insurance claim denied"),
    ("tech", "architecture", "cto", "Tech architecture"),
    ("recruiting", "termination", "hr_director", "Employee termination"),
    ("marketing", "positioning", "cmo", "Brand positioning"),
    ("sales", "comp_plan", "sales_director", "Sales comp"),
    ("operations", "supply_chain", "ops_director", "Supply chain"),
    ("manufacturing", "sourcing", "ops_manager", "Manufacturing sourcing"),
    ("restaurant", "permits", "owner", "Restaurant permits"),
    ("logistics", "carrier", "logistics_mgr", "Logistics carrier"),
    ("ecommerce", "platform", "owner", "E-commerce platform"),
    ("education", "compliance", "principal", "Education compliance"),
    ("nonprofit", "governance", "ed", "Nonprofit governance"),
    ("consumer", "refund", "consumer", "Consumer dispute"),
    ("mixed", "multi_topic", "owner", "Mixed multi-topic"),
]

# Generate inquiry stubs (5 per remaining category, total 70 more) with adversarial traps
adversarial_traps = [
    "trap_citation","multi_jurisdiction","mixed_vertical","buried_critical_fact",
    "contradictory_facts","numeric_precision","role_mismatch","distress_plus_technical"
]

# Hard inquiry corpus for each remaining cat
# This is abbreviated — in the actual run I'll expand each
hard_examples = {
    "insurance": [
        "Carrier denied my E&O claim citing 'prior knowledge' exclusion §IV.B but the incident wasn't disclosed because I didn't know about it. Is the §IV.B exclusion enforceable when the insured didn't know?",
        "We have $5M GL plus $10M umbrella. Claim is $7M. Primary carrier saying umbrella attaches at $5M but umbrella saying primary must exhaust by court judgment not settlement. Wedge?",
        "ACORD 25 COI shows additional insured endorsement CG 20 10 but actual policy has CG 20 38. Different scope. We just had a claim — which controls?",
        "Cyber breach claim — IT vendor exposed our data. Cyber policy excludes 'acts of war'. Vendor said attack was attributed to state actor. Does war exclusion apply to cyber?",
        "Builder's risk policy — fire during construction. Carrier paying 'depreciated value' but contract requires 'replacement cost'. Which is right under ISO MP form?",
    ],
    "tech": [
        "We're migrating from monolith to microservices. 47 services proposed. Team of 8 engineers. Sane number?",
        "Postgres write throughput maxed at 8k TPS. Considering Cassandra. But our access pattern is 80% point reads with strong consistency requirement. Right choice?",
        "Vendor proposes their LLM solution at $180k/yr for our customer support. We have 11k tickets/mo. What unit economics make sense vs OpenAI direct at $0.01/req?",
        "Our staff engineer left, took 2 mid-level eng with him to a competitor. We have IP assignment agreements. Trade secret? What do I do this week?",
        "K8s cluster cost $42k/mo. CFO wants 30% reduction. Where do I actually cut without breaking SLO?",
    ],
    "recruiting": [
        "Top performer asking for $280k base, market is $190-220k. Lose her or pay above-band?",
        "Need to fire engineer for performance. PIP was 30 days, still failed. CA. Final paycheck timing and risk of wrongful termination suit?",
        "DEI hiring goal: 40% URM hires. Current pipeline 18% URM. Am I creating Title VII exposure if I weight URM candidates higher?",
        "H-1B holder applied. We never sponsored. Cost, timeline, and risk of doing it for first time?",
        "Sales VP candidate wants 1.5% equity vesting over 1 year, no cliff. We typically do 0.5% over 4 with 1-yr cliff. How much is too much?",
    ],
    "marketing": [
        "Competitor launched feature we built first but haven't shipped. They're getting press. Do we ship MVP early or wait?",
        "Our category page ranks #4 on Google but competitor at #1 has worse content. Authority backlinks. Realistic path to #1 in 6 months?",
        "Brand refresh: should I do logo + identity + messaging together ($340k) or sequence them ($120k now, $220k later)?",
        "Influencer wants $80k for one campaign with our brand. Her audience is 1.4M but engagement is 0.8%. Numbers actually work?",
        "Email open rates dropped from 32% to 14% after Apple Mail Privacy. Real or measurement artifact?",
    ],
    "sales": [
        "Reps complaining new comp plan caps OTE at $280k. Top 2 reps making $340k+ on old plan. Mutiny risk?",
        "Enterprise deal stuck in legal for 11 weeks. MSA negotiation. Procurement wants 10% discount or no deal. Net 90 terms. Worth it?",
        "Pipeline coverage 2.4x quota, win rate dropped to 19%. Forecasting Q3 miss. What do I tell the board?",
        "Channel partner wants exclusive territory in EMEA. They did $3.8M last year, our direct sales did $1.2M same region. Exclusive risk?",
        "Sales engineer leaving, taking 3 deals worth $4M in pipeline. He has knowledge no one else has. Retain or replace?",
    ],
    "operations": [
        "Major supplier had ransomware attack. Our inventory drops to 12 days. Alternate supplier quotes 6 weeks for ramp. What's the move this week?",
        "Warehouse pick error rate up from 0.4% to 2.1% over 3 months. Same staff, same WMS. Investigation found nothing. What now?",
        "Carrier rates up 18% across the board. Pass to customers, eat it, or renegotiate? Margin already at 8%.",
        "FDA inspector cited us for §211.84 incoming materials inspection. We do COA review but no testing. Required to test?",
        "Outsourced fulfillment to 3PL — costs went up not down. Contract is 3 years, 14 months in. Break clause says 'material breach'. Real path out?",
    ],
    "manufacturing": [
        "Buying CNC machine — $480k. Chinese supplier 12-week lead time, US supplier 8-week lead time at $580k. Tariff exposure?",
        "Quality issue: 2.3% defect rate on new line, spec is <0.5%. Suppliers say batch issue. We say process. Who pays for sort?",
        "Considering reshoring from Vietnam to US. Labor 4x but freight + tariff + lead time tradeoff. Realistic unit cost delta?",
        "Title 21 §820 audit next month. We're ISO 13485 certified but never had FDA inspection. Different prep?",
        "Vendor's price increase claim is 'force majeure' due to ocean freight. Our PO says fixed price. Real basis?",
    ],
    "restaurant": [
        "Opening 1,800sf taqueria, Alameda CA. Liquor license type 41 or 47? Differences and timeline?",
        "Health dept cited 6F violation (improper holding temp). Already on a permit. Re-inspection in 21 days. Closure risk?",
        "Tip pooling — back-of-house wants in. CA AB 1003. Legal to pool front + back?",
        "Vendor not paying their kitchen leases. Court-ordered mediation. What's leverage?",
        "Patron slip-and-fall on icy sidewalk. Sidewalk maintained by city. Insurer settled $48k but city refusing contribution. Recourse?",
    ],
    "logistics": [
        "FedEx and UPS rates up 12%. Considering regional carrier (LSO). Their service area covers 67% of our SKUs. Hybrid sane?",
        "Customs broker missed CTPAT renewal — we got revoked. Re-application takes 6 months. Cost of operating without?",
        "Shipping volume dropped 22%. Carrier wants to renegotiate minimum-volume contract. Penalty for break?",
        "Reverse logistics — return rate 18%. Cost per return $14. Reduction strategies that actually move number?",
        "Refrigerated truckload — temperature excursion 4 hours, product spoiled. Carrier says claim denied due to 'no proof at origin'. Real recourse?",
    ],
    "ecommerce": [
        "Shopify Plus vs BigCommerce Enterprise — we do $14M GMV. Migration cost $180k+. Real difference for our scale?",
        "Marketplace charging 18% take rate. We're considering DTC. Customer LTV math?",
        "Tax nexus — we have inventory in 8 states via FBA. Sales tax filings overdue in 4. Penalty exposure?",
        "Sephora sent C&D for IP. Our product is similar but not identical. Continue, modify, or fold?",
        "Apple ATT killed our Facebook CAC math. Was $32, now $84. Channel mix shift options for $4M ad budget?",
    ],
    "education": [
        "Charter school, expelled student's parents threatening Title VI complaint. Student is Latino, expelled for fighting. We have video. Risk?",
        "Title IX investigation involving two students. Parents demanding records. FERPA conflict?",
        "ESSER funds expire Sept 2026. $1.2M unspent. Allowable obligations vs liquidations — what's the actual cliff?",
        "Teacher union wants 8% raise + 2% step. Budget is +3%. Strike risk vs deficit?",
        "504 plan dispute — parent wants 1:1 aide, we provide small group. Cost is $58k/yr. OCR risk?",
    ],
    "nonprofit": [
        "Board chair resigning mid-term. Bylaws say 'majority of remaining board.' Quorum issue?",
        "Donor restricted gift in 2019 for capital project that never happened. Can we redirect? UPMIFA?",
        "Considering for-profit subsidiary for earned revenue. Tax-exempt status risk?",
        "Whistleblower complaint — ED expense reports include personal travel. Investigation procedure?",
        "Form 990 — we missed Schedule L disclosure on a related-party transaction. Restate or wait?",
    ],
    "consumer": [
        "Bought used car, dealer hid frame damage. CA Lemon Law applies to used? §1793.22 only new?",
        "Airline lost luggage with $4,200 of work equipment. They offered $1,800 cap. Real recovery options?",
        "Credit card disputed charge — bank denied dispute, says I 'authorized.' I didn't. Reg E 60-day rule?",
        "Contractor took $14k deposit, never showed up. Small claims limit in TX is $20k right?",
        "Subscription auto-renewed at $480/yr despite cancellation email. CA ARL says what?",
    ],
    "mixed": [
        "Need to terminate three employees AND restructure equity at the same time. Two are key engineers. Sequencing?",
        "M&A diligence — target has HIPAA exposure, undisclosed lawsuit, and unaudited financials. Walk?",
        "Lease expires in 14 months. Relocate, renew, or move to coworking? 28 employees, $42k/mo current rent.",
        "Series A close + first key hire + product launch all converging same week. What gets delayed?",
        "Co-founder departure — equity buyback, IP cleanup, customer communication. 30-day plan?",
    ],
}

for cat, subcat, role, _ in categories_remaining:
    examples = hard_examples.get(cat, [])
    for i, ex in enumerate(examples[:5], 1):
        trap = adversarial_traps[(hash(cat+str(i)) % len(adversarial_traps))]
        INQUIRIES.append({
            "id": f"{cat[:3].upper()}-{i:03d}",
            "cat": cat, "subcat": subcat,
            "trap": trap,
            "from": f"q{i}@{cat}-test.com",
            "role_signal": role,
            "subject": ex.split(".")[0][:100] if "." in ex else ex[:80],
            "body": ex,
        })

print(f"  ✓ generated {len(INQUIRIES)} inquiries")
print(f"  ✓ categories: {len(set(q['cat'] for q in INQUIRIES))}")
print(f"  ✓ trap types: {sorted(set(q['trap'] for q in INQUIRIES))}")

# Write to disk
import os
out = "/opt/Murphy-System/quality_run_31ad/inquiries.json"
os.makedirs("/opt/Murphy-System/quality_run_31ad", exist_ok=True)
with open(out, "w") as f:
    json.dump(INQUIRIES, f, indent=2)
print(f"  ✓ saved to {out}")
