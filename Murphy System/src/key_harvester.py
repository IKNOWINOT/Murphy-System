# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Key Harvester — Murphy System

Orchestrates automated third-party API key acquisition via Playwright browser
automation.  Every provider's Terms of Service acceptance is gated through
TOSAcceptanceGate — Murphy NEVER checks an agreement checkbox without an
explicit human approval first.

Flow (per provider):
  1. Check if key already exists → skip
  2. If requires_payment → mark BLOCKED_PAYMENT, log, skip
  3. Launch Playwright browser (PlaywrightTaskRunner)
  4. Navigate to signup URL
  5. Fill email / password fields
  6. TOS GATE — take screenshot, call tos_gate.request_approval(), wait
     for human decision; on rejection → skip provider
  7. Click TOS checkbox + submit
  8. Detect CAPTCHA → BLOCKED_CAPTCHA
  9. Poll IMAP for verification email
 10. Navigate verification link
 11. Navigate to keys page
 12. Create and extract key
 13. Validate format (env_manager)
 14. Store securely (secure_key_manager + env_manager)

Design Principles:
  - HITL-first: TOS gate is mandatory, never bypassed
  - Thread-safe, bounded state
  - Logging throughout for full observability
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy imports (optional deps)
# ---------------------------------------------------------------------------

try:
    from playwright_task_definitions import (
        ClickTask,
        ExtractTask,
        FillTask,
        NavigateTask,
        PlaywrightTaskRunner,
        ScreenshotTask,
        TaskStatus,
    )
    _HAS_PLAYWRIGHT = True
except ImportError:  # pragma: no cover
    _HAS_PLAYWRIGHT = False
    PlaywrightTaskRunner = None  # type: ignore[assignment,misc]

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
    def validate_api_key(provider: str, key: str) -> tuple:  # type: ignore[misc]
        return True, "ok"
    def write_env_key(path: Optional[str], key: str, value: str) -> None:  # type: ignore[misc]
        pass

from tos_acceptance_gate import TOSAcceptanceGate, TOSAcceptanceStatus


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


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class ProviderRecipe:
    """Browser automation recipe for signing up with a provider.

    ``signup_selectors`` maps logical field names (``email``, ``password``) to
    CSS selectors on the signup form.  Values are intentional placeholders —
    real selectors must be verified against each provider's live sign-up page
    before deployment.
    """

    name: str
    env_var: str
    signup_url: str
    keys_page_url: str
    tier: str  # "free" | "free_trial" | "paid_only"
    requires_payment: bool
    signup_selectors: Dict[str, str]  # e.g. {"email": "#email", "password": "#password"}
    tos_checkbox_selector: str
    create_key_selector: str
    key_extract_selector: str
    key_format_pattern: str  # regex or empty string
    notes: str = ""


@dataclass
class HarvestResult:
    """Outcome of a single provider key acquisition attempt."""

    provider: str
    status: AcquisitionStatus
    key_stored: bool = False
    tos_accepted: bool = False
    error: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# ---------------------------------------------------------------------------
# Provider recipes
# ---------------------------------------------------------------------------

