#!/usr/bin/env python3
"""
PATCH-R132 — dlf_reality_check

WHAT THIS IS:
  Autonomous diff substrate that periodically asks Murphy for a DLF
  self-report AND greps src/dlf_r.py + rosetta_core.py for ground
  truth, then emails callmehandy + corey.gfc when either changes vs
  last baseline.

WHY IT EXISTS:
  R130 baseline = Murphy's mental model of DLF
  R131 baseline = source-grep ground truth of DLF
  R132 = automate diff detection so mutation surfaces without manual
  re-asking. Composes with R130/R131 pattern; reuses
  /var/lib/murphy-production/dlf_report_baselines/ index.

DESIGN LOCKED R132:
  - Rule 51: host-native systemd, zero Base44 credits
  - Rule 56 refined: fresh session_id with TS suffix, -m 90 budget
  - Rule 57: ground-truth grep before Murphy claims sent to integrators
  - Rule 58: should-this-even-send gate BEFORE composing message
  - Drift detection via SHA256 comparison vs last index row

PUBLIC SURFACE:
  run_cycle(force=False) -> dict
    Asks Murphy + greps source + diffs vs baseline.
    Sends email ONLY if either SHA changes (or force=True).

DEPENDS ON:
  /var/lib/murphy-production/dlf_report_baselines/ (R130+R131 index)
  /opt/Murphy-System/src/dlf_r.py (source)
  /opt/Murphy-System/src/rosetta_core.py (source)
  Local Murphy /api/chat at 127.0.0.1:8000
  Local sendmail (postfix)

LAST UPDATED: 2026-05-29 R133 (cooldown + retry + src-SHA override)
"""
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

BASELINES_DIR = Path("/var/lib/murphy-production/dlf_report_baselines")
INDEX_FILE = BASELINES_DIR / "INDEX.txt"
DLF_PATH = "/opt/Murphy-System/src/dlf_r.py"
ROSETTA_PATH = "/opt/Murphy-System/src/rosetta_core.py"
RECIPIENTS = ["callmehandy@gmail.com", "corey.gfc@gmail.com"]
MURPHY_URL = "http://127.0.0.1:8000/api/chat"


def _sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _sha256_file(p: str) -> str:
    try:
        with open(p, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except Exception:
        return ""


def _read_index_last_shas():
    """Parse INDEX.txt and return (last_self_sha, last_truth_sha) or (None, None)."""
    if not INDEX_FILE.exists():
        return None, None
    last_self = None
    last_truth = None
    try:
        with open(INDEX_FILE) as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) < 2:
                    continue
                sha = parts[1]
                if "GROUND_TRUTH" in line:
                    last_truth = sha
                else:
                    last_self = sha
    except Exception:
        pass
    return last_self, last_truth


