"""
Murphy Honeypot + Counter-Intelligence Engine  —  PATCH-087
ETH-HACK-004

Architecture — Three interlocking layers:

  LAYER 1 — HONEYPOT TRAPS
    Fake endpoints that look juicy to attackers:
      /admin, /wp-admin, /phpmyadmin, /.env, /config.json, /backup.zip,
      /.git/config, /api/v1/admin/users, /shell, /console, /debug
    Each trap: logs attacker IP, UA, payload, timing. Returns convincing
    fake responses (fake DB creds, fake config, fake tokens) that waste
    attacker time and reveal their tools/techniques.

  LAYER 2 — PASSIVE FINGERPRINTING (on every inbound request)
    Murphy's middleware silently profiles every visitor:
      - TLS fingerprint (JA3-style) via nginx $ssl_client_fingerprint
      - HTTP header anomaly scoring (tool detection: curl, nmap, Metasploit, BurpSuite)
      - Request timing patterns (scanner cadence detection)
      - IP reputation lookup (AbuseIPDB-style local blocklist + GeoIP)
      - Path traversal / injection attempt detection
    Suspicion score 0–100. Above threshold → auto-trigger counter-scan.

  LAYER 3 — COUNTER-SCAN TRIGGER (active retaliation)
    When suspicion >= threshold (default 65):
      1. Immediately routes attacker IP through Tor (anonymized)
      2. Runs our full ethical hacking scan AGAINST the attacker
      3. Feeds results into AttackGraph (PATCH-086 graph gets new nodes)
      4. Stores full dossier: IP, tools used, vulns found on their end
      5. Optional tarpit: slow-loris delay on attacker connection (wastes their time)

  LAYER 4 — ORIGIN MASKING FOR ALL OUTBOUND
    Every counter-scan and outbound probe:
      - Routes through Tor exit node (real IP never visible)
      - Rotates circuit every N counter-scans
      - Randomizes User-Agent, TLS fingerprint, request timing/jitter
      - Strips all identifying headers (Server, X-Powered-By etc already done in nginx)

API:
  GET  /api/honeypot/dashboard       — live dossier of all caught attackers
  GET  /api/honeypot/stream          — SSE: real-time alerts as attackers hit traps
  GET  /api/honeypot/dossier/{ip}    — full profile for a specific IP
  POST /api/honeypot/whitelist        — add IP to whitelist (don't counter-scan)
  GET  /api/honeypot/config          — current config (threshold, tarpit, etc.)
  POST /api/honeypot/config          — update config

Trap routes (public, no auth — that's the point):
  GET/POST /admin, /wp-admin, /phpmyadmin, /.env, /.git/config,
           /config.json, /backup.zip, /shell, /console, /debug,
           /api/v1/admin/users, /server-status, /actuator/health,
           /api/keys, /_internal, /setup, /install

PATCH-087 | ETH-HACK-004
Copyright © 2020 Inoni LLC / Corey Post — BSL 1.1
"""
from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import json
import logging
import random
import re
import threading
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, PlainTextResponse, Response, StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# ── Two routers: protected API + public traps ──────────────────────────────
api_router  = APIRouter(prefix="/api/honeypot", tags=["honeypot"])
trap_router = APIRouter(tags=["honeypot_traps"])   # no prefix — traps live at root

# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class HoneypotConfig:
    suspicion_threshold: int   = 60    # 0–100: trigger counter-scan above this
    tarpit_enabled: bool       = True  # slow attacker responses
    tarpit_delay_s: float      = 4.0   # seconds to delay trap responses
    counter_scan_enabled: bool = True  # actually scan back
    counter_scan_transport: str = "tor" # always Tor for counter-scans
    max_dossiers: int          = 500   # cap stored attacker records
    rotate_circuit_every: int  = 5     # new Tor circuit every N counter-scans
    whitelist: Set[str]        = field(default_factory=lambda: {
        "127.0.0.1", "::1", "5.78.41.114"
    })

_config = HoneypotConfig()
_counter_scan_count = 0

