"""
R604 — Visible Agents Surface
==============================

Backend routes the founder can hit to SEE agent work.

GET  /api/agents                — list employed agents + their last artifact
GET  /api/agents/artifacts      — list all agent-produced artifacts
GET  /agents                    — HTML page rendering the above

This goes into a standalone microservice on port 8092 so it doesn't
touch the monolith (per founder canon: prefer microservice additions
over monolith edits). Nginx proxies /api/agents/* and /agents to it.
"""
import os, json, sqlite3, logging
from datetime import datetime, timezone
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from typing import List, Dict, Any

ENTITY_DB = "/var/lib/murphy-production/entity_graph.db"
ARTIFACTS_DIR = Path("/var/lib/murphy-production/artifacts")

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("r604_agents_surface")

app = FastAPI(title="Murphy Agents Surface")

# Known employed agents — registry. R603 added CTO; CFO/CSO/CEO come next.
KNOWN_AGENTS = {
    "cto": {
        "role": "Chief Technology Officer",
        "description": "Reads shape, journey, and wirer DBs; produces daily health report.",
        "first_employed": "2026-06-05",
        "artifact_category": "report",
        "schedule": "daily 08:00 PT (active)",
        "marker": "R603v2",
    },
    "cfo": {
        "role": "Chief Financial Officer",
        "description": "Reads treasury, capital_engine, and billing DBs; produces daily financial state report.",
        "first_employed": "2026-06-05",
        "artifact_category": "report",
        "schedule": "daily 08:15 PT (active)",
        "marker": "R603B",
    },
    "cso": {
        "role": "Chief Sales Officer",
        "description": "Reads CRM, sales_pipeline, and outreach DBs; produces daily sales report.",
        "first_employed": "2026-06-05",
        "artifact_category": "report",
        "schedule": "daily 08:30 PT (active)",
        "marker": "R603C",
    },
    "ceo": {
        "role": "Chief Executive Officer",
        "description": "Reads the latest CTO/CFO/CSO reports; produces a strategic synthesis brief.",
        "first_employed": "2026-06-05",
        "artifact_category": "report",
        "schedule": "daily 09:00 PT (active)",
        "marker": "R603D",
    },
}

def _conn():
    return sqlite3.connect(f"file:{ENTITY_DB}?mode=ro", uri=True)

def _agent_artifacts(role_key: str) -> List[Dict[str, Any]]:
    """Find artifacts attributed to a given agent role using its declared marker."""
    meta = KNOWN_AGENTS.get(role_key, {})
    marker = meta.get("marker", role_key.upper())
    conn = _conn()
    rows = conn.execute(
        "SELECT id, category, title, file_url, version, notes, created_at "
        "FROM data_room_artifacts WHERE notes LIKE ? ORDER BY created_at DESC LIMIT 20",
        (f"%{marker}%",)
    ).fetchall()
    conn.close()
    return [
        {"id": r[0], "category": r[1], "title": r[2], "file_url": r[3],
         "version": r[4], "notes": r[5], "created_at": r[6]}
        for r in rows
    ]

@app.get("/api/agents")
def list_agents():
    """Show every employed agent + their latest artifact."""
    result = []
    for key, meta in KNOWN_AGENTS.items():
        artifacts = _agent_artifacts(key)
        latest = artifacts[0] if artifacts else None
        result.append({
            "key": key,
            "role": meta["role"],
            "description": meta["description"],
            "first_employed": meta["first_employed"],
            "schedule": meta["schedule"],
            "total_artifacts": len(artifacts),
            "latest_artifact": latest,
        })
    return {"agents": result, "as_of": datetime.now(timezone.utc).isoformat()}

@app.get("/api/agents/artifacts")
def list_artifacts():
    """All artifacts in the data room, newest first."""
    conn = _conn()
    rows = conn.execute(
        "SELECT id, category, title, file_url, version, current, notes, created_at "
        "FROM data_room_artifacts ORDER BY created_at DESC LIMIT 100"
    ).fetchall()
    conn.close()
    return {
        "artifacts": [
            {
                "id": r[0], "category": r[1], "title": r[2],
                "file_url": r[3], "version": r[4], "current": bool(r[5]),
                "notes": r[6], "created_at": r[7],
            } for r in rows
        ],
        "count": len(rows),
    }

