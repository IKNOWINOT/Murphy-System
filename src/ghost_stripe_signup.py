"""
Ghost Stripe Signup — ghost_stripe_signup.py
PATCH-154d

Uses GhostBrowser (real Chromium CDP, no Playwright) to register a Stripe account.
hCaptcha's JS runs natively in the real browser — no fake HSW tokens.
Form fill uses CDP Input events with human timing.
Email verification via IMAP polling on cpost@murphy.systems.

Copyright © 2020-2026 Inoni LLC — Created by Corey Post
PATCH-154d | Label: MCB-GHOST-STRIPE-001
License: BSL 1.1
"""
from __future__ import annotations

import asyncio
import email as email_lib
import imaplib
import json
import logging
import random
import re
import time
from dataclasses import dataclass, field
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

STRIPE_REGISTER_URL = "https://dashboard.stripe.com/register"
STRIPE_APIKEYS_URL  = "https://dashboard.stripe.com/apikeys"

# IMAP config — our self-hosted mail server
IMAP_HOST = "127.0.0.1"
IMAP_PORT = 993
IMAP_USER = "murphy@murphy.systems"
IMAP_PASS = "UIKTCUFJ2IMxX6oluBUfLZhgILjCVyeAMstPeRvteg0"


@dataclass
class GhostStripeResult:
    success: bool
    email_used: str = ""
    publishable_key: str = ""
    secret_key: str = ""
    error: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)


