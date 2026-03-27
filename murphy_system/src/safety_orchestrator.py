"""
Safety Orchestrator for Murphy System Runtime

Wires together WingmanProtocol, TelemetryAdapter, and GoldenPathBridge to
provide continuous fire/life-safety validation across six safety domains.

Key capabilities:
- Continuous safety validation cycles using WingmanProtocol
- Auto-creates default pairs for each safety domain on instantiation
- Registers safety-specific runbooks automatically
- Per-domain status and violation history via dashboard
- Regulatory compliance mapping (OSHA, NFPA, IBC)
- Thread-safe operation

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from golden_path_bridge import GoldenPathBridge
from telemetry_adapter import TelemetryAdapter
from wingman_protocol import (
    ExecutionRunbook,
    ValidationRule,
    ValidationSeverity,
    WingmanProtocol,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Regulatory mappings
# ---------------------------------------------------------------------------

_OSHA_MAP: Dict[str, str] = {
    "fire_safety": "29 CFR 1910.157 — Portable Fire Extinguishers",
    "evacuation": "29 CFR 1910.38 — Emergency Action Plans",
    "structural": "29 CFR 1926 Subpart Q — Concrete and Masonry Construction",
    "hazmat": "29 CFR 1910.120 — Hazardous Waste Operations and Emergency Response",
    "electrical": "29 CFR 1910.303 — General Electrical Requirements",
    "fall_protection": "29 CFR 1926.502 — Fall Protection Systems Criteria",
}

_NFPA_MAP: Dict[str, str] = {
    "fire_safety": "NFPA 10 — Standard for Portable Fire Extinguishers",
    "evacuation": "NFPA 101 — Life Safety Code",
    "structural": "NFPA 5000 — Building Construction and Safety Code",
    "hazmat": "NFPA 430 — Code for the Storage of Liquid and Solid Oxidizers",
    "electrical": "NFPA 70 — National Electrical Code",
    "fall_protection": "NFPA 101 — Life Safety Code §7.2",
}

_REGULATORY_FRAMEWORKS: Dict[str, Dict[str, str]] = {
    "OSHA": _OSHA_MAP,
    "NFPA": _NFPA_MAP,
}


def _build_safety_runbook(domain: str) -> ExecutionRunbook:
    """Create a domain-specific safety validation runbook."""
    return ExecutionRunbook(
        runbook_id=f"safety_{domain}",
        name=f"Safety Runbook — {domain.replace('_', ' ').title()}",
        domain=domain,
        validation_rules=[
            ValidationRule(
                rule_id="check_has_output",
                description="Safety reading must contain a non-empty result",
                check_fn_name="check_has_output",
                severity=ValidationSeverity.BLOCK,
                applicable_domains=[domain],
            ),
            ValidationRule(
                rule_id="check_confidence_threshold",
                description="Safety sensor confidence must meet minimum threshold",
                check_fn_name="check_confidence_threshold",
                severity=ValidationSeverity.BLOCK,
                applicable_domains=[domain],
            ),
            ValidationRule(
                rule_id="check_gate_clearance",
                description="All safety gates must have passed",
                check_fn_name="check_gate_clearance",
                severity=ValidationSeverity.BLOCK,
                applicable_domains=[domain],
            ),
        ],
    )


class SafetyOrchestrator:
    """Runs continuous safety validation cycles using WingmanProtocol.

    Starts working immediately on instantiation — no manual setup.
    Wires WingmanProtocol + TelemetryAdapter + GoldenPathBridge.
    """

    SAFETY_DOMAINS = [
        "fire_safety",
        "evacuation",
        "structural",
        "hazmat",
        "electrical",
        "fall_protection",
    ]

    def __init__(
        self,
        wingman_protocol: Optional[WingmanProtocol] = None,
        telemetry: Optional[TelemetryAdapter] = None,
        golden_paths: Optional[GoldenPathBridge] = None,
    ) -> None:
        self._lock = threading.Lock()
        self.wingman = wingman_protocol or WingmanProtocol()
        self.telemetry = telemetry or TelemetryAdapter()
        self.golden_paths = golden_paths or GoldenPathBridge()

        # pair_id indexed by domain
        self._domain_pairs: Dict[str, str] = {}
        # violation history indexed by domain
        self._violation_history: Dict[str, List[Dict[str, Any]]] = {
            d: [] for d in self.SAFETY_DOMAINS
        }
        # last check result per domain
        self._last_results: Dict[str, Dict[str, Any]] = {}

        self._setup()

    def _setup(self) -> None:
        """Register runbooks and create default pairs for all safety domains."""
        for domain in self.SAFETY_DOMAINS:
            runbook = _build_safety_runbook(domain)
            self.wingman.register_runbook(runbook)
            pair = self.wingman.create_pair(
                subject=f"safety_{domain}",
                executor_id=f"safety_sensor_{domain}",
                validator_id=f"safety_validator_{domain}",
                runbook_id=runbook.runbook_id,
            )
            with self._lock:
                self._domain_pairs[domain] = pair.pair_id
        logger.info(
            "SafetyOrchestrator ready — %d domains initialised",
            len(self.SAFETY_DOMAINS),
        )

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def run_safety_check(self, domain: str, readings: Dict[str, Any]) -> Dict[str, Any]:
        """Validate *readings* through the wingman protocol for *domain*.

        Returns a dict with:
            approved       – True if all blocking rules passed
            violations     – list of blocking failure messages
            recommendation – human-readable action string
            severity       – "ok" | "warning" | "critical"
        """
        if domain not in self.SAFETY_DOMAINS:
            return {
                "approved": False,
                "violations": [f"Unknown domain: {domain}"],
                "recommendation": (
                    f"Register '{domain}' as a valid safety domain before running checks. "
                    f"Valid domains: {', '.join(self.SAFETY_DOMAINS)}."
                ),
                "severity": "critical",
            }

        with self._lock:
            pair_id = self._domain_pairs.get(domain)

        if pair_id is None:
            return {
                "approved": False,
                "violations": ["Domain pair not initialised"],
                "recommendation": "Re-initialise SafetyOrchestrator to rebuild domain pairs.",
                "severity": "critical",
            }

        # Ensure the output has a 'result' key for the has-output check
        output: Dict[str, Any] = {"result": readings, **readings}

        validation = self.wingman.validate_output(pair_id, output)
        approved: bool = validation.get("approved", False)
        blocking: List[Dict] = validation.get("blocking_failures", [])

        violations = [b.get("message", str(b)) for b in blocking]
        _WARNING_VIOLATION_LIMIT = 1
        severity = "ok" if approved else ("warning" if len(violations) <= _WARNING_VIOLATION_LIMIT else "critical")

        if approved:
            recommendation = (
                f"{domain.replace('_', ' ').title()} readings are within safe parameters. "
                "Continue normal operations and schedule next routine inspection."
            )
        else:
            viol_summary = "; ".join(violations[:3])
            recommendation = (
                f"Safety check failed for {domain.replace('_', ' ')} — {viol_summary}. "
                "Halt affected operations, notify safety officer, and remediate before resuming."
            )

        event: Dict[str, Any] = {
            "domain": domain,
            "approved": approved,
            "violations": violations,
            "recommendation": recommendation,
            "severity": severity,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

        with self._lock:
            self._last_results[domain] = event
            if violations:
                self._violation_history[domain].append(event)

        self.telemetry.collect_metric(
            metric_type="system_events",
            metric_name=f"safety_check_{domain}",
            value=1.0 if approved else 0.0,
            labels={"domain": domain, "approved": str(approved)},
        )

        if approved:
            self.golden_paths.record_success(
                task_pattern=f"safety_check_{domain}",
                domain="fire_life_safety",
                execution_spec={"readings": readings, "result": "approved"},
            )
        else:
            self.golden_paths.record_failure(
                task_pattern=f"safety_check_{domain}",
                domain="fire_life_safety",
            )

        return {
            "approved": approved,
            "violations": violations,
            "recommendation": recommendation,
            "severity": severity,
        }

    def get_safety_dashboard(self) -> Dict[str, Any]:
        """Return per-domain status, violation history, and overall safety score."""
        with self._lock:
            last_results = dict(self._last_results)
            violation_history = {d: list(v) for d, v in self._violation_history.items()}

        domain_statuses: Dict[str, Any] = {}
        for domain in self.SAFETY_DOMAINS:
            last = last_results.get(domain)
            total_checks = len(violation_history.get(domain, [])) + (
                1 if (last and last.get("approved")) else 0
            )
            domain_statuses[domain] = {
                "last_severity": last.get("severity", "unknown") if last else "unknown",
                "last_checked_at": last.get("checked_at") if last else None,
                "total_violations": len(violation_history.get(domain, [])),
            }

        approved_count = sum(
            1 for d in self.SAFETY_DOMAINS
            if last_results.get(d, {}).get("approved") is True
        )
        total_checked = sum(
            1 for d in self.SAFETY_DOMAINS if d in last_results
        )
        safety_score = round(
            (approved_count / (total_checked or 1)) * 100, 1
        )

        return {
            "domain_statuses": domain_statuses,
            "violation_history": violation_history,
            "overall_safety_score": safety_score,
            "domains_checked": total_checked,
            "domains_passing": approved_count,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_compliance_status(self, regulatory_framework: str = "OSHA") -> Dict[str, Any]:
        """Map safety checks to regulatory requirements for *regulatory_framework*.

        Returns compliance mapping per domain plus overall alignment status.
        """
        framework_map = _REGULATORY_FRAMEWORKS.get(regulatory_framework.upper(), _OSHA_MAP)

        with self._lock:
            last_results = dict(self._last_results)

        domain_compliance: Dict[str, Any] = {}
        for domain in self.SAFETY_DOMAINS:
            last = last_results.get(domain)
            regulation = framework_map.get(domain, f"{regulatory_framework} — {domain}")
            domain_compliance[domain] = {
                "regulation": regulation,
                "aligned": last.get("approved", False) if last else None,
                "last_checked_at": last.get("checked_at") if last else None,
                "recommendation": last.get("recommendation") if last else (
                    f"Run a safety check for '{domain}' to determine {regulatory_framework} alignment."
                ),
            }

        checked_domains = [d for d in self.SAFETY_DOMAINS if d in last_results]
        aligned_domains = [
            d for d in checked_domains
            if last_results.get(d, {}).get("approved") is True
        ]
        overall = (
            "aligned"
            if checked_domains and len(aligned_domains) == len(checked_domains)
            else ("partial" if aligned_domains else "not_aligned")
        )

        return {
            "regulatory_framework": regulatory_framework,
            "overall_alignment": overall,
            "domain_compliance": domain_compliance,
            "aligned_count": len(aligned_domains),
            "total_domains": len(self.SAFETY_DOMAINS),
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
        }
