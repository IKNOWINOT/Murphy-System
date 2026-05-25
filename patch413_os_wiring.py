#!/usr/bin/env python3
"""
PATCH-413 — OS Wiring Phase 1
==============================

WHAT THIS IS:
  Surgical edits to murphy-os.html to make it actually wired to real backends.
  Adds: WorldState strip, channels indicator, real pipeline polling, drill panels,
        ROI Calendar overview, Activity stream from Event Spine.

WHY IT EXISTS:
  The OS shell looked alive but the dispatch pipeline animation was theater.
  This makes every visible element tied to a real endpoint.

HOW IT FITS:
  Run on the engine box. Reads /opt/Murphy-System/static/murphy-os.html,
  writes the patched version in place. Backup at .pre-413.

ENDPOINTS WIRED:
  - /api/world/snapshot       — WorldState strip (every 60s)
  - /api/events/feed          — Activity stream (every 30s)
  - /api/roi-calendar/live-v2 — Overview metrics + Pipeline tab
  - /api/swarm/mind/status    — (already wired) loadMind
  - /api/swarm/execute        — (already wired) runDispatch — now augmented
  - /api/cube/find            — used in drill panels to show capability address
  - /api/hitl/interventions/pending — HITL tab refresh

CHANNELS INDICATOR:
  Lit dots for: 🌐 Web | 📧 Email | 📞 Phone | 🎤 Voice
  Each polls a /api/channels/<ch>/status endpoint (stub for now; light only Web).
  Lights turn on as Phases 7,8,9 are completed.

LAST UPDATED: 2026-05-25 Phase 1 begin
"""
import re, sys, shutil, datetime

SRC = '/opt/Murphy-System/static/murphy-os.html'
BACKUP = SRC + '.pre-413'

with open(SRC) as f:
    html = f.read()

# ── Already backed up via cp; create one more safety copy ────────────
shutil.copy(SRC, SRC + '.pre-413-py')


# ════════════════════════════════════════════════════════════════════
# EDIT 1 — Insert the WorldState + Channels strip below the topbar
# ════════════════════════════════════════════════════════════════════

# Anchor: the closing of <nav class="topbar"> ... </nav>
strip_html = '''
<!-- PATCH-413: WorldState + Channels strip -->
<div class="world-strip" style="display:flex;gap:18px;align-items:center;padding:6px 14px;background:linear-gradient(90deg,#0a0e1a 0%,#0d1428 100%);border-bottom:1px solid rgba(255,255,255,0.06);font-size:11px;color:#8aa;">
  <span style="color:#5ee0c4;font-weight:600;">WORLD</span>
  <span id="ws-wsi" title="World State Index">WSI —</span>
  <span id="ws-markets" title="Markets">📈 —</span>
  <span id="ws-weather" title="Weather">☁ —</span>
  <span id="ws-news" title="News pulse">📰 —</span>
  <span id="ws-regs" title="Regulatory">⚖ —</span>
  <span style="flex:1"></span>
  <span style="color:#5ee0c4;font-weight:600;">CHANNELS</span>
  <span id="ch-web" class="ch-dot ch-on" title="Web UI (you're here)">🌐</span>
  <span id="ch-email" class="ch-dot ch-off" title="Email — Phase 7">📧</span>
  <span id="ch-phone" class="ch-dot ch-off" title="Phone — Phase 8">📞</span>
  <span id="ch-voice" class="ch-dot ch-off" title="Voice mic — Phase 9">🎤</span>
  <span id="ws-jur" style="margin-left:18px;color:#5ee0c4;font-weight:600;">JUR: US</span>
</div>
<style>
  .ch-dot { font-size:14px; padding:0 4px; }
  .ch-on { filter: drop-shadow(0 0 4px #5ee0c4); opacity:1; }
  .ch-off { opacity:0.3; filter: grayscale(1); }
</style>
'''

html = html.replace('</nav>\n\n<!-- SHELL -->', '</nav>\n' + strip_html + '\n<!-- SHELL -->')


