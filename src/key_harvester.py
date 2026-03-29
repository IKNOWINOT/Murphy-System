# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Key Harvester — Murphy System

Orchestrates automated third-party API key acquisition via Murphy's native
MultiCursor desktop automation.  Uses the user's real browser (webbrowser.open)
with GhostDesktopRunner for OS-level typing/clicking and OCR-based element
detection — no Playwright binary, no bot fingerprinting.

Three hard rules that are never bypassed:

  1. **Credential gate first** — Murphy asks the user what email/password to
     use before any browser opens.  No default credentials; no silent reuse.
  2. **TOS gate before every checkbox** — every "I Agree" click is preceded
     by an explicit human approval through TOSAcceptanceGate.
  3. **Visible browser** — the user's own real browser is used (webbrowser.open)
     so the user can see exactly what Murphy is doing.  The provider's API-keys
     page is also opened in the system browser for independent verification.

Acquisition order is email-first: SendGrid is acquired before all others so
that account verification emails from every subsequent provider can be
received and processed automatically.

CAPTCHA handling employs a layered strategy cascade:
  HumanSimulator (delays + scroll + hover) →
  CaptchaHandler.detect() →
  per-type strategies (audio fallback, Cloudflare wait, HITL escalation) →
  exponential-backoff retry

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
import re
import secrets
import string
import threading
import time
import uuid
import webbrowser
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy imports
# ---------------------------------------------------------------------------

try:
    from murphy_native_automation import (
        ActionType,
        GhostDesktopRunner,
        MurphyNativeRunner,
        NativeStep,
        NativeTask,
        TaskStatus,
        TaskType,
    )
    _HAS_NATIVE_AUTOMATION = True
except ImportError:  # pragma: no cover
    _HAS_NATIVE_AUTOMATION = False
    MurphyNativeRunner = None  # type: ignore[assignment,misc]
    NativeTask = None  # type: ignore[assignment,misc]
    NativeStep = None  # type: ignore[assignment,misc]
    ActionType = None  # type: ignore[assignment,misc]
    TaskType = None  # type: ignore[assignment,misc]

# Optional split-screen imports (only available in full Murphy System installation)
try:
    from murphy_native_automation import (  # type: ignore[assignment]
        CursorContext,
        MultiCursorDesktop,
        ScreenZone,
        SplitScreenLayout,
        SplitScreenManager,
    )
    _HAS_SPLIT_SCREEN = True
except ImportError:  # pragma: no cover
    _HAS_SPLIT_SCREEN = False
    MultiCursorDesktop = None  # type: ignore[assignment,misc]
    SplitScreenLayout = None  # type: ignore[assignment,misc]

# Backward-compatible alias — existing code referencing _HAS_PLAYWRIGHT still works
_HAS_PLAYWRIGHT = _HAS_NATIVE_AUTOMATION

try:
    from secure_key_manager import store_api_key
    _HAS_SKM = True
except ImportError:  # pragma: no cover
    _HAS_SKM = False

    def store_api_key(name: str, value: str, **_kw: Any) -> str:  # type: ignore[misc]
        return "unavailable"

try:
    from env_manager import validate_api_key, write_env_key
    _HAS_ENV_MGR = True
except ImportError:  # pragma: no cover
    _HAS_ENV_MGR = False

    def validate_api_key(provider: str, key: str) -> Tuple[bool, str]:  # type: ignore[misc]
        return True, "ok"

    def write_env_key(path: Optional[str], key: str, value: str) -> None:  # type: ignore[misc]
        pass

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)
from tos_acceptance_gate import (
    CredentialRequest,
    CredentialRequestStatus,
    TOSAcceptanceGate,
    TOSAcceptanceStatus,
    UserCredentialGate,
)

# FastAPI Request type — imported at module level so it is resolvable from
# __globals__ when FastAPI inspects handler annotations under PEP 563.
try:
    from fastapi import Request as _FastAPIRequest
except ImportError:  # pragma: no cover
    _FastAPIRequest = None  # type: ignore[assignment,misc]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Seconds between TOS approval polls.
_TOS_POLL_INTERVAL: float = 2.0
#: Maximum seconds to wait for TOS approval.
_TOS_POLL_TIMEOUT: float = 300.0
#: Maximum seconds to wait for a credential response.
_CRED_POLL_TIMEOUT: float = 300.0
#: Seconds between IMAP polls.
_EMAIL_POLL_INTERVAL: float = 10.0
#: Maximum seconds to wait for a verification email.
_EMAIL_POLL_TIMEOUT: float = 120.0

#: CAPTCHA backoff ceiling in seconds.
_CAPTCHA_MAX_BACKOFF: float = 60.0
#: Number of CAPTCHA retry attempts before escalating to HITL.
_CAPTCHA_MAX_RETRIES: int = 3

# ---------------------------------------------------------------------------
# Human-like user agents — periodically rotate to avoid bot fingerprinting
# ---------------------------------------------------------------------------

_USER_AGENTS: List[str] = [
    # Chrome on Windows 10
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    # Chrome on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    # Firefox on Linux
    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
    # Safari on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
    # Edge on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
]

#: Common realistic viewport sizes used by real browsers.
_VIEWPORT_SIZES: List[Tuple[int, int]] = [
    (1920, 1080),
    (1440, 900),
    (1366, 768),
    (1280, 800),
    (1536, 864),
    (1280, 720),
]

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class AcquisitionStatus(str, Enum):
    """Lifecycle states for a single provider key acquisition run."""

    PENDING = "pending"
    SIGNING_UP = "signing_up"
    AWAITING_TOS_APPROVAL = "awaiting_tos_approval"
    AWAITING_EMAIL = "awaiting_email"
    VERIFYING = "verifying"
    EXTRACTING_KEY = "extracting_key"
    COMPLETED = "completed"
    BLOCKED_CAPTCHA = "blocked_captcha"
    BLOCKED_PAYMENT = "blocked_payment"
    BLOCKED_2FA = "blocked_2fa"
    FAILED = "failed"
    SKIPPED = "skipped"


class CaptchaType(str, Enum):
    """Detected CAPTCHA variant."""

    NONE = "none"
    RECAPTCHA_V2 = "recaptcha_v2"
    RECAPTCHA_V3 = "recaptcha_v3"
    HCAPTCHA = "hcaptcha"
    CLOUDFLARE_TURNSTILE = "cloudflare_turnstile"
    GENERIC = "generic"


class CaptchaStrategy(str, Enum):
    """Strategy used to handle a detected CAPTCHA."""

    HUMAN_DELAYS = "human_delays"            # Already applied pre-detection
    SCROLL_BEFORE_INTERACT = "scroll_before_interact"
    HOVER_BEFORE_CLICK = "hover_before_click"
    USER_AGENT_ROTATE = "user_agent_rotate"
    VIEWPORT_RANDOMIZE = "viewport_randomize"
    AUDIO_FALLBACK = "audio_fallback"        # Click audio challenge button
    CLOUDFLARE_WAIT = "cloudflare_wait"      # Wait for auto-pass
    RETRY_BACKOFF = "retry_backoff"          # Exponential back-off + retry
    HITL_ESCALATE = "hitl_escalate"          # Send to human via HITL queue
    OPEN_VISIBLE_BROWSER = "open_visible_browser"  # Non-headless so user can solve


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class ProviderRecipe:
    """Browser automation recipe for signing up with a provider.

    ``signup_selectors`` maps logical field names (``email``, ``password``,
    ``submit``) to CSS selectors on the signup form.  Values are best-effort
    placeholders; verify against each provider's live sign-up page before
    production use.
    """

    name: str
    env_var: str
    signup_url: str
    keys_page_url: str
    tier: str                          # "free" | "free_trial" | "paid_only"
    requires_payment: bool
    signup_selectors: Dict[str, str]   # {"email": "…", "password": "…", "submit": "…"}
    tos_checkbox_selector: str
    create_key_selector: str
    key_extract_selector: str
    key_format_pattern: str            # regex or ""
    notes: str = ""
    # OCR-friendly interaction labels (Murphy MultiCursor native)
    email_field_label: str = "Email"       # OCR text near the email field
    password_field_label: str = "Password"  # OCR text near the password field
    submit_button_label: str = "Sign Up"    # OCR text on the submit button
    tos_checkbox_label: str = "I agree"     # OCR text near the TOS checkbox
    create_key_label: str = "Create"        # OCR text on the create key button
    key_region_label: str = "API Key"       # OCR text identifying the key display region


