"""
PATCH-178: Automation Pre-Fight Engine — automation_prefight.py

Pre-fight is the intelligence gate that runs BEFORE any browser automation task.
It answers one question: "Which engine should handle this, and why?"

Decision tree:
  1. Probe target URL → detect captcha type
  2. Check engine availability (GhostController CDP, Playwright)
  3. Apply routing rules based on captcha type + engine capability matrix
  4. Return: AutomationMethod + confidence + rationale

PATCH-178 ROUTING PHILOSOPHY:
  Ghost is the default. Ghost IS a user.
  It drives real Chromium via CDP — real mouse coordinates, real keyboard events,
  real JS execution context, real browser fingerprint (TLS, canvas, fonts, WebGL).
  No webdriver marker. No automation flags. Behaviorally indistinguishable from human.

  Playwright is the fallback. It's a test tool that websites increasingly detect:
    - navigator.webdriver = true (patchable but suspicious)
    - Headless chrome signals in user-agent, permissions API
    - Canvas/WebGL fingerprint differs from real Chromium
    - CDP connection pattern is detectable

  Rules (in priority order):
    Ghost unavailable              → Playwright (only option)
    Both unavailable               → HITL (human takes over)
    Probe failed                   → Ghost (real fingerprint, conservative)
    Any captcha detected           → Ghost (real browser handles all types)
    High-value / login-gated site  → Ghost (real session, real cookies)
    No captcha, simple form        → Ghost (still better — real user behavior)
    Playwright explicitly preferred (future: per-recipe override)  → Playwright

  In practice: Ghost handles everything it can. Playwright only runs when
  Ghost is explicitly unavailable.

Murphy's Law applied: A fake browser will eventually be caught. Use the real one.
"""
from __future__ import annotations

import logging
import time
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Engine availability (checked once at import) ──────────────────────────

def _check_playwright() -> bool:
    try:
        from playwright.async_api import async_playwright  # noqa
        import os
        chromium = "/opt/Murphy-System/.cache/ms-playwright/chromium-1217/chrome-linux64/chrome"
        return os.path.exists(chromium)
    except ImportError:
        return False


def _check_ghost() -> bool:
    """Ghost = GhostBrowser (CDP) or GhostDesktopRunner (native automation)."""
    try:
        from murphy_native_automation import GhostDesktopRunner  # noqa
        return True
    except ImportError:
        pass
    try:
        from ghost_stripe_signup import GhostStripeSignup  # noqa
        return True
    except ImportError:
        pass
    return False


_PLAYWRIGHT_AVAILABLE: bool = _check_playwright()
_GHOST_AVAILABLE: bool = _check_ghost()


# ── Enums ──────────────────────────────────────────────────────────────────

class AutomationMethod(str, Enum):
    """The selected automation engine."""
    GHOST       = "ghost"        # CDP/real Chromium — GhostController (DEFAULT)
    PLAYWRIGHT  = "playwright"   # Playwright headless — fallback only
    HITL        = "hitl"         # Escalate to human — no engine can handle


class CaptchaProfile(str, Enum):
    """Captcha presence detected on target page."""
    NONE                = "none"
    HCAPTCHA            = "hcaptcha"
    RECAPTCHA_V2        = "recaptcha_v2"
    RECAPTCHA_V3        = "recaptcha_v3"
    CLOUDFLARE_TURNSTILE = "cloudflare_turnstile"
    GENERIC             = "generic"
    PROBE_FAILED        = "probe_failed"   # Couldn't reach URL — assume worst


# ── Data classes ───────────────────────────────────────────────────────────

@dataclass
class PreFightProbe:
    """Result of probing the target URL."""
    url: str
    reachable: bool
    captcha_profile: CaptchaProfile
    status_code: int = 0
    probe_time_ms: float = 0.0
    raw_signatures: list = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class PreFightDecision:
    """
    The routing decision produced by the pre-fight engine.

    method:         Which engine to use
    captcha:        What was detected on the target
    confidence:     0.0–1.0 — how confident the routing decision is
    rationale:      Human-readable explanation (for HITL / logging)
    ghost_ok:       Is GhostController available?
    playwright_ok:  Is Playwright available?
    probe:          Raw probe data
    """
    method: AutomationMethod
    captcha: CaptchaProfile
    confidence: float
    rationale: str
    ghost_ok: bool
    playwright_ok: bool
    probe: Optional[PreFightProbe] = None


# ── Captcha signatures (ordered by specificity) ──────────────────────────

_CAPTCHA_SIGS: Dict[CaptchaProfile, list] = {
    CaptchaProfile.CLOUDFLARE_TURNSTILE: [
        "challenges.cloudflare.com",
        "cf-turnstile",
        "turnstile/v0/api.js",
        "cf_clearance",
    ],
    CaptchaProfile.HCAPTCHA: [
        "hcaptcha.com/1/api.js",
        "h-captcha",
        "data-hcaptcha-sitekey",
        "hcaptcha.com",
    ],
    CaptchaProfile.RECAPTCHA_V3: [
        "grecaptcha.execute",
        "recaptcha/api.js?render=",
        "g-recaptcha-response",
    ],
    CaptchaProfile.RECAPTCHA_V2: [
        "g-recaptcha",
        "www.google.com/recaptcha",
        "recaptcha/api.js",
        "data-sitekey",
    ],
    CaptchaProfile.GENERIC: [
        "captcha",
        "i am not a robot",
        "bot check",
        "prove you're human",
        "security check",
    ],
}

