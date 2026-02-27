# Murphy System — License Strategy Analysis

## Executive Summary

**Recommendation: Business Source License 1.1 (BSL 1.1)** for the core platform,
converting to Apache 2.0 after 4 years. Enterprise features remain under a
separate proprietary commercial license.

This is the same model used by HashiCorp (Terraform, Vault, Consul),
and previously by CockroachDB. It is the most battle-tested approach for
projects that need source-available code for adoption while preventing
competitors from offering the software as a competing hosted service.

---

## Requirements

| # | Requirement | Priority |
|---|------------|----------|
| 1 | Sell enterprise functions commercially (multi-tenant SaaS, managed hosting, premium support, white-label) | Must have |
| 2 | Open-source the core to spread adoption | Must have |
| 3 | Prevent competitors from taking the core and hosting it as a competing service without contributing back | Must have |

---

## License Comparison Matrix

| License | OSI Approved | Prevents Hosting-as-a-Service | Allows Commercial Enterprise Add-ons | Adoption Friendly | Time-Delayed Open Source | Used By |
|---------|:---:|:---:|:---:|:---:|:---:|---------|
| **Apache 2.0** (current) | ✅ | ❌ | ✅ | ✅✅✅ | N/A | Kubernetes, Apache projects |
| **MIT + Commons Clause** | ❌ | ⚠️ Ambiguous | ✅ | ⚠️ | ❌ | Redis (briefly, abandoned) |
| **AGPL v3** | ✅ | ⚠️ Partial | ✅ | ⚠️ | N/A | GitLab CE, Grafana, Nextcloud |
| **SSPL v1** | ❌ | ✅ (nuclear) | ✅ | ❌ | ❌ | MongoDB |
| **Elastic License 2.0** | ❌ | ✅ | ✅ | ⚠️ | ❌ | Elasticsearch, Kibana |
| **BSL 1.1** | ❌ (converts) | ✅ | ✅ | ✅✅ | ✅ (4 years) | HashiCorp Terraform/Vault, MariaDB |
| **FSL 1.1** | ❌ (converts) | ✅ | ✅ | ✅✅ | ✅ (2 years) | Sentry |

---

## Detailed Analysis of Each License

### 1. Apache 2.0 (Current License) — ❌ NOT RECOMMENDED

**What it does:** Permissive open-source license. Anyone can use, modify,
distribute, and host the software commercially with no obligations beyond
attribution and patent grant.

**Why companies use it:** Maximum adoption. No friction for enterprise users.
Patent protection.

**Why it fails here:** Provides **zero protection** against a cloud provider
(AWS, Azure, GCP, or any competitor) taking the entire codebase and offering
it as a managed service. This is exactly what happened to:
- Elasticsearch (AWS launched OpenSearch)
- Redis (AWS launched ElastiCache)
- MongoDB (before SSPL switch)

**Verdict:** The current Apache 2.0 license leaves Murphy System completely
exposed to the exact scenario you want to prevent.

---

### 2. MIT + Commons Clause — ❌ NOT RECOMMENDED

**What it does:** Adds a clause to MIT that says "The Software is provided…
without the right to Sell the Software." Attempts to prevent commercial
hosting.

**Problems:**
- The term "Sell" is legally ambiguous — does "selling support" count?
- Created massive community backlash when Redis Labs used it (2018)
- Redis Labs abandoned it within a year in favor of their own RSAL license
- Widely regarded as a failed experiment
- Not OSI-approved, and the community perceives it as "bait and switch"

**Verdict:** Legally weak, community-toxic. No major company still uses this.

---

### 3. AGPL v3 — ⚠️ VIABLE BUT INSUFFICIENT

**What it does:** Strong copyleft. If you run modified AGPL software and
users interact with it over a network, you must release your complete source
code under AGPL. This is the "network copyleft" that closes the "SaaS
loophole" in GPL.

**Who uses it:**
- **GitLab** — CE (Community Edition) is MIT, EE (Enterprise) is proprietary.
  GitLab considered AGPL but chose MIT for maximum adoption.
- **Grafana Labs** — Core Grafana is AGPL v3. Enterprise features are
  proprietary.
- **Nextcloud** — AGPL v3 for the core.

**Why it's not enough:**
- A competitor CAN legally host AGPL software as a service — they just have
  to publish their source modifications. Most large cloud providers can
  comply with this relatively easily.
- AWS, Google, and Microsoft have all demonstrated willingness to host AGPL
  software when profitable enough.
