"""
Ship 31i.C — /os/stranger founder dashboard.

Joins three live data sources to show what stranger_responder actually
did in production:
  1. inbound_replies.db (the inbound email that triggered work)
  2. outbound_email_queue (the reply text that was queued/sent)
  3. ad_impressions (which ad was shown, score, matched keywords)

Per Shape of Complete v2 founder lock: if the founder can't see it in
production, it isn't done. This module makes 5 rows visible at once:
  row 1 INBOUND     row 3 PAY GATE   row 6 GENERATIVE
  row 9 AD INJECT   row 11 OUTBOUND  + row 15 DASHBOARD itself

Read-only. No state changes. No PII to anyone but the founder.
"""

import json, sqlite3, html
from datetime import datetime, timezone, timedelta

INBOUND_DB = "/var/lib/murphy-production/inbound_replies.db"
MAIL_DB = "/var/lib/murphy-production/murphy_mail.db"
ENTITY_DB = "/var/lib/murphy-production/entity_graph.db"


def _safe_json(s):
    try:
        return json.loads(s) if s else {}
    except Exception:
        return {}


def list_recent_strangers(limit: int = 30):
    """Return list of recent stranger replies joined with outbound + ad data."""
    c = sqlite3.connect(INBOUND_DB)
    c.row_factory = sqlite3.Row
    rows = c.execute("""
        SELECT id, msg_hash, received_at, from_addr, from_domain, subject,
               body_preview, auto_response_status, auto_response_sent_at,
               auto_response_target, delivery_mode, intent_class,
               intent_confidence, cc_addrs
        FROM inbound_replies
        WHERE auto_response_status LIKE 'stranger%'
        ORDER BY received_at DESC
        LIMIT ?
    """, (limit,)).fetchall()
    c.close()

    out = []
    for r in rows:
        meta = _safe_json(r["auto_response_target"])
        item = {
            "id": r["id"],
            "received_at": r["received_at"],
            "from_addr": r["from_addr"],
            "from_domain": r["from_domain"],
            "subject": r["subject"] or "(no subject)",
            "preview": (r["body_preview"] or "")[:200],
            "status": r["auto_response_status"],
            "sent_at": r["auto_response_sent_at"],
            "delivery_mode": r["delivery_mode"] or "direct",
            "intent_class": r["intent_class"],
            "intent_confidence": r["intent_confidence"],
            "cc_addrs": r["cc_addrs"],
            "cost_usd": meta.get("cost_usd"),
            "magnify_tok": meta.get("magnify_tok"),
            "reply_tok": meta.get("reply_tok"),
            "quota_reason": meta.get("quota_reason"),
            "reply_body": None,
            "ad_advertiser": None,
            "ad_score": None,
            "ad_keywords": None,
        }
        # Try to find the actual outbound reply body for this stranger
        try:
            mc = sqlite3.connect(MAIL_DB); mc.row_factory = sqlite3.Row
            # Match by recipient + received-at proximity (sent within 30 min)
            since = r["received_at"]
            qrow = mc.execute("""
                SELECT body, status, sent_at FROM outbound_email_queue
                WHERE to_addresses LIKE ?
                  AND created_at >= ?
                ORDER BY created_at ASC LIMIT 1
            """, (f'%{r["from_addr"]}%', since)).fetchone()
            mc.close()
            if qrow:
                item["reply_body"] = qrow["body"]
                item["reply_status"] = qrow["status"]
        except Exception:
            pass
        # Try to find ad impression for this reply
        try:
            ec = sqlite3.connect(ENTITY_DB); ec.row_factory = sqlite3.Row
            ad_row = ec.execute("""
                SELECT ai.role_detected, ai.vertical_detected, ai.score,
                       ai.keywords_matched, inv.advertiser
                FROM ad_impressions ai
                JOIN ad_inventory inv ON inv.id = ai.ad_id
                WHERE ai.reply_to_addr = ? AND ai.sent_ts >= ?
                ORDER BY ai.sent_ts ASC LIMIT 1
            """, (r["from_addr"], r["received_at"])).fetchone()
            ec.close()
            if ad_row:
                item["ad_advertiser"] = ad_row["advertiser"]
                item["ad_score"] = ad_row["score"]
                item["ad_role"] = ad_row["role_detected"]
                item["ad_vertical"] = ad_row["vertical_detected"]
                item["ad_keywords"] = ad_row["keywords_matched"]
        except Exception:
            pass
        out.append(item)
    return out


def stats_24h():
    """Aggregate stats over last 24h."""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    c = sqlite3.connect(INBOUND_DB)
    row = c.execute("""
        SELECT COUNT(*) total,
               SUM(CASE WHEN auto_response_status = 'stranger_sent' THEN 1 ELSE 0 END) sent,
               SUM(CASE WHEN auto_response_status = 'stranger_shadow_sent' THEN 1 ELSE 0 END) shadow,
               SUM(CASE WHEN delivery_mode = 'ambient' THEN 1 ELSE 0 END) ambient,
               SUM(CASE WHEN delivery_mode = 'direct' THEN 1 ELSE 0 END) direct
        FROM inbound_replies
        WHERE auto_response_status LIKE 'stranger%'
          AND received_at >= ?
    """, (cutoff,)).fetchone()
    c.close()

    ec = sqlite3.connect(ENTITY_DB)
    ad_stats = ec.execute("""
        SELECT COUNT(*) impressions,
               COUNT(DISTINCT ad_id) unique_ads,
               COUNT(click_ts) clicks
        FROM ad_impressions WHERE sent_ts >= ?
    """, (cutoff,)).fetchone()
    ec.close()

    return {
        "stranger_total": row[0] or 0,
        "stranger_sent": row[1] or 0,
        "stranger_shadow": row[2] or 0,
        "ambient_count": row[3] or 0,
        "direct_count": row[4] or 0,
        "ad_impressions": ad_stats[0] or 0,
        "ad_unique": ad_stats[1] or 0,
        "ad_clicks": ad_stats[2] or 0,
    }


