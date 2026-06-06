#!/usr/bin/env python3
"""
R603B — CFO Agent (Phase C, first replica of R603 pattern)
============================================================

Reads treasury + capital_engine + billing → writes financial state
report → saves artifact → emails founder → registers in data_room.

Same canon as R603. Read-only DB access. One email side effect.
Murphy approved this pattern Phase C 2026-06-05.
"""
import os, sys, json, sqlite3, subprocess, uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

NOW = datetime.now(timezone.utc)
ARTIFACT_DIR = Path("/var/lib/murphy-production/artifacts")
ARTIFACT_ID = f"r603b_cfo_financial_report_{NOW.strftime('%Y%m%dT%H%M%SZ')}"
TREASURY_DB = "/var/lib/murphy-production/treasury.db"
CAPITAL_DB = "/var/lib/murphy-production/capital_engine.db"
BILLING_DB = "/var/lib/murphy-production/billing.db"
RECIPIENT = "cpost@murphy.systems"
SENDER = "cfo-agent@murphy.systems"


def _safe_query(db_path, sql, default=None):
    """Read-only query; return default on any failure (DB missing, table missing)."""
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        result = conn.execute(sql).fetchall()
        conn.close()
        return result
    except Exception as e:
        return default


def read_treasury():
    """Treasury state: wallets, journal entries, payments."""
    wallets = _safe_query(TREASURY_DB,
        "SELECT name, currency, balance FROM operations_wallet ORDER BY balance DESC LIMIT 5",
        default=[])
    recent_payments = _safe_query(TREASURY_DB,
        "SELECT count(*), COALESCE(SUM(amount), 0) FROM payment_records "
        "WHERE created_at > datetime('now', '-7 days')",
        default=[(0, 0)])
    total_payments = _safe_query(TREASURY_DB,
        "SELECT count(*), COALESCE(SUM(amount), 0) FROM payment_records",
        default=[(0, 0)])
    journal_count = _safe_query(TREASURY_DB,
        "SELECT count(*) FROM journal_entries", default=[(0,)])
    return {
        "wallets": wallets or [],
        "payments_7d_count": recent_payments[0][0] if recent_payments else 0,
        "payments_7d_amount": recent_payments[0][1] if recent_payments else 0,
        "payments_total_count": total_payments[0][0] if total_payments else 0,
        "payments_total_amount": total_payments[0][1] if total_payments else 0,
        "journal_entries": journal_count[0][0] if journal_count else 0,
    }


def read_capital():
    """Capital engine: budgets, ledger, spend proposals."""
    budget = _safe_query(CAPITAL_DB,
        "SELECT count(*), COALESCE(SUM(amount), 0) FROM capital_budget", default=[(0,0)])
    ledger_recent = _safe_query(CAPITAL_DB,
        "SELECT count(*), COALESCE(SUM(amount), 0) FROM capital_ledger "
        "WHERE ts > datetime('now', '-7 days')", default=[(0,0)])
    proposals_open = _safe_query(CAPITAL_DB,
        "SELECT count(*) FROM spend_proposals WHERE status IN ('pending','open','proposed')",
        default=[(0,)])
    return {
        "budget_lines": budget[0][0] if budget else 0,
        "budget_total": budget[0][1] if budget else 0,
        "ledger_7d_count": ledger_recent[0][0] if ledger_recent else 0,
        "ledger_7d_amount": ledger_recent[0][1] if ledger_recent else 0,
        "open_spend_proposals": proposals_open[0][0] if proposals_open else 0,
    }


def read_billing():
    """Billing: subscriptions, IPN events, billing records."""
    subs = _safe_query(BILLING_DB,
        "SELECT count(*), COUNT(CASE WHEN status='active' THEN 1 END) FROM tenant_subscriptions",
        default=[(0,0)])
    ipn_recent = _safe_query(BILLING_DB,
        "SELECT count(*) FROM ipn_events WHERE created_at > datetime('now', '-7 days')",
        default=[(0,)])
    billing_records = _safe_query(BILLING_DB,
        "SELECT count(*) FROM billing_records", default=[(0,)])
    plans = _safe_query(BILLING_DB,
        "SELECT name, price_usd FROM nowpayments_plans LIMIT 5", default=[])
    return {
        "total_subscriptions": subs[0][0] if subs else 0,
        "active_subscriptions": subs[0][1] if subs else 0,
        "ipn_events_7d": ipn_recent[0][0] if ipn_recent else 0,
        "billing_records_total": billing_records[0][0] if billing_records else 0,
        "plans": plans or [],
    }


