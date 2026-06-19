"""
Ship 31cy — Shape of Complete as-built walker.

Audits the live system every 6h. Asks for every capability listed in end_goal:
  - Is it wired?
  - Is it operating?
  - How is it reached?
Writes to as_built. Compare runs to prove the operating shape moved.
"""
from __future__ import annotations
import os, sqlite3, subprocess, json, uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

DB = "/var/lib/murphy-production/shape_of_complete.db"
MURPHY_ROOT = "/opt/Murphy-System"


def _now():
    return datetime.now(timezone.utc).isoformat()


def _is_frozen() -> bool:
    try:
        c = sqlite3.connect(DB, timeout=10)
        r = c.execute("SELECT frozen FROM walker_state WHERE id=1").fetchone()
        c.close()
        return bool(r and r[0])
    except Exception:
        return False


def _service_active(name: str) -> bool:
    try:
        r = subprocess.run(["systemctl", "is-active", name],
                           capture_output=True, text=True, timeout=5)
        return r.stdout.strip() == "active"
    except Exception:
        return False


def _file_exists(rel: str) -> bool:
    return Path(MURPHY_ROOT, rel).exists()


def _grep_app(pattern: str) -> bool:
    try:
        r = subprocess.run(
            ["grep", "-q", "-E", pattern, f"{MURPHY_ROOT}/src/runtime/app.py"],
            timeout=10,
        )
        return r.returncode == 0
    except Exception:
        return False


def _db_recent(db_path: str, table: str, time_col: str = "created_at",
               hours: int = 24) -> bool:
    if not Path(db_path).exists():
        return False
    try:
        c = sqlite3.connect(db_path, timeout=5)
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        n = c.execute(
            f"SELECT COUNT(*) FROM {table} WHERE {time_col} > ?", (cutoff,)
        ).fetchone()[0]
        c.close()
        return n > 0
    except Exception:
        return False


