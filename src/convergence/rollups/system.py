"""System domain — health, git, deploys, snapshots."""
import subprocess
from typing import Dict, Any


def rollup_system(tenant_id: str | None = None) -> Dict[str, Any]:
    git_head = "unknown"
    try:
        r = subprocess.run(
            ["git", "-C", "/opt/Murphy-System", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=2,
        )
        if r.returncode == 0:
            git_head = r.stdout.strip()
    except Exception:
        pass

    # service uptime
    uptime = None
    try:
        r = subprocess.run(
            ["systemctl", "show", "murphy-production.service",
             "--property=ActiveEnterTimestamp", "--value"],
            capture_output=True, text=True, timeout=2,
        )
        if r.returncode == 0:
            uptime = r.stdout.strip()
    except Exception:
        pass

    summary = {
        "deploy_commit": git_head,
        "service_started_at": uptime,
        "service_status": "healthy",  # TODO: actual probe
    }
    return {
        "summary": summary,
        "items": [],
        "raw_endpoints": [
            "/health",
            "/api/self/health",
            "/api/self/git",
        ],
    }
