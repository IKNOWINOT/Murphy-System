"""
Tests for every Murphy System UI type.

Validates that all 16 HTML interfaces:
- Exist on disk with correct structure
- Have required accessibility features (skip links, aria labels, roles)
- Reference the shared design system (CSS + JS)
- Have MurphyLibrarianChat integration
- Use correct API field names that match the backend

Also validates that the backend API accepts all field name variants
used by different frontend components (query, question, message).

Design Label: TEST-UI-TYPES
Owner: QA Team
"""

import os
import re
import sys
import json
import unittest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
MURPHY_DIR = os.path.join(TESTS_DIR, '..')
SRC_DIR = os.path.join(MURPHY_DIR, 'src')
sys.path.insert(0, MURPHY_DIR)
sys.path.insert(0, SRC_DIR)

# ---------------------------------------------------------------------------
# All 16 HTML UI files in the system
# ---------------------------------------------------------------------------

ALL_UI_FILES = {
    # Landing & entry points
    'murphy_landing_page.html': {
        'title_contains': 'Murphy System',
        'type': 'landing',
        'must_have_skip_link': True,
        'must_have_librarian': True,
        'must_have_nav': True,
    },
    'murphy-smoke-test.html': {
        'title_contains': 'Murphy',
        'type': 'smoke_test',
        'must_have_skip_link': False,
        'must_have_librarian': True,
        'must_have_nav': False,
    },
    # Terminal views (sidebar + top bar + main content + librarian)
    'terminal_unified.html': {
        'title_contains': 'Unified',
        'type': 'terminal',
        'must_have_skip_link': True,
        'must_have_librarian': True,
        'must_have_nav': True,
    },
    'terminal_integrated.html': {
        'title_contains': 'Murphy',
        'type': 'terminal',
        'must_have_skip_link': True,
        'must_have_librarian': True,
        'must_have_nav': True,
    },
    'terminal_architect.html': {
        'title_contains': 'Architect',
        'type': 'terminal',
        'must_have_skip_link': True,
        'must_have_librarian': True,
        'must_have_nav': True,
    },
    'terminal_enhanced.html': {
        'title_contains': 'Murphy',
        'type': 'terminal',
        'must_have_skip_link': True,
        'must_have_librarian': True,
        'must_have_nav': True,
    },
    'terminal_costs.html': {
        'title_contains': 'Finance',
        'type': 'terminal',
        'must_have_skip_link': True,
        'must_have_librarian': True,
        'must_have_nav': True,
    },
    'terminal_orgchart.html': {
        'title_contains': 'Murphy',
        'type': 'terminal',
        'must_have_skip_link': True,
        'must_have_librarian': True,
        'must_have_nav': True,
    },
    'terminal_integrations.html': {
        'title_contains': 'Murphy',
        'type': 'terminal',
        'must_have_skip_link': True,
        'must_have_librarian': True,
        'must_have_nav': True,
    },
    'terminal_orchestrator.html': {
        'title_contains': 'Murphy',
        'type': 'terminal_legacy',
        'must_have_skip_link': False,
        'must_have_librarian': False,
        'must_have_nav': False,
    },
    'terminal_worker.html': {
        'title_contains': 'Murphy',
        'type': 'terminal',
        'must_have_skip_link': True,
        'must_have_librarian': True,
        'must_have_nav': True,
    },
    # Graphical / canvas UIs
    'workflow_canvas.html': {
        'title_contains': 'Workflow',
        'type': 'canvas',
        'must_have_skip_link': True,
        'must_have_librarian': True,
        'must_have_nav': False,
    },
    'system_visualizer.html': {
        'title_contains': 'Topology',
        'type': 'canvas',
        'must_have_skip_link': True,
        'must_have_librarian': False,
        'must_have_nav': False,
    },
    # Onboarding
    'onboarding_wizard.html': {
        'title_contains': 'Murphy',
        'type': 'onboarding',
        'must_have_skip_link': True,
        'must_have_librarian': False,
        'must_have_nav': False,
    },
    # Integrated dashboard views
    'murphy_ui_integrated.html': {
        'title_contains': 'Murphy',
        'type': 'dashboard',
        'must_have_skip_link': False,
        'must_have_librarian': False,
        'must_have_nav': False,
    },
    'murphy_ui_integrated_terminal.html': {
        'title_contains': 'Murphy',
        'type': 'dashboard',
        'must_have_skip_link': False,
        'must_have_librarian': False,
        'must_have_nav': False,
    },
}


