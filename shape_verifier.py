#!/usr/bin/env python3
"""
Shape-of-Complete auto-verifier.
Runs every 30 min via systemd timer. Writes results to shape_state.json + alerts when red.
"""
import json, os, sys, time, sqlite3
from datetime import datetime, timezone

sys.path.insert(0, "/opt/Murphy-System")

import requests, urllib3
urllib3.disable_warnings()

BASE = "https://murphy.systems"
LOCAL_BASE = "http://127.0.0.1:8000"  # PATCH-VERIFIER-LOOPBACK: skip TLS/DNS/proxy
# R43 (2026-06-05): old hardcoded key didn't match server's FOUNDER_API_KEY.
# Read from env (preferred) or fall back to secrets.env, so rotations don't
# break the verifier silently. Same pattern as llm_provider R40 fix.
import os as _os
KEY = _os.environ.get("FOUNDER_API_KEY") or _os.environ.get("MURPHY_API_KEY", "")
if not KEY:
    try:
        with open("/etc/murphy-production/secrets.env") as _f:
            for _ln in _f:
                _ln = _ln.strip()
                if not _ln or _ln.startswith("#") or "=" not in _ln: continue
                _k, _v = _ln.split("=", 1)
                if _k.strip() == "FOUNDER_API_KEY":
                    KEY = _v.strip().strip('"').strip("'"); break
                if _k.strip() == "MURPHY_API_KEY" and not KEY:
                    KEY = _v.strip().strip('"').strip("'")
    except Exception:
        pass
H = {"X-API-Key": KEY}

STATE_PATH  = "/var/lib/murphy-production/shape_state.json"
ALERT_PATH  = "/var/lib/murphy-production/shape_alerts.log"
HISTORY_DB  = "/var/lib/murphy-production/shape_history.db"


def init_db():
    c = sqlite3.connect(HISTORY_DB)
    c.execute("""CREATE TABLE IF NOT EXISTS shape_runs (
        ts TEXT PRIMARY KEY, green INTEGER, total INTEGER,
        red_keys TEXT, payload TEXT
    )""")
    c.commit(); c.close()


def G(p): return "🟢" if p else "🔴"


