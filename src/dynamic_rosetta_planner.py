# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""DynamicRosettaPlanner — PATCH-360. Pick your team for THIS task."""

from __future__ import annotations
import hashlib, logging, re, time, uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("murphy.dynamic_rosetta")

@dataclass
class TaskProfile:
    domain: str
    complexity: str
    stake: str
    skills_needed: List[str]
    keywords: List[str]
    requires_hitl: bool
    requires_auditor: bool
    estimated_agents: int

@dataclass
class AgentBlueprint:
    agent_id: str
    role_class: str
    department: str
    reports_to: Optional[str]
    tone: str
    bias: str
    hitl_threshold: float
    capabilities: List[str]
    boundaries: List[str]
    task_brief: str
    emoji: str

@dataclass
class OrgNode:
    agent_id: str
    role_class: str
    reports_to: Optional[str]
    direct_reports: List[str] = field(default_factory=list)

@dataclass
class OrgChart:
    root_id: str
    nodes: Dict[str, OrgNode]
    depth: int
    def to_dict(self):
        return {
            "root": self.root_id,
            "depth": self.depth,
            "agents": {
                aid: {"role": n.role_class, "reports_to": n.reports_to, "direct_reports": n.direct_reports}
                for aid, n in self.nodes.items()
            }
        }

@dataclass
class DispatchPacket:
    team_id: str
    task_profile: TaskProfile
    team: List[AgentBlueprint]
    soul_contexts: Dict[str, str]
    org_chart: OrgChart
    coordinator_id: str
    created_at: str
    prompt: str
    def to_dict(self):
        return {
            "team_id": self.team_id,
            "domain": self.task_profile.domain,
            "complexity": self.task_profile.complexity,
            "stake": self.task_profile.stake,
            "agent_count": len(self.team),
            "coordinator": self.coordinator_id,
            "agents": [{"id": a.agent_id, "role": a.role_class, "dept": a.department,
                         "tone": a.tone, "brief": a.task_brief, "capabilities": a.capabilities}
                        for a in self.team],
            "org_chart": self.org_chart.to_dict(),
            "soul_loaded": list(self.soul_contexts.keys()),
        }