#: One recipe per supported provider.  CSS selectors are best-effort
#: placeholders; verify against live pages before use in production.
PROVIDER_RECIPES: List[ProviderRecipe] = [
    ProviderRecipe(
        name="groq",
        env_var="GROQ_API_KEY",
        signup_url="https://console.groq.com/login",
        keys_page_url="https://console.groq.com/keys",
        tier="free",
        requires_payment=False,
        signup_selectors={"email": "input[name='email']", "password": "input[name='password']"},
        tos_checkbox_selector="input[type='checkbox'][name*='terms']",
        create_key_selector="button[data-testid='create-api-key']",
        key_extract_selector="input[data-testid='api-key-value']",
        key_format_pattern=r"^gsk_[A-Za-z0-9]{20,}$",
        notes="Free tier; no credit card required.",
    ),
    ProviderRecipe(
        name="openai",
        env_var="OPENAI_API_KEY",
        signup_url="https://platform.openai.com/signup",
        keys_page_url="https://platform.openai.com/api-keys",
        tier="free_trial",
        requires_payment=False,
        signup_selectors={"email": "input[name='email']", "password": "input[name='password']"},
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
        signup_selectors={"email": "input[name='email']", "password": "input[name='password']"},
        tos_checkbox_selector="input[type='checkbox'][name*='terms']",
        create_key_selector="button[aria-label='Create Key']",
        key_extract_selector="code.api-key",
        key_format_pattern=r"^sk-ant-[A-Za-z0-9_-]{20,}$",
        notes="Free tier with rate limits.",
    ),
    ProviderRecipe(
        name="elevenlabs",
        env_var="ELEVENLABS_API_KEY",
        signup_url="https://elevenlabs.io/sign-up",
        keys_page_url="https://elevenlabs.io/app/settings/api-keys",
        tier="free",
        requires_payment=False,
        signup_selectors={"email": "input[name='email']", "password": "input[name='password']"},
        tos_checkbox_selector="input[type='checkbox'][name*='terms']",
        create_key_selector="button[data-testid='generate-api-key']",
        key_extract_selector="input[data-testid='api-key-value']",
        key_format_pattern=r"^[A-Za-z0-9_-]{32,}$",
        notes="Free tier with character limits.",
    ),
    ProviderRecipe(
        name="sendgrid",
        env_var="SENDGRID_API_KEY",
        signup_url="https://signup.sendgrid.com/",
        keys_page_url="https://app.sendgrid.com/settings/api_keys",
        tier="free",
        requires_payment=False,
        signup_selectors={"email": "input#email", "password": "input#password"},
        tos_checkbox_selector="input[type='checkbox'][name*='opt_in']",
        create_key_selector="button[data-testid='btn-create-api-key']",
        key_extract_selector="input.api-key-display",
        key_format_pattern=r"^SG\.[A-Za-z0-9_-]{22,}\.[A-Za-z0-9_-]{43,}$",
        notes="Free tier: 100 emails/day.",
    ),
    ProviderRecipe(
        name="stripe",
        env_var="STRIPE_API_KEY",
        signup_url="https://dashboard.stripe.com/register",
        keys_page_url="https://dashboard.stripe.com/test/apikeys",
        tier="free",
        requires_payment=False,
        signup_selectors={"email": "input[name='email']", "password": "input[name='password']"},
        tos_checkbox_selector="input[type='checkbox'][name*='agree']",
        create_key_selector="button[data-test='reveal-key-button']",
        key_extract_selector="input[data-test='api-key-value']",
        key_format_pattern=r"^sk_(test|live)_[A-Za-z0-9]{24,}$",
        notes="Test mode keys are free.",
    ),
    ProviderRecipe(
        name="twilio",
        env_var="TWILIO_AUTH_TOKEN",
        signup_url="https://www.twilio.com/try-twilio",
        keys_page_url="https://console.twilio.com/",
        tier="free_trial",
        requires_payment=False,
        signup_selectors={"email": "input[name='email']", "password": "input[name='password']"},
        tos_checkbox_selector="input[type='checkbox'][name*='terms']",
        create_key_selector="button[data-testid='create-key']",
        key_extract_selector="span.auth-token",
        key_format_pattern=r"^[A-Za-z0-9]{32}$",
        notes="Trial account with limited credits.",
    ),
    ProviderRecipe(
        name="heygen",
        env_var="HEYGEN_API_KEY",
        signup_url="https://app.heygen.com/signup",
        keys_page_url="https://app.heygen.com/settings/api",
        tier="paid_only",
        requires_payment=True,
        signup_selectors={"email": "input[name='email']", "password": "input[name='password']"},
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
        signup_selectors={"email": "input[name='email']", "password": "input[name='password']"},
        tos_checkbox_selector="input[type='checkbox'][name*='terms']",
        create_key_selector="button[aria-label='Create API Key']",
        key_extract_selector="code.api-key",
        key_format_pattern=r"^[A-Za-z0-9_-]{32,}$",
        notes="Requires paid subscription.",
    ),
    ProviderRecipe(
        name="vapi",
        env_var="VAPI_API_KEY",
        signup_url="https://dashboard.vapi.ai/sign-up",
        keys_page_url="https://dashboard.vapi.ai/keys",
        tier="free",
        requires_payment=False,
        signup_selectors={"email": "input[name='email']", "password": "input[name='password']"},
        tos_checkbox_selector="input[type='checkbox'][name*='terms']",
        create_key_selector="button[data-testid='create-key']",
        key_extract_selector="input[data-testid='api-key-value']",
        key_format_pattern=r"^[A-Za-z0-9_-]{32,}$",
        notes="Free tier available.",
    ),
    ProviderRecipe(
        name="hubspot",
        env_var="HUBSPOT_API_KEY",
        signup_url="https://app.hubspot.com/signup-hubspot/crm",
        keys_page_url="https://app.hubspot.com/integrations-settings/api-key",
        tier="free",
        requires_payment=False,
        signup_selectors={"email": "input[name='email']", "password": "input[name='password']"},
        tos_checkbox_selector="input[type='checkbox'][name*='agree']",
        create_key_selector="button[data-test='generate-api-key-btn']",
        key_extract_selector="input[data-test='api-key-value']",
        key_format_pattern=r"^[A-Za-z0-9_-]{36}$",
        notes="Free CRM tier.",
    ),
    ProviderRecipe(
        name="shopify",
        env_var="SHOPIFY_API_KEY",
        signup_url="https://partners.shopify.com/signup",
        keys_page_url="https://partners.shopify.com/organizations",
        tier="free",
        requires_payment=False,
        signup_selectors={"email": "input[name='account[email]']", "password": "input[name='account[password]']"},
        tos_checkbox_selector="input[type='checkbox'][name*='terms']",
        create_key_selector="button[data-testid='create-app-button']",
        key_extract_selector="input[data-testid='api-key-value']",
        key_format_pattern=r"^[A-Za-z0-9]{32}$",
        notes="Partner account; free development store.",
    ),
    ProviderRecipe(
        name="coinbase",
        env_var="COINBASE_API_KEY",
        signup_url="https://www.coinbase.com/signup",
        keys_page_url="https://www.coinbase.com/settings/api",
        tier="free",
        requires_payment=False,
        signup_selectors={"email": "input[name='email']", "password": "input[name='password']"},
        tos_checkbox_selector="input[type='checkbox'][name*='terms']",
        create_key_selector="button[data-testid='new-api-key']",
        key_extract_selector="input.api-key-display",
        key_format_pattern=r"^[A-Za-z0-9_-]{16,}$",
        notes="Requires identity verification.",
    ),
    ProviderRecipe(
        name="github",
        env_var="GITHUB_TOKEN",
        signup_url="https://github.com/signup",
        keys_page_url="https://github.com/settings/tokens/new",
        tier="free",
        requires_payment=False,
        signup_selectors={"email": "input#email", "password": "input#password"},
        tos_checkbox_selector="input[type='checkbox'][name*='terms']",
        create_key_selector="input[type='submit'].btn-primary",
        key_extract_selector="code#new-oauth-token",
        key_format_pattern=r"^gh[ps]_[A-Za-z0-9]{36,}$",
        notes="Free personal access token.",
    ),
    ProviderRecipe(
        name="slack",
        env_var="SLACK_API_TOKEN",
        signup_url="https://slack.com/get-started#/createnew",
        keys_page_url="https://api.slack.com/apps",
        tier="free",
        requires_payment=False,
        signup_selectors={"email": "input[name='email']", "password": "input[name='password']"},
        tos_checkbox_selector="input[type='checkbox'][name*='terms']",
        create_key_selector="button[data-qa='create_app_button']",
        key_extract_selector="code.token-value",
        key_format_pattern=r"^xox[bpars]-[A-Za-z0-9_-]+$",
        notes="Free workspace; Bot Token required.",
    ),
]

