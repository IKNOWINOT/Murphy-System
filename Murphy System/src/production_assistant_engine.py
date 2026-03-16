# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Production Assistant Engine for Murphy System.

Design Label: PROD-ENG-001 — Production Assistant Engine
Owner: Platform Engineering / Operations

Mirrors the onboarding assistant pattern (AgenticOnboardingEngine /
OnboardingOrchestrator) but is focused on production operations:
proposals, work orders, and service requests.

Lifecycle:
  request_intake → regulatory_validation → deliverable_matching →
  confidence_gating → approval → execution → monitoring

Key components:
  - DeliverableGateValidator — decomposes proposals/work orders into
    individual deliverable items, evaluates each through SafetyGate at
    the 0.99 production confidence threshold, and returns a detailed report.
  - ProductionAssistantOrchestrator — manages the full request lifecycle,
    emits events via EventBackbone, records successful paths via
    GoldenPathBridge, and wires production-specific SafetyGate instances.

Regulatory cross-referencing:
  - Location → REGULATORY_ZONES (from agentic_onboarding_engine) → frameworks
  - Industry → INDUSTRY_REQUIREMENTS → required compliance frameworks
  - Function → FUNCTION_REQUIREMENTS → required compliance frameworks
  All three dimensions must align with every deliverable. If a proposal says
  "automate patient data processing in the EU" but does not include GDPR and
  HIPAA compliance measures, it MUST fail the 99% gate.

Safety invariants:
  - Thread-safe: all shared state guarded by threading.Lock.
  - Non-destructive: request profiles transition forward only; no deletion.
  - Input validated before processing (CWE-20).
  - Collection hard caps prevent memory exhaustion (CWE-400).
  - Error messages sanitised before logging (CWE-209).
  - Raw PII never written to log records.

Zero external dependencies outside the Murphy System package.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import re
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Local imports (all within Murphy System package)
# ---------------------------------------------------------------------------
# REGULATORY_ZONES maps country codes to compliance frameworks
from agentic_onboarding_engine import REGULATORY_ZONES  # type: ignore[import]

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Production confidence threshold                              [PROD-ENG-001]
# ---------------------------------------------------------------------------

PRODUCTION_CONFIDENCE_THRESHOLD: float = 0.99

# ---------------------------------------------------------------------------
# Regulatory knowledge maps
# ---------------------------------------------------------------------------

#: Industry → set of required compliance framework names (canonical).
#: Matching is case-insensitive and also accepts common abbreviations / aliases.
INDUSTRY_REQUIREMENTS: Dict[str, List[str]] = {
    "healthcare":          ["HIPAA", "HITECH"],
    "medical":             ["HIPAA", "HITECH"],
    "finance":             ["SOX", "PCI_DSS"],
    "financial_services":  ["SOX", "PCI_DSS", "GLBA"],
    "banking":             ["SOX", "PCI_DSS", "GLBA"],
    "education":           ["FERPA", "COPPA"],
    "retail":              ["PCI_DSS"],
    "ecommerce":           ["PCI_DSS", "CCPA"],
    "manufacturing":       ["ISO_27001"],
    "construction":        ["OSHA", "ADA"],
    "logistics":           ["DOT", "ISO_27001"],
    "real_estate":         ["RESPA", "FCRA"],
    "legal":               ["ABA", "HIPAA"],
    "nonprofit":           ["IRS_990"],
    "agriculture":         ["USDA", "EPA"],
    "energy":              ["NERC_CIP", "ISO_27001"],
    "telecommunications":  ["FCC", "CPNI"],
    "government":          ["FISMA", "FedRAMP"],
    "default":             ["ISO_27001"],
}