# Domain role templates: (role_class, dept, tone, bias, hitl_thresh, caps, bounds, emoji)
DOMAIN_ROLE_TEMPLATES: Dict[str, List[Tuple]] = {
    "exec_admin": [
        ("Coordinator",         "Operations",  "gracious",   "human_impact",   0.60, ["task routing","decision synthesis","team coordination"],             ["Escalate when uncertain","Revenue focus"], "👔"),
        ("Executive Analyst",   "Operations",  "precise",    "accuracy",       0.70, ["data synthesis","report generation","briefing"],                     ["Facts only","No speculation"], "📊"),
        ("Scheduler",           "Operations",  "methodical", "efficiency",     0.85, ["task ordering","gate clearance","rate limiting"],                    ["No task runs without gate clearance","HITL for high-risk"], "🗓️"),
        ("HITL Gate",           "Safety",      "cautious",   "caution",        0.00, ["approval routing","risk scoring","escalation"],                      ["When in doubt escalate","Never auto-approve external spend"], "🔴"),
        ("Auditor",             "Compliance",  "rigorous",   "accuracy",       0.95, ["compliance review","audit trail","policy check"],                    ["Zero tolerance for violations","Maintain audit trail"], "📋"),
    ],
    "sales": [
        ("Sales Coordinator",   "Revenue",     "decisive",   "conversion",     0.55, ["pipeline management","deal prioritization","team coordination"],     ["No spam","Personalize every touchpoint"], "💼"),
        ("CRM Analyst",         "Revenue",     "precise",    "accuracy",       0.75, ["deal analysis","pipeline scoring","contact research"],               ["Facts only","Flag stale deals"], "📈"),
        ("Outreach Writer",     "Revenue",     "creative",   "engagement",     0.65, ["email drafting","subject line optimization","follow-up sequencing"], ["Never send without human review for high-stake","No deceptive tactics"], "✉️"),
        ("Market Researcher",   "Intelligence","observant",  "completeness",   0.80, ["lead enrichment","competitor analysis","signal collection"],         ["Never discard a signal","Flag anomalies"], "🔍"),
        ("HITL Gate",           "Safety",      "cautious",   "caution",        0.00, ["approval routing","risk scoring","send authorization"],              ["Approve every external email send","No bulk without founder sign-off"], "🔴"),
    ],
    "engineering": [
        ("Lead Engineer",       "Engineering", "methodical", "system_health",  0.65, ["architecture design","code review","deployment planning"],           ["Stability first","One patch one thing","Test before ship"], "⚙️"),
        ("Code Executor",       "Engineering", "decisive",   "speed_safety",   0.70, ["code generation","patch application","API integration"],             ["Never execute without gate clearance","Log everything"], "⚡"),
        ("QA Auditor",          "Quality",     "rigorous",   "accuracy",       0.90, ["test generation","regression check","coverage analysis"],            ["Zero tolerance for untested deploys","Regression before ship"], "🧪"),
        ("Security Reviewer",   "Security",    "cautious",   "safety",         0.85, ["vulnerability scan","dependency audit","secret detection"],          ["Block on any credential exposure","HITL for security findings"], "🛡️"),
        ("HITL Gate",           "Safety",      "cautious",   "caution",        0.00, ["deploy approval","rollback decision","incident escalation"],         ["Approve every production deploy","Founder approval for rollback"], "🔴"),
    ],
    "compliance": [
        ("Compliance Lead",     "Compliance",  "rigorous",   "accuracy",       0.95, ["framework mapping","policy enforcement","team coordination"],        ["Zero tolerance for violations","Flag immediately"], "⚖️"),
        ("Legal Analyst",       "Legal",       "precise",    "risk_mitigation",0.85, ["regulation interpretation","risk assessment","contract review"],     ["No legal advice flag for counsel","Document everything"], "📜"),
        ("Data Privacy Officer","Privacy",     "cautious",   "data_safety",    0.90, ["GDPR audit","PII detection","data residency check"],                 ["Never allow unencrypted PII in transit","Log every access"], "🔒"),
        ("Auditor",             "Compliance",  "thorough",   "completeness",   0.95, ["audit trail","evidence collection","compliance reporting"],          ["Immutable log required","No action without audit entry"], "📋"),
        ("HITL Gate",           "Safety",      "cautious",   "caution",        0.00, ["compliance escalation","founder notification","policy block"],       ["Block on any compliance failure","Immediate escalation"], "🔴"),
    ],
    "finance": [
        ("Finance Coordinator", "Finance",     "precise",    "accuracy",       0.75, ["budget management","financial analysis","team coordination"],        ["No unauthorized spend","Document all financial decisions"], "💰"),
        ("Financial Analyst",   "Finance",     "methodical", "accuracy",       0.80, ["revenue modeling","cost analysis","projection generation"],         ["Facts only","Sensitivity analysis required for projections"], "📊"),
        ("Risk Assessor",       "Risk",        "cautious",   "risk_mitigation",0.85, ["scenario modeling","risk scoring","mitigation planning"],           ["Flag all high-risk scenarios","No decision without risk doc"], "⚠️"),
        ("Auditor",             "Compliance",  "rigorous",   "accuracy",       0.95, ["financial audit","SOX compliance","transaction review"],            ["Immutable audit trail","Flag irregularities immediately"], "📋"),
        ("HITL Gate",           "Safety",      "cautious",   "caution",        0.00, ["spend approval","wire authorization","budget override"],            ["Approve every spend over $100","Founder approval for over $1000"], "🔴"),
    ],
    "research": [
        ("Research Lead",       "Intelligence","observant",  "completeness",   0.70, ["hypothesis formation","source collection","synthesis"],             ["Cite sources","Flag uncertainty"], "🔭"),
        ("Data Collector",      "Intelligence","precise",    "accuracy",       0.80, ["web research","API data pull","corpus expansion"],                  ["Primary sources only","Never fabricate citations"], "📡"),
        ("Analyst",             "Intelligence","methodical", "accuracy",       0.75, ["pattern recognition","statistical analysis","insight generation"],  ["Show your work","Confidence intervals required"], "🧠"),
        ("Fact Checker",        "Quality",     "rigorous",   "accuracy",       0.90, ["claim verification","source validation","contradiction detection"], ["Flag unverifiable claims","No publication without check"], "✅"),
    ],
    "creative": [
        ("Creative Director",   "Creative",    "creative",   "engagement",     0.55, ["concept development","creative strategy","team direction"],         ["Brand voice above all","No offensive content"], "🎨"),
        ("Content Writer",      "Creative",    "creative",   "engagement",     0.65, ["copywriting","long-form content","headline generation"],            ["Never plagiarize","Match tone to audience"], "✍️"),
        ("Editor",              "Quality",     "precise",    "accuracy",       0.80, ["copy editing","fact checking","style consistency"],                 ["No publish without edit pass","Flag factual claims"], "📝"),
        ("Brand Auditor",       "Compliance",  "rigorous",   "accuracy",       0.90, ["brand compliance","tone review","trademark check"],                 ["Flag off-brand content","Legal review for trademark use"], "🔍"),
    ],
    "data": [
        ("Data Lead",           "Engineering", "methodical", "accuracy",       0.70, ["pipeline design","schema management","team coordination"],          ["Data integrity first","No schema change without migration plan"], "🗄️"),
        ("ETL Engineer",        "Engineering", "precise",    "speed_safety",   0.75, ["data transformation","pipeline execution","validation"],           ["Validate before load","Idempotent operations only"], "⚡"),
        ("Data Analyst",        "Intelligence","observant",  "completeness",   0.75, ["trend analysis","anomaly detection","reporting"],                   ["Show your work","Flag data quality issues"], "📊"),
        ("Privacy Auditor",     "Compliance",  "cautious",   "data_safety",    0.90, ["PII detection","retention policy","access audit"],                  ["No PII without consent","Log every access"], "🔒"),
    ],
    "prod_ops": [
        ("Ops Coordinator",     "Engineering", "methodical", "system_health",  0.65, ["incident coordination","deployment management","health monitoring"], ["Stability first","Rollback before blame"], "🔧"),
        ("Production Engineer", "Engineering", "decisive",   "speed_safety",   0.70, ["deploy execution","health checks","patch application"],             ["Never deploy without tests","Log all changes"], "⚡"),
        ("Incident Responder",  "Engineering", "cautious",   "safety",         0.75, ["incident triage","runbook execution","root cause analysis"],        ["Contain before fix","Communicate status every 15min"], "🚨"),
        ("SRE Monitor",         "Engineering", "observant",  "system_health",  0.80, ["telemetry analysis","alert triage","capacity planning"],            ["Page on SLO breach","Trend before threshold"], "📡"),
        ("HITL Gate",           "Safety",      "cautious",   "caution",        0.00, ["deploy approval","rollback decision","outage escalation"],          ["Approve every production deploy","Founder approval for major incident"], "🔴"),
    ],
    # PCR-035 BEGIN business_strategy team
    "business_strategy": [
        # role_class,         dept,          tone,        bias,             hitl, capabilities,                                                   bounds,                                         emoji
        ("Strategy Lead",     "Executive",   "decisive",  "synthesis",      0.55, ["task decomposition","cross-team coordination","prioritization"], ["No fluff","Every claim has evidence"],       "🎯"),
        ("Market Researcher", "Research",    "curious",   "evidence",       0.60, ["market sizing","competitive analysis","trend identification"],   ["Cite every source","Flag assumptions"],     "🔬"),
        ("Financial Analyst", "Finance",     "precise",   "accuracy",       0.65, ["unit economics","pricing modeling","projections"],               ["Show math","No hand-waving on numbers"],    "📊"),
        ("Product Architect", "Engineering", "rigorous",  "buildability",   0.55, ["system design","stack selection","integration mapping"],         ["Pick proven tech","Flag build vs buy"],     "🏗️"),
        ("Risk Assessor",     "Risk",        "skeptical", "risk_first",     0.50, ["risk identification","scenario planning","mitigation design"],   ["Surface every risk","Rank by impact"],      "⚠️"),
        ("HITL Gate",         "Governance",  "cautious",  "human_approval", 0.00, ["high-stake approvals","scope checks"],                            ["Block on critical","Defer to founder"],    "🚪"),
    ],
    # PCR-035 END business_strategy team
}
DOMAIN_ROLE_TEMPLATES["general"] = DOMAIN_ROLE_TEMPLATES["exec_admin"]

