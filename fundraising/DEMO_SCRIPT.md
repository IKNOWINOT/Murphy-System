# Murphy System — 3-Minute Demo Script

> **Format:** Loom screen-share or live demo in a 30-minute investor meeting.  
> **Total runtime:** ~3 minutes. Practice until you can hit each beat on time.

---

## Setup (Before You Hit Record)

- Murphy server running locally: `cd "Murphy System" && bash setup_and_start.sh`
- Or if already running: confirm `http://localhost:8000/api/health` returns `{"status": "healthy"}`
- Terminal open with a large font (investors watch on small screens)
- Browser open to `terminal_unified.html` or `terminal_architect.html`
- Kill all notifications. Full screen terminal + browser split-view.

---

## 0:00–0:30 — Setup & Context

**Say:**

> "What you're about to see is Murphy System — an AI automation platform that converts plain English into governed, production-grade workflows. It covers enterprise business automation, industrial control systems — SCADA, BACnet, OPC UA — and content creator pipelines. All in one system.
>
> This was built by one person. I'm Corey Post, the sole developer. 218,000 lines of Python, 1,122 modules, 8,843 passing tests. It runs right now. Let me show you."

---

## 0:30–2:30 — Live Demo

### Step 1: Show the server is running (15 sec)

```bash
curl http://localhost:8000/api/health
```

**Expected output:**
```json
{"status": "healthy", "version": "1.0.0", "timestamp": "..."}
```

**Say:** *"The API server is live. That's the runtime — not a mock."*

---

### Step 2: Show system capabilities (20 sec)

```bash
curl http://localhost:8000/api/status
```

**Expected output (abbreviated):**
```json
{
  "modules_loaded": 1122,
  "connectors": 90,
  "automation_types": ["factory", "content", "data", "system", "agent", "business"],
  "web_interfaces": 14
}
```

**Say:** *"1,122 modules loaded. 90+ platform connectors. 6 automation types. This is what 'production-ready' actually looks like."*

---

### Step 3: Open the terminal UI (20 sec)

Open `terminal_unified.html` in the browser. Show the dark terminal interface.

**Say:** *"This is Murphy's natural interface — a terminal UI. Every Murphy deployment gets this. No slides. No drag-and-drop flowcharts unless you want them."*

---

### Step 4: Describe a task in natural language (45 sec)

Type into the prompt field:

> `Set up a weekly revenue report that pulls from Stripe, formats it into a PDF, and emails it to my CFO every Monday morning at 9am.`

Hit enter. Let Murphy generate.

**While it runs, say:**

> *"I'm not clicking buttons or dragging connectors. I described what I want. Murphy is now building the execution plan — the DAG — including which connectors to use, what data to transform, and where to deliver it."*

**Point at the output:**

> *"See this confidence score? Every step gets scored. High confidence — Murphy executes automatically. Medium confidence — it flags for review. Low confidence — it stops and asks me. That's the confidence-gated execution layer. No other platform has this."*

---

### Step 5: Point out HITL gate (20 sec)

Show the HITL approval prompt (if generated) or explain:

**Say:**

> *"The final step — sending the email to the CFO — triggered a Human-in-the-Loop gate. Murphy knows that sending financial data to a C-suite executive is a high-stakes action. It won't fire until a human approves it. This is the governance framework that makes Murphy safe to run in regulated industries."*

---

## 2:30–3:00 — Close

**Say:**

> "Let me leave you with the numbers: 218,000 lines of production Python. 1,122 modules. 8,843 passing tests. 90+ platform connectors — including SCADA, BACnet, and OPC UA, which no other automation platform touches. 14 working web interfaces. All built by one developer.
>
> I'm raising $500,000 on a SAFE at a $5 to $7 million valuation cap. No discount. 18 months of runway. First hire unlocks the first design partner conversations.
>
> If you want to go deeper: corey.gfc@gmail.com. The full codebase is at github.com/IKNOWINOT/Murphy-System. Thank you."

---

## Backup Lines (If Something Breaks)

**If the server is down:**
> *"The server needs a moment — that's fine, this is a local dev instance. While it restarts, let me show you the codebase structure — 1,122 modules, 90 connectors — this is what you're investing in."*

**If the NL generation is slow:**
> *"Murphy is routing through the LLM — depending on which model is configured, this can take 5–10 seconds. In production with a dedicated inference endpoint, this is sub-2-seconds. What you're watching is the DAG being built in real time."*

**If asked about revenue mid-demo:**
> *"We're pre-revenue — intentionally. I've been building, not selling. This raise funds the first hire and the design partner process. First revenue target: 6 months after close."*

---

## Notes for Recording (Loom)

- Record at 1920×1080, not 4K (Loom plays better at standard res)
- Use `--font-size 16` in your terminal config for readability
- Slow down typing — investors are reading the output, not just watching
- Pause for 1 second after each curl output before speaking
- End with your face on camera for 5 seconds — it builds trust

---

*Back to [Fundraising Plan](FUNDRAISING_PLAN.md) · [Investment Memo](INVESTOR_MEMO.md)*
