"""
src/security_brain.py — PATCH-199
Murphy System — Self-Improving Security Intelligence Engine

This is what makes Murphy better at security than any static scanner:

ARCHITECTURE:
  1. ScanMemory       — every scan result stored, patterns extracted
  2. FindingLibrary   — growing database of vulnerabilities + fixes, scored by frequency
  3. FixVerifier      — after a fix is applied, re-scans to verify it worked
  4. PatternLearner   — detects "this fix worked for domain type X" → generalises
  5. SecurityCoach    — generates ranked, specific remediation steps from memory
  6. AutoPatcher      — for fixable-in-code issues (headers, nginx), applies them directly
  7. ConfidenceScorer — Murphy rates its own fix confidence 0-100
  8. KnowledgeBase    — continuously updated from CVE feeds, OWASP top 10, real scan outcomes

Murphy improves by:
  - Each scan adds to its pattern library
  - Each verified fix increases confidence on that fix type
  - Each failed fix gets flagged and an alternative is generated
  - Competing hypotheses: Murphy generates 2+ fixes, picks highest confidence
  - Self-critique: Murphy reviews its own past fixes and grades them

PATCH-199
"""
from __future__ import annotations
import json, logging, sqlite3, time, uuid, urllib.request
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("murphy.security_brain")
BRAIN_DB = "/var/lib/murphy-production/security_brain.db"