# Map name → recipe for fast lookup
_RECIPE_MAP: Dict[str, ProviderRecipe] = {r.name: r for r in PROVIDER_RECIPES}

# ---------------------------------------------------------------------------
# IMAP helper
# ---------------------------------------------------------------------------

_CAPTCHA_INDICATORS = [
    "captcha",
    "recaptcha",
    "hcaptcha",
    "cloudflare challenge",
    "i am not a robot",
    "bot check",
]


def _page_has_captcha(page_text: str) -> bool:
    """Heuristic: return True if page content suggests a CAPTCHA challenge."""
    lower = page_text.lower()
    return any(indicator in lower for indicator in _CAPTCHA_INDICATORS)


# ---------------------------------------------------------------------------
# KeyHarvester
# ---------------------------------------------------------------------------

class KeyHarvester:
    """Orchestrates automated API key acquisition for all configured providers.

    Parameters
    ----------
    user_email:
        The email address used to sign up for each provider.
    imap_config:
        Dict with keys ``host``, ``port``, ``username``, ``password`` for
        polling verification emails.  May be ``None`` to skip email polling.
    tos_gate:
        An initialised :class:`~tos_acceptance_gate.TOSAcceptanceGate` that
        will gate every TOS acceptance step.
    """

    #: Seconds between TOS approval status polls.
    TOS_POLL_INTERVAL: float = 2.0
    #: Maximum seconds to wait for TOS approval before timing out.
    TOS_POLL_TIMEOUT: float = 300.0
    #: Maximum seconds to wait for a verification email.
    EMAIL_POLL_TIMEOUT: float = 120.0
    #: Seconds between IMAP polls.
    EMAIL_POLL_INTERVAL: float = 10.0

    def __init__(
        self,
        user_email: str,
        imap_config: Optional[Dict[str, Any]],
        tos_gate: TOSAcceptanceGate,
    ) -> None:
        self._user_email = user_email
        self._imap_config = imap_config
        self._tos_gate = tos_gate
        self._results: List[HarvestResult] = []
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def harvest_all(self) -> List[HarvestResult]:
        """Iterate through all PROVIDER_RECIPES and attempt to acquire each key.

        Providers whose key is already present in the environment are skipped.
        Providers that require payment are logged and skipped.

        Returns:
            List of :class:`HarvestResult` for every provider.
        """
        for recipe in PROVIDER_RECIPES:
            result = await self._acquire_single(recipe)
            with self._lock:
                self._results.append(result)
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

    # ------------------------------------------------------------------
    # Internal acquisition flow
    # ------------------------------------------------------------------

    async def _acquire_single(self, recipe: ProviderRecipe) -> HarvestResult:
        """Run the full browser automation flow for a single provider."""

        # Step 1: Already configured?
        if os.getenv(recipe.env_var):
            logger.info("Provider '%s': key already set, skipping.", recipe.name)
            return HarvestResult(provider=recipe.name, status=AcquisitionStatus.SKIPPED)

        # Step 2: Requires payment?
        if recipe.requires_payment:
            logger.info(
                "Provider '%s': requires_payment=True, skipping (BLOCKED_PAYMENT).",
                recipe.name,
            )
            return HarvestResult(
                provider=recipe.name,
                status=AcquisitionStatus.BLOCKED_PAYMENT,
            )

        # Step 3 onwards: browser automation
        if not _HAS_PLAYWRIGHT:
            logger.warning(
                "Provider '%s': Playwright not available, cannot automate signup.",
                recipe.name,
            )
            return HarvestResult(
                provider=recipe.name,
                status=AcquisitionStatus.FAILED,
                error="playwright_task_definitions not available",
            )

        runner = PlaywrightTaskRunner()
        try:
            return await self._run_signup_flow(runner, recipe)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Provider '%s': unexpected error: %s", recipe.name, exc)
            return HarvestResult(
                provider=recipe.name,
                status=AcquisitionStatus.FAILED,
                error=str(exc),
            )
        finally:
            await runner.close()

    async def _run_signup_flow(
        self,
        runner: Any,
        recipe: ProviderRecipe,
    ) -> HarvestResult:
        """Execute the Playwright signup flow for *recipe*."""

        # Step 4: Navigate to signup page
        nav_result = await runner.execute_task(NavigateTask(url=recipe.signup_url))
        if nav_result.status != TaskStatus.COMPLETED:
            return HarvestResult(
                provider=recipe.name,
                status=AcquisitionStatus.FAILED,
                error=f"Navigation failed: {nav_result.error}",
            )

        # Step 5: Fill email + password
        email_sel = recipe.signup_selectors.get("email", "input[name='email']")
        pwd_sel = recipe.signup_selectors.get("password", "input[name='password']")

        for selector, value in [(email_sel, self._user_email), (pwd_sel, _random_password())]:
            fill_result = await runner.execute_task(FillTask(selector=selector, value=value))
            if fill_result.status != TaskStatus.COMPLETED:
                logger.warning(
                    "Provider '%s': FillTask failed for selector '%s': %s",
                    recipe.name,
                    selector,
                    fill_result.error,
                )

        # Step 6: TOS GATE — screenshot then wait for human approval
        screenshot_path = f"/tmp/tos_screenshot_{recipe.name}_{uuid.uuid4().hex[:8]}.png"
        await runner.execute_task(ScreenshotTask(path=screenshot_path))

        tos_req = self._tos_gate.request_approval(recipe.name, screenshot_path)
        logger.info(
            "Provider '%s': TOS approval requested (request_id=%s). Waiting for human.",
            recipe.name,
            tos_req.request_id,
        )

        # Poll for approval decision
        approved = await self._wait_for_tos_decision(tos_req.request_id)
        if not approved:
            logger.info("Provider '%s': TOS rejected or timed out — skipping.", recipe.name)
            return HarvestResult(
                provider=recipe.name,
                status=AcquisitionStatus.SKIPPED,
                tos_accepted=False,
            )

        # TOS approved — click checkbox then submit
        if recipe.tos_checkbox_selector:
            await runner.execute_task(ClickTask(selector=recipe.tos_checkbox_selector))

        submit_sel = recipe.signup_selectors.get("submit", "button[type='submit']")
        await runner.execute_task(ClickTask(selector=submit_sel))

        # Step 7: CAPTCHA detection
        page_text_result = await runner.execute_task(
            ExtractTask(selector="body", attribute="innerText")
        )
        if page_text_result.data:
            page_text = str(page_text_result.data.get("text", ""))
            if _page_has_captcha(page_text):
                logger.warning("Provider '%s': CAPTCHA detected.", recipe.name)
                await runner.execute_task(
                    ScreenshotTask(path=f"/tmp/captcha_{recipe.name}.png")
                )
                return HarvestResult(
                    provider=recipe.name,
                    status=AcquisitionStatus.BLOCKED_CAPTCHA,
                    tos_accepted=True,
                    error="CAPTCHA detected on signup page",
                )

        # Step 8-9: Poll IMAP for verification email
        verify_url = await self._wait_for_verification_email(recipe.name)
        if verify_url:
            await runner.execute_task(NavigateTask(url=verify_url))

        # Step 10: Navigate to keys page
        await runner.execute_task(NavigateTask(url=recipe.keys_page_url))

        # Step 11: Click create key button
        create_result = await runner.execute_task(
            ClickTask(selector=recipe.create_key_selector)
        )
        if create_result.status != TaskStatus.COMPLETED:
            logger.warning(
                "Provider '%s': create key click failed: %s",
                recipe.name,
                create_result.error,
            )

        # Step 12: Extract key value
        extract_result = await runner.execute_task(
            ExtractTask(selector=recipe.key_extract_selector, attribute="value")
        )
        key_value: Optional[str] = None
        if extract_result.data:
            key_value = extract_result.data.get("text") or extract_result.data.get("value")

        if not key_value:
            return HarvestResult(
                provider=recipe.name,
                status=AcquisitionStatus.FAILED,
                tos_accepted=True,
                error="Could not extract key value from page",
            )

        key_value = key_value.strip()

        # Step 13: Validate format
        if recipe.key_format_pattern and _HAS_ENV_MGR:
            valid, msg = validate_api_key(recipe.name, key_value)
            if not valid:
                # Try regex directly as fallback
                if not re.match(recipe.key_format_pattern, key_value):
                    logger.warning(
                        "Provider '%s': key format validation failed: %s", recipe.name, msg
                    )

        # Step 14: Store securely
        if _HAS_SKM:
            store_api_key(recipe.env_var, key_value)

        # Step 15: Write to .env
        if _HAS_ENV_MGR:
            try:
                write_env_key(None, recipe.env_var, key_value)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Provider '%s': write_env_key failed: %s", recipe.name, exc
                )

        logger.info("Provider '%s': key successfully acquired and stored.", recipe.name)
        return HarvestResult(
            provider=recipe.name,
            status=AcquisitionStatus.COMPLETED,
            key_stored=True,
            tos_accepted=True,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _wait_for_tos_decision(self, request_id: str) -> bool:
        """Poll the TOS gate until the request is no longer PENDING.

        Returns ``True`` if ACCEPTED, ``False`` if REJECTED / SKIPPED / timed out.
        """
        from tos_acceptance_gate import TOSAcceptanceStatus

        deadline = time.monotonic() + self.TOS_POLL_TIMEOUT
        while time.monotonic() < deadline:
            with self._tos_gate._lock:  # noqa: SLF001
                req = self._tos_gate._requests.get(request_id)  # noqa: SLF001
            if req is None:
                return False
            if req.status == TOSAcceptanceStatus.ACCEPTED:
                return True
            if req.status in (TOSAcceptanceStatus.REJECTED, TOSAcceptanceStatus.SKIPPED):
                return False
            await asyncio.sleep(self.TOS_POLL_INTERVAL)

        logger.warning(
            "TOS approval timed out for request_id=%s after %ss",
            request_id,
            self.TOS_POLL_TIMEOUT,
        )
        return False

    async def _wait_for_verification_email(self, provider_name: str) -> Optional[str]:
        """Poll IMAP for a verification email and return the verification URL.

        Returns ``None`` if IMAP is not configured, no email arrived, or an
        error occurred.  Follows the polling pattern from
        ``src/comms/connectors.py``.
        """
        if not self._imap_config:
            logger.debug("Provider '%s': no IMAP config, skipping email check.", provider_name)
            return None

        try:
            import imaplib  # noqa: PLC0415
            import email as email_lib  # noqa: PLC0415
        except ImportError:
            return None

        host = self._imap_config.get("host", "")
        port = int(self._imap_config.get("port", 993))
        username = self._imap_config.get("username", "")
        password = self._imap_config.get("password", "")

        deadline = time.monotonic() + self.EMAIL_POLL_TIMEOUT
        while time.monotonic() < deadline:
            try:
                with imaplib.IMAP4_SSL(host, port) as conn:
                    conn.login(username, password)
                    conn.select("INBOX")
                    # Search for unseen messages containing provider name
                    _, msg_ids = conn.search(
                        None,
                        f'(UNSEEN SUBJECT "{provider_name}")',
                    )
                    for msg_id in (msg_ids[0].split() if msg_ids[0] else []):
                        _, data = conn.fetch(msg_id, "(RFC822)")
                        if data and data[0]:
                            raw = data[0][1] if isinstance(data[0], tuple) else b""
                            msg = email_lib.message_from_bytes(raw)
                            body = _extract_email_body(msg)
                            url = _find_verification_url(body)
                            if url:
                                logger.info(
                                    "Provider '%s': verification URL found.", provider_name
                                )
                                return url
            except Exception as exc:  # noqa: BLE001
                logger.debug(
                    "Provider '%s': IMAP poll error: %s", provider_name, exc
                )

            await asyncio.sleep(self.EMAIL_POLL_INTERVAL)

        logger.warning(
            "Provider '%s': verification email not received within %ss.",
            provider_name,
            self.EMAIL_POLL_TIMEOUT,
        )
        return None


# ---------------------------------------------------------------------------
# Email parsing helpers
# ---------------------------------------------------------------------------

def _extract_email_body(msg: Any) -> str:
    """Return plain-text body from an email.message.Message object."""
    if msg.is_multipart():
        parts = []
        for part in msg.walk():
            ctype = part.get_content_type()
            if ctype == "text/plain":
                try:
                    parts.append(part.get_payload(decode=True).decode(errors="replace"))
                except Exception:  # noqa: BLE001
                    pass
        return "\n".join(parts)
    try:
        return msg.get_payload(decode=True).decode(errors="replace")
    except Exception:  # noqa: BLE001
        return ""


_URL_PATTERN = re.compile(r"https?://\S+", re.IGNORECASE)


def _find_verification_url(body: str) -> Optional[str]:
    """Extract the first HTTP(S) URL from *body* that looks like a verification link."""
    for url in _URL_PATTERN.findall(body):
        url = url.rstrip(".,;)")
        lower = url.lower()
        if any(kw in lower for kw in ("verify", "confirm", "activate", "validate")):
            return url
    return None


def _random_password() -> str:
    """Generate a random strong password for signup automation."""
    import secrets
    import string
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*()"
    return "".join(secrets.choice(alphabet) for _ in range(20))