#: Regulatory function → set of required compliance framework names.
#: A "function" describes what the automation *does* (not the industry).
FUNCTION_REQUIREMENTS: Dict[str, List[str]] = {
    "data_processing":          ["GDPR", "CCPA"],
    "patient_data":             ["HIPAA", "HITECH"],
    "financial_transactions":   ["PCI_DSS", "SOX"],
    "payment_processing":       ["PCI_DSS"],
    "credit_reporting":         ["FCRA"],
    "email_marketing":          ["CAN_SPAM", "CASL"],
    "sms_marketing":            ["TCPA", "CASL"],
    "children_data":            ["COPPA", "FERPA"],
    "employee_data":            ["HIPAA", "ADA"],
    "cross_border_data":        ["GDPR", "PIPEDA"],
    "cloud_hosting":            ["ISO_27001", "SOC2"],
    "access_control":           ["ISO_27001", "RBAC"],
    "audit_logging":            ["SOC2", "ISO_27001"],
    "permitting":               ["ADA"],
    "safety_inspection":        ["OSHA"],
    "zoning_compliance":        ["ADA"],
    "tax_processing":           ["SOX", "IRS"],
    "hr_automation":            ["ADA", "HIPAA"],
    "contract_management":      ["ESIGN", "UCC"],
    "telemedicine":             ["HIPAA", "HITECH"],
    "research_data":            ["IRB", "HIPAA"],
}

# ---------------------------------------------------------------------------
# Framework alias map — alternative names/abbreviations that map to canonical
# framework names recognised in REGULATORY_ZONES / INDUSTRY_REQUIREMENTS.
# ---------------------------------------------------------------------------

_FRAMEWORK_ALIASES: Dict[str, str] = {
    "gdpr_uk":  "GDPR_UK",
    "dsgvo":    "GDPR",
    "lgpd":     "GDPR",
    "pipeda":   "PIPEDA",
    "appi":     "APPI",
    "it_act":   "IT_Act",
    "dpdp":     "DPDP",
    "difc_dp":  "DIFC_DP",
    "adgm":     "ADGM",
    "can_spam": "CAN_SPAM",
    "pci_dss":  "PCI_DSS",
    "pci":      "PCI_DSS",
    "soc_2":    "SOC2",
    "soc2":     "SOC2",
    "hipaa":    "HIPAA",
    "hitech":   "HITECH",
    "ferpa":    "FERPA",
    "coppa":    "COPPA",
    "ccpa":     "CCPA",
    "casl":     "CASL",
    "glba":     "GLBA",
    "sox":      "SOX",
    "ada":      "ADA",
    "osha":     "OSHA",
    "fisma":    "FISMA",
    "fedramp":  "FedRAMP",
    "nerc_cip": "NERC_CIP",
    "iso_27001": "ISO_27001",
    "iso27001": "ISO_27001",
}

# ---------------------------------------------------------------------------
# Input-validation constants                                        [CWE-20]
# ---------------------------------------------------------------------------

_MAX_SPEC_LEN = 50_000
_MAX_ITEM_LEN = 2_000
_MAX_ITEMS = 200
_MAX_PROFILES = 10_000
_MAX_NOTES_LEN = 2_000
_MAX_AUDIT_LOG = 50_000

# ---------------------------------------------------------------------------
# Lifecycle enumerations
# ---------------------------------------------------------------------------


class RequestLifecycle(str, Enum):
    """Lifecycle states for a production request."""
    REQUEST_INTAKE        = "request_intake"
    REGULATORY_VALIDATION = "regulatory_validation"
    DELIVERABLE_MATCHING  = "deliverable_matching"
    CONFIDENCE_GATING     = "confidence_gating"
    APPROVAL              = "approval"
    EXECUTION             = "execution"
    MONITORING            = "monitoring"
    BLOCKED               = "blocked"
    COMPLETED             = "completed"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class DeliverableItem:
    """
    A single element extracted from a proposal/work-order deliverable spec.

    Each item is independently evaluated through the confidence gate at the
    PRODUCTION_CONFIDENCE_THRESHOLD (0.99).
    """
    item_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    description: str = ""
    #: Required framework that this item must satisfy.
    required_framework: str = ""
    #: Source dimension: "location", "industry", or "function".
    source_dimension: str = ""
    #: Whether the deliverable spec text mentions/satisfies this requirement.
    satisfied_in_spec: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_id":           self.item_id,
            "description":       self.description,
            "required_framework": self.required_framework,
            "source_dimension":  self.source_dimension,
            "satisfied_in_spec": self.satisfied_in_spec,
        }


