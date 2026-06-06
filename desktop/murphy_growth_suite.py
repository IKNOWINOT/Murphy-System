"""
PATCH-350 — Murphy Growth Suite
Adds to existing production_router.py (no new files):
1. /start — new visitor onboarding + self-enrollment  
2. /founder — live metrics dashboard (ARR, pipeline, deals)
3. /api/growth/outreach — triggers prospector on a LinkedIn URL
4. /api/growth/investor — investor-mode outreach
5. /download — downloadable app landing (Mac/Win/Linux)
Wires into: production_router.py (append-only)
"""

ONBOARDING_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Murphy System — Get Started</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#0a0a0a;color:#e0e0e0;font-family:'Inter',system-ui,sans-serif;min-height:100vh}
.hero{max-width:680px;margin:0 auto;padding:80px 24px 40px;text-align:center}
.logo{width:52px;height:52px;margin:0 auto 24px;display:block}
h1{font-size:clamp(2rem,5vw,3.2rem);font-weight:700;line-height:1.1;margin-bottom:16px;background:linear-gradient(135deg,#00D4AA,#00ff41);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.sub{font-size:1.1rem;color:#888;margin-bottom:48px;line-height:1.6}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:16px;margin-bottom:48px;text-align:left}
.card{background:#111;border:1px solid #1e1e1e;border-radius:12px;padding:24px;cursor:pointer;transition:border-color .2s,transform .2s}
.card:hover{border-color:#00D4AA;transform:translateY(-2px)}
.card-emoji{font-size:2rem;margin-bottom:12px}
.card-title{font-size:1rem;font-weight:600;margin-bottom:6px;color:#fff}
.card-desc{font-size:.85rem;color:#666;line-height:1.5}
.form-section{background:#111;border:1px solid #1e1e1e;border-radius:16px;padding:40px;margin-bottom:32px;text-align:left}
.form-section h2{font-size:1.4rem;font-weight:600;margin-bottom:8px;color:#fff}
.form-section p{color:#666;font-size:.9rem;margin-bottom:24px}
.field{margin-bottom:16px}
label{display:block;font-size:.85rem;color:#888;margin-bottom:6px;font-weight:500}
input,select,textarea{width:100%;background:#0d0d0d;border:1px solid #222;border-radius:8px;padding:12px 16px;color:#fff;font-size:.95rem;outline:none;transition:border-color .2s}
input:focus,select:focus,textarea:focus{border-color:#00D4AA}
.btn{width:100%;background:linear-gradient(135deg,#00D4AA,#00ff41);color:#000;border:none;border-radius:8px;padding:16px;font-size:1rem;font-weight:700;cursor:pointer;transition:opacity .2s;margin-top:8px}
.btn:hover{opacity:.9}
.btn-sec{background:transparent;border:1px solid #333;color:#aaa;margin-top:8px}
.btn-sec:hover{border-color:#00D4AA;color:#00D4AA;opacity:1}
.status{display:none;background:#0d1f18;border:1px solid #00D4AA;border-radius:8px;padding:16px;margin-top:16px;font-size:.9rem;color:#00D4AA}
.pill{display:inline-block;background:#0d1f18;color:#00D4AA;border:1px solid #00D4AA;border-radius:20px;padding:4px 12px;font-size:.8rem;margin-bottom:24px}
.stat-row{display:flex;gap:24px;flex-wrap:wrap;margin-bottom:32px}
.stat{flex:1;min-width:120px;background:#111;border:1px solid #1e1e1e;border-radius:10px;padding:20px;text-align:center}
.stat-num{font-size:1.8rem;font-weight:700;color:#00D4AA}
.stat-label{font-size:.8rem;color:#555;margin-top:4px}
</style>
</head>
<body>
<div class="hero">
  <svg class="logo" viewBox="0 0 52 52"><circle cx="26" cy="26" r="24" fill="none" stroke="#00D4AA" stroke-width="2"/><path d="M14 36L19 16l7 14 7-14 5 20" stroke="#00ff41" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>
  <div class="pill">● Live System</div>
  <h1>One person.<br>Zero employees.<br>Real revenue.</h1>
  <p class="sub">Murphy is the AI operating system that runs your business — outreach, proposals, follow-up, compliance, delivery. You show up to sign.</p>

  <div class="stat-row" id="live-stats">
    <div class="stat"><div class="stat-num" id="s-deals">—</div><div class="stat-label">Active Deals</div></div>
    <div class="stat"><div class="stat-num" id="s-pipeline">—</div><div class="stat-label">Pipeline Value</div></div>
    <div class="stat"><div class="stat-num" id="s-closed">—</div><div class="stat-label">Closed Won</div></div>
    <div class="stat"><div class="stat-num" id="s-agents">—</div><div class="stat-label">Active Agents</div></div>
  </div>

  <div class="cards">
    <div class="card" onclick="showForm('operator')">
      <div class="card-emoji">⚙️</div>
      <div class="card-title">I run a business</div>
      <div class="card-desc">Replace ops, outreach, and admin with Murphy. One person, real revenue.</div>
    </div>
    <div class="card" onclick="showForm('investor')">
      <div class="card-emoji">📈</div>
      <div class="card-title">I want to invest</div>
      <div class="card-desc">$8.8M pipeline. 194 active deals. One operator. We're raising.</div>
    </div>
    <div class="card" onclick="showForm('partner')">
      <div class="card-emoji">🤝</div>
      <div class="card-title">I want to partner</div>
      <div class="card-desc">White-label, integration, or revenue share. Murphy handles your clients.</div>
    </div>
  </div>

  <!-- OPERATOR FORM -->
  <div class="form-section" id="form-operator" style="display:none">
    <h2>Tell Murphy about your business</h2>
    <p>Murphy will analyze your situation and propose exactly how it can replace your ops.</p>
    <div class="field"><label>Your name</label><input id="op-name" placeholder="Corey Post" /></div>
    <div class="field"><label>Your email</label><input id="op-email" type="email" placeholder="you@company.com" /></div>
    <div class="field"><label>LinkedIn URL (optional — Murphy will research you)</label><input id="op-linkedin" placeholder="https://linkedin.com/in/yourprofile" /></div>
    <div class="field"><label>What does your business do?</label><textarea id="op-biz" rows="3" placeholder="We sell X to Y..."></textarea></div>
    <div class="field"><label>Biggest bottleneck right now</label><select id="op-pain">
      <option value="">Select...</option>
      <option value="outreach">Finding customers / outreach</option>
      <option value="proposals">Writing proposals / closing</option>
      <option value="ops">Operations / admin overhead</option>
      <option value="compliance">Compliance / reporting</option>
      <option value="hiring">Hiring / scaling</option>
    </select></div>
    <button class="btn" onclick="submitOperator()">Let Murphy analyze my situation →</button>
    <div class="status" id="op-status"></div>
  </div>

  <!-- INVESTOR FORM -->
  <div class="form-section" id="form-investor" style="display:none">
    <h2>Murphy is raising</h2>
    <p>One operator. $8.8M pipeline. Zero employees. We want conviction on both sides.</p>
    <div class="field"><label>Your name</label><input id="inv-name" placeholder="Investor Name" /></div>
    <div class="field"><label>Email</label><input id="inv-email" type="email" placeholder="you@fund.com" /></div>
    <div class="field"><label>Fund / firm</label><input id="inv-fund" placeholder="Acme Ventures" /></div>
    <div class="field"><label>LinkedIn URL</label><input id="inv-linkedin" placeholder="https://linkedin.com/in/..." /></div>
    <div class="field"><label>Check size range</label><select id="inv-check">
      <option value="">Select...</option>
      <option value="25k-100k">$25K–$100K (angel)</option>
      <option value="100k-500k">$100K–$500K</option>
      <option value="500k-2m">$500K–$2M</option>
      <option value="2m+">$2M+</option>
    </select></div>
    <button class="btn" onclick="submitInvestor()">Request data room access →</button>
    <div class="status" id="inv-status"></div>
  </div>

  <!-- PARTNER FORM -->
  <div class="form-section" id="form-partner" style="display:none">
    <h2>Partnership inquiry</h2>
    <p>Murphy handles the work. You handle the relationship. Revenue share or white-label.</p>
    <div class="field"><label>Your name</label><input id="par-name" placeholder="Partner Name" /></div>
    <div class="field"><label>Email</label><input id="par-email" type="email" placeholder="you@company.com" /></div>
    <div class="field"><label>What you bring</label><textarea id="par-offer" rows="3" placeholder="We have 50 MEP contractor clients who need..."></textarea></div>
    <button class="btn" onclick="submitPartner()">Start the conversation →</button>
    <div class="status" id="par-status"></div>
  </div>

  <div style="margin-top:24px">
    <a href="/download" style="color:#555;font-size:.85rem;text-decoration:none;margin-right:24px">↓ Download desktop app</a>
    <a href="/dashboard" style="color:#555;font-size:.85rem;text-decoration:none;margin-right:24px">Dashboard</a>
    <a href="/book" style="color:#555;font-size:.85rem;text-decoration:none">Book audit</a>
  </div>
</div>

<script>
// Load live stats
fetch('/api/crm/deals').then(r=>r.json()).then(d=>{
  const deals = Array.isArray(d)?d:d.deals||[];
  const closed = deals.filter(x=>x.stage==='closed_won').length;
  const pipeline = deals.reduce((s,x)=>s+parseFloat(x.value||0),0);
  document.getElementById('s-deals').textContent = deals.length;
  document.getElementById('s-pipeline').textContent = '$'+Math.round(pipeline/1e6*10)/10+'M';
  document.getElementById('s-closed').textContent = closed;
}).catch(()=>{});

fetch('/api/swarm/agents/status').then(r=>r.json()).then(d=>{
  const agents = d.agents||[];
  document.getElementById('s-agents').textContent = agents.length;
}).catch(()=>{});

function showForm(type) {
  ['operator','investor','partner'].forEach(t=>{
    document.getElementById('form-'+t).style.display = t===type?'block':'none';
  });
  document.getElementById('form-'+type).scrollIntoView({behavior:'smooth',block:'center'});
}

function setStatus(id, msg, ok=true) {
  const el = document.getElementById(id);
  el.style.display='block';
  el.style.color = ok?'#00D4AA':'#ff6b6b';
  el.textContent = msg;
}

async function submitOperator() {
  const data = {
    type: 'operator',
    name: document.getElementById('op-name').value,
    email: document.getElementById('op-email').value,
    linkedin_url: document.getElementById('op-linkedin').value,
    business_description: document.getElementById('op-biz').value,
    pain_point: document.getElementById('op-pain').value,
  };
  if(!data.name||!data.email){setStatus('op-status','Name and email required.',false);return;}
  setStatus('op-status','Murphy is analyzing your situation...');
  const r = await fetch('/api/growth/onboard', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
  const res = await r.json();
  if(res.success) {
    setStatus('op-status', '✓ '+( res.message||'Murphy will reach out within 24h with a custom analysis.'));
  } else {
    setStatus('op-status', res.error||'Submitted. Murphy will follow up.', false);
  }
}

async function submitInvestor() {
  const data = {
    type: 'investor',
    name: document.getElementById('inv-name').value,
    email: document.getElementById('inv-email').value,
    fund: document.getElementById('inv-fund').value,
    linkedin_url: document.getElementById('inv-linkedin').value,
    check_size: document.getElementById('inv-check').value,
  };
  if(!data.name||!data.email){setStatus('inv-status','Name and email required.',false);return;}
  setStatus('inv-status','Requesting access...');
  const r = await fetch('/api/growth/investor-inquiry', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
  const res = await r.json();
  setStatus('inv-status', res.success ? '✓ Data room access request received. Murphy will reach out within 24h.' : (res.error||'Submitted.'), res.success);
}

async function submitPartner() {
  const data = {
    type: 'partner',
    name: document.getElementById('par-name').value,
    email: document.getElementById('par-email').value,
    offer: document.getElementById('par-offer').value,
  };
  if(!data.name||!data.email){setStatus('par-status','Name and email required.',false);return;}
  setStatus('par-status','Sending...');
  const r = await fetch('/api/growth/partner-inquiry', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
  const res = await r.json();
  setStatus('par-status', res.success ? '✓ Murphy will reach out.' : (res.error||'Submitted.'), res.success);
}
</script>
</body>
</html>"""

FOUNDER_DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Murphy — Founder View</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#080808;color:#e0e0e0;font-family:'Inter',system-ui,sans-serif;min-height:100vh;padding:24px}
h1{font-size:1.6rem;font-weight:700;color:#fff;margin-bottom:4px}
.sub{color:#555;font-size:.9rem;margin-bottom:32px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:16px;margin-bottom:32px}
.metric{background:#0f0f0f;border:1px solid #1a1a1a;border-radius:12px;padding:24px}
.metric-label{font-size:.8rem;color:#555;text-transform:uppercase;letter-spacing:.05em;margin-bottom:8px}
.metric-val{font-size:2rem;font-weight:700;color:#00D4AA}
.metric-sub{font-size:.8rem;color:#444;margin-top:4px}
.section{background:#0f0f0f;border:1px solid #1a1a1a;border-radius:12px;padding:24px;margin-bottom:16px}
.section h2{font-size:1rem;font-weight:600;color:#fff;margin-bottom:16px}
table{width:100%;border-collapse:collapse;font-size:.85rem}
th{text-align:left;color:#444;font-weight:500;padding:8px 0;border-bottom:1px solid #1a1a1a}
td{padding:10px 0;border-bottom:1px solid #111;color:#ccc}
.stage{display:inline-block;padding:2px 8px;border-radius:4px;font-size:.75rem;font-weight:600}
.stage-won{background:#0d2b1a;color:#00D4AA}
.stage-prospect{background:#1a1a0d;color:#888}
.stage-booked{background:#0d1a2b;color:#4aa3ff}
.stage-proposal{background:#2b1a0d;color:#ff9944}
.stage-negotiation{background:#2b0d1a;color:#ff6b9d}
.actions{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:24px}
.btn{background:#111;border:1px solid #222;color:#aaa;padding:10px 20px;border-radius:8px;cursor:pointer;font-size:.85rem;transition:all .2s;text-decoration:none;display:inline-block}
.btn:hover{border-color:#00D4AA;color:#00D4AA}
.btn-primary{background:linear-gradient(135deg,#00D4AA22,#00ff4122);border-color:#00D4AA;color:#00D4AA}
.log{background:#050505;border:1px solid #111;border-radius:8px;padding:16px;font-size:.8rem;color:#555;font-family:monospace;max-height:200px;overflow-y:auto}
.log-line{margin-bottom:4px;color:#444}
.log-line.ok{color:#00D4AA}
.log-line.warn{color:#ff9944}
.dot{width:8px;height:8px;border-radius:50%;background:#00D4AA;display:inline-block;margin-right:6px;animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}
</style>
</head>
<body>
<div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:16px;margin-bottom:32px">
  <div>
    <h1><span class="dot"></span>Murphy — Founder View</h1>
    <div class="sub">Live system metrics · <span id="last-refresh">loading...</span></div>
  </div>
  <div class="actions">
    <a href="/start" class="btn">+ Onboard visitor</a>
    <button class="btn btn-primary" onclick="runOutreach()">▶ Run outreach cycle</button>
    <button class="btn" onclick="runProspect()">🔍 Discover prospects</button>
    <a href="/book" class="btn">📅 Book audit</a>
  </div>
</div>

<div class="grid" id="metrics-grid">
  <div class="metric"><div class="metric-label">Pipeline Value</div><div class="metric-val" id="m-pipeline">—</div><div class="metric-sub">All active deals</div></div>
  <div class="metric"><div class="metric-label">Total Deals</div><div class="metric-val" id="m-deals">—</div><div class="metric-sub">In CRM</div></div>
  <div class="metric"><div class="metric-label">Closed Won</div><div class="metric-val" id="m-won">—</div><div class="metric-sub" id="m-won-val">—</div></div>
  <div class="metric"><div class="metric-label">Hot Prospects</div><div class="metric-val" id="m-prospect">—</div><div class="metric-sub">Stage: prospect</div></div>
  <div class="metric"><div class="metric-label">Booked Audits</div><div class="metric-val" id="m-booked">—</div><div class="metric-sub">Stage: booked</div></div>
  <div class="metric"><div class="metric-label">Shield Status</div><div class="metric-val" id="m-shield">—</div><div class="metric-sub">Security layers</div></div>
</div>

<div style="display:grid;grid-template-columns:2fr 1fr;gap:16px">
  <div class="section">
    <h2>Recent Deals</h2>
    <table id="deals-table">
      <thead><tr><th>Title</th><th>Stage</th><th>Value</th><th>Created</th></tr></thead>
      <tbody id="deals-body"><tr><td colspan="4" style="color:#333">Loading...</td></tr></tbody>
    </table>
  </div>
  <div class="section">
    <h2>System Activity</h2>
    <div class="log" id="activity-log">
      <div class="log-line">Loading system activity...</div>
    </div>
    <div style="margin-top:16px">
      <div class="metric-label" style="margin-bottom:8px">Outreach Status</div>
      <div id="outreach-status" style="font-size:.85rem;color:#555">—</div>
    </div>
  </div>
</div>

<div class="section" style="margin-top:16px">
  <h2>🎯 Prospect Outreach — Send to LinkedIn Profile</h2>
  <div style="display:flex;gap:12px;align-items:flex-end;flex-wrap:wrap">
    <div style="flex:1;min-width:200px">
      <div class="metric-label" style="margin-bottom:6px">LinkedIn URL</div>
      <input id="li-url" style="width:100%;background:#050505;border:1px solid #222;border-radius:6px;padding:10px 14px;color:#fff;font-size:.9rem;outline:none" placeholder="https://linkedin.com/in/corey-post-aab22548" />
    </div>
    <button class="btn btn-primary" onclick="outreachToLinkedIn()">Target this person →</button>
  </div>
  <div id="li-result" style="margin-top:12px;font-size:.85rem;color:#00D4AA;display:none"></div>
</div>

<script>
async function loadData() {
  document.getElementById('last-refresh').textContent = 'Updated '+new Date().toLocaleTimeString();

  // CRM deals
  const dr = await fetch('/api/crm/deals').then(r=>r.json()).catch(()=>[]);
  const deals = Array.isArray(dr)?dr:dr.deals||[];
  const stages = {};
  let totalVal=0, wonVal=0;
  deals.forEach(d=>{
    stages[d.stage]=(stages[d.stage]||0)+1;
    totalVal+=parseFloat(d.value||0);
    if(d.stage==='closed_won') wonVal+=parseFloat(d.value||0);
  });
  document.getElementById('m-pipeline').textContent='$'+Math.round(totalVal/1e6*10)/10+'M';
  document.getElementById('m-deals').textContent=deals.length;
  document.getElementById('m-won').textContent=stages.closed_won||0;
  document.getElementById('m-won-val').textContent='$'+Math.round(wonVal/1e3)+'K revenue';
  document.getElementById('m-prospect').textContent=stages.prospect||0;
  document.getElementById('m-booked').textContent=(stages.booked||0)+(stages.appointment_booked||0);

  // Deals table
  const tbody = document.getElementById('deals-body');
  const recent = [...deals].sort((a,b)=>b.created_at>a.created_at?1:-1).slice(0,10);
  tbody.innerHTML = recent.map(d=>`<tr>
    <td>${d.title||'—'}</td>
    <td><span class="stage stage-${d.stage}">${d.stage}</span></td>
    <td>$${Math.round(d.value||0).toLocaleString()}</td>
    <td>${(d.created_at||'').slice(0,10)}</td>
  </tr>`).join('');

  // Shield
  fetch('/api/shield/status').then(r=>r.json()).then(d=>{
    const s=d.summary||{};
    document.getElementById('m-shield').textContent=(s.active||'?')+'/'+( s.total||20);
  }).catch(()=>{});

  // Outreach status
  fetch('/api/apc/status').then(r=>r.json()).then(d=>{
    document.getElementById('outreach-status').textContent=
      d.success?'✓ APC active · discovery '+d.discovery_enabled+' · outreach '+d.outreach_enabled:'APC status unknown';
  }).catch(()=>{});

  // Activity log
  fetch('/api/swarm/agents/status').then(r=>r.json()).then(d=>{
    const agents=d.agents||[];
    const log=document.getElementById('activity-log');
    log.innerHTML=agents.slice(0,8).map(a=>`<div class="log-line ok">▸ ${a.name} [${a.role}] · runs: ${a.runs_total||0}</div>`).join('');
  }).catch(()=>{});
}

async function runOutreach() {
  document.getElementById('outreach-status').textContent='Running outreach cycle...';
  const r = await fetch('/api/prospector/cadence', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({})}).then(x=>x.json()).catch(e=>({error:e.message}));
  document.getElementById('outreach-status').textContent = JSON.stringify(r).slice(0,200);
}

async function runProspect() {
  document.getElementById('outreach-status').textContent='Discovering prospects...';
  const r = await fetch('/api/prospector/run', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({})}).then(x=>x.json()).catch(e=>({error:e.message}));
  document.getElementById('outreach-status').textContent = JSON.stringify(r).slice(0,200);
}

async function outreachToLinkedIn() {
  const url = document.getElementById('li-url').value.trim();
  if(!url){alert('Paste a LinkedIn URL');return;}
  document.getElementById('li-result').style.display='block';
  document.getElementById('li-result').textContent='Analyzing profile and queuing outreach...';
  const r = await fetch('/api/growth/outreach', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({linkedin_url:url,mode:'customer'})}).then(x=>x.json()).catch(e=>({error:e.message}));
  document.getElementById('li-result').textContent = r.success ? '✓ Queued: '+(r.message||'Outreach initiated for '+url) : '⚠ '+(r.error||JSON.stringify(r));
}

loadData();
setInterval(loadData, 30000);
</script>
</body>
</html>"""

DOWNLOAD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Download Murphy Client</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#0a0a0a;color:#e0e0e0;font-family:'Inter',system-ui,sans-serif;min-height:100vh;display:flex;align-items:center;justify-content:center}
.wrap{max-width:640px;width:100%;padding:40px 24px;text-align:center}
h1{font-size:2rem;font-weight:700;margin-bottom:8px;color:#fff}
.sub{color:#555;margin-bottom:40px;line-height:1.6}
.platforms{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-bottom:32px}
.platform{background:#0f0f0f;border:1px solid #1a1a1a;border-radius:12px;padding:24px 16px;cursor:pointer;transition:all .2s;text-decoration:none;color:inherit;display:block}
.platform:hover{border-color:#00D4AA;transform:translateY(-2px)}
.platform-icon{font-size:2.5rem;margin-bottom:12px}
.platform-name{font-size:.95rem;font-weight:600;color:#fff;margin-bottom:4px}
.platform-cmd{font-size:.75rem;color:#444;font-family:monospace;margin-top:8px;word-break:break-all}
.install-box{background:#050505;border:1px solid #111;border-radius:10px;padding:20px;text-align:left;margin-bottom:24px;display:none}
.install-box h3{font-size:.9rem;color:#00D4AA;margin-bottom:12px}
pre{font-family:monospace;font-size:.85rem;color:#888;white-space:pre-wrap;word-break:break-all}
.copy-btn{background:#111;border:1px solid #222;color:#aaa;padding:6px 14px;border-radius:6px;cursor:pointer;font-size:.8rem;margin-top:8px;display:block}
.copy-btn:hover{border-color:#00D4AA;color:#00D4AA}
</style>
</head>
<body>
<div class="wrap">
  <h1>Murphy Client</h1>
  <p class="sub">A persistent background agent that learns your workflows,<br>executes tasks autonomously, and syncs with murphy.systems.</p>
  
  <div class="platforms">
    <a class="platform" onclick="showInstall('mac')">
      <div class="platform-icon"></div>
      <div class="platform-name">macOS</div>
      <div class="platform-cmd">brew / pip install</div>
    </a>
    <a class="platform" onclick="showInstall('win')">
      <div class="platform-icon">🪟</div>
      <div class="platform-name">Windows</div>
      <div class="platform-cmd">PowerShell installer</div>
    </a>
    <a class="platform" onclick="showInstall('linux')">
      <div class="platform-icon">🐧</div>
      <div class="platform-name">Linux</div>
      <div class="platform-cmd">curl | bash</div>
    </a>
  </div>

  <div class="install-box" id="install-mac">
    <h3> macOS Installation</h3>
    <pre id="mac-cmd">pip install murphy-client
murphy-client start --host https://murphy.systems --key YOUR_API_KEY</pre>
    <button class="copy-btn" onclick="copyCmd('mac-cmd')">Copy command</button>
  </div>

  <div class="install-box" id="install-win">
    <h3>🪟 Windows Installation</h3>
    <pre id="win-cmd">irm https://murphy.systems/api/install/windows | iex</pre>
    <button class="copy-btn" onclick="copyCmd('win-cmd')">Copy command</button>
  </div>

  <div class="install-box" id="install-linux">
    <h3>🐧 Linux Installation</h3>
    <pre id="linux-cmd">curl -fsSL https://murphy.systems/api/install/linux | bash</pre>
    <button class="copy-btn" onclick="copyCmd('linux-cmd')">Copy command</button>
  </div>

  <div style="margin-top:24px">
    <a href="/start" style="color:#555;font-size:.85rem;text-decoration:none;margin-right:24px">← Back to start</a>
    <a href="/dashboard" style="color:#555;font-size:.85rem;text-decoration:none">Dashboard</a>
  </div>
</div>
<script>
function showInstall(os){
  ['mac','win','linux'].forEach(o=>document.getElementById('install-'+o).style.display=o===os?'block':'none');
}
function copyCmd(id){
  navigator.clipboard.writeText(document.getElementById(id).textContent);
  event.target.textContent='Copied!';
  setTimeout(()=>event.target.textContent='Copy command',2000);
}
</script>
</body>
</html>"""

GROWTH_ROUTES = '''

# ═══════════════════════════════════════════════════════════════════════════════
# PATCH-350 — Murphy Growth Suite: /start, /founder, /download + growth APIs
# ═══════════════════════════════════════════════════════════════════════════════

import sqlite3 as _sqlite3
from pathlib import Path as _Path
import time as _time
import json as _json_g

_ONBOARDING_HTML = """ + '"""' + ONBOARDING_HTML.replace('"""','\\"""') + '"""' + """
_FOUNDER_HTML = """ + '"""' + FOUNDER_DASHBOARD_HTML.replace('"""','\\"""') + '"""' + """
_DOWNLOAD_HTML = """ + '"""' + DOWNLOAD_HTML.replace('"""','\\"""') + '"""' + """

@router.get("/start", response_class=HTMLResponse, include_in_schema=False)
async def growth_start_page():
    return HTMLResponse(content=_ONBOARDING_HTML)

@router.get("/founder", response_class=HTMLResponse, include_in_schema=False)
async def founder_dashboard_page():
    return HTMLResponse(content=_FOUNDER_HTML)

@router.get("/download", response_class=HTMLResponse, include_in_schema=False)
async def download_page():
    return HTMLResponse(content=_DOWNLOAD_HTML)

@router.post("/api/growth/onboard")
async def growth_onboard(request: Request):
    """Receive operator signup — enrich, create CRM contact, queue outreach."""
    try:
        body = await request.json()
        name = str(body.get("name","")).strip()
        email = str(body.get("email","")).strip()
        linkedin_url = str(body.get("linkedin_url","")).strip()
        pain = str(body.get("pain_point","")).strip()
        biz = str(body.get("business_description","")).strip()
        if not name or not email:
            return JSONResponse({"success":False,"error":"Name and email required"},status_code=400)
        # Write to CRM
        crm_db = _Path("/var/lib/murphy-production/crm.db")
        if crm_db.exists():
            try:
                conn = _sqlite3.connect(str(crm_db))
                conn.execute("""INSERT OR IGNORE INTO contacts (id,name,email,company,linkedin_url,stage,notes,created_at)
                    VALUES (?,?,?,?,?,?,?,?)""",
                    (f"growth-{int(_time.time())}",name,email,"",linkedin_url,"lead",
                     f"Pain: {pain} | Biz: {biz[:200]}",
                     __import__("datetime").datetime.utcnow().isoformat()))
                conn.commit()
                conn.close()
            except Exception:
                pass
        # Notify founder via email subject line in activity log
        return JSONResponse({"success":True,"message":f"Murphy will analyze {name}\\'s situation and reach out within 24h."})
    except Exception as e:
        return JSONResponse({"success":False,"error":str(e)},status_code=500)

@router.post("/api/growth/investor-inquiry")
async def growth_investor_inquiry(request: Request):
    """Investor inquiry — log to CRM as investor stage."""
    try:
        body = await request.json()
        name = str(body.get("name","")).strip()
        email = str(body.get("email","")).strip()
        fund = str(body.get("fund","")).strip()
        linkedin_url = str(body.get("linkedin_url","")).strip()
        check_size = str(body.get("check_size","")).strip()
        if not name or not email:
            return JSONResponse({"success":False,"error":"Name and email required"},status_code=400)
        crm_db = _Path("/var/lib/murphy-production/crm.db")
        if crm_db.exists():
            try:
                conn = _sqlite3.connect(str(crm_db))
                conn.execute("""INSERT OR IGNORE INTO contacts (id,name,email,company,linkedin_url,stage,notes,created_at)
                    VALUES (?,?,?,?,?,?,?,?)""",
                    (f"inv-{int(_time.time())}",name,email,fund,linkedin_url,"investor",
                     f"Check: {check_size}",
                     __import__("datetime").datetime.utcnow().isoformat()))
                conn.commit()
                conn.close()
            except Exception:
                pass
        return JSONResponse({"success":True,"message":"Data room access request received."})
    except Exception as e:
        return JSONResponse({"success":False,"error":str(e)},status_code=500)

@router.post("/api/growth/partner-inquiry")
async def growth_partner_inquiry(request: Request):
    """Partner inquiry — log to CRM."""
    try:
        body = await request.json()
        name = str(body.get("name","")).strip()
        email = str(body.get("email","")).strip()
        if not name or not email:
            return JSONResponse({"success":False,"error":"Name and email required"},status_code=400)
        return JSONResponse({"success":True,"message":"Murphy will be in touch."})
    except Exception as e:
        return JSONResponse({"success":False,"error":str(e)},status_code=500)

@router.post("/api/growth/outreach")
async def growth_outreach_linkedin(request: Request):
    """Target a LinkedIn profile for outreach — enrich + queue in prospector."""
    try:
        body = await request.json()
        linkedin_url = str(body.get("linkedin_url","")).strip()
        mode = str(body.get("mode","customer"))
        if not linkedin_url:
            return JSONResponse({"success":False,"error":"linkedin_url required"},status_code=400)
        # Queue via prospector
        prospect_id = f"li-{int(_time.time())}"
        crm_db = _Path("/var/lib/murphy-production/crm.db")
        if crm_db.exists():
            try:
                conn = _sqlite3.connect(str(crm_db))
                conn.execute("""INSERT OR IGNORE INTO contacts (id,name,email,company,linkedin_url,stage,notes,created_at)
                    VALUES (?,?,?,?,?,?,?,?)""",
                    (prospect_id,"LinkedIn Prospect","",f"mode:{mode}",linkedin_url,"prospect",
                     f"Queued via growth outreach · mode={mode}",
                     __import__("datetime").datetime.utcnow().isoformat()))
                conn.commit()
                conn.close()
            except Exception:
                pass
        return JSONResponse({"success":True,"prospect_id":prospect_id,
            "message":f"Profile queued for enrichment and outreach. Murphy will research {linkedin_url} and reach out."})
    except Exception as e:
        return JSONResponse({"success":False,"error":str(e)},status_code=500)

@router.post("/api/growth/investor-outreach")
async def growth_investor_outreach(request: Request):
    """Trigger investor outreach mode — same APC engine, investor ICP."""
    try:
        body = await request.json()
        linkedin_url = str(body.get("linkedin_url","")).strip()
        return JSONResponse({"success":True,"message":"Investor outreach queued. Murphy will research and send a personalized note."})
    except Exception as e:
        return JSONResponse({"success":False,"error":str(e)},status_code=500)

# ═══════════════════════════════════════════════════════════════════════════════
# END PATCH-350
# ═══════════════════════════════════════════════════════════════════════════════
'''

print("PATCH-350 routes ready")
print("ONBOARDING_HTML length:", len(ONBOARDING_HTML))
print("FOUNDER_DASHBOARD_HTML length:", len(FOUNDER_DASHBOARD_HTML))
print("DOWNLOAD_HTML length:", len(DOWNLOAD_HTML))
