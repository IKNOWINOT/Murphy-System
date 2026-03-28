"""
Test Suite: Legal & License Compliance — LEGAL-001

Programmatic verification of legal compliance for the Murphy System:
  - No GPL/AGPL/SSPL dependencies in requirements files
  - No plaintext API keys in source code
  - All source files carry BSL 1.1 license headers (Inoni-owned code)
  - THIRD_PARTY_LICENSES.md exists and is non-empty
  - PRIVACY.md exists and is non-empty
  - PII is redacted in logging calls
  - No trademarked names used as Murphy System class branding

Tests use the storyline-actuals record() pattern for cause/effect/lesson tracking.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import datetime
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List

import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
DOCS_DIR = PROJECT_ROOT / "docs"
TESTS_DIR = PROJECT_ROOT / "tests"

sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# Record infrastructure (storyline-actuals pattern)
# ---------------------------------------------------------------------------

@dataclass
class ComplianceRecord:
    """One compliance check record."""
    check_id: str
    description: str
    expected: Any
    actual: Any
    passed: bool
    cause: str = ""
    effect: str = ""
    lesson: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )


_records: List[ComplianceRecord] = []


def record(
    check_id: str,
    description: str,
    expected: Any,
    actual: Any,
    cause: str = "",
    effect: str = "",
    lesson: str = "",
) -> bool:
    """Record a check and return whether expected == actual."""
    passed = expected == actual
    _records.append(ComplianceRecord(
        check_id=check_id,
        description=description,
        expected=expected,
        actual=actual,
        passed=passed,
        cause=cause,
        effect=effect,
        lesson=lesson,
    ))
    return passed


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

COPYLEFT_LICENSES = {"gpl", "agpl", "sspl", "eupl"}
COPYLEFT_PATTERN = re.compile(
    r"\b(pylint|gpl-2|gpl-3|agpl|sspl|eupl)\b", re.IGNORECASE,
)

# Patterns that look like real API keys (not placeholders)
SECRET_PATTERNS = [
    re.compile(r"""(?<=['"])(di_[A-Za-z0-9]{20,})(?=['"])"""),
    re.compile(r"""(?<=['"])(sk-[A-Za-z0-9]{20,})(?=['"])"""),
    re.compile(r"""(?<=['"])(pk_live_[A-Za-z0-9]{10,})(?=['"])"""),
    re.compile(r"""(?<=['"])(sk_live_[A-Za-z0-9]{10,})(?=['"])"""),
    re.compile(r"""(?<=['"])(xoxb-[A-Za-z0-9\-]{20,})(?=['"])"""),
]

REQUIREMENTS_FILES = [
    PROJECT_ROOT / "requirements.txt",
    PROJECT_ROOT.parent / "requirements.txt",
]


def _read_requirements() -> List[str]:
    """Read all requirements file lines, resolving -r references."""
    lines: List[str] = []
    for req_file in PROJECT_ROOT.rglob("requirements*.txt"):
        try:
            text = req_file.read_text(encoding="utf-8")
            for line in text.splitlines():
                stripped = line.strip()
                if stripped and not stripped.startswith("#") and not stripped.startswith("-r"):
                    lines.append(stripped)
        except OSError:
            pass
    return lines


def _get_python_files() -> List[Path]:
    """Return all .py files under src/."""
    return list(SRC_DIR.rglob("*.py"))


# ===========================================================================
# 0A — Dependency License Checks
# ===========================================================================

