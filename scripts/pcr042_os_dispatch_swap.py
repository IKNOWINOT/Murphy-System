#!/usr/bin/env python3
"""
PCR-042 — Swap /os primary dispatch from swarm/execute to rosetta/dispatch,
add graph_state renderer. Closes Shape-of-Complete gate (e) on the /os surface.

Audit found:
  /os runDispatch() calls /api/swarm/execute (legacy)
  /os has zero graph_state rendering
  /os has the 8-stage animated pipeline that polls real subsystems

Approach (b): keep the animation, swap the dispatch call, render graph_state
when response lands. Best of both worlds — "Murphy is thinking" visualization
during, then real artifacts after.

CHANGES (single file: static/murphy-os.html):
  1. runDispatch primary call: /api/swarm/execute → /api/rosetta/dispatch
  2. Request body: {task, budget: 50} → {prompt: task}
  3. Inject renderOsGraphState(gs, prompt) — adapted to /os CSS tokens
     (--bg, --border, --text, --teal, --orange, --yellow)
  4. On success: if graph_state present, render it into #result-box
     ABOVE the existing result fields (status/runid/duration/cost).
     The legacy result fields still populate (status, task_id, etc.)
     so nothing breaks for callers that don't return graph_state.
  5. Fall back gracefully: when graph_state is absent, behave like today.

PRESERVES:
  - The 8-stage pipeline animation
  - The console log messages
  - The face emoji transitions
  - The result-box show/hide flow
  - All R64d retry/drill-down hooks

ZERO backend changes. Single HTML file. Marker-based revert.
"""

from __future__ import annotations
import argparse
import sys
from pathlib import Path

OS_HTML = Path("/opt/Murphy-System/static/murphy-os.html")

# ─── 1. Swap dispatch call: swarm/execute → rosetta/dispatch ─────────────

OLD_CALL = "    const result = await api('POST', '/api/swarm/execute', { task, budget: 50 }, 180000);"

NEW_CALL = """    // PCR-042: swap to rosetta/dispatch — gets graph_state back instead of synthesis blob
    const result = await api('POST', '/api/rosetta/dispatch', { prompt: task }, 180000);"""

# ─── 2. On success branch: render graph_state if present ────────────────

OLD_SUCCESS = '''    if (result.success !== false) {
      logConsole('✅ Complete — run_id: ' + (result.task_id||'').slice(0,16) + ' status: ' + (result.status||'ok'), 'success');
      const rb = document.getElementById('result-box');
      rb.classList.add('show');
      document.getElementById('result-text').textContent = result.synthesis || result.result || 'Task completed.';
      document.getElementById('res-status').textContent = result.status || 'completed';
      document.getElementById('res-runid').textContent = (result.task_id||result.run_id||'').slice(0,20);
      document.getElementById('res-duration').textContent = ((result.duration_ms||0)/1000).toFixed(2) + 's';
      document.getElementById('res-cost').textContent = '$' + (result.total_cost||0).toFixed(4);
      addActivity('Dispatch complete: "' + task.slice(0,40) + '"', 'success');
    } else {'''

NEW_SUCCESS = '''    if (result.success !== false) {
      logConsole('✅ Complete — run_id: ' + (result.dag_id||result.task_id||'').slice(0,16) + ' status: ' + (result.status||'ok'), 'success');
      const rb = document.getElementById('result-box');
      rb.classList.add('show');
      // PCR-042: prefer graph_state rendering when present
      if (result.graph_state && result.graph_state.nodes) {
        const realKeys = Object.keys(result.graph_state.nodes).filter(k => k.indexOf('@v') === -1);
        if (realKeys.length > 0) {
          renderOsGraphState(result.graph_state, task);
          logConsole('  → ' + realKeys.length + ' artifacts across ' + (result.graph_state.rounds||0) + ' rounds', 'success');
        } else {
          // graph_state shape present but empty (planner coverage gap)
          document.getElementById('result-text').textContent = 'Dispatch completed but no graph_state nodes produced. Planner may have routed to a non-graph plan.';
        }
      } else {
        // Legacy / non-graph response — keep existing behavior
        document.getElementById('result-text').textContent = result.synthesis || result.result || 'Task completed.';
      }
      document.getElementById('res-status').textContent = result.status || (result.graph_state ? 'graph-complete' : 'completed');
      document.getElementById('res-runid').textContent = (result.dag_id||result.task_id||result.run_id||'').slice(0,20);
      document.getElementById('res-duration').textContent = ((result.duration_ms||0)/1000).toFixed(2) + 's';
      document.getElementById('res-cost').textContent = '$' + (result.total_cost||0).toFixed(4);
      addActivity('Dispatch complete: "' + task.slice(0,40) + '"', 'success');
    } else {'''

