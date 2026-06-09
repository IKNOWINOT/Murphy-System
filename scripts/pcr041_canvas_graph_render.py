#!/usr/bin/env python3
"""
PCR-041 — Render graph_state in /canvas (closes Shape-of-Complete gate (e))

The audit found: PCR-040 produces a real graph_state in the dispatch
response, but ZERO UI pages render it. /canvas calls dispatch correctly,
but immediately discards the response and re-fetches via /api/work/{id}
which doesn't carry graph_state.

This patch adds:
  1. renderGraphState(graph_state, prompt) — paints the 5-agent / 4-round
     graph as a stack of artifact cards in #canvas-body, grouped by
     producer_role, sorted by output_type. Each card shows:
       - role badge (color-coded by domain)
       - output_type
       - JSON content (collapsible <details>)
       - version pill (v1, v2, ...) when refinement ran
  2. A banner at the top showing rounds, fired, failed, unfilled,
     and passes (PCR-040c) when present.
  3. sendDispatch() captures response.graph_state and calls
     renderGraphState() BEFORE the work-list refresh. The work-list
     refresh still runs in the background, but the user sees the
     artifacts immediately.

ZERO backend changes. Single HTML file. Marker-based revert.

CANON CHECK (does it do what it's designed to do):
  Block intent:    A user can see the multi-agent graph that produced
                   their deliverable, with each artifact's content.
  Pipeline intent: Type prompt → Send → artifacts visible on screen
                   within the dispatch RTT.
  Verification:    After patch, sendDispatch a PawPath prompt; verify
                   the 15 artifact cards render with real content.
"""

from __future__ import annotations
import argparse
import sys
from pathlib import Path

CANVAS = Path("/opt/Murphy-System/static/murphy-work-canvas.html")

# ─── 1. Replace sendDispatch's success branch to capture + render graph_state

OLD_SEND = '''    if (d.success) {
      toast('Task sent! Loading work item...', 3000);
      input.value = '';
      await loadWorkList();
      // Auto-select the newest
      if (workItems.length) await selectWork(workItems[0].dag_id);
    } else {
      toast('Error: ' + (d.error || 'Unknown error'));
    }'''

NEW_SEND = '''    if (d.success) {
      toast('Dispatched. Rendering graph...', 2000);
      input.value = '';
      // PCR-041: render PCR-040 graph_state immediately if present
      if (d.graph_state && d.graph_state.nodes) {
        renderGraphState(d.graph_state, prompt);
      }
      // Background refresh of the work-list (doesn't block UI)
      loadWorkList().then(() => {
        if (workItems.length && !d.graph_state) selectWork(workItems[0].dag_id);
      }).catch(() => {});
    } else {
      toast('Error: ' + (d.error || 'Unknown error'));
    }'''

# ─── 2. Insert the renderGraphState function just before sendDispatch

OLD_HOOK = '''// ── Dispatch ──────────────────────────────────────────────────────────────────
async function sendDispatch() {'''

