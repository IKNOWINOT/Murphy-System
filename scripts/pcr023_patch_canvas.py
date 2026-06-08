#!/usr/bin/env python3
"""
pcr023_patch_canvas.py — PCR-023 / Phase 6b: canvas hotspot overlay.

Adds a small <script> to murphy-work-canvas.html that polls
/api/canvas/hotspots and auto-attaches a <murphy-readout> for each
flag. Idempotent. Marker-based.
"""

from __future__ import annotations
import argparse
import re
import sys
from pathlib import Path

CANVAS = Path("/opt/Murphy-System/static/murphy-work-canvas.html")
MARKER_BEGIN = "<!-- === PCR-023 BEGIN canvas hotspot overlay === -->"
MARKER_END = "<!-- === PCR-023 END canvas hotspot overlay === -->"

OVERLAY = f'''
{MARKER_BEGIN}
<script>
(function() {{
  // PCR-023 / Phase 6b: poll bottleneck flags and surface as canvas attachments
  if (window.canvasHotspotsActive) return;
  window.canvasHotspotsActive = true;
  async function loadHotspots() {{
    try {{
      const r = await fetch('/api/canvas/hotspots', {{ credentials: 'include' }});
      if (r.status === 401) return; // not owner; silent
      const data = await r.json();
      const seen = new Set((window.canvasAttachments || []).map(a => a.id));
      (data.hotspots || []).forEach(h => {{
        if (h.id && !seen.has(h.id)) {{
          if (typeof window.canvasAttachResult === 'function') {{
            window.canvasAttachResult(h.id, h.label || h.id);
          }}
        }}
      }});
    }} catch (e) {{}}
  }}
  // First poll at 10s (let page settle), then every 5 min
  setTimeout(loadHotspots, 10000);
  setInterval(loadHotspots, 5 * 60 * 1000);
}})();
</script>
{MARKER_END}
'''


def patch(verify=False, revert=False):
    text = CANVAS.read_text(encoding="utf-8", errors="replace")
    has = MARKER_BEGIN in text
    if verify:
        return has, "  ✓ canvas hotspot overlay present" if has else "  ✗ overlay missing"
    if revert:
        if not has:
            return True, "  · nothing to revert"
        pat = re.compile(re.escape(MARKER_BEGIN) + r".*?" +
                         re.escape(MARKER_END) + r"\n?", re.DOTALL)
        CANVAS.write_text(pat.sub("", text), encoding="utf-8")
        return True, "  ✓ reverted"
    if has:
        return True, "  · already patched (idempotent)"
    # Insert right before </body>
    if "</body>" in text:
        text = text.replace("</body>", OVERLAY + "\n</body>", 1)
    else:
        text = text + "\n" + OVERLAY
    CANVAS.write_text(text, encoding="utf-8")
    return True, "  ✓ overlay inserted before </body>"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--revert", action="store_true")
    args = ap.parse_args()
    print(f"PCR-023 canvas patcher verify={args.verify} revert={args.revert}")
    print("=" * 60)
    ok, msg = patch(verify=args.verify, revert=args.revert)
    print(msg)
    print("=" * 60)
    print("  ✓ done" if ok else "  ✗ failed")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