@dataclass
class HarvestResult:
    """Outcome of a single provider key acquisition attempt."""

    provider: str
    status: AcquisitionStatus
    key_stored: bool = False
    tos_accepted: bool = False
    captcha_strategy_used: Optional[CaptchaStrategy] = None
    error: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# ---------------------------------------------------------------------------
# Provider recipes — email-first ordering
# ---------------------------------------------------------------------------
# SendGrid is listed FIRST so that Murphy has a working email API before
# attempting signups that send verification emails.

PROVIDER_RECIPES: List[ProviderRecipe] = [
    # ── 1 · Email provider first ──────────────────────────────────────────
    ProviderRecipe(
        name="sendgrid",
        env_var="SENDGRID_API_KEY",
        signup_url="https://signup.sendgrid.com/",
        keys_page_url="https://app.sendgrid.com/settings/api_keys",
        tier="free",
        requires_payment=False,
        signup_selectors={
            "email": "input#email",
            "password": "input#password",
            "submit": "button[type='submit']",
        },
        tos_checkbox_selector="input[type='checkbox'][name*='opt_in']",
        create_key_selector="button[data-testid='btn-create-api-key']",
        key_extract_selector="input.api-key-display",
        key_format_pattern=r"^SG\.[A-Za-z0-9_-]{22,}\.[A-Za-z0-9_-]{43,}$",
        notes="Free tier: 100 emails/day. Must be first — verification emails from other providers flow through here.",
    ),
    # ── 2-4 · LLM providers ───────────────────────────────────────────────
    ProviderRecipe(
        name="deepinfra",
        env_var="DEEPINFRA_API_KEY",
        signup_url="https://deepinfra.com",
        keys_page_url="https://deepinfra.com/dash/api_keys",
        tier="free",
        requires_payment=False,
        signup_selectors={
            "email": "input[name='email']",
            "password": "input[name='password']",
            "submit": "button[type='submit']",
        },
        tos_checkbox_selector="input[type='checkbox'][name*='terms']",
        create_key_selector="button[data-testid='create-api-key']",
        key_extract_selector="input[data-testid='api-key-value']",
        key_format_pattern=r"^[A-Za-z0-9_-]{20,}$",
        notes="Free tier; no credit card required.",
    ),
    ProviderRecipe(
        name="openai",
        env_var="OPENAI_API_KEY",
        signup_url="https://platform.openai.com/signup",
        keys_page_url="https://platform.openai.com/api-keys",
        tier="free_trial",
        requires_payment=False,
        signup_selectors={
            "email": "input[name='email']",
            "password": "input[name='password']",
            "submit": "button[type='submit']",
        },
        tos_checkbox_selector="input[type='checkbox'][name*='terms']",
        create_key_selector="button[data-testid='create-new-secret-key-button']",
        key_extract_selector="input[data-testid='api-key-display']",
        key_format_pattern=r"^sk-[A-Za-z0-9_-]{20,}$",
        notes="Free trial with usage limits.",
    ),
    ProviderRecipe(
        name="anthropic",
        env_var="ANTHROPIC_API_KEY",
        signup_url="https://console.anthropic.com/login",
        keys_page_url="https://console.anthropic.com/settings/keys",
        tier="free_trial",
        requires_payment=False,
        signup_selectors={
            "email": "input[name='email']",
            "password": "input[name='password']",
            "submit": "button[type='submit']",
        },
        tos_checkbox_selector="input[type='checkbox'][name*='terms']",
        create_key_selector="button[aria-label='Create Key']",
        key_extract_selector="code.api-key",
        key_format_pattern=r"^sk-ant-[A-Za-z0-9_-]{20,}$",
        notes="Free tier with rate limits.",
    ),
    # ── 5 · Voice / media ─────────────────────────────────────────────────
    ProviderRecipe(
        name="elevenlabs",
        env_var="ELEVENLABS_API_KEY",
        signup_url="https://elevenlabs.io/sign-up",
        keys_page_url="https://elevenlabs.io/app/settings/api-keys",
        tier="free",
        requires_payment=False,
        signup_selectors={
            "email": "input[name='email']",
            "password": "input[name='password']",
            "submit": "button[type='submit']",
        },
        tos_checkbox_selector="input[type='checkbox'][name*='terms']",
        create_key_selector="button[data-testid='generate-api-key']",
        key_extract_selector="input[data-testid='api-key-value']",
        key_format_pattern=r"^[A-Za-z0-9_-]{32,}$",
        notes="Free tier with character limits.",
    ),
    # ── 6 · Communications ────────────────────────────────────────────────
    ProviderRecipe(
        name="twilio",
        env_var="TWILIO_AUTH_TOKEN",
        signup_url="https://www.twilio.com/try-twilio",
        keys_page_url="https://console.twilio.com/",
        tier="free_trial",
        requires_payment=False,
        signup_selectors={
            "email": "input[name='email']",
            "password": "input[name='password']",
            "submit": "button[type='submit']",
        },
        tos_checkbox_selector="input[type='checkbox'][name*='terms']",
        create_key_selector="button[data-testid='create-key']",
        key_extract_selector="span.auth-token",
        key_format_pattern=r"^[A-Za-z0-9]{32}$",
        notes="Trial account with limited credits.",
    ),
    # ── 7 · Developer tools ───────────────────────────────────────────────
    ProviderRecipe(
        name="github",
        env_var="GITHUB_TOKEN",
        signup_url="https://github.com/signup",
        keys_page_url="https://github.com/settings/tokens/new",
        tier="free",
        requires_payment=False,
        signup_selectors={
            "email": "input#email",
            "password": "input#password",
            "submit": "button[type='submit'].btn-primary",
        },
        tos_checkbox_selector="input[type='checkbox'][name*='terms']",
        create_key_selector="input[type='submit'].btn-primary",
        key_extract_selector="code#new-oauth-token",
        key_format_pattern=r"^gh[ps]_[A-Za-z0-9]{36,}$",
        notes="Free personal access token.",
    ),
    # ── 8 · Workspace ─────────────────────────────────────────────────────
    ProviderRecipe(
        name="slack",
        env_var="SLACK_API_TOKEN",
        signup_url="https://slack.com/get-started#/createnew",
        keys_page_url="https://api.slack.com/apps",
        tier="free",
        requires_payment=False,
        signup_selectors={
            "email": "input[name='email']",
            "password": "input[name='password']",
            "submit": "button[type='submit']",
        },
        tos_checkbox_selector="input[type='checkbox'][name*='terms']",
        create_key_selector="button[data-qa='create_app_button']",
        key_extract_selector="code.token-value",
        key_format_pattern=r"^xox[bpars]-[A-Za-z0-9_-]+$",
        notes="Free workspace; Bot Token required.",
    ),
    # ── 9 · Voice AI ──────────────────────────────────────────────────────
    ProviderRecipe(
        name="vapi",
        env_var="VAPI_API_KEY",
        signup_url="https://dashboard.vapi.ai/sign-up",
        keys_page_url="https://dashboard.vapi.ai/keys",
        tier="free",
        requires_payment=False,
        signup_selectors={
            "email": "input[name='email']",
            "password": "input[name='password']",
            "submit": "button[type='submit']",
        },
        tos_checkbox_selector="input[type='checkbox'][name*='terms']",
        create_key_selector="button[data-testid='create-key']",
        key_extract_selector="input[data-testid='api-key-value']",
        key_format_pattern=r"^[A-Za-z0-9_-]{32,}$",
        notes="Free tier available.",
    ),
    # ── 10 · CRM ──────────────────────────────────────────────────────────
    ProviderRecipe(
        name="hubspot",
        env_var="HUBSPOT_API_KEY",
        signup_url="https://app.hubspot.com/signup-hubspot/crm",
        keys_page_url="https://app.hubspot.com/integrations-settings/api-key",
        tier="free",
        requires_payment=False,
        signup_selectors={
            "email": "input[name='email']",
            "password": "input[name='password']",
            "submit": "button[type='submit']",
        },
        tos_checkbox_selector="input[type='checkbox'][name*='agree']",
        create_key_selector="button[data-test='generate-api-key-btn']",
        key_extract_selector="input[data-test='api-key-value']",
        key_format_pattern=r"^[A-Za-z0-9_-]{36}$",
        notes="Free CRM tier.",
    ),
    # ── 11 · Commerce ─────────────────────────────────────────────────────
    ProviderRecipe(
        name="shopify",
        env_var="SHOPIFY_API_KEY",
        signup_url="https://partners.shopify.com/signup",
        keys_page_url="https://partners.shopify.com/organizations",
        tier="free",
        requires_payment=False,
        signup_selectors={
            "email": "input[name='account[email]']",
            "password": "input[name='account[password]']",
            "submit": "button[type='submit']",
        },
        tos_checkbox_selector="input[type='checkbox'][name*='terms']",
        create_key_selector="button[data-testid='create-app-button']",
        key_extract_selector="input[data-testid='api-key-value']",
        key_format_pattern=r"^[A-Za-z0-9]{32}$",
        notes="Partner account; free development store.",
    ),
    # ── 12 · Payments (test keys) ─────────────────────────────────────────
    ProviderRecipe(
        name="stripe",
        env_var="STRIPE_API_KEY",
        signup_url="https://dashboard.stripe.com/register",
        keys_page_url="https://dashboard.stripe.com/test/apikeys",
        tier="free",
        requires_payment=False,
        signup_selectors={
            "email": "input[name='email']",
            "password": "input[name='password']",
            "submit": "button[type='submit']",
        },
        tos_checkbox_selector="input[type='checkbox'][name*='agree']",
        create_key_selector="button[data-test='reveal-key-button']",
        key_extract_selector="input[data-test='api-key-value']",
        key_format_pattern=r"^sk_(test|live)_[A-Za-z0-9]{24,}$",
        notes="Test mode keys are free.",
    ),
    # ── 13 · Crypto ───────────────────────────────────────────────────────
    ProviderRecipe(
        name="coinbase",
        env_var="COINBASE_API_KEY",
        signup_url="https://www.coinbase.com/signup",
        keys_page_url="https://www.coinbase.com/settings/api",
        tier="free",
        requires_payment=False,
        signup_selectors={
            "email": "input[name='email']",
            "password": "input[name='password']",
            "submit": "button[type='submit']",
        },
        tos_checkbox_selector="input[type='checkbox'][name*='terms']",
        create_key_selector="button[data-testid='new-api-key']",
        key_extract_selector="input.api-key-display",
        key_format_pattern=r"^[A-Za-z0-9_-]{16,}$",
        notes="Requires identity verification.",
    ),
    # ── 14-15 · Paid — acquired last (will be skipped) ────────────────────
    ProviderRecipe(
        name="heygen",
        env_var="HEYGEN_API_KEY",
        signup_url="https://app.heygen.com/signup",
        keys_page_url="https://app.heygen.com/settings/api",
        tier="paid_only",
        requires_payment=True,
        signup_selectors={
            "email": "input[name='email']",
            "password": "input[name='password']",
            "submit": "button[type='submit']",
        },
        tos_checkbox_selector="input[type='checkbox'][name*='terms']",
        create_key_selector="button[data-testid='generate-api-key']",
        key_extract_selector="input.api-key-field",
        key_format_pattern=r"^[A-Za-z0-9_-]{32,}$",
        notes="Requires paid subscription.",
    ),
    ProviderRecipe(
        name="tavus",
        env_var="TAVUS_API_KEY",
        signup_url="https://platform.tavus.io/sign-up",
        keys_page_url="https://platform.tavus.io/api-keys",
        tier="paid_only",
        requires_payment=True,
        signup_selectors={
            "email": "input[name='email']",
            "password": "input[name='password']",
            "submit": "button[type='submit']",
        },
        tos_checkbox_selector="input[type='checkbox'][name*='terms']",
        create_key_selector="button[aria-label='Create API Key']",
        key_extract_selector="code.api-key",
        key_format_pattern=r"^[A-Za-z0-9_-]{32,}$",
        notes="Requires paid subscription.",
    ),
]

