# Murphy vs. Moveworks 100 Use Cases — Coverage Grid
# Source: Moveworks "2026 AI Agent Guide: 100+ Use Cases for the Enterprise"
# Audit date: 2026-06-08

## Legend
- 🟢 NATIVE — Murphy can do this today with existing connectors/skills
- 🟡 REACHABLE — Pattern exists in Murphy; needs a new connector to ship
- 🔴 OUT OF SCOPE — Different category (physical world, deep ServiceNow lock-in, etc.)

## Summary
| Category | Native | Reachable | Out of scope | Total |
|---|---|---|---|---|
| HR | 0 | 8 | 2 | 10 |
| IT | 3 | 5 | 2 | 10 |
| Sales | 6 | 4 | 0 | 10 |
| Finance | 4 | 6 | 0 | 10 |
| Engineering | 5 | 5 | 0 | 10 |
| Customer Service | 4 | 6 | 0 | 10 |
| Legal | 3 | 6 | 1 | 10 |
| Facilities | 0 | 4 | 6 | 10 |
| Marketing | 5 | 5 | 0 | 10 |
| Productivity | 4 | 6 | 0 | 10 |
| **TOTAL** | **34** | **55** | **11** | **100** |

**Coverage: 34/100 native, 89/100 reachable, 11/100 out of scope.**

---

## 1. HR (0/10 native, 8/10 reachable, 2/10 OOS)

| # | Use Case | Status | Murphy path |
|---|---|---|---|
| 1 | Candidate Application Status (Greenhouse) | 🟡 | Need Greenhouse connector; Rosetta recruiter role |
| 2 | Submit Interview Feedback (Workday) | 🟡 | Need Workday connector |
| 3 | Get Team Performance Ratings (Workday) | 🟡 | Need Workday connector |
| 4 | Contract Expiry Notifications (SAP) | 🟡 | Need SAP or generic doc-watcher; pattern exists |
| 5 | Issue Employee Surveys (Workday) | 🟡 | Need Workday connector; cadence_pulse can drive |
| 6 | Change Legal Name (Workday) | 🔴 | Workday-specific identity flow; not our buyer |
| 7 | Change Benefit Elections (Workday) | 🟡 | Need Workday connector |
| 8 | Look Up Team Attendance Report (Workday) | 🟡 | Need Workday connector |
| 9 | Set Goals for Direct Reports (ADP/SAP/Workday) | 🟡 | Need any of the three |
| 10 | View Total Compensation (Workday) | 🔴 | Workday-specific equity flow |

**Murphy advantage in HR:** None today. This is Moveworks' home turf.
**Build priority:** Low. We don't sell to HR teams; we sell to founders.

---

## 2. IT (3/10 native, 5/10 reachable, 2/10 OOS)

| # | Use Case | Status | Murphy path |
|---|---|---|---|
| 1 | Summarize an Incident (ServiceNow) | 🟢 | LLM summarization over our event_spine.db |
| 2 | Monitor SLA Compliance (ServiceNow) | 🟢 | sla_monitor (PCR-006) does this natively |
| 3 | Identify Open Incidents (PagerDuty/Datadog) | 🟡 | Need PagerDuty/Datadog connector |
| 4 | Incident Metrics Summary | 🟢 | audit.db + LLM rollup |
| 5 | Find Company P1 Outages | 🟡 | Need monitoring connector |
| 6 | CVE Lookup (Palo Alto) | 🟡 | Need NVD or Palo Alto connector |
| 7 | Suggest Incident Categories | 🟡 | LLM classifier; needs ServiceNow target |
| 8 | Reset Microsoft MFA | 🔴 | Microsoft Graph + their identity; not us |
| 9 | Review IT Agent Performance | 🟡 | We do this for Murphy agents; need theirs |
| 10 | Check Software License Inventory | 🔴 | ServiceNow ITAM-specific |

