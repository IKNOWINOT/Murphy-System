"""
PATCH-329b — SaaS Frontend Pages
Adds to production_router.py:

  from saas_pages import register_saas_pages
  register_saas_pages(app)

Pages:
  GET  /start          — public lead capture (intake survey)
  GET  /dashboard      — owner dashboard (auth required)
  GET  /hitl/{id}/approve  — one-click approve
  GET  /hitl/{id}/reject   — one-click reject
  GET  /download       — gated download page (must be active subscriber)
  POST /api/stripe/checkout — create Stripe session for $100/mo
  POST /api/stripe/webhook  — Stripe webhook → activate account
"""

import uuid
import sqlite3
import json
import os
from datetime import datetime
from flask import request, jsonify, Response

OO_DB = "/var/lib/murphy-production/owner_operator.db"
STRIPE_SECRET = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_PRICE_ID = os.environ.get("STRIPE_PRICE_ID_100", "")   # $100/mo price ID
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")


# ─────────────────────────────────────────────────────────────────────────────
# GET /start  — Public intake survey
# ─────────────────────────────────────────────────────────────────────────────

START_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Murphy — Start Your Setup</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0a0a0a;color:#e8e8e8;min-height:100vh}
  .hero{background:linear-gradient(135deg,#0a0a0a 0%,#111827 100%);padding:60px 20px 40px;text-align:center;border-bottom:1px solid #1e2535}
  .logo{font-size:32px;font-weight:800;color:#fff;letter-spacing:-1px}
  .logo span{color:#3b82f6}
  .tagline{color:#9ca3af;margin-top:8px;font-size:16px}
  .container{max-width:640px;margin:0 auto;padding:40px 20px}
  .step{display:none}.step.active{display:block}
  .step-label{font-size:12px;color:#6b7280;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px}
  h2{font-size:24px;font-weight:700;margin-bottom:6px;color:#fff}
  .sub{color:#9ca3af;font-size:15px;margin-bottom:32px;line-height:1.5}
  .field{margin-bottom:20px}
  label{display:block;font-size:13px;color:#9ca3af;margin-bottom:6px;font-weight:500}
  input,select,textarea{width:100%;padding:12px 14px;background:#111827;border:1px solid #1e2535;border-radius:8px;color:#e8e8e8;font-size:15px;outline:none;transition:border-color .2s}
  input:focus,select:focus,textarea:focus{border-color:#3b82f6}
  textarea{resize:vertical;min-height:80px}
  select option{background:#111827}
  .btn{width:100%;padding:14px;background:#3b82f6;color:#fff;border:none;border-radius:8px;font-size:16px;font-weight:600;cursor:pointer;transition:background .2s;margin-top:8px}
  .btn:hover{background:#2563eb}
  .btn-back{background:#1e2535;color:#9ca3af;margin-top:8px}
  .btn-back:hover{background:#374151}
  .progress{display:flex;gap:6px;margin-bottom:32px}
  .dot{height:4px;flex:1;background:#1e2535;border-radius:2px;transition:background .3s}
  .dot.done{background:#3b82f6}
  .chip-group{display:flex;flex-wrap:wrap;gap:8px;margin-top:6px}
  .chip{padding:8px 14px;background:#1e2535;border:1px solid #1e2535;border-radius:20px;font-size:13px;cursor:pointer;transition:all .2s;color:#9ca3af}
  .chip.selected{background:#1e3a5f;border-color:#3b82f6;color:#60a5fa}
  .result-card{background:#111827;border:1px solid #1e2535;border-radius:12px;padding:24px;margin-bottom:16px}
  .result-card h3{font-size:16px;font-weight:600;color:#fff;margin-bottom:6px}
  .result-card p{color:#9ca3af;font-size:14px;line-height:1.5}
  .score-badge{display:inline-block;padding:4px 12px;border-radius:20px;font-size:13px;font-weight:600}
  .score-book{background:#1e3a5f;color:#60a5fa}
  .score-nurture{background:#1a2e1a;color:#4ade80}
  .score-enterprise{background:#2d1a3a;color:#c084fc}
  .workflow-item{display:flex;align-items:center;gap:10px;padding:10px 0;border-bottom:1px solid #1e2535}
  .workflow-item:last-child{border-bottom:none}
  .wf-dot{width:8px;height:8px;background:#3b82f6;border-radius:50%;flex-shrink:0}
  .wf-text{font-size:14px;color:#d1d5db}
  .wf-module{font-size:12px;color:#6b7280;font-family:monospace;margin-left:auto}
  .hours-row{display:flex;gap:12px}
  .hours-row .field{flex:1}
  .error{background:#2d1a1a;border:1px solid #7f1d1d;border-radius:8px;padding:12px;color:#f87171;font-size:14px;margin-bottom:16px;display:none}
  .spinner{display:none;text-align:center;padding:20px;color:#6b7280}
</style>
</head>
<body>

<div class="hero">
  <div class="logo">murphy<span>.</span>systems</div>
  <div class="tagline">Your autonomous business operator — $100/month</div>
</div>

<div class="container">

  <!-- PROGRESS -->
  <div class="progress" id="progress">
    <div class="dot done" id="d1"></div>
    <div class="dot" id="d2"></div>
    <div class="dot" id="d3"></div>
    <div class="dot" id="d4"></div>
    <div class="dot" id="d5"></div>
  </div>

  <!-- STEP 1: Basic Info -->
  <div class="step active" id="step1">
    <div class="step-label">Step 1 of 5</div>
    <h2>Let's start with you</h2>
    <p class="sub">Murphy will build your back office around your actual operation — not a template.</p>
    <div class="error" id="err1"></div>
    <div class="field"><label>Your name</label><input type="text" id="contact_name" placeholder="Jane Smith"></div>
    <div class="field"><label>Business email</label><input type="email" id="email" placeholder="jane@yourcompany.com"></div>
    <div class="field"><label>Company name</label><input type="text" id="company_name" placeholder="Acme Plumbing"></div>
    <div class="field"><label>Phone (optional)</label><input type="tel" id="phone" placeholder="+1-503-555-0100"></div>
    <button class="btn" onclick="next(1)">Continue →</button>
  </div>

  <!-- STEP 2: Business Profile -->
  <div class="step" id="step2">
    <div class="step-label">Step 2 of 5</div>
    <h2>Your business</h2>
    <p class="sub">Be honest — the more accurate this is, the better Murphy configures itself.</p>
    <div class="field">
      <label>Industry</label>
      <select id="industry">
        <option value="">Select your industry</option>
        <option>Plumbing / HVAC</option>
        <option>Electrical Contracting</option>
        <option>General Contracting</option>
        <option>MEP Engineering</option>
        <option>Manufacturing</option>
        <option>Logistics / Distribution</option>
        <option>Real Estate</option>
        <option>Legal / Professional Services</option>
        <option>Healthcare / Medical</option>
        <option>Finance / Accounting</option>
        <option>Technology / SaaS</option>
        <option>Retail / E-commerce</option>
        <option>Consulting</option>
        <option>Other</option>
      </select>
    </div>
    <div class="field"><label>Number of employees (including yourself)</label>
      <select id="employees">
        <option value="1">Just me</option>
        <option value="2">2</option>
        <option value="3">3–5</option>
        <option value="8">6–10</option>
        <option value="15">11–20</option>
        <option value="30">21–50</option>
        <option value="75">51–100</option>
        <option value="150">100+</option>
      </select>
    </div>
    <div class="field"><label>Approximate annual revenue</label>
      <select id="annual_revenue">
        <option value="0">Under $250K</option>
        <option value="400000">$250K – $500K</option>
        <option value="750000">$500K – $1M</option>
        <option value="2000000">$1M – $3M</option>
        <option value="6000000">$3M – $10M</option>
        <option value="15000000">$10M+</option>
      </select>
    </div>
    <button class="btn" onclick="next(2)">Continue →</button>
    <button class="btn btn-back" onclick="back(2)">← Back</button>
  </div>

  <!-- STEP 3: Roles & Pain -->
  <div class="step" id="step3">
    <div class="step-label">Step 3 of 5</div>
    <h2>What hats do you wear?</h2>
    <p class="sub">List your actual job titles — even if one person does all of them. Murphy builds a shadow agent for each role.</p>
    <div class="field">
      <label>Your roles (one per line)</label>
      <textarea id="roles" placeholder="Owner / Estimator&#10;Project Manager&#10;Office Admin&#10;Sales"></textarea>
    </div>
    <div class="field">
      <label>What do you spend the most time on each week?</label>
      <textarea id="daily_tasks" placeholder="Follow-ups on open quotes&#10;Scheduling jobs&#10;Invoicing&#10;Answering emails"></textarea>
    </div>
    <div class="field">
      <label>What would you most like to automate?</label>
      <div class="chip-group" id="automation_chips">
        <div class="chip" onclick="toggleChip(this)">Follow-up emails</div>
        <div class="chip" onclick="toggleChip(this)">Appointment booking</div>
        <div class="chip" onclick="toggleChip(this)">Invoicing</div>
        <div class="chip" onclick="toggleChip(this)">Lead qualification</div>
        <div class="chip" onclick="toggleChip(this)">Proposal generation</div>
        <div class="chip" onclick="toggleChip(this)">Contract sending</div>
        <div class="chip" onclick="toggleChip(this)">CRM updates</div>
        <div class="chip" onclick="toggleChip(this)">Scheduling</div>
        <div class="chip" onclick="toggleChip(this)">Job dispatch</div>
        <div class="chip" onclick="toggleChip(this)">Reporting</div>
      </div>
    </div>
    <button class="btn" onclick="next(3)">Continue →</button>
    <button class="btn btn-back" onclick="back(3)">← Back</button>
  </div>

  <!-- STEP 4: Tools & Hours -->
  <div class="step" id="step4">
    <div class="step-label">Step 4 of 5</div>
    <h2>Tools & automation window</h2>
    <p class="sub">Murphy needs to know what you already use and when it's safe to act autonomously.</p>
    <div class="field">
      <label>What tools do you currently use? (one per line)</label>
      <textarea id="current_tools" placeholder="QuickBooks&#10;Google Calendar&#10;Gmail&#10;ServiceTitan"></textarea>
    </div>
    <div class="field">
      <label>Your biggest pain right now (be specific)</label>
      <textarea id="biggest_pain" placeholder="I spend 3 hours a day on follow-ups and they still fall through the cracks"></textarea>
    </div>
    <div class="field">
      <label>Your growth goal</label>
      <input type="text" id="growth_goal" placeholder="Double revenue without hiring anyone new">
    </div>
    <div class="hours-row">
      <div class="field">
        <label>Automation start (Murphy works after)</label>
        <input type="time" id="auto_start" value="23:00">
      </div>
      <div class="field">
        <label>Automation end (Murphy stops before)</label>
        <input type="time" id="auto_end" value="06:00">
      </div>
    </div>
    <p style="font-size:13px;color:#6b7280;margin-top:-12px;margin-bottom:20px">Murphy only acts autonomously within this window. Outside of it, it observes and queues.</p>
    <button class="btn" onclick="submitSurvey()">See My Setup →</button>
    <button class="btn btn-back" onclick="back(4)">← Back</button>
  </div>

  <!-- STEP 5: Results -->
  <div class="step" id="step5">
    <div class="step-label">Your Murphy Setup</div>
    <h2 id="result_headline">Here's what Murphy will build for you</h2>
    <p class="sub" id="result_sub"></p>
    <div class="spinner" id="spinner">Building your setup...</div>
    <div id="result_body"></div>
  </div>

</div>

<script>
let currentStep = 1;
const totalSteps = 5;
let surveyResult = null;

function next(from) {
  if (from === 1) {
    if (!document.getElementById('email').value || !document.getElementById('contact_name').value) {
      showErr('err1','Name and email are required'); return;
    }
  }
  goTo(from + 1);
}
function back(from) { goTo(from - 1); }
function goTo(n) {
  document.getElementById('step' + currentStep).classList.remove('active');
  document.getElementById('step' + n).classList.add('active');
  currentStep = n;
  for (let i = 1; i <= totalSteps; i++) {
    document.getElementById('d' + i).classList.toggle('done', i <= n);
  }
  window.scrollTo(0,0);
}
function showErr(id, msg) {
  const el = document.getElementById(id);
  el.textContent = msg; el.style.display = 'block';
  setTimeout(() => { el.style.display = 'none'; }, 4000);
}
function toggleChip(el) { el.classList.toggle('selected'); }

async function submitSurvey() {
  goTo(5);
  document.getElementById('spinner').style.display = 'block';
  document.getElementById('result_body').innerHTML = '';

  const selectedChips = [...document.querySelectorAll('.chip.selected')].map(c => c.textContent);
  const roles = document.getElementById('roles').value.split('\\n').map(r=>r.trim()).filter(Boolean);
  const daily = document.getElementById('daily_tasks').value.split('\\n').map(r=>r.trim()).filter(Boolean);
  const tools = document.getElementById('current_tools').value.split('\\n').map(r=>r.trim()).filter(Boolean);

  const payload = {
    email: document.getElementById('email').value.trim(),
    contact_name: document.getElementById('contact_name').value.trim(),
    company_name: document.getElementById('company_name').value.trim(),
    phone: document.getElementById('phone').value.trim(),
    industry: document.getElementById('industry').value,
    employees: parseInt(document.getElementById('employees').value),
    annual_revenue: parseInt(document.getElementById('annual_revenue').value),
    roles: roles,
    daily_tasks: daily,
    wished_automated: selectedChips,
    current_tools: tools,
    biggest_pain: document.getElementById('biggest_pain').value.trim(),
    growth_goal: document.getElementById('growth_goal').value.trim(),
    automation_hours_start: document.getElementById('auto_start').value,
    automation_hours_end: document.getElementById('auto_end').value
  };

  try {
    const resp = await fetch('/api/oo/survey', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify(payload)
    });
    const data = await resp.json();
    surveyResult = data;
    renderResults(data, payload);
  } catch(e) {
    document.getElementById('spinner').style.display = 'none';
    document.getElementById('result_body').innerHTML = '<p style="color:#f87171">Something went wrong. Please try again.</p>';
  }
}

function renderResults(data, payload) {
  document.getElementById('spinner').style.display = 'none';

  const routingLabels = {
    nurture: {label:'Getting started', cls:'score-nurture', msg:'Murphy will send you onboarding resources and follow up in a few days.'},
    book: {label:'Ready to build', cls:'score-book', msg:'Great fit. Murphy will show you a booking link to get your setup started.'},
    enterprise: {label:'Enterprise fit', cls:'score-enterprise', msg:"You're exactly who Murphy was built for. Corey will reach out personally."}
  };
  const r = routingLabels[data.routing] || routingLabels['nurture'];

  let wfHtml = '';
  if (data.identified_workflows && data.identified_workflows.length) {
    wfHtml = data.identified_workflows.map(w =>
      `<div class="workflow-item"><div class="wf-dot"></div><div class="wf-text">${cap(w.keyword)} automation</div><div class="wf-module">${w.module}</div></div>`
    ).join('');
  }

  let orgHtml = '';
  if (data.org_chart_scaffold && data.org_chart_scaffold.nodes) {
    orgHtml = data.org_chart_scaffold.nodes.map(n =>
      `<div style="display:flex;align-items:center;gap:10px;padding:8px 0;border-bottom:1px solid #1e2535">
        <div style="width:8px;height:8px;background:#6366f1;border-radius:50%;flex-shrink:0"></div>
        <div style="font-size:14px;color:#d1d5db">${n.title}</div>
        <div style="font-size:12px;color:#6b7280;margin-left:auto">shadow agent</div>
      </div>`
    ).join('');
  }

  document.getElementById('result_headline').textContent = 'Here\'s what Murphy will build for you';
  document.getElementById('result_sub').textContent = data.message || '';

  document.getElementById('result_body').innerHTML = `
    <div class="result-card">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px">
        <h3>Lead Score</h3>
        <span class="score-badge ${r.cls}">${data.lead_score}/10 — ${r.label}</span>
      </div>
      <p>${r.msg}</p>
    </div>

    <div class="result-card">
      <h3 style="margin-bottom:12px">Org Chart Scaffold</h3>
      <p style="margin-bottom:12px;font-size:13px;color:#6b7280">Murphy creates a shadow agent for each of your roles. It watches what you do and learns your patterns.</p>
      ${orgHtml || '<p style="color:#6b7280;font-size:14px">No roles specified</p>'}
    </div>

    <div class="result-card">
      <h3 style="margin-bottom:12px">Identified Workflows</h3>
      <p style="margin-bottom:12px;font-size:13px;color:#6b7280">Murphy matched your needs to existing automation modules in the Murphy system.</p>
      ${wfHtml || '<p style="color:#6b7280;font-size:14px">No workflows mapped</p>'}
    </div>

    <div class="result-card">
      <h3 style="margin-bottom:6px">Automation Hours</h3>
      <p>${data.automation_hours ? data.automation_hours.description : 'Murphy will run autonomously during your configured window'}</p>
    </div>

    <div style="background:linear-gradient(135deg,#1e3a5f,#1a1a2e);border:1px solid #3b82f6;border-radius:12px;padding:24px;margin-top:8px;text-align:center">
      <div style="font-size:20px;font-weight:700;color:#fff;margin-bottom:6px">$100 / month</div>
      <div style="color:#9ca3af;font-size:14px;margin-bottom:20px">Everything above — running autonomously, reporting to you</div>
      <button class="btn" style="max-width:300px;margin:0 auto" onclick="startCheckout('${data.account_id}')">Start My Setup →</button>
      <div style="font-size:12px;color:#6b7280;margin-top:12px">Cancel anytime. Murphy Client downloads after payment.</div>
    </div>
  `;
}

function cap(s) { return s.charAt(0).toUpperCase() + s.slice(1); }

async function startCheckout(accountId) {
  try {
    const resp = await fetch('/api/stripe/checkout', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({account_id: accountId})
    });
    const data = await resp.json();
    if (data.checkout_url) {
      window.location.href = data.checkout_url;
    } else {
      alert('Unable to start checkout. Please email corey@murphy.systems');
    }
  } catch(e) {
    alert('Checkout unavailable. Please email corey@murphy.systems');
  }
}
</script>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────────────
# GET /dashboard  — Owner dashboard
# ─────────────────────────────────────────────────────────────────────────────

DASHBOARD_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Murphy — Dashboard</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0a0a0a;color:#e8e8e8;min-height:100vh}
  nav{background:#111827;border-bottom:1px solid #1e2535;padding:0 24px;display:flex;align-items:center;height:56px;justify-content:space-between}
  .logo{font-size:20px;font-weight:800;color:#fff}.logo span{color:#3b82f6}
  .nav-right{display:flex;align-items:center;gap:16px;font-size:14px;color:#9ca3af}
  .status-dot{width:8px;height:8px;border-radius:50%;display:inline-block;margin-right:6px}
  .dot-green{background:#22c55e}.dot-yellow{background:#eab308}.dot-red{background:#ef4444}
  .main{max-width:1100px;margin:0 auto;padding:32px 20px}
  .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:16px;margin-bottom:24px}
  .card{background:#111827;border:1px solid #1e2535;border-radius:12px;padding:20px}
  .card h3{font-size:13px;color:#6b7280;text-transform:uppercase;letter-spacing:.5px;margin-bottom:12px}
  .big-num{font-size:36px;font-weight:700;color:#fff}
  .big-label{font-size:13px;color:#6b7280;margin-top:4px}
  .section{margin-bottom:32px}
  .section-title{font-size:16px;font-weight:600;color:#fff;margin-bottom:16px;display:flex;align-items:center;gap:8px}
  table{width:100%;border-collapse:collapse}
  th{text-align:left;font-size:12px;color:#6b7280;text-transform:uppercase;letter-spacing:.5px;padding:8px 12px;border-bottom:1px solid #1e2535}
  td{padding:12px;border-bottom:1px solid #1e2535;font-size:14px;color:#d1d5db;vertical-align:top}
  tr:last-child td{border-bottom:none}
  .badge{display:inline-block;padding:3px 10px;border-radius:20px;font-size:12px;font-weight:500}
  .badge-green{background:#14532d;color:#4ade80}
  .badge-yellow{background:#422006;color:#fbbf24}
  .badge-blue{background:#1e3a5f;color:#60a5fa}
  .badge-purple{background:#2d1a3a;color:#c084fc}
  .badge-gray{background:#1e2535;color:#9ca3af}
  .approve-btn{padding:6px 14px;background:#22c55e;color:#fff;border:none;border-radius:6px;font-size:13px;cursor:pointer;margin-right:6px}
  .reject-btn{padding:6px 14px;background:#ef4444;color:#fff;border:none;border-radius:6px;font-size:13px;cursor:pointer}
  .clock-bar{background:#111827;border:1px solid #3b82f6;border-radius:12px;padding:16px 20px;margin-bottom:24px;display:flex;align-items:center;justify-content:space-between}
  .clock-label{font-size:14px;color:#9ca3af}
  .clock-days{font-size:28px;font-weight:700;color:#60a5fa}
  .pattern-bar{height:6px;background:#1e2535;border-radius:3px;overflow:hidden;margin-top:6px}
  .pattern-fill{height:100%;background:#3b82f6;border-radius:3px;transition:width .5s}
  #account-id-input{background:#111827;border:1px solid #1e2535;border-radius:6px;padding:8px 12px;color:#e8e8e8;font-size:14px;width:300px;outline:none}
  .load-btn{padding:8px 16px;background:#3b82f6;color:#fff;border:none;border-radius:6px;font-size:14px;cursor:pointer;margin-left:8px}
  .empty{color:#6b7280;font-size:14px;padding:20px;text-align:center}
  .weekly-rec{background:#1e2535;border-radius:8px;padding:12px;font-size:14px;color:#d1d5db;margin-bottom:8px}
</style>
</head>
<body>
<nav>
  <div class="logo">murphy<span>.</span>systems</div>
  <div class="nav-right">
    <span><span class="status-dot dot-green"></span>System active</span>
  </div>
</nav>

<div class="main">
  <div style="margin-bottom:24px;display:flex;align-items:center;gap:12px">
    <input type="text" id="account-id-input" placeholder="Enter your Account ID">
    <button class="load-btn" onclick="loadDashboard()">Load Dashboard</button>
  </div>

  <div id="dashboard-content" style="display:none">

    <!-- Backlog clock -->
    <div class="clock-bar" id="clock-bar" style="display:none">
      <div>
        <div class="clock-label">Work backlog activates in</div>
        <div class="clock-days" id="clock-days">—</div>
        <div class="clock-label" id="clock-date"></div>
      </div>
      <div style="font-size:13px;color:#6b7280;max-width:300px;text-align:right">
        6 months from your first signed contract.<br>
        Requires 60% of contract paid.
      </div>
    </div>

    <!-- KPI cards -->
    <div class="grid" id="kpi-grid"></div>

    <!-- HITL queue -->
    <div class="section">
      <div class="section-title">⚡ Pending Approvals (HITL)</div>
      <div class="card" id="hitl-table-wrap">
        <div class="empty">Loading...</div>
      </div>
    </div>

    <!-- Shadow patterns -->
    <div class="section">
      <div class="section-title">🧠 Shadow Agent — Learned Patterns</div>
      <div class="card" id="patterns-wrap">
        <div class="empty">Loading...</div>
      </div>
    </div>

    <!-- Work backlog -->
    <div class="section">
      <div class="section-title">📋 Work Backlog</div>
      <div class="card" id="backlog-wrap">
        <div class="empty">Loading...</div>
      </div>
    </div>

    <!-- Contracts -->
    <div class="section">
      <div class="section-title">📄 Contracts</div>
      <div class="card" id="contracts-wrap">
        <div class="empty">Loading...</div>
      </div>
    </div>

    <!-- Weekly metrics -->
    <div class="section">
      <div class="section-title">📊 Weekly Report</div>
      <div class="card" id="metrics-wrap">
        <div class="empty">Loading...</div>
      </div>
    </div>

  </div>
</div>

<script>
let currentAccountId = '';

// Auto-load from URL param
const urlParams = new URLSearchParams(window.location.search);
if (urlParams.get('id')) {
  document.getElementById('account-id-input').value = urlParams.get('id');
  setTimeout(loadDashboard, 100);
}

async function loadDashboard() {
  const aid = document.getElementById('account-id-input').value.trim();
  if (!aid) return;
  currentAccountId = aid;
  document.getElementById('dashboard-content').style.display = 'block';

  try {
    const [dash, weekly] = await Promise.all([
      fetch('/api/oo/dashboard/' + aid).then(r=>r.json()),
      fetch('/api/oo/metrics/weekly/' + aid).then(r=>r.json())
    ]);
    renderDashboard(dash, weekly);
  } catch(e) {
    document.getElementById('dashboard-content').innerHTML = '<p style="color:#f87171;padding:20px">Failed to load. Check your Account ID.</p>';
  }
}

function renderDashboard(d, weekly) {
  // Backlog clock
  if (d.backlog && d.backlog.clock) {
    const clk = d.backlog.clock;
    document.getElementById('clock-bar').style.display = 'flex';
    document.getElementById('clock-days').textContent = clk.days_remaining + ' days';
    document.getElementById('clock-date').textContent = 'Activation: ' + clk.activation_date;
  }

  // KPIs
  const kpis = [
    {label:'Account Status', val: badge(d.account.status), sub:''},
    {label:'Shadow Patterns', val: d.shadow_agent.patterns_learned, sub:'learned behaviors'},
    {label:'HITL Pending', val: d.hitl_queue.pending, sub:'awaiting your approval'},
    {label:'Backlog Items', val: d.backlog.total, sub: d.backlog.queued+' queued, '+d.backlog.active+' active'},
  ];
  document.getElementById('kpi-grid').innerHTML = kpis.map(k=>`
    <div class="card">
      <h3>${k.label}</h3>
      <div class="big-num">${k.val}</div>
      <div class="big-label">${k.sub}</div>
    </div>
  `).join('');

  // HITL table
  if (d.hitl_queue.items && d.hitl_queue.items.length) {
    document.getElementById('hitl-table-wrap').innerHTML = `
      <table>
        <tr><th>Action</th><th>Description</th><th>Created</th><th>Respond</th></tr>
        ${d.hitl_queue.items.map(h=>`
          <tr>
            <td><span class="badge badge-yellow">${h.action}</span></td>
            <td>${h.description}</td>
            <td style="color:#6b7280;font-size:12px">${h.created ? h.created.substring(0,16) : ''}</td>
            <td>
              <button class="approve-btn" onclick="respond('${h.id}','approve')">✓ Approve</button>
              <button class="reject-btn" onclick="respond('${h.id}','reject')">✗ Reject</button>
            </td>
          </tr>`).join('')}
      </table>`;
  } else {
    document.getElementById('hitl-table-wrap').innerHTML = '<div class="empty">No pending approvals — Murphy is running clean ✓</div>';
  }

  // Patterns
  if (d.shadow_agent.top_patterns && d.shadow_agent.top_patterns.length) {
    document.getElementById('patterns-wrap').innerHTML = d.shadow_agent.top_patterns.map(p=>`
      <div style="margin-bottom:16px">
        <div style="display:flex;justify-content:space-between;margin-bottom:4px">
          <span style="font-size:14px;color:#d1d5db">${p.type}</span>
          <span style="font-size:13px;color:#60a5fa">${p.confidence} confidence</span>
        </div>
        <div class="pattern-bar"><div class="pattern-fill" style="width:${p.confidence}"></div></div>
        <div style="font-size:12px;color:#6b7280;margin-top:4px">${p.observations} observations · ${p.approved?'<span style=color:#4ade80>automation approved</span>':p.proposed?'<span style=color:#fbbf24>proposal pending</span>':'observing'}</div>
      </div>`).join('');
  } else {
    document.getElementById('patterns-wrap').innerHTML = '<div class="empty">Shadow agent is observing — patterns will appear as you use the system</div>';
  }

  // Backlog
  if (d.backlog.items && d.backlog.items.length) {
    document.getElementById('backlog-wrap').innerHTML = `
      <table>
        <tr><th>Task</th><th>Phase</th><th>Priority</th><th>Status</th><th>Activates</th></tr>
        ${d.backlog.items.map(b=>`
          <tr>
            <td>${b.task}</td>
            <td><span class="badge badge-blue">${b.phase}</span></td>
            <td>${'★'.repeat(4-Math.min(3,b.priority))}</td>
            <td>${statusBadge(b.status)}</td>
            <td style="font-size:12px;color:#6b7280">${b.activates||'—'}</td>
          </tr>`).join('')}
      </table>`;
  } else {
    document.getElementById('backlog-wrap').innerHTML = '<div class="empty">Backlog will populate after contract is signed and 60% paid</div>';
  }

  // Contracts
  if (d.contracts && d.contracts.length) {
    document.getElementById('contracts-wrap').innerHTML = `
      <table>
        <tr><th>Value</th><th>Paid</th><th>Status</th><th>Signed</th><th>Backlog Activates</th></tr>
        ${d.contracts.map(c=>`
          <tr>
            <td>$${(c.value||0).toLocaleString()}</td>
            <td>${(c.payment_pct||0).toFixed(1)}%</td>
            <td>${statusBadge(c.status)}</td>
            <td style="font-size:12px;color:#6b7280">${c.signed_date||'—'}</td>
            <td style="font-size:12px;color:#60a5fa">${c.backlog_activates||'—'}</td>
          </tr>`).join('')}
      </table>`;
  } else {
    document.getElementById('contracts-wrap').innerHTML = '<div class="empty">No contracts yet</div>';
  }

  // Weekly metrics
  if (weekly) {
    const healthColor = {green:'#4ade80',yellow:'#fbbf24',red:'#f87171'}[weekly.health] || '#9ca3af';
    document.getElementById('metrics-wrap').innerHTML = `
      <div style="display:flex;gap:24px;margin-bottom:20px;flex-wrap:wrap">
        <div><div style="font-size:24px;font-weight:700;color:#fff">${weekly.shadow_learning.observations}</div><div style="font-size:12px;color:#6b7280">observations this week</div></div>
        <div><div style="font-size:24px;font-weight:700;color:#fff">${weekly.shadow_learning.automations_approved}</div><div style="font-size:12px;color:#6b7280">automations approved</div></div>
        <div><div style="font-size:24px;font-weight:700;color:#fff">${weekly.hitl_activity.total_resolved}</div><div style="font-size:12px;color:#6b7280">HITL resolved</div></div>
        <div><div style="font-size:24px;font-weight:700;color:${healthColor}">${weekly.health.toUpperCase()}</div><div style="font-size:12px;color:#6b7280">system health</div></div>
      </div>
      ${(weekly.recommendations||[]).map(r=>`<div class="weekly-rec">${r}</div>`).join('')}
    `;
  }
}

function badge(status) {
  const map = {lead:'badge-gray',demo_booked:'badge-yellow',proposal_sent:'badge-blue',contract_signed:'badge-blue',active:'badge-green',nurture:'badge-gray',book:'badge-blue',enterprise:'badge-purple'};
  return `<span class="badge ${map[status]||'badge-gray'}">${status||'—'}</span>`;
}
function statusBadge(s) {
  const map = {pending:'badge-gray',queued:'badge-yellow',active:'badge-blue',completed:'badge-green',draft:'badge-gray',sent:'badge-yellow',signed:'badge-blue',churned:'badge-gray'};
  return `<span class="badge ${map[s]||'badge-gray'}">${s||'—'}</span>`;
}

async function respond(hitlId, response) {
  const r = await fetch('/api/oo/hitl/respond', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({hitl_id:hitlId,response:response})
  });
  if (r.ok) loadDashboard();
}
</script>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────────────
# GET /hitl/{id}/approve|reject — One-click HITL response pages
# ─────────────────────────────────────────────────────────────────────────────

HITL_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Murphy — Action Response</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,sans-serif;background:#0a0a0a;color:#e8e8e8;min-height:100vh;display:flex;align-items:center;justify-content:center}}
.card{{background:#111827;border:1px solid #1e2535;border-radius:16px;padding:40px;max-width:480px;width:90%;text-align:center}}
.icon{{font-size:48px;margin-bottom:16px}}
h1{{font-size:22px;font-weight:700;color:#fff;margin-bottom:8px}}
p{{color:#9ca3af;font-size:15px;line-height:1.5;margin-bottom:24px}}
.btn{{display:inline-block;padding:12px 32px;border-radius:8px;font-size:16px;font-weight:600;border:none;cursor:pointer;text-decoration:none}}
.btn-approve{{background:#22c55e;color:#fff}}
.btn-reject{{background:#ef4444;color:#fff}}
.result{{padding:20px;border-radius:8px;font-size:15px;margin-top:16px}}
.result-ok{{background:#14532d;color:#4ade80}}
.result-err{{background:#7f1d1d;color:#f87171}}
</style>
</head>
<body>
<div class="card">
  <div class="icon">{icon}</div>
  <h1>{title}</h1>
  <p>{desc}</p>
  <button class="btn btn-{cls}" id="btn" onclick="doIt()">
    {btn_label}
  </button>
  <div id="result"></div>
</div>
<script>
async function doIt() {{
  document.getElementById('btn').disabled = true;
  document.getElementById('btn').textContent = 'Processing...';
  try {{
    const r = await fetch('/api/oo/hitl/respond', {{
      method:'POST',
      headers:{{'Content-Type':'application/json'}},
      body:JSON.stringify({{hitl_id:'{hitl_id}',response:'{response}'}})
    }});
    const data = await r.json();
    document.getElementById('result').innerHTML =
      '<div class="result result-ok">Done — {done_msg}</div>';
    document.getElementById('btn').style.display = 'none';
  }} catch(e) {{
    document.getElementById('result').innerHTML =
      '<div class="result result-err">Something went wrong. Try again.</div>';
    document.getElementById('btn').disabled = false;
    document.getElementById('btn').textContent = '{btn_label}';
  }}
}}
</script>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────────────
# GET /download  — Gated download page (active subscribers only)
# ─────────────────────────────────────────────────────────────────────────────

DOWNLOAD_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Murphy — Download</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,sans-serif;background:#0a0a0a;color:#e8e8e8;min-height:100vh}}
.hero{{background:#111827;border-bottom:1px solid #1e2535;padding:40px 20px;text-align:center}}
.logo{{font-size:28px;font-weight:800;color:#fff}}.logo span{{color:#3b82f6}}
.sub{{color:#9ca3af;margin-top:8px}}
.container{{max-width:640px;margin:0 auto;padding:40px 20px}}
.gated{{background:#111827;border:1px solid #1e2535;border-radius:12px;padding:32px;text-align:center}}
h2{{font-size:20px;font-weight:700;margin-bottom:8px}}
p{{color:#9ca3af;font-size:15px;margin-bottom:20px;line-height:1.5}}
input{{width:100%;padding:12px;background:#0a0a0a;border:1px solid #1e2535;border-radius:8px;color:#e8e8e8;font-size:15px;outline:none;margin-bottom:12px}}
input:focus{{border-color:#3b82f6}}
.btn{{width:100%;padding:13px;background:#3b82f6;color:#fff;border:none;border-radius:8px;font-size:16px;font-weight:600;cursor:pointer}}
.download-card{{background:#111827;border:1px solid #22c55e;border-radius:12px;padding:24px;margin-bottom:16px}}
.download-card h3{{font-size:16px;font-weight:600;color:#fff;margin-bottom:8px}}
.download-card p{{color:#9ca3af;font-size:14px;margin-bottom:16px}}
.dl-btn{{display:inline-block;padding:10px 24px;background:#22c55e;color:#fff;border-radius:8px;font-size:14px;font-weight:600;text-decoration:none;margin-right:8px;cursor:pointer}}
.dl-btn.win{{background:#3b82f6}}.dl-btn.linux{{background:#6366f1}}
.install-code{{background:#0a0a0a;border:1px solid #1e2535;border-radius:6px;padding:12px;font-family:monospace;font-size:13px;color:#4ade80;margin-top:12px;white-space:pre-wrap}}
.err{{color:#f87171;font-size:14px;padding:8px 0}}
</style>
</head>
<body>
<div class="hero">
  <div class="logo">murphy<span>.</span>systems</div>
  <div class="sub">Download the Murphy Client</div>
</div>
<div class="container">
  <div id="gate" class="gated">
    <h2>Enter your Account ID</h2>
    <p>After payment, your Account ID was emailed to you. You can also find it at murphy.systems/dashboard</p>
    <input type="text" id="acct-in" placeholder="e.g. a3b7c2d1-...">
    <div id="gate-err" class="err" style="display:none"></div>
    <button class="btn" onclick="checkAccess()">Get My Download</button>
  </div>

  <div id="download-section" style="display:none">
    <div style="margin-bottom:24px">
      <h2 style="font-size:22px;font-weight:700;margin-bottom:6px">You're all set</h2>
      <p>Download the Murphy Client for your platform. It runs as a background agent and phones home to murphy.systems.</p>
    </div>

    <div class="download-card">
      <h3>🍎 macOS</h3>
      <p>Runs as a launchd service. Watches your files and apps automatically.</p>
      <a class="dl-btn" id="dl-mac" href="#">Download .pkg</a>
      <div class="install-code" id="mac-install"># One-line install (paste in Terminal):
curl -s https://murphy.systems/install/mac | bash</div>
    </div>

    <div class="download-card">
      <h3>🪟 Windows</h3>
      <p>Runs as a Windows Service. Installs silently, starts on login.</p>
      <a class="dl-btn win" id="dl-win" href="#">Download .exe</a>
      <div class="install-code" id="win-install"># Run in PowerShell (as admin):
irm https://murphy.systems/install/windows | iex</div>
    </div>

    <div class="download-card">
      <h3>🐧 Linux / Server</h3>
      <p>Systemd service. Works on Ubuntu, Debian, CentOS, Alpine.</p>
      <a class="dl-btn linux" id="dl-linux" href="#">Download .sh</a>
      <div class="install-code" id="linux-install"># One-line install:
curl -s https://murphy.systems/install/linux | sudo bash</div>
    </div>

    <div style="background:#1e2535;border-radius:8px;padding:16px;margin-top:8px;font-size:14px;color:#9ca3af">
      <strong style="color:#fff">After install, run:</strong><br><br>
      <code style="color:#4ade80">murphy setup</code><br><br>
      Enter your Account ID and API key when prompted. Murphy will start observing immediately.
      Your automation window starts tonight.
    </div>

    <div style="margin-top:24px;text-align:center">
      <a href="/dashboard?id=__ACCT__" style="color:#3b82f6;font-size:14px">Go to Dashboard →</a>
    </div>
  </div>
</div>
<script>
async function checkAccess() {{
  const aid = document.getElementById('acct-in').value.trim();
  if (!aid) return;
  try {{
    const r = await fetch('/api/oo/dashboard/' + aid);
    if (r.ok) {{
      const d = await r.json();
      if (d.account && ['active','contract_signed','demo_booked'].includes(d.account.status)) {{
        document.getElementById('gate').style.display='none';
        document.getElementById('download-section').style.display='block';
        document.querySelectorAll('#download-section a, #download-section [id$=install]').forEach(el=>{{
          if(el.tagName==='A') el.href = el.href.replace('__ACCT__',aid);
        }});
        document.querySelector('[href="/dashboard?id=__ACCT__"]').href='/dashboard?id='+aid;
      }} else {{
        document.getElementById('gate-err').textContent = 'Account found but not yet activated. Complete payment first.';
        document.getElementById('gate-err').style.display='block';
      }}
    }} else {{
      document.getElementById('gate-err').textContent = 'Account not found. Check your Account ID.';
      document.getElementById('gate-err').style.display='block';
    }}
  }} catch(e) {{
    document.getElementById('gate-err').textContent = 'Error checking account. Try again.';
    document.getElementById('gate-err').style.display='block';
  }}
}}
</script>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────────────
# Stripe checkout + webhook
# ─────────────────────────────────────────────────────────────────────────────

def route_stripe_checkout():
    data = request.get_json() or {}
    account_id = data.get('account_id', '')
    if not account_id:
        return jsonify({"error": "account_id required"}), 400

    if not STRIPE_SECRET:
        return jsonify({"error": "Stripe not configured", "contact": "corey@murphy.systems"}), 503

    try:
        import stripe
        stripe.api_key = STRIPE_SECRET

        conn = sqlite3.connect(OO_DB)
        cur = conn.cursor()
        cur.execute("SELECT email, contact_name, company_name FROM owner_operator_accounts WHERE id=?",
                    (account_id,))
        sub = cur.fetchone()
        conn.close()

        if not sub:
            return jsonify({"error": "Account not found"}), 404

        email, name, company = sub

        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            mode='subscription',
            line_items=[{
                'price': STRIPE_PRICE_ID,
                'quantity': 1,
            }],
            customer_email=email,
            metadata={'account_id': account_id},
            success_url=f"https://murphy.systems/download?activated=1&id={account_id}",
            cancel_url="https://murphy.systems/start",
        )

        return jsonify({"checkout_url": session.url}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


def route_stripe_webhook():
    """Stripe calls this when subscription is activated."""
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get('Stripe-Signature', '')

    if not STRIPE_SECRET:
        return '', 200

    try:
        import stripe
        stripe.api_key = STRIPE_SECRET
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    if event['type'] in ('checkout.session.completed', 'customer.subscription.created'):
        obj = event['data']['object']
        account_id = obj.get('metadata', {}).get('account_id')
        if account_id:
            conn = sqlite3.connect(OO_DB)
            cur = conn.cursor()
            cur.execute("""
                UPDATE owner_operator_accounts
                SET status='active', activated_at=CURRENT_TIMESTAMP
                WHERE id=?
            """, (account_id,))
            conn.commit()
            conn.close()

    return '', 200


# ─────────────────────────────────────────────────────────────────────────────
# ROUTE REGISTRATION
# ─────────────────────────────────────────────────────────────────────────────

def register_saas_pages(app):
    """
    Call from production_router.py:
      from saas_pages import register_saas_pages
      register_saas_pages(app)
    """
    def start_page():
        return Response(START_PAGE, mimetype='text/html')

    def dashboard_page():
        return Response(DASHBOARD_PAGE, mimetype='text/html')

    def hitl_approve_page(hitl_id):
        html = HITL_PAGE.format(
            icon='✅', title='Approve this action',
            desc='Murphy is waiting for your go-ahead. Click below to approve.',
            cls='approve', btn_label='✓ Approve Action',
            hitl_id=hitl_id, response='approve',
            done_msg='Action approved. Murphy will execute during your automation window.'
        )
        return Response(html, mimetype='text/html')

    def hitl_reject_page(hitl_id):
        html = HITL_PAGE.format(
            icon='🚫', title='Reject this action',
            desc='Click below to reject. Murphy will not take this action.',
            cls='reject', btn_label='✗ Reject Action',
            hitl_id=hitl_id, response='reject',
            done_msg='Action rejected. Murphy will not proceed.'
        )
        return Response(html, mimetype='text/html')

    def download_page():
        return Response(DOWNLOAD_PAGE, mimetype='text/html')

    app.add_url_rule('/start',                   'oo_start_page',      start_page,          methods=['GET'])
    app.add_url_rule('/dashboard',               'oo_dashboard_page',  dashboard_page,      methods=['GET'])
    app.add_url_rule('/hitl/<hitl_id>/approve',  'oo_hitl_approve',    hitl_approve_page,   methods=['GET'])
    app.add_url_rule('/hitl/<hitl_id>/reject',   'oo_hitl_reject',     hitl_reject_page,    methods=['GET'])
    app.add_url_rule('/download',                'oo_download_page',   download_page,       methods=['GET'])
    app.add_url_rule('/api/stripe/checkout',     'stripe_checkout',    route_stripe_checkout, methods=['POST'])
    app.add_url_rule('/api/stripe/webhook',      'stripe_webhook',     route_stripe_webhook,  methods=['POST'])

    print("[PATCH-329b] SaaS pages registered: /start /dashboard /hitl /download + Stripe")
    return app