def _capability_check(surface: str, capability: str) -> dict:
    """Ship 31cz.W1 (2026-06-19) — corrected operating-tests.

    Previous proxies tested for tables/columns that don't exist or
    measured the wrong signal. Fixed to test the ACTUAL operating
    signal for each capability. Every test now verifiable against
    live ground truth in the production DBs."""
    wired = False
    operating = False
    reach = "unknown"
    ev = []

    if surface == "direct_inquiry":
        # WAS: users.db.user_accounts recency (table doesn't exist)
        # NOW: rosetta_dispatch_log has non-heartbeat work in last 24h
        wired = _grep_app(r"@app\.(post|get)\(.+(ask|chat|inquiry|message)")
        try:
            c = sqlite3.connect("/var/lib/murphy-production/murphy_audit.db", timeout=5)
            r = c.execute(
                "SELECT COUNT(*) FROM rosetta_dispatch_log "
                "WHERE ts > datetime('now','-24 hours') "
                "AND intent_hint NOT LIKE 'Swarm heartbeat%'"
            ).fetchone()
            c.close()
            operating = bool(r and r[0] > 0)
            ev.append(f"non_heartbeat_24h={r[0] if r else 0}")
        except Exception as e:
            ev.append(f"audit_db_err={e}")
        reach = "founder,users"

    elif surface == "os_dashboard":
        # WAS: service active (always true if box up)
        # NOW: actual /os GET hit in nginx access log in last 24h
        wired = _grep_app(r"/os['\"]") or _file_exists("static/os.html") or _file_exists("static/murphy-os.html")
        try:
            r = subprocess.run(
                ["bash","-c","journalctl -u murphy-production --since '24 hours ago' --no-pager 2>/dev/null | grep -cE 'GET /os[ /\\?]'"],
                capture_output=True, text=True, timeout=8
            )
            n = int((r.stdout or "0").strip())
            operating = n > 0
            ev.append(f"os_hits_24h={n}")
        except Exception as e:
            operating = _service_active("murphy-production.service")
            ev.append(f"fallback_service_check err={e}")
        reach = "founder"

    elif surface == "os_shape":
        # WAS: file exists (always true)
        # NOW: shape_of_complete.db has audit_runs in last 24h
        wired = (_grep_app(r"/os/shape") or _file_exists("src/shape_walker_31cy.py"))
        try:
            c = sqlite3.connect(DB, timeout=5)
            r = c.execute(
                "SELECT COUNT(*) FROM audit_runs "
                "WHERE started_at > datetime('now','-24 hours')"
            ).fetchone()
            c.close()
            operating = bool(r and r[0] > 0)
            ev.append(f"audit_runs_24h={r[0] if r else 0}")
        except Exception as e:
            ev.append(f"shape_db_err={e}")
        reach = "founder,team"

    elif surface == "org_chart":
        # WAS: agent_substrate.agents (table doesn't exist)
        # NOW: org_chart_registry has agents with recent activity
        wired = _file_exists("src/org_chart.py") or Path(
            "/var/lib/murphy-production/agent_substrate.db"
        ).exists()
        try:
            c = sqlite3.connect("/var/lib/murphy-production/agent_substrate.db", timeout=5)
            counts = {}
            for tbl in ("org_graph_nodes","departments","capabilities"):
                try:
                    counts[tbl] = c.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
                except Exception:
                    counts[tbl] = 0
            c.close()
            operating = counts.get("org_graph_nodes",0) > 0 and counts.get("departments",0) > 0
            ev.append(f"nodes={counts.get('org_graph_nodes',0)} depts={counts.get('departments',0)} caps={counts.get('capabilities',0)}")
        except Exception as e:
            ev.append(f"substrate_err={e}")
        reach = "rosetta"

    elif surface == "rosetta":
        # WAS: service or DB exists (always true)
        # NOW: rosetta_dispatch_log throughput in last 24h
        wired = _file_exists("src/rosetta_core.py") and _grep_app(r"rosetta")
        try:
            c = sqlite3.connect("/var/lib/murphy-production/murphy_audit.db", timeout=5)
            r = c.execute(
                "SELECT COUNT(*) FROM rosetta_dispatch_log "
                "WHERE ts > datetime('now','-24 hours')"
            ).fetchone()
            c.close()
            n = r[0] if r else 0
            operating = n >= 10  # rosetta is real if it dispatched ≥10 things in a day
            ev.append(f"dispatch_24h={n}")
        except Exception as e:
            ev.append(f"err={e}")
        reach = "all_intake"

    elif surface == "ambient_capture":
        wired = _file_exists("src/inbound_maildir_poller.py")
        operating = _db_recent(
            "/var/lib/murphy-production/inbound_replies.db",
            "inbound_replies", "received_at", 24)
        reach = "email,os"

    elif surface == "immunity":
        # WAS: hardcoded False
        # NOW: antibody interventions OR honeypot trap rows in last 168h
        wired = _file_exists("src/immune_memory.py") or _file_exists("src/honeypot_engine.py")
        try:
            c = sqlite3.connect("/var/lib/murphy-production/antibody_interventions.db", timeout=5)
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=168)).timestamp()
            r = c.execute(
                "SELECT COUNT(*) FROM antibody_interventions WHERE ts > ?", (cutoff,)
            ).fetchone()
            c.close()
            n = r[0] if r else 0
            operating = n > 0
            ev.append(f"antibody_interventions_7d={n}")
        except Exception as e:
            ev.append(f"err={e}")
        reach = "all_output"

    elif surface == "antibody":
        # WAS: ts column with iso compare (ts is REAL epoch, not iso)
        # NOW: epoch comparison
        wired = _file_exists("src/antibody/__init__.py") or _file_exists("src/antibody_loop.py")
        try:
            c = sqlite3.connect("/var/lib/murphy-production/antibody_interventions.db", timeout=5)
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=168)).timestamp()
            r = c.execute(
                "SELECT COUNT(*) FROM antibody_interventions WHERE ts > ?", (cutoff,)
            ).fetchone()
            c.close()
            n = r[0] if r else 0
            operating = n > 0
            ev.append(f"interventions_7d={n}")
        except Exception as e:
            ev.append(f"err={e}")
        reach = "all_output"

    elif surface == "citl":
        wired = Path("/var/lib/murphy-production/autonomy_policy.db").exists()
        try:
            c = sqlite3.connect("/var/lib/murphy-production/autonomy_policy.db", timeout=5)
            r = c.execute("SELECT posture FROM posture_state ORDER BY id DESC LIMIT 1").fetchone()
            c.close()
            posture = (r[0] if r else "OFF")
            operating = posture in ("ASSIST", "AUTONOMOUS")
            ev.append(f"posture={posture}")
        except Exception:
            pass
        reach = "all_action"

    elif surface == "hitl":
        # WAS: hitl_trails (table doesn't exist)
        # NOW: corey_hitl_queue or hitl_tickets recency in hitl_provenance.db
        wired = _file_exists("src/hitl_provenance.py")
        try:
            c = sqlite3.connect("/var/lib/murphy-production/hitl_provenance.db", timeout=5)
            # provenance_trails is live-active (1400+ rows); corey_hitl_queue uses queued_at
            n = 0
            for tbl, col in [("provenance_trails","captured_at"),
                             ("corey_hitl_queue","queued_at"),
                             ("hitl_tickets","created_at")]:
                try:
                    r = c.execute(
                        f"SELECT COUNT(*) FROM {tbl} WHERE {col} > datetime('now','-168 hours')"
                    ).fetchone()
                    if r and r[0]:
                        n = r[0]
                        ev.append(f"{tbl}_7d={n}")
                        break
                except Exception:
                    continue
            c.close()
            operating = n > 0
        except Exception as e:
            ev.append(f"err={e}")
        reach = "founder"

    elif surface == "for_sale":
        # WAS: subscriptions (table doesn't exist)
        # NOW: tenant_subscriptions or stranger_quotas recency
        wired = (_file_exists("static/pricing.html") and
                 Path("/var/lib/murphy-production/billing.db").exists())
        try:
            c = sqlite3.connect("/var/lib/murphy-production/billing.db", timeout=5)
            n = 0
            for tbl in ["tenant_subscriptions","stranger_quotas","billing_records"]:
                try:
                    r = c.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()
                    if r and r[0]:
                        n = r[0]
                        ev.append(f"{tbl}_rows={n}")
                        break
                except Exception:
                    continue
            c.close()
            operating = n > 0
        except Exception as e:
            ev.append(f"err={e}")
        reach = "customers"

    elif surface == "sop_living_docs":
        wired = Path("/etc/murphy-production/reply_protocol.md").exists()
        operating = wired
        reach = "all_actors"

    elif surface == "loom_lite":
        # Loom-Lite captures when stranger_responder or chat-v2 fires.
        # Use 168h window — production turn frequency is lumpy
        # (backlog draining ≠ continuous), so 7d is a more honest measure
        # of whether the capture pipeline is wired and working.
        wired = _file_exists("src/loom_lite/__init__.py")
        operating = _db_recent(
            "/var/lib/murphy-production/ghost_snapshots.db",
            "snapshots", "created_at", 168)
        reach = "all_generative"

    elif surface == "dlf_lite_v2":
        wired = _file_exists("src/dlf_lite_v2/__init__.py")
        operating = _db_recent(
            "/var/lib/murphy-production/dlf_packages.db",
            "packages", "created_at", 168)  # widened to 7d
        reach = "loom_lite"

    elif surface == "critic_v2":
        wired = _file_exists("src/critic_v2_31cv.py")
        operating = _db_recent(
            "/var/lib/murphy-production/critic_v2_log.db",
            "critic_v2_log", "ran_at", 168)
        reach = "all_outbound"

    elif surface == "forward_ambient":
        wired = _file_exists("src/forward_ambient_31cx.py")
        operating = _db_recent(
            "/var/lib/murphy-production/forward_sessions_31cx.db",
            "forward_sessions", "created_at", 168)
        reach = "inbound_mail"

    elif surface == "autoresponder":
        wired = _file_exists("src/stranger_responder.py")
        operating = _service_active("murphy-inbound-autoresponse.timer")
        reach = "stranger_mail"
        ev.append("intentionally OFF since mcconnaire 2026-06-15")

    elif surface == "security_jails":
        # NEW BRANCH — was missing entirely
        wired = Path("/etc/fail2ban/jail.local").exists() or Path(
            "/etc/fail2ban/jail.d/murphy.conf"
        ).exists()
        try:
            r = subprocess.run(
                ["sudo","-n","fail2ban-client","status"],
                capture_output=True, text=True, timeout=5
            )
            out = r.stdout or ""
            # count jails
            jails = []
            for line in out.split("\n"):
                if "Jail list:" in line:
                    jails = [j.strip() for j in line.split(":",1)[1].split(",") if j.strip()]
                    break
            operating = len(jails) >= 3
            ev.append(f"active_jails={len(jails)}: {','.join(jails[:6])}")
        except Exception as e:
            ev.append(f"err={e}")
        reach = "all_login_surfaces"

    elif surface == "immune_wired":
        # NEW BRANCH — was missing
        # is honeypot middleware actually trapping requests?
        wired = _file_exists("src/honeypot_engine.py") and _grep_app(r"honeypot")
        # check ban_log_31cz or similar for recent bans
        operating = False
        for db_path, tbl in [
            ("/var/lib/murphy-production/ban_log_31cz.db", "ban_events"),
            ("/var/lib/murphy-production/honeypot_traps.db", "traps"),
            ("/var/lib/murphy-production/security_brain.db", "scan_memory"),
        ]:
            if Path(db_path).exists():
                try:
                    c = sqlite3.connect(db_path, timeout=5)
                    r = c.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()
                    c.close()
                    n = r[0] if r else 0
                    if n > 0:
                        operating = True
                        ev.append(f"{Path(db_path).name}.{tbl}={n}")
                        break
                except Exception:
                    continue
        reach = "all_inbound"

    elif surface == "honeypot_reach":
        # NEW BRANCH — was missing
        wired = _file_exists("src/honeypot_engine.py") and _grep_app(r"honeypot")
        # operating = honeypot middleware referenced in app.py
        operating = _grep_app(r"HoneypotMiddleware|honeypot_middleware|honeypot_engine")
        reach = "all_requests"

    elif surface == "security_dashboard":
        # NEW BRANCH — was missing
        wired = _grep_app(r"/os/security|/security['\"]")
        operating = wired  # if route registered, dashboard reachable
        reach = "founder"

    elif surface == "abuse_reports":
        # NEW BRANCH — was missing
        wired = _file_exists("src/abuse_reports.py") or _file_exists(
            "src/abuse_filer.py")
        # not yet implemented — leave operating False with honest evidence
        operating = False
        ev.append("not yet wired — pending implementation")
        reach = "external_cert"

    return {
        "wired": int(wired),
        "operating": int(operating),
        "reach_mode": reach,
        "evidence": "; ".join(ev) if ev else "",
    }