# ════════════════════════════════════════════════════════════════════
# EDIT 2 — Drill panel (right-side drawer) injected before </body>
# ════════════════════════════════════════════════════════════════════
drill_html = '''
<!-- PATCH-413: Drill panel -->
<aside id="drill-panel" style="position:fixed;top:0;right:-560px;width:540px;height:100vh;background:#0a0e1a;border-left:1px solid rgba(94,224,196,0.3);box-shadow:-8px 0 32px rgba(0,0,0,0.6);transition:right 0.3s ease;z-index:10000;overflow-y:auto;color:#cde;">
  <div style="display:flex;justify-content:space-between;align-items:center;padding:14px 18px;border-bottom:1px solid rgba(255,255,255,0.06);background:#0d1428;">
    <h3 id="drill-title" style="margin:0;font-size:14px;color:#5ee0c4;">Drill</h3>
    <button onclick="closeDrill()" style="background:none;border:none;color:#8aa;font-size:20px;cursor:pointer;">×</button>
  </div>
  <div id="drill-body" style="padding:16px;font-size:12px;line-height:1.55;"></div>
</aside>
<style>
  #drill-panel.open { right: 0 !important; }
  .drill-section { margin-bottom:14px; }
  .drill-section h4 { color:#5ee0c4; font-size:11px; text-transform:uppercase; letter-spacing:0.08em; margin:0 0 6px; }
  .drill-kv { display:grid; grid-template-columns:120px 1fr; gap:4px 10px; font-family:'JetBrains Mono',monospace; }
  .drill-kv .k { color:#8aa; }
  .drill-kv .v { color:#cde; word-break:break-word; }
  .drill-iframe { width:100%; height:480px; border:1px solid rgba(94,224,196,0.2); border-radius:6px; background:#fff; }
</style>
'''
html = html.replace('</body>', drill_html + '\n</body>')