def synthesize(treasury, capital, billing):
    """Build the report. Same heuristic style as R603 — honest about empty signals."""
    # Headline metrics
    active_revenue = treasury["payments_7d_amount"]
    has_paying_customers = billing["active_subscriptions"] > 0

    rev_em = "🟢" if active_revenue > 0 else "🔴"
    sub_em = "🟢" if has_paying_customers else "🔴"
    runway_em = "🟢" if capital["budget_total"] > 0 else "🟡"

    md = f"""# Murphy Financial Report

**Reporter:** CFO Agent (R603B — first CFO deliverable)
**Generated:** {NOW.isoformat()}
**Period:** trailing 7 days
**For:** Corey Post (cpost@murphy.systems)

---

## Headline

| Signal | Status | Value |
|---|---|---|
| Revenue (7d) | {rev_em} | ${treasury['payments_7d_amount']:,.2f} across {treasury['payments_7d_count']} payment(s) |
| Active subscriptions | {sub_em} | {billing['active_subscriptions']} active / {billing['total_subscriptions']} total |
| Capital budget | {runway_em} | ${capital['budget_total']:,.2f} across {capital['budget_lines']} line(s) |
| Open spend proposals | {'🟡' if capital['open_spend_proposals'] > 0 else '🟢'} | {capital['open_spend_proposals']} awaiting decision |

## Treasury

- Wallets tracked: {len(treasury['wallets'])}
- Lifetime payments: {treasury['payments_total_count']} totaling ${treasury['payments_total_amount']:,.2f}
- Journal entries (lifetime): {treasury['journal_entries']}
- IPN events (7d): {billing['ipn_events_7d']}
"""
    if treasury["wallets"]:
        md += "\n### Top wallets by balance\n\n"
        for name, ccy, bal in treasury["wallets"][:5]:
            md += f"- **{name}** ({ccy}): {bal}\n"

    md += f"\n## Capital Engine\n\n"
    md += f"- Budget lines: {capital['budget_lines']} totaling ${capital['budget_total']:,.2f}\n"
    md += f"- Ledger entries (7d): {capital['ledger_7d_count']} totaling ${capital['ledger_7d_amount']:,.2f}\n"
    md += f"- Open spend proposals: {capital['open_spend_proposals']}\n"

    if billing["plans"]:
        md += "\n## Pricing plans live\n\n"
        for name, price in billing["plans"]:
            md += f"- **{name}**: ${price}\n"

    # Recommendations
    md += "\n## Recommended next actions\n\n"
    actions = []
    if not has_paying_customers:
        actions.append("**Top priority:** zero active subscriptions. Revenue work is the #1 lever. Phase E sales agents (CSO) can help once Phase D ships.")
    if treasury["payments_7d_count"] == 0 and treasury["payments_total_count"] > 0:
        actions.append(f"No payments in last 7 days but {treasury['payments_total_count']} lifetime payments exist — investigate gap.")
    if capital["open_spend_proposals"] > 0:
        actions.append(f"{capital['open_spend_proposals']} spend proposals awaiting founder approval.")
    if not actions:
        actions.append("No urgent financial action items detected.")
    for i, a in enumerate(actions[:5], 1):
        md += f"{i}. {a}\n"

    md += f"""

---

## About this report

Second agent in Murphy's history (after CTO). Reads three financial DBs (treasury, capital_engine, billing) read-only, synthesizes a one-page summary, emails the founder, posts to data_room_artifacts.

Same R603 pattern. Same canon. Approved by Murphy via chat-v2 for Phase C.

Tomorrow: CSO agent (sales pipeline) and CEO agent (synthesis of all three).
"""
    return md


def email_report(subject, body):
    msg = (
        f"From: CFO Agent <{SENDER}>\n"
        f"To: {RECIPIENT}\n"
        f"Subject: {subject}\n"
        f"Content-Type: text/plain; charset=utf-8\n"
        f"X-Murphy-Artifact: {ARTIFACT_ID}\n"
        f"X-Murphy-Agent: cfo\n"
        f"X-Murphy-Pilot: R603B\n\n"
        f"{body}\n"
    )
    result = subprocess.run(
        ["/usr/sbin/sendmail", "-f", SENDER, RECIPIENT],
        input=msg.encode("utf-8"), capture_output=True, timeout=20,
    )
    return result.returncode == 0


def main():
    print(f"R603B CFO agent pilot — {NOW.isoformat()}")
    print("  reading treasury.db ..."); t = read_treasury()
    print(f"    → {t['payments_7d_count']} payments 7d, ${t['payments_7d_amount']:,.2f}")
    print("  reading capital_engine.db ..."); c = read_capital()
    print(f"    → {c['budget_lines']} budget lines, ${c['budget_total']:,.2f}")
    print("  reading billing.db ..."); b = read_billing()
    print(f"    → {b['active_subscriptions']} active subscriptions")

    md = synthesize(t, c, b)

    artifact_dir = ARTIFACT_DIR / ARTIFACT_ID
    artifact_dir.mkdir(parents=True, exist_ok=True)
    report_path = artifact_dir / "financial_report.md"
    with open(report_path, "w") as f: f.write(md)
    print(f"  artifact: {report_path}")

    with open(artifact_dir / "raw_data.json", "w") as f:
        json.dump({"treasury": t, "capital": c, "billing": b}, f, indent=2, default=str)

    ok = email_report(f"Murphy CFO Report — {NOW.strftime('%b %d %H:%M UTC')}", md)
    print(f"  email: {'✓' if ok else '✗'}")

    try:
        conn = sqlite3.connect("/var/lib/murphy-production/entity_graph.db")
        conn.execute(
            "INSERT INTO data_room_artifacts "
            "(id, category, title, file_url, version, current, notes, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (f"art_{uuid.uuid4().hex[:12]}", "report",
             f"CFO Financial Report {NOW.strftime('%Y-%m-%d %H:%M')}",
             str(report_path), 1, 1,
             "R603B CFO pilot — Phase C first replica",
             NOW.isoformat(), NOW.isoformat()))
        conn.commit(); conn.close()
        print("  ✓ registered in data_room_artifacts")
    except Exception as e:
        print(f"  ⚠ register failed: {e}")

    print(json.dumps({"ok": True, "artifact_id": ARTIFACT_ID,
                      "revenue_7d": t["payments_7d_amount"],
                      "active_subs": b["active_subscriptions"]}, indent=2))


if __name__ == "__main__":
    main()