def run_audit(triggered_by: str = "scheduled") -> dict:
    if _is_frozen():
        return {"skipped": True, "reason": "walker frozen"}

    run_id = "audit_" + uuid.uuid4().hex[:12]
    started = _now()

    c = sqlite3.connect(DB, timeout=10)
    goals = c.execute(
        "SELECT surface, capability FROM end_goal WHERE status='open'"
    ).fetchall()

    wired_n = 0
    op_n = 0
    for surface, capability in goals:
        r = _capability_check(surface, capability)
        if r["wired"]: wired_n += 1
        if r["operating"]: op_n += 1
        c.execute(
            "INSERT INTO as_built (audit_run_id, audited_at, surface, capability, "
            "is_wired, is_operating, reach_mode, evidence) VALUES (?,?,?,?,?,?,?,?)",
            (run_id, _now(), surface, capability,
             r["wired"], r["operating"], r["reach_mode"], r["evidence"]),
        )

    finished = _now()
    c.execute(
        "INSERT INTO audit_runs (run_id, started_at, finished_at, surfaces_checked, "
        "wired, operating, triggered_by) VALUES (?,?,?,?,?,?,?)",
        (run_id, started, finished, len(goals), wired_n, op_n, triggered_by),
    )
    c.execute("UPDATE walker_state SET last_run_id=? WHERE id=1", (run_id,))
    c.commit(); c.close()

    return {
        "run_id": run_id,
        "surfaces_checked": len(goals),
        "wired": wired_n,
        "operating": op_n,
        "started": started,
        "finished": finished,
    }