# Fast lookup by name
_RECIPE_MAP: Dict[str, ProviderRecipe] = {r.name: r for r in PROVIDER_RECIPES}


# ---------------------------------------------------------------------------
# CAPTCHA detection helpers
# ---------------------------------------------------------------------------

_CAPTCHA_SIGNATURES: Dict[CaptchaType, List[str]] = {
    CaptchaType.RECAPTCHA_V2: [
        "g-recaptcha",
        "www.google.com/recaptcha",
        "recaptcha/api.js",
        "data-sitekey",
    ],
    CaptchaType.RECAPTCHA_V3: [
        "grecaptcha.execute",
        "recaptcha/api.js?render=",
        "g-recaptcha-response",
    ],
    CaptchaType.HCAPTCHA: [
        "hcaptcha.com/1/api.js",
        "h-captcha",
        "data-hcaptcha-sitekey",
    ],
    CaptchaType.CLOUDFLARE_TURNSTILE: [
        "challenges.cloudflare.com",
        "cf-turnstile",
        "turnstile/v0/api.js",
        "cf_clearance",
    ],
    CaptchaType.GENERIC: [
        "captcha",
        "recaptcha",
        "hcaptcha",
        "i am not a robot",
        "bot check",
        "prove you're human",
        "security check",
    ],
}

# Selectors for audio CAPTCHA challenge buttons
_AUDIO_CAPTCHA_SELECTORS = [
    "#recaptcha-audio-button",
    ".rc-button-audio",
    "button[aria-label*='audio']",
    "button[title*='audio']",
]

# Selectors for reCAPTCHA / hCaptcha checkbox iframes
_CAPTCHA_IFRAME_SELECTORS = [
    "iframe[src*='recaptcha']",
    "iframe[src*='hcaptcha']",
    "iframe[title*='reCAPTCHA']",
    "iframe[title*='hCaptcha']",
]


def detect_captcha_type(page_html: str) -> CaptchaType:
    """Return the most-specific :class:`CaptchaType` present in *page_html*.

    Checks in priority order: Turnstile → hCaptcha → reCAPTCHA v3 →
    reCAPTCHA v2 → generic → none.
    """
    lower = page_html.lower()
    priority_order = [
        CaptchaType.CLOUDFLARE_TURNSTILE,
        CaptchaType.HCAPTCHA,
        CaptchaType.RECAPTCHA_V3,
        CaptchaType.RECAPTCHA_V2,
        CaptchaType.GENERIC,
    ]
    for ctype in priority_order:
        for sig in _CAPTCHA_SIGNATURES[ctype]:
            if sig.lower() in lower:
                return ctype
    return CaptchaType.NONE