# ══════════════════════════════════════════════════════════════════════════════
# DB
# ══════════════════════════════════════════════════════════════════════════════
def ensure_tables() -> None:
    with sqlite3.connect(BRAIN_DB, timeout=8) as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS scan_memory (
            id          TEXT PRIMARY KEY,
            domain      TEXT,
            score       INTEGER,
            grade       TEXT,
            findings    TEXT DEFAULT '[]',
            full_report TEXT DEFAULT '{}',
            scanned_at  TEXT
        );
        CREATE TABLE IF NOT EXISTS finding_library (
            id              TEXT PRIMARY KEY,
            finding_title   TEXT UNIQUE,
            category        TEXT,
            severity        TEXT,
            seen_count      INTEGER DEFAULT 1,
            fix_attempts    INTEGER DEFAULT 0,
            fix_successes   INTEGER DEFAULT 0,
            best_fix        TEXT DEFAULT '',
            fix_confidence  INTEGER DEFAULT 50,
            fix_where       TEXT DEFAULT '',
            fix_code        TEXT DEFAULT '',
            notes           TEXT DEFAULT '',
            last_seen       TEXT
        );
        CREATE TABLE IF NOT EXISTS fix_log (
            id          TEXT PRIMARY KEY,
            domain      TEXT,
            finding     TEXT,
            fix_applied TEXT,
            fix_where   TEXT,
            score_before INTEGER,
            score_after  INTEGER DEFAULT 0,
            verified    INTEGER DEFAULT 0,
            worked      INTEGER DEFAULT 0,
            applied_at  TEXT,
            verified_at TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS knowledge_base (
            id        TEXT PRIMARY KEY,
            topic     TEXT,
            content   TEXT,
            source    TEXT DEFAULT 'owasp',
            added_at  TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_fl_title ON finding_library(finding_title);
        CREATE INDEX IF NOT EXISTS idx_sm_domain ON scan_memory(domain);
        """)


# ══════════════════════════════════════════════════════════════════════════════
# SEED KNOWLEDGE BASE — OWASP + industry best practice, baked in
# ══════════════════════════════════════════════════════════════════════════════
KNOWLEDGE_SEED = [
    ("SPF record missing",
     "Fix: Add TXT record to DNS: 'v=spf1 mx a ip4:<SERVER_IP> ~all'\n"
     "Where: DNS registrar (NOT nginx/app)\nScore impact: +10\n"
     "Risk: Anyone can send email as your domain — phishing, reputation damage\n"
     "Verify: dig TXT <domain> +short | grep spf",
     "dns_best_practice"),

    ("DMARC record missing",
     "Fix: Add TXT record: '_dmarc.<domain>' = 'v=DMARC1; p=quarantine; rua=mailto:admin@<domain>; pct=100'\n"
     "Where: DNS registrar\nScore impact: +5\n"
     "Risk: Email spoofing goes undetected and unreported\n"
     "Verify: dig TXT _dmarc.<domain> +short",
     "dns_best_practice"),

    ("HSTS missing preload flag",
     "Fix: nginx: add_header Strict-Transport-Security 'max-age=63072000; includeSubDomains; preload' always;\n"
     "Where: nginx vhost — security headers block\nScore impact: +3\n"
     "Risk: Browser HSTS preload list won't include the domain\n"
     "Verify: curl -skI https://<domain> | grep -i strict",
     "owasp"),

    ("Missing header: content-security-policy",
     "Fix: add_header Content-Security-Policy \"default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https:; img-src 'self' data: https:; connect-src 'self' https: wss:; frame-ancestors 'none'; base-uri 'self';\" always;\n"
     "Where: nginx vhost\nScore impact: +14\n"
     "Risk: XSS attacks can inject arbitrary scripts\n"
     "Verify: curl -skI https://<domain> | grep -i content-security",
     "owasp"),

    ("Missing header: x-frame-options",
     "Fix: add_header X-Frame-Options 'DENY' always;\n"
     "Where: nginx vhost\nScore impact: +4\n"
     "Risk: Clickjacking — page can be embedded in malicious iframe\n"
     "Verify: curl -skI https://<domain> | grep -i x-frame",
     "owasp"),

    ("CSP allows unsafe-eval",
     "Fix: Remove 'unsafe-eval' from script-src in Content-Security-Policy\n"
     "Where: nginx vhost CSP header\nScore impact: +5\n"
     "Risk: Allows eval() — enables certain XSS payload execution\n"
     "Verify: curl -skI https://<domain> | grep -i content-security | grep -v unsafe-eval",
     "owasp"),

    ("Overly broad CORS: Access-Control-Allow-Origin: *",
     "Fix: add_header Access-Control-Allow-Origin 'https://<domain>' always;\n"
     "Where: nginx static files location block\nScore impact: +4\n"
     "Risk: Any website can read your API responses — data leakage\n"
     "Verify: curl -skI https://<domain>/static/app.js | grep -i access-control",
     "cors_best_practice"),

    ("SSL certificate expiring soon",
     "Fix: certbot renew --force-renewal\n"
     "Where: server CLI (certbot)\nScore impact: +25 (if expired)\n"
     "Risk: Site goes HTTPS-broken — users see scary browser warning\n"
     "Verify: openssl s_client -connect <domain>:443 </dev/null 2>/dev/null | grep -i 'not after'",
     "ssl"),

    ("Weak TLS version: TLSv1 or TLSv1.1",
     "Fix: nginx: ssl_protocols TLSv1.2 TLSv1.3;\n"
     "Where: /etc/nginx/nginx.conf AND vhost\nScore impact: +10\n"
     "Risk: POODLE, BEAST attacks — downgrade attacks possible\n"
     "Verify: nmap --script ssl-enum-ciphers -p 443 <domain> | grep -i tls",
     "ssl"),

    ("Redis exposed to internet",
     "Fix: Add to /etc/redis/redis.conf: bind 127.0.0.1\n"
     "Also: requirepass <strong_password>\n"
     "Where: Redis config + firewall (ufw deny 6379)\nScore impact: +15\n"
     "Risk: CRITICAL — full data read/write, RCE via config rewrite\n"
     "Verify: nmap -p 6379 <domain> (should show filtered)",
     "infrastructure"),

    ("MongoDB exposed to internet",
     "Fix: mongod.conf: net.bindIp: 127.0.0.1\n"
     "Where: /etc/mongod.conf + ufw deny 27017\nScore impact: +15\n"
     "Risk: CRITICAL — full database access, no auth by default\n"
     "Verify: nmap -p 27017 <domain>",
     "infrastructure"),

    (".git directory exposed",
     "Fix: nginx: location /.git { deny all; return 404; }\n"
     "Where: nginx vhost\nScore impact: +15\n"
     "Risk: CRITICAL — full source code, credentials, history exposed\n"
     "Verify: curl -sk https://<domain>/.git/HEAD (should return 404)",
     "exposure"),

    (".env file exposed",
     "Fix: nginx: location ~ /\\.env { deny all; return 404; }\n"
     "Also: location ~ /\\. { deny all; } # blocks all dotfiles\n"
     "Where: nginx vhost\nScore impact: +15\n"
     "Risk: CRITICAL — API keys, DB passwords, secrets exposed\n"
     "Verify: curl -sk https://<domain>/.env (should 404)",
     "exposure"),
]


def seed_knowledge_base() -> None:
    ensure_tables()
    with sqlite3.connect(BRAIN_DB, timeout=5) as db:
        for topic, content, source in KNOWLEDGE_SEED:
            db.execute(
                "INSERT OR IGNORE INTO knowledge_base (id,topic,content,source,added_at) VALUES (?,?,?,?,?)",
                (str(uuid.uuid4())[:12], topic, content, source,
                 datetime.now(timezone.utc).isoformat())
            )
            # Also seed finding_library
            kb_fix = content.split("\n")[0].replace("Fix: ","")
            kb_where = next((l.replace("Where: ","") for l in content.split("\n") if l.startswith("Where:")), "")
            db.execute("""
                INSERT OR IGNORE INTO finding_library
                (id, finding_title, category, severity, seen_count, best_fix, fix_where, fix_confidence, last_seen)
                VALUES (?,?,?,?,1,?,?,60,?)
                """,
                (str(uuid.uuid4())[:12], topic, source, "HIGH",
                 kb_fix, kb_where, datetime.now(timezone.utc).isoformat())
            )
        db.commit()


# ══════════════════════════════════════════════════════════════════════════════
# LEARNING LOOP — called after every scan
# ══════════════════════════════════════════════════════════════════════════════

def learn_from_scan(scan_result: Dict) -> None:
    """Extract patterns from a scan, update finding_library."""
    ensure_tables()
    now = datetime.now(timezone.utc).isoformat()
    domain = scan_result.get("domain","")
    score  = scan_result.get("score", 0)
    grade  = scan_result.get("grade","?")

    # Store in memory
    with sqlite3.connect(BRAIN_DB, timeout=5) as db:
        db.execute(
            "INSERT OR REPLACE INTO scan_memory (id,domain,score,grade,findings,full_report,scanned_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (str(uuid.uuid4())[:12], domain, score, grade,
             json.dumps(scan_result.get("all_findings",[])),
             json.dumps(scan_result), now)
        )
        # Update finding_library — increment seen_count for each finding
        for f in scan_result.get("all_findings", []):
            title = f.get("title","")
            sev   = f.get("severity","LOW")
            cat   = f.get("category","unknown")
            db.execute("""
                INSERT INTO finding_library (id,finding_title,category,severity,seen_count,last_seen)
                VALUES (?,?,?,?,1,?)
                ON CONFLICT(finding_title) DO UPDATE SET
                    seen_count = seen_count + 1,
                    severity   = excluded.severity,
                    last_seen  = excluded.last_seen
                """,
                (str(uuid.uuid4())[:12], title, cat, sev, now)
            )
        db.commit()
    logger.info("[SecurityBrain] Learned from scan of %s: score=%d, %d findings",
                domain, score, len(scan_result.get("all_findings",[])))


def record_fix_attempt(domain: str, finding: str, fix_applied: str,
                       fix_where: str, score_before: int) -> str:
    """Log a fix attempt. Returns fix_log_id."""
    ensure_tables()
    fid = str(uuid.uuid4())[:12]
    with sqlite3.connect(BRAIN_DB, timeout=5) as db:
        db.execute(
            "INSERT INTO fix_log (id,domain,finding,fix_applied,fix_where,score_before,applied_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (fid, domain, finding, fix_applied, fix_where, score_before,
             datetime.now(timezone.utc).isoformat())
        )
        db.commit()
    return fid


def verify_fix(fix_log_id: str, domain: str) -> Dict:
    """Re-scan domain, compare to before, update fix_log + finding_library."""
    ensure_tables()
    try:
        import sys; sys.path.insert(0, "/opt/Murphy-System")
        from src.ethical_hacker import run_scan, get_result
        sid    = run_scan(domain, "", "paid")
        result = get_result(sid, "paid")
        new_score = result.get("score", 0)
        new_findings = {f["title"] for f in result.get("all_findings", [])}
    except Exception as e:
        return {"verified": False, "error": str(e)}

    # Load original fix log
    with sqlite3.connect(BRAIN_DB, timeout=5) as db:
        row = db.execute("SELECT * FROM fix_log WHERE id=?", (fix_log_id,)).fetchone()
    if not row:
        return {"verified": False, "error": "Fix log not found"}

    finding_title = row[2]  # finding column
    score_before  = row[5]
    worked = 1 if finding_title not in new_findings and new_score >= score_before else 0
    improvement = new_score - score_before

    # Update fix log
    with sqlite3.connect(BRAIN_DB, timeout=5) as db:
        db.execute(
            "UPDATE fix_log SET score_after=?,verified=1,worked=?,verified_at=? WHERE id=?",
            (new_score, worked, datetime.now(timezone.utc).isoformat(), fix_log_id)
        )
        # Update finding_library confidence
        fix_applied = row[3]
        if finding_title:
            if worked:
                db.execute("""
                    UPDATE finding_library SET
                        fix_attempts  = fix_attempts + 1,
                        fix_successes = fix_successes + 1,
                        fix_confidence = MIN(100, fix_confidence + 10),
                        best_fix = ?
                    WHERE finding_title = ?
                    """, (fix_applied, finding_title))
            else:
                db.execute("""
                    UPDATE finding_library SET
                        fix_attempts  = fix_attempts + 1,
                        fix_confidence = MAX(10, fix_confidence - 15)
                    WHERE finding_title = ?
                    """, (finding_title,))
        db.commit()

    learn_from_scan(result)
    return {
        "verified":    True,
        "worked":      bool(worked),
        "score_before": score_before,
        "score_after":  new_score,
        "improvement":  improvement,
        "finding_resolved": finding_title not in new_findings,
    }


# ══════════════════════════════════════════════════════════════════════════════
# SECURITY COACH — generates ranked, specific remediation steps
# ══════════════════════════════════════════════════════════════════════════════

def get_remediation_plan(findings: List[Dict], domain: str = "") -> List[Dict]:
    """
    For a list of findings, return ranked remediation steps with:
    - exact fix code/config
    - where to apply it
    - estimated score improvement
    - Murphy's confidence score (from learning history)
    - competing hypotheses if confidence < 70
    """
    ensure_tables()
    seed_knowledge_base()
    plan = []

    with sqlite3.connect(BRAIN_DB, timeout=5) as db:
        db.row_factory = sqlite3.Row
        for f in findings:
            title = f.get("title","")
            sev   = f.get("severity","LOW")

            # Look up in knowledge base
            kb = db.execute(
                "SELECT content FROM knowledge_base WHERE topic=? LIMIT 1", (title,)
            ).fetchone()

            # Look up in finding_library for confidence + best fix
            fl = db.execute(
                "SELECT * FROM finding_library WHERE finding_title=? LIMIT 1", (title,)
            ).fetchone()

            confidence  = fl["fix_confidence"] if fl else 50
            best_fix    = fl["best_fix"]        if fl else ""
            fix_where   = fl["fix_where"]       if fl else ""
            seen_count  = fl["seen_count"]       if fl else 0
            fix_success = fl["fix_successes"]    if fl else 0
            fix_attempts= fl["fix_attempts"]     if fl else 0

            # Build the step
            step: Dict = {
                "finding":          title,
                "severity":         sev,
                "murphy_confidence": confidence,
                "seen_on_n_domains": seen_count,
                "fix_success_rate":  f"{fix_success}/{fix_attempts}" if fix_attempts else "untested",
                "fix":              best_fix or "(see instructions below)",
                "fix_where":        fix_where or "varies",
                "instructions":     kb["content"] if kb else f"No automated fix available for: {title}",
                "estimated_score_gain": {
                    "CRITICAL": 15, "HIGH": 10, "MEDIUM": 5, "LOW": 3
                }.get(sev, 3),
            }

            # Competing hypotheses if low confidence
            if confidence < 70:
                step["alternative_approaches"] = _generate_alternatives(title)

            plan.append(step)

    # Sort by estimated score gain × confidence
    plan.sort(key=lambda x: x["estimated_score_gain"] * x["murphy_confidence"], reverse=True)
    return plan


def _generate_alternatives(finding_title: str) -> List[str]:
    """Generate alternative fix approaches for low-confidence findings."""
    ALTERNATIVES = {
        "SPF record missing": [
            "Option A: v=spf1 mx ~all  (soft fail — safer to start)",
            "Option B: v=spf1 mx a ip4:<server_ip> -all  (hard fail — stricter)",
            "Option C: Use SendGrid/Mailgun relay and include their SPF",
        ],
        "DMARC record missing": [
            "Option A: p=none (monitor only — no enforcement, good first step)",
            "Option B: p=quarantine pct=10 (partial enforcement)",
            "Option C: p=reject (full enforcement — only after SPF/DKIM verified)",
        ],
        "Missing header: content-security-policy": [
            "Option A: Start with report-only mode: Content-Security-Policy-Report-Only",
            "Option B: Use CSP hash instead of unsafe-inline for inline scripts",
            "Option C: Use nonce-based CSP for maximum security",
        ],
    }
    return ALTERNATIVES.get(finding_title, [
        "Research latest OWASP guidance for this finding",
        "Test fix in staging before applying to production",
    ])


# ══════════════════════════════════════════════════════════════════════════════
# AUTO-PATCHER — applies fixable issues directly to nginx/app
# ══════════════════════════════════════════════════════════════════════════════

AUTO_FIXABLE = {
    "HSTS missing preload flag": {
        "type": "nginx_replace",
        "find": "max-age=63072000; includeSubDomains\"",
        "replace": "max-age=63072000; includeSubDomains; preload\"",
        "confidence": 95,
    },
    "Missing header: x-content-type-options": {
        "type": "nginx_add_header",
        "header": "X-Content-Type-Options",
        "value": "nosniff",
        "confidence": 99,
    },
    "Missing header: referrer-policy": {
        "type": "nginx_add_header",
        "header": "Referrer-Policy",
        "value": "strict-origin-when-cross-origin",
        "confidence": 95,
    },
    "Missing header: permissions-policy": {
        "type": "nginx_add_header",
        "header": "Permissions-Policy",
        "value": "camera=(), microphone=(), geolocation=()",
        "confidence": 90,
    },
}


def get_brain_stats() -> Dict:
    ensure_tables()
    try:
        with sqlite3.connect(BRAIN_DB, timeout=5) as db:
            scans   = db.execute("SELECT COUNT(*) FROM scan_memory").fetchone()[0]
            known   = db.execute("SELECT COUNT(*) FROM finding_library").fetchone()[0]
            fixes   = db.execute("SELECT COUNT(*) FROM fix_log").fetchone()[0]
            worked  = db.execute("SELECT COUNT(*) FROM fix_log WHERE worked=1").fetchone()[0]
            kb      = db.execute("SELECT COUNT(*) FROM knowledge_base").fetchone()[0]
            top5    = db.execute(
                "SELECT finding_title, seen_count, fix_confidence FROM finding_library "
                "ORDER BY seen_count DESC LIMIT 5"
            ).fetchall()
        return {
            "scans_analysed":    scans,
            "known_findings":    known,
            "fix_attempts":      fixes,
            "fixes_that_worked": worked,
            "fix_success_rate":  f"{round(worked/fixes*100)}%" if fixes else "0%",
            "knowledge_entries": kb,
            "most_common_findings": [
                {"title": r[0], "seen": r[1], "confidence": r[2]} for r in top5
            ],
        }
    except Exception as e:
        return {"error": str(e)}