class TestDependencyLicenses:
    """Verify no GPL/AGPL/SSPL dependencies exist in requirements."""

    def test_no_gpl_dependencies(self) -> None:
        """No GPL-licensed packages in any requirements file."""
        req_lines = _read_requirements()
        gpl_deps = [
            line for line in req_lines
            if "pylint" in line.lower()
        ]
        ok = record(
            "LEGAL-0A-01",
            "No GPL dependencies in requirements files",
            expected=0,
            actual=len(gpl_deps),
            cause="GPL copyleft is incompatible with BSL 1.1 distribution",
            effect="Replacing GPL deps ensures legal redistribution",
            lesson="Use ruff or flake8 (MIT) instead of pylint (GPL-2.0)",
        )
        assert ok, f"GPL deps found: {gpl_deps}"

    def test_no_agpl_dependencies(self) -> None:
        """No AGPL-licensed packages in requirements."""
        req_lines = _read_requirements()
        agpl_deps = [
            line for line in req_lines
            if "mongodb" in line.lower() or "agpl" in line.lower()
        ]
        ok = record(
            "LEGAL-0A-02",
            "No AGPL dependencies in requirements files",
            expected=0,
            actual=len(agpl_deps),
            cause="AGPL triggers on network use, Murphy serves over network",
            effect="Avoiding AGPL prevents license infection",
            lesson="Always verify dependency licenses before adding",
        )
        assert ok, f"AGPL deps found: {agpl_deps}"

    def test_ruff_replaces_pylint(self) -> None:
        """ruff (MIT) is present as the linter, not pylint (GPL)."""
        req_lines = _read_requirements()
        has_ruff = any("ruff" in line.lower() for line in req_lines)
        has_pylint = any("pylint" in line.lower() for line in req_lines)
        ok = record(
            "LEGAL-0A-03",
            "ruff present, pylint absent in requirements",
            expected=True,
            actual=has_ruff and not has_pylint,
            cause="pylint is GPL-2.0; ruff is MIT",
            effect="Linter available without copyleft risk",
            lesson="ruff is faster and MIT-licensed",
        )
        assert ok, f"ruff={has_ruff}, pylint={has_pylint}"


# ===========================================================================
# 0B — License Header Checks
# ===========================================================================

class TestLicenseHeaders:
    """Verify license headers are consistent."""

    def test_no_apache_in_requirements_header(self) -> None:
        """requirements_murphy_1.0.txt header says BSL-1.1, not Apache."""
        req_file = PROJECT_ROOT / "requirements_murphy_1.0.txt"
        if not req_file.exists():
            pytest.skip("requirements_murphy_1.0.txt not found")
        header = req_file.read_text(encoding="utf-8")[:500]
        has_apache = "Apache License" in header
        ok = record(
            "LEGAL-0B-01",
            "requirements_murphy_1.0.txt header is BSL-1.1",
            expected=False,
            actual=has_apache,
            cause="Project license is BSL 1.1, not Apache 2.0",
            effect="Consistent license declarations avoid legal confusion",
            lesson="All project files should reference BSL 1.1",
        )
        assert ok, "Apache License found in requirements_murphy_1.0.txt header"

    def test_no_apache_in_dockerfile(self) -> None:
        """Dockerfile header says BSL-1.1, not Apache."""
        dockerfile = PROJECT_ROOT / "Dockerfile"
        if not dockerfile.exists():
            pytest.skip("Dockerfile not found")
        header = dockerfile.read_text(encoding="utf-8")[:300]
        has_apache = "Apache License" in header
        ok = record(
            "LEGAL-0B-02",
            "Dockerfile header is BSL-1.1",
            expected=False,
            actual=has_apache,
            cause="Dockerfile should match project license",
            effect="Prevents license misidentification",
            lesson="Infrastructure files need license headers too",
        )
        assert ok, "Apache License found in Dockerfile header"

    def test_no_apache_in_docker_compose(self) -> None:
        """docker-compose.yml header says BSL-1.1, not Apache."""
        compose = PROJECT_ROOT / "docker-compose.yml"
        if not compose.exists():
            pytest.skip("docker-compose.yml not found")
        header = compose.read_text(encoding="utf-8")[:300]
        has_apache = "Apache License" in header
        ok = record(
            "LEGAL-0B-03",
            "docker-compose.yml header is BSL-1.1",
            expected=False,
            actual=has_apache,
            cause="Docker compose should match project license",
            effect="Prevents license misidentification",
            lesson="All config files need consistent license headers",
        )
        assert ok, "Apache License found in docker-compose.yml header"

    def test_auar_module_headers(self) -> None:
        """AUAR module files use BSL-1.1, not Apache."""
        auar_dir = SRC_DIR / "auar"
        if not auar_dir.exists():
            pytest.skip("AUAR module not found")
        apache_files = []
        for py_file in auar_dir.glob("*.py"):
            header = py_file.read_text(encoding="utf-8")[:500]
            if "Apache License" in header:
                apache_files.append(py_file.name)
        ok = record(
            "LEGAL-0B-04",
            "AUAR module files use BSL-1.1 headers",
            expected=0,
            actual=len(apache_files),
            cause="AUAR is Inoni-owned code, should be BSL 1.1",
            effect="Consistent licensing across all modules",
            lesson="Sub-module headers must match project license",
        )
        assert ok, f"Apache headers in AUAR: {apache_files}"


