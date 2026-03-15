"""
Tests for No-Code Natural Language Terminal Routing.

Validates that the terminal_integrated.html processCommand function
correctly routes unrecognized plain-English input to the natural
language handler instead of showing "Unknown command" errors.

Design Label: TEST-NLC-001
Owner: QA Team
"""

import os
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TERMINAL_PATH = os.path.join(
    os.path.dirname(__file__), '..', 'terminal_integrated.html'
)


def _read_terminal_html() -> str:
    """Read the terminal HTML source."""
    with open(TERMINAL_PATH, 'r', encoding='utf-8') as f:
        return f.read()


# ---------------------------------------------------------------------------
# Tests — Natural Language Routing
# ---------------------------------------------------------------------------

class TestNaturalLanguageRouting:
    """Verify the terminal routes unrecognized input to NL handler."""

    def test_default_case_routes_to_natural_language(self):
        """The switch default case calls handleNaturalLanguage, not error."""
        html = _read_terminal_html()
        # Find the default case in the processCommand switch
        assert 'default:' in html, "default case not found"
        # Extract a generous window around the default case
        idx = html.index('default:')
        window = html[idx:idx + 500]
        assert 'handleNaturalLanguage' in window, \
            "default case should route to handleNaturalLanguage"
        assert 'Unknown command' not in window, \
            "default case should NOT show 'Unknown command' error"

    def test_handle_natural_language_function_exists(self):
        """handleNaturalLanguage function is defined."""
        html = _read_terminal_html()
        assert 'async function handleNaturalLanguage' in html

    def test_natural_language_sends_to_chat_api(self):
        """NL handler posts to /chat endpoint for conversational routing."""
        html = _read_terminal_html()
        # Extract a generous window from the function declaration
        idx = html.index('async function handleNaturalLanguage')
        func_window = html[idx:idx + 5000]
        assert '/chat' in func_window, \
            "handleNaturalLanguage should POST to /chat for conversational routing"
        assert 'message' in func_window, \
            "Should send message field to chat endpoint"

    def test_execution_error_shows_clarifying_questions(self):
        """Blocked execution shows clarifying questions via shared helper."""
        html = _read_terminal_html()
        assert 'showExecutionError' in html, \
            "Should have showExecutionError function for blocked execution"
        assert 'clarifying_questions' in html, \
            "Should show clarifying questions when execution is blocked"
        assert 'confidence' in html.lower(), \
            "Should reference confidence scoring"


# ---------------------------------------------------------------------------
# Tests — Sugar Skull Framing
# ---------------------------------------------------------------------------

class TestSugarSkullFraming:
    """Verify skull framing art appears in terminal views."""

    def test_integrated_terminal_has_skull_banner(self):
        """terminal_integrated.html has ☠ skull framing."""
        html = _read_terminal_html()
        assert '☠' in html, "Should contain ☠ skull character"
        assert '☠' in html, "Should contain ☠ skull emoji"

    def test_help_text_has_skull_labels(self):
        """Help text uses ☠ section labels."""
        html = _read_terminal_html()
        assert '☠ SYSTEM' in html
        assert '☠ TASK EXECUTION' in html
        assert '☠ NO-CODE ONBOARDING' in html

    def test_enhanced_terminal_has_skull_banner(self):
        """terminal_enhanced.html has skull framing."""
        path = os.path.join(
            os.path.dirname(__file__), '..', 'terminal_enhanced.html'
        )
        with open(path, 'r', encoding='utf-8') as f:
            html = f.read()
        assert '☠' in html
        assert '☠' in html

    def test_architect_terminal_has_skull_banner(self):
        """terminal_architect.html has skull framing."""
        path = os.path.join(
            os.path.dirname(__file__), '..', 'terminal_architect.html'
        )
        with open(path, 'r', encoding='utf-8') as f:
            html = f.read()
        assert '☠' in html
        assert '☠' in html

    def test_worker_terminal_has_skull_banner(self):
        """terminal_worker.html has skull framing."""
        path = os.path.join(
            os.path.dirname(__file__), '..', 'terminal_worker.html'
        )
        with open(path, 'r', encoding='utf-8') as f:
            html = f.read()
        assert '☠' in html
        assert '☠' in html

    def test_runtime_startup_has_skull_banner(self):
        """murphy_system_1.0_runtime.py main() has skull framing."""
        path = os.path.join(
            os.path.dirname(__file__), '..', 'murphy_system_1.0_runtime.py'
        )
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        assert '☠' in content
        assert '☠' in content

    def test_startup_script_has_skull_banner(self):
        """start_murphy_1.0.sh has skull framing."""
        path = os.path.join(
            os.path.dirname(__file__), '..', 'start_murphy_1.0.sh'
        )
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        assert '☠' in content
        assert '☠' in content


# ---------------------------------------------------------------------------
# Tests — No-Code Messaging
# ---------------------------------------------------------------------------

class TestNoCodeMessaging:
    """Verify the terminal communicates no-code usage clearly."""

    def test_banner_mentions_no_code(self):
        """Terminal banner mentions no-code."""
        html = _read_terminal_html()
        assert 'No-Code' in html or 'no-code' in html or 'No-code' in html

    def test_banner_mentions_natural_language(self):
        """Terminal banner mentions natural language control."""
        html = _read_terminal_html()
        assert 'Natural Language' in html or 'natural language' in html

    def test_help_mentions_plain_english(self):
        """Help text mentions typing in plain English."""
        html = _read_terminal_html()
        assert 'plain English' in html

    def test_init_message_mentions_plain_english(self):
        """System init message tells users to type anything."""
        html = _read_terminal_html()
        assert 'Type anything' in html or 'type anything' in html

    def test_onboarding_wizard_mentions_no_code(self):
        """Onboarding wizard page mentions no-code."""
        path = os.path.join(
            os.path.dirname(__file__), '..', 'onboarding_wizard.html'
        )
        with open(path, 'r', encoding='utf-8') as f:
            html = f.read()
        assert 'No-Code' in html or 'no-code' in html or 'No coding' in html
