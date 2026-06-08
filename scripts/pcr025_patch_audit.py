#!/usr/bin/env python3
"""
pcr025_patch_audit.py — PCR-025 / Phase 7 patcher.

Hook src.provenance_writer.write_from_request into the audit middleware
so every meaningful HTTP request writes one result_provenance row.

Strategy (L35-safe):
  - Anchor on the END of register_audit_middleware() function body —
    a top-level scope, no try/except wrapper.
  - Append a guarded import + log line.
  - Inject the actual provenance call inside _write_event using a
    marker block placed at a known-good position (right after the
    audit row insert, before the function's natural end).

Idempotent. Marker-based. --revert capable.
"""

from __future__ import annotations
import argparse
import re
import sys
from pathlib import Path

TARGET = Path("/opt/Murphy-System/src/audit_middleware.py")

REGISTER_MARKER_BEGIN = "    # === PCR-025 BEGIN provenance writer init ==="
REGISTER_MARKER_END   = "    # === PCR-025 END provenance writer init ==="

REGISTER_BLOCK = f'''
{REGISTER_MARKER_BEGIN}
    try:
        from src import provenance_writer  # noqa: F401
        logger.info("audit_middleware: provenance_writer loaded (PCR-025)")
    except Exception as _e:
        logger.warning("audit_middleware: provenance_writer load failed: %s", _e)
{REGISTER_MARKER_END}
'''

# Hook inside _write_event — placed at the END of the method, after the
# existing audit-row INSERT. Failure here must NEVER raise upward.
WRITE_EVENT_MARKER_BEGIN = "        # === PCR-025 BEGIN provenance side-write ==="
WRITE_EVENT_MARKER_END   = "        # === PCR-025 END provenance side-write ==="

WRITE_EVENT_BLOCK = f'''
{WRITE_EVENT_MARKER_BEGIN}
        try:
            from src.provenance_writer import write_from_request as _pcr025_pw
            _pcr025_pw(
                path=path,
                method=method,
                status_code=status_code,
                latency_ms=latency_ms,
                actor=actor,
                body_hash=body_hash,
                response_size=response_size,
            )
        except Exception as _pcr025_e:
            logger.debug("provenance side-write failed: %s", _pcr025_e)
{WRITE_EVENT_MARKER_END}
'''


def patch_register(verify=False, revert=False):
    text = TARGET.read_text(encoding="utf-8")
    has = REGISTER_MARKER_BEGIN in text
    if verify:
        return has, ("  ✓ register init patched" if has
                     else "  ✗ register init NOT patched")
    if revert:
        if not has:
            return True, "  · nothing to revert"
        pat = re.compile(re.escape(REGISTER_MARKER_BEGIN) + r".*?" +
                         re.escape(REGISTER_MARKER_END) + r"\n?", re.DOTALL)
        TARGET.write_text(pat.sub("", text), encoding="utf-8")
        return True, "  ✓ reverted register init"
    if has:
        return True, "  · register init already patched (idempotent)"

    # Anchor: the existing logger.info call at end of register_audit_middleware
    anchor = '    logger.info("audit_middleware: registered for service=%s", service_name)'
    if anchor not in text:
        return False, "  ✗ anchor line not found"
    text = text.replace(anchor, anchor + REGISTER_BLOCK, 1)
    TARGET.write_text(text, encoding="utf-8")
    return True, "  ✓ inserted register init block"


def patch_write_event(verify=False, revert=False):
    text = TARGET.read_text(encoding="utf-8")
    has = WRITE_EVENT_MARKER_BEGIN in text
    if verify:
        return has, ("  ✓ _write_event side-write patched" if has
                     else "  ✗ _write_event side-write NOT patched")
    if revert:
        if not has:
            return True, "  · nothing to revert"
        pat = re.compile(re.escape(WRITE_EVENT_MARKER_BEGIN) + r".*?" +
                         re.escape(WRITE_EVENT_MARKER_END) + r"\n?", re.DOTALL)
        TARGET.write_text(pat.sub("", text), encoding="utf-8")
        return True, "  ✓ reverted _write_event side-write"
    if has:
        return True, "  · _write_event side-write already patched (idempotent)"

    # Anchor on the existing 'method' + 'path' lines that get computed
    # inside _write_event. We want to insert AFTER they're available.
    # The natural end-of-method anchor is hard because the function is
    # long. Easier: anchor on the existing
    #   'output_summary = _summarize_response(status_code, latency_ms, response_size)'
    # line, which is computed AFTER method/path/actor are set.
    anchor = "        output_summary = _summarize_response(status_code, latency_ms, response_size)"
    if anchor not in text:
        return False, "  ✗ _write_event anchor not found"
    text = text.replace(anchor, anchor + WRITE_EVENT_BLOCK, 1)
    TARGET.write_text(text, encoding="utf-8")
    return True, "  ✓ inserted _write_event side-write block"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--revert", action="store_true")
    args = ap.parse_args()
    print(f"PCR-025 patcher verify={args.verify} revert={args.revert}")
    print("=" * 60)
    ok1, msg1 = patch_register(verify=args.verify, revert=args.revert)
    print("register init:")
    print(msg1)
    ok2, msg2 = patch_write_event(verify=args.verify, revert=args.revert)
    print("_write_event side-write:")
    print(msg2)
    print("=" * 60)
    print("  ✓ done" if (ok1 and ok2) else "  ✗ failed")
    return 0 if (ok1 and ok2) else 2


if __name__ == "__main__":
    sys.exit(main())
