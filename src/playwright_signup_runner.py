"""
Playwright Signup Runner — playwright_signup_runner.py
PATCH-154

Autonomous browser-based account creation and API key extraction.
Uses Playwright + Chromium (already installed) with:
  - Human-like navigator fingerprint patching
  - CaptchaEngine integration (audio solve via Whisper)
  - IMAP email verification
  - Dashboard scraping for API keys

Copyright © 2020-2026 Inoni LLC — Created by Corey Post
PATCH-154 | Label: MCB-PLAYWRIGHT-001
License: BSL 1.1
"""
from __future__ import annotations
import os as _os
_os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "/opt/Murphy-System/.cache/ms-playwright")

import asyncio
import imaplib
import email as email_lib
import logging
import os
import random
import re
import time
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Tuple

logger = logging.getLogger(__name__)

# ── Navigator patch script ─────────────────────────────────────────────────────
# Makes Playwright Chromium look like a real user browser
STEALTH_JS = """
() => {
    // Remove headless signals
    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
    Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
    Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
    Object.defineProperty(navigator, 'platform', {get: () => 'Win32'});
    // Chrome runtime
    window.chrome = {runtime: {}, loadTimes: function(){}, csi: function(){}, app: {}};
    // Permissions
    const originalQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = (parameters) => (
        parameters.name === 'notifications' ?
        Promise.resolve({ state: Notification.permission }) :
        originalQuery(parameters)
    );
}
"""

REAL_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


@dataclass
class SignupResult:
    success: bool
    provider: str
    api_key: Optional[str] = None
    extra_keys: Dict[str, str] = field(default_factory=dict)
    error: Optional[str] = None
    strategy_used: str = ""