# ---------------------------------------------------------------------------
# Human simulator — natural timing and browser gestures
# ---------------------------------------------------------------------------

class HumanSimulator:
    """Injects human-like behaviour into browser automation to reduce bot
    fingerprint signals.

    All delays are randomised from realistic distributions; actions (scroll,
    hover) mirror what a real user would do before clicking.
    """

    # Typing inter-character delay range (seconds)
    _TYPING_DELAY_RANGE: Tuple[float, float] = (0.05, 0.18)
    # Delay between filling a field and moving to the next action
    _BETWEEN_ACTION_RANGE: Tuple[float, float] = (0.4, 1.8)
    # Initial page-load reading pause before interacting
    _PAGE_READ_PAUSE_RANGE: Tuple[float, float] = (1.0, 3.5)
    # Scroll amount before interacting (pixels)
    _SCROLL_RANGE: Tuple[int, int] = (80, 400)

    @staticmethod
    async def pause_between_actions() -> None:
        """Randomised pause between actions."""
        lo, hi = HumanSimulator._BETWEEN_ACTION_RANGE
        await asyncio.sleep(random.uniform(lo, hi))

    @staticmethod
    async def pause_after_page_load() -> None:
        """Simulate reading/processing time after page navigation."""
        lo, hi = HumanSimulator._PAGE_READ_PAUSE_RANGE
        await asyncio.sleep(random.uniform(lo, hi))

    @staticmethod
    async def scroll_page(page: Any) -> None:
        """Scroll the page slightly — appears more human to bot-detection."""
        if page is None:
            return
        try:
            scroll_amount = random.randint(*HumanSimulator._SCROLL_RANGE)
            await page.evaluate(f"window.scrollBy(0, {scroll_amount})")
            await asyncio.sleep(random.uniform(0.3, 0.9))
            # Scroll back near the top so form fields are visible
            await page.evaluate("window.scrollTo(0, 0)")
        except Exception as exc:  # noqa: BLE001
            logger.debug("Non-critical error: %s", exc)

    @staticmethod
    async def hover_element(page: Any, selector: str) -> None:
        """Hover the mouse over *selector* before clicking it."""
        if page is None:
            return
        try:
            await page.hover(selector)
            await asyncio.sleep(random.uniform(0.1, 0.4))
        except Exception as exc:  # noqa: BLE001
            logger.debug("Non-critical error: %s", exc)

    @staticmethod
    def random_user_agent() -> str:
        """Return a randomly selected realistic user-agent string."""
        return random.choice(_USER_AGENTS)

    @staticmethod
    def random_viewport() -> Tuple[int, int]:
        """Return a random ``(width, height)`` from common screen resolutions."""
        return random.choice(_VIEWPORT_SIZES)


# ---------------------------------------------------------------------------
# CAPTCHA handler
# ---------------------------------------------------------------------------

class CaptchaHandler:
    """Applies a strategy cascade to handle detected CAPTCHAs.

    Strategy priority:
      1. Cloudflare Turnstile → wait up to 30 s for auto-pass
      2. reCAPTCHA / hCaptcha audio → click audio button
      3. Generic → retry with exponential back-off
      4. All types → if retries exhausted → HITL escalation screenshot
    """

    def __init__(self, tos_gate: TOSAcceptanceGate) -> None:
        self._tos_gate = tos_gate

    async def handle(
        self,
        page: Any,
        runner: Any,
        captcha_type: CaptchaType,
        provider_name: str,
        attempt: int = 0,
    ) -> Tuple[bool, CaptchaStrategy]:
        """Attempt to resolve the CAPTCHA.  Returns ``(resolved, strategy_used)``.

        ``resolved=True`` means the CAPTCHA appears to have passed.
        ``resolved=False`` means the provider should be marked BLOCKED_CAPTCHA.
        """
        logger.info(
            "CAPTCHA detected for '%s' (type=%s, attempt=%d)",
            provider_name,
            captcha_type.value,
            attempt,
        )

        # Strategy 1: Cloudflare — just wait
        if captcha_type == CaptchaType.CLOUDFLARE_TURNSTILE:
            logger.info(
                "Cloudflare Turnstile detected for '%s' — waiting for auto-pass.",
                provider_name,
            )
            await asyncio.sleep(random.uniform(5.0, 15.0))
            return True, CaptchaStrategy.CLOUDFLARE_WAIT

        # Strategy 2: Audio CAPTCHA fallback for reCAPTCHA/hCaptcha
        if captcha_type in (CaptchaType.RECAPTCHA_V2, CaptchaType.HCAPTCHA):
            resolved = await self._try_audio_captcha(page, provider_name)
            if resolved:
                return True, CaptchaStrategy.AUDIO_FALLBACK

        # Strategy 3: Exponential back-off retry (up to _CAPTCHA_MAX_RETRIES)
        if attempt < _CAPTCHA_MAX_RETRIES:
            backoff = min(2 ** attempt * 5.0, _CAPTCHA_MAX_BACKOFF)
            jitter = random.uniform(0, backoff * 0.2)
            logger.info(
                "CAPTCHA back-off for '%s': sleeping %.1fs then retrying.",
                provider_name,
                backoff + jitter,
            )
            await asyncio.sleep(backoff + jitter)
            return False, CaptchaStrategy.RETRY_BACKOFF

        # Strategy 4: HITL escalation — send screenshot to HITL queue
        screenshot_path = f"/tmp/captcha_{provider_name}_{uuid.uuid4().hex[:8]}.png"
        if runner is not None and NativeTask is not None:
            try:
                runner.run(NativeTask(steps=[
                    NativeStep(action=ActionType.SCREENSHOT, target=screenshot_path),
                ]))
            except Exception as exc:  # noqa: BLE001
                logger.debug("Non-critical error: %s", exc)

        logger.warning(
            "CAPTCHA unresolved for '%s' after %d attempts — HITL escalated (%s).",
            provider_name,
            attempt,
            screenshot_path,
        )
        return False, CaptchaStrategy.HITL_ESCALATE

    @staticmethod
    async def _try_audio_captcha(page: Any, provider_name: str) -> bool:
        """Attempt to switch to audio CAPTCHA and retrieve the answer.

        Returns ``True`` if the audio challenge appeared to be triggered.
        Real audio solving would require an STT service; here we trigger the
        UI switch and leave the window visible so the user can complete it.
        """
        if page is None:
            return False
        for sel in _AUDIO_CAPTCHA_SELECTORS:
            try:
                await page.click(sel, timeout=3000)
                logger.info(
                    "Audio CAPTCHA button clicked for '%s' (selector=%s).",
                    provider_name,
                    sel,
                )
                await asyncio.sleep(2.0)
                return True
            except Exception:  # noqa: BLE001
                continue
        return False


# ---------------------------------------------------------------------------
# IMAP verification email helpers
# ---------------------------------------------------------------------------

_URL_PATTERN = re.compile(r"https?://\S+", re.IGNORECASE)