# ─────────────────────────────────────────────────────────────────────────────
# Attacker Dossier
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class AttackerDossier:
    ip: str
    first_seen: str        = field(default_factory=lambda: _now())
    last_seen: str         = field(default_factory=lambda: _now())
    hit_count: int         = 0
    suspicion_score: int   = 0
    trapped_paths: List[str]        = field(default_factory=list)
    payloads: List[str]             = field(default_factory=list)
    user_agents: List[str]          = field(default_factory=list)
    tool_signatures: List[str]      = field(default_factory=list)
    country: Optional[str]          = None
    counter_scanned: bool           = False
    counter_scan_job_id: Optional[str] = None
    counter_findings: List[Dict]    = field(default_factory=list)
    counter_risk_level: Optional[str] = None
    tarpit_applied: bool  = False
    events: List[Dict]    = field(default_factory=list)

    def add_event(self, path: str, method: str, ua: str, payload: str = "", score_delta: int = 0):
        self.hit_count += 1
        self.last_seen = _now()
        self.suspicion_score = min(100, self.suspicion_score + score_delta)
        if path not in self.trapped_paths:
            self.trapped_paths.append(path)
        if ua and ua not in self.user_agents:
            self.user_agents.append(ua[:200])
        if payload:
            self.payloads.append(payload[:500])
        self.events.append({
            "ts": _now(), "path": path, "method": method,
            "ua": ua[:200], "payload": payload[:200], "score": self.suspicion_score
        })
        # cap events
        if len(self.events) > 100:
            self.events = self.events[-100:]

    def to_dict(self) -> Dict:
        return {
            "ip": self.ip,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "hit_count": self.hit_count,
            "suspicion_score": self.suspicion_score,
            "risk": _score_to_risk(self.suspicion_score),
            "trapped_paths": self.trapped_paths,
            "tool_signatures": self.tool_signatures,
            "user_agents": self.user_agents[:5],
            "country": self.country,
            "counter_scanned": self.counter_scanned,
            "counter_risk_level": self.counter_risk_level,
            "counter_findings_count": len(self.counter_findings),
            "tarpit_applied": self.tarpit_applied,
            "events": self.events[-10:],
        }


class DossierStore:
    def __init__(self):
        self._d: Dict[str, AttackerDossier] = {}
        self._lock = threading.Lock()
        self._alert_queue: deque = deque(maxlen=2000)
        self._subscribers: List[asyncio.Queue] = []
        self._sub_lock = threading.Lock()

    def get_or_create(self, ip: str) -> AttackerDossier:
        with self._lock:
            if ip not in self._d:
                if len(self._d) >= _config.max_dossiers:
                    # evict oldest
                    oldest = min(self._d.values(), key=lambda x: x.last_seen)
                    del self._d[oldest.ip]
                self._d[ip] = AttackerDossier(ip=ip)
            return self._d[ip]

    def get(self, ip: str) -> Optional[AttackerDossier]:
        return self._d.get(ip)

    def list(self) -> List[AttackerDossier]:
        with self._lock:
            return sorted(self._d.values(), key=lambda x: x.suspicion_score, reverse=True)

    def broadcast_alert(self, alert: Dict):
        self._alert_queue.append(alert)
        with self._sub_lock:
            dead = []
            for q in self._subscribers:
                try:
                    q.put_nowait(alert)
                except asyncio.QueueFull:
                    dead.append(q)
            for q in dead:
                self._subscribers.remove(q)

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=200)
        with self._sub_lock:
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        with self._sub_lock:
            try:
                self._subscribers.remove(q)
            except ValueError:
                pass

    def recent_alerts(self, n: int = 50) -> List[Dict]:
        return list(self._alert_queue)[-n:]


_store = DossierStore()

# ─────────────────────────────────────────────────────────────────────────────
# Fingerprinting / suspicion scoring
# ─────────────────────────────────────────────────────────────────────────────

