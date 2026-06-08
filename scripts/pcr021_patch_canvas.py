#!/usr/bin/env python3
"""
pcr021_patch_canvas.py — Phase 5 patcher: Canvas Linking.

Does three things:
  1. Adds /canvas route to src/runtime/app.py
     (mounts existing static/murphy-work-canvas.html)
  2. Adds <script src="/static/components/murphy-readout.js"> to
     murphy-work-canvas.html (before </head>)
  3. Adds a small "Attached Results" sidebar to the canvas body that
     hosts <murphy-readout result-id="..."> tiles
  4. Archives r427_op_canvas.html with a deprecation sentinel comment
     (does NOT delete — leaves file in place for git history; replaces
      first comment block with a "deprecated, see murphy-work-canvas.html")

Idempotent. Marker-based.

Operating rules held:
  - Snapshot before run (state_snapshots/PCR-021_pre/)
  - Tight security sweep (L29)
  - No set -e (L30)
"""

from __future__ import annotations
import argparse
import re
import sys
from pathlib import Path

APP_PY = Path("/opt/Murphy-System/src/runtime/app.py")
WORK_CANVAS = Path("/opt/Murphy-System/static/murphy-work-canvas.html")
R427_CANVAS = Path("/opt/Murphy-System/static/r427_op_canvas.html")

APP_MARKER_BEGIN = "# === PCR-021 BEGIN canvas route ==="
APP_MARKER_END = "# === PCR-021 END canvas route ==="

CANVAS_ROUTE_HANDLER = '''
    # === PCR-021 BEGIN canvas route ===
    @app.get("/canvas", include_in_schema=False)
    async def _pcr021_canvas_page():
        """
        Live Work Canvas (PCR-021 / Phase 5).
        Mounts the existing murphy-work-canvas.html as the canonical
        canvas surface. r427_op_canvas.html is deprecated (sentinel
        comment added; file kept for git history).
        """
        from fastapi.responses import FileResponse as _FR
        return _FR("/opt/Murphy-System/static/murphy-work-canvas.html",
                   media_type="text/html")
    # === PCR-021 END canvas route ===
'''

# Canvas HTML — inject readout component script + attachments sidebar
CANVAS_SCRIPT_TAG = '<script src="/static/components/murphy-readout.js"></script>'