**Murphy advantage in IT:** Self-modifying source means Murphy can write its own incident response code in flight. Moveworks can't.

---

## 3. Sales (6/10 native, 4/10 reachable)

| # | Use Case | Status | Murphy path |
|---|---|---|---|
| 1 | Pre-Meeting Brief (Salesforce) | 🟢 | salesforce_connector + LLM brief |
| 2 | Next Best Actions for Lead (Salesforce) | 🟢 | r82 lead prospector pattern |
| 3 | Identify Stalled Opportunities | 🟢 | salesforce_connector + cadence_pulse |
| 4 | Highlight Upsell (Snowflake) | 🟡 | Need Snowflake connector |
| 5 | Monitor Account Risk (Salesforce) | 🟢 | sentiment + audit pattern |
| 6 | Identify ARR (Salesforce) | 🟢 | salesforce_connector + billing.db rollup |
| 7 | Approve/Reject Deal Discounts (Salesforce) | 🟡 | HITL gate + policy engine |
| 8 | Opportunities Influenced by Campaign | 🟢 | salesforce_connector pattern |
| 9 | Update Opportunity w/ Call Notes | 🟡 | Need Gong/Zoom transcript pull |
| 10 | Create a Quote (Salesforce CPQ) | 🟡 | Need CPQ connector |

**Murphy advantage in Sales:** Our R82 customer-centric composer uses CRM enrichment data (tech stack + pain signatures) that most CRMs DON'T enrich themselves. Moveworks reads what's there; Murphy writes what should be there.

---

## 4. Finance (4/10 native, 6/10 reachable)

| # | Use Case | Status | Murphy path |
|---|---|---|---|
| 1 | Approve/Reject Expense Reports (SAP) | 🟡 | Need SAP connector |
| 2 | Edit Expense Entry Details (SAP) | 🟡 | Need SAP connector |
| 3 | Auto-Identify Past Due Invoices (NetSuite) | 🟢 | billing.db query + cadence_pulse |
| 4 | Look Up Purchase Orders (Coupa/SAP) | 🟡 | Need Coupa or SAP |
| 5 | Identify Vendor Onboarding Status | 🟢 | Inoni's own vendor tracking |
| 6 | Cost Center ID Lookup (ServiceNow) | 🔴 | ServiceNow-specific |
| 7 | Summarize Compensation (SAP) | 🟡 | Need SAP HCM |
| 8 | View Stock Grant Summary (Workday) | 🔴 | Workday equity-specific |
| 9 | Auto-Approve Low-Risk Expenses | 🟢 | Policy gate + LLM classifier (already pattern) |
| 10 | Look Up License Cost | 🟢 | billing.db + tenant_addons rollup |

**Murphy advantage in Finance:** PATCH-409 job-tagged ledger gives **per-customer per-job** invoice attribution. No enterprise system does this — they bill by seat or by API call. Murphy bills by work-attributable job. Pricing canon already supports it.

---

## 5. Engineering (5/10 native, 5/10 reachable)

| # | Use Case | Status | Murphy path |
|---|---|---|---|
| 1 | Identify Open Incidents | 🟡 | Need PagerDuty/Datadog |
| 2 | Find P1 Outages | 🟢 | event_spine + watchdog already does this |
| 3 | Look Up Jira Issues for Epic | 🟡 | Need Jira connector |
| 4 | Look Up Delayed Epics | 🟡 | Need Jira |
| 5 | Incident Metrics Summary | 🟢 | audit.db rollup |
| 6 | Update Issue Status (Jira) | 🟡 | Need Jira |
| 7 | Summarize Incident | 🟢 | LLM summarization (native) |
| 8 | Look Up Issue by Keyword (Jira) | 🟡 | Need Jira |
| 9 | Monitor SLA Compliance | 🟢 | sla_monitor |
| 10 | CVE Lookup | 🟢 | Web search + LLM (native) |

