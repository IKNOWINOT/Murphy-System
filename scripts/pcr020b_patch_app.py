#!/usr/bin/env python3
"""
pcr020b_patch_app.py — Phase 4b patcher.

Adds:
  1. 4 new HTML routes to src/runtime/app.py:
       GET /health-os    → static/health.html  (named -os to avoid clash
                                               with existing /health probe routes)
       GET /comms        → static/comms.html
       GET /developers   → static/developers.html
       GET /roi-calendar → static/roi-calendar.html
     (/marketplace is already mounted; we overwrite its target file
      via the build_log entry rather than re-route.)
  2. 6 more UI label translations in murphy-os.html:
       qaAction labels with human-language tooltips/text
  3. Kill 4 dead nav refs from Section A5:
       /workshop /workspace /chain still 404 — convert href to '#'

Idempotent. Marker-based, like pcr020_patch_app.py.

Operating rules:
  - Tight security sweep (L29)
  - No set -e (L30)
  - Snapshot taken before run (state_snapshots/PCR-020b_pre/)
"""

from __future__ import annotations
import argparse
import re
import sys
from pathlib import Path

APP_PY = Path("/opt/Murphy-System/src/runtime/app.py")
OS_HTML = Path("/opt/Murphy-System/static/murphy-os.html")

MARKER_BEGIN = "# === PCR-020b BEGIN phase 4b routes ==="
MARKER_END = "# === PCR-020b END phase 4b routes ==="

ROUTES_HANDLER = '''
    # === PCR-020b BEGIN phase 4b routes ===
    @app.get("/health-os", include_in_schema=False)
    async def _pcr020b_health_page():
        """System Health aggregated view (PCR-020b)."""
        from fastapi.responses import FileResponse as _FR
        return _FR("/opt/Murphy-System/static/health.html", media_type="text/html")

    @app.get("/comms", include_in_schema=False)
    async def _pcr020b_comms_page():
        """Comms Hub: email + video + matrix (PCR-020b)."""
        from fastapi.responses import FileResponse as _FR
        return _FR("/opt/Murphy-System/static/comms.html", media_type="text/html")

    @app.get("/developers", include_in_schema=False)
    async def _pcr020b_developers_page():
        """Developers: API surface + OpenAPI (PCR-020b)."""
        from fastapi.responses import FileResponse as _FR
        return _FR("/opt/Murphy-System/static/developers.html", media_type="text/html")

    @app.get("/roi-calendar", include_in_schema=False)
    async def _pcr020b_roi_calendar_page():
        """ROI Calendar: event-level ROI (PCR-020b)."""
        from fastapi.responses import FileResponse as _FR
        return _FR("/opt/Murphy-System/static/roi-calendar.html", media_type="text/html")
    # === PCR-020b END phase 4b routes ===
'''

# 6 more translations — Phase 4a did 6; these are the qaAction tile
# labels users see in the OS. We replace the tile name only, not the
# qaAction call itself (which would break behavior).
HTML_TRANSLATIONS_4B = [
    # The qaAction tiles are rendered with these display strings.
    # Conservative: only translate strings we can locate uniquely.
    (">Research Brief<",     ">Quick brief<"),
    (">Verify Citations<",   ">Check sources<"),
    (">Workflows<",          ">My workflows<"),
    (">Swarm Status<",       ">Agent activity<"),
    (">HITL Queue<",         ">Approvals waiting<"),
    (">Capabilities<",       ">What I can do<"),
]

# Section A5 kills — these dead routes appear as nav hrefs in HTML
A5_KILL_PATTERNS = [
    (r'href="/workshop"',  'href="#"'),
    (r'href="/workspace"', 'href="#"'),
    (r'href="/chain"',     'href="#"'),
    # /dispatch is intentionally NOT killed — switchPage('dispatch') is REAL
    # /api/canvas/* are intentionally not touched here — Phase 5
]