COMPLEXITY_TO_TEAM_SIZE = {"trivial": 1, "low": 2, "medium": 3, "high": 5, "critical": 5}

DOMAIN_SIGNALS: Dict[str, List[str]] = {
    "sales":       ["crm","deal","pipeline","prospect","outreach","email","follow-up","lead","conversion","close","revenue","quota","sales"],
    "engineering": ["code","deploy","patch","bug","api","endpoint","function","build","test","repo","git","server","database","backend","frontend","route","schema","migration","docker"],
    "compliance":  ["gdpr","hipaa","soc2","pci","sox","regulation","legal","compliance","audit","policy","privacy","data protection"],
    "finance":     ["budget","revenue","cost","invoice","payment","spend","forecast","financial","roi","margin","expense","profit"],
    "research":    ["research","analyze","investigate","find","lookup","study","market","competitive","intelligence","data collection"],
    "creative":    ["write","draft","copy","content","blog","post","article","creative","brand","messaging","narrative","story"],
    "data":        ["data","etl","pipeline","analytics","dashboard","report","metrics","kpi","visualization","sql","query","dataset"],
    "prod_ops":    ["deploy","health","incident","monitor","server","service","uptime","latency","error","log","alert","outage","sre"],
    "exec_admin":  ["schedule","meeting","brief","summary","status","report","approve","coordinate","plan","strategy","decide"],
    # PCR-035 BEGIN business_strategy domain
    # High-precision multi-word signals for business-plan / architecture /
    # strategy tasks. These should outweigh single-word signals like
    # "email" or "pipeline" that happen to appear in business prompts.
    "business_strategy": [
        "business plan","go-to-market","gtm","v0 architecture","tech stack",
        "icp","value prop","value proposition","competitive moat","wedge",
        "pricing model","unit economics","mrr","aov","ltv","cac",
        "case study","investor","fundraise","pitch deck","term sheet",
        "build a business","build a product","build an mvp","build a v0",
        "strategy for","business model","revenue model","go to market",
        "founding team","first 10 customers","early adopters",
        "highest-risk assumptions","riskiest assumption","validate first",
        "market sizing","tam","sam","som","competitive analysis",
    ],
    # PCR-035 END business_strategy domain
}

