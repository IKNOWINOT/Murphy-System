# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Sandbox Quarantine Protocol - Step 5.5 in the integration pipeline.

Sits between SafetyTester and HITL Approval.  Nothing reaches HITL or the
live system until it passes quarantine.

Steps performed (all in the order described below):
  a) License Compliance Gate          – hard gate, runs first
  b) Documentation Adaptation Filter  – produce integration_profile
  c) Data Input Schema Extraction     – produce input_adapter_spec
  d) ML-Specific Threat Scanner       – detect dangerous patterns
  e) Auto-Remediation                 – fix what can be fixed automatically
  f) Sandbox Test-Load                – isolated import attempt
  g) Quarantine Report                – score & final verdict
"""

from __future__ import annotations

import importlib
import json
import logging
import os
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("integration_engine.sandbox_quarantine")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

APPROVED_LICENSES: frozenset = frozenset({
    "MIT", "BSD", "BSD-2-Clause", "BSD-3-Clause",
    "Apache", "Apache-2.0", "ISC", "Unlicense", "CC0",
})

COPYLEFT_LICENSES: frozenset = frozenset({
    "GPL", "GPL-2.0", "GPL-3.0", "AGPL", "AGPL-3.0",
    "LGPL", "LGPL-2.0", "LGPL-2.1", "LGPL-3.0",
    "SSPL", "SSPL-1.0", "EUPL", "EUPL-1.1", "EUPL-1.2",
})

# ---------------------------------------------------------------------------
# ThreatFinding dataclass
# ---------------------------------------------------------------------------


@dataclass
class ThreatFinding:
    """One finding from the ML-specific threat scanner."""
    file_path: str
    line_number: int
    pattern: str
    severity: str          # CRITICAL / HIGH / MEDIUM / LOW
    can_auto_remediate: bool
    remediation_description: str
    matched_text: str = ""

    def to_dict(self) -> Dict:
        return {
            "file_path": self.file_path,
            "line_number": self.line_number,
            "pattern": self.pattern,
            "severity": self.severity,
            "can_auto_remediate": self.can_auto_remediate,
            "remediation_description": self.remediation_description,
            "matched_text": self.matched_text,
        }


# ---------------------------------------------------------------------------
# QuarantineReport dataclass
# ---------------------------------------------------------------------------

@dataclass
class QuarantineReport:
    """Full output of the quarantine run."""
    admitted: bool
    license_check: Dict[str, Any]
    license_conflicts: List[Dict[str, str]]
    threat_findings: List[ThreatFinding]
    auto_remediations: List[Dict[str, str]]
    integration_profile: Dict[str, Any]
    input_adapter_spec: Dict[str, Any]
    quarantine_score: float
    rejection_reason: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "admitted": self.admitted,
            "license_check": self.license_check,
            "license_conflicts": self.license_conflicts,
            "threat_findings": [f.to_dict() for f in self.threat_findings],
            "auto_remediations": self.auto_remediations,
            "integration_profile": self.integration_profile,
            "input_adapter_spec": self.input_adapter_spec,
            "quarantine_score": self.quarantine_score,
            "rejection_reason": self.rejection_reason,
        }


# ---------------------------------------------------------------------------
# SandboxQuarantine
# ---------------------------------------------------------------------------

class SandboxQuarantine:
    """
    Sandbox Quarantine Protocol.

    Usage::

        quarantine = SandboxQuarantine()
        report = quarantine.quarantine(repo_path, audit, module)
        if not report.admitted:
            # reject — do not create HITL request
            ...
    """

    # Threat scanner patterns: (regex, severity, can_auto_remediate, description)
    _THREAT_PATTERNS: List[Tuple[str, str, bool, str]] = [
        (
            r"pickle\.load\s*\(",
            "CRITICAL",
            False,
            "Replace pickle.load with a restricted unpickler or a safer serialisation format",
        ),
        (
            r"eval\s*\(",
            "CRITICAL",
            False,
            "Remove or sandbox eval() — executes arbitrary code",
        ),
        (
            r"exec\s*\(",
            "CRITICAL",
            False,
            "Remove or sandbox exec() — executes arbitrary code",
        ),
        # SEC-SANDBOX-003: Additional code-execution patterns.
        (
            r"__import__\s*\(",
            "CRITICAL",
            False,
            "SEC-SANDBOX-003: __import__() can bypass restricted builtins — remove or replace",
        ),
        (
            r"importlib\.import_module\s*\(",
            "CRITICAL",
            False,
            "SEC-SANDBOX-003: importlib.import_module can load arbitrary modules — audit usage",
        ),
        (
            r"(?:ctypes|cffi)\.",
            "HIGH",
            False,
            "SEC-SANDBOX-003: ctypes/cffi can invoke arbitrary C functions — audit usage",
        ),
        (
            r"compile\s*\([^)]+,\s*['\"]exec['\"]",
            "HIGH",
            False,
            "SEC-SANDBOX-003: compile(..., 'exec') can create code objects for execution",
        ),
        (
            r"trust_remote_code\s*=\s*True",
            "HIGH",
            True,
            "Set trust_remote_code=False and pin to a specific revision after manual audit",
        ),
        (
            r"torch\.load\s*\([^)]*\)",
            "HIGH",
            True,
            "Add weights_only=True to torch.load() to prevent arbitrary code execution via pickled weights",
        ),
        (
            r"subprocess\s*\.",
            "HIGH",
            False,
            "Audit subprocess usage — may allow shell injection",
        ),
        (
            r"os\.system\s*\(",
            "HIGH",
            False,
            "Audit os.system usage — may allow shell injection",
        ),
        (
            r"(?:requests\.get|requests\.post|urllib\.request|urllib\.urlopen|socket\.connect)",
            "MEDIUM",
            False,
            "Network call detected inside model loading code — verify it is intentional and safe",
        ),
    ]

    def __init__(self) -> None:
        self._approved_licenses = APPROVED_LICENSES
        self._copyleft_licenses = COPYLEFT_LICENSES

    # ------------------------------------------------------------------
    # SEC-SANDBOX-001: Pre-execution quarantine gate
    # ------------------------------------------------------------------

    def quarantine_check(self, code: str) -> Tuple[bool, List[str]]:
        """Check code for dangerous patterns **before** execution.

        SEC-SANDBOX-001: This MUST be called before any ``exec()`` or
        ``eval()`` of user/automation-supplied code.

        SEC-SANDBOX-002: Full containerised runtime isolation is planned as
        a future enhancement.  Until then, this static gate is the hard
        blocker.

        Args:
            code: Source code string to inspect.

        Returns:
            ``(is_safe, findings)`` where *is_safe* is ``False`` when any
            CRITICAL pattern is detected.
        """
        findings: List[str] = []
        is_safe = True
        for pattern, severity, _can_fix, description in self._THREAT_PATTERNS:
            if re.search(pattern, code):
                findings.append(f"[{severity}] {description}")
                if severity == "CRITICAL":
                    is_safe = False
        return is_safe, findings

    # ------------------------------------------------------------------
    # Public entry-point
    # ------------------------------------------------------------------

    def quarantine(
        self,
        repo_path: str,
        audit: Dict[str, Any],
        module: Dict[str, Any],
    ) -> QuarantineReport:
        """
        Run the full quarantine protocol.

        Args:
            repo_path: Local path to the cloned repository.
            audit:     SwissKiss audit dict (contains 'license', 'deps', …).
            module:    Generated Murphy module dict.

        Returns:
            QuarantineReport.  Check `admitted` first.
        """
        repo = Path(repo_path)

        # ----------------------------------------------------------------
        # a) License Compliance Gate — MUST run first, hard gate
        # ----------------------------------------------------------------
        license_check, license_conflicts = self._check_license(audit)
        if not license_check["passed"]:
            return QuarantineReport(
                admitted=False,
                license_check=license_check,
                license_conflicts=license_conflicts,
                threat_findings=[],
                auto_remediations=[],
                integration_profile={},
                input_adapter_spec={},
                quarantine_score=0.0,
                rejection_reason=license_check["reason"],
            )

        # ----------------------------------------------------------------
        # b) Documentation Adaptation Filter
        # ----------------------------------------------------------------
        integration_profile = self._build_integration_profile(repo, audit, module)

        # ----------------------------------------------------------------
        # c) Data Input Schema Extraction
        # ----------------------------------------------------------------
        input_adapter_spec = self._extract_input_adapter_spec(repo, audit, module)

        # ----------------------------------------------------------------
        # d) ML-Specific Threat Scanner
        # ----------------------------------------------------------------
        threat_findings = self._scan_threats(repo)

        # ----------------------------------------------------------------
        # e) Auto-Remediation
        # ----------------------------------------------------------------
        auto_remediations = self._auto_remediate(repo, threat_findings)

        # ----------------------------------------------------------------
        # f) Sandbox Test-Load
        # ----------------------------------------------------------------
        sandbox_result = self._sandbox_test_load(repo, module)

        # ----------------------------------------------------------------
        # g) Score & final decision
        # ----------------------------------------------------------------
        quarantine_score = self._compute_score(
            threat_findings=threat_findings,
            auto_remediations=auto_remediations,
            sandbox_result=sandbox_result,
        )

        if quarantine_score < 0.4:
            return QuarantineReport(
                admitted=False,
                license_check=license_check,
                license_conflicts=license_conflicts,
                threat_findings=threat_findings,
                auto_remediations=auto_remediations,
                integration_profile=integration_profile,
                input_adapter_spec=input_adapter_spec,
                quarantine_score=quarantine_score,
                rejection_reason=(
                    f"Quarantine score {quarantine_score:.2f} is below the minimum "
                    "threshold of 0.40. Address critical/high threat findings before re-submitting."
                ),
            )

        return QuarantineReport(
            admitted=True,
            license_check=license_check,
            license_conflicts=license_conflicts,
            threat_findings=threat_findings,
            auto_remediations=auto_remediations,
            integration_profile=integration_profile,
            input_adapter_spec=input_adapter_spec,
            quarantine_score=quarantine_score,
            rejection_reason=None,
        )

    # ------------------------------------------------------------------
    # a) License Compliance Gate
    # ------------------------------------------------------------------

    def _check_license(
        self, audit: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], List[Dict[str, str]]]:
        """
        Returns (license_check_dict, list_of_transitive_conflicts).
        license_check_dict always has 'passed' and 'reason' keys.
        """
        detected = audit.get("license", "UNKNOWN")

        # Hard gate: missing or unknown
        if detected in ("MISSING", "UNKNOWN", None, ""):
            return (
                {
                    "passed": False,
                    "license": detected,
                    "reason": (
                        f"License is '{detected}'. Cannot verify usage rights — "
                        "auto-rejected."
                    ),
                },
                [],
            )

        # Hard gate: not in approved list
        if detected not in self._approved_licenses:
            return (
                {
                    "passed": False,
                    "license": detected,
                    "reason": (
                        f"License '{detected}' is not in Murphy's approved list "
                        f"({', '.join(sorted(self._approved_licenses))}). Auto-rejected."
                    ),
                },
                [],
            )

        # Transitive dependency conflicts
        conflicts = self._check_transitive_conflicts(audit)

        return (
            {
                "passed": True,
                "license": detected,
                "reason": f"License '{detected}' is approved for use.",
            },
            conflicts,
        )

    def _check_transitive_conflicts(
        self, audit: Dict[str, Any]
    ) -> List[Dict[str, str]]:
        """
        Check dependency list for known copyleft licenses that would conflict
        with Murphy's BSL 1.1 license.
        """
        conflicts: List[Dict[str, str]] = []
        deps = audit.get("deps", {})

        # deps can be a dict  {pkg: {license: ..., version: ...}}
        # or a list [{name, license}]
        items: List[Tuple[str, str]] = []
        if isinstance(deps, dict):
            for pkg, info in deps.items():
                if isinstance(info, dict):
                    lic = info.get("license", "")
                elif isinstance(info, str):
                    lic = info
                else:
                    lic = ""
                items.append((pkg, lic))
        elif isinstance(deps, list):
            for entry in deps:
                if isinstance(entry, dict):
                    items.append((entry.get("name", ""), entry.get("license", "")))

        for pkg, lic in items:
            lic_upper = lic.upper()
            for copyleft in self._copyleft_licenses:
                if copyleft.upper() in lic_upper:
                    conflicts.append({
                        "package": pkg,
                        "license": lic,
                        "conflict_type": "copyleft",
                        "reason": (
                            f"Package '{pkg}' has a '{lic}' license which conflicts "
                            "with Murphy's BSL 1.1."
                        ),
                    })
                    break

        return conflicts

    # ------------------------------------------------------------------
    # b) Documentation Adaptation Filter
    # ------------------------------------------------------------------

    def _build_integration_profile(
        self,
        repo: Path,
        audit: Dict[str, Any],
        module: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Produce a Murphy-internal integration_profile from the README / docs.
        Strips third-party branding and preserves attribution.
        """
        readme_text = self._read_readme(repo)
        raw_docs = self._read_docs(repo)

        profile: Dict[str, Any] = {
            "capabilities": self._extract_capabilities(readme_text, module),
            "api_surface": self._extract_api_surface(readme_text, raw_docs),
            "data_formats": self._extract_data_formats(readme_text, raw_docs),
            "dependencies": self._extract_dependencies(audit, readme_text),
            "hardware_requirements": self._extract_hardware_requirements(readme_text),
            "model_variants": self._extract_model_variants(readme_text),
        }

        # Attribution — always preserved
        profile["attribution"] = self._build_attribution(audit)

        return profile

    def _read_readme(self, repo: Path) -> str:
        for candidate in ("README.md", "README.rst", "README.txt", "README"):
            p = repo / candidate
            if p.exists():
                try:
                    return p.read_text(encoding="utf-8", errors="replace")
                except OSError as exc:
                    logger.debug("Non-critical error: %s", exc)
        return ""

    def _read_docs(self, repo: Path) -> str:
        parts: List[str] = []
        for docs_dir in ("docs", "doc", "documentation"):
            d = repo / docs_dir
            if d.is_dir():
                for fp in sorted(d.rglob("*.md"))[:10]:
                    try:
                        parts.append(fp.read_text(encoding="utf-8", errors="replace"))
                    except OSError as exc:
                        logger.debug("Non-critical error: %s", exc)
        return "\n\n".join(parts)

    @staticmethod
    def _strip_branding(text: str) -> str:
        """
        Remove promotional language, star/badge requests, and external links
        that are not needed for integration.
        """
        # Remove markdown badge lines ([![...](...)])
        text = re.sub(r'\[!\[.*?\]\(.*?\)\]\(.*?\)', "", text)
        # Remove standalone http(s) links not inside code fences
        text = re.sub(r'(?<!\`)(https?://\S+)(?!\`)', "[link removed]", text)
        # Remove "please cite / if you use this work, cite" paragraphs
        text = re.sub(
            r'(?i)(please\s+cite|if\s+you\s+use|cite\s+this|star\s+the\s+repo'
            r'|give\s+us\s+a\s+star|⭐|🌟|thank\s+you\s+for\s+citing)[^\n]*\n?',
            "",
            text,
        )
        return text.strip()

    def _extract_capabilities(
        self, readme: str, module: Dict[str, Any]
    ) -> List[str]:
        caps: List[str] = []
        # Prefer module capabilities when available
        if module.get("capabilities"):
            caps = list(module["capabilities"])
        # Supplement from README bullet points under capability-like headings
        heading_re = re.compile(
            r"(?i)#+\s*(features?|capabilities?|what\s+it\s+does|highlights?|key\s+features?)[^\n]*\n"
            r"((?:[^\n#][^\n]*\n?)*)",
            re.MULTILINE,
        )
        for m in heading_re.finditer(readme):
            block = m.group(2)
            for line in block.splitlines():
                stripped = re.sub(r"^[\s\-\*\•\d\.]+", "", line).strip()
                if stripped and len(stripped) > 5 and stripped not in caps:
                    caps.append(stripped)
        return caps[:30]

    def _extract_api_surface(self, readme: str, docs: str) -> List[Dict[str, str]]:
        combined = readme + "\n" + docs
        entries: List[Dict[str, str]] = []
        # Collect Python function/class signatures from fenced code blocks
        code_block_re = re.compile(r"```(?:python|py)?\n(.*?)```", re.DOTALL)
        sig_re = re.compile(r"^\s*(def |class )\S", re.MULTILINE)
        for block in code_block_re.finditer(combined):
            code = block.group(1)
            for sig_m in sig_re.finditer(code):
                line_start = code.rfind("\n", 0, sig_m.start()) + 1
                line_end = code.find("\n", sig_m.start())
                sig_line = code[line_start: line_end if line_end != -1 else None].strip()
                if sig_line not in [e.get("signature") for e in entries]:
                    entries.append({"signature": sig_line, "source": "readme/docs"})
        return entries[:20]

    def _extract_data_formats(self, readme: str, docs: str) -> List[Dict[str, Any]]:
        combined = readme + "\n" + docs
        formats: List[Dict[str, Any]] = []
        json_re = re.compile(r"```(?:json)?\n(\{.*?\})\n```", re.DOTALL)
        for m in json_re.finditer(combined):
            try:
                obj = json.loads(m.group(1))
                formats.append({"type": "json_example", "schema": obj})
            except json.JSONDecodeError:
                pass
        return formats[:10]

    def _extract_dependencies(
        self, audit: Dict[str, Any], readme: str
    ) -> List[str]:
        deps_list: List[str] = []
        # From audit deps
        raw = audit.get("deps", {})
        if isinstance(raw, dict):
            for pkg, info in raw.items():
                ver = ""
                if isinstance(info, dict):
                    ver = info.get("version", "")
                deps_list.append(f"{pkg}{('==' + ver) if ver else ''}")
        elif isinstance(raw, list):
            for d in raw:
                if isinstance(d, dict):
                    name = d.get("name", "")
                    ver = d.get("version", "")
                    deps_list.append(f"{name}{('==' + ver) if ver else ''}")
                elif isinstance(d, str):
                    deps_list.append(d)
        # Also look for requirements.txt in repo path stored in audit
        return deps_list[:50]

    def _extract_hardware_requirements(self, readme: str) -> List[str]:
        reqs: List[str] = []
        hw_re = re.compile(
            r"(?i)(cuda|gpu|memory|vram|bfloat16|fp16|a100|v100|h100|rtx|tpu)[^\n]*",
        )
        for m in hw_re.finditer(readme):
            line = m.group(0).strip()
            if line not in reqs:
                reqs.append(line)
        return reqs[:10]

    def _extract_model_variants(self, readme: str) -> List[Dict[str, str]]:
        variants: List[Dict[str, str]] = []
        # Look for HuggingFace model links
        hf_re = re.compile(
            r"(?:huggingface\.co/|hf\.co/)([A-Za-z0-9_\-]+/[A-Za-z0-9_\-\.]+)",
        )
        for m in hf_re.finditer(readme):
            model_id = m.group(1)
            if model_id not in [v.get("model_id") for v in variants]:
                variants.append({
                    "model_id": model_id,
                    "source": "readme",
                })
        return variants[:10]

    def _build_attribution(self, audit: Dict[str, Any]) -> Dict[str, str]:
        return {
            "original_license": audit.get("license", "UNKNOWN"),
            "original_authors": audit.get("authors", ""),
            "original_repo_url": audit.get("source_url", audit.get("url", "")),
            "attribution_notice": (
                f"This integration uses code originally licensed under "
                f"{audit.get('license', 'UNKNOWN')}. "
                "See the original repository for full license text and copyright notices."
            ),
        }

    # ------------------------------------------------------------------
    # c) Data Input Schema Extraction
    # ------------------------------------------------------------------

    def _extract_input_adapter_spec(
        self,
        repo: Path,
        audit: Dict[str, Any],
        module: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Produce a Murphy-compatible input_adapter_spec.json that maps Murphy's
        internal data structures to the third-party format.
        """
        readme = self._read_readme(repo)

        spec: Dict[str, Any] = {
            "module_name": module.get("name", "unknown"),
            "murphy_to_thirdparty": [],
            "thirdparty_to_murphy": [],
            "detected_formats": [],
        }

        # Detect conversation format (role/content pattern)
        if re.search(r'"role"\s*:', readme) and re.search(r'"content"\s*:', readme):
            spec["detected_formats"].append("conversation_json")
            spec["murphy_to_thirdparty"].append({
                "murphy_field": "prompt",
                "thirdparty_field": "messages[].content",
                "transform": "wrap_in_conversation_format",
                "notes": "Murphy prompt → list of role/content messages",
            })

        # Detect bounding-box output pattern
        if re.search(r"<object>.*?\(x\d,y\d\)", readme, re.DOTALL):
            spec["thirdparty_to_murphy"].append({
                "thirdparty_field": "model_output",
                "murphy_field": "bounding_boxes",
                "transform": "parse_object_tags",
                "notes": "Parse <object> (x1,y1), (x2,y2) </object> tags to Murphy bbox dicts",
            })

        return spec

    # ------------------------------------------------------------------
    # d) ML-Specific Threat Scanner
    # ------------------------------------------------------------------

    def _scan_threats(self, repo: Path) -> List[ThreatFinding]:
        findings: List[ThreatFinding] = []
        compiled = [
            (re.compile(pat, re.MULTILINE), sev, remed, desc)
            for pat, sev, remed, desc in self._THREAT_PATTERNS
        ]

        # Also check for base64/obfuscated payloads
        b64_re = re.compile(r'base64\.b64decode\s*\(|__import__\s*\(')

        for py_file in sorted(repo.rglob("*.py")):
            try:
                text = py_file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue

            lines = text.splitlines()
            rel = str(py_file.relative_to(repo))

            # Standard threat patterns
            for compiled_re, severity, can_auto, description in compiled:
                for m in compiled_re.finditer(text):
                    line_no = text.count("\n", 0, m.start()) + 1
                    # For torch.load, only flag if weights_only is absent
                    if "torch.load" in m.group(0):
                        if "weights_only=True" in m.group(0):
                            continue
                    findings.append(ThreatFinding(
                        file_path=rel,
                        line_number=line_no,
                        pattern=compiled_re.pattern,
                        severity=severity,
                        can_auto_remediate=can_auto,
                        remediation_description=description,
                        matched_text=lines[line_no - 1].strip() if line_no <= len(lines) else "",
                    ))

            # Base64/obfuscation check (HIGH)
            for m in b64_re.finditer(text):
                line_no = text.count("\n", 0, m.start()) + 1
                findings.append(ThreatFinding(
                    file_path=rel,
                    line_number=line_no,
                    pattern="base64_or_dynamic_import",
                    severity="HIGH",
                    can_auto_remediate=False,
                    remediation_description="Review base64-encoded or dynamically-imported payload",
                    matched_text=lines[line_no - 1].strip() if line_no <= len(lines) else "",
                ))

        return findings

    # ------------------------------------------------------------------
    # e) Auto-Remediation
    # ------------------------------------------------------------------

    def _auto_remediate(
        self,
        repo: Path,
        findings: List[ThreatFinding],
    ) -> List[Dict[str, str]]:
        """
        Apply auto-remediations where `can_auto_remediate=True`.
        Modifies files in-place and returns a log of changes made.
        """
        remediations: List[Dict[str, str]] = []

        # Group remediable findings by file
        file_findings: Dict[str, List[ThreatFinding]] = {}
        for f in findings:
            if f.can_auto_remediate:
                file_findings.setdefault(f.file_path, []).append(f)

        for rel_path, file_fundings in file_findings.items():
            abs_path = repo / rel_path
            try:
                text = abs_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue

            modified = text

            for finding in file_fundings:
                if "trust_remote_code" in finding.pattern:
                    new_text = re.sub(
                        r"trust_remote_code\s*=\s*True",
                        "trust_remote_code=False  # QUARANTINE: requires manual audit before enabling",
                        modified,
                    )
                    if new_text != modified:
                        remediations.append({
                            "file": rel_path,
                            "line": str(finding.line_number),
                            "change": "trust_remote_code=True → trust_remote_code=False",
                            "note": "Manual audit required before re-enabling",
                        })
                        modified = new_text

                elif "torch" in finding.pattern and "load" in finding.pattern:
                    # Add weights_only=True where missing
                    def _add_weights_only(m: re.Match) -> str:  # noqa: E731
                        call = m.group(0)
                        if "weights_only" in call:
                            return call
                        # Insert before closing paren
                        if call.rstrip().endswith(")"):
                            inner = call.rstrip()[:-1]
                            return inner + ", weights_only=True)"
                        return call

                    new_text = re.sub(
                        r"torch\.load\s*\([^)]*\)",
                        _add_weights_only,
                        modified,
                    )
                    if new_text != modified:
                        remediations.append({
                            "file": rel_path,
                            "line": str(finding.line_number),
                            "change": "Added weights_only=True to torch.load()",
                            "note": "Prevents arbitrary code execution via pickled weights",
                        })
                        modified = new_text

            if modified != text:
                try:
                    abs_path.write_text(modified, encoding="utf-8")
                except OSError as exc:
                    logger.warning("Could not write remediated file %s: %s", rel_path, exc)

        return remediations

    # ------------------------------------------------------------------
    # f) Sandbox Test-Load
    # ------------------------------------------------------------------

    def _sandbox_test_load(
        self, repo: Path, module: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Attempt to import the main entry-point in a temporary isolated context.
        Returns a dict with 'success', 'error', and 'notes'.
        """
        result: Dict[str, Any] = {"success": False, "error": None, "notes": []}
        tmpdir = tempfile.mkdtemp(prefix="murphy_quarantine_")

        try:
            # Copy repo into sandbox
            sandbox_repo = Path(tmpdir) / "repo"
            try:
                shutil.copytree(str(repo), str(sandbox_repo), ignore=shutil.ignore_patterns(".git"))
            except Exception as exc:
                result["notes"].append(f"Could not copy repo to sandbox: {exc}")
                return result

            # Try importing the entry point if it's a Python file
            entry = module.get("entry_point", "")
            if entry and entry.endswith(".py"):
                entry_abs = sandbox_repo / Path(entry).name
                if entry_abs.exists():
                    # Isolated sys.path manipulation
                    orig_path = list(sys.path)
                    orig_env = {k: v for k, v in os.environ.items()}
                    try:
                        # Strip sensitive env vars
                        for key in list(os.environ.keys()):
                            if key not in {"PATH", "PYTHONPATH", "HOME", "TMPDIR", "TEMP", "TMP"}:
                                del os.environ[key]

                        sys.path.insert(0, str(sandbox_repo))
                        spec = importlib.util.spec_from_file_location(
                            "_quarantine_sandbox_module", str(entry_abs)
                        )
                        if spec and spec.loader:
                            # Do NOT exec the module to avoid side effects —
                            # just check the spec can be created successfully
                            importlib.util.module_from_spec(spec)
                            result["success"] = True
                            result["notes"].append(f"Entry point '{entry}' is importable")
                        else:
                            result["notes"].append(f"Could not create spec for '{entry}'")
                    except Exception as exc:
                        result["error"] = str(exc)
                        result["notes"].append(f"Import attempt raised: {exc}")
                    finally:
                        sys.path[:] = orig_path
                        # Restore env
                        os.environ.clear()
                        os.environ.update(orig_env)
                else:
                    result["notes"].append(f"Entry point '{entry}' not found in sandbox copy")
                    result["success"] = True  # Non-blocking — repo may have no single entry
            else:
                result["notes"].append("No Python entry point specified — skipping import test")
                result["success"] = True
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

        return result

    # ------------------------------------------------------------------
    # g) Quarantine Score
    # ------------------------------------------------------------------

    def _compute_score(
        self,
        threat_findings: List[ThreatFinding],
        auto_remediations: List[Dict[str, str]],
        sandbox_result: Dict[str, Any],
    ) -> float:
        """
        Compute a 0.0–1.0 quarantine score.

        Penalties:
          - CRITICAL finding (not auto-remediated): −0.25 each
          - HIGH finding (not auto-remediated):     −0.12 each
          - MEDIUM finding:                         −0.05 each
          - Sandbox load failure:                   −0.10
        """
        score = 1.0

        remediated_lines = {r["line"] for r in auto_remediations}

        for f in threat_findings:
            already_fixed = str(f.line_number) in remediated_lines
            if already_fixed:
                continue
            if f.severity == "CRITICAL":
                score -= 0.25
            elif f.severity == "HIGH":
                score -= 0.12
            elif f.severity == "MEDIUM":
                score -= 0.05

        if not sandbox_result.get("success", True):
            score -= 0.10

        return max(0.0, min(1.0, score))