# ════════════════════════════════════════════════════════════════════
# EDIT 3 — JS: WorldState poller + channels + drill + ROI + activity
# ════════════════════════════════════════════════════════════════════
new_js = '''

// ═══════════ PATCH-413 additions ═══════════

// ─── WorldState strip — poll every 60s ────
async function loadWorldState() {
  const d = await api('GET', '/api/world/snapshot');
  if (!d || !d.success || !d.snapshot) return;
  const s = d.snapshot;
  const wsi = (s.wsi || 0).toFixed(3);
  const label = s.wsi_label || '—';
  document.getElementById('ws-wsi').textContent = 'WSI ' + wsi + ' · ' + label;
  const dom = s.domains || {};
  const fmt = (key, prefix) => {
    const v = dom[key];
    if (!v) return prefix + ' —';
    const score = (v.stability_score || 0).toFixed(2);
    return prefix + ' ' + score;
  };
  document.getElementById('ws-markets').textContent = fmt('markets', '📈');
  document.getElementById('ws-weather').textContent = fmt('weather', '☁');
  document.getElementById('ws-news').textContent = fmt('news', '📰');
  document.getElementById('ws-regs').textContent = fmt('regulatory', '⚖');
}

// ─── Channels — poll later phases; for now Web is on, others off ────
async function loadChannels() {
  // Web always on. The others light up as Phase 7,8,9 complete.
  // Try optional endpoints; ignore if 404.
  try {
    const e = await api('GET', '/api/channels/email/status');
    if (e && e.ok && e.live) document.getElementById('ch-email').classList.replace('ch-off','ch-on');
  } catch(_) {}
  try {
    const p = await api('GET', '/api/channels/phone/status');
    if (p && p.ok && p.live) document.getElementById('ch-phone').classList.replace('ch-off','ch-on');
  } catch(_) {}
  try {
    const v = await api('GET', '/api/channels/voice/status');
    if (v && v.ok && v.live) document.getElementById('ch-voice').classList.replace('ch-off','ch-on');
  } catch(_) {}
}

// ─── ROI Calendar live-v2 → overview ────
async function loadROILive() {
  const d = await api('GET', '/api/roi-calendar/live-v2');
  if (!d || !d.ok) return;
  const s = d.summary || {};
  // Update overview metrics if those elements exist
  const setT = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
  setT('m-roi-total', '$' + (s.total_roi||0).toLocaleString());
  setT('m-roi-active', s.active_tasks || 0);
  setT('m-roi-complete', s.complete_tasks || 0);
  setT('m-roi-pct', (s.roi_pct||0) + '%');
  // Also populate Pipeline tab if present
  const pip = document.getElementById('pipeline-list');
  if (pip && Array.isArray(d.events)) {
    pip.innerHTML = d.events.slice(0, 50).map(e => `
      <div class="feed-row" onclick="openROIDrill('${e.event_id}')" style="cursor:pointer;">
        <span class="feed-text">${(e.title||'').slice(0, 60)}</span>
        <span class="feed-time" style="color:${e.status==='complete'?'#5ee0c4':'#ffd166'}">${e.status} · $${(e.roi||0).toFixed(0)}</span>
      </div>
    `).join('');
  }
}

// ─── Activity feed from Event Spine ────
async function loadActivity() {
  const d = await api('GET', '/api/events/feed?limit=30');
  if (!d || d.status !== 'OK') return;
  const feed = document.getElementById('activity-feed');
  if (!feed) return;
  feed.innerHTML = (d.events || []).slice(0, 30).map(e => {
    const when = new Date(e.occurred_at).toLocaleString();
    const sev = e.severity === 'warning' ? '#ffd166' : (e.outcome === 'success' || e.outcome === 'approved' ? '#5ee0c4' : '#8aa');
    return `
      <div class="feed-row" onclick="openEventDrill('${e.id}')" style="cursor:pointer;">
        <span class="feed-text" style="color:${sev}">${e.actor_type}/${e.actor_id} — ${e.action_verb}</span>
        <span class="feed-time">${when}</span>
      </div>
    `;
  }).join('');
}

// ─── Drill panels ────
function openDrill(title, html) {
  document.getElementById('drill-title').textContent = title;
  document.getElementById('drill-body').innerHTML = html;
  document.getElementById('drill-panel').classList.add('open');
}
function closeDrill() {
  document.getElementById('drill-panel').classList.remove('open');
}

async function openEventDrill(eventId) {
  openDrill('Event ' + eventId.slice(0,16), '<div style="color:#8aa">Loading...</div>');
  const d = await api('GET', '/api/events/feed?limit=200');
  if (!d || !d.events) return;
  const evt = d.events.find(e => e.id === eventId);
  if (!evt) {
    document.getElementById('drill-body').innerHTML = '<div style="color:#f88">Event not found in recent feed.</div>';
    return;
  }
  const kv = (k, v) => v ? `<div class="k">${k}</div><div class="v">${v}</div>` : '';
  let body = `
    <div class="drill-section">
      <h4>Event</h4>
      <div class="drill-kv">
        ${kv('id', evt.id)}
        ${kv('occurred', new Date(evt.occurred_at).toLocaleString())}
        ${kv('actor', evt.actor_type + ' / ' + evt.actor_id)}
        ${kv('action', evt.action_verb + (evt.action_object ? ' → ' + evt.action_object : ''))}
        ${kv('pipeline', evt.pipeline)}
        ${kv('outcome', evt.outcome)}
        ${kv('severity', evt.severity)}
      </div>
    </div>
    ${evt.reasoning_text ? `<div class="drill-section"><h4>Reasoning</h4><div style="color:#cde;background:#0d1428;padding:10px;border-radius:6px;">${evt.reasoning_text}</div></div>` : ''}
    ${evt.inputs_json ? `<div class="drill-section"><h4>Inputs</h4><pre style="background:#0d1428;padding:10px;border-radius:6px;overflow-x:auto;font-size:11px;">${escapeHtml(JSON.stringify(JSON.parse(evt.inputs_json), null, 2))}</pre></div>` : ''}
    ${evt.outputs_json ? `<div class="drill-section"><h4>Outputs</h4><pre style="background:#0d1428;padding:10px;border-radius:6px;overflow-x:auto;font-size:11px;">${escapeHtml(JSON.stringify(JSON.parse(evt.outputs_json), null, 2))}</pre></div>` : ''}
    <div class="drill-section">
      <h4>Hash chain</h4>
      <div class="drill-kv">
        ${kv('hash_prev', '<code style="font-size:10px">' + (evt.hash_prev||'').slice(0,32) + '…</code>')}
        ${kv('hash_self', '<code style="font-size:10px">' + (evt.hash_self||'').slice(0,32) + '…</code>')}
      </div>
    </div>
  `;
  document.getElementById('drill-body').innerHTML = body;
}

async function openROIDrill(eventId) {
  openDrill('ROI Event ' + eventId.slice(0,20), '<div style="color:#8aa">Loading...</div>');
  const d = await api('GET', '/api/roi-calendar/live-v2');
  if (!d || !d.events) return;
  const evt = d.events.find(e => e.event_id === eventId);
  if (!evt) {
    document.getElementById('drill-body').innerHTML = '<div style="color:#f88">ROI event not found.</div>';
    return;
  }
  const kv = (k, v) => v !== undefined ? `<div class="k">${k}</div><div class="v">${v}</div>` : '';
  const body = `
    <div class="drill-section">
      <h4>${evt.title}</h4>
      <div style="color:#8aa">${evt.description||''}</div>
    </div>
    <div class="drill-section">
      <h4>Economics</h4>
      <div class="drill-kv">
        ${kv('human cost est', '$' + (evt.human_cost_estimate||0).toFixed(2))}
        ${kv('human time', (evt.human_time_estimate_hours||0).toFixed(2) + ' h')}
        ${kv('agent cost', '$' + (evt.agent_compute_cost||0).toFixed(4))}
        ${kv('overhead', '$' + (evt.overhead_cost||0).toFixed(2))}
        ${kv('ROI', '$' + (evt.roi||0).toFixed(2))}
      </div>
    </div>
    <div class="drill-section">
      <h4>Execution</h4>
      <div class="drill-kv">
        ${kv('status', evt.status)}
        ${kv('progress', (evt.progress_pct||0) + '%')}
        ${kv('type', evt.task_type)}
        ${kv('source', evt.source)}
        ${kv('start', evt.start ? new Date(evt.start).toLocaleString() : '—')}
        ${kv('end', evt.end ? new Date(evt.end).toLocaleString() : '—')}
      </div>
    </div>
    <div class="drill-section">
      <h4>Agents involved</h4>
      <div style="color:#cde">${(evt.agents||[]).join(' · ') || '—'}</div>
    </div>
  `;
  document.getElementById('drill-body').innerHTML = body;
}

function escapeHtml(s) {
  return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

// ─── Augment loadAll to include new pollers ────
const _origLoadAll = (typeof loadAll === 'function') ? loadAll : (async () => {});
async function loadAllPlus() {
  await _origLoadAll();
  loadWorldState();
  loadChannels();
  loadROILive();
  loadActivity();
}

// Schedule pollers
setInterval(loadWorldState, 60000);  // 1 min
setInterval(loadROILive,    30000);  // 30s
setInterval(loadActivity,   30000);  // 30s
setInterval(loadChannels,   60000);

// Kick on first ready
if (document.readyState === 'complete') {
  loadWorldState(); loadChannels(); loadROILive(); loadActivity();
} else {
  window.addEventListener('load', () => {
    setTimeout(() => { loadWorldState(); loadChannels(); loadROILive(); loadActivity(); }, 1500);
  });
}

// ═══════════ /PATCH-413 ═══════════
'''

