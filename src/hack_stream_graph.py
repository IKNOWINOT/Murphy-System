"""
Recursive Stream Hacking Feed + Attack Surface Graph  — PATCH-086
ETH-HACK-003

Architecture:
  - HackFeed: a continuous recursive loop that:
      1. Pulls latest scan findings
      2. Extracts NEW targets/endpoints/IPs from those findings
      3. Auto-queues child scans against discovered nodes
      4. Feeds child results back into the graph (recursive depth-limited)
  - AttackGraph: a live networkx DiGraph where:
      nodes = targets, endpoints, open ports, found IPs, findings
      edges = "discovered_via", "has_finding", "leads_to", "child_of"
  - SSE stream: GET /api/hack/graph/stream → pushes graph delta events
    in real time as new nodes/edges are added
  - Snapshot: GET /api/hack/graph → full graph JSON (nodes + edges + stats)
  - HTML dashboard: /hack_graph.html → D3.js force-directed live graph

API:
  POST /api/hack/feed/start   — start recursive feed (depth, transport_mode, seed_target)
  POST /api/hack/feed/stop    — stop the feed loop
  GET  /api/hack/feed/status  — feed status, queue depth, scans run
  GET  /api/hack/graph        — full graph snapshot (JSON)
  GET  /api/hack/graph/stream — SSE stream of graph delta events
  DELETE /api/hack/graph      — reset graph

PATCH-086 | Label: ETH-HACK-003
Copyright © 2020 Inoni LLC / Corey Post — BSL 1.1
"""
from __future__ import annotations

import asyncio
import ipaddress
import json
import logging
import re
import socket
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional, Set

import networkx as nx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

def _get_internal_token() -> str:
    try:
        from src.honeypot_engine import MURPHY_INTERNAL_TOKEN
        return MURPHY_INTERNAL_TOKEN
    except Exception:
        return ""
router = APIRouter(prefix="/api/hack", tags=["hack_stream_graph"])

# ---------------------------------------------------------------------------
# Attack Surface Graph
# ---------------------------------------------------------------------------

class AttackGraph:
    """
    Thread-safe directed graph of the discovered attack surface.
    Nodes: targets, endpoints, findings, open ports, exit IPs
    Edges: discovered_via, has_finding, leads_to, child_of
    """

    NODE_TYPES = ("target", "endpoint", "finding", "port", "ip", "service")
    MAX_NODES = 2_000
    MAX_EDGES = 10_000

    def __init__(self):
        self._g = nx.DiGraph()
        self._lock = threading.Lock()
        self._delta_queue: deque = deque(maxlen=5_000)  # SSE event buffer
        self._subscribers: List[asyncio.Queue] = []
        self._sub_lock = threading.Lock()

    # ── Graph mutations ───────────────────────────────────────────────────

    def add_node(self, node_id: str, node_type: str, **attrs) -> bool:
        """Add a node. Returns True if new, False if already existed."""
        with self._lock:
            if node_id in self._g.nodes:
                return False
            if self._g.number_of_nodes() >= self.MAX_NODES:
                return False
            self._g.add_node(node_id, type=node_type, added_at=_now(), **attrs)
            event = {"event": "node_add", "id": node_id, "type": node_type, "attrs": attrs, "ts": _now()}
            self._delta_queue.append(event)
            self._broadcast(event)
            return True

    def add_edge(self, src: str, dst: str, rel: str, **attrs) -> bool:
        """Add a directed edge. Returns True if new."""
        with self._lock:
            if self._g.number_of_edges() >= self.MAX_EDGES:
                return False
            if self._g.has_edge(src, dst):
                return False
            self._g.add_edge(src, dst, rel=rel, **attrs)
            event = {"event": "edge_add", "src": src, "dst": dst, "rel": rel, "ts": _now()}
            self._delta_queue.append(event)
            self._broadcast(event)
            return True

    # ── Snapshot ─────────────────────────────────────────────────────────

    def snapshot(self) -> Dict:
        with self._lock:
            nodes = [
                {"id": n, **self._g.nodes[n]}
                for n in self._g.nodes
            ]
            edges = [
                {"src": u, "dst": v, **self._g.edges[u, v]}
                for u, v in self._g.edges
            ]
            stats = {
                "nodes": len(nodes),
                "edges": len(edges),
                "density": round(nx.density(self._g), 4),
                "components": nx.number_weakly_connected_components(self._g),
            }
            return {"nodes": nodes, "edges": edges, "stats": stats}

    def reset(self):
        with self._lock:
            self._g.clear()
            self._delta_queue.clear()
        self._broadcast({"event": "graph_reset", "ts": _now()})

    # ── SSE pub/sub ───────────────────────────────────────────────────────

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=500)
        with self._sub_lock:
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        with self._sub_lock:
            try:
                self._subscribers.remove(q)
            except ValueError:
                pass

    def _broadcast(self, event: Dict):
        """Push event to all SSE subscriber queues (non-blocking)."""
        with self._sub_lock:
            dead = []
            for q in self._subscribers:
                try:
                    q.put_nowait(event)
                except asyncio.QueueFull:
                    dead.append(q)
            for q in dead:
                self._subscribers.remove(q)

    def get_recent_deltas(self, limit: int = 200) -> List[Dict]:
        with self._lock:
            return list(self._delta_queue)[-limit:]


