"""
Murphy Ghost Runner — ghost_runner.py
PATCH-155

Standalone autonomous API key acquisition engine.
Runs OUTSIDE the systemd service sandbox — no namespace restrictions.
Full Playwright + real Chromium (--no-sandbox) + MurphyCaptchaSolver.

Usage (CLI):
    python3 ghost_runner.py --provider stripe
    python3 ghost_runner.py --provider sendgrid --email murphy@murphy.systems
    python3 ghost_runner.py --provider deepinfra
    python3 ghost_runner.py list

Usage (from service):
    POST /api/ghost-runner/run   {"provider": "stripe"}
    GET  /api/ghost-runner/status
    GET  /api/ghost-runner/result/{provider}

Every provider:
  1. Launches real Chromium (no sandbox, --disable-dev-shm-usage)
  2. Applies stealth fingerprint JS
  3. Fills form with human-like timing
  4. Invokes MurphyCaptchaSolver cascade (audio → visual → HITL)
  5. Handles email verification via IMAP (self-hosted mailserver)
  6. Extracts API key(s) from dashboard
  7. Stores via Murphy credential vault + env file

Copyright © 2020-2026 Inoni LLC — Created by Corey Post
PATCH-155 | Label: MCB-GHOST-RUNNER-001
License: BSL 1.1
"""
from __future__ import annotations

import argparse
import asyncio
import email as email_lib
import imaplib
import json
import logging
import os
import random
import re
import sqlite3
import sys
import time
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ── Paths ──────────────────────────────────────────────────────────────────────
SRC_DIR       = Path("/opt/Murphy-System/src")
CACHE_DIR     = Path("/opt/Murphy-System/.cache")
CHROMIUM_BIN  = str(CACHE_DIR / "ms-playwright/chromium-1217/chrome-linux64/chrome")
DB_PATH       = Path("/var/lib/murphy-production/ghost_runner.db")
LOG_PATH      = Path("/var/log/murphy-production/ghost_runner.log")

# ── Murphy API ─────────────────────────────────────────────────────────────────
MURPHY_API    = "http://127.0.0.1:8000"
FOUNDER_KEY   = "founder_ad6b1fade355dc1c6dfa89db96d77608886bf63b01b4fb70"
ENV_FILE      = "/etc/murphy-production/environment"

# ── Mail (self-hosted) ─────────────────────────────────────────────────────────
IMAP_HOST     = "127.0.0.1"
IMAP_PORT     = 993
IMAP_USER     = "murphy@murphy.systems"
IMAP_PASS     = "UIKTCUFJ2IMxX6oluBUfLZhgILjCVyeAMstPeRvteg0"
SIGNUP_EMAIL  = "murphy@murphy.systems"
SIGNUP_PASS   = "Murphy2026!Xx#"   # strong default — overridden per provider

# ── Playwright env ─────────────────────────────────────────────────────────────
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(CACHE_DIR)
sys.path.insert(0, str(SRC_DIR))

# ── Logging — lazy init so file creation doesn't block service import ─────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("ghost_runner")

def _init_file_logging():
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(str(LOG_PATH))
        fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s — %(message)s"))
        logging.getLogger().addHandler(fh)
    except Exception as _lfe:
        logger.warning("[GhostRunner] File logging unavailable: %s", _lfe)

# ── Stealth JS — injected into every page context ──────────────────────────────
STEALTH_JS = """
() => {
    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
    Object.defineProperty(navigator, 'plugins',   {get: () => [1,2,3,4,5]});
    Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
    Object.defineProperty(navigator, 'platform',  {get: () => 'Win32'});
    window.chrome = {runtime:{}, loadTimes:function(){}, csi:function(){}, app:{}};
    const origQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = p =>
        p.name === 'notifications'
            ? Promise.resolve({state: Notification.permission})
            : origQuery(p);
}
"""

REAL_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

CHROMIUM_ARGS = [
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--disable-blink-features=AutomationControlled",
    "--window-size=1280,800",
]


# ══════════════════════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class RunResult:
    provider:   str
    success:    bool
    keys:       Dict[str, str] = field(default_factory=dict)  # {name: value}
    error:      Optional[str]  = None
    strategy:   str            = ""
    timestamp:  str            = field(default_factory=lambda: datetime.utcnow().isoformat())


# ══════════════════════════════════════════════════════════════════════════════
# DATABASE — run history + results cache
# ══════════════════════════════════════════════════════════════════════════════

class GhostRunnerDB:
    def __init__(self):
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        self._init()

    def _init(self):
        self.con.execute("""
            CREATE TABLE IF NOT EXISTS runs (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                provider  TEXT NOT NULL,
                success   INTEGER NOT NULL,
                keys_json TEXT,
                error     TEXT,
                strategy  TEXT,
                ts        TEXT
            )
        """)
        self.con.commit()

    def record(self, r: RunResult):
        self.con.execute(
            "INSERT INTO runs (provider,success,keys_json,error,strategy,ts) VALUES (?,?,?,?,?,?)",
            (r.provider, int(r.success), json.dumps(r.keys), r.error, r.strategy, r.timestamp),
        )
        self.con.commit()

    def last_result(self, provider: str) -> Optional[Dict]:
        cur = self.con.execute(
            "SELECT * FROM runs WHERE provider=? ORDER BY id DESC LIMIT 1", (provider,)
        )
        row = cur.fetchone()
        if not row:
            return None
        cols = [d[0] for d in cur.description]
        d = dict(zip(cols, row))
        d["keys_json"] = json.loads(d["keys_json"] or "{}")
        return d

    def all_runs(self, limit=50) -> List[Dict]:
        cur = self.con.execute("SELECT * FROM runs ORDER BY id DESC LIMIT ?", (limit,))
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