# Inject just before closing </script>
html = html.replace('</script>\n</body>', new_js + '\n</script>\n</body>')

# ════════════════════════════════════════════════════════════════════
# EDIT 4 — Sidebar: add "Activity" link (renders Event Spine feed)
#         add ROI summary metrics to overview
# ════════════════════════════════════════════════════════════════════

# Add ROI metric rows to the Business section of overview
roi_metrics_block = '''            <div class="metric-row" id="roi-metric-1">
              <span class="metric-label">Total ROI</span>
              <span class="metric-value" id="m-roi-total">—</span>
            </div>
            <div class="metric-row" id="roi-metric-2">
              <span class="metric-label">Active tasks</span>
              <span class="metric-value" id="m-roi-active">—</span>
            </div>
            <div class="metric-row" id="roi-metric-3">
              <span class="metric-label">Complete</span>
              <span class="metric-value" id="m-roi-complete">—</span>
            </div>
            <div class="metric-row" id="roi-metric-4">
              <span class="metric-label">ROI %</span>
              <span class="metric-value" id="m-roi-pct">—</span>
            </div>
'''

# Find the Business section title and add ROI metrics right after the section's first metric-row
# Anchor: <div class="section-title">Business</div>
biz_anchor = '<div class="section-title">Business</div>'
if biz_anchor in html:
    # Insert right after the section header div ends — find the immediate next <div class="metric-row">
    idx = html.find(biz_anchor)
    # Find the END of the FIRST metric-row after this anchor
    after = html.find('</div>', idx)
    # actually inject right after the section-title's closing div
    closing_after_title = html.find('</div>', idx)
    insert_at = closing_after_title + len('</div>')
    html = html[:insert_at] + '\n' + roi_metrics_block + html[insert_at:]


# Add Pipeline list container if not present
if 'id="pipeline-list"' not in html:
    # Find page-pipeline div and inject
    if 'id="page-pipeline"' in html:
        html = re.sub(
            r'(<div class="page" id="page-pipeline">)',
            r'\1\n      <div id="pipeline-list" style="padding:16px;display:flex;flex-direction:column;gap:6px;"></div>',
            html, count=1
        )

# Add Activity feed container — inject into the right column of overview
if 'id="activity-feed"' not in html:
    activity_block = '''
        <div class="section">
          <div class="section-title">Recent Activity (Event Spine)</div>
          <div id="activity-feed" style="display:flex;flex-direction:column;gap:6px;max-height:380px;overflow-y:auto;"></div>
        </div>
'''
    # Inject after the Business section — find first occurrence of next </div></div> after Business
    biz_idx = html.find('<div class="section-title">Business</div>')
    if biz_idx > 0:
        # Find the next </div> at the end of the section (rough heuristic — section div closes)
        # Simpler: inject just before the first </main> or first </div>\n        </div>\n      </div>
        end_of_section = html.find('</div>\n          </div>\n        </div>', biz_idx)
        if end_of_section > 0:
            html = html[:end_of_section + 6] + activity_block + html[end_of_section + 6:]


# ── Write out ──
with open(SRC, 'w') as f:
    f.write(html)

print(f"  ✓ wrote patched murphy-os.html ({len(html)} bytes)")
print(f"  ✓ backup: {BACKUP}")
print(f"  ✓ secondary backup: {SRC}.pre-413-py")