STAKE_SIGNALS: Dict[str, List[str]] = {
    "critical": ["production","founder","legal","security","breach","critical","emergency","outage","delete all","wipe","shutdown"],
    "high":     ["deploy","send email","external","payment","invoice","hire","fire","contract","gdpr","hipaa","compliance","financial"],
    "medium":   ["update","modify","change","create","build","generate","draft"],
    "low":      ["analyze","report","check","review","summarize","research"],
}

BRIEFS = {
    "Coordinator":            "Coordinate the team to complete this task.",
    "Sales Coordinator":      "Lead the sales team analysis and action.",
    "CRM Analyst":            "Analyze pipeline data for this task.",
    "Outreach Writer":        "Draft outreach content for this task.",
    "Market Researcher":      "Research signals and intelligence for this task.",
    "Lead Engineer":          "Architect and oversee engineering for this task.",
    "Code Executor":          "Write and execute code for this task.",
    "QA Auditor":             "Verify quality and correctness for this task.",
    "Security Reviewer":      "Scan for security risks in this task.",
    "Compliance Lead":        "Ensure all compliance requirements for this task.",
    "Legal Analyst":          "Assess legal and regulatory risk for this task.",
    "Data Privacy Officer":   "Audit data privacy requirements for this task.",
    "Finance Coordinator":    "Manage financial analysis and decisions for this task.",
    "Financial Analyst":      "Model and analyze financial data for this task.",
    "Risk Assessor":          "Identify and score risks for this task.",
    "Research Lead":          "Lead research and synthesis for this task.",
    "Data Collector":         "Gather all relevant data for this task.",
    "Analyst":                "Identify patterns and insights for this task.",
    "Creative Director":      "Direct creative strategy for this task.",
    "Content Writer":         "Write compelling content for this task.",
    "Editor":                 "Edit and verify quality for this task.",
    "Brand Auditor":          "Check brand compliance for this task.",
    "Data Lead":              "Lead data pipeline work for this task.",
    "ETL Engineer":           "Execute data transformations for this task.",
    "Data Analyst":           "Analyze trends and anomalies for this task.",
    "Privacy Auditor":        "Audit privacy compliance for this task.",
    "Ops Coordinator":        "Coordinate ops team for this task.",
    "Production Engineer":    "Execute production changes for this task.",
    "Incident Responder":     "Triage and respond to this incident.",
    "SRE Monitor":            "Monitor telemetry and alerts for this task.",
    "Auditor":                "Audit compliance and maintain trail for this task.",
    "Fact Checker":           "Verify all claims for this task.",
    "Scheduler":              "Schedule and sequence this task.",
    "Executive Analyst":      "Synthesize data and brief for this task.",
    "HITL Gate":              "Review and approve high-stake actions for this task.",
}