- The "copyleft deterrence" only works against companies who don't want to
  open-source their infrastructure modifications. Large cloud providers have
  already built tooling to handle this.
- Many enterprises have blanket policies against AGPL software, which can
  hurt adoption.

**Verdict:** Deters some competitors but does NOT prevent hosting-as-a-service.
Enterprise AGPL-aversion can hurt adoption.

---

### 4. SSPL v1 (Server Side Public License) — ❌ NOT RECOMMENDED

**What it does:** Based on AGPL but far more aggressive. Section 13 requires
that if you offer the software as a service, you must open-source the
**entire** service stack — management, monitoring, backup, networking,
storage, everything. This is effectively impossible for cloud providers.

**Who uses it:**
- **MongoDB** — Switched from AGPL to SSPL in October 2018 specifically to
  block AWS from hosting MongoDB.

**Problems:**
- Not OSI-approved (OSI explicitly rejected it)
- Not considered open-source by Debian, Fedora, Red Hat, or the Linux
  Foundation
- Considered "toxic" by many open-source communities
- The requirement to open-source your entire infrastructure stack is seen
  as deliberately impossible to comply with (designed to be a poison pill,
  not a real license)
- May create legal uncertainty for legitimate users

**Verdict:** Too aggressive. Designed as a weapon, not a license. Creates
more legal and community problems than it solves.

---

### 5. Elastic License 2.0 (ELv2) — ✅ STRONG OPTION

**What it does:** Simple, readable source-available license with one key
restriction: **"You may not provide the software to third parties as a
hosted or managed service."**

**Who uses it:**
- **Elastic** — Elasticsearch and Kibana use dual ELv2/SSPL (user chooses).
  In 2024 Elastic added AGPL as a third option.

**Strengths:**
- Extremely simple and readable (~400 words)
- The hosted-service restriction is crystal clear
- Allows modification, redistribution, derivative works
- Patent grant included
- Battle-tested by a public company (Elastic, $8B+ market cap)

**Weaknesses:**
- **Never converts** to open source — it's source-available forever
- Not OSI-approved
- Less community trust than BSL (which eventually opens up)
- Some Linux distributions won't package it

**Verdict:** Excellent if you never want the code to become fully open source.
The permanent restriction may hurt long-term adoption compared to BSL.

---

### 6. BSL 1.1 (Business Source License) — ✅ RECOMMENDED

**What it does:** Source-available license that automatically converts to a
true open-source license after a set period (typically 4 years). Includes a
customizable "Additional Use Grant" that specifies what use IS allowed
during the restricted period.

**Who uses it:**
- **HashiCorp** — Terraform, Vault, Consul, Nomad, Packer, Waypoint, Boundary
  (switched from MPL 2.0 to BSL 1.1 in August 2023)
- **MariaDB** — Created the BSL. MariaDB MaxScale uses BSL.
- **CockroachDB** — Used BSL 1.1 from 2019-2024 (recently moved to their
  own CockroachDB Software License for different reasons)

**Key Features:**
- **Source available immediately** — anyone can read, modify, build, and use
  the code
- **Additional Use Grant** — customizable clause that explicitly allows most
  production use, only restricting competitive hosted offerings
- **Automatic conversion** — after the Change Date (4 years), the code
  becomes fully Apache 2.0 (or any OSI-approved license you choose)
- **Non-production use always allowed** — testing, development, evaluation
  are always permitted
- **Clear legal framework** — created by MariaDB's lawyers, reviewed by
  HashiCorp's lawyers, well-understood by enterprise legal teams

**Why it wins for this use case:**

1. **Prevents competitive hosting** — The Additional Use Grant explicitly
   prohibits offering the software as a competing hosted/managed service.

2. **Maximizes adoption** — Source code is visible and usable. Developers
   can read it, build it, modify it, and use it internally. The 4-year
   conversion to Apache 2.0 gives enterprises confidence that they won't
   be locked in.

3. **Supports commercial enterprise features** — Nothing in BSL prevents you
   from selling proprietary enterprise add-ons. The open-core model works
   perfectly: BSL core + proprietary enterprise tier.

4. **Builds trust** — The guaranteed conversion to open source after 4 years
   is a powerful trust signal. It says: "we're not trying to lock you in,
   we just need a head start."

5. **Battle-tested** — HashiCorp processes billions of dollars of
   infrastructure through BSL-licensed Terraform. The license has survived
   enterprise legal review at the largest companies in the world.

---