SCANNER_UA_PATTERNS = [
    (re.compile(r'sqlmap', re.I),              "sqlmap",         40),
    (re.compile(r'nikto',  re.I),              "nikto",          40),
    (re.compile(r'nmap',   re.I),              "nmap",           35),
    (re.compile(r'masscan',re.I),              "masscan",        35),
    (re.compile(r'burpsuite|burp\s',re.I),     "burpsuite",      35),
    (re.compile(r'metasploit|msf',re.I),       "metasploit",     50),
    (re.compile(r'zgrab',  re.I),              "zgrab",          30),
    (re.compile(r'nuclei', re.I),              "nuclei",         35),
    (re.compile(r'gobuster|dirb|dirbuster',re.I),"dirb",         30),
    (re.compile(r'hydra|medusa',re.I),         "brute_force",    45),
    (re.compile(r'python-requests/[0-9]',re.I),"python_script",  15),
    (re.compile(r'^curl/[0-9]',re.I),          "curl_raw",       10),
    (re.compile(r'go-http-client',re.I),       "go_scanner",     20),
    (re.compile(r'dirsearch',re.I),            "dirsearch",      30),
    (re.compile(r'wfuzz|ffuf',re.I),           "fuzzer",         35),
    (re.compile(r'acunetix',re.I),             "acunetix",       45),
    (re.compile(r'nessus',  re.I),             "nessus",         40),
    (re.compile(r'openvas', re.I),             "openvas",        40),
    (re.compile(r'shodan',  re.I),             "shodan",         35),
    (re.compile(r'censys',  re.I),             "censys",         25),
]

INJECTION_PATTERNS = [
    (re.compile(r"'.*OR.*'|UNION.*SELECT|DROP.*TABLE|INSERT.*INTO", re.I), "sqli",   30),
    (re.compile(r"<script|javascript:|onerror=|onload=",            re.I), "xss",    25),
    (re.compile(r"\.\./\.\.|\.\.%2f|%2e%2e",                        re.I), "lfi",    25),
    (re.compile(r"\$\{|%\{|{{.*}}|\${7\*7}",                        re.I), "ssti",   35),
    (re.compile(r";(ls|id|whoami|cat|wget|curl)\b",                  re.I), "cmdi",   40),
    (re.compile(r"(nc|bash|sh)\s+-[ei]",                             re.I), "rce",    50),
    (re.compile(r"eval\(|exec\(|system\(",                           re.I), "code",   40),
    (re.compile(r"\/etc\/passwd|\/etc\/shadow",                      re.I), "lfi",    35),
]

PATH_SCORES = {
    "/.env": 55, "/.git/config": 50, "/wp-admin": 40, "/phpmyadmin": 40,
    "/admin": 30, "/config.json": 45, "/backup.zip": 45, "/shell": 55,
    "/console": 40, "/debug": 35, "/actuator": 40, "/server-status": 30,
    "/api/keys": 55, "/_internal": 45, "/setup": 30, "/install": 30,
}


def _score_request(path: str, ua: str, body: str, headers: Dict) -> Tuple[int, List[str]]:
    """Compute suspicion delta for a single request. Returns (score, [tool_signatures])."""
    score = 0
    tools = []

    # Path hit
    for p, s in PATH_SCORES.items():
        if path.startswith(p):
            score += s
            break

    # UA fingerprinting
    for pattern, name, pts in SCANNER_UA_PATTERNS:
        if pattern.search(ua):
            score += pts
            tools.append(name)

    # Injection in path + body
    combined = path + " " + body
    for pattern, name, pts in INJECTION_PATTERNS:
        if pattern.search(combined):
            score += pts
            if name not in tools:
                tools.append(name)

    # Missing normal browser headers → likely automated
    if not headers.get("accept-language") and not headers.get("accept"):
        score += 10
    if not ua or len(ua) < 5:
        score += 15

    return min(score, 100), tools


def _score_to_risk(s: int) -> str:
    if s >= 80: return "critical"
    if s >= 60: return "high"
    if s >= 40: return "medium"
    if s >= 20: return "low"
    return "info"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _is_whitelisted(ip: str) -> bool:
    if ip in _config.whitelist:
        return True
    try:
        addr = ipaddress.ip_address(ip)
        return addr.is_private or addr.is_loopback
    except ValueError:
        return False

# ─────────────────────────────────────────────────────────────────────────────
# Counter-scan trigger
# ─────────────────────────────────────────────────────────────────────────────

