# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Organization Intake — Step 1 of the org_build_plan pipeline.

Collects the information needed to build a fully configured tenant
on the Murphy System.  The intake questionnaire covers organization
identity, structure, regulatory posture, labor model, existing systems,
and IP protection requirements.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Valid value sets
# ---------------------------------------------------------------------------

VALID_ORG_TYPES: List[str] = [
    "corporation",
    "llc",
    "union_trust",
    "nonprofit",
    "cooperative",
    "government",
    "other",
]

VALID_LABOR_MODELS: List[str] = ["union", "w2", "contractor", "mixed"]

VALID_IP_LEVELS: List[str] = ["standard", "trade_secret", "patent_pending"]

VALID_COMPANY_SIZES: List[str] = ["small", "medium", "enterprise"]

VALID_REGULATORY_FRAMEWORKS: List[str] = [
    "OSHA", "EPA", "HIPAA", "SOC2", "GDPR", "PCI_DSS",
    "ISO27001", "DOT", "FMCSA", "NERC", "CAN_SPAM",
]

# Pulled from setup_wizard.py VALID_INDUSTRIES
VALID_INDUSTRIES: List[str] = [
    "manufacturing",
    "technology",
    "finance",
    "healthcare",
    "retail",
    "energy",
    "media",
    "logistics",
    "nonprofit",
    "other",
]

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class DepartmentSpec:
    """Specification for a single department within the intake profile."""

    name: str = ""
    head_name: str = ""
    head_email: str = ""
    headcount: int = 1
    level: str = "manager"
    responsibilities: List[str] = field(default_factory=list)
    automation_priorities: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a JSON-compatible dictionary."""
        return {
            "name": self.name,
            "head_name": self.head_name,
            "head_email": self.head_email,
            "headcount": self.headcount,
            "level": self.level,
            "responsibilities": list(self.responsibilities),
            "automation_priorities": list(self.automation_priorities),
        }


@dataclass
class OrganizationIntakeProfile:
    """Complete intake profile collected from an incoming organization."""

    org_name: str = ""
    industry: str = "other"
    org_type: str = "corporation"
    labor_model: str = "w2"
    company_size: str = "medium"
    regulatory_frameworks: List[str] = field(default_factory=list)
    existing_systems: List[str] = field(default_factory=list)
    departments: List[DepartmentSpec] = field(default_factory=list)
    workflow_priorities: List[str] = field(default_factory=list)
    connector_needs: List[str] = field(default_factory=list)
    budget_tracking: bool = False
    franchise_model: bool = False
    ip_protection_level: str = "standard"
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a JSON-compatible dictionary."""
        return {
            "org_name": self.org_name,
            "industry": self.industry,
            "org_type": self.org_type,
            "labor_model": self.labor_model,
            "company_size": self.company_size,
            "regulatory_frameworks": list(self.regulatory_frameworks),
            "existing_systems": list(self.existing_systems),
            "departments": [d.to_dict() for d in self.departments],
            "workflow_priorities": list(self.workflow_priorities),
            "connector_needs": list(self.connector_needs),
            "budget_tracking": self.budget_tracking,
            "franchise_model": self.franchise_model,
            "ip_protection_level": self.ip_protection_level,
            "created_at": self.created_at,
        }


# ---------------------------------------------------------------------------
# Intake questionnaire
# ---------------------------------------------------------------------------