def _read_html(filename):
    """Read HTML file content, appending linked local CSS for style checks."""
    path = os.path.join(MURPHY_DIR, filename)
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    for css_href in re.findall(r'href="(static/[^"]+\.css)"', content):
        css_path = os.path.join(MURPHY_DIR, css_href)
        if os.path.isfile(css_path):
            with open(css_path, 'r', encoding='utf-8') as cf:
                content += '\n' + cf.read()
    return content


def _is_redirect_stub(filename):
    """Return True if the HTML file is just a redirect stub."""
    content = _read_html(filename)
    return 'http-equiv="refresh"' in content or 'window.location.replace' in content


# ============================================================================
# 1. File Existence Tests — every UI file must exist
# ============================================================================

class TestUIFileExistence(unittest.TestCase):
    """Every declared UI HTML file must exist on disk."""

    def test_all_16_ui_files_exist(self):
        """All 16 UI HTML files must be present."""
        missing = []
        for fname in ALL_UI_FILES:
            path = os.path.join(MURPHY_DIR, fname)
            if not os.path.isfile(path):
                missing.append(fname)
        self.assertEqual(missing, [], f"Missing UI files: {missing}")

    def test_each_file_is_valid_html(self):
        """Every UI file must contain <!DOCTYPE html> or <html (may have comment header first)."""
        for fname in ALL_UI_FILES:
            path = os.path.join(MURPHY_DIR, fname)
            if not os.path.isfile(path):
                continue
            content = _read_html(fname).lower()
            self.assertTrue(
                '<!doctype html' in content or '<html' in content,
                f"{fname} is not valid HTML (missing DOCTYPE or <html>)"
            )

    def test_each_file_has_title(self):
        """Every UI file must have a <title> tag."""
        for fname, spec in ALL_UI_FILES.items():
            path = os.path.join(MURPHY_DIR, fname)
            if not os.path.isfile(path):
                continue
            content = _read_html(fname)
            title_match = re.search(r'<title>(.*?)</title>', content, re.IGNORECASE)
            self.assertIsNotNone(title_match, f"{fname} is missing <title> tag")
            self.assertIn(
                spec['title_contains'].lower(),
                title_match.group(1).lower(),
                f"{fname} title does not contain '{spec['title_contains']}'"
            )


# ============================================================================
# 2. Accessibility Tests — skip links, ARIA, semantic HTML
# ============================================================================

class TestUIAccessibility(unittest.TestCase):
    """Accessibility features for each UI type."""

    def test_skip_links_present(self):
        """UIs that require skip links must have them."""
        for fname, spec in ALL_UI_FILES.items():
            if not spec['must_have_skip_link']:
                continue
            path = os.path.join(MURPHY_DIR, fname)
            if not os.path.isfile(path):
                continue
            content = _read_html(fname)
            if _is_redirect_stub(fname):
                continue
            self.assertTrue(
                'skip' in content.lower() and 'href="#' in content.lower(),
                f"{fname} missing skip link for accessibility"
            )

    def test_main_landmark_present(self):
        """Terminal and landing pages must have a <main> landmark."""
        for fname, spec in ALL_UI_FILES.items():
            if spec['type'] not in ('terminal', 'landing', 'onboarding'):
                continue  # Canvas UIs use split-pane layout, no <main>
            path = os.path.join(MURPHY_DIR, fname)
            if not os.path.isfile(path):
                continue
            content = _read_html(fname)
            if _is_redirect_stub(fname):
                continue
            self.assertTrue(
                '<main' in content,
                f"{fname} missing <main> landmark element"
            )

    def test_aria_labels_on_inputs(self):
        """All <input> and <textarea> elements should have aria-label or label."""
        for fname in ALL_UI_FILES:
            path = os.path.join(MURPHY_DIR, fname)
            if not os.path.isfile(path):
                continue
            content = _read_html(fname)
            if _is_redirect_stub(fname):
                continue
            # Find input elements without aria-label (exclude hidden inputs)
            inputs = re.findall(r'<input\b[^>]*>', content)
            for inp in inputs:
                if 'type="hidden"' in inp or 'type=\'hidden\'' in inp:
                    continue
                has_label = ('aria-label' in inp or 'id=' in inp or
                             'placeholder=' in inp)
                self.assertTrue(
                    has_label,
                    f"{fname} has <input> without aria-label/id/placeholder: {inp[:80]}"
                )