class DynamicRosettaPlanner:
    """Pick your team for THIS task. plan() returns a DispatchPacket."""

    def __init__(self, llm_controller=None):
        self._llm = llm_controller
        logger.info("[PATCH-360] DynamicRosettaPlanner initialized")

    def plan(self, prompt: str) -> DispatchPacket:
        t0 = time.time()
        team_id = "team_" + uuid.uuid4().hex[:8]
        profile = self.analyze_task(prompt)
        team    = self.select_team(profile, team_id)
        souls   = self.write_souls(team, prompt, profile)
        org     = self.build_org(team)
        packet  = DispatchPacket(
            team_id=team_id, task_profile=profile, team=team,
            soul_contexts=souls, org_chart=org,
            coordinator_id=org.root_id,
            created_at=datetime.now(timezone.utc).isoformat(),
            prompt=prompt,
        )
        logger.info("[PATCH-360] Packet ready in %.0fms — %d agents, domain=%s, coordinator=%s",
                    (time.time()-t0)*1000, len(team), profile.domain, org.root_id)
        return packet

    def analyze_task(self, prompt: str) -> TaskProfile:
        lower = prompt.lower()
        words = re.findall(r"\w+", lower)
        # PCR-035 BEGIN multi-word signal weighting
        # Multi-word signals (e.g. "business plan", "go-to-market") count
        # for 3 instead of 1 — they are higher precision than single words
        # which can appear incidentally in prompts.
        domain_scores: Dict[str, int] = {}
        for domain, signals in DOMAIN_SIGNALS.items():
            score = 0
            for s in signals:
                if s in lower:
                    score += 3 if " " in s or "-" in s else 1
            if score > 0:
                domain_scores[domain] = score
        # PCR-035 END multi-word signal weighting
        domain = max(domain_scores, key=domain_scores.get) if domain_scores else "exec_admin"

        stake = "low"
        for tier in ("critical", "high", "medium", "low"):
            if any(s in lower for s in STAKE_SIGNALS.get(tier, [])):
                stake = tier
                break

        wc = len(words)
        if wc < 8 or stake == "low":
            complexity = "trivial"
        elif wc < 20 and stake in ("low", "medium"):
            complexity = "low"
        elif wc < 50 or stake == "medium":
            complexity = "medium"
        elif wc < 100 or stake == "high":
            complexity = "high"
        else:
            complexity = "critical"

        SKILL_HINTS = {
            "email_drafting":  ["email","draft","write","send","outreach"],
            "data_analysis":   ["analyze","analysis","data","metrics","report"],
            "code_generation": ["code","function","api","endpoint","script"],
            "legal_review":    ["legal","compliance","regulation","contract"],
            "financial_model": ["budget","cost","revenue","forecast","roi"],
            "research":        ["research","find","investigate","lookup"],
            "deployment":      ["deploy","ship","release","patch","push"],
            "scheduling":      ["schedule","calendar","meeting","book"],
        }
        skills_needed = [sk for sk, hints in SKILL_HINTS.items()
                         if any(h in lower for h in hints)] or ["task_execution"]

        STOPWORDS = {"the","a","an","and","or","for","to","of","in","is","be","with",
                     "that","this","it","on","at","by","from","as","are","was","were",
                     "will","can","do","please","me","my","i","we","you","our"}
        keywords = [w for w in words if len(w) > 3 and w not in STOPWORDS][:8]

        return TaskProfile(
            domain=domain, complexity=complexity, stake=stake,
            skills_needed=skills_needed, keywords=keywords,
            requires_hitl=stake in ("high","critical"),
            requires_auditor=domain in ("compliance","finance","legal") or stake == "critical",
            estimated_agents=COMPLEXITY_TO_TEAM_SIZE.get(complexity, 3),
        )

    def select_team(self, profile: TaskProfile, team_id: str) -> List[AgentBlueprint]:
        templates = DOMAIN_ROLE_TEMPLATES.get(profile.domain, DOMAIN_ROLE_TEMPLATES["general"])
        n = profile.estimated_agents
        regular   = [t for t in templates if t[0] != "HITL Gate"]
        hitl_tmpl = next((t for t in templates if t[0] == "HITL Gate"), None)
        selected  = regular[:n]
        if profile.requires_hitl and hitl_tmpl:
            if len(selected) < 5:
                selected.append(hitl_tmpl)
            else:
                selected[-1] = hitl_tmpl

        team: List[AgentBlueprint] = []
        coordinator_id: Optional[str] = None
        for i, tmpl in enumerate(selected):
            role_class, dept, tone, bias, hitl_thresh, caps, bounds, emoji = tmpl
            slug = role_class.lower().replace(" ", "_")
            uid  = hashlib.md5((team_id + "_" + role_class).encode()).hexdigest()[:6]
            agent_id = slug + "_" + uid
            is_coord = (i == 0)
            if is_coord:
                coordinator_id = agent_id
            brief = BRIEFS.get(role_class, "Execute " + role_class + " work on this task.")
            team.append(AgentBlueprint(
                agent_id=agent_id, role_class=role_class, department=dept,
                reports_to=coordinator_id if not is_coord else None,
                tone=tone, bias=bias, hitl_threshold=hitl_thresh,
                capabilities=caps, boundaries=bounds,
                task_brief=brief, emoji=emoji,
            ))
        return team

    def write_souls(self, team: List[AgentBlueprint], prompt: str, profile: TaskProfile) -> Dict[str, str]:
        return {a.agent_id: self._render_soul(a, profile) for a in team}

    def _render_soul(self, agent: AgentBlueprint, profile: TaskProfile) -> str:
        """
        PATCH-385 — Load full layered Deep Soul (L0-L4) from entity_graph.db.

        Rosetta has NO token limit. Layer selection is by relevance to the
        agent's role and the task domain. Full soul stack is returned —
        every layer that exists for this agent is included, no truncation.
        """
        try:
            from src.deep_soul_engine import build_deep_soul

            # Build the full layered soul — no budget cap
            soul_layers = build_deep_soul(
                agent_id=agent.agent_id,
                role_title=agent.role_class,
                domain=getattr(profile, "domain", "operations"),
                person_id=getattr(agent, "shadows_person_id", None),
                project_ids=getattr(profile, "project_ids", None) or [],
                include_gmail_context=False,  # PATCH-385: gmail injection happens at task time, not render
            )

            # full_soul key already concatenates L0+L1+L2+L3+L4
            # If missing (older deep_soul_engine), build it ourselves
            if "full_soul" in soul_layers and soul_layers["full_soul"]:
                return soul_layers["full_soul"]

            return "\n\n".join(
                soul_layers.get(layer, "")
                for layer in ("L0", "L1", "L2", "L3", "L4")
                if soul_layers.get(layer)
            )
        except Exception as e:
            logger.warning(
                "[PATCH-385] Deep soul load failed for %s — falling back to stub: %s",
                agent.agent_id, e,
            )
            # Fallback to a minimal soul (NOT the old 95-word version — just identity)
            return (
                f"# AGENT — {agent.agent_id}\n"
                f"**Role:** {agent.role_class}\n"
                f"**Reports to:** {agent.reports_to or 'CEO'}\n"
                f"**Task domain:** {getattr(profile, 'domain', 'operations')}\n"
            )

    def build_org(self, team: List[AgentBlueprint]) -> OrgChart:
        nodes: Dict[str, OrgNode] = {}
        root_id: Optional[str] = None
        for agent in team:
            nodes[agent.agent_id] = OrgNode(
                agent_id=agent.agent_id, role_class=agent.role_class,
                reports_to=agent.reports_to,
            )
            if agent.reports_to is None:
                root_id = agent.agent_id
        for agent in team:
            if agent.reports_to and agent.reports_to in nodes:
                nodes[agent.reports_to].direct_reports.append(agent.agent_id)

        def _depth(nid: str, d: int = 0) -> int:
            n = nodes.get(nid)
            if not n or not n.direct_reports:
                return d
            return max(_depth(r, d+1) for r in n.direct_reports)

        rid = root_id or (team[0].agent_id if team else "unknown")
        return OrgChart(root_id=rid, nodes=nodes, depth=_depth(rid))
