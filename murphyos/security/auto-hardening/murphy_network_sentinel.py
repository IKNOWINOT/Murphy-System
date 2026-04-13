# SPDX-License-Identifier: LicenseRef-BSL-1.1
# © 2020 Inoni Limited Liability Company — Creator: Corey Post — BSL 1.1
"""Automatic network threat detection and response.

``NetworkSentinel`` analyses live connections using heuristic scoring,
blocks threats via nftables rules that auto-expire, detects DNS-based data
exfiltration, and learns a "normal" traffic baseline over time.

Known-good destinations are maintained in an allowlist so legitimate work
is never disrupted.

Error codes: MURPHY-AUTOSEC-ERR-031 .. MURPHY-AUTOSEC-ERR-045
"""
from __future__ import annotations

import collections
import hashlib
import json
import logging
import math
import os
import pathlib
import re
import socket
import subprocess
import threading
import time
from typing import Any, Deque, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("murphy.autosec.network_sentinel")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEFAULT_BLOCK_DURATION = 3600  # seconds — auto-expire after 1 h
MAX_BASELINE_SAMPLES = 10_000
DNS_LABEL_ENTROPY_THRESHOLD = 3.5  # bits — above this is suspicious
NFT_TABLE = "murphy_autosec"
NFT_CHAIN = "sentinel_block"
STATE_DIR = pathlib.Path("/var/lib/murphy/network_sentinel")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _run(cmd: List[str], **kw: Any) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=30, **kw)


def _shannon_entropy(data: str) -> float:
    """Calculate Shannon entropy (bits) of a string."""
    if not data:
        return 0.0
    freq: Dict[str, int] = {}
    for ch in data:
        freq[ch] = freq.get(ch, 0) + 1
    length = len(data)
    return -sum(
        (c / length) * math.log2(c / length) for c in freq.values()
    )