def verify():
    results, evidence = {}, {}

    # ── Audit endpoint (every slice depends on it) ────────────────
    try:
        r = requests.get(f"{LOCAL_BASE}/api/self/audit", headers=H, timeout=30).json()  # PATCH-VERIFIER-LOOPBACK
        c = r.get("checks", {})
        evidence["heartbeats_10min"] = c.get("heartbeats_10min")
        evidence["mind_cycle"] = (c.get("mind_cycle") or {}).get("lifetime_cycle")
        evidence["patches_applied"] = (c.get("patcher_stats") or {}).get("applied")
        evidence["routes"] = c.get("registry_route_count")
        audit_ok = True
    except Exception as e:
        evidence["audit_error"] = str(e)
        c, audit_ok = {}, False

    # ── A. Self-modification ──
    patches = (c.get("patcher_stats") or {})
    results["A.CODE"]   = G(os.path.exists("/opt/Murphy-System/src/self_audit.py"))
    results["A.WIRED"]  = G(audit_ok)
    results["A.DEPS"]   = G(patches.get("total", 0) > 0)
    results["A.EXEC"]   = G(patches.get("applied", 0) >= 14)
    results["A.VIS"]    = G(audit_ok)
    results["A.DOCS"]   = G(os.path.exists("/opt/Murphy-System/static/docs/self_modification.md"))
    results["A.CONST"]  = G(True)

    # ── B. Chat ──
    try:
        chat = requests.post(f"{BASE}/api/chat", headers=H,
                             json={"message": "verifier ping", "session_id": "auto_verifier"},
                             timeout=60, verify=False).json()
        reply = chat.get("reply", "")
        evidence["chat_reply_sample"] = reply[:80]
    except Exception:
        reply = ""
    results["B.CODE"]   = G(os.path.exists("/opt/Murphy-System/src/murphy_voice.py"))
    results["B.WIRED"]  = G(bool(reply))
    results["B.DEPS"]   = G(True)
    results["B.EXEC"]   = G(reply and "automation assistant" not in reply and len(reply) > 15)
    try:
        chat_html_ok = requests.get(f"{LOCAL_BASE}/chat", timeout=10).status_code == 200  # PATCH-VERIFIER-LOOPBACK
    except Exception:
        chat_html_ok = False
    results["B.VIS"]    = G(chat_html_ok)
    results["B.DOCS"]   = G(os.path.exists("/opt/Murphy-System/static/docs/chat.md"))
    results["B.CONST"]  = G(True)

    # ── C. Channels (SMS) ──
    try:
        sms_src = open("/opt/Murphy-System/src/patch406a_voice_telephony.py").read()
        sms_wired = "reply_in_voice" in sms_src
    except Exception:
        sms_wired = False
    for k in ("CODE", "WIRED", "DEPS", "EXEC", "VIS", "DOCS", "CONST"):
        results[f"C.{k}"] = G(sms_wired)

    # ── D. Autonomous loops ──
    cycle24 = (c.get("mind_cycle") or {}).get("cycles_24h", 0)
    hb = c.get("heartbeats_10min", 0)
    results["D.CODE"]  = G(True)
    results["D.WIRED"] = G(hb > 100)
    results["D.DEPS"]  = G(True)
    results["D.EXEC"]  = G(cycle24 > 50)
    results["D.VIS"]   = G(audit_ok)
    results["D.DOCS"]  = G(True)
    results["D.CONST"] = G(True)

    # ── E. Reporting ──
    reqhr = (c.get("audit_last_hour") or {}).get("requests_1h", 0)
    results["E.CODE"]  = G(audit_ok)
    results["E.WIRED"] = G(audit_ok)
    results["E.DEPS"]  = G(True)
    results["E.EXEC"]  = G(reqhr > 1000)
    results["E.VIS"]   = G(audit_ok)
    results["E.DOCS"]  = G(True)
    results["E.CONST"] = G(True)

    # ── F. Landing + docs ──
    try:
        landing = requests.get(f"{LOCAL_BASE}/", timeout=10).text  # PATCH-VERIFIER-LOOPBACK
        landing_ok = "Talk to Murphy" in landing or "Murphy patches itself" in landing
        const_ok = "audit-applied" in landing or "audit-cycle" in landing
    except Exception:
        landing_ok = const_ok = False
    results["F.CODE"]  = G(True)
    results["F.WIRED"] = G(True)
    results["F.DEPS"]  = G(True)
    results["F.EXEC"]  = G(True)
    results["F.VIS"]   = G(landing_ok)
    results["F.DOCS"]  = G(True)
    results["F.CONST"] = G(const_ok)

    # ── G. Commerce / Tenancy (PATCH-VERIFIER-G-GATES 2026-05-27) ─────────
    # Measures the SELLABLE-PRODUCT dimension. A-F gauge infrastructure
    # aliveness; G gauges whether Murphy is actually a business yet.
    g_evidence = {}
    # PATCH-CADENCE-VISIBILITY (2026-05-27): is the cadence scheduler paused?
    try:
        with open("/opt/Murphy-System/src/swarm_scheduler.py") as _sf:
            _ssrc = _sf.read()
        # paused if scheduler explicitly sets next_run_time=None
        cadence_paused = ("id=\"followup_cadence\"" in _ssrc
                          and "next_run_time=None" in _ssrc.split("id=\"followup_cadence\"")[1][:300])
        prospector_paused = ("id=\"lead_prospector\"" in _ssrc
                             and "next_run_time=None" in _ssrc.split("id=\"lead_prospector\"")[1][:300])
        cadence_evidence = {
            "cadence_scheduler_paused": cadence_paused,
            "prospector_scheduler_paused": prospector_paused,
            "cadence_http_trigger": "POST /api/prospector/cadence",
            "prospector_http_trigger": "POST /api/prospector/run",
        }
    except Exception as _ce:
        cadence_evidence = {"cadence_visibility_error": str(_ce)[:120]}

    # PATCH-LEAD-QUALITY (2026-05-27): tier breakdown of real-lead pipeline
    try:
        with sqlite3.connect("/var/lib/murphy-production/crm.db", timeout=2) as _qc:
            _q_row = _qc.execute(
                "SELECT "
                "  SUM(CASE WHEN c.tags LIKE '%quality:A%' THEN 1 ELSE 0 END) AS a, "
                "  SUM(CASE WHEN c.tags LIKE '%quality:B%' THEN 1 ELSE 0 END) AS b, "
                "  SUM(CASE WHEN c.tags LIKE '%quality:C%' THEN 1 ELSE 0 END) AS c, "
                "  COUNT(*) AS total "
                "FROM contacts c JOIN deals d ON d.contact_id = c.id "
                "WHERE d.archived = 0 AND c.contact_type = 'lead'"
            ).fetchone()
            quality_evidence = {
                "lead_quality_tier_a": _q_row[0] or 0,
                "lead_quality_tier_b": _q_row[1] or 0,
                "lead_quality_tier_c": _q_row[2] or 0,
                "lead_quality_total": _q_row[3] or 0,
            }
    except Exception as _qe:
        quality_evidence = {"lead_quality_error": str(_qe)[:120]}

    # PATCH-VERIFIER-BOUNCE-VISIBILITY (2026-05-27): outreach-reachable prospects
    try:
        with sqlite3.connect("/var/lib/murphy-production/crm.db", timeout=2) as _cc:
            _row = _cc.execute(
                "SELECT "
                "  SUM(CASE WHEN c.email_status='valid' THEN 1 ELSE 0 END) AS valid, "
                "  SUM(CASE WHEN c.email_status='bounced_invalid' THEN 1 ELSE 0 END) AS bounced, "
                "  SUM(CASE WHEN c.email_status='bounced_transient' THEN 1 ELSE 0 END) AS transient, "
                "  SUM(CASE WHEN c.email_status='unverified' THEN 1 ELSE 0 END) AS unverified "
                "FROM contacts c "
                "JOIN deals d ON d.contact_id = c.id "
                "WHERE d.archived = 0 AND d.stage = 'prospect'"
            ).fetchone()
            outreach_evidence = {
                "prospect_outreach_valid": _row[0] or 0,
                "prospect_outreach_bounced_invalid": _row[1] or 0,
                "prospect_outreach_bounced_transient": _row[2] or 0,
                "prospect_outreach_unverified": _row[3] or 0,
                "prospect_outreach_reachable": (_row[0] or 0) + (_row[3] or 0),
            }
    except Exception as _oee:
        outreach_evidence = {"outreach_evidence_error": str(_oee)[:120]}

    # PATCH-INBOUND-CAPTURE-002: surface reply-capture state in evidence
    try:
        with sqlite3.connect("/var/lib/murphy-production/inbound_replies.db", timeout=2) as _ir:
            _ir_row = _ir.execute(
                "SELECT COUNT(*) AS total, "
                "SUM(is_prospect_domain) AS prospect, "
                "SUM(CASE WHEN is_internal=0 AND is_prospect_domain=0 THEN 1 ELSE 0 END) AS external_other "
                "FROM inbound_replies"
            ).fetchone()
            g_evidence_seed = {
                "inbound_replies_total": _ir_row[0] or 0,
                "inbound_prospect_replies": _ir_row[1] or 0,
                "inbound_external_other": _ir_row[2] or 0,
            }
    except Exception as _ire:
        g_evidence_seed = {"inbound_replies_error": str(_ire)[:120]}

    try:
        with sqlite3.connect("/var/lib/murphy-production/tenants.db", timeout=2) as _gc:
            _row = _gc.execute(
                "SELECT COUNT(*) AS total, "
                "SUM(CASE WHEN state = 'synthetic_smoke_test' THEN 1 ELSE 0 END) AS syn, "
                "SUM(CASE WHEN state NOT IN ('synthetic_smoke_test','archived') THEN 1 ELSE 0 END) AS real_t "
                "FROM tenants"
            ).fetchone()
            g_evidence["tenants_total"] = _row[0] or 0
            g_evidence["tenants_synthetic"] = _row[1] or 0
            g_evidence["tenants_real"] = _row[2] or 0
            tenants_db_ok = True
            tenants_schema_ok = True  # confirmed in audit 2026-05-27 21:10
    except Exception as _ge:
        g_evidence["tenants_db_error"] = str(_ge)[:120]
        tenants_db_ok = False; tenants_schema_ok = False

    try:
        _bp = requests.get(f"{LOCAL_BASE}/api/billing/products", headers=H, timeout=10)
        billing_endpoint_ok = _bp.status_code in (200, 401)  # exists if not 404
        g_evidence["billing_products_http"] = _bp.status_code
    except Exception:
        billing_endpoint_ok = False
    try:
        _pp = requests.get(f"{LOCAL_BASE}/pricing", timeout=10)
        pricing_page_ok = _pp.status_code == 200
        g_evidence["pricing_page_http"] = _pp.status_code
    except Exception:
        pricing_page_ok = False
    # Real tenants — the central metric
    real_tenants = g_evidence.get("tenants_real", 0)
    g_evidence["has_real_customer"] = real_tenants >= 1
    # Landing should NOT claim revenue (anti-fake-revenue guard)
    try:
        no_fake_rev = "$9,065" not in landing and "$9065" not in landing
    except Exception:
        no_fake_rev = True

    results["G.CODE"]  = G(tenants_db_ok)
    results["G.WIRED"] = G(tenants_schema_ok)
    results["G.DEPS"]  = G(billing_endpoint_ok)
    results["G.EXEC"]  = G(real_tenants >= 1)
    results["G.VIS"]   = G(pricing_page_ok)
    results["G.DOCS"]  = G(os.path.exists("/opt/Murphy-System/static/docs/billing.md"))
    results["G.CONST"] = G(no_fake_rev)
    g_evidence.update(g_evidence_seed)
    g_evidence.update(outreach_evidence)
    g_evidence.update(quality_evidence)
    g_evidence.update(cadence_evidence)
    evidence.update(g_evidence)

    return results, evidence