### 7. FSL 1.1 (Functional Source License) — ✅ HONORABLE MENTION

**What it does:** Similar to BSL but with a shorter conversion period (2
years) and a "Competing Use" restriction instead of a customizable
Additional Use Grant.

**Who uses it:**
- **Sentry** — Error monitoring platform. Switched from BSL to FSL in 2023.

**Compared to BSL:**
- 2-year conversion window (vs 4 years for BSL) — may be too short to
  protect commercial interests
- Less customizable — "Competing Use" is defined by the license, not by you
- Newer, less battle-tested
- Backed by Sentry and the FSL organization

**Verdict:** Good license, but the 2-year conversion window is too short for
most commercial open-core businesses. BSL's 4-year window and customizable
Additional Use Grant give more flexibility.

---

## Industry Precedent Summary

| Company | Previous License | Current License | Why They Switched |
|---------|-----------------|----------------|-------------------|
| **HashiCorp** | MPL 2.0 | **BSL 1.1** → Apache 2.0 (4yr) | AWS, others were offering competing hosted Terraform/Vault services |
| **Elastic** | Apache 2.0 | **ELv2 / SSPL / AGPL** (triple) | AWS launched OpenSearch, directly competing with Elastic Cloud |
| **MongoDB** | AGPL v3 | **SSPL v1** | AWS, Azure, GCP were all hosting MongoDB as a service |
| **CockroachDB** | Apache 2.0 → BSL 1.1 | **CockroachDB Software License** | Needed stronger control over cloud hosting |
| **Sentry** | BSL 1.1 | **FSL 1.1** → Apache 2.0 (2yr) | Wanted shorter conversion window, simpler terms |
| **GitLab** | MIT (CE) + Proprietary (EE) | **MIT (CE) + Proprietary (EE)** | Never changed — chose adoption over protection |
| **Confluent** | Apache 2.0 (Kafka) | **Confluent Community License** (connectors) | Cloud providers hosting Kafka connectors as a service |
| **MariaDB** | GPL v2 | **BSL 1.1** (MaxScale) | Created BSL specifically for this use case |

**The clear trend:** Every major open-core company that faced cloud-provider
competition has moved away from permissive licenses toward source-available
licenses with hosting restrictions.

---

## Definitive Recommendation

### License Structure for Murphy System

```
┌─────────────────────────────────────────────────────┐
│                  Murphy System                       │
├──────────────────────┬──────────────────────────────┤
│     Core Platform    │    Enterprise Features       │
│                      │                              │
│   BSL 1.1            │   Proprietary Commercial     │
│   → Apache 2.0       │   License                    │
│     after 4 years    │                              │
│                      │   • Multi-tenant SaaS        │
│   • Core engine      │   • Managed hosting          │
│   • Base features    │   • White-label              │
│   • CLI tools        │   • Premium support          │
│   • APIs             │   • SSO / SAML / SCIM        │
│   • Documentation    │   • Advanced analytics       │
│   • Community edition│   • SLA guarantees           │
└──────────────────────┴──────────────────────────────┘
```

### What This Means in Practice

| User Type | Can They Use Murphy System? |
|-----------|---------------------------|
| Individual developer using it personally | ✅ Yes, freely |
| Startup using it internally | ✅ Yes, freely |
| Enterprise using it for their own operations | ✅ Yes, freely |
| Consultant deploying it for clients | ✅ Yes, freely |
| Developer contributing back | ✅ Yes, freely |
| Company building integrations/plugins | ✅ Yes, freely |
| Cloud provider offering "Murphy-as-a-Service" | ❌ No — must purchase commercial license |
| Competitor offering a competing hosted platform | ❌ No — must purchase commercial license |

---

## Exact License Text (BSL 1.1 for Murphy System)

The following is the recommended `LICENSE` file content:

