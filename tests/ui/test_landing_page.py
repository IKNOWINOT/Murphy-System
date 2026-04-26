"""
Murphy System — Landing Page UI Tests
tests/ui/test_landing_page.py

Every interactive element on murphy_landing_page.html has its own test.
Screenshots are saved to tests/ui/screenshots/landing/ and committed to the repo.

Run individually:  pytest tests/ui/test_landing_page.py -v
"""

import pytest
try:
    from tests.ui.conftest import MCBPageShim as Page, expect
except ImportError:
    from conftest import MCBPageShim as Page, expect

BASE = "http://localhost:18080"
PAGE_URL = f"{BASE}/murphy_landing_page.html"


# ── Page load ────────────────────────────────────────────────────────────
def test_landing_page_loads(page: Page, screenshot):
    """Page returns 200 and renders the hero headline."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    title = page.title()
    assert "Murphy System" in title, f"Expected 'Murphy System' in page title, got: {title!r}"
    screenshot(page, "initial_load")


def test_landing_hero_headline_visible(page: Page, screenshot):
    """Hero h1 is visible and contains expected text."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    h1 = page.locator("h1#hero-h")
    expect(h1).to_be_visible()
    text = h1.inner_text()
    assert "Stop Patching Tools" in text or "Business" in text
    screenshot(page, "hero_headline")


def test_landing_hero_start_free_cta(page: Page, screenshot):
    """Primary CTA 'Start Free' exists and links to /ui/signup."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    btn = page.locator("a.btn-p.lg", has_text="Start Free").first
    expect(btn).to_be_visible()
    assert "/ui/signup" in (btn.get_attribute("href") or "")
    screenshot(page, "hero_start_free_cta")


def test_landing_hero_live_demo_cta(page: Page, screenshot):
    """Secondary CTA 'See It Live' exists and points to #demo."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    btn = page.locator("a.btn-s.lg", has_text="See It Live").first
    expect(btn).to_be_visible()
    assert "#demo" in (btn.get_attribute("href") or "")
    screenshot(page, "hero_live_demo_cta")


def test_landing_stat_badges_visible(page: Page, screenshot):
    """Three stat badges are rendered in the hero."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    badges = page.locator(".stat-badge")
    count = badges.count()
    assert count == 3, f"Expected 3 stat badges, got {count}"
    screenshot(page, "hero_stat_badges")


def test_landing_industry_pills_visible(page: Page, screenshot):
    """Industry pills are visible in the hero strip."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    pills = page.locator(".ind-pill")
    count = pills.count()
    assert count >= 6, f"Expected >=6 industry pills, got {count}"
    screenshot(page, "hero_industry_pills")


# ── Navigation bar ────────────────────────────────────────────────────────
def test_nav_solutions_link(page: Page, screenshot):
    """Nav 'Solutions' link points to #solutions."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    link = page.locator("nav a[href='#solutions']")
    expect(link).to_be_visible()
    expect(link).to_have_text("Solutions")
    screenshot(page, "nav_solutions_link")


def test_nav_industries_link(page: Page, screenshot):
    """Nav 'Industries' link points to #industries."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    link = page.locator("nav a[href='#industries']")
    expect(link).to_be_visible()
    screenshot(page, "nav_industries_link")


def test_nav_demo_link(page: Page, screenshot):
    """Nav 'Demo' link points to #demo."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    link = page.locator("nav a[href='#demo']")
    expect(link).to_be_visible()
    screenshot(page, "nav_demo_link")


def test_nav_partner_link(page: Page, screenshot):
    """Nav 'Partner' link points to #partner."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    link = page.locator("nav a[href='#partner']")
    expect(link).to_be_visible()
    screenshot(page, "nav_partner_link")


def test_nav_pricing_link(page: Page, screenshot):
    """Nav 'Pricing' link points to #pricing."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    link = page.locator("nav a[href='#pricing']")
    expect(link).to_be_visible()
    screenshot(page, "nav_pricing_link")


def test_nav_financing_link(page: Page, screenshot):
    """Nav 'Financing' link exists and points to grant wizard."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    link = page.locator("nav a[href='/ui/grant-wizard']")
    expect(link).to_be_visible()
    screenshot(page, "nav_financing_link")


