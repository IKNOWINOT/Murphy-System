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
    wired = False
    operating = False
    reach = "unknown"
    ev = []

    if surface == "direct_inquiry":
        wired = _grep_app(r"@app\.(post|get)\(.+(ask|chat|inquiry|message)")
        operating = _db_recent("/var/lib/murphy-production/users.db",
                               "user_accounts", "created_at", 168)
        reach = "founder,users"

    elif surface == "os_dashboard":
        wired = _grep_app(r"/os['\"]") or _file_exists("static/os.html")
        operating = _service_active("murphy-production.service")
        reach = "founder"

    elif surface == "os_shape":
        wired = _grep_app(r"/os/shape") or _file_exists("src/shape_walker_31cy.py")
        operating = _file_exists("src/shape_walker_31cy.py")
        reach = "founder,team"

    elif surface == "org_chart":
        wired = Path("/var/lib/murphy-production/agent_substrate.db").exists()
        operating = _db_recent("/var/lib/murphy-production/agent_substrate.db",
                               "agents", "created_at", 168)
        reach = "rosetta"

    elif surface == "rosetta":
        wired = _file_exists("src/rosetta_core.py") and _grep_app(r"rosetta")
        operating = (_service_active("murphy-rosetta.service") or
                     Path("/var/lib/murphy-production/rosetta.db").exists())
        reach = "all_intake"

    elif surface == "ambient_capture":
        wired = _file_exists("src/inbound_maildir_poller.py")
        operating = _db_recent(
            "/var/lib/murphy-production/inbound_replies.db",
            "inbound_replies", "received_at", 24)
        reach = "email,os"

    elif surface == "immunity":
        wired = _file_exists("src/immune_memory.py")
        operating = False
        reach = "all_output"
        ev.append("module exists, zero call sites in src/")

    elif surface == "antibody":
        wired = _file_exists("src/antibody/__init__.py")
        operating = _db_recent(
            "/var/lib/murphy-production/antibody_interventions.db",
            "antibody_interventions", "ts", 168)
        reach = "all_output"
        ev.append("module exists, not wired into stranger_responder")

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
        wired = _file_exists("src/hitl_provenance.py")
        operating = _db_recent(
            "/var/lib/murphy-production/hitl_provenance.db",
            "hitl_trails", "created_at", 168)
        reach = "founder"

    elif surface == "for_sale":
        wired = (_file_exists("static/pricing.html") and
                 Path("/var/lib/murphy-production/billing.db").exists())
        operating = _db_recent(
            "/var/lib/murphy-production/billing.db",
            "subscriptions", "created_at", 720)
        reach = "customers"

    elif surface == "sop_living_docs":
        wired = Path("/etc/murphy-production/reply_protocol.md").exists()
        operating = wired
        reach = "all_actors"

    elif surface == "loom_lite":
        wired = _file_exists("src/loom_lite/__init__.py")
        operating = _db_recent(
            "/var/lib/murphy-production/ghost_snapshots.db",
            "snapshots", "created_at", 24)
        reach = "all_generative"

    elif surface == "dlf_lite_v2":
        wired = _file_exists("src/dlf_lite_v2/__init__.py")
        operating = _db_recent(
            "/var/lib/murphy-production/dlf_packages.db",
            "packages", "created_at", 24)
        reach = "loom_lite"

    elif surface == "critic_v2":
        wired = _file_exists("src/critic_v2_31cv.py")
        try:
            wired = wired and ("Ship 31cv" in Path(
                f"{MURPHY_ROOT}/src/stranger_responder.py"
            ).read_text(errors="ignore")[:200000])
        except Exception:
            pass
        operating = _db_recent(
            "/var/lib/murphy-production/critic_v2_log.db",
            "critic_v2_log", "ran_at", 24)
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
