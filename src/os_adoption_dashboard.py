"""
Ship 31r — /os/adoption + /os/role-audit founder dashboards.

Mirror pattern of /os/stranger from Ship 31i.C:
  - SQL only (no LLM), fast, server-rendered HTML
  - GitHub-dark theme for visual consistency
  - Joins on entity_graph.db tables only (low coupling)
"""
import sqlite3
from datetime import datetime, timezone

DB = "/var/lib/murphy-production/entity_graph.db"

_STYLE = """<style>
body{background:#0d1117;color:#c9d1d9;font:14px -apple-system,BlinkMacSystemFont,sans-serif;margin:0;padding:24px}
h1{color:#58a6ff;margin:0 0 8px 0}
.sub{color:#8b949e;margin:0 0 24px 0;font-size:13px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin:0 0 24px 0}
.stat{background:#161b22;border:1px solid #30363d;border-radius:6px;padding:12px}
.stat .label{color:#8b949e;font-size:11px;text-transform:uppercase;letter-spacing:.05em}
.stat .value{color:#c9d1d9;font-size:24px;font-weight:600;margin-top:4px}
table{width:100%;border-collapse:collapse;background:#161b22;border:1px solid #30363d;border-radius:6px;overflow:hidden}
th{background:#21262d;color:#8b949e;font-size:11px;text-transform:uppercase;letter-spacing:.05em;padding:10px 12px;text-align:left;border-bottom:1px solid #30363d}
td{padding:10px 12px;border-bottom:1px solid #21262d;vertical-align:top;font-size:13px}
tr:last-child td{border-bottom:none}
.muted{color:#6e7681}
.role{background:#1f6feb33;color:#79c0ff;padding:2px 6px;border-radius:3px;font-size:11px;font-family:monospace}
.vert{background:#3fb95033;color:#56d364;padding:2px 6px;border-radius:3px;font-size:11px;font-family:monospace;margin-left:4px}
.nav{margin-bottom:24px}
.nav a{color:#58a6ff;text-decoration:none;margin-right:16px;font-size:13px}
.nav a:hover{text-decoration:underline}
pre{background:#0d1117;border:1px solid #30363d;border-radius:4px;padding:8px;font-size:11px;color:#c9d1d9;overflow:auto;max-height:160px;white-space:pre-wrap}
</style>"""

_NAV = ('<div class="nav">'
        '<a href="/os/stranger">← strangers</a>'
        '<a href="/os/adoption">orgs</a>'
        '<a href="/os/role-audit">role-audit</a>'
        '</div>')


def _conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def render_adoption_html():
    """Render /os/adoption — which organizations are engaging."""
    c = _conn()
    rows = c.execute("""SELECT * FROM adoption_signal
        ORDER BY last_seen_ts DESC LIMIT 100""").fetchall()
    total_orgs = c.execute("SELECT COUNT(*) FROM adoption_signal").fetchone()[0]
    total_inbound = c.execute("SELECT COALESCE(SUM(inbound_count),0) FROM adoption_signal").fetchone()[0]
    total_outbound = c.execute("SELECT COALESCE(SUM(outbound_count),0) FROM adoption_signal").fetchone()[0]
    unsubs = c.execute("SELECT COUNT(*) FROM unsubscribe_registry").fetchone()[0]
    allow = c.execute("SELECT COUNT(*) FROM launch_allowlist WHERE status='active'").fetchone()[0]
    c.close()

    html = ["<!DOCTYPE html><html><head><meta charset='utf-8'>",
            "<title>Murphy — Organization Adoption</title>", _STYLE,
            "</head><body>", _NAV,
            "<h1>Organization Adoption</h1>",
            f"<p class='sub'>{total_orgs} organizations have engaged with Murphy · "
            f"as of {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</p>",
            "<div class='grid'>",
            f"<div class='stat'><div class='label'>Orgs Tracked</div><div class='value'>{total_orgs}</div></div>",
            f"<div class='stat'><div class='label'>Total Inbound</div><div class='value'>{total_inbound}</div></div>",
            f"<div class='stat'><div class='label'>Total Outbound</div><div class='value'>{total_outbound}</div></div>",
            f"<div class='stat'><div class='label'>Allowlisted</div><div class='value'>{allow}</div></div>",
            f"<div class='stat'><div class='label'>Unsubscribed</div><div class='value'>{unsubs}</div></div>",
            "</div>",
            "<table><thead><tr>",
            "<th>last seen</th><th>org</th><th>contact</th><th>role · vertical</th>",
            "<th>in</th><th>out</th><th>actions</th><th>last action</th>",
            "</tr></thead><tbody>"]

    if not rows:
        html.append("<tr><td colspan='8' class='muted'>No engagement yet. "
                    "When organizations email Murphy, they'll appear here.</td></tr>")
    else:
        for r in rows:
            ts = (r["last_seen_ts"] or "")[:19].replace("T", " ")
            role = f"<span class='role'>{r['role_first_detected'] or '?'}</span>"
            vert = f"<span class='vert'>{r['vertical_first_detected'] or '?'}</span>"
            unsub = " <span class='muted'>(unsub)</span>" if r["unsubscribed"] else ""
            html.append("<tr>"
                        f"<td class='muted'>{ts}</td>"
                        f"<td><strong>{r['org_domain']}</strong>{unsub}</td>"
                        f"<td class='muted'>{r['contact_addr'] or ''}</td>"
                        f"<td>{role}{vert}</td>"
                        f"<td>{r['inbound_count'] or 0}</td>"
                        f"<td>{r['outbound_count'] or 0}</td>"
                        f"<td>{r['actionable_count'] or 0}</td>"
                        f"<td class='muted'>{r['last_action'] or ''}</td>"
                        "</tr>")
    html.append("</tbody></table></body></html>")
    return "".join(html)