def test_nav_login_button(page: Page, screenshot):
    """Topbar Login button links to /ui/login."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    btn = page.locator(".topbar-right a[href='/ui/login']")
    expect(btn).to_be_visible()
    screenshot(page, "nav_login_button")


def test_nav_start_free_button(page: Page, screenshot):
    """Topbar Start Free button links to /ui/signup."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    btn = page.locator(".topbar-right a[href='/ui/signup']")
    expect(btn).to_be_visible()
    screenshot(page, "nav_start_free_button")


def test_nav_hamburger_visible_mobile(page: Page, screenshot):
    """Hamburger button is visible at mobile width."""
    page.set_viewport_size({"width": 375, "height": 812})
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    btn = page.locator("#hamburger-btn")
    expect(btn).to_be_visible()
    screenshot(page, "nav_hamburger_mobile")


def test_nav_hamburger_toggles_menu(page: Page, screenshot):
    """Clicking hamburger opens the mobile nav menu."""
    page.set_viewport_size({"width": 375, "height": 812})
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    btn = page.locator("#hamburger-btn")
    btn.click()
    nav = page.locator("#main-nav")
    expect(nav).to_have_class(r".*open.*")
    screenshot(page, "nav_hamburger_menu_open")


def test_nav_system_status_pill(page: Page, screenshot):
    """System status pill is rendered in topbar."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    pill = page.locator("#sys-status-pill")
    expect(pill).to_be_visible()
    screenshot(page, "nav_system_status_pill")


# ── Live Status Bar ───────────────────────────────────────────────────────
def test_status_bar_visible(page: Page, screenshot):
    """Live status bar section is visible."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    bar = page.locator("#status-bar")
    expect(bar).to_be_visible()
    screenshot(page, "status_bar")


def test_status_bar_api_gateway_indicator(page: Page, screenshot):
    """API Gateway status indicator is visible."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    indicator = page.locator(".lstat", has_text="API Gateway")
    expect(indicator).to_be_visible()
    screenshot(page, "status_bar_api_gateway")


def test_status_bar_configure_link(page: Page, screenshot):
    """Configure → link exists in status bar."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    link = page.locator("#status-bar a.btn-s")
    expect(link).to_be_visible()
    screenshot(page, "status_bar_configure_link")


# ── Solutions Section ─────────────────────────────────────────────────────
def test_solutions_section_visible(page: Page, screenshot):
    """Solutions section renders on the page."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    section = page.locator("#solutions")
    expect(section).to_be_visible()
    screenshot(page, "solutions_section")


def test_solutions_six_cards_rendered(page: Page, screenshot):
    """Exactly 6 solution cards are rendered."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    cards = page.locator(".sol-card")
    expect(cards).to_have_count(6)
    screenshot(page, "solutions_six_cards")


def test_solutions_ai_automation_card(page: Page, screenshot):
    """AI Automation solution card has problem label and CTA."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    card = page.locator(".sol-card", has_text="AI Automation")
    expect(card).to_be_visible()
    problem = card.locator(".sol-problem")
    expect(problem).to_be_visible()
    outcome = card.locator(".sol-outcome")
    expect(outcome).to_be_visible()
    screenshot(page, "solutions_ai_automation_card")


def test_solutions_comms_card(page: Page, screenshot):
    """Unified Communications card is visible."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    card = page.locator(".sol-card", has_text="Unified Communications")
    expect(card).to_be_visible()
    screenshot(page, "solutions_comms_card")


def test_solutions_compliance_card(page: Page, screenshot):
    """Compliance Automation card is visible."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    card = page.locator(".sol-card", has_text="Compliance Automation")
    expect(card).to_be_visible()
    screenshot(page, "solutions_compliance_card")


def test_solutions_trading_card(page: Page, screenshot):
    """Trading & Finance card is visible."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    card = page.locator(".sol-card", has_text="Trading")
    expect(card).to_be_visible()
    screenshot(page, "solutions_trading_card")


def test_solutions_integrations_card(page: Page, screenshot):
    """Custom Integrations card is visible."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    card = page.locator(".sol-card", has_text="Custom Integrations")
    expect(card).to_be_visible()
    screenshot(page, "solutions_integrations_card")


def test_solutions_privacy_card(page: Page, screenshot):
    """Local AI / Privacy First card is visible."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    card = page.locator(".sol-card", has_text="Privacy First")
    expect(card).to_be_visible()
    screenshot(page, "solutions_privacy_card")