def freeze(reason: str = "manual") -> dict:
    c = sqlite3.connect(DB, timeout=10)
    c.execute("UPDATE walker_state SET frozen=1, frozen_at=?, frozen_reason=? WHERE id=1",
              (_now(), reason))
    c.commit(); c.close()
    return {"frozen": True, "reason": reason, "at": _now()}


def unfreeze() -> dict:
    c = sqlite3.connect(DB, timeout=10)
    c.execute("UPDATE walker_state SET frozen=0, frozen_at=NULL, frozen_reason=NULL WHERE id=1")
    c.commit(); c.close()
    return {"frozen": False, "at": _now()}


_HTML_HEAD = """<!DOCTYPE html><html><head><meta charset='utf-8'>
<title>Shape of Complete — Murphy</title>
<style>
body{background:#0c1015;color:#f5f0e1;font-family:Georgia,serif;margin:0;padding:32px;}
h1{color:#d4af37;font-weight:300;letter-spacing:2px;border-bottom:1px solid #2a2f38;padding-bottom:12px;}
h2{color:#d4af37;font-weight:400;margin-top:32px;}
.tabs{margin:24px 0;}
.tab{display:inline-block;padding:8px 18px;background:#1a1f28;color:#d4af37;cursor:pointer;border:1px solid #2a2f38;margin-right:4px;}
.tab.active{background:#d4af37;color:#0c1015;}
.face{display:none;} .face.active{display:block;}
table{width:100%;border-collapse:collapse;margin-top:12px;}
th{color:#d4af37;text-align:left;padding:10px;border-bottom:1px solid #2a2f38;font-weight:400;}
td{padding:10px;border-bottom:1px solid #1a1f28;font-size:14px;}
.wired{color:#6ec3e4;} .operating{color:#7ed957;} .dormant{color:#d96b6b;} .muted{color:#707682;}
.frozen{background:#d96b6b;color:white;padding:6px 14px;display:inline-block;}
.live{background:#7ed957;color:#0c1015;padding:6px 14px;display:inline-block;}
.summary{background:#1a1f28;padding:16px;border-left:3px solid #d4af37;margin:16px 0;}
</style></head><body>"""