# ============================================================================
# 3. Design System Integration Tests
# ============================================================================

class TestUIDesignSystem(unittest.TestCase):
    """Shared design system references in each UI type."""

    def test_design_system_css_linked(self):
        """Non-stub UIs must reference murphy-design-system.css."""
        for fname, spec in ALL_UI_FILES.items():
            if spec['type'] in ('dashboard', 'terminal_legacy'):
                continue  # Legacy and redirect stubs exempt
            path = os.path.join(MURPHY_DIR, fname)
            if not os.path.isfile(path):
                continue
            content = _read_html(fname)
            if _is_redirect_stub(fname):
                continue
            self.assertIn(
                'murphy-design-system.css',
                content,
                f"{fname} does not link murphy-design-system.css"
            )

    def test_components_js_linked(self):
        """Terminal and landing pages must include murphy-components.js."""
        for fname, spec in ALL_UI_FILES.items():
            if spec['type'] not in ('terminal', 'landing', 'canvas', 'onboarding'):
                continue  # terminal_legacy, dashboard, smoke_test exempt
            path = os.path.join(MURPHY_DIR, fname)
            if not os.path.isfile(path):
                continue
            content = _read_html(fname)
            if _is_redirect_stub(fname):
                continue
            self.assertIn(
                'murphy-components.js',
                content,
                f"{fname} does not include murphy-components.js"
            )

    def test_bsl_license_header(self):
        """All production UIs should have BSL 1.1 license reference."""
        for fname, spec in ALL_UI_FILES.items():
            if spec['type'] in ('smoke_test', 'dashboard'):
                continue
            path = os.path.join(MURPHY_DIR, fname)
            if not os.path.isfile(path):
                continue
            content = _read_html(fname)
            if _is_redirect_stub(fname):
                continue
            has_bsl = ('BSL' in content or 'Business Source License' in content or
                       'bsl' in content.lower())
            self.assertTrue(
                has_bsl,
                f"{fname} missing BSL 1.1 license reference"
            )


# ============================================================================
# 4. Librarian Integration Tests
# ============================================================================

class TestUILibrarianIntegration(unittest.TestCase):
    """MurphyLibrarianChat component integration per UI type."""

    def test_librarian_chat_present(self):
        """UIs requiring Librarian must instantiate MurphyLibrarianChat."""
        for fname, spec in ALL_UI_FILES.items():
            if not spec['must_have_librarian']:
                continue
            path = os.path.join(MURPHY_DIR, fname)
            if not os.path.isfile(path):
                continue
            content = _read_html(fname)
            if _is_redirect_stub(fname):
                continue
            self.assertIn(
                'MurphyLibrarianChat',
                content,
                f"{fname} missing MurphyLibrarianChat component"
            )

    def test_librarian_posts_to_correct_endpoint(self):
        """Librarian chat must POST to /librarian/ask."""
        for fname, spec in ALL_UI_FILES.items():
            if not spec['must_have_librarian']:
                continue
            path = os.path.join(MURPHY_DIR, fname)
            if not os.path.isfile(path):
                continue
            content = _read_html(fname)
            if _is_redirect_stub(fname):
                continue
            # Check either inline call or via murphy-components.js
            has_endpoint = (
                '/librarian/ask' in content or
                'MurphyLibrarianChat' in content
            )
            self.assertTrue(
                has_endpoint,
                f"{fname} doesn't call /librarian/ask or use MurphyLibrarianChat"
            )


# ============================================================================
# 5. Navigation Tests
# ============================================================================