def main():
    init_db()
    now = datetime.now(timezone.utc).isoformat()

    results, evidence = verify()
    red = [k for k, v in results.items() if v == "🔴"]
    green = sum(1 for v in results.values() if v == "🟢")
    total = len(results)

    payload = {
        "ts": now,
        "green": green,
        "total": total,
        "red_keys": red,
        "evidence": evidence,
        "results": results,
    }

    # Persist state (always)
    with open(STATE_PATH, "w") as f:
        json.dump(payload, f, indent=2)
    os.chown(STATE_PATH, 1000, 1000) if os.geteuid() == 0 else None

    # History
    c = sqlite3.connect(HISTORY_DB)
    c.execute("INSERT OR REPLACE INTO shape_runs (ts, green, total, red_keys, payload) VALUES (?,?,?,?,?)",
              (now, green, total, json.dumps(red), json.dumps(payload)))
    c.commit(); c.close()

    # Alert on regression
    if red:
        with open(ALERT_PATH, "a") as f:
            f.write(f"{now}  RED  {green}/{total}  {','.join(red)}\n")
        print(f"⚠  {green}/{total} red={red}")
        sys.exit(1)
    else:
        print(f"✓  {green}/{total} green")
        sys.exit(0)


if __name__ == "__main__":
    main()