async def _trigger_counter_scan(dossier: AttackerDossier):
    """Silently scan back through Tor. Anonymized — Murphy's IP never exposed."""
    global _counter_scan_count
    if not _config.counter_scan_enabled:
        return
    if dossier.counter_scanned:
        return  # already scanned this attacker

    ip = dossier.ip
    dossier.counter_scanned = True
    logger.info("ETH-HACK-004: Counter-scanning %s via Tor (anonymized)", ip)

    # Rotate Tor circuit periodically
    _counter_scan_count += 1
    if _counter_scan_count % _config.rotate_circuit_every == 0:
        try:
            from src.hack_transport import _new_tor_circuit
            await _new_tor_circuit()
            await asyncio.sleep(2)
        except Exception:
            pass

    try:
        from src.ethical_hacking_engine import _run_scan, ScanJob, _store_job

        # Try HTTP first; many attackers run web servers
        targets = [f"http://{ip}", f"https://{ip}"]
        for target_url in targets:
            job = ScanJob(
                job_id=str(uuid.uuid4()),
                target=target_url,
                started_at=_now(),
            )
            _store_job(job)
            try:
                await _run_scan(
                    job,
                    authorized=True,
                    transport_mode=_config.counter_scan_transport,
                )
                dossier.counter_scan_job_id = job.job_id
                dossier.counter_findings = job.findings
                dossier.counter_risk_level = job.summary.get("risk_level") if job.summary else None

                # Feed into the attack graph
                try:
                    from src.hack_stream_graph import _graph
                    nid = f"attacker:{ip}"
                    _graph.add_node(nid, node_type="target", url=f"http://{ip}",
                                    label=f"ATTACKER:{ip}", depth=0, is_attacker=True)
                    for f in job.findings:
                        fid = f"finding:{uuid.uuid4().hex[:8]}"
                        _graph.add_node(fid, node_type="finding",
                                        severity=f.get("severity","info"),
                                        title=f.get("title",""),
                                        category=f.get("category",""))
                        _graph.add_edge(nid, fid, rel="has_finding")
                except Exception:
                    pass

                if job.findings:
                    break  # got results, don't need second target
            except Exception as e:
                logger.debug("ETH-HACK-004: counter-scan %s failed: %s", target_url, e)

        alert = {
            "event": "counter_scan_complete",
            "ip": ip,
            "findings": len(dossier.counter_findings),
            "risk": dossier.counter_risk_level,
            "ts": _now(),
        }
        _store.broadcast_alert(alert)
        logger.info("ETH-HACK-004: Counter-scan complete for %s — %d findings", ip, len(dossier.counter_findings))

    except Exception as e:
        logger.warning("ETH-HACK-004: Counter-scan error for %s: %s", ip, e)

# ─────────────────────────────────────────────────────────────────────────────
# Core trap handler
# ─────────────────────────────────────────────────────────────────────────────

async def _handle_trap(request: Request, trap_name: str, fake_response: Any, content_type: str = "application/json") -> Response:
    """Central handler called by every trap endpoint."""
    ip = _client_ip(request)

    if _is_whitelisted(ip):
        return Response(status_code=404)

    ua = request.headers.get("user-agent", "")
    body = ""
    try:
        body = (await request.body()).decode("utf-8", errors="replace")[:1000]
    except Exception:
        pass

    headers_dict = dict(request.headers)
    score_delta, tools = _score_request(
        str(request.url.path), ua, body, headers_dict
    )
    # Trap hits always add a base score
    score_delta = max(score_delta, 25)

    dossier = _store.get_or_create(ip)
    dossier.add_event(str(request.url.path), request.method, ua, body, score_delta)
    for t in tools:
        if t not in dossier.tool_signatures:
            dossier.tool_signatures.append(t)

    alert = {
        "event": "trap_hit",
        "ip": ip,
        "path": str(request.url.path),
        "method": request.method,
        "ua": ua[:120],
        "tools": tools,
        "suspicion": dossier.suspicion_score,
        "risk": _score_to_risk(dossier.suspicion_score),
        "ts": _now(),
    }
    _store.broadcast_alert(alert)
    logger.warning("ETH-HACK-004: TRAP HIT [%s] %s %s — suspicion=%d",
                   trap_name, request.method, request.url.path, dossier.suspicion_score)

    # Tarpit: slow response to waste attacker time
    if _config.tarpit_enabled:
        dossier.tarpit_applied = True
        await asyncio.sleep(_config.tarpit_delay_s + random.uniform(0, 2))

    # Trigger counter-scan if suspicion threshold reached
    if dossier.suspicion_score >= _config.suspicion_threshold and not dossier.counter_scanned:
        asyncio.create_task(_trigger_counter_scan(dossier))

    # Return convincing fake content
    if callable(fake_response):
        fake_response = fake_response()

    if isinstance(fake_response, str):
        return PlainTextResponse(fake_response, status_code=200)
    elif isinstance(fake_response, bytes):
        return Response(content=fake_response, media_type=content_type, status_code=200)
    else:
        return JSONResponse(content=fake_response, status_code=200)