_db: Optional[GhostRunnerDB] = None

def get_db() -> GhostRunnerDB:
    global _db
    if _db is None:
        _db = GhostRunnerDB()
    return _db


# ══════════════════════════════════════════════════════════════════════════════
# BASE RUNNER — shared browser + captcha + IMAP + credential store utilities
# ══════════════════════════════════════════════════════════════════════════════

class BaseProviderRunner:
    """
    Base class for all provider-specific runners.
    Subclass and implement `_run(page) -> RunResult`.
    """
    PROVIDER = "base"

    def __init__(self):
        self.email   = SIGNUP_EMAIL
        self.password = SIGNUP_PASS

    # ── Browser ────────────────────────────────────────────────────────────────

    async def _launch(self):
        from playwright.async_api import async_playwright
        pw = await async_playwright().start()
        browser = await pw.chromium.launch(
            headless=True,
            executable_path=CHROMIUM_BIN,
            args=CHROMIUM_ARGS,
        )
        ctx = await browser.new_context(
            user_agent=REAL_UA,
            viewport={"width": 1280, "height": 800},
            locale="en-US",
            timezone_id="America/New_York",
        )
        await ctx.add_init_script(STEALTH_JS)
        page = await ctx.new_page()
        return pw, browser, ctx, page

    async def _human_type(self, page, selector: str, text: str):
        await page.click(selector, timeout=8000)
        await asyncio.sleep(random.uniform(0.2, 0.6))
        for ch in text:
            await page.keyboard.type(ch)
            await asyncio.sleep(random.uniform(0.04, 0.16))

    async def _set_react_input(self, page, selector: str, value: str) -> bool:
        """Set value on a React-controlled input without losing state."""
        return await page.evaluate(
            """([sel, val]) => {
                const el = document.querySelector(sel);
                if (!el) return false;
                const setter = Object.getOwnPropertyDescriptor(
                    window.HTMLInputElement.prototype, 'value').set;
                setter.call(el, val);
                el.dispatchEvent(new Event('input',  {bubbles:true}));
                el.dispatchEvent(new Event('change', {bubbles:true}));
                return true;
            }""",
            [selector, value],
        )

    async def _wait_selector(self, page, selector: str, timeout=20000) -> bool:
        try:
            await page.wait_for_selector(selector, timeout=timeout)
            return True
        except Exception:
            return False

    # ── Captcha ────────────────────────────────────────────────────────────────

    async def _solve_captcha(self, page) -> bool:
        """
        Invoke MurphyCaptchaSolver cascade.
        Falls back to HITL Matrix alert if all strategies fail.
        Returns True if solved (or no captcha found).
        """
        try:
            from murphy_captcha_solver import get_solver
            solver = get_solver()
            html = await page.content()
            url  = page.url

            # Detect type
            from murphy_captcha import CaptchaDetector, CaptchaType
            detector = CaptchaDetector()
            result   = detector.detect(html, url)

            if not result.detected:
                return True  # nothing to solve

            logger.info("[CaptchaGate] Detected: %s — strategy: %s", result.type.value, result.strategy)

            if result.type == CaptchaType.HCAPTCHA:
                sr = await solver.solve_hcaptcha(None, url, page)
            elif result.type in (CaptchaType.RECAPTCHA_V2, CaptchaType.RECAPTCHA_ENTERPRISE):
                sr = await solver.solve_recaptcha_v2(page)
            elif result.type == CaptchaType.CLOUDFLARE_TURNSTILE:
                sr = await solver.solve_turnstile(None, url, page)
            else:
                logger.warning("[CaptchaGate] Unhandled type: %s — attempting HITL", result.type.value)
                await self._hitl_alert(f"Captcha type {result.type.value} on {url} — manual solve needed")
                return False

            if sr.success:
                logger.info("[CaptchaGate] Solved via %s", sr.strategy)
                return True
            else:
                logger.warning("[CaptchaGate] Solve failed (%s): %s", sr.strategy, sr.error)
                await self._hitl_alert(f"Captcha solve failed ({sr.strategy}) on {url}: {sr.error}")
                return False

        except ImportError:
            logger.warning("[CaptchaGate] murphy_captcha_solver unavailable — attempting HITL")
            await self._hitl_alert(f"CAPTCHA on {page.url} — murphy_captcha_solver not loaded")
            return False
        except Exception as e:
            logger.error("[CaptchaGate] Exception: %s", e)
            return False

    # ── IMAP ───────────────────────────────────────────────────────────────────

    def _poll_imap(
        self,
        subject_pattern: str,
        sender_pattern:  str = "",
        timeout:         int = 300,
        poll_interval:   int = 10,
    ) -> Optional[str]:
        """
        Poll IMAP inbox for matching email. Returns full body or None.
        Checks ALL messages (not just UNSEEN) to handle timing edge cases.
        """
        deadline = time.time() + timeout
        logger.info("[IMAP] Polling for '%s' (timeout=%ds)", subject_pattern, timeout)
        while time.time() < deadline:
            try:
                with imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT) as imap:
                    imap.login(IMAP_USER, IMAP_PASS)
                    imap.select("INBOX")
                    _, data = imap.search(None, "ALL")
                    ids = data[0].split()
                    for num in reversed(ids[-20:]):   # last 20 messages
                        _, msg_data = imap.fetch(num, "(RFC822)")
                        msg  = email_lib.message_from_bytes(msg_data[0][1])
                        subj = msg.get("Subject", "")
                        frm  = msg.get("From", "")
                        match_subj = re.search(subject_pattern, subj, re.I)
                        match_from = (not sender_pattern) or re.search(sender_pattern, frm, re.I)
                        if match_subj and match_from:
                            logger.info("[IMAP] Found: %s", subj)
                            return self._extract_body(msg)
            except Exception as e:
                logger.debug("[IMAP] Poll error: %s", e)
            time.sleep(poll_interval)
        logger.warning("[IMAP] Timeout waiting for '%s'", subject_pattern)
        return None

    def _extract_body(self, msg) -> str:
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() in ("text/plain", "text/html"):
                    try:
                        body += part.get_payload(decode=True).decode(errors="replace")
                    except Exception:
                        pass
        else:
            try:
                body = msg.get_payload(decode=True).decode(errors="replace")
            except Exception:
                body = str(msg.get_payload())
        return body

    def _extract_link(self, body: str, patterns: Optional[List[str]] = None) -> Optional[str]:
        """Extract first URL matching any of the given regex patterns from email body."""
        default_patterns = [
            r"https://[\w./%-]+(?:verify|confirm|activate|email)[^\s\"'<>]+",
            r"href=[\"'](https://[^\"']+(?:verify|confirm|activate|token|auth)[^\"']+)[\"']",
        ]
        for pat in (patterns or default_patterns):
            m = re.search(pat, body, re.I)
            if m:
                url = m.group(1) if m.lastindex else m.group(0)
                logger.info("[IMAP] Extracted link: %s...", url[:60])
                return url
        return None

    # ── Credential store ───────────────────────────────────────────────────────

    def _store(self, integration: str, credential: str):
        """Store key in Murphy credential vault (hot — no restart needed)."""
        try:
            data = json.dumps({"integration": integration, "credential": credential}).encode()
            req = urllib.request.Request(
                f"{MURPHY_API}/api/credentials/store",
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "X-API-Key": FOUNDER_KEY,
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as r:
                resp = json.loads(r.read())
                logger.info("[Vault] Stored %s: %s", integration, resp)
        except Exception as e:
            logger.warning("[Vault] Could not store %s: %s — falling back to env file", integration, e)
            self._write_env(integration.upper() + "_API_KEY", credential)

    def _write_env(self, key: str, value: str):
        """Directly write to env file as fallback."""
        try:
            with open(ENV_FILE, "r") as f:
                content = f.read()
            if f"{key}=" in content:
                content = re.sub(rf"^{key}=.*$", f"{key}={value}", content, flags=re.MULTILINE)
            else:
                content += f"\n{key}={value}\n"
            with open(ENV_FILE, "w") as f:
                f.write(content)
            os.environ[key] = value
            logger.info("[Env] Set %s", key)
        except Exception as e:
            logger.error("[Env] Could not write %s: %s", key, e)

    # ── HITL alert ─────────────────────────────────────────────────────────────

    async def _hitl_alert(self, message: str):
        """Send Matrix HITL alert for manual intervention."""
        try:
            from matrix_client import send_hitl_alert
            await send_hitl_alert(f"[GhostRunner/{self.PROVIDER}] {message}")
        except Exception as e:
            logger.warning("[HITL] Matrix alert failed: %s", e)

    # ── Entry point ────────────────────────────────────────────────────────────

    async def run(self) -> RunResult:
        pw = browser = ctx = page = None
        try:
            pw, browser, ctx, page = await self._launch()
            result = await self._run(page)
            return result
        except Exception as e:
            logger.error("[%s] Unhandled exception: %s", self.PROVIDER, e, exc_info=True)
            return RunResult(provider=self.PROVIDER, success=False, error=str(e))
        finally:
            if browser:
                try:
                    await browser.close()
                except Exception:
                    pass
            if pw:
                try:
                    await pw.stop()
                except Exception:
                    pass

    async def _run(self, page) -> RunResult:
        raise NotImplementedError


# ══════════════════════════════════════════════════════════════════════════════
# PROVIDER: STRIPE
# ══════════════════════════════════════════════════════════════════════════════

class StripeRunner(BaseProviderRunner):
    PROVIDER = "stripe"

    async def _run(self, page) -> RunResult:
        from playwright.async_api import TimeoutError as PWTimeout

        logger.info("[Stripe] Navigating to register page")
        await page.goto("https://dashboard.stripe.com/register", timeout=30000)
        await asyncio.sleep(random.uniform(2, 4))

        # Fill form via React native setter
        await page.evaluate("""
            ([em, nm, pw]) => {
                function fill(el, val) {
                    if (!el) return;
                    var s = Object.getOwnPropertyDescriptor(
                        window.HTMLInputElement.prototype, 'value').set;
                    s.call(el, val);
                    el.dispatchEvent(new Event('input',  {bubbles:true}));
                    el.dispatchEvent(new Event('change', {bubbles:true}));
                }
                fill(document.getElementById('register-email-input'),    em);
                fill(document.getElementById('register-name-input'),     nm);
                fill(document.getElementById('register-password-input'), pw);
            }
        """, [self.email, "Murphy Systems", self.password])
        await asyncio.sleep(random.uniform(1, 2))

        # Solve captcha if present
        await self._solve_captcha(page)
        await asyncio.sleep(1)

        # Submit
        await page.evaluate("""
            () => {
                const btn = document.querySelector('button[type="submit"]');
                if (btn) btn.click();
            }
        """)
        logger.info("[Stripe] Form submitted — waiting for redirect or verification step")

        # Wait: either email verification prompt or dashboard
        await asyncio.sleep(5)
        current_url = page.url
        logger.info("[Stripe] Post-submit URL: %s", current_url)

        # Handle email verification
        if "verify" in current_url or "email" in current_url or "register" in current_url:
            logger.info("[Stripe] Email verification required — polling IMAP")
            body = self._poll_imap(
                subject_pattern=r"stripe|verify|confirm",
                sender_pattern=r"stripe\.com",
                timeout=300,
            )
            if not body:
                return RunResult(
                    provider=self.PROVIDER, success=False,
                    error="No verification email received (check MX record)"
                )
            link = self._extract_link(body)
            if not link:
                return RunResult(
                    provider=self.PROVIDER, success=False,
                    error="Could not extract verification link from email"
                )
            logger.info("[Stripe] Clicking verification link")
            await page.goto(link, timeout=30000)
            await asyncio.sleep(3)

        # Navigate to API keys page
        logger.info("[Stripe] Navigating to /apikeys")
        await page.goto("https://dashboard.stripe.com/apikeys", timeout=30000)
        await asyncio.sleep(3)

        # Extract keys
        keys = await self._extract_stripe_keys(page)
        if not keys:
            return RunResult(
                provider=self.PROVIDER, success=False,
                error="Could not extract Stripe API keys from dashboard"
            )

        # Store all found keys
        sk = keys.get("secret_key_test") or keys.get("secret_key_live", "")
        pk = keys.get("publishable_key_test") or keys.get("publishable_key_live", "")
        if sk:
            self._store("stripe", sk)
        if pk:
            self._write_env("STRIPE_PUBLISHABLE_KEY", pk)

        logger.info("[Stripe] ✅ Success. Keys extracted: %s", list(keys.keys()))
        return RunResult(provider=self.PROVIDER, success=True, keys=keys, strategy="playwright+captcha")

    async def _extract_stripe_keys(self, page) -> Dict[str, str]:
        keys = {}
        # Try to reveal hidden keys first
        await page.evaluate("""
            () => {
                document.querySelectorAll('button').forEach(b => {
                    if (/reveal|show|copy/i.test(b.textContent)) b.click();
                });
            }
        """)
        await asyncio.sleep(2)
        html = await page.evaluate("document.documentElement.innerText")
        for pat, name in [
            (r"sk_test_[A-Za-z0-9]{20,}", "secret_key_test"),
            (r"sk_live_[A-Za-z0-9]{20,}", "secret_key_live"),
            (r"pk_test_[A-Za-z0-9]{20,}", "publishable_key_test"),
            (r"pk_live_[A-Za-z0-9]{20,}", "publishable_key_live"),
        ]:
            m = re.search(pat, html)
            if m:
                keys[name] = m.group(0)
        return keys


# ══════════════════════════════════════════════════════════════════════════════
# PROVIDER: SENDGRID
# ══════════════════════════════════════════════════════════════════════════════

class SendGridRunner(BaseProviderRunner):
    PROVIDER = "sendgrid"

    async def _run(self, page) -> RunResult:
        logger.info("[SendGrid] Navigating to signup")
        await page.goto("https://signup.sendgrid.com/", timeout=30000)
        await asyncio.sleep(random.uniform(2, 4))

        # Fill form
        await self._human_type(page, "input[name='email']",            self.email)
        await self._human_type(page, "input[name='password']",         self.password)
        await self._human_type(page, "input[name='first_name']",       "Murphy")
        await self._human_type(page, "input[name='last_name']",        "Systems")
        await self._human_type(page, "input[name='company']",          "Murphy Systems LLC")

        # Try phone field if present
        try:
            ph_el = await page.query_selector("input[name='phone']")
            if ph_el:
                await self._human_type(page, "input[name='phone']", "+14155551234")
        except Exception:
            pass

        await self._solve_captcha(page)
        await asyncio.sleep(1)

        # Submit
        await page.click("button[type='submit']", timeout=8000)
        logger.info("[SendGrid] Form submitted")
        await asyncio.sleep(5)

        # Email verification
        body = self._poll_imap(
            subject_pattern=r"sendgrid|verify|confirm|welcome",
            sender_pattern=r"sendgrid\.com|twilio\.com",
            timeout=300,
        )
        if body:
            link = self._extract_link(body)
            if link:
                await page.goto(link, timeout=30000)
                await asyncio.sleep(3)

        # Navigate to API keys
        await page.goto("https://app.sendgrid.com/settings/api_keys", timeout=30000)
        await asyncio.sleep(3)

        # Create API key if none visible
        html = await page.evaluate("document.documentElement.innerText")
        key_match = re.search(r"SG\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}", html)
        if not key_match:
            # Click "Create API Key"
            await page.evaluate("""
                () => {
                    document.querySelectorAll('button,a').forEach(el => {
                        if (/create api key/i.test(el.textContent)) el.click();
                    });
                }
            """)
            await asyncio.sleep(2)
            await self._human_type(page, "input[name='name']", "Murphy-Production")
            await page.evaluate("""
                () => {
                    document.querySelectorAll('button').forEach(b => {
                        if (/create|save/i.test(b.textContent)) b.click();
                    });
                }
            """)
            await asyncio.sleep(3)
            html = await page.evaluate("document.documentElement.innerText")
            key_match = re.search(r"SG\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}", html)

        if not key_match:
            return RunResult(provider=self.PROVIDER, success=False, error="Could not extract SendGrid API key")

        api_key = key_match.group(0)
        self._store("sendgrid", api_key)
        logger.info("[SendGrid] ✅ Key extracted and stored")
        return RunResult(
            provider=self.PROVIDER, success=True,
            keys={"SENDGRID_API_KEY": api_key}, strategy="playwright+captcha"
        )


# ══════════════════════════════════════════════════════════════════════════════
# PROVIDER: DEEPINFRA
# ══════════════════════════════════════════════════════════════════════════════

class DeepInfraRunner(BaseProviderRunner):
    PROVIDER = "deepinfra"

    async def _run(self, page) -> RunResult:
        logger.info("[DeepInfra] Navigating to signup")
        await page.goto("https://deepinfra.com/dash/sign_up", timeout=30000)
        await asyncio.sleep(random.uniform(2, 4))

        # Try Google OAuth (skip form filling)
        google_btn = await page.query_selector("button[data-provider='google'], a[href*='google']")
        if not google_btn:
            # Regular form
            await self._human_type(page, "input[type='email']",    self.email)
            await self._human_type(page, "input[type='password']", self.password)
            await self._solve_captcha(page)
            await page.click("button[type='submit']", timeout=8000)
            await asyncio.sleep(5)

        # Navigate to API token page
        await page.goto("https://deepinfra.com/dash/api_keys", timeout=30000)
        await asyncio.sleep(2)

        html = await page.evaluate("document.documentElement.innerText")
        token_match = re.search(r"[A-Za-z0-9]{20,}", html)   # DeepInfra tokens are opaque strings
        if not token_match:
            # Try generating one
            await page.evaluate("""
                () => {
                    document.querySelectorAll('button').forEach(b => {
                        if (/create|generate|new/i.test(b.textContent)) b.click();
                    });
                }
            """)
            await asyncio.sleep(2)
            html = await page.evaluate("document.documentElement.innerText")
            # Look for the specific token pattern after generation
            # DeepInfra tokens shown once — scan for long opaque strings
            candidates = re.findall(r"[A-Za-z0-9]{32,}", html)
            if candidates:
                api_key = candidates[0]
                self._store("deepinfra", api_key)
                return RunResult(
                    provider=self.PROVIDER, success=True,
                    keys={"DEEPINFRA_API_KEY": api_key}, strategy="playwright"
                )
            return RunResult(provider=self.PROVIDER, success=False, error="Could not extract DeepInfra token")

        api_key = token_match.group(0)
        self._store("deepinfra", api_key)
        return RunResult(
            provider=self.PROVIDER, success=True,
            keys={"DEEPINFRA_API_KEY": api_key}, strategy="playwright"
        )


# ══════════════════════════════════════════════════════════════════════════════
# PROVIDER: TOGETHER AI
# ══════════════════════════════════════════════════════════════════════════════

class TogetherRunner(BaseProviderRunner):
    PROVIDER = "together"

    async def _run(self, page) -> RunResult:
        logger.info("[Together] Navigating to signup")
        await page.goto("https://api.together.xyz/signup", timeout=30000)
        await asyncio.sleep(random.uniform(2, 4))

        await self._human_type(page, "input[name='email'], input[type='email']", self.email)
        await self._human_type(page, "input[name='password'], input[type='password']", self.password)
        await self._solve_captcha(page)

        await page.evaluate("""
            () => {
                const btn = document.querySelector("button[type='submit']");
                if (btn) btn.click();
            }
        """)
        await asyncio.sleep(5)

        # Email verification
        body = self._poll_imap(
            subject_pattern=r"together|verify|confirm|welcome",
            timeout=240,
        )
        if body:
            link = self._extract_link(body)
            if link:
                await page.goto(link, timeout=30000)
                await asyncio.sleep(3)

        # API keys page
        for api_url in [
            "https://api.together.xyz/settings/api-keys",
            "https://api.together.xyz/account",
        ]:
            await page.goto(api_url, timeout=30000)
            await asyncio.sleep(2)
            html = await page.evaluate("document.documentElement.innerText")
            # Together API keys look like: long hex or base64 strings
            m = re.search(r"[a-f0-9]{64}", html) or re.search(r"[A-Za-z0-9+/]{40,}={0,2}", html)
            if m:
                api_key = m.group(0)
                self._store("together", api_key)
                return RunResult(
                    provider=self.PROVIDER, success=True,
                    keys={"TOGETHER_API_KEY": api_key}, strategy="playwright"
                )

        return RunResult(provider=self.PROVIDER, success=False, error="Could not extract Together API key")


# ══════════════════════════════════════════════════════════════════════════════
# PROVIDER: OPENWEATHER
# ══════════════════════════════════════════════════════════════════════════════

class OpenWeatherRunner(BaseProviderRunner):
    PROVIDER = "openweather"

    async def _run(self, page) -> RunResult:
        logger.info("[OpenWeather] Navigating to signup")
        await page.goto("https://home.openweathermap.org/users/sign_up", timeout=30000)
        await asyncio.sleep(random.uniform(2, 4))

        await self._human_type(page, "input#user_username",           "MurphySystems")
        await self._human_type(page, "input#user_email",              self.email)
        await self._human_type(page, "input#user_password",           self.password)
        await self._human_type(page, "input#user_password_confirmation", self.password)

        # Check required checkboxes
        await page.evaluate("""
            () => {
                document.querySelectorAll('input[type=checkbox]').forEach(cb => {
                    if (!cb.checked) cb.click();
                });
            }
        """)
        await self._solve_captcha(page)
        await page.click("input[type='submit'], button[type='submit']", timeout=8000)
        await asyncio.sleep(5)

        # Email verification
        body = self._poll_imap(subject_pattern=r"openweather|confirm|verify", timeout=240)
        if body:
            link = self._extract_link(body)
            if link:
                await page.goto(link, timeout=30000)
                await asyncio.sleep(2)

        # API keys
        await page.goto("https://home.openweathermap.org/api_keys", timeout=30000)
        await asyncio.sleep(2)
        html = await page.evaluate("document.documentElement.innerText")
        m = re.search(r"[a-f0-9]{32}", html)
        if not m:
            return RunResult(provider=self.PROVIDER, success=False, error="No API key found")
        api_key = m.group(0)
        self._store("openweather", api_key)
        return RunResult(
            provider=self.PROVIDER, success=True,
            keys={"OPENWEATHER_API_KEY": api_key}, strategy="playwright"
        )


# ══════════════════════════════════════════════════════════════════════════════
# PROVIDER REGISTRY
# ══════════════════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════════════════
# LINKEDIN RUNNER — PATCH-175
# ══════════════════════════════════════════════════════════════════════════════

class LinkedInRunner(BaseProviderRunner):
    """
    Logs into LinkedIn with personal account, then creates Murphy Systems
    company page.
    PATCH-175
    """
    PROVIDER = "linkedin"

    LI_EMAIL    = "Corey.gfc@gmail.com"
    LI_PASSWORD = "Sputnik12!"

    COMPANY = {
        "name":       "Murphy Systems",
        "url_slug":   "murphy-systems-ai",
        "website":    "https://murphy.systems",
        "industry":   "Technology, Information and Internet",
        "size":       "1-10",
        "type":       "Privately Held",
        "tagline":    "What can go wrong, will go wrong. We shield you from it.",
        "description": (
            "Murphy Systems is an AI-native platform that anticipates, names, "
            "and shields against every failure AI can cause. Powered by a 9-agent "
            "swarm, Shield Wall protection, and the Murphy North Star."
        ),
    }


    def _poll_gmail(self, timeout: int = 180, poll_interval: int = 10) -> Optional[str]:
        """
        PATCH-175a: Poll Gmail API for LinkedIn verification PIN.
        Uses OAuth token stored in env GMAIL_OAUTH_TOKEN.
        Returns email body text or None on timeout.
        """
        import json as _json, time as _time, urllib.request as _ur
        token = os.environ.get("GMAIL_OAUTH_TOKEN", "")
        if not token:
            logger.warning("[LinkedInGmail] GMAIL_OAUTH_TOKEN not set — falling back to IMAP")
            return self._poll_imap(subject_pattern=r"linkedin|security|verification|PIN", timeout=timeout)

        deadline = _time.time() + timeout
        logger.info("[LinkedInGmail] Polling Gmail for LinkedIn PIN (timeout=%ds)", timeout)

        seen_ids: set = set()
        while _time.time() < deadline:
            try:
                req = _ur.Request(
                    "https://gmail.googleapis.com/gmail/v1/users/me/messages"
                    "?q=from:linkedin+subject:PIN&maxResults=5",
                    headers={"Authorization": f"Bearer {token}"}
                )
                with _ur.urlopen(req, timeout=10) as r:
                    data = _json.loads(r.read())
                for msg in data.get("messages", []):
                    mid = msg["id"]
                    if mid in seen_ids:
                        continue
                    seen_ids.add(mid)
                    # Fetch full message
                    req2 = _ur.Request(
                        f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{mid}?format=full",
                        headers={"Authorization": f"Bearer {token}"}
                    )
                    with _ur.urlopen(req2, timeout=10) as r2:
                        mdata = _json.loads(r2.read())
                    # Decode body
                    import base64 as _b64
                    def _get_body(p):
                        if p.get("body", {}).get("data"):
                            return _b64.urlsafe_b64decode(p["body"]["data"]).decode("utf-8", "ignore")
                        for part in p.get("parts", []):
                            t = _get_body(part)
                            if t:
                                return t
                        return ""
                    body = _get_body(mdata["payload"])
                    # Check it has a 6-digit code
                    m = re.search(r"\b(\d{6})\b", body)
                    if m:
                        logger.info("[LinkedInGmail] Found PIN: %s", m.group(1))
                        return body
            except Exception as e:
                logger.debug("[LinkedInGmail] Poll error: %s", e)
            _time.sleep(poll_interval)

        logger.warning("[LinkedInGmail] Timeout — no LinkedIn PIN email found in Gmail")
        return None


    async def _run(self, page) -> RunResult:
        import asyncio, random, re

        logger.info("[LinkedIn] Step 1: Navigate to login")
        # Use slow approach — appear human before login page even loads
        await page.goto("https://www.linkedin.com/", timeout=30000)
        await asyncio.sleep(random.uniform(3, 6))
        await page.mouse.move(random.randint(200,800), random.randint(100,500))
        await asyncio.sleep(random.uniform(1, 2))

        await page.goto("https://www.linkedin.com/login", timeout=30000)
        await asyncio.sleep(random.uniform(3, 5))

        logger.info("[LinkedIn] Step 2: Fill credentials")
        await self._human_type(page, "input[type='email']", self.LI_EMAIL)
        await asyncio.sleep(random.uniform(0.8, 1.5))
        await self._human_type(page, "input[type='password']", self.LI_PASSWORD)
        await asyncio.sleep(random.uniform(0.5, 1.0))

        # Human-like mouse movement before click
        await page.mouse.move(random.randint(300, 600), random.randint(350, 450))
        await asyncio.sleep(random.uniform(0.3, 0.7))
        await page.locator("button[type=submit]").first.click(timeout=8000)
        await asyncio.sleep(random.uniform(5, 9))

        url = page.url
        html = await page.evaluate("document.documentElement.innerText")
        logger.info("[LinkedIn] Post-login URL: %s", url)

        # Handle checkpoint / verification code sent to email
        if "checkpoint" in url or "challenge" in url or "verification" in url:
            logger.info("[LinkedIn] Checkpoint detected — checking for email verification code")
            # Poll IMAP for LinkedIn verification email
            body = self._poll_gmail(timeout=120)
            if body:
                # Extract 6-digit code
                code_match = re.search(r"\b(\d{6})\b", body)
                if code_match:
                    code = code_match.group(1)
                    logger.info("[LinkedIn] Got verification code: %s", code)
                    try:
                        await self._human_type(page, "input[name='pin'], input[id*='pin'], input[type='number'], input[autocomplete*='one-time']", code)
                        await asyncio.sleep(1)
                        await page.click("button[type=submit]", timeout=5000)
                        await asyncio.sleep(4)
                        url = page.url
                    except Exception as e:
                        logger.warning("[LinkedIn] Could not enter verification code: %s", e)
                else:
                    logger.warning("[LinkedIn] No 6-digit code found in email body")
            else:
                logger.warning("[LinkedIn] No verification email received within timeout")

        # Final check — are we logged in?
        url = page.url
        if "feed" not in url and "mynetwork" not in url and "in/" not in url:
            if "login" in url or "checkpoint" in url:
                return RunResult(
                    provider=self.PROVIDER, success=False,
                    error=f"Login blocked — URL: {url}"
                )

        logger.info("[LinkedIn] Logged in. URL: %s", url)
        # PATCH-175a: Extract li_at cookie and store it
        try:
            cookies = await page.context.cookies()
            li_at = next((c["value"] for c in cookies if c["name"] == "li_at"), None)
            if li_at:
                logger.info("[LinkedIn] Extracted li_at cookie (len=%d)", len(li_at))
                self._store_credential("LINKEDIN_SESSION_COOKIE", li_at)
                # Also write to secrets.env
                env_line = f"\nLINKEDIN_LI_AT={li_at}\n"
                try:
                    with open("/etc/murphy-production/secrets.env", "a") as _ef:
                        _ef.write(env_line)
                    logger.info("[LinkedIn] li_at written to secrets.env")
                except Exception as _ce:
                    logger.warning("[LinkedIn] Could not write to secrets.env: %s", _ce)
        except Exception as _ce:
            logger.warning("[LinkedIn] Cookie extraction failed: %s", _ce)
        logger.info("[LinkedIn] Step 3: Create company page")
        await page.goto("https://www.linkedin.com/login", timeout=30000)
        await asyncio.sleep(random.uniform(2, 4))

        await self._human_type(page, "input[type='email']", self.LI_EMAIL)
        await asyncio.sleep(random.uniform(0.4, 0.9))
        await self._human_type(page, "input[type='password']", self.LI_PASSWORD)
        await asyncio.sleep(random.uniform(0.3, 0.7))
        await page.locator("button[type=submit]").first.click(timeout=8000)
        await asyncio.sleep(random.uniform(4, 7))

        # Handle checkpoint / verification
        url = page.url
        if "checkpoint" in url or "challenge" in url or "verification" in url:
            logger.warning("[LinkedIn] Hit checkpoint — may need HITL")
            await self._solve_captcha(page)
            await asyncio.sleep(3)

        # Confirm logged in
        html = await page.evaluate("document.documentElement.innerText")
        if "feed" not in page.url and "Sign in" in html:
            return RunResult(
                provider=self.PROVIDER, success=False,
                error="Login failed — still on login page"
            )

        logger.info("[LinkedIn] Step 2: Navigate to company page creation")
        await page.goto("https://www.linkedin.com/company/setup/new/", timeout=30000)
        await asyncio.sleep(random.uniform(3, 5))

        # Select company type — Small Business
        try:
            await page.click("div[data-test-id='small-business'], "
                             "button:has-text('Small business'), "
                             "label:has-text('Small business')", timeout=8000)
            await asyncio.sleep(1)
        except Exception:
            logger.warning("[LinkedIn] Could not click Small Business tile — trying next")

        # Company name
        await self._wait_selector(page, "input[name='localizedName'], input[id*='name']", 15000)
        try:
            await self._human_type(page, "input[name='localizedName']", self.COMPANY["name"])
        except Exception:
            await self._human_type(page, "input[id*='name']", self.COMPANY["name"])
        await asyncio.sleep(random.uniform(0.5, 1))

        # URL slug
        try:
            slug_sel = "input[name='vanityName'], input[id*='vanity'], input[id*='url']"
            await self._wait_selector(page, slug_sel, 5000)
            slug_field = await page.query_selector(slug_sel)
            if slug_field:
                await slug_field.triple_click()
                await asyncio.sleep(0.3)
                await self._human_type(page, slug_sel, self.COMPANY["url_slug"])
        except Exception:
            logger.warning("[LinkedIn] Could not set URL slug — continuing")

        # Website
        try:
            await self._human_type(page, "input[name='websiteUrl'], input[id*='website']",
                                   self.COMPANY["website"])
        except Exception:
            logger.warning("[LinkedIn] Could not set website — continuing")

        # Industry
        try:
            ind_sel = "input[id*='industry'], input[placeholder*='ndustry']"
            await self._wait_selector(page, ind_sel, 5000)
            await self._human_type(page, ind_sel, "Technology")
            await asyncio.sleep(1.5)
            await page.click("div[role=option]:first-child, li[role=option]:first-child",
                             timeout=5000)
        except Exception:
            logger.warning("[LinkedIn] Could not set industry — continuing")

        # Company size
        try:
            await page.select_option("select[name*='size'], select[id*='size']",
                                     label="1-10 employees", timeout=5000)
        except Exception:
            try:
                await page.click("label:has-text('1-10')", timeout=5000)
            except Exception:
                logger.warning("[LinkedIn] Could not set size — continuing")

        # Company type
        try:
            await page.select_option("select[name*='type'], select[id*='type']",
                                     label="Privately Held", timeout=5000)
        except Exception:
            logger.warning("[LinkedIn] Could not set type — continuing")

        await asyncio.sleep(random.uniform(1, 2))

        # Check terms checkbox if present
        try:
            await page.evaluate("""
                () => {
                    const cb = document.querySelector('input[type=checkbox]');
                    if (cb && !cb.checked) cb.click();
                }
            """)
        except Exception:
            pass

        # Submit
        try:
            await page.click(
                "button[type=submit], button:has-text('Create page'), "
                "button:has-text('Continue')", timeout=8000)
            await asyncio.sleep(random.uniform(4, 6))
        except Exception as e:
            return RunResult(provider=self.PROVIDER, success=False,
                             error=f"Could not click submit: {e}")

        # Check result
        url = page.url
        logger.info("[LinkedIn] Post-submit URL: %s", url)

        if "company" in url or "admin" in url:
            # Add description / tagline if we land on the page
            try:
                await page.goto(url + "/edit/about/", timeout=20000)
                await asyncio.sleep(2)
                try:
                    tl_sel = "input[name*='tagline'], textarea[name*='tagline']"
                    await self._human_type(page, tl_sel, self.COMPANY["tagline"])
                except Exception:
                    pass
                try:
                    desc_sel = "textarea[name*='description'], textarea[id*='description']"
                    await self._human_type(page, desc_sel, self.COMPANY["description"])
                except Exception:
                    pass
                try:
                    await page.click("button[type=submit]", timeout=5000)
                    await asyncio.sleep(2)
                except Exception:
                    pass
            except Exception:
                logger.warning("[LinkedIn] Could not add tagline/description — continuing")

            self._store("LINKEDIN_COMPANY_URL", url)
            return RunResult(
                provider=self.PROVIDER, success=True,
                keys={"LINKEDIN_COMPANY_URL": url},
                strategy="playwright"
            )
        else:
            # Capture HTML for diagnosis
            html_snippet = await page.evaluate(
                "document.documentElement.innerText"
            )
            return RunResult(
                provider=self.PROVIDER, success=False,
                error=f"Unexpected post-submit URL: {url} | "
                      f"Page snippet: {html_snippet[:300]}"
            )

PROVIDERS: Dict[str, type] = {
    "stripe":       StripeRunner,
    "sendgrid":     SendGridRunner,
    "deepinfra":    DeepInfraRunner,
    "together":     TogetherRunner,
    "openweather":  OpenWeatherRunner,
    "linkedin":     LinkedInRunner,
}


# ══════════════════════════════════════════════════════════════════════════════
# ORCHESTRATOR — callable from service or CLI
# ══════════════════════════════════════════════════════════════════════════════

async def run_provider(provider: str) -> RunResult:
    _init_file_logging()
    """
    Main entry point. Called by:
      - CLI:     python3 ghost_runner.py --provider stripe
      - Service: POST /api/ghost-runner/run {"provider": "stripe"}
      - Automation: GhostRunnerScheduler
    """
    if provider not in PROVIDERS:
        return RunResult(
            provider=provider, success=False,
            error=f"Unknown provider '{provider}'. Available: {', '.join(PROVIDERS)}"
        )
    logger.info("[GhostRunner] Starting provider: %s", provider)
    runner = PROVIDERS[provider]()
    result = await runner.run()
    get_db().record(result)
    logger.info(
        "[GhostRunner] %s → %s | keys=%s | error=%s",
        provider, "✅ SUCCESS" if result.success else "❌ FAIL",
        list(result.keys.keys()), result.error
    )
    return result


def run_provider_sync(provider: str) -> RunResult:
    """Synchronous wrapper for non-async callers."""
    return asyncio.run(run_provider(provider))


# ══════════════════════════════════════════════════════════════════════════════
# FASTAPI ROUTER — plugs into Murphy's existing API
# ══════════════════════════════════════════════════════════════════════════════

def create_ghost_runner_router():
    """
    Mounts at /api/ghost-runner/
    POST /api/ghost-runner/run        {"provider": "stripe"}
    GET  /api/ghost-runner/status
    GET  /api/ghost-runner/result/{provider}
    GET  /api/ghost-runner/history
    GET  /api/ghost-runner/providers
    """
    from fastapi import APIRouter, BackgroundTasks, HTTPException
    from pydantic import BaseModel

    router = APIRouter(prefix="/api/ghost-runner", tags=["ghost-runner"])

    class RunRequest(BaseModel):
        provider: str

    # Run in a background process — don't block the event loop with browser
    _active_runs: Dict[str, str] = {}   # provider → "running" | "idle"

    @router.post("/run")
    async def run_endpoint(req: RunRequest, background_tasks: BackgroundTasks):
        provider = req.provider.lower()
        if provider not in PROVIDERS:
            raise HTTPException(400, f"Unknown provider: {provider}")
        if _active_runs.get(provider) == "running":
            return {"status": "already_running", "provider": provider}

        _active_runs[provider] = "running"

        async def _bg():
            try:
                await run_provider(provider)
            finally:
                _active_runs[provider] = "idle"

        background_tasks.add_task(_bg)
        return {"status": "started", "provider": provider}

    @router.get("/status")
    def status():
        return {
            "active_runs": dict(_active_runs),
            "providers":   list(PROVIDERS.keys()),
            "chromium":    CHROMIUM_BIN,
        }

    @router.get("/result/{provider}")
    def last_result(provider: str):
        r = get_db().last_result(provider)
        if not r:
            raise HTTPException(404, f"No run recorded for provider: {provider}")
        return r

    @router.get("/history")
    def history():
        return get_db().all_runs(limit=100)

    @router.get("/providers")
    def list_providers():
        return {"providers": list(PROVIDERS.keys())}

    return router


# ══════════════════════════════════════════════════════════════════════════════
# CLI ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Murphy Ghost Runner — autonomous API key acquisition")
    parser.add_argument("--provider", "-p", help="Provider to run (stripe, sendgrid, ...)")
    parser.add_argument("list", nargs="?", help="List available providers")
    args = parser.parse_args()

    if args.list == "list" or (not args.provider):
        print("Available providers:")
        for name in PROVIDERS:
            print(f"  {name}")
        return

    result = run_provider_sync(args.provider)
    print(json.dumps({
        "provider": result.provider,
        "success":  result.success,
        "keys":     {k: v[:12] + "..." for k, v in result.keys.items()},
        "strategy": result.strategy,
        "error":    result.error,
    }, indent=2))
    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    main()