NEW_HOOK = '''// ── PCR-041 graph_state renderer ──────────────────────────────────────────────
// Paints the PCR-040 graph_state into #canvas-body as a stack of artifact
// cards, grouped by producer_role, ordered by output_type.
function renderGraphState(gs, prompt) {
  const host = document.getElementById('canvas-body');
  if (!host) return;
  const rounds   = gs.rounds || 0;
  const fired    = (gs.fired || []).length;
  const failed   = (gs.failed || []).length;
  const unfilled = (gs.unfilled || []);
  const mode     = gs.mode || 'unknown';
  const passes   = gs.passes || [];

  // Group nodes by producer_role; ignore archived @v keys for the main view
  const nodes = gs.nodes || {};
  const groups = {};
  for (const key in nodes) {
    if (key.indexOf('@v') !== -1) continue; // archived versions
    const n = nodes[key];
    const role = n.producer_role || 'Unknown';
    if (!groups[role]) groups[role] = [];
    groups[role].push({ key, ...n });
  }
  const roleColors = ['#ff5a00','#22c55e','#3b82f6','#f59e0b','#a855f7','#06b6d4','#ec4899','#84cc16'];
  const esc = s => String(s == null ? '' : s)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;').replace(/'/g,'&#39;');

  let html = '';

  // Top banner
  html += '<div style="padding:18px 22px;border-bottom:1px solid var(--border);background:var(--surface);">';
  html += '<div style="font-size:11px;color:var(--text-muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;">DISPATCH RESULT  ·  mode=' + esc(mode) + '</div>';
  html += '<div style="font-size:15px;color:var(--text);margin-bottom:10px;line-height:1.4;">' + esc(prompt.substring(0,200)) + (prompt.length > 200 ? '…' : '') + '</div>';
  html += '<div style="display:flex;gap:14px;flex-wrap:wrap;font-size:12px;">';
  html += '<span style="color:var(--text-dim);">rounds: <b style="color:var(--text);">' + rounds + '</b></span>';
  html += '<span style="color:var(--green);">fired: <b>' + fired + '</b></span>';
  html += '<span style="color:' + (failed ? 'var(--orange)' : 'var(--text-muted)') + ';">failed: <b>' + failed + '</b></span>';
  html += '<span style="color:' + (unfilled.length ? 'var(--yellow)' : 'var(--text-muted)') + ';">unfilled: <b>' + unfilled.length + '</b></span>';
  if (passes.length > 1) {
    html += '<span style="color:var(--blue);">refinement passes: <b>' + passes.length + '</b></span>';
  }
  html += '</div></div>';

  if (unfilled.length) {
    html += '<div style="padding:10px 22px;background:var(--yellow-dim);border-bottom:1px solid var(--border);font-size:12px;color:var(--yellow);">';
    html += '⚠ Unfilled inputs: ' + unfilled.map(esc).join(', ');
    html += '</div>';
  }

  // Role columns
  html += '<div style="padding:18px 22px;">';
  const roleList = Object.keys(groups).sort();
  roleList.forEach((role, i) => {
    const color = roleColors[i % roleColors.length];
    const artifacts = groups[role].sort((a,b) => a.key.localeCompare(b.key));
    html += '<div style="margin-bottom:22px;">';
    html += '<div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;">';
    html += '<div style="width:8px;height:8px;border-radius:50%;background:' + color + ';"></div>';
    html += '<div style="font-size:13px;font-weight:600;color:var(--text);">' + esc(role) + '</div>';
    html += '<div style="font-size:11px;color:var(--text-muted);">' + artifacts.length + ' artifact' + (artifacts.length !== 1 ? 's' : '') + '</div>';
    html += '</div>';

    artifacts.forEach(a => {
      const ok = a.success !== false;
      const version = a.version || 1;
      const versionPill = version > 1
        ? '<span style="font-size:10px;background:var(--blue-dim);color:var(--blue);padding:2px 6px;border-radius:3px;margin-left:6px;">v' + version + '</span>'
        : '';
      const statusMark = ok ? '✓' : '✗';
      const statusColor = ok ? 'var(--green)' : 'var(--orange)';
      let bodyTxt = '';
      try {
        bodyTxt = (typeof a.content === 'string') ? a.content : JSON.stringify(a.content, null, 2);
      } catch(e) { bodyTxt = String(a.content); }
      html += '<div style="background:var(--card);border:1px solid var(--border);border-radius:6px;padding:12px 14px;margin-bottom:8px;">';
      html += '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px;">';
      html += '<div style="font-size:12px;color:var(--text);"><span style="color:' + statusColor + ';">' + statusMark + '</span> <b>' + esc(a.output_type || a.key) + '</b>' + versionPill + '</div>';
      html += '</div>';
      if (!ok && a.error) {
        html += '<div style="font-size:11px;color:var(--orange);background:rgba(255,90,0,0.08);padding:6px 8px;border-radius:4px;font-family:monospace;">' + esc(a.error) + '</div>';
      } else {
        html += '<details style="margin-top:4px;">';
        html += '<summary style="font-size:11px;color:var(--text-dim);cursor:pointer;user-select:none;">view content (' + bodyTxt.length + ' chars)</summary>';
        html += '<pre style="margin-top:8px;font-size:11px;color:var(--text);background:var(--black);border:1px solid var(--border);border-radius:4px;padding:10px;overflow-x:auto;white-space:pre-wrap;word-break:break-word;max-height:400px;">' + esc(bodyTxt) + '</pre>';
        html += '</details>';
      }
      html += '</div>';
    });

    html += '</div>';
  });

  html += '</div>';
  host.innerHTML = html;
  // Scroll to top so user sees the banner first
  host.scrollTop = 0;
}

// ── Dispatch ──────────────────────────────────────────────────────────────────
async function sendDispatch() {'''


def apply(verify, revert):
    print(f"PCR-041 canvas graph render  verify={verify}  revert={revert}")
    src = CANVAS.read_text(encoding="utf-8")
    if revert:
        if "PCR-041" not in src:
            print("  · already absent"); return 0
        src = src.replace(NEW_SEND, OLD_SEND, 1)
        src = src.replace(NEW_HOOK, OLD_HOOK, 1)
        if verify: print("  ✓ would revert"); return 0
        CANVAS.write_text(src, encoding="utf-8")
        print("  ✓ reverted"); return 0
    if "PCR-041" in src:
        print("  · already present"); return 0
    misses = []
    if OLD_SEND not in src: misses.append("OLD_SEND")
    if OLD_HOOK not in src: misses.append("OLD_HOOK")
    if misses:
        print(f"  ✗ anchors missing: {misses}")
        return 1
    src = src.replace(OLD_SEND, NEW_SEND, 1)
    src = src.replace(OLD_HOOK, NEW_HOOK, 1)
    if verify: print("  ✓ would apply"); return 0
    CANVAS.write_text(src, encoding="utf-8")
    print("  ✓ renderGraphState() injected")
    print("  ✓ sendDispatch() now captures + renders graph_state")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--revert", action="store_true")
    a = ap.parse_args()
    return apply(a.verify, a.revert)


if __name__ == "__main__":
    sys.exit(main())
