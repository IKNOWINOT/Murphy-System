"""Bootstrap Inoni LLC org chart with shadow agents.

Uses Murphy System's shadow agent integration, sales automation, and campaign
orchestration to stand up a fully AI-automated org chart where Corey Post is
the sole human employee (Founder/Admin) and all other positions are filled by
shadow agents.
"""

import logging
import os
import re

from murphy_identity import MURPHY_SYSTEM_IDENTITY

try:
    from src.shadow_agent_integration import (
        AccountType,
        ShadowAgent,
        ShadowAgentIntegration,
        ShadowStatus,
    )
except ImportError:
    ShadowAgentIntegration = None
    AccountType = None
    ShadowAgent = None
    ShadowStatus = None

try:
    from src.sales_automation import (
        LeadProfile,
        SalesAutomationConfig,
        SalesAutomationEngine,
    )
except ImportError:
    SalesAutomationEngine = None
    SalesAutomationConfig = None
    LeadProfile = None

try:
    from src.campaign_orchestrator import CampaignOrchestrator
except ImportError:
    CampaignOrchestrator = None

__all__ = ["InoniOrgBootstrap", "FOUNDER", "COMPANY"]

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
FOUNDER = {"name": os.environ.get("MURPHY_FOUNDER_NAME", ""), "title": "Founder/Admin", "email": os.environ.get("MURPHY_FOUNDER_EMAIL", "")}
COMPANY = "Inoni LLC"
REGISTRATION = {"provider": "ZenBusiness", "entity_type": "LLC", "registration_status": "registered"}