class PlaywrightSignupRunner:
    """
    Autonomous signup + API key extraction using Playwright Chromium.

    Usage:
        runner = PlaywrightSignupRunner()
        result = await runner.run_stripe(email, password)
        if result.success:
            print(result.api_key)  # sk_test_...
    """

    def __init__(
        self,
        imap_host: str = "127.0.0.1",
        imap_port: int = 993,
        imap_user: str = "cpost@murphy.systems",
        imap_pass: str = "UIKTCUFJ2IMxX6oluBUfLZhgILjCVyeAMstPeRvteg0",
        headless: bool = True,
    ):
        self.imap_host = imap_host
        self.imap_port = imap_port
        self.imap_user = imap_user
        self.imap_pass = imap_pass
        self.headless = headless

    # ── Browser bootstrap ──────────────────────────────────────────────────────

    async def _launch(self):
        """Launch stealth Chromium. Returns (playwright, browser, context, page)."""
        from playwright.async_api import async_playwright
        pw = await async_playwright().start()
        browser = await pw.chromium.launch(
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--window-size=1280,800",
            ],
        )
        context = await browser.new_context(
            user_agent=REAL_UA,
            viewport={"width": 1280, "height": 800},
            locale="en-US",
            timezone_id="America/New_York",
        )
        await context.add_init_script(STEALTH_JS)
        page = await context.new_page()
        return pw, browser, context, page

    async def _human_type(self, page, selector: str, text: str):
        """Type with realistic per-character delays."""
        await page.click(selector)
        await asyncio.sleep(random.uniform(0.3, 0.8))
        for ch in text:
            await page.keyboard.type(ch)
            await asyncio.sleep(random.uniform(0.05, 0.18))

    async def _try_solve_captcha(self, page, html: str, url: str) -> bool:
        """Invoke CaptchaEngine if a captcha is detected. Returns True if solved."""
        try:
            from murphy_captcha import CaptchaEngine, CaptchaType
            engine = CaptchaEngine()
            result = await engine.handle(html, url, page)
            if result.detected:
                logger.info("[Runner] Captcha %s — resolved=%s strategy=%s notes=%s",
                            result.type.value, result.resolved,
                            result.strategy, result.notes)
                return result.resolved
            return True  # no captcha
        except Exception as e:
            logger.warning("[Runner] captcha engine error: %s", e)
            return False

    # ── IMAP helpers ───────────────────────────────────────────────────────────


    async def run_stripe_with_tempmail(
        self,
        company_name: str = "Murphy Systems",
        password: str = "Sputnik12!",
    ) -> "SignupResult":
        """
        Register Stripe using cpost@murphy.systems directly — our self-hosted
        mail server can receive the verification email via IMAP.
        PATCH-154c: No temp email needed — use canonical owner address.
        """
        logger.info("[Stripe] Using owner email for registration: cpost@murphy.systems")
        return await self.run_stripe(
            email="cpost@murphy.systems",
            company_name=company_name,
            password=password,
        )

    def _wait_for_email(
        self, subject_pattern: str, timeout: int = 300, poll: int = 10
    ) -> Optional[str]:
        """Poll IMAP inbox for an email matching subject_pattern. Returns body text."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                with imaplib.IMAP4_SSL(self.imap_host, self.imap_port) as imap:
                    imap.login(self.imap_user, self.imap_pass)
                    imap.select("INBOX")
                    _, data = imap.search(None, "UNSEEN")
                    for num in data[0].split():
                        _, msg_data = imap.fetch(num, "(RFC822)")
                        msg = email_lib.message_from_bytes(msg_data[0][1])
                        subj = msg.get("Subject", "")
                        if re.search(subject_pattern, subj, re.I):
                            body = self._extract_body(msg)
                            logger.info("[Runner] Email found: %s", subj)
                            return body
            except Exception as e:
                logger.debug("[Runner] IMAP poll error: %s", e)
            time.sleep(poll)
        return None

    def _extract_body(self, msg) -> str:
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                ct = part.get_content_type()
                if ct in ("text/plain", "text/html"):
                    body += part.get_payload(decode=True).decode(errors="replace")
        else:
            body = msg.get_payload(decode=True).decode(errors="replace")
        return body

    def _extract_verify_link(self, body: str) -> Optional[str]:
        """Extract first https link that looks like an email verification URL."""
        patterns = [
            r"https://[\w./-]+verify[\w./?=&%-]+",
            r"https://[\w./-]+confirm[\w./?=&%-]+",
            r"https://[\w./-]+activate[\w./?=&%-]+",
            r"https://[\w./-]+email[\w./?=&%-]+token[\w./?=&%-]+",
        ]
        for pat in patterns:
            m = re.search(pat, body)
            if m:
                return m.group(0)
        # Fallback: any link with "verify" or "confirm"
        m = re.search(r'href=["\'](https://[^"\']+(?:verify|confirm|activate)[^"\']+)["\'\s]', body, re.I)
        if m:
            return m.group(1)
        return None

    # ── Stripe ─────────────────────────────────────────────────────────────────

    async def run_stripe(
        self,
        email: str = "cpost@murphy.systems",
        company_name: str = "Murphy Systems",
        password: str = "Sputnik12!",
    ) -> SignupResult:
        """
        Full autonomous Stripe account creation + API key extraction.

        Steps:
          1. Navigate to dashboard.stripe.com/register
          2. Fill email, name, password with human timing
          3. Solve reCAPTCHA v2 via audio challenge + Whisper
          4. Wait for verification email via IMAP
          5. Click verify link in new tab
          6. Navigate to /apikeys and extract sk_test_ key
          7. Store via credential vault
        """
        pw = browser = context = page = None
        try:
            pw, browser, context, page = await self._launch()
            logger.info("[Stripe] Navigating to register page")
            await page.goto("https://dashboard.stripe.com/register", timeout=30000)
            await asyncio.sleep(random.uniform(2, 4))

            # Fill form with React-compatible value setting
            html = await page.content()

            # Use React native setter for controlled inputs
            await page.evaluate("""
                ([em, nm, pw]) => {
                    function setNativeValue(el, val) {
                        if (!el) return;
                        var setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                        setter.call(el, val);
                        el.dispatchEvent(new Event('input', {bubbles: true}));
                        el.dispatchEvent(new Event('change', {bubbles: true}));
                    }
                    setNativeValue(document.getElementById('register-email-input'), em);
                    setNativeValue(document.getElementById('register-name-input'), nm);
                    setNativeValue(document.getElementById('register-password-input-with-description'), pw);
                }
            """, [email, company_name, password])

            await asyncio.sleep(random.uniform(1.5, 3.0))

            # Handle captcha
            html = await page.content()
            url = page.url
            captcha_solved = await self._try_solve_captcha(page, html, url)
            if not captcha_solved:
                logger.warning("[Stripe] Captcha not solved — attempting submit anyway")

            # Submit form
            await page.click('button[type="submit"]')
            await asyncio.sleep(random.uniform(3, 6))

            # Check result
            current_url = page.url
            logger.info("[Stripe] Post-submit URL: %s", current_url)

            if "register" in current_url:
                # Still on register — check for errors
                error_text = await page.evaluate("""
                    () => {
                        var errs = document.querySelectorAll('[class*="error"], [class*="Error"]');
                        return Array.from(errs).map(e => e.textContent.trim()).join(' | ');
                    }
                """)
                if error_text:
                    logger.warning("[Stripe] Form errors: %s", error_text)
                    # Might be email already registered — try login instead
                    return await self._stripe_login_and_get_keys(page, context, email, password)

            # Wait for verification email — try IMAP first, then TempMail
            logger.info("[Stripe] Waiting for verification email...")
            body = None

            # IMAP path (works when MX record is configured)
            # PATCH-154c: cpost@murphy.systems is used for registration.
            # Our self-hosted IMAP will receive the Stripe verification email.
            # Give it a full 5 minutes — Stripe can be slow.
            logger.info("[Stripe] Polling IMAP (cpost@murphy.systems) for Stripe verification email...")
            try:
                body = self._wait_for_email(
                    subject_pattern=r"verify|confirm|stripe|email",
                    timeout=300,   # 5 minutes — real IMAP, not tempmail
                    poll=10,
                )
            except Exception as _imap_e:
                logger.warning("[Stripe] IMAP poll error: %s", _imap_e)
                body = None

            if body:
                # Extract all links and try each one that looks like a verify link
                import re as _re
                links = _re.findall(r'href=["\'](https?://[^"\' ]+)["\']', body)
                links += _re.findall(r'(https://stripe\.com/[^\s<>"\']+)', body)
                verify_link = next(
                    (l for l in links if any(k in l for k in ["verify", "confirm", "activate", "email"])),
                    None
                )
                if verify_link:
                    logger.info("[Stripe] Clicking verify link: %s", verify_link[:80])
                    verify_page = await context.new_page()
                    await verify_page.goto(verify_link, timeout=30000)
                    await asyncio.sleep(4)
                    await verify_page.close()
                else:
                    logger.warning("[Stripe] No verify link found in email body")
            else:
                logger.warning("[Stripe] No verification email received — proceeding anyway")

            # Now get API keys
            logger.info("[Stripe] Navigating to API keys page")
            await page.goto("https://dashboard.stripe.com/apikeys", timeout=30000)
            await asyncio.sleep(3)

            return await self._extract_stripe_keys(page)

        except Exception as e:
            logger.error("[Stripe] Signup runner error: %s", e, exc_info=True)
            return SignupResult(success=False, provider="stripe", error=str(e))
        finally:
            try:
                if browser:
                    await browser.close()
                if pw:
                    await pw.stop()
            except Exception:
                pass

    async def _stripe_login_and_get_keys(
        self, page, context, email: str, password: str
    ) -> SignupResult:
        """If account exists, log in and grab keys."""
        try:
            await page.goto("https://dashboard.stripe.com/login", timeout=30000)
            await asyncio.sleep(2)
            await page.evaluate("""
                function setNativeValue(el, val) {
                    var setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                    setter.call(el, val);
                    el.dispatchEvent(new Event('input', {bubbles: true}));
                    el.dispatchEvent(new Event('change', {bubbles: true}));
                }
                var emailEl = document.querySelector('input[name="email"], input[type="email"]');
                var passEl = document.querySelector('input[name="password"], input[type="password"]');
                if (emailEl) setNativeValue(emailEl, arguments[0]);
                if (passEl) setNativeValue(passEl, arguments[1]);
            """, email, password)
            await asyncio.sleep(1)
            await page.click('button[type="submit"]')
            await asyncio.sleep(5)
            await page.goto("https://dashboard.stripe.com/apikeys", timeout=30000)
            await asyncio.sleep(3)
            return await self._extract_stripe_keys(page)
        except Exception as e:
            return SignupResult(success=False, provider="stripe", error=f"login failed: {e}")

    async def _extract_stripe_keys(self, page) -> SignupResult:
        """Scrape API keys from dashboard.stripe.com/apikeys."""
        try:
            content = await page.content()
            # Look for publishable key (always visible)
            pk_match = re.search(r'pk_(test|live)_[A-Za-z0-9]{20,}', content)
            # Secret key may be hidden — try to reveal it
            try:
                await page.click('text=Reveal test key', timeout=5000)
                await asyncio.sleep(2)
                content = await page.content()
            except Exception:
                pass

            sk_match = re.search(r'sk_(test|live)_[A-Za-z0-9]{20,}', content)

            pk = pk_match.group(0) if pk_match else ""
            sk = sk_match.group(0) if sk_match else ""

            if sk:
                logger.info("[Stripe] Extracted sk=%s... pk=%s...", sk[:15], pk[:15] if pk else "?")
                # Store via credential vault
                await self._store_credential("stripe", sk)
                if pk:
                    await self._store_env("STRIPE_PUBLISHABLE_KEY", pk)
                return SignupResult(
                    success=True,
                    provider="stripe",
                    api_key=sk,
                    extra_keys={"publishable_key": pk},
                    strategy_used="playwright_headless",
                )
            else:
                # Return partial — keys page loaded but couldn't extract
                logger.warning("[Stripe] Keys page loaded but sk not found. URL=%s", page.url)
                return SignupResult(
                    success=False,
                    provider="stripe",
                    error=f"Could not extract sk_ from keys page. URL={page.url}",
                )
        except Exception as e:
            return SignupResult(success=False, provider="stripe", error=f"key extract error: {e}")

    async def _store_credential(self, integration: str, key: str):
        """Store key via Murphy credential vault API."""
        try:
            import urllib.request, json
            data = json.dumps({"integration": integration, "credential": key}).encode()
            req = urllib.request.Request(
                "http://127.0.0.1:8000/api/credentials/store",
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {os.environ.get('FOUNDER_API_KEY', 'founder_ad6b1fade355dc1c6dfa89db96d77608886bf63b01b4fb70')}",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as r:
                resp = json.loads(r.read())
                logger.info("[Runner] Stored credential %s: %s", integration, resp)
        except Exception as e:
            logger.warning("[Runner] Could not store credential %s: %s", integration, e)

    async def _store_env(self, key: str, value: str):
        """Write an env var to the Murphy environment file."""
        try:
            env_file = "/etc/murphy-production/environment"
            with open(env_file, "r") as f:
                content = f.read()
            if f"{key}=" in content:
                import re
                content = re.sub(rf"^{key}=.*$", f"{key}={value}", content, flags=re.MULTILINE)
            else:
                content += f"\n{key}={value}\n"
            with open(env_file, "w") as f:
                f.write(content)
            os.environ[key] = value
            logger.info("[Runner] Set env %s", key)
        except Exception as e:
            logger.warning("[Runner] Could not set env %s: %s", key, e)


# ── FastAPI router ─────────────────────────────────────────────────────────────

def create_playwright_runner_router():
    """Expose POST /api/playwright-runner/{provider} for manual triggers."""
    from fastapi import APIRouter
    router = APIRouter(prefix="/api/playwright-runner", tags=["playwright-runner"])

    @router.post("/{provider}")
    async def run_provider(provider: str, request: dict = None):
        from fastapi import Request
        runner = PlaywrightSignupRunner()
        if provider == "stripe":
            result = await runner.run_stripe()
        elif provider == "stripe-tempmail":
            # PATCH-154c: uses cpost@murphy.systems + IMAP (owner email directly)
            result = await runner.run_stripe_with_tempmail()
        elif provider == "ghost-stripe":
            # PATCH-154d: GhostBrowser (real Chromium CDP) — hCaptcha JS runs natively
            import asyncio as _asyncio
            from ghost_stripe_signup import GhostStripeSignup
            ghost = GhostStripeSignup(
                email="murphy@murphy.systems",
                password="Murphy2026!",
                company="Murphy Systems LLC",
            )
            ghost_result = await _asyncio.get_event_loop().run_in_executor(None, ghost.run)
            return {
                "success": ghost_result.success,
                "provider": "stripe-ghost",
                "email_used": ghost_result.email_used,
                "publishable_key_masked": (ghost_result.publishable_key[:12] + "...") if ghost_result.publishable_key else None,
                "secret_key_masked": (ghost_result.secret_key[:12] + "...") if ghost_result.secret_key else None,
                "error": ghost_result.error,
                "extra": ghost_result.extra,
            }
        else:
            return {"success": False, "error": f"Provider {provider!r} not yet implemented"}
        return {
            "success": result.success,
            "provider": result.provider,
            "api_key_masked": (result.api_key[:10] + "...") if result.api_key else None,
            "extra_keys": {k: v[:10] + "..." for k, v in result.extra_keys.items()},
            "strategy": result.strategy_used,
            "error": result.error,
        }

    @router.get("/status")
    async def runner_status():
        return {"status": "ready", "providers_supported": ["stripe"]}

    return router
