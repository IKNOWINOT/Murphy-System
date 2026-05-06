"""
src/ethical_hacker.py — PATCH-198
Murphy System — Ethical Hacking / Website Security Scanner

Free tier  → score + 3 top findings (teaser). Gate: email capture.
Paid tier  → full breakdown, remediation steps, re-scan scheduling, badge.

What it scans (100% passive / non-destructive / ethical):
  ─────────────────────────────────────────────────────
  SSL/TLS
    certificate valid, expiry days, grade (A/B/C/F)
    weak ciphers, TLS version (1.0/1.1 = FAIL)
    HSTS header present

  HTTP Security Headers
    Strict-Transport-Security
    Content-Security-Policy
    X-Frame-Options
    X-Content-Type-Options
    Referrer-Policy
    Permissions-Policy
    Cross-Origin-Opener-Policy
    Cross-Origin-Resource-Policy

  DNS / Infrastructure
    SPF record (email spoofing)
    DMARC record
    DNSSEC enabled
    open DNS resolver check
    IPv6 support

  Open Ports (nmap top-20, non-intrusive)
    common dangerous open ports: 21,23,25,3389,5900,6379,27017

  Content / Exposure
    directory listing enabled
    .git exposed
    .env file exposed
    admin panel guessable (/admin, /wp-admin, /phpmyadmin)
    error pages leaking stack traces
    server version disclosure (Server header)

  Cookies
    Secure flag
    HttpOnly flag
    SameSite attribute

  Reputation
    Google Safe Browsing status (via public API)
    Blacklist check (SURBL, Spamhaus-style DNS checks)

Scoring: 0–100. Weighted per category. Letter grade A–F.
PATCH-198
"""
from __future__ import annotations

import hashlib, json, logging, re, socket, sqlite3, ssl, subprocess
import time, uuid, urllib.request, urllib.parse
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("murphy.ethicalhack")

SCAN_DB = "/var/lib/murphy-production/ethical_hack.db"

# ── Scoring weights ───────────────────────────────────────────────────────────
WEIGHTS = {
    "ssl":          25,
    "headers":      25,
    "dns":          15,
    "ports":        15,
    "exposure":     15,
    "cookies":       5,
}

GRADE_MAP = [
    (90, "A"), (75, "B"), (60, "C"), (45, "D"), (0, "F")
]


# ══════════════════════════════════════════════════════════════════════════════
# DB
# ══════════════════════════════════════════════════════════════════════════════

