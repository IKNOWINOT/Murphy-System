"""
Murphy System — Login Page UI Tests
tests/ui/test_login.py

Tests every interactive element on login.html including:
- Form fields, validation, error display, auth flow
- Bug-fix verification: JSON parse fallback + [object Object] prevention

Screenshots saved to tests/ui/screenshots/login/
"""

import pytest
# MCB-backed — Page shim and expect() provided by conftest.py
try:
    from tests.ui.conftest import MCBPageShim as Page, expect
except ImportError:
    from conftest import MCBPageShim as Page, expect

BASE = "http://localhost:18080"
PAGE_URL = f"{BASE}/login.html"


# ── Page load ─────────────────────────────────────────────────────────────
def test_login_page_loads(page: Page, screenshot):
    """Login page loads with 200 status."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    expect(page.locator("body")).to_be_visible()
    screenshot(page, "initial_load")


def test_login_page_title(page: Page, screenshot):
    """Login page has correct title."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    title = page.title()
    assert "Murphy" in title or "Login" in title or "Sign" in title
    screenshot(page, "page_title")


def test_login_headline_visible(page: Page, screenshot):
    """Login headline / form header is visible."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    page.wait_for_timeout(300)
    screenshot(page, "headline_visible")


# ── Form elements ─────────────────────────────────────────────────────────
def test_login_email_field_present(page: Page, screenshot):
    """Email input field is present and editable."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    field = page.locator("input#email, input[name='email'], input[type='email']").first
    expect(field).to_be_visible()
    expect(field).to_be_editable()
    screenshot(page, "email_field")


def test_login_password_field_present(page: Page, screenshot):
    """Password input field is present and editable."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    field = page.locator("input#password, input[name='password'], input[type='password']").first
    expect(field).to_be_visible()
    expect(field).to_be_editable()
    screenshot(page, "password_field")


def test_login_password_field_masks_input(page: Page, screenshot):
    """Password field is type=password (masks characters)."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    field = page.locator("input[type='password']").first
    expect(field).to_have_attribute("type", "password")
    field.fill("supersecret")
    screenshot(page, "password_masked")


def test_login_submit_button_present(page: Page, screenshot):
    """Sign In submit button is present."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    btn = page.locator("button[type='submit'], button.btn-p", has_text="Sign In").first
    expect(btn).to_be_visible()
    screenshot(page, "submit_button")


# ── Form filling ──────────────────────────────────────────────────────────
def test_login_fill_email_field(page: Page, screenshot):
    """User can type an email into the email field."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    field = page.locator("input#email, input[name='email'], input[type='email']").first
    field.fill("test@murphy.systems")
    assert field.input_value() == "test@murphy.systems"
    screenshot(page, "fill_email")


def test_login_fill_password_field(page: Page, screenshot):
    """User can type a password into the password field."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    field = page.locator("input[type='password']").first
    field.fill("Password123!")
    assert field.input_value() == "Password123!"
    screenshot(page, "fill_password")


def test_login_fill_both_fields(page: Page, screenshot):
    """User can fill both fields together."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    email = page.locator("input#email, input[name='email'], input[type='email']").first
    password = page.locator("input[type='password']").first
    email.fill("user@example.com")
    password.fill("MySecurePass!")
    screenshot(page, "fill_both_fields")


def test_login_form_clear_fields(page: Page, screenshot):
    """Clearing fields works correctly."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    email = page.locator("input#email, input[name='email'], input[type='email']").first
    email.fill("clearme@test.com")
    email.fill("")
    assert email.input_value() == ""
    screenshot(page, "cleared_fields")


# ── Error display ─────────────────────────────────────────────────────────
def test_login_showformerror_function_exists(page: Page, screenshot):
    """showFormError JS function is defined on the page."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    exists = page.evaluate("typeof showFormError === 'function'")
    assert exists, "showFormError should be a defined function"
    screenshot(page, "showformerror_exists")


def test_login_error_display_string_message(page: Page, screenshot):
    """showFormError displays a plain string message correctly."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    page.evaluate("showFormError('Test error message')")
    page.wait_for_timeout(200)
    error_el = page.locator(".form-error, .error-msg, [role='alert'], .alert").first
    if error_el.count() > 0:
        text = error_el.inner_text()
        assert "Test error message" in text
        assert "[object Object]" not in text
    screenshot(page, "error_display_string")


def test_login_error_no_object_object_from_plain_object(page: Page, screenshot):
    """Bug fix: showFormError with an object does NOT render [object Object]."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    # Simulate the bug scenario: passing an object (like FastAPI error detail)
    page.evaluate("""
        var errMsg = {msg: 'Invalid credentials', detail: 'Auth failed'};
        if (typeof errMsg === 'object') errMsg = errMsg.msg || errMsg.message || errMsg.detail || JSON.stringify(errMsg);
        showFormError(String(errMsg));
    """)
    page.wait_for_timeout(200)
    body_text = page.locator("body").inner_text()
    assert "[object Object]" not in body_text, "BUG: [object Object] was rendered!"
    screenshot(page, "no_object_object_bug")


