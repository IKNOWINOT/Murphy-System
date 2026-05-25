#!/usr/bin/env python3
"""
PATCH-421 — Activate the Platform Self-Modification gateway
============================================================

WHAT THIS IS:
  Three small changes to make the already-mounted PSM gateway USABLE:

  1. Provision MURPHY_PLATFORM_OPERATOR_TOKEN in the env file so
     /launch can authenticate (currently returns 401 because the
     design fails closed when unconfigured — PSM-003 spec).

  2. Wire _get_orch in app.py to return a real SelfAutomationOrchestrator
     singleton instead of the hardcoded `lambda: None` (which makes
     every launch 503 even with a valid token).

  3. Leaves the rest of the safety stack EXACTLY as designed:
     - RSC pre-launch gate (already live via rsc_unified_sink proxy)
     - SelfEditLedger hash-chained immutable audit log
     - Operator token in constant-time compare
     - 401 / 409 / 503 / 422 / 202 status codes per PSM-003 contract

WHY IT EXISTS:
  Audit found PSM router is already mounted (PATCH-079d, line 24141 of
  app.py) but unusable:
    - /launch → 401 (no token configured)
    - /ledger → 200 (working, empty hash chain)
    - /console → 200 (working)
  The infrastructure is real; only the activation steps were missing.

HOW IT FITS:
  - Edits /etc/murphy-production/environment to set operator token
  - Edits /opt/Murphy-System/src/runtime/app.py to wire orchestrator
  - Service restart picks up both

LAST UPDATED: 2026-05-25 by PATCH-421
"""
import ast
import os
import secrets
import shutil
import subprocess
from pathlib import Path

NL = chr(10)

# ──────────────────────────────────────────────────────────────────
# Step 1: Provision operator token in environment file
# ──────────────────────────────────────────────────────────────────
ENV_FILE = Path("/etc/murphy-production/environment")
TOKEN_VAR = "MURPHY_PLATFORM_OPERATOR_TOKEN"
LEDGER_VAR = "MURPHY_PLATFORM_SELF_EDIT_LEDGER_PATH"
LEDGER_PATH = "/var/lib/murphy-production/platform_self_edit_ledger.jsonl"

env_text = ENV_FILE.read_text() if ENV_FILE.exists() else ""

if TOKEN_VAR in env_text:
    print(f"  ⚠ {TOKEN_VAR} already in env file — leaving alone")
    # Extract existing token to display fingerprint
    for line in env_text.splitlines():
        if line.startswith(f"{TOKEN_VAR}="):
            existing = line.split("=", 1)[1].strip()
            print(f"    fingerprint: {existing[:8]}...{existing[-4:]} ({len(existing)} chars)")
            break
else:
    # Generate a strong token — used to authorize self-modification launches
    new_token = "psm_" + secrets.token_urlsafe(32)
    lines = env_text.rstrip().splitlines() if env_text.strip() else []
    lines.append("")
    lines.append("# PATCH-421: PSM operator token (authorizes /api/platform/self-modification/launch)")
    lines.append(f"{TOKEN_VAR}={new_token}")
    lines.append(f"{LEDGER_VAR}={LEDGER_PATH}")
    ENV_FILE.write_text(NL.join(lines) + NL)
    os.chmod(ENV_FILE, 0o640)  # keep tight perms
    print(f"  ✓ {TOKEN_VAR} provisioned: psm_...{new_token[-6:]} ({len(new_token)} chars)")
    print(f"  ✓ {LEDGER_VAR} → {LEDGER_PATH}")

# Ensure ledger directory exists with correct ownership
ledger_dir = Path(LEDGER_PATH).parent
ledger_dir.mkdir(parents=True, exist_ok=True)
try:
    import pwd, grp
    murphy_uid = pwd.getpwnam("murphy").pw_uid
    murphy_gid = grp.getgrnam("murphy").gr_gid
    # Touch the file so the ledger can append on first launch
    Path(LEDGER_PATH).touch(exist_ok=True)
    os.chown(LEDGER_PATH, murphy_uid, murphy_gid)
    print(f"  ✓ ledger file owned by murphy:murphy")
except Exception as e:
    print(f"  ⚠ ledger ownership step failed (non-fatal): {e}")

# ──────────────────────────────────────────────────────────────────
# Step 2: Wire SelfAutomationOrchestrator into _get_orch
# ──────────────────────────────────────────────────────────────────
APP = Path("/opt/Murphy-System/src/runtime/app.py")
src = APP.read_text()

if "PATCH-421" in src:
    print("  ⚠ PATCH-421 marker already in app.py — skipping orchestrator wiring")
else:
    OLD = (
        "        def _get_orch():" + NL +
        "            return None  # orchestrator optional"
    )
    if OLD not in src:
        print("  ✗ Could not find the lambda-None orchestrator stub. Aborting.")
        raise SystemExit(1)

    NEW = (
        "        def _get_orch():" + NL +
        "            # PATCH-421: Wire real orchestrator instead of None." + NL +
        "            # Returns None gracefully if class can't load — PSM-003" + NL +
        "            # contract handles that as 503 (orchestrator_not_wired)." + NL +
        "            try:" + NL +
        "                from src.self_automation_orchestrator import SelfAutomationOrchestrator" + NL +
        "                # Singleton stash on the app object so we don't rebuild per request" + NL +
        "                if not hasattr(app.state, '_psm_orchestrator'):" + NL +
        "                    app.state._psm_orchestrator = SelfAutomationOrchestrator()" + NL +
        "                return app.state._psm_orchestrator" + NL +
        "            except Exception as _orch_exc:" + NL +
        "                import logging as _l" + NL +
        "                _l.getLogger('murphy.psm').warning(" + NL +
        "                    'PATCH-421: orchestrator unavailable: %s', _orch_exc)" + NL +
        "                return None"
    )

    new_src = src.replace(OLD, NEW, 1)
    ast.parse(new_src)
    print("  ✓ AST parses")

    backup = APP.with_suffix(".py.pre-421")
    shutil.copy(APP, backup)
    APP.write_text(new_src)
    print(f"  ✓ wrote {APP} (backup: {backup.name})")

print()
print("Activation:")
print("  systemctl restart murphy-production")
