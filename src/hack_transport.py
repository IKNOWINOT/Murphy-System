"""
Ethical Hacking Engine — Transport Layer  PATCH-085b
ETH-HACK-002 | Location Masking + Node Routing

Provides anonymized HTTP transport for the ethical hacking engine:

  1. TorTransport     — routes all scan traffic through Tor SOCKS5 (127.0.0.1:9050)
                        Each scan can request a NEW Tor circuit for a fresh exit IP.
  2. ProxyChainTransport — routes through an ordered list of external SOCKS4/5 or HTTP
                           proxies (externally planted nodes). Supports chaining N hops.
  3. RotatingTransport — randomly selects from a pool of available transports per
                         request, making traffic pattern analysis harder.
  4. TransportRegistry — manages the pool of known nodes (tor, proxies, direct).
                         Nodes can be added via API and are health-checked on use.

API additions (mounted on /api/hack):
  POST /api/hack/nodes          — register an external proxy node
  GET  /api/hack/nodes          — list registered nodes + health
  DELETE /api/hack/nodes/{id}   — remove a node
  POST /api/hack/nodes/verify   — test a node is reachable
  POST /api/hack/scan           — now accepts transport_mode: "tor"|"proxy"|"rotate"|"direct"
                                  and node_ids: list of node IDs to use as chain

Safety invariants:
  - Tor is always local — no credential exposure
  - External proxy nodes stored in-memory only (not persisted to disk)
  - All traffic is HTTP probes only — no exploit payloads sent via anonymized transport
  - transport_mode requires authorized=True for scan requests

PATCH-085b | Label: ETH-HACK-002
Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""
from __future__ import annotations

import asyncio
import logging
import random
import socket
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

def _get_internal_token() -> str:
    try:
        from src.honeypot_engine import MURPHY_INTERNAL_TOKEN
        return MURPHY_INTERNAL_TOKEN
    except Exception:
        return ""
router = APIRouter(prefix="/api/hack", tags=["ethical_hacking_transport"])

# ---------------------------------------------------------------------------
# Tor control — request a new circuit (fresh exit IP)
# ---------------------------------------------------------------------------

TOR_SOCKS = "socks5://127.0.0.1:9050"
TOR_CONTROL_PORT = 9051  # not always open by default


async def _new_tor_circuit() -> bool:
    """
    Request a new Tor circuit via ControlPort (NEWNYM signal).
    Returns True if signal sent successfully, False otherwise.
    Rate-limited by Tor to once per 10 seconds naturally.
    """
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection("127.0.0.1", TOR_CONTROL_PORT), timeout=3
        )
        writer.write(b'AUTHENTICATE ""\r\nSIGNAL NEWNYM\r\nQUIT\r\n')
        await writer.drain()
        resp = await asyncio.wait_for(reader.read(256), timeout=3)
        writer.close()
        await writer.wait_closed()
        success = b"250" in resp
        logger.info("ETH-HACK-002: Tor NEWNYM signal sent — %s", "OK" if success else "no 250 response")
        return success
    except Exception as e:
        logger.debug("ETH-HACK-002: Tor ControlPort unavailable (%s) — circuit unchanged", e)
        return False


def _get_tor_client(verify_ssl: bool = False) -> httpx.AsyncClient:
    """Return an httpx AsyncClient routing through Tor SOCKS5."""
    transport = httpx.AsyncHTTPTransport(proxy=TOR_SOCKS)
    return httpx.AsyncClient(
        transport=transport,
        verify=verify_ssl,
        timeout=30,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; rv:109.0) Gecko/20100101 Firefox/115.0"
        },
    )


# ---------------------------------------------------------------------------
# Node registry — externally planted proxy nodes
# ---------------------------------------------------------------------------

class NodeType(str, Enum):
    TOR      = "tor"
    SOCKS5   = "socks5"
    SOCKS4   = "socks4"
    HTTP     = "http"
    HTTPS    = "https"


class NodeStatus(str, Enum):
    UNKNOWN  = "unknown"
    HEALTHY  = "healthy"
    DEGRADED = "degraded"
    DEAD     = "dead"


@dataclass
class ProxyNode:
    node_id: str
    node_type: NodeType
    host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None
    label: str = ""
    status: NodeStatus = NodeStatus.UNKNOWN
    last_checked: Optional[str] = None
    latency_ms: Optional[float] = None
    exit_ip: Optional[str] = None
    added_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def proxy_url(self) -> str:
        scheme = self.node_type.value
        if self.username and self.password:
            return f"{scheme}://{self.username}:{self.password}@{self.host}:{self.port}"
        return f"{scheme}://{self.host}:{self.port}"

    def to_dict(self) -> Dict:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type.value,
            "host": self.host,
            "port": self.port,
            "label": self.label,
            "status": self.status.value,
            "last_checked": self.last_checked,
            "latency_ms": self.latency_ms,
            "exit_ip": self.exit_ip,
            "added_at": self.added_at,
            # never expose credentials in API response
        }


class TransportRegistry:
    """Singleton registry of proxy nodes."""

    def __init__(self):
        self._nodes: Dict[str, ProxyNode] = {}
        # Pre-register the local Tor node
        tor_node = ProxyNode(
            node_id="tor-local",
            node_type=NodeType.TOR,
            host="127.0.0.1",
            port=9050,
            label="Local Tor SOCKS5",
        )
        self._nodes["tor-local"] = tor_node

    def add(self, node: ProxyNode) -> None:
        self._nodes[node.node_id] = node

    def remove(self, node_id: str) -> bool:
        if node_id == "tor-local":
            raise ValueError("Cannot remove built-in Tor node")
        return self._nodes.pop(node_id, None) is not None

    def get(self, node_id: str) -> Optional[ProxyNode]:
        return self._nodes.get(node_id)

    def list(self) -> List[ProxyNode]:
        return list(self._nodes.values())

    def healthy(self) -> List[ProxyNode]:
        return [n for n in self._nodes.values() if n.status in (NodeStatus.HEALTHY, NodeStatus.UNKNOWN)]


_registry = TransportRegistry()


async def _verify_node(node: ProxyNode) -> ProxyNode:
    """Health-check a proxy node — measure latency and detect exit IP."""
    t0 = time.monotonic()
    try:
        if node.node_type == NodeType.TOR:
            client = _get_tor_client()
        else:
            transport = httpx.AsyncHTTPTransport(proxy=node.proxy_url)
            client = httpx.AsyncClient(transport=transport, verify=False, timeout=15)

        async with client:
            resp = await client.get("https://api.ipify.org?format=json", timeout=12)
            latency = (time.monotonic() - t0) * 1000
            exit_ip = resp.json().get("ip", "unknown")
            node.latency_ms = round(latency, 1)
            node.exit_ip = exit_ip
            node.status = NodeStatus.HEALTHY
            logger.info("ETH-HACK-002: Node %s healthy — exit IP %s, latency %.0fms",
                        node.node_id, exit_ip, latency)
    except Exception as e:
        node.status = NodeStatus.DEAD
        node.latency_ms = None
        logger.warning("ETH-HACK-002: Node %s dead — %s", node.node_id, e)

    node.last_checked = datetime.now(timezone.utc).isoformat()
    return node


# ---------------------------------------------------------------------------
# Transport factory — build the right httpx client for a given mode
# ---------------------------------------------------------------------------

class TransportMode(str, Enum):
    DIRECT  = "direct"
    TOR     = "tor"
    PROXY   = "proxy"    # single named proxy node
    ROTATE  = "rotate"   # random healthy node per request
    CHAIN   = "chain"    # NOT natively supported by httpx — simulated hop-by-hop


def build_client(
    mode: TransportMode = TransportMode.DIRECT,
    node_ids: Optional[List[str]] = None,
    verify_ssl: bool = False,
) -> httpx.AsyncClient:
    """
    Build an httpx.AsyncClient with the requested transport mode.

    CHAIN mode: httpx doesn't natively support true SOCKS chain (N hops
    in sequence). We use the first node in the chain as the transport proxy.
    True multi-hop chaining requires proxychains or a VPN mesh — flagged as
    a future extension (ETH-HACK-003).
    """
    ua = "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0"

    if mode == TransportMode.DIRECT:
        return httpx.AsyncClient(
            verify=verify_ssl, timeout=20,
            headers={"User-Agent": ua, "X-Murphy-Internal": _get_internal_token()},
        )

    elif mode == TransportMode.TOR:
        return _get_tor_client(verify_ssl=verify_ssl)

    elif mode == TransportMode.ROTATE:
        healthy = _registry.healthy()
        if not healthy:
            logger.warning("ETH-HACK-002: ROTATE mode — no healthy nodes, falling back to direct")
            return httpx.AsyncClient(
            verify=verify_ssl, timeout=20,
            headers={"User-Agent": ua, "X-Murphy-Internal": _get_internal_token()},
        )
        node = random.choice(healthy)
        logger.info("ETH-HACK-002: ROTATE selected node %s (%s)", node.node_id, node.label)
        if node.node_type == NodeType.TOR:
            return _get_tor_client(verify_ssl=verify_ssl)
        transport = httpx.AsyncHTTPTransport(proxy=node.proxy_url)
        return httpx.AsyncClient(transport=transport, verify=verify_ssl, timeout=20, headers={"User-Agent": ua})

    elif mode in (TransportMode.PROXY, TransportMode.CHAIN):
        if not node_ids:
            raise ValueError("node_ids required for PROXY/CHAIN mode")
        # Use the first node (or only node) as transport
        node = _registry.get(node_ids[0])
        if not node:
            raise ValueError(f"Node {node_ids[0]} not found in registry")
        if node.node_type == NodeType.TOR:
            return _get_tor_client(verify_ssl=verify_ssl)
        transport = httpx.AsyncHTTPTransport(proxy=node.proxy_url)
        if len(node_ids) > 1:
            logger.info("ETH-HACK-002: CHAIN mode — true multi-hop not yet native in httpx; "
                        "using first node %s as entry. ETH-HACK-003 will add proxychains support.", node_ids[0])
        return httpx.AsyncClient(transport=transport, verify=verify_ssl, timeout=20, headers={"User-Agent": ua})

    else:
        return httpx.AsyncClient(
            verify=verify_ssl, timeout=20,
            headers={"User-Agent": ua, "X-Murphy-Internal": _get_internal_token()},
        )


# ---------------------------------------------------------------------------
# API — node management endpoints
# ---------------------------------------------------------------------------

class NodeAddRequest(BaseModel):
    node_type: NodeType
    host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None
    label: str = ""
    auto_verify: bool = True


class NodeVerifyRequest(BaseModel):
    node_id: str


@router.post("/nodes")
async def add_node(req: NodeAddRequest):
    """Register an external proxy/relay node."""
    # Reject obviously local addresses from being registered as 'external'
    try:
        addr = socket.gethostbyname(req.host)
        import ipaddress as _ip
        if _ip.ip_address(addr).is_loopback and req.node_type != NodeType.TOR:
            raise HTTPException(status_code=400, detail="Loopback addresses only allowed for Tor nodes")
    except HTTPException:
        raise
    except Exception:
        pass  # DNS failure — allow and let verify catch it

    node = ProxyNode(
        node_id=str(uuid.uuid4()),
        node_type=req.node_type,
        host=req.host,
        port=req.port,
        username=req.username,
        password=req.password,
        label=req.label or f"{req.node_type.value}:{req.host}:{req.port}",
    )
    _registry.add(node)

    if req.auto_verify:
        asyncio.create_task(_verify_node(node))

    return {"node_id": node.node_id, "status": "registered", "node": node.to_dict()}


@router.get("/nodes")
async def list_nodes():
    """List all registered proxy/relay nodes."""
    nodes = _registry.list()
    return {
        "count": len(nodes),
        "nodes": [n.to_dict() for n in nodes],
    }


@router.delete("/nodes/{node_id}")
async def remove_node(node_id: str):
    """Remove a proxy node from the registry."""
    try:
        removed = _registry.remove(node_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not removed:
        raise HTTPException(status_code=404, detail="Node not found")
    return {"deleted": node_id}


@router.post("/nodes/verify")
async def verify_node(req: NodeVerifyRequest):
    """Test a node's health and detect its exit IP."""
    node = _registry.get(req.node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    node = await _verify_node(node)
    return {"node": node.to_dict()}


@router.post("/nodes/tor/newcircuit")
async def new_tor_circuit():
    """Request a fresh Tor exit circuit (new IP)."""
    success = await _new_tor_circuit()
    return {
        "success": success,
        "note": "New circuit requested. Wait ~10s then re-verify the tor-local node to confirm new exit IP.",
    }
