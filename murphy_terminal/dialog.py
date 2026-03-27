"""
Murphy Terminal — Dialog Context

State tracking for synthetic interview dialogs.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post | License: BSL 1.1
"""

from __future__ import annotations

import re
from typing import Optional, List, Dict, Any
from datetime import datetime

from murphy_terminal.config import API_PROVIDER_LINKS, INTENT_PATTERNS


def detect_feedback(message: str) -> bool:
    """Check if message contains feedback indicators."""
    feedback_patterns = [
        r"\bthanks?\b",
        r"\bgreat\b",
        r"\bgood\b",
        r"\bhelpful\b",
        r"\bperfect\b",
        r"\bawesome\b",
        r"\bexcellent\b",
    ]
    message_lower = message.lower()
    return any(re.search(p, message_lower) for p in feedback_patterns)


def detect_intent(message: str) -> Optional[str]:
    """Detect user intent from message using pattern matching."""
    message_lower = message.lower()
    for intent, patterns in INTENT_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, message_lower):
                return intent
    return None


class DialogContext:
    """
    Maintains state for multi-turn dialogs and synthetic interviews.
    
    Tracks:
    - Current interview stage
    - Collected information
    - Inferred integrations
    - Conversation history
    """

    def __init__(self) -> None:
        self.stage: str = "idle"
        self.collected: Dict[str, Any] = {}
        self.history: List[Dict[str, Any]] = []
        self.inferred_integrations: List[str] = []
        self.interview_complete: bool = False
        self.started_at: Optional[datetime] = None

    def start_interview(self) -> str:
        """Begin a new onboarding interview."""
        self.stage = "company_name"
        self.collected = {}
        self.inferred_integrations = []
        self.interview_complete = False
        self.started_at = datetime.now()
        return (
            "Great! Let's get started with your Murphy System setup.\n\n"
            "First, what's the name of your company or project?"
        )

    def process_response(self, message: str) -> str:
        """Process user response based on current interview stage."""
        self.history.append({
            "stage": self.stage,
            "message": message,
            "timestamp": datetime.now().isoformat(),
        })

        if self.stage == "company_name":
            self.collected["company_name"] = message.strip()
            self.stage = "industry"
            return (
                f"Got it — '{self.collected['company_name']}'.\n\n"
                "What industry or domain are you in?\n"
                "(e.g., tech, finance, healthcare, retail, consulting)"
            )

        elif self.stage == "industry":
            self.collected["industry"] = message.strip()
            self._infer_integrations(message)
            self.stage = "team_size"
            return (
                f"Interesting — {self.collected['industry']}.\n\n"
                "How large is your team?\n"
                "(e.g., solo, 2-10, 11-50, 51-200, 200+)"
            )

        elif self.stage == "team_size":
            self.collected["team_size"] = message.strip()
            self.stage = "primary_goal"
            return (
                "Thanks! What's your primary goal with Murphy?\n"
                "(e.g., automation, analytics, customer support, sales, operations)"
            )

        elif self.stage == "primary_goal":
            self.collected["primary_goal"] = message.strip()
            self._infer_integrations(message)
            self.stage = "current_tools"
            return (
                "What tools or platforms are you currently using?\n"
                "(e.g., Slack, HubSpot, Salesforce, Google Workspace, GitHub)"
            )

        elif self.stage == "current_tools":
            self.collected["current_tools"] = message.strip()
            self._infer_integrations(message)
            self.stage = "complete"
            self.interview_complete = True
            return self._generate_summary()

        else:
            return "I'm not sure what stage we're at. Try 'start interview' to begin again."

    def _infer_integrations(self, message: str) -> None:
        """Infer needed integrations from user responses."""
        message_lower = message.lower()
        
        integration_keywords = {
            "slack": ["slack", "team messaging", "chat"],
            "github": ["github", "git", "code", "repository", "development"],
            "hubspot": ["hubspot", "crm", "marketing", "sales"],
            "salesforce": ["salesforce", "sales", "crm"],
            "stripe": ["stripe", "payment", "billing", "subscription"],
            "sendgrid": ["sendgrid", "email", "mail"],
            "google": ["google", "gmail", "sheets", "drive", "calendar"],
            "twilio": ["twilio", "sms", "phone", "voice"],
        }

        for integration, keywords in integration_keywords.items():
            if any(kw in message_lower for kw in keywords):
                if integration not in self.inferred_integrations:
                    self.inferred_integrations.append(integration)

    def _generate_summary(self) -> str:
        """Generate interview summary and recommendations."""
        summary = [
            "# Murphy Setup Summary\n",
            f"**Company:** {self.collected.get('company_name', 'Unknown')}",
            f"**Industry:** {self.collected.get('industry', 'Unknown')}",
            f"**Team Size:** {self.collected.get('team_size', 'Unknown')}",
            f"**Primary Goal:** {self.collected.get('primary_goal', 'Unknown')}",
            f"**Current Tools:** {self.collected.get('current_tools', 'Unknown')}",
            "\n## Recommended Integrations\n",
        ]

        if self.inferred_integrations:
            for integration in self.inferred_integrations:
                info = API_PROVIDER_LINKS.get(integration, {})
                name = info.get("name", integration.title())
                desc = info.get("description", "")
                summary.append(f"- **{name}**: {desc}")
        else:
            summary.append("- No specific integrations detected. Start with the basics!")

        summary.extend([
            "\n## Next Steps\n",
            "1. Configure your API keys with `api keys`",
            "2. Test the connection with `health`",
            "3. Start automating with `execute <task>`",
            "\nType `help` for more commands.",
        ])

        return "\n".join(summary)

    def reset(self) -> None:
        """Reset dialog context to initial state."""
        self.__init__()

    def is_in_interview(self) -> bool:
        """Check if currently in an interview."""
        return self.stage not in ("idle", "complete")