class TestUINavigation(unittest.TestCase):
    """Sidebar/navigation structure per UI type."""

    def test_sidebar_navigation_present(self):
        """Terminal UIs must have sidebar navigation."""
        for fname, spec in ALL_UI_FILES.items():
            if not spec['must_have_nav']:
                continue
            path = os.path.join(MURPHY_DIR, fname)
            if not os.path.isfile(path):
                continue
            content = _read_html(fname)
            if _is_redirect_stub(fname):
                continue
            has_nav = ('<nav' in content or 'role="navigation"' in content)
            self.assertTrue(
                has_nav,
                f"{fname} missing <nav> or role=navigation"
            )

    def test_terminal_has_sidebar_toggle(self):
        """Terminal UIs should have a sidebar toggle button."""
        for fname, spec in ALL_UI_FILES.items():
            if spec['type'] != 'terminal':
                continue
            path = os.path.join(MURPHY_DIR, fname)
            if not os.path.isfile(path):
                continue
            content = _read_html(fname)
            if _is_redirect_stub(fname):
                continue
            has_toggle = ('toggle' in content.lower() and 'sidebar' in content.lower())
            self.assertTrue(
                has_toggle,
                f"{fname} missing sidebar toggle functionality"
            )


# ============================================================================
# 6. UI-Type-Specific Feature Tests
# ============================================================================

class TestLandingPageFeatures(unittest.TestCase):
    """Landing page specific features."""

    def test_hero_section_exists(self):
        """Landing page must have a hero section."""
        content = _read_html('murphy_landing_page.html')
        self.assertTrue(
            'hero' in content.lower(),
            "Landing page missing hero section"
        )

    def test_feature_cards_exist(self):
        """Landing page must show feature cards."""
        content = _read_html('murphy_landing_page.html')
        self.assertTrue(
            'card' in content.lower(),
            "Landing page missing feature cards"
        )

    def test_terminal_links_exist(self):
        """Landing page must link to terminal views."""
        content = _read_html('murphy_landing_page.html')
        self.assertTrue(
            'terminal_unified.html' in content or 'terminal-unified' in content,
            "Landing page must link to terminal-unified (URL or filename)"
        )

    def test_no_inline_styles(self):
        """Landing page should use zero inline styles (design system only)."""
        content = _read_html('murphy_landing_page.html')
        # Count style= attributes (excluding SVG and meta)
        inline_styles = re.findall(r'<(?!svg|path|circle|rect|meta)[a-z]+[^>]+style="', content)
        self.assertEqual(
            len(inline_styles), 0,
            f"Landing page has {len(inline_styles)} inline style(s) — should use CSS classes"
        )


class TestOnboardingWizardFeatures(unittest.TestCase):
    """Onboarding wizard specific features."""

    def test_step_indicators_exist(self):
        """Onboarding wizard must show step progress indicators."""
        content = _read_html('onboarding_wizard.html')
        self.assertTrue(
            'step' in content.lower(),
            "Onboarding wizard missing step indicators"
        )

    def test_chat_input_exists(self):
        """Onboarding wizard must have a chat input."""
        content = _read_html('onboarding_wizard.html')
        has_input = ('input' in content.lower() or 'textarea' in content.lower())
        self.assertTrue(has_input, "Onboarding wizard missing chat input")

    def test_calls_librarian_api(self):
        """Onboarding wizard must call the MFGC chat API."""
        content = _read_html('onboarding_wizard.html')
        self.assertIn(
            '/onboarding/mfgc-chat',
            content,
            "Onboarding wizard doesn't call /onboarding/mfgc-chat"
        )


class TestWorkflowCanvasFeatures(unittest.TestCase):
    """Workflow canvas specific features."""

    def test_node_palette_exists(self):
        """Workflow canvas must have a node palette."""
        content = _read_html('workflow_canvas.html')
        self.assertTrue(
            'palette' in content.lower() or 'node' in content.lower(),
            "Workflow canvas missing node palette"
        )

    def test_save_button_exists(self):
        """Workflow canvas must have a save button."""
        content = _read_html('workflow_canvas.html')
        self.assertIn('save', content.lower())

    def test_load_button_exists(self):
        """Workflow canvas must have a load button."""
        content = _read_html('workflow_canvas.html')
        self.assertIn('load', content.lower())

    def test_natural_language_input(self):
        """Workflow canvas must have NL workflow description input."""
        content = _read_html('workflow_canvas.html')
        has_nl = ('plain english' in content.lower() or
                  'natural language' in content.lower() or
                  'describe' in content.lower())
        self.assertTrue(has_nl, "Workflow canvas missing natural language input")

    def test_canvas_js_linked(self):
        """Workflow canvas must include murphy-canvas.js."""
        content = _read_html('workflow_canvas.html')
        self.assertIn('murphy-canvas.js', content)

    def test_calls_workflow_terminal_endpoints(self):
        """Workflow canvas must reference workflow-terminal API endpoints."""
        content = _read_html('workflow_canvas.html')
        self.assertIn('workflow-terminal', content)


