#!/usr/bin/env python3
"""
PATCH-WALKER-CLI-001 (2026-05-28 R81) — Keyboard-driven HITL review walker

WHAT THIS IS:
  A terminal-driven walker UI that calls the R75/R79/R80 walker HTTP API.
  Reviewer presses one key per item to verify/flag/skip/snooze/rewind/quit.
  Each item displays in full context with the action menu beneath it.

WHY IT EXISTS:
  R74 built the walker substrate. R75-R80 built the HTTP API around it.
  Until Phase D UI ships, this CLI is the actual review UX Corey can USE.
  Tests the HTTP API surface (R59 organic evidence) AND gives the user
  immediate value before Phase D.

USAGE:
  python3 walker_cli.py [--reviewer corey] [--limit N] [--kind KIND]
  
KEYBINDS (single keypress):
  v - verify (looks correct)
  f - flag (open feedback ticket)
  s - suggest (flag with correction note)  
  k - skip (return later)
  z - snooze (advance, don't show today)
  r - rewind one item
  p - show progress summary
  q - quit

DEPENDS ON:
  - /api/hitl/walker/next     (R75)
  - /api/hitl/walker/decision (R75)
  - /api/hitl/walker/progress (R75/R80)
  - /api/hitl/walker/rewind   (R75)

NO IMPORTS from src.hitl_review_walker — uses HTTP exclusively (R81
loose coupling per Murphy meta-Q). This validates the public API
surface; if HTTP fails, the CLI fails — which is the right signal.

LAST UPDATED: 2026-05-28 R81
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = os.environ.get("MURPHY_BASE", "http://127.0.0.1:8000")
# PATCH-CLI-KEY-FALLBACK-R87 — auth key from env, ~/.murphy_key, or /etc env file
def _resolve_api_key():
    k = os.environ.get("MURPHY_API_KEY", "").strip()
    if k:
        return k
    # Try /etc/murphy-production/environment (FOUNDER_API_KEY)
    try:
        with open("/etc/murphy-production/environment") as f:
            for line in f:
                line = line.strip()
                if line.startswith("FOUNDER_API_KEY="):
                    return line.split("=", 1)[1].strip()
                if line.startswith("MURPHY_API_KEY="):
                    return line.split("=", 1)[1].strip()
    except (OSError, IOError):
        pass
    # Try ~/.murphy_key
    try:
        home = os.path.expanduser("~")
        with open(os.path.join(home, ".murphy_key")) as f:
            k = f.read().strip()
            if k:
                return k
    except (OSError, IOError):
        pass
    return ""

KEY = _resolve_api_key()


def _request(method, path, body=None, timeout=20):
    # PATCH-CLI-HEADERS-R86 — add curl-equivalent headers so auth gate sees a
    # complete request. R85 Part 1c proved urllib with User-Agent + Accept = 200.
    url = BASE + path
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Murphy-WalkerCLI/1.0",
        "Accept": "application/json, */*",
    }
    if KEY:
        headers["X-API-Key"] = KEY
    data = None
    if body is not None:
        data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            err_body = e.read().decode()
        except Exception:
            err_body = ""
        return {"ok": False, "error": f"HTTP {e.code}: {err_body[:300]}"}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def get_next(reviewer, kinds=None):
    qs = "reviewer=" + urllib.parse.quote(reviewer)
    return _request("GET", f"/api/hitl/walker/next?{qs}")


def decision(reviewer, item_id, action, note=None):
    return _request("POST", "/api/hitl/walker/decision",
                    body={"reviewer": reviewer, "item_id": item_id,
                          "action": action, "note": note})


def progress(reviewer):
    qs = "reviewer=" + urllib.parse.quote(reviewer)
    return _request("GET", f"/api/hitl/walker/progress?{qs}")


def rewind(reviewer, items=1):
    return _request("POST", "/api/hitl/walker/rewind",
                    body={"reviewer": reviewer, "items": items})




def drill_evidence(trail_id):
    """PATCH-CLI-DRILL-R83 — drill from trail_id to evidence."""
    return _request("GET", "/api/hitl/walker/evidence/" + str(trail_id))

# ────────────────────────────────────────────────────────────────
# Display

def _color(s, c):
    if not sys.stdout.isatty():
        return s
    codes = {"red": "31", "green": "32", "yellow": "33", "blue": "34",
             "magenta": "35", "cyan": "36", "white": "37", "dim": "2",
             "bold": "1"}
    return f"\033[{codes.get(c, '0')}m{s}\033[0m"


def render_item(item, prog):
    raw = item.get("raw", {})
    kind = item.get("kind", "?")
    print()
    print(_color("═" * 70, "dim"))
    print(_color(f"{item.get('title','?')}", "bold"))
    print(_color(f"  {kind}  ·  {item.get('timestamp','?')}", "dim"))
    print(_color(f"  status: {item.get('status','?')}", "yellow" if item.get('status') in ("flagged","needs_review") else "dim"))
    print()
    print(item.get("summary", ""))
    print()

    if kind == "provenance_trail":
        print(_color("  source_kind:", "dim"), raw.get("source_kind", "?"))
        print(_color("  source_hint:", "dim"), raw.get("source_hint", "?"))
    elif kind == "gfo_augmentation":
        print(_color("  refusal_action:", "dim"), raw.get("action", "?"))
        print(_color("  refusal_target:", "dim"), raw.get("target", "?"))
        print(_color("  finding_ok:    ", "dim"), raw.get("finding_ok", "?"))
        if raw.get("finding_reason"):
            print(_color("  finding_reason:", "dim"), raw.get("finding_reason"))

    print()
    pn = (f"  [{prog.get('items_reviewed',0)} reviewed · "
          f"{prog.get('items_flagged',0)} flagged · "
          f"{prog.get('items_skipped',0)} skipped · "
          f"{prog.get('remaining',0)} remaining]")
    print(_color(pn, "cyan"))
    print()
    print(_color("  [v]erify  [f]lag  [s]uggest  s[k]ip  [z]snooze  [d]rill  [r]ewind  [p]rogress  [q]uit", "green"))


def render_progress(p):
    print()
    print(_color("═" * 70, "dim"))
    print(_color("  PROGRESS", "bold"))
    print(f"  reviewer:       {p.get('reviewer_id')}")
    print(f"  items_reviewed: {p.get('items_reviewed', 0)}")
    print(f"  items_flagged:  {p.get('items_flagged', 0)}")
    print(f"  items_skipped:  {p.get('items_skipped', 0)}")
    print(f"  remaining:      {p.get('remaining', 0)}")
    print(f"  cursor_at:      {p.get('cursor_at', '?')}")
    print(f"  last_active:    {p.get('last_active', '?')}")


def get_keypress():
    """Single-character input. Falls back to line input on non-tty."""
    if not sys.stdin.isatty():
        line = sys.stdin.readline()
        return line[:1] if line else ""
    try:
        import termios, tty
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
        return ch
    except Exception:
        return sys.stdin.readline()[:1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reviewer", default="corey", help="Reviewer ID")
    ap.add_argument("--limit", type=int, default=0, help="Max items this session (0=unlimited)")
    ap.add_argument("--once", action="store_true", help="Show one item and exit")
    args = ap.parse_args()

    print(_color(f"Walker — reviewer={args.reviewer}", "bold"))
    if args.once:
        nxt = get_next(args.reviewer)
        if not nxt.get("ok"):
            print(_color(f"ERROR: {nxt.get('error')}", "red"))
            return 1
        if nxt.get("item") is None:
            print(_color("No items pending.", "yellow"))
            return 0
        prog = progress(args.reviewer).get("progress", {})
        render_item(nxt["item"], prog)
        return 0

    handled = 0
    while True:
        if args.limit and handled >= args.limit:
            print(_color(f"\nReached limit of {args.limit}. Stopping.", "yellow"))
            break
        nxt = get_next(args.reviewer)
        if not nxt.get("ok"):
            print(_color(f"\nERROR: {nxt.get('error')}", "red"))
            return 1
        if nxt.get("item") is None:
            print(_color("\nNo more items pending. Done!", "green"))
            break
        prog = progress(args.reviewer).get("progress", {})
        render_item(nxt["item"], prog)
        key = get_keypress().lower()
        if key == "q":
            print(_color("\nBye.", "dim"))
            break
        elif key == "v":
            r = decision(args.reviewer, nxt["item"]["item_id"], "verify")
            print(_color(f"  ✓ verified", "green") if r.get("ok") else _color(f"  ✗ {r.get('error')}", "red"))
        elif key == "f":
            r = decision(args.reviewer, nxt["item"]["item_id"], "flag", note="flagged via CLI")
            print(_color(f"  ⚑ flagged + ticket opened", "yellow") if r.get("ok") else _color(f"  ✗ {r.get('error')}", "red"))
        elif key == "s":
            print(_color("  suggestion (one line): ", "cyan"), end="", flush=True)
            note = sys.stdin.readline().strip()
            r = decision(args.reviewer, nxt["item"]["item_id"], "suggest", note=note)
            print(_color(f"  ✎ suggestion recorded", "yellow") if r.get("ok") else _color(f"  ✗ {r.get('error')}", "red"))
        elif key == "k":
            r = decision(args.reviewer, nxt["item"]["item_id"], "skip")
            print(_color(f"  ↷ skipped", "dim") if r.get("ok") else _color(f"  ✗ {r.get('error')}", "red"))
        elif key == "z":
            r = decision(args.reviewer, nxt["item"]["item_id"], "snooze")
            if r.get("ok"):
                print(_color("  💤 snoozed", "dim"))
            else:
                print(_color("  ✗ " + str(r.get("error", "")), "red"))
        elif key == "d":
            # PATCH-CLI-DRILL-R83 — drill into trail evidence
            item_id = nxt["item"]["item_id"]
            if item_id.startswith("gfo_"):
                print(_color("  drill not implemented for gfo items", "yellow"))
            else:
                ev = drill_evidence(item_id)
                if ev.get("ok"):
                    print(_color("  ── DRILL ── evidence for trail ──", "cyan"))
                    prose_text = ev.get("prose", "")
                    print(_color("  " + prose_text, "white"))
                    snaps = ev.get("evidence_snapshots", []) or []
                    if snaps:
                        for i, e in enumerate(snaps[:3]):
                            kind = e.get("method", "?")
                            data = str(e.get("raw_data", ""))[:100]
                            print(_color("    [" + str(i+1) + "] method=" + str(kind) + ": " + data, "dim"))
                    else:
                        print(_color("  (no evidence matched this trail)", "dim"))
                else:
                    err = ev.get("error") or ev.get("detail") or ev.get("reason") or "unknown"
                    print(_color("  ✗ drill failed: " + str(err), "red"))
        elif key == "r":
            r = rewind(args.reviewer, 1)
            print(_color(f"  ⏪ rewound 1 item", "magenta") if r.get("ok") else _color(f"  ✗ {r.get('error')}", "red"))
        elif key == "p":
            p = progress(args.reviewer)
            render_progress(p.get("progress", {}))
        else:
            print(_color(f"  unknown key: {key!r} — try v/f/s/k/z/r/p/q", "red"))
        handled += 1

    final = progress(args.reviewer).get("progress", {})
    render_progress(final)
    return 0


if __name__ == "__main__":
    sys.exit(main())