# This goes near the top of <body>, as a togglable sidebar
CANVAS_ATTACHMENTS_BLOCK = '''
<!-- === PCR-021 BEGIN canvas attachments === -->
<div id="canvas-attachments" style="position:fixed;right:14px;top:60px;width:340px;max-height:80vh;overflow:auto;background:rgba(11,17,24,.96);border:1px solid #2a2a2a;border-radius:10px;padding:12px;z-index:50;display:none;box-shadow:0 4px 30px rgba(0,0,0,.55);">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
    <div style="color:#ff5a00;font-size:12px;text-transform:uppercase;letter-spacing:1px;font-weight:600;">Attached Results</div>
    <div>
      <button onclick="canvasCompareSelected()" style="background:none;border:1px solid #2a2a2a;color:#7aa2f7;font-size:11px;padding:3px 8px;border-radius:4px;cursor:pointer;margin-right:4px;">Compare</button>
      <button onclick="canvasToggleAttachments()" style="background:none;border:none;color:#6b7787;font-size:18px;cursor:pointer;">×</button>
    </div>
  </div>
  <div id="canvas-attachments-list" style="display:flex;flex-direction:column;gap:6px;">
    <div style="color:#6b7787;font-style:italic;font-size:12px;">No results attached yet.</div>
  </div>
  <div id="canvas-compare-pane" style="display:none;margin-top:14px;padding-top:14px;border-top:1px solid #2a2a2a;">
    <div style="color:#789;font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;">Compare</div>
    <div id="canvas-compare-content"></div>
  </div>
</div>
<button id="canvas-attachments-toggle" onclick="canvasToggleAttachments()" style="position:fixed;right:14px;top:14px;background:#181818;border:1px solid #2a2a2a;color:#ff5a00;padding:6px 12px;border-radius:6px;cursor:pointer;font-size:12px;z-index:51;">📎 Results</button>
<script>
  // Canvas attachment API (PCR-021 / Phase 5)
  window.canvasAttachments = window.canvasAttachments || [];

  function canvasToggleAttachments() {
    var el = document.getElementById('canvas-attachments');
    el.style.display = (el.style.display === 'none' || !el.style.display) ? 'block' : 'none';
  }
  function canvasAttachResult(resultId, label) {
    if (window.canvasAttachments.some(a => a.id === resultId)) return;
    window.canvasAttachments.push({ id: resultId, label: label || resultId });
    canvasRenderAttachments();
  }
  function canvasRemoveResult(resultId) {
    window.canvasAttachments = window.canvasAttachments.filter(a => a.id !== resultId);
    canvasRenderAttachments();
  }
  function canvasRenderAttachments() {
    var list = document.getElementById('canvas-attachments-list');
    if (!window.canvasAttachments.length) {
      list.innerHTML = '<div style="color:#6b7787;font-style:italic;font-size:12px;">No results attached yet.</div>';
      return;
    }
    list.innerHTML = window.canvasAttachments.map(a =>
      '<div style="position:relative;">' +
        '<murphy-readout result-id="' + a.id.replace(/[&<>"']/g, '') + '"></murphy-readout>' +
        '<button onclick="canvasRemoveResult(\\'' + a.id.replace(/[&<>"\\']/g, '') + '\\')" ' +
        'style="position:absolute;top:6px;right:6px;background:none;border:none;color:#6b7787;cursor:pointer;font-size:14px;">×</button>' +
      '</div>'
    ).join('');
  }
  function canvasCompareSelected() {
    var pane = document.getElementById('canvas-compare-pane');
    var content = document.getElementById('canvas-compare-content');
    if (window.canvasAttachments.length < 2) {
      pane.style.display = 'block';
      content.innerHTML = '<div style="color:#f0b86e;font-size:12px;">Need at least 2 attached results to compare.</div>';
      return;
    }
    pane.style.display = 'block';
    var pair = window.canvasAttachments.slice(0, 2);
    content.innerHTML =
      '<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">' +
        '<div><div style="color:#789;font-size:10px;margin-bottom:4px;">A</div>' +
          '<murphy-readout result-id="' + pair[0].id.replace(/[&<>"']/g, '') + '" expanded="1"></murphy-readout></div>' +
        '<div><div style="color:#789;font-size:10px;margin-bottom:4px;">B</div>' +
          '<murphy-readout result-id="' + pair[1].id.replace(/[&<>"']/g, '') + '" expanded="1"></murphy-readout></div>' +
      '</div>';
  }
  // Demo: attach the preview readout once on load so the panel isn't empty
  // in dev. Real attaches will come from user actions (drag-drop or button click).
  document.addEventListener('DOMContentLoaded', function() {
    if (window.location.search.indexOf('demo=1') !== -1) {
      canvasAttachResult('preview', 'Demo readout');
      canvasToggleAttachments();
    }
  });
</script>
<!-- === PCR-021 END canvas attachments === -->
'''

# Sentinel for deprecating r427
R427_SENTINEL = '''<!--
  === DEPRECATED (PCR-021 / Phase 5, 2026-06-08) ===
  This canvas surface has been consolidated into:
    /static/murphy-work-canvas.html  (route: /canvas)
  This file is kept for git history. Do not link to it from new UI.
  If you must serve it, do so under a new path, not /canvas.
  =================================================
-->
'''


def patch_app_py(verify=False, revert=False):
    if not APP_PY.exists():
        return False, f"app.py missing: {APP_PY}"
    text = APP_PY.read_text(encoding="utf-8")
    has_marker = APP_MARKER_BEGIN in text

    if verify:
        return (has_marker,
                "  ✓ /canvas route patched" if has_marker
                else "  ✗ /canvas route NOT in app.py")

    if revert:
        if not has_marker:
            return True, "  · no patch to revert"
        pat = re.compile(re.escape(APP_MARKER_BEGIN) + r".*?" +
                         re.escape(APP_MARKER_END) + r"\n?", re.DOTALL)
        APP_PY.write_text(pat.sub("", text), encoding="utf-8")
        return True, "  ✓ reverted /canvas route"

    if has_marker:
        return True, "  · already patched (idempotent)"

    # Anchor near the /marketplace existing route (Phase 4b added 4 routes
    # near this anchor; we add Phase 5's near the same anchor)
    anchor = '@app.get("/marketplace", include_in_schema=False)'
    if anchor in text:
        new_text = text.replace(anchor,
                                CANVAS_ROUTE_HANDLER.lstrip("\n") + "\n    " + anchor)
        APP_PY.write_text(new_text, encoding="utf-8")
        return True, "  ✓ /canvas route inserted near /marketplace anchor"
    APP_PY.write_text(text + "\n" + CANVAS_ROUTE_HANDLER + "\n", encoding="utf-8")
    return True, "  ✓ /canvas route appended"