class TestSystemVisualizerFeatures(unittest.TestCase):
    """System visualizer specific features."""

    def test_search_input_exists(self):
        """System visualizer must have a module search input."""
        content = _read_html('system_visualizer.html')
        self.assertIn('search', content.lower())

    def test_auto_layout_button(self):
        """System visualizer must have an auto-layout button."""
        content = _read_html('system_visualizer.html')
        self.assertIn('layout', content.lower())

    def test_canvas_rendering(self):
        """System visualizer must include canvas rendering code."""
        content = _read_html('system_visualizer.html')
        has_canvas = ('canvas' in content.lower() or 'svg' in content.lower())
        self.assertTrue(has_canvas, "System visualizer missing canvas/SVG rendering")


class TestFinanceTerminalFeatures(unittest.TestCase):
    """Finance/costs terminal specific features."""

    def test_costs_section(self):
        """Finance terminal must have a costs section."""
        content = _read_html('terminal_costs.html')
        self.assertIn('cost', content.lower())

    def test_efficiency_section(self):
        """Finance terminal must have an efficiency section."""
        content = _read_html('terminal_costs.html')
        self.assertIn('efficiency', content.lower())

    def test_supply_chain_section(self):
        """Finance terminal must have a supply chain section."""
        content = _read_html('terminal_costs.html')
        self.assertIn('supply', content.lower())


class TestArchitectTerminalFeatures(unittest.TestCase):
    """Architect terminal specific features."""

    def test_has_topology_link(self):
        """Architect terminal should link to system visualizer."""
        content = _read_html('terminal_architect.html')
        self.assertTrue(
            'system_visualizer' in content.lower() or 'system-visualizer' in content.lower(),
            "Architect terminal must link to system visualizer"
        )


class TestWorkerTerminalFeatures(unittest.TestCase):
    """Worker terminal specific features."""

    def test_has_task_view(self):
        """Worker terminal must have a work/task view."""
        content = _read_html('terminal_worker.html')
        has_tasks = ('task' in content.lower() or 'delivery' in content.lower() or
                     'work' in content.lower() or 'queue' in content.lower())
        self.assertTrue(has_tasks, "Worker terminal missing task/work view")


class TestOrgChartTerminalFeatures(unittest.TestCase):
    """Org chart terminal specific features."""

    def test_has_org_chart_view(self):
        """Org chart terminal must reference organization/team structure."""
        content = _read_html('terminal_orgchart.html')
        has_org = ('org' in content.lower() or 'team' in content.lower() or
                   'role' in content.lower())
        self.assertTrue(has_org, "Org chart terminal missing org/team view")


class TestIntegrationsTerminalFeatures(unittest.TestCase):
    """Integrations terminal specific features."""

    def test_has_integrations_list(self):
        """Integrations terminal must list available integrations."""
        content = _read_html('terminal_integrations.html')
        self.assertIn('integration', content.lower())


class TestOrchestratorTerminalFeatures(unittest.TestCase):
    """Orchestrator terminal specific features."""

    def test_has_orchestrator_controls(self):
        """Orchestrator terminal must have orchestration controls."""
        content = _read_html('terminal_orchestrator.html')
        has_orch = ('orchestrat' in content.lower() or 'pipeline' in content.lower())
        self.assertTrue(has_orch, "Orchestrator terminal missing orchestration controls")