_PRIORITY_ORDER = [
    CaptchaProfile.CLOUDFLARE_TURNSTILE,
    CaptchaProfile.HCAPTCHA,
    CaptchaProfile.RECAPTCHA_V3,
    CaptchaProfile.RECAPTCHA_V2,
    CaptchaProfile.GENERIC,
]


def _detect_captcha(html: str) -> Tuple[CaptchaProfile, list]:
    """Scan HTML for captcha signatures. Returns (type, matched_signatures)."""
    lower = html.lower()
    for ctype in _PRIORITY_ORDER:
        matched = [sig for sig in _CAPTCHA_SIGS[ctype] if sig.lower() in lower]
        if matched:
            return ctype, matched
    return CaptchaProfile.NONE, []


# ── URL probe ─────────────────────────────────────────────────────────────

def probe_url(url: str, timeout: float = 8.0) -> PreFightProbe:
    """
    Fetch the target URL and detect captcha profile.
    Uses a real browser user-agent to get the actual page JS/HTML.
    """
    t0 = time.monotonic()
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            html = resp.read(65536).decode("utf-8", errors="ignore")
            status = resp.status
    except urllib.error.HTTPError as e:
        try:
            html = e.read(32768).decode("utf-8", errors="ignore")
            status = e.code
        except Exception:
            html = ""
            status = e.code
    except Exception as exc:
        elapsed = (time.monotonic() - t0) * 1000
        return PreFightProbe(
            url=url,
            reachable=False,
            captcha_profile=CaptchaProfile.PROBE_FAILED,
            probe_time_ms=round(elapsed, 1),
            error=str(exc),
        )

    elapsed = (time.monotonic() - t0) * 1000
    captcha, sigs = _detect_captcha(html)

    return PreFightProbe(
        url=url,
        reachable=True,
        captcha_profile=captcha,
        status_code=status,
        probe_time_ms=round(elapsed, 1),
        raw_signatures=sigs,
    )


# ── Routing engine ────────────────────────────────────────────────────────