def patch_work_canvas(verify=False, revert=False):
    notes = []
    if not WORK_CANVAS.exists():
        return False, ["murphy-work-canvas.html missing"]
    text = WORK_CANVAS.read_text(encoding="utf-8", errors="replace")
    has_script = CANVAS_SCRIPT_TAG in text
    has_attachments_marker = "<!-- === PCR-021 BEGIN canvas attachments ===" in text

    if verify:
        notes.append("  " + ("✓" if has_script else "✗") + " readout script tag")
        notes.append("  " + ("✓" if has_attachments_marker else "✗") + " attachments block")
        return (has_script and has_attachments_marker), notes

    if revert:
        if has_script:
            text = text.replace(CANVAS_SCRIPT_TAG + "\n", "").replace(CANVAS_SCRIPT_TAG, "")
            notes.append("  ✓ removed script tag")
        if has_attachments_marker:
            pat = re.compile(r"<!-- === PCR-021 BEGIN canvas attachments ===.*?<!-- === PCR-021 END canvas attachments === -->\n?",
                             re.DOTALL)
            text = pat.sub("", text)
            notes.append("  ✓ removed attachments block")
        WORK_CANVAS.write_text(text, encoding="utf-8")
        return True, notes

    # Insert script tag before </head>
    if not has_script:
        if "</head>" in text:
            text = text.replace("</head>", CANVAS_SCRIPT_TAG + "\n</head>", 1)
            notes.append("  ✓ inserted readout script tag before </head>")
        else:
            notes.append("  · no </head>; appending at top")
            text = CANVAS_SCRIPT_TAG + "\n" + text
    else:
        notes.append("  · script tag already present")

    # Insert attachments block right after <body>
    if not has_attachments_marker:
        if "<body>" in text:
            text = text.replace("<body>", "<body>\n" + CANVAS_ATTACHMENTS_BLOCK, 1)
            notes.append("  ✓ inserted attachments sidebar after <body>")
        else:
            notes.append("  · no <body> tag found; appending to end")
            text = text + "\n" + CANVAS_ATTACHMENTS_BLOCK
    else:
        notes.append("  · attachments block already present")

    WORK_CANVAS.write_text(text, encoding="utf-8")
    return True, notes


def patch_r427(verify=False, revert=False):
    if not R427_CANVAS.exists():
        return True, "  · r427 file already absent (nothing to deprecate)"
    text = R427_CANVAS.read_text(encoding="utf-8", errors="replace")
    has_sentinel = "PCR-021 / Phase 5" in text and "DEPRECATED" in text

    if verify:
        return (has_sentinel,
                "  ✓ r427 has deprecation sentinel" if has_sentinel
                else "  ✗ r427 not yet marked deprecated")

    if revert:
        if has_sentinel:
            text = text.replace(R427_SENTINEL, "")
            R427_CANVAS.write_text(text, encoding="utf-8")
        return True, "  ✓ r427 sentinel removed"

    if has_sentinel:
        return True, "  · r427 already deprecated (idempotent)"

    # Insert sentinel after <!DOCTYPE html> line, before <html>
    if "<!DOCTYPE" in text:
        text = re.sub(r"(<!DOCTYPE[^>]*>\n?)", r"\1" + R427_SENTINEL, text, count=1)
    else:
        text = R427_SENTINEL + text
    R427_CANVAS.write_text(text, encoding="utf-8")
    return True, "  ✓ r427 marked deprecated"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--revert", action="store_true")
    args = ap.parse_args()

    print(f"PCR-021 patcher verify={args.verify} revert={args.revert}")
    print("=" * 60)

    ok1, msg1 = patch_app_py(verify=args.verify, revert=args.revert)
    print("app.py:")
    if isinstance(msg1, list):
        for m in msg1: print(m)
    else:
        print(msg1)

    ok2, notes2 = patch_work_canvas(verify=args.verify, revert=args.revert)
    print("murphy-work-canvas.html:")
    for n in notes2: print(n)

    ok3, msg3 = patch_r427(verify=args.verify, revert=args.revert)
    print("r427_op_canvas.html:")
    print(msg3 if isinstance(msg3, str) else "\n".join(msg3))

    print("=" * 60)
    if ok1 and ok2 and ok3:
        print("  ✓ done")
        return 0
    print("  ✗ failed")
    return 2


if __name__ == "__main__":
    sys.exit(main())