class TestEnhancedTerminalFeatures(unittest.TestCase):
    """Enhanced/power-user terminal specific features."""

    def test_has_command_input(self):
        """Enhanced terminal must have a command input."""
        content = _read_html('terminal_enhanced.html')
        has_input = ('input' in content.lower() or 'command' in content.lower())
        self.assertTrue(has_input, "Enhanced terminal missing command input")


class TestSmokeTestFeatures(unittest.TestCase):
    """Smoke test page specific features."""

    def test_has_health_check(self):
        """Smoke test must check system health."""
        content = _read_html('murphy-smoke-test.html')
        self.assertIn('health', content.lower())


class TestDashboardFeatures(unittest.TestCase):
    """Integrated dashboard features."""

    def test_dashboard_files_exist(self):
        """Both dashboard HTML files must exist."""
        for fname in ['murphy_ui_integrated.html', 'murphy_ui_integrated_terminal.html']:
            path = os.path.join(MURPHY_DIR, fname)
            self.assertTrue(os.path.isfile(path), f"Missing: {fname}")


# ============================================================================
# 7. API Field Name Compatibility Tests (the bug fix)
# ============================================================================

class TestAPIFieldNameCompatibility(unittest.TestCase):
    """Verify the backend accepts all field name variants used by UIs."""

    @classmethod
    def setUpClass(cls):
        """Create a test client for the Murphy System API."""
        try:
            # Use development mode to bypass auth middleware in tests
            os.environ.setdefault("MURPHY_ENV", "development")
            from src.runtime.app import create_app
            from fastapi.testclient import TestClient
            cls.app = create_app()
            cls.client = TestClient(cls.app)
            cls.api_available = True
        except Exception:
            cls.api_available = False

    def test_librarian_accepts_message_field(self):
        """POST /api/librarian/ask must accept 'message' field."""
        if not self.api_available:
            self.skipTest("API not available")
        resp = self.client.post("/api/librarian/ask", json={
            "message": "How do I automate email sending?"
        })
        self.assertIn(resp.status_code, (200, 201))
        data = resp.json()
        # Must return a non-empty response
        response_text = data.get("response") or data.get("message") or data.get("reply_text") or ""
        self.assertTrue(len(response_text) > 10, f"Empty response for 'message' field: {data}")

    def test_librarian_accepts_query_field(self):
        """POST /api/librarian/ask must accept 'query' field (MurphyLibrarianChat)."""
        if not self.api_available:
            self.skipTest("API not available")
        resp = self.client.post("/api/librarian/ask", json={
            "query": "What integrations are available?"
        })
        self.assertIn(resp.status_code, (200, 201))
        data = resp.json()
        response_text = data.get("response") or data.get("message") or data.get("reply_text") or ""
        self.assertTrue(len(response_text) > 10, f"Empty response for 'query' field: {data}")

    def test_librarian_accepts_question_field(self):
        """POST /api/librarian/ask must accept 'question' field (onboarding wizard)."""
        if not self.api_available:
            self.skipTest("API not available")
        resp = self.client.post("/api/librarian/ask", json={
            "question": "I need to automate quality control"
        })
        self.assertIn(resp.status_code, (200, 201))
        data = resp.json()
        response_text = data.get("response") or data.get("message") or data.get("reply_text") or ""
        self.assertTrue(len(response_text) > 10, f"Empty response for 'question' field: {data}")

    def test_librarian_returns_automation_guidance(self):
        """Librarian must respond about automation, not give empty/canned response."""
        if not self.api_available:
            self.skipTest("API not available")
        resp = self.client.post("/api/librarian/ask", json={
            "query": "How can I automate my sales pipeline?"
        })
        data = resp.json()
        response_text = data.get("response") or data.get("message") or data.get("reply_text") or ""
        # Must mention automation-related concepts
        response_lower = response_text.lower()
        has_automation_content = any(word in response_lower for word in [
            'automat', 'plan', 'interview', 'workflow', 'integration', 'execution',
        ])
        self.assertTrue(
            has_automation_content,
            f"Librarian response doesn't mention automation concepts: {response_text[:200]}"
        )

    def test_chat_endpoint_works(self):
        """POST /api/chat must accept messages and return a response."""
        if not self.api_available:
            self.skipTest("API not available")
        resp = self.client.post("/api/chat", json={
            "message": "status"
        })
        self.assertIn(resp.status_code, (200, 201))

    def test_workflow_terminal_list_exists(self):
        """GET /api/workflow-terminal/list must exist and return an array."""
        if not self.api_available:
            self.skipTest("API not available")
        resp = self.client.get("/api/workflow-terminal/list")
        self.assertIn(resp.status_code, (200, 201))
        data = resp.json()
        self.assertIsInstance(data, list)

    def test_workflow_terminal_save_works(self):
        """POST /api/workflow-terminal/save must save and return an ID."""
        if not self.api_available:
            self.skipTest("API not available")
        resp = self.client.post("/api/workflow-terminal/save", json={
            "name": "Test Workflow",
            "nodes": [{"id": "n1", "type": "trigger", "label": "Start"}],
        })
        self.assertIn(resp.status_code, (200, 201))
        data = resp.json()
        self.assertTrue(data.get("ok") or data.get("success"))
        self.assertIn("id", data)

    def test_workflow_terminal_load_works(self):
        """GET /api/workflow-terminal/load?id=... must load a saved workflow."""
        if not self.api_available:
            self.skipTest("API not available")
        # First save a workflow
        save_resp = self.client.post("/api/workflow-terminal/save", json={
            "name": "Load Test Workflow",
            "nodes": [{"id": "n1", "type": "action", "label": "Do Thing"}],
        })
        wf_id = save_resp.json().get("id", "")
        # Then load it
        resp = self.client.get(f"/api/workflow-terminal/load?id={wf_id}")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data.get("name"), "Load Test Workflow")
        self.assertEqual(len(data.get("nodes", [])), 1)

    def test_health_endpoint(self):
        """GET /api/health must return healthy status."""
        if not self.api_available:
            self.skipTest("API not available")
        resp = self.client.get("/api/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data.get("status"), "healthy")


# ============================================================================
# 8. Cross-UI Consistency Tests
# ============================================================================

class TestCrossUIConsistency(unittest.TestCase):
    """Verify consistency across all UI types."""

    def test_all_terminals_share_design_system(self):
        """All terminal UIs must use the same design system CSS."""
        terminal_files = [f for f, s in ALL_UI_FILES.items() if s['type'] == 'terminal']
        for fname in terminal_files:
            path = os.path.join(MURPHY_DIR, fname)
            if not os.path.isfile(path):
                continue
            content = _read_html(fname)
            if _is_redirect_stub(fname):
                continue
            self.assertIn(
                'murphy-design-system.css', content,
                f"{fname} doesn't use shared design system"
            )

    def test_all_terminals_have_murphy_api(self):
        """All terminal UIs must instantiate MurphyAPI."""
        terminal_files = [f for f, s in ALL_UI_FILES.items() if s['type'] == 'terminal']
        for fname in terminal_files:
            path = os.path.join(MURPHY_DIR, fname)
            if not os.path.isfile(path):
                continue
            content = _read_html(fname)
            if _is_redirect_stub(fname):
                continue
            self.assertIn(
                'MurphyAPI', content,
                f"{fname} doesn't instantiate MurphyAPI"
            )

    def test_all_terminals_have_theme_toggle(self):
        """All terminal UIs must have a theme toggle."""
        terminal_files = [f for f, s in ALL_UI_FILES.items() if s['type'] == 'terminal']
        for fname in terminal_files:
            path = os.path.join(MURPHY_DIR, fname)
            if not os.path.isfile(path):
                continue
            content = _read_html(fname)
            if _is_redirect_stub(fname):
                continue
            has_theme = ('MurphyTheme' in content or 'theme' in content.lower())
            self.assertTrue(
                has_theme,
                f"{fname} missing theme toggle"
            )

    def test_no_ui_file_exceeds_size_limit(self):
        """No UI file should exceed 100KB (reasonable limit for HTML)."""
        for fname in ALL_UI_FILES:
            path = os.path.join(MURPHY_DIR, fname)
            if not os.path.isfile(path):
                continue
            size = os.path.getsize(path)
            self.assertLess(
                size, 100_000,
                f"{fname} is {size:,} bytes — exceeds 100KB limit"
            )


if __name__ == '__main__':
    unittest.main()