**Murphy advantage in Engineering:** Self-patching. When Murphy detects an incident, it can WRITE the fix and ship it (snapshot → verify → commit). Moveworks files the Jira ticket; Murphy closes it with a PR.

---

## 6. Customer Service (4/10 native, 6/10 reachable)

| # | Use Case | Status | Murphy path |
|---|---|---|---|
| 1 | Automate Ticket Triage (Zendesk) | 🟡 | Need Zendesk |
| 2 | Detect/Act on Renewal Risks | 🟢 | salesforce + sentiment pattern |
| 3 | Summarize Top Recurring Cases | 🟢 | event_spine + LLM cluster |
| 4 | Efficient Ticket Routing (Zendesk) | 🟡 | Need Zendesk |
| 5 | Weekly Customer Feedback Digest | 🟢 | Already shipped pattern |
| 6 | Escalate Urgent Community Posts (Gainsight) | 🟡 | Need Gainsight or Discord |
| 7 | Predict Churn Risks | 🟢 | salesforce + ML pattern |
| 8 | Celebrate Customer Milestones | 🟡 | Need event tracking |
| 9 | Summarize Customer Issue | 🟢 | Native LLM |
| 10 | Knowledge Base Management | 🟡 | docs/auto + RAG (PCR-010) |

**Murphy advantage in CS:** Soul + HITL means Murphy refuses to send a bad response. Their agent generates and sends. Ours generates, gates through soul, refuses if bad.

---

## 7. Legal (3/10 native, 6/10 reachable, 1/10 OOS)

| # | Use Case | Status | Murphy path |
|---|---|---|---|
| 1 | Legal Doc Review / E-Discovery | 🟡 | RAG over docs (PCR-010) |
| 2 | Automated Doc Drafting (DocuSign) | 🟡 | Need DocuSign |
| 3 | Look Up SLA Status | 🟢 | sla_monitor |
| 4 | Policy Review/Approval | 🟡 | compliance_as_code_engine |
| 5 | Send MNDA via DocuSign | 🟡 | Need DocuSign |
| 6 | Reminder to Pending Signers (DocuSign) | 🟡 | Need DocuSign |
| 7 | Look Up Envelope Status (DocuSign) | 🟡 | Need DocuSign |
| 8 | Procurement Contract Guidelines | 🟢 | RAG over glossary + canon |
| 9 | Contract Extension Alerts | 🟢 | cadence_pulse + billing.db |
| 10 | IP Protection / Management | 🔴 | USPTO-specific |

**Murphy advantage in Legal:** Canon-as-code. Our compliance gate REFUSES to act outside policy. Theirs surfaces a warning.

---

## 8. Facilities (0/10 native, 4/10 reachable, 6/10 OOS)

Almost entirely physical-world or building-management-system specific.
- 🔴 Book meeting room, desk, locker, badge access, EV charger, visitor reg
- 🟡 Submit issue, remote work request, catering feedback, lunch satisfaction (all are forms-and-routing patterns)

**Murphy advantage in Facilities:** None. Wrong category for us.

---

## 9. Marketing (5/10 native, 5/10 reachable)

| # | Use Case | Status | Murphy path |
|---|---|---|---|
| 1 | Analyze Marketing Campaigns | 🟢 | Google Analytics connector exists |
| 2 | A/B Test Result Summary (Pendo) | 🟡 | Need Pendo |
| 3 | Submit Content Requests (SmartSheet/Asana) | 🟡 | Need PM tool |
| 4 | Opportunities Influenced by Campaign | 🟢 | salesforce + GA rollup |
| 5 | Product Messaging / Competitive Info | 🟢 | RAG over docs + web search |
| 6 | Surface Competitive Intel (Gong) | 🟡 | Need Gong |
| 7 | Marketing Asset Campaign (Marketo) | 🟡 | Need Marketo |
| 8 | Campaign Engagement Hotspots | 🟢 | salesforce + GA |
| 9 | Keyword Alerts | 🟢 | web_search skill |
| 10 | Look Up Leads for Campaign | 🟢 | crm.db query (we have 283 enriched) |

