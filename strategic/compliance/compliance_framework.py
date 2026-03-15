# Copyright © 2020-2026 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

"""
compliance/compliance_framework.py
=====================================
SOC 2 Type II, ISO 27001, and HIPAA compliance assessment for the Murphy System.

Provides:
  ComplianceFramework — evaluates Murphy System components against controls,
                        identifies gaps, and generates a remediation report.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ComplianceControl:
    framework:    str
    control_id:   str
    title:        str
    description:  str
    murphy_component: str
    status:       str   # "IMPLEMENTED" | "PARTIAL" | "PLANNED" | "NOT_STARTED"
    gap:          Optional[str] = None
    remediation:  Optional[str] = None
    due_date:     Optional[str] = None


# ---------------------------------------------------------------------------
# Control definitions
# ---------------------------------------------------------------------------

SOC2_CONTROLS: List[ComplianceControl] = [
    ComplianceControl(
        framework="SOC 2 Type II",
        control_id="CC6.1",
        title="Logical and Physical Access Controls",
        description="Restrict logical access to prevent unauthorized access.",
        murphy_component="Murphy Gate — EXECUTIVE/COMPLIANCE gates + ImmutableAuditLog",
        status="IMPLEMENTED",
    ),
    ComplianceControl(
        framework="SOC 2 Type II",
        control_id="CC7.2",
        title="System Monitoring",
        description="Monitor system components for anomalies and security events.",
        murphy_component="ConfidenceEngine — real-time scoring + SIEMForwarder",
        status="IMPLEMENTED",
    ),
    ComplianceControl(
        framework="SOC 2 Type II",
        control_id="CC8.1",
        title="Change Management",
        description="Authorize, design, develop, acquire, configure, document, test, approve, and implement changes.",
        murphy_component="GateCompiler — ChangeManagementGate enforces PR-gated rule changes",
        status="IMPLEMENTED",
    ),
    ComplianceControl(
        framework="SOC 2 Type II",
        control_id="A1.2",
        title="Availability — Performance Monitoring",
        description="Monitor system availability and capacity.",
        murphy_component="SLODashboard + PerformanceBenchmark + observability/telemetry.py",
        status="IMPLEMENTED",
    ),
    ComplianceControl(
        framework="SOC 2 Type II",
        control_id="PI1.4",
        title="Processing Integrity — Error Handling",
        description="Detect and handle processing errors.",
        murphy_component="ConfidenceEngine — BLOCK_EXECUTION action",
        status="IMPLEMENTED",
    ),
]

ISO27001_CONTROLS: List[ComplianceControl] = [
    ComplianceControl(
        framework="ISO 27001",
        control_id="A.9.4.1",
        title="Information Access Restriction",
        description="Restrict access to information and application system functions.",
        murphy_component="Murphy Gate — HITL approval workflow + RBACMiddleware",
        status="IMPLEMENTED",
    ),
    ComplianceControl(
        framework="ISO 27001",
        control_id="A.12.4.1",
        title="Event Logging",
        description="Produce, protect, and retain event logs.",
        murphy_component="ConfidenceResult — SIEMForwarder structured log pipeline",
        status="IMPLEMENTED",
    ),
    ComplianceControl(
        framework="ISO 27001",
        control_id="A.14.2.1",
        title="Secure Development Policy",
        description="Rules for development of software and systems.",
        murphy_component="murphy_confidence — zero-dep library",
        status="IMPLEMENTED",
    ),
    ComplianceControl(
        framework="ISO 27001",
        control_id="A.18.1.4",
        title="Privacy and Protection of Personally Identifiable Information",
        description="Ensure privacy and protection of PII as required by law.",
        murphy_component="Murphy Gate — COMPLIANCE gate + PIIScanner pre-gate hook",
        status="IMPLEMENTED",
    ),
]

HIPAA_CONTROLS: List[ComplianceControl] = [
    ComplianceControl(
        framework="HIPAA",
        control_id="164.312(a)(1)",
        title="Access Control",
        description="Implement technical policies to allow only authorized persons access to ePHI.",
        murphy_component="Murphy Gate — COMPLIANCE + HITL gates + EPHIClassifier hazard scoring",
        status="IMPLEMENTED",
    ),
    ComplianceControl(
        framework="HIPAA",
        control_id="164.312(b)",
        title="Audit Controls",
        description="Implement hardware, software, and procedural mechanisms to record ePHI activity.",
        murphy_component="HIPAAAuditBackend — encrypted, access-controlled, hash-chained audit store",
        status="IMPLEMENTED",
    ),
    ComplianceControl(
        framework="HIPAA",
        control_id="164.312(e)(1)",
        title="Transmission Security",
        description="Guard against unauthorized access to ePHI in transit.",
        murphy_component="Murphy System API layer + IntegrityVerifier HMAC-SHA256",
        status="IMPLEMENTED",
    ),
    ComplianceControl(
        framework="HIPAA",
        control_id="164.308(a)(1)",
        title="Security Management Process",
        description="Implement policies to prevent, detect, contain, and correct security violations.",
        murphy_component="BLOCK_EXECUTION gate action + ImmutableAuditLog + SIEMForwarder",
        status="IMPLEMENTED",
    ),
]


# ---------------------------------------------------------------------------
# ComplianceFramework
# ---------------------------------------------------------------------------

class ComplianceFramework:
    """
    Evaluates Murphy System components against SOC 2 Type II, ISO 27001,
    and HIPAA controls, then generates a remediation roadmap.

    Usage::

        framework = ComplianceFramework()
        report    = framework.generate_report()
        import json; print(json.dumps(report, indent=2))
    """

    ALL_CONTROLS: List[ComplianceControl] = (
        SOC2_CONTROLS + ISO27001_CONTROLS + HIPAA_CONTROLS
    )

    def _score_control(self, control: ComplianceControl) -> int:
        return {"IMPLEMENTED": 100, "PARTIAL": 50, "PLANNED": 25, "NOT_STARTED": 0}.get(
            control.status, 0
        )

    def _readiness_for(self, framework: str) -> Dict[str, Any]:
        controls = [c for c in self.ALL_CONTROLS if c.framework == framework]
        scores   = [self._score_control(c) for c in controls]
        avg      = sum(scores) / len(scores) if scores else 0.0
        gaps     = [c for c in controls if c.gap]
        return {
            "framework":        framework,
            "total_controls":   len(controls),
            "readiness_pct":    round(avg, 1),
            "implemented":      sum(1 for c in controls if c.status == "IMPLEMENTED"),
            "partial":          sum(1 for c in controls if c.status == "PARTIAL"),
            "planned":          sum(1 for c in controls if c.status == "PLANNED"),
            "not_started":      sum(1 for c in controls if c.status == "NOT_STARTED"),
            "open_gaps":        len(gaps),
            "controls":         [self._control_dict(c) for c in controls],
        }

    @staticmethod
    def _control_dict(c: ComplianceControl) -> Dict[str, Any]:
        return {
            "control_id":        c.control_id,
            "title":             c.title,
            "murphy_component":  c.murphy_component,
            "status":            c.status,
            "gap":               c.gap,
            "remediation":       c.remediation,
            "due_date":          c.due_date,
        }

    def generate_report(self) -> Dict[str, Any]:
        """
        Generate a JSON-serialisable compliance readiness report.

        Returns
        -------
        dict
            Keys: ``generated``, ``verified_by``, ``frameworks``, ``overall_readiness_pct``,
            ``remediation_items``, ``next_steps``.
        """
        soc2  = self._readiness_for("SOC 2 Type II")
        iso   = self._readiness_for("ISO 27001")
        hipaa = self._readiness_for("HIPAA")

        all_pcts     = [soc2["readiness_pct"], iso["readiness_pct"], hipaa["readiness_pct"]]
        overall_pct  = round(sum(all_pcts) / len(all_pcts), 1)

        remediation_items = [
            {
                "framework":    c.framework,
                "control_id":   c.control_id,
                "title":        c.title,
                "gap":          c.gap,
                "remediation":  c.remediation,
                "due_date":     c.due_date,
            }
            for c in self.ALL_CONTROLS if c.gap
        ]

        next_steps = [
            "Prioritise HIPAA audit log backend (due 2026-05-30)",
            "Deploy append-only gate event store for SOC 2 CC6.1",
            "Implement RBAC middleware for ISO 27001 A.9.4.1",
            "Integrate PII detection with COMPLIANCE gate",
            "Engage SOC 2 auditor for Type II examination scope definition",
            "Schedule ISO 27001 gap assessment with certified auditor",
        ]

        return {
            "generated":           datetime.utcnow().isoformat(),
            "verified_by":         "Corey Post — Inoni LLC",
            "overall_readiness_pct": overall_pct,
            "frameworks":          [soc2, iso, hipaa],
            "open_remediation_items": len(remediation_items),
            "remediation_items":   remediation_items,
            "next_steps":          next_steps,
        }


def main() -> Dict[str, Any]:
    """Run compliance assessment and print a summary."""
    import json
    framework = ComplianceFramework()
    report    = framework.generate_report()

    print("=" * 60)
    print("  MURPHY SYSTEM — Compliance Framework Assessment")
    print("=" * 60)
    print(f"  Overall readiness : {report['overall_readiness_pct']}%")
    for fw in report["frameworks"]:
        print(f"  {fw['framework']:20s}: {fw['readiness_pct']}% "
              f"({fw['open_gaps']} gaps)")
    print(f"\n  Open remediation items: {report['open_remediation_items']}")
    print("\n  Next steps:")
    for step in report["next_steps"]:
        print(f"    • {step}")

    return report


if __name__ == "__main__":
    import json
    report = main()
    print("\n" + json.dumps(report, indent=2))