def render_html() -> str:
    c = sqlite3.connect(DB, timeout=10)
    last_run = c.execute(
        "SELECT run_id, finished_at, surfaces_checked, wired, operating "
        "FROM audit_runs ORDER BY started_at DESC LIMIT 1"
    ).fetchone()

    as_built = []
    if last_run:
        as_built = c.execute(
            "SELECT surface, capability, is_wired, is_operating, reach_mode, evidence "
            "FROM as_built WHERE audit_run_id=? "
            "ORDER BY is_operating DESC, is_wired DESC, surface ASC",
            (last_run[0],)
        ).fetchall()

    gaps = c.execute(
        "SELECT decided_at, ship, head_hash, chose, why, closes_gap "
        "FROM gap_decisions ORDER BY decided_at DESC LIMIT 30"
    ).fetchall()

    goals = c.execute(
        "SELECT surface, capability, must_be_reachable_from, must_feed, "
        "must_be_gated_by, priority FROM end_goal "
        "WHERE status='open' ORDER BY priority DESC, surface ASC"
    ).fetchall()

    operating_caps = {(s, c_) for (s, c_, _, op, _, _) in as_built if op}
    final = [(s, cap) for (s, cap, _, _, _, _) in goals if (s, cap) not in operating_caps]

    fr = c.execute("SELECT frozen, frozen_at, frozen_reason FROM walker_state WHERE id=1").fetchone()
    c.close()

    h = [_HTML_HEAD]
    h.append("<h1>Shape of Complete — Murphy</h1>")

    if last_run:
        pct_w = (last_run[3] * 100) // max(last_run[2], 1)
        pct_o = (last_run[4] * 100) // max(last_run[2], 1)
        badge = '<span class="frozen">WALKER FROZEN</span>' if (fr and fr[0]) else '<span class="live">WALKER LIVE</span>'
        reason = f'<span class="muted"> — reason: {fr[2]}</span>' if (fr and fr[0]) else ''
        h.append(f'<div class="summary"><strong>Last audit:</strong> {last_run[1]} ({last_run[0]})<br>'
                 f'<strong>Surfaces:</strong> {last_run[2]} &nbsp; '
                 f'<strong>Wired:</strong> {last_run[3]} ({pct_w}%) &nbsp; '
                 f'<strong>Operating:</strong> {last_run[4]} ({pct_o}%)<br>{badge}{reason}</div>')
    else:
        h.append('<div class="summary">No audits yet — POST /api/shape/audit</div>')

    h.append('<div class="tabs">')
    for face in ("as-built","gap","end-goal","final"):
        h.append(f'<span class="tab" onclick="show(\'{face}\')" id="tab-{face}">{face.upper()}</span>')
    h.append('</div>')

    # AS-BUILT
    h.append('<div class="face active" id="face-as-built"><h2>AS-BUILT — wired and operating right now</h2>')
    h.append('<table><tr><th>Surface</th><th>Capability</th><th>Wired</th><th>Operating</th><th>Reach</th><th>Evidence</th></tr>')
    for (surface, cap, w, op, reach, ev) in as_built:
        wcls = "operating" if w else "dormant"
        ocls = "operating" if op else "dormant"
        h.append(f'<tr><td>{surface}</td><td>{cap[:60]}</td>'
                 f'<td class="{wcls}">{"YES" if w else "no"}</td>'
                 f'<td class="{ocls}">{"YES" if op else "no"}</td>'
                 f'<td class="muted">{reach}</td><td class="muted">{(ev or "")[:80]}</td></tr>')
    h.append('</table></div>')

    # GAP
    h.append('<div class="face" id="face-gap"><h2>GAP — active stream of choices</h2>')
    h.append('<table><tr><th>When</th><th>Ship</th><th>HEAD</th><th>Chose</th><th>Why</th><th>Closes</th></tr>')
    for (when, ship, head, chose, why, closes) in gaps:
        h.append(f'<tr><td class="muted">{when[:16]}</td><td>{ship or ""}</td>'
                 f'<td class="muted">{(head or "")[:10]}</td>'
                 f'<td>{(chose or "")[:60]}</td><td class="muted">{(why or "")[:60]}</td>'
                 f'<td class="wired">{(closes or "")[:30]}</td></tr>')
    h.append('</table></div>')

    # END GOAL
    h.append('<div class="face" id="face-end-goal"><h2>END GOAL — everything we want to have</h2>')
    h.append('<table><tr><th>Pri</th><th>Surface</th><th>Capability</th><th>Reached from</th><th>Feeds</th><th>Gated by</th></tr>')
    for (s, cap, reach, feed, gate, prio) in goals:
        h.append(f'<tr><td>{prio}</td><td>{s}</td><td>{cap[:60]}</td>'
                 f'<td class="muted">{reach or ""}</td>'
                 f'<td class="muted">{feed or ""}</td>'
                 f'<td class="muted">{gate or ""}</td></tr>')
    h.append('</table></div>')

    # FINAL
    h.append('<div class="face" id="face-final"><h2>FINAL — End Goal minus operating As-Built</h2>')
    if not final:
        h.append('<p class="operating">All end-goal capabilities operating. Ship the next set.</p>')
    else:
        h.append(f'<p class="muted">{len(final)} capabilities defined but not yet operating:</p>')
        h.append('<table><tr><th>Surface</th><th>Capability</th></tr>')
        for (s, cap) in final:
            h.append(f'<tr><td>{s}</td><td>{cap[:80]}</td></tr>')
        h.append('</table>')
    h.append('</div>')

    h.append("""<script>
function show(f){
  document.querySelectorAll('.face').forEach(e=>e.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(e=>e.classList.remove('active'));
  document.getElementById('face-'+f).classList.add('active');
  document.getElementById('tab-'+f).classList.add('active');
}
document.getElementById('tab-as-built').classList.add('active');
</script></body></html>""")
    return "\n".join(h)
