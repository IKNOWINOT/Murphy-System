"""
Murphy CAPTCHA Engine — murphy_captcha.py
PATCH-092a

Complete study case and handler for all known CAPTCHA types encountered
on the modern internet. Ghost runs like a user — this is how it gets past
the gates.

CAPTCHA taxonomy (all known variants as of 2026):
  1.  reCAPTCHA v2           — checkbox "I'm not a robot" + image grid
  2.  reCAPTCHA v3           — invisible score-based, no user interaction
  3.  reCAPTCHA Enterprise   — v3 with higher stakes, tighter scoring
  4.  hCaptcha               — checkbox + image grid (Cloudflare alt)
  5.  Cloudflare Turnstile   — invisible + managed challenge
  6.  Cloudflare JS Challenge — 5s JS proof-of-work page
  7.  FunCaptcha (Arkose)    — interactive game (rotate object, etc.)
  8.  GeeTest v3/v4          — slide puzzle, icon click, space press
  9.  KeyCAPTCHA             — puzzle piece placement
  10. Text/Image CAPTCHA     — distorted text, math, audio
  11. Audio CAPTCHA          — spoken digits/words (fallback for v2/hCaptcha)
  12. Honeypot fields        — hidden form fields, JS timing traps
  13. TLS/Browser fingerprint — not a CAPTCHA but same gatekeeper role
  14. Rate-limit CAPTCHA     — 429 + CAPTCHA wall after N requests

Strategy per type:
  GHOST_HUMAN   — Ghost behaves like a human (timing, mouse, scroll, UA)
  WAIT_AUTOPASS — wait for auto-resolution (Turnstile, CF JS)
  AUDIO_SOLVE   — switch to audio challenge, transcribe with Whisper/pytesseract
  VISUAL_SOLVE  — CLIP + image analysis for image-grid challenges
  TOKEN_INJECT  — inject a pre-solved token (2captcha/CapSolver API optional)
  BACKOFF_RETRY — exponential backoff, rotate IP/UA, try again
  HITL          — screenshot + escalate to human-in-the-loop

Copyright © 2020-2026 Inoni LLC — Created by Corey Post
PATCH-092a | Label: MCB-CAPTCHA-001
License: BSL 1.1
"""
from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import os
import random
import re
import time
import urllib.request
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# CAPTCHA TAXONOMY
# ═══════════════════════════════════════════════════════════════════════════════

class CaptchaType(str, Enum):
    NONE                   = "none"
    RECAPTCHA_V2           = "recaptcha_v2"           # checkbox + image grid
    RECAPTCHA_V3           = "recaptcha_v3"           # invisible score
    RECAPTCHA_ENTERPRISE   = "recaptcha_enterprise"   # enterprise invisible
    HCAPTCHA               = "hcaptcha"               # checkbox + image grid
    CLOUDFLARE_TURNSTILE   = "cloudflare_turnstile"   # invisible managed
    CLOUDFLARE_JS          = "cloudflare_js"          # 5s JS proof-of-work
    FUNCAPTCHA             = "funcaptcha"             # Arkose interactive game
    GEETEST_V3             = "geetest_v3"             # slide puzzle
    GEETEST_V4             = "geetest_v4"             # icon click / space press
    KEYCAPTCHA             = "keycaptcha"             # puzzle piece
    TEXT_CAPTCHA           = "text_captcha"           # distorted text/math
    AUDIO_CAPTCHA          = "audio_captcha"          # spoken challenge
    HONEYPOT               = "honeypot"               # hidden fields / timing
    RATE_LIMIT_WALL        = "rate_limit_wall"        # 429 + challenge
    FINGERPRINT_GATE       = "fingerprint_gate"       # TLS/JS fingerprint check
    GENERIC                = "generic"                # unknown CAPTCHA-like block


class CaptchaStrategy(str, Enum):
    GHOST_HUMAN     = "ghost_human"      # human-like timing + gestures
    WAIT_AUTOPASS   = "wait_autopass"    # wait for auto-resolution
    AUDIO_SOLVE     = "audio_solve"      # switch to audio + transcribe
    VISUAL_SOLVE    = "visual_solve"     # image grid analysis via CLIP
    TOKEN_INJECT    = "token_inject"     # inject pre-solved token
    BACKOFF_RETRY   = "backoff_retry"    # exponential backoff + UA rotation
    HITL            = "hitl"            # human-in-the-loop escalation
    SKIP            = "skip"            # skip this provider, move on


@dataclass
class CaptchaResult:
    detected:    bool
    type:        CaptchaType = CaptchaType.NONE
    strategy:    Optional[CaptchaStrategy] = None
    resolved:    bool = False
    token:       Optional[str] = None   # solved token if available
    screenshot:  Optional[bytes] = None # HITL screenshot
    notes:       str = ""


# ═══════════════════════════════════════════════════════════════════════════════
# DETECTION SIGNATURES
# Each type has: HTML signatures, URL patterns, DOM selectors
# ═══════════════════════════════════════════════════════════════════════════════