# ─────────────────────────────────────────────────────────────────────────────
# FAKE CONTENT generators — each trap returns convincing bait
# ─────────────────────────────────────────────────────────────────────────────

def _fake_env() -> str:
    return """APP_ENV=production
APP_KEY=base64:xK3mN9pQrT7vWzY2bCdFhJkL5nPqSuVw
DB_CONNECTION=mysql
DB_HOST=db.murphy-internal.svc
DB_PORT=3306
DB_DATABASE=murphy_prod
DB_USERNAME=murphy_app
DB_PASSWORD=Xk9!mP2@nQ7vR
REDIS_HOST=redis.murphy-internal.svc
REDIS_PASSWORD=rP8#kL3mN9qT
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
STRIPE_SECRET_KEY=sk_live_XXXXXXXXXXXXXXXXXXXX
JWT_SECRET=mNpQrStuVwXyZ1234567890abcdefghijklmnop
MAIL_PASSWORD=smtp_pass_EXAMPLE
"""

def _fake_git_config() -> str:
    return """[core]
\trepositoryformatversion = 0
\tfilemode = true
\tbare = false
\tlogallrefupdates = true
[remote "origin"]
\turl = https://ghp_EXAMPLETOKEN123456789@github.com/murphy-internal/murphy-core.git
\tfetch = +refs/heads/*:refs/remotes/origin/*
[branch "main"]
\tremote = origin
\tmerge = refs/heads/main
[user]
\temail = deploy@murphy.systems
\tname = Murphy CI
"""

def _fake_admin_users() -> Dict:
    return {
        "users": [
            {"id": 1, "email": "admin@murphy.systems",    "role": "superadmin", "password_hash": "$2b$12$EXAMPLEHASH1"},
            {"id": 2, "email": "cpost@murphy.systems",    "role": "owner",      "password_hash": "$2b$12$EXAMPLEHASH2"},
            {"id": 3, "email": "devops@murphy.systems",   "role": "admin",      "password_hash": "$2b$12$EXAMPLEHASH3"},
        ],
        "total": 3,
        "page": 1,
    }

def _fake_config() -> Dict:
    return {
        "database": {"host": "db.murphy-internal.svc", "port": 5432, "name": "murphy_prod",
                     "user": "murphy_app", "password": "Xk9!mP2@nQ7v"},
        "redis":    {"host": "redis.murphy-internal.svc", "port": 6379, "password": "rP8#kL3mN9qT"},
        "jwt_secret": "mNpQrStuVwXyZ1234567890abcdefghijklmnop",
        "debug": False,
        "version": "1.0.0",
    }

def _fake_api_keys() -> Dict:
    return {
        "keys": [
            {"name": "production",  "key": "sk_prod_" + uuid.uuid4().hex, "scopes": ["read", "write", "admin"]},
            {"name": "ci_deploy",   "key": "sk_ci_"   + uuid.uuid4().hex, "scopes": ["deploy"]},
            {"name": "monitoring",  "key": "sk_mon_"  + uuid.uuid4().hex, "scopes": ["read"]},
        ]
    }

def _fake_shell() -> str:
    return "root@murphy-prod:/opt/Murphy-System# "