@app.get("/api/agents/artifacts/{artifact_id}")
def get_artifact(artifact_id: str):
    """Return artifact metadata + content if it's a file we can read."""
    conn = _conn()
    row = conn.execute(
        "SELECT id, category, title, file_url, notes, created_at "
        "FROM data_room_artifacts WHERE id = ?", (artifact_id,)
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, f"artifact {artifact_id} not found")
    meta = {"id": row[0], "category": row[1], "title": row[2],
            "file_url": row[3], "notes": row[4], "created_at": row[5]}
    # if file_url is a local path, include content
    if row[3] and row[3].startswith("/var/lib/murphy-production/artifacts/"):
        p = Path(row[3])
        if p.exists() and p.stat().st_size < 1_000_000:
            try:
                meta["content"] = p.read_text(errors="replace")
                meta["content_format"] = "markdown" if p.suffix == ".md" else "text"
            except Exception as e:
                meta["content_error"] = str(e)
    return meta

@app.get("/agents", response_class=HTMLResponse)
def agents_page():
    """Visible page — what founder loads in a browser."""
    return """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Murphy Agents</title>
<style>
body { font-family: -apple-system, system-ui, sans-serif; max-width: 900px; margin: 2em auto; padding: 0 1em; color: #1a1a1a; }
h1 { border-bottom: 2px solid #333; padding-bottom: 0.3em; }
.agent { background: #f7f7f9; border-left: 4px solid #4a7; padding: 1em 1.2em; margin: 1em 0; border-radius: 4px; }
.agent h3 { margin: 0 0 0.3em 0; }
.muted { color: #666; font-size: 0.9em; }
.artifact { background: #fff; border: 1px solid #ddd; padding: 0.6em 1em; margin: 0.5em 0; border-radius: 3px; }
.artifact a { color: #06c; text-decoration: none; }
.artifact a:hover { text-decoration: underline; }
pre { background: #f0f0f3; padding: 1em; border-radius: 4px; overflow-x: auto; font-size: 0.85em; }
.empty { color: #888; font-style: italic; }
</style>
</head>
<body>
<h1>Murphy Agents</h1>
<p class="muted">Every employed agent and what they've produced. Live data from data_room_artifacts.</p>
<div id="agents">Loading…</div>
<h2>All artifacts</h2>
<div id="artifacts">Loading…</div>
<script>
async function load() {
  const a = await fetch('/api/agents').then(r=>r.json());
  document.getElementById('agents').innerHTML = a.agents.map(ag => `
    <div class="agent">
      <h3>${ag.role}</h3>
      <div class="muted">${ag.description}</div>
      <div class="muted">First employed: ${ag.first_employed} · Schedule: ${ag.schedule} · Total artifacts: ${ag.total_artifacts}</div>
      ${ag.latest_artifact ? `
        <div class="artifact">
          <div><strong>Latest:</strong> <a href="/api/agents/artifacts/${ag.latest_artifact.id}">${ag.latest_artifact.title}</a></div>
          <div class="muted">${ag.latest_artifact.created_at}</div>
          <div class="muted">${ag.latest_artifact.notes || ''}</div>
        </div>
      ` : '<div class="empty">No artifacts yet.</div>'}
    </div>
  `).join('');
  const r = await fetch('/api/agents/artifacts').then(r=>r.json());
  document.getElementById('artifacts').innerHTML = r.artifacts.map(x => `
    <div class="artifact">
      <a href="/api/agents/artifacts/${x.id}">${x.title}</a>
      <span class="muted"> · ${x.category} · ${x.created_at}</span>
      ${x.notes ? `<div class="muted">${x.notes}</div>` : ''}
    </div>
  `).join('');
}
load();
</script>
</body>
</html>"""

@app.get("/health")
def health():
    return {"ok": True, "service": "r604_agents_surface"}
