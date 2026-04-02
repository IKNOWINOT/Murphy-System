# Murphy System — 6-Week Fundraising Plan

> **Goal:** Close $500K SAFE at $5M–$7M cap within 6 weeks of launching outreach.  
> **Strategy:** Lead with working software. Every conversation starts with a live demo, not a deck.

---

## Target Investors

| Investor | Pre-Revenue Friendly | Check Size | Best Path to Intro | Thesis Alignment |
|---|:---:|---|---|---|
| **Naval Ravikant** | ✅ Yes | $100K–$250K | AngelList raise + Twitter/X demo post tagging @Naval | Solo-founder moonshots, extreme technical leverage |
| **Jason Calacanis** | ✅ Yes | $25K–$100K | LAUNCH accelerator ([launch.co/apply](https://launch.co/apply)) + founders@launch.co | Category-defining products, bold founders |
| **Mark Cuban** | ✅ Yes | $250K–$1M | mark@markcuban.com — cold email with Loom link (he reads these) | Working products over decks, technical underdogs |
| **Kulveer Taggar** | ✅ Yes | $100K–$250K | Twitter/X DM + YC alumni network | Industrial AI, transformative automation |
| **Elad Gil** | ⚠️ Maybe | $250K–$1M | Portfolio founder intro, or via Naval/Jason if one commits first | Application-layer AI platforms |
| **Scott Belsky** | ⚠️ Maybe | $100K–$500K | Needs 5–10 creator waitlist signups first, then direct outreach | Creative workflow automation, tools for creators |

**Recommended syndicate:** Elad Gil ($250K–$500K lead) + Kulveer Taggar ($100K–$250K) + Scott Belsky ($100K–$250K). See [COMPETITIVE_MOAT.md](COMPETITIVE_MOAT.md) for rationale.

**Sequencing:**
1. Land Naval or Jason first (fastest to reach, will amplify via their audiences)
2. Use any commitment to approach Elad Gil
3. Elad's name unlocks Kulveer and Scott

---

## Week-by-Week Plan

### Weeks 1–2: Build the Proof Arsenal

Before reaching out to anyone, have every asset ready:

- [ ] **Record 3-min Loom demo** (follow [`DEMO_SCRIPT.md`](DEMO_SCRIPT.md))
  - Demo must show: running server, health endpoint, NL→workflow generation, HITL gate, confidence score
  - Upload to Loom, create a shareable link with view tracking enabled
- [ ] **Deploy design partner landing page** (`DESIGN_PARTNER_WAITLIST.html`)
  - Deploy to Netlify Drop (drag-and-drop, free, 30 seconds)
  - or GitHub Pages on `iknowinot.github.io/murphy-waitlist`
- [ ] **Create AngelList raise** at [angel.co/raise](https://angel.co/raise)
  - Import this investor memo as the deck
  - Set raise amount to $500K, instrument to SAFE, cap to $5M–$7M
- [ ] **Set up Clerky account** at [clerky.com](https://www.clerky.com)
  - Generate SAFE template ($500 flat fee)
  - Have docs ready to send within 24 hours of a verbal commitment
- [ ] **Prepare the one-email pitch** (see template below)

### Week 3: Warm Intro Hunting

The goal is to identify the best path to each investor — warm intros convert 10x better than cold.

**For Naval Ravikant:**
- Post the Loom demo on Twitter/X with a thread: "I built a self-healing, self-improving AI automation platform that speaks SCADA, BACnet, and plain English. Solo. 218K lines. 8,843 tests. Here's a 3-minute demo."
- Tag @Naval in the thread
- Submit to AngelList — Naval runs Rolling Funds there; he will see it

**For Jason Calacanis:**
- Apply to LAUNCH Accelerator at [launch.co/apply](https://launch.co/apply)
- Email founders@launch.co with the one-paragraph pitch + Loom link
- TWIS podcast submissions: Jason reads the show email; a cold email with a working demo link is the right move

**For Mark Cuban:**
- Email mark@markcuban.com with subject: "Working AI automation platform — SCADA to creator economy — solo dev — Loom demo"
- Keep the email to 5 sentences + Loom link. He responds to working demos, not decks.

**For Kulveer Taggar:**
- Twitter/X DM with: "Built the first NL→workflow system that speaks OPC UA and BACnet natively. Solo dev. Running in production. 3-min demo?"
- Search YC alumni network (if you have access) for mutual connections

**For Elad Gil:**
- Do NOT cold email. Wait until Naval, Jason, or Mark has committed.
- Then reach out via a portfolio founder intro or the AngelList raise

### Weeks 4–5: Conversations

**For every 30-minute investor meeting, use this playbook:**

#### 0–3 min: Live Demo
- Screen share — do NOT use slides
- `curl http://localhost:8000/api/health` → show healthy JSON response
- `curl http://localhost:8000/api/status` → show module count and capabilities
- Open terminal_unified.html (or terminal_architect.html)
- Type a task in plain English: *"Set up a weekly revenue report that pulls from Stripe, formats it, and emails it to my CFO every Monday."*
- Show Murphy generating the workflow DAG
- Point out the confidence score and HITL gate on the final email step

**Key line:** *"Every other automation platform makes you be the engineer. Murphy makes you be the operator."*

#### 3–8 min: Competitive Moat
- Show the comparison table from [COMPETITIVE_MOAT.md](COMPETITIVE_MOAT.md)
- Lead with the industrial OT gap: *"No SaaS company has ever shipped a BACnet/OPC UA connector. I have 90+ of them. The industrial automation market is $180B with zero modern competition."*
- Then: *"218K lines of source, 8,843 passing tests, 1,122 modules — solo developer. That's the signal."*

#### 8–12 min: The Ask
- *"I'm raising $500K on a SAFE at a $5M–$7M cap. No discount. No board seats. 18 months of runway."*
- Show the use-of-funds table (founder salary $8K/mo, first hire $10K/mo, infra $3K/mo)
- *"First hire unlocks the first design partner conversations I can't handle alone while continuing to ship."*

#### 12–20 min: FAQ Handling
*(See FAQ section below)*

---

## Common Questions & Answers

**"Why no revenue?"**
> "Because I've been building. 218K lines, 1,122 modules, 14 web interfaces, 8,843 tests — that's what one person shipping full-time looks like. The product is real. The first design partner conversations start the month after we close."

**"Can one person maintain a 1,122-module codebase?"**
> "I already have been. The self-healing engine, immune system, and automated test suite mean the system monitors itself. The first hire is a force-multiplier on an already-built foundation — not someone to build it."

**"What stops Zapier from copying this?"**
> "Nothing stops them from trying. But Zapier's business model depends on breadth of simple connectors for non-technical users. Industrial OT is a different customer, different sales motion, and requires deep protocol expertise that took years to build. They have 1,500 employees and haven't touched SCADA. I have. The governance stack alone — confidence gating, HITL graduation, the causality sandbox — is 18 months of work for a funded team to replicate."

**"What's the first revenue path?"**
> "5 industrial OT design partners. Target: facilities managers and plant engineers who currently pay $50K–$500K/year for automation tooling. Our $99/mo OT bundle is not a threat to their existing vendor — it's an upgrade layer on top of it. First customer target: 6 months."

**"What if you burn out or get hit by a bus?"**
> "Fair question. The answer is in the code. The self-improvement engine, correction loop, and 706 test files mean the system's behaviour is captured in tests, not in my head. A competent engineer could pick up this codebase. The first hire mitigates the bus factor immediately. And honestly — I built this in my current state. The raise solves the overwork problem."

---

### Week 6: Close

**The FOMO cascade:**
1. As soon as one investor verbally commits, email the others: *"[Investor name] has committed. I have [remaining $X] left in the round."*
2. Send Clerky SAFE documents within 24 hours of a verbal yes — momentum dies during paperwork delays.
3. If the round is oversubscribed, increase the cap from $5M to $7M before adding investors; do not add investors above the cap.

**Closing checklist:**
- [ ] Wire Clerky SAFE with correct cap, amount, and investor name
- [ ] Countersign and return within 48 hours
- [ ] Wire instructions from Inoni LLC business bank account
- [ ] Announce close on Twitter/X (generates inbound interest for the next round)

---

## SAFE Terms

| Term | Value |
|------|-------|
| Instrument | SAFE (Simple Agreement for Future Equity) |
| Total raise | $500,000 |
| Valuation cap | $5M–$7M (negotiable based on lead investor) |
| Discount | None |
| Board seats | None |
| Pro-rata rights | Offered to investors $100K+ |
| Estimated dilution | ~7–10% (at $5M cap) |
| Legal docs | Clerky SAFE (~$500 flat fee) |
| MFN clause | Standard Y Combinator SAFE language |

**Why SAFE?** No valuation negotiation, no board seats, closes in days not months. The standard instrument for pre-revenue angel rounds. YC-standard docs mean investors know exactly what they're signing.

---

## One-Email Pitch Template

```
Subject: Murphy System — AI automation that speaks SCADA + plain English — $500K SAFE — Loom demo

Hi [Name],

I built Murphy System: an AI automation platform that converts plain English into governed, production-grade workflows — across enterprise, industrial OT (SCADA/BACnet/OPC UA), and content creator pipelines. Solo developer. 218K lines. 8,843 tests. Running in production.

No automation platform covers factory floor to enterprise to content creator in one governed system. Industrial OT ($180B market) has zero modern competitors. I'm the first.

3-min demo: [LOOM LINK]

Raising $500K SAFE at $5M–$7M cap. No revenue yet — this is pre-revenue. Use of funds: first hire + 18 months of runway → 5 design partners → first revenue in 6–9 months.

Worth 20 minutes?

Corey Post
corey.gfc@gmail.com
github.com/IKNOWINOT/Murphy-System
```

---

*Back to [Investment Memo](INVESTOR_MEMO.md) · [Competitive Moat](COMPETITIVE_MOAT.md)*