# ─── 3. Inject renderOsGraphState before runDispatch ─────────────────────
# Anchor: the `async function runDispatch() {` definition

OLD_HOOK = "async function runDispatch() {"

NEW_HOOK = '''// ── PCR-042 graph_state renderer for /os ──────────────────────────────────────
// Adapted from PCR-041 (/canvas) to use /os CSS tokens.
// Renders into #result-text — replaces the synthesis blob with a real
// per-role / per-artifact view of the PCR-040 graph.
function renderOsGraphState(gs, prompt) {
  const host = document.getElementById('result-text');
  if (!host) return;
  const rounds   = gs.rounds || 0;
  const fired    = (gs.fired || []).length;
  const failed   = (gs.failed || []).length;
  const unfilled = (gs.unfilled || []);
  const mode     = gs.mode || 'unknown';
  const passes   = gs.passes || [];

  const nodes = gs.nodes || {};
  const groups = {};
  for (const key in nodes) {
    if (key.indexOf('@v') !== -1) continue;
    const n = nodes[key];
    const role = n.producer_role || 'Unknown';
    if (!groups[role]) groups[role] = [];
    groups[role].push({ key, ...n });
  }
  const roleColors = ['#39d353','#ff7b72','#e3b341','#00d4aa','#f85149','#a855f7','#3b82f6','#ec4899'];
  const esc = s => String(s == null ? '' : s)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;').replace(/'/g,'&#39;');

  let html = '';
  // Banner
  html += '<div style="padding:12px 14px;border:1px solid var(--border);background:var(--teal-dim);border-radius:6px;margin-bottom:14px;">';
  html += '<div style="font-size:10px;color:var(--teal);text-transform:uppercase;letter-spacing:1.2px;margin-bottom:6px;font-weight:600;">PCR-040 GRAPH RESULT · mode=' + esc(mode) + '</div>';
  html += '<div style="display:flex;gap:14px;flex-wrap:wrap;font-size:11px;color:var(--text);">';
  html += '<span>rounds: <b>' + rounds + '</b></span>';
  html += '<span style="color:var(--teal);">fired: <b>' + fired + '</b></span>';
  html += '<span style="color:' + (failed ? 'var(--orange)' : 'var(--text)') + ';">failed: <b>' + failed + '</b></span>';
  html += '<span style="color:' + (unfilled.length ? 'var(--yellow)' : 'var(--text)') + ';">unfilled: <b>' + unfilled.length + '</b></span>';
  if (passes.length > 1) html += '<span style="color:var(--live);">passes: <b>' + passes.length + '</b></span>';
  html += '</div></div>';

  if (unfilled.length) {
    html += '<div style="padding:8px 12px;background:rgba(227,179,65,0.08);border:1px solid var(--yellow);border-radius:4px;font-size:11px;color:var(--yellow);margin-bottom:12px;">';
    html += '⚠ Unfilled inputs: ' + unfilled.map(esc).join(', ') + '</div>';
  }

  // Role groups
  const roleList = Object.keys(groups).sort();
  roleList.forEach((role, i) => {
    const color = roleColors[i % roleColors.length];
    const artifacts = groups[role].sort((a,b) => a.key.localeCompare(b.key));
    html += '<div style="margin-bottom:18px;">';
    html += '<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;padding-bottom:6px;border-bottom:1px solid var(--border);">';
    html += '<div style="width:6px;height:6px;border-radius:50%;background:' + color + ';"></div>';
    html += '<div style="font-size:12px;font-weight:600;color:var(--text);">' + esc(role) + '</div>';
    html += '<div style="font-size:10px;color:#7d8590;">' + artifacts.length + ' artifact' + (artifacts.length !== 1 ? 's' : '') + '</div>';
    html += '</div>';

    artifacts.forEach(a => {
      const ok = a.success !== false;
      const version = a.version || 1;
      const vpill = version > 1
        ? '<span style="font-size:9px;background:var(--live-dim);color:var(--live);padding:1px 5px;border-radius:3px;margin-left:5px;">v' + version + '</span>'
        : '';
      const mark = ok ? '✓' : '✗';
      const mcolor = ok ? 'var(--teal)' : 'var(--orange)';
      let body = '';
      try { body = (typeof a.content === 'string') ? a.content : JSON.stringify(a.content, null, 2); }
      catch(e) { body = String(a.content); }
      html += '<div style="background:#0d1117;border:1px solid var(--border);border-radius:4px;padding:10px 12px;margin-bottom:6px;">';
      html += '<div style="font-size:11px;color:var(--text);margin-bottom:4px;"><span style="color:' + mcolor + ';">' + mark + '</span> <b>' + esc(a.output_type || a.key) + '</b>' + vpill + '</div>';
      if (!ok && a.error) {
        html += '<div style="font-size:10px;color:var(--orange);font-family:monospace;padding:5px 8px;background:rgba(248,81,73,0.08);border-radius:3px;">' + esc(a.error) + '</div>';
      } else {
        html += '<details><summary style="font-size:10px;color:#7d8590;cursor:pointer;user-select:none;">view content (' + body.length + ' chars)</summary>';
        html += '<pre style="margin-top:6px;font-size:10px;color:var(--text);background:#010409;border:1px solid var(--border);border-radius:3px;padding:8px;overflow-x:auto;white-space:pre-wrap;word-break:break-word;max-height:320px;">' + esc(body) + '</pre>';
        html += '</details>';
      }
      html += '</div>';
    });
    html += '</div>';
  });

  host.innerHTML = html;
}

async function runDispatch() {'''