def render_html(items, stats):
    """Render the dashboard as standalone HTML — minimal, fast, no JS framework."""
    def esc(x):
        return html.escape(str(x or ""))

    rows_html = []
    for it in items:
        ad_chip = ""
        if it.get("ad_advertiser"):
            ad_chip = (f'<span class="chip ad">📣 {esc(it["ad_advertiser"])} '
                       f'<small>(score {it.get("ad_score", 0):.2f}, '
                       f'role={esc(it.get("ad_role"))}, '
                       f'vert={esc(it.get("ad_vertical"))})</small></span>')
        mode_chip = f'<span class="chip {esc(it["delivery_mode"])}">{esc(it["delivery_mode"]).upper()}</span>'
        cost = f'${it["cost_usd"]:.5f}' if it.get("cost_usd") else "-"
        reply_section = ""
        if it.get("reply_body"):
            reply_section = f'<details><summary>reply text ({len(it["reply_body"])} chars)</summary><pre>{esc(it["reply_body"][:4000])}</pre></details>'
        rows_html.append(f"""
        <tr>
          <td class="ts">{esc(it["received_at"])[:19]}</td>
          <td>{esc(it["from_addr"])}</td>
          <td>{esc(it["subject"])[:80]}{mode_chip}{ad_chip}</td>
          <td>{esc(it["status"])}</td>
          <td>{cost}</td>
          <td><details><summary>inbound preview</summary><pre>{esc(it["preview"])}</pre></details>
              {reply_section}
          </td>
        </tr>
        """)

    return f"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<title>/os/stranger — Murphy Founder Dashboard</title>
<style>
  body {{ font-family: ui-monospace, Menlo, monospace; background: #0d1117; color: #c9d1d9; margin: 20px; }}
  h1 {{ color: #58a6ff; }}
  .stats {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin: 20px 0; }}
  .stat {{ background: #161b22; padding: 12px; border: 1px solid #30363d; border-radius: 6px; }}
  .stat .label {{ color: #8b949e; font-size: 11px; text-transform: uppercase; }}
  .stat .value {{ font-size: 28px; color: #58a6ff; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th, td {{ padding: 8px; border-bottom: 1px solid #30363d; vertical-align: top; }}
  th {{ background: #161b22; color: #8b949e; text-align: left; font-size: 11px; text-transform: uppercase; }}
  .ts {{ color: #8b949e; font-size: 11px; white-space: nowrap; }}
  .chip {{ display: inline-block; margin-left: 6px; padding: 2px 6px; border-radius: 3px; font-size: 10px; }}
  .chip.direct {{ background: #1f6feb; color: #fff; }}
  .chip.ambient {{ background: #d29922; color: #000; }}
  .chip.ad {{ background: #2ea043; color: #fff; }}
  pre {{ background: #0d1117; border: 1px solid #30363d; padding: 8px; white-space: pre-wrap; max-width: 800px; font-size: 11px; }}
  details summary {{ cursor: pointer; color: #58a6ff; font-size: 12px; }}
  .header {{ display: flex; justify-content: space-between; align-items: center; }}
  .header .ts {{ font-size: 12px; }}
</style></head>
<body>
<div class="header">
  <h1>/os/stranger — Stranger Reply Log</h1>
  <span class="ts">refreshed {esc(datetime.now(timezone.utc).isoformat()[:19])} UTC</span>
</div>

<div class="stats">
  <div class="stat"><div class="label">24h replies</div><div class="value">{stats["stranger_total"]}</div></div>
  <div class="stat"><div class="label">sent live</div><div class="value">{stats["stranger_sent"]}</div></div>
  <div class="stat"><div class="label">shadow (founder cc)</div><div class="value">{stats["stranger_shadow"]}</div></div>
  <div class="stat"><div class="label">direct / ambient</div><div class="value">{stats["direct_count"]} / {stats["ambient_count"]}</div></div>
  <div class="stat"><div class="label">ad impressions 24h</div><div class="value">{stats["ad_impressions"]}</div></div>
  <div class="stat"><div class="label">unique ads shown</div><div class="value">{stats["ad_unique"]}</div></div>
  <div class="stat"><div class="label">ad clicks</div><div class="value">{stats["ad_clicks"]}</div></div>
  <div class="stat"><div class="label">CTR</div><div class="value">{(100*stats["ad_clicks"]/stats["ad_impressions"]) if stats["ad_impressions"] else 0:.1f}%</div></div>
</div>

<table>
<thead><tr>
  <th>received</th><th>from</th><th>subject + mode + ad</th>
  <th>status</th><th>cost</th><th>bodies</th>
</tr></thead>
<tbody>
{"".join(rows_html)}
</tbody>
</table>

<p style="color:#8b949e; font-size:11px; margin-top:30px;">
Shape of Complete v2 — Ship 31i.C. Read-only. Joins inbound_replies + outbound_email_queue + ad_impressions.
</p>
</body></html>"""