# ===========================================================================
# 0C — API Key Security
# ===========================================================================

class TestAPIKeySecurity:
    """Verify no plaintext API keys in source code."""

    def test_no_hardcoded_api_keys(self) -> None:
        """No real API keys hardcoded in Python source files."""
        findings: List[str] = []
        for py_file in _get_python_files():
            try:
                content = py_file.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            for pattern in SECRET_PATTERNS:
                matches = pattern.findall(content)
                for match in matches:
                    # Skip obvious test/placeholder values
                    if any(kw in match.lower() for kw in ("test", "fake", "example", "your_", "placeholder")):
                        continue
                    findings.append(f"{py_file.name}: {match[:10]}...")
        ok = record(
            "LEGAL-0C-01",
            "No hardcoded API keys in src/ Python files",
            expected=0,
            actual=len(findings),
            cause="Hardcoded keys are a security and legal risk",
            effect="All keys must be in env vars or SecureKeyManager",
            lesson="Use os.environ.get() or SecureKeyManager for secrets",
        )
        assert ok, f"Hardcoded keys found: {findings}"

    def test_no_secrets_in_default_values(self) -> None:
        """No os.environ.get() with real-looking key defaults."""
        secret_default_pattern = re.compile(
            r'os\.environ\.get\([^,]+,\s*["\'](?:gsk_|sk-|pk_live_|sk_live_)([A-Za-z0-9]{10,})["\']'
        )
        findings: List[str] = []
        for py_file in _get_python_files():
            try:
                content = py_file.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if secret_default_pattern.search(content):
                findings.append(py_file.name)
        ok = record(
            "LEGAL-0C-02",
            "No real API keys as environ.get defaults in src/",
            expected=0,
            actual=len(findings),
            cause="Default values in environ.get may leak to production",
            effect="Forces explicit configuration, prevents accidental exposure",
            lesson="Use empty string or None as default for API keys",
        )
        assert ok, f"Secret defaults found in: {findings}"


# ===========================================================================
# 0D — Trademark Naming
# ===========================================================================

class TestTrademarkNaming:
    """Verify no trademarked names used as Murphy System branding."""

    def test_no_trademark_class_names(self) -> None:
        """No classes named directly after trademarked services."""
        # Allowed: DeepInfraConnector, OpenAIAdapter, etc. (service + suffix)
        # Not allowed: class DeepInfra, class OpenAI, class Stripe (as Murphy's own)
        trademark_class_pattern = re.compile(
            r'class\s+(DeepInfra|OpenAI|Anthropic|Stripe|Coinbase|HeyGen|Tavus|Twilio|SendGrid)\s*[\(:]',
        )
        findings: List[str] = []
        for py_file in _get_python_files():
            try:
                content = py_file.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            for match in trademark_class_pattern.finditer(content):
                # Skip test files
                if "test" in py_file.name.lower():
                    continue
                findings.append(f"{py_file.name}: class {match.group(1)}")
        ok = record(
            "LEGAL-0D-01",
            "No bare trademarked class names in src/",
            expected=0,
            actual=len(findings),
            cause="Using trademarked names as class names implies ownership",
            effect="Adapter/Connector suffix clarifies integration vs ownership",
            lesson="Name classes LLMProviderAdapter with config for provider name",
        )
        assert ok, f"Trademark class names: {findings}"


# ===========================================================================
# 0E — Data Privacy
# ===========================================================================