# ---------------------------------------------------------------------------
# NetworkSentinel
# ---------------------------------------------------------------------------
class NetworkSentinel:
    """Automatic network threat detection and response engine.

    Parameters
    ----------
    allowlist : set[str], optional
        IP addresses or CIDR ranges considered known-good.
    block_duration : int
        Default seconds before an nftables block rule expires.
    state_dir : pathlib.Path
        Directory for persisting baseline and allowlist data.
    """

    def __init__(
        self,
        allowlist: Optional[Set[str]] = None,
        block_duration: int = DEFAULT_BLOCK_DURATION,
        state_dir: pathlib.Path = STATE_DIR,
    ) -> None:
        self._allowlist: Set[str] = allowlist or set()
        self._block_duration = block_duration
        self._state_dir = state_dir
        self._baseline: Dict[str, Any] = {}
        self._recent_connections: Deque[Dict[str, Any]] = collections.deque(
            maxlen=MAX_BASELINE_SAMPLES
        )
        self._blocked: Dict[str, float] = {}  # ip → expiry timestamp
        self._lock = threading.Lock()
        self._nft_ready: Optional[bool] = None
        logger.info("NetworkSentinel initialised (block_duration=%ds).", block_duration)

    # -- nftables helpers ---------------------------------------------------

    def _ensure_nft_table(self) -> bool:
        """Create the nftables table and chain if they don't exist."""
        if self._nft_ready is not None:
            return self._nft_ready

        try:
            _run(["nft", "add", "table", "inet", NFT_TABLE])
            _run([
                "nft", "add", "chain", "inet", NFT_TABLE, NFT_CHAIN,
                "{ type filter hook input priority 0 ; policy accept ; }",
            ])
            self._nft_ready = True
        except FileNotFoundError:  # MURPHY-AUTOSEC-ERR-031
            logger.warning(
                "MURPHY-AUTOSEC-ERR-031: nftables binary not found; "
                "auto-blocking disabled."
            )
            self._nft_ready = False
        except Exception as exc:  # MURPHY-AUTOSEC-ERR-032
            logger.warning(
                "MURPHY-AUTOSEC-ERR-032: nftables setup failed: %s", exc
            )
            self._nft_ready = False
        return self._nft_ready  # type: ignore[return-value]

    # -- heuristic scoring --------------------------------------------------

    def analyze_connection(self, conn: Dict[str, Any]) -> float:
        """Score a connection from 0.0 (benign) to 1.0 (malicious).

        Heuristics considered:
        - Unknown destination (not in allowlist)
        - High port (ephemeral source to low-numbered remote)
        - Unusual bytes-per-second rate
        - Connection at an anomalous hour
        - High DNS label entropy (exfil indicator)
        """
        score = 0.0
        dest_ip: str = conn.get("dest_ip", "")
        dest_port: int = conn.get("dest_port", 0)
        bytes_per_sec: float = conn.get("bytes_per_sec", 0.0)
        dns_query: str = conn.get("dns_query", "")
        timestamp: float = conn.get("timestamp", time.time())

        # 1. Allowlist check — known-good → minimal score
        if dest_ip in self._allowlist:
            return 0.0

        # 2. Unknown destination
        score += 0.15

        # 3. Suspicious ports
        if dest_port in (4444, 5555, 6666, 1337, 31337):
            score += 0.25

        # 4. High throughput anomaly
        if self._baseline:
            avg_bps = self._baseline.get("avg_bytes_per_sec", 0)
            if avg_bps > 0 and bytes_per_sec > avg_bps * 10:
                score += 0.20

        # 5. Anomalous hour
        hour = time.localtime(timestamp).tm_hour
        if self._baseline:
            normal_hours: Set[int] = set(self._baseline.get("active_hours", range(6, 23)))
            if hour not in normal_hours:
                score += 0.10

        # 6. DNS exfiltration heuristic
        if dns_query:
            entropy = _shannon_entropy(dns_query.split(".")[0])
            if entropy > DNS_LABEL_ENTROPY_THRESHOLD:
                score += 0.30

        score = min(score, 1.0)

        with self._lock:
            self._recent_connections.append(conn)

        if score >= 0.7:
            logger.warning(
                "High threat score %.2f for %s:%d", score, dest_ip, dest_port
            )
        return score

    # -- blocking -----------------------------------------------------------

    def auto_block_threat(
        self,
        ip: str,
        duration: Optional[int] = None,
        reason: str = "",
    ) -> bool:
        """Block *ip* via nftables with an auto-expire timeout.

        Returns *True* if the rule was applied (or if the IP is already
        blocked).
        """
        if ip in self._allowlist:
            logger.info("Refusing to block allowlisted IP %s.", ip)
            return False

        dur = duration or self._block_duration
        with self._lock:
            if ip in self._blocked and self._blocked[ip] > time.time():
                logger.debug("IP %s already blocked.", ip)
                return True

        if not self._ensure_nft_table():
            logger.error(
                "MURPHY-AUTOSEC-ERR-033: Cannot block %s — nftables unavailable.", ip
            )
            return False

        try:
            res = _run([
                "nft", "add", "rule", "inet", NFT_TABLE, NFT_CHAIN,
                "ip", "saddr", ip, "counter", "drop",
                "comment", f'"murphy-block {reason}"',
            ])
            if res.returncode != 0:
                logger.error(
                    "MURPHY-AUTOSEC-ERR-034: nft add rule failed: %s", res.stderr
                )
                return False
        except Exception as exc:  # MURPHY-AUTOSEC-ERR-035
            logger.error("MURPHY-AUTOSEC-ERR-035: Block error: %s", exc)
            return False

        expiry = time.time() + dur
        with self._lock:
            self._blocked[ip] = expiry

        # Schedule unblock
        t = threading.Timer(dur, self._unblock, args=(ip,))
        t.daemon = True
        t.start()

        logger.info("Blocked %s for %ds (reason: %s).", ip, dur, reason or "auto")
        return True

    def _unblock(self, ip: str) -> None:
        """Remove the nftables rule for *ip*."""
        try:
            res = _run(["nft", "-a", "list", "chain", "inet", NFT_TABLE, NFT_CHAIN])
            for line in res.stdout.splitlines():
                if ip in line:
                    match = re.search(r"handle (\d+)", line)
                    if match:
                        _run([
                            "nft", "delete", "rule", "inet", NFT_TABLE,
                            NFT_CHAIN, "handle", match.group(1),
                        ])
            with self._lock:
                self._blocked.pop(ip, None)
            logger.info("Unblocked %s (auto-expire).", ip)
        except Exception as exc:  # MURPHY-AUTOSEC-ERR-036
            logger.error("MURPHY-AUTOSEC-ERR-036: Unblock failed for %s: %s", ip, exc)

    # -- DNS exfiltration detection -----------------------------------------

    def dns_exfil_detector(self, query: str, client_ip: str = "") -> bool:
        """Return *True* if *query* looks like DNS exfiltration.

        Detection heuristics:
        * Label length > 50 characters
        * Shannon entropy > threshold
        * Excessive sub-domains (> 5 labels)
        """
        labels = query.rstrip(".").split(".")
        if len(labels) > 5:
            logger.warning(
                "MURPHY-AUTOSEC-ERR-037: Excessive DNS labels (%d) in query from %s: %s",
                len(labels), client_ip, query,
            )
            return True

        first_label = labels[0] if labels else ""
        if len(first_label) > 50:
            logger.warning(
                "MURPHY-AUTOSEC-ERR-038: Oversized DNS label (%d chars) from %s.",
                len(first_label), client_ip,
            )
            return True

        if _shannon_entropy(first_label) > DNS_LABEL_ENTROPY_THRESHOLD:
            logger.warning(
                "MURPHY-AUTOSEC-ERR-039: High-entropy DNS label (%.2f bits) from %s: %s",
                _shannon_entropy(first_label), client_ip, first_label,
            )
            return True

        return False

    # -- baseline learning --------------------------------------------------

    def learn_normal_baseline(self, window_hours: int = 24) -> Dict[str, Any]:
        """Analyse recent connections to build a traffic baseline.

        The baseline captures average bytes-per-second, common destination
        ports, active hours, and typical destination IPs.
        """
        with self._lock:
            conns = list(self._recent_connections)

        if not conns:
            logger.info("MURPHY-AUTOSEC-ERR-040: No connections to learn from.")
            return self._baseline

        cutoff = time.time() - (window_hours * 3600)
        recent = [c for c in conns if c.get("timestamp", 0) >= cutoff]
        if not recent:
            logger.info("MURPHY-AUTOSEC-ERR-040: No recent connections in window.")
            return self._baseline

        bps_values = [c.get("bytes_per_sec", 0) for c in recent]
        ports: Dict[int, int] = {}
        hours: Set[int] = set()
        dest_ips: Set[str] = set()

        for c in recent:
            p = c.get("dest_port", 0)
            ports[p] = ports.get(p, 0) + 1
            ts = c.get("timestamp", time.time())
            hours.add(time.localtime(ts).tm_hour)
            dest_ips.add(c.get("dest_ip", ""))

        self._baseline = {
            "avg_bytes_per_sec": sum(bps_values) / len(bps_values) if bps_values else 0,
            "common_ports": sorted(ports, key=ports.get, reverse=True)[:20],  # type: ignore[arg-type]
            "active_hours": sorted(hours),
            "known_dest_ips": sorted(dest_ips),
            "sample_count": len(recent),
        }
        logger.info(
            "Baseline learned from %d connections (%d-hour window).",
            len(recent), window_hours,
        )
        return self._baseline

    # -- persistence --------------------------------------------------------

    def save_state(self) -> bool:
        """Persist baseline and allowlist to disk."""
        try:
            self._state_dir.mkdir(parents=True, exist_ok=True)
            state = {
                "baseline": self._baseline,
                "allowlist": sorted(self._allowlist),
            }
            (self._state_dir / "sentinel_state.json").write_text(
                json.dumps(state, indent=2)
            )
            logger.info("NetworkSentinel state saved.")
            return True
        except Exception as exc:  # MURPHY-AUTOSEC-ERR-041
            logger.error("MURPHY-AUTOSEC-ERR-041: State save failed: %s", exc)
            return False

    def load_state(self) -> bool:
        """Load persisted baseline and allowlist."""
        path = self._state_dir / "sentinel_state.json"
        try:
            data = json.loads(path.read_text())
            self._baseline = data.get("baseline", {})
            self._allowlist.update(data.get("allowlist", []))
            logger.info("NetworkSentinel state loaded.")
            return True
        except FileNotFoundError:
            logger.debug("MURPHY-AUTOSEC-ERR-042: No saved state found.")
            return False
        except Exception as exc:  # MURPHY-AUTOSEC-ERR-043
            logger.error("MURPHY-AUTOSEC-ERR-043: State load failed: %s", exc)
            return False

    # -- allowlist management -----------------------------------------------

    def add_to_allowlist(self, ip: str) -> None:
        """Add an IP to the known-good allowlist."""
        self._allowlist.add(ip)
        logger.info("Added %s to allowlist.", ip)

    def remove_from_allowlist(self, ip: str) -> None:
        """Remove an IP from the allowlist."""
        self._allowlist.discard(ip)
        logger.info("Removed %s from allowlist.", ip)

    # -- summary ------------------------------------------------------------

    def threat_summary(self) -> Dict[str, Any]:
        """Return a summary of current threat status."""
        with self._lock:
            active_blocks = {
                ip: exp for ip, exp in self._blocked.items() if exp > time.time()
            }
        return {
            "active_blocks": len(active_blocks),
            "blocked_ips": list(active_blocks.keys()),
            "baseline_sample_count": self._baseline.get("sample_count", 0),
            "allowlist_size": len(self._allowlist),
        }