@dataclass
class DeliverableGateReport:
    """
    Gate evaluation result for a single :class:`DeliverableItem`.

    Produced by :class:`DeliverableGateValidator` for every item that is
    evaluated.  All items must pass (passed=True) for the overall validation
    to succeed.
    """
    item_id: str = ""
    required_framework: str = ""
    source_dimension: str = ""
    confidence_score: float = 0.0
    passed: bool = False
    gate_action: str = ""
    gate_message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_id":           self.item_id,
            "required_framework": self.required_framework,
            "source_dimension":  self.source_dimension,
            "confidence_score":  self.confidence_score,
            "passed":            self.passed,
            "gate_action":       self.gate_action,
            "gate_message":      self.gate_message,
        }


@dataclass
class GateValidationReport:
    """
    Aggregate result of validating all deliverable items in a proposal/
    work-order through the 99%-confidence safety gate.

    ``passed`` is True only when *every* individual :class:`DeliverableGateReport`
    has ``passed=True``.  Any single failure forces the overall result to False
    and triggers ``GateAction.BLOCK_EXECUTION``.
    """
    proposal_id: str = ""
    work_order_id: str = ""
    #: Per-item gate reports (one per required framework item).
    item_reports: List[DeliverableGateReport] = field(default_factory=list)
    #: True only if ALL items passed.
    passed: bool = False
    #: Minimum confidence score across all items.
    min_confidence: float = 0.0
    #: Items that failed (description of missing requirements).
    failed_items: List[str] = field(default_factory=list)
    #: Items that passed.
    passed_items: List[str] = field(default_factory=list)
    #: Human-readable summary.
    summary: str = ""
    evaluated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "proposal_id":    self.proposal_id,
            "work_order_id":  self.work_order_id,
            "item_reports":   [r.to_dict() for r in self.item_reports],
            "passed":         self.passed,
            "min_confidence": self.min_confidence,
            "failed_items":   list(self.failed_items),
            "passed_items":   list(self.passed_items),
            "summary":        self.summary,
            "evaluated_at":   self.evaluated_at,
        }


@dataclass
class ProductionRequestProfile:
    """
    Full lifecycle state for a single production request.

    Mirrors the :class:`OnboardingProfile` pattern from
    ``agentic_onboarding_engine`` but tracks the production-operations
    lifecycle instead of the onboarding lifecycle.
    """
    profile_id: str = field(default_factory=lambda: f"prod-{uuid.uuid4().hex[:12]}")
    #: Source proposal or work-order identifier.
    source_id: str = ""
    #: Short title or description.
    title: str = ""
    #: Country / regulatory zone.
    country: str = ""
    regulatory_zone: str = ""
    #: Industry of the client.
    industry: str = ""
    #: Automation functions being performed.
    functions: List[str] = field(default_factory=list)
    #: Required compliance frameworks resolved from location + industry + functions.
    required_frameworks: List[str] = field(default_factory=list)
    lifecycle: RequestLifecycle = RequestLifecycle.REQUEST_INTAKE
    gate_validation_report: Optional[GateValidationReport] = None
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    history: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "profile_id":      self.profile_id,
            "source_id":       self.source_id,
            "title":           self.title,
            "country":         self.country,
            "regulatory_zone": self.regulatory_zone,
            "industry":        self.industry,
            "functions":       list(self.functions),
            "required_frameworks": list(self.required_frameworks),
            "lifecycle":       self.lifecycle.value,
            "gate_validation_report": (
                self.gate_validation_report.to_dict()
                if self.gate_validation_report else None
            ),
            "created_at":      self.created_at,
            "updated_at":      self.updated_at,
            "history":         list(self.history),
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sanitize_error(exc: Exception) -> str:  # [CWE-209]
    """Return an opaque error token; never leak raw exception text."""
    return f"ERR-{type(exc).__name__}-{id(exc) & 0xFFFF:04X}"


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalise_framework(name: str) -> str:
    """Return the canonical framework name, resolving aliases."""
    key = name.lower().replace("-", "_").replace(" ", "_")
    return _FRAMEWORK_ALIASES.get(key, name.upper())