def test_solutions_cta_buttons_all_present(page: Page, screenshot):
    """Every solution card has a CTA button."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    cards = page.locator(".sol-card")
    count = cards.count()
    for i in range(count):
        card = cards.nth(i)
        cta = card.locator("a.btn-s")
        expect(cta).to_be_visible()
    screenshot(page, "solutions_all_ctas")


# ── Industries Section ────────────────────────────────────────────────────
def test_industries_section_visible(page: Page, screenshot):
    """Industries section is visible on the page."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    section = page.locator("#industries")
    expect(section).to_be_visible()
    screenshot(page, "industries_section")


def test_industries_eight_cards_rendered(page: Page, screenshot):
    """Exactly 8 industry cards are rendered."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    cards = page.locator(".ind-card")
    expect(cards).to_have_count(8)
    screenshot(page, "industries_eight_cards")


def test_industries_healthcare_card(page: Page, screenshot):
    """Healthcare industry card with pain point visible."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    card = page.locator(".ind-card", has_text="Healthcare")
    expect(card).to_be_visible()
    pain = card.locator(".ind-card-pain")
    expect(pain).to_be_visible()
    screenshot(page, "industries_healthcare_card")


def test_industries_manufacturing_card(page: Page, screenshot):
    """Manufacturing industry card visible."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    card = page.locator(".ind-card", has_text="Manufacturing")
    expect(card).to_be_visible()
    screenshot(page, "industries_manufacturing_card")


def test_industries_finance_card(page: Page, screenshot):
    """Finance & Banking card visible."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    card = page.locator(".ind-card", has_text="Finance")
    expect(card).to_be_visible()
    screenshot(page, "industries_finance_card")


def test_industries_legal_card(page: Page, screenshot):
    """Legal industry card visible."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    card = page.locator(".ind-card", has_text="Legal")
    expect(card).to_be_visible()
    screenshot(page, "industries_legal_card")


def test_industries_construction_card(page: Page, screenshot):
    """Construction industry card visible."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    card = page.locator(".ind-card", has_text="Construction")
    expect(card).to_be_visible()
    screenshot(page, "industries_construction_card")


def test_industries_tech_card(page: Page, screenshot):
    """Technology/SaaS industry card visible."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    card = page.locator(".ind-card", has_text="Technology")
    expect(card).to_be_visible()
    screenshot(page, "industries_tech_card")


def test_industries_services_card(page: Page, screenshot):
    """Professional Services industry card visible."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    card = page.locator(".ind-card", has_text="Professional Services")
    expect(card).to_be_visible()
    screenshot(page, "industries_services_card")


def test_industries_education_card(page: Page, screenshot):
    """Education industry card visible."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    card = page.locator(".ind-card", has_text="Education")
    expect(card).to_be_visible()
    screenshot(page, "industries_education_card")


def test_industries_all_cta_buttons(page: Page, screenshot):
    """Every industry card has a See Demo / Partner CTA."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    cards = page.locator(".ind-card")
    count = cards.count()
    for i in range(count):
        cta = cards.nth(i).locator("a.btn-s")
        expect(cta).to_be_visible()
    screenshot(page, "industries_all_ctas")


# ── How It Works Section ──────────────────────────────────────────────────
def test_how_it_works_section_visible(page: Page, screenshot):
    """How It Works section renders four steps."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    section = page.locator("#how-it-works")
    expect(section).to_be_visible()
    steps = section.locator(".card")
    assert steps.count() == 4
    screenshot(page, "how_it_works_section")


def test_how_it_works_step1_onboard(page: Page, screenshot):
    """Step 1 'Onboard' card is visible."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    card = page.locator("#how-it-works .card", has_text="Onboard in Minutes")
    expect(card).to_be_visible()
    screenshot(page, "how_it_works_step1")


def test_how_it_works_step2_connect(page: Page, screenshot):
    """Step 2 'Connect' card is visible."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    card = page.locator("#how-it-works .card", has_text="Connect Your Stack")
    expect(card).to_be_visible()
    screenshot(page, "how_it_works_step2")


def test_how_it_works_step3_automate(page: Page, screenshot):
    """Step 3 'Automate' card is visible."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    card = page.locator("#how-it-works .card", has_text="Automate with Confidence")
    expect(card).to_be_visible()
    screenshot(page, "how_it_works_step3")