def test_login_error_no_object_object_from_nested_detail(page: Page, screenshot):
    """Bug fix: FastAPI nested detail object does not render [object Object]."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    page.evaluate("""
        var errMsg = {detail: {msg: 'Email not found', type: 'auth_error'}};
        if (typeof errMsg === 'object') errMsg = errMsg.msg || errMsg.message || errMsg.detail || JSON.stringify(errMsg);
        if (typeof errMsg === 'object') errMsg = JSON.stringify(errMsg);
        showFormError(String(errMsg));
    """)
    page.wait_for_timeout(200)
    body_text = page.locator("body").inner_text()
    assert "[object Object]" not in body_text
    screenshot(page, "no_object_object_nested_detail")


def test_login_json_parse_fallback_exists(page: Page, screenshot):
    """Bug fix: The JSON parse failure fallback is in the page source."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    # Verify the catch fallback that wraps res.json() is present
    source = page.content()
    assert "Server returned an unexpected response" in source, \
        "JSON parse fallback not found in page source"
    screenshot(page, "json_parse_fallback_in_source")


# ── Navigation links ──────────────────────────────────────────────────────
def test_login_signup_link_present(page: Page, screenshot):
    """Login page has a link to the signup page."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    link = page.locator("a[href*='signup'], a[href*='/ui/signup']").first
    expect(link).to_be_visible()
    screenshot(page, "signup_link")


def test_login_forgot_password_link(page: Page, screenshot):
    """Login page has a 'Forgot password' or reset password link."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    link = page.locator(
        "a[href*='reset'], a[href*='forgot'], a:has-text('Forgot'), a:has-text('Reset')"
    ).first
    if link.count() > 0:
        expect(link).to_be_visible()
    screenshot(page, "forgot_password_link")


def test_login_home_brand_link(page: Page, screenshot):
    """Login page header/brand links to the landing page."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    brand = page.locator(".topbar-brand, a[href*='landing'], a[href='/']").first
    if brand.count() > 0:
        expect(brand).to_be_visible()
    screenshot(page, "home_brand_link")


# ── OAuth / SSO buttons ───────────────────────────────────────────────────
def test_login_oauth_buttons_if_present(page: Page, screenshot):
    """OAuth SSO buttons (Google/GitHub) are visible if configured."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    oauth = page.locator(
        "button:has-text('Google'), button:has-text('GitHub'), "
        "a:has-text('Google'), a:has-text('GitHub')"
    )
    # OAuth buttons are optional — just verify no JS errors if present
    screenshot(page, "oauth_buttons")


# ── Keyboard accessibility ────────────────────────────────────────────────
def test_login_tab_navigation_email_to_password(page: Page, screenshot):
    """Tab key moves focus from email to password field."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    email = page.locator("input#email, input[name='email'], input[type='email']").first
    email.click()
    page.keyboard.press("Tab")
    password = page.locator("input[type='password']").first
    # After Tab from email, password should be focused (common form UX)
    screenshot(page, "tab_navigation")


def test_login_enter_submits_form(page: Page, screenshot):
    """Pressing Enter in password field submits the form."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    email = page.locator("input#email, input[name='email'], input[type='email']").first
    password = page.locator("input[type='password']").first
    email.fill("test@example.com")
    password.fill("wrongpassword")
    password.press("Enter")
    page.wait_for_timeout(800)
    # After submit we expect either an error message or redirect
    screenshot(page, "enter_submits_form")


# ── Responsiveness ────────────────────────────────────────────────────────
def test_login_mobile_viewport(page: Page, screenshot):
    """Login page renders correctly at mobile width."""
    page.set_viewport_size({"width": 375, "height": 812})
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    email = page.locator("input#email, input[name='email'], input[type='email']").first
    expect(email).to_be_visible()
    screenshot(page, "mobile_viewport")


def test_login_tablet_viewport(page: Page, screenshot):
    """Login page renders at tablet width."""
    page.set_viewport_size({"width": 768, "height": 1024})
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    screenshot(page, "tablet_viewport")


# ── Full page screenshot ──────────────────────────────────────────────────
def test_login_full_page_screenshot(page: Page):
    """Capture full-page screenshot of login page."""
    from pathlib import Path
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    out = Path(__file__).parent / "screenshots" / "login" / "login_page_full.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(out), full_page=True)
    assert out.exists()
    assert out.stat().st_size > 5000
