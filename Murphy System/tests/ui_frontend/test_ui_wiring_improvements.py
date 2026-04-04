"""
UI Wiring Improvements — Tests
===============================

Validates that backend APIs are properly wired to frontend UI pages.
Covers five improvements:
1. MurphyHeader notification badge
2. MurphySidebar + CommandPalette expanded navigation
3. Trading dashboard risk/emergency-stop API wiring
4. Ambient intelligence stats API wiring
5. Compliance dashboard dynamic country/industry detection
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent


# ---------------------------------------------------------------------------
# 1. MurphyHeader — notification badge wired to /api/collaboration/notifications
# ---------------------------------------------------------------------------

class TestMurphyHeaderNotifications:
    """MurphyHeader should poll for notification count and display a badge."""

    @pytest.fixture(autouse=True)
    def _load(self):
        self.js = (ROOT / "static" / "murphy-components.js").read_text()

    def test_notification_bell_rendered(self):
        assert "murphy-notif-bell" in self.js, (
            "MurphyHeader should render a notification bell element"
        )

    def test_notification_badge_element(self):
        assert "murphy-notif-badge" in self.js, (
            "MurphyHeader should render a notification badge counter"
        )

    def test_polls_notification_count_api(self):
        assert "/collaboration/notifications/" in self.js, (
            "MurphyHeader should poll /api/collaboration/notifications/{userId}/count"
        )
        assert "/count" in self.js, (
            "MurphyHeader should call the /count endpoint"
        )

    def test_poll_notifications_method_exists(self):
        assert "_pollNotifications" in self.js, (
            "MurphyHeader should define a _pollNotifications method"
        )


# ---------------------------------------------------------------------------
# 2. MurphySidebar — expanded navigation links
# ---------------------------------------------------------------------------

class TestSidebarNavigation:
    """Sidebar should link to all major dashboards, not just 8 hardcoded ones."""

    @pytest.fixture(autouse=True)
    def _load(self):
        self.js = (ROOT / "static" / "murphy-components.js").read_text()

    EXPECTED_SIDEBAR_HREFS = [
        "/ui/onboarding",
        "/ui/system-visualizer",
        "/ui/terminal-orchestrator",
        "/ui/trading",
        "/ui/risk-dashboard",
        "/ui/paper-trading",
        "/ui/grant-wizard",
        "/ui/grant-dashboard",
        "/ui/financing",
        "/ui/wallet",
        "/ui/compliance",
        "/ui/calendar",
        "/ui/meeting-intelligence",
        "/ui/ambient",
        "/ui/workspace",
        "/ui/community",
        "/ui/management",
        "/ui/org-portal",
        "/ui/docs",
        "/ui/admin",
    ]

    @pytest.mark.parametrize("href", EXPECTED_SIDEBAR_HREFS)
    def test_sidebar_has_link(self, href):
        assert href in self.js, (
            f"MurphySidebar should include a navigation link to {href}"
        )


class TestCommandPaletteNavigation:
    """Command palette (Ctrl+K) should list all dashboards."""

    @pytest.fixture(autouse=True)
    def _load(self):
        self.js = (ROOT / "static" / "murphy-components.js").read_text()

    EXPECTED_PALETTE_HREFS = [
        "/ui/onboarding",
        "/ui/system-visualizer",
        "/ui/trading",
        "/ui/risk-dashboard",
        "/ui/paper-trading",
        "/ui/grant-wizard",
        "/ui/grant-dashboard",
        "/ui/financing",
        "/ui/wallet",
        "/ui/compliance",
        "/ui/calendar",
        "/ui/meeting-intelligence",
        "/ui/ambient",
        "/ui/workspace",
        "/ui/community",
        "/ui/management",
        "/ui/org-portal",
        "/ui/docs",
        "/ui/admin",
    ]

    @pytest.mark.parametrize("href", EXPECTED_PALETTE_HREFS)
    def test_palette_has_command(self, href):
        assert href in self.js, (
            f"Command palette should include a command for {href}"
        )


# ---------------------------------------------------------------------------
# 3. Trading dashboard — risk panel + emergency stop wired to backend
# ---------------------------------------------------------------------------

class TestTradingDashboardRiskWiring:
    """Trading dashboard should call risk, emergency, and graduation APIs."""

    @pytest.fixture(autouse=True)
    def _load(self):
        self.html = (ROOT / "trading_dashboard.html").read_text()

    def test_calls_risk_assessment_api(self):
        assert "/api/trading/risk/assessment" in self.html, (
            "Trading dashboard should fetch risk assessment data"
        )

    def test_calls_emergency_status_api(self):
        assert "/api/trading/emergency/status" in self.html, (
            "Trading dashboard should check emergency stop status from backend"
        )

    def test_calls_graduation_status_api(self):
        assert "/api/trading/graduation/status" in self.html, (
            "Trading dashboard should fetch graduation progress from backend"
        )

    def test_emergency_stop_calls_backend(self):
        assert "/api/trading/emergency/trigger" in self.html, (
            "Emergency stop button should call backend API, not just set UI state"
        )

    def test_load_risk_data_function(self):
        assert "loadRiskData" in self.html, (
            "Trading dashboard should define a loadRiskData function"
        )

    def test_risk_data_in_refresh_all(self):
        assert "loadRiskData()" in self.html, (
            "refreshAll should include loadRiskData in its polling cycle"
        )


# ---------------------------------------------------------------------------
# 4. Ambient intelligence — stats bar wired to /api/ambient/stats
# ---------------------------------------------------------------------------

class TestAmbientIntelligenceStats:
    """Ambient intelligence page should fetch stats from the backend API."""

    @pytest.fixture(autouse=True)
    def _load(self):
        self.html = (ROOT / "ambient_intelligence.html").read_text()

    def test_calls_ambient_stats_api(self):
        assert "/api/ambient/stats" in self.html, (
            "Ambient intelligence page should fetch data from /api/ambient/stats"
        )

    def test_updates_stat_insights(self):
        assert "stat-insights" in self.html, (
            "Page should have a stat-insights element populated from API"
        )

    def test_updates_stat_delivered(self):
        assert "stat-delivered" in self.html, (
            "Page should have a stat-delivered element populated from API"
        )

    def test_load_ambient_stats_function(self):
        assert "loadAmbientStats" in self.html, (
            "Page should define a loadAmbientStats function"
        )

    def test_stats_polling_interval(self):
        assert "setInterval(loadAmbientStats" in self.html, (
            "Ambient stats should be polled on an interval"
        )


# ---------------------------------------------------------------------------
# 5. Compliance dashboard — dynamic country/industry for detection
# ---------------------------------------------------------------------------

class TestComplianceDashboardDetection:
    """Compliance dashboard should use user-selected country/industry, not hardcoded."""

    @pytest.fixture(autouse=True)
    def _load(self):
        self.html = (ROOT / "compliance_dashboard.html").read_text()

    def test_no_hardcoded_country(self):
        assert "country=XX" not in self.html, (
            "Compliance dashboard should not use hardcoded country=XX placeholder"
        )

    def test_no_hardcoded_industry(self):
        assert "industry=YY" not in self.html, (
            "Compliance dashboard should not use hardcoded industry=YY placeholder"
        )

    def test_country_selector_exists(self):
        assert 'id="detect-country"' in self.html, (
            "Compliance dashboard should have a country selector element"
        )

    def test_industry_selector_exists(self):
        assert 'id="detect-industry"' in self.html, (
            "Compliance dashboard should have an industry selector element"
        )

    def test_uses_dynamic_country(self):
        assert "detect-country" in self.html, (
            "JS should read country from the detect-country element"
        )

    def test_uses_dynamic_industry(self):
        assert "detect-industry" in self.html, (
            "JS should read industry from the detect-industry element"
        )

    def test_validation_before_fetch(self):
        assert "!country || !industry" in self.html or "!country||!industry" in self.html, (
            "Should validate that both country and industry are selected before fetching"
        )


# ---------------------------------------------------------------------------
# 6. Mirror check — Murphy System/ subdirectory should be in sync
# ---------------------------------------------------------------------------

class TestMirrorSync:
    """Murphy System/ subdirectory copies should match root files."""

    FILES = [
        "static/murphy-components.js",
        "trading_dashboard.html",
        "ambient_intelligence.html",
        "compliance_dashboard.html",
    ]

    @pytest.mark.parametrize("relpath", FILES)
    def test_mirror_matches_root(self, relpath):
        root_file = ROOT / relpath
        mirror_file = ROOT / "Murphy System" / relpath
        if not mirror_file.exists():
            pytest.skip(f"Mirror file {relpath} does not exist")
        assert root_file.read_text() == mirror_file.read_text(), (
            f"Murphy System/{relpath} should be in sync with root {relpath}"
        )