class GhostStripeSignup:
    """
    Registers a Stripe account using GhostBrowser (real Chromium/CDP).
    hCaptcha runs via real JS in the browser — generates a valid token.
    """

    def __init__(
        self,
        email: str = "murphy@murphy.systems",
        password: str = "Murphy2026!",
        company: str = "Murphy Systems LLC",
    ):
        self.email = email
        self.password = password
        self.company = company

    # ── CDP helpers ────────────────────────────────────────────────────────────

    def _eval(self, browser, tab_id: str, js: str) -> Any:
        """Run JS in the page, return result value."""
        result = browser._ws_command(tab_id, "Runtime.evaluate", {
            "expression": js,
            "returnByValue": True,
            "awaitPromise": True,
        })
        return result.get("result", {}).get("value")

    def _human_type(self, browser, tab_id: str, text: str):
        """Type text character-by-character via CDP Input events."""
        for ch in text:
            browser._ws_command(tab_id, "Input.dispatchKeyEvent", {
                "type": "keyDown", "text": ch,
            })
            browser._ws_command(tab_id, "Input.dispatchKeyEvent", {
                "type": "keyUp", "text": ch,
            })
            time.sleep(random.uniform(0.04, 0.14))

    def _click_selector(self, browser, tab_id: str, selector: str) -> bool:
        """Click an element by CSS selector — get coords from DOM then CDP click."""
        js = f"""
        (() => {{
            const el = document.querySelector({json.dumps(selector)});
            if (!el) return null;
            const r = el.getBoundingClientRect();
            return {{x: r.left + r.width/2, y: r.top + r.height/2}};
        }})()
        """
        pos = self._eval(browser, tab_id, js)
        if not pos:
            return False
        x, y = int(pos["x"]), int(pos["y"])
        for ev in ("mousePressed", "mouseReleased"):
            browser._ws_command(tab_id, "Input.dispatchMouseEvent", {
                "type": ev, "x": x, "y": y, "button": "left", "clickCount": 1,
            })
            time.sleep(0.05)
        return True

    def _fill_react_input(self, browser, tab_id: str, selector: str, value: str):
        """Fill a React-controlled input by setting nativeInputValueSetter."""
        js = f"""
        (() => {{
            const el = document.querySelector({json.dumps(selector)});
            if (!el) return false;
            const nativeSetter = Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype, 'value').set;
            nativeSetter.call(el, {json.dumps(value)});
            el.dispatchEvent(new Event('input', {{bubbles: true}}));
            el.dispatchEvent(new Event('change', {{bubbles: true}}));
            return true;
        }})()
        """
        return self._eval(browser, tab_id, js)

    def _wait_for_selector(self, browser, tab_id: str, selector: str, timeout: float = 15.0) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            exists = self._eval(browser, tab_id,
                f"!!document.querySelector({json.dumps(selector)})")
            if exists:
                return True
            time.sleep(0.5)
        return False

    def _wait_url_change(self, browser, tab_id: str, from_url: str, timeout: float = 30.0) -> str:
        deadline = time.time() + timeout
        while time.time() < deadline:
            url = self._eval(browser, tab_id, "window.location.href") or ""
            if url != from_url:
                return url
            time.sleep(1.0)
        return from_url

    def _get_url(self, browser, tab_id: str) -> str:
        return self._eval(browser, tab_id, "window.location.href") or ""

    # ── hCaptcha token extraction ──────────────────────────────────────────────

    def _wait_for_hcaptcha_token(self, browser, tab_id: str, timeout: float = 120.0) -> Optional[str]:
        """
        Wait for hCaptcha to generate a real h-captcha-response token.
        The real browser JS sets textarea[name=h-captcha-response] when solved.
        """
        logger.info("[GhostStripe] Waiting for hCaptcha real JS token (timeout=%ds)...", timeout)
        deadline = time.time() + timeout
        while time.time() < deadline:
            token = self._eval(browser, tab_id, """
                (() => {
                    const ta = document.querySelector('textarea[name="h-captcha-response"]');
                    if (ta && ta.value && ta.value.length > 20) return ta.value;
                    // Also try hcaptcha.getResponse()
                    try {
                        const r = window.hcaptcha ? window.hcaptcha.getResponse() : '';
                        if (r && r.length > 20) return r;
                    } catch(e) {}
                    return '';
                })()
            """)
            if token:
                logger.info("[GhostStripe] hCaptcha token obtained (len=%d)", len(token))
                return token
            time.sleep(2.0)
        logger.warning("[GhostStripe] hCaptcha token timeout — proceeding without token")
        return None

    # ── IMAP ──────────────────────────────────────────────────────────────────

    def _poll_imap_for_stripe(self, timeout: int = 300, poll: int = 10) -> Optional[str]:
        """Poll IMAP for a Stripe verification email. Returns body text."""
        deadline = time.time() + timeout
        logger.info("[GhostStripe] Polling IMAP for Stripe email (up to %ds)...", timeout)
        while time.time() < deadline:
            try:
                with imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT) as imap:
                    imap.login(IMAP_USER, IMAP_PASS)
                    imap.select("INBOX")
                    _, data = imap.search(None, "ALL")
                    ids = data[0].split()
                    # Check last 10 messages
                    for num in reversed(ids[-10:]):
                        _, msg_data = imap.fetch(num, "(RFC822)")
                        msg = email_lib.message_from_bytes(msg_data[0][1])
                        subject = msg.get("Subject", "")
                        sender  = msg.get("From", "")
                        if re.search(r"stripe|verify|confirm", subject + sender, re.I):
                            logger.info("[GhostStripe] Stripe email found: %s", subject)
                            return self._extract_body(msg)
            except Exception as e:
                logger.debug("[GhostStripe] IMAP error: %s", e)
            time.sleep(poll)
        return None

    def _extract_body(self, msg) -> str:
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() in ("text/plain", "text/html"):
                    body += part.get_payload(decode=True).decode(errors="replace")
        else:
            body = msg.get_payload(decode=True).decode(errors="replace")
        return body

    def _extract_verify_link(self, body: str) -> Optional[str]:
        for pat in [
            r"https://[\w./-]+confirm[\w./?=&%+-]+",
            r"https://[\w./-]+verify[\w./?=&%+-]+",
            r"https://[\w./-]+activate[\w./?=&%+-]+",
        ]:
            m = re.search(pat, body)
            if m:
                return m.group(0)
        m = re.search(r'href=["\'](https://[^"\' ]+(?:verify|confirm|activate)[^"\' ]+)["\']', body, re.I)
        if m:
            return m.group(1)
        return None

    # ── Stripe API key extraction ──────────────────────────────────────────────

    def _extract_keys(self, browser, tab_id: str) -> Dict[str, str]:
        """Scrape API keys from /apikeys page."""
        keys = {}
        html = self._eval(browser, tab_id, "document.documentElement.innerText") or ""
        # Look for sk_test / sk_live / pk_test / pk_live
        for pat, key in [
            (r"sk_test_[A-Za-z0-9]{20,}", "secret_key_test"),
            (r"sk_live_[A-Za-z0-9]{20,}", "secret_key_live"),
            (r"pk_test_[A-Za-z0-9]{20,}", "publishable_key_test"),
            (r"pk_live_[A-Za-z0-9]{20,}", "publishable_key_live"),
        ]:
            m = re.search(pat, html)
            if m:
                keys[key] = m.group(0)
                logger.info("[GhostStripe] Extracted %s: %s...", key, m.group(0)[:16])
        # Try reveal buttons
        self._eval(browser, tab_id, """
            document.querySelectorAll('button').forEach(btn => {
                if (/reveal|show|copy/i.test(btn.textContent)) btn.click();
            });
        """)
        time.sleep(2)
        html2 = self._eval(browser, tab_id, "document.documentElement.innerText") or ""
        for pat, key in [
            (r"sk_test_[A-Za-z0-9]{20,}", "secret_key_test"),
            (r"sk_live_[A-Za-z0-9]{20,}", "secret_key_live"),
        ]:
            m = re.search(pat, html2)
            if m and key not in keys:
                keys[key] = m.group(0)
                logger.info("[GhostStripe] Revealed %s: %s...", key, m.group(0)[:16])
        return keys

    # ── Main flow ─────────────────────────────────────────────────────────────

    def run(self) -> GhostStripeResult:
        """
        Full synchronous flow:
        1. Launch GhostBrowser (real Chromium)
        2. Navigate to Stripe register
        3. Fill form with human timing
        4. Wait for hCaptcha real JS token
        5. Submit form
        6. Poll IMAP for verification email
        7. Click verify link in new tab
        8. Extract API keys
        9. Store via credential vault
        """
        browser = None
        try:
            from murphy_ghost_vision import GhostBrowser
        except ImportError as e:
            return GhostStripeResult(success=False, email_used=self.email,
                                     error=f"GhostBrowser import failed: {e}")
        try:
            logger.info("[GhostStripe] Launching GhostBrowser...")
            browser = GhostBrowser(headless=True)
            browser.launch()
            tab_id = browser.new_tab()
            logger.info("[GhostStripe] Tab %s opened", tab_id)

            # Navigate
            logger.info("[GhostStripe] Navigating to %s", STRIPE_REGISTER_URL)
            browser.navigate(tab_id, STRIPE_REGISTER_URL, timeout=30.0)
            time.sleep(3)

            # Wait for form
            if not self._wait_for_selector(browser, tab_id, 'input[type="email"], input[name="email"]', timeout=20):
                # Try alternative: maybe already logged in
                url = self._get_url(browser, tab_id)
                logger.warning("[GhostStripe] No email input found at %s", url)

            # Fill email
            logger.info("[GhostStripe] Filling email: %s", self.email)
            filled = self._fill_react_input(browser, tab_id,
                'input[type="email"], input[name="email"]', self.email)
            if not filled:
                # Fallback: click + human type
                self._click_selector(browser, tab_id, 'input[type="email"]')
                time.sleep(0.3)
                self._human_type(browser, tab_id, self.email)
            time.sleep(random.uniform(0.5, 1.2))

            # Fill full name
            logger.info("[GhostStripe] Filling name")
            self._fill_react_input(browser, tab_id,
                'input[name="name"], input[placeholder*="name" i]', "Corey Post")
            time.sleep(random.uniform(0.3, 0.8))

            # Fill password
            logger.info("[GhostStripe] Filling password")
            self._fill_react_input(browser, tab_id,
                'input[type="password"]', self.password)
            time.sleep(random.uniform(0.5, 1.0))

            # Accept ToS checkbox if present
            self._eval(browser, tab_id, """
                (() => {
                    const cb = document.querySelector(
                        'input[type="checkbox"], [data-db-analytics-name*="terms"]');
                    if (cb && !cb.checked) cb.click();
                })()
            """)
            time.sleep(0.5)

            # Wait for hCaptcha real JS token
            # Note: In headless mode hCaptcha may auto-pass or show easy challenge
            token = self._wait_for_hcaptcha_token(browser, tab_id, timeout=90.0)

            # Submit the form
            logger.info("[GhostStripe] Submitting registration form")
            submitted = self._eval(browser, tab_id, """
                (() => {
                    // Try submit button click
                    const btn = document.querySelector(
                        'button[type="submit"], button[data-db-analytics-name*="create"]');
                    if (btn) { btn.click(); return 'button'; }
                    // Try form submit
                    const form = document.querySelector('form');
                    if (form) { form.submit(); return 'form'; }
                    return null;
                })()
            """)
            logger.info("[GhostStripe] Submit method: %s", submitted)
            time.sleep(5)

            url_after = self._get_url(browser, tab_id)
            logger.info("[GhostStripe] Post-submit URL: %s", url_after)

            # Poll IMAP for verification email
            body = self._poll_imap_for_stripe(timeout=300, poll=10)
            if body:
                verify_link = self._extract_verify_link(body)
                if verify_link:
                    logger.info("[GhostStripe] Clicking verify link: %s", verify_link[:80])
                    verify_tab = browser.new_tab()
                    browser.navigate(verify_tab, verify_link, timeout=30.0)
                    time.sleep(5)
                    browser.close_tab(verify_tab)
                else:
                    logger.warning("[GhostStripe] No verify link found in email body")
            else:
                logger.warning("[GhostStripe] No verification email — proceeding to apikeys")

            # Get API keys
            logger.info("[GhostStripe] Navigating to API keys page")
            browser.navigate(tab_id, STRIPE_APIKEYS_URL, timeout=30.0)
            time.sleep(4)
            keys = self._extract_keys(browser, tab_id)

            if keys:
                # Store via credential vault
                try:
                    from credential_vault import CredentialVault
                    vault = CredentialVault()
                    for k, v in keys.items():
                        vault.store(f"stripe_{k}", v)
                    logger.info("[GhostStripe] Stored %d keys in vault", len(keys))
                except Exception as ve:
                    logger.warning("[GhostStripe] Vault store failed: %s", ve)
                    # Also try env update
                    import os
                    for k, v in keys.items():
                        os.environ[f"STRIPE_{k.upper()}"] = v

                return GhostStripeResult(
                    success=True,
                    email_used=self.email,
                    publishable_key=keys.get("publishable_key_test", keys.get("publishable_key_live", "")),
                    secret_key=keys.get("secret_key_test", keys.get("secret_key_live", "")),
                    extra=keys,
                )
            else:
                # No keys yet — account may need email verification first
                return GhostStripeResult(
                    success=False,
                    email_used=self.email,
                    error="Account created but no API keys extracted — check email verification",
                    extra={"post_submit_url": url_after, "got_email": bool(body)},
                )

        except Exception as e:
            logger.error("[GhostStripe] Error: %s", e, exc_info=True)
            return GhostStripeResult(success=False, email_used=self.email, error=str(e))
        finally:
            try:
                if browser:
                    browser.close()
            except Exception:
                pass
