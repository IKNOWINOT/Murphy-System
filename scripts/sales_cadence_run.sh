#!/bin/bash
# R440 — Daily sales cadence wrapper.
# Replaces Base44 automation "Murphy Sales Engine — Daily Prospecting + Follow-up Cadence"
# Runs: prospecting cycle + follow-up cadence + heartbeat emit.
# Schedule: 16:00 UTC daily (= 09:00 PT).
#
# Sentinel: _R440_NATIVE_SALES_CADENCE
set -euo pipefail

LOG="/var/log/murphy/sales_cadence.log"
mkdir -p "$(dirname "$LOG")"
echo "── $(date -u +%FT%TZ) — R440 sales cadence starting ──" >> "$LOG"

cd /opt/Murphy-System

# Source vault key for any modules that need it (lead_prospector reads it)
if [ -f /etc/murphy/vault.env ]; then
    set -a; . /etc/murphy/vault.env; set +a
fi

# Run prospecting + followup + heartbeat in one Python process.
/opt/Murphy-System/venv/bin/python3 - <<'PY' 2>&1 | tee -a "$LOG"
import json, sys, time
sys.path.insert(0, "/opt/Murphy-System")

t0 = time.monotonic()
errors = []
result = {"stage": "start"}

try:
    from src.lead_prospector import run_prospecting_cycle, run_followup_cadence, get_stats
except Exception as e:
    print(f"FATAL import: {e}")
    sys.exit(2)

# Stage 1 — prospecting
try:
    prosp = run_prospecting_cycle(max_total=30)
    result["prospecting"] = prosp
    print(f"  prospecting: {json.dumps(prosp)[:300]}")
except Exception as e:
    errors.append(f"prospecting: {e}")
    print(f"  ✗ prospecting failed: {e}")

# Stage 2 — followup cadence
try:
    follow = run_followup_cadence()
    result["followup"] = follow
    print(f"  followup: {json.dumps(follow)[:300]}")
except Exception as e:
    errors.append(f"followup: {e}")
    print(f"  ✗ followup failed: {e}")

# Stage 3 — stats summary
try:
    result["stats"] = get_stats()
    print(f"  stats: {json.dumps(result['stats'])}")
except Exception as e:
    errors.append(f"stats: {e}")

# Stage 4 — cadence heartbeat
duration_ms = int((time.monotonic() - t0) * 1000)
try:
    from src.cadence_emit import emit_heartbeat
    emit_heartbeat(
        "murphy-sales-cadence.timer",
        duration_ms=duration_ms,
        success=(len(errors) == 0),
        error_text="; ".join(errors) if errors else None,
    )
    print(f"  heartbeat emitted: success={len(errors) == 0} dur={duration_ms}ms")
except Exception as e:
    print(f"  ✗ heartbeat emit failed: {e}")

sys.exit(0 if not errors else 1)
PY

EXIT=${PIPESTATUS[0]}
echo "── $(date -u +%FT%TZ) — R440 sales cadence done exit=$EXIT ──" >> "$LOG"
exit $EXIT
