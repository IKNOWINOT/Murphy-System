"""
PATCH-120 — src/hitl_gate_swarm.py
Murphy System — Swarm Rosetta HITL Gate (Human-In-The-Loop)

When a DAG reaches a HITL node (stake=high/critical):
  1. Pause the DAG — serialize its state to hitl_queue SQLite table
  2. Notify the human via available channel (Telegram bot if configured, else log)
  3. Expose GET /api/hitl/pending + POST /api/hitl/approve/{id}
  4. On approval: resume DAG from the blocked node (not restart)
  5. On 24h timeout: auto-cancel and notify

This replaces the stub BlockedError-only approach in workflow_dag.py.

Copyright © 2020-2026 Inoni LLC — Created by Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("murphy.hitl_gate_swarm")

_DB_PATH = Path("/var/lib/murphy-production/hitl_queue.db")
_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

HITL_TIMEOUT_HOURS = 24


@dataclass
class HITLRequest:
    hitl_id: str
    dag_id: str
    dag_name: str
    blocked_node_id: str
    blocked_node_name: str
    intent: str
    domain: str
    stake: str
    account: str
    created_at: str
    expires_at: str
    status: str = "pending"   # pending | approved | rejected | expired | cancelled
    approved_by: Optional[str] = None
    resolved_at: Optional[str] = None
    dag_state_json: str = ""  # serialized dag dict for resume


class HITLQueue:
    """Persistent HITL approval queue."""

    def __init__(self, db_path: Path = _DB_PATH):
        self._db_path = db_path
        self._lock = threading.Lock()
        self._init_db()
        self._start_expiry_watcher()

    def _conn(self):
        return sqlite3.connect(str(self._db_path), timeout=10)

    def _init_db(self):
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS hitl_queue (
                    hitl_id           TEXT PRIMARY KEY,
                    dag_id            TEXT,
                    dag_name          TEXT,
                    blocked_node_id   TEXT,
                    blocked_node_name TEXT,
                    intent            TEXT,
                    domain            TEXT,
                    stake             TEXT,
                    account           TEXT,
                    created_at        TEXT,
                    expires_at        TEXT,
                    status            TEXT DEFAULT 'pending',
                    approved_by       TEXT,
                    resolved_at       TEXT,
                    dag_state_json    TEXT
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_hitl_status ON hitl_queue(status)")

    def enqueue(self, dag, blocked_node) -> HITLRequest:
        """Pause a DAG at a HITL node. Persist for human review."""
        now = datetime.now(timezone.utc)
        expires = now + timedelta(hours=HITL_TIMEOUT_HOURS)
        req = HITLRequest(
            hitl_id=f"hitl-{uuid.uuid4().hex[:10]}",
            dag_id=dag.dag_id,
            dag_name=dag.name,
            blocked_node_id=blocked_node.node_id,
            blocked_node_name=blocked_node.name,
            intent=dag.origin_nl_text or dag.name,
            domain=dag.domain,
            stake=dag.stake,
            account=dag.account,
            created_at=now.isoformat(),
            expires_at=expires.isoformat(),
            dag_state_json=json.dumps(dag.to_dict()),
        )
        with self._lock:
            with self._conn() as conn:
                conn.execute("""
                    INSERT INTO hitl_queue
                    (hitl_id,dag_id,dag_name,blocked_node_id,blocked_node_name,
                     intent,domain,stake,account,created_at,expires_at,
                     status,approved_by,resolved_at,dag_state_json)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    req.hitl_id, req.dag_id, req.dag_name,
                    req.blocked_node_id, req.blocked_node_name,
                    req.intent, req.domain, req.stake, req.account,
                    req.created_at, req.expires_at,
                    req.status, req.approved_by, req.resolved_at, req.dag_state_json
                ))
        self._notify(req)
        logger.warning("HITL: DAG %s paused at node '%s' [stake=%s] → hitl_id=%s",
                       dag.dag_id, blocked_node.name, dag.stake, req.hitl_id)
        return req

    def approve(self, hitl_id: str, approved_by: str = "human") -> Optional[Dict]:
        """Approve a pending HITL request. Returns resumed DAG result or None."""
        with self._lock:
            with self._conn() as conn:
                row = conn.execute(
                    "SELECT * FROM hitl_queue WHERE hitl_id=? AND status='pending'", (hitl_id,)
                ).fetchone()
                if not row:
                    return None
                cols = ["hitl_id","dag_id","dag_name","blocked_node_id","blocked_node_name",
                        "intent","domain","stake","account","created_at","expires_at",
                        "status","approved_by","resolved_at","dag_state_json"]
                req_dict = dict(zip(cols, row))

                now = datetime.now(timezone.utc).isoformat()
                conn.execute(
                    "UPDATE hitl_queue SET status='approved', approved_by=?, resolved_at=? WHERE hitl_id=?",
                    (approved_by, now, hitl_id)
                )

        # Resume the DAG
        logger.info("HITL: approved %s by %s — resuming DAG %s", hitl_id, approved_by, req_dict["dag_id"])
        return self._resume_dag(req_dict, approved_by)

    def reject(self, hitl_id: str, rejected_by: str = "human") -> bool:
        with self._lock:
            with self._conn() as conn:
                now = datetime.now(timezone.utc).isoformat()
                conn.execute(
                    "UPDATE hitl_queue SET status='rejected', approved_by=?, resolved_at=? "
                    "WHERE hitl_id=? AND status='pending'",
                    (rejected_by, now, hitl_id)
                )
        logger.info("HITL: rejected %s by %s", hitl_id, rejected_by)
        return True

    def pending(self) -> List[Dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT hitl_id,dag_id,dag_name,blocked_node_name,intent,domain,stake,account,created_at,expires_at "
                "FROM hitl_queue WHERE status='pending' ORDER BY created_at DESC"
            ).fetchall()
        cols = ["hitl_id","dag_id","dag_name","blocked_node_name","intent","domain","stake","account","created_at","expires_at"]
        return [dict(zip(cols, r)) for r in rows]

    def stats(self) -> Dict:
        with self._conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM hitl_queue").fetchone()[0]
            by_status = conn.execute("SELECT status, COUNT(*) FROM hitl_queue GROUP BY status").fetchall()
        return {"total": total, "by_status": {s: c for s, c in by_status}}

    def _notify(self, req: HITLRequest):
        """Notify human via Telegram if configured, else log prominently."""
        telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        telegram_chat = os.environ.get("TELEGRAM_CHAT_ID", "")

        msg = (
            f"🔴 MURPHY HITL APPROVAL REQUIRED\n"
            f"DAG: {req.dag_name}\n"
            f"Node: {req.blocked_node_name}\n"
            f"Intent: {req.intent[:120]}\n"
            f"Stake: {req.stake.upper()}\n"
            f"Domain: {req.domain}\n"
            f"Expires: {req.expires_at[:16]} UTC\n\n"
            f"Approve: POST /api/hitl/approve/{req.hitl_id}\n"
            f"Reject:  POST /api/hitl/reject/{req.hitl_id}"
        )

        if telegram_token and telegram_chat:
            try:
                import urllib.request
                payload = json.dumps({"chat_id": telegram_chat, "text": msg}).encode()
                req_http = urllib.request.Request(
                    f"https://api.telegram.org/bot{telegram_token}/sendMessage",
                    data=payload,
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )
                urllib.request.urlopen(req_http, timeout=5)
                logger.info("HITL: Telegram notification sent for %s", req.hitl_id)
            except Exception as exc:
                logger.warning("HITL: Telegram notify failed: %s", exc)
        else:
            # No Telegram configured — log prominently so it's visible in journal
            logger.warning(
                "HITL PENDING (no Telegram configured):\n%s\n"
                "→ To approve: curl -X POST http://127.0.0.1:8000/api/hitl/approve/%s",
                msg, req.hitl_id
            )

    def _resume_dag(self, req_dict: Dict, approved_by: str) -> Optional[Dict]:
        """Deserialize DAG, mark HITL node as DONE, continue execution."""
        try:
            from src.workflow_dag import DAGGraph, DAGNode, NodeType, NodeStatus, DAGExecutor, WorkflowDB
            dag_data = json.loads(req_dict["dag_state_json"])

            # Rebuild DAG
            dag = DAGGraph(
                dag_id=dag_data["dag_id"],
                name=dag_data["name"],
                description=dag_data.get("description",""),
                domain=dag_data["domain"],
                stake=dag_data["stake"],
                account=dag_data["account"],
                created_at=dag_data["created_at"],
                status=dag_data["status"],
                origin_signal_id=dag_data.get("origin_signal_id"),
                origin_nl_text=dag_data.get("origin_nl_text"),
            )
            for nd in dag_data.get("nodes", []):
                node = DAGNode(
                    node_id=nd["node_id"],
                    node_type=NodeType(nd["node_type"]),
                    name=nd["name"],
                    description=nd["description"],
                    config=nd.get("config", {}),
                    depends_on=nd.get("depends_on", []),
                    status=NodeStatus(nd["status"]),
                    result=nd.get("result"),
                    error=nd.get("error"),
                )
                dag.nodes.append(node)

            # Mark the HITL node as DONE so executor continues
            blocked_id = req_dict["blocked_node_id"]
            for node in dag.nodes:
                if node.node_id == blocked_id and node.status == NodeStatus.BLOCKED:
                    node.status = NodeStatus.DONE
                    node.result = {"hitl_approved_by": approved_by}
                    break

            dag.status = "running"
            executor = DAGExecutor(db=WorkflowDB())
            result_dag = executor.execute(dag)
            return {"dag_id": dag.dag_id, "status": result_dag.status,
                    "nodes": [(n.name, n.status) for n in result_dag.nodes]}
        except Exception as exc:
            logger.error("HITL resume failed: %s", exc)
            return {"error": str(exc)}

    def _start_expiry_watcher(self):
        """Background thread: expire HITL requests older than 24h."""
        def _watch():
            while True:
                try:
                    now = datetime.now(timezone.utc).isoformat()
                    with self._lock:
                        with self._conn() as conn:
                            expired = conn.execute(
                                "SELECT hitl_id FROM hitl_queue WHERE status='pending' AND expires_at < ?",
                                (now,)
                            ).fetchall()
                            for (hid,) in expired:
                                conn.execute(
                                    "UPDATE hitl_queue SET status='expired', resolved_at=? WHERE hitl_id=?",
                                    (now, hid)
                                )
                                logger.warning("HITL: request %s expired (24h timeout)", hid)
                except Exception as exc:
                    logger.warning("HITL expiry watcher error: %s", exc)
                time.sleep(300)  # check every 5 min

        t = threading.Thread(target=_watch, daemon=True, name="hitl-expiry-watcher")
        t.start()


# ── Singleton ─────────────────────────────────────────────────────────────────
_hitl_queue: Optional[HITLQueue] = None
_hitl_lock = threading.Lock()

def get_hitl_queue() -> HITLQueue:
    global _hitl_queue
    if _hitl_queue is None:
        with _hitl_lock:
            if _hitl_queue is None:
                _hitl_queue = HITLQueue()
    return _hitl_queue