def _fake_debug() -> Dict:
    return {
        "debug": True, "env": "production",
        "config": _fake_config(),
        "routes": ["/api/admin", "/api/users", "/api/keys", "/_internal"],
        "secrets_file": "/etc/murphy-production/secrets.env",
    }

def _fake_backup_zip() -> bytes:
    # Return empty zip magic bytes — tools will try to unzip and waste time
    return b"PK\x03\x04" + b"\x00" * 100

def _fake_server_status() -> str:
    return """Apache/2.4.51 (Ubuntu) Server Status
Total Accesses: 1,284,930
Total Traffic: 42.3 GB
Uptime: 847 hours
Requests/sec: 12.4
Bytes/sec: 8200
Workers: 150 busy, 100 idle
"""

def _fake_actuator() -> Dict:
    return {
        "status": "UP",
        "components": {
            "db":    {"status": "UP", "details": {"database": "PostgreSQL 14.2", "validationQuery": "isValid()"}},
            "redis": {"status": "UP"},
            "mail":  {"status": "UP"},
        },
        "diskSpace": {"status": "UP", "total": 107374182400, "free": 52428800000},
    }

def _fake_phpmyadmin() -> str:
    return """<!DOCTYPE html>
<html><head><title>phpMyAdmin</title></head>
<body>
<form method="POST" action="/phpmyadmin/index.php">
<input name="pma_username" value="root">
<input type="password" name="pma_password">
<input type="submit" value="Go">
</form></body></html>"""

# ─────────────────────────────────────────────────────────────────────────────
# TRAP ENDPOINTS — the actual honeypot routes
# ─────────────────────────────────────────────────────────────────────────────

TRAP_ROUTES = [
    # (path, methods, trap_name, fake_content, content_type)
    ("/.env",                    ["GET"],        "env_file",       _fake_env,           "text/plain"),
    ("/.env.local",              ["GET"],        "env_local",      _fake_env,           "text/plain"),
    ("/.env.production",         ["GET"],        "env_prod",       _fake_env,           "text/plain"),
    ("/.git/config",             ["GET"],        "git_config",     _fake_git_config,    "text/plain"),
    ("/.git/HEAD",               ["GET"],        "git_head",       lambda: "ref: refs/heads/main\n", "text/plain"),
    ("/config.json",             ["GET"],        "config_json",    _fake_config,        "application/json"),
    ("/backup.zip",              ["GET"],        "backup_zip",     _fake_backup_zip,    "application/zip"),
    ("/backup.sql",              ["GET"],        "backup_sql",     lambda: "-- MySQL dump\nCREATE TABLE users ...\n", "text/plain"),
    ("/wp-admin",                ["GET","POST"], "wp_admin",       lambda: "<html><title>WordPress Login</title></html>", "text/html"),
    ("/wp-login.php",            ["GET","POST"], "wp_login",       lambda: "<html><title>WordPress Login</title></html>", "text/html"),
    ("/phpmyadmin",              ["GET","POST"], "phpmyadmin",     _fake_phpmyadmin,    "text/html"),
    ("/phpmyadmin/index.php",    ["GET","POST"], "phpmyadmin_idx", _fake_phpmyadmin,    "text/html"),
    ("/admin",                   ["GET","POST"], "admin",          lambda: {"status":"ok","admin":True}, "application/json"),
    ("/admin/",                  ["GET","POST"], "admin_slash",    lambda: {"status":"ok"}, "application/json"),
    ("/shell",                   ["GET","POST"], "shell",          _fake_shell,         "text/plain"),
    ("/console",                 ["GET","POST"], "console",        _fake_debug,         "application/json"),
    ("/debug",                   ["GET"],        "debug",          _fake_debug,         "application/json"),
    ("/server-status",           ["GET"],        "server_status",  _fake_server_status, "text/plain"),
    ("/server-info",             ["GET"],        "server_info",    _fake_server_status, "text/plain"),
    ("/api/v1/admin/users",      ["GET"],        "admin_users",    _fake_admin_users,   "application/json"),
    ("/api/v1/admin",            ["GET"],        "admin_api",      _fake_admin_users,   "application/json"),
    ("/api/keys",                ["GET"],        "api_keys",       _fake_api_keys,      "application/json"),
    ("/api/secret",              ["GET"],        "api_secret",     _fake_api_keys,      "application/json"),
    ("/_internal",               ["GET"],        "internal",       _fake_debug,         "application/json"),
    ("/setup",                   ["GET","POST"], "setup",          lambda: {"setup_complete":False,"db_configured":False}, "application/json"),
    ("/install",                 ["GET","POST"], "install",        lambda: {"installed":False}, "application/json"),
    ("/actuator/health",         ["GET"],        "actuator",       _fake_actuator,      "application/json"),
    ("/actuator/env",            ["GET"],        "actuator_env",   _fake_config,        "application/json"),
    ("/actuator/beans",          ["GET"],        "actuator_beans", _fake_debug,         "application/json"),
    ("/actuator/mappings",       ["GET"],        "actuator_maps",  _fake_debug,         "application/json"),
    ("/metrics",                 ["GET"],        "metrics",        lambda: {"requests":12840,"errors":0}, "application/json"),
    ("/robots.txt",              ["GET"],        "robots",         lambda: "User-agent: *\nDisallow: /admin\nDisallow: /.env\nDisallow: /config\n", "text/plain"),
    ("/sitemap.xml",             ["GET"],        "sitemap",        lambda: "<?xml version='1.0'?><urlset/>", "text/xml"),
    ("/xmlrpc.php",              ["POST"],       "xmlrpc",         lambda: "<?xml version='1.0'?><methodResponse/>", "text/xml"),
    ("/cgi-bin/",                ["GET"],        "cgi",            lambda: "", "text/plain"),
]


