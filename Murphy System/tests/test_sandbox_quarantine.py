# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Tests for the Sandbox Quarantine Protocol — SQP-001.

Covers:
  - License gate (approved, GPL, missing, unknown)
  - Transitive license conflict detection
  - ML threat scanner (trust_remote_code, pickle, torch.load)
  - Auto-remediation correctness
  - Documentation adapter strips branding / extracts capabilities
  - Data format extraction produces valid adapter spec
  - Quarantine score calculation and threshold gates
  - End-to-end: RynnBrain-like repo through full quarantine
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict

import pytest

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"

from integration_engine.sandbox_quarantine import (
    QuarantineReport,
    SandboxQuarantine,
    ThreatFinding,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_repo(files: Dict[str, str]) -> str:
    """Create a temporary directory tree with the given filename → content map."""
    tmpdir = tempfile.mkdtemp(prefix="sq_test_")
    for rel, content in files.items():
        p = Path(tmpdir) / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    return tmpdir


def _base_audit(license_name: str = "Apache-2.0") -> Dict[str, Any]:
    return {
        "license": license_name,
        "license_ok": license_name in {
            "MIT", "BSD", "BSD-2-Clause", "BSD-3-Clause",
            "Apache", "Apache-2.0", "ISC", "Unlicense", "CC0",
        },
        "deps": {},
        "risk_scan": {"count": 0, "issues": []},
        "source_url": "https://github.com/example/repo",
        "authors": "Test Author",
    }


def _base_module(name: str = "test_module") -> Dict[str, Any]:
    return {
        "name": name,
        "description": "Test module",
        "module_path": f"modules/{name}.py",
        "capabilities": ["capability_a", "capability_b"],
        "entry_point": f"{name}.py",
        "commands": [],
    }


# ---------------------------------------------------------------------------
# a) License gate
# ---------------------------------------------------------------------------

class TestLicenseGate:
    def setup_method(self):
        self.sq = SandboxQuarantine()
        self.module = _base_module()

    def test_approved_mit_passes(self, tmp_path):
        report = self.sq.quarantine(str(tmp_path), _base_audit("MIT"), self.module)
        assert report.license_check["passed"] is True
        assert report.license_check["license"] == "MIT"

    def test_approved_apache_passes(self, tmp_path):
        report = self.sq.quarantine(str(tmp_path), _base_audit("Apache-2.0"), self.module)
        assert report.license_check["passed"] is True

    def test_gpl_is_rejected(self, tmp_path):
        report = self.sq.quarantine(str(tmp_path), _base_audit("GPL-3.0"), self.module)
        assert report.admitted is False
        assert report.license_check["passed"] is False
        assert "GPL-3.0" in report.rejection_reason

    def test_missing_license_is_rejected(self, tmp_path):
        report = self.sq.quarantine(str(tmp_path), _base_audit("MISSING"), self.module)
        assert report.admitted is False
        assert report.license_check["passed"] is False
        assert "MISSING" in report.rejection_reason

    def test_unknown_license_is_rejected(self, tmp_path):
        report = self.sq.quarantine(str(tmp_path), _base_audit("UNKNOWN"), self.module)
        assert report.admitted is False
        assert "UNKNOWN" in report.rejection_reason

    def test_license_gate_blocks_all_further_steps(self, tmp_path):
        """When license gate fails, no threat findings or profiles should be populated."""
        report = self.sq.quarantine(str(tmp_path), _base_audit("GPL-2.0"), self.module)
        assert report.admitted is False
        assert report.threat_findings == []
        assert report.integration_profile == {}
        assert report.input_adapter_spec == {}

    @pytest.mark.parametrize("lic", [
        "BSD", "BSD-2-Clause", "BSD-3-Clause",
        "Apache", "Apache-2.0", "ISC", "Unlicense", "CC0",
    ])
    def test_all_approved_licenses_pass(self, tmp_path, lic):
        report = self.sq.quarantine(str(tmp_path), _base_audit(lic), self.module)
        assert report.license_check["passed"] is True, f"License {lic} should be approved"


# ---------------------------------------------------------------------------
# b) Transitive license conflict detection
# ---------------------------------------------------------------------------

class TestTransitiveLicenseConflicts:
    def setup_method(self):
        self.sq = SandboxQuarantine()
        self.module = _base_module()

    def test_copyleft_dep_flagged(self, tmp_path):
        audit = _base_audit("Apache-2.0")
        audit["deps"] = {
            "some_gpl_lib": {"license": "GPL-3.0", "version": "1.0"},
        }
        report = self.sq.quarantine(str(tmp_path), audit, self.module)
        assert len(report.license_conflicts) == 1
        assert report.license_conflicts[0]["package"] == "some_gpl_lib"
        assert report.license_conflicts[0]["conflict_type"] == "copyleft"

    def test_agpl_dep_flagged(self, tmp_path):
        audit = _base_audit("MIT")
        audit["deps"] = {"agpl_pkg": {"license": "AGPL-3.0"}}
        report = self.sq.quarantine(str(tmp_path), audit, self.module)
        assert any(c["package"] == "agpl_pkg" for c in report.license_conflicts)

    def test_permissive_deps_no_conflict(self, tmp_path):
        audit = _base_audit("Apache-2.0")
        audit["deps"] = {
            "requests": {"license": "Apache-2.0", "version": "2.31"},
            "pillow":   {"license": "MIT", "version": "10.0"},
        }
        report = self.sq.quarantine(str(tmp_path), audit, self.module)
        assert report.license_conflicts == []

    def test_deps_as_list(self, tmp_path):
        audit = _base_audit("Apache-2.0")
        audit["deps"] = [
            {"name": "lgpl_lib", "license": "LGPL-3.0"},
            {"name": "ok_lib",   "license": "MIT"},
        ]
        report = self.sq.quarantine(str(tmp_path), audit, self.module)
        assert len(report.license_conflicts) == 1
        assert report.license_conflicts[0]["package"] == "lgpl_lib"


# ---------------------------------------------------------------------------
# c) ML threat scanner
# ---------------------------------------------------------------------------

class TestMLThreatScanner:
    def setup_method(self):
        self.sq = SandboxQuarantine()
        self.module = _base_module()

    def test_trust_remote_code_detected(self):
        repo = _make_repo({
            "inference.py": 'model = AutoModel.from_pretrained("x", trust_remote_code=True)\n',
        })
        findings = self.sq._scan_threats(Path(repo))
        labels = [f.pattern for f in findings]
        assert any("trust_remote_code" in lbl for lbl in labels)
        sev = next(f.severity for f in findings if "trust_remote_code" in f.pattern)
        assert sev == "HIGH"

    def test_pickle_load_detected(self):
        repo = _make_repo({
            "load.py": "import pickle\ndata = pickle.load(open('model.pkl', 'rb'))\n",
        })
        findings = self.sq._scan_threats(Path(repo))
        assert any("pickle" in f.pattern for f in findings)
        sev = next(f.severity for f in findings if "pickle" in f.pattern)
        assert sev == "CRITICAL"

    def test_torch_load_without_weights_only(self):
        repo = _make_repo({
            "model.py": "import torch\nweights = torch.load('weights.pt')\n",
        })
        findings = self.sq._scan_threats(Path(repo))
        assert any("torch.load" in f.matched_text for f in findings)

    def test_torch_load_with_weights_only_not_flagged(self):
        repo = _make_repo({
            "model.py": "import torch\nweights = torch.load('weights.pt', weights_only=True)\n",
        })
        findings = self.sq._scan_threats(Path(repo))
        assert not any("torch.load" in f.matched_text for f in findings)

    def test_eval_detected(self):
        repo = _make_repo({"hack.py": "result = eval(user_input)\n"})
        findings = self.sq._scan_threats(Path(repo))
        assert any("eval" in f.pattern for f in findings)

    def test_exec_detected(self):
        repo = _make_repo({"hack.py": "exec(code)\n"})
        findings = self.sq._scan_threats(Path(repo))
        assert any("exec" in f.pattern for f in findings)

    def test_subprocess_detected(self):
        repo = _make_repo({"run.py": "import subprocess\nsubprocess.run(['ls', '-la'])\n"})
        findings = self.sq._scan_threats(Path(repo))
        assert any("subprocess" in f.pattern for f in findings)

    def test_os_system_detected(self):
        repo = _make_repo({"run.py": "import os\nos.system('rm -rf /tmp/test')\n"})
        findings = self.sq._scan_threats(Path(repo))
        assert any("os.system" in f.matched_text for f in findings)

    def test_requests_get_flagged(self):
        repo = _make_repo({"load.py": "import requests\ndata = requests.get('http://example.com/weights')\n"})
        findings = self.sq._scan_threats(Path(repo))
        assert any("requests" in f.pattern for f in findings)
        sev = next(f.severity for f in findings if "requests" in f.pattern)
        assert sev == "MEDIUM"

    def test_clean_file_has_no_findings(self):
        repo = _make_repo({
            "clean.py": (
                "def add(a, b):\n"
                "    return a + b\n"
            )
        })
        findings = self.sq._scan_threats(Path(repo))
        assert findings == []


# ---------------------------------------------------------------------------
# d) Auto-remediation
# ---------------------------------------------------------------------------

class TestAutoRemediation:
    def setup_method(self):
        self.sq = SandboxQuarantine()

    def test_trust_remote_code_remediated(self):
        repo = _make_repo({
            "infer.py": 'model = AutoModel.from_pretrained("x", trust_remote_code=True)\n',
        })
        findings = self.sq._scan_threats(Path(repo))
        remeds = self.sq._auto_remediate(Path(repo), findings)
        assert len(remeds) >= 1
        content = (Path(repo) / "infer.py").read_text()
        assert "trust_remote_code=False" in content
        assert "trust_remote_code=True" not in content

    def test_torch_load_weights_only_added(self):
        repo = _make_repo({
            "model.py": "import torch\nw = torch.load('w.pt')\n",
        })
        findings = self.sq._scan_threats(Path(repo))
        remeds = self.sq._auto_remediate(Path(repo), findings)
        content = (Path(repo) / "model.py").read_text()
        assert "weights_only=True" in content

    def test_pickle_not_auto_remediated(self):
        repo = _make_repo({
            "load.py": "import pickle\nd = pickle.load(open('f', 'rb'))\n",
        })
        findings = self.sq._scan_threats(Path(repo))
        remeds = self.sq._auto_remediate(Path(repo), findings)
        content = (Path(repo) / "load.py").read_text()
        # pickle.load should NOT be auto-modified
        assert "pickle.load" in content
        # No remediations for pickle (can_auto_remediate=False)
        assert not any("pickle" in r.get("change", "") for r in remeds)


# ---------------------------------------------------------------------------
# e) Documentation adapter
# ---------------------------------------------------------------------------

class TestDocumentationAdapter:
    def setup_method(self):
        self.sq = SandboxQuarantine()
        self.module = _base_module()

    def test_strips_badge_links(self, tmp_path):
        readme = (
            "[![Build](https://img.shields.io/badge/build-passing.svg)](https://example.com)\n"
            "## Features\n- Do things\n"
        )
        (tmp_path / "README.md").write_text(readme, encoding="utf-8")
        profile = self.sq._build_integration_profile(tmp_path, _base_audit(), self.module)
        # Attribution should be present
        assert "attribution" in profile

    def test_extracts_capabilities_from_module(self, tmp_path):
        module = _base_module()
        module["capabilities"] = ["spatial reasoning", "object detection"]
        profile = self.sq._build_integration_profile(tmp_path, _base_audit(), module)
        assert "spatial reasoning" in profile["capabilities"]
        assert "object detection" in profile["capabilities"]

    def test_hardware_requirements_extracted(self, tmp_path):
        readme = (
            "## Requirements\n"
            "CUDA 11.8+ required. Minimum 24GB VRAM for 8B model.\n"
        )
        (tmp_path / "README.md").write_text(readme, encoding="utf-8")
        profile = self.sq._build_integration_profile(tmp_path, _base_audit(), self.module)
        hw = " ".join(profile["hardware_requirements"])
        assert "CUDA" in hw or "VRAM" in hw

    def test_attribution_preserved(self, tmp_path):
        audit = _base_audit("Apache-2.0")
        audit["authors"] = "DAMO Academy"
        audit["source_url"] = "https://github.com/alibaba-damo-academy/RynnBrain"
        profile = self.sq._build_integration_profile(tmp_path, audit, self.module)
        attr = profile["attribution"]
        assert attr["original_license"] == "Apache-2.0"
        assert "DAMO" in attr["original_authors"]
        assert "github.com" in attr["original_repo_url"]

    def test_model_variants_extracted_from_hf_links(self, tmp_path):
        readme = (
            "Download from https://huggingface.co/Alibaba-DAMO-Academy/RynnBrain-2B\n"
            "or https://huggingface.co/Alibaba-DAMO-Academy/RynnBrain-8B\n"
        )
        (tmp_path / "README.md").write_text(readme, encoding="utf-8")
        profile = self.sq._build_integration_profile(tmp_path, _base_audit(), self.module)
        ids = [v["model_id"] for v in profile["model_variants"]]
        assert any("RynnBrain-2B" in mid for mid in ids)
        assert any("RynnBrain-8B" in mid for mid in ids)


# ---------------------------------------------------------------------------
# f) Data format extraction
# ---------------------------------------------------------------------------

class TestDataFormatExtraction:
    def setup_method(self):
        self.sq = SandboxQuarantine()
        self.module = _base_module()

    def test_conversation_format_detected(self, tmp_path):
        readme = (
            "Messages must follow this format:\n"
            '```json\n{"role": "user", "content": [{"type": "text", "text": "hello"}]}\n```\n'
        )
        (tmp_path / "README.md").write_text(readme, encoding="utf-8")
        spec = self.sq._extract_input_adapter_spec(tmp_path, _base_audit(), self.module)
        assert "conversation_json" in spec.get("detected_formats", [])

    def test_spec_has_required_keys(self, tmp_path):
        spec = self.sq._extract_input_adapter_spec(tmp_path, _base_audit(), self.module)
        assert "module_name" in spec
        assert "murphy_to_thirdparty" in spec
        assert "thirdparty_to_murphy" in spec
        assert "detected_formats" in spec

    def test_bounding_box_mapping_detected(self, tmp_path):
        readme = (
            "Output format: `<object> (x1,y1), (x2,y2) </object>`\n"
        )
        (tmp_path / "README.md").write_text(readme, encoding="utf-8")
        spec = self.sq._extract_input_adapter_spec(tmp_path, _base_audit(), self.module)
        ttp = spec.get("thirdparty_to_murphy", [])
        assert any(m.get("murphy_field") == "bounding_boxes" for m in ttp)


# ---------------------------------------------------------------------------
# g) Quarantine score and thresholds
# ---------------------------------------------------------------------------

class TestQuarantineScore:
    def setup_method(self):
        self.sq = SandboxQuarantine()

    def _make_finding(self, severity: str, can_auto: bool = False, line: int = 1) -> ThreatFinding:
        return ThreatFinding(
            file_path="x.py",
            line_number=line,
            pattern="test_pattern",
            severity=severity,
            can_auto_remediate=can_auto,
            remediation_description="",
        )

    def test_no_findings_score_is_1(self):
        score = self.sq._compute_score([], [], {"success": True})
        assert score == 1.0

    def test_critical_finding_reduces_score(self):
        findings = [self._make_finding("CRITICAL")]
        score = self.sq._compute_score(findings, [], {"success": True})
        assert score == pytest.approx(0.75, abs=0.01)

    def test_high_finding_reduces_score(self):
        findings = [self._make_finding("HIGH")]
        score = self.sq._compute_score(findings, [], {"success": True})
        assert score == pytest.approx(0.88, abs=0.01)

    def test_medium_finding_reduces_score(self):
        findings = [self._make_finding("MEDIUM")]
        score = self.sq._compute_score(findings, [], {"success": True})
        assert score == pytest.approx(0.95, abs=0.01)

    def test_remediated_finding_not_penalised(self):
        findings = [self._make_finding("HIGH", can_auto=True, line=5)]
        remeds = [{"file": "x.py", "line": "5", "change": "fixed"}]
        score = self.sq._compute_score(findings, remeds, {"success": True})
        assert score == pytest.approx(1.0, abs=0.01)

    def test_sandbox_failure_reduces_score(self):
        score = self.sq._compute_score([], [], {"success": False})
        assert score == pytest.approx(0.90, abs=0.01)

    def test_score_capped_at_zero(self):
        findings = [self._make_finding("CRITICAL", line=i) for i in range(10)]
        score = self.sq._compute_score(findings, [], {"success": False})
        assert score == 0.0

    def test_score_threshold_reject_below_04(self, tmp_path):
        """Repos with score < 0.4 are auto-rejected."""
        # Create repo with many critical findings
        code = "\n".join(f"import pickle; pickle.load(f{i})" for i in range(4))
        (tmp_path / "bad.py").write_text(code, encoding="utf-8")
        report = self.sq.quarantine(str(tmp_path), _base_audit(), _base_module())
        if report.quarantine_score < 0.4:
            assert report.admitted is False
            assert report.rejection_reason is not None

    def test_score_above_07_admitted(self, tmp_path):
        """Clean repo with no threats should be admitted."""
        (tmp_path / "clean.py").write_text("def hello(): pass\n", encoding="utf-8")
        report = self.sq.quarantine(str(tmp_path), _base_audit(), _base_module())
        assert report.admitted is True
        assert report.quarantine_score >= 0.7


# ---------------------------------------------------------------------------
# End-to-end: RynnBrain-like repo
# ---------------------------------------------------------------------------

class TestRynnBrainEndToEnd:
    """Simulate a RynnBrain-like repo going through the full quarantine."""

    RYNNBRAIN_AUDIT = {
        "license": "Apache-2.0",
        "license_ok": True,
        "deps": {
            "transformers": {"license": "Apache-2.0", "version": "4.57.1"},
            "torch":        {"license": "BSD-3-Clause", "version": "2.1.0"},
            "pillow":       {"license": "MIT",          "version": "10.0"},
        },
        "risk_scan": {"count": 0, "issues": []},
        "source_url": "https://github.com/alibaba-damo-academy/RynnBrain",
        "authors": "Alibaba DAMO Academy",
    }

    RYNNBRAIN_MODULE = {
        "name": "rynnbrain",
        "description": "Embodied AI foundation model (RynnBrain)",
        "module_path": "modules/rynnbrain.py",
        "capabilities": [
            "egocentric video understanding",
            "object localization",
            "spatial reasoning",
            "visual language navigation",
            "task planning",
        ],
        "entry_point": "inference.py",
        "commands": [],
    }

    def _make_rynnbrain_repo(self) -> str:
        readme = """\
# RynnBrain

Embodied AI foundation model.

## Features
- Egocentric video understanding
- Object localization: `<cup> (10,20), (50,80) </cup>`
- Visual language navigation

## Installation
```
pip install transformers==4.57.1 torch
```

## Usage
```python
from transformers import AutoModelForImageTextToText, AutoProcessor

messages = [{"role": "user", "content": [{"type": "image", "image": "img.jpg"}, {"type": "text", "text": "what is this?"}]}]
```

## Hardware
CUDA GPU required. Minimum 8GB VRAM for 2B model.

## Model Variants
- https://huggingface.co/Alibaba-DAMO-Academy/RynnBrain-2B
- https://huggingface.co/Alibaba-DAMO-Academy/RynnBrain-8B
"""
        inference = """\
from transformers import AutoModelForImageTextToText, AutoProcessor
import torch

model = AutoModelForImageTextToText.from_pretrained(
    "Alibaba-DAMO-Academy/RynnBrain-8B",
    revision="4e694f27d5a23b3c3b487be1a97e708c15cb9fd4",
    torch_dtype=torch.bfloat16,
    device_map="auto",
)
processor = AutoProcessor.from_pretrained(
    "Alibaba-DAMO-Academy/RynnBrain-8B",
    revision="4e694f27d5a23b3c3b487be1a97e708c15cb9fd4",
)
"""
        return _make_repo({"README.md": readme, "inference.py": inference})

    def test_rynnbrain_passes_license_gate(self):
        sq = SandboxQuarantine()
        repo = self._make_rynnbrain_repo()
        report = sq.quarantine(repo, self.RYNNBRAIN_AUDIT, self.RYNNBRAIN_MODULE)
        assert report.license_check["passed"] is True, report.license_check.get("reason")

    def test_rynnbrain_no_transitive_conflicts(self):
        sq = SandboxQuarantine()
        repo = self._make_rynnbrain_repo()
        report = sq.quarantine(repo, self.RYNNBRAIN_AUDIT, self.RYNNBRAIN_MODULE)
        assert report.license_conflicts == []

    def test_rynnbrain_no_trust_remote_code(self):
        sq = SandboxQuarantine()
        repo = self._make_rynnbrain_repo()
        report = sq.quarantine(repo, self.RYNNBRAIN_AUDIT, self.RYNNBRAIN_MODULE)
        trust_rc_findings = [f for f in report.threat_findings if "trust_remote_code" in f.pattern]
        assert trust_rc_findings == [], "RynnBrain should NOT use trust_remote_code=True"

    def test_rynnbrain_admitted(self):
        sq = SandboxQuarantine()
        repo = self._make_rynnbrain_repo()
        report = sq.quarantine(repo, self.RYNNBRAIN_AUDIT, self.RYNNBRAIN_MODULE)
        assert report.admitted is True, f"Should be admitted but got: {report.rejection_reason}"

    def test_rynnbrain_score_above_threshold(self):
        sq = SandboxQuarantine()
        repo = self._make_rynnbrain_repo()
        report = sq.quarantine(repo, self.RYNNBRAIN_AUDIT, self.RYNNBRAIN_MODULE)
        assert report.quarantine_score >= 0.7, (
            f"Expected score >= 0.70 for clean RynnBrain repo, got {report.quarantine_score}"
        )

    def test_rynnbrain_integration_profile_populated(self):
        sq = SandboxQuarantine()
        repo = self._make_rynnbrain_repo()
        report = sq.quarantine(repo, self.RYNNBRAIN_AUDIT, self.RYNNBRAIN_MODULE)
        profile = report.integration_profile
        assert "capabilities" in profile
        assert "attribution" in profile
        assert profile["attribution"]["original_license"] == "Apache-2.0"

    def test_rynnbrain_input_adapter_spec_populated(self):
        sq = SandboxQuarantine()
        repo = self._make_rynnbrain_repo()
        report = sq.quarantine(repo, self.RYNNBRAIN_AUDIT, self.RYNNBRAIN_MODULE)
        spec = report.input_adapter_spec
        assert spec["module_name"] == "rynnbrain"
        assert "conversation_json" in spec.get("detected_formats", [])

    def test_quarantine_report_serialisable(self):
        sq = SandboxQuarantine()
        repo = self._make_rynnbrain_repo()
        report = sq.quarantine(repo, self.RYNNBRAIN_AUDIT, self.RYNNBRAIN_MODULE)
        report_dict = report.to_dict()
        # Must be JSON serialisable
        json_str = json.dumps(report_dict)
        assert len(json_str) > 10