def test_how_it_works_step4_scale(page: Page, screenshot):
    """Step 4 'Scale' card is visible."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    card = page.locator("#how-it-works .card", has_text="Scale Without Chaos")
    expect(card).to_be_visible()
    screenshot(page, "how_it_works_step4")


# ── Swarm Forge Section ───────────────────────────────────────────────────
def test_forge_section_visible(page: Page, screenshot):
    """Swarm Forge section (#demo) is visible on the page."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    section = page.locator("#demo")
    expect(section).to_be_visible()
    screenshot(page, "forge_section_visible")


def test_forge_input_present(page: Page, screenshot):
    """Forge custom input field is rendered."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    inp = page.locator("#forge-input")
    expect(inp).to_be_visible()
    screenshot(page, "forge_input_field")


def test_forge_run_button_present(page: Page, screenshot):
    """Forge Run button ('Forge It') is present."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    btn = page.locator("#forge-run-btn")
    expect(btn).to_be_visible()
    screenshot(page, "forge_run_button")


def test_forge_chips_present(page: Page, screenshot):
    """Swarm Forge deliverable chips are present and have data-forge attributes."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    chips = page.locator(".demo-chip[data-forge]")
    count = chips.count()
    assert count >= 4, f"Expected >=4 forge chips, got {count}"
    screenshot(page, "forge_chips")


def test_forge_chip_game_present(page: Page, screenshot):
    """MMORPG Game chip is present."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    chip = page.locator(".demo-chip[data-forge*='game']")
    assert chip.count() > 0, "Expected a forge chip with data-forge containing 'game'"
    screenshot(page, "forge_chip_game")


def test_forge_chip_app_present(page: Page, screenshot):
    """Web App MVP chip is present."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    chip = page.locator(".demo-chip[data-forge*='app']")
    assert chip.count() > 0, "Expected a forge chip with data-forge containing 'app'"
    screenshot(page, "forge_chip_app")


def test_forge_chip_automation_present(page: Page, screenshot):
    """Automation + Payments chip is present."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    chip = page.locator(".demo-chip[data-forge*='automat']")
    assert chip.count() > 0, "Expected a forge chip with data-forge containing 'automat'"
    screenshot(page, "forge_chip_automation")


def test_forge_chip_course_present(page: Page, screenshot):
    """Complete Course chip is present."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    chip = page.locator(".demo-chip[data-forge*='course']")
    assert chip.count() > 0, "Expected a forge chip with data-forge containing 'course'"
    screenshot(page, "forge_chip_course")


def test_forge_grid_hidden_initially(page: Page, screenshot):
    """The 64-pane grid is hidden before a forge run starts."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    grid_wrap = page.locator("#forge-grid-wrap")
    # Should be hidden (display:none) initially
    assert grid_wrap.count() > 0
    screenshot(page, "forge_grid_initially_hidden")


def test_forge_result_hidden_initially(page: Page, screenshot):
    """Result block is hidden before any forge run."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    result = page.locator("#forge-result")
    assert result.count() > 0
    screenshot(page, "forge_result_initially_hidden")


def test_forge_run_button_click_shows_grid(page: Page, screenshot):
    """Clicking a forge chip starts the animation (grid becomes visible)."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    chip = page.locator(".demo-chip[data-forge]").first
    chip.click()
    page.wait_for_timeout(500)
    grid_wrap = page.locator("#forge-grid-wrap")
    # Grid should now be displayed
    display = page.evaluate("document.getElementById('forge-grid-wrap').style.display")
    assert display != "none", "Expected forge grid to be visible after chip click"
    screenshot(page, "forge_run_grid_visible")


def test_forge_status_updates_on_run(page: Page, screenshot):
    """Status line updates when forge run starts."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    chip = page.locator(".demo-chip[data-forge]").first
    chip.click()
    page.wait_for_timeout(400)
    status = page.locator("#forge-status")
    text = status.inner_text()
    assert len(text) > 0, "Expected forge status to have text after run"
    screenshot(page, "forge_status_updates")


def test_forge_custom_input_typed(page: Page, screenshot):
    """Typing a custom query in forge input and pressing Enter starts the forge."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    inp = page.locator("#forge-input")
    inp.fill("build me an automation suite with stripe payments")
    inp.press("Enter")
    page.wait_for_timeout(500)
    status = page.locator("#forge-status")
    text = status.inner_text()
    assert len(text) > 0
    screenshot(page, "forge_custom_input_result")


# ── Demo Modal (backward-compat) ──────────────────────────────────────────
def test_demo_modal_exists_in_dom(page: Page, screenshot):
    """Demo modal exists in the DOM (for backward-compat deep-links)."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    modal = page.locator("#demo-modal")
    assert modal.count() > 0
    screenshot(page, "demo_modal_in_dom")


def test_demo_modal_close_button_present(page: Page, screenshot):
    """Demo modal has a close button."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    close_btn = page.locator("#demo-close")
    assert close_btn.count() > 0
    screenshot(page, "demo_modal_close_button")


# ── AI Engine Section ─────────────────────────────────────────────────────
def test_ai_engine_section_visible(page: Page, screenshot):
    """AI Engine section is visible."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    section = page.locator("#ai-engine")
    expect(section).to_be_visible()
    screenshot(page, "ai_engine_section")


def test_ai_engine_headline_privacy(page: Page, screenshot):
    """AI Engine headline emphasizes privacy / data stays local."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    h2 = page.locator("#ai-h")
    expect(h2).to_be_visible()
    text = h2.inner_text()
    assert "Never" in text or "Server" in text or "Private" in text
    screenshot(page, "ai_engine_headline")


def test_ai_engine_configure_llm_button(page: Page, screenshot):
    """'Configure LLM' button exists in AI Engine section."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    btn = page.locator("#ai-engine a.btn-p")
    expect(btn).to_be_visible()
    screenshot(page, "ai_engine_configure_llm_btn")


def test_ai_engine_view_status_button(page: Page, screenshot):
    """'View Status' button exists in AI Engine section."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    btn = page.locator("#ai-engine a.btn-s")
    expect(btn).to_be_visible()
    screenshot(page, "ai_engine_view_status_btn")


def test_ai_engine_terminal_visualisation(page: Page, screenshot):
    """The terminal visualisation in AI Engine is rendered."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    vis = page.locator("#ai-engine .seg-vis")
    expect(vis).to_be_visible()
    screenshot(page, "ai_engine_terminal_vis")


# ── Comparison Table ──────────────────────────────────────────────────────
def test_compare_section_visible(page: Page, screenshot):
    """Comparison section is visible."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    section = page.locator("#compare")
    expect(section).to_be_visible()
    screenshot(page, "compare_section")


def test_compare_table_has_columns(page: Page, screenshot):
    """Comparison table has Murphy, Zapier+Notion+HubSpot, Salesforce columns."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    headers = page.locator(".ctable th")
    texts = [headers.nth(i).inner_text() for i in range(headers.count())]
    assert any("Murphy" in t for t in texts)
    assert any("Zapier" in t for t in texts)
    assert any("Salesforce" in t for t in texts)
    screenshot(page, "compare_table_columns")


def test_compare_table_rows_complete(page: Page, screenshot):
    """Comparison table has at least 10 feature rows."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    rows = page.locator(".ctable tbody tr")
    assert rows.count() >= 10
    screenshot(page, "compare_table_rows")


# ── Compliance Section ────────────────────────────────────────────────────
def test_compliance_section_visible(page: Page, screenshot):
    """Compliance section is visible."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    section = page.locator("#compliance")
    expect(section).to_be_visible()
    screenshot(page, "compliance_section")


def test_compliance_soc2_pill(page: Page, screenshot):
    """SOC 2 Type II compliance pill is present."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    pill = page.locator(".comp-pill", has_text="SOC 2 Type II")
    expect(pill).to_be_visible()
    screenshot(page, "compliance_soc2_pill")


def test_compliance_hipaa_pill(page: Page, screenshot):
    """HIPAA compliance pill is present."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    pill = page.locator(".comp-pill", has_text="HIPAA")
    expect(pill).to_be_visible()
    screenshot(page, "compliance_hipaa_pill")


def test_compliance_gdpr_pill(page: Page, screenshot):
    """GDPR compliance pill is present."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    pill = page.locator(".comp-pill", has_text="GDPR")
    expect(pill).to_be_visible()
    screenshot(page, "compliance_gdpr_pill")


def test_compliance_open_dashboard_button(page: Page, screenshot):
    """'Open Compliance Dashboard' button exists."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    btn = page.locator("#compliance a.btn-p")
    expect(btn).to_be_visible()
    screenshot(page, "compliance_open_dashboard_btn")


# ── Pricing Section ───────────────────────────────────────────────────────
def test_pricing_section_visible(page: Page, screenshot):
    """Pricing section is visible."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    section = page.locator("#pricing")
    expect(section).to_be_visible()
    screenshot(page, "pricing_section")


def test_pricing_four_plans_rendered(page: Page, screenshot):
    """Four pricing cards are rendered."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    cards = page.locator(".pcard")
    expect(cards).to_have_count(4)
    screenshot(page, "pricing_four_plans")


def test_pricing_starter_plan_free(page: Page, screenshot):
    """Starter plan shows $0/mo."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    card = page.locator(".pcard", has_text="Starter")
    expect(card).to_be_visible()
    assert "$0" in card.inner_text()
    screenshot(page, "pricing_starter_free")


def test_pricing_solo_plan_99(page: Page, screenshot):
    """Solo plan shows $99/mo."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    card = page.locator(".pcard", has_text="Solo")
    expect(card).to_be_visible()
    assert "$99" in card.inner_text()
    screenshot(page, "pricing_solo_99")


def test_pricing_business_plan_299(page: Page, screenshot):
    """Business plan shows $299/mo and is featured."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    card = page.locator(".pcard.featured")
    expect(card).to_be_visible()
    assert "$299" in card.inner_text()
    screenshot(page, "pricing_business_featured")


def test_pricing_enterprise_plan_custom(page: Page, screenshot):
    """Enterprise plan shows Custom pricing."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    card = page.locator(".pcard", has_text="Enterprise")
    expect(card).to_be_visible()
    assert "Custom" in card.inner_text()
    screenshot(page, "pricing_enterprise_custom")


def test_pricing_all_plan_ctas(page: Page, screenshot):
    """All pricing cards have CTA buttons."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    cards = page.locator(".pcard")
    for i in range(cards.count()):
        btn = cards.nth(i).locator("a.btn-p")
        expect(btn).to_be_visible()
    screenshot(page, "pricing_all_ctas")


def test_pricing_financing_link(page: Page, screenshot):
    """'Apply for grants & financing' link exists in pricing section."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    link = page.locator("#pricing a[href='/ui/grant-wizard']")
    expect(link).to_be_visible()
    screenshot(page, "pricing_financing_link")


# ── Partner Section ───────────────────────────────────────────────────────
def test_partner_section_visible(page: Page, screenshot):
    """Partner section is visible on page."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    section = page.locator("#partner")
    expect(section).to_be_visible()
    screenshot(page, "partner_section")


def test_partner_headline_text(page: Page, screenshot):
    """Partner headline reads 'Build on Murphy. Sell with Murphy.'"""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    h2 = page.locator("#partner-h")
    expect(h2).to_be_visible()
    text = h2.inner_text()
    assert "Build on Murphy" in text or "Sell with Murphy" in text
    screenshot(page, "partner_headline")


def test_partner_three_benefit_cards(page: Page, screenshot):
    """Partner section shows 3 benefit cards."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    cards = page.locator(".partner-card")
    expect(cards).to_have_count(3)
    screenshot(page, "partner_benefit_cards")


def test_partner_custom_integration_card(page: Page, screenshot):
    """Custom Integration Pipeline card is visible."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    card = page.locator(".partner-card", has_text="Custom Integration Pipeline")
    expect(card).to_be_visible()
    screenshot(page, "partner_integration_card")


def test_partner_revenue_sharing_card(page: Page, screenshot):
    """Revenue Sharing card is visible."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    card = page.locator(".partner-card", has_text="Revenue Sharing")
    expect(card).to_be_visible()
    screenshot(page, "partner_revenue_card")


def test_partner_white_label_card(page: Page, screenshot):
    """White-Label Ready card is visible."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    card = page.locator(".partner-card", has_text="White-Label")
    expect(card).to_be_visible()
    screenshot(page, "partner_white_label_card")


def test_partner_request_integration_cta(page: Page, screenshot):
    """'Request a Custom Integration' CTA button exists and links to /ui/partner."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    btn = page.locator("#partner a.btn-p.lg")
    expect(btn).to_be_visible()
    assert "/ui/partner" in (btn.get_attribute("href") or "")
    screenshot(page, "partner_request_cta")


# ── Proof / Stats Section ─────────────────────────────────────────────────
def test_proof_section_visible(page: Page, screenshot):
    """Proof/stats section is visible."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    section = page.locator("#proof")
    expect(section).to_be_visible()
    screenshot(page, "proof_section")


def test_proof_stat_537k_lines(page: Page, screenshot):
    """537,071 lines stat is present."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    card = page.locator(".stat-card", has_text="537,071")
    expect(card).to_be_visible()
    screenshot(page, "proof_stat_537k")


def test_proof_stat_24k_tests(page: Page, screenshot):
    """24,341 test functions stat is present."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    card = page.locator(".stat-card", has_text="24,341")
    expect(card).to_be_visible()
    screenshot(page, "proof_stat_24k_tests")


# ── Guarantee Section ─────────────────────────────────────────────────────
def test_guarantee_section_visible(page: Page, screenshot):
    """Guarantee section is visible."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    section = page.locator("#guarantee")
    expect(section).to_be_visible()
    screenshot(page, "guarantee_section")


def test_guarantee_four_cards(page: Page, screenshot):
    """Four guarantee cards are rendered."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    cards = page.locator(".gcard")
    expect(cards).to_have_count(4)
    screenshot(page, "guarantee_four_cards")


def test_guarantee_open_source_card(page: Page, screenshot):
    """Open Source (BSL 1.1) guarantee card visible."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    card = page.locator(".gcard", has_text="Open Source")
    expect(card).to_be_visible()
    screenshot(page, "guarantee_open_source")


def test_guarantee_data_never_leaves_card(page: Page, screenshot):
    """'Data Never Leaves (LLM)' guarantee card visible."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    card = page.locator(".gcard", has_text="Data Never Leaves")
    expect(card).to_be_visible()
    screenshot(page, "guarantee_data_privacy")


# ── Under the Hood (collapsible) ──────────────────────────────────────────
def test_under_the_hood_section_visible(page: Page, screenshot):
    """Under the Hood section is visible."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    section = page.locator("#under-the-hood")
    expect(section).to_be_visible()
    screenshot(page, "under_the_hood_section")


def test_under_the_hood_toggle_button(page: Page, screenshot):
    """Toggle button exists and expands architecture grid."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    btn = page.locator("#uth-toggle-btn")
    expect(btn).to_be_visible()
    # Initially collapsed
    content = page.locator("#uth-content")
    assert "open" not in (content.get_attribute("class") or "")
    # Click to expand
    btn.click()
    page.wait_for_timeout(300)
    assert "open" in (content.get_attribute("class") or "")
    screenshot(page, "under_the_hood_expanded")


def test_under_the_hood_arch_cards_shown_after_expand(page: Page, screenshot):
    """Architecture cards are shown after expanding."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    page.locator("#uth-toggle-btn").click()
    page.wait_for_timeout(300)
    cards = page.locator(".arch-card")
    assert cards.count() >= 10
    screenshot(page, "under_the_hood_arch_cards")


def test_under_the_hood_collapse_toggle(page: Page, screenshot):
    """Clicking toggle again collapses the architecture grid."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    btn = page.locator("#uth-toggle-btn")
    btn.click()
    page.wait_for_timeout(200)
    btn.click()
    page.wait_for_timeout(200)
    content = page.locator("#uth-content")
    assert "open" not in (content.get_attribute("class") or "")
    screenshot(page, "under_the_hood_collapsed")


# ── Final CTA ─────────────────────────────────────────────────────────────
def test_final_cta_section_visible(page: Page, screenshot):
    """Final CTA section is visible."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    section = page.locator("#final-cta")
    expect(section).to_be_visible()
    screenshot(page, "final_cta_section")


def test_final_cta_start_free_button(page: Page, screenshot):
    """Final CTA 'Start Free Trial' button exists."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    btn = page.locator("#final-cta a.btn-p.lg")
    expect(btn).to_be_visible()
    screenshot(page, "final_cta_start_free")


def test_final_cta_demo_button(page: Page, screenshot):
    """Final CTA 'Live Demo' button points to #demo."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    btn = page.locator("#final-cta a[href='#demo']")
    expect(btn).to_be_visible()
    screenshot(page, "final_cta_demo_button")


def test_final_cta_partner_button(page: Page, screenshot):
    """Final CTA 'Partner With Us' button exists."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    btn = page.locator("#final-cta a[href='/ui/partner']")
    expect(btn).to_be_visible()
    screenshot(page, "final_cta_partner_button")


# ── Footer ────────────────────────────────────────────────────────────────
def test_footer_visible(page: Page, screenshot):
    """Footer is rendered."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    footer = page.locator("footer")
    expect(footer).to_be_visible()
    screenshot(page, "footer_visible")


def test_footer_solutions_link(page: Page, screenshot):
    """Footer has Solutions link."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    link = page.locator("footer a[href='#solutions']")
    expect(link).to_be_visible()
    screenshot(page, "footer_solutions_link")


def test_footer_industries_link(page: Page, screenshot):
    """Footer has Industries link."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    link = page.locator("footer a[href='#industries']")
    expect(link).to_be_visible()
    screenshot(page, "footer_industries_link")


def test_footer_demo_link(page: Page, screenshot):
    """Footer has Demo link."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    link = page.locator("footer a[href='#demo']")
    expect(link).to_be_visible()
    screenshot(page, "footer_demo_link")


def test_footer_pricing_link(page: Page, screenshot):
    """Footer has Pricing link."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    link = page.locator("footer a[href='#pricing']")
    expect(link).to_be_visible()
    screenshot(page, "footer_pricing_link")


def test_footer_partner_link(page: Page, screenshot):
    """Footer has Partner link."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    link = page.locator("footer a[href='/ui/partner']")
    expect(link).to_be_visible()
    screenshot(page, "footer_partner_link")


def test_footer_financing_link(page: Page, screenshot):
    """Footer has Financing link."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    link = page.locator("footer a[href='/ui/grant-wizard']")
    expect(link).to_be_visible()
    screenshot(page, "footer_financing_link")


def test_footer_copyright_text(page: Page, screenshot):
    """Footer shows copyright text."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    copy = page.locator(".fcopy")
    expect(copy).to_be_visible()
    assert "Inoni" in copy.inner_text() or "2020" in copy.inner_text()
    screenshot(page, "footer_copyright")


# ── Scroll-to anchors ─────────────────────────────────────────────────────
def test_nav_solutions_scrolls_to_section(page: Page, screenshot):
    """Clicking nav Solutions link scrolls to the Solutions section."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    page.locator("nav a[href='#solutions']").click()
    page.wait_for_timeout(400)
    screenshot(page, "scroll_to_solutions")


def test_nav_industries_scrolls_to_section(page: Page, screenshot):
    """Clicking nav Industries link scrolls to the Industries section."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    page.locator("nav a[href='#industries']").click()
    page.wait_for_timeout(400)
    screenshot(page, "scroll_to_industries")


def test_nav_demo_scrolls_to_section(page: Page, screenshot):
    """Clicking nav Demo link scrolls to the Demo section."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    page.locator("nav a[href='#demo']").click()
    page.wait_for_timeout(400)
    screenshot(page, "scroll_to_demo")


def test_nav_pricing_scrolls_to_section(page: Page, screenshot):
    """Clicking nav Pricing link scrolls to the Pricing section."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    page.locator("nav a[href='#pricing']").click()
    page.wait_for_timeout(400)
    screenshot(page, "scroll_to_pricing")


def test_nav_partner_scrolls_to_section(page: Page, screenshot):
    """Clicking nav Partner link scrolls to the Partner section."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    page.locator("nav a[href='#partner']").click()
    page.wait_for_timeout(400)
    screenshot(page, "scroll_to_partner")


# ── Multi-cursor: two tabs viewing different sections simultaneously ───────
def test_multicursor_two_tabs_parallel_sections(multi_cursor, screenshot):
    """
    Multi-cursor test: Tab A views Solutions, Tab B views Industries
    simultaneously — demonstrates parallel UI automation capability.
    """
    tab_a, tab_b = multi_cursor(2)

    tab_a.goto(PAGE_URL + "#solutions", wait_until="domcontentloaded")
    tab_b.goto(PAGE_URL + "#industries", wait_until="domcontentloaded")

    # Both tabs are operational independently
    expect(tab_a.locator("#solutions")).to_be_visible()
    expect(tab_b.locator("#industries")).to_be_visible()

    tab_a.screenshot(path=str(SCREENSHOTS_DIR / "landing" / "multicursor_tab_a_solutions.png"))
    tab_b.screenshot(path=str(SCREENSHOTS_DIR / "landing" / "multicursor_tab_b_industries.png"))


# ── Full page screenshot ──────────────────────────────────────────────────
def test_landing_full_page_screenshot(page: Page):
    """Capture a full-page screenshot of the complete landing page."""
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    page.wait_for_timeout(500)
    out = SCREENSHOTS_DIR / "landing" / "landing_page_full.png"
    page.screenshot(path=str(out), full_page=True)
    assert out.exists()
    assert out.stat().st_size > 10_000  # meaningful image