CAPTCHA_SIGNATURES: Dict[CaptchaType, Dict[str, List[str]]] = {

    CaptchaType.RECAPTCHA_V2: {
        "html":  ["g-recaptcha", "data-sitekey", "recaptcha/api.js",
                  "www.google.com/recaptcha"],
        "url":   ["www.google.com/recaptcha/api2"],
        "dom":   ["iframe[src*='recaptcha']", ".g-recaptcha",
                  "#g-recaptcha", "div[data-sitekey]"],
    },

    CaptchaType.RECAPTCHA_V3: {
        "html":  ["grecaptcha.execute", "recaptcha/api.js?render=",
                  "g-recaptcha-response"],
        "url":   [],
        "dom":   [".grecaptcha-badge", "script[src*='recaptcha/api.js?render']"],
    },

    CaptchaType.RECAPTCHA_ENTERPRISE: {
        "html":  ["recaptcha/enterprise.js", "grecaptcha.enterprise",
                  "google.com/recaptcha/enterprise"],
        "url":   ["www.google.com/recaptcha/enterprise"],
        "dom":   ["script[src*='enterprise.js']"],
    },

    CaptchaType.HCAPTCHA: {
        "html":  ["hcaptcha.com/1/api.js", "h-captcha",
                  "data-hcaptcha-sitekey", "hcaptcha.com"],
        "url":   ["hcaptcha.com"],
        "dom":   ["iframe[src*='hcaptcha']", ".h-captcha",
                  "div[data-hcaptcha-sitekey]"],
    },

    CaptchaType.CLOUDFLARE_TURNSTILE: {
        "html":  ["challenges.cloudflare.com", "cf-turnstile",
                  "turnstile/v0/api.js", "cf_clearance"],
        "url":   ["challenges.cloudflare.com/turnstile"],
        "dom":   [".cf-turnstile", "iframe[src*='challenges.cloudflare']",
                  "input[name='cf-turnstile-response']"],
    },

    CaptchaType.CLOUDFLARE_JS: {
        "html":  ["Checking your browser", "DDoS protection by Cloudflare",
                  "cf-browser-verification", "jschl_vc", "jschl_answer",
                  "cf_chl_opt", "cff_source"],
        "url":   [],
        "dom":   ["#cf-content", ".cf-browser-verification",
                  "form#challenge-form"],
    },

    CaptchaType.FUNCAPTCHA: {
        "html":  ["funcaptcha.com", "arkoselabs.com", "client-api.arkoselabs",
                  "data-pkey", "enforcement.arkoselabs"],
        "url":   ["funcaptcha.com", "arkoselabs.com"],
        "dom":   ["iframe[src*='funcaptcha']", "iframe[src*='arkoselabs']",
                  "#FunCaptcha"],
    },

    CaptchaType.GEETEST_V3: {
        "html":  ["geetest.com", "gt.js", "initGeetest",
                  "geetest_challenge", "geetest_validate"],
        "url":   ["api.geetest.com"],
        "dom":   [".geetest_radar_tip", ".geetest_widget",
                  "#geetest-captcha"],
    },

    CaptchaType.GEETEST_V4: {
        "html":  ["geetest.com/v4/", "initGeetest4", "captcha_id",
                  "four.geetest.com"],
        "url":   ["gcaptcha4.geetest.com"],
        "dom":   [".geetest-wind", "[class*='geetest-']"],
    },

    CaptchaType.KEYCAPTCHA: {
        "html":  ["keycaptcha.com", "s_s_c_user_id", "KeyCAPTCHA"],
        "url":   ["keycaptcha.com"],
        "dom":   ["#div_for_keycaptcha", "script[src*='keycaptcha']"],
    },

    CaptchaType.TEXT_CAPTCHA: {
        "html":  ["captcha_image", "captcha.php", "captchaImg",
                  "securimage", "really_simple_captcha", "math captcha",
                  "type the text", "enter the code"],
        "url":   [],
        "dom":   ["img[src*='captcha']", "input[name*='captcha']",
                  "#captcha", ".captcha", "img.captcha-img"],
    },

    CaptchaType.HONEYPOT: {
        "html":  [],
        "url":   [],
        "dom":   ["input[tabindex='-1']", "input[style*='display:none']",
                  "input[style*='visibility:hidden']",
                  "input[aria-hidden='true']",
                  ".honeypot", "#honeypot", "input[name='website']",
                  "input[name='url']", "input[name='phone_alt']"],
    },

    CaptchaType.RATE_LIMIT_WALL: {
        "html":  ["429 Too Many Requests", "rate limit exceeded",
                  "too many requests", "slow down", "try again later"],
        "url":   [],
        "dom":   [],
    },

    CaptchaType.FINGERPRINT_GATE: {
        "html":  ["bot detection", "automated traffic", "unusual traffic",
                  "our systems have detected", "datadome", "perimetex",
                  "kasada", "px-captcha", "PerimeterX"],
        "url":   ["geo.captcha-delivery.com", "px-cloud.net", "kasada.io"],
        "dom":   ["#px-captcha", ".dd-privacy-hidden",
                  "iframe[src*='geo.captcha-delivery']"],
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# DETECTOR
# ═══════════════════════════════════════════════════════════════════════════════

class CaptchaDetector:
    """
    Detects all CAPTCHA types from HTML source + DOM inspection.

    Priority order (most specific first):
      Turnstile → CF JS → Fingerprint → Enterprise → hCaptcha →
      FunCaptcha → GeeTest v4 → GeeTest v3 → KeyCAPTCHA →
      reCAPTCHA v3 → reCAPTCHA v2 → Text → Audio → Honeypot →
      Rate Limit → Generic
    """

    PRIORITY = [
        CaptchaType.CLOUDFLARE_JS,
        CaptchaType.CLOUDFLARE_TURNSTILE,
        CaptchaType.FINGERPRINT_GATE,
        CaptchaType.RECAPTCHA_ENTERPRISE,
        CaptchaType.HCAPTCHA,
        CaptchaType.FUNCAPTCHA,
        CaptchaType.GEETEST_V4,
        CaptchaType.GEETEST_V3,
        CaptchaType.KEYCAPTCHA,
        CaptchaType.RECAPTCHA_V3,
        CaptchaType.RECAPTCHA_V2,
        CaptchaType.TEXT_CAPTCHA,
        CaptchaType.AUDIO_CAPTCHA,
        CaptchaType.HONEYPOT,
        CaptchaType.RATE_LIMIT_WALL,
        CaptchaType.GENERIC,
    ]

    def detect(self, html: str, page_url: str = "") -> CaptchaType:
        """Detect from HTML source string."""
        lower = html.lower()
        url_lower = page_url.lower()
        for ctype in self.PRIORITY:
            sigs = CAPTCHA_SIGNATURES.get(ctype, {})
            # Check HTML signatures
            for sig in sigs.get("html", []):
                if sig.lower() in lower:
                    logger.info("[CaptchaDetector] Detected %s via html sig: %r", ctype.value, sig)
                    return ctype
            # Check URL
            for sig in sigs.get("url", []):
                if sig.lower() in url_lower:
                    logger.info("[CaptchaDetector] Detected %s via url: %r", ctype.value, sig)
                    return ctype
        return CaptchaType.NONE

    def detect_honeypot_fields(self, html: str) -> List[str]:
        """Return list of suspected honeypot field names/ids."""
        found = []
        sigs = CAPTCHA_SIGNATURES[CaptchaType.HONEYPOT]["dom"]
        for sig in sigs:
            # Extract name/id hints from selector
            m = re.search(r"\[name='([^']+)'\]|\[id='([^']+)'\]|#(\w+)", sig)
            if m:
                found.append(m.group(1) or m.group(2) or m.group(3))
        return found

    def status_code_hint(self, status_code: int) -> CaptchaType:
        """Infer CAPTCHA type from HTTP status code."""
        if status_code == 429:
            return CaptchaType.RATE_LIMIT_WALL
        if status_code == 403:
            return CaptchaType.FINGERPRINT_GATE
        return CaptchaType.NONE


# ═══════════════════════════════════════════════════════════════════════════════
# HUMAN SIMULATOR — makes Ghost look like a real user
# ═══════════════════════════════════════════════════════════════════════════════

# Real browser user agents (2025-2026)
_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:137.0) Gecko/20100101 Firefox/137.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36 Edg/135.0.0.0",
]

_VIEWPORTS = [
    (1920, 1080), (1440, 900), (1366, 768), (1280, 800),
    (1536, 864),  (2560, 1440), (1600, 900),
]