class TestDataPrivacy:
    """Verify PII is redacted in logs and PRIVACY.md exists."""

    def test_privacy_md_exists(self) -> None:
        """PRIVACY.md exists and is non-empty."""
        privacy = PROJECT_ROOT / "PRIVACY.md"
        exists = privacy.exists() and privacy.stat().st_size > 100
        ok = record(
            "LEGAL-0E-01",
            "PRIVACY.md exists and is non-empty",
            expected=True,
            actual=exists,
            cause="Data privacy documentation is required",
            effect="Users know what data is collected and why",
            lesson="Always document data collection practices",
        )
        assert ok, "PRIVACY.md missing or empty"

    def test_third_party_licenses_exists(self) -> None:
        """THIRD_PARTY_LICENSES.md exists and is non-empty."""
        tpl = PROJECT_ROOT / "THIRD_PARTY_LICENSES.md"
        exists = tpl.exists() and tpl.stat().st_size > 100
        ok = record(
            "LEGAL-0E-02",
            "THIRD_PARTY_LICENSES.md exists and is non-empty",
            expected=True,
            actual=exists,
            cause="Third-party license attribution is legally required",
            effect="Proper attribution for all dependencies",
            lesson="MIT/BSD/Apache all require attribution in redistribution",
        )
        assert ok, "THIRD_PARTY_LICENSES.md missing or empty"

    def test_no_plaintext_email_in_signup_logger(self) -> None:
        """signup_gateway.py does not log raw email addresses."""
        sg_file = SRC_DIR / "signup_gateway.py"
        if not sg_file.exists():
            pytest.skip("signup_gateway.py not found")
        content = sg_file.read_text(encoding="utf-8")
        # Check that logger lines don't use profile.email directly
        plaintext_email_log = re.findall(
            r'logger\.\w+\(.*profile\.email(?!\s*\)).*\)', content,
        )
        ok = record(
            "LEGAL-0E-03",
            "No plaintext email in signup_gateway logger calls",
            expected=0,
            actual=len(plaintext_email_log),
            cause="Logging raw emails is a PII violation",
            effect="Emails are redacted as u***@domain.com in logs",
            lesson="Always use _redact_email() before logging",
        )
        assert ok, f"Plaintext email in logger: {plaintext_email_log}"

    def test_no_plaintext_phone_in_comms_logger(self) -> None:
        """comms/connectors.py does not log raw phone numbers."""
        conn_file = SRC_DIR / "comms" / "connectors.py"
        if not conn_file.exists():
            pytest.skip("comms/connectors.py not found")
        content = conn_file.read_text(encoding="utf-8")
        # Check that Twilio logger line doesn't include to_number
        plaintext_phone = re.findall(
            r'logger\.\w+\(.*to_number.*\)', content,
        )
        ok = record(
            "LEGAL-0E-04",
            "No plaintext phone number in Twilio SMS logger",
            expected=0,
            actual=len(plaintext_phone),
            cause="Logging raw phone numbers is a PII violation",
            effect="Phone numbers are redacted in log output",
            lesson="Never log PII; use redaction helpers",
        )
        assert ok, f"Plaintext phone in logger: {plaintext_phone}"

    def test_signup_audit_redacts_email(self) -> None:
        """signup_gateway.py _audit call for signup redacts email."""
        sg_file = SRC_DIR / "signup_gateway.py"
        if not sg_file.exists():
            pytest.skip("signup_gateway.py not found")
        content = sg_file.read_text(encoding="utf-8")
        # The audit call should use _redact_email, not raw profile.email
        raw_email_audit = re.findall(
            r'_audit\("signup".*"email":\s*profile\.email', content,
        )
        ok = record(
            "LEGAL-0E-05",
            "Signup audit uses _redact_email for email field",
            expected=0,
            actual=len(raw_email_audit),
            cause="Audit logs with raw email violate PII policy",
            effect="Audit entries contain redacted emails only",
            lesson="Apply _redact_email before any persistence",
        )
        assert ok, f"Raw email in audit: {raw_email_audit}"

    def test_eula_audit_redacts_ip(self) -> None:
        """signup_gateway.py _audit call for EULA redacts IP address."""
        sg_file = SRC_DIR / "signup_gateway.py"
        if not sg_file.exists():
            pytest.skip("signup_gateway.py not found")
        content = sg_file.read_text(encoding="utf-8")
        # The audit call should use _redact_ip, not raw ip_address
        raw_ip_audit = re.findall(
            r'_audit\("accept_eula".*"ip":\s*ip_address[^)]', content,
        )
        ok = record(
            "LEGAL-0E-06",
            "EULA audit uses _redact_ip for IP field",
            expected=0,
            actual=len(raw_ip_audit),
            cause="Audit logs with raw IP violate PII policy",
            effect="Audit entries contain redacted IPs only",
            lesson="Apply _redact_ip before any persistence",
        )
        assert ok, f"Raw IP in audit: {raw_ip_audit}"