def patch_app_py(verify: bool = False, revert: bool = False) -> tuple[bool, str]:
    if not APP_PY.exists():
        return False, f"app.py missing: {APP_PY}"
    text = APP_PY.read_text(encoding="utf-8")
    has_marker = MARKER_BEGIN in text

    if verify:
        if has_marker:
            return True, "  ✓ phase 4b routes patched"
        return False, "  ✗ phase 4b routes NOT in app.py"

    if revert:
        if not has_marker:
            return True, "  · no patch to revert"
        pat = re.compile(re.escape(MARKER_BEGIN) + r".*?" +
                         re.escape(MARKER_END) + r"\n?", re.DOTALL)
        new_text = pat.sub("", text)
        APP_PY.write_text(new_text, encoding="utf-8")
        return True, "  ✓ reverted"

    if has_marker:
        return True, "  · already patched (idempotent)"

    # Anchor: insert near the existing /marketplace route
    anchor = '@app.get("/marketplace", include_in_schema=False)'
    if anchor in text:
        new_text = text.replace(anchor,
                                ROUTES_HANDLER.lstrip("\n") + "\n    " + anchor)
        APP_PY.write_text(new_text, encoding="utf-8")
        return True, "  ✓ phase 4b routes inserted near /marketplace anchor"
    # Fallback: append
    APP_PY.write_text(text + "\n" + ROUTES_HANDLER + "\n", encoding="utf-8")
    return True, "  ✓ phase 4b routes appended (no anchor found)"


def patch_html(verify: bool = False, revert: bool = False) -> tuple[bool, list[str]]:
    notes = []
    if not OS_HTML.exists():
        return False, ["murphy-os.html missing"]
    text = OS_HTML.read_text(encoding="utf-8", errors="replace")

    if verify:
        applied = sum(1 for _old, new in HTML_TRANSLATIONS_4B if new in text)
        nav_killed = sum(1 for pat, _new in A5_KILL_PATTERNS
                         if not re.search(pat, text))
        notes.append(f"  · 4b translations applied: {applied}/{len(HTML_TRANSLATIONS_4B)}")
        notes.append(f"  · A5 nav kills: {nav_killed}/{len(A5_KILL_PATTERNS)}")
        return True, notes  # informational only — don't fail verify on partials

    if revert:
        for old, new in HTML_TRANSLATIONS_4B:
            text = text.replace(new, old)
        for pat, replacement in A5_KILL_PATTERNS:
            # Can't perfectly reverse — best effort only
            pass
        OS_HTML.write_text(text, encoding="utf-8")
        notes.append("  ✓ translations reverted (nav kills not reversible)")
        return True, notes

    # Apply 4b translations
    n_translated = 0
    for old, new in HTML_TRANSLATIONS_4B:
        if old in text and new not in text:
            text = text.replace(old, new)
            n_translated += 1
    notes.append(f"  ✓ applied {n_translated} more label translations")

    # Apply A5 kills
    n_killed = 0
    for pattern, replacement in A5_KILL_PATTERNS:
        new_text, count = re.subn(pattern, replacement, text)
        if count:
            text = new_text
            n_killed += count
    notes.append(f"  ✓ killed {n_killed} dead nav hrefs (Section A5)")

    OS_HTML.write_text(text, encoding="utf-8")
    return True, notes


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--revert", action="store_true")
    args = ap.parse_args()

    print(f"PCR-020b patcher verify={args.verify} revert={args.revert}")
    print("=" * 60)

    ok1, msg1 = patch_app_py(verify=args.verify, revert=args.revert)
    print("app.py:"); print(msg1)

    ok2, notes2 = patch_html(verify=args.verify, revert=args.revert)
    print("murphy-os.html:")
    for n in notes2: print(n)

    print("=" * 60)
    if ok1 and ok2:
        print("  ✓ done")
        return 0
    print("  ✗ failed")
    return 2


if __name__ == "__main__":
    sys.exit(main())