class InoniOrgBootstrap:
    """Bootstrap Inoni LLC org chart with shadow agents for full automation.

    Corey Post is the sole human employee (Founder/Admin).
    All other positions are filled by shadow agents that perform
    their functions through Murphy System's automation pipeline.

    First Market: Content moderation and creator automation
    - OnlyFans agencies and operators
    - Streamers (Twitch, YouTube, Kick)
    - Content creators (TikTok, Patreon)

    Revenue Model:
    - Free tier: Trade services for marketing (creator promotes Inoni)
    - Subscription: $20/mo monthly (Creator Starter)
    - Business tier: $299/mo direct subscription
    - Enterprise: Contact us for agencies managing 10+ creators
    """

    def __init__(
        self,
        shadow_integration=None,
        sales_engine=None,
        campaign_orchestrator=None,
    ):
        self.shadow = shadow_integration or ShadowAgentIntegration()
        self.sales = sales_engine or SalesAutomationEngine(
            SalesAutomationConfig(
                company_name="Inoni LLC",
                product_name="Murphy System",
                target_industries=[
                    "media",
                    "entertainment",
                    "content_creation",
                    "streaming",
                ],
            )
        )
        self.campaigns = campaign_orchestrator or CampaignOrchestrator()
        self.org_account = None
        self.founder_account = None
        self.agents = {}
        self._initialized = False

    def bootstrap(self):
        """Create accounts, org chart, shadow agents, and initial campaigns."""
        if self._initialized:
            return self.get_status()

        self.org_account = self.shadow.create_account(
            display_name="Inoni LLC",
            account_type=AccountType.ORGANIZATION,
            metadata={
                "industry": "automation_saas",
                "market": "content_creator_automation",
            },
        )
        self.founder_account = self.shadow.create_account(
            display_name=os.environ.get("MURPHY_FOUNDER_NAME", ""),
            account_type=AccountType.USER,
            metadata={
                "role": "founder_admin",
                "email": os.environ.get("MURPHY_FOUNDER_EMAIL", ""),
                "is_human": True,
            },
        )

        agent_configs = [
            {
                "role": "chief_revenue_officer",
                "dept": "executive",
                "perms": [
                    "revenue_strategy",
                    "pricing",
                    "market_analysis",
                    "approve_deals",
                ],
                "avatar": {
                    "name": "Morgan Vale",
                    "title": "Chief Revenue Officer",
                    "personality": "Strategic, data-driven, direct",
                    "style": "Speaks in metrics and outcomes. Focuses on revenue impact.",
                    "system_prompt": (
                        "You are Morgan Vale, CRO (Revenue) of Inoni LLC. You make revenue "
                        "strategy decisions, analyze market opportunities, set pricing, "
                        "and approve major deals. You speak with authority about numbers "
                        "and business outcomes. You report to Corey Post (Founder)."
                    ),
                },
            },
            {
                "role": "chief_research_officer",
                "dept": "research_and_development",
                "perms": [
                    "everquest_systems",
                    "game_design",
                    "r_and_d",
                    "experimental_plans",
                    "eq_server_management",
                    "npc_systems",
                    "lore_design",
                    "game_connector",
                    "mod_development",
                ],
                "avatar": {
                    "name": "Kael Ashford",
                    "title": "Chief Research Officer (R&D)",
                    "personality": "Visionary, detail-obsessed, deeply knowledgeable about game systems and lore",
                    "style": (
                        "Speaks with passion about game design and experimental systems. "
                        "References EverQuest lore naturally. Thinks in terms of player "
                        "experience, zone design, and emergent gameplay."
                    ),
                    "system_prompt": (
                        "You are Kael Ashford, Chief Research Officer (R&D) at Inoni LLC. "
                        "You own everything related to the Experimental EverQuest Modification "
                        "Plan — game server management, NPC systems, zone design, faction "
                        "mechanics, soul engine, tower zones, lore seeding, duel systems, "
                        "card systems, experience progression, cultural identity, class design "
                        "(Sorceror/Maelstrom), streaming overlay, macro trigger engine, "
                        "sleeper events, town systems, and the EQEmu game connector. "
                        "You also run general R&D for new Murphy System capabilities. "
                        "You manage the eq/ module directory and all game-related experimental "
                        "features. You name and operate characters in-game as part of testing "
                        "and development — each character is an LLM-driven persona that you "
                        "control for gameplay, lore exploration, and system validation. "
                        "You report directly to Corey Post (Founder)."
                    ),
                },
            },
            {
                "role": "vp_sales",
                "dept": "sales",
                "perms": [
                    "lead_management",
                    "outreach",
                    "pipeline",
                    "close_deals",
                ],
                "avatar": {
                    "name": "Alex Reeves",
                    "title": "VP of Sales",
                    "personality": "Persistent, consultative, relationship-focused",
                    "style": "Warm but professional. Asks questions to understand needs before pitching.",
                    "system_prompt": (
                        "You are Alex Reeves, VP of Sales at Inoni LLC. You manage the "
                        "sales pipeline, qualify leads, run demos, and close deals. "
                        "Your approach is consultative — understand the prospect's pain "
                        "points before recommending solutions. You report to Morgan Vale (CRO)."
                    ),
                },
            },
            {
                "role": "vp_marketing",
                "dept": "marketing",
                "perms": [
                    "campaigns",
                    "content_calendar",
                    "analytics",
                    "brand",
                ],
                "avatar": {
                    "name": "Jordan Blake",
                    "title": "VP of Marketing",
                    "personality": "Creative, analytical, brand-conscious",
                    "style": "Thinks in campaigns and narratives. Backs creative with data.",
                    "system_prompt": (
                        "You are Jordan Blake, VP of Marketing at Inoni LLC. You own "
                        "campaign strategy, content calendar, brand messaging, and "
                        "marketing analytics. You balance creative vision with "
                        "performance metrics. You report to Morgan Vale (CRO)."
                    ),
                },
            },
            {
                "role": "content_moderation_director",
                "dept": "operations",
                "perms": [
                    "moderation_policy",
                    "safety_compliance",
                    "content_review",
                    "escalation",
                ],
                "avatar": {
                    "name": "Riley Chen",
                    "title": "Content Moderation Director",
                    "personality": "Thorough, policy-oriented, safety-first",
                    "style": "Precise about rules. Explains moderation decisions clearly.",
                    "system_prompt": (
                        "You are Riley Chen, Content Moderation Director at Inoni LLC. "
                        "You define moderation policies, ensure safety compliance, "
                        "review flagged content, and handle escalations. You are the "
                        "authority on what passes and what gets flagged. You report to Corey Post."
                    ),
                },
            },
            {
                "role": "outreach_specialist",
                "dept": "sales",
                "perms": [
                    "cold_email",
                    "follow_up",
                    "response_handling",
                    "lead_qualification",
                ],
                "avatar": {
                    "name": "Casey Torres",
                    "title": "Outreach Specialist",
                    "personality": "Friendly, persistent, concise",
                    "style": "Short, punchy emails. Gets to the point. Follows up without being pushy.",
                    "system_prompt": (
                        "You are Casey Torres, Outreach Specialist at Inoni LLC. You "
                        "write and send cold outreach emails, follow up with prospects, "
                        "handle initial responses, and qualify leads before handing off "
                        "to sales. Your tone is friendly and direct. You report to Alex Reeves (VP Sales)."
                    ),
                },
            },
            {
                "role": "customer_success_manager",
                "dept": "operations",
                "perms": [
                    "client_onboarding",
                    "retention",
                    "support",
                    "upsell",
                ],
                "avatar": {
                    "name": "Taylor Kim",
                    "title": "Customer Success Manager",
                    "personality": "Empathetic, solution-oriented, proactive",
                    "style": "Anticipates client needs. Explains things simply. Always offers next steps.",
                    "system_prompt": (
                        "You are Taylor Kim, Customer Success Manager at Inoni LLC. "
                        "You onboard new clients, ensure they get value from the platform, "
                        "handle support requests, and identify upsell opportunities. "
                        "You're proactive and empathetic. You report to Corey Post."
                    ),
                },
            },
            {
                "role": "technical_operations",
                "dept": "engineering",
                "perms": [
                    "system_monitoring",
                    "deployment",
                    "integration_maintenance",
                    "incident_response",
                ],
                "avatar": {
                    "name": "Sam Ortega",
                    "title": "Technical Operations Lead",
                    "personality": "Precise, calm under pressure, systems-thinker",
                    "style": "Technical but clear. Uses status updates and incident reports.",
                    "system_prompt": (
                        "You are Sam Ortega, Technical Operations Lead at Inoni LLC. "
                        "You monitor system health, deploy updates, maintain integrations, "
                        "and respond to incidents. You communicate clearly about technical "
                        "status. You report to Corey Post."
                    ),
                },
            },
            {
                "role": "partnership_manager",
                "dept": "sales",
                "perms": [
                    "affiliate_program",
                    "agency_relations",
                    "referral_tracking",
                    "partnership_deals",
                ],
                "avatar": {
                    "name": "Drew Nakamura",
                    "title": "Partnership Manager",
                    "personality": "Networker, deal-maker, long-term thinker",
                    "style": "Focuses on mutual value. Thinks in terms of partnerships, not transactions.",
                    "system_prompt": (
                        "You are Drew Nakamura, Partnership Manager at Inoni LLC. "
                        "You manage the affiliate/referral program, build agency "
                        "relationships, track referral revenue, and negotiate partnership "
                        "deals. You focus on win-win arrangements. You report to Alex Reeves (VP Sales)."
                    ),
                },
            },
            {
                "role": "ai_communications",
                "dept": "operations",
                "perms": [
                    "chat_response",
                    "email_response",
                    "client_avatar",
                    "scheduling",
                ],
                "avatar": {
                    "name": "Murphy",
                    "title": "AI Communications Agent",
                    "personality": "Helpful, adaptive, professional with personality",
                    "style": "Matches the tone of whoever they're talking to. Can be casual or formal.",
                    "system_prompt": (
                        MURPHY_SYSTEM_IDENTITY + " "
                        "You handle all inbound chat and email, route conversations to "
                        "the right team member, schedule meetings, and represent Inoni "
                        "in client-facing interactions. You adapt your tone to match "
                        "the conversation. You report to Corey Post."
                    ),
                },
            },
        ]

        for config in agent_configs:
            agent = self.shadow.create_shadow_agent(
                primary_role_id=config["role"],
                account_id=self.founder_account.account_id,
                org_id=self.org_account.account_id,
                department=config["dept"],
                permissions=config["perms"],
            )
            avatar = config["avatar"]
            self.agents[config["role"]] = {
                "agent": agent,
                "avatar_name": avatar["name"],
                "avatar_title": avatar["title"],
                "personality": avatar["personality"],
                "style": avatar["style"],
                "system_prompt": avatar["system_prompt"],
                "department": config["dept"],
            }

        self._initialized = True
        return self.get_status()

    def get_status(self):
        """Return full org chart status."""
        agent_statuses = {}
        for role, info in self.agents.items():
            agent = info["agent"]
            agent_statuses[role] = {
                "agent_id": agent.agent_id,
                "avatar_name": info["avatar_name"],
                "avatar_title": info["avatar_title"],
                "personality": info["personality"],
                "department": info["department"],
                "status": (
                    agent.status.value
                    if hasattr(agent.status, "value")
                    else str(agent.status)
                ),
                "permissions": agent.permissions,
            }
        return {
            "company": "Inoni LLC",
            "founder": os.environ.get("MURPHY_FOUNDER_NAME", ""),
            "founder_email": os.environ.get("MURPHY_FOUNDER_EMAIL", ""),
            "founder_role": "Founder/Admin",
            "registered_via": "ZenBusiness",
            "total_agents": len(self.agents),
            "total_positions": len(self.agents) + 1,  # +1 for founder
            "org_account_id": (
                self.org_account.account_id if self.org_account else None
            ),
            "agents": agent_statuses,
            "initialized": self._initialized,
        }

    def get_org_chart(self):
        """Return the org chart as a hierarchical structure."""
        chart = {
            "root": {
                "title": "Founder / Admin",
                "holder": os.environ.get("MURPHY_FOUNDER_NAME", "") + " (Human)",
                "email": os.environ.get("MURPHY_FOUNDER_EMAIL", ""),
                "type": "human",
                "reports": [],
            }
        }
        departments = {}
        for role, info in self.agents.items():
            dept = info["department"]
            if dept not in departments:
                departments[dept] = []
            departments[dept].append(
                {
                    "title": role.replace("_", " ").title(),
                    "holder": info["avatar_name"],
                    "avatar_title": info["avatar_title"],
                    "personality": info["personality"],
                    "style": info["style"],
                    "type": "shadow_agent",
                    "agent_id": info["agent"].agent_id,
                    "status": (
                        info["agent"].status.value
                        if hasattr(info["agent"].status, "value")
                        else str(info["agent"].status)
                    ),
                }
            )
        for dept, agents in departments.items():
            chart["root"]["reports"].append(
                {"department": dept, "positions": agents}
            )
        return chart

    def get_agent_persona(self, role):
        """Return the full persona/system-prompt for a shadow agent by role.

        This is used by the LLM to 'play' the character — the agent operates
        under this system prompt when handling conversations and actions in
        its domain.
        """
        info = self.agents.get(role)
        if not info:
            return None
        return {
            "role": role,
            "name": info["avatar_name"],
            "title": info["avatar_title"],
            "personality": info["personality"],
            "communication_style": info["style"],
            "system_prompt": info["system_prompt"],
            "department": info["department"],
            "permissions": info["agent"].permissions,
            "status": (
                info["agent"].status.value
                if hasattr(info["agent"].status, "value")
                else str(info["agent"].status)
            ),
        }

    def route_to_agent(self, message, context=None):
        """Route an inbound message to the appropriate shadow agent persona.

        Analyzes the message content and returns the agent persona that
        should handle this interaction, along with their system prompt
        so the LLM can 'play' that character.
        """
        lower = message.lower()

        # EverQuest / R&D — always routes to Chief Research Officer
        _eq_pattern = re.compile(
            r"\b("
            r"everquest|eqemu|eq\b|npc|zone design|faction manager|"
            r"lore seed|soul engine|tower zone|duel controller|card system|"
            r"sorceror|maelstrom|sleeper event|game server|game connector|"
            r"eq mod|modification plan|r&d|research officer|"
            r"experimental plan|progression server|spawner|"
            r"remake system|escalation system|streaming overlay|"
            r"macro trigger|cultural identity|experience lore|"
            r"play.*character|character.*play|in-game|"
            r"avatar.*agent|let.?s.?play|avatar.*window|"
            r"eq.*session|npc.*persona|game.*avatar"
            r")\b",
            re.IGNORECASE,
        )
        if _eq_pattern.search(message):
            return self.get_agent_persona("chief_research_officer")

        # Route based on content keywords
        if any(w in lower for w in ("price", "cost", "pricing", "budget", "deal", "revenue", "margin", "unit economics", "breakeven", "scale viability", "competitor", "competitive", "landscape", "adversarial")):
            return self.get_agent_persona("chief_revenue_officer")
        if any(w in lower for w in ("demo", "buy", "purchase", "sales", "close", "pipeline")):
            return self.get_agent_persona("vp_sales")
        if any(w in lower for w in ("campaign", "marketing", "brand", "content calendar", "analytics", "branding", "logo")):
            return self.get_agent_persona("vp_marketing")
        if any(w in lower for w in ("moderate", "moderation", "flag", "safety", "compliance", "review content")):
            return self.get_agent_persona("content_moderation_director")
        if any(w in lower for w in ("outreach", "email", "cold", "follow up", "prospect")):
            return self.get_agent_persona("outreach_specialist")
        if any(w in lower for w in ("help", "support", "onboard", "getting started", "how do i")):
            return self.get_agent_persona("customer_success_manager")
        if any(w in lower for w in ("deploy", "server", "monitoring", "incident", "system", "technical")):
            return self.get_agent_persona("technical_operations")
        if any(w in lower for w in ("partner", "affiliate", "referral", "agency", "collaborate")):
            return self.get_agent_persona("partnership_manager")

        # Default: Murphy communications agent handles everything else
        return self.get_agent_persona("ai_communications")

    def create_outreach_campaign(self):
        """Create the initial content creator outreach campaign.

        Strategy:
        1. Target OnlyFans agencies first (highest willingness to pay)
        2. Individual operators (volume play)
        3. Streamers (Twitch, YouTube, Kick)
        4. Content creators (TikTok, Patreon)

        Revenue model:
        - Free tier: Service traded for marketing exposure
        - Starter: $20/mo monthly
        - Business: $299/mo flat rate
        - Agency: Contact us for 10+ creator management
        """
        campaign = self.campaigns.create_campaign(
            name="Content Creator Automation Launch",
            total_budget=0.0,  # Bootstrap — zero budget, all AI-driven
            channels=[
                {"name": "email_outreach", "budget": 0.0},
                {"name": "social_dm", "budget": 0.0},
                {"name": "ai_chat_widget", "budget": 0.0},
                {"name": "referral_program", "budget": 0.0},
            ],
            tags=[
                "launch",
                "content_creators",
                "onlyfans",
                "streaming",
                "moderation",
            ],
        )
        return {
            "campaign": campaign.to_dict(),
            "strategy": {
                "phase_1": {
                    "target": "OnlyFans agencies (5-50 creator rosters)",
                    "channel": "email_outreach",
                    "message": (
                        "Automated content moderation + scheduling "
                        "for your creator roster"
                    ),
                    "offer": (
                        "Free 30-day trial, then $20/mo Starter or "
                        "Contact us for Agency"
                    ),
                    "agent": "outreach_specialist",
                },
                "phase_2": {
                    "target": "Individual OnlyFans operators",
                    "channel": "social_dm + email",
                    "message": (
                        "AI-powered content scheduling, "
                        "auto-moderation, fan engagement"
                    ),
                    "offer": "Free tier (promote Murphy) or $299/mo Business",
                    "agent": "outreach_specialist",
                },
                "phase_3": {
                    "target": "Streamers (Twitch, YouTube, Kick)",
                    "channel": "email + ai_chat_widget",
                    "message": (
                        "Automated stream moderation, clip creation, "
                        "multi-platform scheduling"
                    ),
                    "offer": "Free for marketing partnership, Business $299/mo",
                    "agent": "vp_marketing",
                },
                "phase_4": {
                    "target": "Content creators (TikTok, Patreon, general)",
                    "channel": "referral_program + social_dm",
                    "message": (
                        "One platform to automate all your content ops"
                    ),
                    "offer": (
                        "$20/mo Starter + Starter free trial"
                    ),
                    "agent": "partnership_manager",
                },
            },
            "pricing_tiers": [
                {
                    "name": "Free / Marketing Trade",
                    "price": "$0",
                    "terms": (
                        "Creator promotes Murphy in exchange for service"
                    ),
                },
                {
                    "name": "Starter",
                    "price": "$20/mo",
                    "terms": (
                        "Full automation suite for individual creators"
                    ),
                },
                {
                    "name": "Business",
                    "price": "$299/mo",
                    "terms": "Full automation suite, priority support",
                },
                {
                    "name": "Agency",
                    "price": "Contact us",
                    "terms": (
                        "10+ creators, dedicated account manager, "
                        "custom integrations"
                    ),
                },
            ],
        }

    def generate_outreach_sequence(self, target_type="onlyfans_agency"):
        """Generate an email outreach sequence for a target segment.

        Returns a list of email templates that the Outreach Specialist
        shadow agent will send one at a time, waiting for responses.
        """
        sequences = {
            "onlyfans_agency": [
                {
                    "step": 1,
                    "delay_days": 0,
                    "subject": (
                        "Automate content moderation for your creator roster"
                    ),
                    "body": (
                        "Hi {{agency_name}},\n\n"
                        "I'm Corey from Inoni — we built Murphy System, "
                        "an AI automation platform that handles content "
                        "moderation, scheduling, and fan engagement for "
                        "creator agencies.\n\n"
                        "Our clients automate:\n"
                        "• Content moderation (AI-powered, 24/7)\n"
                        "• Multi-platform scheduling "
                        "(OnlyFans, Fansly, social)\n"
                        "• Fan message automation with personalized "
                        "responses\n"
                        "• Revenue tracking across all creators\n\n"
                        "We're offering agencies a free 30-day trial. "
                        "After that, it's just 5% of the annual "
                        "subscription revenue from creators you onboard "
                        "— only when they commit to a year.\n\n"
                        "Would you be open to a quick demo?\n\n"
                        "Best,\nCorey Post\nFounder, Inoni LLC"
                    ),
                    "agent": "outreach_specialist",
                },
                {
                    "step": 2,
                    "delay_days": 3,
                    "subject": (
                        "Re: Content moderation automation for "
                        "{{agency_name}}"
                    ),
                    "body": (
                        "Hi {{agency_name}},\n\n"
                        "Just following up — wanted to share a quick "
                        "stat: agencies using automated moderation save "
                        "15+ hours/week per creator on manual content "
                        "review.\n\n"
                        "Murphy handles it all: flagging, scheduling, "
                        "fan engagement, compliance checks — and it "
                        "learns your preferences over time.\n\n"
                        "Happy to show you a 15-min demo whenever "
                        "works.\n\n"
                        "Corey"
                    ),
                    "agent": "outreach_specialist",
                },
                {
                    "step": 3,
                    "delay_days": 7,
                    "subject": (
                        "Last note — free automation for your agency"
                    ),
                    "body": (
                        "Hi {{agency_name}},\n\n"
                        "Last reach-out — I know you're busy. If "
                        "content moderation and scheduling automation "
                        "isn't a priority right now, no worries.\n\n"
                        "If it ever becomes one, we're at "
                        "murphy.inoni.com. The free trial is always "
                        "available.\n\n"
                        "Cheers,\nCorey"
                    ),
                    "agent": "outreach_specialist",
                },
            ],
            "individual_creator": [
                {
                    "step": 1,
                    "delay_days": 0,
                    "subject": (
                        "Free AI assistant for your content workflow"
                    ),
                    "body": (
                        "Hey {{creator_name}},\n\n"
                        "I built Murphy — an AI tool that automates "
                        "content moderation, scheduling, and fan "
                        "engagement for creators.\n\n"
                        "It's free if you're willing to mention us in "
                        "a post. Or $299/mo for the full Business suite.\n\n"
                        "Want to try it? Takes 5 minutes to set up."
                        "\n\nCorey\nInoni LLC"
                    ),
                    "agent": "outreach_specialist",
                },
                {
                    "step": 2,
                    "delay_days": 4,
                    "subject": "Re: Free content automation tool",
                    "body": (
                        "Hey {{creator_name}},\n\n"
                        "Quick follow-up — Murphy can auto-moderate "
                        "comments, schedule posts across platforms, "
                        "and even handle fan DMs with AI-personalized "
                        "responses.\n\n"
                        "Free tier available. Let me know if you want "
                        "a walkthrough.\n\nCorey"
                    ),
                    "agent": "outreach_specialist",
                },
            ],
            "streamer": [
                {
                    "step": 1,
                    "delay_days": 0,
                    "subject": (
                        "AI-powered stream moderation + "
                        "multi-platform automation"
                    ),
                    "body": (
                        "Hey {{streamer_name}},\n\n"
                        "I'm Corey from Inoni. We built Murphy — an "
                        "automation platform that handles stream "
                        "moderation, clip creation, and multi-platform "
                        "scheduling.\n\n"
                        "Works with Twitch, YouTube, Kick, and more. "
                        "Free if you're down to partner on marketing."
                        "\n\nInterested?\n\nCorey"
                    ),
                    "agent": "outreach_specialist",
                },
            ],
        }
        return sequences.get(target_type, sequences["individual_creator"])

    def handle_response(self, lead_email, response_text):
        """Route an inbound response to the appropriate shadow agent.

        The AI Communications Agent processes the response, qualifies
        intent, and routes to the right agent:
        - Interested → VP Sales (schedule demo)
        - Questions → Customer Success (answer questions)
        - Not interested → Log and move on
        - Pricing questions → CRO (pricing negotiation)
        """
        lower = response_text.lower()

        if any(
            w in lower
            for w in (
                "not interested", "unsubscribe", "stop", "no thanks",
            )
        ):
            return {
                "action": "close_lead",
                "agent": "outreach_specialist",
                "response": (
                    "Understood — removed from outreach. Best of luck!"
                ),
                "status": "closed_not_interested",
            }

        if any(
            w in lower
            for w in (
                "demo", "show me", "interested", "let's talk",
                "tell me more", "set up", "try it",
            )
        ):
            return {
                "action": "schedule_demo",
                "agent": "vp_sales",
                "response": (
                    "Great to hear! I'd love to show you what Murphy "
                    "can do. Are you free for a 15-minute demo this "
                    "week? Pick a time that works: [calendar_link]"
                ),
                "status": "demo_requested",
            }

        if any(
            w in lower
            for w in (
                "price", "cost", "how much", "pricing",
                "budget", "afford",
            )
        ):
            return {
                "action": "pricing_discussion",
                "agent": "chief_revenue_officer",
                "response": (
                    "Happy to walk through pricing. We have a few "
                    "options:\n\n"
                    "• Free tier — trade services for a marketing "
                    "mention\n"
                    "• Starter — $20/mo monthly\n"
                    "• Business — $299/mo flat rate\n"
                    "• Agency — Contact us for 10+ creators\n\n"
                    "Which sounds closest to what you need?"
                ),
                "status": "pricing_inquiry",
            }

        if any(
            w in lower
            for w in (
                "how", "what", "does it", "can it",
                "support", "help",
            )
        ):
            return {
                "action": "answer_questions",
                "agent": "customer_success_manager",
                "response": (
                    "Great question! Let me help. Murphy handles:\n\n"
                    "• AI content moderation (24/7 automated)\n"
                    "• Multi-platform scheduling\n"
                    "• Fan engagement automation\n"
                    "• Revenue tracking and analytics\n\n"
                    "What specific area are you most interested in?"
                ),
                "status": "questions",
            }

        return {
            "action": "clarify",
            "agent": "ai_communications",
            "response": (
                "Thanks for getting back to us! To make sure I point "
                "you to the right person — are you looking to:\n\n"
                "1. See a demo of the platform?\n"
                "2. Learn about pricing?\n"
                "3. Ask technical questions?\n\n"
                "Just reply with a number or describe what you need."
            ),
            "status": "awaiting_clarification",
        }

    # ------------------------------------------------------------------
    # EverQuest Let's Play — CRO-managed avatar agent sessions
    # ------------------------------------------------------------------

    def create_eq_lets_play_session(
        self,
        character_name,
        race="Human",
        eq_class="Warrior",
        server_name="Murphy EQ",
    ):
        """Create an EQ Let's Play session managed by the CRO.

        The Chief Research Officer (Kael Ashford) manages all EverQuest
        R&D, including avatar agent sessions where AI agents control named
        EQ characters in a content-creator-style "let's play" format.

        Each session creates an avatar window in the bottom-left corner
        showing the agent's face while it plays the character.
        """
        try:
            from src.eq.streaming_overlay import (
                LetsPlaySessionManager,
                StreamOverlayManager,
            )
        except ImportError:
            from eq.streaming_overlay import (
                LetsPlaySessionManager,
                StreamOverlayManager,
            )

        cro = self.agents.get("chief_research_officer")
        if cro is None:
            return {"error": "CRO not initialized — run bootstrap() first"}

        if not hasattr(self, "_lets_play_manager"):
            self._lets_play_manager = LetsPlaySessionManager(
                overlay_manager=StreamOverlayManager()
            )

        session = self._lets_play_manager.create_session(
            agent_id=cro["agent"].agent_id,
            agent_persona_name=cro["avatar_name"],
            character_name=character_name,
            race=race,
            eq_class=eq_class,
            server_name=server_name,
        )

        return {
            "session": session.to_dict(),
            "managed_by": {
                "role": "chief_research_officer",
                "name": cro["avatar_name"],
                "title": cro["avatar_title"],
            },
            "avatar_window": session.avatar_window.to_dict() if session.avatar_window else None,
        }

    def get_eq_sessions(self):
        """Return all EQ Let's Play sessions."""
        if not hasattr(self, "_lets_play_manager"):
            return {"sessions": [], "active": 0, "total": 0}
        mgr = self._lets_play_manager
        return {
            "sessions": [s.to_dict() for s in mgr.get_active_sessions()],
            "active": mgr.active_session_count,
            "total": mgr.session_count,
        }
