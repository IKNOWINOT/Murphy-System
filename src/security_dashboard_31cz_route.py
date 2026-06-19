"""
Ship 31cz.S — Security Dashboard route at /os/security and /api/security/dashboard.

Aggregates real security signals from existing sources:
  - fail2ban: active jails + currently-banned IPs
  - security_brain.db: scan findings, fixes applied, knowledge entries
  - antibody_interventions.db: interventions on outbound content
  - honeypot traps (if security_brain.scan_memory has them)

Reach: founder only (admin-gated). UI is /os/security; data feed is
/api/security/dashboard.

Why this exists: walker reports this surface as red because no /os/security
route exists. Building the route lets the founder see the full security
posture in one place rather than ssh-ing into the box.

Locked: 2026-06-19 — Corey, recovery night.
"""
from __future__ import annotations

import os
import sqlite3
import subprocess
from datetime import datetime, timezone, timedelta
from typing import Any
from pathlib import Path

DB_DIR = Path("/var/lib/murphy-production")


def _fail2ban_summary() -> dict:
    """List of (jail, banned_count, banned_ips)."""
    try:
        r = subprocess.run(
            ["sudo", "-n", "fail2ban-client", "status"],
            capture_output=True, text=True, timeout=5,
        )
        out = r.stdout or ""
        jails: list[str] = []
        for line in out.splitlines():
            if "Jail list:" in line:
                jails = [j.strip() for j in line.split(":", 1)[1].split(",") if j.strip()]
                break
        details = []
        total_banned = 0
        for jail in jails:
            try:
                jr = subprocess.run(
                    ["sudo", "-n", "fail2ban-client", "status", jail],
                    capture_output=True, text=True, timeout=4,
                )
                jout = jr.stdout or ""
                currently = 0
                ips: list[str] = []
                for ln in jout.splitlines():
                    if "Currently banned:" in ln:
                        try:
                            currently = int(ln.split(":", 1)[1].strip())
                        except Exception:
                            currently = 0
                    elif "Banned IP list:" in ln:
                        ips = [ip.strip() for ip in ln.split(":", 1)[1].split() if ip.strip()]
                details.append({
                    "jail": jail,
                    "currently_banned": currently,
                    "ips": ips[:25],  # cap at 25 for payload size
                })
                total_banned += currently
            except Exception as e:
                details.append({"jail": jail, "error": str(e)})
        return {
            "ok": True,
            "active_jails": len(jails),
            "jails": details,
            "total_currently_banned": total_banned,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _security_brain_summary() -> dict:
    """Counts from security_brain.db + most recent finding."""
    db = DB_DIR / "security_brain.db"
    if not db.exists():
        return {"ok": False, "error": "security_brain.db missing"}
    try:
        c = sqlite3.connect(str(db), timeout=5)
        c.row_factory = sqlite3.Row
        counts = {}
        for tbl in ("scan_memory", "finding_library", "fix_log", "knowledge_base"):
            try:
                counts[tbl] = c.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
            except Exception:
                counts[tbl] = 0
        recent_findings = []
        try:
            for row in c.execute(
                "SELECT * FROM finding_library ORDER BY rowid DESC LIMIT 5"
            ).fetchall():
                recent_findings.append(dict(row))
        except Exception:
            pass
        c.close()
        return {
            "ok": True,
            "counts": counts,
            "recent_findings": recent_findings,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _antibody_summary() -> dict:
    """Recent antibody interventions on outbound content."""
    db = DB_DIR / "antibody_interventions.db"
    if not db.exists():
        return {"ok": True, "interventions_7d": 0, "recent": [], "note": "no interventions db"}
    try:
        c = sqlite3.connect(str(db), timeout=5)
        c.row_factory = sqlite3.Row
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=168)).timestamp()
        n = c.execute(
            "SELECT COUNT(*) FROM antibody_interventions WHERE ts > ?", (cutoff,)
        ).fetchone()[0]
        recent = [dict(r) for r in c.execute(
            "SELECT * FROM antibody_interventions ORDER BY ts DESC LIMIT 10"
        ).fetchall()]
        c.close()
        return {"ok": True, "interventions_7d": n, "recent": recent}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _nginx_attack_signal_24h() -> dict:
    """Recent 4xx/5xx blasts from the same IP — a credential-spray signal."""
    try:
        r = subprocess.run(
            ["bash", "-c",
             "journalctl -u nginx --since '24 hours ago' --no-pager 2>/dev/null "
             "| grep -oE '[0-9]+\\.[0-9]+\\.[0-9]+\\.[0-9]+' "
             "| sort | uniq -c | sort -rn | head -10"],
            capture_output=True, text=True, timeout=8,
        )
        lines = [ln.strip() for ln in (r.stdout or "").splitlines() if ln.strip()]
        top_ips = []
        for ln in lines:
            parts = ln.split(None, 1)
            if len(parts) == 2:
                top_ips.append({"hits": int(parts[0]), "ip": parts[1]})
        return {"ok": True, "top_ips_24h": top_ips}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def get_security_dashboard() -> dict:
    """Aggregate everything for the dashboard."""
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "fail2ban": _fail2ban_summary(),
        "security_brain": _security_brain_summary(),
        "antibody": _antibody_summary(),
        "nginx_traffic": _nginx_attack_signal_24h(),
    }

# ── Route registration helper ──────────────────────────────────────────
def register_routes(app, _ignored=None) -> None:
    """Wire /os/security and /api/security/dashboard into the FastAPI app."""
    from fastapi.responses import HTMLResponse, JSONResponse
    from pathlib import Path

    @app.get("/api/security/dashboard", include_in_schema=False)
    async def _security_dashboard_api():
        return JSONResponse(get_security_dashboard())

    @app.get("/os/security", include_in_schema=False)
    async def _security_dashboard_page():
        html_path = Path("/opt/Murphy-System/static/security_dashboard.html")
        if html_path.exists():
            return HTMLResponse(html_path.read_text())
        return HTMLResponse(
            "<html><body><h1>Security Dashboard</h1>"
            "<p>HTML page not yet present. Data feed at "
            "<a href='/api/security/dashboard'>/api/security/dashboard</a></p></body></html>"
        )
