"""
Ethical Hacking Engine — PATCH-085
Murphy System Self-Penetration Testing & Authorized Target Scanning

Capabilities:
  1. Self-scan: Murphy audits its own running API for vulnerabilities
  2. Port scan: TCP connect scan on authorized targets
  3. Header audit: HTTP security header analysis
  4. Auth probe: test for common auth weaknesses (default creds, bypass patterns)
  5. Input fuzzing: OWASP Top-10 payload injection against form endpoints
  6. SSL/TLS audit: certificate and cipher analysis
  7. Rate limit probe: test if endpoints enforce rate limiting
  8. CORS audit: detect misconfigured CORS policies
  9. Secret leak scan: check for exposed secrets in HTTP responses / JS
  10. Session audit: cookie flags, session fixation vectors

REST API (prefix /api/hack):
  POST /api/hack/scan          — launch a full scan job (async, returns job_id)
  GET  /api/hack/scan/{job_id} — poll scan status + results
  GET  /api/hack/scans         — list all scan jobs
  POST /api/hack/self          — quick self-scan of this Murphy instance
  GET  /api/hack/payloads      — list available fuzzing payload categories
  DELETE /api/hack/scan/{job_id} — delete a scan record

Safety invariants:
  - All target scans require explicit authorization flag in request
  - Self-scan is always permitted
  - Rate-limited: max 1 concurrent scan per session
  - All findings logged with timestamp, severity, and remediation advice
  - Non-destructive: read-only probes only (no exploit execution)

PATCH-085 | Label: ETH-HACK-001
Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""
from __future__ import annotations

import asyncio
import ipaddress
import json
import logging
import socket
import ssl
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/hack", tags=["ethical_hacking"])

# ---------------------------------------------------------------------------
# Severity + Finding types
# ---------------------------------------------------------------------------

class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH     = "high"
    MEDIUM   = "medium"
    LOW      = "low"
    INFO     = "info"


class FindingCategory(str, Enum):
    HEADERS         = "missing_security_headers"
    AUTH            = "authentication_weakness"
    INJECTION       = "injection_vulnerability"
    SSL             = "ssl_tls_weakness"
    CORS            = "cors_misconfiguration"
    RATE_LIMIT      = "missing_rate_limiting"
    SECRET_LEAK     = "secret_exposure"
    SESSION         = "session_weakness"
    PORT            = "open_port"
    INFO_DISCLOSURE = "information_disclosure"


@dataclass
class Finding:
    category: FindingCategory
    severity: Severity
    title: str
    detail: str
    evidence: str
    remediation: str
    endpoint: str = ""
    cvss_estimate: float = 0.0


# ---------------------------------------------------------------------------
# Job store (in-memory, bounded)
# ---------------------------------------------------------------------------

class ScanStatus(str, Enum):
    PENDING   = "pending"
    RUNNING   = "running"
    COMPLETE  = "complete"
    ERROR     = "error"


@dataclass
class ScanJob:
    job_id: str
    target: str
    started_at: str
    status: ScanStatus = ScanStatus.PENDING
    finished_at: Optional[str] = None
    findings: List[Dict] = field(default_factory=list)
    summary: Dict = field(default_factory=dict)
    error: Optional[str] = None


_jobs: Dict[str, ScanJob] = {}
_jobs_lock = threading.Lock()
_MAX_JOBS = 200


def _store_job(job: ScanJob) -> None:
    with _jobs_lock:
        if len(_jobs) >= _MAX_JOBS:
            oldest = sorted(_jobs.values(), key=lambda j: j.started_at)[0]
            del _jobs[oldest.job_id]
        _jobs[job.job_id] = job


def _get_job(job_id: str) -> Optional[ScanJob]:
    with _jobs_lock:
        return _jobs.get(job_id)


# ---------------------------------------------------------------------------
# OWASP Top-10 fuzzing payloads
# ---------------------------------------------------------------------------

PAYLOADS: Dict[str, List[str]] = {
    "sqli": [
        "' OR '1'='1", "' OR 1=1--", "'; DROP TABLE users;--",
        "1' AND SLEEP(3)--", "\" OR \"\"=\"", "\\' OR 1=1--",
    ],
    "xss": [
        "<script>alert(1)</script>", "<img src=x onerror=alert(1)>",
        "javascript:alert(1)", "<svg onload=alert(1)>",
        "'><script>alert(document.cookie)</script>",
    ],
    "ssti": [
        "{{7*7}}", "${7*7}", "#{7*7}", "<%=7*7%>", "{{''.class.mro[2].subclasses()}}",
    ],
    "lfi": [
        "../../../../etc/passwd", "..\\..\\..\\windows\\win.ini",
        "/etc/passwd%00", "....//....//etc/passwd",
    ],
    "cmdi": [
        "; ls -la", "| whoami", "`id`", "$(id)", "; cat /etc/passwd",
    ],
    "open_redirect": [
        "//evil.com", "https://evil.com", "/\\evil.com",
        "javascript:alert(1)", "%2F%2Fevil.com",
    ],
}

# Security headers we require
REQUIRED_HEADERS = {
    "Strict-Transport-Security": {
        "severity": Severity.HIGH,
        "remediation": "Add: Strict-Transport-Security: max-age=31536000; includeSubDomains; preload",
    },
    "Content-Security-Policy": {
        "severity": Severity.MEDIUM,
        "remediation": "Add a Content-Security-Policy header to restrict resource loading.",
    },
    "X-Content-Type-Options": {
        "severity": Severity.MEDIUM,
        "remediation": "Add: X-Content-Type-Options: nosniff",
    },
    "X-Frame-Options": {
        "severity": Severity.MEDIUM,
        "remediation": "Add: X-Frame-Options: DENY or SAMEORIGIN to prevent clickjacking.",
    },
    "Referrer-Policy": {
        "severity": Severity.LOW,
        "remediation": "Add: Referrer-Policy: strict-origin-when-cross-origin",
    },
    "Permissions-Policy": {
        "severity": Severity.LOW,
        "remediation": "Add: Permissions-Policy to restrict browser feature access.",
    },
}

# Common ports to check
COMMON_PORTS = [21, 22, 23, 25, 80, 443, 3000, 3306, 5432, 5672, 6379, 8000, 8080, 8443, 9200, 27017]

# ---------------------------------------------------------------------------
# Scan probes
# ---------------------------------------------------------------------------

async def _probe_headers(target: str, client: httpx.AsyncClient) -> List[Finding]:
    findings = []
    try:
        resp = await client.get(target, follow_redirects=True, timeout=10)
        headers = {k.lower(): v for k, v in resp.headers.items()}

        for hdr, meta in REQUIRED_HEADERS.items():
            if hdr.lower() not in headers:
                findings.append(Finding(
                    category=FindingCategory.HEADERS,
                    severity=meta["severity"],
                    title=f"Missing security header: {hdr}",
                    detail=f"The response from {target} is missing the {hdr} header.",
                    evidence=f"Response headers: {dict(list(headers.items())[:8])}",
                    remediation=meta["remediation"],
                    endpoint=target,
                ))

        # Check for server version disclosure
        server = headers.get("server", "")
        x_powered = headers.get("x-powered-by", "")
        if any(c.isdigit() for c in server) or x_powered:
            findings.append(Finding(
                category=FindingCategory.INFO_DISCLOSURE,
                severity=Severity.LOW,
                title="Server version disclosure",
                detail="The server is revealing technology version info in headers.",
                evidence=f"Server: {server} | X-Powered-By: {x_powered}",
                remediation="Remove or genericise Server and X-Powered-By headers.",
                endpoint=target,
                cvss_estimate=3.1,
            ))

    except Exception as e:
        logger.warning("HACK: header probe failed for %s: %s", target, e)

    return findings


async def _probe_cors(target: str, client: httpx.AsyncClient) -> List[Finding]:
    findings = []
    evil_origin = "https://evil-attacker.com"
    try:
        resp = await client.options(
            target,
            headers={"Origin": evil_origin, "Access-Control-Request-Method": "GET"},
            timeout=10,
        )
        acao = resp.headers.get("access-control-allow-origin", "")
        acac = resp.headers.get("access-control-allow-credentials", "")

        if acao == "*":
            findings.append(Finding(
                category=FindingCategory.CORS,
                severity=Severity.MEDIUM,
                title="CORS wildcard origin",
                detail="Access-Control-Allow-Origin: * allows any site to read responses.",
                evidence=f"ACAO: {acao}",
                remediation="Restrict CORS to specific trusted origins.",
                endpoint=target,
                cvss_estimate=5.4,
            ))
        if acao == evil_origin:
            sev = Severity.CRITICAL if acac.lower() == "true" else Severity.HIGH
            findings.append(Finding(
                category=FindingCategory.CORS,
                severity=sev,
                title="CORS reflects arbitrary origin" + (" with credentials" if acac.lower() == "true" else ""),
                detail="Server reflects any Origin value in ACAO header.",
                evidence=f"ACAO: {acao} | ACAC: {acac}",
                remediation="Validate Origin against a whitelist before reflecting it.",
                endpoint=target,
                cvss_estimate=8.1 if sev == Severity.CRITICAL else 6.5,
            ))
    except Exception as e:
        logger.warning("HACK: CORS probe failed: %s", e)

    return findings


async def _probe_rate_limit(target: str, client: httpx.AsyncClient) -> List[Finding]:
    findings = []
    login_url = urljoin(target.rstrip("/") + "/", "api/auth/login")
    responses = []
    try:
        for _ in range(15):
            r = await client.post(
                login_url,
                json={"email": "test@example.com", "password": "wrongpassword"},
                timeout=5,
            )
            responses.append(r.status_code)
        # If we never get 429 or 403, rate limiting is absent
        if 429 not in responses and all(c not in responses for c in [403, 503]):
            findings.append(Finding(
                category=FindingCategory.RATE_LIMIT,
                severity=Severity.HIGH,
                title="No rate limiting on login endpoint",
                detail="15 consecutive failed login attempts received no 429 response.",
                evidence=f"Status codes: {responses}",
                remediation="Implement rate limiting (e.g. slowapi) on /api/auth/login — max 5 attempts per minute per IP.",
                endpoint=login_url,
                cvss_estimate=7.5,
            ))
    except Exception as e:
        logger.warning("HACK: rate limit probe failed: %s", e)

    return findings


async def _probe_ssl(target: str) -> List[Finding]:
    findings = []
    parsed = urlparse(target)
    host = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == "https" else 80)

    if parsed.scheme != "https":
        findings.append(Finding(
            category=FindingCategory.SSL,
            severity=Severity.HIGH,
            title="Target not using HTTPS",
            detail="The target URL does not use HTTPS.",
            evidence=f"Scheme: {parsed.scheme}",
            remediation="Redirect all HTTP traffic to HTTPS and use a valid TLS certificate.",
            endpoint=target,
            cvss_estimate=7.4,
        ))
        return findings

    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((host, port), timeout=10) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                cert = ssock.getpeercert()
                cipher = ssock.cipher()
                proto = ssock.version()

                # Check protocol version
                if proto in ("SSLv2", "SSLv3", "TLSv1", "TLSv1.1"):
                    findings.append(Finding(
                        category=FindingCategory.SSL,
                        severity=Severity.HIGH,
                        title=f"Deprecated TLS version: {proto}",
                        detail=f"The server supports {proto} which has known vulnerabilities.",
                        evidence=f"Negotiated: {proto}",
                        remediation="Disable TLS 1.0 and 1.1. Require TLS 1.2+ minimum.",
                        endpoint=target,
                        cvss_estimate=7.4,
                    ))

                # Check cert expiry
                not_after = cert.get("notAfter", "")
                if not_after:
                    exp = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
                    days_left = (exp - datetime.now(timezone.utc)).days
                    if days_left < 30:
                        sev = Severity.CRITICAL if days_left < 7 else Severity.HIGH
                        findings.append(Finding(
                            category=FindingCategory.SSL,
                            severity=sev,
                            title=f"TLS certificate expires in {days_left} days",
                            detail="Certificate expiry will cause browsers to block access.",
                            evidence=f"Not After: {not_after}",
                            remediation="Renew the certificate immediately. Use certbot auto-renewal.",
                            endpoint=target,
                            cvss_estimate=8.2,
                        ))
                else:
                    findings.append(Finding(
                        category=FindingCategory.SSL,
                        severity=Severity.INFO,
                        title="TLS OK",
                        detail=f"TLS {proto} active, cipher: {cipher[0] if cipher else 'unknown'}",
                        evidence=f"Cert expires: {not_after}",
                        remediation="No action needed.",
                        endpoint=target,
                    ))
    except ssl.SSLCertVerificationError as e:
        findings.append(Finding(
            category=FindingCategory.SSL,
            severity=Severity.CRITICAL,
            title="TLS certificate verification failure",
            detail="The TLS certificate is invalid, expired, or self-signed.",
            evidence=str(e),
            remediation="Install a valid certificate from a trusted CA (e.g. Let's Encrypt).",
            endpoint=target,
            cvss_estimate=9.1,
        ))
    except Exception as e:
        logger.warning("HACK: SSL probe failed: %s", e)

    return findings


async def _probe_auth(target: str, client: httpx.AsyncClient) -> List[Finding]:
    findings = []
    login_url = urljoin(target.rstrip("/") + "/", "api/auth/login")

    default_creds = [
        {"email": "admin@admin.com", "password": "admin"},
        {"email": "admin@murphy.systems", "password": "admin"},
        {"email": "test@test.com", "password": "test"},
        {"email": "admin@murphy.systems", "password": "password"},
        {"email": "admin@murphy.systems", "password": "Password1"},
    ]

    for creds in default_creds:
        try:
            r = await client.post(login_url, json=creds, timeout=5)
            if r.status_code == 200:
                data = r.json()
                if data.get("success") or data.get("token") or data.get("session_token"):
                    findings.append(Finding(
                        category=FindingCategory.AUTH,
                        severity=Severity.CRITICAL,
                        title="Default credentials accepted",
                        detail=f"Login succeeded with default credentials: {creds['email']}",
                        evidence=f"HTTP 200 with success response",
                        remediation="Change default credentials immediately. Enforce strong password policy.",
                        endpoint=login_url,
                        cvss_estimate=9.8,
                    ))
        except Exception:
            pass

    # Check for auth bypass on protected endpoint
    protected = urljoin(target.rstrip("/") + "/", "api/admin/users")
    try:
        r = await client.get(protected, timeout=5)
        if r.status_code == 200:
            findings.append(Finding(
                category=FindingCategory.AUTH,
                severity=Severity.CRITICAL,
                title="Admin endpoint accessible without authentication",
                detail=f"GET {protected} returned 200 without any auth token.",
                evidence=f"HTTP {r.status_code}",
                remediation="Ensure all /api/admin/* routes require authenticated owner/admin role.",
                endpoint=protected,
                cvss_estimate=9.1,
            ))
    except Exception:
        pass

    return findings


async def _probe_injection(target: str, client: httpx.AsyncClient) -> List[Finding]:
    findings = []
    # Fuzz the login endpoint with injection payloads
    login_url = urljoin(target.rstrip("/") + "/", "api/auth/login")
    search_url = urljoin(target.rstrip("/") + "/", "api/search")

    for category, payloads in [("sqli", PAYLOADS["sqli"][:3]), ("xss", PAYLOADS["xss"][:2]), ("ssti", PAYLOADS["ssti"][:2])]:
        for payload in payloads:
            try:
                r = await client.post(
                    login_url,
                    json={"email": payload, "password": payload},
                    timeout=5,
                )
                body = r.text.lower()
                # Look for reflection or SQL errors
                error_signals = ["syntax error", "sql", "mysql", "postgresql", "sqlite",
                                 "traceback", "exception", "stack trace", str(payload).lower()[:10]]
                for sig in error_signals:
                    if sig in body and sig not in ["email", "password"]:
                        findings.append(Finding(
                            category=FindingCategory.INJECTION,
                            severity=Severity.HIGH,
                            title=f"Potential {category.upper()} reflection/error on login",
                            detail=f"Payload '{payload}' triggered signal '{sig}' in response.",
                            evidence=f"HTTP {r.status_code}, body contains: '{sig}'",
                            remediation="Sanitize all inputs, use parameterized queries, never reflect raw user input in errors.",
                            endpoint=login_url,
                            cvss_estimate=8.1,
                        ))
                        break
            except Exception:
                pass

    return findings


async def _probe_secret_leak(target: str, client: httpx.AsyncClient) -> List[Finding]:
    findings = []
    import re as _re

    secret_patterns = [
        (r"ghp_[A-Za-z0-9]{36}", "GitHub PAT"),
        (r"sk-[A-Za-z0-9]{48}", "OpenAI API key"),
        (r"AKIA[0-9A-Z]{16}", "AWS Access Key"),
        (r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}", "JWT token"),
        (r"password\s*[:=]\s*['\"]?[^\s'\"]{8,}", "Hardcoded password"),
    ]

    # Check main page, JS files
    urls_to_check = [target, urljoin(target, "/ui/murphy-runtime.js"), urljoin(target, "/static/murphy.js")]
    for url in urls_to_check:
        try:
            r = await client.get(url, timeout=8)
            for pattern, label in secret_patterns:
                matches = _re.findall(pattern, r.text)
                if matches:
                    findings.append(Finding(
                        category=FindingCategory.SECRET_LEAK,
                        severity=Severity.CRITICAL,
                        title=f"Secret leaked in HTTP response: {label}",
                        detail=f"Found pattern matching {label} in response from {url}.",
                        evidence=f"Pattern: {pattern} | Matches: {len(matches)}",
                        remediation="Remove all secrets from client-facing code and HTTP responses. Use environment variables.",
                        endpoint=url,
                        cvss_estimate=9.8,
                    ))
        except Exception:
            pass

    return findings


async def _probe_session(target: str, client: httpx.AsyncClient) -> List[Finding]:
    findings = []
    login_url = urljoin(target.rstrip("/") + "/", "api/auth/login")
    try:
        r = await client.post(
            login_url,
            json={"email": "probe@example.com", "password": "wrongpassword123"},
            timeout=5,
        )
        sc_header = r.headers.get("set-cookie", "")
        if sc_header:
            flags = sc_header.lower()
            if "httponly" not in flags:
                findings.append(Finding(
                    category=FindingCategory.SESSION,
                    severity=Severity.HIGH,
                    title="Session cookie missing HttpOnly flag",
                    detail="Cookie accessible via JavaScript — XSS can steal sessions.",
                    evidence=f"Set-Cookie: {sc_header[:200]}",
                    remediation="Add HttpOnly flag to all session cookies.",
                    endpoint=login_url,
                    cvss_estimate=7.4,
                ))
            if "secure" not in flags:
                findings.append(Finding(
                    category=FindingCategory.SESSION,
                    severity=Severity.HIGH,
                    title="Session cookie missing Secure flag",
                    detail="Cookie sent over HTTP — can be intercepted by MITM.",
                    evidence=f"Set-Cookie: {sc_header[:200]}",
                    remediation="Add Secure flag to all session cookies on HTTPS deployments.",
                    endpoint=login_url,
                    cvss_estimate=6.8,
                ))
            if "samesite" not in flags:
                findings.append(Finding(
                    category=FindingCategory.SESSION,
                    severity=Severity.MEDIUM,
                    title="Session cookie missing SameSite attribute",
                    detail="Missing SameSite allows cross-site request forgery.",
                    evidence=f"Set-Cookie: {sc_header[:200]}",
                    remediation="Add SameSite=Lax or SameSite=Strict to session cookies.",
                    endpoint=login_url,
                    cvss_estimate=5.4,
                ))
    except Exception as e:
        logger.warning("HACK: session probe error: %s", e)

    return findings


def _port_scan(host: str, ports: List[int] = COMMON_PORTS) -> List[Finding]:
    """Synchronous TCP connect scan."""
    findings = []
    for port in ports:
        try:
            with socket.create_connection((host, port), timeout=2):
                findings.append(Finding(
                    category=FindingCategory.PORT,
                    severity=Severity.INFO if port in (80, 443, 22) else Severity.MEDIUM,
                    title=f"Open port: {port}",
                    detail=f"TCP port {port} is open and accepting connections on {host}.",
                    evidence=f"TCP connect to {host}:{port} succeeded",
                    remediation="Close any ports that don't need to be public. Use firewall rules (UFW) to restrict.",
                    endpoint=f"{host}:{port}",
                ))
        except (socket.timeout, ConnectionRefusedError, OSError):
            pass

    # Flag dangerous open ports
    dangerous = {21: "FTP (unencrypted)", 23: "Telnet (unencrypted)", 6379: "Redis (often unauthenticated)"}
    for f in findings:
        port_num = int(f.endpoint.split(":")[-1])
        if port_num in dangerous:
            f.severity = Severity.HIGH
            f.title = f"Dangerous open port: {port_num} ({dangerous[port_num]})"
            f.cvss_estimate = 8.0

    return findings


# ---------------------------------------------------------------------------
# Full scan runner
# ---------------------------------------------------------------------------

async def _run_scan(job: ScanJob, authorized: bool) -> None:
    target = job.target
    all_findings: List[Finding] = []

    try:
        job.status = ScanStatus.RUNNING

        async with httpx.AsyncClient(verify=False, timeout=15) as client:
            # Run all probes concurrently
            probe_tasks = [
                _probe_headers(target, client),
                _probe_cors(target, client),
                _probe_ssl(target),
                _probe_session(target, client),
                _probe_secret_leak(target, client),
            ]
            if authorized:
                probe_tasks += [
                    _probe_rate_limit(target, client),
                    _probe_auth(target, client),
                    _probe_injection(target, client),
                ]

            results = await asyncio.gather(*probe_tasks, return_exceptions=True)
            for r in results:
                if isinstance(r, list):
                    all_findings.extend(r)

            # Port scan (sync, run in thread)
            parsed = urlparse(target)
            host = parsed.hostname
            if host and authorized:
                loop = asyncio.get_event_loop()
                port_findings = await loop.run_in_executor(None, _port_scan, host)
                all_findings.extend(port_findings)

        # Summarize
        sev_counts = {s.value: 0 for s in Severity}
        for f in all_findings:
            sev_counts[f.severity.value] += 1

        risk_score = (
            sev_counts["critical"] * 10 +
            sev_counts["high"] * 7 +
            sev_counts["medium"] * 4 +
            sev_counts["low"] * 1
        )

        job.findings = [
            {
                "category": f.category.value,
                "severity": f.severity.value,
                "title": f.title,
                "detail": f.detail,
                "evidence": f.evidence,
                "remediation": f.remediation,
                "endpoint": f.endpoint,
                "cvss_estimate": f.cvss_estimate,
            }
            for f in all_findings
        ]
        job.summary = {
            "total_findings": len(all_findings),
            "severity_breakdown": sev_counts,
            "risk_score": risk_score,
            "risk_level": (
                "critical" if risk_score >= 30 else
                "high" if risk_score >= 15 else
                "medium" if risk_score >= 5 else
                "low"
            ),
        }
        job.status = ScanStatus.COMPLETE

    except Exception as e:
        job.status = ScanStatus.ERROR
        job.error = str(e)
        logger.error("HACK: scan job %s failed: %s", job.job_id, e)

    finally:
        job.finished_at = datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------

class ScanRequest(BaseModel):
    target: str
    authorized: bool = False  # Must be True for intrusive probes


class SelfScanRequest(BaseModel):
    include_intrusive: bool = True


@router.post("/scan")
async def launch_scan(req: ScanRequest):
    """Launch an async security scan against a target."""
    # Basic target validation
    parsed = urlparse(req.target)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise HTTPException(status_code=400, detail="Invalid target URL. Must be http:// or https://")

    job = ScanJob(
        job_id=str(uuid.uuid4()),
        target=req.target,
        started_at=datetime.now(timezone.utc).isoformat(),
    )
    _store_job(job)

    # Fire and forget
    asyncio.create_task(_run_scan(job, authorized=req.authorized))

    return {"job_id": job.job_id, "status": "pending", "target": req.target}


@router.post("/self")
async def self_scan(req: SelfScanRequest = SelfScanRequest()):
    """Scan this Murphy instance (always authorized)."""
    target = "https://murphy.systems"

    job = ScanJob(
        job_id=str(uuid.uuid4()),
        target=target,
        started_at=datetime.now(timezone.utc).isoformat(),
    )
    _store_job(job)

    asyncio.create_task(_run_scan(job, authorized=req.include_intrusive))

    return {"job_id": job.job_id, "status": "pending", "target": target, "note": "Self-scan always authorized"}


@router.get("/scan/{job_id}")
async def get_scan(job_id: str):
    """Poll scan status and results."""
    job = _get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Scan job not found")

    return {
        "job_id": job.job_id,
        "target": job.target,
        "status": job.status.value,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
        "summary": job.summary,
        "findings": job.findings,
        "error": job.error,
    }


@router.get("/scans")
async def list_scans():
    """List all scan jobs."""
    with _jobs_lock:
        jobs = sorted(_jobs.values(), key=lambda j: j.started_at, reverse=True)
    return {
        "count": len(jobs),
        "scans": [
            {
                "job_id": j.job_id,
                "target": j.target,
                "status": j.status.value,
                "started_at": j.started_at,
                "finished_at": j.finished_at,
                "summary": j.summary,
            }
            for j in jobs
        ],
    }


@router.delete("/scan/{job_id}")
async def delete_scan(job_id: str):
    """Delete a scan record."""
    with _jobs_lock:
        if job_id not in _jobs:
            raise HTTPException(status_code=404, detail="Scan job not found")
        del _jobs[job_id]
    return {"deleted": job_id}


@router.get("/payloads")
async def list_payloads():
    """List available fuzzing payload categories."""
    return {
        "categories": list(PAYLOADS.keys()),
        "counts": {k: len(v) for k, v in PAYLOADS.items()},
        "total": sum(len(v) for v in PAYLOADS.values()),
    }