def render_role_audit_html():
    """Render /os/role-audit — multi-role test results with actionable extraction."""
    c = _conn()
    rows = c.execute("""SELECT * FROM role_audit_log
        ORDER BY run_ts DESC, id DESC LIMIT 50""").fetchall()
    total = c.execute("SELECT COUNT(*) FROM role_audit_log").fetchone()[0]
    unique_runs = c.execute("SELECT COUNT(DISTINCT run_ts) FROM role_audit_log").fetchone()[0]
    avg_cost = c.execute("SELECT AVG(reply_cost_usd) FROM role_audit_log").fetchone()[0] or 0
    avg_latency = c.execute("SELECT AVG(reply_latency_s) FROM role_audit_log").fetchone()[0] or 0
    c.close()

    html = ["<!DOCTYPE html><html><head><meta charset='utf-8'>",
            "<title>Murphy — Role Audit Log</title>", _STYLE,
            "</head><body>", _NAV,
            "<h1>Role-Synthesis Audit Log</h1>",
            f"<p class='sub'>{total} runs across {unique_runs} test batches · "
            "every actionable commitment Murphy made, examinable after the fact</p>",
            "<div class='grid'>",
            f"<div class='stat'><div class='label'>Total runs</div><div class='value'>{total}</div></div>",
            f"<div class='stat'><div class='label'>Test batches</div><div class='value'>{unique_runs}</div></div>",
            f"<div class='stat'><div class='label'>Avg cost</div><div class='value'>${avg_cost:.5f}</div></div>",
            f"<div class='stat'><div class='label'>Avg latency</div><div class='value'>{avg_latency:.1f}s</div></div>",
            "</div>"]

    if not rows:
        html.append("<p class='muted'>No role-audit runs yet. "
                    "Run the multi-role stress test to populate this.</p>")
    else:
        for r in rows:
            ts = (r["run_ts"] or "")[:19].replace("T", " ")
            import json
            try:
                actions = json.loads(r["actionable_extracted"] or "[]")
            except Exception:
                actions = []
            actions_html = "".join(f"<li>{a}</li>" for a in actions) or "<li class='muted'>no actionable extracted</li>"
            ad = r["ad_advertiser"] or "—"
            ad_kw = r["ad_keywords_matched"] or ""

            html.append(f"<div style='background:#161b22;border:1px solid #30363d;border-radius:6px;padding:16px;margin:12px 0'>"
                        f"<div style='display:flex;justify-content:space-between;margin-bottom:8px'>"
                        f"<strong style='color:#58a6ff'>{r['label']}</strong>"
                        f"<span class='muted'>{ts}</span></div>"
                        f"<div style='margin:8px 0'>"
                        f"<span class='role'>{r['role_detected']}</span>"
                        f"<span class='vert'>{r['vertical_detected']}</span>"
                        f"<span class='muted' style='margin-left:8px'>ad: {ad} ({ad_kw})</span>"
                        f"<span class='muted' style='margin-left:8px'>cost: ${r['reply_cost_usd']:.5f}</span>"
                        f"<span class='muted' style='margin-left:8px'>{r['reply_latency_s']:.1f}s</span>"
                        f"</div>"
                        f"<div class='muted' style='font-size:11px;margin-top:8px'>FROM: {r['from_addr']} — {r['subject']}</div>"
                        f"<div style='margin-top:8px'><strong>Actionable commitments:</strong>"
                        f"<ul style='margin:4px 0;padding-left:20px'>{actions_html}</ul></div>"
                        f"<details style='margin-top:8px'><summary class='muted' style='cursor:pointer'>full reply ({len(r['reply_full'] or '')} chars)</summary>"
                        f"<pre>{(r['reply_full'] or '').replace('<','&lt;')}</pre></details>"
                        f"</div>")
    html.append("</body></html>")
    return "".join(html)


