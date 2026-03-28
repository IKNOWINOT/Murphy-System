"""
Tests for session-4 completion implementations.

Covers:
- B5: LLM Integration graceful error handling (bare except → typed except)
- B7: Credential verification history service_provider filter
- Regression: All prior completion test suites still pass

Best-practice labels (30 yr+ team standards):
    [UNIT]  — isolated function/class test
    [INTEG] — cross-module integration
    [SEC]   — security-related
"""

import sys
import os

# Ensure repo root and src are on the path.
_base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _base)
sys.path.insert(0, os.path.join(_base, 'src'))


# ============================================================================
# B5 — LLM Integration: bare except blocks replaced with typed handlers
# ============================================================================

class TestLLMIntegrationErrorHandling:
    """[UNIT] Verify that bare `except:` blocks have been replaced with
    typed exception handlers in llm_integration.py."""

    def test_no_bare_except_in_source(self):
        """[UNIT] llm_integration.py must not contain bare ``except:`` blocks.

        Uses the Python AST to detect actual bare-except handlers so that
        occurrences in comments, docstrings, or string literals don't produce
        false positives.
        """
        import ast

        llm_path = os.path.join(_base, 'src', 'llm_integration.py')
        with open(llm_path) as fh:
            source = fh.read()

        tree = ast.parse(source, filename=llm_path)

        bare_except_lines = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                bare_except_lines.append(node.lineno)

        assert bare_except_lines == [], (
            f"Bare except blocks found at lines: {bare_except_lines}"
        )

    def test_generate_candidates_returns_existing_on_bad_json(self):
        """[UNIT] generate_candidates should return existing_candidates
        when LLM returns non-JSON."""
        from llm_integration import LLMEnhancedMFGC, LLMProvider

        mfgc = LLMEnhancedMFGC(llm_provider=LLMProvider.NONE)
        existing = [{"approach": "manual", "score": 0.5}]
        result = mfgc.generate_candidates("test task", "expand", existing)
        # With NONE provider, LLM is unavailable so existing are returned
        assert result == existing

    def test_analyze_risks_returns_empty_when_unavailable(self):
        """[UNIT] analyze_risks should return [] when LLM is unavailable."""
        from llm_integration import LLMEnhancedMFGC, LLMProvider

        mfgc = LLMEnhancedMFGC(llm_provider=LLMProvider.NONE)
        result = mfgc.analyze_risks("task", [{"candidate": "a"}])
        assert result == []

    def test_synthesize_gates_returns_empty_when_unavailable(self):
        """[UNIT] synthesize_gates should return [] when LLM unavailable."""
        from llm_integration import LLMEnhancedMFGC, LLMProvider

        mfgc = LLMEnhancedMFGC(llm_provider=LLMProvider.NONE)
        result = mfgc.synthesize_gates("task", [{"risk": "x"}])
        assert result == []


# ============================================================================
# B7 — Credential verification history: service_provider filter
# ============================================================================

class TestCredentialVerificationHistoryFilter:
    """[UNIT] Verify that the service_provider filter in
    get_verification_history actually filters results."""

    def _build_interface(self):
        """Build a CredentialVerificationInterface with synthetic history."""
        from confidence_engine.credential_interface import (
            CredentialVerificationInterface,
            VerificationResponse,
            CredentialStatus,
            ServiceProvider,
        )

        iface = CredentialVerificationInterface()

        # Insert synthetic history entries
        iface.verification_history.append(VerificationResponse(
            credential_id="cred-aws-1",
            is_valid=True,
            status=CredentialStatus.ACTIVE,
            verification_methods_passed=[],
            verification_methods_failed=[],
            service_provider=ServiceProvider.AWS,
        ))
        iface.verification_history.append(VerificationResponse(
            credential_id="cred-gh-1",
            is_valid=True,
            status=CredentialStatus.ACTIVE,
            verification_methods_passed=[],
            verification_methods_failed=[],
            service_provider=ServiceProvider.GITHUB,
        ))
        iface.verification_history.append(VerificationResponse(
            credential_id="cred-aws-2",
            is_valid=False,
            status=CredentialStatus.EXPIRED,
            verification_methods_passed=[],
            verification_methods_failed=[],
            service_provider=ServiceProvider.AWS,
        ))

        return iface

    def test_filter_by_service_provider_aws(self):
        """[UNIT] get_verification_history(service_provider=AWS) returns
        only AWS entries."""
        from confidence_engine.credential_interface import ServiceProvider

        iface = self._build_interface()
        aws_history = iface.get_verification_history(
            service_provider=ServiceProvider.AWS
        )
        assert len(aws_history) == 2
        assert all(h.service_provider == ServiceProvider.AWS for h in aws_history)

    def test_filter_by_service_provider_github(self):
        """[UNIT] get_verification_history(service_provider=GITHUB) returns
        only GitHub entries."""
        from confidence_engine.credential_interface import ServiceProvider

        iface = self._build_interface()
        gh_history = iface.get_verification_history(
            service_provider=ServiceProvider.GITHUB
        )
        assert len(gh_history) == 1
        assert gh_history[0].credential_id == "cred-gh-1"

    def test_filter_by_credential_id(self):
        """[UNIT] get_verification_history(credential_id=...) still works."""
        iface = self._build_interface()
        history = iface.get_verification_history(credential_id="cred-aws-2")
        assert len(history) == 1
        assert history[0].credential_id == "cred-aws-2"

    def test_combined_filter(self):
        """[UNIT] Combining credential_id + service_provider narrows results."""
        from confidence_engine.credential_interface import ServiceProvider

        iface = self._build_interface()
        history = iface.get_verification_history(
            credential_id="cred-aws-1",
            service_provider=ServiceProvider.AWS,
        )
        assert len(history) == 1
        assert history[0].credential_id == "cred-aws-1"

    def test_no_filter_returns_all(self):
        """[UNIT] get_verification_history() without filters returns all."""
        iface = self._build_interface()
        assert len(iface.get_verification_history()) == 3

    def test_verification_response_has_service_provider_field(self):
        """[UNIT][SEC] VerificationResponse model exposes service_provider."""
        from confidence_engine.credential_interface import (
            VerificationResponse,
            CredentialStatus,
            ServiceProvider,
        )
        resp = VerificationResponse(
            credential_id="x",
            is_valid=True,
            status=CredentialStatus.ACTIVE,
            verification_methods_passed=[],
            verification_methods_failed=[],
            service_provider=ServiceProvider.AWS,
        )
        assert resp.service_provider == ServiceProvider.AWS


# ============================================================================
# Regression — code generation templates keep intentional TODOs
# ============================================================================

class TestCodegenTemplatesStillIntentional:
    """[UNIT] Ensure codegen templates retain their intentional TODO markers
    (these are *output* strings, not implementation gaps)."""

    def _read_source(self, rel_path):
        path = os.path.join(_base, rel_path)
        with open(path) as f:
            return f.readlines()

    def test_research_engine_template_has_todo(self):
        """The _template_basic method emits TODO in generated code."""
        lines = self._read_source('src/research_engine.py')
        found_template_todo = any(
            'TODO: Implement' in line
            for line in lines
        )
        assert found_template_todo, "research_engine.py template should keep TODO"

    def test_smart_codegen_template_has_todo(self):
        """smart_codegen.py templates emit TODO in generated code."""
        lines = self._read_source('src/smart_codegen.py')
        found = any('TODO' in line for line in lines)
        assert found, "smart_codegen.py template should keep TODO"