def select_method(probe: PreFightProbe) -> PreFightDecision:
    """
    PATCH-178: Core routing logic.

    Ghost is the default engine. It controls the browser exactly like a human:
      - Real CDP mouse events with randomised coordinates and movement curves
      - Real CDP keyboard input with inter-key timing jitter
      - Real Chromium JS context — hCaptcha, Turnstile, reCAPTCHA all run natively
      - Real browser fingerprint: TLS fingerprint, canvas hash, WebGL renderer,
        font metrics, audio context — indistinguishable from a live user
      - No navigator.webdriver flag, no automation markers
      - Real cookies, real session persistence, real browsing history

    Playwright is the fallback for when Ghost is unavailable:
      - Detectable automation markers even with stealth patches
      - Fake canvas/WebGL fingerprint vs real Chromium
      - Sites increasingly fingerprint headless Chromium at the JS level
      - Still useful as a last resort when Ghost is down

    Routing priority:
      1. Neither engine → HITL (no choice)
      2. Ghost unavailable → Playwright (only option, log the downgrade)
      3. Probe failed → Ghost (real fingerprint is safest assumption)
      4. Any captcha → Ghost (real browser solves all captcha types natively)
      5. No captcha → Ghost (still better — real user behavior, real events)
      6. Playwright only as explicit fallback
    """
    ghost_ok = _GHOST_AVAILABLE
    pw_ok    = _PLAYWRIGHT_AVAILABLE
    cap      = probe.captcha_profile

    # ── Priority 1: Neither engine available → HITL ───────────────────────
    if not ghost_ok and not pw_ok:
        return PreFightDecision(
            method=AutomationMethod.HITL,
            captcha=cap,
            confidence=1.0,
            rationale=(
                "HITL escalation: neither GhostController nor Playwright is available. "
                "Human must complete this task manually."
            ),
            ghost_ok=ghost_ok,
            playwright_ok=pw_ok,
            probe=probe,
        )

    # ── Priority 2: Ghost unavailable → Playwright fallback ───────────────
    if not ghost_ok:
        return PreFightDecision(
            method=AutomationMethod.PLAYWRIGHT,
            captcha=cap,
            confidence=0.60,
            rationale=(
                f"GhostController unavailable — Playwright fallback (captcha={cap.value}). "
                "WARNING: Playwright automation markers may be detected. "
                "Recommend investigating Ghost availability."
            ),
            ghost_ok=ghost_ok,
            playwright_ok=pw_ok,
            probe=probe,
        )

    # ── Priority 3: Probe failed → Ghost (conservative) ──────────────────
    if cap == CaptchaProfile.PROBE_FAILED:
        return PreFightDecision(
            method=AutomationMethod.GHOST,
            captcha=cap,
            confidence=0.80,
            rationale=(
                f"URL probe failed ({probe.error or 'unreachable'}) — "
                "GhostController selected as safe default: real browser fingerprint "
                "handles unknown captcha types and bot-detection without automation markers."
            ),
            ghost_ok=ghost_ok,
            playwright_ok=pw_ok,
            probe=probe,
        )

    # ── Priority 4: Any captcha → Ghost ───────────────────────────────────
    if cap == CaptchaProfile.HCAPTCHA:
        return PreFightDecision(
            method=AutomationMethod.GHOST,
            captcha=cap,
            confidence=0.98,
            rationale=(
                "hCaptcha detected. Ghost selected: hCaptcha JS runs in the real "
                "Chromium context and generates a genuine h-captcha-response token. "
                "Real mouse movement + real browser fingerprint passes behavioral checks."
            ),
            ghost_ok=ghost_ok,
            playwright_ok=pw_ok,
            probe=probe,
        )

    if cap == CaptchaProfile.CLOUDFLARE_TURNSTILE:
        return PreFightDecision(
            method=AutomationMethod.GHOST,
            captcha=cap,
            confidence=0.97,
            rationale=(
                "Cloudflare Turnstile detected. Ghost selected: Turnstile checks "
                "TLS fingerprint, canvas entropy, WebGL renderer, and browser history "
                "consistency — all genuine in GhostController's real Chromium instance."
            ),
            ghost_ok=ghost_ok,
            playwright_ok=pw_ok,
            probe=probe,
        )

    if cap in (CaptchaProfile.RECAPTCHA_V2, CaptchaProfile.RECAPTCHA_V3):
        return PreFightDecision(
            method=AutomationMethod.GHOST,
            captcha=cap,
            confidence=0.92,
            rationale=(
                f"{cap.value} detected. Ghost selected: reCAPTCHA risk scoring "
                "analyzes mouse movement patterns, click timing, scroll behavior, "
                "and browsing history — all real in GhostController. "
                "Ghost generates genuine low-risk scores vs Playwright's detectable patterns."
            ),
            ghost_ok=ghost_ok,
            playwright_ok=pw_ok,
            probe=probe,
        )

    if cap == CaptchaProfile.GENERIC:
        return PreFightDecision(
            method=AutomationMethod.GHOST,
            captcha=cap,
            confidence=0.90,
            rationale=(
                "Generic bot-detection signals detected. Ghost selected: "
                "real Chromium with real user events handles all behavioral checks. "
                "Unknown captcha type is safer to approach with a real browser."
            ),
            ghost_ok=ghost_ok,
            playwright_ok=pw_ok,
            probe=probe,
        )

    # ── Priority 5: No captcha → Ghost still preferred ────────────────────
    # Even without captcha, sites use JS fingerprinting, behavioral analysis,
    # honeypot fields, and timing checks. Ghost's real user model handles all of these.
    return PreFightDecision(
        method=AutomationMethod.GHOST,
        captcha=cap,
        confidence=0.93,
        rationale=(
            "No captcha detected. Ghost selected as default: "
            "real CDP mouse events, real keyboard timing, real browser fingerprint. "
            "Ghost acts exactly like a user — no automation markers, "
            "real JS execution, real cookies, real session state. "
            "Playwright reserved as fallback only."
        ),
        ghost_ok=ghost_ok,
        playwright_ok=pw_ok,
        probe=probe,
    )


# ── Public API ────────────────────────────────────────────────────────────

def run_prefight(url: str, timeout: float = 8.0) -> PreFightDecision:
    """
    PATCH-178: Entry point for all browser automation tasks.

    Ghost is the default. Playwright is the fallback.
    HITL is the last resort.

    1. Probe the target URL
    2. Detect captcha type
    3. Route to Ghost (default) or Playwright (fallback)
    4. Return decision with rationale

    Usage:
        decision = run_prefight("https://dashboard.stripe.com/register")
        if decision.method == AutomationMethod.GHOST:
            # use GhostStripeSignup / GhostController CDP
        elif decision.method == AutomationMethod.PLAYWRIGHT:
            # use PlaywrightSignupRunner (Ghost unavailable)
        else:
            # HITL escalate (nothing works)
    """
    logger.info("PATCH-178: pre-fight probe starting for %s", url)
    probe = probe_url(url, timeout=timeout)
    decision = select_method(probe)

    logger.info(
        "PATCH-178: pre-fight result — url=%s captcha=%s method=%s confidence=%.2f | %s",
        url,
        decision.captcha.value,
        decision.method.value,
        decision.confidence,
        decision.rationale[:80],
    )
    return decision


def prefight_status() -> dict:
    """Return engine availability for healthcheck / dashboard display."""
    return {
        "ghost_controller": _GHOST_AVAILABLE,
        "playwright": _PLAYWRIGHT_AVAILABLE,
        "engines_available": sum([_GHOST_AVAILABLE, _PLAYWRIGHT_AVAILABLE]),
        "default_engine": "ghost",
        "routing_active": True,
        "patch": "PATCH-178",
        "philosophy": "Ghost is the default. Playwright is the fallback. Ghost acts like a real user.",
    }