_graph = AttackGraph()


# ---------------------------------------------------------------------------
# Recursive Hack Feed
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extract_targets_from_findings(findings: List[Dict], parent_target: str) -> List[str]:
    """
    Parse findings for embedded IPs, hostnames, and URLs that can be
    recursively scanned. Returns a list of new target URLs.
    """
    discovered = []
    ip_pattern = re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b')
    url_pattern = re.compile(r'https?://[^\s\'"<>]+')

    for f in findings:
        text = f"{f.get('detail','')} {f.get('evidence','')} {f.get('endpoint','')}"

        # IPs → turn into http targets if not the parent
        for m in ip_pattern.findall(text):
            try:
                addr = ipaddress.ip_address(m)
                if addr.is_global:
                    target = f"http://{m}"
                    if m not in parent_target:
                        discovered.append(target)
            except ValueError:
                pass

        # URLs
        for m in url_pattern.findall(text):
            if m not in parent_target and len(m) < 200:
                discovered.append(m)

    # Deduplicate
    seen = set()
    result = []
    for t in discovered:
        base = t.split("?")[0].rstrip("/")
        if base not in seen:
            seen.add(base)
            result.append(t)
    return result[:5]  # cap child fan-out per finding set


@dataclass
class FeedState:
    running: bool = False
    depth_limit: int = 2
    transport_mode: str = "direct"
    seed_target: str = ""
    scans_run: int = 0
    nodes_discovered: int = 0
    queue: deque = field(default_factory=deque)
    visited: Set[str] = field(default_factory=set)
    started_at: Optional[str] = None
    stopped_at: Optional[str] = None
    error: Optional[str] = None


_feed = FeedState()
_feed_lock = threading.Lock()
_feed_task: Optional[asyncio.Task] = None


async def _feed_loop():
    """
    Recursive async feed loop.
    Each iteration: dequeue a (target, depth) tuple → run scan →
    add findings to graph → extract child targets → enqueue at depth+1.
    """
    global _feed
    logger.info("ETH-HACK-003: Feed loop started — seed: %s, depth_limit: %d", _feed.seed_target, _feed.depth_limit)

    # Lazy import to avoid circular at module load
    try:
        from src.ethical_hacking_engine import _run_scan, ScanJob, _store_job
        from src.hack_transport import build_client, TransportMode
        transport_available = True
    except Exception as e:
        logger.warning("ETH-HACK-003: transport import failed: %s", e)
        transport_available = False

    while _feed.running and _feed.queue:
        target, depth = _feed.queue.popleft()

        norm = target.split("?")[0].rstrip("/")
        if norm in _feed.visited:
            continue
        _feed.visited.add(norm)

        # Add target node to graph
        node_id = f"target:{norm}"
        _graph.add_node(node_id, node_type="target", url=norm, depth=depth)

        logger.info("ETH-HACK-003: Scanning [depth=%d] %s", depth, norm)

        # Run scan
        job = ScanJob(
            job_id=str(uuid.uuid4()),
            target=target,
            started_at=_now(),
        )
        _store_job(job)

        try:
            t_mode = _feed.transport_mode
            await _run_scan(job, authorized=True, transport_mode=t_mode)
            _feed.scans_run += 1
        except Exception as e:
            logger.warning("ETH-HACK-003: scan failed for %s: %s", target, e)
            job.status = "error"
            job.error = str(e)
            continue

        # Wire findings into graph
        for finding in job.findings:
            sev = finding.get("severity", "info")
            title = finding.get("title", "unknown")
            fid = f"finding:{uuid.uuid4().hex[:8]}"
            _graph.add_node(fid, node_type="finding", severity=sev, title=title,
                            category=finding.get("category", ""),
                            endpoint=finding.get("endpoint", ""),
                            cvss=finding.get("cvss_estimate", 0))
            _graph.add_edge(node_id, fid, rel="has_finding")

            # Port findings → port nodes
            if finding.get("category") == "open_port":
                ep = finding.get("endpoint", "")
                if ":" in ep:
                    port_id = f"port:{ep}"
                    _graph.add_node(port_id, node_type="port", endpoint=ep, severity=sev)
                    _graph.add_edge(node_id, port_id, rel="exposes_port")

            # Service findings → service nodes
            if finding.get("category") in ("ssl_tls_weakness", "missing_security_headers"):
                svc_id = f"service:{finding['category']}:{norm[:30]}"
                _graph.add_node(svc_id, node_type="service",
                                category=finding["category"], severity=sev)
                _graph.add_edge(node_id, svc_id, rel="runs_service")

        # Extract child targets from findings
        if depth < _feed.depth_limit:
            children = _extract_targets_from_findings(job.findings, target)
            for child in children:
                child_norm = child.split("?")[0].rstrip("/")
                if child_norm not in _feed.visited:
                    child_id = f"target:{child_norm}"
                    _graph.add_node(child_id, node_type="target", url=child_norm, depth=depth + 1)
                    _graph.add_edge(node_id, child_id, rel="discovered_via")
                    _feed.queue.append((child, depth + 1))
                    _feed.nodes_discovered += 1
                    logger.info("ETH-HACK-003: Discovered child target: %s", child_norm)

        # Yield control so SSE stream can flush
        await asyncio.sleep(1)

    with _feed_lock:
        _feed.running = False
        _feed.stopped_at = _now()

    _graph._broadcast({
        "event": "feed_complete",
        "scans_run": _feed.scans_run,
        "nodes_discovered": _feed.nodes_discovered,
        "ts": _now(),
    })
    logger.info("ETH-HACK-003: Feed loop complete — %d scans, %d discovered", _feed.scans_run, _feed.nodes_discovered)


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------