def render_leaderboard_html():
    """Render /os/agent-leaderboard — top agents by fitness with deployments."""
    from src.agent_rating_loop import get_leaderboard, get_recent_uses

    rows = get_leaderboard(limit=50)
    recent = get_recent_uses(limit=30)
    total = len(rows)
    high_fit = sum(1 for r in rows if (r.get("fitness_score") or 0) >= 0.65)
    total_deps = sum((r.get("deployments") or 0) for r in rows)
    avg_q = (sum((r.get("last_quality_score") or 0) for r in rows) / total) if total else 0

    html = ["<!DOCTYPE html><html><head><meta charset='utf-8'>",
            "<title>Murphy — Agent Leaderboard</title>", _STYLE,
            "</head><body>", _NAV,
            "<h1>Agent Leaderboard</h1>",
            f"<p class='sub'>{total} role agents tracked · "
            f"{high_fit} above 0.65 reuse threshold · "
            f"{total_deps} total deployments · "
            f"avg last-quality {avg_q:.2f}</p>",
            "<div class='grid'>",
            f"<div class='stat'><div class='label'>Agents</div><div class='value'>{total}</div></div>",
            f"<div class='stat'><div class='label'>Reusable (≥0.65)</div><div class='value'>{high_fit}</div></div>",
            f"<div class='stat'><div class='label'>Deployments</div><div class='value'>{total_deps}</div></div>",
            f"<div class='stat'><div class='label'>Avg last-quality</div><div class='value'>{avg_q:.2f}</div></div>",
            "</div>",
            "<h2 style='color:#58a6ff;margin-top:32px'>Ranking</h2>",
            "<table><thead><tr>",
            "<th>rank</th><th>role · vertical</th><th>fitness</th>",
            "<th>deployments</th><th>last quality</th><th>soul size</th><th>last used</th>",
            "</tr></thead><tbody>"]

    if not rows:
        html.append("<tr><td colspan='7' class='muted'>No agents yet. They're created on first use.</td></tr>")
    else:
        for i, r in enumerate(rows, 1):
            fit = r.get("fitness_score") or 0
            reusable = fit >= 0.65
            fit_color = "#56d364" if reusable else "#8b949e"
            ts = (r.get("last_used_ts") or "")[:19].replace("T", " ")
            sig = r.get("role_signature") or "?"
            role, _, vert = sig.partition(":")
            html.append(
                f"<tr><td><strong>#{i}</strong></td>"
                f"<td><span class='role'>{role}</span><span class='vert'>{vert}</span></td>"
                f"<td style='color:{fit_color};font-weight:600'>{fit:.3f}</td>"
                f"<td>{r.get('deployments') or 0}</td>"
                f"<td>{(r.get('last_quality_score') or 0):.2f}</td>"
                f"<td class='muted'>{r.get('soul_len') or 0}b</td>"
                f"<td class='muted'>{ts}</td></tr>"
            )
    html.append("</tbody></table>")

    html.append("<h2 style='color:#58a6ff;margin-top:32px'>Recent uses</h2>")
    html.append("<table><thead><tr><th>when</th><th>role</th><th>score</th>"
                "<th>cost</th><th>latency</th><th>routing</th></tr></thead><tbody>")
    if not recent:
        html.append("<tr><td colspan='6' class='muted'>No use log yet.</td></tr>")
    else:
        for u in recent:
            ts = (u.get("used_ts") or "")[:19].replace("T", " ")
            persisted = "🔄" if u.get("used_persisted_soul") else "🆕"
            score = u.get("judge_score") or 0
            score_color = "#56d364" if score >= 0.7 else ("#d29922" if score >= 0.4 else "#f85149")
            html.append(
                f"<tr><td class='muted'>{ts}</td>"
                f"<td><span class='role'>{u.get('role_signature') or '?'}</span></td>"
                f"<td style='color:{score_color};font-weight:600'>{score:.2f}</td>"
                f"<td>${(u.get('cost_usd') or 0):.5f}</td>"
                f"<td>{(u.get('latency_s') or 0):.1f}s</td>"
                f"<td class='muted'>{persisted} {(u.get('routing_decision') or '')[:60]}</td></tr>"
            )
    html.append("</tbody></table></body></html>")
    return "".join(html)