def _spec_mentions_framework(spec: str, framework: str) -> bool:
    """
    Return True when *spec* (the deliverable text) mentions *framework* or
    any of its known aliases.

    Matching is case-insensitive and uses word-boundary patterns so that
    e.g. "HIPAA" does not match inside "Compliance" accidentally.
    """
    if not spec:
        return False

    canonical = framework.upper()
    spec_upper = spec.upper()

    # Build search terms: canonical + all aliases that map to this framework
    terms = {canonical}
    for alias, target in _FRAMEWORK_ALIASES.items():
        if target.upper() == canonical:
            terms.add(alias.upper().replace("_", "-"))
            terms.add(alias.upper().replace("_", " "))
            terms.add(alias.upper())

    for term in terms:
        # Use word-boundary search for short/ambiguous terms; plain substring
        # for longer terms (≥ 5 chars) to avoid regex complexity
        if len(term) >= 5:
            if term in spec_upper:
                return True
        else:
            pattern = r"(?<![A-Z0-9])" + re.escape(term) + r"(?![A-Z0-9])"
            if re.search(pattern, spec_upper):
                return True

    return False


def _resolve_location_frameworks(location: str) -> Tuple[str, List[str]]:
    """
    Resolve a regulatory location string to (country_code, [frameworks]).

    The location string may be in forms like "US/California", "EU/Germany",
    or plain country codes such as "DE", "CA".  We extract the country or
    zone prefix and look it up in REGULATORY_ZONES.
    """
    # Extract the leading ISO country/zone code (up to the first "/" or space)
    match = re.match(r"^([A-Za-z]{2,4})", location.strip())
    if not match:
        return "unknown", REGULATORY_ZONES.get("default", {}).get("frameworks", [])

    candidate = match.group(1).upper()

    # Direct country-code lookup
    if candidate in REGULATORY_ZONES:
        entry = REGULATORY_ZONES[candidate]
        return candidate, list(entry.get("frameworks", []))

    # Zone-prefix lookup: check if any country maps to a zone matching candidate
    for code, entry in REGULATORY_ZONES.items():
        if entry.get("zone", "").upper().startswith(candidate):
            return candidate, list(entry.get("frameworks", []))

    # Handle common pseudo-codes
    _PSEUDO: Dict[str, str] = {
        "EU": "DE",  # EU → Germany as the primary GDPR reference
        "UK": "GB",
    }
    if candidate in _PSEUDO:
        real = _PSEUDO[candidate]
        entry = REGULATORY_ZONES.get(real, REGULATORY_ZONES["default"])
        return real, list(entry.get("frameworks", []))

    return "unknown", REGULATORY_ZONES.get("default", {}).get("frameworks", [])


def _resolve_industry_frameworks(industry: str) -> List[str]:
    """Return required compliance frameworks for the given industry."""
    key = industry.lower().replace(" ", "_").replace("-", "_")
    return list(INDUSTRY_REQUIREMENTS.get(key, INDUSTRY_REQUIREMENTS["default"]))


def _resolve_function_frameworks(function: str) -> List[str]:
    """Return required compliance frameworks for the given automation function."""
    key = function.lower().replace(" ", "_").replace("-", "_")
    return list(FUNCTION_REQUIREMENTS.get(key, []))


# ---------------------------------------------------------------------------
# DeliverableGateValidator
# ---------------------------------------------------------------------------