**Murphy advantage in Marketing:** We have a customer-centric LLM composer (R82) that uses real CRM enrichment to write personalized outreach. Most CRMs just blast generic templates. This is a genuine product advantage.

---

## 10. Productivity (4/10 native, 6/10 reachable)

| # | Use Case | Status | Murphy path |
|---|---|---|---|
| 1 | Meeting Summaries (Gong) | 🟡 | Need Gong/transcript source |
| 2 | Create Task (Asana) | 🟡 | Need Asana |
| 3 | Update Task (Asana) | 🟡 | Need Asana |
| 4 | Create Project (Asana) | 🟡 | Need Asana |
| 5 | Next Steps from Meeting (Gong) | 🟡 | Need Gong |
| 6 | Lookup Attendance (Zoom) | 🟡 | Need Zoom |
| 7 | Lookup Meeting Q&A (Zoom) | 🟡 | Need Zoom |
| 8 | See All My Tasks (Asana) | 🟢 | Conductor + state machine native |
| 9 | Lookup Public Slack Channels | 🟢 | slack_connector |
| 10 | Lookup Gong Meetings | 🟡 | Need Gong |

**Murphy advantage in Productivity:** Murphy IS productivity — it doesn't help an employee be productive, it does the work autonomously. Different value prop entirely.

---

## Strategic implications

### Where Murphy is structurally superior
1. **Autonomy depth.** They surface info + take simple actions. Murphy plans + writes code + ships changes + verifies.
2. **Self-modification.** Murphy is the only system in either rubric that patches its own source.
3. **Tenancy + privacy at code level.** CrossTenantReadRefused exception is enforceable; their RBAC is configurable.
4. **Job-attributed billing.** Customer-facing per-job invoices, not per-seat.
5. **BYO transaction model.** Tenant uses own credentials = Murphy takes zero. They always sit in the middle.
6. **Soul + HITL gate.** Runtime refusal of policy violations, not post-hoc audit.
7. **Variance Interception (just shipped).** 33/66 thresholds + Pythagorean cost growth = structural failure prevention they don't articulate.

### Where Moveworks is structurally superior
1. **100+ enterprise connectors.** We have ~9.
2. **1,000+ pre-built agent templates.** We have ~10 working skills.
3. **SOC 2 / ISO 27001 certifications.** We have the architecture for it; not the audit.
4. **100+ language support.** English only.
5. **Native Slack/Teams ChatOps.** We have channel-connections, not deep workspace integration.
6. **Agent Studio low-code builder.** Rosetta architecture is more powerful but not low-code.

### Hybrid play — what to steal
- **Use-case taxonomy as sales doc.** ← Just shipped this audit.
- **"Pre-built operator" framing.** Rebrand Rosetta role bundles as "Murphy Operators" with the existing operator pricing ($1,499/$2,999/$5,999). Each one replaces a $60k/yr human, not a Slack reminder.
- **Ciena-format case studies.** Three of them, even with internal tenants for now.

### What NOT to steal
- Don't chase their 1,000-template marketplace. Depth-not-catalog is our moat.
- Don't drop self-modifying architecture to look like normal SaaS.
- Don't lead with employee-help-desk use cases. Wrong buyer.

### Honest read
- **Different categories.** Moveworks is the help-desk-agent-for-employees Cadillac.
- **Murphy is the autonomous-business-operator.**
- A Fortune-500 IT director buys Moveworks. A founder building an autonomous business builds on Murphy.
- We are **superior on the dimensions that matter for autonomy**, behind on **dimensions that matter for enterprise distribution**.
- The hybrid: package what we have using their framing (taxonomy, operators, case studies). Don't chase what they have (connectors, certifications, languages) until revenue justifies it.