def apply(verify, revert):
    print(f"PCR-042 /os dispatch swap  verify={verify}  revert={revert}")
    src = OS_HTML.read_text(encoding="utf-8")
    if revert:
        if "PCR-042" not in src:
            print("  · already absent"); return 0
        src = src.replace(NEW_CALL, OLD_CALL, 1)
        src = src.replace(NEW_SUCCESS, OLD_SUCCESS, 1)
        src = src.replace(NEW_HOOK, OLD_HOOK, 1)
        if verify: print("  ✓ would revert"); return 0
        OS_HTML.write_text(src, encoding="utf-8")
        print("  ✓ reverted"); return 0
    if "PCR-042" in src:
        print("  · already present"); return 0
    misses = []
    if OLD_CALL not in src: misses.append("OLD_CALL")
    if OLD_SUCCESS not in src: misses.append("OLD_SUCCESS")
    if OLD_HOOK not in src: misses.append("OLD_HOOK")
    if misses:
        print(f"  ✗ anchors missing: {misses}")
        return 1
    src = src.replace(OLD_CALL, NEW_CALL, 1)
    src = src.replace(OLD_SUCCESS, NEW_SUCCESS, 1)
    src = src.replace(OLD_HOOK, NEW_HOOK, 1)
    if verify: print("  ✓ would apply"); return 0
    OS_HTML.write_text(src, encoding="utf-8")
    print("  ✓ runDispatch primary: swarm/execute → rosetta/dispatch")
    print("  ✓ renderOsGraphState() injected")
    print("  ✓ success branch wired to render graph_state")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--revert", action="store_true")
    a = ap.parse_args()
    return apply(a.verify, a.revert)


if __name__ == "__main__":
    sys.exit(main())
