"""
Sales Automation Module for the Murphy System.
Configures Murphy System to automate its own sales process,
including lead scoring, qualification, demo generation, and proposals.
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Industry-to-feature mapping for personalized demos and proposals
INDUSTRY_FEATURES: Dict[str, List[str]] = {
    "manufacturing": [
        "robotics integration",
        "factory automation",
        "predictive maintenance",
        "safety compliance",
    ],
    "technology": [
        "CI/CD automation",
        "code generation",
        "agent swarms",
        "API integration",
    ],
    "finance": [
        "trading bot",
        "compliance monitoring",
        "risk assessment",
        "audit trails",
    ],
    "healthcare": [
        "HIPAA compliance",
        "data security",
        "patient workflow automation",
    ],
    "retail": [
        "inventory automation",
        "content creation",
        "customer analytics",
    ],
    "energy": [
        "energy management",
        "building automation",
        "SCADA integration",
    ],
    "media": [
        "content creation",
        "social media moderation",
        "digital asset generation",
    ],
}

VALID_STATUSES = [
    "new",
    "qualified",
    "demo_scheduled",
    "proposal_sent",
    "closed_won",
    "closed_lost",
]

SIZE_SCORES: Dict[str, int] = {"small": 10, "medium": 30, "enterprise": 50}

DEFAULT_EDITIONS = [
    {
        "name": "community",
        "price": "Free",
        "description": "Open-source core with full automation runtime",
    },
    {
        "name": "professional",
        "price": "Per-Seat",
        "description": "Managed hosting, priority support, advanced analytics",
    },
    {
        "name": "enterprise",
        "price": "Contact us",
        "description": "On-premise, 24/7 support, compliance, custom modules",
    },
]

DEFAULT_TARGET_INDUSTRIES = list(INDUSTRY_FEATURES.keys())

DEFAULT_SALES_CHANNELS = ["website", "email", "demo", "partner"]


@dataclass
class SalesAutomationConfig:
    """Configuration for the Murphy System sales automation pipeline."""

    company_name: str = "Inoni LLC"
    product_name: str = "murphy_system"
    editions: List[Dict] = field(default_factory=lambda: list(DEFAULT_EDITIONS))
    target_industries: List[str] = field(
        default_factory=lambda: list(DEFAULT_TARGET_INDUSTRIES)
    )
    sales_channels: List[str] = field(
        default_factory=lambda: list(DEFAULT_SALES_CHANNELS)
    )
    demo_mode_enabled: bool = True


@dataclass
class LeadProfile:
    """Represents a prospective customer in the sales pipeline."""

    company_name: str
    contact_name: str
    contact_email: str
    industry: str
    company_size: str
    interests: List[str] = field(default_factory=list)
    score: float = 0.0
    status: str = "new"
    lead_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    notes: List[str] = field(default_factory=list)


class SalesAutomationEngine:
    """Automates the Murphy System sales pipeline."""

    def __init__(self, config: Optional[SalesAutomationConfig] = None):
        self.config = config or SalesAutomationConfig()
        self._pipeline: Dict[str, LeadProfile] = {}

    def register_lead(self, lead: LeadProfile) -> str:
        """Add a lead to the pipeline and return its lead_id."""
        self._pipeline[lead.lead_id] = lead
        return lead.lead_id

    def score_lead(self, lead: LeadProfile) -> float:
        """Score a lead from 0-100 based on size, industry, and interests."""
        score = SIZE_SCORES.get(lead.company_size, 0)
        if lead.industry in self.config.target_industries:
            score += 20
        score += min(len(lead.interests) * 5, 30)
        lead.score = min(score, 100)
        return lead.score

    def qualify_lead(self, lead: LeadProfile) -> Dict:
        """Determine whether a lead is qualified and return details.

        Tuning #2: Three-tier qualification:
            >= 40  → qualified (schedule demo)
            30-39  → borderline (interest discovery)
            < 30   → not qualified (nurture with content)
        """
        score = self.score_lead(lead)
        if score >= 40:
            qualified = True
            tier = "qualified"
            lead.status = "qualified"
            reason = "Score meets threshold"
            action = "Schedule demo"
        elif score >= 30:
            qualified = False
            tier = "borderline"
            lead.status = "borderline"
            reason = "Score in borderline range — needs interest discovery"
            action = "Targeted interest discovery"
        else:
            qualified = False
            tier = "not_qualified"
            lead.status = "not_qualified"
            reason = "Score below threshold"
            action = "Nurture with content"
        return {
            "lead_id": lead.lead_id,
            "score": score,
            "qualified": qualified,
            "tier": tier,
            "reason": reason,
            "recommended_action": action,
        }

    def recommend_edition(self, lead: LeadProfile) -> str:
        """Recommend an edition based on company size and interests."""
        if lead.company_size == "enterprise":
            return "enterprise"
        if lead.company_size == "medium":
            return "professional"
        return "community"

    def get_feature_highlights(self, industry: str) -> List[str]:
        """Return industry-specific Murphy System feature highlights."""
        return INDUSTRY_FEATURES.get(industry, [
            "universal automation runtime",
            "agent swarms",
            "event backbone",
        ])

    def generate_demo_script(self, lead: LeadProfile) -> Dict:
        """Generate a personalized demo script for the lead."""
        highlights = self.get_feature_highlights(lead.industry)
        edition = self.recommend_edition(lead)
        return {
            "greeting": (
                f"Welcome {lead.contact_name} from {lead.company_name}! "
                f"Today we'll show how {self.config.product_name} transforms "
                f"{lead.industry} operations."
            ),
            "feature_highlights": highlights,
            "demo_steps": [
                f"Overview of {self.config.product_name} architecture",
                f"Live demo of {highlights[0] if highlights else 'core runtime'}",
                f"Walk through {edition} edition capabilities",
                "Q&A and next steps",
            ],
            "closing": (
                f"Thank you for your time, {lead.contact_name}. "
                f"We'll follow up with a tailored {edition} proposal."
            ),
        }

    def generate_proposal(self, lead: LeadProfile) -> Dict:
        """Generate a sales proposal for the lead."""
        edition = self.recommend_edition(lead)
        highlights = self.get_feature_highlights(lead.industry)
        edition_info = next(
            (e for e in self.config.editions if e["name"] == edition),
            self.config.editions[0],
        )
        return {
            "executive_summary": (
                f"Proposal for {lead.company_name} to adopt "
                f"{self.config.product_name} {edition.title()} Edition "
                f"for {lead.industry} automation."
            ),
            "recommended_edition": edition,
            "features_included": highlights,
            "pricing": edition_info["price"],
            "implementation_plan": [
                "Discovery & requirements gathering",
                "Environment setup and integration",
                "Configuration and customization",
                "Training and go-live support",
            ],
            "timeline": "4-8 weeks",
        }

    def advance_lead(self, lead_id: str, new_status: str) -> bool:
        """Move a lead to a new status. Returns True on success."""
        if new_status not in VALID_STATUSES:
            return False
        lead = self._pipeline.get(lead_id)
        if lead is None:
            return False
        lead.status = new_status
        return True

    def get_pipeline_summary(self) -> Dict:
        """Return a summary of all leads grouped by status."""
        summary: Dict[str, List[str]] = {s: [] for s in VALID_STATUSES}
        for lead in self._pipeline.values():
            summary.setdefault(lead.status, []).append(lead.lead_id)
        total = len(self._pipeline)
        return {"total_leads": total, "by_status": summary}