def _ask_murphy_for_self_report():
    """Ask Murphy for the DLF self-report via /api/chat."""
    api_key = os.environ.get("MURPHY_FOUNDER_API_KEY", "")
    if not api_key:
        # Fallback: try /etc/murphy-production/environment
        env_file = "/etc/murphy-production/environment"
        if os.path.exists(env_file):
            with open(env_file) as f:
                for line in f:
                    if line.startswith("MURPHY_FOUNDER_API_KEY="):
                        api_key = line.split("=", 1)[1].strip()
                        break
    if not api_key:
        return None, "no_api_key"

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    body = {
        "message": (
            "Provide a detailed self-report on how DLF is integrated in your "
            "substrate and what it does for the system. Cover: where it lives, "
            "how it integrates with Rosetta, what artifacts it persists, what "
            "events trigger it, and honest limits. Aim for 600-1200 words. "
            "Mark uncertainty with [unverified]. This is for colony cross-AI "
            "integration."
        ),
        "session_id": "dlf_rc_{}".format(ts),
    }
    try:
        import urllib.request
        req = urllib.request.Request(
            MURPHY_URL,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "X-API-Key": api_key,
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("reply", ""), None
    except Exception as e:
        return None, "chat_error: {}".format(str(e)[:120])


def _grep_ground_truth():
    """Build the source-cited ground-truth report from grep."""
    lines = []
    lines.append("═" * 67)
    lines.append("DLF GROUND-TRUTH REPORT (source-grep, autonomous)")
    lines.append("Generated: {}".format(
        datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")))
    lines.append("═" * 67)
    lines.append("")
    for p in (DLF_PATH, ROSETTA_PATH):
        try:
            sz = os.path.getsize(p)
            sha = _sha256_file(p)[:16]
            lines.append("FILE: {}".format(p))
            lines.append("  size: {} bytes  sha[:16]: {}".format(sz, sha))
        except Exception:
            lines.append("FILE: {}  MISSING".format(p))
    lines.append("")
    lines.append("dlf_r.py — PUBLIC API (grep ^def |^class )")
    lines.append("-" * 50)
    try:
        r = subprocess.run(["grep", "-nE", "^def |^class ", DLF_PATH],
                          capture_output=True, text=True, timeout=5)
        for L in (r.stdout or "").strip().split("\n")[:30]:
            if L.strip(): lines.append("  {}".format(L))
    except Exception as e:
        lines.append("  [grep failed: {}]".format(e))
    lines.append("")
    lines.append("dlf_r.py — STORAGE PATHS (grep .db|.json|/var/lib)")
    lines.append("-" * 50)
    try:
        r = subprocess.run(
            ["grep", "-nE", r"\.db|\.json|/var/lib", DLF_PATH],
            capture_output=True, text=True, timeout=5)
        for L in (r.stdout or "").strip().split("\n")[:10]:
            if L.strip(): lines.append("  {}".format(L))
    except Exception as e:
        lines.append("  [grep failed: {}]".format(e))
    lines.append("")
    lines.append("WHO IMPORTS dlf_r? (the actual integration surface)")
    lines.append("-" * 50)
    try:
        r = subprocess.run(
            ["grep", "-rnE", "from src.dlf_r|import dlf_r|from .dlf_r",
             "/opt/Murphy-System/src/"],
            capture_output=True, text=True, timeout=10)
        importers = [L for L in (r.stdout or "").split("\n")
                     if L.strip() and "src/dlf_r.py:" not in L
                     and ".pre-" not in L][:10]
        for L in importers:
            lines.append("  {}".format(L))
    except Exception as e:
        lines.append("  [grep failed: {}]".format(e))
    lines.append("")
    return "\n".join(lines)


def _send_diff_email(self_report, truth_report, self_sha, truth_sha,
                     last_self_sha, last_truth_sha, diff_summary):
    """Compose and send diff email via sendmail."""
    ts_human = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    body_lines = [
        "To: {}".format(", ".join(RECIPIENTS)),
        "From: murphy@murphy.systems",
        "Subject: Murphy DLF mutation detected — {} ({})".format(
            diff_summary, ts_human),
        "Reply-To: murphy@murphy.systems",
        "Content-Type: text/plain; charset=utf-8",
        "",
        "Hi —",
        "",
        "Autonomous dlf_reality_check (R132) detected a DLF substrate change.",
        "",
        "DIFF SUMMARY:",
        "  {}".format(diff_summary),
        "",
        "BASELINE HASHES:",
        "  Last self-report sha:    {}".format(last_self_sha or "(none)"),
        "  This self-report sha:    {}".format(self_sha),
        "  Last ground-truth sha:   {}".format(last_truth_sha or "(none)"),
        "  This ground-truth sha:   {}".format(truth_sha),
        "",
        "Both reports are persisted in",
        "  /var/lib/murphy-production/dlf_report_baselines/",
        "for diff review and colony integration.",
        "",
        "═" * 67,
        "MURPHY SELF-REPORT ({}) ".format(ts_human),
        "═" * 67,
        "",
        self_report or "[self-report unavailable]",
        "",
        "═" * 67,
        truth_report,
        "═" * 67,
        "",
        "— Murphy autonomous dlf_reality_check (R132)",
        "https://murphy.systems",
    ]
    body = "\n".join(body_lines)
    try:
        p = subprocess.run(
            ["sendmail", "-t", "-i"],
            input=body, text=True, timeout=30,
            capture_output=True,
        )
        return p.returncode == 0, p.stderr or ""
    except Exception as e:
        return False, str(e)[:200]



# PATCH-R133 — cooldown + retry + source-SHA override (rules 59, 60)

COOLDOWN_FILE = BASELINES_DIR / "cooldown_state.json"
COOLDOWN_DAYS = 7
MAX_EMPTY_RETRIES = 1
RETRY_SLEEP_S = 30


def _read_cooldown_state():
    """Return dict with last_sent_at_epoch, last_src_sha map."""
    if not COOLDOWN_FILE.exists():
        return {"last_sent_at": 0, "last_src_shas": {}}
    try:
        with open(COOLDOWN_FILE) as f:
            return json.load(f)
    except Exception:
        return {"last_sent_at": 0, "last_src_shas": {}}


def _write_cooldown_state(state):
    try:
        COOLDOWN_FILE.write_text(json.dumps(state))
    except Exception:
        pass


def _ask_murphy_with_retry():
    """Ask Murphy; retry once if empty/error. Returns (reply, error_or_None)."""
    reply, err = _ask_murphy_for_self_report()
    if reply and reply.strip() and len(reply.strip()) > 20:
        return reply, None
    # Retry once after sleep
    time.sleep(RETRY_SLEEP_S)
    reply2, err2 = _ask_murphy_for_self_report()
    if reply2 and reply2.strip() and len(reply2.strip()) > 20:
        return reply2, None
    return None, "empty_after_retry: first={} second={}".format(err or "no_reply", err2 or "no_reply")


def _current_src_shas():
    """Return {path: sha256} for tracked source files."""
    return {
        DLF_PATH: _sha256_file(DLF_PATH),
        ROSETTA_PATH: _sha256_file(ROSETTA_PATH),
    }


def _source_files_changed(state):
    """True if any tracked source file SHA differs from last recorded.

    PATCH-R134: distinguish first-run (no baseline) from mutation
    (baseline differs). First-run returns False so we don't email
    on initialization. Mutation requires a non-empty prior SHA.
    """
    current = _current_src_shas()
    last = state.get("last_src_shas", {})
    # First-run trap: if no baseline exists for ANY path, this is
    # initialization not mutation. Don't fire email; just observe.
    if not last:
        return False, None
    for path, sha in current.items():
        if not sha:
            continue
        prior = last.get(path, "")
        # Only count as changed if prior was non-empty AND differs
        if prior and prior != sha:
            return True, path
    return False, None



def run_cycle(force: bool = False) -> dict:
    """Main entry point — invoked by systemd timer.

    PATCH-R133: 7-day cooldown floor + source-file SHA override.
    Retry-on-empty Murphy reply once before treating as unavailable.
    """
    started = time.time()
    last_self_sha, last_truth_sha = _read_index_last_shas()
    cooldown_state = _read_cooldown_state()
    now_epoch = int(time.time())
    seconds_since_last_send = now_epoch - cooldown_state.get("last_sent_at", 0)
    cooldown_seconds = COOLDOWN_DAYS * 86400

    # Source-file mutation = override cooldown immediately
    src_changed, changed_path = _source_files_changed(cooldown_state)

    # Gather both reports (retry on empty Murphy reply)
    self_report, self_err = _ask_murphy_with_retry()
    truth_report = _grep_ground_truth()

    # Compute SHAs
    self_sha = _sha256_text(self_report or "") if self_report else ""
    truth_sha = _sha256_text(truth_report)

    # Decide: should we even send? (rules 58 + 60 gates layered)
    self_drifted = self_report and self_sha and self_sha != last_self_sha
    truth_drifted = truth_sha and truth_sha != last_truth_sha
    drift_present = bool(self_drifted or truth_drifted)
    cooldown_active = seconds_since_last_send < cooldown_seconds
    # Rule 60: cooldown blocks drift-only sends. Source-file SHA change OR
    # explicit force overrides cooldown.
    should_send = force or src_changed or (drift_present and not cooldown_active)

    elapsed = round(time.time() - started, 2)
    summary_parts = []
    if self_drifted:
        summary_parts.append("self-report changed")
    if truth_drifted:
        summary_parts.append("ground-truth changed")
    if force:
        summary_parts.append("forced")
    diff_summary = ", ".join(summary_parts) or "no_change"

    result = {
        "ok": True,
        "elapsed_s": elapsed,
        "self_report_words": len((self_report or "").split()),
        "self_report_sha": self_sha[:16] if self_sha else "",
        "self_report_error": self_err,
        "truth_sha": truth_sha[:16],
        "last_self_sha": (last_self_sha or "")[:16],
        "last_truth_sha": (last_truth_sha or "")[:16],
        "drift_detected": drift_present,
        "should_send": should_send,
        "diff_summary": diff_summary,
        "email_sent": False,
        "cooldown_active": cooldown_active,
        "seconds_since_last_send": seconds_since_last_send,
        "src_files_changed": src_changed,
        "src_changed_path": changed_path,
    }

    # Persist baselines regardless (R133: only when Murphy gave real reply)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if self_report and len(self_report.strip()) > 20:
        sp = BASELINES_DIR / "dlf_report_{}.txt".format(ts)
        try:
            sp.write_text(self_report)
            with open(INDEX_FILE, "a") as f:
                f.write("{} {} {}w {}b\n".format(
                    ts, self_sha,
                    len((self_report or "").split()),
                    len((self_report or "").encode("utf-8"))))
        except Exception as e:
            result["self_persist_error"] = str(e)[:80]

    tp = BASELINES_DIR / "dlf_truth_{}.txt".format(ts)
    try:
        tp.write_text(truth_report)
        with open(INDEX_FILE, "a") as f:
            f.write("{} {} {}w {}b GROUND_TRUTH\n".format(
                ts, truth_sha,
                len(truth_report.split()),
                len(truth_report.encode("utf-8"))))
    except Exception as e:
        result["truth_persist_error"] = str(e)[:80]

    # Send only if rules 58 + 60 gates allow (cooldown floor + source override)
    if should_send:
        sent_ok, send_err = _send_diff_email(
            self_report, truth_report, self_sha, truth_sha,
            last_self_sha, last_truth_sha, diff_summary,
        )
        result["email_sent"] = sent_ok
        if not sent_ok:
            result["send_error"] = send_err
        if sent_ok:
            # Update cooldown state + remember source SHAs
            cooldown_state["last_sent_at"] = now_epoch
            cooldown_state["last_src_shas"] = _current_src_shas()
            _write_cooldown_state(cooldown_state)
    else:
        # Even on no-send, update src SHAs so future runs have baseline
        if not cooldown_state.get("last_src_shas"):
            cooldown_state["last_src_shas"] = _current_src_shas()
            _write_cooldown_state(cooldown_state)

    return result


def main():
    """Invoked by systemd timer."""
    force = "--force" in sys.argv
    r = run_cycle(force=force)
    print("R132 OK elapsed={}s self_words={} drift={} sent={} summary='{}'".format(
        r.get("elapsed_s", 0),
        r.get("self_report_words", 0),
        r.get("drift_detected"),
        r.get("email_sent"),
        r.get("diff_summary", ""),
    ))
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