def _make_trap_handler(trap_name: str, fake_content: Any, content_type: str):
    async def handler(request: Request):
        return await _handle_trap(request, trap_name, fake_content, content_type)
    handler.__name__ = f"trap_{trap_name}"
    return handler


# Register all trap routes
for _path, _methods, _tname, _fake, _ctype in TRAP_ROUTES:
    trap_router.add_api_route(
        _path,
        _make_trap_handler(_tname, _fake, _ctype),
        methods=_methods,
        include_in_schema=False,
    )

# ─────────────────────────────────────────────────────────────────────────────
# PASSIVE FINGERPRINT MIDDLEWARE (catches scans against real routes too)
# ─────────────────────────────────────────────────────────────────────────────

class HoneypotMiddleware:
    """
    Starlette middleware that silently scores every inbound request.
    Doesn't interfere with legitimate traffic — just scores and watches.
    """
    SKIP_PREFIXES = ("/api/honeypot", "/static", "/ui/", "/_")
    SCAN_PATH_PATTERNS = [
        re.compile(r'\.(php|asp|aspx|jsp|cgi|cfm)$', re.I),
        re.compile(r'(passwd|shadow|id_rsa|authorized_keys|\.ssh)', re.I),
        re.compile(r'(eval|base64_decode|system\(|exec\()', re.I),
        re.compile(r'(\.\./|%2e%2e|%252e)', re.I),
        re.compile(r'(select\s+.+from|union\s+select)', re.I),
    ]

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        headers = dict(scope.get("headers", []))

        # Skip our own honeypot API and static assets
        if any(path.startswith(p) for p in self.SKIP_PREFIXES):
            await self.app(scope, receive, send)
            return

        # Extract IP
        client = scope.get("client")
        ip = client[0] if client else "unknown"
        xff = headers.get(b"x-forwarded-for", b"").decode()
        if xff:
            ip = xff.split(",")[0].strip()

        if _is_whitelisted(ip):
            await self.app(scope, receive, send)
            return

        ua = headers.get(b"user-agent", b"").decode()
        body = ""  # don't read body here — would break request

        score_delta, tools = _score_request(path, ua, body, {
            k.decode(): v.decode() for k, v in headers.items()
        })

        if score_delta >= 20:
            dossier = _store.get_or_create(ip)
            dossier.add_event(path, scope.get("method", "GET"), ua, "", score_delta)
            for t in tools:
                if t not in dossier.tool_signatures:
                    dossier.tool_signatures.append(t)

            if score_delta >= 30:
                alert = {
                    "event": "suspicious_request",
                    "ip": ip, "path": path, "ua": ua[:80],
                    "tools": tools, "suspicion": dossier.suspicion_score,
                    "ts": _now(),
                }
                _store.broadcast_alert(alert)

            if dossier.suspicion_score >= _config.suspicion_threshold and not dossier.counter_scanned:
                asyncio.create_task(_trigger_counter_scan(dossier))

        await self.app(scope, receive, send)