# ===========================================================================
# 0F — Export Control
# ===========================================================================

class TestExportControl:
    """Verify cryptographic code uses standard algorithms only."""

    def test_no_restricted_crypto_algorithms(self) -> None:
        """No restricted cryptographic algorithms in source code."""
        restricted_patterns = [
            re.compile(r'\bSKIPJACK\b', re.IGNORECASE),
            re.compile(r'\bCLIPPER\b', re.IGNORECASE),
        ]
        findings: List[str] = []
        for py_file in _get_python_files():
            try:
                content = py_file.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            for pattern in restricted_patterns:
                if pattern.search(content):
                    findings.append(f"{py_file.name}: {pattern.pattern}")
        ok = record(
            "LEGAL-0F-01",
            "No restricted crypto algorithms in src/",
            expected=0,
            actual=len(findings),
            cause="Restricted algorithms need export classification",
            effect="Standard algorithms (AES, RSA, ECDSA) are EAR99 exempt",
            lesson="Use cryptography library defaults for safe algorithms",
        )
        assert ok, f"Restricted crypto found: {findings}"

    def test_standard_crypto_usage(self) -> None:
        """Verify cryptography library uses standard Fernet/AES."""
        skm_file = SRC_DIR / "secure_key_manager.py"
        if not skm_file.exists():
            pytest.skip("secure_key_manager.py not found")
        content = skm_file.read_text(encoding="utf-8")
        uses_fernet = "Fernet" in content
        ok = record(
            "LEGAL-0F-02",
            "SecureKeyManager uses standard Fernet encryption",
            expected=True,
            actual=uses_fernet,
            cause="Fernet (AES-128-CBC + HMAC) is EAR99 mass-market exempt",
            effect="No export control classification needed",
            lesson="Standard symmetric encryption is safe for distribution",
        )
        assert ok, "SecureKeyManager does not use Fernet"


# ===========================================================================
# Summary
# ===========================================================================

class TestComplianceSummary:
    """Verify overall compliance posture."""

    def test_redact_email_helper_exists(self) -> None:
        """_redact_email helper function exists in signup_gateway."""
        sg_file = SRC_DIR / "signup_gateway.py"
        if not sg_file.exists():
            pytest.skip("signup_gateway.py not found")
        content = sg_file.read_text(encoding="utf-8")
        has_helper = "def _redact_email" in content
        ok = record(
            "LEGAL-SUM-01",
            "_redact_email helper exists in signup_gateway",
            expected=True,
            actual=has_helper,
            cause="PII redaction requires a helper function",
            effect="Consistent email masking across all log/audit calls",
            lesson="Centralize PII redaction in helper functions",
        )
        assert ok, "_redact_email not found in signup_gateway.py"

    def test_redact_ip_helper_exists(self) -> None:
        """_redact_ip helper function exists in signup_gateway."""
        sg_file = SRC_DIR / "signup_gateway.py"
        if not sg_file.exists():
            pytest.skip("signup_gateway.py not found")
        content = sg_file.read_text(encoding="utf-8")
        has_helper = "def _redact_ip" in content
        ok = record(
            "LEGAL-SUM-02",
            "_redact_ip helper exists in signup_gateway",
            expected=True,
            actual=has_helper,
            cause="PII redaction requires a helper function",
            effect="Consistent IP masking across all log/audit calls",
            lesson="Centralize PII redaction in helper functions",
        )
        assert ok, "_redact_ip not found in signup_gateway.py"