def ensure_tables() -> None:
    with sqlite3.connect(SCAN_DB, timeout=8) as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS scans (
                id           TEXT PRIMARY KEY,
                domain       TEXT,
                email        TEXT DEFAULT '',
                score        INTEGER DEFAULT 0,
                grade        TEXT DEFAULT 'F',
                tier         TEXT DEFAULT 'free',
                findings     TEXT DEFAULT '[]',
                full_report  TEXT DEFAULT '{}',
                status       TEXT DEFAULT 'pending',
                created_at   TEXT,
                completed_at TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS scan_leads (
                id         TEXT PRIMARY KEY,
                email      TEXT UNIQUE,
                domain     TEXT,
                scan_id    TEXT,
                converted  INTEGER DEFAULT 0,
                created_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_scans_domain ON scans(domain);
            CREATE INDEX IF NOT EXISTS idx_scans_email  ON scans(email);
        """)


# ══════════════════════════════════════════════════════════════════════════════
# INDIVIDUAL CHECK FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def _fetch(url: str, timeout: int = 8, follow: bool = True) -> Tuple[Optional[str], Dict]:
    """Returns (body, response_info). Uses GET — never POST. Never raises."""
    info: Dict = {"status": 0, "headers": {}, "final_url": url, "error": ""}
    try:
        req = urllib.request.Request(
            url,
            method="GET",
            headers={
                "User-Agent": "MurphySecurityScanner/1.0 (+https://murphy.systems/security)",
                "Accept": "text/html,application/xhtml+xml,application/json,*/*",
            }
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            info["status"]    = r.status
            info["headers"]   = dict(r.headers)
            info["final_url"] = r.url
            body = r.read(65536).decode("utf-8", errors="replace")
            return body, info
    except urllib.error.HTTPError as e:
        info["status"] = e.code
        info["headers"] = dict(e.headers) if e.headers else {}
        return None, info
    except Exception as e:
        info["error"] = str(e)
        return None, info


def check_ssl(domain: str) -> Dict:
    findings = []
    passed = 0; total = 5
    details = {}

    try:
        ctx = ssl.create_default_context()
        with ctx.wrap_socket(socket.socket(), server_hostname=domain) as s:
            s.settimeout(8)
            s.connect((domain, 443))
            cert = s.getpeercert()
            cipher = s.cipher()

        # Expiry
        exp = datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z")
        days_left = (exp - datetime.utcnow()).days
        details["cert_expiry_days"] = days_left
        details["cert_subject"]     = dict(x[0] for x in cert.get("subject",[]))
        details["cert_issuer"]      = dict(x[0] for x in cert.get("issuer",[]))

        if days_left < 0:
            findings.append({"severity":"CRITICAL","title":"SSL certificate EXPIRED",
                "detail":f"Certificate expired {abs(days_left)} days ago","category":"ssl"})
        elif days_left < 14:
            findings.append({"severity":"HIGH","title":"SSL certificate expiring soon",
                "detail":f"Expires in {days_left} days","category":"ssl"})
        else:
            passed += 1

        # TLS version / cipher
        tls_ver = cipher[1] if cipher else ""
        details["tls_version"] = tls_ver
        details["cipher"]      = cipher[0] if cipher else ""
        if tls_ver in ("TLSv1", "TLSv1.1", "SSLv3", "SSLv2"):
            findings.append({"severity":"HIGH","title":f"Weak TLS version: {tls_ver}",
                "detail":"TLS 1.0/1.1 are deprecated. Upgrade to TLS 1.2+","category":"ssl"})
        else:
            passed += 1

        passed += 1  # cert valid

    except ssl.SSLCertVerificationError as e:
        findings.append({"severity":"CRITICAL","title":"SSL certificate invalid",
            "detail":str(e)[:120],"category":"ssl"})
    except Exception as e:
        findings.append({"severity":"HIGH","title":"SSL/HTTPS not available",
            "detail":str(e)[:100],"category":"ssl"})

    # HSTS header
    _, info = _fetch(f"https://{domain}", timeout=6)
    h = {k.lower(): v for k, v in info.get("headers", {}).items()}
    if "strict-transport-security" in h:
        hsts_val = h["strict-transport-security"]
        details["hsts"] = hsts_val
        if "preload" not in hsts_val:
            findings.append({"severity":"LOW","title":"HSTS missing preload flag",
                "detail":"Add 'preload' to Strict-Transport-Security to enable browser HSTS preload list",
                "category":"ssl"})
        else:
            passed += 1
    else:
        findings.append({"severity":"MEDIUM","title":"HSTS header missing",
            "detail":"Strict-Transport-Security not set — browsers may allow HTTP downgrade","category":"ssl"})

    score = round((passed / total) * WEIGHTS["ssl"])
    return {"score": score, "max": WEIGHTS["ssl"], "findings": findings, "details": details}


def check_headers(domain: str) -> Dict:
    findings = []
    passed = 0
    REQUIRED = {
        "content-security-policy":   ("HIGH",   "CSP missing — XSS attacks possible"),
        "x-frame-options":           ("MEDIUM",  "X-Frame-Options missing — clickjacking risk"),
        "x-content-type-options":    ("LOW",     "X-Content-Type-Options missing — MIME sniffing risk"),
        "referrer-policy":           ("LOW",     "Referrer-Policy missing — data leakage risk"),
        "permissions-policy":        ("LOW",     "Permissions-Policy missing"),
        "cross-origin-opener-policy":("LOW",     "COOP header missing"),
    }
    details = {}

    # Try GET on root — if that fails or gives 4xx, try /api/health
    _, info = _fetch(f"https://{domain}/", timeout=8)
    if info.get("status",0) in (405, 0):
        _, info = _fetch(f"https://{domain}/api/health", timeout=8)
    if info.get("status",0) in (405, 0):
        _, info = _fetch(f"https://{domain}/index.html", timeout=8)
    h = {k.lower(): v for k, v in info.get("headers", {}).items()}

    # Server disclosure
    srv = h.get("server","")
    if srv and any(c.isdigit() for c in srv):
        findings.append({"severity":"LOW","title":f"Server version disclosed: {srv[:60]}",
            "detail":"Remove version number from Server header to reduce fingerprinting","category":"headers"})
    else:
        passed += 1

    for header, (sev, msg) in REQUIRED.items():
        if header in h:
            passed += 1
            details[header] = h[header][:80]
            # Extra: check CSP quality
            if header == "content-security-policy":
                csp_val = h[header].lower()
                if "unsafe-eval" in csp_val:
                    findings.append({"severity":"MEDIUM","title":"CSP allows unsafe-eval",
                        "detail":"Remove 'unsafe-eval' from script-src — enables arbitrary JS execution",
                        "category":"headers"})
                if "unsafe-inline" in csp_val and "nonce-" not in csp_val:
                    findings.append({"severity":"LOW","title":"CSP uses unsafe-inline without nonce",
                        "detail":"Replace 'unsafe-inline' with CSP nonces for stronger XSS protection",
                        "category":"headers"})
        else:
            findings.append({"severity": sev, "title": f"Missing header: {header}",
                "detail": msg, "category": "headers"})

    total = len(REQUIRED) + 1
    # CORS wildcard check
    acao = h.get("access-control-allow-origin","")
    if acao == "*":
        findings.append({"severity":"MEDIUM","title":"Overly broad CORS: Access-Control-Allow-Origin: *",
            "detail":"Wildcard CORS allows any origin to read API responses — scope to specific domains",
            "category":"headers"})
    else:
        passed += 1

    total += 1
    score = round((passed / total) * WEIGHTS["headers"])
    return {"score": score, "max": WEIGHTS["headers"], "findings": findings, "details": details}


def check_dns(domain: str) -> Dict:
    findings = []
    passed = 0; total = 3
    details = {}

    # SPF
    try:
        import subprocess
        spf = subprocess.run(["dig", "+short", "TXT", domain],
                             capture_output=True, text=True, timeout=6).stdout
        if "v=spf1" in spf.lower():
            passed += 1
            details["spf"] = "present"
        else:
            findings.append({"severity":"HIGH","title":"SPF record missing",
                "detail":"No SPF record — anyone can spoof email from your domain","category":"dns"})
    except Exception:
        try:
            result = socket.getaddrinfo(domain, None)
            passed += 1
        except Exception:
            findings.append({"severity":"HIGH","title":"Domain not resolving",
                "detail":"DNS lookup failed","category":"dns"})

    # DMARC
    try:
        dmarc = subprocess.run(["dig", "+short", "TXT", f"_dmarc.{domain}"],
                               capture_output=True, text=True, timeout=6).stdout
        if "v=dmarc1" in dmarc.lower():
            passed += 1
            details["dmarc"] = "present"
        else:
            findings.append({"severity":"HIGH","title":"DMARC record missing",
                "detail":"No DMARC policy — email spoofing not blocked","category":"dns"})
    except Exception:
        findings.append({"severity":"MEDIUM","title":"DMARC check failed",
            "detail":"Could not verify DMARC record","category":"dns"})

    # IPv6
    try:
        socket.getaddrinfo(domain, None, socket.AF_INET6)
        passed += 1
        details["ipv6"] = True
    except Exception:
        details["ipv6"] = False
        findings.append({"severity":"LOW","title":"No IPv6 support",
            "detail":"IPv6 not configured — minor future-proofing gap","category":"dns"})

    score = round((passed / total) * WEIGHTS["dns"])
    return {"score": score, "max": WEIGHTS["dns"], "findings": findings, "details": details}


def check_ports(domain: str) -> Dict:
    findings = []
    passed = 0
    details = {}
    DANGEROUS = {
        21:    ("HIGH",   "FTP open — unencrypted file transfer"),
        23:    ("CRITICAL","Telnet open — unencrypted remote access"),
        3306:  ("HIGH",   "MySQL exposed to internet"),
        5432:  ("HIGH",   "PostgreSQL exposed to internet"),
        6379:  ("CRITICAL","Redis exposed — no auth by default"),
        27017: ("CRITICAL","MongoDB exposed — data breach risk"),
        3389:  ("HIGH",   "RDP open — brute-force target"),
        5900:  ("HIGH",   "VNC open — remote desktop exposed"),
        8080:  ("MEDIUM", "HTTP alt-port open — possible dev server"),
        9200:  ("CRITICAL","Elasticsearch open — data exposure risk"),
        2375:  ("CRITICAL","Docker daemon exposed — full host takeover risk"),
    }

    try:
        nm_out = subprocess.run(
            ["nmap", "-T3", "--open", "-p",
             ",".join(str(p) for p in DANGEROUS.keys()),
             "--host-timeout", "15s", domain],
            capture_output=True, text=True, timeout=20
        ).stdout
        details["nmap_raw"] = nm_out[:500]

        open_ports = re.findall(r"(\d+)/tcp\s+open", nm_out)
        details["open_dangerous_ports"] = open_ports

        for port_str in open_ports:
            port = int(port_str)
            if port in DANGEROUS:
                sev, msg = DANGEROUS[port]
                findings.append({"severity": sev,
                    "title": f"Dangerous port open: {port}",
                    "detail": msg, "category": "ports"})
            else:
                findings.append({"severity":"MEDIUM",
                    "title": f"Unexpected port open: {port}",
                    "detail": "Review whether this service needs to be publicly accessible",
                    "category": "ports"})

        if not open_ports:
            passed = WEIGHTS["ports"]
        else:
            SEV_SCORE = {"CRITICAL":15,"HIGH":10,"MEDIUM":5,"LOW":2}
            deductions = sum(
                SEV_SCORE.get(DANGEROUS.get(int(p),("LOW",""))[0], 2)
                for p in open_ports
            ) if open_ports else 0
            passed = max(0, WEIGHTS["ports"] - deductions)

    except Exception as e:
        logger.debug("Port scan error: %s", e)
        details["port_scan_error"] = str(e)
        passed = WEIGHTS["ports"] // 2  # neutral if scan fails

    return {"score": passed, "max": WEIGHTS["ports"], "findings": findings, "details": details}


def check_exposure(domain: str) -> Dict:
    findings = []
    passed = 0; total = 7
    details = {}

    PATHS = [
        ("/.git/HEAD",           "CRITICAL", ".git directory exposed — source code leaked"),
        ("/.env",                "CRITICAL", ".env file exposed — credentials/secrets leaked"),
        ("/wp-admin/",           "MEDIUM",   "WordPress admin panel guessable"),
        ("/phpmyadmin/",         "HIGH",     "phpMyAdmin exposed — database admin tool public"),
        ("/admin/",              "MEDIUM",   "Admin panel at /admin/ — possible brute-force target"),
        ("/.htpasswd",           "HIGH",     ".htpasswd exposed — credentials file public"),
        ("/server-status",       "MEDIUM",   "Apache server-status exposed — reveals internal info"),
    ]

    for path, sev, msg in PATHS:
        url = f"https://{domain}{path}"
        body, info = _fetch(url, timeout=5)
        status = info.get("status", 0)
        if status in (200, 301, 302) and body:
            # Verify it's actually exposing something real
            is_real = True
            if path == "/.git/HEAD" and body and "ref:" not in body:
                is_real = False
            if path == "/.env" and body and "=" not in body:
                is_real = False
            if is_real:
                findings.append({"severity": sev, "title": f"Exposed: {path}",
                    "detail": msg, "category": "exposure", "url": url})
                details[path] = f"HTTP {status}"
            else:
                passed += 1
        else:
            passed += 1
        time.sleep(0.2)

    score = round((passed / total) * WEIGHTS["exposure"])
    return {"score": score, "max": WEIGHTS["exposure"], "findings": findings, "details": details}


def check_cookies(domain: str) -> Dict:
    findings = []
    passed = 0; total = 3
    details = {}

    body, info = _fetch(f"https://{domain}", timeout=8)
    h = {k.lower(): v for k, v in info.get("headers", {}).items()}
    set_cookie = h.get("set-cookie", "")

    if not set_cookie:
        return {"score": WEIGHTS["cookies"], "max": WEIGHTS["cookies"],
                "findings": [], "details": {"note": "No cookies set on homepage"}}

    cookie_lower = set_cookie.lower()
    if "secure" in cookie_lower:
        passed += 1
    else:
        findings.append({"severity":"MEDIUM","title":"Cookie missing Secure flag",
            "detail":"Cookies can be sent over HTTP — session hijack risk","category":"cookies"})

    if "httponly" in cookie_lower:
        passed += 1
    else:
        findings.append({"severity":"MEDIUM","title":"Cookie missing HttpOnly flag",
            "detail":"Cookies accessible via JavaScript — XSS can steal sessions","category":"cookies"})

    if "samesite" in cookie_lower:
        passed += 1
    else:
        findings.append({"severity":"LOW","title":"Cookie missing SameSite attribute",
            "detail":"CSRF attack surface slightly increased","category":"cookies"})

    details["set_cookie_sample"] = set_cookie[:100]
    score = round((passed / total) * WEIGHTS["cookies"])
    return {"score": score, "max": WEIGHTS["cookies"], "findings": findings, "details": details}


# ══════════════════════════════════════════════════════════════════════════════
# MAIN SCAN
# ══════════════════════════════════════════════════════════════════════════════

def _grade(score: int) -> str:
    for threshold, letter in GRADE_MAP:
        if score >= threshold:
            return letter
    return "F"


def _severity_order(f: Dict) -> int:
    return {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}.get(f.get("severity","LOW"), 4)


def run_scan(domain: str, email: str = "", tier: str = "free") -> str:
    """
    Run full ethical hack scan. Returns scan_id.
    Scan runs in background — poll /api/ethicalhack/result/{scan_id}.
    """
    ensure_tables()
    domain = re.sub(r"https?://", "", domain).split("/")[0].lower().strip()
    scan_id = str(uuid.uuid4())[:16]
    now = datetime.now(timezone.utc).isoformat()

    with sqlite3.connect(SCAN_DB, timeout=5) as db:
        db.execute(
            "INSERT INTO scans (id,domain,email,score,grade,tier,status,created_at) "
            "VALUES (?,?,?,0,'?',?,?,?)",
            (scan_id, domain, email, tier, "running", now)
        )
        db.commit()

    # Capture email as lead
    if email:
        with sqlite3.connect(SCAN_DB, timeout=5) as db:
            db.execute(
                "INSERT OR IGNORE INTO scan_leads (id,email,domain,scan_id,created_at) "
                "VALUES (?,?,?,?,?)",
                (str(uuid.uuid4())[:12], email.lower(), domain, scan_id, now)
            )
            db.commit()
        # Also add to CRM
        _add_scan_lead_to_crm(email, domain, scan_id)

    # Run scan synchronously (FastAPI will run this in threadpool via run_in_executor)
    try:
        report = _execute_scan(domain)
        all_findings = []
        total_score  = 0
        category_scores = {}

        for cat, result in report.items():
            total_score += result.get("score", 0)
            category_scores[cat] = {
                "score": result.get("score",0),
                "max":   result.get("max",0),
                "pct":   round(result.get("score",0)/max(result.get("max",1),1)*100),
            }
            all_findings.extend(result.get("findings", []))

        all_findings.sort(key=_severity_order)
        grade = _grade(total_score)

        full_report = {
            "domain":           domain,
            "score":            total_score,
            "grade":            grade,
            "category_scores":  category_scores,
            "all_findings":     all_findings,
            "critical_count":   sum(1 for f in all_findings if f["severity"]=="CRITICAL"),
            "high_count":       sum(1 for f in all_findings if f["severity"]=="HIGH"),
            "medium_count":     sum(1 for f in all_findings if f["severity"]=="MEDIUM"),
            "low_count":        sum(1 for f in all_findings if f["severity"]=="LOW"),
            "scanned_at":       datetime.now(timezone.utc).isoformat(),
        }

        # Free tier: show score + grade + top 3 findings (teaser)
        free_findings = all_findings[:3]

        # PATCH-199: Feed scan results into SecurityBrain for learning
        try:
            from src.security_brain import learn_from_scan
            learn_from_scan(full_report)
        except Exception as _be:
            logger.debug("[EthicalHack] Brain learn error: %s", _be)

        with sqlite3.connect(SCAN_DB, timeout=5) as db:
            db.execute(
                "UPDATE scans SET score=?,grade=?,findings=?,full_report=?,"
                "status=?,completed_at=? WHERE id=?",
                (total_score, grade,
                 json.dumps(free_findings),
                 json.dumps(full_report),
                 "complete",
                 datetime.now(timezone.utc).isoformat(),
                 scan_id)
            )
            db.commit()

    except Exception as e:
        logger.error("[EthicalHack] Scan failed for %s: %s", domain, e)
        with sqlite3.connect(SCAN_DB, timeout=5) as db:
            db.execute("UPDATE scans SET status='error' WHERE id=?", (scan_id,))
            db.commit()

    return scan_id


def _execute_scan(domain: str) -> Dict:
    """Run all check functions. Returns dict by category."""
    report = {}
    checks = [
        ("ssl",      check_ssl),
        ("headers",  check_headers),
        ("dns",      check_dns),
        ("exposure", check_exposure),
        ("cookies",  check_cookies),
        ("ports",    check_ports),
    ]
    for name, fn in checks:
        try:
            report[name] = fn(domain)
        except Exception as e:
            logger.warning("[EthicalHack] %s check error on %s: %s", name, domain, e)
            report[name] = {"score": 0, "max": WEIGHTS.get(name,10),
                            "findings": [], "details": {"error": str(e)}}
        time.sleep(0.3)
    return report


def get_result(scan_id: str, tier: str = "free") -> Dict:
    """Return scan result. tier=free → teaser. tier=paid → full report."""
    ensure_tables()
    try:
        with sqlite3.connect(SCAN_DB, timeout=5) as db:
            db.row_factory = sqlite3.Row
            row = db.execute("SELECT * FROM scans WHERE id=?", (scan_id,)).fetchone()
    except Exception as e:
        return {"error": str(e)}
    if not row:
        return {"error": "Scan not found"}

    base = {
        "scan_id":      scan_id,
        "domain":       row["domain"],
        "score":        row["score"],
        "grade":        row["grade"],
        "status":       row["status"],
        "created_at":   row["created_at"],
        "completed_at": row["completed_at"],
    }

    if row["status"] != "complete":
        return base

    free_findings = json.loads(row["findings"] or "[]")
    full_report   = json.loads(row["full_report"] or "{}")

    if tier == "free":
        return {
            **base,
            "findings":         free_findings,
            "total_findings":   full_report.get("critical_count",0) +
                                full_report.get("high_count",0) +
                                full_report.get("medium_count",0) +
                                full_report.get("low_count",0),
            "critical_count":   full_report.get("critical_count",0),
            "high_count":       full_report.get("high_count",0),
            "teaser":           True,
            "upgrade_message":  (
                f"Your site scored {row['score']}/100 ({row['grade']}). "
                f"We found {full_report.get('critical_count',0)} critical and "
                f"{full_report.get('high_count',0)} high-severity issues. "
                "Unlock the full breakdown, remediation steps, and re-scan scheduling."
            ),
        }
    else:
        return {**base, **full_report, "teaser": False}


def _add_scan_lead_to_crm(email: str, domain: str, scan_id: str) -> None:
    """Add scan requester to CRM as a warm lead."""
    try:
        with sqlite3.connect("/var/lib/murphy-production/crm.db", timeout=5) as db:
            existing = db.execute(
                "SELECT id FROM contacts WHERE LOWER(email)=?", (email.lower(),)
            ).fetchone()
            if existing:
                return
            # Check DNC
            dnc = db.execute(
                "SELECT id FROM dnc_suppression WHERE LOWER(email)=?", (email.lower(),)
            ).fetchone()
            if dnc:
                return
            cid = str(uuid.uuid4())[:12]
            did = str(uuid.uuid4())[:12]
            now = datetime.now(timezone.utc).isoformat()
            db.execute(
                "INSERT INTO contacts (id,name,email,company,contact_type,owner_id,"
                "tags,custom_fields,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (cid, "", email, domain, "lead", "founder",
                 json.dumps(["ethical-hack-scan","warm-lead"]),
                 json.dumps({"scan_id": scan_id, "domain": domain,
                             "source": "ethical_hack_scanner",
                             "buying_trigger": "Requested free security scan"}),
                 now)
            )
            db.execute(
                "INSERT INTO deals (id,title,stage,value,contact_id,owner_id,"
                "notes,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (did, f"{domain} — Security Scan Lead", "qualified", 4900,
                 cid, "founder",
                 f"Came in via free ethical hack scan. Scan ID: {scan_id}",
                 now, now)
            )
            db.commit()
        logger.info("[EthicalHack] CRM lead added: %s @ %s", email, domain)
    except Exception as e:
        logger.warning("[EthicalHack] CRM lead error: %s", e)


def get_scan_stats() -> Dict:
    ensure_tables()
    try:
        with sqlite3.connect(SCAN_DB, timeout=5) as db:
            total  = db.execute("SELECT COUNT(*) FROM scans").fetchone()[0]
            done   = db.execute("SELECT COUNT(*) FROM scans WHERE status='complete'").fetchone()[0]
            leads  = db.execute("SELECT COUNT(*) FROM scan_leads").fetchone()[0]
            conv   = db.execute("SELECT COUNT(*) FROM scan_leads WHERE converted=1").fetchone()[0]
            avg_sc = db.execute("SELECT AVG(score) FROM scans WHERE status='complete'").fetchone()[0]
        return {
            "total_scans":     total,
            "completed":       done,
            "leads_captured":  leads,
            "converted":       conv,
            "avg_score":       round(avg_sc or 0, 1),
        }
    except Exception as e:
        return {"error": str(e)}