```
License text copyright (c) 2020 MariaDB Corporation Ab, All Rights Reserved.
"Business Source License" is a trademark of MariaDB Corporation Ab.

Parameters

Licensor:             Inoni Limited Liability Company (Corey Post)
Licensed Work:        Murphy System
                      The Licensed Work is (c) 2025 Inoni Limited Liability Company.
Additional Use Grant: You may make production use of the Licensed Work,
                      provided Your use does not include offering the Licensed
                      Work to third parties as a hosted or managed service that
                      competes with Murphy System's paid offerings. For purposes
                      of this license:

                      A "competitive offering" is a Product that is offered to
                      third parties on a paid basis, including through paid
                      support arrangements, that provides substantially similar
                      functionality to any Murphy System paid product or
                      service. If Your Product is not a competitive offering
                      when You first make it generally available, it will not
                      become a competitive offering later due to Murphy System
                      releasing a new version of the Licensed Work with
                      additional capabilities. In addition, Products that are
                      not provided on a paid basis are not competitive.

                      "Product" means software that is offered to end users to
                      manage in their own environments or offered as a service
                      on a hosted basis.

                      Hosting or using the Licensed Work for internal purposes
                      within an organization is not considered a competitive
                      offering. Your organization includes all of your
                      affiliates under common control.

Change Date:          Four years from the date the Licensed Work is published.
Change License:       Apache License, Version 2.0

For information about alternative licensing arrangements for the Licensed Work,
please visit https://github.com/Murphy-System or contact the project maintainers.

Notice

Business Source License 1.1

Terms

The Licensor hereby grants you the right to copy, modify, create derivative
works, redistribute, and make non-production use of the Licensed Work. The
Licensor may make an Additional Use Grant, above, permitting limited
production use.

Effective on the Change Date, or the fourth anniversary of the first publicly
available distribution of a specific version of the Licensed Work under this
License, whichever comes first, the Licensor hereby grants you rights under
the terms of the Change License, and the rights granted in the paragraph
above terminate.

If your use of the Licensed Work does not comply with the requirements
currently in effect as described in this License, you must purchase a
commercial license from the Licensor, its affiliated entities, or authorized
resellers, or you must refrain from using the Licensed Work.

All copies of the original and modified Licensed Work, and derivative works
of the Licensed Work, are subject to this License. This License applies
separately for each version of the Licensed Work and the Change Date may vary
for each version of the Licensed Work released by Licensor.

You must conspicuously display this License on each original or modified copy
of the Licensed Work. If you receive the Licensed Work in original or
modified form from a third party, the terms and conditions set forth in this
License apply to your use of that work.

Any use of the Licensed Work in violation of this License will automatically
terminate your rights under this License for the current and all other
versions of the Licensed Work.

This License does not grant you any right in any trademark or logo of
Licensor or its affiliates (provided that you may use a trademark or logo of
Licensor as expressly required by this License).

TO THE EXTENT PERMITTED BY APPLICABLE LAW, THE LICENSED WORK IS PROVIDED ON
AN "AS IS" BASIS. LICENSOR HEREBY DISCLAIMS ALL WARRANTIES AND CONDITIONS,
EXPRESS OR IMPLIED, INCLUDING (WITHOUT LIMITATION) WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, NON-INFRINGEMENT, AND
TITLE.
```

---

## Migration Checklist

When ready to adopt BSL 1.1, complete these steps:

- [ ] Get agreement from all contributors (or ensure CLA is in place)
- [ ] Replace `LICENSE` file with BSL 1.1 text above
- [ ] Update `README.md` license badge and section
- [ ] Add license headers to all source files
- [ ] Create `enterprise/` directory with proprietary license for enterprise features
- [ ] Update `CONTRIBUTING.md` to reference new license and CLA requirements
- [ ] Announce the change to the community with clear explanation
- [ ] Set up dual-licensing infrastructure for enterprise customers

---

## FAQ

**Q: Is BSL 1.1 "open source"?**
A: No, not by the OSI definition during the restriction period. It is
"source-available." After the Change Date (4 years), it converts to Apache
2.0 which IS OSI-approved open source. This is an important distinction.

**Q: Will this hurt adoption?**
A: Minimally. HashiCorp's Terraform adoption has continued to grow under BSL.
The source code is fully visible and usable. The only restriction is on
competitive hosted offerings — which doesn't affect 99%+ of users.

**Q: What about the OpenTF/OpenTofu fork?**
A: Yes, when HashiCorp switched to BSL, the community forked Terraform as
OpenTofu under MPL 2.0. This is a real risk. However: (a) OpenTofu has
not displaced Terraform, (b) it required massive community effort, and
(c) only the code BEFORE the BSL switch could be forked — all new
development is protected.

**Q: Can someone fork the code before the license change?**
A: The current Apache 2.0 code can always be forked. But all NEW code
written after the BSL switch is protected. The fork would be frozen at
the point of the license change.

**Q: What about contributors?**
A: You should implement a Contributor License Agreement (CLA) that grants
the project the right to license contributions under BSL. This is standard
practice (HashiCorp, Elastic, MongoDB all require CLAs).