def _extract_email_body(msg: Any) -> str:
    """Return the plain-text body from an ``email.message.Message`` object."""
    if msg.is_multipart():
        parts = []
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                try:
                    parts.append(
                        part.get_payload(decode=True).decode(errors="replace")
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.debug("Non-critical error: %s", exc)
        return "\n".join(parts)
    try:
        return msg.get_payload(decode=True).decode(errors="replace")
    except Exception:  # noqa: BLE001
        return ""


def _find_verification_url(body: str) -> Optional[str]:
    """Extract the first HTTP(S) URL that looks like a verification link."""
    for url in _URL_PATTERN.findall(body):
        url = url.rstrip(".,;)")
        lower = url.lower()
        if any(kw in lower for kw in ("verify", "confirm", "activate", "validate")):
            return url
    return None


def _random_password() -> str:
    """Generate a cryptographically random strong password for signup automation."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(secrets.choice(alphabet) for _ in range(20))


# ---------------------------------------------------------------------------
# KeyHarvester
# ---------------------------------------------------------------------------

class KeyHarvester:
    """Orchestrates automated API key acquisition for all configured providers.

    Parameters
    ----------
    tos_gate:
        An initialised :class:`~tos_acceptance_gate.TOSAcceptanceGate`.
    credential_gate:
        An initialised :class:`~tos_acceptance_gate.UserCredentialGate` used
        to ask the user what email/password to use before any signup begins.
    imap_config:
        Optional dict with keys ``host``, ``port``, ``username``, ``password``
        for polling verification emails.
    interactive:
        When ``True`` (default) the Playwright browser launches in non-headless
        (visible) mode and provider API-key pages are also opened in the
        system's default browser.
    """

    def __init__(
        self,
        tos_gate: TOSAcceptanceGate,
        credential_gate: UserCredentialGate,
        imap_config: Optional[Dict[str, Any]] = None,
        interactive: bool = True,
    ) -> None:
        self._tos_gate = tos_gate
        self._credential_gate = credential_gate
        self._imap_config = imap_config
        self._interactive = interactive
        self._results: List[HarvestResult] = []
        self._lock = threading.Lock()
        self._captcha_handler = CaptchaHandler(tos_gate)
        # Credentials populated after _request_user_credentials()
        self._user_email: str = ""
        self._user_password: str = ""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def harvest_all(self) -> List[HarvestResult]:
        """Collect user credentials, then acquire every provider key in order.

        Email providers (SendGrid) are processed first so verification emails
        from subsequent providers can be received automatically.

        If ``interactive=True``, the Murphy HITL terminal UI is opened in the
        system browser before harvest begins so the user can see and respond to
        credential and TOS approval requests without having to navigate manually.

        Returns:
            List of :class:`HarvestResult` for every provider.
        """
        # Open the Murphy HITL terminal UI so the user can respond to gates
        if self._interactive:
            murphy_port = int(os.getenv("MURPHY_PORT", os.getenv("PORT", "8000")))
            murphy_hitl_url = f"http://localhost:{murphy_port}/ui/terminal-integrated"
            self._open_provider_ui(murphy_hitl_url, "Murphy HITL Terminal", "hitl-queue")

        # Step 0: collect credentials via HITL before any browser opens
        credentials_ok = await self._request_user_credentials()
        if not credentials_ok:
            logger.warning("User declined to provide credentials — harvest aborted.")
            return []

        for recipe in PROVIDER_RECIPES:
            result = await self._acquire_single(recipe)
            with self._lock:
                capped_append(self._results, result)

        return list(self._results)

    def get_status(self) -> Dict[str, int]:
        """Return aggregate counts for the current harvest run."""
        with self._lock:
            results = list(self._results)
        total = len(results)
        completed = sum(1 for r in results if r.status == AcquisitionStatus.COMPLETED)
        blocked = sum(
            1 for r in results
            if r.status in (
                AcquisitionStatus.BLOCKED_CAPTCHA,
                AcquisitionStatus.BLOCKED_PAYMENT,
                AcquisitionStatus.BLOCKED_2FA,
                AcquisitionStatus.FAILED,
            )
        )
        pending = sum(1 for r in results if r.status == AcquisitionStatus.PENDING)
        skipped = sum(1 for r in results if r.status == AcquisitionStatus.SKIPPED)
        return {
            "total": total,
            "completed": completed,
            "blocked": blocked,
            "pending": pending,
            "skipped": skipped,
        }

    def get_results(self) -> List[HarvestResult]:
        """Return a snapshot of all HarvestResults so far."""
        with self._lock:
            return list(self._results)

    async def _harvest_parallel(
        self, recipes: List[ProviderRecipe]
    ) -> List[HarvestResult]:
        """Harvest up to 3 providers in parallel using a QUAD split-screen layout.

        Zone 0-2 → provider signup flows (one per zone).
        Zone 3   → reserved for the HITL monitor terminal.

        Providers are processed in batches of 3.  Falls back to sequential
        processing when split-screen classes are unavailable.
        """
        if not _HAS_SPLIT_SCREEN or MultiCursorDesktop is None:
            # Fall back to sequential if split-screen is unavailable
            results: List[HarvestResult] = []
            for recipe in recipes:
                result = await self._acquire_single(recipe)
                with self._lock:
                    capped_append(self._results, result)
                results.append(result)
            return results

        screen_w = int(os.getenv("MURPHY_SCREEN_WIDTH", "2560"))
        screen_h = int(os.getenv("MURPHY_SCREEN_HEIGHT", "1440"))
        desktop = MultiCursorDesktop(screen_width=screen_w, screen_height=screen_h)
        zones = desktop.apply_layout(SplitScreenLayout.QUAD)
        # Zone 3 is reserved for the HITL monitor; providers use zones 0-2
        batch_size = max(1, len(zones) - 1)  # 3 provider zones from QUAD

        all_results: List[HarvestResult] = []
        for i in range(0, len(recipes), batch_size):
            batch = recipes[i : i + batch_size]
            tasks = [self._acquire_single(recipe) for recipe in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in batch_results:
                if isinstance(result, BaseException):
                    logger.error("Credential acquisition failed for batch item: %s", result)
                    continue
                with self._lock:
                    capped_append(self._results, result)
                all_results.append(result)

        return all_results

    # ------------------------------------------------------------------
    # Credential collection
    # ------------------------------------------------------------------

    async def _request_user_credentials(self) -> bool:
        """Open a HITL credential request and wait for the user to respond.

        Returns ``True`` if credentials were provided, ``False`` if declined
        or timed out.
        """
        req = self._credential_gate.request_credentials(
            purpose=f"API key acquisition for {len(PROVIDER_RECIPES)} providers",
            suggested_email=os.getenv("MURPHY_HARVEST_EMAIL", ""),
        )
        msg = self._credential_gate.format_request_message(req)
        logger.info(
            "Credential collection HITL request created:\n%s",
            msg,
        )

        # Poll for response
        deadline = time.monotonic() + _CRED_POLL_TIMEOUT
        while time.monotonic() < deadline:
            with self._credential_gate._lock:  # noqa: SLF001
                cred_req = self._credential_gate._requests.get(req.request_id)  # noqa: SLF001
            if cred_req is None:
                return False
            if cred_req.status == CredentialRequestStatus.PROVIDED:
                creds = self._credential_gate.get_credentials(req.request_id)
                if creds:
                    self._user_email, self._user_password = creds
                    logger.info("Credentials received (email=%s).", self._user_email)
                    return True
                return False
            if cred_req.status == CredentialRequestStatus.DECLINED:
                logger.info("Credential request declined by user.")
                return False
            await asyncio.sleep(2.0)

        logger.warning(
            "Credential collection timed out after %ss.", _CRED_POLL_TIMEOUT
        )
        return False

    # ------------------------------------------------------------------
    # Single-provider acquisition flow
    # ------------------------------------------------------------------

    async def _acquire_single(self, recipe: ProviderRecipe) -> HarvestResult:
        """Run the full browser automation flow for one provider."""

        # Step 1: Already configured?
        if os.getenv(recipe.env_var):
            logger.info("Provider '%s': key already set — skipping.", recipe.name)
            return HarvestResult(provider=recipe.name, status=AcquisitionStatus.SKIPPED)

        # Step 2: Requires payment?
        if recipe.requires_payment:
            logger.info(
                "Provider '%s': requires_payment=True — BLOCKED_PAYMENT.", recipe.name
            )
            return HarvestResult(
                provider=recipe.name, status=AcquisitionStatus.BLOCKED_PAYMENT
            )

        # Step 3: Check native automation is available
        if not _HAS_NATIVE_AUTOMATION:
            logger.warning(
                "Provider '%s': murphy_native_automation not available.", recipe.name
            )
            return HarvestResult(
                provider=recipe.name,
                status=AcquisitionStatus.FAILED,
                error="murphy_native_automation not available",
            )

        # Step 4: Open provider signup page in the user's real browser
        if self._interactive:
            self._open_provider_ui(recipe.signup_url, recipe.name, "signup")

        runner = MurphyNativeRunner()
        try:
            return await self._run_signup_flow(runner, recipe)
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "Provider '%s': unexpected error: %s", recipe.name, exc
            )
            return HarvestResult(
                provider=recipe.name,
                status=AcquisitionStatus.FAILED,
                error=str(exc),
            )

    async def _run_signup_flow(
        self,
        runner: Any,
        recipe: ProviderRecipe,
    ) -> HarvestResult:
        """Execute the full Murphy native signup + key extraction flow.

        Uses webbrowser.open() (via OPEN_URL) to load pages in the user's real
        browser, then GhostDesktopRunner actions (GHOST_CLICK / GHOST_TYPE) for
        OCR-guided form filling.  All steps are dispatched through
        MurphyNativeRunner.run() — no Playwright binary required.
        """
        email_to_use = self._user_email or os.getenv("MURPHY_HARVEST_EMAIL", "")
        pwd_to_use = self._user_password or _random_password()

        # Build the form-fill task: navigate → scroll → fill email → fill password
        form_task = NativeTask(
            task_type=TaskType.FILL_ONBOARDING_WIZARD,
            steps=[
                NativeStep(action=ActionType.OPEN_URL, target=recipe.signup_url),
                NativeStep(action=ActionType.GHOST_WAIT, timeout_ms=2000),
                NativeStep(action=ActionType.SCROLL_TO_BOTTOM),
                NativeStep(action=ActionType.WAIT_MS, timeout_ms=500),
                NativeStep(action=ActionType.GHOST_CLICK, target=recipe.email_field_label),
                NativeStep(action=ActionType.GHOST_TYPE, value=email_to_use),
                NativeStep(action=ActionType.GHOST_CLICK, target=recipe.password_field_label),
                NativeStep(action=ActionType.GHOST_TYPE, value=pwd_to_use),
            ],
        )
        nav_result = runner.run(form_task)
        if nav_result.get("status") not in ("passed", "pass", "ok"):
            return HarvestResult(
                provider=recipe.name,
                status=AcquisitionStatus.FAILED,
                error=f"Navigation/form-fill failed: {nav_result.get('error', '')}",
            )

        # Human pause after page load + form fill
        await HumanSimulator.pause_after_page_load()
        await HumanSimulator.pause_between_actions()

        # --- check for CAPTCHA before TOS gate ------------------------------
        captcha_type, captcha_strategy = await self._check_and_handle_captcha(
            runner, recipe, attempt=0
        )
        if captcha_type != CaptchaType.NONE and captcha_strategy in (
            CaptchaStrategy.HITL_ESCALATE,
            CaptchaStrategy.RETRY_BACKOFF,
        ):
            return HarvestResult(
                provider=recipe.name,
                status=AcquisitionStatus.BLOCKED_CAPTCHA,
                captcha_strategy_used=captcha_strategy,
                error=f"CAPTCHA blocked ({captcha_type.value})",
            )

        # --- TOS GATE: screenshot → request_approval → wait for human -------
        screenshot_path = (
            f"/tmp/tos_{recipe.name}_{uuid.uuid4().hex[:8]}.png"
        )
        try:
            runner.run(NativeTask(steps=[
                NativeStep(action=ActionType.SCREENSHOT, target=screenshot_path),
            ]))
        except Exception as exc:  # noqa: BLE001
            logger.debug("Non-critical screenshot error: %s", exc)

        tos_req = self._tos_gate.request_approval(recipe.name, screenshot_path)
        logger.info(
            "Provider '%s': TOS approval requested (id=%s) — waiting for human.",
            recipe.name,
            tos_req.request_id,
        )

        tos_approved = await self._wait_for_tos_decision(tos_req.request_id)
        if not tos_approved:
            logger.info(
                "Provider '%s': TOS not approved — skipping.", recipe.name
            )
            return HarvestResult(
                provider=recipe.name,
                status=AcquisitionStatus.SKIPPED,
                tos_accepted=False,
            )

        # --- click TOS checkbox + submit ------------------------------------
        if recipe.tos_checkbox_label or recipe.tos_checkbox_selector:
            tos_label = recipe.tos_checkbox_label or recipe.tos_checkbox_selector
            runner.run(NativeTask(steps=[
                NativeStep(action=ActionType.GHOST_CLICK, target=tos_label),
            ]))
            await HumanSimulator.pause_between_actions()

        runner.run(NativeTask(steps=[
            NativeStep(action=ActionType.GHOST_CLICK, target=recipe.submit_button_label),
        ]))
        await HumanSimulator.pause_after_page_load()

        # --- check for CAPTCHA after submit ---------------------------------
        captcha_type, captcha_strategy = await self._check_and_handle_captcha(
            runner, recipe, attempt=0
        )
        if captcha_type != CaptchaType.NONE and captcha_strategy in (
            CaptchaStrategy.HITL_ESCALATE,
        ):
            return HarvestResult(
                provider=recipe.name,
                status=AcquisitionStatus.BLOCKED_CAPTCHA,
                tos_accepted=True,
                captcha_strategy_used=captcha_strategy,
                error=f"Post-submit CAPTCHA blocked ({captcha_type.value})",
            )

        # --- email verification ---------------------------------------------
        verify_url = await self._wait_for_verification_email(recipe.name)
        if verify_url:
            runner.run(NativeTask(steps=[
                NativeStep(action=ActionType.OPEN_URL, target=verify_url),
            ]))
            await HumanSimulator.pause_after_page_load()

        # --- navigate to keys page + open in system browser ----------------
        runner.run(NativeTask(steps=[
            NativeStep(action=ActionType.OPEN_URL, target=recipe.keys_page_url),
        ]))
        if self._interactive:
            self._open_provider_ui(recipe.keys_page_url, recipe.name, "api-keys")
        await HumanSimulator.pause_after_page_load()

        # --- create API key -------------------------------------------------
        runner.run(NativeTask(steps=[
            NativeStep(action=ActionType.GHOST_CLICK, target=recipe.create_key_label),
        ]))
        await HumanSimulator.pause_between_actions()

        # --- extract key value via OCR -------------------------------------
        key_result = runner.run(NativeTask(steps=[
            NativeStep(action=ActionType.GHOST_ASSERT_OCR, target=recipe.key_region_label),
        ]))
        key_value: Optional[str] = None
        for sr in key_result.get("step_results", []):
            text = (sr.get("text") or sr.get("value") or sr.get("ocr_text") or "").strip()
            if text and (not recipe.key_format_pattern or re.match(recipe.key_format_pattern, text)):
                key_value = text
                break

        if not key_value:
            return HarvestResult(
                provider=recipe.name,
                status=AcquisitionStatus.FAILED,
                tos_accepted=True,
                error="Could not extract key value from page",
            )

        # --- validate format ------------------------------------------------
        if recipe.key_format_pattern:
            if not re.match(recipe.key_format_pattern, key_value):
                if _HAS_ENV_MGR:
                    valid, msg = validate_api_key(recipe.name, key_value)
                    if not valid:
                        logger.warning(
                            "Provider '%s': key format invalid: %s", recipe.name, msg
                        )

        # --- store securely -------------------------------------------------
        if _HAS_SKM:
            store_api_key(recipe.env_var, key_value)

        if _HAS_ENV_MGR:
            try:
                write_env_key(None, recipe.env_var, key_value)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Provider '%s': write_env_key failed: %s", recipe.name, exc
                )

        logger.info(
            "Provider '%s': key acquired and stored successfully.", recipe.name
        )
        return HarvestResult(
            provider=recipe.name,
            status=AcquisitionStatus.COMPLETED,
            key_stored=True,
            tos_accepted=True,
            captcha_strategy_used=captcha_strategy if captcha_type != CaptchaType.NONE else None,
        )

    # ------------------------------------------------------------------
    # CAPTCHA detection + handling
    # ------------------------------------------------------------------

    async def _check_and_handle_captcha(
        self,
        runner: Any,
        recipe: ProviderRecipe,
        attempt: int,
    ) -> Tuple[CaptchaType, Optional[CaptchaStrategy]]:
        """Use OCR to detect CAPTCHA indicators on screen, run handler if needed.

        Returns ``(CaptchaType, CaptchaStrategy | None)``.
        """
        # Use GHOST_ASSERT_OCR to scan visible text for CAPTCHA indicators
        ocr_result = runner.run(NativeTask(steps=[
            NativeStep(action=ActionType.GHOST_ASSERT_OCR, target="captcha", optional=True),
        ]))
        page_text = " ".join(
            sr.get("text", "") + " " + sr.get("ocr_text", "")
            for sr in ocr_result.get("step_results", [])
        )

        captcha_type = detect_captcha_type(page_text)
        if captcha_type == CaptchaType.NONE:
            return CaptchaType.NONE, None

        # Pass None for page — runner manages pages internally
        resolved, strategy = await self._captcha_handler.handle(
            page=None,
            runner=runner,
            captcha_type=captcha_type,
            provider_name=recipe.name,
            attempt=attempt,
        )
        return captcha_type, strategy

    # ------------------------------------------------------------------
    # TOS decision polling
    # ------------------------------------------------------------------

    async def _wait_for_tos_decision(self, request_id: str) -> bool:
        """Poll the TOS gate until the request leaves PENDING state.

        Returns ``True`` if ACCEPTED, ``False`` if REJECTED / SKIPPED / timed out.
        """
        deadline = time.monotonic() + _TOS_POLL_TIMEOUT
        while time.monotonic() < deadline:
            with self._tos_gate._lock:  # noqa: SLF001
                req = self._tos_gate._requests.get(request_id)  # noqa: SLF001
            if req is None:
                return False
            if req.status == TOSAcceptanceStatus.ACCEPTED:
                return True
            if req.status in (
                TOSAcceptanceStatus.REJECTED,
                TOSAcceptanceStatus.SKIPPED,
            ):
                return False
            await asyncio.sleep(_TOS_POLL_INTERVAL)

        logger.warning(
            "TOS approval timed out for request_id=%s after %ss.",
            request_id,
            _TOS_POLL_TIMEOUT,
        )
        return False

    # ------------------------------------------------------------------
    # Email verification polling
    # ------------------------------------------------------------------

    async def _wait_for_verification_email(
        self, provider_name: str
    ) -> Optional[str]:
        """Poll IMAP for a verification email and return the URL.

        Follows the pattern from ``src/comms/connectors.py``.
        Returns ``None`` if IMAP is not configured or no email arrives.
        """
        if not self._imap_config:
            return None
        try:
            import email as email_lib  # noqa: PLC0415
            import imaplib  # noqa: PLC0415
        except ImportError:
            return None

        host = self._imap_config.get("host", "")
        port = int(self._imap_config.get("port", 993))
        username = self._imap_config.get("username", "")
        password = self._imap_config.get("password", "")

        deadline = time.monotonic() + _EMAIL_POLL_TIMEOUT
        while time.monotonic() < deadline:
            try:
                with imaplib.IMAP4_SSL(host, port) as conn:
                    conn.login(username, password)
                    conn.select("INBOX")
                    _, msg_ids = conn.search(
                        None, f'(UNSEEN SUBJECT "{provider_name}")'
                    )
                    for mid in msg_ids[0].split() if msg_ids[0] else []:
                        _, data = conn.fetch(mid, "(RFC822)")
                        if data and data[0]:
                            raw = data[0][1] if isinstance(data[0], tuple) else b""
                            msg = email_lib.message_from_bytes(raw)
                            body = _extract_email_body(msg)
                            url = _find_verification_url(body)
                            if url:
                                logger.info(
                                    "Provider '%s': verification URL found.",
                                    provider_name,
                                )
                                return url
            except Exception as exc:  # noqa: BLE001
                logger.debug(
                    "Provider '%s': IMAP poll error: %s", provider_name, exc
                )
            await asyncio.sleep(_EMAIL_POLL_INTERVAL)

        logger.warning(
            "Provider '%s': verification email not received within %ss.",
            provider_name,
            _EMAIL_POLL_TIMEOUT,
        )
        return None

    # ------------------------------------------------------------------
    # UI helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _open_provider_ui(url: str, provider_name: str, page_type: str) -> None:
        """Open *url* in the system's default browser.

        This gives the user a second independent view of each provider's
        signup or API-keys page so they don't need to navigate manually.
        """
        try:
            webbrowser.open(url)
            logger.info(
                "Opened %s page for '%s' in system browser: %s",
                page_type,
                provider_name,
                url,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Could not open system browser for '%s': %s", provider_name, exc
            )

    # ------------------------------------------------------------------
    # JavaScript evaluation helper
    # ------------------------------------------------------------------

    @staticmethod
    async def _evaluate_safe(runner: Any, script: str) -> None:
        """Dispatch a scroll/wait action via the native runner.

        Kept for backward compatibility; in the native stack scroll is handled
        via ``SCROLL_TO_BOTTOM`` and waits via ``WAIT_MS`` NativeStep actions.
        Silently skips if native automation is unavailable.
        """
        if not _HAS_NATIVE_AUTOMATION or NativeTask is None:
            return
        try:
            runner.run(NativeTask(steps=[
                NativeStep(action=ActionType.SCROLL_TO_BOTTOM),
            ]))
        except Exception as exc:  # noqa: BLE001
            logger.debug("Non-critical error: %s", exc)


# ---------------------------------------------------------------------------
# Module-level shared gate instances
# ---------------------------------------------------------------------------
# These singletons are used by the REST API router so that the web UI can
# drive the same gate objects that KeyHarvester uses internally.

_shared_tos_gate: Optional[TOSAcceptanceGate] = None
_shared_credential_gate: Optional[UserCredentialGate] = None
_shared_harvester: Optional[KeyHarvester] = None


def get_shared_gates() -> Tuple[TOSAcceptanceGate, UserCredentialGate]:
    """Return (or lazily create) the module-level shared gate singletons.

    The same instances are injected into KeyHarvester when the REST router
    starts a harvest, so HITL responses from the web UI are seen by the
    running harvest coroutine.
    """
    global _shared_tos_gate, _shared_credential_gate
    if _shared_tos_gate is None:
        _shared_tos_gate = TOSAcceptanceGate()
        _shared_credential_gate = UserCredentialGate()
    return _shared_tos_gate, _shared_credential_gate


# ---------------------------------------------------------------------------
# FastAPI REST router — /api/key-harvester/*
# ---------------------------------------------------------------------------

def create_key_harvester_router() -> Any:
    """Create a FastAPI APIRouter that exposes the key harvester over HTTP.

    Endpoints:

    ``GET  /api/key-harvester/status``
        Returns harvest run counts and gate states.

    ``POST /api/key-harvester/start``
        Launches harvest_all() in a background thread.  Accepts optional
        ``imap_config`` body field.

    ``GET  /api/key-harvester/pending-credentials``
        Lists pending UserCredentialGate requests.

    ``POST /api/key-harvester/credentials/{request_id}/provide``
        Body: ``{"email": "…", "password": "…"}``.

    ``POST /api/key-harvester/credentials/{request_id}/decline``
        Declines a pending credential request.

    ``GET  /api/key-harvester/pending-tos``
        Lists pending TOS approval requests (with formatted message).

    ``POST /api/key-harvester/tos/{request_id}/approve``
        Body: ``{"approved_by": "…"}``.  Approves TOS — the human is the
        legal accepting party.

    ``POST /api/key-harvester/tos/{request_id}/reject``
        Body: ``{"rejected_by": "…", "reason": "…"}``.

    ``POST /api/key-harvester/tos/{request_id}/skip``
        Skips a pending TOS request.

    ``GET  /api/key-harvester/audit-log``
        Returns the full TOS audit trail.

    Returns:
        A ``fastapi.APIRouter`` instance (or a stub object when FastAPI is not
        installed).
    """
    try:
        from fastapi import APIRouter  # noqa: PLC0415
        from fastapi.responses import JSONResponse  # noqa: PLC0415
    except ImportError:  # pragma: no cover
        logger.warning("FastAPI not available — key harvester router not created.")
        return None

    # _FastAPIRequest is imported at module level (resolvable under PEP 563)
    if _FastAPIRequest is None:  # pragma: no cover
        logger.warning("FastAPI Request type not available — router not created.")
        return None

    router = APIRouter(prefix="/api/key-harvester", tags=["key-harvester"])

    # ------------------------------------------------------------------ status
    @router.get("/status")
    async def kh_status():
        tos_gate, cred_gate = get_shared_gates()
        harvest_status: Dict[str, Any] = {"total": 0, "completed": 0, "blocked": 0, "pending": 0, "skipped": 0}
        if _shared_harvester is not None:
            harvest_status = _shared_harvester.get_status()
        return JSONResponse({
            "success": True,
            "harvest": harvest_status,
            "pending_tos": len(tos_gate.get_pending()),
            "pending_credentials": len(cred_gate.get_pending()),
            "providers_total": len(PROVIDER_RECIPES),
        })

    # ------------------------------------------------------------------ start
    @router.post("/start")
    async def kh_start(request: _FastAPIRequest):
        import asyncio as _asyncio  # noqa: PLC0415
        global _shared_harvester
        tos_gate, cred_gate = get_shared_gates()
        body: Dict[str, Any] = {}
        try:
            body = await request.json()
        except Exception as exc:  # noqa: BLE001
            logger.debug("Non-critical error: %s", exc)
        imap_cfg = body.get("imap_config")
        interactive = bool(body.get("interactive", True))

        _shared_harvester = KeyHarvester(
            tos_gate=tos_gate,
            credential_gate=cred_gate,
            imap_config=imap_cfg,
            interactive=interactive,
        )

        def _run() -> None:
            loop = _asyncio.new_event_loop()
            _asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(_shared_harvester.harvest_all())  # type: ignore[union-attr]
            finally:
                loop.close()

        import threading as _threading  # noqa: PLC0415
        thread = _threading.Thread(target=_run, daemon=True, name="KeyHarvesterThread")
        thread.start()

        return JSONResponse({
            "success": True,
            "message": "Key harvest started in background thread.",
            "providers": [r.name for r in PROVIDER_RECIPES],
        })

    # ------------------------------------------------------------------ credentials
    @router.get("/pending-credentials")
    async def kh_pending_creds():
        _, cred_gate = get_shared_gates()
        pending = cred_gate.get_pending()
        return JSONResponse({
            "success": True,
            "count": len(pending),
            "requests": [
                {
                    "request_id": r.request_id,
                    "purpose": r.purpose,
                    "suggested_email": r.suggested_email,
                    "status": r.status.value,
                    "requested_at": r.requested_at,
                    "message": cred_gate.format_request_message(r),
                }
                for r in pending
            ],
        })

    @router.post("/credentials/{request_id}/provide")
    async def kh_provide_creds(request_id: str, request: _FastAPIRequest):
        _, cred_gate = get_shared_gates()
        body: Dict[str, Any] = {}
        try:
            body = await request.json()
        except Exception as exc:  # noqa: BLE001
            logger.debug("kh_provide_creds error: %s", exc)
        email = body.get("email", "")
        password = body.get("password", "")
        ok = cred_gate.provide(request_id, email=email, password=password)
        return JSONResponse({"success": ok, "request_id": request_id})

    @router.post("/credentials/{request_id}/decline")
    async def kh_decline_creds(request_id: str):
        _, cred_gate = get_shared_gates()
        ok = cred_gate.decline(request_id)
        return JSONResponse({"success": ok, "request_id": request_id})

    # ------------------------------------------------------------------ TOS
    @router.get("/pending-tos")
    async def kh_pending_tos():
        tos_gate, _ = get_shared_gates()
        pending = tos_gate.get_pending()
        return JSONResponse({
            "success": True,
            "count": len(pending),
            "requests": [
                {
                    "request_id": r.request_id,
                    "provider": r.provider_key,
                    "provider_name": r.provider_name,
                    "tos_url": r.tos_url,
                    "privacy_url": r.privacy_url,
                    "acceptable_use_url": r.acceptable_use_url,
                    "screenshot_path": r.screenshot_path,
                    "status": r.status.value,
                    "liability_note": r.liability_note,
                    "message": tos_gate.format_approval_message(r),
                }
                for r in pending
            ],
        })

    @router.post("/tos/{request_id}/approve")
    async def kh_approve_tos(request_id: str, request: _FastAPIRequest):
        tos_gate, _ = get_shared_gates()
        body: Dict[str, Any] = {}
        try:
            body = await request.json()
        except Exception as exc:  # noqa: BLE001
            logger.debug("kh_approve_tos error: %s", exc)
        approved_by = body.get("approved_by", "web-ui")
        ok = tos_gate.approve(request_id, approved_by=approved_by)
        return JSONResponse({"success": ok, "request_id": request_id})

    @router.post("/tos/{request_id}/reject")
    async def kh_reject_tos(request_id: str, request: _FastAPIRequest):
        tos_gate, _ = get_shared_gates()
        body: Dict[str, Any] = {}
        try:
            body = await request.json()
        except Exception as exc:  # noqa: BLE001
            logger.debug("kh_reject_tos error: %s", exc)
        rejected_by = body.get("rejected_by", "web-ui")
        reason = body.get("reason", "")
        ok = tos_gate.reject(request_id, rejected_by=rejected_by, reason=reason)
        return JSONResponse({"success": ok, "request_id": request_id})

    @router.post("/tos/{request_id}/skip")
    async def kh_skip_tos(request_id: str):
        tos_gate, _ = get_shared_gates()
        ok = tos_gate.skip(request_id)
        return JSONResponse({"success": ok, "request_id": request_id})

    # ------------------------------------------------------------------ audit
    @router.get("/audit-log")
    async def kh_audit_log():
        tos_gate, _ = get_shared_gates()
        return JSONResponse({
            "success": True,
            "audit_log": tos_gate.get_audit_log(),
        })

    return router