_INTAKE_QUESTIONS: List[Dict[str, Any]] = [
    {
        "question_id": "org_name",
        "question": "What is the legal name of your organization?",
        "category": "identity",
        "required": True,
        "options": [],
        "help_text": "Enter the full legal name as it appears on official documents.",
        "order": 1,
    },
    {
        "question_id": "industry",
        "question": "Which industry best describes your organization?",
        "category": "identity",
        "required": True,
        "options": VALID_INDUSTRIES,
        "help_text": "Select the closest match — this selects your starter preset.",
        "order": 2,
    },
    {
        "question_id": "org_type",
        "question": "What is your organization's legal structure?",
        "category": "identity",
        "required": True,
        "options": VALID_ORG_TYPES,
        "help_text": "Choose the entity type that matches your legal formation.",
        "order": 3,
    },
    {
        "question_id": "company_size",
        "question": "How large is your organization?",
        "category": "structure",
        "required": True,
        "options": VALID_COMPANY_SIZES,
        "help_text": "small (<50 employees), medium (50-500), enterprise (500+).",
        "order": 4,
    },
    {
        "question_id": "labor_model",
        "question": "What is your primary workforce model?",
        "category": "structure",
        "required": True,
        "options": VALID_LABOR_MODELS,
        "help_text": "Select union, W2, contractor, or a mixed arrangement.",
        "order": 5,
    },
    {
        "question_id": "regulatory_frameworks",
        "question": "Which regulatory frameworks apply to your organization?",
        "category": "regulatory",
        "required": False,
        "options": VALID_REGULATORY_FRAMEWORKS,
        "help_text": "Comma-separated list of applicable compliance frameworks.",
        "order": 6,
    },
    {
        "question_id": "existing_systems",
        "question": "Which platforms and tools does your organization currently use?",
        "category": "systems",
        "required": False,
        "options": [],
        "help_text": "List existing system IDs (e.g. slack, salesforce, quickbooks).",
        "order": 7,
    },
    {
        "question_id": "connector_needs",
        "question": "Which additional platform connectors do you need?",
        "category": "systems",
        "required": False,
        "options": [],
        "help_text": "List any additional connector IDs beyond your existing systems.",
        "order": 8,
    },
    {
        "question_id": "workflow_priorities",
        "question": "What are your top workflow automation priorities?",
        "category": "structure",
        "required": False,
        "options": [],
        "help_text": "E.g. invoice_automation, safety_monitoring, client_onboarding.",
        "order": 9,
    },
    {
        "question_id": "ip_protection_level",
        "question": "What level of intellectual property protection do you require?",
        "category": "ip",
        "required": True,
        "options": VALID_IP_LEVELS,
        "help_text": "standard, trade_secret, or patent_pending (affects workspace isolation).",
        "order": 10,
    },
    {
        "question_id": "budget_tracking",
        "question": "Do you need budget tracking and financial reporting enabled?",
        "category": "structure",
        "required": False,
        "options": ["yes", "no"],
        "help_text": "Enables financial dashboards and budget alert automations.",
        "order": 11,
    },
    {
        "question_id": "franchise_model",
        "question": "Does your organization operate as a franchise or multi-location model?",
        "category": "structure",
        "required": False,
        "options": ["yes", "no"],
        "help_text": "Enables multi-location workspace hierarchy and franchise permissions.",
        "order": 12,
    },
]


# ---------------------------------------------------------------------------
# OrganizationIntake class
# ---------------------------------------------------------------------------