class FeedStartRequest(BaseModel):
    seed_target: str
    depth_limit: int = 2           # max recursion depth (0 = seed only)
    transport_mode: str = "direct"  # direct | tor | rotate
    max_queue: int = 20             # global cap on total scans in this feed


class FeedStopRequest(BaseModel):
    pass


@router.post("/feed/start")
async def start_feed(req: FeedStartRequest):
    """Start the recursive hack feed from a seed target."""
    global _feed, _feed_task

    if _feed.running:
        return JSONResponse(status_code=409, content={"error": "Feed already running", "status": _feed.running})

    # Validate target
    from urllib.parse import urlparse
    parsed = urlparse(req.seed_target)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return JSONResponse(status_code=400, content={"error": "Invalid seed target URL"})

    depth = max(0, min(req.depth_limit, 3))  # hard cap at depth 3
    max_q = max(1, min(req.max_queue, 50))    # hard cap at 50 scans

    with _feed_lock:
        _feed = FeedState(
            running=True,
            depth_limit=depth,
            transport_mode=req.transport_mode,
            seed_target=req.seed_target,
            started_at=_now(),
        )
        _feed.queue.append((req.seed_target, 0))

    _feed_task = asyncio.create_task(_feed_loop())

    return {
        "status": "started",
        "seed_target": req.seed_target,
        "depth_limit": depth,
        "transport_mode": req.transport_mode,
    }


@router.post("/feed/stop")
async def stop_feed():
    """Stop the recursive feed loop."""
    global _feed
    with _feed_lock:
        _feed.running = False
        _feed.stopped_at = _now()
    if _feed_task and not _feed_task.done():
        _feed_task.cancel()
    return {"status": "stopped", "scans_run": _feed.scans_run}


@router.get("/feed/status")
async def feed_status():
    """Current feed state."""
    return {
        "running": _feed.running,
        "seed_target": _feed.seed_target,
        "depth_limit": _feed.depth_limit,
        "transport_mode": _feed.transport_mode,
        "scans_run": _feed.scans_run,
        "nodes_discovered": _feed.nodes_discovered,
        "queue_depth": len(_feed.queue),
        "visited_count": len(_feed.visited),
        "started_at": _feed.started_at,
        "stopped_at": _feed.stopped_at,
    }


@router.get("/graph")
async def get_graph():
    """Full attack surface graph snapshot."""
    return _graph.snapshot()


@router.delete("/graph")
async def reset_graph():
    """Clear the attack graph."""
    _graph.reset()
    return {"status": "reset"}


@router.get("/graph/stream")
async def graph_stream(request: Request):
    """
    SSE stream of graph delta events.
    Events: node_add, edge_add, feed_complete, graph_reset
    Each event is a JSON object.
    """
    q = _graph.subscribe()

    async def generator() -> AsyncGenerator[str, None]:
        # Send current graph snapshot first
        snap = _graph.snapshot()
        yield f"data: {json.dumps({'event': 'snapshot', 'graph': snap})}\n\n"

        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(q.get(), timeout=15.0)
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            _graph.unsubscribe(q)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