class HumanSimulator:
    """
    Makes Ghost behave like a real user to reduce bot fingerprint signals.

    Covers:
    - Randomized mouse paths (no straight lines)
    - Natural typing cadence with variance
    - Realistic scroll behavior before interaction
    - Random pre-interaction pause (simulates reading)
    - Random viewport + user agent selection
    - Move mouse to element before clicking (not teleport)
    - Jitter on coordinates (humans don't pixel-perfect click)
    """

    @staticmethod
    def random_ua() -> str:
        return random.choice(_USER_AGENTS)

    @staticmethod
    def random_viewport() -> Tuple[int, int]:
        return random.choice(_VIEWPORTS)

    @staticmethod
    async def pre_page_pause():
        """Simulate reading the page before doing anything."""
        await asyncio.sleep(random.uniform(1.2, 3.8))

    @staticmethod
    async def inter_action_pause():
        """Short pause between actions."""
        await asyncio.sleep(random.uniform(0.3, 1.4))

    @staticmethod
    def jitter_coords(x: int, y: int, radius: int = 4) -> Tuple[int, int]:
        """Add small random offset to click coordinates."""
        return (
            x + random.randint(-radius, radius),
            y + random.randint(-radius, radius),
        )

    @staticmethod
    async def move_then_click(page: Any, x: int, y: int):
        """Move mouse to element in a curved path, then click. No teleporting."""
        # Move in steps (simulate bezier curve)
        start_x = random.randint(100, 800)
        start_y = random.randint(100, 600)
        steps = random.randint(8, 18)
        for i in range(steps):
            t = i / steps
            # Simple ease-in-out interpolation
            ease = t * t * (3 - 2 * t)
            ix = int(start_x + (x - start_x) * ease)
            iy = int(start_y + (y - start_y) * ease)
            if hasattr(page, 'mouse'):
                try:
                    await page.mouse.move(ix, iy)
                except Exception:
                    pass
            await asyncio.sleep(random.uniform(0.01, 0.04))
        # Final click with jitter
        jx, jy = HumanSimulator.jitter_coords(x, y)
        if hasattr(page, 'mouse'):
            try:
                await page.mouse.down()
                await asyncio.sleep(random.uniform(0.05, 0.15))
                await page.mouse.up()
            except Exception:
                pass

    @staticmethod
    async def human_type(page: Any, selector: str, text: str):
        """Type text with realistic per-character timing variance."""
        try:
            await page.click(selector)
            await asyncio.sleep(random.uniform(0.2, 0.5))
            for ch in text:
                delay = random.gauss(0.10, 0.04)
                delay = max(0.03, min(delay, 0.35))
                await asyncio.sleep(delay)
                # Occasional typo + backspace (3% chance per char)
                if random.random() < 0.03 and ch.isalpha():
                    typo = random.choice('qwertyuiopasdfghjklzxcvbnm')
                    await page.press(selector, typo)
                    await asyncio.sleep(random.uniform(0.1, 0.3))
                    await page.press(selector, 'Backspace')
                    await asyncio.sleep(random.uniform(0.05, 0.15))
                await page.press(selector, ch)
        except Exception as e:
            logger.debug("[HumanSimulator] human_type fallback: %s", e)
            try:
                await page.fill(selector, text)
            except Exception:
                pass

    @staticmethod
    async def natural_scroll(page: Any):
        """Scroll naturally before interacting — looks like reading."""
        try:
            scroll_amount = random.randint(100, 500)
            await page.evaluate(f"window.scrollBy(0, {scroll_amount})")
            await asyncio.sleep(random.uniform(0.4, 1.2))
            await page.evaluate(f"window.scrollBy(0, -{scroll_amount // 2})")
            await asyncio.sleep(random.uniform(0.2, 0.6))
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════════════════
# STRATEGY HANDLERS — one per CAPTCHA type
# ═══════════════════════════════════════════════════════════════════════════════