class OrganizationIntake:
    """Collects and validates an organization's intake profile.

    Walk through :meth:`get_questions`, submit answers via
    :meth:`apply_answer`, then call :meth:`get_profile` once all
    required answers are provided.
    """

    def __init__(self) -> None:
        self._profile = OrganizationIntakeProfile()
        self._answers: Dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Questionnaire helpers
    # ------------------------------------------------------------------

    def get_questions(self) -> List[Dict[str, Any]]:
        """Return the ordered list of intake questions."""
        return [q.copy() for q in _INTAKE_QUESTIONS]

    def apply_answer(self, question_id: str, answer: Any) -> Dict[str, Any]:
        """Validate and apply *answer* for *question_id*.

        Returns ``{"applied": True}`` on success or
        ``{"applied": False, "error": "reason"}`` on validation failure.
        """
        question = next(
            (q for q in _INTAKE_QUESTIONS if q["question_id"] == question_id),
            None,
        )
        if question is None:
            return {"applied": False, "error": f"Unknown question_id: {question_id}"}

        # Options-constrained single-value fields
        options = question.get("options", [])
        if options and not isinstance(answer, (list, tuple)):
            if str(answer) not in options:
                return {
                    "applied": False,
                    "error": f"Invalid value '{answer}'. Must be one of: {options}",
                }

        # Multi-value list fields — validate each item against options
        if isinstance(answer, (list, tuple)) and options:
            invalid = [v for v in answer if v not in options]
            if invalid:
                return {
                    "applied": False,
                    "error": f"Invalid values {invalid}. Must be from: {options}",
                }

        self._answers[question_id] = answer
        self._apply_to_profile(question_id, answer)
        return {"applied": True}

    def _apply_to_profile(self, question_id: str, answer: Any) -> None:
        """Write a validated answer into the profile dataclass."""
        bool_map = {"yes": True, "no": False, True: True, False: False}

        if question_id == "org_name":
            self._profile.org_name = str(answer)
        elif question_id == "industry":
            self._profile.industry = str(answer)
        elif question_id == "org_type":
            self._profile.org_type = str(answer)
        elif question_id == "company_size":
            self._profile.company_size = str(answer)
        elif question_id == "labor_model":
            self._profile.labor_model = str(answer)
        elif question_id == "regulatory_frameworks":
            if isinstance(answer, (list, tuple)):
                self._profile.regulatory_frameworks = list(answer)
            else:
                self._profile.regulatory_frameworks = [
                    f.strip() for f in str(answer).split(",") if f.strip()
                ]
        elif question_id == "existing_systems":
            if isinstance(answer, (list, tuple)):
                self._profile.existing_systems = list(answer)
            else:
                self._profile.existing_systems = [
                    s.strip() for s in str(answer).split(",") if s.strip()
                ]
        elif question_id == "connector_needs":
            if isinstance(answer, (list, tuple)):
                self._profile.connector_needs = list(answer)
            else:
                self._profile.connector_needs = [
                    s.strip() for s in str(answer).split(",") if s.strip()
                ]
        elif question_id == "workflow_priorities":
            if isinstance(answer, (list, tuple)):
                self._profile.workflow_priorities = list(answer)
            else:
                self._profile.workflow_priorities = [
                    s.strip() for s in str(answer).split(",") if s.strip()
                ]
        elif question_id == "ip_protection_level":
            self._profile.ip_protection_level = str(answer)
        elif question_id == "budget_tracking":
            self._profile.budget_tracking = bool_map.get(answer, bool(answer))
        elif question_id == "franchise_model":
            self._profile.franchise_model = bool_map.get(answer, bool(answer))

    # ------------------------------------------------------------------
    # Profile access
    # ------------------------------------------------------------------

    def get_profile(self) -> OrganizationIntakeProfile:
        """Return the current :class:`OrganizationIntakeProfile`."""
        return self._profile

    def validate_profile(self) -> Dict[str, Any]:
        """Validate the current profile and return issues.

        Returns ``{"valid": True, "issues": []}`` when the profile is
        ready to proceed, or ``{"valid": False, "issues": [...]}`` with
        a list of human-readable problem descriptions.
        """
        issues: List[str] = []
        p = self._profile

        if not p.org_name or not p.org_name.strip():
            issues.append("org_name is required")
        if p.industry not in VALID_INDUSTRIES:
            issues.append(
                f"industry '{p.industry}' is not valid. "
                f"Must be one of: {VALID_INDUSTRIES}"
            )
        if p.org_type not in VALID_ORG_TYPES:
            issues.append(
                f"org_type '{p.org_type}' is not valid. "
                f"Must be one of: {VALID_ORG_TYPES}"
            )
        if p.labor_model not in VALID_LABOR_MODELS:
            issues.append(
                f"labor_model '{p.labor_model}' is not valid. "
                f"Must be one of: {VALID_LABOR_MODELS}"
            )
        if p.company_size not in VALID_COMPANY_SIZES:
            issues.append(
                f"company_size '{p.company_size}' is not valid. "
                f"Must be one of: {VALID_COMPANY_SIZES}"
            )
        if p.ip_protection_level not in VALID_IP_LEVELS:
            issues.append(
                f"ip_protection_level '{p.ip_protection_level}' is not valid. "
                f"Must be one of: {VALID_IP_LEVELS}"
            )
        for fw in p.regulatory_frameworks:
            if fw not in VALID_REGULATORY_FRAMEWORKS:
                issues.append(
                    f"regulatory_framework '{fw}' is not recognised. "
                    f"Valid values: {VALID_REGULATORY_FRAMEWORKS}"
                )

        return {"valid": len(issues) == 0, "issues": issues}

    def apply_preset(self, preset_id: str) -> OrganizationIntakeProfile:
        """Load defaults from an industry preset into the profile.

        Applies the preset's default_org_type, default_labor_model,
        default_company_size, recommended_frameworks, and default_departments
        without overwriting an already-set org_name.
        """
        from .presets import get_preset

        preset = get_preset(preset_id)
        if preset is None:
            raise ValueError(
                f"Unknown preset '{preset_id}'. "
                f"Use presets.list_presets() to see available options."
            )

        p = self._profile
        # Only fill in values not yet explicitly set
        if p.industry == "other":
            p.industry = preset.industry
        if p.org_type == "corporation":
            p.org_type = preset.default_org_type
        if p.labor_model == "w2":
            p.labor_model = preset.default_labor_model
        if p.company_size == "medium":
            p.company_size = preset.default_company_size
        if not p.regulatory_frameworks:
            p.regulatory_frameworks = list(preset.recommended_frameworks)
        if not p.departments:
            p.departments = [
                DepartmentSpec(
                    name=d.get("name", ""),
                    head_name=d.get("head_name", ""),
                    head_email=d.get("head_email", ""),
                    headcount=d.get("headcount", 1),
                    level=d.get("level", "manager"),
                    responsibilities=d.get("responsibilities", []),
                    automation_priorities=d.get("automation_priorities", []),
                )
                for d in preset.default_departments
            ]

        logger.info(
            "Applied preset '%s' to intake profile for '%s'",
            preset_id,
            p.org_name or "(unnamed)",
        )
        return p

    def to_dict(self) -> Dict[str, Any]:
        """Serialise the entire intake state to a JSON-compatible dictionary."""
        return {
            "profile": self._profile.to_dict(),
            "answers": dict(self._answers),
        }


__all__ = [
    "DepartmentSpec",
    "OrganizationIntakeProfile",
    "OrganizationIntake",
    "VALID_ORG_TYPES",
    "VALID_LABOR_MODELS",
    "VALID_IP_LEVELS",
    "VALID_INDUSTRIES",
    "VALID_REGULATORY_FRAMEWORKS",
]
