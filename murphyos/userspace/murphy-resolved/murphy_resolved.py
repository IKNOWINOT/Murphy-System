#!/usr/bin/env python3
# SPDX-License-Identifier: BSL-1.1
# © 2020 Inoni Limited Liability Company — Creator: Corey Post
#
# murphy_resolved.py — Lightweight DNS resolver for *.murphy.local
#
# Resolves:
#   *.murphy.local          → 127.0.0.1
#   <name>.swarm.murphy.local → 127.0.100.x  (agent namespace IPs)
#   pqc-ca.murphy.local     → 127.0.0.1      (PQC CA endpoint)
#
# Forwards all other queries to the upstream resolver.
# Integrates with systemd-resolved via resolved.conf.d drop-in.
#
# ---------------------------------------------------------------------------
# Error-code registry
# ---------------------------------------------------------------------------
# MURPHY-RESOLVED-ERR-001  dnslib dependency not installed
# MURPHY-RESOLVED-ERR-002  Upstream DNS forward failed
# MURPHY-RESOLVED-ERR-003  Interrupted by KeyboardInterrupt during shutdown
# ---------------------------------------------------------------------------

"""MurphyOS local DNS resolver for the .murphy.local domain."""

import logging
import signal
import socket
import struct
import sys
import threading

try:
    from dnslib import DNSRecord, DNSHeader, RR, A, QTYPE
    from dnslib.server import DNSServer, BaseResolver
except ImportError:  # MURPHY-RESOLVED-ERR-001
    sys.exit(
        "MURPHY-RESOLVED-ERR-001: dnslib is required.  Install with:  pip install dnslib"
    )

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [murphy-resolved] %(levelname)s  %(message)s",
)
logger = logging.getLogger("murphy-resolved")

LISTEN_ADDR = "127.0.0.53"
LISTEN_PORT = 5354

UPSTREAM_DNS = "127.0.0.53"
UPSTREAM_PORT = 53

# Swarm agent IP pool — 127.0.100.0/24
_SWARM_BASE = (127, 0, 100)

# Known static names inside murphy.local
_STATIC_MAP: dict[str, str] = {
    "murphy.local": "127.0.0.1",
    "api.murphy.local": "127.0.0.1",
    "dashboard.murphy.local": "127.0.0.1",
    "pqc-ca.murphy.local": "127.0.0.1",
    "matrix.murphy.local": "127.0.0.1",
}

# Simple hash to deterministically assign swarm agent IPs
def _swarm_ip(name: str) -> str:
    """Map a swarm agent name to a 127.0.100.x address."""
    h = sum(ord(c) for c in name) % 254 + 1  # 1-254
    return f"{_SWARM_BASE[0]}.{_SWARM_BASE[1]}.{_SWARM_BASE[2]}.{h}"


class MurphyResolver(BaseResolver):
    """Resolve *.murphy.local locally, forward everything else."""

    def __init__(self, upstream: str = UPSTREAM_DNS, upstream_port: int = UPSTREAM_PORT):
        self.upstream = upstream
        self.upstream_port = upstream_port

    def resolve(self, request, handler):
        reply = request.reply()
        qname = str(request.q.qname).rstrip(".")
        qtype = QTYPE[request.q.qtype]

        # Only handle A queries inside murphy.local
        if qname.endswith(".murphy.local") or qname == "murphy.local":
            ip = self._lookup(qname)
            if ip and qtype in ("A", "ANY", "*"):
                reply.add_answer(
                    RR(request.q.qname, QTYPE.A, rdata=A(ip), ttl=60)
                )
                logger.info("Resolved %s → %s", qname, ip)
                return reply
            # NXDOMAIN for unknown murphy.local names
            reply.header.rcode = 3
            logger.info("NXDOMAIN for %s", qname)
            return reply

        # Forward non-murphy.local queries upstream
        return self._forward(request)

    def _lookup(self, qname: str) -> str | None:
        """Return an IP for a murphy.local name, or None."""
        # Static map first
        if qname in _STATIC_MAP:
            return _STATIC_MAP[qname]

        # Swarm agents: <name>.swarm.murphy.local
        if qname.endswith(".swarm.murphy.local"):
            agent_name = qname.removesuffix(".swarm.murphy.local")
            return _swarm_ip(agent_name)

        # Wildcard: anything else under murphy.local → loopback
        if qname.endswith(".murphy.local"):
            return "127.0.0.1"

        return None

    def _forward(self, request):
        """Forward a DNS query to the upstream resolver."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(5)
            sock.sendto(request.pack(), (self.upstream, self.upstream_port))
            data, _ = sock.recvfrom(4096)
            sock.close()
            return DNSRecord.parse(data)
        except Exception as exc:  # MURPHY-RESOLVED-ERR-002
            logger.warning("MURPHY-RESOLVED-ERR-002: Upstream forward failed: %s", exc)
            reply = request.reply()
            reply.header.rcode = 2  # SERVFAIL
            return reply


def main():
    """Start the Murphy DNS resolver."""
    resolver = MurphyResolver()
    server = DNSServer(
        resolver,
        address=LISTEN_ADDR,
        port=LISTEN_PORT,
    )
    logger.info("Murphy DNS resolver listening on %s:%d", LISTEN_ADDR, LISTEN_PORT)

    # Graceful shutdown
    stop_event = threading.Event()

    def _shutdown(signum, _frame):
        logger.info("Received signal %d — shutting down", signum)
        stop_event.set()
        server.stop()

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    server.start_thread()

    try:
        stop_event.wait()
    except KeyboardInterrupt:  # MURPHY-RESOLVED-ERR-003
        logger.debug("MURPHY-RESOLVED-ERR-003: interrupted by KeyboardInterrupt")
    finally:
        server.stop()
        logger.info("Murphy DNS resolver stopped")


if __name__ == "__main__":
    main()
