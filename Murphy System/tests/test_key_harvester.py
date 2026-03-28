"""
Tests for KeyHarvester — key_harvester.py

All tests run in mock mode — no real browser, no real API, no real IMAP.

Covers:
- PROVIDER_RECIPES completeness, email-first ordering, data integrity
- AcquisitionStatus and CaptchaType / CaptchaStrategy enums
- HarvestResult dataclass fields
- HumanSimulator static helpers
- detect_captcha_type() for every CAPTCHA variant
- CaptchaHandler strategy dispatch (Cloudflare, audio, backoff, HITL)
- KeyHarvester.harvest_all() — skips existing keys and payment-required
- KeyHarvester.harvest_all() — credential gate (declined → aborted)
- KeyHarvester._acquire_single() — TOS gate approve / reject flows
- KeyHarvester.get_status() and get_results()
- _find_verification_url() and _extract_email_body()
- _random_password() strength

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import asyncio
import os
import threading
import uuid
from dataclasses import asdict
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


from key_harvester import (
    AcquisitionStatus,
    CaptchaHandler,
    CaptchaStrategy,
    CaptchaType,
    HarvestResult,
    HumanSimulator,
    KeyHarvester,
    ProviderRecipe,
    PROVIDER_RECIPES,
    _RECIPE_MAP,
    _extract_email_body,
    _find_verification_url,
    _random_password,
    detect_captcha_type,
)
from murphy_native_automation import ActionType, NativeTask
from tos_acceptance_gate import (
    CredentialRequestStatus,
    TOSAcceptanceGate,
    TOSAcceptanceStatus,
    UserCredentialGate,
)

# ---------------------------------------------------------------------------
# Expected providers + helper sets
# ---------------------------------------------------------------------------

EXPECTED_PROVIDERS = {
    "deepinfra", "openai", "anthropic", "elevenlabs", "sendgrid",
    "stripe", "twilio", "heygen", "tavus", "vapi",
    "hubspot", "shopify", "coinbase", "github", "slack",
}

PAYMENT_REQUIRED = {"heygen", "tavus"}
EMAIL_FIRST = "sendgrid"  # Must be the very first recipe


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tos_gate():
    return TOSAcceptanceGate()


@pytest.fixture
def cred_gate():
    return UserCredentialGate()


@pytest.fixture
def harvester(tos_gate, cred_gate):
    return KeyHarvester(
        tos_gate=tos_gate,
        credential_gate=cred_gate,
        imap_config=None,
        interactive=False,  # non-interactive for tests (no browser/system-browser)
    )


# ---------------------------------------------------------------------------
# PROVIDER_RECIPES — completeness and ordering
# ---------------------------------------------------------------------------

class TestProviderRecipes:
    def test_has_all_15_providers(self):
        names = {r.name for r in PROVIDER_RECIPES}
        assert EXPECTED_PROVIDERS <= names, (
            f"Missing: {EXPECTED_PROVIDERS - names}"
        )

    def test_email_provider_is_first(self):
        """SendGrid must be first so verification emails work for later providers."""
        assert PROVIDER_RECIPES[0].name == EMAIL_FIRST, (
            f"Expected '{EMAIL_FIRST}' first; got '{PROVIDER_RECIPES[0].name}'"
        )

    def test_payment_required_providers_are_last(self):
        """Providers requiring payment should come after all free providers."""
        names = [r.name for r in PROVIDER_RECIPES]
        payment_indices = [i for i, r in enumerate(PROVIDER_RECIPES) if r.requires_payment]
        non_payment_indices = [i for i, r in enumerate(PROVIDER_RECIPES) if not r.requires_payment]
        if payment_indices and non_payment_indices:
            assert min(payment_indices) > max(non_payment_indices), (
                "All requires_payment providers must come after all free providers"
            )

    @pytest.mark.parametrize("recipe", PROVIDER_RECIPES)
    def test_recipe_has_nonempty_name(self, recipe):
        assert recipe.name

    @pytest.mark.parametrize("recipe", PROVIDER_RECIPES)
    def test_recipe_has_nonempty_env_var(self, recipe):
        assert recipe.env_var

    @pytest.mark.parametrize("recipe", PROVIDER_RECIPES)
    def test_recipe_has_nonempty_signup_url(self, recipe):
        assert recipe.signup_url.startswith("https://")

    @pytest.mark.parametrize("recipe", PROVIDER_RECIPES)
    def test_recipe_has_nonempty_keys_page_url(self, recipe):
        assert recipe.keys_page_url.startswith("https://")

    @pytest.mark.parametrize("recipe", PROVIDER_RECIPES)
    def test_recipe_has_email_selector(self, recipe):
        assert "email" in recipe.signup_selectors

    @pytest.mark.parametrize("recipe", PROVIDER_RECIPES)
    def test_recipe_has_password_selector(self, recipe):
        assert "password" in recipe.signup_selectors

    @pytest.mark.parametrize("recipe", PROVIDER_RECIPES)
    def test_recipe_tier_is_known_value(self, recipe):
        assert recipe.tier in ("free", "free_trial", "paid_only")

    def test_heygen_requires_payment(self):
        assert _RECIPE_MAP["heygen"].requires_payment is True

    def test_tavus_requires_payment(self):
        assert _RECIPE_MAP["tavus"].requires_payment is True

    def test_sendgrid_does_not_require_payment(self):
        assert _RECIPE_MAP["sendgrid"].requires_payment is False

    def test_recipe_map_covers_all_recipes(self):
        assert set(_RECIPE_MAP.keys()) == {r.name for r in PROVIDER_RECIPES}


# ---------------------------------------------------------------------------
# AcquisitionStatus enum
# ---------------------------------------------------------------------------

class TestAcquisitionStatus:
    def test_all_expected_values_exist(self):
        expected = {
            "pending", "signing_up", "awaiting_tos_approval", "awaiting_email",
            "verifying", "extracting_key", "completed",
            "blocked_captcha", "blocked_payment", "blocked_2fa",
            "failed", "skipped",
        }
        actual = {s.value for s in AcquisitionStatus}
        assert expected <= actual


# ---------------------------------------------------------------------------
# CaptchaType and CaptchaStrategy enums
# ---------------------------------------------------------------------------

class TestCaptchaEnums:
    def test_captcha_type_values(self):
        expected = {
            "none", "recaptcha_v2", "recaptcha_v3",
            "hcaptcha", "cloudflare_turnstile", "generic",
        }
        assert expected <= {t.value for t in CaptchaType}

    def test_captcha_strategy_values(self):
        expected = {
            "human_delays", "scroll_before_interact", "hover_before_click",
            "user_agent_rotate", "viewport_randomize",
            "audio_fallback", "cloudflare_wait", "retry_backoff",
            "hitl_escalate", "open_visible_browser",
        }
        assert expected <= {s.value for s in CaptchaStrategy}


# ---------------------------------------------------------------------------
# HarvestResult dataclass
# ---------------------------------------------------------------------------

class TestHarvestResult:
    def test_default_fields(self):
        r = HarvestResult(provider="deepinfra", status=AcquisitionStatus.PENDING)
        assert r.key_stored is False
        assert r.tos_accepted is False
        assert r.error == ""
        assert r.captcha_strategy_used is None
        assert r.timestamp  # ISO 8601

    def test_completed_result(self):
        r = HarvestResult(
            provider="deepinfra",
            status=AcquisitionStatus.COMPLETED,
            key_stored=True,
            tos_accepted=True,
        )
        assert r.status == AcquisitionStatus.COMPLETED
        assert r.key_stored is True
        assert r.tos_accepted is True

    def test_all_fields_serialisable(self):
        r = HarvestResult(
            provider="openai",
            status=AcquisitionStatus.BLOCKED_CAPTCHA,
            captcha_strategy_used=CaptchaStrategy.HITL_ESCALATE,
            error="CAPTCHA blocked",
        )
        d = asdict(r)
        assert d["provider"] == "openai"
        assert d["captcha_strategy_used"] == "hitl_escalate"


# ---------------------------------------------------------------------------
# detect_captcha_type()
# ---------------------------------------------------------------------------

class TestDetectCaptchaType:
    def test_none_for_clean_page(self):
        assert detect_captcha_type("<html><body>Hello</body></html>") == CaptchaType.NONE

    def test_recaptcha_v2(self):
        html = '<div class="g-recaptcha" data-sitekey="abc"></div>'
        assert detect_captcha_type(html) == CaptchaType.RECAPTCHA_V2

    def test_recaptcha_v3(self):
        html = "<script>grecaptcha.execute('key')</script>"
        assert detect_captcha_type(html) == CaptchaType.RECAPTCHA_V3

    def test_hcaptcha(self):
        html = '<div class="h-captcha" data-hcaptcha-sitekey="x"></div>'
        assert detect_captcha_type(html) == CaptchaType.HCAPTCHA

    def test_cloudflare_turnstile(self):
        html = '<script src="https://challenges.cloudflare.com/turnstile/v0/api.js"></script>'
        assert detect_captcha_type(html) == CaptchaType.CLOUDFLARE_TURNSTILE

    def test_generic_captcha(self):
        html = "<p>Please solve the captcha to continue.</p>"
        assert detect_captcha_type(html) == CaptchaType.GENERIC

    def test_cloudflare_takes_priority_over_generic(self):
        html = "captcha challenges.cloudflare.com cf-turnstile"
        assert detect_captcha_type(html) == CaptchaType.CLOUDFLARE_TURNSTILE

    def test_case_insensitive(self):
        assert detect_captcha_type("CAPTCHA RECAPTCHA") != CaptchaType.NONE


# ---------------------------------------------------------------------------
# HumanSimulator
# ---------------------------------------------------------------------------

class TestHumanSimulator:
    def test_random_user_agent_returns_string(self):
        ua = HumanSimulator.random_user_agent()
        assert isinstance(ua, str) and len(ua) > 20

    def test_random_user_agent_varies(self):
        agents = {HumanSimulator.random_user_agent() for _ in range(30)}
        assert len(agents) > 1, "Should rotate through multiple user-agents"

    def test_random_viewport_returns_tuple(self):
        w, h = HumanSimulator.random_viewport()
        assert isinstance(w, int) and isinstance(h, int)
        assert w > 800 and h > 500

    def test_random_viewport_varies(self):
        sizes = {HumanSimulator.random_viewport() for _ in range(30)}
        assert len(sizes) > 1

    @pytest.mark.asyncio
    async def test_pause_between_actions_completes(self):
        # Should complete without error (patch sleep for speed)
        with patch("asyncio.sleep", new_callable=AsyncMock):
            await HumanSimulator.pause_between_actions()

    @pytest.mark.asyncio
    async def test_pause_after_page_load_completes(self):
        with patch("asyncio.sleep", new_callable=AsyncMock):
            await HumanSimulator.pause_after_page_load()

    @pytest.mark.asyncio
    async def test_scroll_page_with_none_page_is_noop(self):
        # Should not raise when page is None
        await HumanSimulator.scroll_page(None)

    @pytest.mark.asyncio
    async def test_hover_element_with_none_page_is_noop(self):
        await HumanSimulator.hover_element(None, "button")


# ---------------------------------------------------------------------------
# CaptchaHandler
# ---------------------------------------------------------------------------

class TestCaptchaHandler:
    @pytest.mark.asyncio
    async def test_cloudflare_returns_cloudflare_wait_strategy(self, tos_gate):
        handler = CaptchaHandler(tos_gate)
        with patch("asyncio.sleep", new_callable=AsyncMock):
            resolved, strategy = await handler.handle(
                page=None,
                runner=None,
                captcha_type=CaptchaType.CLOUDFLARE_TURNSTILE,
                provider_name="test",
                attempt=0,
            )
        assert resolved is True
        assert strategy == CaptchaStrategy.CLOUDFLARE_WAIT

    @pytest.mark.asyncio
    async def test_retry_backoff_strategy_on_first_attempt(self, tos_gate):
        handler = CaptchaHandler(tos_gate)
        with patch("asyncio.sleep", new_callable=AsyncMock):
            resolved, strategy = await handler.handle(
                page=None,
                runner=None,
                captcha_type=CaptchaType.GENERIC,
                provider_name="test",
                attempt=0,
            )
        assert resolved is False
        assert strategy == CaptchaStrategy.RETRY_BACKOFF

    @pytest.mark.asyncio
    async def test_hitl_escalate_after_max_retries(self, tos_gate):
        handler = CaptchaHandler(tos_gate)
        with patch("asyncio.sleep", new_callable=AsyncMock):
            resolved, strategy = await handler.handle(
                page=None,
                runner=None,
                captcha_type=CaptchaType.GENERIC,
                provider_name="test",
                attempt=3,  # >= _CAPTCHA_MAX_RETRIES
            )
        assert resolved is False
        assert strategy == CaptchaStrategy.HITL_ESCALATE

    @pytest.mark.asyncio
    async def test_recaptcha_v2_attempts_audio_then_backoff(self, tos_gate):
        """reCAPTCHA v2 tries audio (fails with None page) then falls to backoff."""
        handler = CaptchaHandler(tos_gate)
        with patch("asyncio.sleep", new_callable=AsyncMock):
            resolved, strategy = await handler.handle(
                page=None,
                runner=None,
                captcha_type=CaptchaType.RECAPTCHA_V2,
                provider_name="test",
                attempt=0,
            )
        # Audio fails with None page, falls to backoff on attempt 0
        assert strategy in (CaptchaStrategy.RETRY_BACKOFF, CaptchaStrategy.AUDIO_FALLBACK)


# ---------------------------------------------------------------------------
# KeyHarvester.harvest_all() — credential gate
# ---------------------------------------------------------------------------

class TestHarvestAllCredentialGate:
    @pytest.mark.asyncio
    async def test_harvest_aborted_when_credentials_declined(self, harvester, cred_gate):
        """If the user declines to provide credentials, harvest_all returns empty."""
        # Pre-decline the pending request by intercepting request_credentials
        original_rc = cred_gate.request_credentials

        def _decline_immediately(purpose, suggested_email=""):
            req = original_rc(purpose=purpose, suggested_email=suggested_email)
            cred_gate.decline(req.request_id)
            return req

        with patch.object(cred_gate, "request_credentials", side_effect=_decline_immediately):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                results = await harvester.harvest_all()
        assert results == []

    @pytest.mark.asyncio
    async def test_harvest_aborted_when_credentials_timeout(self, harvester):
        """If no credential response arrives, harvest_all returns empty."""
        with patch("key_harvester._CRED_POLL_TIMEOUT", 0.01):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                results = await harvester.harvest_all()
        assert results == []


# ---------------------------------------------------------------------------
# KeyHarvester.harvest_all() — skip logic (no browser needed)
# ---------------------------------------------------------------------------

class TestHarvestAllSkipLogic:
    @pytest.mark.asyncio
    async def test_skips_providers_with_existing_env_vars(
        self, harvester, cred_gate, monkeypatch
    ):
        """Providers whose env var is already set must be skipped."""
        # Provide credentials so harvest proceeds past gate
        _provide_creds(cred_gate, harvester)

        # Set env vars for ALL providers
        for recipe in PROVIDER_RECIPES:
            monkeypatch.setenv(recipe.env_var, "dummy_existing_key")

        with patch("asyncio.sleep", new_callable=AsyncMock):
            results = await harvester.harvest_all()

        for r in results:
            assert r.status == AcquisitionStatus.SKIPPED

    @pytest.mark.asyncio
    async def test_marks_payment_required_as_blocked(
        self, harvester, cred_gate, monkeypatch
    ):
        """Providers with requires_payment=True must be BLOCKED_PAYMENT."""
        _provide_creds(cred_gate, harvester)

        # Clear env vars for paid-only providers
        for name in PAYMENT_REQUIRED:
            monkeypatch.delenv(_RECIPE_MAP[name].env_var, raising=False)
        # Block all free providers by setting their env vars
        for recipe in PROVIDER_RECIPES:
            if recipe.name not in PAYMENT_REQUIRED:
                monkeypatch.setenv(recipe.env_var, "dummy")

        with patch("asyncio.sleep", new_callable=AsyncMock):
            results = await harvester.harvest_all()

        blocked_results = {r.provider: r for r in results if r.provider in PAYMENT_REQUIRED}
        for name in PAYMENT_REQUIRED:
            assert blocked_results[name].status == AcquisitionStatus.BLOCKED_PAYMENT


# ---------------------------------------------------------------------------
# KeyHarvester._acquire_single() — TOS gate integration
# ---------------------------------------------------------------------------

class TestAcquireSingleTOSGate:
    @pytest.mark.asyncio
    async def test_tos_rejected_returns_skipped(
        self, harvester, tos_gate, monkeypatch
    ):
        """If native automation is unavailable, the provider should be FAILED."""
        harvester._user_email = "test@example.com"
        harvester._user_password = "pwd123"

        recipe = _RECIPE_MAP["deepinfra"]
        monkeypatch.delenv(recipe.env_var, raising=False)

        # Patch _HAS_NATIVE_AUTOMATION so we skip real automation
        with patch("key_harvester._HAS_NATIVE_AUTOMATION", False):
            result = await harvester._acquire_single(recipe)

        assert result.status == AcquisitionStatus.FAILED
        assert "native_automation" in result.error.lower() or "murphy" in result.error.lower()

    @pytest.mark.asyncio
    async def test_tos_gate_request_approval_called(
        self, harvester, tos_gate, monkeypatch
    ):
        """request_approval must be called (in real flow after filling fields)."""
        harvester._user_email = "test@example.com"
        harvester._user_password = "pwd123"

        recipe = _RECIPE_MAP["deepinfra"]
        monkeypatch.delenv(recipe.env_var, raising=False)

        # We verify by checking the tos_gate's pending queue after a mocked run
        original_request = tos_gate.request_approval
        calls = []

        def _capturing_request(provider_key, screenshot_path=None):
            req = original_request(provider_key, screenshot_path)
            calls.append(req)
            # Immediately approve so flow continues
            tos_gate.approve(req.request_id, approved_by="test_approver")
            return req

        with patch.object(tos_gate, "request_approval", side_effect=_capturing_request):
            # Mock MurphyNativeRunner so no real automation is needed
            mock_runner = _make_mock_runner(key_value="di_testkey_abc123456789xyz")
            with patch("key_harvester.MurphyNativeRunner", return_value=mock_runner):
                with patch("key_harvester._HAS_NATIVE_AUTOMATION", True):
                    with patch("asyncio.sleep", new_callable=AsyncMock):
                        await harvester._acquire_single(recipe)

        assert len(calls) == 1, "request_approval must be called exactly once per provider"
        assert calls[0].provider_key == "deepinfra"

    @pytest.mark.asyncio
    async def test_tos_rejected_skips_provider(
        self, harvester, tos_gate, monkeypatch
    ):
        """Provider is SKIPPED when TOS is rejected."""
        harvester._user_email = "test@example.com"
        harvester._user_password = "pwd123"

        recipe = _RECIPE_MAP["deepinfra"]
        monkeypatch.delenv(recipe.env_var, raising=False)

        original = tos_gate.request_approval

        def patched_request(provider_key, screenshot_path=None):
            req = original(provider_key, screenshot_path)
            # Immediately reject so _wait_for_tos_decision returns False
            tos_gate.reject(req.request_id, rejected_by="rejector")
            return req

        mock_runner = _make_mock_runner(key_value="")
        with patch.object(tos_gate, "request_approval", side_effect=patched_request):
            with patch("key_harvester.MurphyNativeRunner", return_value=mock_runner):
                with patch("key_harvester._HAS_NATIVE_AUTOMATION", True):
                    with patch("key_harvester._TOS_POLL_TIMEOUT", 0.1):
                        with patch("asyncio.sleep", new_callable=AsyncMock):
                            result = await harvester._acquire_single(recipe)

        assert result.status == AcquisitionStatus.SKIPPED
        assert result.tos_accepted is False


# ---------------------------------------------------------------------------
# KeyHarvester.get_status() and get_results()
# ---------------------------------------------------------------------------

class TestGetStatusAndResults:
    def test_get_status_empty(self, harvester):
        status = harvester.get_status()
        assert status == {
            "total": 0, "completed": 0, "blocked": 0, "pending": 0, "skipped": 0
        }

    def test_get_status_counts(self, harvester):
        with harvester._lock:
            harvester._results = [
                HarvestResult("a", AcquisitionStatus.COMPLETED),
                HarvestResult("b", AcquisitionStatus.SKIPPED),
                HarvestResult("c", AcquisitionStatus.BLOCKED_CAPTCHA),
                HarvestResult("d", AcquisitionStatus.BLOCKED_PAYMENT),
                HarvestResult("e", AcquisitionStatus.FAILED),
                HarvestResult("f", AcquisitionStatus.PENDING),
            ]
        s = harvester.get_status()
        assert s["total"] == 6
        assert s["completed"] == 1
        assert s["skipped"] == 1
        assert s["blocked"] == 3   # BLOCKED_CAPTCHA + BLOCKED_PAYMENT + FAILED
        assert s["pending"] == 1

    def test_get_results_returns_snapshot(self, harvester):
        with harvester._lock:
            harvester._results = [HarvestResult("deepinfra", AcquisitionStatus.COMPLETED)]
        results = harvester.get_results()
        assert len(results) == 1
        assert results[0].provider == "deepinfra"
        # Mutating the snapshot should not affect internal list
        results.clear()
        assert len(harvester._results) == 1


# ---------------------------------------------------------------------------
# _find_verification_url() and _extract_email_body()
# ---------------------------------------------------------------------------

class TestEmailHelpers:
    def test_find_verification_url_returns_url(self):
        body = "Click here to verify your account: https://example.com/verify?token=abc123"
        url = _find_verification_url(body)
        assert url == "https://example.com/verify?token=abc123"

    def test_find_verification_url_returns_confirm(self):
        body = "Please confirm your email: https://signup.example.com/confirm/xyz"
        url = _find_verification_url(body)
        assert "confirm" in url.lower()

    def test_find_verification_url_ignores_non_verification(self):
        body = "Visit our site at https://example.com or https://example.com/about"
        url = _find_verification_url(body)
        assert url is None

    def test_find_verification_url_strips_trailing_punctuation(self):
        body = "Verify: https://example.com/verify?t=abc."
        url = _find_verification_url(body)
        assert not url.endswith(".")

    def test_find_verification_url_returns_none_for_empty(self):
        assert _find_verification_url("") is None

    def test_extract_email_body_plain_text(self):
        import email as email_lib
        raw = "From: x@x.com\r\nContent-Type: text/plain\r\n\r\nHello body"
        msg = email_lib.message_from_string(raw)
        body = _extract_email_body(msg)
        assert "Hello body" in body

    def test_extract_email_body_multipart(self):
        import email as email_lib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        msg = MIMEMultipart("alternative")
        msg.attach(MIMEText("plain text body", "plain"))
        msg.attach(MIMEText("<b>html body</b>", "html"))
        body = _extract_email_body(msg)
        assert "plain text body" in body


# ---------------------------------------------------------------------------
# _random_password()
# ---------------------------------------------------------------------------

class TestRandomPassword:
    def test_password_length(self):
        pwd = _random_password()
        assert len(pwd) == 20

    def test_password_is_string(self):
        assert isinstance(_random_password(), str)

    def test_passwords_are_unique(self):
        pwds = {_random_password() for _ in range(50)}
        assert len(pwds) == 50, "Passwords must be cryptographically unique"

    def test_password_has_digits(self):
        # Over 50 attempts, at least one should contain a digit
        has_digit = any(any(c.isdigit() for c in _random_password()) for _ in range(20))
        assert has_digit

    def test_password_has_uppercase(self):
        has_upper = any(any(c.isupper() for c in _random_password()) for _ in range(20))
        assert has_upper


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

def _provide_creds(cred_gate: UserCredentialGate, harvester: KeyHarvester) -> None:
    """Synchronously simulate providing credentials via the HITL gate.

    This bypasses the async poll loop by directly setting harvester fields
    and pre-providing credentials so harvest_all() returns quickly.
    """
    harvester._user_email = "harvest@test.com"
    harvester._user_password = "TestP@ssw0rd1!"

    # Also satisfy the credential gate so _request_user_credentials returns True
    req = cred_gate.request_credentials(purpose="test credentials")
    cred_gate.provide(req.request_id, email="harvest@test.com", password="TestP@ssw0rd1!")

    # Pre-seed so _request_user_credentials() short-circuits the poll
    original_request_creds = harvester._credential_gate.request_credentials

    def _instant_provide(purpose, suggested_email=""):
        r = original_request_creds(purpose=purpose, suggested_email=suggested_email)
        cred_gate.provide(r.request_id, email="harvest@test.com", password="TestP@ssw0rd1!")
        return r

    harvester._credential_gate.request_credentials = _instant_provide  # type: ignore[method-assign]


def _make_mock_runner(key_value: str = "di_test_key_abc123") -> Any:
    """Build a mock MurphyNativeRunner that returns successful run() results."""
    from unittest.mock import MagicMock

    mock_runner = MagicMock()
    # run() returns a result dict (synchronous, not async)
    mock_runner.run = MagicMock(return_value={
        "status": "passed",
        "step_results": [{"status": "ok", "text": key_value, "value": key_value}],
    })
    mock_runner.run_suite = MagicMock(return_value=[{
        "status": "passed",
        "step_results": [{"status": "ok", "text": key_value, "value": key_value}],
    }])
    return mock_runner


# ---------------------------------------------------------------------------
# harvest_all — Murphy HITL UI opening
# ---------------------------------------------------------------------------

class TestHarvestAllHITLUIOpening:
    @pytest.mark.asyncio
    async def test_hitl_ui_opened_when_interactive(self, harvester, cred_gate, monkeypatch):
        """harvest_all() opens the Murphy HITL terminal URL in system browser."""
        harvester._interactive = True
        opened_urls: list = []
        monkeypatch.setattr("webbrowser.open", lambda url: opened_urls.append(url) or True)

        # Abort immediately after credential decline so the test stays fast
        original_rc = cred_gate.request_credentials

        def _decline(purpose, suggested_email=""):
            req = original_rc(purpose=purpose, suggested_email=suggested_email)
            cred_gate.decline(req.request_id)
            return req

        with patch.object(cred_gate, "request_credentials", side_effect=_decline):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                await harvester.harvest_all()

        murphy_ui_opened = any("localhost" in u and "terminal" in u for u in opened_urls)
        assert murphy_ui_opened, (
            f"Murphy HITL terminal URL not opened. Opened URLs: {opened_urls}"
        )

    @pytest.mark.asyncio
    async def test_hitl_ui_not_opened_when_non_interactive(self, harvester, cred_gate, monkeypatch):
        """harvest_all() does NOT open browser UIs when interactive=False."""
        harvester._interactive = False
        opened_urls: list = []
        monkeypatch.setattr("webbrowser.open", lambda url: opened_urls.append(url) or True)

        original_rc = cred_gate.request_credentials

        def _decline(purpose, suggested_email=""):
            req = original_rc(purpose=purpose, suggested_email=suggested_email)
            cred_gate.decline(req.request_id)
            return req

        with patch.object(cred_gate, "request_credentials", side_effect=_decline):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                await harvester.harvest_all()

        assert opened_urls == [], (
            f"Browser should not open in non-interactive mode. Got: {opened_urls}"
        )

    @pytest.mark.asyncio
    async def test_hitl_ui_opens_before_credential_gate(
        self, harvester, cred_gate, monkeypatch
    ):
        """The Murphy UI must open BEFORE the credential collection gate fires."""
        harvester._interactive = True
        event_log: list = []
        monkeypatch.setattr(
            "webbrowser.open",
            lambda url: event_log.append(("browser_open", url)) or True,
        )
        original_rc = cred_gate.request_credentials

        def _track_and_decline(purpose, suggested_email=""):
            event_log.append(("credential_request",))
            req = original_rc(purpose=purpose, suggested_email=suggested_email)
            cred_gate.decline(req.request_id)
            return req

        with patch.object(cred_gate, "request_credentials", side_effect=_track_and_decline):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                await harvester.harvest_all()

        # Browser open must appear before credential_request in the log
        types = [e[0] for e in event_log]
        assert "browser_open" in types
        assert "credential_request" in types
        browser_idx = types.index("browser_open")
        cred_idx = types.index("credential_request")
        assert browser_idx < cred_idx, (
            "Murphy HITL UI must open before the credential collection gate is shown"
        )


# ---------------------------------------------------------------------------
# REST router
# ---------------------------------------------------------------------------

class TestKeyHarvesterRouter:
    """Tests for create_key_harvester_router() using FastAPI TestClient."""

    @pytest.fixture
    def test_client(self):
        pytest.importorskip("fastapi")
        pytest.importorskip("httpx")
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from key_harvester import create_key_harvester_router, get_shared_gates
        import key_harvester as kh

        # Reset shared state for each test
        kh._shared_tos_gate = None
        kh._shared_credential_gate = None
        kh._shared_harvester = None

        app = FastAPI()
        router = create_key_harvester_router()
        assert router is not None
        app.include_router(router)
        return TestClient(app)

    def test_status_endpoint_returns_200(self, test_client):
        resp = test_client.get("/api/key-harvester/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "harvest" in body
        assert "providers_total" in body
        assert body["providers_total"] == len(PROVIDER_RECIPES)

    def test_pending_tos_empty_on_fresh_start(self, test_client):
        resp = test_client.get("/api/key-harvester/pending-tos")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["count"] == 0

    def test_pending_credentials_empty_on_fresh_start(self, test_client):
        resp = test_client.get("/api/key-harvester/pending-credentials")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["count"] == 0

    def test_tos_approve_unknown_id_returns_false(self, test_client):
        resp = test_client.post(
            "/api/key-harvester/tos/nonexistent/approve",
            json={"approved_by": "test_user"},
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is False

    def test_tos_reject_unknown_id_returns_false(self, test_client):
        resp = test_client.post(
            "/api/key-harvester/tos/nonexistent/reject",
            json={"rejected_by": "test_user", "reason": "test"},
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is False

    def test_tos_skip_unknown_id_returns_false(self, test_client):
        resp = test_client.post("/api/key-harvester/tos/nonexistent/skip")
        assert resp.status_code == 200
        assert resp.json()["success"] is False

    def test_credential_decline_unknown_id_returns_false(self, test_client):
        resp = test_client.post("/api/key-harvester/credentials/nonexistent/decline")
        assert resp.status_code == 200
        assert resp.json()["success"] is False

    def test_audit_log_empty_on_fresh_start(self, test_client):
        resp = test_client.get("/api/key-harvester/audit-log")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["audit_log"] == []

    def test_full_tos_approve_flow(self, test_client):
        """Create a TOS request via gate, then approve it via REST endpoint."""
        from key_harvester import get_shared_gates
        tos_gate, _ = get_shared_gates()
        req = tos_gate.request_approval("deepinfra", screenshot_path="/tmp/test.png")

        # Should now show up in pending-tos
        resp = test_client.get("/api/key-harvester/pending-tos")
        assert resp.json()["count"] == 1
        assert resp.json()["requests"][0]["provider"] == "deepinfra"

        # Approve via REST
        resp = test_client.post(
            f"/api/key-harvester/tos/{req.request_id}/approve",
            json={"approved_by": "test_approver"},
        )
        assert resp.json()["success"] is True

        # Should now be removed from pending
        resp = test_client.get("/api/key-harvester/pending-tos")
        assert resp.json()["count"] == 0

        # Audit log should have one entry
        resp = test_client.get("/api/key-harvester/audit-log")
        assert len(resp.json()["audit_log"]) == 1

    def test_full_credential_provide_flow(self, test_client):
        """Create a credential request via gate, then provide via REST."""
        from key_harvester import get_shared_gates
        _, cred_gate = get_shared_gates()
        req = cred_gate.request_credentials(purpose="test")

        resp = test_client.get("/api/key-harvester/pending-credentials")
        assert resp.json()["count"] == 1

        resp = test_client.post(
            f"/api/key-harvester/credentials/{req.request_id}/provide",
            json={"email": "user@example.com", "password": "TestPass1!"},
        )
        assert resp.json()["success"] is True

        # Now pending count drops to 0
        resp = test_client.get("/api/key-harvester/pending-credentials")
        assert resp.json()["count"] == 0

    def test_tos_message_included_in_pending_list(self, test_client):
        """pending-tos should include the formatted message for the HITL UI."""
        from key_harvester import get_shared_gates
        tos_gate, _ = get_shared_gates()
        tos_gate.request_approval("openai")

        resp = test_client.get("/api/key-harvester/pending-tos")
        items = resp.json()["requests"]
        assert len(items) == 1
        msg = items[0]["message"]
        assert "openai" in msg.lower() or "OpenAI" in msg


# ---------------------------------------------------------------------------
# get_shared_gates()
# ---------------------------------------------------------------------------

class TestGetSharedGates:
    def test_returns_same_instances_on_subsequent_calls(self):
        import key_harvester as kh
        kh._shared_tos_gate = None
        kh._shared_credential_gate = None

        from key_harvester import get_shared_gates
        g1 = get_shared_gates()
        g2 = get_shared_gates()
        assert g1[0] is g2[0]
        assert g1[1] is g2[1]

    def test_returns_correct_types(self):
        import key_harvester as kh
        kh._shared_tos_gate = None
        kh._shared_credential_gate = None

        from key_harvester import get_shared_gates
        tos_gate, cred_gate = get_shared_gates()
        assert isinstance(tos_gate, TOSAcceptanceGate)
        assert isinstance(cred_gate, UserCredentialGate)


# ---------------------------------------------------------------------------
# runner.run() integration (mock runner)
# ---------------------------------------------------------------------------

class TestSharedPageInSignupFlow:
    @pytest.mark.asyncio
    async def test_shared_page_called_when_playwright_available(
        self, harvester, tos_gate, monkeypatch
    ):
        """When native automation is available, _run_signup_flow uses runner.run()."""
        harvester._user_email = "test@example.com"
        harvester._user_password = "pwd123"

        recipe = _RECIPE_MAP["deepinfra"]
        monkeypatch.delenv(recipe.env_var, raising=False)

        original = tos_gate.request_approval

        def patched_request(provider_key, screenshot_path=None):
            req = original(provider_key, screenshot_path)
            tos_gate.approve(req.request_id, approved_by="tester")
            return req

        mock_runner = _make_mock_runner(key_value="di_testkey_abc123456789xyz")
        with patch.object(tos_gate, "request_approval", side_effect=patched_request):
            with patch("key_harvester.MurphyNativeRunner", return_value=mock_runner):
                with patch("key_harvester._HAS_NATIVE_AUTOMATION", True):
                    with patch("asyncio.sleep", new_callable=AsyncMock):
                        await harvester._acquire_single(recipe)

        # runner.run() was called (navigate + form fill + TOS + key extract ...)
        mock_runner.run.assert_called()
        # First call should be the form-fill NativeTask with OPEN_URL + GHOST_TYPE
        first_call_task = mock_runner.run.call_args_list[0][0][0]
        assert isinstance(first_call_task, NativeTask)
        step_actions = [step.action for step in first_call_task.steps]
        assert ActionType.OPEN_URL in step_actions
        assert ActionType.GHOST_TYPE in step_actions