class DeliverableGateValidator:
    """
    Validates every deliverable item in a proposal or work order against
    the production confidence gate (0.99 threshold, blocking=True).

    For each required compliance framework (derived from location, industry,
    and automation functions), a :class:`DeliverableItem` is created and its
    presence in the deliverable specification text is checked.  Each item is
    then evaluated through a production :class:`SafetyGate`.  **All** items
    must individually reach ≥ 0.99 confidence for the overall validation to
    pass.

    Usage::

        validator = DeliverableGateValidator()
        report = validator.validate(
            proposal_id="prop-abc",
            regulatory_location="US/California",
            regulatory_industry="healthcare",
            regulatory_functions=["patient_data", "telemedicine"],
            deliverable_spec="...must include HIPAA, HITECH compliance...",
        )
        if not report.passed:
            # Hard block — at least one framework requirement is missing
            raise RuntimeError("Deliverable does not meet regulatory requirements")
    """

    def validate(
        self,
        proposal_id: str,
        regulatory_location: str,
        regulatory_industry: str,
        regulatory_functions: List[str],
        deliverable_spec: str,
        work_order_id: str = "",
    ) -> GateValidationReport:
        """
        Validate the deliverable specification against all regulatory
        requirements derived from location, industry, and functions.

        Parameters
        ----------
        proposal_id:
            Identifier of the proposal being validated.
        regulatory_location:
            Client location (e.g. ``"US/California"``, ``"EU/Germany"``).
        regulatory_industry:
            Client industry (e.g. ``"healthcare"``, ``"finance"``).
        regulatory_functions:
            Automation functions the deliverable performs (e.g. ``["patient_data"]``).
        deliverable_spec:
            Free-text description of the deliverable.  Must mention every
            required framework to pass.
        work_order_id:
            Optional work-order identifier for correlation.

        Returns
        -------
        GateValidationReport
            Aggregate result.  ``report.passed`` is True only when every
            individual item passes the 0.99 confidence gate.
        """
        # 1. Resolve regulatory requirements along three dimensions
        items = self._build_deliverable_items(
            regulatory_location=regulatory_location,
            regulatory_industry=regulatory_industry,
            regulatory_functions=regulatory_functions,
            deliverable_spec=deliverable_spec,
        )

        # 2. Gate each item
        item_reports: List[DeliverableGateReport] = []
        for item in items:
            report = self._gate_item(item)
            item_reports.append(report)

        # 3. Aggregate
        passed_items = [r.required_framework for r in item_reports if r.passed]
        failed_items = [r.required_framework for r in item_reports if not r.passed]
        all_passed = len(failed_items) == 0 and len(items) > 0

        # Min confidence across all evaluated items (0 if no items)
        if item_reports:
            min_confidence = min(r.confidence_score for r in item_reports)
        else:
            min_confidence = 0.0

        if all_passed:
            summary = (
                f"All {len(items)} regulatory requirements satisfied in deliverable spec."
            )
        else:
            summary = (
                f"BLOCKED: {len(failed_items)} of {len(items)} regulatory requirements "
                f"missing from deliverable spec: {', '.join(failed_items)}"
            )

        return GateValidationReport(
            proposal_id=proposal_id,
            work_order_id=work_order_id,
            item_reports=item_reports,
            passed=all_passed,
            min_confidence=min_confidence,
            failed_items=failed_items,
            passed_items=passed_items,
            summary=summary,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_deliverable_items(
        regulatory_location: str,
        regulatory_industry: str,
        regulatory_functions: List[str],
        deliverable_spec: str,
    ) -> List[DeliverableItem]:
        """
        Resolve all required frameworks along location, industry, and function
        dimensions and create a :class:`DeliverableItem` for each unique
        framework that must be present in the deliverable spec.
        """
        required: Dict[str, str] = {}  # framework → source_dimension

        # Location-based frameworks
        _, loc_frameworks = _resolve_location_frameworks(regulatory_location)
        for fw in loc_frameworks:
            canon = _normalise_framework(fw)
            if canon not in required:
                required[canon] = "location"

        # Industry-based frameworks
        ind_frameworks = _resolve_industry_frameworks(regulatory_industry)
        for fw in ind_frameworks:
            canon = _normalise_framework(fw)
            if canon not in required:
                required[canon] = "industry"

        # Function-based frameworks
        for func in regulatory_functions:
            func_frameworks = _resolve_function_frameworks(func)
            for fw in func_frameworks:
                canon = _normalise_framework(fw)
                if canon not in required:
                    required[canon] = f"function:{func}"

        # Build items
        items: List[DeliverableItem] = []
        for canon, source_dim in required.items():
            satisfied = _spec_mentions_framework(deliverable_spec, canon)
            items.append(
                DeliverableItem(
                    description=f"Deliverable must address {canon} requirement",
                    required_framework=canon,
                    source_dimension=source_dim,
                    satisfied_in_spec=satisfied,
                )
            )

        return items

    @staticmethod
    def _gate_item(item: DeliverableItem) -> DeliverableGateReport:
        """
        Evaluate a single :class:`DeliverableItem` through a production
        :class:`SafetyGate` with threshold=0.99 and blocking=True.

        The confidence score is deterministically derived from whether the
        item is satisfied in the spec:
          - Satisfied → 1.0 (always passes the 0.99 gate)
          - Not satisfied → 0.0 (always blocked)
        """
        confidence_score = 1.0 if item.satisfied_in_spec else 0.0

        try:
            from strategic.murphy_confidence.gates import SafetyGate  # type: ignore[import]
            from strategic.murphy_confidence.types import (  # type: ignore[import]
                ConfidenceResult as ConfRes,
            )
            from strategic.murphy_confidence.types import (
                GateAction,
                GateType,
                Phase,
            )

            conf_result = ConfRes(
                score=confidence_score,
                phase=Phase.EXECUTE,
                action=(
                    GateAction.PROCEED_AUTOMATICALLY
                    if confidence_score >= PRODUCTION_CONFIDENCE_THRESHOLD
                    else GateAction.BLOCK_EXECUTION
                ),
                allowed=confidence_score >= PRODUCTION_CONFIDENCE_THRESHOLD,
                rationale=(
                    f"production_assistant_engine.DeliverableGateValidator:"
                    f"{item.required_framework}"
                ),
                weights={},
            )

            gate = SafetyGate(
                gate_id=f"prod_{item.required_framework.lower()}",
                gate_type=GateType.COMPLIANCE,
                threshold=PRODUCTION_CONFIDENCE_THRESHOLD,
                blocking=True,
            )
            gate_result = gate.evaluate(conf_result)

            return DeliverableGateReport(
                item_id=item.item_id,
                required_framework=item.required_framework,
                source_dimension=item.source_dimension,
                confidence_score=confidence_score,
                passed=gate_result.passed,
                gate_action=gate_result.action.value,
                gate_message=gate_result.message,
            )

        except ImportError:
            # SafetyGate not available — fall back to direct threshold check
            passed = confidence_score >= PRODUCTION_CONFIDENCE_THRESHOLD
            return DeliverableGateReport(
                item_id=item.item_id,
                required_framework=item.required_framework,
                source_dimension=item.source_dimension,
                confidence_score=confidence_score,
                passed=passed,
                gate_action=(
                    "PROCEED_AUTOMATICALLY" if passed else "BLOCK_EXECUTION"
                ),
                gate_message=(
                    f"Gate 'prod_{item.required_framework.lower()}' (COMPLIANCE) "
                    + ("PASSED" if passed else "FAILED [BLOCKING]")
                    + f" — confidence {confidence_score:.4f}"
                ),
            )


# ---------------------------------------------------------------------------
# ProductionAssistantOrchestrator
# ---------------------------------------------------------------------------


class ProductionAssistantOrchestrator:
    """
    Manages the full production-request lifecycle from intake through monitoring.

    Lifecycle:
      request_intake → regulatory_validation → deliverable_matching →
      confidence_gating → approval → execution → monitoring

    Wires together:
      - :class:`DeliverableGateValidator` — per-item 99% confidence gating
      - :class:`EventBackbone` — gate-pass / gate-fail events
      - :class:`GoldenPathBridge` — successful path recording for replay

    All shared state is guarded by a :class:`threading.Lock`.
    """

    def __init__(
        self,
        validator: Optional[DeliverableGateValidator] = None,
        event_backbone: Any = None,
        golden_path: Any = None,
    ) -> None:
        self._validator: DeliverableGateValidator = (
            validator or DeliverableGateValidator()
        )
        self._backbone = event_backbone
        self._golden_path = golden_path

        self._profiles: Dict[str, ProductionRequestProfile] = {}
        self._audit_log: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def intake_request(
        self,
        title: str,
        country: str,
        industry: str,
        functions: List[str],
        source_id: str = "",
    ) -> ProductionRequestProfile:
        """
        Create a new :class:`ProductionRequestProfile` in the
        REQUEST_INTAKE state and return it.

        Parameters
        ----------
        title:
            Short human-readable description of the request.
        country:
            ISO-3166 country code (e.g. ``"US"``, ``"DE"``) or location
            string (e.g. ``"US/California"``).
        industry:
            Industry of the client (e.g. ``"healthcare"``, ``"construction"``).
        functions:
            List of automation functions (e.g. ``["patient_data", "billing"]``).
        source_id:
            Optional external identifier (proposal_id, work-order number, …).
        """
        if len(self._profiles) >= _MAX_PROFILES:
            raise RuntimeError("Production request registry is at capacity")

        _, loc_frameworks = _resolve_location_frameworks(country)
        ind_frameworks = _resolve_industry_frameworks(industry)
        func_frameworks: List[str] = []
        for fn in functions:
            func_frameworks.extend(_resolve_function_frameworks(fn))

        # Deduplicate while preserving order
        seen: set = set()
        required: List[str] = []
        for fw in loc_frameworks + ind_frameworks + func_frameworks:
            canon = _normalise_framework(fw)
            if canon not in seen:
                seen.add(canon)
                required.append(canon)

        # Derive zone from REGULATORY_ZONES
        code, _ = _resolve_location_frameworks(country)
        zone_entry = REGULATORY_ZONES.get(code, REGULATORY_ZONES.get("default", {}))
        reg_zone = zone_entry.get("zone", "international") if isinstance(zone_entry, dict) else "international"

        profile = ProductionRequestProfile(
            source_id=source_id,
            title=title,
            country=code,
            regulatory_zone=reg_zone,
            industry=industry,
            functions=list(functions),
            required_frameworks=required,
            lifecycle=RequestLifecycle.REQUEST_INTAKE,
        )

        with self._lock:
            self._profiles[profile.profile_id] = profile
            self._record_audit("intake_request", {"profile_id": profile.profile_id})

        self._emit_event("production_request_intake", {
            "profile_id": profile.profile_id,
            "country": code,
            "industry": industry,
        })

        logger.info(
            "Production request intake: id=%s title=%r", profile.profile_id, title
        )
        return profile

    def validate_and_gate(
        self,
        profile_id: str,
        deliverable_spec: str,
    ) -> GateValidationReport:
        """
        Run the full deliverable-gate validation pipeline on an existing profile.

        Advances the profile lifecycle from REQUEST_INTAKE through
        REGULATORY_VALIDATION → DELIVERABLE_MATCHING → CONFIDENCE_GATING →
        APPROVAL (on pass) or BLOCKED (on fail).

        Returns a :class:`GateValidationReport` describing per-item results.
        """
        if len(deliverable_spec) > _MAX_SPEC_LEN:
            raise ValueError(
                f"deliverable_spec exceeds maximum length of {_MAX_SPEC_LEN} characters"
            )

        with self._lock:
            profile = self._profiles.get(profile_id)
        if profile is None:
            raise KeyError(f"Profile not found: {profile_id!r}")

        # Advance through regulatory_validation → deliverable_matching → confidence_gating
        self._advance(profile, RequestLifecycle.REGULATORY_VALIDATION)
        self._advance(profile, RequestLifecycle.DELIVERABLE_MATCHING)
        self._advance(profile, RequestLifecycle.CONFIDENCE_GATING)

        report = self._validator.validate(
            proposal_id=profile.source_id or profile.profile_id,
            regulatory_location=profile.country,
            regulatory_industry=profile.industry,
            regulatory_functions=profile.functions,
            deliverable_spec=deliverable_spec,
        )

        with self._lock:
            profile.gate_validation_report = report
            profile.updated_at = _ts()
            new_lifecycle = (
                RequestLifecycle.APPROVAL if report.passed else RequestLifecycle.BLOCKED
            )
            profile.lifecycle = new_lifecycle
            profile.history.append({
                "transition": new_lifecycle.value,
                "at": profile.updated_at,
                "passed": report.passed,
            })
            self._record_audit(
                "validate_and_gate",
                {
                    "profile_id": profile_id,
                    "passed": report.passed,
                    "failed_items": report.failed_items,
                },
            )

        # Emit gate-pass or gate-fail event
        if report.passed:
            self._emit_event("production_gate_pass", {
                "profile_id": profile_id,
                "passed_items": report.passed_items,
            })
            # Record this successful path for future replay
            self._record_golden_path(profile, report)
        else:
            self._emit_event("production_gate_fail", {
                "profile_id": profile_id,
                "failed_items": report.failed_items,
                "summary": report.summary,
            })

        logger.info(
            "validate_and_gate: profile=%s passed=%s min_confidence=%.4f",
            profile_id,
            report.passed,
            report.min_confidence,
        )
        return report

    def advance_to_execution(self, profile_id: str) -> bool:
        """
        Advance an APPROVAL-state profile to EXECUTION.

        Returns True on success, False if the profile is not in APPROVAL state.
        """
        with self._lock:
            profile = self._profiles.get(profile_id)
        if profile is None:
            return False
        if profile.lifecycle != RequestLifecycle.APPROVAL:
            return False
        self._advance(profile, RequestLifecycle.EXECUTION)
        self._emit_event("production_execution_started", {"profile_id": profile_id})
        return True

    def advance_to_monitoring(self, profile_id: str) -> bool:
        """
        Advance an EXECUTION-state profile to MONITORING.

        Returns True on success, False if the profile is not in EXECUTION state.
        """
        with self._lock:
            profile = self._profiles.get(profile_id)
        if profile is None:
            return False
        if profile.lifecycle != RequestLifecycle.EXECUTION:
            return False
        self._advance(profile, RequestLifecycle.MONITORING)
        self._emit_event("production_monitoring_started", {"profile_id": profile_id})
        return True

    def get_profile(self, profile_id: str) -> Optional[ProductionRequestProfile]:
        """Return a profile by ID, or None if not found."""
        with self._lock:
            return self._profiles.get(profile_id)

    def get_audit_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Return the most recent audit log entries (up to *limit*)."""
        with self._lock:
            return list(self._audit_log[-limit:])

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _advance(
        self, profile: ProductionRequestProfile, new_state: RequestLifecycle
    ) -> None:
        """Advance the profile to *new_state* and record the transition."""
        with self._lock:
            profile.lifecycle = new_state
            profile.updated_at = _ts()
            profile.history.append({
                "transition": new_state.value,
                "at": profile.updated_at,
            })

    def _emit_event(self, event_name: str, payload: Dict[str, Any]) -> None:
        """Emit an event on the EventBackbone; silently skip if not wired."""
        if self._backbone is None:
            return
        try:
            from event_backbone import EventType  # type: ignore[import]
            # Use GATE_EVALUATED / GATE_BLOCKED where semantically appropriate
            _event_map = {
                "production_gate_pass": "GATE_EVALUATED",
                "production_gate_fail": "GATE_BLOCKED",
            }
            et_name = _event_map.get(event_name)
            if et_name:
                et = EventType[et_name]
            else:
                # Fall back to TASK_SUBMITTED / TASK_COMPLETED heuristic
                et = (
                    EventType.TASK_COMPLETED
                    if "complete" in event_name or "pass" in event_name
                    else EventType.TASK_SUBMITTED
                )
            self._backbone.publish(et, {**payload, "_event": event_name})
        except Exception as exc:
            logger.debug("EventBackbone publish skipped: %s", _sanitize_error(exc))

    def _record_golden_path(
        self,
        profile: ProductionRequestProfile,
        report: GateValidationReport,
    ) -> None:
        """Record a successful production path via GoldenPathBridge."""
        if self._golden_path is None:
            return
        try:
            self._golden_path.record_success(
                task_pattern=f"production:{profile.industry}:{profile.regulatory_zone}",
                domain="production",
                execution_spec={
                    "country": profile.country,
                    "industry": profile.industry,
                    "functions": profile.functions,
                    "required_frameworks": profile.required_frameworks,
                    "passed_items": report.passed_items,
                },
                metadata={"profile_id": profile.profile_id},
            )
        except Exception as exc:
            logger.debug(
                "GoldenPathBridge record_success skipped: %s", _sanitize_error(exc)
            )

    def _record_audit(self, action: str, details: Dict[str, Any]) -> None:
        """Append an audit entry (caller must hold self._lock or pass a copy)."""
        entry = {"action": action, "at": _ts(), **details}
        # Bounded by _MAX_AUDIT_LOG — drop oldest entries when at capacity
        if len(self._audit_log) >= _MAX_AUDIT_LOG:
            self._audit_log = self._audit_log[-((_MAX_AUDIT_LOG // 2)):]
        self._audit_log.append(entry)