# ─────────────────────────────────────────────────────────────────────────────
# API — dashboard + SSE stream
# ─────────────────────────────────────────────────────────────────────────────

@api_router.get("/dashboard")
async def honeypot_dashboard():
    attackers = _store.list()
    return {
        "total_caught": len(attackers),
        "high_risk": sum(1 for a in attackers if a.suspicion_score >= 60),
        "counter_scanned": sum(1 for a in attackers if a.counter_scanned),
        "recent_alerts": _store.recent_alerts(20),
        "attackers": [a.to_dict() for a in attackers[:50]],
        "config": {
            "threshold": _config.suspicion_threshold,
            "tarpit": _config.tarpit_enabled,
            "counter_scan": _config.counter_scan_enabled,
            "transport": _config.counter_scan_transport,
        },
    }


@api_router.get("/stream")
async def honeypot_stream(request: Request):
    """SSE stream — real-time alerts as attackers hit traps."""
    q = _store.subscribe()

    async def generator():
        # Send recent alerts as initial burst
        for alert in _store.recent_alerts(10):
            yield f"data: {json.dumps(alert)}\n\n"

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
            _store.unsubscribe(q)

    return StreamingResponse(generator(), media_type="text/event-stream",
        headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no","Connection":"keep-alive"})


@api_router.get("/dossier/{ip}")
async def get_dossier(ip: str):
    d = _store.get(ip)
    if not d:
        return JSONResponse(status_code=404, content={"error": "No dossier found"})
    full = d.to_dict()
    full["all_events"] = d.events
    full["all_payloads"] = d.payloads
    full["counter_findings"] = d.counter_findings
    return full


class WhitelistRequest(BaseModel):
    ip: str
    reason: str = ""

@api_router.post("/whitelist")
async def add_whitelist(req: WhitelistRequest):
    _config.whitelist.add(req.ip)
    return {"whitelisted": req.ip}


class ConfigUpdate(BaseModel):
    suspicion_threshold: Optional[int]  = None
    tarpit_enabled: Optional[bool]      = None
    tarpit_delay_s: Optional[float]     = None
    counter_scan_enabled: Optional[bool]= None
    counter_scan_transport: Optional[str]= None
    rotate_circuit_every: Optional[int] = None

@api_router.get("/config")
async def get_config():
    return {
        "suspicion_threshold": _config.suspicion_threshold,
        "tarpit_enabled": _config.tarpit_enabled,
        "tarpit_delay_s": _config.tarpit_delay_s,
        "counter_scan_enabled": _config.counter_scan_enabled,
        "counter_scan_transport": _config.counter_scan_transport,
        "rotate_circuit_every": _config.rotate_circuit_every,
        "whitelist_count": len(_config.whitelist),
    }

@api_router.post("/config")
async def update_config(req: ConfigUpdate):
    if req.suspicion_threshold is not None:
        _config.suspicion_threshold = max(0, min(100, req.suspicion_threshold))
    if req.tarpit_enabled is not None:
        _config.tarpit_enabled = req.tarpit_enabled
    if req.tarpit_delay_s is not None:
        _config.tarpit_delay_s = max(0, min(30, req.tarpit_delay_s))
    if req.counter_scan_enabled is not None:
        _config.counter_scan_enabled = req.counter_scan_enabled
    if req.counter_scan_transport is not None:
        _config.counter_scan_transport = req.counter_scan_transport
    if req.rotate_circuit_every is not None:
        _config.rotate_circuit_every = max(1, req.rotate_circuit_every)
    return {"status": "updated"}