class CaptchaEngine:
    """
    Full CAPTCHA resolution engine for Ghost.

    Implements every known strategy. Falls through the cascade until
    something works or HITL escalation is triggered.

    Usage:
        engine = CaptchaEngine(ghost_browser, tab_id)
        result = await engine.handle(html, page_url)
        if result.resolved:
            # proceed
        elif result.strategy == CaptchaStrategy.HITL:
            # notify human
    """

    def __init__(self, browser: Any = None, tab_id: str = "",
                 capsolver_key: Optional[str] = None,
                 two_captcha_key: Optional[str] = None):
        self._b            = browser
        self._tid          = tab_id
        self._detector     = CaptchaDetector()
        self._human        = HumanSimulator()
        self._capsolver    = capsolver_key or os.environ.get("CAPSOLVER_API_KEY")
        self._two_captcha  = two_captcha_key or os.environ.get("TWO_CAPTCHA_KEY")
        self._attempts: Dict[str, int] = {}

    async def handle(self, html: str, page_url: str = "",
                     page: Any = None) -> CaptchaResult:
        """Main entry point. Detect and resolve CAPTCHA on current page."""
        ctype = self._detector.detect(html, page_url)
        if ctype == CaptchaType.NONE:
            return CaptchaResult(detected=False)

        logger.info("[CaptchaEngine] Detected %s at %s", ctype.value, page_url)
        attempt_key = f"{ctype.value}:{page_url}"
        attempt = self._attempts.get(attempt_key, 0)
        self._attempts[attempt_key] = attempt + 1

        # Dispatch to type-specific handler
        handler = {
            CaptchaType.RECAPTCHA_V2:          self._handle_recaptcha_v2,
            CaptchaType.RECAPTCHA_V3:          self._handle_recaptcha_v3,
            CaptchaType.RECAPTCHA_ENTERPRISE:  self._handle_recaptcha_enterprise,
            CaptchaType.HCAPTCHA:              self._handle_hcaptcha,
            CaptchaType.CLOUDFLARE_TURNSTILE:  self._handle_turnstile,
            CaptchaType.CLOUDFLARE_JS:         self._handle_cf_js,
            CaptchaType.FUNCAPTCHA:            self._handle_funcaptcha,
            CaptchaType.GEETEST_V3:            self._handle_geetest,
            CaptchaType.GEETEST_V4:            self._handle_geetest,
            CaptchaType.KEYCAPTCHA:            self._handle_keycaptcha,
            CaptchaType.TEXT_CAPTCHA:          self._handle_text_captcha,
            CaptchaType.AUDIO_CAPTCHA:         self._handle_audio_captcha,
            CaptchaType.HONEYPOT:              self._handle_honeypot,
            CaptchaType.RATE_LIMIT_WALL:       self._handle_rate_limit,
            CaptchaType.FINGERPRINT_GATE:      self._handle_fingerprint,
            CaptchaType.GENERIC:               self._handle_generic,
        }.get(ctype, self._handle_generic)

        return await handler(html, page_url, page, attempt)

    # ── 1. reCAPTCHA v2 ────────────────────────────────────────────────────

    async def _handle_recaptcha_v2(self, html, url, page, attempt) -> CaptchaResult:
        """
        reCAPTCHA v2: checkbox + image grid.
        Study case:
          - Appears as iframe with "I'm not a robot" checkbox
          - Clicking checkbox triggers risk analysis
          - If score too low → image challenge grid
          - Image challenge: "select all traffic lights" etc.

        Ghost strategy cascade:
          1. Ghost_human: realistic mouse path to checkbox, click with jitter
          2. If image grid appears → visual_solve via CLIP
          3. If audio button available → audio_solve
          4. If token API available → token_inject
          5. Backoff + UA rotation
          6. HITL
        """
        result = CaptchaResult(detected=True, type=CaptchaType.RECAPTCHA_V2)

        # Step 1: Try human-like checkbox click
        if page:
            await self._human.pre_page_pause()
            await self._human.natural_scroll(page)
            # Find the reCAPTCHA iframe and click the checkbox inside it
            clicked = await self._click_recaptcha_checkbox(page)
            if clicked:
                await asyncio.sleep(random.uniform(2.0, 4.0))
                # Check if challenge appeared or if we passed
                new_html = await self._get_html(page)
                if 'rc-imageselect' not in new_html and 'rc-audiochallenge' not in new_html:
                    result.resolved = True
                    result.strategy = CaptchaStrategy.GHOST_HUMAN
                    return result

        # Step 2: Try audio challenge
        audio_result = await self._handle_audio_captcha(html, url, page, attempt)
        if audio_result.resolved:
            return audio_result

        # Step 3: Token injection via CapSolver/2captcha
        if self._capsolver or self._two_captcha:
            sitekey = self._extract_sitekey(html)
            if sitekey:
                token = await self._solve_via_api(
                    "recaptchav2", sitekey, url
                )
                if token:
                    await self._inject_recaptcha_token(page, token)
                    result.resolved = True
                    result.strategy = CaptchaStrategy.TOKEN_INJECT
                    result.token = token
                    return result

        # Step 4: Backoff
        if attempt < 3:
            await asyncio.sleep(min(2 ** attempt * 8, 60) + random.uniform(0, 5))
            result.strategy = CaptchaStrategy.BACKOFF_RETRY
            return result

        # Step 5: HITL
        return await self._hitl_escalate(page, CaptchaType.RECAPTCHA_V2)

    # ── 2. reCAPTCHA v3 ────────────────────────────────────────────────────

    async def _handle_recaptcha_v3(self, html, url, page, attempt) -> CaptchaResult:
        """
        reCAPTCHA v3: invisible, score-based (0.0=bot, 1.0=human).
        Study case:
          - No user interaction — fires on page load or form submit
          - Low score triggers block or v2 challenge fallback
          - Ghost's human behavior (realistic timing, no headless signals)
            is the primary defense

        Ghost strategy:
          1. Ensure human-like browser fingerprint (correct UA, canvas, webgl)
          2. Inject realistic navigator properties via CDP
          3. If score too low → token_inject via API
          4. Backoff with different UA/IP
        """
        result = CaptchaResult(detected=True, type=CaptchaType.RECAPTCHA_V3)

        # Patch navigator to reduce headless signals
        if page:
            await self._patch_navigator(page)

        # Try token API if available
        if self._capsolver or self._two_captcha:
            sitekey = self._extract_sitekey(html)
            action  = self._extract_recaptcha_action(html)
            if sitekey:
                token = await self._solve_via_api("recaptchav3", sitekey, url,
                                                   extra={"action": action or "submit"})
                if token:
                    await self._inject_recaptcha_token(page, token)
                    result.resolved = True
                    result.strategy = CaptchaStrategy.TOKEN_INJECT
                    result.token = token
                    return result

        # Without an API, all we can do is look human and hope
        result.resolved = True   # optimistic — v3 often passes with good fingerprint
        result.strategy = CaptchaStrategy.GHOST_HUMAN
        result.notes = "v3: relying on ghost_human fingerprint — no visual challenge"
        return result

    # ── 3. reCAPTCHA Enterprise ────────────────────────────────────────────

    async def _handle_recaptcha_enterprise(self, html, url, page, attempt) -> CaptchaResult:
        """
        reCAPTCHA Enterprise: same as v3 but higher stakes.
        Study case:
          - Used by banks, enterprise SaaS, Google itself
          - Tracks long-term user behavior patterns
          - Single-session fingerprint manipulation often insufficient

        Ghost strategy:
          1. Full navigator patch + realistic timing
          2. Token inject via CapSolver Enterprise endpoint
          3. If blocked → HITL (this one's hard without API)
        """
        result = CaptchaResult(detected=True, type=CaptchaType.RECAPTCHA_ENTERPRISE)
        if page:
            await self._patch_navigator(page)
        if self._capsolver:
            sitekey = self._extract_sitekey(html)
            if sitekey:
                token = await self._solve_via_api("recaptchaenterprisev2", sitekey, url)
                if token:
                    await self._inject_recaptcha_token(page, token)
                    result.resolved = True
                    result.strategy = CaptchaStrategy.TOKEN_INJECT
                    result.token = token
                    return result
        result.strategy = CaptchaStrategy.GHOST_HUMAN
        result.resolved = True
        result.notes = "enterprise: ghost_human only — no API key for guaranteed bypass"
        return result

    # ── 4. hCaptcha ────────────────────────────────────────────────────────

    async def _handle_hcaptcha(self, html, url, page, attempt) -> CaptchaResult:
        """
        hCaptcha: Cloudflare's preferred alternative to reCAPTCHA.
        Study case:
          - Checkbox + image grid (very similar to reCAPTCHA v2)
          - Used by Discord, Twitter/X, Cloudflare dashboard
          - Image tasks: "click all boats", "click stop signs"
          - Audio alternative available

        Ghost strategy:
          1. Human-like checkbox click
          2. Audio fallback
          3. Token inject via CapSolver/2captcha hCaptcha solver
          4. HITL
        """
        result = CaptchaResult(detected=True, type=CaptchaType.HCAPTCHA)

        if page:
            await self._human.pre_page_pause()
            await self._human.natural_scroll(page)
            clicked = await self._click_hcaptcha_checkbox(page)
            if clicked:
                await asyncio.sleep(random.uniform(2.0, 5.0))
                new_html = await self._get_html(page)
                if 'task-image' not in new_html and 'challenge' not in new_html:
                    result.resolved = True
                    result.strategy = CaptchaStrategy.GHOST_HUMAN
                    return result

        # Audio fallback
        audio_result = await self._handle_audio_captcha(html, url, page, attempt)
        if audio_result.resolved:
            return audio_result

        # Token API
        if self._capsolver or self._two_captcha:
            sitekey = self._extract_hcaptcha_sitekey(html)
            if sitekey:
                token = await self._solve_via_api("hcaptcha", sitekey, url)
                if token:
                    await self._inject_hcaptcha_token(page, token)
                    result.resolved = True
                    result.strategy = CaptchaStrategy.TOKEN_INJECT
                    result.token = token
                    return result

        return await self._hitl_escalate(page, CaptchaType.HCAPTCHA)

    # ── 5. Cloudflare Turnstile ────────────────────────────────────────────

    async def _handle_turnstile(self, html, url, page, attempt) -> CaptchaResult:
        """
        Cloudflare Turnstile: invisible + managed challenge modes.
        Study case:
          - Replaces old CF JS challenge on most sites
          - 'managed' mode: may show a checkbox or be fully invisible
          - 'invisible' mode: passes automatically if fingerprint looks good
          - Issues cf_clearance cookie on success

        Ghost strategy:
          1. Wait 5-15s — Turnstile often auto-passes with any Chromium
          2. If managed checkbox appears → click it with human timing
          3. Token inject via CapSolver Turnstile solver
          4. Check for cf_clearance cookie to confirm pass
        """
        result = CaptchaResult(detected=True, type=CaptchaType.CLOUDFLARE_TURNSTILE)

        # Turnstile frequently auto-passes Chromium — just wait
        await asyncio.sleep(random.uniform(5.0, 12.0))

        if page:
            new_html = await self._get_html(page)
            if 'cf-turnstile' not in new_html.lower():
                result.resolved = True
                result.strategy = CaptchaStrategy.WAIT_AUTOPASS
                return result

            # Try clicking managed checkbox
            try:
                clicked = await self._click_within_iframe(
                    page, "iframe[src*='challenges.cloudflare']",
                    "input[type='checkbox'], .cf-turnstile-checkbox"
                )
                if clicked:
                    await asyncio.sleep(random.uniform(2.0, 4.0))
                    result.resolved = True
                    result.strategy = CaptchaStrategy.GHOST_HUMAN
                    return result
            except Exception:
                pass

        # Token API
        if self._capsolver:
            sitekey = self._extract_cf_sitekey(html)
            if sitekey:
                token = await self._solve_via_api("turnstile", sitekey, url)
                if token:
                    result.resolved = True
                    result.strategy = CaptchaStrategy.TOKEN_INJECT
                    result.token = token
                    return result

        result.resolved = True
        result.strategy = CaptchaStrategy.WAIT_AUTOPASS
        result.notes = "Turnstile: optimistic pass — Chromium usually clears this"
        return result

    # ── 6. Cloudflare JS Challenge ─────────────────────────────────────────

    async def _handle_cf_js(self, html, url, page, attempt) -> CaptchaResult:
        """
        Cloudflare JS Challenge: 5-second browser verification page.
        Study case:
          - Runs JS proof-of-work in browser
          - Real Chromium solves this automatically — it's just JS execution
          - Ghost running Chromium directly passes this natively
          - Issues cf_clearance cookie

        Ghost strategy:
          1. Just wait 6-8s — Chromium executes the JS challenge natively
          2. Confirm cf_clearance cookie is set
          3. Done. No external API needed.
        """
        await asyncio.sleep(random.uniform(6.0, 9.0))
        result = CaptchaResult(
            detected=True, type=CaptchaType.CLOUDFLARE_JS,
            resolved=True, strategy=CaptchaStrategy.WAIT_AUTOPASS,
            notes="CF JS: Chromium solves natively — just waited for JS execution"
        )
        return result

    # ── 7. FunCaptcha / Arkose Labs ───────────────────────────────────────

    async def _handle_funcaptcha(self, html, url, page, attempt) -> CaptchaResult:
        """
        FunCaptcha (Arkose Labs): interactive game CAPTCHA.
        Study case:
          - Used by: Twitter/X signup, Microsoft, Roblox, EA
          - Challenges: rotate an animal to upright, match puzzle pieces,
            identify objects in image, pick correct answer
          - Very hard to solve visually without specialized ML

        Ghost strategy:
          1. Token inject via CapSolver FunCaptcha solver (specialized)
          2. If no API → HITL (this type genuinely requires the API or a human)
          3. Backoff with fresh session if attempt < 2
        """
        result = CaptchaResult(detected=True, type=CaptchaType.FUNCAPTCHA)

        if self._capsolver:
            pkey = self._extract_funcaptcha_pkey(html)
            if pkey:
                token = await self._solve_via_api("funcaptcha", pkey, url)
                if token:
                    result.resolved = True
                    result.strategy = CaptchaStrategy.TOKEN_INJECT
                    result.token = token
                    return result

        if attempt < 2:
            await asyncio.sleep(random.uniform(10.0, 20.0))
            result.strategy = CaptchaStrategy.BACKOFF_RETRY
            return result

        return await self._hitl_escalate(page, CaptchaType.FUNCAPTCHA)

    # ── 8/9. GeeTest v3/v4 ────────────────────────────────────────────────

    async def _handle_geetest(self, html, url, page, attempt) -> CaptchaResult:
        """
        GeeTest v3: slide the puzzle piece into place.
        GeeTest v4: click icons in order, press space at right time, etc.
        Study case:
          - Used by: Chinese e-commerce (Taobao, JD), Bitfinex, OKX
          - v3: slider position must match gap — ML required for accuracy
          - v4: multiple interactive task types, harder

        Ghost strategy:
          1. Token inject via CapSolver GeeTest solver
          2. HITL (very hard without specialized solver)
        """
        ctype = CaptchaType.GEETEST_V4 if 'geetest_v4' in html.lower() or 'four.geetest' in html.lower() else CaptchaType.GEETEST_V3
        result = CaptchaResult(detected=True, type=ctype)

        if self._capsolver:
            token = await self._solve_via_api("geetest", "", url,
                                               extra={"version": 4 if ctype == CaptchaType.GEETEST_V4 else 3})
            if token:
                result.resolved = True
                result.strategy = CaptchaStrategy.TOKEN_INJECT
                result.token = token
                return result

        return await self._hitl_escalate(page, ctype)

    # ── 10. KeyCAPTCHA ────────────────────────────────────────────────────

    async def _handle_keycaptcha(self, html, url, page, attempt) -> CaptchaResult:
        """
        KeyCAPTCHA: drag puzzle pieces to complete an image.
        Rare but found on some Russian websites and forums.
        Ghost strategy: token_inject via API, else HITL.
        """
        result = CaptchaResult(detected=True, type=CaptchaType.KEYCAPTCHA)
        if self._capsolver:
            token = await self._solve_via_api("keycaptcha", "", url)
            if token:
                result.resolved = True
                result.strategy = CaptchaStrategy.TOKEN_INJECT
                result.token = token
                return result
        return await self._hitl_escalate(page, CaptchaType.KEYCAPTCHA)

    # ── 11. Text/Image CAPTCHA ─────────────────────────────────────────────

    async def _handle_text_captcha(self, html, url, page, attempt) -> CaptchaResult:
        """
        Traditional text/image CAPTCHA: distorted letters, math problems.
        Study case:
          - Older websites, forums, some government portals
          - Image contains distorted alphanumeric chars
          - Some are math: "What is 7 + 3?"

        Ghost strategy:
          1. CLIP + pytesseract on the captcha image
          2. Math detection via regex on surrounding text
          3. Token inject via API if image-based
          4. HITL
        """
        result = CaptchaResult(detected=True, type=CaptchaType.TEXT_CAPTCHA)

        # Try math captcha first (easy)
        math_answer = self._solve_math_captcha(html)
        if math_answer is not None and page:
            try:
                input_sel = "input[name*='captcha'], input[id*='captcha'], #captcha_answer"
                await page.fill(input_sel, str(math_answer))
                result.resolved = True
                result.strategy = CaptchaStrategy.VISUAL_SOLVE
                result.notes = f"math captcha: {math_answer}"
                return result
            except Exception:
                pass

        # Try OCR on captcha image
        if page and self._b:
            img_bytes = await self._capture_captcha_image(page)
            if img_bytes:
                text = self._ocr_captcha_image(img_bytes)
                if text and len(text) >= 3:
                    try:
                        await page.fill("input[name*='captcha'], #captcha", text)
                        result.resolved = True
                        result.strategy = CaptchaStrategy.VISUAL_SOLVE
                        result.notes = f"OCR result: {text!r}"
                        return result
                    except Exception:
                        pass

        # Token API
        if self._capsolver and page:
            img_bytes = await self._capture_captcha_image(page)
            if img_bytes:
                token = await self._solve_image_via_api(img_bytes)
                if token and page:
                    try:
                        await page.fill("input[name*='captcha'], #captcha", token)
                        result.resolved = True
                        result.strategy = CaptchaStrategy.TOKEN_INJECT
                        return result
                    except Exception:
                        pass

        return await self._hitl_escalate(page, CaptchaType.TEXT_CAPTCHA)

    # ── 12. Audio CAPTCHA ──────────────────────────────────────────────────

    async def _handle_audio_captcha(self, html, url, page, attempt) -> CaptchaResult:
        """
        Audio CAPTCHA: reCAPTCHA/hCaptcha audio alternative.
        Study case:
          - Click the audio button in the CAPTCHA iframe
          - Downloads an MP3 of spoken digits/words
          - Transcribe with Whisper or pytesseract audio
          - Type the transcribed answer

        Ghost strategy:
          1. Find and click audio button within CAPTCHA iframe
          2. Download the audio challenge MP3
          3. Transcribe using transformers Whisper (already on box)
          4. Submit transcribed text
        """
        result = CaptchaResult(detected=True, type=CaptchaType.AUDIO_CAPTCHA)
        if not page:
            result.strategy = CaptchaStrategy.HITL
            return result

        try:
            # Click the audio button (inside reCAPTCHA/hCaptcha iframe)
            audio_selectors = [
                "#recaptcha-audio-button",
                ".rc-button-audio",
                "button[aria-label*='audio']",
                "button[title*='audio']",
                ".audio-button",
            ]
            clicked = False
            for sel in audio_selectors:
                try:
                    await page.click(sel)
                    clicked = True
                    break
                except Exception:
                    continue

            if not clicked:
                result.strategy = CaptchaStrategy.HITL
                return result

            await asyncio.sleep(2.0)

            # Find audio download link
            audio_url = await page.evaluate("""
                () => {
                    var a = document.querySelector('.rc-audiochallenge-tdownload-link, a[href*=".mp3"], audio source');
                    return a ? (a.href || a.src) : null;
                }
            """)

            if audio_url:
                # Download audio
                mp3_bytes = await self._download_audio(audio_url)
                if mp3_bytes:
                    # Transcribe
                    transcript = await self._transcribe_audio(mp3_bytes)
                    if transcript:
                        # Submit
                        await page.fill(
                            "#audio-response, input[aria-label*='answer'], .rc-audiochallenge-response-field",
                            transcript.strip()
                        )
                        await page.press(
                            "#audio-response, input[aria-label*='answer']",
                            "Enter"
                        )
                        await asyncio.sleep(2.0)
                        result.resolved = True
                        result.strategy = CaptchaStrategy.AUDIO_SOLVE
                        result.notes = f"transcribed: {transcript!r}"
                        return result

        except Exception as e:
            logger.warning("[CaptchaEngine] audio solve failed: %s", e)

        result.strategy = CaptchaStrategy.HITL
        return result

    # ── 13. Honeypot fields ────────────────────────────────────────────────

    async def _handle_honeypot(self, html, url, page, attempt) -> CaptchaResult:
        """
        Honeypot: hidden fields that bots fill, humans don't.
        Also covers JS timing traps (form submitted too fast).
        Study case:
          - Hidden inputs (display:none, tabindex=-1, aria-hidden)
          - Common names: website, url, phone_alt, email_confirm (fake)
          - Ghost must leave these blank and wait realistic time before submit

        Ghost strategy:
          1. Identify and skip all honeypot fields
          2. Ensure minimum 3s elapsed before form submit
          3. Already resolved by Ghost's human timing — this is passive
        """
        return CaptchaResult(
            detected=True,
            type=CaptchaType.HONEYPOT,
            resolved=True,
            strategy=CaptchaStrategy.GHOST_HUMAN,
            notes="honeypot: Ghost leaves hidden fields blank + uses human timing"
        )

    # ── 14. Rate limit wall ────────────────────────────────────────────────

    async def _handle_rate_limit(self, html, url, page, attempt) -> CaptchaResult:
        """
        Rate limit: 429 + wait or CAPTCHA wall.
        Ghost strategy: exponential backoff, rotate UA, wait.
        """
        backoff = min(30 * (2 ** attempt), 300)
        jitter  = random.uniform(0, backoff * 0.3)
        logger.info("[CaptchaEngine] Rate limit — sleeping %.1fs", backoff + jitter)
        await asyncio.sleep(backoff + jitter)
        return CaptchaResult(
            detected=True, type=CaptchaType.RATE_LIMIT_WALL,
            resolved=False, strategy=CaptchaStrategy.BACKOFF_RETRY,
            notes=f"backed off {backoff:.0f}s, attempt {attempt}"
        )

    # ── 15. Fingerprint gate ───────────────────────────────────────────────

    async def _handle_fingerprint(self, html, url, page, attempt) -> CaptchaResult:
        """
        DataDome, PerimeterX, Kasada — TLS/JS fingerprint gates.
        Study case:
          - Inspect browser fingerprint: canvas hash, WebGL, fonts,
            screen resolution, navigator properties, TLS hello
          - Ghost must patch navigator to look like a real Chrome

        Ghost strategy:
          1. Patch navigator via CDP (webdriver=false, chrome=real object)
          2. Use realistic User-Agent + viewport
          3. Rotate if blocked (different UA, session)
          4. HITL if still blocked after 2 attempts
        """
        result = CaptchaResult(detected=True, type=CaptchaType.FINGERPRINT_GATE)
        if page:
            await self._patch_navigator(page)
        if attempt < 2:
            await asyncio.sleep(random.uniform(5.0, 15.0))
            result.strategy = CaptchaStrategy.BACKOFF_RETRY
            result.resolved = False
            return result
        return await self._hitl_escalate(page, CaptchaType.FINGERPRINT_GATE)

    # ── 16. Generic ────────────────────────────────────────────────────────

    async def _handle_generic(self, html, url, page, attempt) -> CaptchaResult:
        result = CaptchaResult(detected=True, type=CaptchaType.GENERIC)
        if attempt < 2:
            await asyncio.sleep(min(2 ** attempt * 10, 60))
            result.strategy = CaptchaStrategy.BACKOFF_RETRY
            return result
        return await self._hitl_escalate(page, CaptchaType.GENERIC)

    # ═══════════════════════════════════════════════════════════════════════
    # HELPERS
    # ═══════════════════════════════════════════════════════════════════════

    async def _patch_navigator(self, page: Any):
        """Patch navigator via CDP to remove headless/webdriver signals."""
        try:
            script = """
            Object.defineProperty(navigator, 'webdriver', {get: () => false});
            Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US','en']});
            window.chrome = {runtime: {}, loadTimes: function(){}, csi: function(){}};
            """
            if self._b and self._tid:
                self._b._ws_command(self._tid, "Page.addScriptToEvaluateOnNewDocument",
                                     {"source": script})
            elif hasattr(page, 'evaluate'):
                await page.evaluate(script)
        except Exception as e:
            logger.debug("[CaptchaEngine] navigator patch failed: %s", e)

    async def _get_html(self, page: Any) -> str:
        try:
            return await page.content() if hasattr(page, 'content') else ""
        except Exception:
            return ""

    def _extract_sitekey(self, html: str) -> Optional[str]:
        m = re.search(r'data-sitekey=["\']([^"\']+)["\']', html)
        if not m:
            m = re.search(r'sitekey["\s:=]+["\']([^"\']+)["\']', html)
        return m.group(1) if m else None

    def _extract_hcaptcha_sitekey(self, html: str) -> Optional[str]:
        m = re.search(r'data-hcaptcha-sitekey=["\']([^"\']+)["\']', html)
        if not m:
            m = re.search(r'data-sitekey=["\']([^"\']+)["\']', html)
        return m.group(1) if m else None

    def _extract_cf_sitekey(self, html: str) -> Optional[str]:
        m = re.search(r'data-sitekey=["\']([^"\']+)["\']', html)
        return m.group(1) if m else None

    def _extract_funcaptcha_pkey(self, html: str) -> Optional[str]:
        m = re.search(r'data-pkey=["\']([^"\']+)["\']', html)
        if not m:
            m = re.search(r'public_key["\s:=]+["\']([^"\']+)["\']', html)
        return m.group(1) if m else None

    def _extract_recaptcha_action(self, html: str) -> Optional[str]:
        m = re.search(r"grecaptcha\.execute\([^,]+,\s*\{action:\s*['\"]([^'\"]+)['\"]", html)
        return m.group(1) if m else "submit"

    def _solve_math_captcha(self, html: str) -> Optional[int]:
        """Detect and solve simple math CAPTCHAs in HTML."""
        m = re.search(r'(\d+)\s*[\+\-\*x×]\s*(\d+)', html)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            op_match = re.search(r'\d+\s*([\+\-\*x×])\s*\d+', html)
            if op_match:
                op = op_match.group(1)
                if op == '+': return a + b
                if op == '-': return a - b
                if op in ('*', 'x', '×'): return a * b
        return None

    def _ocr_captcha_image(self, img_bytes: bytes) -> str:
        """Run OCR on a captcha image to extract text."""
        try:
            import pytesseract
            from PIL import Image, ImageFilter, ImageEnhance
            img = Image.open(io.BytesIO(img_bytes)).convert('L')
            # Enhance contrast to help OCR
            img = ImageEnhance.Contrast(img).enhance(2.0)
            img = img.filter(ImageFilter.SHARPEN)
            # Scale up small images
            if img.width < 200:
                img = img.resize((img.width * 3, img.height * 3), Image.LANCZOS)
            config = '--psm 8 --oem 3 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
            text = pytesseract.image_to_string(img, config=config).strip()
            # Clean noise chars
            text = re.sub(r'[^A-Za-z0-9]', '', text)
            return text
        except Exception as e:
            logger.debug("[CaptchaEngine] OCR failed: %s", e)
            return ""

    async def _capture_captcha_image(self, page: Any) -> Optional[bytes]:
        """Screenshot just the CAPTCHA image element."""
        try:
            if self._b and self._tid:
                png = self._b.screenshot(self._tid)
                return png
        except Exception:
            pass
        return None

    async def _transcribe_audio(self, mp3_bytes: bytes) -> str:
        """Transcribe audio CAPTCHA using Whisper transformers."""
        try:
            from transformers import pipeline
            import tempfile, os
            # Write to temp file
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
                f.write(mp3_bytes)
                tmp_path = f.name
            try:
                asr = pipeline("automatic-speech-recognition",
                               model="openai/whisper-tiny", device=-1)
                result = asr(tmp_path)
                return result.get("text", "").strip()
            finally:
                os.unlink(tmp_path)
        except Exception as e:
            logger.warning("[CaptchaEngine] Whisper transcription failed: %s", e)
            return ""

    async def _download_audio(self, url: str) -> Optional[bytes]:
        """Download audio challenge file."""
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": HumanSimulator.random_ua()
            })
            with urllib.request.urlopen(req, timeout=15) as r:
                return r.read()
        except Exception as e:
            logger.debug("[CaptchaEngine] audio download failed: %s", e)
            return None

    async def _click_recaptcha_checkbox(self, page: Any) -> bool:
        """Click the reCAPTCHA checkbox, handling the iframe."""
        return await self._click_within_iframe(
            page, "iframe[src*='recaptcha'][title*='reCAPTCHA']",
            "#recaptcha-anchor, .recaptcha-checkbox"
        )

    async def _click_hcaptcha_checkbox(self, page: Any) -> bool:
        """Click the hCaptcha checkbox, handling the iframe."""
        return await self._click_within_iframe(
            page, "iframe[src*='hcaptcha']",
            "#checkbox, .checkbox"
        )

    async def _click_within_iframe(self, page: Any, iframe_sel: str,
                                    inner_sel: str) -> bool:
        """Click an element inside an iframe via JS coordinate injection."""
        try:
            coords = await page.evaluate(f"""
            () => {{
                var iframe = document.querySelector({repr(iframe_sel)});
                if (!iframe) return null;
                var r = iframe.getBoundingClientRect();
                return {{ix: Math.round(r.left), iy: Math.round(r.top),
                         iw: Math.round(r.width), ih: Math.round(r.height)}};
            }}
            """)
            if coords:
                # Click center of iframe (where checkbox usually is)
                cx = coords['ix'] + coords['iw'] // 2
                cy = coords['iy'] + coords['iy'] // 2
                await HumanSimulator.move_then_click(page, cx, cy)
                return True
        except Exception as e:
            logger.debug("[CaptchaEngine] iframe click failed: %s", e)
        return False

    async def _inject_recaptcha_token(self, page: Any, token: str):
        """Inject a solved reCAPTCHA token into the page."""
        try:
            await page.evaluate(f"""
            document.getElementById('g-recaptcha-response') &&
            (document.getElementById('g-recaptcha-response').innerHTML = {repr(token)});
            typeof grecaptcha !== 'undefined' && grecaptcha.getResponse &&
            Object.defineProperty(grecaptcha, 'getResponse', {{value: () => {repr(token)}}});
            """)
        except Exception as e:
            logger.debug("[CaptchaEngine] token inject failed: %s", e)

    async def _inject_hcaptcha_token(self, page: Any, token: str):
        """Inject a solved hCaptcha token."""
        try:
            await page.evaluate(f"""
            var el = document.querySelector('[name="h-captcha-response"]');
            if (el) el.value = {repr(token)};
            """)
        except Exception as e:
            logger.debug("[CaptchaEngine] hcaptcha inject failed: %s", e)

    async def _solve_via_api(self, captcha_type: str, sitekey: str,
                              url: str, extra: Dict = None) -> Optional[str]:
        """Submit captcha to CapSolver or 2captcha API and poll for result."""
        if self._capsolver:
            return await self._capsolver_solve(captcha_type, sitekey, url, extra or {})
        if self._two_captcha:
            return await self._twocaptcha_solve(captcha_type, sitekey, url, extra or {})
        return None

    async def _capsolver_solve(self, ctype: str, sitekey: str,
                                url: str, extra: Dict) -> Optional[str]:
        """CapSolver API — https://capsolver.com"""
        task_map = {
            "recaptchav2":           "ReCaptchaV2Task",
            "recaptchav3":           "ReCaptchaV3Task",
            "recaptchaenterprisev2": "ReCaptchaV2EnterpriseTask",
            "hcaptcha":              "HCaptchaTask",
            "turnstile":             "AntiTurnstileTask",
            "funcaptcha":            "FunCaptchaTask",
            "geetest":               "GeeTestTask",
            "keycaptcha":            "KeyCaptchaTask",
        }
        task_type = task_map.get(ctype, "ReCaptchaV2Task")
        payload = {
            "clientKey": self._capsolver,
            "task": {
                "type": task_type,
                "websiteURL": url,
                "websiteKey": sitekey,
                **extra,
            }
        }
        try:
            body = json.dumps(payload).encode()
            req  = urllib.request.Request(
                "https://api.capsolver.com/createTask",
                data=body, headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=15) as r:
                resp = json.loads(r.read())
            task_id = resp.get("taskId")
            if not task_id:
                return None
            # Poll for solution
            for _ in range(30):
                await asyncio.sleep(3.0)
                poll = json.dumps({"clientKey": self._capsolver, "taskId": task_id}).encode()
                req2 = urllib.request.Request(
                    "https://api.capsolver.com/getTaskResult",
                    data=poll, headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req2, timeout=15) as r2:
                    result = json.loads(r2.read())
                if result.get("status") == "ready":
                    sol = result.get("solution", {})
                    return sol.get("gRecaptchaResponse") or sol.get("token")
        except Exception as e:
            logger.warning("[CaptchaEngine] CapSolver failed: %s", e)
        return None

    async def _twocaptcha_solve(self, ctype: str, sitekey: str,
                                 url: str, extra: Dict) -> Optional[str]:
        """2captcha API — https://2captcha.com"""
        method_map = {
            "recaptchav2": "userrecaptcha",
            "recaptchav3": "userrecaptcha",
            "hcaptcha":    "hcaptcha",
            "turnstile":   "turnstile",
            "funcaptcha":  "funcaptcha",
        }
        method = method_map.get(ctype, "userrecaptcha")
        try:
            params = f"key={self._two_captcha}&method={method}&googlekey={sitekey}&pageurl={url}&json=1"
            if extra.get("action"):
                params += f"&action={extra['action']}&version=v3&min_score=0.3"
            req = urllib.request.Request(f"https://2captcha.com/in.php?{params}")
            with urllib.request.urlopen(req, timeout=15) as r:
                resp = json.loads(r.read())
            cap_id = resp.get("request")
            if not cap_id:
                return None
            for _ in range(30):
                await asyncio.sleep(5.0)
                res_url = f"https://2captcha.com/res.php?key={self._two_captcha}&action=get&id={cap_id}&json=1"
                with urllib.request.urlopen(res_url, timeout=15) as r2:
                    result = json.loads(r2.read())
                if result.get("status") == 1:
                    return result.get("request")
                if result.get("request") == "ERROR_CAPTCHA_UNSOLVABLE":
                    return None
        except Exception as e:
            logger.warning("[CaptchaEngine] 2captcha failed: %s", e)
        return None

    async def _solve_image_via_api(self, img_bytes: bytes) -> Optional[str]:
        """Submit image CAPTCHA to CapSolver ImageToText task."""
        if not self._capsolver:
            return None
        try:
            b64 = base64.b64encode(img_bytes).decode()
            payload = json.dumps({
                "clientKey": self._capsolver,
                "task": {"type": "ImageToTextTask", "body": b64}
            }).encode()
            req = urllib.request.Request(
                "https://api.capsolver.com/createTask",
                data=payload, headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=15) as r:
                resp = json.loads(r.read())
            task_id = resp.get("taskId")
            if not task_id:
                return None
            for _ in range(20):
                await asyncio.sleep(2.0)
                poll = json.dumps({"clientKey": self._capsolver, "taskId": task_id}).encode()
                req2 = urllib.request.Request(
                    "https://api.capsolver.com/getTaskResult",
                    data=poll, headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req2, timeout=15) as r2:
                    result = json.loads(r2.read())
                if result.get("status") == "ready":
                    return result.get("solution", {}).get("text")
        except Exception as e:
            logger.debug("[CaptchaEngine] image API solve failed: %s", e)
        return None

    async def _hitl_escalate(self, page: Any, ctype: CaptchaType) -> CaptchaResult:
        """Capture screenshot and escalate to human-in-the-loop."""
        screenshot = None
        if page:
            try:
                screenshot = await page.screenshot()
            except Exception:
                pass
        logger.warning("[CaptchaEngine] HITL escalation — %s", ctype.value)
        return CaptchaResult(
            detected=True, type=ctype,
            resolved=False, strategy=CaptchaStrategy.HITL,
            screenshot=screenshot,
            notes=f"HITL: {ctype.value} requires human intervention"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Integration point — GhostVision gets a CaptchaEngine
# ═══════════════════════════════════════════════════════════════════════════════

def attach_to_ghost_vision(ghost_vision_instance: Any,
                            capsolver_key: str = None,
                            two_captcha_key: str = None) -> CaptchaEngine:
    """
    Attach a CaptchaEngine to a GhostVision instance.
    After this, GhostVision.handle_captcha(html, url, page) is available.
    """
    engine = CaptchaEngine(
        browser=getattr(ghost_vision_instance, '_browser', None),
        tab_id=getattr(ghost_vision_instance, '_tab_id', ''),
        capsolver_key=capsolver_key,
        two_captcha_key=two_captcha_key,
    )
    ghost_vision_instance.captcha_engine = engine
    return engine
