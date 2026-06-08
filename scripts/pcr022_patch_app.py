#!/usr/bin/env python3
"""
pcr022_patch_app.py — PCR-022 / Phase 6a patcher.

Adds GET /api/bottleneck/flags to src/runtime/app.py.

The endpoint reads /var/lib/murphy-production/bottleneck_flags.json
(written by src/bottleneck_monitor.py running on a systemd timer) and
returns it as JSON. Owner-only (same pattern as /api/provenance from
PCR-020).

Idempotent. Marker-based, --revert capable.
"""

from __future__ import annotations
import argparse
import re
import sys
from pathlib import Path

APP_PY = Path("/opt/Murphy-System/src/runtime/app.py")
MARKER_BEGIN = "# === PCR-022 BEGIN bottleneck flags route ==="
MARKER_END = "# === PCR-022 END bottleneck flags route ==="

FLAGS_HANDLER = '''
    # === PCR-022 BEGIN bottleneck flags route ===
    @app.get("/api/bottleneck/flags")
    async def _pcr022_bottleneck_flags(request: Request):
        """
        Bottleneck monitor read endpoint. Returns the latest flag set
        as written by src/bottleneck_monitor.py.

        Owner-only (founder email or same-host). If the monitor has
        never run, returns an empty payload instead of 404.
        """
        import json, os
        from pathlib import Path as _Path
        _founder_email = os.environ.get("MURPHY_FOUNDER_EMAIL", "cpost@murphy.systems")
        _caller_email = None
        try:
            _caller_email = request.headers.get("x-murphy-user")
        except Exception:
            pass
        _is_founder = bool(_caller_email) and _caller_email == _founder_email
        if not _is_founder:
            try:
                _host = (request.client.host if request.client else "") or ""
                _is_founder = _host in ("127.0.0.1", "::1")
            except Exception:
                pass
        if not _is_founder:
            return JSONResponse({"error": "owner_only"}, status_code=401)

        flags_path = _Path("/var/lib/murphy-production/bottleneck_flags.json")
        if not flags_path.exists():
            return JSONResponse({
                "generated_at": None,
                "window_minutes": 0,
                "flags": [],
                "flag_count": 0,
                "stats": {},
                "phase": "6a (read-only)",
                "note": "monitor has not yet produced output; check systemd timer murphy-bottleneck-monitor.timer",
            })
        try:
            with flags_path.open("r", encoding="utf-8") as f:
                return JSONResponse(json.load(f))
        except Exception as e:
            return JSONResponse({"error": "read_failed", "detail": str(e)[:200]},
                                status_code=500)
    # === PCR-022 END bottleneck flags route ===
'''


def patch_app_py(verify=False, revert=False):
    if not APP_PY.exists():
        return False, f"app.py missing: {APP_PY}"
    text = APP_PY.read_text(encoding="utf-8")
    has = MARKER_BEGIN in text

    if verify:
        return has, ("  ✓ bottleneck flags route patched" if has
                     else "  ✗ NOT patched")
    if revert:
        if not has:
            return True, "  · nothing to revert"
        pat = re.compile(re.escape(MARKER_BEGIN) + r".*?" +
                         re.escape(MARKER_END) + r"\n?", re.DOTALL)
        APP_PY.write_text(pat.sub("", text), encoding="utf-8")
        return True, "  ✓ reverted"
    if has:
        return True, "  · already patched (idempotent)"
    anchor = '@app.get("/api/self/audit")'
    if anchor in text:
        new_text = text.replace(anchor,
                                FLAGS_HANDLER.lstrip("\n") + "\n    " + anchor)
        APP_PY.write_text(new_text, encoding="utf-8")
        return True, "  ✓ inserted before /api/self/audit anchor"
    APP_PY.write_text(text + "\n" + FLAGS_HANDLER + "\n", encoding="utf-8")
    return True, "  ✓ appended (no anchor)"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--revert", action="store_true")
    args = ap.parse_args()
    print(f"PCR-022 patcher verify={args.verify} revert={args.revert}")
    print("=" * 60)
    ok, msg = patch_app_py(verify=args.verify, revert=args.revert)
    print("app.py:"); print(msg)
    print("=" * 60)
    print("  ✓ done" if ok else "  ✗ failed")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
